---
title: Validate weather forecasts after enough TWC-source history exists
lane: theory
theory: weather_model_gap
created: 2026-09-05
created_by: codex-weather-20260905
author_lane: new-theory
author_focus: weather_model_gap
author_context: WG-1 source census found a genuine settlement-source transition before any qualifying trade existed.
status: open
---

The baseline is implemented and its original source corpus is complete.
Current TWC-source evidence is unconfirmed: all three cities switched from NWS
on August 14, leaving only 18 comparable training dates per city in the first
campaign. The separately frozen NWS diagnostic then lost 5.61 net points over
297 positions, with all pooled 95% intervals below zero. No city passed support.

Do not repeat the stationary baseline or collect the same history again.
Proceed only with a justified forecast improvement or TWC-specific mechanism,
then freeze a new procedure and untouched validation dates before returns.
At least 30 same-source training labels per city are still required. Preserve
independent city evidence, multiplicity adjustments, actual settlement clocks,
rounded one-contract fees, and current execution checks. A source-equivalence
bridge requires its own evidence; station identity alone is insufficient.

Register a new campaign identity and bind its proof before enabling any
probability. Keep the original campaigns immutable and experimental NWS rows
excluded from production. Read the current theory/runbook and
[legacy result](../../backtests/wg1-nws-20260905/RESULTS.md) before designing it.
