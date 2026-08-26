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
python -m tools.cli score report <theory_id>
```

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
   narrow theory wearing a broad one's clothes — that is a real finding and a
   version bump, not a failure.
5. **Is it inverted?** A theory reliably on the wrong side is reliably
   informative. Check whether the opposite side clears the bar *after* fees —
   fees are paid either way, so a mirrored edge is not automatic.
6. **What tier is the evidence?** Tier C is contaminated and cannot kill
   anything. Check what actually produced these rows before believing them.
7. **Did the procedure change mid-track?** Segment by `theory_version`. Mixed
   versions in one record are two theories averaged into a number describing
   neither.

Report what you found either way. "n=29, inside the noise, no slice tested
yet" is a real result and belongs in that theory's `NOTES.md` — distilled
into `THEORY.md` only if it changes the theory's standing: a status change,
a version bump, or a claim you can no longer make.

## 6. Retirement is the user's call

Only when the checklist comes back empty — the sample is large enough, the
edge is negative gross *and* net, no slice works, it is not inverted, the
evidence is clean — do you propose retirement. You never execute it:

```bash
python -m tools.cli theories propose-retirement <id> \
    --rationale "<what you diagnosed and what you ruled out>"
```

This leaves the theory running and records a standing suggestion that every
session's orient surfaces until the user rules on it. `theories status <id>
retired` refuses without `--authorized-by user` *and* a proposal on file.

**Say it out loud in your report.** A proposal that sits in the database
unmentioned is not a suggestion to anyone.

If the user does retire it, record why against the originating idea, so the
failure is written where the next proposal will look:

```bash
python -m tools.cli ideas status <slug> dead \
    --outcome "<why it failed>" --revisit-angle "<or omit>"
```

## 7. Report both ROI numbers

`roi_all` is hypothetical — it assumes every suggestion was taken. `roi_taken`
is real money. Never present the first as if it were the second.
