---
name: go-floor
description: Run today's floor — settle and score, run every theory and its sub-theories against today's board, and report. Invoked by go when the floor lane is claimed.
---

# go-floor — the daily floor

Invoked by `go` once you hold the floor claim. **If you do not hold it,
you are in the wrong skill** — `floor claim` is what makes this run
exactly once a day, and a second unclaimed run is the collision it
exists to prevent.

This lane is **focused**. Everything you notice that is not the floor
gets a ticket, not your attention:

```bash
python -m tools.cli tickets new --lane maintenance --slug <slug> \
    --title "<one line>" --body "<what to do>" --session <you>
```

The floor sees every theory's output in one pass, which makes it the best
place in the repo to notice a thesis nobody has proposed — and the worst
place to chase one. File it: `--lane new-theory` for a thesis needing its
own screen or population, `--lane theory --theory <slug>` when it is a
subset of an existing theory's own output. Add `ideas record` alongside,
so it cannot be re-proposed in three weeks. Then finish the floor.

The floor's own procedure follows. It is fixed: the user must be able to
say `go`, walk away, and come back knowing every running theory saw
today's board through its complete procedure.

## 1. Rebuild the board

```python
from tools import board as board_tool, db

conn = db.connect(); db.init_db(conn)
board = board_tool.get_board(conn, force=True)   # ~100k markets, ~13s
```

`force=True` **only here, and only with the claim in hand.** Every other
call this session — and every theory, and every subagent — uses
`board_tool.get_board(conn)` with no force, which reuses this pull. One
session, one board; every number downstream is only as current as this
fetch. Enforced by `tests/test_db_discipline.py`.

Sessions in every other lane never force. Plain `get_board(conn)` reuses
this pull for four hours — two boards means two sessions reasoning over
different prices.

## 2. Settle and score — the theory *and* each sub-theory

Evidence does not exist until settlements land and scores are written.

1. Run `score-theories` to settle what resolved.
2. Persist scores: `python -m tools.cli score report <id> --save`.

**A sub-theory is a theory run over a subset of another theory's data,
and its evidence is its own.** It accrues separately, clears its own
gates, and can be strongly supported while the theory around it is flat
or negative. So scoring is not one number per theory: `--save` writes one
row per **segment** — `aggregate`, `slice:<slug>` for each sub-theory,
and `complement` (what is left once every ready sub-theory is removed,
scored separately so the remainder never borrows what a subset earned).

`state`'s EVIDENCE panel then shows sub-theories under their parent:

```
no_side_premium     edge_net -7.54   n 66  clusters 55
    sub: cell-a-no-favorite    edge_net  7.02  n 2   clusters 1
    sub: cell-b-yes-avoid      edge_net -8.00  n 64  clusters 54
```

A negative parent with a positive subset is not a contradiction to
explain away — it is the normal case this partition exists for.

## 3. Run every theory, explicitly

**Get your work list from the checklist, not from the theory table:**

```bash
python -m tools.cli floor checklist
```

```
  calibration_harvest
  insider_judgment
    sub: strong-moderate-no        <- this is a line in your report too
  no_side_premium
    sub: cell-a-no-favorite
    sub: cell-b-yes-avoid
  structural_arb
```

**Every row on that list gets run, and every row gets a line in the
report.** Sub-theories included, and that is not a nicety: a sub-theory
IS a theory by this repo's definition, its evidence is its own, and it
can be the best-evidenced thing in the repo while its parent reads
breakeven. `insider_judgment`'s `strong-moderate-no` is exactly that, and
a floor report that covered all four theories carefully and never
mentioned it (2026-09-01) missed the single most important number on the
board. `floor complete` now refuses a report that leaves one out.

**Run every theory whose status is `testing`, `active`, or `under_review`
— by its `RUNBOOK.md`, through every stage.**

"Ran the theory" means every row of its runbook's Stages table. A
judgment theory whose screen ran but whose judgment stages did not has
**not** run: name the stage and why, and count it blocked, not run.
`under_review` runs too — pulling a theory you suspect is broken
guarantees you never learn whether it was broken or merely unlucky.

**Delegating is allowed and encouraged when the list is long.** Give one
theory to one Sonnet subagent, hand it the theory's folder and its
RUNBOOK, and have it run every stage and report back. Rules that make
delegation safe:

- **Findings go to disk before they reach you** — each subagent writes
  its own dated entry to that theory's `NOTES.md`. Reasoning that exists
  only in a reply dies with the session.
- **Numbers come from code, not from a model.** `score report`,
  `promote`, `bucket_rates` print exact figures; asking a model to read
  them is the expensive way to get them subtly wrong.
- **Subagents share your board** — `get_board(conn)`, never a force.
- A subagent running a theory *is* in that theory's decision path, so any
  LLM judging stage it performs records provenance exactly as you would.
  A subagent merely *diagnosing* is not, and records none.

