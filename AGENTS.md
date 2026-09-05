# Market Edge Finder

This repository supports Codex and Claude Code. Both runtimes use the same
research rules, tools, database, and evidence standards.

## Read before working

1. Read `docs/agents/policy-map.md` and load the complete guide sections it
   assigns to your current task. `docs/RESEARCH_GUIDE.md` remains the single
   authoritative research policy. A section includes its subsections; read
   through the next `##` heading. Route by the action the user requested, not
   every research noun mentioned in supplied context. Use the bounded profile
   when one fits; use the action matrix when doing more. Read selected sections
   one at a time, continue from a truncation point instead of restarting, and
   load additional sections before widening the task. Read the whole guide only
   when the scope genuinely cannot be mapped.
2. Read the adapter for the application running this session:
   - Codex: `docs/agents/codex.md`.
   - Claude Code: `docs/agents/claude.md`.
   Use the session's actual tool inventory when examples differ. The
   application and the model are separate identities; never infer either
   from a copied prompt or an old ledger row.
3. Invoke the relevant skill from `.agents/skills/`. That directory holds
   the complete shared procedures. `.claude/skills/` contains generated
   discovery entrypoints which direct Claude to the same procedures.
4. For research or saving findings, start at `knowledge/README.md` and follow
   the relevant summary branch. Read `docs/agents/research-memory.md` before
   writing research context. Whole notebooks and historical logs are retrieved
   by question, never loaded as startup context.

User instructions define the task. An explicit coding request is not an
autonomous `go` session: do the requested work without starting the floor
or claiming a research lane merely because one is due. `go` and `supervise`
use their own session procedures when requested.

## Universal invariants

These are the startup constraints; their definitions and exceptions live in
the mapped guide sections and task skills.

- The user places every bet manually and alone authorizes theory retirement.
- A recommendation resolves to a Kalshi ticker. Interpretive screens require
  research before recommendation; mechanical or measured edges follow their
  own evidence and promotion gates.
- Judgment classifies; measurement quantifies. Never invent a probability,
  model identity, knowledge cutoff, or execution setting.
- Valid tier A/B backtests count fully toward production probabilities,
  calibration, and ranking, alongside live outcomes. They can satisfy the
  evidence gates without a live track record. No live-only waiting period or
  additional discount. Contaminated or undocumented replays do not qualify.
- Preserve rejected controls and first-class sub-theories. A version bump
  defaults to `continues`; do not discard earlier evidence without an explicit
  reason it no longer applies. Under the user's idealized-judge assumption,
  models following the same procedure share calibration; aim for comparable
  intelligence and record the actual model. A provider/model switch alone
  requires no experiment, evidence reset, or version bump. See provenance policy.
- Preserve paid judgments and perishable source data. Persist work in batches
  and use shared APIs for the ledger, board, scoring, and governance.
- Share one board per research session. Respect peer edits, ownership, and
  actual host concurrency. During supervision, reserve one advertised global
  slot for required worker-created judgment and count every external or nested
  active agent the native inventory exposes. No invented native tools or
  hidden extra workers.
- Keep theories self-contained, with shared helpers elevated only for real
  callers. Read the architecture policy before changing these boundaries.

## Working here

- Run `python -m tools.cli tools` before touching code. Use
  `python -m tools.cli --help` for commands.
- Python 3.11+; install with `python -m pip install -r requirements.txt`.
- Run `python -m pytest tests/ -q`; network tests are excluded by default.
- After changing skill metadata, run `python -m tools.agent_setup` and
  verify `python -m tools.agent_setup --check`. Edit the canonical skills,
  not their generated Claude entrypoints.
- On Windows use PowerShell syntax; see the runtime adapter for translating
  shell examples. Confirm the working directory before running commands.
- Preserve peer edits and historical evidence. Research data is shared;
  tests use private databases. Never run an experiment against the user's
  ledger as a substitute for a test fixture.

The user places every bet manually. Every recorded opportunity requires a
Kalshi ticker, honest edge basis, and applicable model/prompt provenance.
Judgment classifies; measurement quantifies. The full rules live in the
shared guide and the skill for the task.
