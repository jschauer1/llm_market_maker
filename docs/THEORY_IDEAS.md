# Theory Idea Backlog

Written 2026-08-24. A backlog of researched, implementable theory ideas for this
repo. Each entry is written so a fresh session (no context beyond CLAUDE.md and
this file) can pick it up and implement it.

**Before implementing any idea here:**

1. `python -m tools.cli ideas search "<keyword>"` — confirm nothing has changed
   since this file was written (each idea below is recorded in the registry
   under its slug; check its `status` and `outcome`).
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

**Prioritization at a glance** (my ranking; effort is S/M/L):

| # | slug | lens | LLM in path? | backtest tier | effort | why this rank |
|---|------|------|--------------|---------------|--------|---------------|
| 1 | `calibration-harvest` | price/base rates | no | A | S | fastest path to huge-n evidence; directly documented on Kalshi |
| 2 | `deadline-drift` | time structure | no | A | M | design already agreed in-session; documented mechanism |
| 3 | `structural-arb` | logical consistency | no | A | S | near-risk-free when it fires; trivial to run forever |
| 4 | `series-bias-mining` | per-series base rates | no | A | M | a machine for finding more mention_families |
| 5 | `news-drift` | microstructure/momentum | no | A | M | documented underreaction; candlesticks are enough |
| 6 | `cross-venue-fair-value` | cross-venue flow | match-time only | A/B | M | uses this repo's unique Polymarket tooling |
| 7 | `smile-smoothing` | cross-sectional shape | no | A | M | soft sibling of structural-arb, more firings |
| 8 | `settled-but-trading` | resolution mechanics | no | A | M–L | closest to free money, but per-family resolvers |
| 9 | `whale-follow` | smart-money flow | match-time only | A (on PM side) | L | strong evidence, most infrastructure |
| 10 | `vol-crossing` | stochastic model | no | A | M | clean model family; crypto ladders have huge n |
| 11 | `new-market-anchor` | issuance mechanics | no | A | S | cheap measurement study; theory only if bias found |
| 12 | `implication-graph` | logical consistency (far) | construction only | B-ish | L | novel lens; hardest to keep clean |

Sources for the evidence claims are collected at the bottom of this file.

---

## 1. `calibration-harvest` — board-wide favorite-longshot harvesting

**Thesis.** Kalshi prices are systematically miscalibrated as a function of
price, horizon, and category — and the *direction* of the miscalibration
depends on the (domain × horizon) cell. Bet the side each cell's measured
realized rate says is cheap, when the gap exceeds the ask plus fees.

**Why the edge should exist.** This is the favorite-longshot bias, the oldest
documented anomaly in betting markets (Griffith 1949), and it has been
measured *on Kalshi specifically*, twice, at scale, with signed magnitudes:
- Whelan ("Makers and Takers", 300,000+ contracts): low-price contracts win
  far less often than break-even requires after fees; high-price contracts
  win more often and yield small positive returns.
- Le 2026 (353M trades, 429k contracts across Kalshi + Polymarket; read in
  full for this backlog; replication repo public): calibration slopes by
  domain × horizon, Table 4. **Politics is compressed toward 50% at nearly
  all horizons** (slopes 1.32–1.83 beyond 3h; a 70¢ political contract one
  week out maps to ≈83%; at a raw price of 0.75 the isotonic estimate is
  0.886 — a ~13-point gross gap on the favorite side). **Weather is the
  opposite at short horizons** (slopes 0.69–0.87 within 12h; a 75¢ weather
  contract is really 69.1% — the *favorite* is rich and the fade side is
  cheap). Sports and crypto are near-calibrated short-dated but compressed
  long-dated (slopes 1.74 and 1.36 beyond one month). The universal horizon
  component rises from 0.99 (0–1h) to 1.32 (1mo+): everything compresses
  toward 50% as horizon grows.

The repo's own `mention_family` work independently rediscovered the same
shape in one family: win rate rises from 0.73 below $0.75 to 1.00 at $0.85+.
The mechanism is structural (lottery-ticket preference on the cheap side,
capital lockup aversion on the expensive side), so it should decay slowly if
at all.

**Procedure.** Fully mechanical, no stage 2.
- Cells are **signed**: a cell's trade can be "buy the favorite" (politics,
  most horizons; anything long-dated) or "fade the favorite" (short-horizon
  weather). Never encode a universal buy-favorites rule — Le's Table 4 shows
  the sign flips by domain, and this repo must re-measure the signs on its
  own settled history rather than importing the paper's numbers as the edge
  (`edge_basis="measured"` means *our* measurement; the paper is the prior
  that says where to look, and two pre-registered cells to check first:
  political favorites at 2d–1mo horizons, and short-dated weather extremes).
