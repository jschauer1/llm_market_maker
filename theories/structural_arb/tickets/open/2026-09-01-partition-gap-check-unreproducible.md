---
title: The partition-gap standing check does not reproduce and over-triggers ~15x
lane: theory
theory: structural_arb
created: 2026-09-01
created_by: llm-market-identifier-af
author_lane: theory
author_focus: structural_arb
author_context: Found while running the two standing checks NOTES.md leaves open; ran out of session before replacing the definition.
status: open
---
NOTES.md 2026-08-29 correction #2 leaves a STANDING check: recompute 'events priced as a partition' / flagged / gap / gap-intersect-candidates 'before repeating nothing-to-find as settled'. Session 78 recorded 53 / 43 / 10 / 0 on the 2026-08-29 board.

RE-RUN 2026-09-01: the recipe AS WRITTEN ('>=3 legs sharing one deadline, sum in [0.90, 1.05]') does not reproduce those numbers under any price field. It yields 913 partition events on the same 08-29 board with asks, 1,566 with bids, 1,840 with mids, 928 with last. An order of magnitude more than 53. So session 78 used a NARROWER definition than the one it wrote down, and the recorded recipe is not a usable instrument.

The reconstruction is NOT the problem: flag_candidates reproduces exactly (1,449 on 08-29, 1,480 on 09-01) and ME=true reproduces exactly (6,414). The divergence is entirely in the partition definition.

WHY IT MATTERS: on today's board the ask-side check returns gap-intersect-candidates = 2, not 0. Both are false alarms and obviously so - KXLEADERSOUT-27JAN01 is 30 DIFFERENT WORLD LEADERS and KXRAIN-26AUG31 is 22 DIFFERENT CITIES, neither remotely exclusive, and Kalshi flags both False correctly. So the substantive claim survives; what is broken is the check that was supposed to guarantee it, which now cries wolf.

WHAT TO DO: replace the price-sum heuristic with one that means exclusivity rather than correlating with it. The legs of a real partition divide ONE underlying quantity, and scan.underlying_key already computes exactly that grouping - a definition built on it would not have admitted either false positive, since neither event has a shared underlying at all. Do NOT spend time tuning the [0.90, 1.05] band; the band is not the problem, the premise that 'asks sum near 1' implies exclusivity is.

Keep it out of screen() as session 78 deliberately did - it is a research check, not a decision input, and the suite must stay deterministic.
