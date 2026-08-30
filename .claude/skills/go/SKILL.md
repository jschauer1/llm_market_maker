---
name: go
description: Run an autonomous research session — orient on current state, choose the highest-value work, do it, log it, and report. Use when the user says "go", or asks you to work on finding edge without specifying what to do.
---

# Autonomous Research Session

You are the researcher. Nobody is going to tell you what to test.

**The session has six phases. Phases 0–3 are the floor** — the same every
session, completed **and reported** before any phase-4 work begins: no
menu item starts until every running theory has been run in whole and
every bet it produced has been recorded and promoted. Phase 4 is where
the session earns more than its floor. Two rules bind throughout: record
everything (§2), and never ask the user a question — escalate and keep
working (§7).

| phase | what | consistency surface |
|---|---|---|
| 0 | Peers | this file's protocol |
| 1 | Orient | `get_board(force=True)`, `state`, the queue |
| 2 | The floor: settle, then run every theory | each theory's `RUNBOOK.md` |
| 3 | Promote | `docs/promotion-key.md` + `cli promote` |
| 4 | Value menu loop | this file's §4 |
| 5 | Log & report | §5 and the §6 report contract |

## 0. Peers

Before the board pull, run `ListAgents`. No peer sessions working this
repo → note "no peers" for the floor report and continue.

Peers found → send each **one orientation message**: who you are, that
you are starting a go floor, and which floor items you intend to own
(the board pull, the settle run, the per-theory list). Ask for their
claims by return message. Items a peer claims are theirs — verify
completion through `state` and the freshness check instead of redoing
them; unclaimed items are yours. No reply after a short wait → proceed
with everything, say so in the report, and re-check before any expensive
duplicate (the 30-minute force floor already makes the board pull
collision-safe — extend that shape: one owner per floor item, everyone
else reads the shared result).

This orientation message is the **only** unprompted peer message this
skill authorizes (user carve-out, 2026-08-30, to the standing
no-unprompted-messaging rule). Anything further follows the peer's
reply. Four sessions collided on 2026-08-30 and a defective duplicate
run had to be quarantined; this phase exists so that never repeats.

## 1. Orient (always)

**First, pull a fresh Kalshi board.** This is not optional, and it comes
before every local-state query below:

```python
from tools import board as board_tool, db

conn = db.connect(); db.init_db(conn)
board = board_tool.get_board(conn, force=True)   # ~100k markets, ~13s
```

`force=True` here and **nowhere else**: this is the session's one
deliberate refresh (skip it only when phase 0 assigned the pull to a
peer — then `get_board(conn)` reads their pull). Every number the rest
of the session produces is only as current as this fetch. The pull is
snapshotted automatically, so it also feeds the first-party price
history the project accrues.

**Every later call in the session — and every theory — uses
`board_tool.get_board(conn)` with no `force`**, which reuses this pull
instead of re-walking the feed. One session, one board. Enforced now by
`tests/test_db_discipline.py`, not just prose.

Then read local state:

```bash
python -m tools.cli state
python -m tools.cli theories list --running   # testing + active + under_review
python -m tools.cli theories pending-retirement
python -m tools.cli ideas revisitable
```

Anything `pending-retirement` returns is a decision **waiting on the
user** — carry it into §6.4 every session until they rule.

**Then work the queue.** Endorsed positions still open and still
`user_action='untouched'` are bets this system recommended and nobody
has resolved:

```python
from tools import db, ledger

conn = db.connect()
queued = [r for r in ledger.list_opportunities(
              conn, disposition="endorsed", unsettled_only=True)
          if (r["user_action"] or "untouched") == "untouched"]
```

**Use `unsettled_only=True`, not a `settled_at` field on the row** — the
listing has never returned one; filtering on it silently counted settled
positions as outstanding until 2026-08-29.

A queued bet **decays**. For each: check age against close time; re-run
it through `python -m tools.cli promote <id>` (which re-quotes) rather
than eyeballing whether the edge held — a queued bet that no longer
clears its rung is closed out as stale in §6.5, never silently
re-endorsed; and chase the disposition (`mark-taken … taken|skipped`) so
`roi_taken` stops being `null`.

