# backtest-2026-09-01-takerflow — tier A

Replay of follow-the-flow over settled Kalshi markets. Every number here
is regenerable from the ledger (`cli score report taker_flow`,
`cli slices report taker_flow`) and from `decisions.json` beside this
file; the raw per-trade corpus is gitignored and regenerable via
`backtest.collect()`.

## What ran

| | |
|---|---|
| decision point | 24h before resolution |
| flow window | trailing 7 days, ≥ 20 trades |
| entry rule | `\|imbalance\| > 0.6`, take the aggressor's side |
| entry price | last trade at or before the decision point |
| window | resolutions 2026-07-06 → 2026-09-01 |
| markets collected | 5,184 |
| usable decisions | 3,585 (58 settlement days, 1,931 event clusters) |
| rows recorded | 1,105 (those clearing the 0.6 threshold) |

## Headline: the pre-registered rule failed

Pre-registered in `NOTES.md` and committed (`faf78ac`) **before** the full
sample was read. The rule was `|imbalance| > 0.6` at a 24h buffer, and the
claim under test was the Stanford study's localisation of the effect in
single-name markets.

| population | n | clusters | edge (pts) | clustered t | 95% CI |
|---|---|---|---|---|---|
| all | 1,105 | 813 | +0.70 | +0.62 | [−1.51, +2.91] |
| single-name | 635 | 405 | +0.71 | +0.46 | [−2.29, +3.70] |
| broad-based | 470 | 410 | +0.69 | +0.42 | [−2.56, +3.94] |

Every CI includes zero, and **the single-name split shows no difference at
all** (+0.71 vs +0.69). The localisation claim does not replicate on
Kalshi at a horizon this repo can trade. Net of fees the whole population
is −0.17 pts (`calibration_edge_net`), i.e. flat-to-slightly-negative.

## What is there instead: a tail, not a gradient

Splitting the same population at 0.9:

| bucket | n | clusters | days | gross (pts) | clustered t |
|---|---|---|---|---|---|
| `strong` 0.6–0.9 | 782 | 618 | 58 | **−0.78** | −0.60 |
| `extreme` ≥ 0.9 | 323 | 280 | 55 | **+4.29** | +2.04 |

The moderate band is worth nothing; the entire effect sits in near-total
one-sidedness. That discontinuity is what the mechanism predicts — total
one-sidedness is what informed flow looks like and moderate imbalance is
noise — but it was **found by mining this run**, so this run cannot vouch
for it. It is registered as the slice `extreme-imbalance` with this run in
`mined_from_run_ids`; its out-of-sample n is 0 and it is not `ready`.

## What could have killed the tail and did not

Every partition available was checked. The cell is not one lucky corner:

| check | result |
|---|---|
| concentration | top series is 10/323 = **3%** of the cell; 280 clusters over 323 rows |
| leave-one-series-out | worst case still **+3.50** (t=+1.68) |
| price bands | positive in **all five**: +1.06, +6.43, +11.79, +6.67, +2.17 |
| flow side | yes-flow +4.41, no-flow +3.42 — works both ways |
| time | first half +4.46, second half +4.21 |

Consistency across partitions is not significance. It rules out the
one-lucky-corner explanation and nothing more.

## What the buffer sweep says, and why it is not evidence

Kill test 2 asked whether the effect is intra-day and therefore untradeable
at a once-daily rhythm. The answer is not "intra-day" — it is *incoherent*,
which is the more useful finding:

| buffer | 168h | 72h | 48h | 24h | 12h | 6h | 2h | 0.5h |
|---|---|---|---|---|---|---|---|---|
| edge at \|imb\|>0.8 | −3.87 | +4.33 | +6.82 | +2.69 | +0.59 | +0.80 | −2.20 | −2.86 |

A real intra-day effect grows monotonically toward the close. This is
*most negative closest to the close*. The 48h peak is uncorroborated by
its neighbours, and the sweep covered 24 cells where one |t| > 1.7 is what
chance produces. **Nothing in that table is bettable**, and the 24h buffer
was pre-registered because it is the rhythm this repo trades at, not
because it scored well.

## Biases, so the numbers can be caveated

1. **Entry is the last trade price, not the ask.** No historical order book
   exists and candlesticks are empty for archived tickers. This **flatters**
   every number here by roughly a half-spread. At the tail's mean entry of
   0.405 the fee alone is 1.68 pts, so +4.29 gross is ~+2.6 net of fees and
   perhaps +1.1 to +2.1 after a realistic half-spread. **Thin, and the
   reason this is a forward test rather than a recommendation.**
2. **Survivorship in the outcome source** — `settlements` is what past
   sessions captured, not a census.
3. **Decision point is relative to resolution, not close**, so the stated
   buffer is a lower bound on how early the decision was taken.

## Ledger treatment

Rows are recorded as **observations**: `edge_pts_net = 0.0`,
`edge_basis='prior'`. This run *produced* the bucket rates the live theory
claims, so letting it also claim them would make `realization` ≈ 1.0 by
construction and credibility would look earned when nothing was
demonstrated. `rank.realization` treats a non-positive claimed edge as
neutral. The realized calibration edge is unaffected — it is computed from
outcome against entry price, which is what this run exists to establish.
