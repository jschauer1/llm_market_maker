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

# A coarse proxy: excludes whole sports/esports LEAGUES by ticker prefix, on
# the assumption that a league's markets are mostly live game outcomes the
# insider thesis cannot apply to. That assumption is not precise — checked
# against the live board, none of the markets these prefixes actually
# exclude are game outcomes; they are league-adjacent items (MLB call-ups,
# retirement announcements, franchise approvals) that a specific informed
# group plausibly *does* know in advance, exactly what this theory targets
# (a franchise approval is "a board that has voted"). Known trade-off:
# excluding by whole league is cheap and safe against the live-score
# majority, at the cost of dropping those non-game league markets too.
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


def is_mention_family(series_ticker: str) -> bool:
    """True for "will X mention/say/do Y" series -- a family gate.py's
    regex does not currently name and is not on `EXCLUDED_PREFIXES`, so
    without this check it is invisible: neither excluded nor deliberately
    included, just whatever `PLAUSIBLE` happens to catch.

    Found in the 2026-08-24 tier A stage-1 backtest
    (`run_id=backtest-2026-08-24-stage1-90d`): 116 of 200 real screen hits
    were this family, and it backtested positive (`calibration_edge_net=
    +5.48pts`) -- unlike the structurally similar "aggregate of many
    independent people" family gate.py *does* catch, which backtested
    strongly negative (`-11.12pts`). See `mention_bucket.py` and THEORY.md
    Status item 3: this is deliberately a separate, narrower classification
    from `is_excluded`, not folded into it, because the measured evidence
    points the opposite direction -- worth a bucket of its own, not a
    rejection.

    Accepts either a series ticker (`KXTRUMPMENTION`) or a full market
    ticker (`KXTRUMPMENTION-26JUL01-MAKE`); the pattern only needs the
    series prefix, which a market ticker always carries.
    """
    return "MENTION" in series_ticker or series_ticker.endswith(("SAY", "ACT"))


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
