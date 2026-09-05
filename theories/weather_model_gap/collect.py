"""Checkpoint and normalize the frozen WG-1 weather replay sources."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

from tools.atomic_write import write_json
from tools.db import utcnow
from tools.http import HttpError, get_json
from tools.kalshi.markets import BASE_URL

from .data import normalize_label
from .stations import STATIONS


CURRENT_MARKETS_URL = f"{BASE_URL}/markets"
HISTORICAL_MARKETS_URL = f"{BASE_URL}/historical/markets"
CURRENT_CANDLES_URL = f"{BASE_URL}/markets/candlesticks"
FORECAST_URL = "https://single-runs-api.open-meteo.com/v1/forecast"
TWC_METADATA_URL = "https://weather.com/kalshi/api/climate/primary"
NWS_STATION_URL = "https://api.weather.gov/stations/{station}"
MODEL = "ecmwf_ifs"
PERIOD_INTERVAL = 60
DEFAULT_START = date(2026, 3, 1)
DEFAULT_END = date(2026, 8, 31)
DEFAULT_CAMPAIGN = Path(__file__).resolve().parent / "backtests" / "wg1-20260905"
MONTHS = {name: number for number, name in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1
)}


class SourceDataError(ValueError):
    """A source returned data that cannot satisfy the frozen replay contract."""


class _SourceFetchError(RuntimeError):
    """A checkpointed HTTP failure for an exact immutable source request."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _cached_fetch(path: Path, url: str, params: dict, fetch) -> object:
    if path.exists():
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if wrapper.get("url") != url or wrapper.get("params") != params:
            raise SourceDataError(f"cached request identity changed at {path}")
        if wrapper.get("fetch_error"):
            raise _SourceFetchError(str(wrapper["fetch_error"]))
        return wrapper.get("response")
    payload = fetch(url, params=params)
    write_json(path, {
        "fetched_at": utcnow(), "url": url, "params": params, "response": payload,
    }, indent=2, sort_keys=True)
    return payload


def _finite(value: object, label: str) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise SourceDataError(f"{label} is boolean")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SourceDataError(f"{label} is not numeric") from exc
    if not math.isfinite(number):
        raise SourceDataError(f"{label} is not finite")
    return number


def normalize_candle_response(payload: object, entry_ts: int) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("candlesticks"), list):
        raise SourceDataError("candle response has no candlesticks list")
    rows = payload["candlesticks"]
    if not rows:
        return []
    matches = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise SourceDataError("candle row is not an object")
        ts = raw.get("end_period_ts")
        if isinstance(ts, bool) or not isinstance(ts, (int, float)) or not float(ts).is_integer():
            raise SourceDataError("candle has invalid end timestamp")
        if int(ts) == entry_ts:
            matches.append(raw)
    if len(matches) != 1:
        raise SourceDataError("candle response must contain one bar ending at exact entry")
    raw = matches[0]

    def quote(group: str) -> float | None:
        block = raw.get(group)
        if block is None:
            return None
        if not isinstance(block, dict):
            raise SourceDataError(f"{group} is not an object")
        return _finite(block.get("close_dollars", block.get("close")), f"{group}.close")

    return [{
        "end_ts": entry_ts,
        "yes_bid_close": quote("yes_bid"),
        "yes_ask_close": quote("yes_ask"),
        "volume": _finite(raw.get("volume_fp", raw.get("volume")), "volume"),
        "open_interest": _finite(raw.get("open_interest_fp", raw.get("open_interest")), "open_interest"),
    }]


def _normalize_candle_or_missing(payload: object, entry_ts: int) -> tuple[list[dict], str | None]:
    """Keep a malformed/non-entry response visible without aborting the census."""
    try:
        return normalize_candle_response(payload, entry_ts), None
    except SourceDataError as exc:
        return [], str(exc)


