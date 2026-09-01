---
name: go-theory
description: Continue building out one existing theory — its tickets, its evidence, its sub-theories, its runbook. Invoked by go when the theory lane is claimed.
---

# go-theory — build out one theory

Invoked by `go` once you hold the theory lane with a `--focus`. **One
theory, this whole session.** You are that theory's expert for the
duration: its folder holds everything you need, and its `NOTES.md` is
where what you learn goes.

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

## 2. Pick the work

A ticket against this theory is the strongest signal — somebody wrote it
for whoever came next, and that is you. Absent one, in rough order of
value:

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
- **A version bump it has earned.** Adopting a proven sub-theory's rule,
  tightening a threshold. Default to `continues` so the evidence carries;
  `breaking` only when the old evidence genuinely does not apply, and say
  what makes that true.

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
python -m tools.cli tickets new --lane new-theory --slug <slug> ...
```

The one exception is a maintenance problem that makes progress **truly
impossible** — not slower, not uglier, impossible. File the ticket, say
in your report that you pivoted and why, then go fix it.

## 5. Finish

```bash
python -m tools.cli lane release <claim id> --summary "<what you did>"
```

Report: what you worked on and why, what the theory's evidence looks like
now (segment by segment — the parent and each sub-theory), what you
recorded, what tickets you filed, and anything for the user's ruling.
Then append Did / Learned / Next to `RESEARCH_LOG.md`.

**If the work is unfinished, leave a ticket for the next session** saying
exactly where you got to. That is the difference between a session that
made progress and a session that has to be repeated.
