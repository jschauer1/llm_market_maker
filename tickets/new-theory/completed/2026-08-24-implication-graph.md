---
title: Distinct events carry logical implications; when P(A) > P(B) at executable quotes but A implies B, B is cheap
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: done
closed: 2026-09-02
resolution: KILLED ON CLASS EVIDENCE, 2026-09-02, WITHOUT a direct measurement of implication edges -- and this resolution says so on purpose. This spec's trade is a CROSS-EVENT HARD-IDENTITY violation (section 4: ask(A_yes) + ask(B_no) < 1 - fees; section 3 excludes probabilistic relations outright as 'forecasts wearing a constraint's clothes'). That channel is no longer untested. TWO independent cross-event identities have now been measured at EXECUTABLE prices with real fees, and both are flat. (1) COMBO-VS-LEG, 2026-08-30, the first cross-event probe: Kalshi's 92 listed *COMBO markets are 2x2 partitions whose legs sit in separate events, so {DD,DR} is an EXACT synthetic of the standalone leg -- an identity that holds whatever the correlation, which is a strictly stronger test than product-of-legs. 34 exact riskless constructions: 1 profitable at zero buffer (+0.05 pts), 0 at a 1c/leg buffer. Mid-price gaps up to 6.4 pts exist but sit ENTIRELY INSIDE THE SPREAD, and the most liquid case (KXBALANCEPOWERCOMBO, 10.7M volume, 1c spread) has the SMALLEST gap. Study: studies/2026-08-30-parlay-markup/ (rule-0 section). (2) AGGREGATION-GAP, 2026-09-01, the second: KXNFLWINS lists 32 teams as 32 separate events, each a complete 1..17 ladder, so sum of E[wins] must equal 272-ties -- a conservation law ACROSS events, correlation-free like the synthetic. Mid sum 274.25 against a true <=272, but the bid/ask band is [264.03, 284.47] and straddles it; both riskless baskets fail at executable prices (all-NO costs 279.96 against a 272 floor). Evidence: tickets/new-theory/evidence/2026-09-01-aggregation-gap-probe/; that ticket was closed on its own the same day. Add the three WITHIN-event nulls -- calendar-arb (0 violations across 10 snapshots), smile-smoothing (97.6% of 959 rungs sat EXACTLY on their own isotonic fit, max deviation 1.5c), structural_arb's NO-basket path (exactly 1 of 6,414 mutually-exclusive events on a whole board, 0 tradeable) -- and the count is five independent measurements from five directions, every one flat once the spread is paid. Rule 0f is the mechanism: the gaps are real on the mid and gone at the ask. COST SIDE, which is why this is a close and not a warning: Effort L, composite 7/15 (second-lowest in the backlog), and its own assessment calls it 'the highest process overhead per candidate in the backlog' -- an LLM construction stage, hand verification of EVERY edge, and a rule-text-hashed edge store, all spent BEFORE a single quote is checked. WHAT IS NOT ESTABLISHED, stated plainly: nobody has measured dispersion on implication edges specifically. The two probes measured different identities (a partition synthetic, a conservation law), not 'X wins the general implies X wins the primary'. This is a close on the class, not on the population, and it is recorded that way so a future session can weigh it rather than inherit it. WHAT WOULD REOPEN IT: rule 0's cheap check, which this spec never had -- a ONE-BOARD measurement of the dispersion the thesis needs (hand-build ~20 implication edges from rules text, price both legs at executable quotes, count violations past a 1c/leg buffer) run BEFORE any scaffolding. That is an afternoon, not an Effort-L build; if it fires, reopen with the count. STILL OPEN and deliberately not covered here, per README rule 0: cross-event relative value where NO arbitrage identity exists -- a forecast disagreement between two separately-priced events. That is a different and much weaker claim than this spec makes and needs its own pre-registration. MATCHING TRAP inherited by any successor: KS/NH/OH list governor and senate contests from DIFFERENT election cycles under adjacent tickers (GOVPARTYKS-27-D beside SENATEKS-26-D); matching legs by ticker year-suffix pairs the wrong election and produces a confident, wrong arbitrage. Match on close_time.
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
