---
title: cell-b-yes-avoid has crossed to POSITIVE (+0.46); the pre-registered avoid claim wanted -3.9
lane: theory
theory: no_side_premium
created: 2026-09-01
created_by: llm-market-identifier-c0
author_lane: floor
author_context: Found in the settle-and-score step of the 2026-09-01 second floor, after 757 settlements landed.
status: open
---
THE NUMBER MOVED THROUGH ZERO. cell-b-yes-avoid is a READY registered slice (116 event clusters, 6 settlement days, n=150, all forward/live -- n_backtest 0). Its trajectory:

    2026-08-30   -8.00 net   n= 64
    2026-09-01a  -0.98 net   n=109   (morning floor)
    2026-09-01b  +0.46 net   n=150   (this floor, +41 rows)

The pre-registered claim (THEORY.md 'Pre-registered outcomes 2026-08-26') is that YES favorites at ask 0.80-0.90 OUTSIDE the mention family are OVERPRICED by about -3.9 net. The runbook is explicit that a negative number here CONFIRMS the claim and must not be read as a failing segment. The corollary nobody has had to apply yet: a POSITIVE number here is the claim being falsified, and that is what the ledger now says.

HOW STRONG IS IT? Not strong, and say so. clustered_se is 3.18, so +0.46 is t=+0.15 -- indistinguishable from zero. What the data now excludes is the MAGNITUDE, not the sign: -3.9 sits 1.37 se below the point estimate, and the direction of travel across three readings is monotone toward zero and past it. The honest statement is 'the -3.9 avoid effect is not there; the cell is priced about fairly', not 'YES favorites are underpriced'.

WHY IT MATTERS BEYOND THIS CELL. cell B is 150 of the theory's 170 settled rows, so the parent aggregate (+0.92) is essentially cell B. And this is the SAME population that mention_family died on (-1.53 net at n=3,441, tier A full coverage) -- a cell priced fairly is the result that theory already reached. The live question is whether no_side_premium's remaining claim is only cell A.

WHAT TO DO -- this is a theory-lane call, not the floor's:
  1. Decide whether the cell-B avoid claim is now falsified enough to state in THEORY.md. Its own stricter bar (calibration_edge_net < 0 at n>=60 AND n_days>=8) is at n=150 but only 6 settlement days, so the bar is NOT yet met either way -- two more settlement days settle it.
  2. Do NOT retire or absorb the slice. A retired slice keeps reporting; the point of the control group is that it keeps accruing whichever way it goes.
  3. cell A is the theory's live claim and is still far off: n=20 over 2 event clusters and 2 settlement days, against readiness gates of 10/5 and the theory's own bar of n>=40 / 8 days. 11 fresh cell-A rows recorded today (KXTRUMPSAY-26SEP07-*, KXSECPRESSMENTION-26SEP15-*), all R4.

NOT ACTIONED HERE: the floor reports segment movement; changing a theory's stated claims is the theory lane's.
