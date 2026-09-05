"""Collect the frozen TRG-1 TSA archive diagnostic without evaluating returns."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import time
from typing import Callable

import requests

from tools.atomic_write import write_json, write_text
from tools.db import utcnow
from tools.http import get_json
from tools.kalshi.markets import BASE_URL

from .data import DataError, entry_for, normalize_candle, parse_contract, parse_tsa_html


START = date(2022, 6, 19)
END = date(2026, 8, 30)
YEARS = range(2019, 2027)
SERIES = ("KXTSAW", "TSAW")
CAMPAIGN = Path(__file__).resolve().parent / "backtests" / "trg1-20260905"
SOURCES = Path(__file__).resolve().parent / "sources"
ROOT = Path(__file__).resolve().parents[2]
CURRENT_MARKETS = f"{BASE_URL}/markets"
HISTORICAL_MARKETS = f"{BASE_URL}/historical/markets"
CURRENT_CANDLES = f"{BASE_URL}/markets/candlesticks"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(value: object) -> str:
    return _sha_bytes(_canonical(value))


def _source_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _cached_json(path: Path, url: str, params: dict, fetch: Callable) -> tuple[object, dict]:
    if path.exists():
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if wrapper.get("url") != url or wrapper.get("params") != params:
            raise DataError(f"cached request identity changed at {path}")
    else:
        wrapper = {"fetched_at": utcnow(), "url": url, "params": params, "response": fetch(url, params=params)}
        write_json(path, wrapper, indent=2, sort_keys=True)
    receipt = {"path": _source_path(path), "sha256": _sha_bytes(path.read_bytes()), "url": url}
    return wrapper.get("response"), receipt


def _get_html(url: str, *, attempts: int = 5) -> bytes:
    delay = 1.0
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, timeout=30, headers={"User-Agent": "market-edge-finder/1.0"})
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(delay)
                delay *= 2
    raise RuntimeError(f"GET {url} failed after {attempts} attempts: {last}") from last


def _tsa_counts(campaign: Path, fetch_html: Callable[[str], bytes]) -> tuple[dict[str, int], list[dict]]:
    counts: dict[str, int] = {}
    receipts = []
    for year in YEARS:
        url = f"https://www.tsa.gov/travel/passenger-volumes/{year}" if year != 2026 else "https://www.tsa.gov/travel/passenger-volumes"
        source = SOURCES / f"tsa_{year}.html"
        if not source.exists():
            source = campaign / "raw" / "tsa" / f"tsa_{year}.html"
            if not source.exists():
                content = fetch_html(url)
                write_text(source, content.decode("utf-8"))
        payload = source.read_bytes()
        parsed = parse_tsa_html(payload.decode("utf-8"), year)
        for day, number in parsed.items():
            if day in counts and counts[day] != number:
                raise DataError(f"conflicting TSA count for {day}")
            counts[day] = number
        receipts.append({"path": _source_path(source), "sha256": _sha_bytes(payload), "url": url})
    return dict(sorted(counts.items())), receipts


def _pages(campaign: Path, series: str, tier: str, fetch: Callable) -> tuple[list[tuple[dict, dict]], list[dict]]:
    url = CURRENT_MARKETS if tier == "current" else HISTORICAL_MARKETS
    cursor = ""
    rows, receipts, seen = [], [], set()
    page = 0
    while True:
        page += 1
        params = {"series_ticker": series, "limit": 1000}
        if tier == "current":
            params["status"] = "settled"
        if cursor:
            params["cursor"] = cursor
        path = campaign / "raw" / "markets" / tier / series / f"page-{page:04d}.json"
        payload, receipt = _cached_json(path, url, params, fetch)
        receipts.append(receipt)
        if not isinstance(payload, dict) or not isinstance(payload.get("markets"), list):
            raise DataError(f"{tier} market page is malformed")
        rows.extend((raw, receipt) for raw in payload["markets"])
        new_cursor = payload.get("cursor") or ""
        if not isinstance(new_cursor, str):
            raise DataError("market cursor is not a string")
        if not new_cursor:
            return rows, receipts
        if new_cursor in seen:
            raise DataError("market pagination repeated a cursor")
        seen.add(new_cursor)
        cursor = new_cursor


_CONTRACT_KEYS = ("ticker", "event_ticker", "rules_primary", "rules_secondary", "open_time", "strike_type", "floor_strike")


def _identity(row: dict) -> dict:
    return {key: row.get(key) for key in _CONTRACT_KEYS}


def _progress(campaign: Path, **values) -> None:
    path = campaign / "progress.json"
    current = json.loads(path.read_text()) if path.exists() else {}
    current.update(values)
    current["updated_at"] = utcnow()
    write_json(path, current, indent=2, sort_keys=True)


def _calendar() -> list[date]:
    return [START + timedelta(days=7 * i) for i in range(((END - START).days // 7) + 1)]


def collect(
    campaign: str | Path = CAMPAIGN,
    *,
    fetch: Callable = get_json,
    fetch_html: Callable[[str], bytes] = _get_html,
    workers: int = 8,
) -> dict:
    campaign = Path(campaign)
    protocol = campaign / "PROTOCOL.md"
    if not protocol.exists():
        raise FileNotFoundError(protocol)
    campaign.mkdir(parents=True, exist_ok=True)
    _progress(campaign, stage="tsa")
    daily_counts, receipts = _tsa_counts(campaign, fetch_html)

    inventory: dict[str, dict] = {}
    excluded = Counter()
    duplicate_tickers = []
    conflicting_tickers = set()
    for series in SERIES:
        for tier in ("current", "historical"):
            rows, page_receipts = _pages(campaign, series, tier, fetch)
            receipts.extend(page_receipts)
            for raw, row_receipt in rows:
                if not isinstance(raw, dict) or not isinstance(raw.get("ticker"), str):
                    raise DataError("market inventory contains a malformed row")
                parsed, reason = parse_contract(raw)
                if reason:
                    excluded[reason] += 1
                    continue
                week_end = parsed["week_end"]
                if not START <= week_end <= END:
                    continue
                ticker = raw["ticker"]
                if ticker in conflicting_tickers:
                    continue
                candidate = {"raw": raw, "parsed": parsed, "tier": tier, "series": series,
                             "receipt_path": row_receipt["path"], "record_digest": _sha(raw)}
                prior = inventory.get(ticker)
                if prior is None:
                    inventory[ticker] = candidate
                else:
                    duplicate_tickers.append(ticker)
                    if _identity(prior["raw"]) != _identity(raw):
                        inventory.pop(ticker, None)
                        conflicting_tickers.add(ticker)
                        excluded["conflicting_duplicate"] += 1
                    elif tier == "historical":
                        inventory[ticker] = candidate

    grouped: dict[tuple[date, str], list[dict]] = defaultdict(list)
    for item in inventory.values():
        grouped[(item["parsed"]["week_end"], item["raw"]["event_ticker"])].append(item)
    for items in grouped.values():
        items.sort(key=lambda item: item["raw"]["ticker"])
    _progress(campaign, stage="candles", events=len(grouped), markets=len(inventory))

    candles: dict[str, dict | None] = {}
    candle_reasons: dict[str, str | None] = {}
    candle_receipts: dict[str, dict] = {}
    historical_jobs = []
    current_groups: dict[tuple[date, str], list[str]] = defaultdict(list)
    for item in inventory.values():
        ticker = item["raw"]["ticker"]
        close_value = item["raw"].get("close_time")
        try:
            closed_at = datetime.fromisoformat(str(close_value).replace("Z", "+00:00"))
        except ValueError:
            candles[ticker], candle_reasons[ticker] = None, "close_time_invalid"
            continue
        entry_dt = entry_for(item["parsed"]["week_end"])
        if closed_at <= entry_dt:
            candles[ticker], candle_reasons[ticker] = None, "market_closed_by_entry"
        elif item["tier"] == "historical":
            historical_jobs.append(item)
        else:
            current_groups[(item["parsed"]["week_end"], item["series"])].append(ticker)

    def historical_job(item: dict):
        ticker = item["raw"]["ticker"]
        entry = int(entry_for(item["parsed"]["week_end"]).timestamp())
        url = f"{BASE_URL}/historical/markets/{ticker}/candlesticks"
        params = {"start_ts": entry - 3600, "end_ts": entry, "period_interval": 60}
        path = campaign / "raw" / "candles" / "historical" / f"{ticker}.json"
        payload, receipt = _cached_json(path, url, params, fetch)
        try:
            return ticker, normalize_candle(payload, entry), None, receipt
        except DataError as exc:
            return ticker, None, str(exc), receipt

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(historical_job, item) for item in historical_jobs]
        for index, future in enumerate(as_completed(futures), 1):
            ticker, candle, reason, receipt = future.result()
            candles[ticker], candle_reasons[ticker], candle_receipts[ticker] = candle, reason, receipt
            receipts.append(receipt)
            if index % 50 == 0:
                _progress(campaign, stage="candles", historical_complete=index, historical_total=len(futures))

    for (week_end, series), tickers in sorted(current_groups.items()):
        entry = int(entry_for(week_end).timestamp())
        for offset in range(0, len(tickers), 100):
            chunk = sorted(tickers)[offset:offset + 100]
            params = {"market_tickers": ",".join(chunk), "start_ts": entry - 3600, "end_ts": entry, "period_interval": 60}
            path = campaign / "raw" / "candles" / "current" / f"{week_end}-{series}-{offset // 100 + 1:03d}.json"
            payload, receipt = _cached_json(path, CURRENT_CANDLES, params, fetch)
            receipts.append(receipt)
            returned = {}
            if not isinstance(payload, dict) or not isinstance(payload.get("markets"), list):
                raise DataError("current candle batch is malformed")
            for group in payload["markets"]:
                if not isinstance(group, dict) or group.get("market_ticker") not in chunk:
                    raise DataError("current candle batch returned an unexpected ticker")
                returned[group["market_ticker"]] = group
            for ticker in chunk:
                candle_receipts[ticker] = receipt
                try:
                    candles[ticker] = normalize_candle(returned.get(ticker, {"candlesticks": []}), entry)
                    candle_reasons[ticker] = None
                except DataError as exc:
                    candles[ticker], candle_reasons[ticker] = None, str(exc)

    events = []
    weeks_present = defaultdict(list)
    for (week_end, event_ticker), items in sorted(grouped.items()):
        weeks_present[week_end].append(event_ticker)
        events.append({
            "week_end": week_end.isoformat(),
            "event_ticker": event_ticker,
            "entry_time": entry_for(week_end).isoformat().replace("+00:00", "Z"),
            "markets": [item["raw"] for item in items],
            "candles": {item["raw"]["ticker"]: candles.get(item["raw"]["ticker"]) for item in items},
            "candle_reasons": {item["raw"]["ticker"]: candle_reasons.get(item["raw"]["ticker"]) for item in items},
            "inventory_sources": {item["raw"]["ticker"]: {
                "inventory_tier": item["tier"], "series_query": item["series"],
                "receipt_path": item["receipt_path"], "record_digest": item["record_digest"],
                "candle_receipt_path": candle_receipts.get(item["raw"]["ticker"], {}).get("path"),
                "candle_receipt_digest": candle_receipts.get(item["raw"]["ticker"], {}).get("sha256"),
            } for item in items},
        })

    calendar = [{"week_end": day.isoformat(), "event_tickers": sorted(weeks_present[day]),
                 "reason": None if weeks_present[day] else "no_explicit_source_event"} for day in _calendar()]
    receipts = sorted({(r["path"], r["sha256"], r["url"]): r for r in receipts}.values(), key=lambda r: r["path"])
    source_digest = _sha(receipts)
    coverage = {
        "calendar_weeks": len(calendar), "calendar": calendar,
        "event_records": len(events), "markets": sum(len(e["markets"]) for e in events),
        "missing_event_weeks": [row["week_end"] for row in calendar if row["reason"]],
        "duplicate_tickers": sorted(set(duplicate_tickers)),
        "exclusions": dict(sorted(excluded.items())),
        "markets_with_exact_candle": sum(c is not None for e in events for c in e["candles"].values()),
        "markets_missing_exact_candle": sum(c is None for e in events for c in e["candles"].values()),
        "receipts": receipts,
    }
    dataset = {
        "schema_version": 1, "source_as_of": utcnow(), "source_validated": False,
        "historical_publication_claim": False, "daily_counts": daily_counts,
        "events": events, "coverage": coverage, "source_digest": source_digest,
        "protocol_digest": _sha_bytes(protocol.read_bytes()),
    }
    write_json(campaign / "dataset.json", dataset, indent=2, sort_keys=True)
    write_json(campaign / "manifest.json", {
        "schema_version": 1, "completed_at": utcnow(), "source_validated": False,
        "historical_publication_claim": False, "coverage": coverage,
        "source_digest": source_digest, "protocol_digest": dataset["protocol_digest"],
        "dataset_digest": _sha_bytes((campaign / "dataset.json").read_bytes()),
    }, indent=2, sort_keys=True)
    _progress(campaign, stage="complete", events=len(events), markets=coverage["markets"])
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=CAMPAIGN)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(collect(args.campaign, workers=args.workers)["coverage"], indent=2))


if __name__ == "__main__":
    main()