def _parse_naive_hour(value: object) -> datetime:
    if not isinstance(value, str):
        raise SourceDataError("forecast time is not a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SourceDataError(f"invalid forecast time {value!r}") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def normalize_forecast_response(
    payload: object, request: dict, station: dict, target_date: date
) -> dict:
    if not isinstance(payload, dict):
        raise SourceDataError("forecast response is not an object")
    params = request.get("params") if isinstance(request, dict) else None
    if not isinstance(params, dict):
        raise SourceDataError("forecast request params are missing")
    expected_run = datetime.combine(target_date - timedelta(days=1), time(12), timezone.utc)
    run_value = params.get("run")
    try:
        requested_run = datetime.fromisoformat(str(run_value)).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise SourceDataError("invalid requested forecast run") from exc
    if requested_run != expected_run:
        raise SourceDataError("forecast request is not the prior-day 12Z run")
    if params.get("timezone") not in {"GMT", "UTC"}:
        raise SourceDataError("forecast request timezone is not GMT")
    if payload.get("utc_offset_seconds") != 0 or payload.get("timezone") not in {"GMT", "UTC"}:
        raise SourceDataError("forecast response is not UTC/GMT")
    units = payload.get("hourly_units")
    if not isinstance(units, dict) or units.get("temperature_2m") not in {"°F", "F"}:
        raise SourceDataError("forecast temperature units are not Fahrenheit")
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise SourceDataError("forecast response has no hourly object")
    times = hourly.get("time")
    temperatures = hourly.get("temperature_2m")
    if not isinstance(times, list) or not isinstance(temperatures, list) or len(times) != len(temperatures) or not times:
        raise SourceDataError("forecast hourly arrays are missing or unequal")
    parsed_times = [_parse_naive_hour(value) for value in times]
    if parsed_times[0] != expected_run.replace(tzinfo=None):
        raise SourceDataError("forecast returned run does not match requested run")
    if len(set(parsed_times)) != len(parsed_times):
        raise SourceDataError("forecast contains duplicate hourly times")
    by_time = dict(zip(parsed_times, temperatures))
    start_hour = -int(station["standard_utc_offset_hours"])
    standard_start = datetime.combine(target_date, time(), None) + timedelta(hours=start_hour)
    selected = []
    for step in range(24):
        stamp = standard_start + timedelta(hours=step)
        if stamp not in by_time:
            raise SourceDataError(f"forecast is missing standard-day hour {stamp.isoformat()}")
        value = _finite(by_time[stamp], f"temperature at {stamp.isoformat()}")
        if value is None:
            raise SourceDataError(f"missing temperature at {stamp.isoformat()}")
        selected.append(value)
    identity = {"request": request, "raw_response": payload}
    return {
        "raw_response": payload,
        "run": expected_run.isoformat(),
        "request": request,
        "source_digest": _sha(identity),
        "standard_day_temperature_f": selected,
        "reason": None,
    }


def _target_date(event_ticker: object) -> date | None:
    if not isinstance(event_ticker, str):
        return None
    token = event_ticker.rsplit("-", 1)[-1].upper()
    if len(token) != 7 or not token[:2].isdigit() or not token[5:].isdigit():
        return None
    month = MONTHS.get(token[2:5])
    if month is None:
        return None
    try:
        return date(2000 + int(token[:2]), month, int(token[5:]))
    except ValueError:
        return None


