# A bucket contributes edge, not probability

**Summary:** Transfer a bucket's realized improvement over its own prices, then let the candidate's quote affect fees and payability.
**Applies to:** Judgment buckets spanning heterogeneous entry prices after minimum row and settlement-day gates.
**Finding:** Measured (2026-08-29): treating a pooled bucket win rate as every candidate's probability made claimed edge move one-for-one with price and minted positive edge on cheap gate-leaked rows; replacing it with realized edge fixed the interpretation, but earlier cohorts retain their original arithmetic.
**Do next time:** Store mean entry price with the bucket rate, require day spread, and label assumptions as priors. Since v7, bound the transferred probability to `[0, 1]` and recompute gross/net from it; an additive edge cannot exceed binary payout headroom.
**Evidence:** [THEORY.md — Version 4 bucket correction](../THEORY.md#version); [NOTES.md — a bucket contributes an edge](../notes/archive/NOTES.md#2026-08-29-cont--v4-a-bucket-contributes-an-edge-not-a-probability)
**Revisit when:** Buckets condition on price bands directly or the pricing contract changes.
**Updated:** 2026-09-05
