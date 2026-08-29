"""Pure arithmetic for the structural-arb scanner.

Everything here is deterministic math over `tools.domain.Market` objects:
no network, no database, no model. `theory.py` owns fetching (the event
mutually-exclusive flag, live re-quotes); this module owns deciding.

Three violation kinds, every one riskless-net-of-fees at top-of-book when
it fires:

- ``nested_pair``: A's YES set provably contains B's. Buy YES(A) at ask +
  NO(B) at ask. Pays 1 always, 2 when the outcome lands in A minus B, so
  cost + fees < 1 is a guaranteed profit. (Equivalent statement:
  yes_ask(A) < yes_bid(B) — the subset is bid above the superset's ask.)
- ``no_basket``: k markets of one event, pairwise provably mutually
  exclusive (at most one can resolve YES). Buying NO on all k pays at
  least k-1, so sum(no_ask) + fees < k-1 is a guaranteed profit.
  Exclusivity is proven either from strike geometry (this module) or from
  the event envelope's ``mutually_exclusive`` flag (theory.py fetches it;
  this module only receives the verdict).
- YES-side basket sums (sum(yes_ask) < 1 on an exhaustive partition) are
  deliberately NOT implemented in v1: the payout floor needs *at least
  one* leg to resolve YES, i.e. exhaustiveness, and neither the event
  flag ("at most one") nor strike endpoints (whose open/closed convention
  Kalshi does not publish per market) can prove it. See THEORY.md.

Boundary honesty: `greater`/`greater_or_equal`/`less`/`less_or_equal`
carry their closure in the name and are treated as known. `between` is
inclusive-looking on Kalshi but unverified, so its closure is UNKNOWN:
containment and disjointness proofs involving a `between` endpoint demand
strict inequality. A proof that cannot be completed is a non-finding, by
construction — this scanner's false positives cost real money and its
false negatives cost nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from tools.domain import Leg, Market
from tools.timeutil import days_until  # noqa: F401  (re-exported)
from tools.ladders import (NEG_INF, POS_INF, YesSet, underlying_key,  # noqa: F401
                           yes_set)
from tools.sizing import fee_pts

#: Required profit beyond fees, per leg, before a violation fires
#: (spec 2026-08-24: start at 1 cent per leg).
BUFFER_PER_LEG = 0.01

def _covers_lo(a: YesSet, b: YesSet) -> bool:
    """Provably: every outcome at/below B's lower edge that is in B is in A."""
    if a.lo == NEG_INF:
        return True
    if b.lo == NEG_INF:
        return False
    if a.lo < b.lo:
        return True
    if a.lo > b.lo:
        return False
    # Equal finite edges: need A provably closed here, or B provably open.
    return (a.boundary_known and a.lo_closed) or (
        b.boundary_known and not b.lo_closed)


def _covers_hi(a: YesSet, b: YesSet) -> bool:
    if a.hi == POS_INF:
        return True
    if b.hi == POS_INF:
        return False
    if a.hi > b.hi:
        return True
    if a.hi < b.hi:
        return False
    return (a.boundary_known and a.hi_closed) or (
        b.boundary_known and not b.hi_closed)


def contains(a: YesSet, b: YesSet) -> bool:
    """Provably A ⊇ B."""
    return _covers_lo(a, b) and _covers_hi(a, b)


def proper_contains(a: YesSet, b: YesSet) -> bool:
    """Provably A ⊇ B and not B ⊇ A (identical sets are one market priced
    twice, not a ladder relation)."""
    return contains(a, b) and not contains(b, a)


def _before(a: YesSet, b: YesSet) -> bool:
    """Provably every point of A is below every point of B."""
    if a.hi == POS_INF or b.lo == NEG_INF:
        return False
    if a.hi < b.lo:
        return True
    if a.hi > b.lo:
        return False
    # Touching edges: disjoint unless both could be closed at the point.
    return (a.boundary_known and not a.hi_closed) or (
        b.boundary_known and not b.lo_closed)


