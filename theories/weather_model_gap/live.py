"""Resumable live-source collection for WG-1.

The 00:00--01:00 UTC guard runs before any source is touched.  A collection
retains current series inventories, the exact prior-day 12Z forecast, the
entry candle, fresh quotes, and selected order books under one immutable run
directory.  The March--August campaign remains the reusable history base.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable, Mapping

from tools.domain import Market
from tools.http import get_json
from tools.kalshi import markets as kalshi_markets
from tools.kalshi.markets import BASE_URL
from tools.theory import TheoryContext

from . import collect, data
from .stations import STATIONS
from .theory import WeatherModelGapTheory


UTC = timezone.utc
ROOT = Path(__file__).resolve().parent
BASE_CAMPAIGN = ROOT / "backtests" / "wg1-20260905"
DEFAULT_DATA_DIR = ROOT / "data" / "live"
CURRENT_CANDLES_URL = f"{BASE_URL}/markets/candlesticks"

Fetch = Callable[..., dict | list]
Clock = Callable[[], datetime]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("live collection time must be timezone-aware")
    return value.astimezone(UTC)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _write_once(path: Path, value: object) -> None:
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise ValueError(f"immutable live checkpoint changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(encoded, encoding="utf-8")
    temp.replace(path)


class CaptureFetch:
    """Content-addressed HTTP checkpoint used for quotes and order books."""

    def __init__(self, root: Path, fetch: Fetch, clock: Clock,
                 *, allow_network: bool = True):
        self.root = Path(root)
        self.fetch = fetch
        self.clock = clock
        self.allow_network = allow_network

    def __call__(self, url: str, params: dict | None = None, timeout: int = 30):
        request = {"url": url, "params": dict(params or {})}
        path = self.root / f"{_digest(request)}.json"
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved.get("request") != request or "response" not in saved:
                raise ValueError(f"captured HTTP identity mismatch: {path}")
            return saved["response"]
        if not self.allow_network:
            raise FileNotFoundError(f"no captured response for {request}")
        response = self.fetch(url, params=params, timeout=timeout)
        _write_once(path, {
            "fetched_at": _utc(self.clock()).isoformat(),
            "request": request,
            "response": response,
        })
        return response


def _load_base(base_dataset):
    if callable(base_dataset):
        return base_dataset()
    if base_dataset is not None:
        return base_dataset
    return data.load_dataset(BASE_CAMPAIGN)


def _current_events(
    target: date,
    *,
    campaign: Path,
    forecast_cache: Path,
    fetch: Fetch,
    base: Mapping,
) -> tuple[list[dict], dict]:
    """Collect missing rolling-history events plus today's open events."""
    grouped: dict[str, list[dict]] = {}
    pages = 0
    for series in STATIONS:
        rows, count = collect._pages(series, "current", campaign, fetch)
        pages += count
        for source in rows:
            raw = dict(source)
            raw.setdefault("series_ticker", series)
            event_ticker = raw.get("event_ticker")
            event_date = collect._target_date(event_ticker)
            if event_date is None or not target - timedelta(days=90) <= event_date <= target:
                continue
            grouped.setdefault(event_ticker, []).append(raw)

    base_keys = {
        row.get("event_ticker") for row in base.get("events", [])
        if isinstance(row, Mapping)
    }
    selected = {
        key: sorted(rows, key=lambda row: row["ticker"])
        for key, rows in grouped.items()
        if key not in base_keys or collect._target_date(key) == target
    }
    dates = sorted({collect._target_date(key) for key in selected})
    forecasts = {
        day: collect._forecast_for_date(
            day, tuple(STATIONS), forecast_cache, fetch
        )
        for day in dates if day is not None
    }
    events = []
    for event_ticker in sorted(
        selected, key=lambda key: (collect._target_date(key), key)
    ):
        markets = selected[event_ticker]
        event_date = collect._target_date(event_ticker)
        series = str(markets[0]["series_ticker"])
        if series not in STATIONS or event_date is None:
            continue
        events.append({
            "event_ticker": event_ticker,
            "series_ticker": series,
            "station": STATIONS[series]["station"],
            "target_date": event_date.isoformat(),
            "markets": markets,
            "candles": {row["ticker"]: [] for row in markets},
            "forecast": forecasts[event_date][series],
            "label": data.normalize_label(markets, STATIONS[series]),
        })
    return events, {"current_market_pages": pages,
                    "supplemental_events": len(events)}


