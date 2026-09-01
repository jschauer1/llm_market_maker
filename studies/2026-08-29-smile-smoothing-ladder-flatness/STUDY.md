# Kalshi strike ladders are already on their own isotonic fit

**Date:** 2026-08-29 · **Status:** complete · **Tier:** A (no model in the
measurement path) · **Outcome:** killed idea `smile-smoothing` (backlog #11)

## Question

Spec [`smile-smoothing`](../../tickets/new-theory/completed/2026-08-24-smile-smoothing.md)
claims that even on a *monotone* ladder — no hard `structural_arb`
violation — individual strikes get pushed off the smooth implied
distribution by uninformed flow. Fit a monotone curve across the ladder,
bet the most deviant strike back toward it.

The theory was built to the spec before being measured. It is not
registered, because the measurement killed it at step one.

## Method

`fit.py` (the would-be theory's stage 1, kept here as the artifact):

- Group board markets by `(event_ticker, underlying_key)` — never by
  event alone, since one Kalshi event routinely holds a ladder per player
  or per team whose strikes compare numerically and mean nothing across
  underlyings (`tools.ladders.underlying_key`).
- Keep one-sided ladders only (`greater*` or `less*`, never mixed, never
  `between` — those have two edges and no single threshold).
- Fit **isotonic regression** (hand-rolled PAVA) to the mids, in the
  direction arithmetic forces: `greater*` rungs price P(X > k), which is
  non-increasing in k; `less*` rungs the reverse. No distribution, no
  smoothness, no parameters.
- Deviation is `mid − fit`. A candidate must clear fees **at the
  executable ask**, not at the mid — the spec's named trap.
- Ladders already non-monotone at executable quotes are conceded to
  `structural_arb`, whose trade is riskless and strictly better.

`measure.py` sweeps the per-rung liquidity floor, because the entire
question is whether off-curve strikes exist *where they can be traded*.

Board: the 2026-08-29T11:46:51Z pull, 111,102 markets.

## Result

| min vol | max spread | ladders | rungs | **rungs exactly on the fit** | max deviation | best net | ≥3 pts |
|---|---|---|---|---|---|---|---|
| 200 | 0.10 | 150 | 959 | **97.6%** | 0.0150 | +0.86 | **0** |
| 50 | 0.15 | 204 | 1,328 | 97.2% | 0.0225 | +0.86 | **0** |
| 10 | 0.25 | 283 | 1,827 | 96.4% | 0.0550 | +1.43 | **0** |
| 0 | 0.40 | 809 | 7,064 | 90.3% | 0.1167 | +6.23 | 4 |
| 0 | 1.00 | 977 | 8,518 | 83.8% | 0.3087 | +17.93 | 41 |

At any tradeable liquidity floor, **the isotonic fit is a no-op**: 96–98%
of rungs sit *exactly* on it, the largest deviation anywhere is 1.5¢, and
**nothing clears a 3-point buffer**. Median deviation is 0.0000.

Candidates appear only as the spread filter opens — and they are not
trades. Of the 41 that clear 3 points with **no liquidity floor at all**:

- median volume **0** — they are untraded markets
- only **3** have volume ≥ 200
- only **2** clear both spread ≤ 0.10 and volume ≥ 200

A 40¢-wide book on a zero-volume rung has no meaningful "mid". Its
distance from the fit measures **the absence of a quote**, not uninformed
flow, and buying it at the ask pays the whole spread for the privilege.
This is precisely the trap the spec's §6 named, arriving through the live
screen instead of through a backtest.

## Why the premise fails

Kalshi lists and quotes ladder siblings **together, within one event**.
The same market makers post the whole ladder, so it comes out internally
consistent by construction — there is no smoothing left to do. The
options-desk analogy in the spec's §2 imagines strikes quoted
independently enough to drift apart; on Kalshi they are not.

This is the same structural fact the
[calendar-arb study](../2026-08-27-calendar-arb-firing-rate/) found from
the other direction: near-dated date ladders live inside one event and
are priced consistently (min basket cost 1.000, never below). Two
independent measurements, two dead theories, one cause. **Anything whose
edge lives *between siblings of one Kalshi event* should expect to find
nothing** — that is the generalizable result, and it is worth checking
before building the next such theory.

## What survives

`tools/ladders.py` — `YesSet`, `yes_set`, `underlying_key`,
`strike_value`, `is_upper_tail`. Elevated from
`theories/structural_arb/scan.py` during this work under the normal
caller-count rule (three real callers: `structural_arb`, the
[violation-liquidity probe](../2026-08-29-structural-arb-violation-liquidity/),
and this study). `structural_arb` re-exports the names and its funnel is
byte-identical before and after, so the move did **not** bump its
version. That elevation is the durable output of a dead theory.

## Limits

- **One board.** But the deviation distribution is degenerate (97.6%
  *exactly* zero, not merely small), which is a structural property of
  how ladders are quoted rather than a daily fluctuation — a power
  problem would look like small non-zero deviations, not this.
- Liquidity floors are the shared-screen conventions, not tuned here.
- The spec's own kill criterion (§7) was an *inversion* test — do deviant
  strikes settle in their own favour? That test was never reached: it
  presumes deviations exist to have a direction, and at tradeable
  liquidity they do not.

## Revisit angle

Recorded on the idea. Not "never" — "not this way, and not on a quiet
board":

1. **Event-time flow.** Measure during a high-flow window (a CPI print, a
   heavily-traded game) rather than a quiet Saturday, when retail
   actually hits single strikes. If deviations still do not open up under
   load, the premise is dead outright.
2. **Cross-event, not within-event.** The within-event channel is closed
   by construction (see above). Ladders on the *same underlying in
   different events* are the only place sibling inconsistency could
   survive — that is a different theory needing its own pre-registration.
3. **The one liquid outlier.** `KXGPTAPP-26SEP07-T105` (vol 2,558, spread
   0.05, +17.93 claimed) is the single candidate that passes both floors
   and is worth an eyeball — but one candidate per board is not a theory,
   and it may simply be a ladder whose true curve is not monotone in the
   naive strike ordering.

## 2026-08-29 (session 3, item 4) — smile-smoothing killed at step one; tools/ladders.py survives it (migrated from RESEARCH_LOG.md)

> Contributed verbatim by the parallel session `llm-market-identifier-4f`,
> which owned this build under the 2026-08-29 session split. Appended by
> `llm-market-identifier-18`, which owns this file for the day.

**Did:** Took smile-smoothing (backlog #11) under the session split with
llm-market-identifier-18. Built it to spec, then measured it against the whole
111,102-market board **before registering it as a theory**. Killed it. Study:
`studies/2026-08-29-smile-smoothing-ladder-flatness/` (code, sweep, write-up).

**Learned:**

1. **The population does not exist.** At a tradeable liquidity floor
   (vol>=200, spread<=0.10) the isotonic fit is a no-op: **97.6% of 959 rungs
   across 150 ladders sit exactly on it**, median deviation 0.0000, max
   deviation anywhere 1.5c, and zero candidates clear a 3-point buffer. Still
   96.4% on-fit and zero candidates at spread<=0.25.
2. **The candidates that do appear are empty books, not flow.** Only with no
   liquidity floor at all do 41 clear 3pts — median volume **0**, only 3 of 41
   with volume>=200, only 2 clearing both floors. A 40c-wide book on a
   zero-volume rung has no meaningful mid, so its distance from the fit
   measures the *absence of a quote*. That is the trap the spec's section 6
   named, arriving through the live screen instead of a backtest.
3. **Cause, and it generalizes.** Kalshi lists and quotes ladder siblings
   *together inside one event*, so the ladder is internally consistent by
   construction. This is the same structural fact the 2026-08-27 calendar-arb
   study found from the other direction (near-dated date ladders inside one
   event, min basket cost 1.000, never below). Two independent measurements,
   two dead theories, one cause. **Anything whose edge lives between siblings
   of one Kalshi event should expect to find nothing** — check that before
   building the next such theory.
4. **A dead theory still shipped something.** `tools/ladders.py` — `YesSet`,
   `yes_set`, `underlying_key`, `strike_value`, `is_upper_tail` — elevated out
   of `structural_arb` under the caller-count rule (three real callers).
   structural_arb re-exports the names and its funnel is byte-identical before
   and after, so **no version bump**. 29 new tests, suite **929** green.
5. **Measure before registering.** Building to spec first and registering only
   after the screen produces something cost one session and left the ledger
   clean. A registered theory emitting zero rows forever would have looked
   identical to one that was never run.

**Next:** series-bias-mining (#4) is the remaining open build, but it is a
settled-history sweep and would contend with the rate-limited candlestick
endpoint; hold until the politics collection is done.
