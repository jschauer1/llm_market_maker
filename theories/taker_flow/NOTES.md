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
