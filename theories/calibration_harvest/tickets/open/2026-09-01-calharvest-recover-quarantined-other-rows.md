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

---

## MEASURED 2026-09-01 (session llm-market-identifier-d8, theory lane): the headline "69x the corpus" is true and does not mean what it says

Do this if you want it, but not for the reason written above. **The
6,856 quarantined `other|*` rows span exactly FOUR settlement days** --
2026-08-29, 08-30, 08-31, 09-01. They are four floors' worth of the same
board, relabelled.

The gate is `n >= 30` **AND** `n_days >= 8`. Recovery moves `n` and
**cannot move `n_days` at all**: it relabels rows that already exist, on
days that already exist. Not one cell crosses the day floor as a result.

Per cell, if every quarantined row were recovered and correctly
relabelled (v4 `effective_n` in the last column):

    cell                          n   days   mbar   n_eff(v4)
    other|2d-1w|0.92-0.97      1504      4  376.0          17
    other|2d-1w|0.65-0.75      1130      4  282.5          17
    other|2d-1w|0.85-0.92      1118      4  279.5          17
    other|2d-1w|0.75-0.85      1102      4  275.5          17
    other|1w-1mo|0.65-0.75      316      4   79.0          17
    other|<=2d|0.92-0.97        313      3  104.3          13
    ...

1,504 rows on 4 days is worth **17** effective observations, because
they are ~376 markets from one board settling together. That is the
v4 design-effect treatment (NOTES.md 2026-09-01 later), and it is
already the *generous* reading -- v3 valued the same rows at 4.

**So this is not "the difference between a readable grid within weeks
and within months."** Nothing here is close to readable, and no
relabelling makes it so. What buys a readable grid is settlement DAYS,
and there are exactly two sources of those: calendar time going
forward (~1 day per day), and a tier-A walk of settled history (up to
58 days in one afternoon, `collect run`). The walk dominates this
ticket on the only axis that binds.

**What the recovery is still genuinely worth**, stated honestly so the
next session can price it:

  - The nine never-labelled domains (sports, entertainment, economics,
    financials, ...) get four days of forward rows they otherwise do not
    have. That is a real head start, just a four-day one.
  - It removes a standing 6,856-row hole in the audit trail.
  - It is cheap, and the dedup question it raises is worth settling once
    rather than re-encountering.

It is a good tidy-up. It is not an unlock, and a session should not pick
it over a domain walk expecting to get a measurable cell out of it.

The two open questions this ticket raises are both still open and still
correct to raise: whether relabelling a recorded row is legitimate for a
measurement corpus, and what the dedup key should be. Neither is
affected by the above.
