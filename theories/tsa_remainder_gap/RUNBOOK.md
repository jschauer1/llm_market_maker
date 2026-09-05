# TSA Remainder Gap — runbook

## Stages

One mechanical stage: sealed published daily counts, strict contract parsing,
empirical remainder forecast, executable-price selection, and normal Theory
recording. No research or judging subagents are needed to execute it.

## Run

```text
python -m theories.tsa_remainder_gap.run
```

Run Friday 15:00–15:30 UTC. Outside the window, report the skip without collecting
an unnecessary board. Inside, collect and hash primary TSA responses, require
Monday–Thursday plus 52 complete prior weeks, refresh quotes and best-level depth,
and record at most one selected position for the target week. The runner must
finish all these checks; a formula alone is not a live run.

## Record

The inherited Theory start/finish contract owns ledger/provenance writes.
Probabilities are mechanical model estimates. Report claimed and credibility-
weighted edge separately using the promotion tool; historical diagnostic returns
never become production calibration. The user places bets manually. If reporting
a bet worth placing, remind them to record their action:

```text
python -m tools.cli opportunities mark-taken <id> taken --theory tsa_remainder_gap --size <N> --reason "<why>"
```

## Sub-theories

None registered initially. Check `python -m tools.cli slices report tsa_remainder_gap`
for current registrations. Evaluate every registered subset when the parent runs,
and list each indented beneath it even when no position qualifies. A descriptive
side or holiday table is not a registered subset.

## Report

Name the parent and every registered subset, selected ticker/side and executable
price or the exact skip reason. Include gate counts, source/quote timestamps,
run ID and whether evidence is experimental. A positive model estimate is not
proof of a positive realized edge. Do not omit an unsuccessful or skipped week.

## Skip

Wrong entry time; incomplete or stale source; ambiguous contract; market closed
at entry; invalid/missing quotes; insufficient open interest or depth; no side
clearing the fixed edge floor; or an already-recorded position for that week.

## Historical diagnostic

Read the [frozen protocol](backtests/trg1-20260905/PROTOCOL.md). Reuse the completed
campaign and its receipts; do not recollect or tune an already evaluated holdout.

```text
python -m theories.tsa_remainder_gap.collect
python -m theories.tsa_remainder_gap.backtest --prepare
python -m theories.tsa_remainder_gap.backtest
```

The collector's resumable raw responses form one immutable dataset. Preparation
freezes decisions before settlement. Both development and holdout use `exp/`
run IDs and stay excluded from production scores. Results, clustered intervals,
no-signal weeks and exclusions belong in the campaign, not copied into notebooks.