## 2. The floor: settle, then run every theory — in whole

**This is the part of `go` that is not a choice.** The user must be able
to say `go`, walk away, and come back knowing every running theory saw
today's board through its complete procedure. A session that did
something clever while the theories went un-run has failed its one
standing obligation.

Two halves, in order:

1. **Settle and score.** Run `score-theories` to settle what resolved,
   then persist each running theory's scores:
   `python -m tools.cli score report <id> --save` — `--save` is what
   keeps `state` EVIDENCE rendering reality instead of an empty table.
2. **Run every theory whose status is `testing`, `active`, or
   `under_review` — by its RUNBOOK.md, through every stage.** Each
   running theory carries a standardized runbook (Stages / Run / Record
   / Report / Skip — conventions-tested). "Ran the theory" means every
   stage in its Stages table: a judgment theory whose screen ran but
   whose judgment stages did not has **not** run — if a stage is
   blocked (judge budget, API down), the floor report names the stage
   and why, and the theory counts as blocked, not run. `under_review`
   runs too: pulling a theory you suspect is broken guarantees you never
   learn whether it was broken or merely unlucky.

**Record everything.** Every candidate a theory's procedure produces is
recorded — probation, `under_review`, n=0, all of it, rejections
included. Recording and recommending are different acts: the ledger
takes everything (it is how unproven theories accrue the evidence that
would prove them, and how rejections stay a control group); the report
takes only what §3 promotes. Never decline to record a bet because the
theory looks weak, and never surface one because it looks strong — both
directions of that call belong to the key.

**Skip a theory only when it already ran today *at its current
version*** (per theory and per version — a version bump means a
different theory):

```python
from tools import db
conn = db.connect()
current = {r["id"]: r["version"] for r in conn.execute(
    "SELECT id, version FROM theories WHERE status IN "
    "('testing','active','under_review')")}
seen = {(r["theory_id"], r["theory_version"]): r["last_day"]
        for r in conn.execute(
            "SELECT theory_id, theory_version, MAX(DATE(last_seen_at)) AS last_day "
            "FROM opportunities WHERE run_mode = 'live' "
            "GROUP BY theory_id, theory_version")}
today = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
for tid, ver in sorted(current.items()):
    day = seen.get((tid, ver))
    print(f"{tid} v{ver}: {'current' if day == today else f'STALE (last {day})'}")
```

