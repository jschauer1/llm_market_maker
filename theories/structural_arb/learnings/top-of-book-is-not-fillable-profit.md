# Top-of-book existence is not fillable profit

**Summary:** Measure joint executable depth after refreshing all legs, even when the payout inequality is mathematically riskless.
**Applies to:** Multi-leg arbitrage where one dust quote can create a large apparent return.
**Finding:** Measured (2026-08-27 and amended 2026-09-01): liquid-looking violations repeatedly had negligible size at the arbitrage prices; lifetime volume did not substitute for depth, and the only attractive liquid example disappeared after its dust level moved.
**Do next time:** Requote every leg, derive asks from the opposite bids correctly, walk baskets in lockstep, and report fillable floor profit.
**Evidence:** [THEORY.md — depth gate](../THEORY.md#decision-procedure-fully-mechanical-edge_basismodel); [liquidity study — What this means](../studies/answer/2026-08-29-structural-arb-violation-liquidity/STUDY.md#what-this-means)
**Revisit when:** Historical order books become available or execution can atomically fill all legs.
**Updated:** 2026-09-04
