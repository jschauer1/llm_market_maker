# Theory Backlog — Index

Date: 2026-08-24 (superseded docs/theory-specs/, same content migrated to
official spec format and extended after a second literature pass)

Twenty-two researched, implementable theory design specs, one file per
theory, each written so a fresh session (no context beyond CLAUDE.md and
the spec) can pick it up and implement it. (Rounds: 12 from the first
literature pass, 5 from the second, 5 from the third — parlay-fade,
weather-model-gap, calendar-arb, attention-model, metaculus-gap.) This index holds the shared
contracts, the priority ranking, the parked ideas, and the shared
sources; every spec links back here instead of repeating them.

## Before implementing any spec

0. **Does this theory's edge live *between siblings of one Kalshi
   event*? If so, expect to find nothing, and measure before you
   build.** Kalshi lists and quotes the markets inside an event
   *together* — the same makers post the whole ladder or date-set — so
   they come out internally consistent by construction. Three independent measurements in 2026-08, from different
   directions, and no spec anticipated it:

   - **`calendar-arb`** (#12, now `dead`): zero violations at its own
     1c/leg buffer across 10 snapshots. Near-dated date ladders are
     siblings inside ONE event, so basket cost never fell below 1.000;
     cross-event ladders exist only at 1y+ where carry dwarfs a
     cent-scale edge. Study:
     `studies/2026-08-27-calendar-arb-firing-rate/`.
   - **`smile-smoothing`** (#11, now `dead`): at a tradeable liquidity
     floor, **97.6% of 959 strike rungs sat *exactly* on their own
     isotonic fit**, max deviation 1.5c, zero candidates. Deviations
     appeared only in rungs with median volume **0**, where the "mid" is
     an empty book rather than a price. Study:
     `studies/2026-08-29-smile-smoothing-ladder-flatness/`.

   - **`structural_arb`'s NO-basket path** (2026-08-29, exhaustive):
     with the event envelope making Kalshi's `mutually_exclusive` flag
     free, all **6,414** mutually-exclusive events on one board were
     checked directly. **Exactly 1** had a NO-basket costing less than
     its guaranteed payout, at 0.125c/leg against a 1c/leg buffer — **0
     tradeable**. This is the strongest form of the finding: not a
     sample, the whole board, from the direction most favourable to the
     thesis. See `theories/structural_arb/NOTES.md` 2026-08-29.

   The cheap check is a one-board measurement of the *dispersion the
   thesis needs*, run before any theory scaffolding — both of the above
   were settled in well under a session that way. Cross-**event**
   relative value is not covered by this warning and remains open; the
   closed channel is specifically within-event.

0b. **A pre-registration must name its inclusion rules and its power
   floor, not just its contrast.** Naming only the hypothesis leaves the
   rules that decide who is *in* the sample undeclared — and those rules
   routinely span the entire conclusion. Two independent failures on
   2026-08-29, hours apart, in different theories, by different sessions:

   - **`calibration_harvest`**: the pre-registered bar fixed a four-way
     horizon ordering. It failed. A two-group long-vs-short collapse was
     then chosen *after* seeing where the sign flipped and published as
     "pre-registered" (t 3.50 — also the best of three available splits).
     The proposed replacement estimator was no safer: a day-level
     regression on horizon-bin rank reads **+0.50/t 0.26** including days
     with ≥2 horizon bins and **+3.14/t 2.68** including only days with
     ≥3. The inclusion rule *was* the result. Retracted; see that
     theory's `NOTES.md` 2026-08-29 (correction).
   - **`series-bias-mining`**: the bar used *series count* as its power
     proxy. Count says nothing about whether a series can resolve the
     3–6pt effect worth betting; the median tested series had a minimum
     detectable effect of **13.5 pts**, so "0 of 17 flagged" meant *not
     measured*, not *calibrated*. See
     `studies/2026-08-29-series-bias-mining/`.

   **Caveat found the same day, by the floor's own author:** an
   SE-based power floor is **not outcome-neutral for binomial data.**
   Bernoulli variance is `p(1−p)`, so a series with an extreme win rate
   has a small SE and therefore a small MDE — the floor preferentially
   admits exactly the candidates where a large gap can sit. Measured in
   `series-bias-mining` pass 2: mean win rate **0.864** among series with
   MDE ≤ 8 versus **0.829** among MDE > 8, and the single flagged series
   was the most extreme in the population *and* had the lowest MDE. So
   prefer a floor on `n` and `n_days` where the design allows it, and
   where an SE-based floor is used, **report the outcome composition of
   who passed it** so the selection channel is visible rather than
   silent.

   So write down, before looking: the contrast **and** who is in the
   sample **and** the smallest effect the design can detect. If the
   answer to the last one is larger than a theory-grade edge, the run
   cannot inform the question and should be resized before it is run,
   not reinterpreted after. Report a failed pre-registered test *as
   failed*; a better-looking cut found afterwards is a hypothesis for the
   next population, never the headline.

0c. **If the theory scans many candidates, give it a negative control
   — a slice whose answer is already known.** A screen that reports hits
   tells you nothing on its own; a screen that reports *no* hits on data
   known to be fairly priced is a screen whose next positive is worth
   reading. Build the control into the run, not into a follow-up.

   Worked example: `series-bias-mining` carried `mention_family`'s ten
   series as a control, because that family is known from a
   full-coverage backtest (n=3,441, −1.53 net) to be priced fairly. All
   ten came back non-significant. That is the one thing that run
   established about its own guard — and it cost nothing, because the
   series were already in the population.

   Two rules that follow: measure the control, and **keep it out of the
   multiple-comparisons family** — correction budget spent on series
   nobody would promote only dilutes the real tests.

0d. **Build the fixtures before touching real data.** A fixture universe
   with a planted effect among known-null cases catches the bugs that
   look like discoveries. `series-bias-mining`'s caught one that would
   have flagged **every calibrated series**: its statistic was net of
   fees, and fees are a near-constant −1 to −3pt offset, so a perfectly
   calibrated series scored −1.12 with the *same sign in both halves* —
   sailing through the split-sample guard that existed to stop exactly
   that. A guard defeating itself, and it would have read as a finding.
   Score a bias gross; report net beside it for whether the bias is
   bettable.

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
| 8 | [parlay-fade](2026-08-24-theory-parlay-fade-design.md) | combo markup vs product-of-legs | 3 | 3 | 4 | 10 | A | M |
| 9 | [weather-model-gap](2026-08-24-theory-weather-model-gap-design.md) | ensemble forecast vs market | 4 | 3 | 3 | 10 | A | M |
| 10 | [cross-venue-fair-value](2026-08-24-theory-cross-venue-fair-value-design.md) | cross-venue convergence | 3 | 3 | 3 | 9 | A | M |
| 11 | ~~[smile-smoothing](2026-08-24-theory-smile-smoothing-design.md)~~ **DEAD 2026-08-29** | ladder shape | 4 | 3 | 3 | 10 | A | M |
| 12 | ~~[calendar-arb](2026-08-24-theory-calendar-arb-design.md)~~ **DEAD 2026-08-27** | date-ladder nesting logic | 3 | 4 | 3 | 10 | A | S |
| 13 | [econ-anchoring](2026-08-24-theory-econ-anchoring-design.md) | consensus anchoring on releases | 3 | 3 | 3 | 9 | A | M |
| 14 | [settled-but-trading](2026-08-24-theory-settled-but-trading-design.md) | resolution-source staleness | 4 | 3 | 3 | 10 | A | M–L |
| 15 | [new-market-anchor](2026-08-24-theory-new-market-anchor-design.md) | issuance mispricing (study) | 3 | 5 | 2 | 10 | A | S |
| 16 | [maker-mode-execution](2026-08-24-theory-maker-mode-execution-design.md) | execution layer: spread capture | 5 | 4 | 3 | 12 | A | M |
| 17 | [attention-model](2026-08-24-theory-attention-model-design.md) | Wikipedia attention vs box office | 3 | 3 | 3 | 9 | A | M |
| 18 | [metaculus-gap](2026-08-24-theory-metaculus-gap-design.md) | forecaster aggregate vs market | 2 | 3 | 3 | 8 | A | M |
| 19 | [whale-follow](2026-08-24-theory-whale-follow-design.md) | proven-wallet mirroring | 3 | 2 | 3 | 8 | A (PM leg) | L |
| 20 | [vol-crossing](2026-08-24-theory-vol-crossing-design.md) | barrier-option model | 3 | 3 | 2 | 8 | A | M |
| 21 | [implication-graph](2026-08-24-theory-implication-graph-design.md) | cross-event logic | 2 | 2 | 3 | 7 | B | L |
| 22 | [insider-flow-radar](2026-08-24-theory-insider-flow-radar-design.md) | anomalous fresh flow | 2 | 2 | 2 | 6 | A (detector) | L |

**Where priority diverges from the composite score, sequencing is why:**
series-bias-mining (Σ12) and maker-mode-execution (Σ12) sit below
deadline-drift (Σ10) because the miner's value routes through *future*
theories rather than immediate bets, and maker-mode needs at least one
measured theory live before its paired backtest has anything to run on —
while deadline-drift's design is already user-agreed and adds a second
*lens* (time structure) early, which diversifies what the board scan can
see. news-drift (Σ10, L=2) ranks 5 despite the low likelihood because its
backtest is cheap, shared with overreaction-fade, and decisive either
way — high information per effort, not high expected edge. parlay-fade
(Σ10) ranks 8 on the strength of its evidence (L=4, the highest-quality
new measurement in the backlog) despite workflow friction; calendar-arb
(Σ10) sits at 12 rather than beside structural-arb because its firing
rate is even less known and its two legs span separate event pages.

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
- **Settlement spillover** (round 3) — when market A settles, related
  markets (same entity, same series family) may reprice slowly; trade
  the lag. Parked because the related-market identification is either
  LLM-judgment (implication-graph's cost profile) or so conservative it
  rarely fires, and the clean mechanical subset — date ladders — is
  exactly [calendar-arb](2026-08-24-theory-calendar-arb-design.md).
  Revisit angle: mine candlestick history for *measured* co-movement
  pairs first, then trade only pairs with demonstrated propagation lag.
- **Same-game parlay correlation pricing** (round 3) — pricing
  correlated legs properly is a real modeling edge (an AMM-design
  literature exists), but it is the hard version of
  [parlay-fade](2026-08-24-theory-parlay-fade-design.md); parked until
  the cross-game version has evidence.

## Evidence folder — for reviewers

`evidence/` holds what a reviewing model needs to check the specs'
claims without redoing the research:

- [Evidence ledger](evidence/2026-08-24-evidence-ledger.md) — **start
  here when reviewing**: every load-bearing quantitative claim across
  the 22 specs, mapped to its source and graded A (primary read in
  full, transcribed with locators) / B (primary located,
  summary-verified) / C (practitioner, directly read) / D (secondhand
  aggregation — treat as a lead, not evidence). The ledger names the
  claims that still need verification at implementation time.
- [Le 2026 reading notes](evidence/2026-08-24-le-2026-calibration-notes.md) —
  full Table 4/5 transcriptions, isotonic checks, dataset description.
- [Angelini & De Angelis 2026 reading notes](evidence/2026-08-24-angelini-deangelis-2026-notes.md) —
  impact coefficient, Table 6 drift matrix, the verbatim
  executable-returns negative.

## Shared sources

Papers marked **read in full** were extracted and read during the
2026-08-24 sessions; quoted numbers come from their text and are
transcribed with locators in `evidence/`.

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
- [arXiv 2607.14430 — Prices, Probabilities, and Parlays](https://arxiv.org/abs/2607.14430) — 23M Kalshi moneyline trades; legs essentially perfectly calibrated in mid-life TTE buckets; cross-game parlays systematically overpriced vs product of legs, growing with leg count. Combo mechanics: [Sportico RFQ explainer](https://www.sportico.com/business/sports-betting/2025/kalshi-parlay-combo-rfq-explainer-1234877038/), [Penny Parlay criticism](https://www.gamblinginsider.com/news/180114/kalshi-penny-parlay-worst-bet-in-america-smallest-bettors-buying-it).
- Weather practitioner documentation: [botforkalshi](https://www.botforkalshi.com/blog/kalshi-weather-trading-strategy), [PillarLab playbook](https://pillarlabai.com/blog/how-to-trade-temperature-markets-kalshi/) — per-station settlement, ~2°F fee cushion, 8pp entry floors, NWS bias patterns; keyless data at [api.weather.gov](https://api.weather.gov) and [Open-Meteo](https://open-meteo.com).
- [Mestyán, Yasseri & Kertész 2013](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0071226) — Wikipedia activity predicts opening box office ~a month ahead.
- Forecaster-aggregate evidence: [platform-comparison work](https://manifund.org/projects/comparing-forecasting-platform-accuracy), [Metaculus's own markets-vs-polls argument](https://www.metaculus.com/notebooks/17599/why-i-reject-the-comparison-of-metaculus-to-prediction-markets/).
- Polymarket wallet-copy ecosystem: [Polycopy](https://polycopy.app/best-polymarket-traders), [copy-score backtest](https://polyloly.com/blog/polymarket-insider-tail-backtest-46-percent-roi), [wallet-selection traps](https://medium.com/@0xmega/how-to-find-the-best-polymarket-wallets-to-copy-trade-without-getting-rekt-26dd65123324).
