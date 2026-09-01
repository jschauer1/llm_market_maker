---
title: Recover the 6,860 quarantined pre-v3 `other|*` rows into their true domains
lane: theory
theory: calibration_harvest
created: 2026-09-01
created_by: llm-market-identifier-df
author_lane: maintenance
author_context: Fixing the v3 double-run/domain-collapse defect; found the quarantined rows are recoverable but decided the migration is a theory-lane judgment call.
status: open
---
The v3 fix (2026-09-01, see NOTES.md and THEORY.md Version) quarantines every `other|*` cell below v3, because `other` used to mean both 'a category the grid does not bin' and 'a series this run's map never covered'. That took the forward corpus from 6,960 rows to 100, and 21 cells to 6.

THE ROWS ARE NOT LOST, AND THIS IS THE POINT OF THE TICKET. Every attempt carries `series_ticker` in `extra_json` -- verified 9,269 of 9,269 on `live-2026-08-31-calharvest` -- and `collect.all_series_categories()` re-derives the true Kalshi category, and so the true domain, for each one. The entry price and the outcome, which are what a cell measurement actually needs, were never touched by the mislabelling.

WHY MAINTENANCE DID NOT JUST DO IT. Two reasons, both judgment calls about what this theory's evidence IS rather than about tooling:

 1. Re-labelling a recorded row rewrites what was recorded. The row was DECIDED under the wrong label (priced at 0.0 against a cell with no rates). For a cell MEASUREMENT corpus the decision does not matter -- the observation does -- but that is an argument someone should make explicitly for this theory, not a maintenance session's call. CLAUDE.md's rule is that a meaning change is migrated explicitly and separately, and says so in RESEARCH_LOG.md.
 2. The double-count has to be resolved at the same time, and how is not obvious. On 2026-08-31 and 2026-09-01 a politics market appears in BOTH runs -- `other|*` in the weather run and `politics|*` in the politics run. Recovering the `other` copy re-creates the duplicate the quarantine removed. Someone has to decide the dedup key: (ticker, settlement day)? (ticker, run)? Note the six surviving cross-day pairs are legitimate and must NOT be deduped away -- see NOTES.md.

WHAT IT IS WORTH. ~6,860 settled observations, roughly 69x the current corpus. Against a bar of n>=30 AND n_days>=8 per cell, the present corpus has 0 of 6 cells measurable and the best cell sits at 4 settlement days. This is plausibly the difference between this theory having a readable grid within weeks and within months. It is also the only source of forward rows for the nine domains the partial maps never labelled at all (sports=3103, entertainment=1358, economics=681, financials=681, ... on the 2026-09-01 board).

SUGGESTED SHAPE. A migration script, not a change to `forward_cells.load`: read the quarantined attempts, re-derive `domain` from `extra_json.series_ticker` + the category map, write the corrected cell into a NEW column or a new table rather than overwriting `rationale`/`extra_json` -- the old value is the audit trail for why the quarantine existed. Then `load` can prefer the corrected label where it exists. Pin it with a test, and record the dedup rule you chose and why.

DO NOT drop `OTHER_QUARANTINED_BELOW_VERSION` when this lands. It is what protects the corpus if a partial map is ever driven again; the recovery should make the quarantine unnecessary for these specific rows, not remove the guard.
