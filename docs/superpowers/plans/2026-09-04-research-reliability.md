# Research Reliability Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development and test-driven-development. The user approved efficient parallel implementation.

**Goal:** Make evidence use and concurrent work reliable, then reduce agent setup and recovery work.

**Architecture:** Narrow shared primitives with existing consumers; theory-local decisions and replay remain local.

**Tech Stack:** Python 3.11, SQLite, pathlib, OS file locks, pytest, Markdown.

**Spec:** `docs/superpowers/specs/2026-09-04-research-reliability-design.md`

## Global Constraints

Valid A/B backtests count fully in production and can clear gates without live
settlements. Preserve historical evidence and all existing working-tree edits.
Use private fixtures; no live DB/schema/data mutations. No new dependencies or
generic replay/dispatch framework. Root owns git, shared documentation and integration.

## Task 1: Shared eligible evidence — Sol

Files: `tools/score.py`, `tools/slices.py`, optional narrow `tools/evidence.py`,
their tests and necessary private fixtures. Root owns CLI wiring if required.

- [x] Reproduce differences with A/B/C/NULL/unregistered replay and live fixtures.
- [x] Define and implement shared selection with explicit diagnostic access and exclusion counts.
- [x] Apply it to production score/bucket/slice consumers; retain context-specific mining exclusions.
- [x] Prove A/B-only history drives measured pricing and existing gates; preserve chains/experiments.
- [x] Run focused regressions and report the interface and any score refresh implications.

## Task 2: Collector ownership — Sol

Files: `tools/filelock.py`, `tools/atomic_write.py`, actual JSON collector callers
under `theories/deadline_drift/` and `theories/insider_bias/backfill_history.py`,
their tests. Do not change storage schemas or write capture data.

- [x] Inventory complete load/mutate/save transactions and reproduce competing writers.
- [x] Implement exclusive ownership with OS-released locks and unique atomic-write temporary paths.
- [x] Integrate real callers, preserving successful output and resumability.
- [x] Test contention, process death, exceptions, and unchanged destination on write failure.

## Task 3: Ticket transitions — Luna

Files: `tools/tickets.py`, `tests/test_tickets.py`; use the existing atomic-write API.

- [x] Reproduce rename-before-note and interrupted-close failures on private paths.
- [x] Make transitions retryable without duplicate notes or overwriting unrelated destinations.
- [x] Test note-write/move/unlink failures and successful retry; preserve existing citation guards.
- [x] Report focused tests; root closes completed maintenance tickets after review.

## Task 4: Persistent judgment batches — after Task 1

Files: narrow `tools/judgments.py`, `tools/theory.py`, tests, active judging runbook
and canonical skill examples (coordinate documentation ownership with root).

- [x] Specify a serializable receipt with run/theory/version/stage/batch and input identities.
- [x] Persist exact execution metadata and results; validate mismatches and safe retries.
- [x] Add a supported run method for completed batches without re-screening or changing ctx time.
- [x] Update actual live workflow and reuse in theory-local replay only where its interface fits.
- [x] Test save/load/resume, mismatched runs/payloads, duplicates, and provenance before opportunities.

## Task 5: Shared position facts — after Task 3

Files: `tools/positions.py` if warranted, `tools/ledger.py`, `tools/promotion.py`,
`tools/state.py`, relevant tests. Preserve query-specific display filters.

- [x] Reproduce basket settlement disagreement and retain supersession counterexamples.
- [x] Share settlement/supersession primitives across their real consumers.
- [x] Verify same results for singles and all basket legs, current/future versions, lanes, and sides.

## Task 6: Task-scoped instructions — root

Files: `AGENTS.md`, `docs/RESEARCH_GUIDE.md` and policy sections/map,
canonical `.agents/skills/`, `tools/agent_setup.py` only if generation requires it,
convention tests and README.

- [x] Map every guide section and existing rule marker to an owner and task triggers.
- [x] Keep a concise mandatory invariant contract; require relevant owned policy for each operation.
- [x] Preserve one authoritative text for each policy, with navigable full reference.
- [x] Validate rule coverage, discovery synchronization, and fresh-reader Codex/Claude scenarios.

## Integration

- [x] Review each task; resolve interface collisions before phase two.
- [x] Update toolkit/docs, close resolved tickets, and append a concise research-log entry.
- [x] Run the full offline suite and discovery check; review the whole pass independently.
- [x] Deliver results and concrete remaining limitations without changing live research data.

## Final verification

The complete offline suite passed: **1,565 passed, 4 network tests deselected**
(77.19 seconds). Discovery synchronization and whitespace checks passed.
Independent reviews resolved every finding and verified two-process, two-batch
judgment recovery, OS lock recovery, and full-weight A/B-only evidence.
Changes remain uncommitted on `codex/dual-agent-support`. Live research data,
historical tier metadata and saved score caches were not recomputed. Claude
Code is unavailable on this host; its shared discovery and workflow were
checked statically. Windows locking was exercised; Linux directory no-replace
support was inspected, and unsupported POSIX directory moves refuse safely.
