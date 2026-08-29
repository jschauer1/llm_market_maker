"""deadline-drift stage 1 — the audited allowlist screen. No model.

The population is markets that resolve YES only if a discrete,
**unscheduled affirmative event** occurs by a deadline: charged before D,
pardoned before D, traded before D, manager out before D, IPO confirmed
before D, debut before D.

**Why an allowlist rather than a general rules-text screen.** Five audit
rounds (`studies/2026-08-29-deadline-drift-classifier-audit/`) established
that a *board-wide* mechanical screen cannot reach the spec's 10%
misclassification bar. Rounds 1-4 tuned regex to a plateau near 15%; round
5 added Kalshi's own `mutually_exclusive` flag and a price-partition test
and came in at 12%, not distinguishable from round 4. The residue is
multi-destination "which branch" markets, which are semantic.

Round 5b then audited the allowlist **exhaustively** -- it is a series-level
construct, so all 70 surviving series were inspected, with no sampling error
at all -- and found 70/70 genuinely per-subject: every sibling is a
different subject (a different player traded, official pardoned, leader
out), never a branch of one outcome. 0 carry `mutually_exclusive=True`;
0 are priced as partitions.

So this screen is a *family* rule, not a phrasing rule, and the structural
exclusions are kept on top of it as a guard. That combination is what was
audited, and the guard is what removes `KXUKCABOUT` ("who is **next** to
leave the Burnham Cabinet" -- 23 markets, a pure partition that the family
suffix rule would otherwise admit).

**The price-partition test carries a lower bound here that round 5's frozen
classifier lacked.** Session 09 found the defect: with no floor, any >=3
same-deadline siblings summing <=1.05 counted as a partition, including
unrelated longshots. Measured, 281 of 318 exclusions were spurious --
`KXCOACHOUTNFL` is 22 *independent* coach hazards summing 0.13. A partition
of one outcome sums to about a dollar, so the band is two-sided.
"""

from __future__ import annotations

import re
from collections import defaultdict

from tools.domain import Candidate, Leg, Market

#: Series families whose markets are per-subject hazards by construction.
#: A *family* rule, so a newly listed series inside a known family joins
#: automatically; the structural guard below still applies to it.
ALLOW_PREFIXES = (
    "KXFEDERALCHARGE", "KXTRUMPPARDON", "KXNBATRADE", "KXNFLTRADE",
    "KXIPO", "KXNCAAFCONFLEAVE", "KXMLBDEBUT",
)
ALLOW_SUFFIXES = ("OUT", "ANNOUNCEOUT")

BY_DEADLINE = re.compile(
    r"\b(?:before|by|on or before|no later than)\s+"
    r"(?:\w+\s+\d{1,2},\s*\d{4}|\d{4}-\d{2}-\d{2}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2})",
    re.IGNORECASE)

#: A partition of one outcome sums to about a dollar. Two-sided on purpose:
#: see the module docstring on the 281-of-318 spurious exclusions.
PARTITION_SUM = (0.90, 1.05)
PARTITION_MIN_LEGS = 3

#: Entry band. Above it the market believes the event happened or is
#: locked; below it fees eat the residual.
ENTRY_BAND = (0.05, 0.60)
MAX_DAYS_TO_CLOSE = 21
MIN_VOLUME = 100.0


def in_allowlist(series_ticker: str | None) -> bool:
    s = series_ticker or ""
    return (any(s.startswith(p) for p in ALLOW_PREFIXES)
            or any(s.endswith(x) for x in ALLOW_SUFFIXES))


def _price(m: Market) -> float | None:
    for v in (m.mid, m.yes_ask, m.last_price):
        if v is not None:
            return float(v)
    return None


def _deadline(m: Market) -> str | None:
    hit = BY_DEADLINE.search(m.rules_primary or "")
    return hit.group(0).lower() if hit else None


def partition_events(board: list[Market]) -> set[str]:
    """Events the market prices as a partition of one outcome.

    Siblings at *different* deadlines are a date ladder -- nested, not
    exclusive -- and are exempt: without that exemption the rule kills
    `KXALITOOUT` at four deadlines, which cost 88 false positives when
    first measured.
    """
    by_event: dict[str, list[Market]] = defaultdict(list)
    for m in board:
        by_event[m.event_ticker].append(m)
    lo, hi = PARTITION_SUM
    out = set()
    for ev, ms in by_event.items():
        if len(ms) < PARTITION_MIN_LEGS:
            continue
        deadlines = {_deadline(m) for m in ms}
        if len(deadlines) != 1 or None in deadlines:
            continue
        prices = [p for p in (_price(m) for m in ms) if p is not None]
        if prices and lo <= sum(prices) <= hi:
            out.add(ev)
    return out


def population(board: list[Market]) -> list[Market]:
    """Every allowlist market that survives the structural guard.

    No price or horizon filter -- this is the set hazard bins are
    estimated over, and restricting it to the entry band would condition
    the base rate on the very price the edge is measured against.
    """
    partitions = partition_events(board)
    out = []
    for m in board:
        if not in_allowlist(m.series_ticker):
            continue
        if not BY_DEADLINE.search(m.rules_primary or ""):
            continue
        if m.event.get("mutually_exclusive") is True:
            continue
        if m.event_ticker in partitions:
            continue
        out.append(m)
    return out


def screen(board: list[Market], *, now) -> tuple[list[Candidate], dict]:
    """Tradeable candidates: NO on allowlist markets in the late window."""
    from tools.timeutil import days_until

    pop = population(board)
    lo, hi = ENTRY_BAND
    cands, funnel = [], {"board_markets": len(board), "population": len(pop)}
    dropped = defaultdict(int)
    for m in pop:
        if not m.is_open:
            dropped["closed"] += 1
            continue
        days = days_until(m.close_time, now=now)
        if days is None or days > MAX_DAYS_TO_CLOSE or days < 0:
            dropped["outside_horizon"] += 1
            continue
        if m.yes_ask is None or not lo <= m.yes_ask <= hi:
            dropped["outside_entry_band"] += 1
            continue
        if m.no_ask is None or not 0.0 < m.no_ask < 1.0:
            dropped["no_ask_unavailable"] += 1
            continue
        if (m.volume or 0.0) < MIN_VOLUME:
            dropped["below_volume_floor"] += 1
            continue
        cands.append(Candidate(
            legs=(Leg(market=m, side="no", price=m.no_ask),),
            days_to_close=days))
    funnel.update(dropped)
    funnel["candidates"] = len(cands)
    return cands, dict(funnel)
