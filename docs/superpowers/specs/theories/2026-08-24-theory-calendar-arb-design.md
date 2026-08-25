# Calendar Arbitrage — Theory Design Spec

Date: 2026-08-24
Status: backlog — not yet proposed as a theory
Registry slug: `calendar-arb` · Priority: 12 of 22 · Effort: S ·
LLM in decision path: no · Backtest tier: A

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "calendar-arb"` for status changes,
then formalize via the `propose-theory` skill.

## Assessment

**Applicability 3/5 · Implementability 4/5 · Likelihood of success 3/5 ·
Composite 10/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
calibrated probabilities)

- *Applicability 3:* like structural-arb, near-riskless when it fires
  and idle otherwise; two-leg execution is manual but pre-verifiable.
- *Implementability 4:* pure code; the only care point is verifying true
  nesting mechanically (same underlying, same threshold, same resolution
  source, strictly nested windows).
- *Likelihood 3:* the constraint is exact and nobody is assigned to
  cross-event consistency on Kalshi, but the firing rate net of fees is
  unknown — the same uncertainty structural-arb carries, on a wider
  surface (date ladders span *events*, which fewer participants compare).

## 1. Hypothesis

Within a series, the same threshold with a later deadline must be at
least as likely: P(X happens by June) ≤ P(X happens by July). Kalshi
lists these as *separate events*, priced by separate crowds, with no
cross-event margining — so date-monotonicity violations at executable
quotes are a hard-logic arbitrage no within-event scanner sees. Buy the
later-deadline YES and the earlier-deadline NO when the pair's combined
price locks a profit net of fees.

## 2. Evidence

The mechanism is the same one structural-arb exploits (uncoordinated
crowds, no consistency enforcement), one level up: sibling *strikes*
share an event page and get eyeballed together, while date siblings live
on different event pages and don't. The cross-event inconsistency
literature (Clinton & Huang through 2024; the within-Kalshi date-ladder
case) says nothing arbitrages across events. No direct measurement of
the firing rate exists — producing one from snapshot history is this
spec's first deliverable and costs little.

## 3. Non-goals and exclusions

- Strictly nested windows with identical thresholds and identical
  resolution mechanics only. "By June" vs "in June" (a window, not a
  cumulative deadline) is **not** nested — the classifier must read the
  window structure from rules text, and anything ambiguous is skipped
  loudly.
- Semantic implications between *different* propositions stay with
  [implication-graph](2026-08-24-theory-implication-graph-design.md);
  this spec's pairs must be verifiable by code alone.
- Soft relative value between date siblings (later trading only 1¢ above
  earlier, implying an absurd conditional hazard) is a v2 — v1 trades
  only hard violations.

## 4. Decision procedure

Fully mechanical.

- Group board markets by series; within a series, identify date-ladder
  families: same parsed threshold/subject, same resolution source,
  cumulative deadlines. Order by deadline.
- Violation: `ask(YES, later) + ask(NO, earlier) < 1 − fees − buffer`
  (start: 1¢ buffer per leg), both legs with top-of-book size.
  `edge_basis="model"` — arithmetic. Payoff check: if the event happens
  by the earlier deadline both legs can lose? No — verify the exact
  payoff matrix in code: earlier-YES ⇒ later-YES under nesting, so
  {earlier NO wins & later YES wins}, {both earlier-NO and later-NO win},
  and {earlier-YES & later-YES} are the only outcomes; the basket pays
  ≥ $1 in all three exactly when nesting holds — which is why nesting
  verification is the whole game.
- Report what the nesting classifier skipped, by reason, gate-style.

## 5. Data requirements

Board with rules text; snapshots for the historical firing-rate
measurement. Nothing external.

## 6. Backtest design

Tier A over snapshot history: replay boards, count executable violations
net of fees, and — the honesty constraint shared with structural-arb —
report *existence*, not fill certainty. Additionally settle historical
violation baskets from actual outcomes as an end-to-end audit of the
nesting classifier: any basket that would have lost is a classifier bug,
never bad luck.

## 7. Kill criteria

Zero executable firings across available snapshot history and 60 live
days → record and leave running (costs nothing), same posture as
structural-arb. A single settled basket loss → stop and fix the
classifier before any further trade; the theory's premise is that losses
are impossible under correct nesting.

## 8. Implementation plan

`theories/calendar_arb/{THEORY.md,nesting.py,scan.py}` + tests. Shares
the series-grouping idiom with structural-arb; build order between the
two is free. Effort S.

## 9. Testing approach

Unit tests: nesting classifier on real rules-text fixtures (true nesting,
window-vs-cumulative traps, source mismatches), payoff-matrix
verification, violation arithmetic with fees. The classifier's skip
report is tested, not incidental.

## 10. Open risks

- The by/in window trap is the whole risk concentrated in one place; the
  classifier must default to skip.
- Two-leg manual execution across *different event pages* is clumsier
  than within one ladder; quotes must be re-verified at placement, and
  the report should present both legs with explicit instructions.

## 11. Sources

Mechanism shared with
[structural-arb](2026-08-24-theory-structural-arb-design.md); cross-event
inconsistency context in
[Clinton & Huang 2025](https://ideas.repec.org/p/osf/socarx/d5yx2_v1.html).
