# Theory Backlog — Index

Date: 2026-08-24 (superseded docs/theory-specs/, same content migrated to
official spec format and extended after a second literature pass)

Seventeen researched, implementable theory design specs, one file per
theory, each written so a fresh session (no context beyond CLAUDE.md and
the spec) can pick it up and implement it. This index holds the shared
contracts, the priority ranking, the parked ideas, and the shared
sources; every spec links back here instead of repeating them.

## Before implementing any spec

1. `python -m tools.cli ideas search "<slug>"` — confirm nothing has
   changed since the spec was written (each is registered under its slug;
   check `status` and `outcome`).
2. Use the `propose-theory` skill to formalize the chosen idea into
   `theories/<slug>/` with a THEORY.md before writing procedure code
   (exceptions noted in a spec's Status line, e.g. maker-mode-execution
   lands as tooling changes, new-market-anchor starts as a study).
3. Follow the repo contracts in CLAUDE.md. Most-missed: entry prices are
   the **ask**, never the mid; every recorded edge carries an
   `edge_basis` (`measured`/`model`/`prior` — never a felt sense); any
   LLM in the decision path requires provenance records and prompts on
   disk; any change to a decision procedure bumps the theory version;
   backtest tier A means **no LLM anywhere in the decision path**.
4. Reuse the validated patterns already in the repo: the price-bin bucket
   pattern in `theories/insider_bias/mention_family/mention_bucket.py`
   (`PRICE_BINS`, `bucket_for_price`, measured rates via
   `tools/buckets.py`), the code-gate-with-category-report pattern in
   `theories/insider_bias/insider_judgment/gate.py`, the tier-A backtest
   pattern in `theories/insider_bias/insider_judgment/backtest.py`, and
   fee math from `tools/sizing.py`. The session board comes from
   `tools.board.get_board(conn)` — never `markets.list_open()` directly.

## Assessment rubric

Every spec carries an Assessment block scoring three metrics, 1–5 each.
These are **ordinal priors for prioritization** with stated reasoning —
the same epistemics as a confidence bucket, never a calibrated
probability — and they are deliberately honest: two specs score their own
likelihood 2/5 because the best available evidence points against them.

- **Applicability (A):** how directly the theory serves this repo's use
  case — a manual Kalshi bettor asking "what's the best bet right now."
  Considers whether output is directly bettable on Kalshi, candidate
  frequency, and capital/holding profile.
- **Implementability (I):** data in hand vs external, code and
  statistical complexity, dependencies on other specs, and effort to
  first evidence.
- **Likelihood of success (L):** strength and directness of the evidence
  (measured on Kalshi > measured on an analogous market > mechanism
  argument), threat of fee/spread erosion, competition, and how much
  sample it takes to prove.

## Priority ranking (effort S/M/L; A/I/L scores from each spec's Assessment)

