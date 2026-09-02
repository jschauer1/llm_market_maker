# Kalshi prices the accumulation collapse in real time — there is no lag to harvest

**Verdict: DO NOT BUILD `accumulation-decay`.** Reached on branch 1 of the
rule pre-registered in `PREREG.md` before any calibration number existed.

Session `fleet-w2-g2`, new-theory lane, 2026-09-01. Spec:
`tickets/new-theory/completed/2026-09-01-accumulation-decay.md`, registry
idea 31. Population: **222 settled `KXALBUMEQUIV` markets, 28 events,
10-11 resolution days**, 2026-06-21 to 2026-08-30. 1,046 liquid
observations.

## The price path, which is the whole answer

Cost to buy the **favorite** at executable quotes, by fraction of the
seven-day Luminate tracking window elapsed. Liquid only
(`open_interest >= 100`, `spread <= 0.07`):

| elapsed | n | cost p25 | **median** | p75 | net edge | t | evts |
|---|---|---|---|---|---|---|---|
| pre-window | 145 | 0.680 | **0.830** | 0.930 | +2.94 | +0.57 | 24 |
| 0–25% | 140 | 0.760 | **0.910** | 0.970 | −0.70 | −0.15 | 26 |
| 25–50% | 164 | 0.800 | **0.950** | 0.980 | +2.62 | +0.45 | 25 |
| 50–75% | 194 | 0.900 | **0.980** | 1.000 | −2.64 | −0.73 | 28 |
| 75–100% | 194 | 0.960 | **1.000** | 1.000 | −1.87 | −1.15 | 28 |
| **POST (count fixed, unpublished)** | **209** | **1.000** | **1.000** | 1.000 | +0.30 | +0.82 | 28 |

**The thesis predicted prices would lag this collapse. They do not lag it
at all.** By the time the window is three-quarters elapsed the median
favorite already costs a full dollar. The unfiltered table is the same
shape (medians 0.840 / 0.910 / 0.940 / 0.970 / 1.000 / 1.000).

## The number that makes it unarguable

In the POST bucket the count is **already fixed in Luminate's data and not
yet published** — the purest possible form of "determined but still
trading", and the case the ticket was really about. So ask the most
generous question available: **what could a perfect forecaster make there?**

> Buy the favorite at the executable ask in the POST bucket, and assume it
> **always** wins:
> **mean +0.453 pts, median +0.000 pts, max +9.37.**
> 22 of 209 observations carry >= 2 pts of gross headroom; 10 carry >= 5.

That is the ceiling with **perfect foresight and zero forecasting cost**.
No data source, model, or run-rate arithmetic can beat it, because the
price is already there. 94.7% of the bucket is quoted at >= 0.97 and the
favorite wins 99.5% of the time — the market is not merely close, it is
right.

This is not a one-sided-book artifact: the bucket splits **107 YES-favorites
and 102 NO-favorites**, and both have a median cost of exactly 1.000.

## Where headroom does exist, it is uncertainty and not mispricing

The 75–100% bucket has a real perfect-foresight ceiling of **+2.889 pts**
and 41 of 194 observations priced at or below 0.95. That looks like the
edge — until you notice the favorite there wins **94.3%** of the time, not
99.5%. The 5.7% that lose eat exactly the headroom, and the measured net
edge is **−1.87 (t=−1.15)**.

So the residual price late in the window is **genuine remaining
uncertainty, correctly sized**. That independently satisfies branch 3 of
the pre-registered rule ("headroom survives but calibration edge <= 0 ->
the residual is not mispricing"), on the adjacent bucket, for the same
verdict.

## Honest limits, stated as pre-registered

- **The outcome test was always underpowered and was demoted before it
  ran.** 28-31 event clusters is the ceiling for this family and cannot be
  raised: one event is one album-week resolving off one Luminate number,
  the family makes ~3 events/week, and the DB already holds more history
  than Kalshi's ~60-day archive still serves. MDE ~25 pts. Every `t` in the
  table above should be read as "no LARGE effect", never "no 3-point edge".
- **The kill does not rest on those t-statistics.** It rests on the price
  distribution (n=1,046 observations, no clustering problem) and on the
  perfect-foresight ceiling, which is arithmetic. A 3-point edge cannot
  hide behind a 0.45-point ceiling.
- **This is a null about weekly tracking windows.** The annual families
  (`KXARTISTSTREAMSY` 401 liquid, `KXMUSICREPORT`) have almost no settled
  history by construction, so they are untested — but they are untested in
  a way that cannot be fixed for a year, which is itself a reason not to
  build.

## What the probe established for free, and is worth keeping

**The tracking window is recoverable from the ticker with no external
data.** `KXALBUMEQUIV-ANG26SEP24-15K` -> week ending 2026-09-24 -> window
September 18–24 -> market closes 2026-09-27T14:00Z. Verified against the
title text on **33 of 33** board events with no exceptions, and it parsed
238 of 238 settled tickers. Any future work on this family gets its event
clock for nothing.

**The three-day publication gap is a real, structural, mechanically
detectable state** — window closed, count fixed, market still open — and
Kalshi prices it at 1.000. That is a useful negative fact about the whole
`settled-but-trading` idea family (idea 9), because this was its most
favourable instance: a determined outcome, a known publication lag, and no
wording latitude at all.

## Reproducing

```bash
python collect.py candles.jsonl     # 238 settled markets, 222 with candles
python measure.py candles.jsonl
```

`candles.jsonl` holds the full daily candle series per market (executable
`yes_bid_close`/`yes_ask_close`, volume, open interest) and is kept: this
history is **past Kalshi's ~60-day archive** and is no longer re-fetchable.
