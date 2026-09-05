# Weather Model Gap

## Hypothesis

Traders may price a city point forecast instead of the payout station's full
temperature distribution. An exact archived forecast, corrected by that
station's measured forecast errors, may price daily brackets better. Weather
specialists are the counterargument; forecast disagreement must earn its place
against payable asks. Mechanical, with no LLM judgment.

## Status and version

Version 1, WG-1. The frozen replay selected zero trades: the August 14 switch
from NWS to The Weather Company leaves only 18 comparable history dates per
city, below the 30-label training minimum. No edge was measured. The registry
is authoritative; no city is recommendable until its own validation passes.
[Initial result](backtests/wg1-20260905/RESULTS.md). A separate experimental NWS
replay selected 297 positions and lost 5.61 net points on average; no city
passed its support test. This weakens the case for repeating the simple model,
without transferring old-source results into current-source probabilities.
[Legacy diagnostic](backtests/wg1-nws-20260905/RESULTS.md).
[Protocol and source design](backtests/wg1-20260905/PROTOCOL.md).

## Procedure

Only Weather Company daily-high series KXHIGHNY (Central Park), KXHIGHLAX
(LAX), and KXHIGHCHI (Midway). Use Open-Meteo's Single Runs API with the exact
`ecmwf_ifs` run initialized at 12 UTC the preceding day. Forecast is the maximum
hourly Fahrenheit temperature during the station's fixed standard-time day,
rounded half-up to a whole degree. Never substitute reanalysis or a stitched
forecast. Coordinates, station IDs and source rules are verified.

For each station, use its preceding 90 calendar days of forecast errors,
requiring at least 30 exact payout labels settled before entry. Model today's
high as today's forecast plus each historical error. A strike's YES probability
is `(hits + 0.5)/(n + 1)`; NO is its complement. No city borrows another's errors.
The model corrects average station/sample bias; it does not assume that weather
errors are constant across seasons or extreme conditions.

Entry is 00 UTC on the target date. Require exact entry-hour activity,
open interest >=100, spread <=4 cents and bought ask between 5 and 95 cents.
Buy at most one contract per station/date: the largest forecast gap after fees,
at least 8 points, ties by ticker then side. YES costs its ask; NO costs
`1 - YES bid`. The live window ends at 01 UTC and requires fresh quotes and
available size. The floor executes the [runbook](RUNBOOK.md), without research.

## Evidence

March–June 2026 supplies history for a July–August chronological holdout;
calibration advances only as prior labels become available. Retained inventories
include current and historical APIs without final-volume selection. An exact
entry candle is mandatory; missing quotes cannot become hypothetical fills.
Decisions and source hashes freeze before returns; registration binds the
freeze, and production eligibility recomputes actual ledger outcomes.

Support requires at least 30 independent clusters on each of event, target
weather date and settlement date, no pending selected outcomes, and positive
lower confidence bounds. The pooled test uses 95% intervals. Each city uses
mean minus 2.6 cluster standard errors, covering three predeclared comparisons.
Historical candles cannot prove fillable depth; positive results remain
quoted-price evidence. A practically large effect is rejected only where its
upper confidence bound is below +3 net points; otherwise it remains unconfirmed.

## Sub-theories

- `nyc`: unchanged parent output for KXHIGHNY.
- `lax`: unchanged parent output for KXHIGHLAX.
- `chicago`: unchanged parent output for KXHIGHCHI.

Run and report every registered subset whenever the parent runs. Each city
calibrates separately and must qualify separately. A supported city may operate
while the aggregate is negative. Keep other cities recording zero-edge prior
observations; never narrow the parent's screen to its current winner.

## Learnings

[Browse scoped lessons](learnings/README.md). Original source receipts,
protocols and results stay in owner campaign folders. New findings need a
future decision they change; no duplicate narrative or raw tables in summaries.
