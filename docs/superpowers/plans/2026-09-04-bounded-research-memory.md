# Bounded Research Memory Implementation Plan

> **For agentic workers:** Use the scoped assignments below; preserve existing
> uncommitted work. User selected implementation with subagents in this session.

**Goal:** Make saved knowledge retrievable through bounded summaries.

**Architecture:** Markdown maps select scoped lesson cards; cards link to
original evidence. Instructions define one writing/reading contract shared by
Codex and Claude.

**Tech Stack:** Markdown, existing agent entrypoints and validation commands.

**Spec:** [Approved scope](../specs/2026-09-04-bounded-research-memory-design.md).

## Constraints

Context/documents only. Preserve sources and paid data. No changes to trading,
evidence math, lifecycle, scheduling, or production Python. Card/menu limits and
source fidelity follow the spec. No unrelated commit or cleanup.

## Tasks

- [x] Baseline: simulate expert startup and routine close-out under existing
  instructions; identify compulsory historical reading and redundant logging.
- [x] Root: write `docs/agents/research-memory.md`, root/topic navigation,
  templates, and update canonical skills and guide references.
- [x] Theory curator: distill scoped cards and maps for all seven existing
  theory folders, retaining original notes and specifications. Stop at two
  cards per current theory and one per retired theory; use targeted source
  reads under the spec's migration allowance. Unindexed history is acceptable.
- [x] Shared curator: organize ownerless study results by execution/evidence
  questions, with at most four shared lesson cards; directly link short study
  answers instead of rewriting them.
- [x] Root: preserve the old log verbatim in `knowledge/archive/`, write its
  retrieval map, and replace `RESEARCH_LOG.md` with bounded current narrative.
- [x] Verify: link targets and budget counts; original-log hash; existing
  policy/discovery/convention tests; fresh-agent retrieval and writing scenarios.

## Validation record

Baseline reviewer found an insider expert was directed to read 26,286 words of
theory/runbook/notebook, including the 16,026-word notebook. Routine maintenance
was required to append a global diary despite the existing cross-session bar.
The user then explicitly preferred bounded, selective migration over
exhaustive preservation in active memory; curator assignments were capped.

Final utility review removed two cards: a duplicated shared lesson and an
arithmetic recap tied to mutable ticket status. It corrected a cross-corpus
claim and two overstatements. Final inventory: 13 maps (1,788 words), 14 cards
(1,853 words), and a 152-word active log. Seven notebooks and four old Learnings
sections moved to owner archives, removing 64,216 words from active files.
Thirty-seven research source documents received a useful navigation route;
study/result evidence and current theory procedures were preserved.

`python -m pytest tests/test_research_memory.py tests/test_policy_map.py
tests/test_agent_setup.py tests/test_conventions.py tests/test_db_discipline.py
-q`: **54 passed**. Permanent checks cover budgets, required card fields,
navigation targets, and archive-aware historical citation resolution.
`python -m tools.agent_setup --check`: clean. A separate mechanical check
verified every new map/card link and heading anchor, source-body hashes, and
the original log's exact SHA-256:
`812e1e03abdb58b87a2febf6d0dd0288d8a52bb7ef5d49074cb9c3ddbd0a2882`.

A fresh-agent scenario located the subset rule through summaries, declined
routine diary output, and preserved scope in an unconfirmed hypothetical
finding. Its selected instruction/navigation/source reading was 2,737 words;
this measures that scenario, not every research session's full context.
