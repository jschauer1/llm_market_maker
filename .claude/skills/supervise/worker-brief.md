# Worker brief

Sent verbatim as a research session's prompt, with `{{SESSION_NAME}}`
substituted and nothing else. It lives on disk rather than inline so a
change to what a session is told shows up in `git diff` and gets reviewed
like any other change to a procedure.

**What this file must never contain**, and what must never be added to a
spawn on top of it:

- **A lane, a theory, a ticket, or any hint about which is worth
  picking.** `go` orients the session and chooses; a nudge from here
  competes with the exploration phase `go` calls the largest single
  lever in a session, and a nudge is worse than an order because it
  biases without being visible as a decision.
- **Any description of how this session is being managed.** No fleet, no
  slots, no supervisor, no mention that anything reads the report or
  decides what happens next. A session told it is being watched writes
  for the watcher.

`go` and CLAUDE.md contextualize the session. This brief adds only the
three things they cannot know: the session name to use, that commits for
this tree happen elsewhere, and what the report must end with.

---

Your session name is **`{{SESSION_NAME}}`**. Use exactly that string
wherever a tool wants `--session`.

**Invoke the `go` skill and follow it.** It and CLAUDE.md are the
authority on what this session does. Nothing below overrides either.

## This session does not write to git

**Forbidden:** `git add`, `commit`, `push`, `checkout`, `reset`, `stash`,
`merge`, `rebase`, `restore`, `clean`, `rm`, and every wrapper around
them. **Free:** `git log`, `git status`, `git diff`, `git show` — read
whatever you need.

You share this working directory with several other live sessions, all
committing to one local `master`. A tree-wide git write does not only
affect your work: this tree has held 83 dirty entries from three sessions
at once, with deletions already staged in the shared index. One
`git stash` would have destroyed an afternoon of other sessions'
uncommitted work, silently, with no way to attribute the loss.

Commits for this tree are made outside your session. That is not a thing
you need to arrange or wait for.

## End your report with the paths you touched

The last section, under `## Manifest` — repo-relative paths you created
or modified, one per line.

**Work you do not list does not get committed.** A path you forget sits
uncommitted in a shared tree until someone notices, and "someone
notices" is not a mechanism this repo has. If you spent four hours on a
backtest, its results belong in the manifest.

Do not list paths you did not touch, and do not list gitignored
artifacts — the DB, `user_reports/`, study data directories.
`git status --porcelain -- <path>` settles it if you are unsure.

## Report format

```
## Outcome
What you set out to do, and what actually happened. A result, a kill, or
a block — name which. One paragraph.

## Lane
Which lane you claimed, its focus, and confirmation you released it.

## What is recorded, and where
The durable artifacts: ledger rows, scores, tickets filed, the
RESEARCH_LOG.md entry, files written. This is what makes the work
survive your report.

## Open items
Escalations, questions you want ruled on, anything you found in another
lane and ticketed rather than chased. Bets that cleared the promotion
key go here with ticker, side, ask, ranked edge and segment.

## Manifest
path/one.py
path/two.md
```

## Finishing

`go`'s "never ask — escalate and continue" applies in full. Do not stop
and wait on anyone: write the item under `## Open items` and keep working
on everything it does not block.

Your session is done when the work survives without your report — the
lane released, a durable artifact recorded, an outcome reached. A report
describing exploration that recorded nothing is not a finished session,
and finishing it later costs more than finishing it now. Record as you
go, which is the repo's standing data convention regardless.
