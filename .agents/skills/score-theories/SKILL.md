---
name: score-theories
description: Settle resolved opportunities and recompute calibration scores. Use when checking how recommendations performed, or as part of a research session.
---

# Score Theories

## 1. Find what has resolved

```python
from tools import db, ledger
from tools.kalshi import markets
conn = db.connect(); db.init_db(conn)
tickers = ledger.tickers_awaiting_settlement(conn)  # skip what already has a settlement
quotes = markets.quotes(tickers)
```

`tickers_awaiting_settlement` returns only tickers with no settlement on
file: without that filter this re-quotes every opportunity ever recorded, on
every run, unbounded — a ledger with 95 tickers today only grows. A ticker
with a settlement already on file has nothing left to check here.

**Never read `kalshi_ticker` off an opportunity row for this.** A basket's
header carries a synthetic `BASKET:<hash>` that is not a market — quoting it
asks Kalshi about nothing and never asks about the legs, so no basket could
ever settle. `tickers_awaiting_settlement` reaches through
`opportunity_legs` for a basket and uses the header ticker for a single, so
both kinds settle by the same loop. A basket is settled only when every leg
is; `ledger.list_opportunities(conn, unsettled_only=True)` applies the same
rule if you want the position rows rather than the tickers.

A Kalshi market is settled when its status is `finalized` and `result` is set.

## 2. Record settlements

```python
from tools import score
score.record_settlement(conn, ticker, result, resolved_at=...)
```

## 3. Recompute scores and bucket rates

```bash
python -m tools.cli score report <theory_id> --save
```

Run this once per running theory whenever settlements landed. It is what
keeps `state` EVIDENCE rendering reality instead of "scores never
written" — and it does more than persist one number.

