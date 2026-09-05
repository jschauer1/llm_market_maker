"""Pure, point-in-time ND-1 move detection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median


DAY_SECONDS = 86_400
MOVE_THRESHOLD = 0.15
PRICE_BAND = (0.15, 0.85)
MAX_SPREAD = 0.04
MIN_OPEN_INTEREST = 100.0


@dataclass(frozen=True, slots=True)
class MoveSignal:
    """One ND-1 entry reconstructed from five completed daily candles."""

    side: str
    signal_ts: int
    entry_ts: int
    move: float
    directional_mid: float
    entry_price: float
    signal_mid: float
    entry_mid: float
    signal_volume: float
    prior_volume_median: float
    entry_volume: float
    entry_open_interest: float
    entry_yes_bid: float
    entry_yes_ask: float
    entry_spread: float


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _timestamp(value: object) -> int | None:
    numeric = _number(value)
    if numeric is None or not numeric.is_integer():
        return None
    return int(numeric)


def _quote(row: dict) -> tuple[float, float, float] | None:
    bid = _number(row.get("yes_bid_close"))
    ask = _number(row.get("yes_ask_close"))
    if bid is None or ask is None or not (0.0 <= bid <= ask <= 1.0):
        return None
    return bid, ask, (bid + ask) / 2.0


def detect(candles: list[dict], as_of_ts: int) -> MoveSignal | None:
    """Return the latest eligible ND-1 signal using no data after ``as_of_ts``.

    History is deliberately not sorted or gap-filled here. The adapter owns
    normalization; this boundary verifies that its latest five rows are in
    order and exactly one day apart before allowing them to select a trade.
    """
    as_of = _timestamp(as_of_ts)
    if as_of is None:
        return None

    visible: list[dict] = []
    for row in candles or []:
        if not isinstance(row, dict):
            continue
        end_ts = _timestamp(row.get("end_ts"))
        if end_ts is not None and end_ts <= as_of:
            visible.append(row)
    if len(visible) < 5:
        return None

    window = visible[-5:]
    timestamps = [_timestamp(row.get("end_ts")) for row in window]
    if any(ts is None for ts in timestamps):
        return None
    if any(b - a != DAY_SECONDS for a, b in zip(timestamps, timestamps[1:])):
        return None

    quotes = [_quote(row) for row in window]
    volumes = [_number(row.get("volume")) for row in window]
    if any(quote is None for quote in quotes):
        return None
    if any(volume is None or volume < 0.0 for volume in volumes):
        return None

    signal_mid = quotes[3][2]
    previous_mid = quotes[2][2]
    move = signal_mid - previous_mid
    if abs(move) + 1e-12 < MOVE_THRESHOLD:
        return None
    if not PRICE_BAND[0] <= signal_mid <= PRICE_BAND[1]:
        return None

    prior_median = float(median(volumes[:3]))
    if volumes[3] <= prior_median:
        return None

    entry_bid, entry_ask, entry_mid = quotes[4]
    entry_spread = entry_ask - entry_bid
    entry_oi = _number(window[4].get("open_interest"))
    if not PRICE_BAND[0] <= entry_mid <= PRICE_BAND[1]:
        return None
    if entry_spread > MAX_SPREAD + 1e-12:
        return None
    if entry_oi is None or entry_oi < MIN_OPEN_INTEREST:
        return None
    if volumes[4] <= 0.0:
        return None

    entry_ts = timestamps[4]
    if as_of - entry_ts >= DAY_SECONDS:
        return None

    side = "yes" if move > 0.0 else "no"
    directional_mid = entry_mid if side == "yes" else 1.0 - entry_mid
    entry_price = entry_ask if side == "yes" else 1.0 - entry_bid
    return MoveSignal(
        side=side,
        signal_ts=timestamps[3],
        entry_ts=entry_ts,
        move=move,
        directional_mid=directional_mid,
        entry_price=entry_price,
        signal_mid=signal_mid,
        entry_mid=entry_mid,
        signal_volume=volumes[3],
        prior_volume_median=prior_median,
        entry_volume=volumes[4],
        entry_open_interest=entry_oi,
        entry_yes_bid=entry_bid,
        entry_yes_ask=entry_ask,
        entry_spread=entry_spread,
    )
