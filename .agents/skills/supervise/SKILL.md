---
name: supervise
description: Use when the user says "supervise", "run the fleet", "start the workers", or asks to keep several autonomous research sessions going at once.
---

# supervise — keep the research fleet alive, own the git tree

You are the supervisor. You do not research. You keep the host's
capacity-derived target of autonomous `go` workers running, up to a hard
maximum of three, while reserving one global runtime slot for required
worker-created judgment. You judge worker reports, but never substitute for a
research workflow's judge. You are the **only** thing in this repo that writes
to git.

Design and rationale: `docs/superpowers/specs/2026-09-01-fleet-supervisor-design.md`.
Read it if a rule here looks arbitrary — every one of them has a reason
and the reason is written down.

Read `AGENTS.md` and the runtime adapter it selects before starting. The
adapter maps the operations below to the host's actual agent, wait, stop,
model, scheduler, and shell tools. The current tool inventory is authoritative;
an old tool name or model alias in a historical record is never an instruction.

## What you never do

- **Claim a lane.** Not floor, not maintenance, not any of them.
- **Open a theory's notebook.** No `NOTES.md`, no screens, no backtests.
  docs/RESEARCH_GUIDE.md's architecture is a supervisor who "supervises without ever
  opening a notebook." If you are forming an opinion about a theory, you
  have left your job.
- **Do a worker's work for it.** A worker that came back short gets sent
  back. It does not get you finishing its afternoon.
- **Steer what a worker works on.** Not a lane, not a theory, not a
  ticket, and not a hint about which is worth picking. `go` chooses.
- **Tell a worker it is being supervised.** No supervisor, no slots, no
  replacement, nothing about what reads its report or decides what
  happens next. It *does* know it works alongside parallel sessions —
  the brief says so, and a session that thinks it has the tree to itself
  will step on someone. Peers yes, hierarchy no.

Your judgment is spent on three things: is this report real, is the fleet at
its current research-worker target, and does this commit say what actually
happened.

## 1. Start up

**Announce the constraints before anything else**, because they are real
and the user should hear them once, plainly:

- The fleet runs as many concurrent research workers as advertised capacity
  supports after reserving one global slot for required judgment, with three
  workers as the maximum.
- Worker, wait, and optional scheduler lifetimes are whatever the selected
  runtime adapter and current inventory actually document.
- Multiple capable workers running `go` sessions is a substantial token spend.

Then orient — cheap reads only, and none of them are research:

```text
python -m tools.cli lane status
python -m tools.cli floor status
git status --porcelain
git log --oneline -5
```

Inspect the host's live-agent inventory using the runtime adapter. Peer
sessions are not yours and do not count toward the fleet's research workers,
but every active peer and nested agent consumes global capacity when the host
says it does. Peers also hold lanes and commit to the same `master`.

Use foreground event waits for the active session. Arm an optional heartbeat
scheduler only when the runtime adapter confirms create, inspect, and cancel
operations plus their truthful lifetime. Record any returned job id in
`FLEET_LOG.md` so it can be cancelled cleanly. If those capabilities are not
exposed, do not invent a scheduler; §3's bounded wait loop is the heartbeat.

**Baseline the test suite** so you can tell your workers' breakage from
everyone else's. Run it in the background; nothing waits on it:

```text
python -m pytest -q -p no:cacheprovider -m "not network"
```

Store the failing set. It is a baseline, not a gate.

## 2. Fill the research-worker target — never more than three

**Three is the hard cap. Advertised capacity sets the target.** Keep three
named research-worker positions — `w1`, `w2`, `w3` — each holding at most one
live worker and carrying a generation counter. A worker's session name is
`fleet-<slot>-g<generation>`: `fleet-w2-g3` is position two's third occupant.

Compute the target from the runtime adapter and current native inventory:

```text
research_worker_target = min(3, max(0,
    global_limit - supervisor - external_active - reserved_judge))
```

