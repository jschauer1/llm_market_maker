"""calibration_harvest -- the board screen.

Deliberately NOT built on `theories.insider_bias.screen`. That module is a
sibling theory's inheritance boundary, and importing it here would be both a
cross-theory import (forbidden; see
`tests/test_conventions.py::test_no_theory_imports_a_sibling_theory`) and
wrong on the merits: its 14-day `MAX_DAYS_AHEAD` cap is exactly the parameter
this theory must not have. Le 2026's horizon component rises monotonically to
1mo+, so capping the board at two weeks discards the cells with the largest
documented effect before anything is measured. The overlap in the other
parameters (spread, volume) is coincidence of both wanting tradeable markets,
not shared ancestry.

Every survivor carries a cell key. A market whose price falls in the dead
middle has no cell and is dropped -- this theory has nothing to say about a
coin flip, and a screen that emitted one would be inviting `price()` to
invent a rate for it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from tools.domain import Candidate, Leg, Market, ScreenResult
from theories.calibration_harvest import cells

MAX_SPREAD = 0.07
MIN_VOLUME = 500.0

#: Series whose population belongs to another theory. Excluding by pattern
#: keeps two theories from booking the same contract, and is part of the
#: versioned procedure -- adding a family here bumps the version.
#:
#: `mention_family` is retired, but its ledger rows cover a window that
#: overlaps this theory's reachable history, so pooling them would mix two
#: theories' evidence. The check is a substring rather than an import from
#: `theories/insider_bias/families.py`: that is a sibling theory's folder,
#: and a one-line predicate is not worth breaking the no-sibling-import rule
#: for. If a third theory ever needs it, it elevates to `tools/`.
MENTION_MARKERS = ("MENTION", "SAY", "ACT")


def _is_mention_family(series_ticker: str | None) -> bool:
    s = (series_ticker or "").upper()
    return any(marker in s for marker in MENTION_MARKERS)


def days_until(close_time: str | None, now: datetime) -> float | None:
    if not close_time:
        return None
    try:
        closes = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (closes - now).total_seconds() / 86400.0


def favorite(market: Market) -> tuple[str, float] | None:
    """The side this theory would buy, and the ask it would pay.

    Both sides are eligible, because the theory's cells are signed: the
    favorite band harvests compression, the fade band harvests the opposite
    sign where a cell measures it. Which one a market lands in is decided by
    `cells.price_bin`, not here -- this only picks the side whose ask is
    quotable and lets the bin decide whether any cell claims it.
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


def cell_of(candidate: Candidate) -> str | None:
    """The cell key a screened candidate belongs to."""
    return getattr(candidate, "_cell", None) or _cell_cache.get(
        candidate.legs[0].market.ticker
    )


#: Candidate is a frozen slots dataclass, so the cell cannot be attached to
#: it directly. Keyed by ticker, refreshed every screen() call -- the screen
#: is the only writer and `price()` the only reader, both inside one run.
_cell_cache: dict[str, str] = {}


def screen(
    board: list[Market],
    now: datetime | None = None,
    categories: dict[str, str] | None = None,
    max_spread: float = MAX_SPREAD,
    min_volume: float = MIN_VOLUME,
) -> ScreenResult:
    """Bin the board into cells; drop what no cell claims.

    `categories` maps series ticker -> Kalshi category. It is passed in
    rather than fetched so the screen stays pure and testable; the live
    theory fills it from `/series` once per run.
    """
    now = now or datetime.now(timezone.utc)
    categories = categories or {}
    _cell_cache.clear()

    removed: dict[str, int] = {}
    out: list[Candidate] = []

    def drop(reason: str) -> None:
        removed[reason] = removed.get(reason, 0) + 1

    for market in board:
        if not market.is_open:
            drop("not_open")
            continue

        if _is_mention_family(market.series_ticker):
            drop("mention_family")
            continue

        days = days_until(market.close_time, now)
        if days is None or days < 0:
            drop("closed_or_unparseable")
            continue

        if market.volume is None or market.volume < min_volume:
            drop("volume")
            continue

        if market.spread is None or market.spread > max_spread:
            drop("spread")
            continue

        fav = favorite(market)
        if fav is None:
            drop("no_quote")
            continue
        side, price = fav

        category = categories.get(market.series_ticker or "")
        key = cells.cell_key(price=price, days_to_close=days,
                             category=category)
        if key is None:
            drop("no_cell")
            continue

        _cell_cache[market.ticker] = key
        out.append(Candidate(
            legs=(Leg(market=market, side=side, price=price),),
            days_to_close=days,
        ))

    return ScreenResult(
        candidates=tuple(out),
        funnel={
            "board_markets": len(board),
            "survivors": len(out),
            "cells_hit": len(set(_cell_cache.values())),
        },
        gate_removed=removed,
    )
