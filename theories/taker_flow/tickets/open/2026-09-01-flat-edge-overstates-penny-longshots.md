---
title: The pooled +4.29 is applied at 1-cent asks where the same replay measured +1.06
lane: theory
theory: taker_flow
created: 2026-09-01
created_by: llm-market-identifier-70
author_lane: new-theory
author_focus: taker_flow
author_context: Seen in the v2 live run: every top-ranked row is a penny longshot. Not fixed deliberately -- the fix needs numbers that would be mined from the same run.
status: open
---
price() applies one measured gross edge per flow bucket (+4.29 for 'extreme') at every entry price. The v2 live run's ten highest-edge rows are all asks of 0.00-0.01, because a flat points-edge is largest in relative terms exactly where the price is smallest.

THE SAME REPLAY DISAGREES WITH ITSELF THERE. backtest-2026-09-01-takerflow's extreme cell by price band:
    [0.00,0.15)  n=106  +1.06   (t=+0.36)
    [0.15,0.35)  n= 84  +6.43
    [0.35,0.65)  n= 28  +11.79
    [0.65,0.85)  n= 39  +6.67
    [0.85,1.01)  n= 66  +2.17
The pooled +4.29 is dominated by the middle. At a 1-cent ask the honest measured number is +1.06 with a t-statistic of 0.36 -- i.e. nothing -- and that band is also where the 0.980-0.995-style placeholder-ask trap lives in mirror image.

NO LIVE CONSEQUENCE TODAY, which is why this is a ticket and not a hotfix. Every row is R5 MEASURED-AGAINST and quoted:false, because the extreme-imbalance slice is below its gates and the parent aggregate is -0.17. The defect only decides which SUPPRESSED rows sort highest. It becomes real the moment the slice clears its gates -- fix it before then.

WHY I DID NOT JUST FIX IT. The obvious fix is per-band constants, and those bands come from the same run that produced the pooled number, so adopting them is another post-hoc parameter choice on the data that suggested it -- the exact thing the pre-registration discipline in NOTES.md exists to prevent. Three legitimate routes instead:
  1. WAIT. Let extreme-imbalance accrue out-of-sample rows and read the price-band structure from evidence the constants were not fitted on. Slowest, cleanest.
  2. PRE-REGISTER a band split now, as a second slice (e.g. extreme-midprice, extra.price_band), so its credibility counts only what settles after registration. This is the cheap correct move and mirrors what was already done for the tail itself.
  3. RESTRICT the screen's price range on a stated structural argument rather than a fitted one -- e.g. a longshot at 1 cent cannot clear fees plus a half-spread even if the edge is real, which is an arithmetic claim and not a mined one. Bumps the version.

Route 2 or 3. Do not simply hard-code the five band numbers.