**One caveat this check cannot cover: a scan that legitimately found
nothing writes no rows**, so it prints `STALE (last None)` either way.
Resolve that from the session log, not the ledger — and when a theory
runs clean today, say so explicitly ("`structural_arb` v4: ran per
RUNBOOK, 0 candidates") so the next session doesn't redo or wrongly
trust the work. `STALE` is a prompt to check the log; re-run only if the
log does not say the theory ran clean today at its current version.

## 3. Promote — the key decides what the user is told

Every bet in the report cites a rung of `docs/promotion-key.md`; every
bet withheld is withheld by one. **You never decide report-worthiness;
you cite it.** The rungs are mechanical and code evaluates them:

```bash
python -m tools.cli promote --run <run_id>     # per theory run; re-quotes
python -m tools.cli promote <opportunity_id>   # one candidate
```

The output gives each candidate its rung (R1 RECOMMENDED, R2 RISKLESS,
R3 PROVISIONAL, R4 ACCRUING, R5 MEASURED-AGAINST, R6 CONTROL), the
segment that ranked it (slice / complement / aggregate — the sub-theory
partition, applied for you), every criterion checked, and any
**escalations** — above all *orphaned evidence*: a slice proven out of
sample at a prior version with no bet path at the current one. Orphans
go in §6.4 every session until the user rules on adoption.

Three rules the key binds you to:

- **R1/R2/R3 go in the Bets table; R4/R5/R6 never do.** R3 is the
  deliberate "close to an edge" tier — report it, labeled with exactly
  what is missing. R5 is suppressed *even when today's claim looks
  good*: the measured record outranks the claim.
- **Disagree by dissent, not override.** If a rung's answer looks wrong
  for a candidate, report the rung's verdict *and* your dissent as a
  proposed key amendment in §6.4. Never move the candidate yourself.
- **A gap in the key** (a candidate no rung fits, a criterion that reads
  two ways) is itself a finding: report it in §6.4 with your
  best-judgment label clearly marked provisional.

Endorse/reject on a judgment theory's researched candidates stays your
call (that is stage 2, upstream of the key); `ledger.interpret` first,
then promote.

## 4. Then work the value list — item by item

The floor is done and reported; this is where the session earns more.
**This step is a loop, not a single pick**: choose the top item, do it,
report it (§6), then come back and choose the next. The standing menu,
roughly highest-leverage first:

- **Research a queued or freshly-screened candidate** into a real
  recommendation (`find-edge`) — the deeper pass on what the floor
  surfaced.
- **Build a queued theory.** Researched, implementable specs sit in
  [docs/superpowers/specs/theories/](../../../docs/superpowers/specs/theories/)
  — far more are specced than built. Check `ideas search "<slug>"` and
  the build tracker in
  [docs/superpowers/plans/theories/](../../../docs/superpowers/plans/theories/)
  first, then `propose-theory`.
- **Backtest** a theory running on claims rather than evidence
  (`backtest-theory`).
- **Propose a new theory** (`propose-theory`) — from a market pattern, a
  coverage gap, or a recurring `user_reason` divergence.
- **Revisit a parked or dead idea** whose `revisit_after` condition may
  now be met.
- **Tighten a theory** — migrate a proven stage-2 heuristic into stage-1
  code (bump the version), or promote a theory-local tool with multiple
  callers.
- **Diagnose an `under_review` or R5-flagged theory** — often the
  highest-value work on the board; the checklist in `score-theories` §5
  turns "numbers look bad" into an answer.

**Prefer work that changes a decision.** If every active theory is
unproven, another scan adds unproven suggestions while a backtest adds
evidence. State which item you picked and why in one line — then, when
it is done and reported, **pick up the next one**. One item is a busy
day's floor, not the target (user ruling 2026-08-27).

The loop has exactly two exits:

- **Nothing left that changes a decision.** Every remaining item would
  be busywork. Say so and end; an empty menu honestly reported beats a
  padded one.
- **Everything remaining is blocked on the user.** Not "a question came
  up" — §7 handles questions. Only when every remaining thread needs a
  ruling first may the session end, with §6.4 carrying each one.

Ending for any other reason — "one thing is done", "the report is
written", "the session feels long" — is the failure mode this loop
exists to prevent: a report is a checkpoint, never a finish line.

## 4a. How much to delegate

**Your call, every time.** Doing the work yourself is a perfectly good
session; subagents are for genuinely wide work (several theories to
diagnose, a batch of candidates to judge), never a target.

**Numbers come from code, not from a model** — `score report`, `promote`,
`bucket_rates` print exact figures; asking a model to read them is the
expensive way to get them subtly wrong. **If you delegate, findings go
to disk before they reach you** — a per-theory diagnosis lands in that
theory's `NOTES.md` as a dated entry; reasoning that exists only in a
subagent's reply dies with the session. A diagnosing subagent is *not*
in any theory's decision path and gets **no** `judgment_runs` row —
provenance records what judged a bet, nothing else.

## 5. Log it

Append to `RESEARCH_LOG.md`:

```markdown
## YYYY-MM-DD — <one-line summary>

**Did:** what you actually did.
**Learned:** what you now know that you didn't.
**Next:** what is worth picking up next session.
```

Theory-specific findings go in that theory's `NOTES.md` — dated, raw,
append-only. `THEORY.md` changes only when the claim, the procedure, or
the status changes.

<!-- rule: notes-theory-log-split (moved from CLAUDE.md § What lives in a theory, 2026-08-29) -->
`RESEARCH_LOG.md` stays cross-theory: a log entry is earned by a fact that
changes how a session that never touched this theory would act — a
mechanism, a ruling, a precedent, a constraint, a breakthrough, a
correction. A result inside one theory is a headline and a pointer into
its `NOTES.md`, never a copy. This was forward-only from 2026-08-25 and
produced 5,838 words of copies anyway, because the log was what got read;
it binds now because `state` is.
<!-- /rule -->

## 6. Report — fixed sections, fixed order, every session

A report lands after the floor (phases 0–3) and again after every §4
item. The floor report always carries sections 1–5; a §4 item's report
needs only what it found plus updates to 4 and 5. The shape never
varies, so the user learns it once:

1. **Floor** — peers found and the division of labor; one line per
   running theory in a fixed shape: `<id> v<n> — ran per RUNBOOK
   (<stages>), <candidates> recorded, gate removed <counts by category>`
   or `blocked at <stage>: <why>` or `skipped: <skip-condition>`; what
   settled and how scores moved.
2. **Bets** — one table, grouped R1 / R2 / R3, citing the key version:
   rung, ticker, side, today's ask, claimed net edge, ranked edge,
   segment, n/n_days behind it, edge basis, theory, bucket +
   interpretation (judgment theories), suggested size. R2 baskets list
   every leg with its ask and the verify-every-leg warning. An empty
   table is a valid, honest table.
3. **Activity** — R4 counts per theory (top few each, by the theory's
   own stage-1 ordering where one exists), R5 warnings by name, R6
   counts. This is where "recorded but not recommended" lives — visible
   without being endorsed.
4. **For your ruling** — everything escalated instead of asked: pending
   retirements (with the diagnosis), orphaned evidence, key gaps and
   dissents, permission-blocked actions. Carried every session until
   ruled; a standing proposal nobody mentions is not a suggestion to
   anyone.
5. **Queue** — endorsed-untouched-unsettled positions re-promoted at
   today's ask: which still stand (the *same* position, not a
   re-endorsement), which you closed as stale. Then the mark-taken asks
   **by id** — "did you take 9204?" gets acted on; "mark whatever you
   did" does not. Remind the user:
   `python -m tools.cli opportunities mark-taken <id> taken --theory
   <slug> --size <N> --reason "<why>"` (or `skipped`). Until a bet is
   marked, `roi_taken` stays `null` and the divergence signal
   `compare-theories` mines never accumulates.

