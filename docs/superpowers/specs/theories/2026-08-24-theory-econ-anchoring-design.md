# Economic Data Anchoring — Theory Design Spec

Date: 2026-08-24
Status: backlog — not yet proposed as a theory
Registry slug: `econ-anchoring` · Priority: 13 of 22 · Effort: M ·
LLM in decision path: no · Backtest tier: A

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "econ-anchoring"` for status changes,
then formalize via the `propose-theory` skill.

## Assessment

**Applicability 3/5 · Implementability 3/5 · Likelihood of success 3/5 ·
Composite 9/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
calibrated probabilities)

- *Applicability 3:* only a handful of qualifying releases per month, so
  candidate flow and evidence accrual are slow (~12 settlements per year
  per series); the ladders themselves are liquid.
- *Implementability 3:* real-time vintage handling (ALFRED) and
  walk-forward fitting are the work; keyless data access still needs
  verification and is a hard prerequisite.
- *Likelihood 3:* seventeen years of persistence in the anchoring
  literature is a strong prior, but Kalshi's econ crowd is its sharpest
  (Le 2026 measures the Finance domain near-flat), and the strikes may
  already skew trendward — the spec's second kill criterion.

## 1. Hypothesis

Consensus forecasts of scheduled economic releases anchor on prior months:
when a series has been trending, the consensus under-extrapolates, so the
released figure surprises in the trend direction more often than chance.
Kalshi's econ ladders (CPI, jobless claims, payrolls) price near the
consensus mode; buying the strike(s) on the trend side of the mode before
the release captures the predictable component of the surprise.

## 2. Evidence

- Campbell & Sharpe, "Anchoring Bias in Consensus Forecasts and Its Effect
  on Market Prices" (JFQA 2009): monthly data-release consensus forecasts
  are anchored to recent months, forecast errors are predictable from
  prior realizations, and *market prices* (bonds) move on the predictable
  component — i.e., the anchoring is priced in by the market too.
- A 2026 Federal Reserve FEDS paper re-runs the Campbell–Sharpe anchoring
  regression on 2012–2026 data and finds positive, statistically
  significant anchoring coefficients at all horizons — the bias has not
  been arbitraged away in seventeen years, which is exactly the
  persistence a theory wants.
- Le 2026 measures Kalshi Finance-domain calibration as roughly flat —
  meaning Kalshi econ prices track consensus faithfully. That is what
  makes this thesis coherent: the market prices the *consensus*, and the
  consensus itself is predictably wrong. The edge is against the anchor,
  not against the crowd's reading of the anchor.

## 3. Non-goals and exclusions

- Only scheduled, recurring, numeric releases with long public history
  (CPI, claims, NFP-type). No Fed-decision markets — Le 2026 and the
  macro-markets literature both measure Fed/rates markets near-perfectly
  calibrated; there is no anchor gap to harvest there.
- No LLM anywhere. No stage 2.
- This is not a forecast of the release value — it is a bet that the
  *distribution* Kalshi implies is shifted toward the anchor relative to
  the true conditional distribution.

## 4. Decision procedure

Fully mechanical.

- For each supported series (start with CPI m/m and initial claims), pull
  the official release history (keyless: BLS/FRED public endpoints) and
  compute the anchoring signal — the Campbell–Sharpe predictor: recent
  realized changes relative to the longer trailing mean (their regression
  form, coefficients fit on history *before* the decision date).
- Screen: the Kalshi ladder for the upcoming release, within N days of the
  release (start: 5), liquidity floor per strike.
- Candidate: the strike range on the signal side of the market-implied
  mode. Edge: the model's shifted distribution vs strike prices —
  `edge_basis="model"`, from the fitted anchoring regression, never from
  introspection. A conservative cap (start: claim no more than 5 points)
  keeps a regression artifact from claiming a huge edge.

## 5. Data requirements

- Official release series: FRED/BLS public APIs — **verify keyless access
  during implementation**; FRED technically issues free keys, but several
  series are fetchable without one via public CSV endpoints. If a key
  turns out to be unavoidable, this theory is `paused` on that
  prerequisite (the repo allows no API keys), and the spec's registry
  entry gets that as `revisit_after`.
- Kalshi ladder history: in-repo candlesticks.
- Explicitly *not* required: a consensus-forecast feed. The market mode
  proxies the consensus (Le 2026 says Kalshi tracks it), which avoids the
  hardest data dependency. Recording the realized market mode at decision
  time preserves auditability.

## 6. Backtest design

Tier A. For every historical release of a supported series in the
candlestick window: fit the anchoring regression on data strictly before
the decision date, form the signal, take the rule's strikes at their
historical asks, settle against the actual print. Report per-series and
pooled; split-sample across time as with every theory in this backlog.

Lookahead traps: regression coefficients must be walk-forward (refit per
decision date on prior data only); revised economic data must be avoided —
use real-time/first-print vintages (FRED's ALFRED real-time archive covers
this and is public).

## 7. Kill criteria

- Walk-forward signal accuracy no better than coin-flip on surprise
  direction → the anchor gap doesn't survive at monthly frequency in this
  window; kill and record.
- Signal predicts direction but the tradeable strikes never clear fees
  (ladders may already skew slightly toward the trend side) → "real,
  priced-in"; record the gap between mode and true distribution as a
  finding even though it isn't tradeable.

## 8. Implementation plan

`theories/econ_anchoring/{THEORY.md,signal.py,releases.py}` + tests.
`releases.py` (fetching official series with real-time vintages) is a
plausible future `tools/` promotion — build it theory-local first per the
repo rule. Effort M; the vintage-data handling is most of it.

## 9. Testing approach

- Unit tests: anchoring regression against the published Campbell–Sharpe
  example structure, walk-forward refit discipline, strike selection.
- Fixture backtest with a constructed trending series verifying the signal
  fires on the trend side and respects the vintage boundary.

## 10. Open risks

- Kalshi econ ladders are comparatively liquid and professionally traded;
  the anchor gap may be priced into the tails even if the mode tracks
  consensus (kill criterion 2 measures exactly this).
- Monthly releases mean slow evidence accrual: ~12 settlements per year
  per series. Combining series (with per-series reporting) is the only way
  to reach meaningful n on a useful horizon.
- Data revisions and methodology changes (CPI re-weighting) can break a
  regression fit silently; `releases.py` should pin methodology-change
  dates as fit boundaries.

## 11. Sources

- [Campbell & Sharpe 2009 — Anchoring Bias in Consensus Forecasts (JFQA)](https://www.federalreserve.gov/econres/steven-a-sharpe.htm)
- [FEDS 2026 series](https://www.federalreserve.gov/econres/feds/2026.htm) — anchoring regression re-confirmed on 2012–2026 data.
- [Le 2026](https://arxiv.org/pdf/2602.19520) — Finance-domain calibration flatness on Kalshi (the market-tracks-consensus premise).
