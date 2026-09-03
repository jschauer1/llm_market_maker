---
title: go-study and tickets/study/README both document --slug with a date prefix, and create() prepends its own
lane: maintenance
created: 2026-09-03
created_by: fleet-w3-g5
author_lane: study
author_focus: maker-mode-fill-simulation
author_context: Hit while creating a new study ticket at the start of a study-lane session; the documented invocation was copied verbatim from the skill.
status: open
---
`tickets.create()` builds a study directory as `f'{day}-{slug}'` -- it prepends today's date itself (tools/tickets.py, the `if lane == \"study\"` branch of `create`).

Both places that document the command tell you to pass the date IN the slug:

- `.claude/skills/go-study/SKILL.md` section 3: `--slug <YYYY-MM-DD>-<slug>`
- `tickets/study/README.md` ("A study is a ticket" section): `--slug <date>-<slug>`

Following either produces `tickets/study/question/2026-09-03-2026-09-03-<slug>/`.

It does not raise, and it does not obviously look wrong in the CLI's own
output line, so the double date survives until somebody reads the tree.
`backlog()` parses the directory name with `_DATE_PREFIX` and would take
the FIRST date as `created` and `2026-09-03-<slug>` as the slug -- so
`cli studies` renders a study whose slug contains a date, next to
siblings whose slug does not. Every citation of the study by path then
carries the doubled name permanently.

Fix is one word in each doc (`--slug <slug>`, no date), and it is worth
also making `create()` reject a slug that already starts with a
`YYYY-MM-DD-` prefix rather than silently doubling it -- the same guard
`ticket_dir` now applies to theory paths, for the same reason: refusing
beats guessing.

Caught at 2026-09-03T02:15Z; the malformed directory was removed and the
study recreated correctly, so there is no stray directory in the tree.