def disjoint(a: YesSet, b: YesSet) -> bool:
    """Provably A ∩ B = ∅."""
    return _before(a, b) or _before(b, a)


def intersects(a: YesSet, b: YesSet) -> bool:
    """Provably A ∩ B ≠ ∅ — an *interior* overlap, immune to closure
    doubt. Not the negation of `disjoint`: between the two proofs lies
    'cannot tell'."""
    lo = max(a.lo, b.lo)
    hi = min(a.hi, b.hi)
    return lo < hi  # a whole open interval in common needs no closure


def _fee(price: float) -> float:
    """Per-contract fee in dollars at `price`."""
    return fee_pts(price) / 100.0


def _ask(price: float | None) -> float | None:
    """An executable ask: present and strictly inside (0, 1]. A 0 ask is
    an empty book side, not a free contract."""
    if price is None or price <= 0.0 or price > 1.0:
        return None
    return price


@dataclass(frozen=True, slots=True)
class Finding:
    """One violation, fully priced. `cost` is the sum of leg asks, `fee`
    the summed per-contract fees in dollars (unrounded; an actual order
    rounds up to the cent — at multi-contract size the difference
    amortizes toward zero)."""

    kind: str                 # "nested_pair" | "no_basket"
    event_ticker: str
    legs: tuple[Leg, ...]
    min_payout: float
    max_payout: float
    note: str = ""

    @property
    def cost(self) -> float:
        return sum(leg.price for leg in self.legs)

    @property
    def fee(self) -> float:
        return sum(_fee(leg.price) for leg in self.legs)

    @property
    def profit_floor(self) -> float:
        """Guaranteed dollars per basket, after (unrounded) fees."""
        return self.min_payout - self.cost - self.fee

    @property
    def clears_buffer(self) -> bool:
        return self.profit_floor >= BUFFER_PER_LEG * len(self.legs)


def _nested_pair_findings(scalar: list[tuple[Market, YesSet]],
                          event_ticker: str) -> list[Finding]:
    out = []
    for a_m, a_s in scalar:
        ya = _ask(a_m.yes_ask)
        if ya is None:
            continue
        for b_m, b_s in scalar:
            if b_m.ticker == a_m.ticker:
                continue
            nb = _ask(b_m.no_ask)
            if nb is None:
                continue
            if not proper_contains(a_s, b_s):
                continue
            f = Finding(
                kind="nested_pair", event_ticker=event_ticker,
                legs=(Leg(market=a_m, side="yes", price=ya),
                      Leg(market=b_m, side="no", price=nb)),
                min_payout=1.0, max_payout=2.0,
                note=(f"YES {a_m.ticker} ⊇ YES {b_m.ticker}: "
                      f"yes_ask({ya:.2f}) + no_ask({nb:.2f}) < 1"),
            )
            if f.clears_buffer:
                out.append(f)
    return out


def _max_weight_disjoint(cands: list[tuple[Market, YesSet, float]],
                         ) -> list[tuple[Market, YesSet, float]]:
    """Exact max-total-saving pairwise-disjoint subset (weighted interval
    scheduling). k per event is small, so the O(k^2) predecessor scan is
    fine."""
    cands = sorted(cands, key=lambda t: (t[1].hi, t[1].lo))
    n = len(cands)
    best: list[float] = [0.0] * (n + 1)
    choice: list[tuple[int, bool]] = [(0, False)] * (n + 1)
    for i in range(1, n + 1):
        m, s, w = cands[i - 1]
        # last j (in sort order) provably disjoint from i — and, because
        # selection is chained through p, from everything chosen before j
        p = 0
        for j in range(i - 1, 0, -1):
            if _before(cands[j - 1][1], s):
                p = j
                break
        take = w + best[p]
        skip = best[i - 1]
        if take > skip:
            best[i] = take
            choice[i] = (p, True)
        else:
            best[i] = skip
            choice[i] = (i - 1, False)
    out = []
    i = n
    while i > 0:
        p, took = choice[i]
        if took:
            out.append(cands[i - 1])
        i = p if took else i - 1
    out.reverse()
    # The chain only verified each pick against its immediate predecessor.
    # With strict inequalities that is transitive; equal-endpoint closure
    # proofs are not, so re-verify the whole set and drop the cheaper
    # member of any unproven pair — sound, and at worst sub-optimal.
    changed = True
    while changed:
        changed = False
        for x in range(len(out)):
            for y in range(x + 1, len(out)):
                if not disjoint(out[x][1], out[y][1]):
                    victim = x if out[x][2] < out[y][2] else y
                    del out[victim]
                    changed = True
                    break
            if changed:
                break
    return out


