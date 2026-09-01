---
title: calendar-arb-firing-rate/probe.py reads boards by exact stamp, so re-running it now silently truncates
lane: maintenance
created: 2026-09-01
created_by: llm-market-identifier-af
author_lane: theory
author_focus: structural_arb
author_context: Found by grepping for the blast radius of the same defect in structural_arb's own study probe; not my lane to fix another study.
status: open
---
studies/2026-08-27-calendar-arb-firing-rate/probe.py:108 reads a board with WHERE platform='kalshi' AND captured_at=?. snapshot.board_as_of exists precisely because that stopped being the board on 2026-08-30, when dedup-on-write landed: a pull writes NO row for a market whose payload did not change, so an exact-stamp filter returns 'the markets that MOVED at that pull'.

THE PROBE WAS CORRECT WHEN IT RAN (2026-08-27, before dedup). The defect bites only on RE-RUNS, which is exactly what its Reproduce section invites.

MEASURED SIZE OF THE DISTORTION on the identical defect in structural_arb's probe, same 17 captures both ways:
  2026-08-27T11:47:05Z   exact:  3,254 markets   as_of: 107,656 markets
  2026-08-30T19:22:32Z   exact: 55,433 markets   as_of: 104,304 markets
  raw violations found   exact:     24 total     as_of:      36 total
A third of the findings were invisible. The subset is NOT random - markets that move are the liquid ones - so it is biased along the liquidity axis both studies measure.

WHY THIS ONE MATTERS PARTICULARLY. That study's conclusion (zero violations across 10 snapshots; near-dated ladders are same-event siblings priced at exactly 1.000) is what FALSIFIED calendar-arb's hard-arbitrage premise. And the open ticket 2026-09-01-calendar-arb-soft-relative-value points a future session straight back at it - 'the 295 near-dated same-event pairs already sitting at cost 1.000 as a ready-made dataset'. Whoever picks that up will re-run this probe against a truncated board and not be told.

WHAT TO DO. Route the read through snapshot.board_as_of(conn, 'kalshi', at) and payload_text, as studies/2026-08-29-structural-arb-violation-liquidity/probe_volume_threshold.py now does (it prints exact-stamp and reconstructed counts side by side so the distortion stays visible - worth copying). Re-run and state whether the 295-pair figure and the zero-violation result move.

DO NOT edit the original probe in place if its numbers are cited anywhere as-run; supersede it with a new file and leave the original as the record of what was actually measured on 2026-08-27. That is the pattern used for the structural_arb probe.

ALREADY CORRECT, as the counter-example: studies/2026-08-29-side-asymmetry-extension/measure.py:69 uses board_as_of and carries a comment naming this exact trap.
