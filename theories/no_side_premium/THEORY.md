# No-Side Premium

<!-- research-memory-route -->
> [Find scoped lessons and avoided mistakes](learnings/README.md). Read this specification
> for the claim/procedure relevant to your task; historical learning narratives
> are source evidence, not an accumulating current-memory summary.
<!-- /research-memory-route -->


## Hypothesis

Retail flow buys YES. At equal prices the affirmative side of a question
underperforms the negative side — an "optimism tax" paid by hope-driven
takers that nobody's hope pushes into NO. Where that flow concentrates,
NO favorites are underpriced and YES favorites overpriced, independent
of the price-level bias a calibration theory would capture.

Why it persists: the tax is a behavioral flow imbalance, not a
mispricing anyone can see on one market; and at favorite prices the
per-contract profit is small enough that pros don't queue to collect it.

Full design rationale: `git show 6e7d920:tickets/new-theory/completed/2026-08-24-no-side-premium.md` (registry idea
`no-side-premium`); external evidence (Becker microstructure; Reichenbach
& Walther 2025) cited there.

## Founding evidence (why the discovery runs are not bets)

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
pre-registered (idea 14 revisit angle, 2026-08-26), so the runs that
suggested the cells cannot validate them. Eligible out-of-sample tier A/B
replays would count in full; forward settlements are the evidence source
currently available to this theory.

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

- **Cell A confirms** if its eligible out-of-sample
  `calibration_edge_net` > 0 at
  n ≥ 40 settled (interim look; ~±4.7 pts SE) and stays positive at
  n ≈ 150 (~±2.4 pts, enough to resolve a +2 claim). On confirmation:
  version bump, `edge_basis` moves to `measured`, rows become
  recommendable.
- **Cell B confirms** (avoid validated) if its eligible out-of-sample
  `calibration_edge_net` < 0 at n ≥ 60. On confirmation the tradeable
  mirror (NO at 0.10–0.20 against these favorites) becomes a *new*
  pre-registered cell — the mirror is not automatic, fees are paid both
  ways.
- **Kill cell A** if ≤ 0 at n ≥ 150. **Kill cell B's claim** if ≥ 0 at
  n ≥ 150. Both dead → propose retirement, record against idea 14 that
  the side effect did not survive out-of-sample testing.

### Amendment, 2026-08-27 — every bar above also requires `n_days ≥ 8`

Rows are not independent draws. The settlement-day clustering study
(`tickets/study/answer/2026-08-27-settlement-day-clustering/`) measured this screen's
whole population over three consecutive close-days and found the
day-level favorite edge swinging +4.26 / −7.29 / +5.40 net, with the
YES/NO split *reversing* between days (08-25: YES −1.42, NO +7.98;
08-27: YES +12.15, NO −3.05). This theory measures exactly that split,
so a row-counted sample spanning three settlement days cannot resolve a
2-point side effect however many rows it holds.

So each bar above now reads "**and** `n_days ≥ 8`", where `n_days` comes
from `score.settlement_day_clusters()`, and the interim look additionally
requires the day-clustered SE to be reported alongside the point estimate.

This is a post-hoc amendment to a pre-registration, which is normally
exactly the wrong thing to do. Why it is admissible here: it was derived
from a **control population** (215 markets, whole screen, none selected
on outcome), not from this theory's own rows; and it makes confirmation
strictly **harder** in both directions — no bar was loosened. It does not
bump the version because the decision procedure — population, cells,
sides, price bands, recording — is untouched; only the evidentiary bar
for reading the results moved.

**Worked example of why it was needed:** cell B's first 12 settlements
came in 12/12 (+14.59 net), which read naively falsifies its −3.9 claim.
All 12 settled on 2026-08-27, a day on which **all 55** YES favorites in
the population won. Cell B did not beat that day; it was a subset of it.
Under the amended bar that sample is `n_days=1` — one draw, no computable
SE, no reading either way. See `NOTES.md` 2026-08-27.

## Slices (2026-08-29)

Both cells are **registered slices** (`cell-a-no-favorite`,
`cell-b-yes-avoid`; `cli slices report no_side_premium`), backdated to
the 2026-08-26 pre-registration above. The slice machinery supplies the
out-of-sample bookkeeping and current segment scores; the motivating
full-coverage evidence lives in sibling theories' ledgers and does not
validate these registrations. The bars in "Pre-registered outcomes" remain
the confirmation criteria — generic slice readiness (10 clusters / 5 days)
only gates how ranking reads a cell, and cell B is an avoid-list whose
confirming direction is negative. Registration changed no procedure; no
version bump.

## How to backtest

The tier-A measurements above are the backtest; they are recorded in
`backtest_runs` and the idea registry. Nothing in the forward procedure
uses an LLM. Replaying the two cells over stored snapshots adds no
information beyond the fullcov runs (same window, same data) and is not
planned.

## Status

`testing`, v1. The theory remains a measurement, not a source of bets:
both cells still record `edge_basis='prior'`, so neither becomes
recommendable merely because the generic slice-readiness gate is clear.

Read the two registered cells separately:

- `cell-a-no-favorite` is the only positive trade claim. It stays
  unconfirmed and non-recommendable until its own row and settlement-day
  confirmation bars are met.
- `cell-b-yes-avoid` is a negative control, never a recommendation. A
  negative record confirms the avoid claim; a nonnegative record kills it
  only when both its row and settlement-day requirements are met. Keep
  reporting the cell independently either way.
- The parent aggregate mixes a positive claim with a negative control and is
  not a decision statistic.

Use `python -m tools.cli slices report no_side_premium` for the current
cell records and `python -m tools.cli score report no_side_premium` for
the aggregate and disposition views. Eligible tier A/B replay evidence would
count in full, but the two historical full-coverage runs motivated these
cells and cannot validate the same pre-registration.

The dated measurements and changes in interpretation are preserved in the
[historical notebook](theories/no_side_premium/notes/archive/NOTES.md),
especially the 2026-09-01 entries, and in the linked studies under
`theories/no_side_premium/studies/answer/`. Those sources
explain the day-clustering amendment, the failed paired estimator,
composition controls, and the early-close exposure check; they are evidence,
not current status.

## Version

**1** — initial: the two pre-registered cells exactly as idea 14's revisit
angle states them; population pinned to the insider screen defaults; live ask
refresh before recording. The later day-clustering and interpretation
corrections changed how evidence is read, not the population, cell boundaries,
side, price bands, or recording procedure, so the version remains 1.
