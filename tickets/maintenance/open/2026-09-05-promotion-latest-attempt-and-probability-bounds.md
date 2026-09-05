---
title: Fix mixed-attempt re-quoting and impossible bucket probabilities
lane: maintenance
created: 2026-09-05
created_by: codex-insider-refresh-20260905
author_lane: theory
author_focus: insider_judgment
status: open
---
Live run insider-refresh-20260905T054912Z exposed two arithmetic blockers before any bet was reported. Opportunity 110002 retains first entry 0.86 but its latest attempt entered at 0.81, with model probability 0.828397 and net edge 0.76244. promote re-quotes the latest net edge against the first entry and invents an additional five points (5.52794 at an unchanged 0.81 ask). Read a coherent latest decision attempt for current quote adjustment; preserve first-position cost and historical attempts.

Edge.from_bucket also adds a measured gross edge without bounding probability: opportunity 113409 has q=1.001919; 110004 has q=1.011919. New bucket outputs must stay within [0,1] with net/gross consistent. Existing impossible records must be explicitly identified during promotion, not silently recommended. Watch regression tests fail before fixes; test repeated cheaper and dearer entries, prior paths, and extreme measured buckets. Preserve raw run receipts and version history. Resolve before publishing this run's candidate list.

The follow-up audit found the same mixed-attempt problem in pooled scoring:
first entry can be combined with later edge/confidence. Select the earliest
confidence-bearing attempt for a judgment theory (otherwise earliest
attempt), keeping one outcome per observation. Named-disposition queries
must select a coherent matching attempt inside the requested run. Preserve
original attempts and document the policy change; recompute bucket and
segment scores before relying on the run's evidence.
