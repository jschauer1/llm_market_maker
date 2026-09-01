# structural_arb — runbook

How to run this theory end to end. `THEORY.md` says *what* it claims —
sibling-strike monotonicity violations priced into riskless baskets;
this says *how a run happens*. Where prose and `scan.py`/`theory.py`
disagree, the code is right and the prose is a bug.

Current version: **4**. Fully mechanical (`uses_llm_judgment = False`),
tier A. Every find is riskless net of fees when recorded (`min_payout`
covers cost + fees), so scoring routes it to the riskless bucket and no
calibration claim is ever made. Changing a screen constant
(`MIN_LEG_VOLUME`, `MIN_FILLABLE_PROFIT_USD`, `MIN_ANNUALISED_RETURN`),
the mutually-exclusive guard, or the depth gate bumps the version.

## Stages

| # | stage | who decides | artifact |
|---|---|---|---|
| 1 | violation geometry | code | `scan.py` over the shared board |
| 2 | sterile-class screens | code | v3 constants: leg volume ≥ 100, annualised return ≥ 5%/yr past 30 days |
| 3 | mutually-exclusive guard | code | event envelope flag (free since 2026-08-29); `theory_facts` fallback for envelope-less snapshots |
| 4 | fresh-quote verification | code | live runs only — a violation that cannot be re-verified at fresh quotes is not recorded, full stop |
| 5 | depth gate + record | code | orderbook depth; fillable profit < $5 records as `rejected` (dust control group) |

No judgment stage. "Run the theory" means all five stages — the contract
runs them as one call. Backtests skip stage 4 by design (a replay prices
the snapshot; its output measures violation existence, not fillability).

## Run

```python
from datetime import datetime, timezone

from tools import board as board_tool, db, registry
from tools.theory import TheoryContext

conn = db.connect(); db.init_db(conn)
ctx = TheoryContext.build(conn=conn, board=board_tool.get_board(conn),
                          now=datetime.now(timezone.utc), run_id="live")
result = registry.discover()["structural_arb"].start(ctx).finish()
```

## Record

Finds record through `ledger.record_basket` via the contract — one
header plus legs, scored as a single joint payoff. Sub-$5 fillable finds
record `rejected`, never dropped. Execution risk across legs is
*reported* to the user, never modelled.

## Sub-theories

A **sub-theory** is a theory run over a *subset* of this theory's data --
a registered slice with its own evidence and its own gates, which may be
strong while the parent is flat.

**None registered**, and the shape of this theory argues against them:
every find is riskless net of fees, so it is scored on return in the
riskless bucket and makes no calibration claim at all. A slice
partitions a *calibration* record; there is none here to partition.

Check anyway when running, so a later registration is never missed:

```bash
python -m tools.cli slices report structural_arb
```

## Report

The floor line must carry the funnel with **removals by category** —
flag candidates found, removed as `not_mutually_exclusive`, removed by
sterile-class screens, evaporated at fresh quotes, rejected as dust —
and each surviving basket itemized with per-leg asks plus the
verify-every-leg warning. "Ran clean, 0 candidates" is the common
honest outcome (2026-08-30: 1,411 flag candidates, all removed); say it
in the log — the ledger cannot.

## Skip

Skip only when the ledger or the session log shows a live run today at
the current version (the go freshness check). A clean run writes no
rows, so the log line is the only record it happened.
