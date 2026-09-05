---
title: Apply recorded backtest eligibility consistently to scoring and pricing
lane: maintenance
created: 2026-09-04
created_by: codex-dual-agent-support
author_context: Compatibility review of model attribution and the shared evidence policy
status: done
closed: 2026-09-04
resolution: Implemented shared production eligibility for scoring, bucket pricing, slices and settlement-day reports. Valid A/B replays count fully without a live prerequisite; contaminated, undocumented and mismatched replays remain diagnostic with exclusion reasons. Covered by private regression fixtures and independent review; existing saved derived scores were not recomputed.
---
The shared guide's "What counts as evidence" rule excludes tier C and
replays with no recorded tier. Current consumers do not all enforce that rule.

Observed in code at base revision `350fabf`:

- `tools/score.py` `bucket_rates` explicitly documents no tier filter, matching
  `compute_score`, and leaves it to the caller to check for tier-C runs.
- `TheoryContext.build` binds that bucket-rate function for normal live pricing.
- `tools/slices.py` `evaluate` removes rows touched by tier C, but aggregate and
  complement input still admits replay rows with missing or NULL tiers. Slice
  qualification separately constructs an A/B run set.

This is an enforcement gap, not a claim that the current live database contains
contaminated scores. No live records were migrated or recomputed during the
compatibility work.

Reproduce with private fixtures covering live, tier A, tier B, tier C, NULL tier,
missing registration, and a position touched by multiple runs. Then centralize
eligibility for decision-facing scores and bucket rates, preserving explicit
diagnostic access to excluded runs. Keep the existing distinctions between
experiment lanes, carried versions, and slice mining/OOS exclusions. A shared
primitive is warranted only where these real consumers use the same rule.

Acceptance: excluded replay evidence cannot change production credibility or
measured bucket probabilities; A/B evidence and valid live observations retain
their current weight; diagnostic reports state excluded counts and reasons.
Document any recomputation needed before touching the user's ledger.
