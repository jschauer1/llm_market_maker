# News Drift

## Hypothesis

Large daily price moves can leave further information adjustment for later
days. Participants slow to revise their pre-news beliefs are the proposed
counterparty. This is a testable mechanism, not an assumption that market
makers leave money available. Buy in the move direction and hold to resolution.

## Status and version

`testing`, version 1, ND-1. The procedure and evidence protocol were frozen
on 2026-09-05 before measuring its historical returns. Current registry state
is authoritative. No production calibration is installed. The selected-cache
experiment and complete-calendar chart replay both produced zero supported
bets. The chart replay had only eight training signals; its later all-signal
return was negative even if every pending contract wins. This rejects that
sample as a basis for betting, without proving continuation never works.
[Chart result](backtests/nd1-charts-long-20260905/RESULTS.md).

## Stage 1 — mechanical screen

Target event categories Politics, Elections, Economics, Entertainment, World.
Unknown categories, Sports, Mentions, and continuous financial/crypto prices
are outside the population. At the shared 2026-09-05T00:41:36Z capture, 4,761
markets in those categories passed open, OI >=100, spread <=0.04, nonterminal
quotes. That is the market population before the signal, not a count of bets.

Five consecutive daily candles are required. The fourth candle's YES quote
midpoint must move >=0.15 from the third and finish within [0.15,0.85]. Its
volume exceeds the median of the three preceding volumes. Enter at the fifth
candle, one full day later: YES after a rise, NO after a fall. All five quotes
are finite, ordered, and within [0,1]; volumes are nonnegative. Entry midpoint
is within [0.15,0.85], spread <=0.04, open interest >=100, and volume >0.
No interpolated gaps; each timestamp differs by exactly 86,400 seconds.
Live execution uses that history and the current quote, also checked against
the entry gates, within 24 hours after the last completed daily candle.
Historical NO ask is **1 - YES bid**, YES entry is YES ask. Midpoints detect
the move; neither leg is assumed buyable at a midpoint. Deadline/realized
close does not select a signal. Repeated attempts do not multiply positions.
An entry at/after actual historical trading close is vetoed as untradeable;
this is a market-open check, never a future-close proximity feature.

## Stage 2 — judgment

None. No model in the decision path; replay contamination tier A. Code and
data provenance still apply. Historical coverage and execution bias are
separate from the absence of model contamination.

## Pricing

Fit one pooled directional residual: mean(realized directional payout minus
entry directional midpoint). A forecast equals current directional midpoint
plus this residual, clamped to [0,1]. The artifact requires >=30 training
tickers, >=10 event clusters, a strict outcome-availability cutoff, source
digest and ND-1 protocol ID. The forecast is mechanical (`edge_basis=model`),
with fees subtracted from probability minus payable ask. Nonpositive signals
are recorded as rejected controls. Missing/unapproved calibration records
zero-edge `prior` observations; it must never produce recommendations.

## How to backtest

Use the same screen and pricing functions as live, with one point-in-time
context per entry. Each campaign freezes its population and dates before
measurement. The clean chart campaign uses January–April training and
May–August validation; the earlier cache experiment used August 1 as cutoff.
Both training decisions and known outcomes precede the declared cutoff.
Only the training partition fits a model. One first entry per ticker per
campaign. No cell search: the pooled continuation result is primary, and
the reversal side is an explicitly exploratory paired diagnostic.

Start with cached daily bid/ask candles. The settled-only, partial historical
frame is not a census: save a source manifest and quantify missing coverage.
If selection/right-censoring cannot be bounded, the campaign stays `exp/`
and cannot authorize production calibration. Candle closes have no depth or
queue information; claims are limited to quoted-price returns, and actual
recommendations need current depth. Current series category metadata is
structural but may have changed; report its capture/source.
The initial cache was collected through the insider screen's final-volume
and category filters with windows anchored to realized close. Its selection
cannot represent the whole ND-1 population. Clustered uncertainty cannot fix
that selection. The row-weighted estimand is one contract per ticker; report
largest event share and effective event count. Conditional calibration alone
does not identify slow information diffusion as the causal mechanism.

## Evidence bar and falsifier

Show realized gross and fee-net points, one-contract rounded-fee sensitivity,
event and settlement-day counts, and 95% cluster intervals separately by
event and settlement day. Positive support needs both lower bounds above
zero, >=30 event clusters, >=10 settlement days, and valid population
reconstruction. A 95% upper bound below +3 net points rules out a practically
large ND-1 effect in this population. Insufficient power means unconfirmed,
not proof that all continuation mechanisms fail.

## Sub-theories

`weekly-charts`: the unchanged parent signal restricted to six predefined
music-chart/album-sales series, selected by issuance structure before seeing
returns. [Protocol and exact population](backtests/nd1-charts-long-20260905/PROTOCOL.md).
Its calibration, if earned, applies only to those series. Evaluate it whenever
the parent runs and report it separately. Other subdivisions discovered in a
campaign need new independent evidence; discovery is not automatically bettable.

## Learnings

Start at [the learning map](learnings/README.md). Campaign folders retain the
frozen protocols. Reusable findings need population and evidence scope.