def _scalar_no_basket(scalar: list[tuple[Market, YesSet]],
                      event_ticker: str) -> Finding | None:
    """Best NO basket over provably pairwise-disjoint strikes.

    Per-leg saving s = 1 - no_ask - fee; a set S of disjoint markets pays
    at least |S|-1, so its floor profit is sum(s) - 1. Only legs with
    s > BUFFER_PER_LEG can help, and the exact best subset among disjoint
    intervals is a weighted-interval-scheduling DP."""
    cands = []
    for m, s in scalar:
        na = _ask(m.no_ask)
        if na is None:
            continue
        saving = 1.0 - na - _fee(na)
        if saving > BUFFER_PER_LEG:
            cands.append((m, s, saving))
    if len(cands) < 2:
        return None
    chosen = _max_weight_disjoint(cands)
    if len(chosen) < 2:
        return None
    f = Finding(
        kind="no_basket", event_ticker=event_ticker,
        legs=tuple(Leg(market=m, side="no", price=_ask(m.no_ask))
                   for m, _, _ in chosen),
        min_payout=float(len(chosen) - 1), max_payout=float(len(chosen)),
        note=(f"{len(chosen)} pairwise-disjoint strikes (geometry); "
              "at most one can resolve YES"),
    )
    return f if f.clears_buffer else None


def _flag_no_basket(markets: list[Market], event_ticker: str,
                    ) -> Finding | None:
    """Best NO basket assuming the whole event is mutually exclusive.

    Arithmetic only — the caller must confirm the event envelope's
    mutually_exclusive flag before treating this as real. Any provable
    interior overlap between two scalar legs contradicts the flag and
    voids the event (returned findings never include such a pair)."""
    cands = []
    for m in markets:
        na = _ask(m.no_ask)
        if na is None:
            continue
        saving = 1.0 - na - _fee(na)
        if saving > BUFFER_PER_LEG:
            cands.append((m, yes_set(m), saving, underlying_key(m)))
    if len(cands) < 2:
        return None
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            _, si, _, ki = cands[i]
            _, sj, _, kj = cands[j]
            # Intervals only compare on one underlying; across
            # underlyings an "overlap" is two unrelated scales.
            if (si is not None and sj is not None and ki is not None
                    and ki == kj and intersects(si, sj)):
                return None  # flag would contradict geometry
    f = Finding(
        kind="no_basket", event_ticker=event_ticker,
        legs=tuple(Leg(market=m, side="no", price=_ask(m.no_ask))
                   for m, _, _, _ in cands),
        min_payout=float(len(cands) - 1), max_payout=float(len(cands)),
        note=(f"{len(cands)} legs; event flagged mutually_exclusive "
              "(at most one YES) — flag verified at scan time"),
    )
    return f if f.clears_buffer else None


def group_by_event(board: list[Market]) -> dict[str, list[Market]]:
    """Open markets with a real event, grouped. The shared sibling-group
    helper smile-smoothing will want lives here until it has a second
    caller (repo promotion rule)."""
    out: dict[str, list[Market]] = {}
    for m in board:
        if not m.is_open or not m.event_ticker:
            continue
        out.setdefault(m.event_ticker, []).append(m)
    return {k: v for k, v in out.items() if len(v) >= 2}


