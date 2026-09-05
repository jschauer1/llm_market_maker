# Dual Agent Support Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for the independent tasks below. The user requested efficient delegation; reuse the audit agents for their corresponding implementations.

**Goal:** Support Codex and Claude Code through shared rules and truthful provenance.

**Architecture:** Compact shared bootstrap, one research guide, canonical skills with generated Claude entrypoints, and small runtime adapters. Existing Python research contracts remain provider-independent.

**Tech Stack:** Python 3.11+, pathlib, argparse, pytest, Markdown.

**Spec:** `docs/superpowers/specs/2026-09-04-dual-agent-support-design.md`

## Global Constraints

- No new dependencies, API credentials, live ledger migrations, or rewritten historical evidence.
- Preserve untracked user Codex files by comparing before replacing; known differences are provider substitutions.
- Native tools and available models are authoritative; never invent tool/model names or knowledge cutoffs.
- Root owns git and integration. Workers edit only their assigned files.
- Work on `codex/dual-agent-support` in the existing checkout to preserve the user's untracked integration work.

## Task 1: Shared instructions and discovery (root)

Files: `AGENTS.md`, `CLAUDE.md`, `docs/RESEARCH_GUIDE.md`,
`tools/agent_setup.py`, `tests/test_agent_setup.py`,
`tests/test_conventions.py`, generated `.claude/skills/`, `README.md`.

- [x] Add tests using a temporary repository with a canonical skill and supporting file. Check detects missing/stale wrappers without mutation; generation produces a wrapper containing the original metadata and an explicit root-relative source reference; an unchanged second generation writes nothing; unrelated local skills survive.
- [x] Run `python -m pytest tests/test_agent_setup.py -q` and observe failures before implementation.
- [x] Implement `sync(root: Path, *, check: bool = False) -> list[str]` and CLI `python -m tools.agent_setup [--check]`. No database connection. Validate sources before writes, preserve unrelated files, report changed paths.
- [x] Move the full shared policy to the guide, write a compact entrypoint, import it from Claude, and update convention consumers to inspect the actual shared source and both skill trees.
- [x] Generate wrappers after Task 2 and verify `python -m tools.agent_setup --check` exits zero.

## Task 2: Portable workflows (workflow agent)

Files: canonical `.agents/skills/`, `docs/agents/codex.md`,
`docs/agents/claude.md`.

- [x] Finish the read-only inventory of copies and provider assumptions.
- [x] Preserve research rules while making active instructions refer to AGENTS.md, canonical skill paths, and host-independent operations.
- [x] Put native tool examples, capacity handling, scheduler availability, and model/effort selection in the runtime adapters. Remove fictitious `.Codex` references and universal Claude-only lifecycle assumptions.
- [x] Preserve the three-worker fleet cap and useful worker-brief constraints. Link to canonical supporting resources.
- [x] Report changed paths and walk through Codex and Claude `go`/`supervise` scenarios without launching actual research.

## Task 3: Attribution and judgment entrypoints (runtime agent)

Files: `tools/cli.py`, `tools/theories.py`, `tools/ideas.py`,
`tools/provenance.py`, corresponding tests; live judgment RUNBOOK if needed.

- [x] Add failing tests for explicit Codex attribution, neutral defaults, and retirement denied to either provider. Keep explicit Claude calls compatible.
- [x] Update CLI choices/defaults/help and API defaults; preserve all stored historical values. Use actual provider/model identities in examples.
- [x] Check the judgment boundary for silently guessed effort/model data. Implement narrowly scoped fixes only when demonstrated by regression tests.
- [x] Apply the user's idealized-judge ruling: comparable-capability models following the same procedure share calibration without a mandatory experiment. Preserve historical provenance and independently verify replay cutoffs.
- [x] Run focused CLI, theory, ideas, provenance, and theory-contract tests.

## Integration and broader improvements (root)

- [x] Review each implementation against the spec and inspect the combined diff.
- [x] Run the complete offline suite and a separate agent review of fresh-session instructions and provenance.
- [x] Mark compatibility complete, then select and repair one evidenced operational reporting defect for the broader refactor request.
- [x] Re-run affected tests and full suite after fixes, append a concise research-log entry, and deliver files plus known runtime validation limits.


## Verified outcome

- Complete offline suite: **1,505 passed, 1 skipped, 4 deselected**.
- Generated discovery check and whitespace check: clean.
- Independent fresh-reader/code review: initial findings fixed; no remaining
  blocking findings in compatibility or the bounded queue fix.
- General improvement: queue supersession now matches promotion and uses one
  query for displayed rows and total. Five incident/counterexample regressions
  cover this behavior.
- Deferred evidence-eligibility work is recorded in
  `tickets/maintenance/completed/2026-09-04-apply-evidence-eligibility-consistently.md`
  (resolved by the following reliability pass).
- Claude Code is not installed locally; no end-to-end Claude launch was tested.
  Native fleet capacity remains a host capability, described in the adapters.
- Changes remain in the working tree on `codex/dual-agent-support`; no remote
  publication or live research database migration was performed.