**`--save` writes one row per segment, not one per theory.** A
sub-theory (a registered slice — a theory over a *subset* of this
theory's data) has evidence of its own: it accrues separately, clears
its own gates, and can be strong while the parent around it is flat.
`save_segment_scores` therefore persists:

| segment | what it is |
|---|---|
| `aggregate` | the whole theory |
| `slice:<slug>` | one sub-theory, out-of-sample |
| `complement` | what remains once every *ready* sub-theory is removed |

The complement is scored separately so the remainder never borrows what
a subset earned. Unready sub-theories are saved too — a record nobody
can see is a record nobody can watch approach its gates, and "invisible
until it matters" is how a proven subset ends up orphaned.

**Every segment comes from one pool**, spanning live *and* backtest rows
and the theory's whole version chain — the same pool
`slices.ranking_segment` ranks on, so what `state` shows is what
`promote` will decide from. A pooled row is labelled `run_mode='pooled'`
and records its version span in `pooled_versions`; scope to one mode
with `--run-mode` when you want a single-mode measurement.

Read the partition back with:

```bash
python -m tools.cli slices report <theory_id>
```

`--pool chain` on `score report` scopes the **printed** figures; the
saved rows always pool the chain, because a bump carries evidence
forward unless it explicitly broke (see docs/RESEARCH_GUIDE.md, "Theory lifecycle and versioning").

Then recompute what each confidence bucket is actually worth — this is what
replaces guessed probabilities with measured ones:

```python
rates = score.bucket_rates(conn, theory_id, version)
score.save_bucket_rates(conn, theory_id, version, rates)
```

Report any bucket that crossed 10 settled results: it has just graduated from
a declared prior to a measurement, which changes every future edge that theory
claims. If a bucket's measured rate is far from its prior, say so — a `strong`
bucket that turns out to be worth nothing is one of the most valuable findings
this system can produce, and the theory's priors in `THEORY.md` should be
updated to match reality.

For any theory with registered slices (`python -m tools.cli slices list
--theory <id>`), also recompute the segments:

```bash
python -m tools.cli slices report <theory_id>
```

Report two events the moment they happen: a slice **crossing its
readiness gates** (≥ 10 out-of-sample clusters and ≥ 5 settlement days)
— from then on find-edge ranks that theory per segment, in-slice
candidates on the slice's record and the rest on the complement — and a
ready slice whose out-of-sample `calibration_edge_net` has **gone
negative**, which is a real falsification of a pre-registered claim, not
noise to sit on.

**Crossing the gates is the mechanism completing, not a prompt to change
the theory.** A ready sub-theory is already the decision point for the
rows it matches; nothing is adopted, promoted or merged. Never fold a
proven slice's predicate into its parent's screen — the bet is identical
and it destroys the complement and the out-of-sample split that make the
slice's number mean anything (docs/RESEARCH_GUIDE.md, "A sub-theory is maintained, not
absorbed"). A slice that looks unreachable at the current version is an
**orphan**, fixed by relinking the evidence chain
(`theories.reclassify_bump`), not by adoption. Diagnose it like any underperforming theory, and if the
slice is dead, propose retiring it (`slices retire` is
user/supervisor-authorized, like theory retirement; a retired slice
keeps reporting, so the record survives).

The score report returns all four dispositions. The one that matters most:

```python
score.interpretation_value(conn, theory_id, version)
```

- **Positive delta** — interpretation is adding edge. The pipeline is a
  candidate generator; your judgment is the product.
- **Near zero** — interpretation adds nothing. Strengthen stage 1 or trust the
  pipeline and save the research time.
- **Negative** — interpretation is destroying value. Say so plainly.

It is `None` until both endorsed and rejected samples have settled.

<!-- explainer: tier-reading (authority: docs/RESEARCH_GUIDE.md § Backtest tiers) -->
### Reading a tier before you trust its number

Every calibration edge and bucket rate you just recomputed carries a tier.
Check it before deciding how much weight the number deserves — full
definitions live in docs/RESEARCH_GUIDE.md § Backtest tiers; this is what each one means
for a session about to act on a score.

- **Tier A** — no outcome judgment sat in the decision path. The replay
  covers all reachable history and reproduces exactly on a rerun. Nothing
  in this system is more solid than a tier A number.
- **Tier B** — outcome judgment on markets that settled after the judging
  model's knowledge cutoff. Its sample is smaller than tier A's by
  construction, but the t-statistic and the credibility weighting already
  paid that small-sample penalty once — **marking the score down again for
  being tier B just double-counts a cost that's already been charged.**
  The doubts the statistics do not already price are narrower and
  specific: cutoffs leak at the edges rather than sealing cleanly, so some
  residual contamination can remain, and rerunning the same replay on a
  different model version can move the verdicts. Weigh those two
  directly; don't re-charge for sample size, which is already spent.
- **Tier C** — outcome judgment on markets the model could plausibly have
  known the outcome of. Contaminated, and excluded from credibility
  outright. If a tier C number ever reaches this checklist, run the
  contamination probe before treating anything it says as evidence.
<!-- /explainer -->

## 4. Apply lifecycle flags

- `n = 20` with *net* calibration edge (`calibration_edge_net`) ≤ 0 →
  `under_review`. The theory **keeps running**. A theory taken off the board
  stops producing the evidence that would tell you whether it was broken or
  merely unlucky, so review is a diagnosis, not a bench.
- `paused` is for a theory blocked on a missing prerequisite — data that does
  not exist yet, tooling not written. It is not where failing theories go.

```bash
python -m tools.cli theories status <id> under_review
```

## 5. Diagnose before you dispose

An underperforming theory is the most information-dense object in this repo.
The salvageable cases all look exactly like death from the outside, so work
the checklist before forming any opinion about whether to keep it. Every
question below is answerable from data already on disk.

1. **Can this sample reject zero at all?** Bet outcomes are near-Bernoulli;
   at n=30 the standard error on a win rate is roughly 9 points. A small
   negative number at small n is noise wearing a verdict's clothes. If the
   result is inside the noise, the finding is *"still unmeasured"* — say that,
   and let it keep running.
2. **Gross positive, net negative?** Compare `calibration_edge` against
   `calibration_edge_net`. If the thesis wins before fees and loses after, the
   thesis is *right* and the entry is wrong. Fees are `min(0.07·P·(1−P),
   0.035)` per contract — worst at mid prices. Raising the edge threshold or
   avoiding the punitive price band is a version bump, not a burial.
3. **Is it the screen or the judgment?** `interpretation_value` splits them.
   Negative → stage 1 has edge and stage 2 is destroying it; cut stage 2 and
   the theory may be fine. Positive while the total is negative → judgment
   works on a bad candidate set; tighten stage 1.
4. **Does one slice work?** Break the settled rows down by confidence bucket,
   market family (series prefix), days-to-close, price band, and
   `theory_version`. A theory that loses overall while one slice wins is a
   narrow theory wearing a broad one's clothes — that is a real finding, and
   its follow-through is a **registered slice** (`cli slices register`, with
   the mechanism and the mined runs' in-sample status recorded) when the cut
   is expressible over recorded fields, or a version bump / sibling theory
   when it needs its own procedure. Never bet the finding on the data that
   produced it — the slice's out-of-sample split enforces exactly that.
5. **Is it inverted?** A theory reliably on the wrong side is reliably
   informative. Check whether the opposite side clears the bar *after* fees —
   fees are paid either way, so a mirrored edge is not automatic.
6. **What tier is the evidence?** Tier C is contaminated and cannot kill
   anything. Check what actually produced these rows before believing them.
7. **Did the procedure change mid-track?** Segment by `theory_version`. Mixed
   versions in one record are two theories averaged into a number describing
   neither.

Report what you found either way. "n=29, inside the noise, no slice tested
yet" is a real result and belongs in that theory's dated source note — distilled
into `THEORY.md` only if it changes the theory's standing: a status change,
a version bump, or a claim you can no longer make.

Consolidate a reusable lesson only when the diagnosis changes a future
decision; link its scoped source from the theory's learning map. Follow
`docs/agents/research-memory.md` without turning routine scoring into a diary.

## 6. Retirement is the user's call

Only when the checklist comes back empty — the sample is large enough, the
edge is negative gross *and* net, no slice works, it is not inverted, the
evidence is clean — do you propose retirement. You never execute it:

```bash
python -m tools.cli theories propose-retirement <id> --rationale "<what you diagnosed and what you ruled out>"
```

This leaves the theory running and records a standing suggestion that every
session's orient surfaces until the user rules on it. `theories status <id>
retired` refuses without `--authorized-by user` *and* a proposal on file.

**Say it out loud in your report.** A proposal that sits in the database
unmentioned is not a suggestion to anyone.

**When the user does retire it, the folder moves.** A retired theory leaves
`theories/` for `theories/retired/`, keeping only `RETIRED.md`, `THEORY.md`,
`NOTES.md` and `RESULTS.md`, Markdown `learnings/` and `notes/`, plus its studies;
update incoming knowledge links to the retired path. Its code, runbook, prompts,
tickets, tests and raw backtest payloads are deleted, and stay retrievable at
the git rev `RETIRED.md` names. docs/RESEARCH_GUIDE.md's "Theory lifecycle and versioning"
section has the rule; do not re-derive it here.

If the user does retire it, record why against the originating idea, so the
failure is written where the next proposal will look:

```bash
python -m tools.cli ideas status <slug> dead --outcome "<why it failed>" --revisit-angle "<or omit>"
```

## 7. Report both ROI numbers

`roi_all` is hypothetical — it assumes every suggestion was taken. `roi_taken`
is real money. Never present the first as if it were the second.
