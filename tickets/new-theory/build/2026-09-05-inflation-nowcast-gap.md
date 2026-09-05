---
title: Cleveland Fed daily nowcasts may outprice monthly Kalshi CPI ladders
lane: new-theory
created: 2026-09-05
created_by: codex-recurring-sources-20260905
author_lane: find-theories
author_focus: inflation-nowcast-gap
author_context: Bounded recurring macro, health, and energy source audit against the cached live board; this was the only candidate with a public daily history, enough independent Kalshi dates, and current executable central strikes.
status: open
---
Effort: M - LLM in decision path: no - Backtest tier: A if the retained official daily-vintage rows and Kalshi candles pass the timestamp audit; otherwise contaminated and ineligible for promotion.

## Assessment

**Applicability 3/5 - Implementability 4/5 - Likelihood of success 3/5 - Composite 10/15.** CPI releases occur monthly, but two mature Kalshi series currently have enough archived dates and liquid central strikes. The source is public, mechanical, and already stores daily historical paths. The main uncertainty is whether the crowd has already absorbed the same prominent nowcast.

## Hypothesis

The Cleveland Fed's public daily inflation nowcast contains release-specific information from oil, gasoline, CPI, and PCE inputs. Near the release, some Kalshi monthly CPI ladders remain anchored to a stale consensus or recent print. A fixed-time, walk-forward residual distribution around the official nowcast can therefore price individual integer-tenth thresholds better than the executable Kalshi asks.

This is distinct from `econ-anchoring`: that ticket extrapolates recent official releases and uses the Kalshi mode as a consensus proxy. This theory's only predictor is an independently published, timestamped external model. No trend-side prior or LLM judgment enters the probability.

## Verified population and sources (2026-09-05 snapshot)

Start only with `KXCPI` and `KXCPICORE`. Kalshi's public historical endpoint returned 60 and 49 independent release dates respectively (2021-07-12 through 2026-06-10 for headline; 2022-07-13 through 2026-06-10 for core). The cached live board contained 40 headline and 44 core strike markets across four target months each; 19 strikes had OI >= 100 and spread <= 10 cents. Treat the two series on the same release date as one calendar cluster and allow at most one position across both.

The Cleveland Fed monthly chart payload is public at `https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json?sc_lang=en`. On 2026-09-05 it was 7,584,820 bytes, contained 159 target-month envelopes from 2013-07 through 2026-09, daily labels, all four monthly measures, and a payload comment dated 2026-09-04. The official page says updates occur each business day around 10:00 a.m. ET and the official 2023 assessment says values from 2013:Q3 onward were generated and published on the website in real time.

`KXPCECORE` (22 archived release dates) and `KXPCEHEAD` (zero archived dates under that ticker) are excluded from v1. They may be added prospectively after reaching 30 dates, never pooled in to rescue CPI results.

## Fixed decision procedure

1. Capture the official JSON bytes and hash them. For each target month, reconstruct the last daily nowcast visible by **12:00 p.m. ET on the business day before the scheduled release**. The noon cutoff is safely after the source's stated roughly-10 a.m. update. If the record has no unambiguous calendar date or the source method/rules do not match the target, skip.
2. Use the first officially published, seasonally adjusted month-over-month CPI value at one decimal, exactly matching Kalshi's rules. No revised outcome may enter training.
3. Per series, use an expanding walk-forward set of strictly earlier release dates. Require at least 30. Form residuals `actual_first_print - official_nowcast` without fitting coefficients. For each current threshold, add historical residuals to the current nowcast, apply Decimal `ROUND_HALF_UP` to one decimal, then evaluate Kalshi's strict `>` gate. Estimate YES as Jeffreys `(hits + 0.5)/(n + 1)` and NO as `1 - YES`.
4. Reconstruct the exact Kalshi quote at the fixed cutoff. Require open status, OI >= 100, spread <= 10 cents, activity in the cutoff hour, and ask in [0.05, 0.95]. Compute the normal fee at that ask. Require model probability minus ask minus fee >= 8 percentage points.
5. Across headline/core and all strikes for a release date, select one candidate: highest fee-net gap, then ticker and side. Use only the executable ask. Record the source digest, forecast row/date, training dates, model probability, quote timestamp, spread, OI, and fee.

