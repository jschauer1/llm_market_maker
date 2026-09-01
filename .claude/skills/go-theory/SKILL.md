---
name: go-theory
description: Continue building out one existing theory — its tickets, its evidence, its sub-theories, its runbook. Invoked by go when the theory lane is claimed.
---

# go-theory — build out one theory until it yields or is exhausted

Invoked by `go` once you hold the theory lane with a `--focus`. **One
theory, this whole session.** You are that theory's expert for the
duration: its folder holds everything you need, and its `NOTES.md` is
where what you learn goes.

**You are not here to do one task. You are here to find an edge in this
theory**, and to keep going until you have one or until you can honestly
say the theory is exhausted. Finishing a ticket is not finishing the
session — when one avenue closes, take the next one. A report is a
checkpoint, never a finish line.

Persistence is the whole point of this lane. An edge is rarely the first
thing you try: the screen is usually close and the profitable part is
usually a subset, so the session that finds it is the one that kept
slicing after the headline number came back flat.

## 1. Read yourself in

```bash
python -m tools.cli tickets list --lane theory --theory <slug>
python -m tools.cli score report <slug>
python -m tools.cli slices report <slug>
```

Then the folder itself, in this order: `THEORY.md` (what it claims and
where it stands), `RUNBOOK.md` (how a run happens, including its
`## Sub-theories` section), `NOTES.md` (the lab notebook — dated,
append-only, and usually where the real state is).

**Read the whole notebook, not the tail.** A theory's dead ends are the
most expensive thing in its folder, and re-running one is the most common
way a session wastes itself.

## 2. Work it, and keep working it

A ticket against this theory is the strongest signal — somebody wrote it
for whoever came next, and that is you. Absent one, in rough order of
value. **This is a menu you work down, not a menu you pick one item
from:**

- **Evidence it does not have.** A claim with no measurement, or a
  sub-theory short of its gates, and history you can fetch → run the
  replay (`backtest-theory`). Settlements and backtests are the same
  evidence and the replay costs days instead of months; this is usually
  the answer.
- **A diagnosis it needs.** `under_review`, or a segment past its gates
  with a negative record → `score-theories` §5 turns "the numbers look
  bad" into a cause. Do not write the theory off: fees eating a real
  edge, inverted judgment over a sound screen, one profitable slice, and
  a too-small sample all look identical from outside.
- **A sub-theory worth registering.** A pattern the settled rows suggest
  is a hypothesis to pre-register (`cli slices register`), never an edge
  to bet on the data that suggested it. Registration starts the
  out-of-sample clock the same day.
- **A stage worth mechanising.** A stage-2 heuristic that has proven
  itself moves into stage-1 code — and bumps the version.
- **A version bump it has earned.** Tightening a threshold, mechanising a
  stage, changing what a prompt asks. Default to `continues` so the
  evidence carries; `breaking` only when the old evidence genuinely does
  not apply, and say what makes that true.

  **Not this:** folding a proven sub-theory's rule into the parent's
  screen. See below — it is the most common wrong turn on this lane.

Then go back to the top of the list and look again. Each thing you do
changes what the next-best thing is — a backtest that lands turns "no
evidence" into "a segment to slice", and a slice you register turns into
a gate to watch. **Work down the list until the list is empty**, not
until you have done one thing.

### Do not absorb a sub-theory into the theory

**This is the most common wrong turn on this lane**, and it looks like
progress: the theory is flat, one sub-theory is clearly working, so the
screen "should" be rewritten to produce that population — or the
predicate folded into the decision procedure and the version bumped.

**Don't.** A ready sub-theory is *already* the decision point for the
rows it matches. `ranking_segment` routes a matching candidate to the
slice's own score row and `promote` ranks it there, so **the bet placed
is identical either way.** There is nothing to promote it to.

What absorbing costs is real:

- **The control group.** The complement stops accruing, so nobody can
  ever check again whether the slice is still the part that works.
- **The out-of-sample bookkeeping.** `registered_at` and
  `mined_from_run_ids` are what make the slice's evidence trustworthy.
  Absorbed rows are ordinary parent rows carrying none of it.

If the sub-theory's evidence looks unavailable at the current version,
that is an **orphan**, and the fix is to relink the evidence chain —
`theories.reclassify_bump` on a bump recorded `breaking` under the old
default — not to adopt the rule. If the parent genuinely should not
exist, that is a retirement proposal for the user, after which the
sub-theory is proposed as its own theory (`propose-theory`), starting at
n=0 and citing its measurements as founding evidence.

Maintain the sub-theory. Report it. Do not merge it.

### A dead headline number is not a dead theory

When the aggregate comes back flat or negative, that is the *beginning*
of the analysis. Almost every real edge in this repo was a subset of
something that looked dead in total, and the interesting failures all
look identical from outside: a real edge eaten by fees, judgment
inverted on top of a sound screen, one profitable slice buried in a broad
screen, a sample too small to reject zero.

So before you conclude there is nothing here, **mine the settled rows**:
slice by side, price band, entry timing, sub-family, volume, confidence
bucket, and whatever structure the thesis itself implies. With honest
p-values, event-clustered checks, and awareness that you are running many
comparisons.

`mention_family` is the worked example twice over. Its aggregate was dead
— −1.53 net over n=3,441 — and the slicing pass still found a real,
mechanism-backed asymmetry (NO favorites at 0.90+ underpriced, +2.25 net,
stable across every partition) that became a registered sub-theory. The
headline number would have ended the session; the slicing pass is what
found the edge.

The discipline that keeps this honest: a pattern found post-hoc is a
**hypothesis to pre-register**, never an edge to bet on the data that
suggested it. Register it as a slice (`cli slices register`) and the
out-of-sample clock starts the same day. And a pattern that fails a small
sample is *unconfirmed*, not disproven — say which one you mean.

