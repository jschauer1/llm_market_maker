# No-Side Premium

## Hypothesis

Retail flow buys YES. At equal prices the affirmative side of a question
underperforms the negative side — an "optimism tax" paid by hope-driven
takers that nobody's hope pushes into NO. Where that flow concentrates,
NO favorites are underpriced and YES favorites overpriced, independent
of the price-level bias a calibration theory would capture.

Why it persists: the tax is a behavioral flow imbalance, not a
mispricing anyone can see on one market; and at favorite prices the
per-contract profit is small enough that pros don't queue to collect it.

Full design rationale: `docs/superpowers/specs/theories/
2026-08-24-theory-no-side-premium-design.md` (registry idea
`no-side-premium`); external evidence (Becker microstructure; Reichenbach
& Walther 2025) cited there.

## Evidence so far (why this is a forward test, not a bet)

Two full-coverage tier-A backtests measured the asymmetry:

- mention fullcov (`backtest-2026-08-25-mention-fullcov`, n=3,441): NO
  favorites at 0.90+ underpriced, **+2.25 net**, stable across
  partitions; YES favorites overpriced everywhere.
- insider fullcov non-mention (`backtest-2026-08-25-insider-fullcov`,
  n=3,181): YES favorites 0.80–0.90 **−3.89 net** (−5.80 in the
  gate-plausible slice); every NO band ≥ its YES counterpart below
  $0.90. But the mention cell did **not** replicate here (+1.04,
  p=0.09), and this population's best NO cell (0.65–0.80, +4.32) was
  negative on the mention population.

Band structure moves between populations; only the side-level direction
is consistent. Per the pairing discipline, the durable claim was
pre-registered (idea 14 revisit angle, 2026-08-26) and nothing is bet
until forward settlements measure it.

## Decision procedure (fully mechanical, v1)

Population: `theories.insider_bias.screen.screen()` — favorites
0.65–0.97, spread ≤ 0.07, volume ≥ 500, ≤ 14 days to close — the exact
screen both backtests drew from (imported, not copied; parameters
pinned by `tests/theories/test_no_side_premium.py`). Live runs refresh
every candidate's ask (batched quotes) and record the scan-time ask; a
row whose fresh ask leaves its cell is dropped, because the cell
definition is the pre-registration and does not stretch.

Two cells, disjoint by construction:

| cell | population slice | recorded as | claimed edge |
|---|---|---|---|
| A | mention-family series, NO favorite, no-ask ≥ 0.85 | `screened`, outcome=no | +2.0 net, `prior` |
| B | non-mention, YES favorite, yes-ask ∈ [0.80, 0.90] | `rejected`, outcome=yes | −3.9 net, `prior` |

Cell B is an avoid-list: rejected rows settle as a free control, which
is exactly what testing "these lose" needs. `edge_basis="prior"`
everywhere — **nothing this theory emits is a recommendable bet in v1**,
and any session reporting its output must say so.

Scoring separates the cells with no extra machinery: `disposition=
'screened'` scores cell A, `'rejected'` scores cell B
(`interpretation_value` is meaningless here and ignored — the
dispositions encode cells, not judgment).

## Stage 2 — none

No gate, no judgment, no prompts. Tier A by construction.

## Pre-registered outcomes (2026-08-26)

- **Cell A confirms** if its forward `calibration_edge_net` > 0 at
  n ≥ 40 settled (interim look; ~±4.7 pts SE) and stays positive at
  n ≈ 150 (~±2.4 pts, enough to resolve a +2 claim). On confirmation:
  version bump, `edge_basis` moves to `measured`, rows become
  recommendable.
- **Cell B confirms** (avoid validated) if its forward
  `calibration_edge_net` < 0 at n ≥ 60. On confirmation the tradeable
  mirror (NO at 0.10–0.20 against these favorites) becomes a *new*
  pre-registered cell — the mirror is not automatic, fees are paid both
  ways.
- **Kill cell A** if ≤ 0 at n ≥ 150. **Kill cell B's claim** if ≥ 0 at
  n ≥ 150. Both dead → propose retirement, record against idea 14 that
  the side effect did not survive out-of-population forward testing.

## How to backtest

The tier-A measurements above are the backtest; they are recorded in
`backtest_runs` and the idea registry. Nothing in the forward procedure
uses an LLM. Replaying the two cells over stored snapshots adds no
information beyond the fullcov runs (same window, same data) and is not
planned.

## Status

`testing` — 2026-08-26: forward test running; rows accrue each session.

## Version

1 — initial: the two pre-registered cells exactly as idea 14's revisit
angle states them; population pinned to insider_bias screen defaults;
live ask refresh before recording.
