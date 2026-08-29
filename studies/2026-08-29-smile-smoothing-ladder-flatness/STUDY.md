# Kalshi strike ladders are already on their own isotonic fit

**Date:** 2026-08-29 · **Status:** complete · **Tier:** A (no model in the
measurement path) · **Outcome:** killed idea `smile-smoothing` (backlog #11)

## Question

Spec [`smile-smoothing`](../../docs/superpowers/specs/theories/2026-08-24-theory-smile-smoothing-design.md)
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
