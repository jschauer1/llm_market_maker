"""Collect official forecast, first-release, and Kalshi receipts for ING-1."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Callable

import requests

from tools.atomic_write import write_json
from tools.db import connect, utcnow
from tools.kalshi.markets import BASE_URL
from tools import snapshot

from .data import (
    DataError, SCHEMA_VERSION, SERIES_MEASURE, entry_for, normalize_candle,
    parse_bls_archive_index, parse_bls_first_release, parse_contract, parse_nowcasts,
)


CAMPAIGN = Path(__file__).resolve().parent / "backtests" / "ing1-20260905"
ROOT = Path(__file__).resolve().parents[2]
CLEVELAND_URL = "https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json?sc_lang=en"
BLS_INDEX_URL = "https://www.bls.gov/bls/news-release/cpi.htm"
HISTORICAL_MARKETS_URL = f"{BASE_URL}/historical/markets"
SERIES = tuple(SERIES_MEASURE)
START_TARGET = "2013-07"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _get_bytes(url: str, attempts: int = 5) -> bytes:
    delay, last = 1.0, None
    for attempt in range(attempts):
        try:
            response = requests.get(url, timeout=60, headers={
                "User-Agent": "Mozilla/5.0 market-edge-finder source audit",
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            })
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(delay)
                delay *= 2
    raise RuntimeError(f"GET {url} failed after {attempts} attempts: {last}") from last


def _raw_source(path: Path, url: str, fetch_bytes: Callable[[str], bytes]) -> tuple[bytes, dict]:
    if not path.exists():
        _write_bytes(path, fetch_bytes(url))
    content = path.read_bytes()
    return content, {"path": _source_path(path), "url": url, "sha256": _sha_bytes(content),
                     "byte_length": len(content)}


def _cached_json(path: Path, url: str, params: dict, fetch_json: Callable) -> tuple[object, dict]:
    if path.exists():
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if wrapper.get("url") != url or wrapper.get("params") != params:
            raise DataError(f"cached request identity changed at {path}")
    else:
        wrapper = {"fetched_at": utcnow(), "url": url, "params": params,
                   "response": fetch_json(url, params=params)}
        write_json(path, wrapper, indent=2, sort_keys=True)
    receipt = {"path": _source_path(path), "url": url, "params": params,
               "fetched_at": wrapper.get("fetched_at"), "sha256": _sha_bytes(path.read_bytes())}
    return wrapper.get("response"), receipt


def _requests_json(url: str, *, params: dict) -> object:
    delay, last = 1.0, None
    for attempt in range(5):
        try:
            response = requests.get(url, params=params, timeout=60,
                                    headers={"User-Agent": "market-edge-finder/1.0"})
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt < 4:
                time.sleep(delay)
                delay *= 2
    raise RuntimeError(f"GET {url} failed after 5 attempts: {last}") from last


def make_training_rows(
    nowcasts: dict[str, dict[str, dict[str, str]]],
    releases: dict[str, dict],
    forecast_digest: str,
) -> tuple[list[dict], dict[str, int]]:
    """Join only exact pre-release Cleveland rows to first BLS publications."""
    rows, excluded = [], Counter()
    for target, release in sorted(releases.items()):
        vintages = nowcasts.get(target)
        if not vintages:
            excluded["missing_target_nowcast"] += 1
            continue
        published = datetime.fromisoformat(release["published_at"])
        try:
            cutoff = entry_for(published, list(vintages))
        except (DataError, ValueError):
            excluded["missing_prior_source_business_day"] += 1
            continue
        observation = cutoff.date().isoformat()
        values = vintages.get(observation)
        if not values:
            excluded["missing_exact_cutoff_nowcast"] += 1
            continue
        for series, measure in SERIES_MEASURE.items():
            actual_key = "headline" if series == "KXCPI" else "core"
            rows.append({
                "series_ticker": series, "measure": measure, "target_month": target,
                "cutoff_ts": cutoff.isoformat(), "forecast_observation_date": observation,
                "forecast_value": values[measure], "actual_value": release[actual_key],
                "actual_published_at": release["published_at"],
                "forecast_source_digest": forecast_digest,
                "label_source_digest": release["sha256"],
            })
    return rows, dict(sorted(excluded.items()))


def _collect_bls(campaign: Path, fetch_bytes: Callable[[str], bytes]) -> tuple[dict[str, dict], list[dict], list[dict]]:
    raw_dir = campaign / "raw" / "bls"
    index_bytes, index_receipt = _raw_source(raw_dir / "cpi_archive_index.html", BLS_INDEX_URL, fetch_bytes)
    archive = [row for row in parse_bls_archive_index(index_bytes.decode("utf-8", errors="replace"))
               if row["target_month"] >= START_TARGET]
    releases, receipts, source_rows = {}, [index_receipt], []

    def one(row: dict) -> tuple[dict, bytes, dict]:
        path = raw_dir / f"{row['target_month']}.html"
        content, receipt = _raw_source(path, row["url"], fetch_bytes)
        return row, content, receipt

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(one, row) for row in archive]
        for future in as_completed(futures):
            row, content, receipt = future.result()
            parsed = parse_bls_first_release(content.decode("utf-8", errors="replace"), row["target_month"])
            release = {**row, **parsed, "sha256": receipt["sha256"], "receipt_path": receipt["path"]}
            if datetime.fromisoformat(parsed["published_at"]).date().isoformat() != row["release_date"]:
                raise DataError(f"BLS index/body release date mismatch for {row['target_month']}")
            releases[row["target_month"]] = release
            receipts.append(receipt)
            source_rows.append({**receipt, "release_date": row["release_date"],
                                "target_month": row["target_month"]})
    return releases, sorted(source_rows, key=lambda row: row["target_month"]), receipts


def _market_pages(campaign: Path, series: str, fetch_json: Callable) -> tuple[list[tuple[dict, dict]], list[dict]]:
    cursor, page, seen, rows, receipts = "", 0, set(), [], []
    while True:
        page += 1
        params: dict[str, object] = {"series_ticker": series, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        path = campaign / "raw" / "kalshi" / "markets" / series / f"page-{page:04d}.json"
        payload, receipt = _cached_json(path, HISTORICAL_MARKETS_URL, params, fetch_json)
        receipts.append(receipt)
        if not isinstance(payload, dict) or not isinstance(payload.get("markets"), list):
            raise DataError(f"malformed Kalshi market page for {series}")
        rows.extend((raw, receipt) for raw in payload["markets"])
        next_cursor = payload.get("cursor") or ""
        if not next_cursor:
            return rows, receipts
        if not isinstance(next_cursor, str) or next_cursor in seen:
            raise DataError("Kalshi pagination cursor is invalid or repeated")
        seen.add(next_cursor)
        cursor = next_cursor


def _cached_open_board(campaign: Path) -> tuple[list[tuple[dict, dict]], list[dict]]:
    """Copy the freshest stored CPI rows without triggering a board refresh."""
    conn = connect()
    try:
        row = conn.execute("SELECT MAX(last_seen_at) stamp FROM market_snapshots WHERE platform='kalshi'").fetchone()
        stamp = row["stamp"] if row else None
        if not stamp:
            return [], []
        raw_rows = conn.execute(
            "SELECT raw_json FROM market_snapshots WHERE platform='kalshi' AND last_seen_at=?", (stamp,)
        ).fetchall()
        markets = []
        for raw_row in raw_rows:
            raw = json.loads(snapshot.payload_text(raw_row["raw_json"]) or "{}")
            ticker = str(raw.get("ticker") or "")
            if ticker.split("-", 1)[0] in SERIES:
                markets.append(raw)
    finally:
        conn.close()
    path = campaign / "raw" / "kalshi" / "cached_open_board.json"
    wrapper = {"captured_at": stamp, "copied_at": utcnow(), "markets": markets}
    if path.exists():
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        markets = wrapper.get("markets", [])
    else:
        write_json(path, wrapper, indent=2, sort_keys=True)
    receipt = {"path": _source_path(path), "url": "local:cached-board", "fetched_at": wrapper.get("captured_at"),
               "sha256": _sha_bytes(path.read_bytes())}
    return [(raw, receipt) for raw in markets if isinstance(raw, dict)], [receipt]


def collect(
    campaign_dir: str | Path = CAMPAIGN, *, fetch_bytes: Callable[[str], bytes] = _get_bytes,
    fetch_json: Callable = _requests_json, workers: int = 8,
) -> dict:
    campaign = Path(campaign_dir)
    protocol = campaign / "PROTOCOL.md"
    if not protocol.exists():
        raise FileNotFoundError(protocol)
    protocol_digest = _sha_bytes(protocol.read_bytes())

    cleveland_bytes, cleveland_receipt = _raw_source(
        campaign / "raw" / "cleveland" / "nowcast_month.json", CLEVELAND_URL, fetch_bytes)
    cleveland_payload = json.loads(cleveland_bytes)
    nowcasts = parse_nowcasts(cleveland_payload)
    comments = {str(row.get("chart", {}).get("_comment")) for row in cleveland_payload if isinstance(row, dict)}
    if len(comments) != 1:
        raise DataError("Cleveland payload does not have one common comment timestamp")

    releases, bls_sources, receipts = _collect_bls(campaign, fetch_bytes)
    receipts.append(cleveland_receipt)
    training_rows, training_exclusions = make_training_rows(nowcasts, releases, cleveland_receipt["sha256"])

    inventory: dict[str, dict] = {}
    exclusions = Counter()
    for series in SERIES:
        source_rows, source_receipts = _market_pages(campaign, series, fetch_json)
        receipts.extend(source_receipts)
        for raw, receipt in source_rows:
            parsed, reason = parse_contract(raw)
            if reason:
                exclusions[reason] += 1
                continue
            ticker = raw.get("ticker")
            if not isinstance(ticker, str):
                exclusions["ticker_missing"] += 1
                continue
            candidate = {"raw": raw, "parsed": parsed, "tier": "historical", "receipt": receipt}
            prior = inventory.get(ticker)
            if prior and _canonical(prior["raw"]) != _canonical(raw):
                inventory.pop(ticker, None)
                exclusions["conflicting_duplicate"] += 1
            elif ticker not in inventory:
                inventory[ticker] = candidate
    cached_rows, cached_receipts = _cached_open_board(campaign)
    receipts.extend(cached_receipts)
    for raw, receipt in cached_rows:
        parsed, reason = parse_contract(raw)
        if reason:
            exclusions[f"cached_{reason}"] += 1
            continue
        ticker = raw.get("ticker")
        if isinstance(ticker, str) and ticker not in inventory:
            inventory[ticker] = {"raw": raw, "parsed": parsed, "tier": "cached", "receipt": receipt}

    jobs, candles, reasons, candle_receipts = [], {}, {}, {}
    for ticker, item in inventory.items():
        release = releases.get(item["parsed"]["target_month"])
        vintages = nowcasts.get(item["parsed"]["target_month"], {})
        if not release:
            reasons[ticker] = "missing_bls_release"
            continue
        try:
            entry = entry_for(datetime.fromisoformat(release["published_at"]), list(vintages))
        except DataError:
            reasons[ticker] = "missing_prior_source_business_day"
            continue
        close_raw = item["raw"].get("close_time")
        try:
            closed = datetime.fromisoformat(str(close_raw).replace("Z", "+00:00"))
        except ValueError:
            reasons[ticker] = "close_time_invalid"
            continue
        if closed <= entry.astimezone(timezone.utc):
            reasons[ticker] = "market_closed_by_entry"
            continue
        if item["tier"] != "historical":
            reasons[ticker] = "cached_open_entry_not_historical"
            continue
        jobs.append((ticker, item, int(entry.timestamp())))

    def candle_job(job):
        ticker, item, stamp = job
        url = f"{BASE_URL}/historical/markets/{ticker}/candlesticks"
        params = {"start_ts": stamp - 3600, "end_ts": stamp, "period_interval": 60}
        path = campaign / "raw" / "kalshi" / "candles" / f"{ticker}.json"
        payload, receipt = _cached_json(path, url, params, fetch_json)
        try:
            return ticker, [normalize_candle(payload, stamp)], None, receipt
        except DataError as exc:
            return ticker, [], str(exc), receipt

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(candle_job, job) for job in jobs]
        for future in as_completed(futures):
            ticker, bars, reason, receipt = future.result()
            candles[ticker], reasons[ticker], candle_receipts[ticker] = bars, reason, receipt
            receipts.append(receipt)

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in inventory.values():
        grouped[(item["parsed"]["series_ticker"], item["parsed"]["event_ticker"])].append(item)
    events = []
    for (series, event_ticker), items in sorted(grouped.items()):
        target = items[0]["parsed"]["target_month"]
        release = releases.get(target)
        vintages = nowcasts.get(target, {})
        if not release or not vintages:
            exclusions["event_missing_release_or_forecast"] += 1
            continue
        try:
            entry = entry_for(datetime.fromisoformat(release["published_at"]), list(vintages))
        except DataError:
            exclusions["event_missing_prior_source_business_day"] += 1
            continue
        observed = entry.date().isoformat()
        measure = SERIES_MEASURE[series]
        if observed not in vintages or measure not in vintages[observed]:
            exclusions["event_missing_exact_forecast"] += 1
            continue
        items.sort(key=lambda item: item["raw"]["ticker"])
        events.append({
            "series_ticker": series, "event_ticker": event_ticker, "target_month": target,
            "release_ts": release["published_at"], "entry_ts": entry.isoformat(),
            "forecast": {"measure": measure, "observation_date": observed,
                         "cutoff_ts": entry.isoformat(), "value": vintages[observed][measure],
                         "source_digest": cleveland_receipt["sha256"]},
            "markets": [item["raw"] for item in items],
            "candles": {item["raw"]["ticker"]: candles.get(item["raw"]["ticker"], []) for item in items},
            "candle_reasons": {item["raw"]["ticker"]: reasons.get(item["raw"]["ticker"]) for item in items},
            "entry_activity": {item["raw"]["ticker"]: {
                "volume": (candles.get(item["raw"]["ticker"]) or [{}])[0].get("volume"),
                "bar_end_ts": (candles.get(item["raw"]["ticker"]) or [{}])[0].get("end_ts"),
            } for item in items},
            "market_sources": {item["raw"]["ticker"]: {
                "inventory_tier": item["tier"], "inventory_receipt_path": item["receipt"]["path"],
                "inventory_receipt_digest": item["receipt"]["sha256"],
                "record_digest": _sha_bytes(_canonical(item["raw"])),
                "candle_receipt_path": candle_receipts.get(item["raw"]["ticker"], {}).get("path"),
                "candle_receipt_digest": candle_receipts.get(item["raw"]["ticker"], {}).get("sha256"),
            } for item in items},
        })

    receipts = sorted({(row["path"], row["sha256"]): row for row in receipts}.values(), key=lambda row: row["path"])
    critical = {"training_rows": training_rows, "events": events, "receipts": receipts}
    source_digest = _sha_bytes(_canonical(critical))
    coverage = {
        "cleveland_target_months": len(nowcasts), "bls_first_releases": len(releases),
        "training_rows": len(training_rows), "training_release_dates": len({r["actual_published_at"] for r in training_rows}),
        "training_by_series": {series: sum(r["series_ticker"] == series for r in training_rows) for series in SERIES},
        "training_exclusions": training_exclusions, "kalshi_events": len(events),
        "kalshi_markets": sum(len(row["markets"]) for row in events),
        "markets_with_exact_candle": sum(bool(bars) for event in events for bars in event["candles"].values()),
        "markets_missing_exact_candle": sum(not bars for event in events for bars in event["candles"].values()),
        "market_exclusions": dict(sorted(exclusions.items())),
    }
    collected_at = utcnow()
    dataset = {
        "schema_version": SCHEMA_VERSION, "campaign": campaign.name, "collected_at": collected_at,
        "protocol_digest": protocol_digest, "source_digest": source_digest,
        "sources": {
            "cleveland": {**cleveland_receipt, "fetched_at": collected_at,
                          "payload_comment": next(iter(comments))},
            "bls": bls_sources,
            "kalshi": {"receipts": [row for row in receipts if "/kalshi/" in row["path"]]},
        },
        "training_rows": training_rows, "events": events, "coverage": coverage,
        "_receipts": receipts,
    }
    write_json(campaign / "dataset.json", dataset, indent=2, sort_keys=True)
    write_json(campaign / "manifest.json", {
        "schema_version": SCHEMA_VERSION, "completed_at": utcnow(), "protocol_digest": protocol_digest,
        "source_digest": source_digest, "dataset_digest": _sha_bytes((campaign / "dataset.json").read_bytes()),
        "coverage": coverage,
    }, indent=2, sort_keys=True)
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=CAMPAIGN)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(collect(args.campaign, workers=args.workers)["coverage"], indent=2))


if __name__ == "__main__":
    main()
