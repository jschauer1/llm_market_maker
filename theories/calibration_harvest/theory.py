"""calibration_harvest -- the Theory the registry discovers.

Fully mechanical: no gate, no judgment, no prompts, no provenance. The whole
decision path is `screen()` binning the board into cells and `price()`
looking each cell's measured rate up. That is the point -- CLAUDE.md prefers
statistics to judgment wherever the thesis allows, and "a measured rate
against an ask" is arithmetic.

`cell_rates` is injected rather than read from the DB inside `price()` so the
theory stays testable with no database, and so a caller can price the same
board against an in-sample and an out-of-sample rate table without touching
the class. The live path fills it from `collect.py`'s measurement.
"""

from __future__ import annotations

from tools.domain import Candidate, Edge, ScoredCandidate
from tools.theory import Theory, TheoryContext
from theories.calibration_harvest import cells, screen as screen_mod


class CalibrationHarvestTheory(Theory):
    id = "calibration_harvest"
    name = "Calibration Harvest"
    # v3 (2026-09-01): ONE run per floor against a COMPLETE category map.
    # The domain axis had been collapsing silently -- `categories` is only
    # a label map, `screen()` has no population filter, and the floor drove
    # it twice a day with a weather-only then a politics-only map. Each run
    # screened the whole board and labelled the other's population `other`:
    # 9,220 markets recorded twice, 9,123 of them domain-collapsed. The map
    # now comes from `collect.all_series_categories()` (one `/series`
    # fetch, all 13,687 series), and `other` is split from `unmapped` so a
    # partial map can never again pass for a residual. See THEORY.md
    # Version and forward_cells.OTHER_QUARANTINED_BELOW_VERSION.
    #
    # v2 (2026-08-29): the Wilson bound counts SETTLEMENT DAYS, not rows.
    # The theory already refused to call a cell measured below
    # MIN_CELL_DAYS because rows are not independent draws; computing the
    # bound on n undid that exactly where it decides to commit money.
    # See cells.cell_edge and THEORY.md Version.
    version = 3
    uses_llm_judgment = False
    prompts: dict = {}

    def __init__(
        self,
        categories: dict[str, str] | None = None,
        cell_rates: dict[str, dict] | None = None,
    ):
        #: series ticker -> Kalshi category. Injected; the live runner
        #: fetches it once per run from /series.
        self.categories = categories or {}
        #: cell key -> {"wins": int, "n": int, "n_days": int}
        self.cell_rates = cell_rates or {}

    def screen(self, ctx: TheoryContext):
        return screen_mod.screen(
            ctx.board, now=ctx.now, categories=self.categories
        )

    def price(self, ctx: TheoryContext, cands: list[Candidate],
              verdicts=None) -> list[ScoredCandidate]:
        """Look up each candidate's cell and price against its measured rate.

        A cell with no rows yet is priced at its own ask -- edge zero, basis
        `model` -- rather than skipped. Recording it costs nothing, and the
        row settles, which is how the cell acquires the rows that would let
        it be measured later. What keeps it out of the user's hands is
        `disposition`/`edge_basis`, not omission from the ledger.
        """
        scored: list[ScoredCandidate] = []
        for cand in cands:
            leg = cand.legs[0]
            key = screen_mod.cell_of(cand)
            rate = self.cell_rates.get(key or "")

            if rate is None:
                edge = Edge(
                    pts_net=0.0, basis="model", pts_gross=0.0,
                    fee_pts=cells.fee_pts(leg.price), model_prob=None,
                )
                rationale = (
                    f"cell {key}: no measured rows yet. Recorded so the "
                    f"cell accrues settlements; not a recommendation."
                )
            else:
                ce = cells.cell_edge(
                    wins=rate["wins"], n=rate["n"],
                    n_days=rate["n_days"], ask=leg.price,
                )
                edge = Edge(
                    pts_net=ce.pts_net, basis=ce.basis,
                    pts_gross=ce.pts_gross, fee_pts=ce.fee_pts,
                    model_prob=ce.model_prob,
                )
                rationale = (
                    f"cell {key}: Wilson-lower rate {ce.model_prob:.3f} "
                    f"from {rate['wins']}/{rate['n']} over "
                    f"{rate['n_days']} settlement days, vs ask "
                    f"{leg.price:.2f} + {ce.fee_pts:.2f}pts fees "
                    f"-> {ce.pts_net:+.2f}pts net ({ce.basis})."
                )
                if ce.basis == "model":
                    reason = ("n" if rate["n"] < cells.MIN_CELL_N
                              else "settlement days")
                    rationale += (
                        f" Not `measured`: too few {reason} "
                        f"(floors are n>={cells.MIN_CELL_N}, "
                        f"n_days>={cells.MIN_CELL_DAYS})."
                    )

            # The cell must be queryable, not just readable in prose:
            # `collect.cell_rates` reads it out of `extra_json`, and it is
            # the whole reason an unmeasured cell's rows are recorded at
            # all. Live rows carried it only in `rationale` until
            # 2026-08-29, so none of them could ever feed the grid.
            parts = (key or "").split("|")
            extra = {
                "cell": key,
                "domain": parts[0] if len(parts) == 3 else None,
                "horizon_bin": parts[1] if len(parts) == 3 else None,
                "price_bin": parts[2] if len(parts) == 3 else None,
                "series_ticker": leg.market.series_ticker,
                "days_to_close_at_entry": cand.days_to_close,
            }
            scored.append(ScoredCandidate(
                candidate=cand,
                edge=edge,
                rationale=rationale,
                judged_blind=None,
                disposition="screened",
                extra=extra,
            ))
        return scored
