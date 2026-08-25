# implication-graph — logical constraints between non-sibling markets

**Priority:** 12 of 12 · **Effort:** L · **LLM in decision path:**
construction time only (per-trade decisions mechanical) · **Backtest tier:**
B-ish (see below)

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search
> "implication-graph"` for status changes since this was written. Formalize
> via the `propose-theory` skill before writing procedure code. Provenance
> obligations apply — this is the only spec in the backlog with an LLM
> anywhere near the procedure.

## Thesis

Beyond same-event ladders, distinct events carry logical relations:
"candidate X wins the general" implies "X wins their primary"; "party P wins
the presidency" relates to state-level markets; "person Y is confirmed by
date D1" implies "confirmed by D2 > D1" across *series*. When P(A) > P(B) at
executable quotes but A ⇒ B, the pair is mispriced and B is cheap (or A is
rich).

## Why the edge should exist

Nothing arbitrages across Kalshi events — the flows are separate crowds.
Cross-event inconsistencies documented during the 2024 election cycle
persisted for days. The constraint, once stated, is as hard as a ladder
monotonicity violation.

## Procedure

Hybrid, with judgment quarantined at construction time:

- An LLM stage proposes implication edges over the board's event titles and
  rules (batched; strong model; prompt on disk; provenance recorded). Every
  proposed edge is then **verified by the session** reading both rule texts
  — a wrong implication is this theory's poison, and the graph is small
  enough to review by hand. Confirmed edges are stored as static facts with
  the confirming evidence, like
  [cross-venue-fair-value](cross-venue-fair-value.md)'s pair store.
- Per-trade decisions are then mechanical: scan confirmed edges for
  `ask(A_yes) + ask(B_no) < 1 − fees`-type violations. `edge_basis="model"`.

## Backtest

The mechanical scan replayed over snapshots is tier A *given the graph*; the
graph itself is judgment, so treat overall evidence as tier B and be
explicit in THEORY.md that the tier attaches to the whole procedure. (A
subtlety worth writing down: the graph is built once and its constraints are
timeless logic, not forecasts, so contamination risk is lower than for
tier-C judgment — but the tier label should still not claim A.)

## Kill criteria

Any settled pair where the "implication" was violated *by the outcomes*
means the edge was wrong, not mispriced — audit the graph construction
before continuing; two such events kill the graph version.

## Build notes

`theories/implication_graph/{THEORY.md,graph.py,scan.py,prompts/}`. Effort
L. Build after [structural-arb](structural-arb.md), whose scan logic it
generalizes.

## Sources

Mechanism-based; the 2024 election-cycle cross-event inconsistencies are the
motivating anecdote, and structural-arb's evidence base covers the
within-event version of the same phenomenon.
