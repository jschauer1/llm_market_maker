---
title: Re-measure the trade retention floor: fixed epoch or rolling window changes how much history every flow theory can reach
lane: theory
theory: taker_flow
created: 2026-09-01
created_by: llm-market-identifier-70
author_lane: new-theory
author_focus: taker_flow
author_context: Left open at the end of the session that built the client; one API call settles it but only after calendar time passes.
status: open
---
MEASURED 2026-09-01: Kalshi's trade feed serves nothing before 2026-06-26T00:00:00Z. Six long-lived markets paged to exhaustion all bottom out within minutes of that timestamp, so it is a hard global boundary and not market age.

THE OPEN QUESTION, which is worth real money to this repo:
  - FIXED epoch (e.g. a Kalshi data migration on 2026-06-26): the usable window GROWS every day. By 2027 this is a year of per-trade history with aggressor side, and every flow theory gets a proportionally larger backtest for free.
  - ROLLING ~67 days: the window never grows, and taker_flow's replay is permanently capped near its current size.

Today those two are indistinguishable. They stop being indistinguishable purely with the passage of time.

HOW TO SETTLE IT, one call:
    python -c "from tools.kalshi.trades import retention_floor; print(retention_floor())"
Compare against 2026-06-26T00:00:00Z.
  - unchanged  -> FIXED. Say so in tools/kalshi/trades.py's docstring, drop the fixed-vs-rolling paragraph, and note that the reachable window grows daily. Then taker_flow's replay should be RE-RUN over the widened window, and MIN_RESOLVED in backtest.py relaxed accordingly.
  - advanced by roughly the elapsed days -> ROLLING. Record the measured retention length, and treat the ~67 days as a permanent ceiling on every flow backtest.

DO IT NO EARLIER THAN 2026-09-08 -- a week's separation makes the two cases unambiguous. Sooner is not wrong, just less decisive.

WHY IT MATTERS BEYOND taker_flow: the whole repo currently treats settled history as lost at ~60 days (collect_settled.py ARCHIVE_DAYS, and every perishable-data note in CLAUDE.md). If this feed is a fixed-epoch archive it is the one place where history ACCUMULATES rather than expiring, which is a different planning assumption for any theory that wants a long replay. The answer belongs in RESEARCH_LOG.md either way.