## 3. Do it, and record it as you go

- **`NOTES.md` gets the dated entry** — raw, append-only, including what
  failed. Findings that exist only in this conversation die with it.
- **`THEORY.md` changes only** when the claim, the procedure, or the
  status changes.
- **`RESEARCH_LOG.md` gets a headline and a pointer**, never a copy — an
  entry is earned by a fact that changes how a session that never touched
  this theory would act.

<!-- rule: notes-theory-log-split (moved from CLAUDE.md § What lives in a theory, 2026-08-29; rehomed from go/ to go-theory/ 2026-09-01 when go became a dispatcher) -->
`RESEARCH_LOG.md` stays cross-theory: a log entry is earned by a fact that
changes how a session that never touched this theory would act — a
mechanism, a ruling, a precedent, a constraint, a breakthrough, a
correction. A result inside one theory is a headline and a pointer into
its `NOTES.md`, never a copy. This was forward-only from 2026-08-25 and
produced 5,838 words of copies anyway, because the log was what got read;
it binds now because `state` is.
<!-- /rule -->
- **Any decision-procedure change bumps the version**, prompts included,
  and any prompt lives in `prompts/` on disk where a diff can review it.
- **Record while you spend.** Batched judgment writes each batch's result
  before dispatching the next, so a session that dies mid-run re-judges
  nothing.

## 4. Stay in the lane

**Do not pivot.** Another theory looking interesting, a tool that annoys
you, an idea for a new thesis — all of these are tickets:

```bash
python -m tools.cli tickets new --lane maintenance --slug <slug> \
    --title "<one line>" --body "<what to do>" --session <you>
```

### An idea for a theory: is it a subset of the one you are on?

Working a theory is the most productive place to have this idea, and it
happens constantly — the data suggests something the current thesis does
not cover. **One question decides what you do with it**, and both answers
keep you in your lane:

**Is it a subset of the theory you are working — the same screen, the
same population, re-weighted?**

- **Yes → it is a sub-theory.** Register it as a slice right now
  (`cli slices register`) with its mechanism and its provenance. It is
  *your* work, in *this* lane, and registering it starts its
  out-of-sample clock today rather than whenever someone gets to it.
- **No → it is a new theory. File a `new-theory` ticket.** Anything
  needing its own screen, its own entry rule, or a different population
  is a different theory, whatever it borrowed from this one. That is the
  same line CLAUDE.md draws between a sub-theory and a sibling theory —
  `no_side_premium` split off from `mention_family` exactly here.

```bash
python -m tools.cli tickets new --lane new-theory --slug <slug> \
    --title "<the thesis in one line>" --session <you> \
    --body "<the mechanism, what suggested it, and why it needs its own screen>"
python -m tools.cli ideas record <slug> "<title>" --description "<the thesis>"
```

**File both.** The ticket is the work; the registry entry is the memory
that stops someone re-proposing it in three weeks, and it deduplicates
across theories in a way a ticket does not.

Write the ticket while the idea is fresh and say *what suggested it* —
"the settled rows at 0.90+ behaved differently" is the part that will be
impossible to reconstruct later, and it is the part that makes the ticket
worth picking up.

Then go back to your theory. The idea is safe now; that is the point of
writing it down.

The one exception is a maintenance problem that makes progress **truly
impossible** — not slower, not uglier, impossible. File the ticket, say
in your report that you pivoted and why, then go fix it.

## 5. Stopping — and the bar for it

There are exactly two honest reasons to stop working this theory.

**You found an edge**, and it is recorded, evidenced and reportable. Say
so, and say which segment carries it.

**You exhausted it** — which is a high bar, not a feeling. Before you may
claim it, all of these must be true:

- Every ticket against this theory is closed, or blocked on something
  outside this lane and ticketed accordingly.
- The evidence it could have, it has. If history is fetchable and the
  replay has not been run, **you are not finished** — that is days of
  calendar time bought in an afternoon, and it is usually the answer.
- The settled rows have actually been mined, not glanced at: sliced by
  side, price band, timing, sub-family, volume, and the structure the
  thesis implies.
- Every pattern that survived that pass is registered as a sub-theory, so
  its out-of-sample clock is running.
- If the numbers are bad, you have a *cause* rather than a verdict —
  `score-theories` §5 turns "the numbers look bad" into fees, or inverted
  judgment, or a subset, or an inadequate sample.

"I ran the thing and it did not work" is not exhaustion. "I could not
think of anything else to try" is not exhaustion either — write down what
you did try, then try the next thing on the list.

**When a theory really is exhausted, that is a finding and it gets
recorded**, not a shrug: a dated `NOTES.md` entry saying what was ruled
out and how, and — if the evidence genuinely says the thesis is dead —
`theories propose-retirement <id> --rationale "<what you diagnosed and
what you ruled out>"`. Retiring is the user's call, never yours; you
diagnose and put it in front of them.

Running out of session before running out of theory is the third case,
and it is normal. **Leave a ticket saying exactly where you got to and
what you would do next** — that is the difference between a session that
made progress and a session that has to be repeated.

## 6. Close out

```bash
python -m tools.cli lane release <claim id> --summary "<what you did>"
```

Report: what you worked on and why, everything you tried including what
failed, what the theory's evidence looks like now (segment by segment —
the parent and each sub-theory), what you recorded, what tickets you
filed, and anything for the user's ruling. Then append Did / Learned /
Next to `RESEARCH_LOG.md`.

**Report what did not work as carefully as what did.** The next session
on this theory will otherwise spend its first hour re-running your dead
ends, and that is the most common way this lane wastes itself.
