---
title: Use current series fee metadata and explicit rounding assumptions
lane: maintenance
created: 2026-09-05
created_by: codex-insider-refresh-20260905
author_lane: theory
author_context: Live quote verification found the documented fee convention has changed.
status: open
---
The live fee check found that tools/sizing.py still describes one universal 0.07 rate and whole-cent order rounding. The current official July 7, 2026 schedule uses per-series maker/taker multipliers; the current API rounding guide distinguishes direct-member 0.0001-dollar balances from non-direct 0.01-dollar balances and order-level rounding rebates. Some series have zero taker fees. Existing historical returns must retain their declared fee assumptions rather than silently being recomputed under today's schedule.

Implement explicit fee assumptions with backward-compatible historical defaults, an auditable current-series lookup for live promotion/sizing, and account precision only when known. Persist the series fee receipt/effective time beside live quote receipts. Test a zero-fee series, general taker, different balance precisions, and missing metadata; no guessed account type. Do not broaden into execution simulation. Current negative research results used the stated general unrounded rate plus a conservative whole-cent sensitivity; this finding does not make them profitable.

Sources checked September 5, 2026: https://kalshi.com/docs/kalshi-fee-schedule.pdf ; https://docs.kalshi.com/getting_started/fee_rounding ; https://docs.kalshi.com/api-reference/market/get-series .
