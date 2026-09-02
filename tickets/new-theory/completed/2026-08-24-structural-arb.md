---
title: Within-event logical violations -- non-monotone ladders, NO-baskets below their payout -- are riskless when they exceed fees
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: done
closed: 2026-09-01
resolution: BUILT. Theory `structural_arb` v1-v4, status `testing`. The geometry is correct and the violations are real; the TRADEABLE firing rate is zero. An exhaustive check of all 6,414 mutually-exclusive events on one board found exactly 1 NO-basket below its payout, at 0.125c/leg against a 1c/leg buffer. Across 17 board captures, 12 of 16 violations were KXWTAGTOTAL at zero open interest. Day 6 of its own 60-day kill clock; no retirement proposed. See theories/structural_arb/studies/answer/2026-08-29-structural-arb-violation-liquidity/.
---
Effort: S · LLM in decision path: no · Backtest tier: A

**This spec was acted on; the `resolution` field above says what
came of it.** Kept rather than deleted, because a completed ticket
is the record of what was asked for and why — which is what a
future session re-deriving the same idea needs.

## Assessment

**Applicability 3/5 · Implementability 5/5 · Likelihood of success 3/5 ·
Composite 11/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 3:* when it fires it is the best bet on the board, but
  it fires rarely, and multi-leg baskets are awkward to execute manually
  before quotes move.
- *Implementability 5:* an afternoon of arithmetic over the board;
  fixtures are trivial to construct.
- *Likelihood 3:* per-firing success is near-certain by construction; the
  uncertainty is entirely in the firing rate net of fees at retail
  latency, which public arb bots compress. The snapshot replay measures
  that rate cheaply before any claim is made.

## 1. Hypothesis

Within a single event, prices must satisfy hard logical constraints: a
strike ladder must be monotone (P(above 50k) ≥ P(above 60k)), and a
mutually-exclusive-exhaustive outcome set must have YES prices summing to
≥ $1 at the bid and ≤ $1 + spread at the ask. When executable quotes
violate a constraint by more than fees, the trade is close to risk-free.

## 2. Evidence

Retail flow hits individual strikes without repricing siblings, and
Kalshi has no cross-contract margining to force consistency. Public
cross-platform arb bots exist (several on GitHub), which caps how long
violations last — but a scanner that runs every session costs nearly
nothing, and the user only needs the violation to exist at the moment
they look. Practitioner documentation reports single-market rebalancing
arb extracting $10.6M in 12 months on Polymarket with ~2.7-second
windows — within-Kalshi single-event consistency is the less-competed
corner of the same phenomenon, and the user's manual workflow only needs
the slower-decaying instances. Expected firing rate: low. Expected edge
when it fires: real.

## 3. Non-goals and exclusions

- Top-of-book only; no depth-walking, no multi-fill execution modeling.
- Non-exhaustive outcome sets (an implicit "none of the above" that never
  trades) support only the monotonicity check, never basket sums — the
  scanner must verify exhaustiveness from event metadata before applying
  the sum rule.
- Cross-*event* logical constraints are out of scope here; they belong to
  [implication-graph](../open/2026-08-24-implication-graph.md).

## 4. Decision procedure

Fully mechanical. From the board, group markets by `event_ticker`:

- Ladders (strike-ordered siblings detected from ticker structure):
  ask-side monotonicity violations net of fees.
- Mutually-exclusive events: `sum(YES asks) < 1 − fees` (buy the basket)
  and `sum(NO asks) < (k−1) − fees`.
- Require a buffer (start: 1¢ per leg) and top-of-book size on every leg.
  `edge_basis="model"` — the edge is arithmetic.

## 5. Data requirements

Board only (quotes per sibling), fee math from `tools/sizing.py`. No
external data.

## 6. Backtest design

Tier A against snapshot history: replay stored board snapshots
(`tools/snapshot.py` keeps complete raw payloads) and count violations
executable net of fees. Honesty constraint: snapshots are point-in-time,
so the backtest measures *existence*, not persistence — THEORY.md must
say so rather than claiming fill certainty.

## 7. Kill criteria

Not applicable in the usual sense — the theory can't be wrong, only
idle. If it fires zero times in 60 days of sessions, record that and
leave it running; it costs nothing.

## 8. Implementation plan

`theories/structural_arb/{THEORY.md,scan.py}` + tests with constructed
violation fixtures. Effort S. Natural home for a shared
"group siblings by event" helper that
[smile-smoothing](2026-08-24-smile-smoothing.md) will want —
build it theory-local first per the repo's promotion rule.

## 9. Testing approach

Unit tests: sibling grouping from ticker structure, monotonicity
detection, basket-sum arithmetic with fees, the exhaustiveness guard, the
per-leg buffer. Fixtures for each violation type and each non-violation
near-miss.

## 10. Open risks

- Ticker-structure parsing for strike ordering varies by series; parse
  defensively and skip unparseable ladders loudly.
- Multi-leg manual execution: by the time the user places leg 3, legs 1–2
  may have moved. Report basket trades with a "verify all legs before
  any" instruction, and prefer single-leg monotonicity trades in ranking.

## 11. Sources

- [Public PM/Kalshi arb bot](https://github.com/ImMike/polymarket-arbitrage) — evidence the hard-arb space is watched.
- [How prediction-market arbitrage works](https://www.trevorlasn.com/blog/how-prediction-market-polymarket-kalshi-arbitrage-works)
- [PredictionTalk 40-paper survey](https://predictiontalk.org/d/14-ai-parsed-40-papers-on-pm-inefficiencies-here-are-5-im-going-to-trade/) — rebalancing-arb magnitudes.
