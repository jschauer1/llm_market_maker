"""Contract adapter for the fully mechanical mention_family theory.

Wraps find_candidates/rank unchanged. The contract path is the VALIDATED
14-day horizon only (empty confidence_suffix); rank_preview and its
"_preview_*" suffixes remain a deliberate, directly-callable ad-hoc path
outside the contract -- a wider horizon changes what edge_basis a caller
may honestly attach, which is why they are two functions (spec 3.1).

The rationale strings replicate mention_bucket.record()'s exactly, so a
row written through finish() is indistinguishable from one written through
record() -- tested against the ledger, not assumed.
"""

from __future__ import annotations

from theories.insider_bias import screen
from theories.insider_bias.mention_family import mention_bucket
from tools.domain import (Candidate, Edge, Leg, Market, ScoredCandidate,
                         ScreenResult)
from tools.theory import Theory, TheoryContext


def _to_candidate(c: dict) -> Candidate:
    return Candidate(
        legs=(Leg(market=Market.from_mapping(c), side=c["fav_side"],
                  price=c["entry_price"]),),
        days_to_close=c["days_to_close"],
    )


def _rationale(r: dict) -> str:
    """Byte-for-byte the text mention_bucket.record() writes."""
    bin_rate_note = (f"measured rate for bucket {r['bucket']} "
                     f"({mention_bucket.MEASURED_RATE_RUN_ID})")
    basis_note = (
        f"{bin_rate_note}, applied directly"
        if r["edge_basis"] == "measured"
        else (
            f"{bin_rate_note} APPLIED AS AN EXTRAPOLATION to a "
            f"days-to-close horizon the backtest never tested "
            f"(>{screen.MAX_DAYS_AHEAD:.0f} days) -- a modeling "
            f"assumption, not a measurement of this population"
        )
    )
    return (
        f"Mechanical mention_family bucket, no judgment applied: "
        f"{basis_note}. Volume (${r.get('volume', 0):,.0f}) is a "
        f"tiebreaker only, not part of the edge -- see "
        f"mention_bucket.py module docstring."
    )


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
            candidates=tuple(_to_candidate(h) for h in hits),
            funnel={"board_markets": len(ctx.board),
                    "family_candidates": len(hits)},
        )

    def price(self, ctx, cands, verdicts=None):
        rates = mention_bucket.measured_rate(ctx.conn)
        ranked = mention_bucket.rank([dict(c) for c in cands], rates)
        out = []
        for r in ranked:
            measured = rates.get(r["bucket"]) or {}
            out.append(ScoredCandidate(
                candidate=_to_candidate(r),
                edge=Edge(pts_net=r["edge_pts_net"], basis=r["edge_basis"],
                          model_prob=measured.get("win_rate")),
                confidence=r["bucket"],
                rationale=_rationale(r),
            ))
        return out
