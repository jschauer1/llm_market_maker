# no_side_premium — runbook

How to run this theory end to end. `THEORY.md` says *what* it claims —
a pre-registered out-of-sample test of the optimism tax's two cells; this says
*how a run happens*. Where prose and `theory.py` disagree, the code is
right and the prose is a bug.

Current version: **1**. Fully mechanical (`uses_llm_judgment = False`);
every row records `edge_basis='prior'` by design — nothing this theory
emits is a bet until eligible out-of-sample evidence measures the cells.
Valid tier A/B replay evidence would count in full, but the available
full-coverage runs motivated these pre-registered cells and therefore cannot
validate them.
Changing a cell boundary, a prior, or the reprice rule bumps the version.

## Stages

| # | stage | who decides | artifact |
|---|---|---|---|
| 1 | population screen | code | `theories.insider_bias.screen.screen()` (imported on purpose — the motivating backtests drew from exactly this screen) |
| 2 | cell assignment | code | `theory._cell` — cell A (mention-family NO favorite, ask ≥ 0.85) or cell B (non-mention YES favorite, ask in [0.80, 0.90]) |
| 3 | live reprice | code | `theory._reprice` — fresh asks; a row whose fresh ask leaves its cell is dropped, the cell never stretches |
| 4 | pricing + record | code | `theory.price` — cell A `screened` at +2.0 prior; cell B `rejected` at −3.9 prior (the avoid cell settles as a free control) |

There is no stage 2 judgment. "Run the theory" means all four stages —
the contract runs them as one call.

## Run

```python
from datetime import datetime, timezone

from tools import board as board_tool, db, registry
from tools.theory import TheoryContext

conn = db.connect(); db.init_db(conn)
ctx = TheoryContext.build(conn=conn, board=board_tool.get_board(conn),
                          now=datetime.now(timezone.utc), run_id="live")
result = registry.discover()["no_side_premium"].start(ctx).finish()
```

## Record

`finish()` writes every scored candidate: cell A rows `screened`, cell B
rows `rejected`. Both cells are measurements — do not endorse cell A rows
and do not treat cell B's `rejected` as stage-2 judgment (it is the
pre-registered avoid claim, recorded so settlements test it for free).
Both cells are also registered slices (`cell-a-no-favorite`,
`cell-b-yes-avoid`), so their evidence partitions automatically.

## Sub-theories

A **sub-theory** is a theory run over a *subset* of this theory's data:
same rows, narrower population, its own evidence, its own gates. It can
be strong while the parent is flat, so it is reported on its own terms.

This theory is *entirely* two sub-theories -- the cells are the claim:

| slug | claim | direction wanted |
|---|---|---|
| `cell-a-no-favorite` | mention-family NO favorites at ask >= 0.85 are underpriced (~+2.0 net) | positive |
| `cell-b-yes-avoid` | YES favorites at 0.80-0.90 elsewhere are overpriced (~-3.9 net) | **negative** -- it is an avoid list, and its candidates are never recommendable |

Cell B is the case where a good result looks like a bad number. A
negative record there *confirms* the claim; do not report it as a
failing segment.

```bash
python -m tools.cli slices report no_side_premium
python -m tools.cli score report no_side_premium --save
```

THEORY.md's own confirmation bars (cell A n>=40 and n_days>=8; cell B
calibration_edge_net < 0 at n>=60 and n_days>=8) are stricter than slice
readiness gates and still govern status and `edge_basis`. Slice
readiness affects ranking only.

## Report

The floor line must carry the funnel and the gate: `board_markets`,
`population`, `cell_a`, `cell_b`, `recorded_at_fresh_ask`, and
`reprice_moved_out_of_cell` from `ScreenResult.gate_removed`. A run with
both cells empty is "ran clean, 0 candidates" — say so; the ledger
cannot.

## Skip

Skip only when the ledger shows a live run today at the current version
(the go freshness check), or the session log says today's run found
nothing. The theory's own stricter confirmation bars (THEORY.md) govern
lifecycle decisions, not whether it runs.