| # | spec | lens | A | I | L | Σ | tier | effort |
|---|------|------|---|---|---|---|------|--------|
| 1 | [calibration-harvest](2026-08-24-theory-calibration-harvest-design.md) | signed price/horizon/domain cells | 5 | 5 | 4 | 14 | A | S |
| 2 | [deadline-drift](2026-08-24-theory-deadline-drift-design.md) | affirmative-event hazard | 4 | 3 | 3 | 10 | A | M |
| 3 | [structural-arb](2026-08-24-theory-structural-arb-design.md) | within-event logic | 3 | 5 | 3 | 11 | A | S |
| 4 | [series-bias-mining](2026-08-24-theory-series-bias-mining-design.md) | per-series base rates | 4 | 4 | 4 | 12 | A | M |
| 5 | [news-drift](2026-08-24-theory-news-drift-design.md) | underreaction continuation | 4 | 4 | 2 | 10 | A | M |
| 6 | [no-side-premium](2026-08-24-theory-no-side-premium-design.md) | YES/NO side bias (optimism tax) | 4 | 4 | 3 | 11 | A | S–M |
| 7 | [overreaction-fade](2026-08-24-theory-overreaction-fade-design.md) | political move reversal | 4 | 4 | 3 | 11 | A | M |
| 8 | [cross-venue-fair-value](2026-08-24-theory-cross-venue-fair-value-design.md) | cross-venue convergence | 3 | 3 | 3 | 9 | A | M |
| 9 | [smile-smoothing](2026-08-24-theory-smile-smoothing-design.md) | ladder shape | 4 | 3 | 3 | 10 | A | M |
| 10 | [econ-anchoring](2026-08-24-theory-econ-anchoring-design.md) | consensus anchoring on releases | 3 | 3 | 3 | 9 | A | M |
| 11 | [settled-but-trading](2026-08-24-theory-settled-but-trading-design.md) | resolution-source staleness | 4 | 3 | 3 | 10 | A | M–L |
| 12 | [new-market-anchor](2026-08-24-theory-new-market-anchor-design.md) | issuance mispricing (study) | 3 | 5 | 2 | 10 | A | S |
| 13 | [maker-mode-execution](2026-08-24-theory-maker-mode-execution-design.md) | execution layer: spread capture | 5 | 4 | 3 | 12 | A | M |
| 14 | [whale-follow](2026-08-24-theory-whale-follow-design.md) | proven-wallet mirroring | 3 | 2 | 3 | 8 | A (PM leg) | L |
| 15 | [vol-crossing](2026-08-24-theory-vol-crossing-design.md) | barrier-option model | 3 | 3 | 2 | 8 | A | M |
| 16 | [implication-graph](2026-08-24-theory-implication-graph-design.md) | cross-event logic | 2 | 2 | 3 | 7 | B | L |
| 17 | [insider-flow-radar](2026-08-24-theory-insider-flow-radar-design.md) | anomalous fresh flow | 2 | 2 | 2 | 6 | A (detector) | L |

**Where priority diverges from the composite score, sequencing is why:**
series-bias-mining (Σ12) and maker-mode-execution (Σ12) sit below
deadline-drift (Σ10) because the miner's value routes through *future*
theories rather than immediate bets, and maker-mode needs at least one
measured theory live before its paired backtest has anything to run on —
while deadline-drift's design is already user-agreed and adds a second
*lens* (time structure) early, which diversifies what the board scan can
see. news-drift (Σ10, L=2) ranks 5 despite the low likelihood because its
backtest is cheap, shared with overreaction-fade, and decisive either
way — high information per effort, not high expected edge.

Paired designs: news-drift ↔ overreaction-fade share one joint
sign-measurement (each claims only the cells measured its way);
cross-venue-fair-value's pair store is reused by whale-follow and
insider-flow-radar; structural-arb's sibling grouping is reused by
smile-smoothing; new-market-anchor can ride calibration-harvest's cell
matrix.

## Considered and parked (with why)

- **Weekend/overnight staleness** — real phenomenon, but needs intraday
  precision at the staleness window and the user bets at human hours;
  revisit if candlestick granularity supports a Monday-open drift the
  user could catch.
- **Poll-gap models for political markets** — modeling-heavy,
  election-cyclical, sharp competition; revisit after the cheap
  structural ideas are exhausted. Keyless public polling data exists.