## 7. Never ask — escalate and continue

An autonomous session **does not stop to ask the user anything.** In
order:

1. **A structural surface answers it** — the key, a runbook, a skill, a
   ruling (`cli rulings list`), CLAUDE.md → take that answer and cite
   it.
2. **Reversible, in scope, no surface answers it** → use your judgment:
   decide, act, record the decision and reasoning in the log. If the
   gap will recur, propose the amendment in §6.4.
3. **User-only** — money, retirements, destructive or irreversible
   operations, permission-layer blocks → write it to §6.4 **and keep
   working** on everything the blocked item does not gate.

"I have a question" is never an exit and never a pause. The question
goes in §6.4; the session takes the next item.

## Rules

- **The floor (phases 0–3) completes and is reported before any §4
  work.** If something blocks it — an API down, a theory erroring — say
  so plainly in the floor report rather than quietly doing other work.
- Never present unresearched screen output as a recommended bet — the
  rung system encodes this: a judgment theory's candidate cannot pass
  R4 without stage-2 endorsement, and a mechanical theory's
  (`edge_basis='model'`) needs none.
- **Never write off an underperforming theory.** R5 and `under_review`
  are diagnosis queues (`score-theories` §5), not verdicts — fees eating
  a real edge, inverted judgment over a sound screen, one profitable
  slice, and a too-small sample all look identical from outside.
- **Retiring is the user's decision, not yours.** Diagnose, then
  `theories propose-retirement <id> --rationale "..."`, then §6.4.
- Search the idea registry before proposing anything new.
- **A theory that ran and found nothing must say so in the log** — the
  ledger records candidates, not scans.
- **A report is a checkpoint, never a finish line.**
- **DB discipline** (enforced by `tests/test_db_discipline.py`; full
  conventions in `tools/README.md`): one board per session through
  `get_board` — never `markets.list_open()`, never a second `force`;
  which run decided something is answered by `opportunity_attempts`,
  never `opportunities.run_id` (first-seer trap, bitten three times);
  open-position queries use `unsettled_only=True`; every snapshot
  payload read goes through `snapshot.payload_text`; back up the ledger
  before settling or migrating (`db backup`, cadence in
  `tools/README.md`); ledger DELETEs are user-only.
