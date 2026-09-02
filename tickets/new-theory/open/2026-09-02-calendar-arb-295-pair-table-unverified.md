---
title: The 295 near-dated pair table that closes calendar-arb was measured on a board ~90k markets short
lane: new-theory
created: 2026-09-02
created_by: fleet-w3-g2
author_lane: maintenance
author_context: Found while fixing the exact-stamp board readers (ticket calendar-arb-probe-exact-stamp-board); re-ran the firing-rate probe correctly but its main() does not compute Result 2's table, so that half is still unverified.
status: open
---
READ THIS BEFORE USING THE 295-PAIR DATASET. The open ticket 2026-09-01-calendar-arb-soft-relative-value points a future session at 'the 295 near-dated same-event pairs already sitting at cost 1.000 as a ready-made dataset'. That figure comes from tickets/study/answer/2026-08-27-calendar-arb-firing-rate/ Result 2, and it was measured with a board reconstruction that is now known to be wrong.

WHAT IS ESTABLISHED. probe.py rebuilt boards with WHERE captured_at = ?. Dedup-on-write (2026-08-30) made that return only the markets that MOVED at a pull. The probe ran 2026-08-27, before dedup, so its numbers were right when made -- but the captures it walked now re-read as little as 3,254 markets against a real board of 107,656. probe_as_of.py (added 2026-09-01) supersedes it and uses snapshot.board_as_of.

WHAT THE RE-RUN SETTLED. Result 1 moved: over 20 captures on correct boards there are 25 violations / 38,124 pairs (was 'zero'), but 19 are one recurring 2028-horizon cross-event pair worth 0.4-2.3 pts against two years of carry, and 3 have a 0.01 NO ask (the placeholder-quote trap). The study's VERDICT is unchanged and this ticket does not reopen it. Full detail in that study's 'Addendum 2026-09-01'.

WHAT IS NOT SETTLED, AND IS THE WORK HERE. Result 2's horizon-by-scope table -- 295 near-dated same-event pairs, min cost 1.000, and critically ZERO cross-event pairs inside 90 days -- is the finding that actually closes calendar-arb and the one the soft-relative-value ticket wants to reuse. probe.py's main() does not compute it, so probe_as_of.py does not reproduce it either. It has never been re-derived on a correct board.

WHY IT MATTERS IN BOTH DIRECTIONS. If the table holds, the soft-relative-value idea has its dataset and can proceed. If 'zero cross-event pairs inside 90 days' was an artifact of a board missing 90k markets -- and the missing markets are the liquid ones, which is the wrong direction for this claim -- then the structural argument that closed calendar-arb is weaker than recorded, and the 295 count is wrong too.

WHAT TO DO. Extend probe_as_of.py with the horizon/scope tabulation (later-leg horizon buckets 90d / 90d-1y / 1y-3y / >3y crossed with same-event vs cross-event, min cost per cell), run it on the newest capture via snapshot.board_as_of, and state whether 295 and the zero-cross-event-inside-90d both hold. Cheap: the grouping code already exists in probe.py's subject_key and the board reconstruction is one call.

FILED FROM MAINTENANCE, NOT DECIDED THERE. Re-deriving the table is a measurement that feeds a build/do-not-build call, so it belongs to whoever takes the soft-relative-value ticket -- or to the study lane if it is run on its own.
