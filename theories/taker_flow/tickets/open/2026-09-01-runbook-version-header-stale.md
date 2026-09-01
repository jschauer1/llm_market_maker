---
title: RUNBOOK says 'Current version: 1' while the registry is at v2
lane: theory
theory: taker_flow
created: 2026-09-01
created_by: llm-market-identifier-c0
author_lane: floor
author_context: Found while running taker_flow per its RUNBOOK during the 2026-09-01 second floor.
status: open
---
theories/taker_flow/RUNBOOK.md line 'Current version: **1**' is stale. The registry row is version 2 (`cli theories list`), `cli state` renders [chain 2], and the runbook's own Sub-theories section describes the v2 `extreme-imbalance` slice registered 2026-09-01T12:05:39Z. So the header contradicts the rest of its own file.

WHY IT IS MORE THAN A TYPO. The runbook header is what a theory expert reads to know which version to record. taker_flow does not declare uses_llm_judgment, so nothing refuses a mis-versioned row -- a session following the header would record provenance and scores at v1 and silently split the track record across two versions, which is exactly the silent merge the versioning rule exists to prevent. It is cheap to get wrong and invisible afterwards.

FIX: update the header to 2 and add the v2 note (what changed: the measured constants plus the extreme-imbalance registration). Check the same header on the other runbooks while there -- insider_judgment's is current at v6, no_side_premium's at v1, structural_arb's at v4, all correct as of today, so this is the only one adrift.

NOT FIXED HERE because the floor lane does not edit theory procedure docs.
