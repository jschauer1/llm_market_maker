# News Drift runbook

## Stages

Mechanical ND-1 screen, followed by mechanical pricing from an approved,
scoped training artifact. No model judgment or research stage. Read the
complete runbook and the current theory claim before running.

## Run

Reuse the shared board; do not force a floor capture. Collect completed
daily candles in batches using the owner live collector. It rechecks quotes
only for surviving signals. Missing history is missing coverage, never a
zero-signal claim. Run:

```bash
python -m theories.news_drift.run
```

This invokes the registered procedure with retained history and fresh market
quotes through `start()` and `finish()`, recording at the actual quote time.
It emits a compact summary and saves the collector's timestamps/funnel.
To recover a just-collected batch, use `--collection <JSON path>` within
30 minutes of its quote capture. Older inputs need fresh collection.
`python -m theories.news_drift.live --collect` collects without recording.
A floor executes this procedure; new research belongs in a theory ticket.

## Record

All supported and rejected signals go through `finish()`. Without validated
calibration, the procedure records zero-edge prior observations and recommends
no bet. Never copy an `exp/` diagnostic artifact into the live calibration
file to make the screen produce positive edges. A valid backtest can authorize
probabilities, but only for its demonstrated population.

## Sub-theories

Run `python -m tools.cli slices list --theory news_drift`. Evaluate
`weekly-charts` against the parent output using its registered series predicate;
its six exact series are in the chart campaign protocol. Also evaluate every
subsequently registered subset. Report each by name indented below News Drift
with its own evidence/skip reason. A subset cannot lend its probability to
rows outside its predicate.

## Report

Show category coverage, missing/failed history, signal and candidate counts,
current quote time, signal time, daily-to-current quote difference, and
calibration status. List proposed Kalshi tickers only with a supported
probability, net edge, ranked edge, and current execution checks. Price
history does not establish fillable size. With no supported bets, explain
whether there were no signals, insufficient coverage, or no usable calibration.

## Skip

Missing history, gaps, stale candles, invalid quotes, insufficient activity,
wide spread or low OI skip the affected market, with the reason counted.
No calibration skips recommendation, not observation recording. Historical
entries at/after trading close are invalid. Never infer a future deadline
from an observed historical close.
