---
title: Mine per-series historical base rates for market families whose own price is persistently wrong
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: done
closed: 2026-09-01
resolution: BUILT AS A STUDY, per the spec's own section 3 (the miner produces measurements, not bets): theories/insider_bias/mention_family/studies/investigation/2026-08-29-series-bias-mining/. Three passes run. Pass 3 declared itself NOT MEASURED by its own pre-registered bar -- 347 series tested against a floor of 30, so breadth was solved, but median MDE was 12.16 against a bar of 8.0. Its 72,010-row priced settled corpus is now the most reused dataset in the repo. Remaining work is tracked in its own open tickets: series-bias-sweep-finish and series-bias-backfill-liquidity.
---
Effort: M · LLM in decision path: no · Backtest tier: A

**This spec was acted on; the `resolution` field above says what
came of it.** Kept rather than deleted, because a completed ticket
is the record of what was asked for and why — which is what a
future session re-deriving the same idea needs.

## Assessment

**Applicability 4/5 · Implementability 4/5 · Likelihood of success 4/5 ·
Composite 12/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 4:* indirect — it produces bettable *families*, not
  bets — but each survivor is a mention_family-grade instrument, so the
  leverage on the whole system is high.
- *Implementability 4:* the statistics need care (split-sample,
  survivorship handling); the plumbing is simple; the candlestick fetch
  loop is heavy but batchable.
- *Likelihood 4:* an existence proof already happened by accident
  (mention_family), and hundreds of series give real surface area. The
  multiple-comparisons guard will kill most flags — that is the design
  working, not failing.

## 1. Hypothesis

`mention_family` was found by accident: a backtest slice showed one
recurring series family with a persistent, exploitable bias. There is no
reason it is the only one. Mine *every* recurring series with enough
settled history for persistent price-vs-outcome bias, and promote the
survivors into their own bucketed sub-theories.

## 2. Evidence

Recurring series (daily/weekly weather, econ prints, pop-culture
recurrences) are traded by habitual retail flow with stable behavioral
biases, and each series has its own resolution quirks that casual traders
misprice consistently. The domain-specificity finding (Le 2026: political
markets compressed, short-horizon weather too extreme; the macro-markets
literature: Fed/rates near-perfectly calibrated) says bias lives at the
*family* level, not the board level — which is exactly what a per-series
miner exploits and a board-wide average washes out. The repo's own
mention_family history (RESEARCH_LOG.md, 2026-08-24 entries) is the
existence proof this miner generalizes.

## 3. Non-goals and exclusions

- The miner produces *measurements*, not bets — no live screen of its
  own. Survivors become separate small theories (or buckets), each with
  its own track record; the safer default is separate theories.
- Series already owned by a running theory (mention_family) are measured
  for comparison but never re-promoted.
- No LLM anywhere.

## 4. Decision procedure

A measurement pipeline:

- For every series with ≥ 30 settled markets in history: at fixed
  decision points (7d, 3d, 1d before close), record (price, outcome)
  pairs from candlesticks; compute realized rate vs mean price per price
  bin; flag series where the gap clears fees with a Wilson interval
  excluding zero.
- **Multiple-comparisons guard — the central design constraint.** With
  hundreds of series, dozens look biased by chance. Require: bias present
  in the first half of the series' history AND the second half, same
  sign, before flagging.
- Output: ranked candidate families with measured bin tables. Each
  survivor's follow-on theory inherits `edge_basis="measured"` only for
  the exact bins the split-sample test validated.

## 5. Data requirements

In-repo: settled series + candlesticks. The fetch loop over hundreds of
series must batch and cache aggressively (`tools/kalshi/history.py`);
~12 months is the available depth.

## 6. Backtest design

The miner *is* a tier-A backtest — the split-sample requirement in
section 4 is the out-of-sample test.

## 7. Kill criteria

- Nothing survives the split test → the board's recurring series are
  calibrated; a valuable negative, record it.
- Survivors' live settlements regress hard (measured minus live rate
  > 10 points at n ≥ 20) → the miner is overfitting; tighten the split
  test before mining again.

## 8. Implementation plan

`theories/series_miner/{THEORY.md,mine.py}` + tests. Effort M — the work
is careful statistics, not plumbing.

## 9. Testing approach

Unit tests: decision-point extraction from candles, bin rate + Wilson
interval math, the split-sample same-sign gate. A fixture universe with
one planted-bias series among calibrated ones, verifying exactly it is
flagged.

## 10. Open risks

- Selection-on-survival subtlety: series that Kalshi delisted mid-window
  truncate history and can fake or hide bias; include only series alive
  across both halves, and say so.
- The 7d/3d/1d decision points are arbitrary; adding more multiplies the
  comparison count — resist until the guard is proven.

## 11. Sources

- [Le 2026 — Domain-Specific Calibration Dynamics](https://arxiv.org/pdf/2602.19520) — bias is family-conditional.
- Repo history: RESEARCH_LOG.md 2026-08-24 mention_family entries.
