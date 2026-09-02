# Evidence Ledger — theory backlog claims and their verification status

Date: 2026-08-24. Companion to the
[backlog index](../README.md).

Every load-bearing quantitative claim in the 22 specs, mapped to its
source and graded by **how it was verified during research** — so a
reviewing model knows which numbers to trust, which to re-check, and
which to treat as leads rather than evidence. When reviewing a spec,
look its claims up here first; a spec is only as strong as its worst
load-bearing grade.

## Grades

- **A — primary, read in full.** The paper's extracted text was read
  during research; exact numbers transcribed with locators in a notes
  file in this folder. Trust the transcription; spot-check against the
  PDF if the claim is decision-critical.
- **B — primary located, summary verified.** The primary source exists
  and was directly fetched (abstract, author's own research page), but
  the full text was not read. Numbers are as the source's own summary
  states them. Verify before treating a specific magnitude as precise.
- **C — practitioner/secondary, directly read.** Blog, tool
  documentation, or platform docs read directly. Useful for mechanics
  and rules of thumb; not academic evidence. Verify mechanics against
  the platform before implementation.
- **D — secondhand aggregation, unverified.** Numbers arrived via
  search-result summaries or a forum's synthesis of papers not
  independently opened. **Treat as leads, not evidence.** A reviewing
  model should either verify at the named source or discount the claim.

## Ledger

### Papers with full notes in this folder (grade A claims)

- **Le 2026** (arXiv:2602.19520) →
  [notes](2026-08-24-le-2026-calibration-notes.md). Grade-A claims:
  Table 4 slope matrix; isotonic 0.75→0.886 (Politics) / 0.691
  (Weather); 70¢→≈83% one week out; universal horizon component
  0.99→1.32; Table 5 trade-size compression (Politics 1.19→1.74,
  Δ+0.53); 87.3%/71.5% variance decomposition; dataset sizes. Cited by:
  calibration-harvest, deadline-drift, series-bias-mining,
  new-market-anchor, vol-crossing, econ-anchoring, weather-model-gap.
  Caveat carried in the notes: under event-clustered SEs roughly half
  of raw slope variation is estimation noise.
- **Angelini & De Angelis 2026** (arXiv:2606.07811) →
  [notes](2026-08-24-angelini-deangelis-2026-notes.md). Grade-A claims:
  0.64 impact coefficient (0.51 clutch); Table 6 drift coefficients;
  "executable-style returns … are negative" (verbatim); salience ×
  liquidity moderation. Cited by: news-drift, overreaction-fade,
  maker-mode-execution.

### Per-spec ledger (remaining claims)

**calibration-harvest**
- Whelan "Makers and Takers": 300k+ contracts; low-price contracts lose
  after fees, high-price win more and yield small positive returns —
  **B** (paper public at karlwhelan.com/Papers/Kalshi.pdf + CEPR
  column; full text not read).
- mention_family in-repo rates (0.73 / 0.87 / 1.00 by price bin,
  n=116) — **A-internal** (repo's own DB and RESEARCH_LOG, 2026-08-24).

**deadline-drift**
- Intrade horizon miscalibration, 500k+ transactions (Berg, Nelson &
  Rietz) — **B** (paper public; characterization from its literature).
- Capital-lockup mechanism (arXiv:2602.21091) — **B** (abstract-level).

**structural-arb**
- Public arb bots exist (GitHub ImMike/polymarket-arbitrage) — **C**
  (repo directly located).
- "$10.6M extracted in 12 months, 2.7s windows" (IMDEA, rebalancing
  arb) — **D** (via PredictionTalk forum synthesis; not independently
  opened). The spec uses it only as competition context.

**series-bias-mining** — rests on Le 2026 (A) + repo history
(A-internal). No external claims.

**news-drift**
- PEAD / Hong–Stein slow diffusion — **B** (canonical literature,
  standard citations).
- All Kalshi-specific numbers — **A** (Angelini notes).

**no-side-premium**
- Takers −1.12% / makers +1.12% per trade; YES underperforms NO by up
  to 64pp at equivalent prices; category gaps Finance 0.17pp →
  Entertainment 4.79–7.32pp — **B** (Becker's own research page
  jbecker.dev/research/prediction-market-microstructure fetched
  directly; dataset public on GitHub; full paper not read). These are
  this spec's core numbers — **a reviewer should verify the 64pp
  figure's exact conditioning** (price range, platform) before build.
- Polymarket YES/default overtrading; no general longshot bias once
  side accounted for (Reichenbach & Walther, SSRN 5910522, 478M
  trades) — **B** (SSRN abstract).

**overreaction-fade**
- Negative/weak daily autocorrelation, cross-exchange divergence,
  accuracy 93% PredictIt / 78% Kalshi / 67% Polymarket (Clinton &
  Huang 2025, $2.4B, 2,500+ markets) — **B** (abstract + RePEc summary
  fetched directly).
- "10pp+ moves revert 60–70%"; "negative serial correlation in 58% of
  national presidential markets"; "Sung et al. (2019)" — **D** (forum
  synthesis; **not found in the abstract read directly**). The spec
  attributes these to "practitioner summaries" deliberately. A reviewer
  should locate them in the paper's body or discount; the spec's design
  (measure signs from our own data) does not depend on the exact
  figures.
- Dalen "event vega", pre-close jitter (arXiv:2510.15205) — **B**
  (abstract-level).

**cross-venue-fair-value**
- Persistent 1–5% cross-venue gaps — **C** (multiple practitioner
  writeups, directly read).
- Venue accuracy asymmetry warning — **B** (Clinton & Huang, above).

**smile-smoothing** — mechanism-based; no external quantitative claims.

**econ-anchoring**
- Campbell & Sharpe, JFQA 2009: consensus anchoring, predictable
  forecast errors, priced into bonds — **B** (canonical paper,
  publicly listed; full text not read).
- "FEDS 2026 re-runs the anchoring regression on 2012–2026 data,
  positive significant coefficients at all horizons" — **D→C**: a FEDS
  2026 paper matching this description surfaced in search (the SEP
  anchoring study), but the specific regression claim came from a
  search summary and the paper's exact scope (SEP projections vs
  monthly data releases) **must be verified at implementation** — the
  spec's §2 wording is deliberately hedged.

