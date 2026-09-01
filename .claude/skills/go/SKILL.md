---
name: go
description: Start an autonomous research session — orient, explore the repo to find the highest-ROI action available, claim one lane, and hand off to its skill. Use when the user says "go", or asks you to work on finding edge without specifying what to do.
---

# go — explore, pick the highest-ROI lane, then stay in it

You are the researcher. Nobody is going to tell you what to test.

**This skill does not do the research. It works out what is worth doing,
picks it, and hands off.** Six lanes, each with its own skill:

| lane | skill | what it is |
|---|---|---|
| `floor` | `go-floor` | today's floor: every theory run against today's board, and the result reported |
| `theory` | `go-theory` | continue building out one existing theory |
| `study` | `go-study` | settle a question with a measurement — a study never bets |
| `new-theory` | `go-new-theory` | take one hypothesis from idea to running theory |
| `find-theories` | `go-find-theories` | go looking for theses nobody has proposed, and file them |
| `maintenance` | `go-maintenance` | the repo itself: tooling, migrations, docs, cleanup |

**You will do exactly one of them, and you will stay in it.** That is the
whole design. A session that touches all six and finishes none is the
failure this replaces; the ticket backlog is what makes finishing one
affordable, because everything you notice and do not do gets written
down instead of lost.

## 1. Orient — the cheap reads, always

```bash
python -m tools.cli floor status     # has today's floor been done?
python -m tools.cli lane status      # who is working on what
python -m tools.cli tickets list     # the backlog, oldest first (one
                                     # line each; --full for bodies)
python -m tools.cli studies          # what has been measured, and what
                                     # is still in flight
python -m tools.cli state            # theories, evidence, rulings, queue
```

Then `ListAgents`, so you know who is actually live rather than who left
a stale claim.

**If the floor is due and nobody holds it, take it and skip to §4.** It
is the one thing that must happen every day, every other lane's evidence
depends on it having run, and it is the only forced choice in this skill.

Everything below is what you do when the floor is settled.

## 2. Explore — find the highest-ROI action

**Always do this. It is not optional and it is not a formality.** The
four commands above tell you the state of things; they do not tell you
what is *worth doing*, and the gap between the best available action and
a plausible-looking one is the largest single lever in a session. A
session that picks the first reasonable ticket and starts is usually
leaving the real work on the table.

**Explore as widely as you need to.** In this phase you may go anywhere
and run anything:

- Read any theory's `THEORY.md`, `NOTES.md`, `RUNBOOK.md` — including
  theories you are not going to work on. Nothing here is private.
- Run any measurement: `score report <id>`, `slices report <id>`,
  `promote --run <run>`, `bucket_rates`, `compare-theories`. Numbers are
  free and reading them is faster than guessing.
- Query the database directly. Open the ticket files. Read
  `tickets/new-theory/open/` for what is specced and unbuilt, and
  `studies/` for what has already been measured.
