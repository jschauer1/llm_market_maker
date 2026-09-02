---
title: Individual strikes get pushed off the smooth implied distribution: fit a monotone curve and bet the deviant rung
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: done
closed: 2026-08-29
resolution: DEAD 2026-08-29, killed at step one before the theory was ever registered. At a tradeable liquidity floor, 97.6% of 959 strike rungs sat EXACTLY on their own isotonic fit, maximum deviation 1.5c, zero candidates. Deviations appeared only in rungs whose median volume was 0, where the mid is an empty book rather than a price. Study: tickets/study/answer/2026-08-29-smile-smoothing-ladder-flatness/. Generalized into rule 0 of this backlog -- an edge living between siblings of one Kalshi event should expect to find nothing, and should measure before it builds.
---
Effort: M · LLM in decision path: no · Backtest tier: A

**This spec was acted on; the `resolution` field above says what
came of it.** Kept rather than deleted, because a completed ticket
is the record of what was asked for and why — which is what a
future session re-deriving the same idea needs.

## Assessment

**Applicability 4/5 · Implementability 3/5 · Likelihood of success 3/5 ·
Composite 10/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 4:* ladders are everywhere on the board; capped at one
  candidate per ladder, still a steady flow.
- *Implementability 3:* the isotonic fit is easy; the work is
  spread-charged backtesting and defensive ticker parsing, plus the
  dependency on structural-arb's sibling grouping.
- *Likelihood 3:* the mechanism is options-desk standard practice, but
  the inversion risk is close to a coin-flip until measured: a deviant
  strike may be the informed one, and the spec's direction test exists
  precisely because the sign cannot be assumed.

## 1. Hypothesis

Even when a strike ladder is monotone (no hard
[structural-arb](2026-08-24-structural-arb.md) violation),
individual strikes get pushed off the smooth implied distribution by
uninformed flow. Fit a monotone probability curve across the ladder; bet
the strike whose price deviates most from the fit, toward the fit, when
the deviation clears fees.

## 2. Evidence

Same mechanism as structural-arb — retail hits single strikes without
repricing siblings — but the soft version fires far more often than hard
violations. The fitted curve pools information from the whole ladder,
which is more data than any single strike's book. Smile smoothing is
standard practice in options markets; Kalshi ladders (CPI, temps, crypto
ranges, box office) are the same object with worse participants.

## 3. Non-goals and exclusions

- Ladders with < 4 liquid strikes — the fit is meaningless.
- No parametric distribution assumptions in v1 (isotonic only); a
  parametric v2 needs its own version bump and justification.
- Hard violations are structural-arb's trade, not this one's — when both
  would fire on a ladder, structural-arb owns it (it is the strictly
  better trade).

## 4. Decision procedure

Fully mechanical. Group ladder siblings by event; fit an isotonic
(shape-constrained, assumption-light) curve to mid prices; compute each
strike's deviation; candidate = deviation > fees + buffer at the
executable quote — express everything as buying YES or NO at the ask.
`edge_basis="model"`. Liquidity floor per strike.

## 5. Data requirements

Board quotes for live scanning; candlesticks with bid/ask for the
backtest; the sibling-grouping helper from structural-arb.

## 6. Backtest design

Tier A. For settled ladders in history: at decision points, fit on that
day's prices, take the rule's trades, settle. Trap: fitting on mids but
"trading" at mids badly overstates edge on thin strikes — the backtest
must charge the historical spread.

## 7. Kill criteria

If deviations mean-revert to the curve but the *curve* was wrong
(deviating strikes settle in their own favor as often as not), the
noise-trader premise is inverted — the deviant strike is where informed
flow was. Test the direction explicitly before trusting the sign; a
confirmed inversion kills this theory (an inverse theory would need its
own justification, not a sign flip).

## 8. Implementation plan

`theories/smile_smoothing/{THEORY.md,fit.py}` + tests. Build after
structural-arb (shares the grouping helper) or build the helper here and
promote later. Effort M.

## 9. Testing approach

Unit tests: isotonic fit on fixture ladders, deviation computation at
executable quotes, the min-strike and liquidity guards. Backtest fixture
with a planted off-curve strike that does/doesn't revert.

## 10. Open risks

- Correlated candidates: one ladder can emit several strikes whose fates
  are mutually exclusive by construction; cap at one candidate per ladder
  (the largest deviation) or the ledger fills with internally-hedged
  rows.
- CPI/econ ladders overlap
  [econ-anchoring](../open/2026-08-24-econ-anchoring.md)'s turf: if
  both run, the anchoring signal is *directional* while this one is
  *shape-based*; they can disagree legitimately, but `find-edge`'s dedup
  must collapse same-ticker conflicts rather than presenting both.

## 11. Sources

Mechanism-based; structural-arb's evidence covers the flow mechanism, and
options-market smile smoothing is the standard-practice analogue.
