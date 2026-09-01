---
title: Distinct events carry logical implications; when P(A) > P(B) at executable quotes but A implies B, B is cheap
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: open
---
Effort: L · LLM in decision path: construction time only (per-trade mechanical) · Backtest tier: B for the whole procedure (see section 6)

**This ticket is the spec.** Before starting, run
`python -m tools.cli ideas search "implication-graph"` in case the status
moved, and read [the backlog's shared contracts](../README.md)
first — rules 0 through 0e there have killed more ideas in this
repo than any single spec's own kill criteria have.

## Assessment

**Applicability 2/5 · Implementability 2/5 · Likelihood of success 3/5 ·
Composite 7/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 2:* the edge inventory is small and cycle-dependent;
  most sessions the graph produces nothing.
- *Implementability 2:* LLM construction, hand verification of every
  edge, provenance obligations, and store maintenance — the highest
  process overhead per candidate in the backlog.
- *Likelihood 3:* conditional on a correctly verified edge, a violation
  trade is near-arbitrage; the risk is concentrated in graph construction
  errors, which the strict kill rule (two outcome-violations kill the
  graph version) bounds but does not eliminate.

## 1. Hypothesis

Beyond same-event ladders, distinct events carry logical relations:
"candidate X wins the general" implies "X wins their primary"; "person Y
confirmed by date D1" implies "confirmed by D2 > D1" across series. When
P(A) > P(B) at executable quotes but A ⇒ B, the pair is mispriced and B
is cheap (or A is rich).

## 2. Evidence

Nothing arbitrages across Kalshi events — the flows are separate crowds.
Cross-event inconsistencies documented during the 2024 election cycle
persisted for days (Clinton & Huang document cross-*exchange* divergence
through the same period; the within-exchange cross-event version has the
same no-one-is-assigned-to-this structure). The constraint, once stated,
is as hard as a ladder monotonicity violation.

## 3. Non-goals and exclusions

- Only strict logical implication from resolution rules — never
  probabilistic/correlational relations ("if X then probably Y"), which
  are forecasts wearing a constraint's clothes.
- Within-event constraints belong to
  [structural-arb](../completed/2026-08-24-structural-arb.md).
- No edge goes live un-verified: every LLM-proposed edge is confirmed by
  the session reading both rule texts before it enters the store.

## 4. Decision procedure

Hybrid, with judgment quarantined at construction time:

- An LLM stage proposes implication edges over the board's event titles
  and rules (batched; strong model; prompt in
  `theories/implication_graph/prompts/`; provenance recorded per stage).
- **Session verification:** each proposed edge is confirmed by reading
  both rule texts — a wrong implication is this theory's poison, and the
  graph is small enough to review by hand. Confirmed edges are stored as
  static facts with the confirming evidence (the pair-store pattern from
  [cross-venue-fair-value](2026-08-24-cross-venue-fair-value.md)).
- Per-trade decisions are mechanical: scan confirmed edges for
  `ask(A_yes) + ask(B_no) < 1 − fees`-type violations.
  `edge_basis="model"`.

## 5. Data requirements

In-repo: board with rules text, snapshots for backtest replay, the edge
store (SQLite, with confirmation evidence and rule-text hashes so a rules
change invalidates an edge).

## 6. Backtest design

The mechanical scan replayed over snapshots is tier A *given the graph*;
the graph itself is judgment, so the overall evidence is tier B, stated
plainly in THEORY.md. A subtlety worth writing down: the graph's
constraints are timeless logic, not forecasts, so contamination risk is
lower than tier-C judgment — but the label still must not claim A.

## 7. Kill criteria

Any settled pair where the "implication" was violated *by the outcomes*
means the edge was wrong, not mispriced — audit graph construction before
continuing; two such events kill the graph version.

## 8. Implementation plan

`theories/implication_graph/{THEORY.md,graph.py,scan.py,prompts/}` +
tests. Build after structural-arb, whose scan logic it generalizes.
Effort L.

## 9. Testing approach

Unit tests: violation arithmetic on fixture edges, rule-text-hash
invalidation, provenance-recording enforcement (recording refuses without
it once `uses_llm_judgment` is declared). Construction-stage prompt
changes bump the version like any procedure change.

## 10. Open risks

- The graph goes stale as events close and new ones list; edge inventory
  is small and maintenance is manual. Batch re-construction runs
  per-cycle (e.g., election season) rather than per-session.
- Subtle rules asymmetries (different resolution sources for A and B) can
  make a true logical implication fail operationally — the verification
  step must check *resolution mechanics*, not just semantics.

## 11. Sources

- [Clinton & Huang 2025](https://ideas.repec.org/p/osf/socarx/d5yx2_v1.html) — persistent cross-market inconsistency through the 2024 cycle.
