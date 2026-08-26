"""insider_bias — shared mechanical favorite screen.

`theories/insider_bias/` is a shared parent for two sibling theories that
both narrow the same board of tradeable favorites before applying their own,
very different decision procedures: `insider_bias.insider_judgment`
(LLM-judged: does a specific identifiable group already know the outcome)
and `insider_bias.mention_family` (mechanical: does this ticker family beat
its own measured historical price). This module is that shared narrowing --
a clear favorite with room left after fees, a tight enough spread to trade,
real volume, and a near-term close. It deliberately makes no probability
estimate; that is each sibling theory's own job, and they do it in
unrelated ways.

Briefly lived at `tools/screen.py` (2026-08-24) on the theory that a module
two theories share belongs in generic `tools/`. Moved back here the same
day: it is not a generic tool the way `tools/buckets.py` or `tools/ledger.py`
are (usable by any future theory for anything) -- it is specifically the
inheritance boundary between these two related theories, and living at
`theories/insider_bias/` makes that relationship visible in the directory
structure rather than hidden behind an import path into an unrelated-looking
top-level module.

`EXCLUDED_PREFIXES` excludes whole sports/esports leagues by ticker prefix
(mostly live game outcomes neither sibling's thesis can apply to) plus
`KXMVECROSSCATEGORY`, which alone settles 400,000+ markets per day and would
otherwise flood any settled-history walk (see
`tools/kalshi/markets.py::list_settled`'s docstring, and
`replay.py`'s module docstring for the full account of
how that was discovered). Known trade-off: excluding by whole league is
cheap and safe against the live-score majority, at the cost of dropping
league-adjacent non-game markets (call-ups, retirements, franchise
approvals) too.
"""

from __future__ import annotations

from datetime import datetime, timezone

from tools.domain import Candidate, Leg, Market

MIN_FAVORITE_PRICE = 0.65
MAX_FAVORITE_PRICE = 0.97
MAX_SPREAD = 0.07
MIN_VOLUME = 500.0
MAX_DAYS_AHEAD = 14.0

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
    """True for market families a mechanical favorite screen should skip."""
    return any(ticker.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def favorite(market: Market) -> tuple[str, float] | None:
    """The favored side and the price you would actually pay for it.

    Uses the ask, not the mid. An edge measured against the mid is an edge
    against a price nobody will fill.
    """
    if market.mid is None:
        return None
    if market.mid >= 0.5:
        side, price = "yes", market.yes_ask
    else:
        side, price = "no", market.no_ask
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
    markets: list[Market],
    now: datetime | None = None,
    min_favorite_price: float = MIN_FAVORITE_PRICE,
    max_favorite_price: float = MAX_FAVORITE_PRICE,
    max_spread: float = MAX_SPREAD,
    min_volume: float = MIN_VOLUME,
    max_days_ahead: float = MAX_DAYS_AHEAD,
) -> list[Candidate]:
    """Narrow normalized Kalshi markets to tradeable-favorite candidates."""
    candidates = []
    for market in markets:
        if not market.is_open or is_excluded(market.ticker):
            continue

        fav = favorite(market)
        if fav is None:
            continue
        side, entry_price = fav
        if not min_favorite_price <= entry_price <= max_favorite_price:
            continue

        if market.spread is None or market.spread > max_spread:
            continue
        if market.volume is None or market.volume < min_volume:
            continue

        days = days_until(market.close_time, now=now)
        if days is None or days < 0 or days > max_days_ahead:
            continue

        candidates.append(Candidate(
            legs=(Leg(market=market, side=side, price=entry_price),),
            days_to_close=days,
        ))
    return candidates