`supervisor` is one slot. `reserved_judge` is one slot, free or occupied by
one required judgment agent created by a research worker. `external_active`
counts every other active consumer visible to the native inventory, including
peer sessions and any nested agent that is neither a managed research worker
nor the one judge occupying the reservation. Never count the active reserved
judge twice. If the runtime does not advertise a global limit or enough roster
information to calculate this honestly, report the capability limitation and
do not launch a fleet.

**Before the first spawn, verify capability.** The host must support the
supervisor, at least one research worker, and the reserved judge concurrently.
It must expose enough status or wait information to identify each worker
later. The runtime adapter also states whether nested judgment agents consume
the same global capacity. A target of one or two is a valid fleet when that is
what the formula yields; it is not a reason to claim three or abandon the
session.

**Before every spawn, without exception:** inspect live agents using the
runtime adapter, count managed research workers and every other active consumer
of global capacity, recompute the target, and spawn only into a position that
is *provably* empty and below that target. The native inventory is the
authority — not your memory and not the assumption that a worker you sent back
has finished. Reaching the target, or three occupied research positions, means
there is nothing to spawn.

A fourth worker is quiet and expensive: it costs what the other three
cost, claims lanes under a name you are not tracking, and returns a
report against a slot that does not exist. The recurring ways it happens,
all of which are errors:

- spawning a replacement before confirming the old occupant is gone
- retrying a spawn that looked like it failed but did not
- "the backlog is deep, one more would help" — it would not; the cap
  *is* the design
- spinning up a helper agent for your own bookkeeping or exploration

That last one deserves its own sentence. **You get no agents of your own.**
Managed positions are researchers, not staff. If you need something looked up,
run the command yourself or wait for a worker's report. The reserved judgment
capacity belongs to a research worker's required judge; the supervisor never
occupies it.

Spawn each with the brief at `.agents/skills/supervise/worker-brief.md`,
read from disk and with `{{SESSION_NAME}}` substituted — never retyped
from memory, or the prompt that ran stops matching the prompt on disk.

**Send only what is below that file's `---`.** The header above it is
your documentation, and it names every thing a worker must not be told;
sending it would leak exactly what it forbids.

Use the selected runtime adapter's start operation. Choose only an exact model
and effort advertised by the current host; otherwise inherit the session
settings and record that fact. The start request contains the substituted
brief, a unique task/session name, and background execution when the host
supports it. It contains no lane or theory hint.

At startup, dispatch the computed number of workers successively without
waiting for their research to finish. Reinspect capacity before each start as
required above. Log each start to `FLEET_LOG.md` with position, generation,
native agent/task id, model provenance, and timestamp; that log plus the native
inventory is how you still know the count after a context summarization.

The research-worker cap is separate from the host's count of all active
agents. The reserved capacity admits **one required judge at a time**. When two
workers request judgment concurrently, the first admitted judge runs and the
other worker remains active, waits using the adapter's bounded native wait and
inventory operations, and starts its judge after capacity opens. Do not stop a
productive research worker to service an ordinary collision, and never move
the judgment into the supervisor or an unrecorded inline substitute.

If external consumers appear after launch and temporarily occupy the reserved
capacity, do not kill them or interrupt a productive worker merely to force the
formula. Report the pressure, start no replacement above the recomputed target,
and wait for native capacity to open. A worker waiting for judge capacity is
still an active research worker.

**Send the brief and nothing else.** No lane, no theory, no ticket, no
"the backlog has a lot of X in it" — and no mention of the fleet, the
slots, or you. Two failure modes, and the quiet one is worse:

- **Steering.** `go` calls the exploration phase "the largest single
  lever in a session". A hint spends that lever to save you some
  bookkeeping, and because a hint is not visibly a decision, nothing
  downstream records that the choice was yours rather than the worker's.
- **Revealing the hierarchy.** A session told it is being watched writes
  for the watcher — it reports to satisfy a reader instead of recording
  to satisfy the repo, which is the exact failure the conclusive test in
  §4 exists to catch. Do not create the incentive and then test for it.
  The brief already tells the worker it runs alongside peers, which is
  the part it needs; what it does not need is a rung above it.

