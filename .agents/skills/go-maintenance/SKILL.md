---
name: go-maintenance
description: Work the repo itself — tooling, migrations, docs, tests, cleanup. The one lane free to move between tickets. Invoked by go when the maintenance lane is claimed.
---

# go-maintenance — keep the machine honest

Invoked by `go` once you hold the maintenance lane. **This is the only
lane allowed to pivot.** Move between tickets freely, and do unfocused
work nobody filed — that is what the lane is for. The research lanes stay
focused because you exist to absorb what they trip over.

Take it seriously: every theory, every score and every bet runs on this.
A tool that is subtly wrong does not raise an error, it produces
confident nonsense that nobody re-checks.

## 1. Read the backlog

```bash
python -m tools.cli tickets list --lane maintenance
```

Oldest first, deliberately — a backlog sorted newest-first becomes a
stack, and the ticket nobody got to is usually the one that most needs
picking up. Work several in a session if they are small.

Beyond the backlog, the standing maintenance surface:

```bash
python -m pytest tests/ -q          # the whole suite, always
python -m tools.cli tools           # what exists and what each is for
python -m tools.cli state           # anything rendering wrong or empty
python -m tools.cli db backup       # before anything that migrates
```

## 2. What counts as maintenance

- **Tooling that is wrong, missing, or lying.** A number that renders
  from the wrong row, a query that silently answers a different question
  than its name, a command that crashes on its own output.
- **Guards for a mistake that actually happened.** This repo's tests
  encode real incidents; that is why they find real bugs. A convention
  nobody can violate accidentally is worth more than a paragraph asking
  people not to.
- **Migrations and schema work**, always after `db backup`.
- **Docs that have drifted from the code.** Especially AGENTS.md and the
  skills — an autonomous session acts on them without checking.
- **Dead weight.** Code with no callers, a helper that earned promotion
  to `tools/`, a study whose result is now a rule.

## 3. The rules that bind hardest here

**Semantics are the dangerous part.** Autonomous sessions read a name,
believe it, and act. Widening what a field may hold is safe; changing
what an existing value *means* rewrites every row already recorded under
the old meaning. Prefer a new name to a redefined one. When meaning must
change, migrate rows explicitly and separately from the schema change,
say so in `RESEARCH_LOG.md`, and leave the old wording visible.

**When a default changes, check what reads it.** A query written against
the old vocabulary keeps running and starts answering a different
question — silently, and only in production.

**Test-first, and watch it fail.** A test that passed the moment you
wrote it has proven nothing. The suite is the repo's memory of what has
already gone wrong.

**Filing is not free, and this lane sees everything.** Maintenance reads
across the whole repo, which makes it the biggest potential source of
backlog noise: every session turns up a dozen things that could be
better. File the ones a session would be right to spend its time on, do
the five-minute ones yourself — you are the lane that is allowed to —
and let the rest go. A backlog of nice-to-haves buries the blockers.

**Never fix a theory's thesis from this lane.** Tooling, yes; judgment
about what a theory should claim belongs to `go-theory` with that
theory's context loaded. File the ticket instead.

**An idea for a theory is a ticket, not a detour.** Maintenance work
reads across the whole repo, so it is a common place to notice a thesis
nobody has proposed — a pattern in the schema, a regularity in the
ledger, something a study half-answered. That is valuable and it is not
this lane's job:

```bash
python -m tools.cli tickets new --lane new-theory --slug <slug> --title "<the thesis in one line>" --body "<the mechanism, and what suggested it>" --session <you>
python -m tools.cli ideas record <slug> "<title>" --description "..."
```

If it is a subset of an existing theory — the same screen and population,
re-weighted — it is a **sub-theory** of that theory, so the ticket goes
to `--lane theory --theory <slug>` and lands in that theory's own folder,
where its expert will see it. Anything needing its own screen, entry rule
or population is a new theory. File both the ticket and the registry
entry: the ticket is the work, the registry entry is what stops it being
re-proposed in three weeks.

## 4. Close what you finish

```bash
python -m tools.cli tickets close <path> --resolution "<what happened>"
```

Close it when it is done or when it turns out not to need doing — a
ticket resolved "not a bug, the caller was wrong" is as useful as a fix,
and leaving it open means somebody re-investigates it.

If a ticket turns out to be bigger than the lane, split it: close the
part you did, file the rest with what you learned. A ticket that has been
looked at three times without moving is a ticket that needs rewriting.

## 5. Finish

```bash
python -m tools.cli lane release <claim id> --summary "<what you fixed>"
```

Report the tickets you closed and what you changed, the unfiled work you
did, anything you filed for other lanes, and anything for the user's
ruling. Keep routine completion in that task record. If the work establishes a
reusable constraint, consolidate it using `docs/agents/research-memory.md`;
only a consequential cross-session change earns a global log entry.

For unfiled routine work, the lane-release summary and final report's file
manifest are the completion record; do not create a lesson or diary just to
prove the session happened.

**Run the full suite before you release the lane**, and say the number in
your report. A maintenance session that leaves the suite red has made the
repo worse than it found it.
