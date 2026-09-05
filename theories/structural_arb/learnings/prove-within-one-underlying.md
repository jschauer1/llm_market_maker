# Prove relationships within one underlying

**Summary:** Establish that strikes describe the same quantity before applying interval containment or disjointness arithmetic.
**Applies to:** Multi-market Kalshi events containing separate ladders for players, teams, locations, or other subjects.
**Finding:** Measured (2026-08-29): grouping a replay by event alone inflated apparent violations by roughly 1,800 times because unrelated numeric ladders were compared; this establishes a proof-harness failure, not a market inefficiency.
**Do next time:** Build an auditable underlying key, reject contradictory metadata, and make ambiguous grouping fail closed.
**Evidence:** [THEORY.md — proof guards](../THEORY.md#decision-procedure-fully-mechanical-edge_basismodel); [liquidity study — wrong first answer](../studies/answer/2026-08-29-structural-arb-violation-liquidity/STUDY.md#a-wrong-first-answer-kept-here-because-it-is-the-trap)
**Revisit when:** Kalshi publishes a stable underlying identifier or new strike types require a different proof representation.
**Updated:** 2026-09-04
