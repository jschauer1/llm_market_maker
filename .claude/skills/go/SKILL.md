---
name: go
description: Start an autonomous research session — orient on the floor, the lanes and the ticket backlog, choose one lane, and hand off to its skill. Use when the user says "go", or asks you to work on finding edge without specifying what to do.
---

# go — choose a lane, then stay in it

You are the researcher. Nobody is going to tell you what to test.

**This skill does not do research. It picks what you will do, and hands
off.** Five lanes, each with its own skill:

| lane | skill | what it is |
|---|---|---|
| `floor` | `go-floor` | today's floor: every theory run against today's board, and the result reported |
| `theory` | `go-theory` | continue building out one existing theory |
| `new-theory` | `go-new-theory` | take one hypothesis from idea to running theory |
| `find-theories` | `go-find-theories` | go looking for theses nobody has proposed, and file them |
| `maintenance` | `go-maintenance` | the repo itself: tooling, migrations, docs, cleanup |

**You will do exactly one of them, and you will stay in it.** That is the
whole design. A session that touches all five and finishes none is the
failure this replaces; the ticket backlog is what makes finishing one
affordable, because everything you notice and do not do gets written
down instead of lost.

## 1. Orient — four commands

```bash
python -m tools.cli floor status     # has today's floor been done?
python -m tools.cli lane status      # who is working on what
python -m tools.cli tickets list     # the backlog, oldest first
python -m tools.cli state            # theories, evidence, rulings, queue
```

Then `ListAgents`, so you know who is actually live rather than who left
a stale claim.

Read the backlog properly before choosing. A ticket is a task somebody
wrote for whoever came next, and picking the *right* one is most of the
value this skill adds — `tickets list --lane <lane>` and open the files
that look plausible. Cheap now, expensive to get wrong.

## 2. Choose

**If the floor is due and nobody holds it, take it.** It is the one thing
that must happen every day, and every other lane's evidence depends on
it having run. That is the only forced choice here.

Otherwise, choose on what will change a decision. Roughly:

- **A theory with tickets against it, or an unproven claim and fetchable
  history** → `theory`. A backtest that turns a claim into evidence is
  usually the highest-value work on the board.
- **A specced idea nobody has built, or a pattern the floor keeps
  surfacing** → `new-theory`.
- **The `new-theory` backlog is thin or picked over** → `find-theories`.
  The repo runs out of ideas long before it runs out of capacity to test
  them, and a session that fills the backlog is worth more than one that
  builds the least-bad thing left in it.
- **Tooling that is wrong, missing, or lying** → `maintenance`. Take it
  seriously: everything else runs on it.
- **Nothing in the backlog is worth doing** → say so and pick the lane
  with the most decision-changing work anyway. An empty backlog is a
  finding, not a reason to stop.

State the lane you picked and why, in one line, before you start.

## 3. Claim it

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

## 4. Hand off

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

**File tickets liberally.** It costs you a minute and it is how the thing
you noticed survives your session:

```bash
python -m tools.cli tickets new --lane maintenance --slug <slug> \
    --title "<one line>" --body "<what to do, for someone who was not here>" \
    --session <you>
# a theory ticket lands in that theory's own folder:
python -m tools.cli tickets new --lane theory --theory <slug> ...
```

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
