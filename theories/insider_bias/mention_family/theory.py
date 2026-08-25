"""Contract adapter for the fully mechanical mention_family theory.

Wraps find_candidates/rank unchanged. The contract path is the VALIDATED
14-day horizon only (empty confidence_suffix); rank_preview and its
"_preview_*" suffixes remain a deliberate, directly-callable ad-hoc path
outside the contract -- a wider horizon changes what edge_basis a caller
may honestly attach, which is why they are two functions (spec 3.1).

price() and mention_bucket.record() both build their rationale through
mention_bucket._rationale_for(), so a row written through finish() is
indistinguishable from one written through record() -- tested against the
ledger, not assumed.
"""

from __future__ import annotations

from dataclasses import replace

from theories.insider_bias.mention_family import mention_bucket
from tools.domain import ScreenResult
from tools.theory import Theory, TheoryContext


class MentionFamilyTheory(Theory):
    id = "mention_family"
    name = "Mention Family"
    version = 1
    uses_llm_judgment = False
    # Voluntary self-documentation: the deciding artifact is this module's
    # code. finish() records it with model='none (deterministic)', matching
    # mention_bucket.record_provenance's long-standing convention.
    prompts = {"other":
               "theories/insider_bias/mention_family/mention_bucket.py"}

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        hits = mention_bucket.find_candidates(ctx.board, now=ctx.now)
        return ScreenResult(
            candidates=tuple(hits),
            funnel={"board_markets": len(ctx.board),
                    "family_candidates": len(hits)},
        )

    def price(self, ctx, cands, verdicts=None):
        rates = mention_bucket.measured_rate(ctx.conn)
        ranked = mention_bucket.rank(list(cands), rates)
        return [replace(sc, rationale=mention_bucket._rationale_for(sc))
                for sc in ranked]
