# Calibration Harvest — runbook

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

The theory is `proposed` and records nothing until a population is complete.
Once it is, build it with the measured rates and the session board:

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
