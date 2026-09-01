---
title: Insider accumulation leaves a signature on Polymarket's ledger: sudden size into a longshot by wallets with no history
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: open
---
Effort: L · LLM in decision path: no (screening); session judgment on alerts · Backtest tier: A for the detector; alert follow-through is judgment

**This ticket is the spec.** Before starting, run
`python -m tools.cli ideas search "insider-flow-radar"` in case the status
moved, and read [the backlog's shared contracts](../README.md)
first — rules 0 through 0e there have killed more ideas in this
repo than any single spec's own kill criteria have.

## Assessment

**Applicability 2/5 · Implementability 2/5 · Likelihood of success 2/5 ·
Composite 6/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities) — lowest-ranked spec in the backlog; kept
because its payoff profile is uncorrelated with everything else here.

- *Applicability 2:* alerts are rare, and each needs a matched liquid
  Kalshi twin — the award/appointment market inventory is thin.
- *Implementability 2:* detector, wash filter, hand-labeled evaluation
  set, and polling cadence; shares infrastructure with whale-follow but
  adds novel components.
- *Likelihood 2:* the signature's separability from wash trading and
  noise is unproven, the adversary adapts, and the asymmetric payoff
  profile resists standard calibration at low n — a variance monster even
  if real.

## 1. Hypothesis

When someone with genuine non-public knowledge trades a prediction market,
they leave a signature on Polymarket's transparent ledger: sudden,
size-aggressive accumulation of a *longshot* side by wallets with little
or no history, in a market with a discrete revelation event ahead. Detect
that signature within hours, and mirror the position on the matched Kalshi
market while the price still says "longshot." This differs from
[whale-follow](2026-08-24-whale-follow.md) in kind:
whale-follow trusts *long track records*; this flags *anomalous fresh
flow* precisely because it has no track record.

## 2. Evidence

- Documented cases of on-chain insider patterns with 12–48 hour lead
  windows before public revelation; the Nobel Peace Prize case (fresh
  wallets accumulating the eventual winner at longshot prices, ~2,700%
  return) is the canonical example.
- The structural premise is just Polymarket's design: per-trade wallet
  identity is public, and informed actors betting real size cannot avoid
  writing their conviction into the ledger. Kalshi's opacity is why the
  *detection* happens on Polymarket and the *bet* happens on Kalshi.
- Honest counter-evidence, which shapes section 3: a Columbia study
  estimates ~25% of all-time Polymarket volume is wash trading (45% in
  sports; spiking worse in high-attention periods). Naive volume-anomaly
  detection fires mostly on manufactured flow.

## 3. Non-goals and exclusions

- Not a volume-spike detector. The signature is specific: new-ish wallets
  + aggressive taker flow + longshot side + a market with a concrete
  upcoming revelation (award, appointment, verdict, announcement).
- Sports excluded entirely (wash-trading rate highest; genuine insider
  edge thinnest).
- Markets without a matched, liquid Kalshi twin are watched but produce no
  opportunity (`record_opportunity` requires the Kalshi ticker).
- No LLM in the detector. The final "act on this alert?" call is session
  judgment reading the alert's evidence — recorded as disposition
  endorsed/rejected, so the judgment's value is measured like any stage 2.

## 4. Decision procedure

- **Detector (code, continuous-ish):** over `tools/polymarket/trades.py`
  flow on non-sports markets with revelation events: score = f(taker
  aggression, buyer wallet age/history depth, size vs market's trailing
  norm, longshot price band, one-sidedness of new flow). Wash-trade
  filter first: drop self-matching patterns, circular flows, and markets
  whose volume/holder profile matches the documented wash signatures.
- **Alert:** score above threshold → alert with the full evidence bundle
  (wallets, sizes, prices, timing, the match candidate from
  `tools/match_market.py`).
- **Action:** session reviews the bundle, endorses or rejects; endorsed →
  buy the flagged side on Kalshi at ask. `edge_basis="prior"` initially —
  a declared conservative prior, because alert win rate is unmeasured
  until several revelations settle; the bucket earns `measured` the
  normal way.

## 5. Data requirements

All existing: Polymarket trades + holders (in-repo tools), match_market,
Kalshi quotes. The detector needs a polling cadence — session-based
polling is fine for a 12–48h signature; no daemon required.

## 6. Backtest design

Tier A for the detector: replay historical Polymarket trade data (public,
complete), fire the detector as-of each historical moment, and check
whether flagged accumulations preceded resolution in the flagged
direction. This measures detector precision/recall on history without any
LLM. The Kalshi leg (was a matched market available, at what price) is
measured separately, as in whale-follow. Alert-level session judgment
cannot be backtested — it accrues live, endorsed-vs-rejected.

## 7. Kill criteria

- Detector precision on history below ~30% (most alerts are noise or
  wash) after the wash filter → the signature isn't separable; kill, and
  record which component failed (the registry entry's `outcome` should
  say whether wash filtering or the signature itself was the problem).
- Detector works on Polymarket history but matched-Kalshi availability
  < ~15% of alerts → throughput-bound; park with revisit condition
  "Kalshi lists more award/appointment markets."

## 8. Implementation plan

`theories/insider_flow_radar/{THEORY.md,detector.py,wash_filter.py}` +
tests. Build after whale-follow (shares wallet-profiling machinery and
the pair store); the wash filter is a candidate for `tools/` promotion
since whale-follow needs it too. Effort L.

## 9. Testing approach

Unit tests: each detector component on constructed trade fixtures
(genuine-pattern, wash-pattern, mixed); precision/recall harness over a
labeled historical sample (label a few dozen known cases by hand — the
documented ones plus randomly sampled negatives).

## 10. Open risks

- Asymmetric-payoff theories are variance monsters: most alerts lose
  small, rare wins pay huge. Standard calibration metrics mislead at low
  n; score this theory on ROI with wide intervals, not win rate.
- Insiders adapt (splitting across wallets, pre-positioning slowly); the
  signature decays and the detector needs re-validation on rolling
  history — schedule that into THEORY.md rather than assuming stability.
- Legal/ethical position: observing public on-chain data is legitimate
  research; the theory trades on *detection of* others' likely insider
  activity, not on non-public information itself. Kalshi ToS should be
  checked for any "trading on material non-public information" clause
  interaction before this goes live — flag to the user at proposal time.

## 11. Sources

- Documented on-chain insider cases (Nobel Peace Prize 2,700% return;
  12–48h lead windows) — practitioner documentation aggregated at
  [PredictionTalk's 40-paper survey](https://predictiontalk.org/d/14-ai-parsed-40-papers-on-pm-inefficiencies-here-are-5-im-going-to-trade/).
- Columbia wash-trading study (SSRN 5714122) — the contamination this
  spec's filter exists for.
- [Reichenbach & Walther 2025](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5910522) — Polymarket trade-level transparency underpinning the detector.