- Look at the board (`get_board(conn)` — no force, that is the floor's).
- Check `git log`, run the tests, read `RESEARCH_LOG.md` for a ruling
  that `state` named.

Use whatever the repo can do. The cost of an hour spent choosing well is
recovered many times over by not spending a session on the third-best
thing.

**What "highest ROI" means here:** how much it changes a decision, per
unit of session spent. Concretely, the questions worth asking:

- **Which theory is closest to bettable?** A segment one settlement day
  short of its gates, or a claim with fetchable history and no replay
  run, is worth more than a theory that needs a month.
- **What is blocked, and what unblocks it?** A tooling bug stopping three
  theories outranks a clean new idea.
- **What is the evidence actually saying?** A sub-theory quietly past its
  gates, an orphan escalation, an `under_review` nobody diagnosed —
  these hide in plain sight in `state` and repay a look.
- **What is cheap and unreasonably valuable?** A replay that converts
  months of waiting into an afternoon is the recurring example.
- **What did the last session say to do next?** `RESEARCH_LOG.md`'s
  **Next** lines and open tickets are somebody's considered answer to
  this exact question, written with more context than you have now.

You are done exploring when you can **name the highest-ROI action and say
why it beats the runner-up.** That is the exit condition — not a clock,
and not "I have read enough". If you cannot state the comparison, you
have not found it yet.

**This is the only phase where ranging widely is right.** Once you
choose, you focus, and the focus rules below are strict. The freedom is
front-loaded on purpose: a session that explored properly does not need
to wander later, because it already knows what it is not doing and why.

## 3. Choose

Choose on what you found. Roughly, in order of how often it is the
answer:

- **A theory with tickets against it, or an unproven claim and fetchable
  history** → `theory`. A backtest that turns a claim into evidence is
  usually the highest-value work on the board.
- **A specced idea nobody has built, or a pattern the floor keeps
  surfacing** → `new-theory`. Every open ticket in
  `tickets/new-theory/open/` **is** a spec — that lane's backlog is
  its design documents.
- **A claim everything downstream rests on that nobody has measured, or
  a study in flight** → `study`. `cli studies` marks the unfinished ones
  with `*`. This lane is cheap and it is at its most valuable *before*
  work rather than after: `calendar-arb` and `smile-smoothing` were both
  killed by a one-afternoon measurement before any theory code existed.
  A study whose data perishes — Kalshi ages settled markets out after
  ~60 days — outranks almost anything else on the board.
- **The `new-theory` backlog is thin or picked over** → `find-theories`.
  The repo runs out of ideas long before it runs out of capacity to test
  them, and a session that fills the backlog is worth more than one that
  builds the least-bad thing left in it.
- **Tooling that is wrong, missing, or lying** → `maintenance`. Take it
  seriously: everything else runs on it.
- **Nothing in the backlog is worth doing** → say so and pick the lane
  with the most decision-changing work anyway. An empty backlog is a
  finding, not a reason to stop.

**State the lane you picked, and what you compared it against**, in a
line or two, before you start. That is the record of the exploration
having happened — and the next session reads it to know what was
already weighed and rejected.

## 4. Claim it

```bash
python -m tools.cli lane claim --lane <lane> --session <your name> \
    [--focus <theory>]        # which theory, on the theory lane
```

`"claimed": false` means a peer has it — **take a different lane.** The
refusal names the holder, so you know who to talk to.

Joining a held lane is allowed and discouraged: pass `--join "<reason>"`
and it is recorded. Do it only when the work genuinely wants two
sessions, never because it was the lane you fancied. If you cannot write
the reason, that is your answer.

The floor is different: it locks. `floor claim` refuses a second holder
outright, because it must happen exactly once.

## 5. Hand off

Invoke the lane's skill and follow it. **Everything after this point
belongs to that skill** — this one is finished once you have chosen.

## Staying in your lane

Every lane except maintenance is **focused**: you work the thing you
picked until it is done or genuinely blocked.

- **Every lane but maintenance** — do not pivot. Something else that
  needs doing gets a **ticket**, not your attention. The one exception:
  a maintenance problem that makes progress *truly impossible* — not
  annoying, not slower, impossible. Then file the ticket, say plainly in
  your report that you pivoted and why, and go fix it.

  Focused does not mean brief. On the research lanes you keep working the
  thing you picked until you have an edge or have genuinely exhausted it
  — finishing one ticket is not finishing the session, and a flat
  headline number is where the analysis starts rather than where it
  stops. `go-theory` carries the bar for what "exhausted" has to mean.
- **`maintenance`** — the only lane free to move between tickets, and
  free to do unfocused work nobody filed. That is what the lane is for.

**File tickets for what you are not going to do** — it is how the thing
you noticed survives your session. Always pass what you were *doing*
(`--author-lane`, `--author-focus`, `--author-context`): a crash hit
mid-backtest and the same crash hit while reading docs are different
reports, and the reader cannot reconstruct which one this was.

**But a ticket spends someone's session, so it is a commitment rather
than a note.** Filing feels free and is not: the backlog is read top to
bottom by sessions choosing work, so **a backlog full of nice-to-haves is
one where the genuinely blocking work never gets picked up.** The bar is
not "is this true" — it is *"would a session be right to spend its time
on this instead of research?"* If the honest answer is no, do not file
it. If it is in your lane and takes five minutes, just do it.
`tickets/README.md` has the file-it / do-not-file-it split.

```bash
python -m tools.cli tickets new --lane maintenance --slug <slug> \
    --title "<one line>" --body "<what to do, for someone who was not here>" \
    --session <you>
# a theory ticket lands INSIDE that theory's own folder:
python -m tools.cli tickets new --lane theory --theory <slug> ...
```

**Always file theory tickets through the CLI, never by writing the file
yourself.** A theory's folder is wherever its registry row says, and that
is not always `theories/<slug>`: `insider_judgment` lives at
`theories/insider_bias/insider_judgment`, under a shared family parent.
`--theory` looks the path up; guessing it from the slug creates a phantom
directory beside the real theory, holding nothing but tickets its expert
will never read. `tickets.ticket_dir` now refuses rather than guessing,
so a hand-rolled path is the only way left to get this wrong.

**An idea for a theory always gets a ticket**, whatever lane you are in —
the research lanes and maintenance both throw them off constantly, and an
idea nobody wrote down is an idea nobody has. One question routes it: is
it a **subset** of an existing theory — the same screen and population,
re-weighted? Then it belongs to that theory (`--lane theory --theory
<slug>`, or register it as a slice if it is the theory you are already
on). Anything needing its own screen, entry rule or population is a new
theory (`--lane new-theory`). File `ideas record` alongside either one:
the ticket is the work, the registry entry is what stops it being
re-proposed in three weeks.

## Talking to other sessions

**Talk to peers who are working — that is encouraged.** Tell them what
lane you took, tell them when you file a ticket that touches their work,
answer their questions, share a fact they need.

Two limits, both about protecting focus:

- **Do not unfocus them.** A message costs a working session its
  attention. If they do not need to act now, file a ticket instead — the
  ticket waits, and a ticket is not an interruption.
- **Do not review each other.** No judging a peer's run, critiquing
  their conclusions, or relaying a verdict on their work. Review costs
  focus on both sides and produces a judgment nothing records. Report
  facts to a peer; send disagreements to your report's "For your ruling".

Checking `lane status` or `floor status` is a fact check, never a review.

## Never ask — escalate and continue

An autonomous session does not stop to ask the user anything. In order:

1. **A structural surface answers it** — the promotion key, a runbook, a
   skill, `cli rulings list`, CLAUDE.md → take that answer and cite it.
2. **Reversible, in scope, nothing answers it** → decide, act, record the
   reasoning. If the gap will recur, propose the amendment in your report.
3. **User-only** — money, retirements, destructive or irreversible
   operations, permission-layer blocks → write it into "For your ruling"
   **and keep working** on everything it does not block.

"I have a question" is never an exit and never a pause.

## Rules

- **One lane per session.** Choosing is this skill's job; finishing is
  the lane skill's.
- **The floor outranks everything** when it is due and unheld.
- **A lane claim is released when you finish**
  (`lane release <id> --summary "..."`), so the next session sees the
  lane open rather than waiting out a six-hour lease.
- **Append to `RESEARCH_LOG.md` before you stop**, whatever lane you were
  in — Did / Learned / Next.
- **DB discipline** (enforced by `tests/test_db_discipline.py`): one board
  per session through `get_board`, never `markets.list_open()`, never a
  second `force`; `opportunity_attempts` answers which run decided
  something, never `opportunities.run_id`; open-position queries use
  `unsettled_only=True`; ledger DELETEs are user-only.
