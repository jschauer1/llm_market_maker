---
title: Re-run the platform sweep and read DD-3 ONCE, at the first sweep where the unseen arm holds >= 80 event clusters
lane: theory
theory: deadline_drift
created: 2026-09-03
created_by: fleet-w1-g4
author_lane: theory
author_focus: deadline_drift
author_context: Filed at the end of the 2026-09-03 session that completed the sweep and found DD-3 seven clusters short of its own floor.
status: open
---
WHERE THIS GOT TO. The 13,772-series platform-wide sweep is complete (3,392 markets). DD-3 read -6.64 net over 73 event clusters against a pre-registered floor of 80, so by its own bar it SETTLES NOTHING. DD-4 (-9.2, 37 clusters) and DD-5 (recurring arm holds 2 clusters) are likewise underpowered. Full numbers in NOTES.md 2026-09-03, summarised in THEORY.md Status.

WHAT TO DO. Seven more event clusters are needed. The store only grows -- markets already captured never leave our disk even as Kalshi ages them out upstream -- so re-running `python -m theories.deadline_drift.collect_settled --platform` will add clusters from new settlements. Budget ~32 minutes for a full sweep; a resume over already-walked series costs seconds.

THE STOPPING RULE IS BINDING AND IS THE POINT OF THIS TICKET. DD-3 is read EXACTLY ONCE MORE, at the first sweep where the unseen arm holds >= 80 event clusters, and that reading is the verdict whatever it says. Do NOT read it at 74, 76 or 79 and then check again next week -- re-checking until a number crosses in a pleasing direction is optional stopping, and this theory has already spent one look on a declared 45% peek.

Practical shape that keeps you honest: `python -m theories.deadline_drift.backtest` prints the cluster count on the line "N event clusters", above the verdict. Run the sweep, run backtest, read ONLY the cluster count. If it is under 80, stop there and do not scroll. If it is 80 or more, that output is the answer and it goes into THEORY.md and NOTES.md.

THE BAR IS UNCHANGED, from THEORY.md: net >= +2 with a 95% event-clustered CI excluding zero. Failure is a CI covering zero at >= 80 clusters, or a point estimate below +2.

WHAT ELSE IS WORTH KNOWING BEFORE YOU START.

1. Every out-of-sample estimate so far is negative, and a 14-cut mining pass (`python -m theories.deadline_drift.mine_arms`) never changes the sign: unseen negative in 14 of 14 cuts, seen positive in 14 of 14. Expect a negative answer, and do not let that expectation change how you read it.

2. The tight-spread unseen cells sit at -0.3 and -1.2, i.e. indistinguishable from ZERO on markets where execution is realistic. The plausible outcomes are "no edge" and "still underpowered", not "an edge in the other direction".

3. DD-1, the forward test on markets settling after 2026-09-01, is untouched by any of this and remains the primary test. It is what would license writing hazard_bins.json -- which lives at the THEORY ROOT, not under data/.

4. DD-5 can never run as written: the unseen arm is one-off by construction, because "unseen" means a series the board-scoped walk never reached and a recurring family always keeps something on the board. Do not spend time on it.

IF DD-3 FAILS AT >= 80 CLUSTERS, that plus a DD-5 that cannot run is what THEORY.md calls the end of the broad thesis, and the right next step is `python -m tools.cli theories propose-retirement` with the diagnosis -- NOT a unilateral retirement, which is a user ruling. Until then the theory keeps running and costs nothing: every row it writes claims pts_net 0.0 with basis prior, so it cannot produce a recommendation.
