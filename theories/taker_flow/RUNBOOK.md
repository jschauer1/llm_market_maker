# taker_flow — runbook

How to run this theory end to end. `THEORY.md` says *what* it claims —
follow near-total one-sided aggressive flow; this says *how a run
happens*. Where prose and `theory.py` disagree, the code is right and the
prose is a bug.

Current version: **1**. Fully mechanical (`uses_llm_judgment = False`);
every row records `edge_basis='model'` from a measured base rate. Changing
a liquidity floor, the lookback, either imbalance threshold, or the
measured constants bumps the version.

## Stages

| # | stage | who decides | artifact |
|---|---|---|---|
| 1 | liquidity screen | code | `theory.is_liquid` — open, both asks, spread ≤ 0.05, vol24 ≥ 1000, OI ≥ 500, 1–45 days to close |
| 2 | flow window | code | `theory.flow_features` — trades in the trailing 7d, ≥ 20 of them |
| 3 | entry test | code | `theory.screen` — `\|imbalance\| > 0.6`, take the aggressor's side at that side's ask |
| 4 | pricing + record | code | `theory.price` — bucket's measured gross minus fees; all rows `screened` |

There is no stage 2 judgment. "Run the theory" means all four stages —
the contract runs them as one call.

**Cost note.** Stage 2 is one API call per liquid market (~1,768 on the
2026-09-01 board), so a run is a few minutes of paging. Stage 4 re-derives
the features for the handful that survived rather than carrying state
between stages, which costs one extra call per *candidate* and keeps the
`Theory` stateless.

## Run

```python
from datetime import datetime, timezone

from tools import board as board_tool, db, registry
from tools.theory import TheoryContext

conn = db.connect(); db.init_db(conn)
ctx = TheoryContext.build(conn=conn, board=board_tool.get_board(conn),
                          now=datetime.now(timezone.utc), run_id="live")
result = registry.discover()["taker_flow"].start(ctx).finish()
```

## Record

`finish()` writes every scored candidate as `screened`. Nothing here is
`endorsed`: the theory's aggregate is not demonstrated, and the only
positive population is a slice that has yet to earn out-of-sample
evidence. Every row carries `extra.flow_bucket`, which is what the slice
predicate matches on — a row without it cannot be routed and is a bug.

## Sub-theories

A **sub-theory** is a theory run over a *subset* of this theory's data:
same rows, narrower population, its own evidence, its own gates. It can be
strong while the parent is flat, so it is reported on its own terms.

| slug | claim | direction wanted |
|---|---|---|
| `extreme-imbalance` | `\|imbalance\| >= 0.9` (`extra.flow_bucket = 'extreme'`) beats its entry prices by ~+4.3 pts gross | positive |

**This slice is the whole live thesis.** The parent's complement
(`strong`, 0.6–0.9) measured −0.78 pts over 618 clusters and is expected
to stay flat; it is kept running as the control group that says whether
the tail is still the part that works.

The slice was **mined** from `backtest-2026-09-01-takerflow`, which is
declared in its `mined_from_run_ids`, so that run vouches for nothing. It
starts at n=0 out-of-sample and must clear ≥10 event clusters and ≥5
settlement days before it can drive a ranking.

## Report

Report the parent and the slice on separate lines, always — the parent's
aggregate is dominated by the flat `strong` population and reading one
number for this theory would bury the only claim it makes. State
explicitly that the slice is accruing and how far off its gates it is.

## Skip

Skip a run when the board is stale (the floor owns the refresh) or when
the trade feed is unreachable. Do **not** skip because the previous run
produced no candidates — an empty screen is a recorded observation about
the board, not a failure.
