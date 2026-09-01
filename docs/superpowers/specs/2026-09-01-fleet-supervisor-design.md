# Fleet supervisor — three `go` workers, one committer

**Status:** accepted 2026-09-01 (user). Built the same day.
**Skill:** `.claude/skills/supervise/`

## The problem

`go` produces one focused session at a time. Capacity is the binding
constraint on this project — the repo runs out of *evidence* long before
it runs out of ideas, and the single largest lever named anywhere in the
skills is "a replay that converts months of waiting into an afternoon."
Three sessions replaying, screening and mining in parallel is three times
that lever.

Running three at once was already possible — peer sessions have been
doing it for a week — and it already hurts in two specific places:

1. **Nobody owns the fleet.** A peer session that dies leaves its lane
   claimed for a six-hour lease, and no one notices. The count of live
   researchers drifts down and the only signal is a human happening to
   run `lane status`.
2. **Nobody owns the tree.** Every session commits to one shared working
   directory on one local `master`. On 2026-09-01 at 18:20 the tree held
   **83 dirty entries from three sessions at once, including 23 deletions
   already staged in the shared index** by a peer mid-refactor. Any
   session running a bare `git commit` would have swept up two other
   sessions' half-finished work into a commit describing its own.

The supervisor exists for exactly these two jobs: keep three workers
alive, and be the only thing that writes to git.

## What it is not

It is not a lane, and it does not research. CLAUDE.md's architecture is
"a supervisor over theory experts", where the supervisor "understands
every theory abstractly and supervises without ever opening a notebook."
This builds that literally. The supervisor claims no lane, opens no
`NOTES.md`, and runs no screen. If it finds itself reading a theory to
form an opinion about the theory, it has left its job.

## Decisions (user, 2026-09-01)

| Question | Ruling |
|---|---|
| Supervisor's own scope | Pure supervisor — no lane, no research |
| Who picks each worker's lane | The worker, via `go` unmodified |
| Heartbeat | `CronCreate` armed by the skill itself |
| Inconclusive report | Send the same worker back; wipe on the second miss |
| Reporting | `FLEET_LOG.md` plus a terminal summary each heartbeat |
| Git scope | Supervisor is **sole committer**; workers are git-mute |
| Push | **Automatic** after each commit |
| Test gate | **None** — commit, push, then report |

The last two were chosen against this document's recommendation, which
was a baseline-diff test gate and push-on-request. The consequence is
recorded under "Known consequences" rather than argued again.

## Architecture

### Slots, not agents

Three fixed slots — `w1`, `w2`, `w3` — each holding at most one live
worker, each with a generation counter. A worker's repo session name is
`fleet-w2-g3`: slot two, third occupant.

Slots rather than a list of agent ids, for three reasons. The supervisor's
context will be summarized during a long run, and "three slots, one of
which is empty" survives summarization where a list of opaque ids does
not. `lane status` becomes self-describing — a claim held by `fleet-w1-g2`
is visibly a fleet worker and visibly not the same session as the
`fleet-w1-g1` that held it an hour ago. And a respawned worker can never
inherit its predecessor's lane claim, because it is a different name.

### Two wake signals with different jobs

**Completion is the primary signal and needs no timer.** A background
subagent finishing re-invokes the supervisor automatically. This is the
path that runs most of the time.

**The 20-minute cron is the safety net**, for the case a worker hangs,
dies silently, or ends without notifying. `CronCreate` at
`7,27,47 * * * *` — off-minute deliberately, per the scheduler's own
guidance that everyone who asks for "every 20 minutes" lands on `:00`.

The distinction matters because it sets what a heartbeat is *for*. A
heartbeat is not "collect results" — results arrive on their own. It is
"is the fleet still three, and is anything stuck."

### State lives in ListAgents and FLEET_LOG.md

No new table, no JSON checkpoint. `ListAgents` is live truth about which
subagents are running; `FLEET_LOG.md` is the append-only record from
which a fresh supervisor can rebuild the roster. Two sources, each
already durable, neither able to drift from the other because one is
observed and one is history.