- **Order-book market making / continuous spread capture** — wrong shape
  for a manual bettor; the one-sided, theory-gated version is
  maker-mode-execution (#13).
- **Kalshi leaderboard copying** — Kalshi exposes no per-trader identity;
  impossible by construction (Polymarket's transparency is why #14 and
  #17 exist).
- **LLM forecast-gap betting** — puts an introspected probability at the
  center of the procedure; the compliant reframing is `insider_bias`,
  which already exists. Parked as redundant, not wrong.

## Shared sources

Papers marked **read in full** were extracted and read during the
2026-08-24 sessions; quoted numbers come from their text.

- [Le 2026 — Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics](https://arxiv.org/pdf/2602.19520) (**read in full**; [replication repo](https://github.com/namanhzz/prediction-market-calibration)) — 353M trades; Politics slopes 1.32–1.83 (compressed toward 50%), Weather 0.69–0.87 short-horizon (too extreme), Sports 1.74 / Crypto 1.36 at 1mo+; universal horizon component 0.99 → 1.32; price 0.75 → 0.886 realized (Politics), 0.691 (Weather); large political trades compress more (1.74 vs 1.19).
- [Angelini & De Angelis 2026 — When Do Markets Fully Process Public Information?](https://arxiv.org/pdf/2606.07811) (**read in full**) — Kalshi NBA in-play: 0.64-for-one impact adjustment, predictable drift, worse when illiquid+salient; **not profitable net of bid–ask at minute scale**.
- [Whelan — Makers and Takers](https://www.karlwhelan.com/Papers/Kalshi.pdf) ([CEPR](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market)) — 300k+ contracts; favorite-longshot bias net of fees; taker losses.
- [Becker — The Microstructure of Wealth Transfer in Prediction Markets](https://www.jbecker.dev/research/prediction-market-microstructure) ([dataset](https://github.com/jon-becker/prediction-market-analysis)) — takers −1.12%/trade vs makers +1.12%; optimism tax (YES underperforms NO by up to 64pp at longshot prices); category inefficiency Finance 0.17pp → Entertainment 4.79–7.32pp.
- [Palumbo 2026 — A Microstructure Perspective on Prediction Markets](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6325658) — Kalshi NFL passive LPs profitable (~$29M/season aggregate) but directionally exposed; "underwriters, not market makers."
- [Clinton & Huang 2025 — Prediction Markets? $2.4B in the 2024 Election](https://ideas.repec.org/p/osf/socarx/d5yx2_v1.html) — negative daily autocorrelation, cross-exchange divergence, Kalshi 78% vs Polymarket 67% accuracy.
- [Reichenbach & Walther 2025 — Accuracy, Skill, and Bias on Polymarket](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5910522) — 478M trades; YES/default overtrading; no general longshot bias once side is accounted for.
- [Dalen 2025 — Toward Black-Scholes for Prediction Markets](https://arxiv.org/pdf/2510.15205) — event vega; pre-close uncertainty jitter.
- [Campbell & Sharpe (JFQA 2009)](https://www.federalreserve.gov/econres/steven-a-sharpe.htm) + [FEDS 2026 series](https://www.federalreserve.gov/econres/feds/2026.htm) — consensus anchoring; forecast errors predictable; re-confirmed 2012–2026.
- [Berg, Nelson & Rietz — Accuracy and Forecast Standard Error of Prediction Markets](https://www.biz.uiowa.edu/faculty/trietz/papers/forecasting.pdf) — Intrade horizon miscalibration.
- [Interest-bearing positions and the long-horizon problem](https://arxiv.org/pdf/2602.21091) — capital-lockup mechanism.
- [PredictionTalk 40-paper survey](https://predictiontalk.org/d/14-ai-parsed-40-papers-on-pm-inefficiencies-here-are-5-im-going-to-trade/) — practitioner aggregation: rebalancing-arb magnitudes, temporal-lag competition, wash-trading rates (Columbia SSRN 5714122: ~25% of PM volume; 45% sports), on-chain insider lead windows.
- Cross-venue gap documentation: [trevorlasn.com](https://www.trevorlasn.com/blog/how-prediction-market-polymarket-kalshi-arbitrage-works), [predictionhunt](https://www.predictionhunt.com/blog/why-same-market-different-prices-kalshi-polymarket), [public arb bot](https://github.com/ImMike/polymarket-arbitrage).
- Polymarket wallet-copy ecosystem: [Polycopy](https://polycopy.app/best-polymarket-traders), [copy-score backtest](https://polyloly.com/blog/polymarket-insider-tail-backtest-46-percent-roi), [wallet-selection traps](https://medium.com/@0xmega/how-to-find-the-best-polymarket-wallets-to-copy-trade-without-getting-rekt-26dd65123324).
