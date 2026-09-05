"""Collect the frozen ND-1 recurring chart cohort without reading returns.

The campaign enumerates both sides of Kalshi's live/historical cutoff, saves
every raw response, and requests one fixed daily-candle window for every
enumerated ticker.  The resulting SQLite file deliberately uses the same two
tables as ``db/history_cache.db`` so the theory-local replay can consume it.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3
from typing import Iterable

from tools.db import utcnow
from tools.http import get_json
from tools.kalshi.markets import BASE_URL


SERIES = (
    "KXALBUMEQUIV",
    "KXPUREALBUMS",
    "KXTOPSONG",
    "KXBILLBOARDRUNNERUPSONG",
    "KXTOPALBUM",
    "KXBILLBOARDRUNNERUPALBUM",
)
EXPECTED_CATEGORY = "Entertainment"
PERIOD_INTERVAL = 1440
START_TS = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
END_TS = int(datetime(2026, 8, 18, tzinfo=timezone.utc).timestamp())
MAX_BATCH_TICKERS = 100
MAX_BATCH_CANDLES = 10_000
EXPECTED_DAILY_BARS = (END_TS - START_TS) // 86_400 + 1
LIVE_BATCH_SIZE = min(
    MAX_BATCH_TICKERS,
    max(1, MAX_BATCH_CANDLES // EXPECTED_DAILY_BARS),
)
DEFAULT_CAMPAIGN = (
    Path(__file__).resolve().parent / "backtests" / "nd1-charts-20260905"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    ticker          TEXT    NOT NULL,
    period_interval INTEGER NOT NULL,
    start_ts        INTEGER NOT NULL,
    end_ts          INTEGER NOT NULL,
    series_ticker   TEXT,
    fetched_at      TEXT    NOT NULL,
    payload         TEXT    NOT NULL,
    PRIMARY KEY (ticker, period_interval)
);
CREATE TABLE IF NOT EXISTS settled_markets (
    ticker        TEXT PRIMARY KEY,
    series_ticker TEXT,
    close_time    TEXT,
    fetched_at    TEXT NOT NULL,
    payload       TEXT NOT NULL
);
"""


def _atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True), encoding="utf-8"
    )
    temp.replace(path)


def _cached_fetch(path: Path, url: str, params: dict, fetch) -> dict:
    """Return a checkpointed response, refusing to reuse it for another call."""
    if path.exists():
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if wrapper.get("url") != url or wrapper.get("params") != params:
            raise ValueError(f"cached request identity changed at {path}")
        payload = wrapper.get("response")
        if not isinstance(payload, dict):
            raise ValueError(f"cached response is malformed at {path}")
        return payload

    payload = fetch(url, params=params)
    if not isinstance(payload, dict):
        raise ValueError(f"API response for {url} is not an object")
    _atomic_json(path, {
        "fetched_at": utcnow(),
        "url": url,
        "params": params,
        "response": payload,
    })
    return payload


