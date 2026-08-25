# Series Bias Mining — Theory Design Spec

Date: 2026-08-24
Status: backlog — not yet proposed as a theory
Registry slug: `series-bias-mining` · Priority: 4 of 22 · Effort: M ·
LLM in decision path: no · Backtest tier: A

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "series-bias-mining"` for status
changes, then formalize via the `propose-theory` skill.

## Assessment

**Applicability 4/5 · Implementability 4/5 · Likelihood of success 4/5 ·
Composite 12/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
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
