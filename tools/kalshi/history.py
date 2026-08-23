"""Kalshi historical prices and point-in-time reconstruction.

Candlesticks carry historical yes_bid and yes_ask, not just the last trade.
That matters: a backtest priced at the mid is a backtest of a trade nobody
could have made. Entry prices reconstructed here use the ask.

point_in_time never looks past its as_of timestamp. That property is the
whole basis of a lookahead-free replay, so the boundary is tested explicitly.
"""

from __future__ import annotations

from tools.http import get_json
from tools.kalshi.markets import BASE_URL

VALID_INTERVALS = (1, 60, 1440)


def _nested(candle: dict, group: str, field: str) -> float | None:
    block = candle.get(group)
    if not isinstance(block, dict):
        return None
    value = block.get(field)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"could not parse {group}.{field}={value!r} as a number — "
            "Kalshi's schema may have changed"
        ) from exc


def _flat(candle: dict, key: str) -> float | None:
    value = candle.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"could not parse {key}={value!r} as a number — "
            "Kalshi's schema may have changed"
        ) from exc


def _end_ts(raw: dict) -> int:
    value = raw.get("end_period_ts")
    if value is None:
        raise ValueError(
            "candle has no end_period_ts — schema drift? "
            f"keys={sorted(raw)}"
        )
    return value


def candlesticks(
    series_ticker: str,
    ticker: str,
    start_ts: int,
    end_ts: int,
    period_interval: int = 1440,
) -> list[dict]:
    """Normalized candles, ascending by end timestamp."""
    if period_interval not in VALID_INTERVALS:
        raise ValueError(
            f"period_interval must be one of {VALID_INTERVALS}, "
            f"got {period_interval}"
        )
    payload = get_json(
        f"{BASE_URL}/series/{series_ticker}/markets/{ticker}/candlesticks",
        params={
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": period_interval,
        },
    )
    candles = [
        {
            "end_ts": _end_ts(raw),
            "open": _nested(raw, "price", "open_dollars"),
            "high": _nested(raw, "price", "high_dollars"),
            "low": _nested(raw, "price", "low_dollars"),
            "close": _nested(raw, "price", "close_dollars"),
            "mean": _nested(raw, "price", "mean_dollars"),
            "yes_bid_close": _nested(raw, "yes_bid", "close_dollars"),
            "yes_ask_close": _nested(raw, "yes_ask", "close_dollars"),
            "volume": _flat(raw, "volume_fp"),
            "open_interest": _flat(raw, "open_interest_fp"),
        }
        for raw in payload.get("candlesticks", [])
    ]
    return sorted(candles, key=lambda c: c["end_ts"])


def point_in_time(
    series_ticker: str,
    ticker: str,
    as_of_ts: int,
    lookback_days: int = 30,
) -> dict | None:
    """Market state as of a past moment, or None if no candle precedes it.

    Returns the most recent candle at or before as_of_ts. Never returns a
    candle from after that moment — this is what keeps a replay honest.
    """
    candles = candlesticks(
        series_ticker,
        ticker,
        start_ts=as_of_ts - 86400 * lookback_days,
        end_ts=as_of_ts,
        period_interval=1440,
    )
    eligible = [c for c in candles if c["end_ts"] <= as_of_ts]
    return eligible[-1] if eligible else None
