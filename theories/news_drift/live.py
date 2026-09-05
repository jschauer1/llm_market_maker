"""Cheap, resumable live collection for ND-1's current-board screen."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Callable
import uuid

from theories.news_drift import data
from theories.news_drift.signal import (
    MAX_SPREAD,
    MIN_OPEN_INTEREST,
    PRICE_BAND,
)
from theories.news_drift.theory import ELIGIBLE_CATEGORIES, NewsDriftTheory
from tools import board as board_tool
from tools import db
from tools.domain import Market
from tools.http import get_json
from tools.kalshi import markets as kalshi_markets
from tools.kalshi.markets import BASE_URL
from tools.theory import TheoryContext


DAY_SECONDS = 86_400
HISTORY_DAYS = 10
BATCH_SIZE = 100
ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data" / "live"
TARGET_CATEGORIES = frozenset(ELIGIBLE_CATEGORIES.values())

BoardLoader = Callable[..., list[Market]]
BatchFetch = Callable[..., dict]
QuoteLoader = Callable[[list[str]], dict[str, Market]]
Clock = Callable[[], datetime]


def _utc(value: datetime) -> datetime:
    return (value.astimezone(timezone.utc) if value.tzinfo
            else value.replace(tzinfo=timezone.utc))


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def _default_board_loader(*, force: bool):
    conn = db.connect()
    try:
        markets = board_tool.get_board(conn, force=force)
        info = board_tool.board_info(conn)
        return markets, {
            "captured_at": info.get("captured_at") if info else None,
        }
    finally:
        conn.close()


def _unpack_board(value) -> tuple[list[Market], dict]:
    if (isinstance(value, tuple) and len(value) == 2
            and isinstance(value[1], dict)):
        return list(value[0]), dict(value[1])
    return list(value), {}


def normalize_batch_payload(
    payload: dict,
    *,
    requested_tickers: list[str],
    as_of_ts: int,
) -> tuple[dict[str, list[dict]], list[str]]:
    """Normalize requested markets and report every absent/unusable ticker."""
    if not isinstance(payload, dict) or not isinstance(payload.get("markets"), list):
        raise ValueError("batch candlestick response must contain a markets list")
    requested = set(requested_tickers)
    by_ticker: dict[str, dict[int, dict]] = {}
    for block in payload["markets"]:
        if not isinstance(block, dict):
            continue
        ticker = block.get("market_ticker")
        if ticker not in requested or not isinstance(block.get("candlesticks"), list):
            continue
        periods = by_ticker.setdefault(ticker, {})
        for raw in block["candlesticks"]:
            row = data.normalize_candlestick(raw, as_of_ts)
            if row is not None:
                periods[row["end_ts"]] = row
    histories = {
        ticker: [periods[ts] for ts in sorted(periods)]
        for ticker in requested_tickers
        if (periods := by_ticker.get(ticker))
    }
    missing = [ticker for ticker in requested_tickers if ticker not in histories]
    return histories, missing


def _prefilter(board: list[Market]) -> tuple[list[Market], dict[str, int], dict[str, int]]:
    funnel = {
        "board": len(board),
        "eligible_category": 0,
        "open": 0,
        "valid_quote": 0,
        "open_interest": 0,
        "spread": 0,
        "mid_band": 0,
        "positive_volume_24h": 0,
        "prefiltered_unique": 0,
    }
    removed: dict[str, int] = {}
    retained: list[Market] = []
    seen: set[str] = set()

    def remove(reason: str) -> None:
        removed[reason] = removed.get(reason, 0) + 1

    for market in board:
        category = (market.event.get("category")
                    if isinstance(market.event, dict) else None)
        if category not in TARGET_CATEGORIES:
            remove("category")
            continue
        funnel["eligible_category"] += 1
        if not market.is_open:
            remove("not_open")
            continue
        funnel["open"] += 1
        bid, ask = _finite(market.yes_bid), _finite(market.yes_ask)
        if bid is None or ask is None or not (0.0 <= bid <= ask <= 1.0):
            remove("invalid_quote")
            continue
        funnel["valid_quote"] += 1
        oi = _finite(market.open_interest)
        if oi is None or oi < MIN_OPEN_INTEREST:
            remove("open_interest")
            continue
        funnel["open_interest"] += 1
        spread = ask - bid
        if spread > MAX_SPREAD + 1e-12:
            remove("spread")
            continue
        funnel["spread"] += 1
        midpoint = (bid + ask) / 2.0
        if not PRICE_BAND[0] <= midpoint <= PRICE_BAND[1]:
            remove("mid_band")
            continue
        funnel["mid_band"] += 1
        volume = _finite(market.volume_24h)
        if volume is None or volume <= 0.0:
            remove("volume_24h")
            continue
        funnel["positive_volume_24h"] += 1
        if market.ticker in seen:
            remove("duplicate_ticker")
            continue
        seen.add(market.ticker)
        retained.append(market)
    funnel["prefiltered_unique"] = len(retained)
    return retained, funnel, removed


def _batch_path(data_dir: Path, index: int, tickers: list[str], as_of_ts: int) -> Path:
    identity = json.dumps(
        {"as_of_ts": as_of_ts, "tickers": tickers},
        separators=(",", ":"),
    ).encode()
    digest = hashlib.sha256(identity).hexdigest()[:16]
    return data_dir / f"batch-{index:04d}-{digest}.json"


def _load_histories(
    markets: list[Market],
    *,
    as_of: datetime,
    batch_fetch: BatchFetch,
    data_dir: Path,
) -> tuple[dict[str, list[dict]], list[str], list[str]]:
    as_of_ts = int(as_of.timestamp())
    requested = [market.ticker for market in markets]
    histories: dict[str, list[dict]] = {}
    missing: list[str] = []
    checkpoints: list[str] = []
    for index, start in enumerate(range(0, len(requested), BATCH_SIZE)):
        chunk = requested[start:start + BATCH_SIZE]
        params = {
            "market_tickers": ",".join(chunk),
            "start_ts": as_of_ts - HISTORY_DAYS * DAY_SECONDS,
            "end_ts": as_of_ts,
            "period_interval": 1440,
            "include_latest_before_start": False,
        }
        path = _batch_path(data_dir, index, chunk, as_of_ts)
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))
            if (saved.get("requested_tickers") != chunk
                    or saved.get("as_of") != as_of.isoformat()
                    or saved.get("request") != params
                    or "response" not in saved):
                raise ValueError(f"checkpoint metadata mismatch: {path}")
            payload = saved["response"]
        else:
            payload = batch_fetch(
                f"{BASE_URL}/markets/candlesticks", params=params
            )
            _write_json(path, {
                "requested_tickers": chunk,
                "as_of": as_of.isoformat(),
                "request": params,
                "response": payload,
            })
        checkpoints.append(str(path))
        normalized, absent = normalize_batch_payload(
            payload, requested_tickers=chunk, as_of_ts=as_of_ts
        )
        histories.update(normalized)
        missing.extend(absent)
    return histories, missing, checkpoints


def _refresh(original: Market, fresh: Market) -> Market:
    """Apply executable fields while retaining the board's event envelope."""
    return replace(
        original,
        yes_bid=fresh.yes_bid,
        yes_ask=fresh.yes_ask,
        no_bid=fresh.no_bid,
        no_ask=fresh.no_ask,
        mid=fresh.mid,
        spread=fresh.spread,
        last_price=fresh.last_price,
        volume=fresh.volume,
        volume_24h=fresh.volume_24h,
        open_interest=fresh.open_interest,
        status=fresh.status,
        is_open=fresh.is_open,
        close_time=fresh.close_time,
        open_time=fresh.open_time,
        raw=fresh.raw,
    )