## Cheapest decisive test

Download and retain the single official JSON response, then fetch historical Kalshi market metadata and one fixed hourly candle per ticker/date. Freeze the eligible decision rows and source hashes before joining outcomes. Use the earliest 30 dates in each series only as warmup; every later date is holdout. Report decisions and ROI for headline, core, pooled, and by calendar release date, with unresolved/missing-price denominators. The two series share monthly release dates, so inference clusters by release date rather than treating series or strikes as independent.

A useful control runs the same gates and dates with the existing `econ-anchoring` predictor. The new theory must add predictive value or executable ROI beyond that control; shared positions are identified rather than double-counted.

## Kill criteria

- Any official history row cannot be tied to a date when it was publicly available, or historical chart values prove retrospectively rewritten without a usable archived/vintage source: stop; do not promote a contaminated replay.
- Fewer than 30 complete prior release dates per supported series at its first scored decision: exclude that series.
- Frozen holdout has no positive fee-net ROI, or apparent point-forecast disagreement does not produce >=8-point executable gaps: record the model as accurate-but-priced or unsuccessful and stop.
- Do not treat the current point nowcast crossing a strike as a probability or recommendation. Only the predeclared residual CDF may supply `probability_estimate`.

## Current concrete check, not a recommendation

The 2026-09-04 official page showed August headline CPI at 0.36% m/m. The cached 2026-09-05 board quoted `KXCPI-26AUG-T0.3` YES at 0.55 ask, 0.06 spread, and OI 23,673.11. This establishes a live, liquid disagreement in point direction; it does not establish that the residual-model probability beats 55% after fees.

## Primary sources

- Cleveland Fed indicator and timing/method FAQ: https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting
- Official daily historical chart payload: https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json?sc_lang=en
- Cleveland Fed real-time assessment (including the post-2013:Q3 publication provenance): https://www.clevelandfed.org/publications/economic-commentary/2023/ec-202306-real-time-assessment-inflation-nowcasting-cleveland-fed
- Kalshi historical markets endpoint: https://api.elections.kalshi.com/trade-api/v2/historical/markets

## build — 2026-09-05

Build authorized: official daily nowcast history plus 60 headline and 49 core CPI Kalshi release dates support a fully mechanical tier-A implementation; freeze protocol before any outcome or return join.

## review — 2026-09-05

Reviewed by the Claude session before commit. The collector had never been run
against its sources; probing them with the theory's own parsers found:

- `data.parse_nowcasts` rejects the real Cleveland payload on its first
  envelope. Event labels such as `CPI Aug` and `PCE Jul` occupy the category
  list but have no data slot, so every dataset array is shorter than its label
  list and the length check raises. Align by date labels only.
- `data.parse_contract` accepts only `KXCPI-`/`KXCPICORE-` event tickers. The
  archive holds 41 of 60 headline and 29 of 49 core release months under the
  legacy `CPI-`/`CPICORE-` prefixes with the same rules format, so 19 months
  per series survive, all from Dec 2024. The 30-traded-date bar is unreachable
  as built. The protocol names series tickers, so accepting legacy event
  prefixes is a code fix, not a protocol change, provided it lands before any
  outcome join.
- BLS answered 403 to the collector's five backoff attempts and 200 to the same
  user agent a minute later. Six parallel workers over about 157 archive pages
  will be blocked; serialize with a pause, or take first prints from ALFRED.
- No replay driver or `run` module exists, though the RUNBOOK names one. The
  screen reads quotes, open interest and open status from board `Market`
  objects and nothing builds those from the dataset's candles at entry. The
  historical candlestick endpoint itself works and returns the fields
  `normalize_candle` expects.
- Cleveland's own `Actual CPI Inflation` series is unrounded current vintage
  (Feb 2024 reads 0.442, first print 0.4), so the BLS first-print choice stands.
