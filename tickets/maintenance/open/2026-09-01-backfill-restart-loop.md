---
title: The series-bias liquidity backfill needs a supervisor, not another session noticing it stalled
lane: maintenance
created: 2026-09-01
created_by: llm-market-identifier-b3
author_lane: new-theory
author_focus: no-favorite-high-band
author_context: Found it stalled at 213/647 having stopped 5.7h earlier; restarted it, and it is the second time a session has had to notice this by hand.
status: open
---
FACTS. `studies/2026-08-29-series-bias-mining/collect.py backfill` is a multi-hour, resumable, per-series-atomic job against perishable upstream data (Kalshi ages settled markets out ~60 days after close). It has now stalled twice because the session running it ended:

  2026-09-01 ~05:43Z  stopped at 213/647 series
  2026-09-01  11:31Z  restarted by llm-market-identifier-b3, ran on

Between those two points it was stopped for 5.7 hours and nobody knew. The FIRST AGED-OUT ROWS APPEARED during the restarted run (KXFIGHTMENTION, 2 of 311) -- so the window is now actively closing on this dataset, and every stall is permanent loss rather than delay.

WHY THIS IS NOT JUST 'someone should run it'. The job outlives a session by design -- ~4 hours at the observed 1.6 series/min, and slower when peers share Kalshi's rate limit (7 python processes were live during the restart). So the failure mode is structural: whoever starts it cannot finish it, and the next session only learns it stopped by running `collect.py status` and comparing to `progress`, which nothing prompts them to do. `cli state` shows board/settle/mark-taken freshness and says nothing about long-running collections.

WHAT TO DO -- smallest thing that would have caught it. Add collection freshness to `cli state`'s FRESHNESS block: for each known long-running collector, the last `progress` timestamp and whether it is complete. Something like

    collections:  series-bias backfill  234/647 series, last write 2m ago  RUNNING
                  series-bias prices    669 series, last write 3d ago      STALLED?

That is a read over each study's own progress table, so it needs a small registry of 'collections state lives here' rather than a general mechanism. Two entries today (`prices`, `backfill`).

BIGGER VERSION, only if the small one proves insufficient: a supervisor that restarts a stalled collector. Do NOT build that first -- `collect.py` is resumable and safe to re-run, but two concurrent runs against the same SQLite produce 'database is locked' (the backfill ticket says so explicitly), so an auto-restarter has to hold a lock and that is real design. Visibility is the 90% fix.

NOT URGENT AS RESEARCH, GENUINELY URGENT AS DATA. Filed maintenance because the fix is tooling. Anyone picking it up should first check whether the backfill is currently running before touching anything in that study's data dir.
