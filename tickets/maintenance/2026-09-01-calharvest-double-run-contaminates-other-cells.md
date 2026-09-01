---
title: calibration_harvest's two floor runs double-count and collapse the 'other' domain axis
lane: maintenance
created: 2026-09-01
created_by: llm-market-identifier-cc
status: open
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