def connect_cache(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    return conn


def paginated_markets(
    series_ticker: str,
    source: str,
    directory: Path,
    *,
    fetch=get_json,
) -> tuple[list[dict], int]:
    """Walk one series to a terminal cursor and checkpoint every raw page."""
    if source not in {"live", "historical"}:
        raise ValueError(f"unknown market source {source!r}")
    url = (
        f"{BASE_URL}/markets"
        if source == "live"
        else f"{BASE_URL}/historical/markets"
    )
    rows: list[dict] = []
    cursor = ""
    page = 0
    while True:
        page += 1
        params = {"series_ticker": series_ticker, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        payload = _cached_fetch(
            directory / f"page-{page:04d}.json", url, params, fetch
        )
        markets = payload.get("markets")
        if not isinstance(markets, list):
            raise ValueError(f"{source} page {page} has no markets list")
        for raw in markets:
            if not isinstance(raw, dict) or not raw.get("ticker"):
                raise ValueError(
                    f"{source} page {page} contains a market without a ticker"
                )
            reported_series = raw.get("series_ticker")
            if reported_series not in (None, "", series_ticker):
                raise ValueError(
                    f"{raw['ticker']} belongs to {reported_series}, not {series_ticker}"
                )
            rows.append(raw)
        new_cursor = payload.get("cursor") or ""
        if not isinstance(new_cursor, str):
            raise ValueError(f"{source} page {page} returned a non-string cursor")
        if not new_cursor:
            return rows, page
        if new_cursor == cursor:
            raise RuntimeError(
                f"{source} pagination returned the same cursor {cursor!r} twice"
            )
        cursor = new_cursor


def collect_series_metadata(
    series: Iterable[str], campaign: Path, *, fetch=get_json
) -> dict:
    """Capture exchange category metadata and surface every non-Entertainment row."""
    categories: dict[str, str] = {}
    conflicts: dict[str, str | None] = {}
    raw_dir = Path(campaign) / "raw" / "series"
    for ticker in series:
        url = f"{BASE_URL}/series/{ticker}"
        payload = _cached_fetch(raw_dir / f"{ticker}.json", url, {}, fetch)
        raw = payload.get("series")
        if not isinstance(raw, dict) or raw.get("ticker") != ticker:
            raise ValueError(f"series metadata response does not identify {ticker}")
        category = raw.get("category")
        if isinstance(category, str) and category.strip():
            categories[ticker] = category.strip()
        if category != EXPECTED_CATEGORY:
            conflicts[ticker] = category if isinstance(category, str) else None
    artifact = {
        "captured_at": utcnow(),
        "categories": categories,
        "conflicts": conflicts,
    }
    _atomic_json(Path(campaign) / "series_categories.json", artifact)
    return artifact


def _number(value, label: str) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{label} is boolean")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not numeric: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} is not finite: {value!r}")
    return number


def _nested(raw: dict, group: str, field: str) -> float | None:
    block = raw.get(group)
    if block is None:
        return None
    if not isinstance(block, dict):
        raise ValueError(f"candle {group} is not an object")
    value = block.get(f"{field}_dollars", block.get(field))
    return _number(value, f"{group}.{field}")


def normalize_candles(
    raw_rows: list[dict], *, start_ts: int = START_TS, end_ts: int = END_TS
) -> list[dict]:
    """Normalize both current and historical schemas inside the frozen window."""
    if not isinstance(raw_rows, list):
        raise ValueError("candlesticks is not a list")
    out = []
    seen = set()
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ValueError("candlestick row is not an object")
        ts = raw.get("end_period_ts")
        if isinstance(ts, bool) or not isinstance(ts, (int, float)):
            raise ValueError(f"invalid end_period_ts {ts!r}")
        if not float(ts).is_integer():
            raise ValueError(f"invalid end_period_ts {ts!r}")
        ts = int(ts)
        if not start_ts <= ts <= end_ts:
            raise ValueError(
                f"candle timestamp {ts} is outside frozen window "
                f"[{start_ts}, {end_ts}]"
            )
        if ts in seen:
            raise ValueError(f"duplicate end_period_ts {ts}")
        seen.add(ts)
        out.append({
            "end_ts": ts,
            "open": _nested(raw, "price", "open"),
            "high": _nested(raw, "price", "high"),
            "low": _nested(raw, "price", "low"),
            "close": _nested(raw, "price", "close"),
            "mean": _nested(raw, "price", "mean"),
            "yes_bid_close": _nested(raw, "yes_bid", "close"),
            "yes_ask_close": _nested(raw, "yes_ask", "close"),
            "volume": _number(
                raw.get("volume_fp", raw.get("volume")), "volume"
            ),
            "open_interest": _number(
                raw.get("open_interest_fp", raw.get("open_interest")),
                "open_interest",
            ),
        })
    return sorted(out, key=lambda row: row["end_ts"])


def _store_candles(
    conn: sqlite3.Connection, ticker: str, series_ticker: str, rows: list[dict],
    *, start_ts: int = START_TS, end_ts: int = END_TS,
) -> None:
    with conn:
        conn.execute(
            "REPLACE INTO candles (ticker, period_interval, start_ts, end_ts, "
            "series_ticker, fetched_at, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticker, PERIOD_INTERVAL, start_ts, end_ts, series_ticker,
             utcnow(), json.dumps(rows, sort_keys=True)),
        )


def _parse_iso_ts(value) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.timestamp()


