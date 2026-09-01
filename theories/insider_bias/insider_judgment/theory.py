"""Contract adapter (OOP spec section 4.7): wraps the existing pipeline,
moves NO decision logic. screen.py, gate.py and the pipeline internals are
untouched; this file only converts shapes at the boundary.

Buckets and priors are lifted VERBATIM from THEORY.md's "Confidence
buckets" table. Changing either is a decision-procedure change and bumps
the version -- exactly like a threshold.

Note what is NOT here: no instance state. The funnel travels on the
ScreenResult, verdicts travel on the TheoryRun (see the spec's
_last_funnel post-mortem, section 4.4).
"""

from __future__ import annotations

from theories.insider_bias.insider_judgment import gate, pipeline
from tools.domain import Edge, ScoredCandidate, ScreenResult
from tools.theory import Theory, TheoryContext

#: THEORY.md "Confidence buckets": conservative priors, standing in only
#: until a bucket has MIN_BUCKET_N settled results.
PRIORS = {"strong": 4.0, "moderate": 2.0, "weak": 0.0}
BUCKETS = tuple(PRIORS)

FUNNEL_KEYS = ("board_markets", "screened_markets", "events", "gated_out",
               "survivors", "survivor_markets")


class InsiderJudgmentTheory(Theory):
    id = "insider_judgment"
    name = "Insider Judgment"
    version = 5
    uses_llm_judgment = True
    #: Stage 5 is the only judging stage. v5 removed stage 6, the main
    #: session's price-aware final review, which had been the sole path to
    #: `disposition='endorsed'` and so the sole path to a bet. It was never
    #: part of the procedure that earned this theory's evidence -- every
    #: backtest row, including the 314 out-of-sample rows behind the
    #: `strong-moderate-no` slice, was produced without it -- while on live
    #: rows it rejected 72 of the 79 candidates that slice's record
    #: entitled. What a bucketed candidate is worth is now decided by its
    #: segment's measured record via the promotion key (key v3), which is
    #: the mechanism built for exactly that call. `prompts/final_review.md`
    #: stays on disk, marked retired: eleven `judgment_runs` rows name it.
    prompts = {
        "analysis":
            "theories/insider_bias/insider_judgment/prompts/analysis.md",
    }

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        funnel = pipeline.run_mechanical_stages(ctx.board, ctx.now)
        return ScreenResult(
            candidates=tuple(funnel["survivor_candidates"]),
            funnel={k: funnel[k] for k in FUNNEL_KEYS},
            gate_removed={k: v for k, v in funnel["gate_counts"].items()
                          if k != gate.PLAUSIBLE},
        )

    def judgment_payload(self, cands):
        if not cands:
            return None
        # Rebuilt from the candidates handed in -- no instance state. The
        # payload is blind by whitelist; assert_blind re-checks inside.
        return pipeline.build_blind_payload(
            pipeline.dedupe_by_event(cands), cands)

    def price(self, ctx, cands, verdicts=None):
        verdicts = verdicts or {}
        rates = (ctx.bucket_rates(self.id, self.version)
                 if ctx.bucket_rates else {})
        out = []
        for c in cands:
            v = verdicts.get(c.key)
            if v is None:
                continue        # unjudged this run: unassessed remainder
            if v.bucket not in BUCKETS:
                raise ValueError(
                    f"unknown bucket {v.bucket!r}; this theory's declared "
                    f"scale is {BUCKETS}"
                )
            out.append(ScoredCandidate(
                candidate=c,
                edge=Edge.from_bucket(v.bucket, c.entry_price, rates, PRIORS),
                confidence=v.bucket,
                rationale=v.rationale,
                judged_blind=True,      # the payload provably carried no price
            ))
        return out