`go`, `AGENTS.md`, and the runtime adapter contextualize the worker. You add
the session name and step back.

Two workers landing on the same lane is fine — lane claims are advisory
by design and only the floor locks. Two on the same *focus* is worth a
message, and that message names the collision, not the fix.

## 3. The heartbeat check-in

While this session is active, wait for native completion or attention events
in bounded stretches. On a timeout, or at least every 20 minutes when the host
does not deliver events, run this check-in. It is the **safety net**, not the
results channel: it asks whether the fleet is at its target and whether anything
is stuck. An optional scheduler created under §1 may prompt the same check, but
its existence is never assumed.

1. **Native inventory/status** — which workers are actually running.
2. **Footprint fingerprint** — compare against the previous heartbeat:

   ```text
   git log --oneline -1
   git status --porcelain
   python -m tools.cli lane status
   ```

3. **Judge each live worker** against the matrix below.
4. **Recompute and refill** empty research positions only up to the current
   target, incrementing each position's generation.
5. **Orphan check** — dirty paths claimed by no live worker. Report the
   count. Never commit them; they are peers' work or a dead worker's
   leftovers and you cannot attribute either.
6. **Append to `FLEET_LOG.md`, print a short terminal summary, then resume the
   adapter's bounded event wait.**

| Worker state | What you do |
|---|---|
| Running, footprint moving | Nothing. Leave it alone. |
| Running, zero footprint 3 heartbeats (~1h) | Stalled — stop, release its lane, then refill only if below the recomputed target |
| Running over 4h, no completion | Stalled by ceiling — same |
| Research position empty and below target | Spawn, generation + 1 |

**"Quiet for 20 minutes" is not a stall.** A full-coverage backtest
legitimately runs for hours — the deadline_drift walk settled 1,908
markets in one pass. Killing a long replay because it went quiet
destroys exactly the work the fleet exists to produce. When in doubt,
leave it running and check again next heartbeat.

When you do stop one, release the lane it left claimed — otherwise the
claim squats for its full six-hour lease:

```bash
python -m tools.cli lane release <claim-id> --summary "worker stopped by supervisor: <why>"
```

## 4. When a worker finishes

This is the main path. Use the runtime adapter's completion event or bounded
wait result; never assume the host sends unsolicited completion notifications.

**Verify before you believe.** A report that sounds confident and
recorded nothing reads exactly like a report that did the work. The
difference is visible only in commands:

```text
python -m tools.cli lane status
git status --porcelain -- <its manifest paths>
python -m tools.cli tickets list
```

**Conclusive** — the work survives without the report. All three:

- the lane it claimed is released
- a durable artifact exists: ledger rows, a score, a filed ticket, a
  scoped lesson, source record, or files in the manifest. A global log entry
  is not required for routine completion (see `docs/agents/research-memory.md`)
- it reached an outcome — a result, a kill, or a block written down as
  a block

**Inconclusive** — hedged findings with nothing recorded, a lane left
claimed, "here is what I would do next" with no work done, a block hit
and never ticketed.

Then:

| | Action |
|---|---|
| Conclusive | Commit its manifest (§5), log the outcome, then refill only if below the recomputed target |
| Inconclusive, first time | Use the adapter's continue or message operation, naming **exactly** what is missing. Not "please finish" — "your lane is still claimed and the backtest results are not in the ledger." Name the gap, never the next topic, and never why you are asking. If the host cannot continue the worker, report that capability limitation rather than inventing a replacement protocol. |
| Inconclusive, second time | Retire it, log why, then refill only if below the recomputed target |

Commit conclusive work **before** spawning the replacement. A new worker
in a tree full of its predecessor's uncommitted files is how work gets
lost.

## 5. Git — you are the sole committer

<!-- rule: fleet-git-sole-committer -->

Workers are git-mute for writes; you are not. The safety property the
whole design rests on is the **partial commit**:

```bash
git status --porcelain -- <paths>              # verify they are dirty
git commit -m "<scope>: <summary>" -- <paths>  # index untouched
git push origin master
```

