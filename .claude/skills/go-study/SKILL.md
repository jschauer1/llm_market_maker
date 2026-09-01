---
name: go-study
description: Run or extend one study — a measurement that answers a question and never bets. Use when a claim needs settling before anyone builds on it, or a study is in flight and needs finishing. Invoked by go when the study lane is claimed.
---

# go-study — settle a question with a measurement

Invoked by `go` once you hold the study lane. **One study, this whole
session.**

**A study is a measurement that answers a question. It never bets.** No
`record_opportunity`, no ticker, no ledger row, no score — if what you
are building produces a bet, you are in the wrong lane and it needs a
spec (`go-new-theory`). `studies/README.md` has the full definition and
the rules; read it before starting.

## Why this lane exists

The answer is almost always cheaper than the thing it decides. A study
that finds nothing has still stopped somebody building the wrong theory,
at a day's cost instead of a month's — `calendar-arb` and
`smile-smoothing` were both killed this way before a line of theory code
was written, and `settlement-day-clustering` caught two theories whose
strong opening numbers were a single settlement day.

So this lane is at its most valuable **before** work, not after it.

## 1. Orient

```bash
python -m tools.cli studies                        # what exists, and its verdict
python -m tools.cli tickets list --lane study      # queued study work
```

`*` marks a study that is **not complete**. Those are the first thing to
look at: an in-flight study is a question somebody thought was worth
answering and then stopped answering, and it is usually cheaper to
finish than a fresh one is to start.

## 2. Choose — in this order

1. **A study in flight**, especially one whose data perishes. Kalshi
   ages settled markets out of its public API after ~60 days, so an
   unfinished collection is not merely delayed, it is *losing rows
   upstream*. This outranks a new question.
2. **A ticket in the study lane.**
3. **The deciding experiment for an open `new-theory` spec.** Several
   tickets name one explicitly and say the theory should not be built
   until it runs. That is the highest-leverage new study available,
   because its answer is already load-bearing for somebody.
4. **A claim a running theory rests on that nobody has checked.**
5. **A new question of your own** — last, not first.

State which you picked and what you compared it against.

## 3. If you are starting a new one: write the bar first

**Before computing any result**, create `studies/<YYYY-MM-DD>-<slug>/STUDY.md`
and commit it, stating:

- **The question**, in one sentence.
- **The population** — inclusion rules, concretely. *The rules that
  decide who is in the sample routinely span the entire conclusion*; a
  pre-registration naming only the contrast is not one.
- **The contrast**, and its predicted direction.
- **The power floor** — the smallest effect this design can detect. If
  the MDE is larger than a theory-grade edge, the run cannot inform the
  question: resize it *before* running, never reinterpret after.
- **What result would kill the idea.**
- **The tier** — A if no outcome judgment is anywhere in the path.

Read `tickets/new-theory/README.md` rules 0–0f first. Two of them kill
studies before they are run, for free: **rule 0** (an edge between
siblings of one Kalshi event finds nothing) and **rule 0f** (measure at
*executable* prices, never the mid, never gross of fees).

Keep the script that proves you had looked at nothing —
`studies/2026-08-30-entry-timing/counts.py` exists for exactly that reason.

**Carry a negative control** if the study scans many candidates: a slice
whose answer is already known. Measure it, and keep it out of the
multiple-comparisons family.

## 4. Run it once

One run, against the bar as written.

- **Report a failed prediction as failed.** A better-looking cut found
  afterwards is a hypothesis for the next population, never the
  headline. Both of the repo's pre-registration failures were this shape.
- **Score gross; report net beside it.** Fees are a near-constant −1 to
  −3pt offset, so a fee-net statistic makes a perfectly calibrated
  series look biased — and sails through a split-sample guard.
- **"Not measured" is a legitimate result** and is different from
  "calibrated". `series-bias-mining` pass 3 declared itself not measured
  by its own bar rather than reporting nine flags, and that was correct.
- **Write incrementally.** Anything running over a minute writes per
  series or per page to a resumable checkpoint, never memory-only with
  one write at the end. The data perishes; an interrupted run must
  resume rather than restart.

## 5. Record the verdict where it can be seen

The header line is the interface — `cli studies` reads it live, so this
is how a supervisor learns what you found without opening the file:

```markdown
**Date:** YYYY-MM-DD · **Status:** complete · **Tier:** A · **Verdict:** <one line>
```

Keep `Status` honest. `collecting` while it is collecting; `complete`
only when the question is answered.

Then close the loop wherever the question came from — the study is not
finished while its answer sits only in `studies/`:

- Killed or confirmed a `new-theory` spec → close that ticket with the
  resolution, or append the finding to it.
- Answered something about a theory → say so in that theory's `NOTES.md`,
  and in `THEORY.md` if it changes what the theory claims or does.
- Found something cross-cutting → `RESEARCH_LOG.md`, and if it is a rule
  everyone needs, `tickets/new-theory/README.md`.

**A pattern found post-hoc is a hypothesis, not an edge.** If it is
expressible over recorded fields, pre-register it as a registered slice
(`cli slices register`) so the out-of-sample bookkeeping is automatic.
Never bet the data that suggested it.

## 6. Before you close the claim

- Is the `Status` line true?
- Does `cli studies` show what you want a supervisor to see?
- Did the answer reach whoever asked the question?
- Is anything you could not finish a ticket in the study's own folder
  (`--lane study --study <slug>`) rather than in your head?

```bash
python -m tools.cli lane release <id> --summary "<what was measured, and what it decided>"
```

## Two things this lane must not do

**Do not let a study become a theory by accident.** The moment it wants
to record a bet it needs a spec and the new-theory lane. File the ticket
and stop.

**Do not re-run a finished study to see if the answer changed.** That is
multiple comparisons by calendar. Extending one is deliberate work with
its own statement of what changed — and a larger family is a harsher
Holm divisor, so two runs over two collection states are two different
tests. Say which collection state produced the number, and never present
whichever of the two looks better.
