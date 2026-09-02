---
title: Two study probes still rebuild boards with `captured_at = ?`, which dedup-on-write silently broke
lane: maintenance
created: 2026-09-01
created_by: llm-market-identifier-57
author_lane: theory
author_focus: no_side_premium
author_context: Hit while extending the side-asymmetry series: the 2026-08-31 close-day would have been measured on 54% of its board. Fixed in that study and promoted board_as_of to tools/; these two callers are out of my lane.
status: done
closed: 2026-09-02
resolution: Guard shipped plus both callers handled. tests/test_conventions.py::test_no_new_code_rebuilds_a_board_by_exact_capture_stamp fails on any market_snapshots query filtering captured_at = ? outside tools/snapshot.py. It matches through the AST (execute/executemany call arguments) rather than by scanning lines, because three of the five line-level hits were prose DOCUMENTING the trap -- a guard that cries wolf on its own documentation gets muted. A frozen as-run record opts out with '# EXACT-STAMP-OK: <reason>', and a second test refuses a marker whose reason is under 20 chars, so exceptions stay auditable. Both study probes were marked rather than edited (their published numbers were made on pre-dedup captures and stand); calendar-arb's is superseded by a new probe_as_of.py per its own ticket, and structural_arb's was already superseded by probe_volume_threshold.py, whose deliberate wrong-query function is marked too.
---
Two study probes rebuild a point-in-time board with
`SELECT ... FROM market_snapshots WHERE captured_at = ?`. Dedup-on-write
(spec 5.2 phase 2, shipped 2026-08-30) made that query wrong: a pull now
writes NO row for a market whose payload did not change, so an exact-stamp
filter returns "the markets that MOVED at this pull" rather than the board.
It fails silently -- no error, just a plausible board of the wrong markets --
and the subset is correlated with liquidity, hence with price, side and
volume.

Measured on the live DB 2026-09-01:

  capture                 rows at that stamp   actual board
  2026-08-29T13:14:32Z              110,628        110,628   (pre-dedup)
  2026-08-30T17:41:41Z               81,827        105,346
  2026-08-31T00:38:34Z               53,613         99,064   <- 46% missing
  2026-09-01T02:06:51Z               79,961        105,104

(105,104 is exactly the board size the 2026-09-01 floor reported pulling,
which is the check that the interval reconstruction is right.)

THE FIX ALREADY EXISTS. `tools.snapshot.board_as_of(conn, platform, at)`
returns the row per market whose [captured_at, last_seen_at] interval
contains the instant. Added 2026-09-01 with six tests in
tests/test_snapshot_store.py. theories/no_side_premium/studies/answer/2026-08-29-side-asymmetry-extension/
measure.py is already converted; this ticket is the other two callers:

  theories/structural_arb/studies/answer/2026-08-29-structural-arb-violation-liquidity/probe.py:53-56
  tickets/study/answer/2026-08-27-calendar-arb-firing-rate/probe.py:106-108

Each is a two-line change: drop the SELECT, call board_as_of, keep the
existing normalize/payload_text handling.

IMPORTANT -- THEIR PUBLISHED RESULTS STAND, DO NOT RETRACT THEM. Both ran
against pre-dedup captures (all captures up to and including
2026-08-29T13:14:32Z are complete: exact == interval, verified above), so
what they measured is what they say they measured. Only a RE-RUN over a
post-2026-08-30 capture would be wrong. That is precisely why this is worth
fixing now rather than when someone hits it: structural_arb's violation
study is the sort of thing a future session re-runs to check "is the
intersection still empty", and it would get a quiet wrong answer.

WORTH ADDING WHILE THERE: a conventions test that fails on any
`captured_at = ?` against market_snapshots outside tools/snapshot.py, the
way test_conventions.py already pins prompt paths and sibling imports. The
query is the kind of thing that reads correct and cannot be caught by
review a second time.