def _pages(series: str, source: str, campaign: Path, fetch) -> tuple[list[dict], int]:
    url = CURRENT_MARKETS_URL if source == "current" else HISTORICAL_MARKETS_URL
    cursor = ""
    seen = set()
    rows = []
    page = 0
    while True:
        page += 1
        params = {"series_ticker": series, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        payload = _cached_fetch(campaign / "raw" / "markets" / source / series / f"page-{page:04d}.json", url, params, fetch)
        if not isinstance(payload, dict) or not isinstance(payload.get("markets"), list):
            raise SourceDataError(f"{source} market page has no markets list")
        for row in payload["markets"]:
            if not isinstance(row, dict) or not row.get("ticker") or not row.get("event_ticker"):
                raise SourceDataError(f"{source} market page has malformed market")
            rows.append(row)
        new_cursor = payload.get("cursor") or ""
        if not isinstance(new_cursor, str):
            raise SourceDataError("market cursor is not a string")
        if not new_cursor:
            return rows, page
        if new_cursor == cursor or new_cursor in seen:
            raise SourceDataError(f"market pagination repeated cursor {new_cursor!r}")
        seen.add(new_cursor)
        cursor = new_cursor


def _validate_station_metadata(series: Iterable[str], campaign: Path, fetch) -> None:
    selected = [STATIONS[item] for item in series]
    twc = _cached_fetch(campaign / "raw" / "stations" / "twc.json", TWC_METADATA_URL, {"date": "2026-09-03"}, fetch)
    if not isinstance(twc, dict) or not isinstance(twc.get("results"), list):
        raise SourceDataError("TWC station metadata has no results list")
    pairs = set()
    for row in twc["results"]:
        station = row.get("station") if isinstance(row, dict) else None
        if isinstance(station, dict):
            pairs.add((station.get("cliId"), station.get("icao")))
    for expected in selected:
        if (expected["cli_id"], expected["station"]) not in pairs:
            raise SourceDataError(f"TWC station metadata does not map {expected['cli_id']} to {expected['station']}")
        url = NWS_STATION_URL.format(station=expected["station"])
        raw = _cached_fetch(campaign / "raw" / "stations" / f"{expected['station']}.json", url, {}, fetch)
        if not isinstance(raw, dict):
            raise SourceDataError(f"NWS metadata for {expected['station']} is malformed")
        props = raw.get("properties") or {}
        geometry = raw.get("geometry") or {}
        coordinates = geometry.get("coordinates")
        elevation = props.get("elevation") or {}
        if props.get("stationIdentifier") != expected["station"] or not isinstance(coordinates, list) or len(coordinates) < 2:
            raise SourceDataError(f"NWS metadata identity mismatch for {expected['station']}")
        if abs(float(coordinates[0]) - expected["longitude"]) > 1e-5 or abs(float(coordinates[1]) - expected["latitude"]) > 1e-5 or abs(float(elevation.get("value")) - expected["elevation"]) > 1e-4:
            raise SourceDataError(f"NWS pinned coordinate/elevation mismatch for {expected['station']}")


def _forecast_for_date(target: date, series: tuple[str, ...], campaign: Path, fetch) -> dict[str, dict]:
    stations = [STATIONS[item] for item in series]
    run = datetime.combine(target - timedelta(days=1), time(12)).strftime("%Y-%m-%dT%H:%M")
    params = {
        "latitude": ",".join(str(item["latitude"]) for item in stations),
        "longitude": ",".join(str(item["longitude"]) for item in stations),
        "elevation": ",".join(str(item["elevation"]) for item in stations),
        "hourly": "temperature_2m",
        "temperature_unit": "fahrenheit",
        "timezone": "GMT",
        "models": MODEL,
        "forecast_days": 3,
        "run": run,
    }
    raw_path = campaign / "raw" / "forecasts" / f"{target.isoformat()}.json"
    if raw_path.exists():
        saved = json.loads(raw_path.read_text(encoding="utf-8"))
        verified = False
        if saved.get("fetch_error") and saved.get("permanent") is not True:
            for receipt_path in campaign.glob("audit-open-meteo-*.json"):
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                response = receipt.get("response") or {}
                if (receipt.get("http_status") == 400
                        and receipt.get("params") == params
                        and response.get("error") is True
                        and "requested model run is not available" in str(response.get("reason", "")).lower()):
                    verified = True
                    break
        if (saved.get("fetch_error") and saved.get("permanent") is not True
                and not verified):
            # Older/transient receipts do not become immutable missing runs.
            # Retrying the identical request preserves the frozen protocol.
            raw_path.unlink()
    fetch_error: str | None = None
    try:
        raw = _cached_fetch(raw_path, FORECAST_URL, params, fetch)
    except _SourceFetchError as exc:
        fetch_error = str(exc)
    except HttpError as exc:
        if raw_path.exists():
            # Corrupt checkpoints and request-identity mismatches are local
            # integrity failures, not missing provider coverage.
            raise
        if "status 400" not in str(exc):
            # Rate limits, timeouts and server errors can recover. They remain
            # uncheckpointed so a resumed collection performs the same call.
            raise
        # A genuinely absent archived run is a source-coverage fact, not a
        # license to substitute another initialization. Persist the failed
        # immutable request and keep every affected event in the denominator.
        if not raw_path.exists():
            write_json(raw_path, {
                "fetched_at": utcnow(),
                "url": FORECAST_URL,
                "params": params,
                "response": None,
                "fetch_error": f"{type(exc).__name__}: {exc}",
                "permanent": True,
            }, indent=2, sort_keys=True)
        fetch_error = f"{type(exc).__name__}: {exc}"
    if fetch_error is not None:
        wrapper = json.loads(raw_path.read_text(encoding="utf-8"))
        reason = f"forecast_source_error: {wrapper.get('fetch_error') or fetch_error}"
        output = {}
        expected_run = datetime.combine(target - timedelta(days=1), time(12), timezone.utc).isoformat()
        for index, name in enumerate(series):
            request = {"url": FORECAST_URL, "params": params, "location_index": index}
            output[name] = {
                "raw_response": None,
                "run": expected_run,
                "request": request,
                "source_digest": _sha({"request": request, "fetch_error": reason}),
                "standard_day_temperature_f": [],
                "reason": reason,
            }
        return output
    payloads = raw if isinstance(raw, list) else [raw]
    if len(payloads) != len(series):
        raise SourceDataError(f"forecast batch for {target} returned {len(payloads)} locations, expected {len(series)}")
    output = {}
    for index, name in enumerate(series):
        request = {"url": FORECAST_URL, "params": params, "location_index": index}
        output[name] = normalize_forecast_response(payloads[index], request, STATIONS[name], target)
    return output


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*.json") if path.is_file())
    if not files:
        raise SourceDataError("source tree is empty")
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _progress(campaign: Path, **values) -> None:
    current = {}
    path = campaign / "progress.json"
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
    if values.get("stage") != "failed":
        current.pop("last_error", None)
    current.update(values)
    current["updated_at"] = utcnow()
    write_json(path, current, indent=2, sort_keys=True)


def collect(
    campaign: str | Path = DEFAULT_CAMPAIGN,
    *,
    fetch=get_json,
    series: Iterable[str] = tuple(STATIONS),
    start_date: date = DEFAULT_START,
    end_date: date = DEFAULT_END,
    protocol_path: str | Path | None = None,
    workers: int = 8,
) -> dict:
    campaign = Path(campaign)
    names = tuple(series)
    if not names or any(name not in STATIONS for name in names):
        raise ValueError("series must be a non-empty subset of STATIONS")
    if start_date > end_date:
        raise ValueError("start_date must not follow end_date")
    protocol = Path(protocol_path) if protocol_path else campaign / "PROTOCOL.md"
    if not protocol.exists():
        raise FileNotFoundError(protocol)
    campaign.mkdir(parents=True, exist_ok=True)
    try:
        _progress(campaign, stage="station_metadata")
        _validate_station_metadata(names, campaign, fetch)

        inventory: dict[str, dict] = {}
        pages = {"current": 0, "historical": 0}
        duplicates = 0
        for name in names:
            for source in ("current", "historical"):
                rows, count = _pages(name, source, campaign, fetch)
                pages[source] += count
                for raw in rows:
                    ticker = raw["ticker"]
                    if ticker in inventory:
                        duplicates += 1
                        inventory[ticker]["sources"].add(source)
                        if source == "historical":
                            inventory[ticker]["raw"] = raw
                    else:
                        inventory[ticker] = {"raw": raw, "series_ticker": name, "sources": {source}}

        grouped: dict[str, list[dict]] = defaultdict(list)
        source_by_ticker = {}
        for ticker, item in inventory.items():
            raw = item["raw"]
            target = _target_date(raw.get("event_ticker"))
            if target is not None and start_date <= target <= end_date:
                grouped[raw["event_ticker"]].append(raw)
                source_by_ticker[ticker] = set(item["sources"])
        for rows in grouped.values():
            rows.sort(key=lambda row: row["ticker"])
        _progress(campaign, stage="forecasts", inventory_markets=len(inventory), events=len(grouped))

        all_dates = [start_date + timedelta(days=step) for step in range((end_date - start_date).days + 1)]
        forecasts = {}
        for index, target in enumerate(all_dates, 1):
            forecasts[target] = _forecast_for_date(target, names, campaign, fetch)
            if index % 10 == 0 or index == len(all_dates):
                _progress(campaign, stage="forecasts", forecasts_complete=index, forecasts_total=len(all_dates))

        candle_jobs = []
        candles: dict[str, list[dict]] = {}
        candle_errors: dict[str, str] = {}
        current_groups: dict[date, list[str]] = defaultdict(list)
        for event_ticker, rows in grouped.items():
            target = _target_date(event_ticker)
            assert target is not None
            entry = int(datetime.combine(target, time(), timezone.utc).timestamp())
            for row in rows:
                ticker = row["ticker"]
                if "historical" in source_by_ticker[ticker]:
                    candle_jobs.append((ticker, entry))
                else:
                    current_groups[target].append(ticker)

        def historical_job(job):
            ticker, entry = job
            params = {"start_ts": entry - 3600, "end_ts": entry, "period_interval": PERIOD_INTERVAL}
            url = f"{BASE_URL}/historical/markets/{ticker}/candlesticks"
            raw = _cached_fetch(campaign / "raw" / "candles" / "historical" / f"{ticker}.json", url, params, fetch)
            if not isinstance(raw, dict):
                raise SourceDataError(f"historical candle response for {ticker} is malformed")
            if raw.get("ticker") not in (None, ticker):
                raise SourceDataError(f"historical candle response identifies the wrong ticker for {ticker}")
            normalized, reason = _normalize_candle_or_missing(raw, entry)
            return ticker, normalized, reason

        _progress(campaign, stage="candles", historical_total=len(candle_jobs))
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            future_map = {pool.submit(historical_job, job): job[0] for job in candle_jobs}
            for index, future in enumerate(as_completed(future_map), 1):
                ticker, normalized, reason = future.result()
                candles[ticker] = normalized
                if reason is not None:
                    candle_errors[ticker] = reason
                if index % 50 == 0 or index == len(future_map):
                    _progress(campaign, stage="candles", historical_complete=index, historical_total=len(future_map))

        current_requests = 0
        for target in sorted(current_groups):
            entry = int(datetime.combine(target, time(), timezone.utc).timestamp())
            tickers = sorted(current_groups[target])
            for chunk_index in range(0, len(tickers), 100):
                chunk = tickers[chunk_index:chunk_index + 100]
                params = {"market_tickers": ",".join(chunk), "start_ts": entry - 3600, "end_ts": entry, "period_interval": PERIOD_INTERVAL}
                raw = _cached_fetch(campaign / "raw" / "candles" / "current" / f"{target.isoformat()}-{chunk_index // 100 + 1:03d}.json", CURRENT_CANDLES_URL, params, fetch)
                current_requests += 1
                if not isinstance(raw, dict) or not isinstance(raw.get("markets"), list):
                    raise SourceDataError("current candle batch has no markets list")
                returned = {}
                for group in raw["markets"]:
                    ticker = group.get("market_ticker") if isinstance(group, dict) else None
                    if ticker not in chunk or ticker in returned:
                        raise SourceDataError(f"current candle batch has unexpected ticker {ticker!r}")
                    returned[ticker] = group
                for ticker in chunk:
                    normalized, reason = _normalize_candle_or_missing(
                        returned.get(ticker, {"candlesticks": []}), entry
                    )
                    candles[ticker] = normalized
                    if ticker not in returned:
                        candle_errors[ticker] = "ticker omitted from current candle response"
                    elif reason is not None:
                        candle_errors[ticker] = reason

        events = []
        for event_ticker in sorted(grouped, key=lambda item: (_target_date(item), item)):
            markets = grouped[event_ticker]
            name = str(markets[0].get("series_ticker") or event_ticker.split("-", 1)[0])
            target = _target_date(event_ticker)
            assert target is not None
            events.append({
                "event_ticker": event_ticker,
                "series_ticker": name,
                "station": STATIONS[name]["station"],
                "target_date": target.isoformat(),
                "markets": markets,
                "candles": {row["ticker"]: candles.get(row["ticker"], []) for row in markets},
                "candle_errors": {row["ticker"]: candle_errors[row["ticker"]] for row in markets if row["ticker"] in candle_errors},
                "forecast": forecasts[target][name],
                "label": normalize_label(markets, STATIONS[name]),
            })

        reasons = Counter(event["label"]["reason"] or "usable" for event in events)
        per_series = Counter(event["series_ticker"] for event in events)
        missing_candles = sum(not bars for event in events for bars in event["candles"].values())
        coverage = {
            "events": len(events),
            "events_by_series": dict(sorted(per_series.items())),
            "inventory_markets": len(inventory),
            "in_window_markets": sum(len(event["markets"]) for event in events),
            "market_pages": pages,
            "inventory_duplicates": duplicates,
            "labels": dict(sorted(reasons.items())),
            "forecast_events_complete": sum(event["forecast"].get("reason") is None for event in events),
            "markets_with_entry_candle": sum(bool(bars) for event in events for bars in event["candles"].values()),
            "markets_missing_entry_candle": missing_candles,
            "candle_source_errors": dict(sorted(candle_errors.items())),
            "historical_candle_requests": len(candle_jobs),
            "current_candle_requests": current_requests,
        }
        dataset = {
            "events": events,
            "coverage": coverage,
            "source_digest": _tree_digest(campaign / "raw"),
            "protocol_digest": hashlib.sha256(protocol.read_bytes()).hexdigest(),
        }
        write_json(campaign / "dataset.json", dataset, indent=2, sort_keys=True)
        manifest = {**coverage, "source_digest": dataset["source_digest"], "protocol_digest": dataset["protocol_digest"], "completed_at": utcnow()}
        write_json(campaign / "manifest.json", manifest, indent=2, sort_keys=True)
        _progress(campaign, stage="complete", **coverage)
        return dataset
    except Exception as exc:
        _progress(campaign, stage="failed", last_error=f"{type(exc).__name__}: {exc}")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument("--start-date", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end-date", type=date.fromisoformat, default=DEFAULT_END)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    result = collect(args.campaign, start_date=args.start_date, end_date=args.end_date, workers=args.workers)
    print(json.dumps(result["coverage"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
