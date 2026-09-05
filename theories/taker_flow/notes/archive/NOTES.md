# taker_flow — lab notebook

Raw, dated, append-only. The distilled version lives in `THEORY.md`.

## 2026-09-01 — session llm-market-identifier-70: the capability, and the pre-registration

Lane `new-theory`, from ticket `kalshi-taker-flow-toxicity` / idea 32.

### The capability finding, and the correction to it

The ticket led with a capability claim worth more than the thesis:
Kalshi's `/trade-api/v2/markets/trades` is unauthenticated and publishes
the aggressor side of every trade, and no theory here reads it. That part
is true and the client now exists at `tools/kalshi/trades.py`.

**The ticket's highest-value hypothesis is falsified.** It observed that
`KXNFLWINS-27BAL-12` returned trades back to 2026-06-25 — "i.e. back to
market open", 8 days older than the ~60-day settled-market archive floor —
and flagged this as a possible route to history the repo treats as
permanently lost. It is not market open. It is a **hard global retention
floor at 2026-06-26T00:00:00Z**, and the ticket mistook one for the other.

Measured by paging six long-lived markets to exhaustion — 2028 nomination
markets that have traded for over a year, so their own open is nowhere
near this boundary:

    KXPRESNOMD-28-KH        4,338 trades   oldest 2026-06-26T00:00:30Z
    KXPRESNOMD-28-GN       16,048 trades   oldest 2026-06-26T00:00:31Z
    KXPRESPERSON-28-MRUB    4,411 trades   oldest 2026-06-26T00:06:23Z
    KXALIENS-27            15,783 trades   oldest 2026-06-26T00:14:04Z
    KXTRUMPOUT27-27-DJT     3,518 trades   oldest 2026-06-26T01:43:56Z
    CONTROLH-2026-R         9,074 trades   oldest 2026-06-26T00:11:42Z

Sampling settled markets by resolution week agrees: the week of 2026-06-15
returns trades for 0 of 12 markets, the week of 2026-06-22 for 4 of 12
(the floor cutting through it), and every week after for 12 of 12. So the
feed reaches ~67 days where `/markets` reaches ~60 — a one-week extension,
not a recovery route. **Nothing here rescues pre-archive history.**

Undecided and cheap to settle: whether that floor is FIXED (a Kalshi
migration date, in which case the window grows and this becomes valuable
later) or ROLLING (~67 days, advancing daily). It sits exactly at midnight
UTC of one date, which is weak evidence for fixed. `trades.retention_floor()`
re-measures it; one call on a later date decides it.

Two more properties, both invisible from the payload:
- **`min_ts` does not seek backwards.** It is a lower-bound filter on a
  newest-first walk — passing 2025-01-01 returns the most recent 1,000
  trades, not the oldest. Reaching old trades means paging past everything
  after them.
- **The board-wide feed is not a bulk route.** With no `ticker`, 40 pages
  (40,000 trades) covered about four minutes of wall clock. Collect per
  ticker.

### Kill test 4, answered first: the three taker fields are one bit

The ticket warned that `taker_side`, `taker_outcome_side` and
`taker_book_side` are three different fields and that the sample showed
`taker_book_side='ask'` with `taker_side='no'`, and said to pin the
convention before building. Done, over 93,399 trades on the 40
highest-volume markets of the 2026-09-01 board. They are perfectly
collinear — exactly two joint values ever occur:

    (taker_side, taker_outcome_side, taker_book_side)     n
    ('yes', 'yes', 'bid')                            59,875
    ('no',  'no',  'ask')                            33,524

So the apparent contradiction is just the fixed mapping: `taker_book_side`
is stated in YES-book terms and carries no information the side does not.
`normalize()` collapses the three to one bit and **raises** on any other
combination, so a schema change fails loudly instead of silently recording
a side that means something else.

Direction pinned empirically rather than assumed: correlation between
volume-weighted yes-taker imbalance and the yes price change *within* the
window is **+0.174**, monotone across five imbalance buckets (−0.0025 at
imb < −0.5 rising to +0.0012 at imb > +0.5). `taker_side='yes'` means the
aggressor bought YES.

**But the same measurement is the first bad news for the thesis**: the
*lead* correlation — imbalance against the price change over the NEXT
window — is **−0.0075**. At a 25-trade horizon, flow does not predict the
next move at all.

### First pass on settled markets, and why it is not yet the answer

