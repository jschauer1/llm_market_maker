# ND-1 cached replay — no supported bet

**Diagnostic, not independent production evidence.** The frozen continuation
rule ran through the real theory and recorded 148 training and 56 holdout
positions. The fitted training residual was too small to price any holdout
signal positively after spread and fees. No live calibration was installed.

| Partition | Tickers | Events | Settlement days | Net points/contract | Event 95% interval | Day 95% interval |
|---|---:|---:|---:|---:|---|---|
| Training | 148 | 89 | 34 | -1.51 | [-8.33, +5.30] | [-8.66, +5.63] |
| Holdout, all signals | 56 | 33 | 13 | +0.57 | [-15.03, +16.18] | [-23.87, +25.01] |

The holdout's +2.94 points against midpoint becomes +1.95 at the ask,
+0.57 after unrounded fees, and +0.12 after one-contract rounded fees.
The opposite-side diagnostic is -5.33 net points. Neither sign is supported.
The wide intervals do not rule out a +3-point effect; this is **unconfirmed**,
not proof that daily continuation never works. The primary modeled strategy
selected zero positive-edge holdout bets; the table describes all signals,
not returns earned by a portfolio it recommended.

## Scope and reproducibility

[Protocol](PROTOCOL.md), [manifest](manifest.json), [machine results](results.json),
[training artifact](diagnostic_calibration.json), [checkpointed decisions](decisions.jsonl).
Training cutoff: 2026-08-01; holdout entry dates: August 1–17. The source digest
and exact ticker universe are in the manifest. The two ledger run IDs are
`exp/nd1-cache-20260905/train` and `exp/nd1-cache-20260905/holdout`.

The signal is mechanical (contamination tier A), but this cache was selected
by a different theory using category/final-volume filters and histories
anchored to realized close. That selection prevents a general ND-1 claim.
Missing categories and incomplete coverage are quantified in the manifest.
Experiment lanes exclude these rows from pooled production scores; that score
was checked to remain n=0. The artifact also blocks use outside an experiment.

Returns assume entry at a daily quoted ask, not historical depth or actual
fills. Actual close only vetoes entries after trading ended; it does not
select an attractive time-to-deadline. Outcome availability uses settlement_ts.
The holdout's largest event is 12.5% of rows (20.36 effective events), so
nominal ticker count materially overstates independent information.

## What this changes

Do not tune a domain/threshold to rescue this holdout or reuse its residual
as a live forecast. The separately preregistered chart cohort collects a full
population with fixed calendar windows. That is a test of missing coverage,
not another claim that the same selected cache proved an edge.
