# FLEET_LOG — what the supervisor did, and to whom

Append-only. Written by the `supervise` skill and by nothing else.

`RESEARCH_LOG.md` carries what the fleet *found*; this carries what the
fleet *was*. They are different questions and mixing them would bury
both — a supervisor's spawn/retire bookkeeping is noise to someone
reading for research continuity, and a research narrative is noise to a
supervisor rebuilding its roster after a context summarization.

That reconstruction is the reason this file exists rather than living in
the supervisor's head. `ListAgents` says which subagents are running
right now; only this file says which slot they occupy, which generation
they are, what their predecessor did, and what has already been
committed on their behalf.

## Format

One `##` section per supervisor session, dated. Inside it, one line per
event, newest last:

```
## 2026-09-01 — supervisor session <name>

- 18:47 armed heartbeat cron <job-id> at 7,27,47
- 18:47 baseline: 1 failing (test_every_repo_path_named_in_docs_resolves, peer-caused)
- 18:48 spawn  w1-g1 <agent-id>
- 18:48 spawn  w2-g1 <agent-id>
- 18:48 spawn  w3-g1 <agent-id>
- 19:07 heartbeat: 3/3 live, footprint moving, 0 orphans
- 19:31 w2-g1 completed — CONCLUSIVE (lane released, 4 ledger rows, ticket filed)
- 19:32 commit 3f9a11c "deadline_drift: ..." (7 paths, w2-g1) pushed
- 19:32 spawn  w2-g2 <agent-id>
- 19:47 heartbeat: 3/3 live, w1-g1 quiet 2 ticks (long replay — leaving)
- 20:14 w3-g1 completed — INCONCLUSIVE (lane still claimed) — sent back
- 21:02 wind down: 3 stopped, 2 lanes released, cron deleted
```

Slot and generation on every worker line, so a claim in `lane status` can
always be traced back to the spawn that made it.

Escalations, rulings and anything the user needs to act on go in the
terminal report and, when they concern research governance,
`RESEARCH_LOG.md`. This file is bookkeeping; it is not where a finding
goes to be found.

---