@dataclass(frozen=True, slots=True)
class ScanOutput:
    findings: tuple[Finding, ...]            # proven, buffer-clearing
    flag_candidates: tuple[Finding, ...]     # need the ME flag confirmed
    funnel: dict


def scan_events(events: dict[str, list[Market]]) -> ScanOutput:
    """Run every geometric check; separate out arithmetic hits that still
    need the event's mutually_exclusive flag. Best finding per (event,
    kind) — sibling findings in one event share legs and are one
    opportunity, not several."""
    findings: list[Finding] = []
    flag_cands: list[Finding] = []
    nested_raw = 0
    scalar_events = 0
    for ev, ms in sorted(events.items()):
        # Interval proofs are valid only among strikes over one
        # underlying quantity — an event routinely holds several (one
        # hits-ladder per player, one points-ladder per team).
        groups: dict[str, list[tuple[Market, YesSet]]] = {}
        for m in ms:
            s = yes_set(m)
            if s is None:
                continue
            key = underlying_key(m)
            if key is None:
                continue
            groups.setdefault(key, []).append((m, s))
        multi = [g for g in groups.values() if len(g) >= 2]
        if multi:
            scalar_events += 1
        nested: list[Finding] = []
        baskets: list[Finding] = []
        for scalar in multi:
            nested.extend(_nested_pair_findings(scalar, ev))
            basket = _scalar_no_basket(scalar, ev)
            if basket is not None:
                baskets.append(basket)
        nested_raw += len(nested)
        if nested:
            findings.append(max(nested, key=lambda f: f.profit_floor))
        if baskets:
            findings.append(max(baskets, key=lambda f: f.profit_floor))
        # The flag path sees every event; geometry already proved a
        # subset for some, so only keep a flag candidate that beats any
        # geometric basket from the same event.
        flag = _flag_no_basket(ms, ev)
        if flag is not None:
            geo = [f for f in findings
                   if f.event_ticker == ev and f.kind == "no_basket"]
            if not geo or flag.profit_floor > geo[0].profit_floor:
                flag_cands.append(flag)
    return ScanOutput(
        findings=tuple(findings),
        flag_candidates=tuple(flag_cands),
        funnel={
            "events_multi": len(events),
            "scalar_events": scalar_events,
            "nested_raw_violations": nested_raw,
            "geometry_findings": len(findings),
            "flag_candidates": len(flag_cands),
        },
    )


def refresh_finding(finding: Finding,
                    fresh: dict[str, Market]) -> Finding | None:
    """Re-decide one finding at fresh quotes. Pure arithmetic: `fresh`
    maps ticker -> Market carrying current asks (the caller patches fresh
    quotes onto the board market so strike raw fields survive).

    A nested pair needs both legs alive at their fresh asks. A NO basket
    may shed legs whose fresh saving no longer clears the per-leg buffer
    (a subset of a mutually-exclusive set is still mutually exclusive)
    but must keep >= 2 and still clear the whole buffer. A leg with no
    fresh quote is dead — a riskless claim on an unverified ask is not
    riskless."""
    if finding.kind == "nested_pair":
        legs = []
        for leg in finding.legs:
            q = fresh.get(leg.market.ticker)
            if q is None or not q.is_open:
                return None
            price = _ask(q.yes_ask if leg.side == "yes" else q.no_ask)
            if price is None:
                return None
            legs.append(Leg(market=q, side=leg.side, price=price))
        nf = Finding(kind=finding.kind, event_ticker=finding.event_ticker,
                     legs=tuple(legs), min_payout=1.0, max_payout=2.0,
                     note=finding.note)
        return nf if nf.clears_buffer else None

    legs = []
    for leg in finding.legs:
        q = fresh.get(leg.market.ticker)
        if q is None or not q.is_open:
            continue
        price = _ask(q.no_ask)
        if price is None:
            continue
        if 1.0 - price - _fee(price) <= BUFFER_PER_LEG:
            continue
        legs.append(Leg(market=q, side="no", price=price))
    if len(legs) < 2:
        return None
    nf = Finding(kind=finding.kind, event_ticker=finding.event_ticker,
                 legs=tuple(legs), min_payout=float(len(legs) - 1),
                 max_payout=float(len(legs)), note=finding.note)
    return nf if nf.clears_buffer else None


