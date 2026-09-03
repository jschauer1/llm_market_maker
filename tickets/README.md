# Tickets — the work queue, and the bar for adding to it

```
tickets/
  maintenance/
    open/        2026-09-01-backfill-restart-loop.md
    completed/   2026-09-01-ticket-dir-ignores-registry-path.md
  new-theory/
    README.md    <- shared contracts every spec in this lane inherits
    reference/   <- the graded ledger behind their claims (NOT a state)
    open/        2026-08-24-maker-mode-execution.md
    build/       <- accepted; ready to implement, and a spec's last state
  study/
    question/ investigation/ answer/   <- a study is a DIRECTORY per state
theories/<registry path>/tickets/ <- theory work, in that theory's folder
    open/
    completed/
<owner>/studies/<state>/<date>-<slug>/ <- studies, beside their owner
```

**Lanes do not share a state list.** `theory` and `maintenance` run
`open/` -> `completed/`. `study` runs `question/` -> `investigation/` ->
`answer/` and has no `completed/` at all, which is what makes a finished
study permanent -- `purge` matches `completed/`, so the query cannot
reach one. `new-theory` runs `open/` -> `build/` -- a theory proves
itself when it is implemented, so there is no measurement stage in
between (user ruling 2026-09-03) -- and likewise has no `completed/`: a spec that ends is **deleted**, because
its verdict is already in the ideas registry or in the theory it became.
`states_for()` in `tools/tickets.py` is the authority.

**A ticket lives inside the thing it is about.** That is the rule, and it
has two owned lanes:

| the work is about | lane | it lands in |
|---|---|---|
| an existing theory | `--lane theory --theory <slug>` | `theories/<registry path>/tickets/` |
| an existing study | `--lane study --study <slug>` | that study's own folder |
| a theory that does not exist yet | `--lane new-theory` | `tickets/new-theory/` — **and it is a spec** |
| the repo itself | `--lane maintenance` | `tickets/maintenance/` |

A theory folder and a study folder are each supposed to hold everything
their expert needs, and queued work against them is part of that. Both
paths are resolved for you and both refuse a name they cannot find — a
theory's folder comes from its registry row (it is not always
`theories/<slug>`), and a study's is its dated folder name exactly.
Guessing either by hand creates a phantom directory beside the real one,
holding nothing but tickets its owner will never read.

**The directory is named for the lane.** `new-theory/` used to be called
`research/`, which meant every session had to know the two were the same
thing and a reader looking for "the new-theory backlog" had to be told
where it was.

**State is a directory, not a field.** The backlog is read
by listing, so a finished ticket has to leave it physically — with a
status field alone, every session reads every ticket ever filed to find
the few still open, and the backlog gets slower and less useful exactly
as the repo accumulates history. On most lanes closing moves the file and
keeps it, because a completed ticket is the record of what was asked for
and why. On `new-theory` closing **deletes** it: there the record already
exists somewhere better, and the second copy is the one that drifts. Git
holds every deleted spec.

A theory's tickets live at its **registry path**, not `theories/<slug>` —
`insider_judgment` sits under a shared family parent. `cli tickets new`
resolves this for you.

## A new-theory ticket is a spec

**Making a theory requires writing its spec first, and the ticket is the
spec.** There is no separate spec tree — there was one, and all 22 of its
documents still read "Status: backlog — not yet proposed as a theory"
weeks after four had become running theories, one had been retired and two
were dead. A second home for a document means a second status field, and
the second one is always the stale one.

So a `new-theory` ticket is not a one-line idea. It states the mechanism,
who is on the other side and why they keep being wrong, the Kalshi
population, what would falsify it, whether it is mechanical or
interpretive, and what the cheapest decisive first step is. Read
`tickets/new-theory/README.md` before writing one: its rules 0–0f are the
shared contracts, and they have killed more ideas here than any single
spec's own kill criteria have.

**An idea to try on an *existing* theory or study is not this.** It
belongs in that theory's or study's own folder — see the table above.
A new-theory ticket is for a theory that does not exist yet.

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

## Reading the backlog

```bash
python -m tools.cli tickets list                  # one line per ticket
python -m tools.cli tickets list --lane new-theory
python -m tools.cli tickets list --full           # every field, as JSON
```

**The default listing is deliberately the cheap one.** A ticket carries
its whole design, so a listing that included the bodies ran to 114 KB and
grew with every ticket ever filed — while being the single most repeated
read in the repo, at the start of every session. Open the file when you
have chosen; do not pay for 38 designs to pick one.

The resolution is required and is read by whoever wonders later. **"No
change needed" is a valid resolution** and closing a ticket that turned
out to be wrong is real work — say why, so the next session does not
re-file it.
