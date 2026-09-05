# Codex and Claude support

## Goal

Either Codex or Claude Code can operate the same research repository with
the same rules, discoverable skills, accurate attribution, and unchanged
historical evidence. The user authorized implementation and efficient
delegation on 2026-09-04. A mixed external-CLI fleet is a separate capability;
this change uses each application's available native agent tools.

## Design

Keep one shared research guide at `docs/RESEARCH_GUIDE.md`, preserving the
existing rules from CLAUDE.md. Both applications enter through a compact
`AGENTS.md`; `CLAUDE.md` imports it. The entrypoint requires reading the
shared guide and the appropriate runtime adapter. Moving the 63 KB guide
out of automatic discovery avoids Codex's default 32 KiB truncation.

Canonical skills live under `.agents/skills/`. Claude discovery files under
`.claude/skills/` retain each skill's frontmatter and explicitly direct the
reader to the canonical procedure. A deterministic Python command generates
and checks these small wrappers. No filesystem links or new dependencies.
Existing supporting-resource paths remain resolvable through compatibility
files; historical prompts and recorded provenance paths are not renamed.

`docs/agents/codex.md` and `docs/agents/claude.md` map shared operations to
the host's actual tools. Native tool inventories are authoritative. Guidance
covers listing, starting, continuing, waiting for and stopping children;
model and effort selection; capacity; and optional heartbeat support.
The fleet reserves one advertised global slot for required worker-created
judgment and uses the remaining capacity for up to three research workers.
Count external and nested active agents as the host does. If the host does not
expose enough capacity or roster information to preserve that reservation,
report the limitation rather than inventing it. Platform-specific scheduler
lifetime claims belong only in the relevant adapter and must be verified
locally.

Agent attribution defaults to `agent` when no provider was supplied. Explicit
`claude`, `codex`, and existing `user` authorizations retain their meaning;
only `user` can authorize retirement. New idea sources can explicitly name
either runtime. Existing source values and judgment records are preserved.
Model names are the actual requested identifiers or honestly labelled
aliases. Under the user's idealized-judge ruling, a model-family change
following the same written procedure shares existing calibration, aiming for
comparable intelligence and reasoning. It does not require an experiment or
version bump. New historical replays still verify their own knowledge cutoff;
the assumption never transfers another model's cutoff.

## Alternatives considered

- Two complete instruction/skill trees: already drifting, including a
  nonexistent `.Codex/` path and fabricated `Codex-opus-5` identity.
- Shared filesystem links: convenient locally, fragile in Windows clones.
- One source plus thin entrypoints: selected; small generation/check command
  prevents discovery metadata from drifting while research rules have one home.

## Validation

Baseline: 1,453 passed, 1 skipped, 4 network tests deselected. Regression
tests must cover wrapper generation/check behavior, both discovery trees,
resolved rule/resource paths, provider-neutral CLI attribution, preserved
retirement restrictions, and exact model provenance. Use private test
databases. Run the complete offline suite and a fresh-reader review of both
runtime workflows. No paid research runs, live ledger migration, or changes
to theory pricing/prompt semantics are part of this refactor.

## Following work

After compatibility is verified, return to the user's broader improvement
request and address a bounded operational defect supported by a failing test.
Prioritize misleading current-state reporting and duplicated maintenance
surfaces over adding new frameworks.