A `fleet_workers` table was considered and rejected: one caller, and
CLAUDE.md's rule is that code elevates by caller count. The log is the
durable store the data conventions ask for.

## Worker lifecycle

Workers spawn with `model: opus`, `run_in_background: true`, and the
brief at `.claude/skills/supervise/worker-brief.md` — on disk rather than
inlined, following the repo's standing rule that a prompt which exists
nowhere on disk cannot be reviewed in a diff.

The brief is deliberately thin. It hands over a session name, forbids git
writes, requires a path manifest, and says *run `go`*. Everything else —
orient, explore, choose the lane, stay in it — is `go`'s job and is not
restated. The exploration phase in particular is left entirely alone:
`go` calls it "the largest single lever in a session", and a supervisor
that pre-assigned lanes would spend that lever to save itself some
bookkeeping.

### Conclusive is verified, not read

A report is **conclusive when the work survives without the report.**
Three conditions, all checked with commands rather than by reading prose:

- the lane it claimed is released (`lane status`)
- a durable artifact exists — ledger rows, a score, a filed ticket, a
  `RESEARCH_LOG.md` entry with Did/Learned/Next, or files in the manifest
- it reached an outcome: a result, a kill, or a block written down as a
  block

Inconclusive is the complement, and it has a characteristic shape:
hedged findings with nothing recorded, a lane left claimed, "here is
what I would do next" with no work done, a block hit and never ticketed.

The verification requirement is the load-bearing part. A model asked
"was this conclusive?" while looking at a confident-sounding report will
say yes. A supervisor that runs `lane status` and `git status` finds out.

### The lifecycle matrix

| Worker state | Supervisor action |
|---|---|
| Completed, conclusive | Commit its manifest, log the outcome, spawn a fresh worker into the slot |
| Completed, inconclusive, first time | `SendMessage` it back naming exactly what is missing |
| Completed, inconclusive, second time | Retire it, log why, spawn fresh |
| Running, footprint moving | Leave it alone |
| Running, no footprint for 3 heartbeats (~1h) | Stalled — stop, release its lane, respawn |
| Running over 4h with no completion | Stalled by ceiling — same treatment |

"Silent for 20 minutes" is deliberately **not** a stall. A full-coverage
backtest legitimately runs for hours; the deadline_drift walk of
2026-09-01 settled 1,908 markets in one pass. Killing a long replay
because it was quiet would destroy exactly the work the fleet exists to
produce.

### Footprint fingerprint

At each heartbeat the supervisor records and compares:

- newest commit sha
- count of files modified under `theories/`, `tickets/`, `studies/`, `tools/`
- live lane claims and their holders
- `opportunities` row count

Movement in any of these is proof of life for the fleet as a whole.
Attributing movement to a particular worker is not always possible in a
shared tree, and the design does not pretend otherwise — the fingerprint
answers "is anything happening", and the lane claim answers "is this
worker still where it said it was."

## Git protocol

### Workers are git-mute for writes

The brief forbids `add`, `commit`, `push`, `checkout`, `reset`, `stash`,
`merge`, `rebase`, `restore`, `clean`, `rm`. Reads — `log`, `status`,
`diff`, `show` — stay free, because a worker often needs to know what
changed.

The brief states the reason rather than only the rule: a worker shares
one tree with three or more other writers, so any tree-wide git write
destroys someone else's uncommitted work. `git stash` is the sharpest
example — one worker stashing would have swept all 83 of that afternoon's
dirty entries out from under three other sessions.

### The manifest is the only channel

Every worker report ends with a list of repo-relative paths it created or
modified. Work not in the manifest does not get committed, and the brief
says so in those words, because a worker that assumes the supervisor will
notice its files is a worker whose afternoon is uncommitted.

### The commit

```bash
git status --porcelain -- <paths>              # verify they are dirty
git commit -m "<scope>: <summary>" -- <paths>  # partial: index untouched
git push origin master
```

`git commit -- <paths>` is the safety property the whole design rests on.
A partial commit takes the working-tree content of exactly the named
paths and **leaves the index alone**, so a peer's staged deletions cannot
ride along no matter what state the index is in. This is what makes a
sole-committer safe in a shared tree without worktree isolation.