def describe(finding: Finding) -> str:
    """The audit line recorded as the opportunity's rationale."""
    legs = ", ".join(f"{leg.side.upper()} {leg.market.ticker} @ "
                     f"{leg.price:.2f}" for leg in finding.legs)
    note = f" {finding.note}." if finding.note else ""
    return (
        f"{finding.kind}: cost {finding.cost:.4f} + fees "
        f"{finding.fee:.4f} < guaranteed payout {finding.min_payout:.2f} "
        f"(max {finding.max_payout:.2f}); floor profit "
        f"{finding.profit_floor:.4f}/basket "
        f"({100 * finding.profit_floor / (finding.cost + finding.fee):.1f}% "
        f"riskless).{note} Legs: {legs}. Fees are unrounded "
        "per-contract; an actual order rounds up to the cent. Verify "
        "every leg's ask before entering any — quotes move, and a "
        "partial basket is not riskless."
    )


# --------------------------------------------------------------- depth
# Top-of-book existence and fillable size are different claims: opps
# 9248 and 9309 were both riskless at the quoted asks and both died
# 0.3-0.5 contracts deep. These two functions turn an orderbook into
# the size a basket can actually be filled at riskless prices.

def implied_ask_ladder(fp: dict | None,
                       side: str) -> list[tuple[float, float]]:
    """Executable asks for `side`, cheapest first, from an orderbook.

    `fp` is the API's `orderbook_fp`: `yes_dollars`/`no_dollars` are the
    resting BID lists as `[price, size]` (dollar strings, fractional
    sizes). Buying a side lifts the opposite side's bids, so each ask is
    `1 - opposite_bid` at that bid's size.
    """
    if not fp:
        return []
    opposite = fp.get("no_dollars" if side == "yes" else "yes_dollars")
    ladder = []
    for entry in opposite or []:
        try:
            bid, size = float(entry[0]), float(entry[1])
        except (TypeError, ValueError, IndexError):
            continue
        ask = 1.0 - bid
        if 0.0 < ask <= 1.0 and size > 0.0:
            ladder.append((ask, size))
    ladder.sort(key=lambda ps: ps[0])
    return ladder


def fillable_floor(ladders: list[list[tuple[float, float]]],
                   min_payout: float) -> tuple[float, float]:
    """(baskets, profit) fillable while every marginal basket stays
    riskless.

    Walks all legs' ask ladders in lockstep — the marginal basket always
    fills at the cheapest available level of every leg, so the greedy
    walk is exact. Stops when the marginal cost plus fees reaches
    `min_payout` (the book has un-crossed) or any leg's ladder runs out.
    """
    if not ladders or any(not lad for lad in ladders):
        return 0.0, 0.0
    idx = [0] * len(ladders)
    remaining = [lad[0][1] for lad in ladders]
    baskets = 0.0
    profit = 0.0
    while True:
        prices = [lad[i][0] for lad, i in zip(ladders, idx)]
        marginal = min_payout - sum(p + _fee(p) for p in prices)
        if marginal <= 0.0:
            return baskets, profit
        fill = min(remaining)
        baskets += fill
        profit += fill * marginal
        for j, lad in enumerate(ladders):
            remaining[j] -= fill
            if remaining[j] <= 1e-12:
                idx[j] += 1
                if idx[j] >= len(lad):
                    return baskets, profit
                remaining[j] = lad[idx[j]][1]
