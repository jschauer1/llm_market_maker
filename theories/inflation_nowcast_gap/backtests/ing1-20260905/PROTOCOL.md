# ING-1 frozen protocol — 2026-09-05

Frozen before any Kalshi outcome or return join. This file defines the first and
only test of the v1 procedure. Changing a threshold or population requires a
new protocol and run id; ING-1 is never overwritten or rerun with new choices.

## Claim and population

The Cleveland Fed's independently published daily inflation nowcast may price
the next first-print monthly CPI value better than Kalshi's executable ladder.
V1 contains exactly `KXCPI` (headline CPI) and `KXCPICORE` (core CPI). Both
resolve from the first published, seasonally adjusted month-over-month change,
reported to one decimal. PCE series are excluded because their Kalshi archives
do not yet provide 30 independent release dates.

The unit of independence is the BLS release date. Headline, core, and every
strike released on the same date form one cluster. The procedure may select at
most one ticker and side across both series for a release date.

## Time and source identity

For each release, use the latest Cleveland Fed monthly nowcast row published on
the last source business day before the scheduled BLS release. Entry is fixed
at 12:00:00 America/New_York on that row's calendar date. The chosen source row
must be dated no later than the entry date; no later source value may be used.
The noon cutoff is after the source's stated update time of about 10:00 a.m. ET.

Forecast source:
`https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json?sc_lang=en`.
Retain the exact response bytes, URL, fetch timestamp, byte count, payload
comment, and SHA-256. Its series names must be exactly `CPI Inflation` and
`Core CPI Inflation`. No year-over-year or quarterly values enter v1.

Labels come from the contemporaneous first BLS CPI publication, never a later
revised series. Retain each source release or table, URL, publication timestamp,
and SHA-256. A label is available to a decision only when its publication
timestamp is strictly before the decision timestamp.

Kalshi market metadata and hourly candles are retained raw with request URL,
parameters, fetch timestamp, and SHA-256. A candle may support entry only when
it is the exact 60-minute bar at the fixed entry cutoff and contains no period
after the decision. Missing responses stay explicitly missing; no synthetic
prices or volume are permitted.

## Dataset contract

`data.load_dataset(path)` returns:

```text
{
  schema_version: "inflation-nowcast-gap/v1",
  campaign, collected_at, protocol_digest, source_digest,
  sources: {
    cleveland: {url, fetched_at, sha256, byte_length, payload_comment},
    bls: [{url, fetched_at, sha256, release_date, target_month}],
    kalshi: {...retained request receipts...}
  },
  training_rows: [{
    series_ticker, measure, target_month, cutoff_ts,
    forecast_observation_date, forecast_value,
    actual_value, actual_published_at,
    forecast_source_digest, label_source_digest
  }],
  events: [{
    series_ticker, event_ticker, target_month, release_ts, entry_ts,
    forecast: {measure, observation_date, cutoff_ts, value, source_digest},
    markets: [raw Kalshi market objects],
    candles: {ticker: [normalized hourly bars]},
    candle_reasons: {ticker: reason-or-null},
    entry_activity: {ticker: {volume, bar_end_ts}},
    market_sources: {ticker: {...receipt...}}
  }],
  coverage: {...counts and explicit exclusion reasons...}
}
```

All timestamps are aware ISO-8601 strings. Decimal measurements and strikes
are retained as strings until parsed with `Decimal`. Root `source_digest`
commits to the critical normalized rows and source receipt identities.

## Mechanical forecast

For an event and decision time, take only `training_rows` with the same series,
an earlier target month, and `actual_published_at < decision_time`. Use all
such rows from the official history beginning in 2013; this is expanding, not
rolling. Require at least 30 complete rows.

For each training row compute the exact Decimal residual
`first_print_actual - official_nowcast`. Add every prior residual to the current
official nowcast. Round each resulting possible print to one decimal with
Decimal `ROUND_HALF_UP`, then apply the contract's strict `rounded_value >
strike` condition. Equality is NO. If `hits` of `n` residuals satisfy YES:

```text
q_yes = (hits + 0.5) / (n + 1)
q_no  = 1 - q_yes
```

This is an empirical residual-resampling model estimate, not a confidence bound
on nature. There is no fitted coefficient, LLM, market-price input, alternate
window, or post-result parameter choice.

## Executable gates and selection

The market must be open at entry and must match one of the two exact series,
target month, source, and strict-above rule. Require open interest at least 100,
YES spread at most 0.10, positive volume in the exact entry-hour bar, and the
chosen side's executable ask in `[0.05, 0.95]`. YES costs `yes_ask`; NO costs
`no_ask` (or the exact complement of YES bid only when that is how the
normalized Kalshi quote represents NO ask). Use the repository's normal fee.
Require `100 * (model_probability - ask) - fee_points >= 8.0`.

Choose the one qualifying position with highest net model gap across all
strikes and both series for a release. Stable ties sort by ticker, then side.
Record every funnel exclusion by reason.

## Replay and evidence bar

Run id: `ing1-20260905/holdout`. This is a fully mechanical tier-A replay if
the timestamp/source audit passes. Each historical context uses the fixed entry
timestamp and the same `screen()` and `price()` as live operation. Freeze the
decision manifest and its hashes before joining the selected Kalshi settlements.

Report headline, core, pooled, and release-date clusters. Preserve all missing
price, activity, rules, forecast, label, and settlement denominators. Compare
forecast calibration and executable-price calibration honestly; do not require
building the separate econ-anchoring theory as a control.

Positive evidence requires at least 30 independent **traded release dates**,
positive fee-net ROI, and a release-date-clustered 95% confidence interval whose
lower bound is above zero. A smaller sample is underpowered regardless of point
estimate. Failure to clear the bar does not authorize lowering the 8-point,
spread, OI, activity, ask, or one-position gates.

## Live boundary

Live operation is permitted only from 12:00:00 through 12:59:59 ET on the
frozen entry date for an event and only from newly captured source data and
fresh Kalshi quotes. Repeated sessions record at most one live position per BLS
release date even if the selected ticker changes. Outside the window, or when
history/source/quote/activity is incomplete, report an explicit zero-decision
observation and do not collect or record a recommendation.
