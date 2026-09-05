---
title: Price daily temperature brackets from archived forecasts and Kalshi's measured station errors
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: Existing weather-model-gap proposal revised after source checks, before forecast-versus-price returns.
status: open
---
# WG-1 build specification — frozen 2026-09-05

## Mechanism and population

Casual traders may price a city point forecast instead of the payout station's
full distribution. A forecast at that station's coordinates, corrected by its
measured forecast errors, may price brackets better. Professional weather
traders are the counterargument: disagreement must beat payable asks out of
sample. Mechanical, no judgment, tier A.

Parent population: exactly KXHIGHNY, KXHIGHLAX, KXHIGHCHI daily highs under
Weather Company rules. Each city is a preregistered sub-theory with separate
calibration and record. The current/historical API union contains184 March–
August2026 events per city;551/552 have consistent payout temperatures. NYC
June23 has a blank expiration value on one leg and cannot train the model.
Live Sep5 NYC has six brackets; observed asks include .26 below79, .56 at79–80,
and .18 at81–82. These are population checks, not recommendations. No
forecast/price returns were inspected.

## Sources and clocks

Retain unfiltered series inventories from current and historical Kalshi APIs.
A training label requires all event legs finalized and binary, exactly one YES,
matching finite whole-degree expiration_value, and agreeing settlement_ts
strictly before the decision. Exclude fallback last-fair-price settlements,
rule-source mismatches and inconsistent labels. Missingness stays visible;
never substitute NWS or discard unsettled holdout trades. Current TWC rules
supersede the original proposal's assumption that NWS always resolves highs.

Pin ECMWF IFS via Open-Meteo Single Runs API, models=ecmwf_ifs,
run=12:00 UTC on D-1. This exact model identifier is fixed; do not substitute
ecmwf_ifs025 or another variant.
Entry00:00 UTC on target date D is12hours after initialization. Retain request,
response, model, coordinates, units and fetch time; reject mismatched or
incomplete runs. Forecast proxy is the maximum hourly Fahrenheit temperature
in D's fixed local-standard day: NYC05Z, Chicago06Z, LAX08Z through the next
day's same hour, end exclusive. Pin station coordinates/elevation from metadata.
Round to integer F with decimal half-up ties. Hourly sampling need not capture
an intra-hour maximum; historical errors measure this difference. Never use
stitched historical forecasts or reanalysis. Individual ensemble-member history
lasts only three days here, so use exact deterministic runs plus empirical errors.

## Frozen procedure

For each station, take usable labels in the preceding90 calendar days, with
settlement_ts before entry and at least30 observations. R=Y-F uses exact payout
temperature Y and the identically constructed forecast proxy F for that past
date. Today's modeled temperatures are F_today+R. For each published strike,
q_yes=(count satisfying the strike+0.5)/(n+1); q_no=1-q_yes. This is smoothed
empirical forecasting, not a confidence bound or introspected probability.
Never pool station errors.

Use the hourly candle ending exactly at entry: YES ask, NO ask=1-YES bid.
Require finite ordered quotes, bought ask in[.05,.95], spread<=.04, OI>=100,
positive entry-hour volume, and market open at entry. Select at most one
contract/side per station/date, highest model edge after fees, minimum8points;
ties by ticker then side. Record through the theory contract. Future fields
never select entries. Live uses fresh quotes only during00:00–01:00UTC and the
same inputs; otherwise report outside entry window. Report entry delay; current
recommendations require order-book depth, absent from historical candles.

## Evidence and falsifier

Collect March1–August31,2026. March–June supplies calibration history; July1–
August31 is the single chronological holdout. Calibration advances using only
labels settled before each entry. Freeze inventories/protocol before returns.
Estimand: one contract per selected station/day, held to resolution. Report net
and rounded one-contract fees, coverage, event, target-weather-date and actual-settlement-date clustered95%
intervals, and pending-outcome bounds. One primary pooled test; city subsets
are separate and cannot borrow evidence. Positive support needs >=30 settlement
days and all three lower bounds above zero. City deployment needs its own support:
with at least 30 clusters on each axis, each city uses mean minus 2.6 cluster-SE
above zero on all three axes. This conservative adjustment covers the three
predeclared city comparisons; a supported city need not wait for its parent.
An upper bound below+3 netpoints rules out a practically large effect in that
population; otherwise negative/underpowered stays unconfirmed. Never retune
threshold, lead, cities or lookback against these holdout outcomes.

## Implementation plan

1. Owner-local collector, strict labels/run parsing and checkpointed source
   captures; test availability and clock boundaries.
2. Small forecast/residual/pricing functions and Theory subclass with injection
   seams, runbook and city sub-theories.
3. Replay actual start/finish, record tier-A provenance, settle known outcomes,
   independently review selection and statistics.
4. Run current procedure; save compact results. Enable recommendations only
   where the frozen holdout supports them. The built theory replaces this spec.

## Primary sources

- [Exact runs and publication lag](https://open-meteo.com/en/docs/single-runs-api).
- [Stitched historical forecasts](https://open-meteo.com/en/docs/historical-forecast-api).
- [Ensemble retention](https://open-meteo.com/en/docs/ensemble-api).
- [Kalshi NYC example](https://api.elections.kalshi.com/trade-api/v2/events/KXHIGHNY-26SEP03?with_nested_markets=true):
  payout84, consistent legs, TWC source and settlement timestamp.
- [TWC station metadata](https://weather.com/kalshi/api/climate/primary?date=2026-09-03).

The [shared proposal contracts](../../../../tickets/new-theory/README.md) apply. Forecast accuracy alone
is not evidence of a tradable edge. Exclude conflicting source rules and report
what every gate removed. Retain paid/original evidence; keep prose compact.
