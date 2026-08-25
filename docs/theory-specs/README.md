# Theory Spec Backlog

Written 2026-08-24. One spec per file, each written so a fresh session (no
context beyond CLAUDE.md and the spec itself) can pick it up and implement
it. This README holds the shared contracts and the priority ranking; every
spec links back here instead of repeating them.

## Before implementing any spec

1. `python -m tools.cli ideas search "<slug>"` — confirm nothing has changed
   since the spec was written (each spec is recorded in the registry under
   its slug; check its `status` and `outcome`).
2. Use the `propose-theory` skill to formalize the chosen idea into
   `theories/<slug>/` with a THEORY.md before writing procedure code.
3. Follow the repo contracts in CLAUDE.md. The ones implementers most often
   miss: entry prices are the **ask**, never the mid; every recorded edge
   carries an `edge_basis` (`measured`/`model`/`prior` — never a felt sense);
   any LLM in the decision path requires provenance records and prompts on
   disk; any change to a decision procedure bumps the theory version; backtest
   tier A means **no LLM anywhere in the decision path**.
4. Reuse the validated patterns already in the repo: the price-bin bucket
   pattern in `theories/insider_bias/mention_family/mention_bucket.py`
   (`PRICE_BINS`, `bucket_for_price`, measured rates via `tools/buckets.py`),
   the code-gate-with-category-report pattern in
   `theories/insider_bias/insider_judgment/gate.py`, the tier-A backtest
   pattern in `theories/insider_bias/insider_judgment/backtest.py`, and fee
   math from `tools/sizing.py`. The session board comes from
   `tools.board.get_board(conn)` — never `markets.list_open()` directly.

## Priority ranking (effort is S/M/L)

| # | spec | lens | LLM in path? | backtest tier | effort | why this rank |
|---|------|------|--------------|---------------|--------|---------------|
| 1 | [calibration-harvest](calibration-harvest.md) | price/base rates | no | A | S | fastest path to huge-n evidence; directly documented on Kalshi |
| 2 | [deadline-drift](deadline-drift.md) | time structure | no | A | M | design already agreed in-session; documented mechanism |
| 3 | [structural-arb](structural-arb.md) | logical consistency | no | A | S | near-risk-free when it fires; trivial to run forever |
| 4 | [series-bias-mining](series-bias-mining.md) | per-series base rates | no | A | M | a machine for finding more mention_families |
| 5 | [news-drift](news-drift.md) | microstructure/momentum | no | A | M | documented underreaction; candlesticks are enough |
| 6 | [cross-venue-fair-value](cross-venue-fair-value.md) | cross-venue flow | match-time only | A/B | M | uses this repo's unique Polymarket tooling |
| 7 | [smile-smoothing](smile-smoothing.md) | cross-sectional shape | no | A | M | soft sibling of structural-arb, more firings |
| 8 | [settled-but-trading](settled-but-trading.md) | resolution mechanics | no | A | M–L | closest to free money, but per-family resolvers |
| 9 | [whale-follow](whale-follow.md) | smart-money flow | match-time only | A (on PM side) | L | strong evidence, most infrastructure |
| 10 | [vol-crossing](vol-crossing.md) | stochastic model | no | A | M | clean model family; crypto ladders have huge n |
| 11 | [new-market-anchor](new-market-anchor.md) | issuance mechanics | no | A | S | cheap measurement study; theory only if bias found |
| 12 | [implication-graph](implication-graph.md) | logical consistency (far) | construction only | B-ish | L | novel lens; hardest to keep clean |

## Considered and parked (with why)

- **Weekend/overnight staleness** — trade markets whose underlying moves
  24/7 while Kalshi books sleep. Real phenomenon, but it needs intraday
  precision at the exact staleness window and the user bets manually at
  human hours; the tradeable overlap is thin. Revisit if candlestick
  granularity turns out to be fine enough to measure a Monday-open drift the
  user could actually catch.
- **Poll-gap models for political markets** — external polling aggregates vs
  price. Modeling-heavy, election-cyclical, and the sharp end of Kalshi
  politics is competitive; low priority until the cheap structural ideas are
  exhausted. Keyless public polling data exists if revisited.
