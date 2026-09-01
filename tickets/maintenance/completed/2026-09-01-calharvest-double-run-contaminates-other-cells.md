---
title: calibration_harvest's two floor runs double-count and collapse the 'other' domain axis
lane: maintenance
created: 2026-09-01
created_by: llm-market-identifier-cc
status: done
closed: 2026-09-01
resolution: Fixed at calibration_harvest v3 (continues). Root cause was wider than the ticket: domain_for() returned 'other' both for a category the grid does not bin and for a series the run's map never covered, so a partial map was indistinguishable from a legitimate residual -- which is how three separate runs collapsed the axis unnoticed.

CODE: cells.domain_for splits 'unmapped' from 'other' (new constant cells.UNMAPPED); collect.all_series_categories() returns the complete ticker->category map from the single /series fetch that returns all 13,687 series with no cursor, so the complete map costs exactly what the partial one cost; screen() reports 'uncategorized' in its funnel.

RUNBOOK: one run per floor against the complete map, rates merged from both collection runs (keys disjoint: weather 12 cells, politics 16, overlap none). The two-run instruction that was never implemented is gone, and the file now says what the code does.

Took option (b) as the ticket recommended, extended to ALL categories rather than just the two measured ones -- with only the measured categories mapped, the other nine domains stay collapsed into 'other', which is the same defect. Measured on the 2026-09-01 board: 9,220 survivors across 11 real domains, 'other' down from 9,123 (99.4%) to 102 (1.1%).

QUARANTINE: per CELL, not per run. 'other|*' below v3 via forward_cells.OTHER_QUARANTINED_BELOW_VERSION (the value changed meaning, so every row written under the old one is unreadable), plus live-2026-08-29-calharvest-v2 by id (exact duplicate: same board, same map, 100% identical cell keys). Per-cell because 'weather|*' on the weather run and 'politics|*' on the politics run were always correct -- a run-level exclusion would have discarded 2,704 clean politics rows to punish the 'other' rows beside them. Corpus 6,960 rows -> 100; 21 cells -> 6; costs no conclusion (0 of 21 were measurable before, 0 of 6 now). No same-day duplicates remain; the six surviving (ticker, day) pairs are cross-day observations, which is the design.

The 2026-08-29 '-v2' pair the ticket asked about is handled. Also checked v3 does not turn an observation theory into a bet-producer: 2,754 rows now price against a measured cell, 0 with edge_net > 0 (max -0.95).

NOT DONE, ticketed to the theory lane as calharvest-recover-quarantined-other-rows: the 6,860 quarantined rows are recoverable (every attempt carries series_ticker in extra_json; the category map re-derives the true domain), but that is a corpus migration plus a dedup-rule decision, which is a judgment call about the theory's evidence rather than tooling.

Tests: 11 new/changed across tests/theories/test_calibration_harvest_{forward_cells,cells,screen,collect}.py, written first and watched fail. Full suite 1281 passed, 0 failed.
---
Found by the 2026-09-01 floor. The RUNBOOK (Collect section, added 2026-08-31) says stage 3 runs twice per floor, 'once per complete population, with distinct run ids so same-day attempts never double-count a market'. The code does not do that: theories/calibration_harvest/screen.py::screen() takes `categories` only as a series-ticker -> category LABEL map for cells.cell_key(); it has NO population filter. Both runs therefore screen the entire board.

Measured on 2026-09-01 (identical pattern on 2026-08-31, the first day the two-run procedure was used):
  - live-2026-09-01-calharvest         : 9,247 attempts
  - live-2026-09-01-calharvest-politics: 9,247 attempts
  - overlap: 9,247 of 9,247 opportunity rows (100%)
  - of those, 6,944 carry an IDENTICAL cell key in both runs and 2,303 differ.

Consequence, by cell family:
  - politics|* and weather|* cells are fine -- each is only ever populated by the run holding that category map.
  - other|* cells are contaminated two ways: (1) the 6,944 same-key markets are counted TWICE into the same other|* cell from one board, and (2) each run labels the OTHER run's category population as 'other' (e.g. ECMOV-28NOV07-DEM1T10 is 'other|1mo+|0.92-0.97' in the weather run and 'politics|1mo+|0.92-0.97' in the politics run).

This is the same failure mode forward_cells.EXCLUDED_RUNS already quarantines the 2026-08-30 'live' run for ('domain axis silently collapsed to other'), just partial instead of total. forward_cells.load() reads every attempt with no per-ticker dedup, so both effects land in the cell measurement.

Not fixed by this floor: the floor ran the theory as its runbook specifies, and the defect is in the runbook/screen pair, not in the run. Deciding between the two available fixes is a maintenance call:
  (a) give screen() a real population filter so each run sees only its own categories (matches the runbook's stated intent), or
  (b) keep one run per floor with a merged categories map covering every measured population (one board, one pass, no duplicate attempts) -- this looks strictly simpler and removes the double-count by construction.

Either way, decide what to do with the already-recorded 2026-08-31 and 2026-09-01 politics runs -- quarantine via EXCLUDED_RUNS is the established precedent, and the rows are real sightings so they should be quarantined rather than deleted. Also check the 2026-08-29 'live-2026-08-29-calharvest' / '-v2' pair, which is the same shape (10,269 attempts each, same day).
