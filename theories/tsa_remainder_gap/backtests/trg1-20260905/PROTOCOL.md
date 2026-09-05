# TRG-1: Friday TSA remainder

Frozen 2026-09-05, before collecting entry quotes or inspecting trading returns.
Mechanical, no LLM judgment; contamination tier A. **This campaign is an
experimental reconstruction from today's mutable TSA archive. It cannot supply
production calibration or establish an executable historical edge.** The source
audit is [here](../../sources/SOURCE_AUDIT.md); sampled public archives did not
recover the disputed vintages.

## Population and split

Enumerate every Sunday from 2022-06-19 through 2026-08-30. Obtain every explicit
TSA-source, strict-above weekly-average contract from both Kalshi API tiers,
including legacy TSAW tickers when their rules meet that population. Deduplicate
by ticker; conflicting duplicates fail closed. Use the contractual target
Sunday, never realized close time, to set Friday 15:00 UTC entry. Preserve missing
calendar weeks and exclusions in coverage.

Development: 2022-06-19 through 2025-08-24. Chronological holdout: 2025-08-31
through 2026-08-30, 53 calendar weeks, including the already-observed missing
2025-11-09 event. The census found 52 available event weeks in that holdout;
do not replace a missing quote or other later exclusion with an earlier week.
The observed September 2026 current-week ratios/quotes are outside this campaign.
No parameter is fitted to development returns. Report both partitions, with the
holdout primary. Source checks have already inspected settlements, so this is
not an untouched source-validation test even though trading returns are unseen.

## Forecast and entry

For target Sunday D, S4 is the Monday-through-Thursday sum. Each of the preceding
52 calendar weeks must contain all seven daily counts. For each prior week,
r = (Friday + Saturday + Sunday)/(Monday + Tuesday + Wednesday + Thursday).
For a strict-above strike K travelers/day, let t = (7K - S4)/S4.
qYES = (count(r > t) + 0.5)/53; qNO = 1 - qYES.
No seasonal bins, alternate lookbacks, fitted coefficients, or holiday exception.

Read the hourly candle **ending exactly Friday 15:00 UTC**. Use its closing
YES ask and bid; NO ask = 1 - YES bid. Require valid uncrossed quotes,
0 < bought-side ask < 1, spread <= 0.10, open interest >= 100, and computed
net edge >= 8 points using `tools.sizing.fee_pts`. All entry liquidity fields
come from that candle. No terminal volume or open-interest substitution. Missing
exact candle fails closed. At most one position per week: highest net edge,
then ascending ticker, then ascending side. No-signal weeks get a reason, not a
fake ledger row. No historical displayed-depth claim: candles do not supply it.
Known actual close or settlement at/before entry excludes an unavailable market,
even if a partial/stale candle bears that hour's timestamp. Actual close never
sets the entry anchor or acts as a forecast feature. Keep exclusions in coverage.

## Recording and evaluation

Seal dataset bytes and their SHA-256 before evaluating. Freeze outcome-free
decisions and their digest before settlement. Replay through the ordinary Theory
start/finish contract with `exp/trg1-20260905/development` and
`exp/trg1-20260905/holdout`. Settle with Kalshi's binary result, not today's TSA
recomputed mean or an inconsistent expiration value. Report source disagreements
separately; never drop losing trades because their source changed.

Primary return is settlement payoff minus executable ask minus repository fee.
Also report the fee rounded upward to a whole cent for one contract. Show entered
weeks, no-signal/exclusion counts, pending outcomes, each side, and weekly and
settlement-day clustered 95% intervals. Keep pending best/worst bounds explicit.
Holiday-week descriptions are exploratory and cannot qualify a subset.

A source-valid confirmation needs >=30 entered weeks, no pending outcomes, and
positive lower 95% bounds under both weekly and settlement-day clustering and
rounded fees. An interval containing zero is unconfirmed. Upper 95% bound below
+3 net points is evidence against this fixed procedure delivering that practical
edge, within the measured source scope. Zero signals establishes only no
eligible entries. This experimental campaign cannot satisfy the source-valid
condition regardless of returns. Promising subsets need registered, independent
confirmation; a flat parent does not disprove them.

## Prospective procedure

Run Friday 15:00–15:30 UTC using an actual sealed TSA response containing Thursday
and all 52 prior weeks, current contract rules, and fresh executable quotes with
at least 10 contracts at the best ask. Missing data means skip. Repeated runs
cannot record a second position for the same week. Historical diagnostic rows
remain excluded; a live arithmetic probability is a probationary model estimate,
never inherited proof that this model beats prices.
