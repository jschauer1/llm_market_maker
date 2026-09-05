"""ND-1 data boundaries: completed candles in; terminal information out."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

from tools.domain import Fetch, Market
from tools.http import get_json
from tools.kalshi.markets import BASE_URL

ROOT = Path(__file__).resolve().parent


def _number(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalize_candlestick(raw: dict, as_of_ts: int) -> dict | None:
    """Normalize one real, completed Kalshi candle needed by ND-1.

    The batch endpoint can optionally emit a synthetic continuity candle
    whose quote fields are null. ND-1 never requests that option and rejects
    any such row defensively. Invalid or future periods are omitted rather
    than gap-filled.
    """
    if not isinstance(raw, dict):
        return None
    ts = _number(raw.get("end_period_ts"))
    if ts is None or not ts.is_integer() or ts > as_of_ts:
        return None
    bid = _number((raw.get("yes_bid") or {}).get("close_dollars"))
    ask = _number((raw.get("yes_ask") or {}).get("close_dollars"))
    volume = _number(raw.get("volume_fp"))
    open_interest = _number(raw.get("open_interest_fp"))
    if any(value is None for value in (bid, ask, volume, open_interest)):
        return None
    if not (0.0 <= bid <= ask <= 1.0):
        return None
    if volume < 0.0 or open_interest < 0.0:
        return None
    return {
        "end_ts": int(ts),
        "yes_bid_close": bid,
        "yes_ask_close": ask,
        "volume": volume,
        "open_interest": open_interest,
    }


def reconstruct(raw: dict, candles: list[dict], category: str,
                as_of_ts: int) -> Market | None:
    """Like history.point_in_time, select <= as-of from already cached candles.

    Whitelist identity only from terminal metadata. No terminal prices, volume,
    deadline, result, settlement value, or raw payload reaches the screen.
    """
    try:
        close = datetime.fromisoformat(raw["close_time"].replace("Z", "+00:00"))
        if close.tzinfo is None or as_of_ts >= close.timestamp():
            return None
    except (KeyError, ValueError, TypeError, AttributeError):
        return None
    past = [c for c in candles if c["end_ts"] <= as_of_ts]
    if not past:
        return None
    c = max(past, key=lambda x: x["end_ts"])
    bid, ask = c.get("yes_bid_close"), c.get("yes_ask_close")
    if not all(isinstance(p, (int, float)) and math.isfinite(p)
               for p in (bid, ask)):
        return None
    return Market(
        platform="kalshi", ticker=raw["ticker"], title=raw.get("title"),
        event_ticker=raw.get("event_ticker"),
        series_ticker=raw.get("series_ticker") or raw["ticker"].split("-")[0],
        yes_bid=bid, yes_ask=ask, no_ask=1 - bid, no_bid=1 - ask,
        mid=(bid + ask) / 2, spread=ask - bid,
        volume_24h=c.get("volume"), open_interest=c.get("open_interest"),
        status="open", is_open=True, event={"category": category},
    )


def load_calibration(path: Path | None = None) -> dict | None:
    path = path or ROOT / "data" / "calibration.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_live_history(market: Market, now: datetime,
                      fetch: Fetch | None = None,
                      cache_dir: Path | None = None) -> list[dict]:
    """Fetch completed daily candles, caching each request window on disk.

    No force-board capture or sibling-theory import. API response parsing
    matches tools.kalshi.history; optional transport keeps fixtures offline.
    Requests are keyed to the UTC hour so failed/empty responses aren't
    mistaken for permanent facts. A caller may share one now across a run.
    """
    fetch = fetch or get_json
    stamp = int(now.timestamp())
    cache_dir = cache_dir or ROOT / "data" / "live_candles"
    key = hashlib.sha256(f"{market.ticker}|{stamp // 3600}".encode()).hexdigest()
    path = cache_dir / f"{key}.json"
    if path.exists():
        stored = json.loads(path.read_text(encoding="utf-8"))
        # An earlier as-of in the same hour must not inherit a later candle.
        return [c for c in stored["candles"] if c["end_ts"] <= stamp]
    series = market.series_ticker or market.ticker.split("-")[0]
    payload = fetch(
        f"{BASE_URL}/series/{series}/markets/{market.ticker}/candlesticks",
        params={"start_ts": stamp - 10 * 86400, "end_ts": stamp,
                "period_interval": 1440},
    )

    rows = []
    for c in payload.get("candlesticks", []):
        row = normalize_candlestick(c, stamp)
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda c: c["end_ts"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Atomic replacement prevents a concurrent reader observing half a JSON.
    import uuid
    temp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps({"ticker": market.ticker, "as_of": now.isoformat(),
                                "candles": rows}), encoding="utf-8")
    temp.replace(path)
    return rows
