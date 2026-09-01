"""deadline-drift — buy NO late on unscheduled-affirmative-event markets.

Fully mechanical: no LLM anywhere in the decision path, tier A. Stage 1 is
`screen.py`; there is no stage 2 and none is planned.

## v2 (2026-09-01): recording starts, and it claims no edge

v1 shipped the audited allowlist and recorded **nothing** -- `price()`
returned `[]` because `hazard_bins.json` did not exist, and it did not
exist because the allowlist could not produce a defensible cell. That was
the right call and it had a cost: the theory sat at `proposed` with n=0
while its 60-day archive window rolled forward and its evidence expired
upstream.

v2 widens the population to DD-1's (see `screen.py`) and starts recording
**observation rows** under the 2026-08-30 ruling: claimed edge 0, a
rationale saying outright that it is not a recommendation, disposition
`screened`. That ruling exists for exactly this case -- rows recorded so
that cells accrue settlements, whose aggregate measures the *board* and
not the decision procedure, and which therefore cannot carry a verdict on
whether the theory works.

**Why zero and not the measured +4.6.** The in-sample estimate over the
full fetchable history is +4.6 pts net at the tradeable price, CI
[+1.0, +8.0] over 94 event clusters. It is also **post-hoc**: the wide
population was chosen and measured in the same session, after a dozen
cuts. CLAUDE.md's pairing discipline makes that a hypothesis to
pre-register, never an edge to bet on the data that suggested it -- so
DD-1 is pre-registered in THEORY.md, its out-of-sample set is markets
settling after 2026-09-01, and these rows are how that set gets
collected. Claiming +4.6 here would bet the number on the data that
produced it and would rank as a recommendation through `promote`.
Claiming 0 cannot: `ranked_edge` is `edge_pts_net * credibility`, so a
zero-edge row is unrankable by construction.

`hazard_bins.json` stays absent and `price()` still refuses to compute a
binned edge from it, for the reason v1 gave: wiring a thin cell into live
pricing manufactures bets out of noise. Writing that file is what DD-1
clearing would license, and nothing before it.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.domain import Candidate, Edge, Fetch, ScoredCandidate, ScreenResult
from tools.theory import Theory, TheoryContext

from theories.deadline_drift import screen as dd_screen

BINS_PATH = Path(__file__).parent / "hazard_bins.json"

#: Days-remaining bin edges, coarsest thing the thesis needs: the claim is
#: about the late window, so the resolution that matters is *within* it.
DAY_BINS = (0, 3, 7, 14, 21)
#: Price bin edges across the entry band.
PRICE_BINS = (0.05, 0.15, 0.25, 0.40, 0.60)


def bin_key(yes_ask: float, days: float) -> str:
    def idx(v, edges):
        for i in range(len(edges) - 1, -1, -1):
            if v >= edges[i]:
                return i
        return 0
    return f"d{idx(days, DAY_BINS)}|p{idx(yes_ask, PRICE_BINS)}"


def load_bins() -> dict | None:
    if not BINS_PATH.exists():
        return None
    return json.loads(BINS_PATH.read_text(encoding="utf-8"))


#: The claimed edge on an observation row. Zero, and the type of zero
#: matters: `ranked_edge = edge_pts_net * credibility`, so this row can
#: never be promoted to a recommendation no matter what credibility the
#: theory later earns. See the module docstring.
OBSERVATION_EDGE = 0.0


class DeadlineDriftTheory(Theory):
    id = "deadline_drift"
    name = "Deadline Drift"
    version = 2
    uses_llm_judgment = False
    # Voluntary self-documentation: the deciding artifact is code.
    prompts = {"other": "theories/deadline_drift/screen.py"}

    def __init__(self, fetch: Fetch | None = None):
        self._fetch = fetch

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        cands, funnel, removed = dd_screen.screen(ctx.board, now=ctx.now)
        # A code gate drops silently inside families it thinks it knows,
        # so what it removed is reported by category on every run.
        return ScreenResult(candidates=tuple(cands), funnel=funnel,
                            gate_removed=removed)

    def price(self, ctx: TheoryContext, cands: list[Candidate],
              verdicts=None) -> list[ScoredCandidate]:
        bins = load_bins()
        if bins is None:
            return self._observations(ctx, cands)
        out = []
        for c in cands:
            leg = c.legs[0]
            key = bin_key(leg.market.yes_ask, c.days_to_close)
            cell = bins.get(key)
            if not cell or cell.get("n", 0) < bins.get("min_n", 30):
                continue
            p_yes = cell["p_yes"]
            gross = ((1.0 - p_yes) - leg.price) * 100.0
            fee = ctx.fee_pts(leg.price) if hasattr(ctx, "fee_pts") else 0.0
            out.append(ScoredCandidate(
                candidate=c,
                edge=Edge(pts_gross=gross, pts_net=gross - fee,
                          basis="model"),
                confidence=None,
                rationale=(f"bin {key}: P(YES)={p_yes:.3f} over n={cell['n']} "
                           f"settled; NO ask {leg.price:.3f}"),
            ))
        return out

    def _observations(self, ctx: TheoryContext, cands: list[Candidate]
                      ) -> list[ScoredCandidate]:
        """DD-1's forward test: rows that accrue settlements and claim nothing.

        The 2026-08-30 ruling governs how these are read: the aggregate
        calibration edge over observation rows measures the BOARD, not
        this decision procedure, so it can carry no verdict on whether
        the theory works and cannot move its lifecycle status. What it
        can do is collect DD-1's out-of-sample set, which is the only
        thing standing between this theory and evidence.
        """
        from theories.deadline_drift import population as pop_facts

        facts = pop_facts.load()
        index: dict = {}
        for m in ctx.board:
            index.setdefault(m.event_ticker, []).append(m)

        out = []
        for c in cands:
            leg = c.legs[0]
            extra = dd_screen.features(leg.market, index, facts)
            extra["test"] = "DD-1"
            extra["days_to_deadline"] = round(c.days_to_close, 3)
            # The probability DD-1 is measured against is the one a NO
            # buyer actually bets against -- `yes_bid`, which is
            # `1 - no_ask`, NOT `yes_ask`. Reading the field named "ask"
            # here is the defect that halved this theory's apparent edge
            # on 2026-09-01 (NOTES.md, correction 2), and it does not look
            # like a bug; it looks like following the rule.
            extra["yes_bid_implied"] = round(1.0 - leg.price, 4)
            extra["yes_ask_optimistic"] = leg.market.yes_ask
            out.append(ScoredCandidate(
                candidate=c,
                edge=Edge(pts_net=OBSERVATION_EDGE, basis="prior"),
                disposition="screened",
                extra=extra,
                rationale=(
                    "DD-1 observation row (pre-registered 2026-09-01), "
                    "NOT A RECOMMENDATION and not a bet. Recorded so this "
                    "population's out-of-sample settlements accrue: DD-1 "
                    "predicts realized P(YES) at least 3 pts below the "
                    f"implied yes_bid {1.0 - leg.price:.3f}, entering the "
                    f"first day inside 21 days of the stated deadline "
                    f"({c.days_to_close:.1f}d) at the payable NO ask "
                    f"{leg.price:.3f}. Claimed edge is 0 on purpose -- the "
                    "in-sample estimate (+4.6 pts net, CI [+1.0, +8.0], 94 "
                    "event clusters) is post-hoc over the data that "
                    "suggested this population, so it vouches for nothing "
                    "until these rows settle."),
            ))
        return out