605 usable settled markets (57 settlement days, 266 series), decision point
48h before resolution, 7-day flow lookback. Price predicts outcome
normally (sanity passes). The residual test — imbalance within price band
— found nothing: every within-band CI straddles zero, and pooled
event-clustered t-statistics were −0.64 / −1.51 / +0.44 for no-heavy /
neutral / yes-heavy.

Follow-the-flow as an actual bet was positive and monotone in threshold
(+1.48 / +2.19 / +2.52 / +6.33 points at |imb| > 0.2 / 0.4 / 0.6 / 0.8)
but never significant, the best being t=+1.54 at n=95. **Entry was at the
last trade price, not the ask** — a real entry pays a half-spread on top,
which plausibly erases all of it.

Then a buffer sweep (kill test 2, "is it intra-day and therefore
untradeable at this repo's once-daily rhythm?"). The answer is worse than
intra-day — it is *incoherent*:

    buffer   |imb|>0.2   |imb|>0.6   |imb|>0.8   (edge pts, clustered t)
     168h    -2.16       -5.37       -3.87
      72h    +3.04       +2.21       +4.33
      48h    +1.90       +3.25       +6.82  (t=+1.74)
      24h    -0.13       +1.10       +2.69
      12h    +0.37       +1.39       +0.59
       6h    -0.19       +0.83       +0.80
       2h    -1.11       -0.51       -2.20
     0.5h    -1.28       -1.63       -2.86

A real intra-day effect would grow monotonically as the buffer shrinks.
This is *most negative closest to the close* and bounces around zero in
between. The +6.82 at 48h is a peak in a noisy series, uncorroborated by
its neighbours at 24h and 72h — and I swept 8 buffers × 3 thresholds = 24
cells, where one |t| > 1.7 is what chance alone produces. **Nothing in
that table survives multiple-comparison awareness, and I am not entitled
to bet the 48h cell.**

### PRE-REGISTRATION — written before running the full sample

Everything above is a sweep, so nothing in it can vouch for itself. The
one part of the source's claim I have *not* tested is the part that came
from the source rather than from me: the Stanford study localises the
effect in **single-name** markets and explicitly finds it absent in
broad-based ones. That is a structural, ticker-derivable split, so it is
code, not judgment.

Pre-registered before looking at the full ~6,000-market sample:

- **Population.** Settled markets resolving after 2026-07-06 (so a 7-day
  flow window sits clear of the retention floor), with ≥ 20 trades in the
  window.
- **Decision point.** 24 hours before resolution. Chosen because it is the
  rhythm this repo can actually trade at, not because it scored well —
  48h scored better and I am deliberately not using it.
- **Signal.** Volume-weighted taker imbalance over the trailing 7 days.
- **Rule.** |imbalance| > 0.6 → take the side the flow is taking.
- **The split under test.** Single-name vs broad-based, derived from the
  ticker's strike suffix: a suffix matching `^[TB]\d` is a numeric
  threshold (broad-based); an alphabetic suffix names an entity
  (single-name). Crude but mechanical and auditable.
- **Prediction.** Positive edge in single-name, absent in broad-based.
- **Kill.** If the single-name event-clustered CI includes zero at full
  sample, the thesis does not replicate on Kalshi at a tradeable horizon
  and the idea goes `dead` with this as the record.

Entry is at the last trade price throughout, which **flatters** the
strategy by the half-spread. Any positive result must clear that before it
means anything.

## 2026-09-01 (cont.) — the pre-registered test failed; what replaced it

**Result of the pre-registration above: FAILED.** At |imb|>0.6 with a 24h
buffer over 3,585 usable decisions (58 settlement days, 1,931 event
clusters): all +0.70 (t=+0.62, CI [−1.51,+2.91]), single-name +0.71
(t=+0.46), broad-based +0.69 (t=+0.42). The single-name localisation —
the one part of the Stanford claim I had not already contaminated by
sweeping — shows **no difference whatsoever**. Net of fees the population
is −0.17. By the stated kill criterion the pre-registered rule is dead.

The pre-registered structural proxy has known impurities (city-coded
weather `KXRAIN-…-BOS` and outcome-coded games `…-TIE` both classify as
single-name). I left it exactly as registered rather than re-tuning it
after seeing the result. It measured no difference either way, so the
impurity decided nothing.

**What is actually in the data is a discontinuity, not a gradient.**
Splitting at 0.9: `strong` (0.6–0.9) is −0.78 over 618 clusters, `extreme`
(≥0.9) is +4.29 over 280 clusters (t=+2.04). Moderate one-sidedness is
worth nothing and near-total one-sidedness is worth something — which is
what the mechanism actually predicts, and is a sharper claim than the one
I pre-registered.

I then tried to kill it and could not: top series is 3% of the cell,
positive in all five price bands, positive on both flow sides, stable
across time (+4.46 / +4.21), leave-one-series-out worst case +3.50. See
`backtests/RESULTS.md` for the tables.

**It is still post-hoc, so it is registered as a slice, not bet.**
`extreme-imbalance`, predicate `{"extra": {"flow_bucket": "extreme"}}`,
with `backtest-2026-09-01-takerflow` declared in `mined_from_run_ids`. Its
out-of-sample n is 0 and it is not `ready` — it must earn ≥10 clusters and
≥5 settlement days forward before it can rank anything. That is the whole
point: the run that suggested it can never vouch for it.

**Honest size of the prize, if it survives.** Mean entry in the tail is
0.405, where the fee alone is 1.68 pts. So +4.29 gross is ~+2.6 net of
fees, and a realistic half-spread on top leaves perhaps +1.1 to +2.1.
Thin. Worth testing forward; not worth claiming.

### A defect found by running it, and fixed the same day (v1 → v2)

The first live run produced 816 candidates and 18 of them claimed a
`model_prob` above 1.0, with entries at an ask of **1.000**. Two distinct
bugs with one root cause — applying a flat population average at prices
where it is arithmetically impossible:

- an ask of 1.00 costs exactly what it can pay, so its maximum profit is
  zero and it is not a position at all;
- the most a position bought at `entry` can gain is `(1-entry)` in points,
  so a 4.29-point claim on a 0.97 ask is unpayable by construction.

v2 excludes an unpayable ask in `screen` (funnel key `unpayable_ask`) and
caps the claim at the headroom in `price`. Bumped `continues`: neither
changes any decision on a payable candidate at a normal price, so the tier
A replay stays valid evidence, but both change the decision path.

Worth noting **how** this was caught: not by reading the code but by
looking at the extreme values of what the live run recorded. The screen's
liquidity filters (spread ≤ 0.05, OI ≥ 500) pass an ask of 1.00 happily,
because a one-cent-wide book at 1.00 is *liquid* — it is just not
*profitable*. Liquidity filters do not imply payability, and any theory
pricing from a population average should check both.

### Data-conventions incident worth recording

Two collector processes ended up appending to one JSONL concurrently (a
`nohup … &` inside a backgrounded tool call detached and survived, then a
second run was launched against the same file). The result was interleaved
writes: one headless fragment whose ticker and outcome were unrecoverable,
plus ~2,600 duplicate records. Recovered by scanning the raw text with a
streaming `JSONDecoder` for complete objects and keeping the copy of each
ticker with the most trades — 5,184 distinct markets survived, and only
one record was lost outright.

The lesson is not "be careful": it is that **per-record `flush()` is not
atomicity**, and an append-only checkpoint is only single-writer-safe. The
resume logic happened to make this recoverable — the dropped market simply
gets re-fetched next run, because the resume set is built from parseable
lines. A collector that had instead written one final blob would have lost
everything.

### v2 live run, and a defect left deliberately unfixed

802 rows recorded (1,768 liquid → 482 thin flow → 471 below threshold →
13 unpayable ask → 802 candidates; 421 `extreme`, 381 `strong`). The new
`unpayable_ask` exclusion fired 13 times, so the v1 bug was real and is
now closed at the top of the price range.

**The bottom of the range has the mirror problem, and I left it.** Every
one of the ten highest-edge rows is an ask of 0.00–0.01, because a flat
points-edge is largest in relative terms where the price is smallest —
while the same replay measures only **+1.06 (t=+0.36)** in the
[0.00,0.15) band against the pooled +4.29. The pooled number is dominated
by mid prices.

Not hotfixed, for a reason worth stating: the obvious fix is per-band
constants, and those bands come from the run that produced the pooled
number. Adopting them is another post-hoc parameter choice on the data
that suggested it — the exact move the pre-registration above exists to
prevent. Ticketed
(`flat-edge-overstates-penny-longshots`) with three legitimate routes,
none of which is "hard-code the five band numbers".

**It has no live consequence today**, which is what makes waiting
affordable. Checked rather than assumed: `cli promote` puts the top row at
**R5 MEASURED-AGAINST**, `quoted: false`, reasoning "matches slice
'extreme-imbalance', which is registered but below its evidence gates" and
"the record outranks the claim". The theory recommends nothing, so the
defect only decides which suppressed rows sort highest. It becomes real
the moment the slice clears its gates — fix it before then.
