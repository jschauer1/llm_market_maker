# Theory Build Plans

The build side of the theory pipeline. Each theory travels:

1. **Spec** — [docs/superpowers/specs/theories/](../../specs/theories/)
   (start at the
   [backlog index](../../specs/theories/2026-08-24-theory-backlog-index.md);
   claims are graded in its
   [evidence ledger](../../specs/theories/evidence/2026-08-24-evidence-ledger.md)).
2. **Plan** — this folder. When a spec is picked up for implementation,
   run the `propose-theory` skill first (registers the theory, scaffolds
   `theories/<slug>/`), then write the implementation plan here as
   `YYYY-MM-DD-<slug>-plan.md` via the superpowers writing-plans skill.
3. **Code** — `theories/<slug>/` in the repo root, per the theory
   contract in CLAUDE.md (THEORY.md is the source of truth for the
   procedure; any procedure change bumps the version).

A plan lands here only after its spec's registry entry
(`python -m tools.cli ideas search "<slug>"`) has been checked for
status changes — a spec may have been killed, parked, or superseded
since it was written.

## Build tracker

| theory | spec | plan | status |
|---|---|---|---|
| *(none built yet)* | | | |

Update this table when a plan is written, when implementation starts,
and when the theory reaches `testing` — it is the quick answer to
"which specs have become code."
