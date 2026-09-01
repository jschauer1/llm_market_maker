---
title: Backfill titles and rules_primary into extra_json from the stored judging payloads
lane: theory
theory: insider_judgment
created: 2026-09-01
created_by: llm-market-identifier-d8
author_lane: theory
author_focus: insider_judgment
author_context: Found while trying to answer single-name-structural-gate: the analysis needed titles, 78% of the evidence had none stored, and the stored judging payloads turn out to carry them.
status: open
---
WHAT IS MISSING. Only 381 of 1,770 bucketed settled rows (21.5%) have a title reachable from `market_snapshots`, and they are the LIVE ones. The backtest rows -- which carry this theory's actual evidence, 3,279 of 3,485 settled observations -- came through the replay and were never snapshotted, so they have a ticker and nothing readable.

`backtest_judged.py` HAD the title and dropped it. It writes `title` and `rules_primary` into every judging payload it builds, uses them, and persists neither into the opportunity's `extra_json`. This is the same defect found in `calibration_harvest/collect.py` the same day (it computed volume-at-entry and spread-at-entry to apply its liquidity floor and discarded both). Worth stating as a pattern: **a stage that receives a field, uses it, and drops it is the repo's most common data loss**, and it is invisible until someone needs the field months later.

IT IS RECOVERABLE, AND CHEAPLY. The judging payloads are on disk:

    theories/insider_bias/insider_judgment/backtests/*/batch_*.payload.json

Each is a list of events carrying `event_ticker`, `series_ticker`, event `title`, `close_time`, and a `markets` list with per-market `ticker`, `title` and `rules_primary`. An index built from all of them covers **2,571 of 4,275 opportunities (60.1%)**, against 381 (21.5%) from snapshots. Combined coverage is higher still. No re-judging, no model spend, no network.

WHAT TO DO.
 1. Build the index from the payload glob, keyed on market ticker.
 2. Write `title` and `rules_primary` into each matching attempt's `extra_json` as NEW keys. Do not overwrite anything -- this is enrichment, not the relabelling the calibration_harvest recovery ticket agonised over, so the audit-trail objection does not apply.
 3. Also fix the source: have `backtest_judged.py` (and the live recording path, if it does not already) persist `title` and `rules_primary` going forward, so no future replay needs a backfill. Not a version bump -- nothing about which rows exist or what edge is computed changes; precedent is calibration_harvest v2 adding the cell key to extra_json and recording it as not a decision change.
 4. Pin with a test that a recorded backtest row carries a title.

WHY IT IS WORTH A SESSION. Three separate open questions all need text and are currently blocked on this:
  - the single-name / broad-based split (closed unconfirmed today partly for want of titles);
  - mining the 362 stage-6 rejection rationales for a mechanizable predicate, which is the live successor to did-stage-6-add-value;
  - `fine-print-divergence` (new-theory backlog) is entirely about `rules_secondary` narrowing what a title promises, and this theory's corpus would be its natural first test set.

DO NOT let it become a re-judging exercise. The point is that the text already exists on disk and only needs indexing.