def _capture_entry_candles(
    events: list[dict], target: date, *, fetch: CaptureFetch
) -> tuple[list[Market], dict]:
    entry_ts = int(datetime.combine(target, time.min, UTC).timestamp())
    targets = [event for event in events
               if event.get("target_date") == target.isoformat()]
    raw_markets = [raw for event in targets for raw in event["markets"]]
    tickers = sorted(raw["ticker"] for raw in raw_markets)
    if not tickers:
        return [], {"target_events": 0, "target_markets": 0,
                    "markets_with_entry_candle": 0,
                    "markets_missing_entry_candle": 0}
    params = {
        "market_tickers": ",".join(tickers),
        "start_ts": entry_ts - 3600,
        "end_ts": entry_ts,
        "period_interval": 60,
    }
    payload = fetch(CURRENT_CANDLES_URL, params=params)
    if not isinstance(payload, Mapping) or not isinstance(payload.get("markets"), list):
        raise ValueError("current candle batch has no markets list")
    blocks = {
        block.get("market_ticker"): block
        for block in payload["markets"] if isinstance(block, Mapping)
    }
    board: list[Market] = []
    present = 0
    for event in targets:
        for raw in event["markets"]:
            ticker = raw["ticker"]
            rows, reason = collect._normalize_candle_or_missing(
                blocks.get(ticker, {"candlesticks": []}), entry_ts
            )
            event["candles"][ticker] = rows
            bar = rows[0] if rows else {}
            enriched = dict(raw)
            enriched["_wg1_entry_ts"] = entry_ts
            enriched["_wg1_entry_volume"] = bar.get("volume")
            enriched["_wg1_entry_candle_reason"] = reason
            board.append(kalshi_markets.normalize(enriched))
            present += bool(rows)
    return board, {
        "target_events": len(targets),
        "target_markets": len(raw_markets),
        "markets_with_entry_candle": present,
        "markets_missing_entry_candle": len(raw_markets) - present,
    }


def _merge_dataset(base: Mapping, supplement: list[dict]) -> dict:
    by_event = {
        row["event_ticker"]: row for row in base.get("events", [])
        if isinstance(row, Mapping) and row.get("event_ticker")
    }
    for row in supplement:
        by_event[row["event_ticker"]] = row
    identity = {
        "base_source_digest": base.get("source_digest"),
        "supplement": supplement,
    }
    return {
        "events": list(by_event.values()),
        "source_digest": _digest(identity),
        "base_source_digest": base.get("source_digest"),
    }


def _signal(scored) -> dict:
    candidate = scored.candidate
    extra = dict(scored.extra or {})
    return {
        "ticker": candidate.ticker,
        "side": candidate.fav_side,
        "entry_price": candidate.entry_price,
        "event_ticker": extra.get("event_ticker"),
        "series_ticker": extra.get("series_ticker"),
        "target_date": extra.get("target_date"),
        "model_prob": extra.get("model_prob"),
        "edge_basis": scored.edge.basis,
        "edge_pts_net": scored.edge.pts_net,
        "disposition": scored.disposition,
        "depth_contracts": extra.get("depth_contracts"),
        "depth_status": extra.get("depth_status"),
        "extra": extra,
    }


