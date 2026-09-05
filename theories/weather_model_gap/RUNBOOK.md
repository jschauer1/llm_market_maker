# Weather Model Gap runbook

## Stages

Read this procedure and the current theory claim. This is mechanical; the
floor performs no research and spawns no judgment agents.

## Run

```bash
python -m theories.weather_model_gap.run
```

The entry window is 00:00–01:00 UTC on the target date. Outside it, report
`outside_entry_window` for the theory and every city. Do not run a fresh
historical collection merely because a floor occurs at another hour.

Within the window, refresh payout labels missing from the retained 90-day
history and fetch the exact preceding 12Z `ecmwf_ifs` run for today's station
day. Reuse immutable forecasts. Entry activity comes from the candle ending
exactly at 00 UTC, with fresh executable quotes checked at the actual decision
time. Require current depth for a recommendation. Missing sources or invalid
rules skip the affected event with a counted reason.

## Record

Run the ordinary `start()` / `finish()` contract. At most one recorded event
per station/date, including repeated sessions. Each city's frozen holdout
qualification is recomputed from verified ledger evidence; an unsupported city
records zero-edge prior observations rather than actionable probabilities.
Never enable a city by editing a report's support flag.

## Sub-theories

Read `python -m tools.cli slices list --theory weather_model_gap`. Evaluate all
registered subsets, initially `nyc`, `lax`, and `chicago`, against the unchanged
parent output. Report Weather Model Gap, then each subset indented below it,
with its own evidence and bet or skip reason. A city's evidence applies only
to that city's series. It need not wait for a positive aggregate.

## Report

Show source/quote time, entry delay, training count, missing sources and gate
counts. Supported opportunities need a specific Kalshi ticker, side, payable
price, model probability, fee-net and credibility-ranked edge, and available
size. Historical quoted returns do not establish fillable size today. The user
places bets manually and records them through `opportunities mark-taken`.

## Skip

Outside the window, missing exact-run forecasts, fewer than 30 same-source
training labels, missing entry activity, invalid quotes or inadequate depth
skip the affected population. Report the reason rather than researching it
during a floor. Insufficient evidence blocks recommendations, not observations.

## Research replay and scoring

Research sessions may resume the owner collector and frozen replay; the floor
never reruns this statistical test:

```bash
python -m theories.weather_model_gap.collect --help
python -m theories.weather_model_gap.backtest --prepare
python -m theories.weather_model_gap.backtest
python -m tools.cli score report weather_model_gap --save
python -m tools.cli slices report weather_model_gap
```

The first command documents collection options. `--prepare` freezes selections
without returns. Existing frozen artifacts must agree on resume. Changed
thresholds, cities, forecast leads or horizons require a new protocol and
independent evidence, not a rerun marketed as confirmation.
