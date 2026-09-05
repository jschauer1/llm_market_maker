# Keep each estimate on one recorded attempt

**Summary:** A price, edge and judgment must describe the same decision; a position rollup can mix dates.
**Applies to:** Reobserved single-contract positions used for live promotion, bucket calibration or slice scoring.
**Finding:** Observed September 5, 2026: a latest 81-cent decision paired with the original 86-cent entry inflated a fresh quote's claimed edge by about five points. Pooled scoring could similarly combine early prices with later labels.
**Do next time:** For live promotion, read one latest attempt. For pooled judgment evidence, use the earliest confidence-bearing attempt; for mechanical evidence, use the earliest attempt. Select named dispositions within the requested run. Preserve explicit revisions on their own attempt and keep first-position accounting intact.
**Evidence:** [Regression tests](../../tests/test_promotion.py); [scoring tests](../../tests/test_attempt_scoring.py); [promotion contract](../../docs/promotion-key.md#preconditions-shared-by-r1-and-r3).
**Revisit when:** A new scoring question deliberately evaluates later decisions, with its own declared sample unit.
**Updated:** 2026-09-05
