"""insider_bias — stage 1 mechanical screen.

Ported from kalshi_trader's deterministic filter. This narrows the whole
Kalshi board to markets where the insider thesis is even possible: a clear
favorite with room left after fees, a tight enough spread to trade, real
volume, and a near-term close.

It deliberately makes no probability estimate. This theory's edge depends on
judging whether a specific group of humans already knows the answer, and no
threshold can decide that. Stage 2 supplies the probability; see THEORY.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

MIN_FAVORITE_PRICE = 0.65
MAX_FAVORITE_PRICE = 0.97
MAX_SPREAD = 0.07
MIN_VOLUME = 500.0
MAX_DAYS_AHEAD = 14.0

# Sports, esports, and multi-variate parlays: outcomes nobody can know in
# advance, so the insider thesis cannot apply by construction.
EXCLUDED_PREFIXES = (
    "KXMVE",
    "KXMLB", "KXNBA", "KXNFL", "KXNHL",
    "KXEPL", "KXLALIGA", "KXBUNDESLIGA", "KXSERIE", "KXMLS", "KXLIGUE",
    "KXEFL", "KXEREDIVISIE", "KXALLSVENSKAN", "KXBRASILEIRO",
    "KXARGPREMDIV", "KXLIGAMX", "KXLIGAPORTUGAL", "KXSAUDIPL",
    "KXSUPERLIG", "KXJLEAGUE", "KXCZEFL", "KXUCLW",
    "KXATP", "KXWTA", "KXITF",
    "KXPGA", "KXLPGA", "KXDPWORLD", "KXCHAMPTOUR",
    "KXBOXING", "KXUFC", "KXNCAA",
    "KXAFL", "KXNASCAR", "KXF1", "KXIPL",
    "KXBSL", "KXSHL", "KXVTB",
    "KXCS2", "KXLOL", "KXCOD", "KXDOTA2",
)


def is_excluded(ticker: str) -> bool:
    """True for market families the thesis cannot apply to."""
    return any(ticker.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def favorite(market: dict) -> tuple[str, float] | None:
    """The favored side and the price you would actually pay for it.

    Uses the ask, not the mid. An edge measured against the mid is an edge
    against a price nobody will fill.
    """
    mid = market.get("mid")
    if mid is None:
        return None
    if mid >= 0.5:
        price = market.get("yes_ask")
        side = "yes"
    else:
        price = market.get("no_ask")
        side = "no"
    if price is None:
        return None
    return side, price


def days_until(close_time: str | None, now: datetime | None = None) -> float | None:
    """Days from now until close, or None if unparseable."""
    if not close_time:
        return None
    try:
        closes = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
    except ValueError:
        return None
    reference = now or datetime.now(timezone.utc)
    return (closes - reference).total_seconds() / 86400.0


def screen(
    markets: list[dict],
    now: datetime | None = None,
    min_favorite_price: float = MIN_FAVORITE_PRICE,
    max_favorite_price: float = MAX_FAVORITE_PRICE,
    max_spread: float = MAX_SPREAD,
    min_volume: float = MIN_VOLUME,
    max_days_ahead: float = MAX_DAYS_AHEAD,
) -> list[dict]:
    """Narrow normalized Kalshi markets to insider-thesis candidates."""
    candidates = []
    for market in markets:
        ticker = market.get("ticker") or ""
        if not market.get("is_open") or is_excluded(ticker):
            continue

        fav = favorite(market)
        if fav is None:
            continue
        side, entry_price = fav
        if not min_favorite_price <= entry_price <= max_favorite_price:
            continue

        spread = market.get("spread")
        if spread is None or spread > max_spread:
            continue

        volume = market.get("volume")
        if volume is None or volume < min_volume:
            continue

        days = days_until(market.get("close_time"), now=now)
        if days is None or days < 0 or days > max_days_ahead:
            continue

        candidate = dict(market)
        candidate["fav_side"] = side
        candidate["entry_price"] = entry_price
        candidate["days_to_close"] = days
        candidates.append(candidate)

    return candidates