**Record everything.** Every candidate a theory's procedure produces gets
recorded — probation theories, `under_review` theories, n=0 theories,
rejections included. Recording and reporting are different acts: the
ledger takes everything, and step 4 decides what the user is shown. Never
decline to record because a theory looks weak, and never report because
one looks strong.

**A theory that runs clean says so.** A scan that legitimately finds
nothing writes no rows, so silence is indistinguishable from not having
run. State it: "`structural_arb` v4: ran per RUNBOOK, 0 candidates."

**Running a theory includes evaluating its sub-theories.** Every runbook
carries a `## Sub-theories` section naming them — or saying none are
registered, which is itself a checked fact rather than an omission. For
each one:

```bash
python -m tools.cli slices report <theory>
```

Report where its evidence stands against its own gates and whether it
produced anything today. **A sub-theory past its gates with a positive
record produces a reportable bet even when its parent theory has none** —
that is the whole reason it is scored separately, and the case is live:
`insider_judgment`'s screen is breakeven while its `strong-moderate-no`
subset is the best-evidenced result in the repo.

A sub-theory proven at a prior theory version with no bet path at the
current one is **orphaned evidence**. `promote` raises it mechanically
and it goes to "For your ruling" every session until it is resolved.

**An orphan is a versioning fact, and the fix is to relink the evidence
chain** — almost always a bump recorded `breaking` under the old
default, correctable with `theories.reclassify_bump`, after which the
sub-theory is ready at the current version and routes its own bets with
nothing else changed. It is **never** fixed by folding the sub-theory's
rule into the parent's screen: that buys no different bet and costs the
complement and the out-of-sample split (CLAUDE.md, "A sub-theory is
maintained, not absorbed"). Relinking a chain is a governance change, so
report it rather than doing it from this lane.

Never rank a current-version candidate on a prior version's record
without saying so explicitly.

## 4. Report the results

Write **`user_reports/<YYYY-MM-DD>/README.md`** — one directory per day —
and summarize it in the terminal with the path. Put anything the report
cites but should not inline (a wide funnel table, a judged payload, a
subagent's raw output) in that same directory beside it; most days there
will be nothing but the README, which is the expected case.

Five sections, in this order. **The order is what the user acts on
first, not what happened first** — the floor's own receipt comes last,
because it is the least actionable thing in the file.
`user_reports/README.md` carries the same contract for the reader.

1. Bets
2. Theories — what each did, and why nothing came of it
3. For your ruling
4. Queue
5. Floor record

Sections 1 and 2 are below in full; 3 and 4 follow them; section 5 is the
receipt — which theories ran through which stages, what the gates removed
by category, what settled, and how the scores moved.

#### 1. Bets — the ones that are well evidenced

A bet is reported when three things hold together:

1. **Theory success or sub-theory success** — the segment it ranks on has
   a positive net calibration edge.
2. **Proper data behind it** — that segment is past its evidence gates
   (at least 10 event clusters and 5 settlement days; never fewer than 3
   settlement days, which carry no usable error bar).
3. **The edge survives today** — positive net edge recomputed at today's
   ask, and executable at that ask.

**Backtested evidence counts the same as forward evidence.** A tier A or
tier B backtest that measured an edge is evidence exactly as a run of
live settlements is — for a sub-theory as much as for a whole theory —
and it feeds the gates in step 2 on the same terms. Never describe a
backtested edge as weaker for being backtested; sample size is already
priced into the t-statistic and into credibility, and charging a second
time for it teaches theories to avoid the honest instrument.

Two exclusions, and only these two. **Tier C never counts** — a model
judging markets whose outcomes it may remember measures recall, not
edge. And **rows a sub-theory was mined from never vouch for it** — a
pattern found by slicing settled data is a hypothesis to register and
then test, not a result; `mention_family`'s +5.48 became −1.53 on full
coverage. Everything else a backtest measured is evidence.

`python -m tools.cli promote --run <run_id>` computes all three and
returns a rung. **R1 RECOMMENDED, R2 RISKLESS and R3 PROVISIONAL are the
reportable bets** (R3 labeled with exactly what is missing). R4, R5 and
R6 are not bets and go in the second section. You never decide
report-worthiness — you cite the rung. Disagree by dissent: report the
rung's verdict *and* your objection as a proposed key amendment, never by
moving the candidate yourself.

For each bet: ticker, side, today's ask, claimed net edge, ranked edge,
**the segment that earned it**, n and settlement days behind it, edge
basis, theory, and suggested size. A basket lists every leg with its own
ask and the instruction to verify all legs before entering.

**A sub-theory that succeeds is evidence exactly as much as a theory
is.** A registered slice past its gates ranks on its own record, and a
bet resting on one is reported on the same footing as a bet resting on
the whole theory — not hedged, not discounted, not called provisional
because the parent theory is flat. State which segment carried it, so
"the slice earned this" is visible rather than implied. The converse
binds too: the remainder never borrows what a slice earned.

#### 2. Theories — what each did, and why nothing came of it

One short section per running theory, in plain language: **what it did
today and why nothing came of it.** This is the floor's main output on
most days, and it is what makes a flat day informative instead of silent.

Say which of these it was:

- **Found nothing** — the screen ran clean, no candidates. Say what the
  screen was looking for and, if a gate dropped candidates, how many and
  in what categories.
- **Found candidates, not yet evidenced** (R4) — how many, and what they
  are waiting on: settlements, settlement days, a judging stage that has
  not run.
- **Measured against** (R5) — the segment is past its gates with a
  negative record. Say so plainly; this is a diagnosis queue, not a
  verdict. Fees eating a real edge, inverted judgment over a sound
  screen, and one profitable slice inside a broad screen all look
  identical from outside.
- **Blocked** — which stage, and why.

**Every sub-theory gets its own line, indented under its parent.** Not
"if it has a record" — every one on the checklist, every day. A
sub-theory *is* a theory here: its evidence is its own, it clears its own
gates, and it is routinely the most important number on the board while
its parent reads flat. `floor complete` refuses a report that omits one.

The shape, so nothing has to be invented:

```markdown
### insider_judgment v5
Ran all five stages. 15 events judged: 2 strong, 4 moderate, 9 weak.
Rungs: R1 2, R5 4, R6 9. (v5 removed the final-review stage — a bucket
is the interpretation and `promote` says what it is worth. Do not
endorse or reject this theory's rows by hand.)

- **strong-moderate-no** — READY, and the best-evidenced result in the
  repo: +3.76 net over n=328, 90 event clusters, 44 settlement days,
  pooled v1–v4 (314 rows replayed). It is already the decision point for
  strong/moderate NO rows; nothing needs adopting. Produced no candidate
  today because [reason].

### no_side_premium v1
Recorded 63. Aggregate moved −7.54 → −0.16 as n went 66 → 129.

- **cell-b-yes-avoid** — READY at −0.98, still confirming its avoid
  claim, but far weaker than the −3.9 it was written against.
- **cell-a-no-favorite** — accruing, n=2. Nothing yet.
```

Say for each: what it claims, where its evidence stands **against its own
gates**, and whether it produced anything today. A ready sub-theory needs
no adoption to drive a bet — it is already the decision point for the rows
it matches, and that is what its line should say.

A slice proven at a prior version with no bet path at the current one is
*orphaned evidence* — the evaluator raises it, and it goes to the ruling
section as a chain to relink, never as a rule to adopt.

#### 3. For your ruling

Everything escalated instead of asked: pending retirements with their
diagnosis, orphaned evidence, gaps in the promotion key,
permission-blocked actions. **Carried every day until the user rules** —
a standing proposal nobody mentions is not a proposal.

#### 4. Queue

Endorsed positions still open and untouched, re-quoted at today's ask:
which still stand (the *same* position, not a re-endorsement), which you
closed as stale. Then ask about each **by id**, so the user can answer in
one line:

`python -m tools.cli opportunities mark-taken <id> taken --theory <slug> --size <N> --reason "<why>"`

(or `skipped`). Until a bet is marked, `roi_taken` stays `null` and the
divergence signal never accumulates.

#### 5. Floor record

The receipt, and last on purpose. One line per running theory in a fixed
shape — `<id> v<n> — ran per RUNBOOK (<stages>), <n> recorded, gate
removed <counts by category>`, or `blocked at <stage>: <why>`, or
`skipped: <condition>`. Then what settled and how the scores moved.

**The report is a deliverable, not the record.** The audit trail stays in
the database, each theory's `NOTES.md`, and `RESEARCH_LOG.md`; a report
is regenerable from the ledger, and where the two disagree the database
is right.

## 5. Close the claim, and stop

Check the report covers everything before you close:

```bash
python -m tools.cli floor check-report user_reports/<YYYY-MM-DD>/README.md
python -m tools.cli floor complete <claim id> \
    --report user_reports/<YYYY-MM-DD>/README.md \
    --summary "<one line>"
```

`complete` **refuses a report that omits a running theory or a registered
sub-theory**, and names what is missing. That is not a formality to route
around: the omission it catches is a real one that already happened, and
the fix is always to write the missing line rather than to skip the
check. `check-report` asks the same question early, so you find out while
you are still writing.

This is what starts the 24-hour clock and tells every later session the
floor is done. **Do it as soon as the report lands** — an uncompleted
claim expires after four hours and invites a duplicate run.

**Then the session is over.** A floor session does the floor and nothing
else: it does not pick up a research item, does not chase an interesting
thread the run surfaced, does not "just check one thing" afterward. Write
what the run suggested into `RESEARCH_LOG.md` under **Next** and let the
next session pick it up with a clear head.

If the floor was blocked partway, say so plainly in the report and
**leave the claim open** — do not complete a floor that did not run. The
lease expires on its own and the next session takes it over, which is the
correct outcome: the guarantee is unmet, and the record should say so.
