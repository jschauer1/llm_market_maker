# Tickets — the work queue, and the bar for adding to it

```
tickets/
  maintenance/
    open/        2026-09-01-state-md-stale.md
    completed/   2026-09-01-ticket-dir-ignores-registry-path.md
  research/                       <- new-theory lane
    open/
    completed/
theories/<registry path>/tickets/ <- theory work, in that theory's folder
    open/
    completed/
```

**Open and completed are directories, not a field.** The backlog is read
by listing, so a finished ticket has to leave it physically — with a
status field alone, every session reads every ticket ever filed to find
the few still open, and the backlog gets slower and less useful exactly
as the repo accumulates history. Closing moves the file; nothing is ever
deleted, because a completed ticket is the record of what was asked for
and why.

A theory's tickets live at its **registry path**, not `theories/<slug>` —
`insider_judgment` sits under a shared family parent. `cli tickets new`
resolves this for you.

## The bar: a ticket is a commitment, not a note

**Every ticket you file spends someone's session.** That is the cost, and
it is easy to miss because filing feels free — it takes a minute and gets
the thing off your plate. But a backlog is read top to bottom by sessions
choosing what to do, and **a backlog full of nice-to-haves is one where
the genuinely blocking work never gets picked up**, because it is sitting
behind eleven cosmetic items that all looked reasonable when filed.

So the bar is not "is this true" or "would this be better". It is:

> **Would a session be right to spend its time on this instead of
> research?**

If the honest answer is no, do not file it.

### File it

- **A real blocker.** Something is broken, wrong, or missing, and it
  stops work — yours or somebody else's.
- **A correctness bug**, especially a silent one. A tool that lies is
  worse than a tool that fails, and it always earns a ticket.
- **A thesis worth testing.** Ideas are the scarce input here, and a
  hypothesis with a mechanism is never noise (see `go-find-theories`
  for the bar an idea itself has to clear).
- **Work you started and could not finish.** Say exactly where you got
  to; that is what makes it resumable rather than repeatable.
- **A decision that needs someone with context you do not have.**

### Do not file it

- **"Would be nice."** Cleanups nobody is blocked on, refactors nobody
  asked for, wording you would have chosen differently.
- **Something you could do right now in your own lane.** If it is in
  scope and takes five minutes, do it. A ticket is for work you are
  *not* going to do.
- **An observation with no action.** "This is confusing" is not a task.
  Either say what to change or leave it out.
- **A duplicate.** Read the backlog first (`cli tickets list`). Add to
  the existing ticket instead — a second ticket for the same thing makes
  both look smaller than the problem is.
- **A thought you have not tested.** If you are not sure it is real,
  spending a paragraph checking beats spending someone's session on it.

When you are genuinely unsure, ask which is worse: this sitting unfiled,
or this sitting in the backlog ahead of something that matters. That
question usually answers itself.

## What a ticket must contain

`cli tickets new` enforces the first three; the rest is on you.

- **`--title`** — one line, what needs to happen.
- **`--body`** — the task, written for a session that was not there. What
  is wrong, how to reproduce it, what "done" looks like. A title with
  nothing under it gets deleted rather than done.
- **`--lane`** — who should pick it up.
- **`--session`, `--author-lane`, `--author-focus`, `--author-context`** —
  who you are and **what you were doing when you hit this**. This is the
  part a reader cannot reconstruct and the part that makes a ticket
  actionable: a crash found while replaying a 90-day backtest and the
  same crash found while reading docs are different reports of different
  urgency. `created_by` alone answers "who" and not "why this matters".

```bash
python -m tools.cli tickets new --lane maintenance \
    --slug snapshot-reader-crashes-on-zlib \
    --title "payload reader crashes on compressed snapshot rows" \
    --body "Repro: ... Expected: ... Done when: ..." \
    --session llm-market-identifier-86 \
    --author-lane theory --author-focus insider_judgment \
    --author-context "replaying the v4 screen over 90 days; it died on the
                      first pre-overhaul row"
```

## Closing

```bash
python -m tools.cli tickets close <path> --resolution "<what happened>"
```

The resolution is required and is read by whoever wonders later. **"No
change needed" is a valid resolution** and closing a ticket that turned
out to be wrong is real work — say why, so the next session does not
re-file it.