def _signal_row(candidate) -> dict:
    leg = candidate.legs[0]
    market = leg.market
    features = dict(market.raw.get("_news_drift", {}))
    return {
        "ticker": market.ticker,
        "title": market.title,
        "event_ticker": market.event_ticker,
        "series_ticker": market.series_ticker,
        "category": features.get("category"),
        "event": dict(market.event),
        "side": leg.side,
        "entry_price": leg.price,
        "quote": {
            "yes_bid": market.yes_bid,
            "yes_ask": market.yes_ask,
            "no_bid": market.no_bid,
            "no_ask": market.no_ask,
            "mid": market.mid,
            "spread": market.spread,
            "volume_24h": market.volume_24h,
            "open_interest": market.open_interest,
            "status": market.status,
        },
        "signal": features,
    }


def collect_live(
    *,
    now: datetime | None = None,
    board_loader: BoardLoader | None = None,
    batch_fetch: BatchFetch | None = None,
    quote_loader: QuoteLoader | None = None,
    clock: Clock | None = None,
    data_dir: Path | str | None = None,
    out_path: Path | str | None = None,
) -> dict:
    """Collect one current ND-1 observation artifact without pricing it."""
    as_of = _utc(now or datetime.now(timezone.utc))
    as_of_ts = int(as_of.timestamp())
    board_loader = board_loader or _default_board_loader
    batch_fetch = batch_fetch or get_json
    quote_loader = quote_loader or kalshi_markets.quotes
    clock = clock or (lambda: datetime.now(timezone.utc))
    data_dir = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR

    current_board, board_metadata = _unpack_board(board_loader(force=False))
    retained, funnel, prefilter_removed = _prefilter(current_board)
    histories, history_missing, checkpoints = _load_histories(
        retained,
        as_of=as_of,
        batch_fetch=batch_fetch,
        data_dir=data_dir,
    )
    funnel.update({
        "history_requested": len(retained),
        "history_returned": len(histories),
        "history_missing": len(history_missing),
    })

    lookup = lambda market, unused_now: histories.get(market.ticker)
    theory = NewsDriftTheory(history_loader=lookup, calibration={})
    historical_screen = theory.screen(TheoryContext(
        conn=None,
        board=retained,
        now=as_of,
        run_id="live/nd1-history-gate",
        run_mode="backtest",
    ))
    signal_tickers = [candidate.ticker
                      for candidate in historical_screen.candidates]
    funnel["history_signal_survivors"] = len(signal_tickers)

    quote_started_at = _utc(clock())
    fresh = quote_loader(signal_tickers)
    quote_completed_at = _utc(clock())
    originals = {market.ticker: market for market in retained}
    refreshed = [
        _refresh(originals[ticker], fresh[ticker])
        for ticker in signal_tickers
        if ticker in fresh
    ]
    quote_missing = [ticker for ticker in signal_tickers if ticker not in fresh]
    funnel.update({
        "quote_requested": len(signal_tickers),
        "quote_returned": len(refreshed),
        "quote_missing": len(quote_missing),
    })

    live_screen = theory.screen(TheoryContext(
        conn=None,
        board=refreshed,
        now=quote_completed_at,
        run_id="live/nd1-collection",
        run_mode="live",
    ))
    signals = [_signal_row(candidate) for candidate in live_screen.candidates]
    funnel["signals"] = len(signals)
    result = {
        "protocol": "ND-1",
        "history_as_of": as_of.isoformat(),
        "board": {
            "captured_at": board_metadata.get("captured_at"),
        },
        "funnel": funnel,
        "prefilter_removed": prefilter_removed,
        "history_gate_removed": historical_screen.gate_removed,
        "live_gate_removed": live_screen.gate_removed,
        "history": {
            "requested_tickers": [market.ticker for market in retained],
            "returned_tickers": list(histories),
            "missing_tickers": history_missing,
            "rows_by_ticker": histories,
            "raw_checkpoints": checkpoints,
        },
        "quotes": {
            "fetch_started_at": quote_started_at.isoformat(),
            "fetch_completed_at": quote_completed_at.isoformat(),
            "requested_tickers": signal_tickers,
            "returned_tickers": [market.ticker for market in refreshed],
            "missing_tickers": quote_missing,
        },
        "signals": signals,
    }
    if out_path is not None:
        _write_json(Path(out_path), result)
    return result


def _parse_as_of(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _utc(parsed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true",
                        help="collect one resumable current-board artifact")
    parser.add_argument("--out", type=Path,
                        help="result JSON path (default: owner data/live)")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="directory for raw batch checkpoints")
    parser.add_argument("--as-of", type=_parse_as_of,
                        help="fixed UTC ISO timestamp for exact resume")
    args = parser.parse_args(argv)
    if not args.collect:
        parser.error("--collect is required")
    wall_now = datetime.now(timezone.utc)
    as_of = args.as_of or wall_now
    if args.as_of is not None and (wall_now - as_of).total_seconds() > 3600:
        parser.error("--as-of cannot be more than one hour old for a live collection")
    out = args.out or args.data_dir / (
        f"nd1-live-{_utc(as_of).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    try:
        result = collect_live(
            now=as_of,
            data_dir=args.data_dir,
            out_path=out,
        )
    except Exception as exc:
        print(json.dumps({"status": "stopped", "error": str(exc)}))
        return 1
    print(json.dumps({
        "status": "complete",
        "out": str(out),
        "history_as_of": result["history_as_of"],
        "quote_fetch_completed_at": result["quotes"]["fetch_completed_at"],
        "funnel": result["funnel"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