Worktree isolation was considered and rejected. The `db` symlink would
have to survive a worktree checkout on Windows for lane claims and the
ledger to work at all, and if it silently did not, three workers would
write three separate databases and the divergence would be invisible
until scores stopped adding up. The partial commit gets the same safety
with no such failure mode.

Message follows repo convention — scope, colon, lowercase summary, scope
being a theory slug or `log`/`study`/`fix` — with the fleet slot and
generation named in the body, and the `Co-Authored-By` trailer. Commits
land on `master`, which is this repo's actual practice rather than a
generic default.

### Never run

`add -A`, `add .`, `commit -a`, `stash`, `reset --hard`, `checkout --`,
`restore`, `clean`, `commit --amend`, `push --force`.

Each destroys peer sessions' uncommitted work in a shared tree. On a
rejected push: fetch, report, escalate. Never force.

### Tests after the push

The user chose no gate, so nothing waits on the suite. To keep "then
report" from being decorative, the supervisor keeps the previous failure
set and blames a worker only for failures its commit **added**.

That baseline is not a nicety. At 18:20 on 2026-09-01 the suite was red
— `test_every_repo_path_named_in_docs_resolves`, because a peer had
deleted a docs subtree while CLAUDE.md still cited it. An absolute gate
would have blocked the whole fleet on another session's in-flight
refactor; a baseline diff correctly blames nobody.

### Orphan reporting, not janitoring

Each heartbeat reports the count of dirty paths claimed by no live
worker — peer sessions' work, and dead workers' leftovers. It reports.
It never commits them. The user chose sole-committer over tree-janitor
specifically so the supervisor never acts on changes it cannot attribute.

## Escalation

The supervisor rules on research governance under the authority
delegated 2026-08-29, and escalates only three classes: real money,
theory retirement (user-only per CLAUDE.md), and permission-layer blocks.

It also **relays bets**. A worker's floor run producing R1/R2/R3
candidates is the product, and a fleet that quietly logged them would
defeat the purpose. Relayed with ticker, side, ask, ranked edge, the
segment that earned it, and the `mark-taken` reminder CLAUDE.md requires.

## Known consequences

- **No gate plus auto-push means a broken commit reaches origin before a
  human reads it.** Chosen deliberately; the background test loop is the
  mitigation.
- **A push publishes peer sessions' commits too.** Every session commits
  to the same local `master`, so `push` is branch-wide by construction.
  Not avoidable without branch isolation, which was not chosen.
- **Everything is session-scoped.** Both `CronCreate` jobs and background
  subagents die when the supervisor's session exits, and recurring crons
  auto-expire after 7 days. There is no durable persistence available for
  either; the skill discloses this at startup rather than pretending.
- **Peers are not counted toward the three.** The supervisor targets
  three workers *it owns*, and reports other live sessions separately as
  context. With peers active this can mean five or more concurrent
  sessions on one tree and one database.

## Testing

`tests/test_conventions.py::test_every_repo_path_named_in_a_skill_resolves`
— every repo path any skill names must exist.

Scoped to the supervise skill in the first draft, then widened when a
probe showed only two unresolved citations across all eleven existing
skills, and both were legitimate: `tools/backtest.py`, which CLAUDE.md
names specifically to forbid it and which is already in
`_DELIBERATELY_ABSENT`, and propose-theory's `_TEMPLATE/THEORY.md`,
shorthand for a real file resolved relative to `theories/`. A guard that
covers every skill for the same cost as one is the better guard.

The gap it closes: `_DOC_FILES` covers only `README.md`, `CLAUDE.md` and
`tools/README.md`, so nothing watched `.claude/skills/` at all — a skill
citing a file it no longer ships stayed invisible until a session tried
to open it mid-run, with no way to recover the instruction. Same failure
mode `test_every_recorded_prompt_path_still_resolves` already guards for
judging prompts. The path regex allows a leading dot, unlike
`_PATH_LIKE`, so that a skill naming another skill's runtime file is
checked rather than silently skipped — which is the citation most worth
checking, since supervise reads `worker-brief.md` at spawn time.

Beyond that the skill is markdown and the real verification is a live
run.
