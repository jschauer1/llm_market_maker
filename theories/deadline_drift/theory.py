"""deadline-drift — buy NO late on unscheduled-affirmative-event markets.

Fully mechanical: no LLM anywhere in the decision path, `edge_basis="model"`,
tier A. Stage 1 is `screen.py`; there is no stage 2 and none is planned.

**This theory is `proposed`, not `testing`, and `price()` says so.** The edge
is `(1 - P_hat(YES | price bin, days-remaining bin)) - no_ask - fees`, where
`P_hat` comes from hazard bins estimated over settled allowlist history.
Those bins do not exist yet -- collecting them is the expensive,
rate-limited step, and the spec's section 7 forbids collecting them until
the population is settled. The population is now settled (round 5b), so
that is the next step and the only thing between this and `testing`.

`price()` therefore returns nothing while `hazard_bins.json` is absent,
rather than inventing a prior. There is deliberately no `edge_basis`
meaning "it felt about right", and a placeholder here would be exactly that.
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


class DeadlineDriftTheory(Theory):
    id = "deadline_drift"
    name = "Deadline Drift"
    version = 1
    uses_llm_judgment = False
    # Voluntary self-documentation: the deciding artifact is code.
    prompts = {"other": "theories/deadline_drift/screen.py"}

    def __init__(self, fetch: Fetch | None = None):
        self._fetch = fetch

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        cands, funnel = dd_screen.screen(ctx.board, now=ctx.now)
        return ScreenResult(candidates=tuple(cands), funnel=funnel)

    def price(self, ctx: TheoryContext, cands: list[Candidate],
              verdicts=None) -> list[ScoredCandidate]:
        bins = load_bins()
        if bins is None:
            # No bins, no edge. Returning [] is the honest answer while the
            # measurement that defines this theory has not been made.
            return []
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