- **Order-book market making / spread capture** — wrong shape for this
  system: the user places occasional manual bets and cannot quote
  continuously.
- **Kalshi leaderboard copying** — Kalshi exposes no per-trader identity;
  impossible by construction. (Polymarket's transparency is why
  [whale-follow](whale-follow.md) exists.)
- **LLM forecast-gap betting** ("research the news, disagree with the
  price") — explicitly the kind of idea CLAUDE.md warns about: it puts an
  introspected probability at the center of the procedure. Only viable if
  reframed as classification against checkable criteria with measured
  buckets, which is... `insider_bias`, which already exists. Parked as
  redundant, not wrong.

## Shared sources

The two papers marked **read in full** were extracted and read during the
2026-08-24 session; the numbers quoted in the specs come from their text,
not from abstracts or secondhand summaries.

- [Whelan — Makers and Takers: The Economics of the Kalshi Prediction Market](https://www.karlwhelan.com/Papers/Kalshi.pdf) ([CEPR summary](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market)) — 300k+ Kalshi contracts; favorite-longshot bias net of fees.
- [Market Efficiency and the Favorite-Longshot Bias in Unemployment Prediction Markets](https://www.researchgate.net/publication/409238145_Market_Efficiency_and_the_Favorite-Longshot_Bias_in_Unemployment_Prediction_Markets) and [Information Efficiency Across Macroeconomic Prediction Markets: Evidence from Kalshi](https://www.researchgate.net/publication/409472804_Information_Efficiency_Across_Macroeconomic_Prediction_Markets_Evidence_from_Kalshi) — domain-specific calibration on Kalshi macro markets.
- [Le 2026 — Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics in Prediction Markets](https://arxiv.org/pdf/2602.19520) (**read in full**) — 353M trades / 429k contracts, Kalshi (Jul 2021–Dec 2025) + Polymarket. Table 4 slopes by domain × horizon: Politics 1.32–1.83 beyond 3h (compressed toward 50%, replicates on Polymarket); Weather 0.69–0.87 within 12h (too extreme); Sports 1.74 and Crypto 1.36 at 1mo+; universal horizon component 0.99 → 1.32. Isotonic checks: price 0.75 → 0.886 realized (Politics), 0.691 (Weather). Large political trades compress *more* (slope 1.74 vs 1.19). [Replication repo](https://github.com/namanhzz/prediction-market-calibration).
- [Angelini & De Angelis 2026 — When Do Markets Fully Process Public Information?](https://arxiv.org/pdf/2606.07811) (**read in full**) — Kalshi NBA in-play, one-minute quotes vs public-information benchmark: 0.64-for-one adjustment on impact; the gap predicts minutes-scale drift, worse when illiquid + salient; **drift not profitable net of bid–ask at that timescale**.
- [Accuracy and Forecast Standard Error of Prediction Markets (Berg, Nelson, Rietz)](https://www.biz.uiowa.edu/faculty/trietz/papers/forecasting.pdf) — Intrade horizon-dependent miscalibration.
- [Can Interest-Bearing Positions Solve the Long-Horizon Problem in Prediction Markets?](https://arxiv.org/pdf/2602.21091) — capital-lockup mechanism distorting long-horizon prices toward 0.5.
- Cross-venue gap documentation: [trevorlasn.com on PM/Kalshi arb](https://www.trevorlasn.com/blog/how-prediction-market-polymarket-kalshi-arbitrage-works), [predictionhunt on why prices differ](https://www.predictionhunt.com/blog/why-same-market-different-prices-kalshi-polymarket), [public arb bot](https://github.com/ImMike/polymarket-arbitrage).
- Polymarket wallet-copy ecosystem: [Polycopy trader rankings](https://polycopy.app/best-polymarket-traders), [copy-score backtest write-up](https://polyloly.com/blog/polymarket-insider-tail-backtest-46-percent-roi), [finding wallets without getting rekt](https://medium.com/@0xmega/how-to-find-the-best-polymarket-wallets-to-copy-trade-without-getting-rekt-26dd65123324) — profitability base rates, scoring traps (spread-capture bots, wallet rotation).
