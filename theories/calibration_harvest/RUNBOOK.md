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

# collect (resumes from the checkpoint; re-running is idempotent)
python -m theories.calibration_harvest.collect run \
    --categories "Climate and Weather" \
    --run-id backtest-2026-08-27-calharvest-weather \
    --checkpoint theories/calibration_harvest/backtests/weather.json

# politics is the big one: ~2,504 series, expect multiple sessions
python -m theories.calibration_harvest.collect run \
    --categories "Politics,Elections" \
    --run-id backtest-2026-08-27-calharvest-politics \
    --checkpoint theories/calibration_harvest/backtests/politics.json
```

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
`testing` at v2; its live rows are observation rows — ruling 13 — recorded
so the cells accrue forward settlements, never recommendations):

```python
from datetime import datetime, timezone
from tools import board as board_tool, db
from tools.theory import TheoryContext
from theories.calibration_harvest import collect
from theories.calibration_harvest.theory import CalibrationHarvestTheory

conn = db.connect()
board = board_tool.get_board(conn)          # never force=True outside go's orient
rates = collect.cell_rates(conn, run_id="backtest-2026-08-27-calharvest-weather")
categories = {s["ticker"]: s["category"]
              for s in collect.target_series({"Climate and Weather"})}
theory = CalibrationHarvestTheory(categories=categories, cell_rates=rates)
ctx = TheoryContext.build(conn, board, datetime.now(timezone.utc),
                          run_id="live-YYYY-MM-DD-calharvest")
run = theory.start(ctx)
run.finish()
```

## Record

Live rows record claimed edge ≤ 0 with the observation rationale — they
are measurements of the board, never bets (ruling 13), and the promotion
key routes them to R6 CONTROL. Never read forward cells through
`opportunities.run_id` — a re-run's rows are invisible to it; read
`opportunity_attempts` (`forward_cells.py` does; the trap bit three times
by 2026-08-30). Defective runs are quarantined by id in
`forward_cells.EXCLUDED_RUNS`, never deleted silently.

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
