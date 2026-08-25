# Reading notes — Le 2026, "Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics in Prediction Markets"

Source: arXiv:2602.19520 **v2, 4 Aug 2026** —
https://arxiv.org/pdf/2602.19520
Author: Nam Anh Le (National Economics University, Vietnam).
Replication: github.com/namanhzz/prediction-market-calibration
Read in full 2026-08-24 (PDF text extracted via pypdf). These notes
transcribe the numbers the theory specs cite, with locators, so a
reviewer can verify against the paper without re-extracting it.

## Dataset (§3)

- 353M trades across 429k binary contracts total. Kalshi is primary:
  64.7M trades, 210,608 binary contracts (~16.8B contracts traded),
  earliest trade 1 Jul 2021, cutoff 31 Dec 2025; 98.6% of
  past-close markets resolved definitively. Polymarket comparison:
  288.7M trades, 218k resolved contracts; timestamps carry ~3h noise
  (Polygon block derivation), affecting the two shortest time bins.
- Domains classified from ticker prefixes: Sports, Politics, Crypto,
  Finance, Weather, Entertainment. Kalshi domain rows (markets /
  trades / resolved-yes share): Politics 6,609 / 4.9M / 40.2%; Finance
  38,058 / 4.3M / 37.7%; Weather 26,911 / 4.4M / 24.0%; Entertainment
  7,212 / 1.5M / 38.0%.

## Method (§4)

Logistic recalibration slopes per (domain × time-to-resolution ×
trade-size) cell; 216 Kalshi cells all meet sample-size requirements
(minimum cell counts range 472 trades in Weather to 22,518 in Sports).
Slope > 1 = underconfidence (prices compressed toward 50%); slope < 1 =
overconfidence (prices too extreme). Isotonic regression used as a
model-free check (§4.2).

## Table 4 — slopes by domain × time-to-resolution (Kalshi) — the number the specs lean on most

| Domain | 0–1h | 1–3h | 3–6h | 6–12h | 12–24h | 24–48h | 2d–1w | 1w–1mo | 1mo+ |
|---|---|---|---|---|---|---|---|---|---|
| Politics | 1.34 | 0.93 | 1.32 | 1.55 | 1.48 | 1.52 | 1.83 | 1.83 | 1.73 |
| Sports | 1.10 | 0.96 | 0.90 | 1.01 | 1.05 | 1.08 | 1.04 | 1.24 | 1.74 |
| Crypto | 0.99 | 1.01 | 1.07 | 1.01 | 1.01 | 1.21 | 1.12 | 1.09 | 1.36 |
| Finance | 0.96 | 1.07 | 1.03 | 0.97 | 0.98 | 0.82 | 1.07 | 1.42 | 1.20 |
| Weather | 0.69 | 0.84 | 0.73 | 0.87 | 0.91 | 0.97 | 1.20 | 1.20 | 1.37 |
| Entertainment | 0.81 | 1.02 | 1.00 | 0.92 | 0.89 | 0.84 | 1.07 | 1.11 | 0.96 |

## Other quantitative findings cited by specs

- **Isotonic check (§4.2):** at a raw price of 0.75, the isotonic
  estimate of realized frequency is **0.886 in Politics** and **0.691 in
  Weather** — "matching the slope-based conclusion that political prices
  are compressed while short-horizon weather prices tend to be too
  extreme."
- **Slope-only illustration (§5, Stylized Fact 2):** "a 70-cent
  political contract one week before resolution maps to approximately
  83%."
- **Universal horizon component (Stylized Fact 1):** mean slope across
  domain–size cells rises from **0.99 (0–1h) to 1.32 (beyond one
  month)**. "At long time horizons, prices in every domain move toward
  the favorite–longshot pattern."
- **Table 5 — slopes by trade size (Kalshi):** Politics Single 1.19 /
  Small 1.22 / Medium 1.37 / Large 1.74, Δ(L−S)=+0.53 with trade-level
  bootstrap CI [0.29, 0.75], surviving market-clustered [0.14, 1.32] and
  event-clustered [0.12, 1.80] resampling. Sports Δ=+0.07 (null under
  clustering); Crypto −0.02; Finance −0.05; Weather −0.07;
  Entertainment +0.01. On Polymarket the Politics cell-level Δ is +0.28
  [0.03, 0.54] but not robust to market clustering [−0.31, 1.12].
- **Cross-platform:** Politics underconfident on Polymarket too (mean
  slope 1.45 across reliable bins); Sports near-calibrated (1.06);
  Crypto mildly underconfident (1.06). Weather/Entertainment have
  negligible Polymarket presence; Finance excluded (2,648 markets).
- **Decomposition fit:** four components (universal horizon, domain,
  domain×horizon, trade-size) explain **87.3% of in-sample variance on
  Kalshi (71.5% out-of-sample)**. Under conservative event-clustered
  SEs, "roughly half of the raw slope variation reflects estimation
  noise" — a caveat specs should carry when quoting individual cells.

## Specs that cite this paper

calibration-harvest (core evidence), deadline-drift (§2), news-drift
(context), series-bias-mining (§2), new-market-anchor (§2), vol-crossing
(§2), econ-anchoring (§2, Finance flatness), weather-model-gap (§2),
no-side-premium (indirect).
