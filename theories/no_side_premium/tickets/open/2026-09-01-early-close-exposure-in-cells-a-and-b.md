---
title: The early-close anchor check reached insider_judgment but never reached cell A or cell B
lane: theory
theory: no_side_premium
created: 2026-09-01
created_by: fleet-w3-g1
author_lane: study
author_focus: 2026-09-01-early-close-exposure-in-the-bettable-slice
author_context: Found while measuring the same bug's effect on insider_judgment's bettable slice; scoped out of that study deliberately rather than done badly.
status: open
---
WHAT IS OPEN. studies/2026-08-29-early-close-exposure-existing-backtests flagged this theory explicitly: 'no_side_premium deserves a specific look for that reason: its cell B (non-mention YES favorites 0.80-0.90, claimed -3.89 net) is drawn from exactly this population.' It then reasoned -- not measured -- that cell B is conservative because an inflating bias makes a claimed loss larger, and that cell A comes from the unexposed mention population. Its own words: 'Both look safe, but that is a reasoned expectation, not a measurement.' That thread is still exactly where it was left.

WHY IT IS WORTH DOING NOW, AND WHY THE ANSWER IS NOT OBVIOUS. studies/2026-09-01-early-close-exposure-in-the-bettable-slice ran the equivalent measurement on insider_judgment and confirmed the bias direction on BOTH sides of the book, which is the part that matters here: exposure moves NO-side measured edge DOWN (-4.51 out of sample, -9.22 in sample) and YES-side measured edge UP (+4.98 out of sample, +24.90 in sample). Note the asymmetry -- the YES-side effect measured several times larger than the NO-side one.

Cell B is a YES-side claim. So it sits on the side where the anchor bias measured LARGEST, and it points the same way as the claim: the bias inflates YES-favorite win rates, which makes a YES favorite look like a BETTER bet, which makes cell B's claimed -3.89 loss look SMALLER than it is. The 2026-08-29 reasoning that cell B is conservative therefore holds directionally -- but the magnitude nobody has is how much of cell B's number is anchor artifact, and the insider_judgment measurement says the YES-side distortion can run to tens of points in-sample.

That matters right now because cell-b-yes-avoid has drifted -8.00 (n 64) -> -0.98 (n 109) -> +0.46 (n 150) and there is already an open ticket asking whether the pre-registered avoid claim is falsified by crossing zero upward. If part of the cell's measured level is an anchor artifact, that ticket is reading a contaminated number. The two questions should be answered together.

WHAT TO DO, AND MOST OF IT IS ALREADY BUILT.
  1. Reuse studies/2026-09-01-early-close-exposure-in-the-bettable-slice/measure.py. Its classify() is a drop-in: published custom_strike.Date first, then deadline_drift's parse_deadline over title/rules_primary/subtitle, EXPOSED at >3 days early. Point it at this theory's settled rows instead of insider_judgment's.
  2. Fetch the raw payloads with that study's collect.py, changing only the run_id list. It is resumable, writes one JSON object per line and flushes per ticker, and records a 404 as a 'gone' line rather than retrying.
  3. Split cell A and cell B rows into EXPOSED / CLEAN and report event-clustered edge per arm, with a power floor written down BEFORE the split -- the parent study's floor of 10 event clusters per arm is the precedent, and it fired there, so expect it to fire here too on a 170-row theory.
  4. Report the YES-side arms with particular care given the measured asymmetry above.

DO THIS SOON, AND THIS IS THE REAL URGENCY. Kalshi ages settled markets out of its public API ~60 days after close. The parent study measured 9.7% of its 1,564-ticker population ALREADY UNREACHABLE on 2026-09-01, against 2.9% unreachable in an overlapping window measured three days earlier on 2026-08-29. The classification needs close_time and rules text from the API, so every day of delay permanently converts rows from classifiable to UNKNOWN. Capture first (step 2), classify later -- capture is the perishable half.

MIND THE OVERLAP. Cell A is drawn from the mention population, which the 2026-08-29 study measured as NOT exposed (3 of 68 sampled carried by-deadline phrasing, none early). So cell A may legitimately come back with an empty exposed arm; that is a result, not a failure, and it should be reported as 'not exposed' rather than 'not measured'.
