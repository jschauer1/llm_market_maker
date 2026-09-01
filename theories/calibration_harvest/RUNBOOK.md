# Calibration Harvest — runbook

## Stages

| # | stage | who decides | artifact |
|---|---|---|---|
| 1 | settled-history collection | code | `collect run` — checkpointed, resumable, tier A |
| 2 | cell rates | code | `read_cells` / `collect rates` |
| 3 | live screen + record | code | `theory.start(ctx).finish()` — observation rows so cells accrue forward settlements |

No judgment stage. "Run the theory" in a session's floor means stage 3;
stages 1–2 are the measurement campaign behind it.

## Collect (the tier-A measurement)

Checkpointed and resumable. Safe to interrupt at any point: each series is
written to the DB and to the checkpoint before the next one starts.

```bash
# what would be walked
python -m theories.calibration_harvest.collect enumerate \
    --categories "Climate and Weather"

# what it would COST, before committing to it. One list_settled per
# series gives the exact candlestick-fetch count, because `worth_fetching`
# reads the settlement snapshot's final volume and volume only grows.
# ALWAYS run this before a new population: the per-series distribution is
# brutally skewed (five weather series were 40% of that walk; KXBTC15M
# alone is 5,491 fetches / ~20 min of 15-minute BTC markets), so sampling
# a few series and extrapolating is wrong by an order of magnitude.
# Checkpointed and resumable like the walk itself.
python -m theories.calibration_harvest.collect size \
    --categories "Economics,Financials" \
    --checkpoint theories/calibration_harvest/backtests/size.json

# collect (resumes from the checkpoint; re-running is idempotent)
python -m theories.calibration_harvest.collect run \
    --categories "Climate and Weather" \
    --run-id backtest-2026-08-27-calharvest-weather \
    --checkpoint theories/calibration_harvest/backtests/weather.json

# politics: COMPLETE since 2026-08-31 (2,508/2,508 series). The data
# lives under run-id backtest-2026-08-29-calharvest-politics (the
# earlier -08-27- name in this file was never the one used; corrected
# 2026-08-31). Re-running only extends to newly listed series.
python -m theories.calibration_harvest.collect run \
    --categories "Politics,Elections" \
    --run-id backtest-2026-08-29-calharvest-politics \
    --checkpoint theories/calibration_harvest/backtests/politics.json

# third population, STARTED 2026-09-01 by session llm-market-identifier-d8,
# NOT yet complete -- do not read its cells until it is. Five mapped
# domains in one run; cell keys are domain-prefixed so they stay disjoint,
# exactly as Politics+Elections were walked together.
python -m theories.calibration_harvest.collect run \
    --categories "Economics,Financials,Science and Technology,Companies,World" \
    --run-id backtest-2026-09-01-calharvest-econfin \
    --checkpoint theories/calibration_harvest/backtests/econfin.json
```

**Do not walk Commodities, Social, Transportation, Exotics or Education.**
`cells.DOMAINS` does not bin them, so every row lands in `other|*` -- the
exact vocabulary v3 quarantined. Walk a category only if `DOMAINS` maps
it, or add the mapping first, which is a decision-path change and bumps
the version.

**Since v3 (2026-09-01) the live screen runs ONCE per floor.** It did not
always; from 2026-08-29 to 2026-09-01 this file said it ran twice, "once
per complete population, with distinct run ids so same-day attempts never
double-count a market". The code has no population filter — `categories`
is only a label map for `cells.cell_key`, and `screen()` always walked the
whole board — so both runs screened everything and each labelled the
other's population `other`. Measured on the 2026-09-01 board: 9,247
attempts per run, **100% overlap**, 6,944 with an identical cell key.

The fix is the one run, driven by a **complete** map:
`collect.all_series_categories()` returns all 13,687 series in one
`/series` fetch, so every market carries its true domain and the map costs
exactly what the partial one did. Rates merge from both collection runs;
their keys are disjoint by domain prefix.

## Read the cells

```bash
# wins / n / distinct settlement days
python -m theories.calibration_harvest.collect rates \
    --run-id backtest-2026-08-27-calharvest-weather

# ...and the three things a cell cannot honestly be read without: the mean
# ask actually paid (a raw edge against a bin midpoint is an edge against
# nothing), the Wilson-bounded edge price() would claim, and the
# day-clustered SE. Prefer this one.
python -m theories.calibration_harvest.read_cells \
    backtest-2026-08-27-calharvest-weather
```

Never read a cell as measured until its population is **complete** — the
checkpoint's series count equals the enumerate count. A partial walk in API
order is a non-random slice, which is the exact failure that killed
`mention_family`.

## Day clustering (always report this)

```bash
python -c "
from tools import db, score
conn = db.connect()
print(score.settlement_day_clusters(conn, 'calibration_harvest', 1,
      run_mode='backtest', run_id='backtest-2026-08-27-calharvest-weather'))
"
```

A cell is `measured` only at `n >= 30` **and** `n_days >= 8`. Report the
day-clustered SE, never the row-level one.

## Run the live screen

Build the theory with the measured rates and the session board (it is
`testing` at v4; **most** of its live rows are observation rows — ruling 13 — recorded
so the cells accrue forward settlements, never recommendations):

