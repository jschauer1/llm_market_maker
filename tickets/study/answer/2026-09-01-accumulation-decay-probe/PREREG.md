# Accumulation decay — pre-registration, written BEFORE any calibration number

Ticket: `tickets/new-theory/open/2026-09-01-accumulation-decay.md` (registry
idea 31). Session `fleet-w2-g2`, new-theory lane, 2026-09-01.

**Written before any price-vs-outcome figure was computed.** At the time of
writing I had looked at exactly four things: which settled markets exist for
this family (238 across 31 events, 11 resolution days), the shape of the
ticker, the fact that the tracking window is recoverable from the ticker, and
the candle schema. No calibration, no bucket means, no edge.

## The thesis being tested

The ticket's own primary kill test, quoted: *"Measure realized P(YES)
against implied price, bucketed by FRACTION OF WINDOW ELAPSED, over settled
history. If the calibration is flat in elapsed-fraction, the thesis is
dead."*

## The structure, established before any measurement

`KXALBUMEQUIV` resolves on Album Equivalent Units accumulated during a
**seven-day Luminate tracking week**. Three facts, verified on all 33 events
on the 2026-09-01 board with zero exceptions:

1. The ticker's event segment ends in the **tracking week's END date**
   (`KXALBUMEQUIV-ANG26SEP24-15K` -> week ending 2026-09-24).
2. The window is that date minus six days, inclusive
   (`ANG26SEP24` -> September 18-24, 2026), matching the title text in
   33/33 cases.
3. The market **closes three days AFTER the window ends** (close
   2026-09-27T14:00Z for a window ending 09-24).

So the window is recoverable from the ticker alone with **no external data**,
which is what makes this test free — and (3) creates a bucket the ticket did
not anticipate: a three-day period where the count is **already fixed in
Luminate's data but not yet published**, and the market still trades.

## Elapsed fraction

For a candle at time `t`, window `[W0, W1)` with `W0` = start date 00:00Z and
`W1` = end date + 1 day 00:00Z:

    f = (t - W0) / (W1 - W0)

Buckets fixed here: `f < 0` (pre-window), `[0, 0.25)`, `[0.25, 0.5)`,
`[0.5, 0.75)`, `[0.75, 1.0)`, `f >= 1.0` (**post-window, determined,
unpublished**).

## Inclusion rules (rule 0b — who is in the sample)

- Settled `KXALBUMEQUIV` markets with `result in (yes, no)`: **238 markets,
  31 events, 11 resolution days**, 2026-06-21 to 2026-08-30.
- One observation per (market, bucket): the daily candle whose `end_ts` is
  nearest the bucket midpoint and inside the bucket.
- **Liquidity filter (primary):** `open_interest >= 100` at that candle AND
  `yes_ask_close - yes_bid_close <= 0.07`. This is the filter validated in
  `theories/no_side_premium/studies/answer/2026-09-01-liquidity-filtered-side-split/`, and the ticket
  explicitly demands spread AND open interest rather than a price cap,
  because the 0.980-0.995 placeholder-ask band sits directly in this
  theory's path. Unfiltered numbers reported beside, never as the headline.
- Prices are **executable**: buying YES costs `yes_ask_close`, buying NO
  costs `1 - yes_bid_close` (rule 0f). No mids anywhere.
- Fees at the entry ask via `fee_pts` in `tools/sizing.py`.

## Power floor, stated before running — and it is the binding constraint

**31 event clusters is the ceiling and cannot be raised.** One event is one
album-week resolving off a single Luminate number, so every strike in the
ladder is one draw. The family produces ~3 events/week and the DB already
holds 11 weeks — more than Kalshi's ~60-day archive, so this history is
already saved and no more is fetchable.

At 31 clusters the SE of a per-bucket calibration edge is about
`sqrt(0.25/31) ~= 9 pts`, so the **MDE is roughly 25 points**. That is far
above a theory-grade 3-6 point edge.

**Therefore the outcome test is DEMOTED to secondary, and the design carries
a primary test that does not depend on outcomes at all.**

### PRIMARY — the price path (high power, no clustering problem)

**Cost to buy the favorite**, per observation:
`min(yes_ask_close, 1 - yes_bid_close)` is *not* it — the favorite is the
side the market prefers, so: favorite = YES if `(yes_ask+yes_bid)/2 > 0.5`
else NO, and its cost is `yes_ask_close` or `1 - yes_bid_close` respectively.

Report the distribution of that cost by bucket. This is a statement about
**prices**, so n is observations rather than clusters, and it is precise.

The thesis requires headroom to survive at `f >= 1`: if the market has
already priced the determined outcome, there is nothing to harvest no
matter what the outcomes did.

### SECONDARY — calibration (low power, only detects a large effect)

Net edge of buying the favorite at the ask, by bucket, clustered on
resolution day (11) and reported with its event-cluster count. **A flat
secondary result establishes "no LARGE mispricing", not "no 3-point edge".**
That limitation is stated here, before the numbers, so it cannot be
quietly dropped afterwards.

## Decision rule, fixed before the numbers

* Cost to buy the favorite at `f >= 1` is **already >= 0.97** (<= 3 pts of
  headroom, before fees of ~2 pts at that price) -> prices have already
  converged; there is nothing left to harvest -> **DO NOT BUILD.**
* **Headroom survives at `f >= 1`** AND the secondary calibration edge in
  that bucket is positive -> a candidate edge -> proceed to design the
  screen and pre-register the theory.
* Headroom survives but calibration edge <= 0 -> the residual is **not**
  mispricing (it is restatement/rules risk or genuine uncertainty) ->
  **DO NOT BUILD**, and record which.
* Fewer than 10 liquid observations at `f >= 1` -> **NOT MEASURED**; say so
  and do not read the pooled number as a substitute.

## What this cannot settle

Whether the *annual* families (`KXARTISTSTREAMSY`, `KXMUSICREPORT`) behave
like the weekly one. They have almost no settled history by construction,
which is why the ticket says to build the weekly family first — but a null
here is a null about weekly tracking windows, and that should be said
rather than generalized.