**settled-but-trading**
- Per-family mechanics (NWS keyless, BLS timestamps) — **C** (platform
  docs).
- "73% of temporal-lag profits to sub-100ms bots" — **D** (forum
  synthesis of Ng/Peng SSRN 2025). Context only.

**new-market-anchor** — rests on Le 2026 (A). Cold-start spread claim
is reasoning, not measurement.

**maker-mode-execution**
- Becker ±1.12pp — **B** (as in no-side-premium).
- Palumbo: NFL passive LPs ≈$29M aggregate seasonal profit,
  directional terminal exposure, "underwriters not market makers"
  (SSRN 6325658, Mar 2026) — **B** (SSRN abstract + search summary of
  the paper's own framing).
- Whelan taker fee structure — **B**.

**attention-model**
- Wikipedia activity predicts opening box office up to a month ahead
  (Mestyán, Yasseri & Kertész, PLOS One 2013) — **B** (paper public,
  open access; abstract verified).
- Entertainment least-efficient category — **B** (Becker, above).
- "1.5% median spreads on blockbusters, $500K daily volume" — **D**
  (blog via search summary). Do not rely on it; measure from the board.

**metaculus-gap**
- Metaculus/GJO aggregates competitive with model ensembles (Codi et
  al. 2022); markets-vs-polls parity — **B** (via the Manifund
  platform-comparison project page and standard literature).
- Metaculus scoring/aggregation mechanics — **C** (Metaculus's own
  documentation).

**whale-follow**
- ~13% of Polymarket wallets profitable — **C** (wallet-tracker
  ecosystem documentation).
- "Copy Score 70+ won 67.7% over 687K resolved trades" — **C/D**
  (polyloly's own backtest write-up; methodology not auditable).
- Wash trading ~25% all-time / 45% sports (Columbia, SSRN 5714122) —
  **D** (via forum; SSRN id known but paper not opened). Load-bearing
  for the wash filter's *necessity* — verify before build.

**vol-crossing**
- Crypto horizon slopes — **A** (Le notes).
- "Options traders quote Kalshi crypto against Deribit vols" — **C**
  (practitioner characterization; treat as color).

**implication-graph**
- Cross-market inconsistency persistence through 2024 — **B** (Clinton
  & Huang).

**insider-flow-radar**
- Nobel Peace Prize wallet case (~2,700%, 12–48h lead) — **D**
  (widely reported anecdote via forum synthesis; verify the specific
  case before citing it in a THEORY.md).
- Wash-trading rates — **D** (as whale-follow).

**parlay-fade**
- Cross-game parlays systematically overpriced vs product of legs,
  growing with leg count; legs essentially perfectly calibrated in
  mid-life TTE buckets; 23M moneyline trades — **B** (arXiv:2607.14430
  abstract fetched directly; these claims are in the abstract).
- "Median overpricing grows geometrically"; "5,918 combo tickers on the
  2026-03-07 NBA slate" — **B/D** (search summary of the paper's body;
  consistent with the abstract but not read directly — verify in the
  paper before quoting magnitudes).
- RFQ mechanics, peer-to-peer quoting, post-fill order book — **C**
  (Sportico + platform guides, directly read). **Verify against the
  live platform before build** — this is the spec's workflow-fit crux.
- Penny Parlay retail criticism — **C** (Gambling Insider).

**weather-model-gap**
- Per-station settlement; ~1.75¢/contract fee; ~2°F cushion; 8pp entry
  floor; edge widest 3–5 days out; per-city NWS bias — **C**
  (multiple independent practitioner playbooks, directly read;
  consistent with each other). Rules of thumb, not measurements — the
  spec re-measures all of them.
- Short-horizon weather overconfidence — **A** (Le notes).

**calendar-arb** — pure logic; no external quantitative claims.

## Maintenance

When a backtest in this repo measures one of these quantities
first-hand, the measurement supersedes the grade here — link the run
and note it. When a D-grade claim is verified or falsified at its
source, upgrade or strike it here rather than editing history.
