# A mined tail starts with no evidence

**Summary:** Register a promising post-hoc threshold as its own slice and exclude the discovery run from its evidence.
**Applies to:** `extreme-imbalance`, defined as absolute volume-weighted taker imbalance at least 0.9 under the parent procedure.
**Finding:** Unconfirmed (2026-09-01): the preregistered single-name rule failed, while the extreme tail looked positive across several partitions; because the tail threshold was mined from that run, those checks narrow explanations but cannot establish the slice's edge.
**Do next time:** Declare the mining run, keep the moderate-imbalance complement accruing, and wait for independent event clusters and settlement days before ranking the slice.
**Evidence:** [backtests/RESULTS.md — pre-registered rule failed](../backtests/RESULTS.md#headline-the-pre-registered-rule-failed); [backtests/RESULTS.md — tail](../backtests/RESULTS.md#what-is-there-instead-a-tail-not-a-gradient); run id `backtest-2026-09-01-takerflow`
**Revisit when:** The slice reaches its independent evidence gates or later data removes the discontinuity.
**Updated:** 2026-09-04
