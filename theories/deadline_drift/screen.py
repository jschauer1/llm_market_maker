"""deadline-drift stage 1 — the DD-1 population screen. No model.

The population is markets that resolve YES only if a discrete,
**unscheduled affirmative event** occurs by a deadline: charged before D,
pardoned before D, traded before D, manager out before D, IPO confirmed
before D, debut before D.

## v2 (2026-09-01): the allowlist is no longer the shipped population

Everything below the "allowlist" heading is retained because it is what
v1 shipped, because `in_allowlist` is DD-2-adjacent history, and because
the structural guard it introduced is reused verbatim by the wide screen.
**It is no longer what `screen()` selects.** The shipped population is now
DD-1's, defined in THEORY.md and implemented in `wide_population` at the
bottom of this module.

The reason is measured, not aesthetic. Over the entire fetchable
by-deadline history (1,908 settled markets in 962 series), priced at the
NO ask a buyer actually pays and clustered by event:

    allowlist -- what v1 shipped        -1.0 pts   CI [-9.8, +5.7]   22 clusters
    wide by-deadline hazard stratum     +4.6 pts   CI [+1.0, +8.0]   94 clusters

The allowlist row is not evidence against the thesis; it is **no evidence
either way** -- 70 series is too thin a slice of the board to measure
anything inside a 60-day archive window. The allowlist was adopted on
2026-08-29 to preserve tier A back when a structural LLM gate was thought
to cost it, and CLAUDE.md's "Structural gates keep tier A" removed that
price on the same day. **The restriction, not the thesis, is what kept
this theory unmeasurable.** See NOTES.md 2026-09-01.

## Why an allowlist was chosen in v1, and what replaced it

Five audit
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


# ---------------------------------------------------------------------
# v2 — the DD-1 population
# ---------------------------------------------------------------------


def days_to_deadline(m: Market, *, now) -> float | None:
    """Days until the deadline STATED IN THE RULES, never the close time.

    This is correction 1 (NOTES.md, 2026-08-29) applied to the live
    screen. On a "does X happen by D" market the actual close is a
    *function of the outcome* -- a NO runs to its deadline, a YES stops
    the moment the event fires -- so `close_time` is only a sound anchor
    for a market that has not resolved yet, and only by luck.

    Measured on today's board it is *usually* luck that holds: across
    4,365 live DD-1 markets the median `close_time - deadline` is +0.56
    days (Kalshi closes at 03:59Z the following morning) and 0 of the 46
    markets inside the entry window differ by more than 1.5 days. That is
    a reason to expect the two anchors to agree live, never a reason to
    read the one that stops being true the moment it matters.
    """
    from theories.deadline_drift.collect_settled import parse_deadline
    import datetime as _dt

    stated = parse_deadline(m.rules_primary)
    if stated is None:
        return None
    return (_dt.datetime.fromisoformat(stated) - now).total_seconds() / 86400.0


def wide_population(board: list[Market], facts: dict | None = None
                    ) -> tuple[list[Market], dict]:
    """DD-1's population: the by-deadline hazard stratum, minus partitions.

    Pre-registered in THEORY.md as `hazard.stratum() == "hazard"` minus
    `hazard.partition_families()`. Three things are worth being explicit
    about, because each one is a place a later session could reasonably
    have expected something different:

    **The partition exclusion is applied with the instruments each
    population affords.** `partition_families` reads settled outcomes and
    cannot run on a live market that has never settled, so live it is
    applied as the *series* set it returns (persisted by
    `population.py`), alongside the two live partition detectors the v1
    screen already carried -- Kalshi's `mutually_exclusive` envelope flag
    and the price-partition test. These are three instruments aimed at
    one exclusion, not three different exclusions.

    **`branch_families` is deliberately NOT applied.** DD-1 does not name
    it, and it is documented in `hazard.py` as a cleaning tool rather than
    a screen. It is recorded per row as a feature instead, so the
    pre-registered population stays exactly what DD-1 says while the
    cleaner subset remains recoverable as a registered slice later. The
    same reasoning is why nothing here filters on DD-2's recurrence split.

    **Nothing here is an entry filter.** Price, horizon and volume live in
    `screen()`; restricting the population by the entry band would
    condition the base rate on the very price the edge is measured
    against.
    """
    from theories.deadline_drift import hazard, population as pop_facts

    facts = pop_facts.load() if facts is None else facts
    excluded = set(facts.get("partition_families") or ())
    partitions = partition_events(board)

    out: list[Market] = []
    removed = defaultdict(int)
    for m in board:
        if not BY_DEADLINE.search(m.rules_primary or ""):
            removed["not_by_deadline"] += 1
            continue
        stratum = hazard.stratum(m.rules_primary or "")
        if stratum != "hazard":
            # A code gate drops silently inside families it thinks it
            # knows, so every removal is reported by category.
            removed[f"stratum_{stratum}"] += 1
            continue
        if (m.series_ticker or "") in excluded:
            removed["partition_family_learned"] += 1
            continue
        if m.event.get("mutually_exclusive") is True:
            removed["mutually_exclusive_flag"] += 1
            continue
        if m.event_ticker in partitions:
            removed["priced_as_partition"] += 1
            continue
        out.append(m)
    return out, dict(removed)


def features(m: Market, board_index: dict, facts: dict) -> dict:
    """Structural context recorded per row, never used to filter.

    Everything here is fixed at listing time and carries no outcome
    information, so it is available at the decision point and legal as a
    registered-slice predicate later ("data over recorded fields").
    """
    from theories.deadline_drift import population as pop_facts

    sibs = board_index.get(m.event_ticker, ())
    asks = [s.yes_ask for s in sibs if s.yes_ask is not None]
    return {
        "series": m.series_ticker,
        # MUST be spelled `event_ticker`: `score.cluster_key` reads exactly
        # this key to cluster uncertainty at the event level, and falls
        # back to stripping the ticker's last dash-segment when it is
        # absent. On this population that fallback is wrong for 4 of 46
        # rows, and one of them (KXMEDIARELEASEDATEAHS-26-SEP19-AME, whose
        # event is KXMEDIARELEASEDATEAHS-26) it SPLITS a real event into
        # several -- which manufactures precision rather than losing it.
        # Clustering matters more here than almost anywhere: one event
        # supplied 22 of the first 46 rows.
        "event_ticker": m.event_ticker,
        # DD-1's kill criterion 3 is "the effect exists only where
        # liquidity is worst", and the in-sample gradient that has to be
        # re-checked was measured on OPEN INTEREST -- a level, meaningful
        # at a point in time the way a per-period volume is not. The
        # ledger records `spread_at_call` and `volume_at_call` for free
        # but has no column for open interest, and the value at the
        # decision point cannot be recovered afterwards: this theory has
        # already lost this exact field twice to collectors that read it,
        # filtered on it and persisted neither (NOTES.md, 2026-09-01).
        # Recording it here is what makes the theory's own kill criterion
        # checkable when these rows settle.
        "open_interest": m.open_interest,
        # DD-2's pre-registered split: does this family teach its own
        # base rate, or is it a one-off with no reference class?
        "recurring": pop_facts.is_recurring(m.series_ticker, facts),
        "settled_events": facts.get("settled_events_per_series", {}).get(
            m.series_ticker or "", 0),
        # Not a filter -- see wide_population's docstring.
        "branch_family": (m.series_ticker or "") in set(
            facts.get("branch_families") or ()),
        "in_allowlist": in_allowlist(m.series_ticker),
        # The AGT/Big-Brother shape: a fixed-k elimination event is not a
        # per-subject hazard even when it is not a one-winner partition.
        # Recorded so that shape is minable without guessing a rule for it
        # from two settled events.
        "event_legs": len(sibs),
        "event_ask_sum": round(sum(asks), 4) if asks else None,
    }


def screen(board: list[Market], *, now, facts: dict | None = None
           ) -> tuple[list[Candidate], dict]:
    """Tradeable candidates: NO in the late window, DD-1's population.

    The entry rule is part of the hypothesis, not a detail: entering the
    **first** qualifying day measures +3.4 on this population in sample,
    and averaging over every qualifying day measures -1.7. The
    overpricing decays as the deadline approaches, which is what
    "deadline drift" means -- so a test that enters late measures
    nothing. Recording enforces it: the ledger's dedup key preserves
    `entry_price` and `first_seen_at` from the first sighting, so a
    market re-screened on later days keeps the price it first qualified
    at.
    """
    from theories.deadline_drift import population as pop_facts

    facts = pop_facts.load() if facts is None else facts
    pop, removed = wide_population(board, facts)
    lo, hi = ENTRY_BAND
    cands = []
    funnel = {"board_markets": len(board), "population": len(pop),
              "facts_from_markets": facts.get("built_from_markets", 0)}
    dropped = defaultdict(int)
    for m in pop:
        if not m.is_open:
            dropped["closed"] += 1
            continue
        days = days_to_deadline(m, now=now)
        if days is None:
            dropped["no_deadline_parsed"] += 1
            continue
        if days > MAX_DAYS_TO_CLOSE or days < 0:
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
    return cands, dict(funnel), dict(removed)