```python
from datetime import datetime, timezone
from tools import board as board_tool, db
from tools.theory import TheoryContext
from theories.calibration_harvest import collect
from theories.calibration_harvest.theory import CalibrationHarvestTheory

conn = db.connect()
board = board_tool.get_board(conn)          # never force=True outside go's orient
# rates from BOTH complete collection runs; keys are disjoint by domain
rates = {**collect.cell_rates(conn,
             run_id="backtest-2026-08-27-calharvest-weather"),
         **collect.cell_rates(conn,
             run_id="backtest-2026-08-29-calharvest-politics")}

# the COMPLETE label map -- never target_series(), which filters to the
# categories being COLLECTED and drops anything stale. That is the right
# answer to a different question, and reusing it here is what collapsed
# the domain axis on every live run before v3.
categories = collect.all_series_categories()

theory = CalibrationHarvestTheory(categories=categories, cell_rates=rates)
ctx = TheoryContext.build(conn, board, datetime.now(timezone.utc),
                          run_id="live-YYYY-MM-DD-calharvest")
run = theory.start(ctx)
run.finish()
```

**Check the funnel before recording anything.** `screen()` reports
`uncategorized` — survivors whose series the map did not cover.

A **handful is normal**: 50 of 9,220 survivors (0.5%) on the 2026-09-01
board, all series listed after the board pull that `/series` had not seen
yet. **Hundreds or thousands means the map is partial** and the run is
reproducing the pre-v3 defect — stop and fix the map rather than
recording. Either way those markets land in a conspicuous `unmapped|*`
cell instead of silently in `other|*`, so it shows in the grid as well as
the funnel.

## Record

Live rows in an **unmeasured** cell record claimed edge 0.0 with the
observation rationale — measurements of the board, never bets (ruling
13) — and the promotion key routes them to R6 CONTROL.

**Since v4 that is no longer every row, and a floor session must not be
surprised by it.** A cell past both floors prices a real Wilson-bounded
edge, and on the 2026-09-01 board **303 rows came out positive with
`edge_basis='measured'` where v3 emitted zero** — all in
`politics|1mo+|0.75-0.85`. Under v3 no cell could clear the bound at all
(arithmetically infeasible above ask 0.65 at the 8-day floor; THEORY.md
Version 4), so "every live row is an observation row" was true by
accident of a broken estimator, not by design.

**Report them at their rung, which is R5.** Checked 2026-09-01 with `cli
promote` and `slices.ranking_segment`: the aggregate segment is past both
gates (n_clusters 2,822, n_days 63) with `calibration_edge_net` −2.45, so
R5 MEASURED-AGAINST fires and they are suppressed from the bets table —
the measured record outranks the claim. They still settle, which is the
out-of-sample test v4 was pre-registered against.

- **Positive `measured` rows are not the theory coming good.** That cell
  is in-sample (one of the two populations the grid was drawn on), n=50,
  and part of a claim retracted 2026-08-29. If a floor ever sees them at
  **R1** instead of R5, the aggregate has turned positive — a real event
  worth stopping for, not a rendering change.
- **They are one cell on one board and settle together.** Read the
  forward record with `forward_cells.py`, never by row count: 303 rows
  landing on one day is not 303 draws, and `cells.effective_n` is now
  what says so.

Never read forward cells through
`opportunities.run_id` — a re-run's rows are invisible to it; read
`opportunity_attempts` (`forward_cells.py` does; the trap bit three times
by 2026-08-30). Defective runs are quarantined by id in
`forward_cells.EXCLUDED_RUNS`, never deleted silently.

**Two quarantines are in force**, both in `forward_cells.py`:

| what | why |
|---|---|
| run `live` (2026-08-30) | no map and no rates passed; total domain collapse |
| run `live-2026-08-29-calharvest-v2` | exact duplicate of that day's first run — same board, same map, 100% identical cell keys |
| every `other\|*` cell below v3 | `other` meant "this run's map missed it" as well as "the grid does not bin it"; the cells pool every domain the theory exists to separate |

The third is per **cell**, not per run, on purpose: `weather|*` on the
weather run and `politics|*` on the politics run were always correct, and
dropping the runs wholesale would discard 2,704 clean politics rows to
punish the `other` rows beside them. What survives is exactly one
correctly labelled row per market per day.

## Sub-theories

A **sub-theory** is a theory run over a *subset* of this theory's data --
a registered slice with its own evidence, its own gates, and its own
record, which may be strong while the parent is flat.

**None registered.** This theory's cells are not slices: they are the
population it observes, recorded with claimed edge 0.0 as observation
rows (ruling 13), so there is no subset making a bet claim to score
separately. Its per-cell measurement lives in `forward_cells.py` and is
reported from there.

Check anyway when running -- a slice registered later must not go
unreported because this section said none existed:

```bash
python -m tools.cli slices report calibration_harvest
```

## Report

The floor line carries markets screened, rows recorded, and the cell
status against the pre-registered bars (`n >= 30` and `n_days >= 8` per
cell) with day-clustered SEs — and under 3 settlement days the honest
words are "not yet measurable" (ruling 14), whatever the t-statistic
reads.

## Skip

Skip stage 3 only when the ledger shows a live run today at the current
version (the go freshness check). Stages 1–2 re-run only when extending
a population — a partial walk in API order is a non-random slice, so
never read a cell mid-collection.
