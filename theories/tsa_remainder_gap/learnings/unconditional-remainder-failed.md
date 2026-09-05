# The fixed remainder model failed its archive diagnostic

**Summary:** Do not rerun or tune TRG-1's exposed holdout as new evidence.

**Applies to:** The 52-week unconditional TSA remainder model, Friday 15:00 UTC,
current-archive reconstruction, holdout 2025-08-31–2026-08-30.

**Finding:** Measured on 2026-09-05: 44 positions across 43 settlement days
averaged -8.07 net points; weekly 95% interval [-15.29, -0.85]. Model probability
averaged 52.1%, but only 4/44 positions won. Both sides were negative. Historical
source revisions prevent treating this as source-valid production evidence.

**Do next time:** Preserve the failed baseline and calendar denominator. Public
partial counts alone did not justify these price gaps. A successor needs a
specific forecasting improvement and independent evaluation, not a threshold
search over this holdout.

**Evidence:** [TRG-1 results](../backtests/trg1-20260905/RESULTS.md), run
`exp/trg1-20260905/holdout`; decisions and source hashes are in that campaign.

**Revisit when:** A distinct conditional mechanism and valid confirmation data exist.

**Updated:** 2026-09-05.
