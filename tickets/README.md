# Tickets

One markdown file per unit of work, read as a backlog at session start
(`python -m tools.cli tickets list`).

- `maintenance/` — the repo itself: tooling, migrations, docs, cleanup.
- `research/` — new theses nobody has built yet (the `new-theory` lane).

**Theory tickets do not live here.** Work queued against an existing
theory goes in that theory's own folder, `theories/<slug>/tickets/`,
because a theory folder is supposed to hold everything its expert needs.

Filed with `tickets new`, closed with `tickets close` — closed tickets
keep their file, since a finished ticket is the record of what was asked
for and why.