- Screen: every market on the board with YES ask in a configurable band
  (start: $0.65–$0.97 on the favorite side, plus the mirrored fade band where
  a cell's sign says so), and a liquidity floor. Do not hard-cap
  days-to-close at 14 — the documented compression *grows* with horizon, so
  bin horizon (≤2d / 2d–1w / 1w–1mo / 1mo+) instead of truncating it, and
  let capital lockup enter through sizing (`tools/sizing.py`), not through
  the screen. Exclude families already claimed by a running theory
  (`mention_family`'s MENTION/SAY/ACT tickers) so two theories never book the
  same trade — do the exclusion by series-ticker pattern and report what was
  excluded, gate.py-style.
- Edge: `edge = realized_rate(cell) − ask − fees`, where `realized_rate` comes
  from tier-A measurement over settled history, binned by
  (price bin × horizon bin × coarse category). `edge_basis="measured"` for
  cells with n ≥ 30, `"model"` for thinner cells if reported at all. Use
  Wilson lower bounds, not point rates, for thin cells — the mention_family
  log already flagged that an unshrunk 1.000 win rate (n=41) is a defect.
- Rank across candidates by net edge; size via `tools/sizing.py`.

**Backtest.** Tier A. Split settled history in half by time; measure cell
rates on the first half, evaluate P&L of the rule on the second half. This
guards against the main statistical trap: with many cells, some look golden
by chance. A cell only counts if it survives out-of-sample.

**Kill criteria.** If no cell clears fees out-of-sample at n ≥ 30, the bias
exists but is priced in — record that in the registry and stop. Partial
survival (e.g., only $0.90+ within 7 days) is a success, not a failure;
narrow the screen to the surviving cells.

**Build notes.** `theories/calibration_harvest/{THEORY.md,screen.py,cells.py}`
plus tests. Reuse `mention_bucket.py`'s structure for `cells.py`. Effort S —
this is mention_family's math with a wider screen. The overlap-exclusion list
is part of the versioned procedure.

---

## 2. `deadline-drift` — "nothing happens by the date"

**Thesis.** Markets that resolve YES only if a discrete, *unscheduled*
affirmative event occurs by a deadline (bill signed, resignation, deal
announced, ceasefire declared, indictment filed) systematically overprice YES
as the deadline approaches with no event. Buy NO in the late window when the
market's implied hazard exceeds the historical hazard by more than fees.

**Why the edge should exist.** Three mechanisms, two documented. (a) Longshot
bias: late-window YES on a quiet market *is* a longshot, and longshots are
overpriced (see idea 1's evidence). (b) Capital asymmetry: an Intrade study
of 500k+ transactions found high-likelihood events underpriced and
low-likelihood events overpriced specifically at long horizon, driven by NO
requiring more locked capital per unit of profit — holders of hopeful YES
positions are slow to capitulate. (c) Anchoring: the story that made the
market interesting keeps its price sticky even as the clock runs out.
Quantitative support from Le 2026: buying NO here means buying a favorite,
and favorites are measurably underpriced in exactly the relevant cells —
political markets (where most unscheduled affirmative-event markets live)
show calibration slopes of 1.48–1.83 from 12h out to a month, i.e., the
market's residual hope in YES is systematically too expensive.

**Procedure.** Fully mechanical, no LLM. Design agreed with the user in the
2026-08-24 session:
- Screen: by-date affirmative-event markets identified from rules-text
  patterns ("occurs by", "before <date>", "on or before") plus a family
  exclusion list, with a per-category report of exclusions (gate.py pattern).
  Two families are explicitly *not* the thesis: **scheduled certainties**
  (games, earnings, launches with fixed dates — no hazard process) and
  **continuous-threshold markets** ("BTC above X by date", weather — those are
  level-crossing processes; see `vol-crossing`, idea 10).
- Filter: days-to-close ≤ 21, YES ask in ~$0.05–$0.60 (above the band the
  market believes the event happened or is locked in; below it fees eat the
  residual), liquidity floor on the NO ask.
- Edge: empirical bins over settled by-date markets —
  `P(resolves YES | price p, t days remaining)` in (time × price) bins from
  ~12 months of candlestick history (`tools/kalshi/history.py`).
  `edge = (1 − P_hat(YES)) − NO_ask − fees`, `edge_basis="model"`.
  Rejected alternative, for the record: fitting a per-market constant-hazard
  curve from the market's own early price path assumes the early price was
  right, which contaminates the measurement. Parametric hazard by category is
  a v2 once bins have data.

**Backtest.** Tier A. Lookahead trap specific to this idea: "the event hasn't
happened yet" must be inferred only from the price path at decision time
(price not yet ≥ ~0.90), never from the settlement we already know. Also
split-sample as in idea 1: bin rates from the first half of history, P&L on
the second.

**Kill criteria.** If implied and empirical hazard agree within fees across
all bins, the market prices decay correctly — kill it. If the screen's
rules-text classifier shows > ~10% misclassification on a hand-audited sample
of 50, fix the screen before trusting any bin (misclassified threshold
markets pool a different process into the bins and poison the measurement —
this is the design's known weak joint).

**Build notes.** `theories/deadline_drift/{THEORY.md,screen.py,hazard_bucket.py}`
plus tests. Effort M — the screen's rules-text classification and its audit
are most of the work; the bucket math is mention_bucket.py again.

---

## 3. `structural-arb` — monotonicity and basket-sum violations

**Thesis.** Within a single event, prices must satisfy hard logical
constraints: a strike ladder must be monotone (P(above 50k) ≥ P(above 60k)),
and a mutually-exclusive-exhaustive outcome set must have YES prices summing
to ≥ $1 at the bid and ≤ $1 + spread at the ask. When executable quotes
violate a constraint by more than fees, the trade is close to risk-free.

**Why the edge should exist.** Retail flow hits individual strikes without
repricing siblings, and Kalshi has no cross-contract margining to force
consistency. Public cross-platform arb bots exist (several on GitHub), which
caps how long violations last — but a scanner that runs every session costs
nearly nothing, and the user only needs the violation to exist at the moment
they look. Expected firing rate: low. Expected edge when it fires: real.

**Procedure.** Fully mechanical. From the board, group markets by
`event_ticker`; for ladders (detect strike-ordered siblings from ticker
structure), check ask-side monotonicity violations net of fees; for
mutually-exclusive events, check `sum(YES asks) < 1 − fees` (buy the basket)
and `sum(NO asks) < (k−1) − fees`. Require a buffer (start: 1¢ per leg) and
top-of-book size on every leg. `edge_basis="model"` — the edge is arithmetic.
One caveat to encode: confirm from the event metadata that the outcome set is
actually exhaustive (some Kalshi events have an implicit "none of the above"
that never trades); non-exhaustive sets only support the monotonicity check,
not basket sums.

**Backtest.** Tier A against snapshot history: replay stored board snapshots
(`tools/snapshot.py` keeps complete raw payloads) and count violations that
were executable net of fees. Note the honesty constraint: snapshots are
point-in-time, so the backtest measures *existence*, not persistence — say so
in THEORY.md rather than claiming fill certainty.

**Kill criteria.** Not applicable in the usual sense — the theory can't be
wrong, only idle. If it fires zero times in 60 days of sessions, record that
and leave it running; it costs nothing.

**Build notes.** `theories/structural_arb/{THEORY.md,scan.py}` plus tests
with constructed violation fixtures. Effort S. This is also the natural home
for a shared "group siblings by event" helper that `smile-smoothing` (idea 7)
will want later — build it in the theory first per the repo's promotion rule.

---

## 4. `series-bias-mining` — a machine for finding more mention_families

**Thesis.** `mention_family` was found by accident: a backtest slice showed
one recurring series family with a persistent, exploitable bias. There is no
reason it is the only one. Mine *every* recurring series with enough settled
history for persistent price-vs-outcome bias, and promote the survivors into
their own bucketed sub-theories.

**Why the edge should exist.** Recurring series (daily/weekly
weather, econ prints, pop-culture recurrences) are traded by habitual retail
flow with stable behavioral biases, and each series has its own resolution
quirks that casual traders misprice consistently. The domain-specificity
finding (Fed markets calibrated, inflation/unemployment not) says bias lives
at the *family* level, not the board level — which is exactly what a per-series
miner exploits and a board-wide average washes out.

**Procedure.** Fully mechanical, and mostly a *measurement pipeline* rather
than a screen:
- For every series with ≥ 30 settled markets in history: at fixed decision
  points (7d, 3d, 1d before close), record (price, outcome) pairs from
  candlesticks; compute realized rate vs mean price per price bin; flag
  series where the gap clears fees with a Wilson interval excluding zero.
- Guard against multiple comparisons — this is the idea's central statistical
  risk. With hundreds of series, dozens will look biased by chance. Require:
  bias present in the first half of the series' history AND the second half,
  same sign, before flagging.
- Output: a ranked list of candidate families, each with its measured bin
  table. Each survivor becomes a small bucketed theory (or a new bucket under
  a shared umbrella theory — decide in THEORY.md; separate theories keep
  track records clean and is the safer default).

**Backtest.** The miner *is* a tier-A backtest. The live theory that follows
each discovered family inherits the family's measured rates as
`edge_basis="measured"` only for the exact bins the split-sample test
validated.

**Kill criteria.** If nothing survives the split-sample test, the board's
recurring series are calibrated — a valuable negative result; record it. If
survivors appear but their live settlements regress hard (measured rate
minus live rate > 10 points at n ≥ 20), the miner is overfitting; tighten the
split test before mining again.

**Build notes.** `theories/series_miner/{THEORY.md,mine.py}` plus tests.
Effort M — the work is careful statistics, not plumbing. The candlestick
fetch loop over hundreds of series should batch and cache aggressively
(`tools/kalshi/history.py`); ~12 months is the available depth.

---

## 5. `news-drift` — underreaction momentum from candlesticks

**Thesis.** When a Kalshi price moves sharply (new information arriving), it
underreacts: the move continues in the same direction over the following
hours-to-days. Enter in the direction of a large recent move, hold to
resolution (v1) or for a fixed horizon (v2).

**Why the edge should exist — and the honest caution.** Underreaction and
post-news drift are among the most robust findings in behavioral finance
(post-earnings-announcement drift; Hong–Stein slow information diffusion).
Angelini & De Angelis 2026 measured it *on Kalshi directly* (NBA in-play
markets, one-minute quotes vs a public-information benchmark): prices adjust
only **0.64-for-one on impact**, the missing adjustment predicts drift over
the following minutes, and underreaction is worse when liquidity is thin and
signals are salient. The caution is in the same paper: **the minute-scale
drift was not profitable net of bid–ask costs.** So the only direct Kalshi
test of this phenomenon found it real but untradeable at that timescale.
This idea's bet is therefore specifically that *slower* drift — daily-scale
moves on politics/econ/entertainment markets, where information diffuses
over days rather than seconds — is large enough to clear the spread. That is
plausible (the drift horizon in equities is weeks, not minutes) but it is an
extrapolation beyond the measured setting, and the backtest exists to check
exactly this.

**Procedure.** Fully mechanical.
- Scope: **exclude live sports entirely** — that family is where the net
  drift is already measured dead, and it resolves too fast for manual bets
  anyway. Target domains where information arrives in stories, not
  scoreboard ticks: politics, econ, entertainment, world events.
- Signal: from candlesticks, a move of ≥ X points (start: 15) within ≤ 24h,
  with volume above the market's own trailing median (a price jump on no
  volume is a stale-quote artifact, not news). Price after the move within
  $0.15–$0.85 (room to drift; avoids resolved-in-fact markets).
- Entry: the **ask on the move side** as of the first candle after the signal
  completes — never the mid, and never a price inside the signal window.
- Edge: measured, not assumed — the backtest produces
  `P(resolves in move direction | signal)` vs the post-signal ask, binned by
  move size and post-move price. `edge_basis="measured"` once bins have n.

**Backtest.** Tier A, candlesticks only. Lookahead traps: (a) the signal must
be computed from completed candles only; (b) entry at the *next* candle's
ask, not the signal candle's close; (c) exclude moves driven by the
resolution event itself (a move to $0.98 an hour before settlement is the
outcome arriving, not news to trade on — the price-band filter handles most
of this, but check close-time proximity too).

**Kill criteria.** If drift exists gross but dies net of the spread + fees
(likely in thin markets — the documented drifts are small), record the
gross/net split explicitly; that distinguishes "no phenomenon" from "real
phenomenon, untradeable here", which have different revisit angles (the
latter revives if Kalshi liquidity deepens).

**Build notes.** `theories/news_drift/{THEORY.md,signal.py}` plus tests.
Effort M. Candlestick granularity (`tools/kalshi/history.py`) bounds how
precise entry timing can be — check the finest interval the API provides and
state it in THEORY.md before trusting the backtest.

---

## 6. `cross-venue-fair-value` — Polymarket as the fair price for Kalshi

**Thesis.** On events listed on both venues, Polymarket is usually deeper and
sharper (larger positions, professional flow, per-wallet accountability).
Treat the Polymarket mid as fair value; when the Kalshi ask is cheap against
it beyond fees plus a divergence threshold, buy the Kalshi side that
converges. This is a *one-sided* trade — the user can only bet Kalshi — so it
carries event risk, unlike true two-leg arb, and needs a bigger threshold
than an arb bot would use.

**Why the edge should exist.** Persistent 1–5% cross-venue gaps are widely
documented, driven by different user bases, fee structures, and capital
frictions. Two-leg arb is competed (public bots exist), but one-sided
convergence-taking is a different, riskier trade with a wider moat — it
requires believing one venue is *right*, not just that they disagree. The
direction of "who is right" is testable, not assumed (see backtest).

**Procedure.**
- Maintain a stable of confirmed matched pairs. Matching is the hard part and
  the only place judgment enters: `tools/match_market.py` produces
  candidates; confirmation compares **resolution criteria, not topic**
  (different resolution sources or deadlines make a "same" market a different
  bet). Confirmation can be an LLM stage (record provenance + prompt on
  disk) or the user by hand for the first N pairs — recommend hand-confirming
  the first stable, because a bad match is this theory's worst failure mode
  and hand-checking doubles as prompt calibration for automating later.
  Match confirmation is *not* in the per-trade decision path — a confirmed
  pair is a static fact — so per-trade decisions stay mechanical.
- Per-trade: `edge = |PM_mid − K_ask side-adjusted| − fees − threshold`, with
  a PM liquidity floor (thin PM books are not fair value; require PM volume
  and depth minimums). `edge_basis="model"`.

**Backtest.** Tier A on the mechanical rule over historical prices of
hand-confirmed pairs (both venues expose history; Polymarket via
`tools/polymarket/markets.py`). Two things to measure, in order: (1) does the
gap predict *convergence direction* — i.e., when they disagree, who moves?
If Kalshi converges to Polymarket more often than the reverse, the fair-value
premise holds; if not, kill the idea before betting anything. (2) P&L of the
threshold rule net of fees.

**Kill criteria.** Premise test (1) failing. Or: gaps exist but only on pairs
whose resolution criteria differ subtly — that's not mispricing, it's two
different bets; if > ~20% of candidate "gaps" turn out to be
criteria-mismatch on audit, the matching bar needs raising before the theory
can run.

**Build notes.** `theories/cross_venue/{THEORY.md,pairs.py,divergence.py}`.
Effort M. Pair store lives in SQLite with the confirmation evidence
(who/what confirmed, date, criteria notes) — pairs are versioned facts, and a
resolution-criteria change on either venue invalidates a pair.

---

## 7. `smile-smoothing` — soft mispricing across strike ladders

**Thesis.** Even when a strike ladder is monotone (no hard `structural-arb`
violation), individual strikes get pushed off the smooth implied distribution
by uninformed flow. Fit a monotone probability curve across the ladder; bet
the strike whose price deviates most from the fit, toward the fit, when the
deviation clears fees.

**Why the edge should exist.** Same mechanism as idea 3 — retail hits single
strikes without repricing siblings — but the soft version fires far more
often than hard violations. The fitted curve pools information from the whole
ladder, which is more data than any single strike's book. This is standard
practice in options markets (smile smoothing); Kalshi ladders (CPI, temps,
crypto ranges, box office) are the same object with worse participants.

**Procedure.** Fully mechanical. Group ladder siblings by event; fit an
isotonic (shape-constrained, assumption-light — preferable to parametric
first) curve to mid prices; compute each strike's deviation; candidate =
deviation > fees + buffer at the executable quote (ask if buying, bid side
via NO if selling — express everything as buying YES or NO at the ask).
`edge_basis="model"`. Liquidity floor per strike; skip ladders with < 4
liquid strikes — the fit is meaningless.

**Backtest.** Tier A. For settled ladders in history: at decision points,
fit on that day's prices, take the rule's trades, settle them. Trap: fitting
on mids but "trading" at mids overstates the edge badly on thin strikes —
the backtest must charge the historical spread (candlesticks carry bid/ask).

**Kill criteria.** If deviations mean-revert to the curve but the *curve*
was wrong (deviating strikes settle in their own favor as often as not), the
"noise trader" premise is wrong — the deviant strike is where the informed
flow was. That result inverts the theory and is worth knowing; test the
direction explicitly before trusting the sign.

**Build notes.** `theories/smile_smoothing/{THEORY.md,fit.py}`. Effort M.
Depends on the sibling-grouping helper from `structural-arb` (idea 3) —
build that one first, or build the helper here and share later per the
promotion rule.

---

## 8. `settled-but-trading` — the answer is public, the price hasn't moved

**Thesis.** Some markets resolve on machine-readable public data with a known
release moment (econ prints, official weather observations, published
rankings/charts). In the window between "the determining fact is public" and
"the market reprices to ~$0.99", buying the determined side is close to free
money at retail speed — minutes to hours, not milliseconds.

**Why the edge should exist.** Kalshi settlement lags its sources, and casual
markets have nobody assigned to reprice them at release time. The edge decays
with venue maturity but re-arises with every new listed family. Unlike HFT
races, the user's manual-betting workflow can actually capture hour-scale
staleness.

**Procedure.** Per-family resolvers, pure code:
- Start with one family where the source is keyless and structured — NWS/NOAA
  observations for settled-weather markets (api.weather.gov requires no key;
  the repo's no-API-keys rule permits keyless public endpoints) or scheduled
  federal releases (BLS/BEA publish at fixed timestamps).
- Resolver contract: given a market's rules, compute the resolved side from
  the source, or return "not determinable" — the resolver must be
  conservative, since its false positives are instant losses. Candidate =
  resolver says determined AND ask of the determined side ≤ $0.97.
  `edge_basis="model"`.
- Report per-family coverage (how many board markets the resolver can read)
  every run, gate-report style.

**Backtest.** Tier A and unusually clean: historical release timestamps are
public, candlesticks show the price path after each release. Measure: how
often was the determined side buyable ≤ $0.97 at T+30min after release, and
did it ever *lose* (a resolver bug or a rules subtlety — e.g., Kalshi
resolving on a revised figure, or a different station than the resolver
read). Any historical loss is a resolver defect to fix before going live.

**Kill criteria.** Per family: if the T+30min buyable rate is ~zero across
history, that family is efficiently repriced; move to the next family. The
theory dies only when several families in a row show no window.

**Build notes.** `theories/settled_trading/{THEORY.md,resolvers/}`. Effort M
for the first family, then S per additional family. The rules-reading per
family is the risk — each resolver's first version should be validated
against 20+ historical settlements before its output is ever bettable.

---

## 9. `whale-follow` — mirror proven Polymarket wallets into Kalshi

**Thesis.** Polymarket exposes per-wallet trade history; a small minority of
wallets are persistently profitable. Score wallets on realized,
fee-adjusted PnL over a trailing window; when a top-scored wallet opens or
adds meaningfully to a position, mirror it into the matched Kalshi market.

**Why the edge should exist.** Skill persistence is measurable there:
only ~13% of Polymarket wallets are profitable at all, and public backtests
of copy-scoring report meaningful win rates for top-scored wallets'
subsequent trades. The whole premise is testable offline before a dollar
moves. Known traps from the copy-trading ecosystem, to design around:
spread-capture bots look profitable but their edge is *execution* (copying
them at market buys what they already skimmed) — filter by holding time and
avoid wallets whose PnL comes from maker-side scalping; top wallets rotate
addresses — scores must decay and re-earn.

**Procedure.**
- Offline scoring pipeline over `tools/polymarket/trades.py` history:
  per-wallet realized PnL, win rate, n, holding time, category concentration.
  Score = shrunk PnL rate (same n/(n+k) shrinkage philosophy as
  `tools/rank.py`). All code.
- Signal: top-decile wallet takes a new position ≥ its own median size.
- Mirror: `tools/match_market.py` → confirmed Kalshi pair (same pair-store
  discipline as idea 6 — reuse it) → buy the same side at the Kalshi ask if
  it is within a tolerance of the whale's PM entry. `edge_basis="model"`
  (the model is the wallet's shrunk track record).

**Backtest.** Tier A, entirely on the Polymarket side first: score wallets on
months 1–6 of trade history, follow their months 7–12 entries on paper,
settle. This tests the *signal*. The Kalshi leg adds match-rate and
price-slippage haircuts, measured separately (how often does a matched Kalshi
market exist, and at what price vs the whale's entry). Keeping the two
measurements separate shows where the edge dies if it dies.

**Kill criteria.** Signal test failing (top-decile wallets' subsequent trades
don't beat their entry prices) kills it cleanly. Signal passing but match
rate < ~20% doesn't kill it — it bounds throughput; record and decide.

**Build notes.** `theories/whale_follow/{THEORY.md,wallets.py,signal.py}`.
Effort L — the largest data pipeline in this list. Build only after idea 6's
pair store exists; it shares the matching infrastructure.

---

## 10. `vol-crossing` — pricing threshold markets as barrier options

**Thesis.** "X above/below level L by date T" markets on continuously traded
underlyings (BTC, ETH, index levels) are digital barrier options. Price them
with a driftless random walk using realized volatility from the underlying's
recent history; bet when the market's price deviates from the model by more
than fees plus a model-risk buffer.

**Why the edge should exist.** Retail systematically overprices "touch"
events far from the current level (lottery preference — the same longshot
bias, in a family where the fair price is actually computable) and
under-adjusts vol regime changes. The model side is textbook (reflection
principle for barrier-hit probability); mispricing on crypto weeklies is
a known pattern among options traders who quote Kalshi crypto ladders
against Deribit vols.

**Procedure.** Fully mechanical. Underlying price history from a keyless
public endpoint (Coinbase/Binance public candles for crypto; document the
exact source in THEORY.md — it is part of the procedure). Estimate realized
vol (start: EWMA over 30 days, hourly); compute hit probability; candidate
when |model − market| > fees + buffer (start: 5 points, because vol
estimation error is real). `edge_basis="model"`. Restrict v1 to BTC/ETH
families — deepest, cleanest underlying data.

**Backtest.** Tier A over every settled crypto threshold market in history:
compute the model price at fixed decision points with only-then-available
underlying data, take the rule's trades, settle. Vol lookahead is the trap:
the EWMA window must end strictly before the decision timestamp.

**Kill criteria.** If deviations predict *the market being right* (market
beats model out-of-sample), Kalshi crypto is sharper than assumed — kill, and
record the direction; the inverse signal ("trust the deviation") would be a
different theory needing its own justification, not a sign flip.

**Kill criteria note.** Also kill any expansion beyond crypto unless the
underlying's data is as good — this family is defined by underlying quality.

**Build notes.** `theories/vol_crossing/{THEORY.md,model.py,underlying.py}`.
Effort M. Note the daily-recurring crypto range markets also feed idea 4's
miner; if the miner flags them first with a pure base-rate edge, that is the
cheaper capture and this model becomes its v2.

---

## 11. `new-market-anchor` — issuance mispricing in the first 48 hours

**Thesis.** Newly listed markets open anchored (near $0.50, or at a market-
maker's coarse prior) and take days to find fair value. If first-48h prices
are systematically biased vs resolution in a measurable direction (e.g.,
too close to $0.50 — real favorites are cheap early), buying the eventual
favorite early captures the correction.

**Why the edge should exist.** The horizon effect — Le 2026 measures the
universal compression component rising from 0.99 at 0–1h to 1.32 beyond a
month on Kalshi, and a newly listed market is by construction at its
longest-horizon, most-compressed moment — plus cold-start liquidity: nobody
has done the work yet, and the first quotes are a market-maker's guess. This
idea is deliberately staged as *measurement first*: the bias direction is an
empirical question, not an assumption (note the overlap with idea 1's 1mo+
cells; if idea 1 is built first, this study is nearly free as a byproduct —
just add a listing-age dimension to its cell matrix).

**Procedure.** Stage 0 is a study, not a theory: across all settled markets,
compare price at listing+24h/+48h to resolution, binned by price and
category. Only if a stable bias emerges does this become a theory (screen:
markets < 48h old matching the biased profile; edge from the measured bias;
`edge_basis="measured"`). If no bias, record the negative and close.

**Backtest.** The study is the tier-A backtest.

**Kill criteria.** Built in — no measured bias, no theory. Cheap either way.

**Build notes.** Start as a script in `theories/new_market_anchor/study.py`.
Effort S for the study. Highest information-per-hour in this list after
idea 1, because the repo already has all the data it needs.

---

## 12. `implication-graph` — logical constraints between non-sibling markets

**Thesis.** Beyond same-event ladders, distinct events carry logical
relations: "candidate X wins the general" implies "X wins their primary";
"party P wins the presidency" relates to state-level markets; "person Y is
confirmed by date D1" implies "confirmed by D2 > D1" across *series*. When
P(A) > P(B) at executable quotes but A ⇒ B, the pair is mispriced and B is
cheap (or A is rich).

**Why the edge should exist.** Nothing arbitrages across Kalshi events —
the flows are separate crowds. Cross-event inconsistencies documented during
the 2024 election cycle persisted for days. The constraint, once stated, is
as hard as a ladder monotonicity violation.

**Procedure.** Hybrid, with judgment quarantined at construction time:
- An LLM stage proposes implication edges over the board's event titles and
  rules (batched; strong model; prompt on disk; provenance recorded). Every
  proposed edge is then **verified by the session** reading both rule texts —
  a wrong implication is this theory's poison, and the graph is small enough
  to review by hand. Confirmed edges are stored as static facts with the
  confirming evidence, like idea 6's pair store.
- Per-trade decisions are then mechanical: scan confirmed edges for
  `ask(A_yes) + ask(B_no) < 1 − fees`-type violations. `edge_basis="model"`.

**Backtest.** The mechanical scan replayed over snapshots is tier A *given
the graph*; the graph itself is judgment, so treat overall evidence as tier B
and be explicit in THEORY.md that the tier attaches to the whole procedure.
(A subtlety worth writing down: the graph is built once and its constraints
are timeless logic, not forecasts, so contamination risk is lower than for
tier-C judgment — but the tier label should still not claim A.)

**Kill criteria.** Any settled pair where the "implication" was violated *by
the outcomes* means the edge was wrong, not mispriced — audit the graph
construction before continuing; two such events kill the graph version.

**Build notes.** `theories/implication_graph/{THEORY.md,graph.py,scan.py,prompts/}`.
Effort L, and the only idea here with an LLM anywhere near the procedure —
provenance obligations apply. Build after `structural-arb`, whose scan logic
it generalizes.

---

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
  impossible by construction. (Polymarket's transparency is why idea 9
  exists.)
- **LLM forecast-gap betting** ("research the news, disagree with the
  price") — explicitly the kind of idea CLAUDE.md warns about: it puts an
  introspected probability at the center of the procedure. Only viable if
  reframed as classification against checkable criteria with measured
  buckets, which is... `insider_bias`, which already exists. Parked as
  redundant, not wrong.

## Sources

- [Whelan — Makers and Takers: The Economics of the Kalshi Prediction Market](https://www.karlwhelan.com/Papers/Kalshi.pdf) ([CEPR summary](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market)) — 300k+ Kalshi contracts; favorite-longshot bias net of fees.
- [Market Efficiency and the Favorite-Longshot Bias in Unemployment Prediction Markets](https://www.researchgate.net/publication/409238145_Market_Efficiency_and_the_Favorite-Longshot_Bias_in_Unemployment_Prediction_Markets) and [Information Efficiency Across Macroeconomic Prediction Markets: Evidence from Kalshi](https://www.researchgate.net/publication/409472804_Information_Efficiency_Across_Macroeconomic_Prediction_Markets_Evidence_from_Kalshi) — domain-specific calibration on Kalshi macro markets.
- [Le 2026 — Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics in Prediction Markets](https://arxiv.org/pdf/2602.19520) (**read in full for this backlog**) — 353M trades / 429k contracts, Kalshi (Jul 2021–Dec 2025) + Polymarket. Table 4 slopes by domain × horizon: Politics 1.32–1.83 beyond 3h (compressed toward 50%, replicates on Polymarket); Weather 0.69–0.87 within 12h (too extreme); Sports 1.74 and Crypto 1.36 at 1mo+; universal horizon component 0.99 → 1.32. Isotonic checks: price 0.75 → 0.886 realized (Politics), 0.691 (Weather). Large political trades compress *more* (slope 1.74 vs 1.19). [Replication repo](https://github.com/namanhzz/prediction-market-calibration).
- [Angelini & De Angelis 2026 — When Do Markets Fully Process Public Information?](https://arxiv.org/pdf/2606.07811) (**read in full for this backlog**) — Kalshi NBA in-play, one-minute quotes vs public-information benchmark: 0.64-for-one adjustment on impact; the gap predicts minutes-scale drift, worse when illiquid + salient; **drift not profitable net of bid–ask at that timescale**.
- [Accuracy and Forecast Standard Error of Prediction Markets (Berg, Nelson, Rietz)](https://www.biz.uiowa.edu/faculty/trietz/papers/forecasting.pdf) — Intrade horizon-dependent miscalibration.
- [Can Interest-Bearing Positions Solve the Long-Horizon Problem in Prediction Markets?](https://arxiv.org/pdf/2602.21091) — capital-lockup mechanism distorting long-horizon prices toward 0.5.
- Cross-venue gap documentation: [trevorlasn.com on PM/Kalshi arb](https://www.trevorlasn.com/blog/how-prediction-market-polymarket-kalshi-arbitrage-works), [predictionhunt on why prices differ](https://www.predictionhunt.com/blog/why-same-market-different-prices-kalshi-polymarket), [public arb bot](https://github.com/ImMike/polymarket-arbitrage).
- Polymarket wallet-copy ecosystem: [Polycopy trader rankings](https://polycopy.app/best-polymarket-traders), [copy-score backtest write-up](https://polyloly.com/blog/polymarket-insider-tail-backtest-46-percent-roi), [finding wallets without getting rekt](https://medium.com/@0xmega/how-to-find-the-best-polymarket-wallets-to-copy-trade-without-getting-rekt-26dd65123324) — profitability base rates, scoring traps (spread-capture bots, wallet rotation).