def collect_live(
    *,
    now: datetime | None = None,
    fetch: Fetch | None = None,
    clock: Clock | None = None,
    base_dataset=None,
    data_dir: Path | str | None = None,
    out_path: Path | str | None = None,
    validation_check=None,
) -> dict:
    """Capture and dry-run today's WG-1 population."""
    as_of = _utc(now or datetime.now(UTC))
    # This guard deliberately precedes even base-dataset loading.
    if as_of.hour != 0:
        return {
            "status": "outside_entry_window",
            "protocol": "WG-1",
            "as_of": as_of.isoformat(),
            "funnel": {"target_events": 0, "signals": 0},
            "signals": [],
        }

    fetch = fetch or get_json
    clock = clock or (lambda: datetime.now(UTC))
    root = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    capture_dir = root / "collections" / as_of.strftime("%Y%m%dT%H%M%SZ")
    canonical_artifact = capture_dir / "collection.json"
    if canonical_artifact.exists():
        artifact = json.loads(canonical_artifact.read_text(encoding="utf-8"))
        if (artifact.get("protocol") != "WG-1"
                or artifact.get("as_of") != as_of.isoformat()):
            raise ValueError("live collection checkpoint identity changed")
        if out_path is not None:
            _write_once(Path(out_path), artifact)
        return artifact
    forecast_cache = root / "forecast-cache"
    base = _load_base(base_dataset)
    if not isinstance(base, Mapping) or not isinstance(base.get("events"), list):
        raise ValueError("base dataset must contain events")
    supplement, inventory_funnel = _current_events(
        as_of.date(), campaign=capture_dir / "inventory",
        forecast_cache=forecast_cache, fetch=fetch, base=base,
    )
    capture_fetch = CaptureFetch(capture_dir / "http", fetch, clock)
    board, candle_funnel = _capture_entry_candles(
        supplement, as_of.date(), fetch=capture_fetch
    )
    merged = _merge_dataset(base, supplement)
    dataset_path = capture_dir / "dataset.json"
    _write_once(dataset_path, {
        "protocol": "WG-1",
        "target_date": as_of.date().isoformat(),
        "created_at": as_of.isoformat(),
        "base_campaign": str(BASE_CAMPAIGN),
        "base_source_digest": base.get("source_digest"),
        "source_digest": merged["source_digest"],
        "events": supplement,
    })

    # Fetch all target quotes once, then make the theory consume the captured
    # response.  Its decision timestamp is the completed quote time.
    quote_started = _utc(clock())
    kalshi_markets.quotes(sorted(m.ticker for m in board), fetch=capture_fetch)
    quote_completed = _utc(clock())
    theory = WeatherModelGapTheory(
        dataset=merged, validation_check=validation_check, fetch=capture_fetch
    )
    ctx = TheoryContext(
        conn=None,
        board=board,
        now=quote_completed,
        run_id=f"live/wg1-{as_of.strftime('%Y%m%dT%H%M%SZ')}",
        run_mode="live",
    )
    dry = theory.start(ctx).finish(dry_run=True)
    depth_completed = _utc(clock())
    signals = [_signal(row) for row in dry.scored]
    funnel = {
        **inventory_funnel,
        **candle_funnel,
        **dry.funnel,
        "signals": len(signals),
    }
    artifact = {
        "status": "complete",
        "protocol": "WG-1",
        "as_of": as_of.isoformat(),
        "target_date": as_of.date().isoformat(),
        "capture_dir": str(capture_dir.resolve()),
        "dataset_path": str(dataset_path.resolve()),
        "dataset_source_digest": merged["source_digest"],
        "base_source_digest": base.get("source_digest"),
        "quote_fetch_started_at": quote_started.isoformat(),
        "quote_fetch_completed_at": quote_completed.isoformat(),
        "depth_fetch_completed_at": depth_completed.isoformat(),
        "board": [asdict(market) for market in board],
        "funnel": funnel,
        "gate_removed": dry.gate_removed,
        "signals": signals,
    }
    _write_once(canonical_artifact, artifact)
    if out_path is not None and Path(out_path) != canonical_artifact:
        _write_once(Path(out_path), artifact)
    return artifact


def load_live_dataset(
    source: Path | str | None = None,
    *,
    now: datetime | None = None,
    base_dataset=None,
) -> dict:
    """Merge a retained live supplement with the frozen history campaign."""
    if source is None:
        current = _utc(now or datetime.now(UTC))
        candidates = sorted(
            (DEFAULT_DATA_DIR / "collections").glob(
                f"{current.strftime('%Y%m%d')}*/dataset.json"
            )
        )
        if not candidates:
            raise FileNotFoundError("no WG-1 live dataset for the current UTC date")
        source = candidates[-1]
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if payload.get("protocol") != "WG-1" or not isinstance(payload.get("events"), list):
        raise ValueError("invalid WG-1 live dataset")
    base = _load_base(base_dataset)
    if base.get("source_digest") != payload.get("base_source_digest"):
        raise ValueError("live dataset base source digest changed")
    merged = _merge_dataset(base, payload["events"])
    if merged["source_digest"] != payload.get("source_digest"):
        raise ValueError("live dataset source digest changed")
    return merged


def _parse_time(value: str) -> datetime:
    return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--as-of", type=_parse_time)
    args = parser.parse_args(argv)
    if not args.collect:
        parser.error("--collect is required")
    wall_now = datetime.now(UTC)
    as_of = args.as_of or wall_now
    if args.as_of is not None and not 0 <= (wall_now - as_of).total_seconds() <= 3600:
        parser.error("--as-of must be within the preceding hour")
    try:
        result = collect_live(
            now=as_of, data_dir=args.data_dir, out_path=args.out
        )
    except Exception as exc:
        print(json.dumps({"status": "stopped", "error": str(exc)}))
        return 1
    print(json.dumps({
        "status": result["status"],
        "target_date": result.get("target_date"),
        "dataset_path": result.get("dataset_path"),
        "funnel": result["funnel"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
