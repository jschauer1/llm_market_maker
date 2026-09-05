# Worker brief

**Everything above the `---` is for the supervisor and is never sent.
The prompt is everything below it**, verbatim, with `{{SESSION_NAME}}`
substituted and nothing else added. Sending this header would leak the
very thing it exists to forbid, so the split is the point rather than a
formatting choice.

The brief lives on disk rather than inline so a change to what a session
is told shows up in `git diff` and gets reviewed like any other change to
a procedure.

**What this file must never contain**, and what must never be added to a
spawn on top of it:

- **A lane, a theory, a ticket, or any hint about which is worth
  picking.** `go` orients the session and chooses; a nudge from here
  competes with the exploration phase `go` calls the largest single
  lever in a session, and a nudge is worse than an order because it
  biases without being visible as a decision.
- **Any description of the hierarchy above it.** No supervisor, no
  slots, no replacement, no mention that anything reads the report or
  decides what happens next. Working *alongside* peers is told plainly
  below, and must be — a session that does not know the tree is shared
  will step on it. Being *supervised* is not told, because a session
  that knows it is being watched writes for the watcher.

`go`, `AGENTS.md`, the shared research guide, and the selected runtime adapter
contextualize the session. This brief adds only the three things they cannot
know: the session name to use, that commits for this tree happen elsewhere,
and what the report must end with.

---

Your session name is **`{{SESSION_NAME}}`**. Use exactly that string
wherever a tool wants `--session`.

**Read `AGENTS.md`, its policy loading map, the guide sections for research
orientation, and the runtime adapter it selects. Invoke the canonical `go`
skill; load the additional mapped policy before acting in its chosen lane.** Those
sources are the authority on what this session does. Nothing below overrides
them.

## You are one of several sessions running in parallel

Other research sessions are working this repo right now, alongside you,
in the same working directory and against the same database. That is
normal, and every coordination mechanism you will meet exists because of
it:

- **Lane claims are advisory, and only the floor locks.** Check
  `lane status` before claiming. If a peer holds what you wanted, take
  something else rather than joining without a reason you can write down.
- **The board is shared.** `get_board(conn)` hands back the session's
  existing pull when it is fresh. Do not force a refetch to get your own.
- **A ticket is the low-interrupt way to tell a peer something.** A
  message costs them their focus; a ticket waits until they are choosing
  work.
- **`git status` will show you other sessions' uncommitted work.** It is
  not yours, it is not abandoned, and it is not a mess to tidy.
- **Agent capacity is shared.** Before starting a required judgment agent,
  inspect the runtime adapter's native inventory. If no global capacity
  remains, keep this research session active and use bounded native waits until
  capacity opens. Do not perform the judge's work inline, and do not launch
  optional child work that consumes capacity needed for judgment.

Peers, not competitors. Two sessions on different lanes is the design
working.

## This session does not write to git

**Forbidden:** `git add`, `commit`, `push`, `checkout`, `reset`, `stash`,
`merge`, `rebase`, `restore`, `clean`, `rm`, and every wrapper around
them. **Free:** `git log`, `git status`, `git diff`, `git show` — read
whatever you need.

As above, you share this working directory with several live sessions,
all committing to one local `master`. A tree-wide git write does not only
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
Source records, lesson/map updates if earned, files written. A global log
entry is conditional under `docs/agents/research-memory.md`. This makes the work
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
