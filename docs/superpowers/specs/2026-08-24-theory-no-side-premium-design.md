# No-Side Premium (Optimism Tax Harvesting) — Theory Design Spec

Date: 2026-08-24
Status: backlog — not yet proposed as a theory
Registry slug: `no-side-premium` · Priority: 6 of 17 · Effort: S–M ·
LLM in decision path: no · Backtest tier: A

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "no-side-premium"` for status changes,
then formalize via the `propose-theory` skill.

## Assessment

**Applicability 4/5 · Implementability 4/5 · Likelihood of success 3/5 ·
Composite 11/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
calibrated probabilities)

- *Applicability 4:* frequent candidates in the entertainment/world
  categories where the measured inefficiency concentrates; direct NO
  entries. NO against cheap YES ties up high collateral per point, like
  deadline-drift.
- *Implementability 4:* all data in-repo; the only added complexity is
  the within-price-bin YES/NO separation in the backtest.
- *Likelihood 3:* the 64pp headline is measured at longshot extremes
  where Kalshi fees and spreads bite proportionally hardest, and there is
  a real chance the effect collapses into calibration-harvest's price
  bias once the side is conditioned on price — which would kill this as a
  *separate* theory even though the money is real.

## 1. Hypothesis

Retail flow buys YES. The affirmative side of a question carries an
"optimism tax": at equal prices, YES contracts systematically underperform
NO contracts, because hope-driven takers cross the spread into YES and
nobody's hope pushes them into NO. Buying NO in the categories and price
bands where YES-taker flow concentrates harvests that premium without
needing any view on the event itself.

## 2. Evidence

- Becker, "The Microstructure of Wealth Transfer in Prediction Markets"
  (largest public Kalshi+Polymarket dataset): takers earn −1.12% mean
  excess return per trade, makers +1.12%; takers disproportionately buy
  YES at longshot prices; **YES contracts underperform NO contracts by up
  to 64 percentage points at equivalent prices**. Inefficiency varies by
  category — Finance ~0.17pp maker–taker gap (near-efficient), Politics
  ~1.02pp, Sports ~2.23pp, **Entertainment/Media 4.79–7.32pp**.
- Reichenbach & Walther 2025 (478M Polymarket trades): documented tendency
  to overtrade the default/"Yes" option; notably they find *no general
  longshot bias* on Polymarket once side is accounted for — evidence the
  side effect and the price effect are partially distinct phenomena.
- The repo's calibration work (see the
  [calibration-harvest spec](2026-08-24-theory-calibration-harvest-design.md))
  measures the *price*-conditional bias; this theory measures the
  *side*-conditional bias at the same price. They overlap but are not the
  same measurement, and section 6 separates them.

## 3. Non-goals and exclusions

- Not a claim that NO always wins — the premium concentrates in cheap-YES /
  expensive-NO territory and emotional categories. The screen restricts to
  where the evidence says the flow is.
- No stage 2. No LLM anywhere.
- Finance-domain markets excluded by default (measured near-efficient).
- Families claimed by running theories (`mention_family` tickers) excluded,
  gate-report style, to keep track records disjoint.

## 4. Decision procedure

Fully mechanical, stage 1 only.

- Screen: board markets where the YES ask is in a longshot band (start:
  $0.03–$0.35), in categories ranked inefficient by the theory's own
  measurement (prior from Becker: entertainment/media/world-events first),
  with a liquidity floor on the NO side and days-to-close ≤ a cutoff
  (start: 30).
- Candidate: buy NO at the NO ask.
- Edge: `edge = realized_NO_rate(cell) − NO_ask − fees`, with cells =
  (category × YES-price bin). `edge_basis="measured"` for cells with
  n ≥ 30 from the tier-A measurement; thinner cells report Wilson lower
  bounds or are skipped.
- Rank by net edge; size via `tools/sizing.py`. Note NO at high prices
  ties up near-full collateral per point of profit — sizing, not the
  screen, accounts for capital efficiency.

## 5. Data requirements

All already in-repo: the session board (`tools.board.get_board`), settled
markets + candlesticks (`tools/kalshi/history.py`, ~12 months), category
from the ticker hierarchy, fee math (`tools/sizing.py`). No external data.

## 6. Backtest design

Tier A. Two measurements, both required:

1. **Side premium isolated from price bias.** For settled markets, compare
   realized NO returns against realized YES returns *within the same price
   bin* — the calibration-harvest cell rates already capture the price
   dimension; this theory's claim survives only if NO beats YES at equal
   price, not merely because cheap contracts lose.
2. **Split-sample rule test.** Category × price-bin cells measured on the
   first half of history, P&L of the rule on the second half. Cells only
   count if the premium survives out-of-sample.

Lookahead traps: none beyond the standard ones — entry at historical NO
ask from candlesticks, never mid.

## 7. Kill criteria

- If the within-price-bin YES/NO gap disappears (i.e., the whole effect is
  the price bias calibration-harvest already captures), kill this as a
  separate theory and record it as a lens duplicate — that outcome makes
  calibration-harvest the single owner of the effect.
- If the premium exists gross but every cell dies net of fees +
  NO-side capital cost, record "real phenomenon, untradeable at Kalshi
  fees" with a revisit angle on fee changes.

## 8. Implementation plan

`theories/no_side_premium/{THEORY.md,screen.py,cells.py}` + tests under
`tests/theories/`. Reuse `mention_bucket.py`'s bin structure for
`cells.py`. Register with no `uses_llm_judgment`. Most of the work is the
within-price-bin YES/NO comparison in the backtest script.

## 9. Testing approach

- Unit tests: cell assignment (category, price bin), edge arithmetic
  against fixtures, the exclusion gate's category report.
- Backtest fixtures: constructed settled sets where the side premium is
  present/absent, verifying measurement 1 distinguishes them.

## 10. Open risks

- Category labels come from ticker prefixes; a coarse or shifting mapping
  smears cells. Mitigation: snapshot the mapping in the theory folder and
  version it.
- The 64pp Becker figure is at extreme longshot prices where Kalshi fees
  and spreads are proportionally largest; the *tradeable* band may be much
  narrower than the *documented* band.
- Overlap with calibration-harvest must be managed at the ledger level if
  both run: same ticker+side from both theories should be collapsed by
  `find-edge`'s cross-theory dedup, and the two theories' screens should
  stay disjoint by construction (this screen's YES-longshot band vs its
  favorite-side band).

## 11. Sources

- [Becker — The Microstructure of Wealth Transfer in Prediction Markets](https://www.jbecker.dev/research/prediction-market-microstructure) ([dataset repo](https://github.com/jon-becker/prediction-market-analysis))
- [Reichenbach & Walther 2025 — Accuracy, Skill, and Bias on Polymarket](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5910522)
- [Whelan — Makers and Takers](https://www.karlwhelan.com/Papers/Kalshi.pdf) — taker losses net of fees on Kalshi specifically.