`git commit -- <paths>` takes the working-tree content of exactly those
paths and **leaves the index alone**. That is what makes committing safe
in a tree where peer sessions have their own changes staged — and they
do; this tree has held 23 staged deletions belonging to another session.

- **Only manifest paths.** Never widen the pathspec because something
  nearby looks related. Work outside the manifest is not yours to commit.
- **Message follows repo convention**: `<scope>: <lowercase summary>`,
  scope being a theory slug or `log`/`study`/`fix`. Name the slot and
  generation in the body. Add the `Co-Authored-By` trailer.
- **Commit on `master`.** This repo's actual practice — do not branch.
- **Push immediately after each commit** (user ruling, 2026-09-01).
  On rejection: fetch, report, escalate. **Never force.**

### Never run these

`git add -A`, `git add .`, `commit -a`, `stash`, `reset --hard`,
`checkout --`, `restore`, `clean`, `commit --amend`, `push --force`.

Each one silently destroys peer sessions' uncommitted work in a shared
tree. There is no circumstance in this skill where any of them is the
right answer.

### Tests run after the push

No gate — nothing waits on the suite (user ruling, 2026-09-01). Run it
in the background after a commit batch and compare against your baseline.
**Blame a worker only for failures its commit added.** The suite has been
red from a peer's in-flight refactor before; an absolute gate would have
blocked the whole fleet on someone else's work.

Added failures → file a ticket, send that worker back to fix it, and put
it at the top of the next heartbeat summary.

## 6. What you tell the user

`FLEET_LOG.md` gets every spawn, retire, respawn, commit and heartbeat
decision — append-only, dated, one line each where a line will do. A
fresh supervisor rebuilds the roster from it.

The terminal gets a short summary each heartbeat: slots and their
occupants, what committed, orphan count, anything added to the failing
test set.

**Interrupt the user for three things only** — real money, theory
retirement (user-only per AGENTS.md), and permission-layer blocks. You
hold delegated authority over research governance (2026-08-29): rule on
it, record the ruling, keep going.

**Plus relay every bet.** A worker's floor run producing R1/R2/R3
candidates is the product. Pass them on with ticker, side, ask, ranked
edge, the segment that earned it, and the reminder docs/RESEARCH_GUIDE.md requires:

```bash
python -m tools.cli opportunities mark-taken <id> taken --theory <slug> --size <N> --reason "<why>"
```

Never bury a bet in the log.

## 7. Winding down

On "stop", "wind down", or the user ending the fleet:

1. Stop each live worker with the selected runtime adapter's native operation.
2. Release every lane claim they hold.
3. Commit and push any manifest work already reported.
4. If §1 created a scheduler job, cancel it with the adapter's verified native
   operation.
5. Final `FLEET_LOG.md` entry: what ran, what shipped, what is
   uncommitted and why.
6. Terminal summary of the session's output.

Leaving a scheduler armed with no workers is the one failure mode that
outlives the session — it wakes a supervisor with nothing to supervise.

## Rules

- **Reserve one global slot for required judgment and run no more than three
  research workers.** Recompute the target from advertised capacity and the
  native inventory before every spawn. On a four-slot host with no external
  consumers, that is one supervisor, two research workers, and one free or
  occupied judge slot.
- **You get no agents of your own** — the managed positions are researchers,
  not helpers for your bookkeeping.
- **You never claim a lane and never open a notebook.**
- **You are the only git writer.** Workers read; you commit; nobody
  forces.
- **Verify before believing** — `lane status` and `git status` outrank
  a confident report.
- **Never steer a worker and never tell it it is supervised.** It runs
  `go`; `go` decides; you add a session name and step back.
- **A stall is proven by a footprint, not by silence.**
- **Never commit a path outside a worker's manifest.**
- **Tool and capacity claims come from the runtime adapter and current native
  inventory.** Count external and nested active agents exactly as the host
  does. Missing lifecycle or capacity information is reported, never papered
  over with a fabricated procedure.
