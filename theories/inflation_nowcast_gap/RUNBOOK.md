# Inflation Nowcast Gap — runbook

## Stages

One deterministic stage: load and verify retained sources, parse exact CPI
contracts, compute the expanding residual CDF, enforce executable gates, and
record through the normal Theory contract. No judging agent is used.

## Run

Collect or resume the retained dataset first:

```text
python -m theories.inflation_nowcast_gap.collect --campaign theories/inflation_nowcast_gap/backtests/ing1-20260905
```

Run the live adapter with the resulting dataset:

```text
python -m theories.inflation_nowcast_gap.run --dataset <path-to-dataset.json>
```

Live collection and recording are permitted only from noon through 12:59:59
America/New_York on the source business day immediately before the BLS release.
Outside that window, the runner exits before loading the board or fetching
quotes. Historical replay uses the campaign command documented beside its
frozen protocol.

## Record

The inherited `start()`/`finish()` path records the selected Kalshi ticker,
exact ask, model probability, fee-net edge, source/protocol hashes, forecast
row, training count, and entry timestamp. Live recording re-quotes targeted
markets and atomically refuses a second position for the same BLS release date.
The user alone places bets.

## Sub-theories

None registered initially. Check the current registry rather than assuming
this stays true:

```text
python -m tools.cli slices report inflation_nowcast_gap
```

Every future registered slice must be reported even when it has zero matching
positions.

## Report

Show the parent and every registered slice, run id, source and quote times,
funnel removals, selected ticker/side/ask/model probability/net edge, or the
exact zero-decision reason. Distinguish model disagreement from demonstrated
forecast skill and from positive fee-net trading evidence.

## Skip

Skip on the wrong time; missing or changed receipt; wrong protocol/source
digest; fewer than 30 prior same-series first prints; ambiguous rules or target
month; absent exact entry-hour activity; closed market; OI below 100; spread
above 10 cents; ask outside `[0.05, 0.95]`; net model gap below eight points;
or an already-recorded position for the release date.

## Evidence

The only frozen replay is
[ING-1](backtests/ing1-20260905/PROTOCOL.md). Report headline, core, pooled,
and release-date clusters, including every missing-data denominator. Do not
retune ING-1 after seeing results.
