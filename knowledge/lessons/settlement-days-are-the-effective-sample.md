# Settlement days, not rows, bound evidence from clustered resolutions

**Summary:** Report settlement-day counts and clustered uncertainty whenever many markets resolve from the same daily event slate.
**Applies to:** Kalshi favorites and theory replays observed in the 2026-08-25 through 2026-08-27 audit, plus historical runs spanning 30-67 settlement days.
**Finding:** Measured — 215 pooled rows showed +3.71 net, but their three daily estimates were +4.26, -7.29, and +5.40, with YES/NO signs reversing by day. Historical clustering widened standard errors 1.15x-2.37x; this study does not estimate a universal day effect.
**Do next time:** Cluster by resolution date, show `n_days` and the daily breakdown beside row totals, and treat thin-day results according to the current evidence gates.
**Evidence:** [Settlement-day study](../../tickets/study/answer/2026-08-27-settlement-day-clustering/STUDY.md), headings “Result” and “Addendum, same day — applying the lens to the repo's historical evidence”
**Revisit when:** A dependence model validated against shared events or legs supports a different effective sample unit.
**Updated:** 2026-09-04