def _calendar_exclusion(
    item: dict, *, start_ts: int = START_TS, end_ts: int = END_TS
) -> str | None:
    """Why this market cannot have traded anywhere in the frozen window."""
    raw = item["raw"]
    opened = _parse_iso_ts(raw.get("open_time"))
    closed = _parse_iso_ts(raw.get("close_time"))
    if opened is not None and opened >= end_ts:
        return "opened_at_or_after_window"
    if closed is not None and closed <= start_ts:
        return "closed_at_or_before_window"
    return None


def collect_candles(
    markets: dict[str, dict],
    conn: sqlite3.Connection,
    raw_dir: Path,
    *,
    fetch=get_json,
    start_ts: int = START_TS,
    end_ts: int = END_TS,
) -> dict:
    """Fetch current markets in batches and archived markets one at a time."""
    if start_ts >= end_ts:
        raise ValueError("candle start_ts must precede end_ts")
    expected_bars = (end_ts - start_ts) // 86_400 + 1
    batch_size = min(
        MAX_BATCH_TICKERS,
        max(1, MAX_BATCH_CANDLES // max(1, expected_bars)),
    )
    exclusions = {
        ticker: reason for ticker, item in markets.items()
        if (reason := _calendar_exclusion(
            item, start_ts=start_ts, end_ts=end_ts
        )) is not None
    }
    historical = sorted(
        ticker for ticker, item in markets.items()
        if "historical" in item["sources"] and ticker not in exclusions
    )
    historical_set = set(historical)
    current = sorted(
        ticker for ticker, item in markets.items()
        if "historical" not in item["sources"] and ticker not in exclusions
    )
    missing: list[str] = []
    stored = 0
    empty = 0
    candle_rows = 0
    requests = 0

    for ticker in sorted(exclusions):
        _store_candles(
            conn, ticker, markets[ticker]["series_ticker"], [],
            start_ts=start_ts, end_ts=end_ts,
        )
        stored += 1
        empty += 1

    for start in range(0, len(current), batch_size):
        chunk = current[start:start + batch_size]
        batch_no = start // batch_size + 1
        params = {
            "market_tickers": ",".join(chunk),
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": PERIOD_INTERVAL,
        }
        payload = _cached_fetch(
            Path(raw_dir) / "live" / f"batch-{batch_no:04d}.json",
            f"{BASE_URL}/markets/candlesticks", params, fetch,
        )
        requests += 1
        groups = payload.get("markets")
        if not isinstance(groups, list):
            raise ValueError("batch candle response has no markets list")
        returned: dict[str, dict] = {}
        for group in groups:
            if not isinstance(group, dict):
                raise ValueError("batch candle market is not an object")
            ticker = group.get("market_ticker") or group.get("ticker")
            if ticker not in chunk:
                raise ValueError(f"batch returned unrequested ticker {ticker!r}")
            if ticker in returned:
                raise ValueError(f"batch returned ticker {ticker} twice")
            returned[ticker] = group
        for ticker in chunk:
            group = returned.get(ticker)
            if group is None:
                missing.append(ticker)
                continue
            rows = normalize_candles(
                group.get("candlesticks"), start_ts=start_ts, end_ts=end_ts
            )
            _store_candles(
                conn, ticker, markets[ticker]["series_ticker"], rows,
                start_ts=start_ts, end_ts=end_ts,
            )
            stored += 1
            empty += not rows
            candle_rows += len(rows)

    for ticker in historical:
        params = {"start_ts": start_ts, "end_ts": end_ts,
                  "period_interval": PERIOD_INTERVAL}
        payload = _cached_fetch(
            Path(raw_dir) / "historical" / f"{ticker}.json",
            f"{BASE_URL}/historical/markets/{ticker}/candlesticks",
            params, fetch,
        )
        requests += 1
        if payload.get("ticker") != ticker:
            missing.append(ticker)
            continue
        rows = normalize_candles(
            payload.get("candlesticks"), start_ts=start_ts, end_ts=end_ts
        )
        _store_candles(
            conn, ticker, markets[ticker]["series_ticker"], rows,
            start_ts=start_ts, end_ts=end_ts,
        )
        stored += 1
        empty += not rows
        candle_rows += len(rows)

    return {
        "requested": len(markets),
        "http_eligible_tickers": len(current) + len(historical),
        "http_requests": requests,
        "stored": stored,
        "empty": int(empty),
        "candle_rows": candle_rows,
        "missing_requests": sorted(missing),
        "excluded_by_calendar_availability": dict(sorted(Counter(
            exclusions.values()
        ).items())),
        "live_batch_size": batch_size,
    }


def _inventory(series: Iterable[str], campaign: Path, fetch) -> tuple[dict, dict]:
    inventory: dict[str, dict] = {}
    duplicates = 0
    pages = {"live": 0, "historical": 0}
    unique_by_source = {"live": set(), "historical": set()}
    for series_ticker in series:
        for source in ("live", "historical"):
            rows, n_pages = paginated_markets(
                series_ticker,
                source,
                campaign / "raw" / "markets" / source / series_ticker,
                fetch=fetch,
            )
            pages[source] += n_pages
            for raw in rows:
                ticker = raw["ticker"]
                unique_by_source[source].add(ticker)
                if ticker in inventory:
                    duplicates += 1
                    inventory[ticker]["sources"].add(source)
                    if source == "historical":
                        inventory[ticker]["raw"] = raw
                    continue
                inventory[ticker] = {
                    "raw": raw,
                    "series_ticker": series_ticker,
                    "sources": {source},
                }
    stats = {
        "unique": len(inventory),
        "duplicates": duplicates,
        "unique_live": len(unique_by_source["live"]),
        "unique_historical": len(unique_by_source["historical"]),
        "pages": pages,
        "statuses": dict(sorted(Counter(
            str(item["raw"].get("status") or "unknown")
            for item in inventory.values()
        ).items())),
    }
    return inventory, stats


def _store_markets(conn: sqlite3.Connection, inventory: dict[str, dict]) -> None:
    stamp = utcnow()
    with conn:
        for ticker in sorted(inventory):
            item = inventory[ticker]
            raw = item["raw"]
            conn.execute(
                "REPLACE INTO settled_markets (ticker, series_ticker, close_time, "
                "fetched_at, payload) VALUES (?, ?, ?, ?, ?)",
                (ticker, item["series_ticker"], raw.get("close_time"), stamp,
                 json.dumps(raw, sort_keys=True)),
            )


def _inventory_tree_digest(campaign: Path) -> str:
    """Hash the immutable raw series and market enumeration tree."""
    root = Path(campaign) / "raw"
    files = []
    for name in ("series", "markets"):
        directory = root / name
        if directory.exists():
            files.extend(path for path in directory.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"no frozen inventory responses under {root}")
    h = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        h.update(len(relative).to_bytes(8, "big"))
        h.update(relative)
        h.update(len(payload).to_bytes(8, "big"))
        h.update(payload)
    return h.hexdigest()


def _reuse_inventory(source: Path, destination: Path) -> str:
    """Copy a frozen enumeration exactly, refusing conflicting destination data."""
    source = source.resolve()
    destination = destination.resolve()
    if source == destination:
        raise ValueError("inventory source and destination must differ")
    source_digest = _inventory_tree_digest(source)
    for name in ("series", "markets"):
        src = source / "raw" / name
        if not src.exists():
            raise ValueError(f"frozen inventory is missing {src}")
        for path in (item for item in src.rglob("*") if item.is_file()):
            relative = path.relative_to(src)
            target = destination / "raw" / name / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.read_bytes() != path.read_bytes():
                    raise ValueError(f"inventory copy conflicts at {target}")
                continue
            shutil.copy2(path, target)
    copied_digest = _inventory_tree_digest(destination)
    if copied_digest != source_digest:
        raise ValueError("copied inventory digest differs from frozen source")
    return source_digest


def collect(
    campaign: str | Path = DEFAULT_CAMPAIGN,
    *,
    fetch=get_json,
    series: Iterable[str] = SERIES,
    start_ts: int = START_TS,
    end_ts: int = END_TS,
    inventory_from: str | Path | None = None,
) -> dict:
    """Run or resume the frozen raw-data collection and return its manifest."""
    campaign = Path(campaign)
    campaign.mkdir(parents=True, exist_ok=True)
    series = tuple(series)
    progress_path = campaign / "progress.json"
    progress = {
        "complete": False,
        "phase": "starting",
        "started_at": utcnow(),
        "series": list(series),
        "last_error": None,
    }
    _atomic_json(progress_path, progress)
    try:
        inventory_digest = None
        inventory_source = None
        if inventory_from is not None:
            inventory_source = Path(inventory_from).resolve()
            progress["phase"] = "reuse_inventory"
            _atomic_json(progress_path, progress)
            inventory_digest = _reuse_inventory(inventory_source, campaign)

        progress["phase"] = "series_metadata"
        _atomic_json(progress_path, progress)
        metadata = collect_series_metadata(series, campaign, fetch=fetch)

        progress["phase"] = "market_enumeration"
        _atomic_json(progress_path, progress)
        inventory, market_stats = _inventory(series, campaign, fetch)
        denominator = {
            "series": list(series),
            "tickers": [
                {
                    "ticker": ticker,
                    "series_ticker": item["series_ticker"],
                    "event_ticker": item["raw"].get("event_ticker"),
                    "status": item["raw"].get("status"),
                    "sources": sorted(item["sources"]),
                }
                for ticker, item in sorted(inventory.items())
            ],
        }
        _atomic_json(campaign / "denominator.json", denominator)
        denominator_bytes = json.dumps(
            denominator, sort_keys=True, separators=(",", ":")
        ).encode()

        conn = connect_cache(campaign / "history.db")
        try:
            _store_markets(conn, inventory)
            progress["phase"] = "candles"
            progress["markets_enumerated"] = len(inventory)
            _atomic_json(progress_path, progress)
            candle_stats = collect_candles(
                inventory, conn, campaign / "raw" / "candles", fetch=fetch,
                start_ts=start_ts, end_ts=end_ts,
            )
        finally:
            conn.close()

        manifest = {
            "protocol": "ND-1",
            "campaign": campaign.name,
            "collected_at": utcnow(),
            "series": list(series),
            "category": EXPECTED_CATEGORY,
            "category_conflicts": metadata["conflicts"],
            "window": {
                "start_ts": start_ts,
                "end_ts": end_ts,
                "period_interval": PERIOD_INTERVAL,
            },
            "database": "history.db",
            "denominator": "denominator.json",
            "denominator_sha256": hashlib.sha256(denominator_bytes).hexdigest(),
            "inventory_reused_from": (
                str(inventory_source) if inventory_source is not None else None
            ),
            "inventory_tree_sha256": (
                inventory_digest or _inventory_tree_digest(campaign)
            ),
            "markets": market_stats,
            "candles": candle_stats,
            "coverage_complete": (
                not metadata["conflicts"]
                and not candle_stats["missing_requests"]
            ),
            "selection": (
                "All live-tier and historical-tier markets returned for each "
                "frozen series; no status, terminal-volume, result, quote, or "
                "realized-close filter."
            ),
        }
        _atomic_json(campaign / "manifest.json", manifest)
        progress.update({"complete": True, "phase": "complete",
                         "finished_at": utcnow(), "last_error": None})
        _atomic_json(progress_path, progress)
        return manifest
    except Exception as exc:
        progress.update({
            "complete": False,
            "phase": "failed",
            "finished_at": utcnow(),
            "last_error": {"type": type(exc).__name__, "message": str(exc)},
        })
        _atomic_json(progress_path, progress)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument("--start", default="2026-06-01",
                        help="inclusive UTC date, YYYY-MM-DD")
    parser.add_argument("--end", default="2026-08-18",
                        help="inclusive UTC boundary, YYYY-MM-DD")
    parser.add_argument("--inventory-from", type=Path)
    args = parser.parse_args()
    try:
        start_ts = int(datetime.fromisoformat(args.start).replace(
            tzinfo=timezone.utc).timestamp())
        end_ts = int(datetime.fromisoformat(args.end).replace(
            tzinfo=timezone.utc).timestamp())
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(collect(
        args.campaign,
        start_ts=start_ts,
        end_ts=end_ts,
        inventory_from=args.inventory_from,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
