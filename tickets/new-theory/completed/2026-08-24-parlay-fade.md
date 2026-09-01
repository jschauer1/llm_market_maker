---
title: Cross-game parlays are overpriced against the product of their legs, and the markup grows with leg count
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: done
closed: 2026-09-01
resolution: BUILT AS A STUDY: studies/2026-08-30-parlay-markup/, pre-registration committed before any markup figure was computed. Its rule-0 probe is the important output and it came back NEGATIVE. Kalshi's 92 *COMBO markets are 2x2 partitions whose legs sit in separate events, which makes {DD, DR} an EXACT synthetic of the standalone leg market -- an identity that holds whatever the correlation between legs. Result: 34 exact riskless constructions at executable prices, 1 profitable at zero buffer (+0.05 pts), 0 at a 1c/leg buffer. Mid-price gaps up to 6.4 pts exist and sit entirely inside the spread.
---
Effort: M · LLM in decision path: no · Backtest tier: A

**This spec was acted on; the `resolution` field above says what
came of it.** Kept rather than deleted, because a completed ticket
is the record of what was asked for and why — which is what a
future session re-deriving the same idea needs.

## Assessment

**Applicability 3/5 · Implementability 3/5 · Likelihood of success 4/5 ·
Composite 10/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 3:* the edge is real but the natural expression —
  responding to RFQs in seconds — fights the manual workflow; resting
  sell-side combo orders is the realistic path and is slower and
  fill-uncertain.
- *Implementability 3:* the math is multiplication; the work is combo
  API discovery and contemporaneous leg-quote alignment.
- *Likelihood 4:* the markup is measured on 23M trades **with a
  leg-calibration control**, the mechanism (retail lottery demand) is
  the most durable in betting, and cross-game independence removes the
  correlation excuse. Docked one point only for fade-side fill
  uncertainty — the gap must be hittable, not just listed.

## 1. Hypothesis

Kalshi combo (parlay) contracts are systematically overpriced relative to
the product of their contemporaneous leg prices, and the gap grows with
leg count. Because combos trade peer-to-peer — participants can respond
to RFQs and combo positions trade on an order book — the *counterparty*
side of retail parlay demand is accessible: quote or sell cross-game
combos at product-of-legs plus a margin, and collect the measured markup.

## 2. Evidence

- arXiv 2607.14430 ("Prices, Probabilities, and Parlays: Systematic Bias
  in Sports Prediction Markets", 2026): 23 million Kalshi moneyline
  trades. Leg-level calibration is **essentially perfect in mid-life
  time-to-expiry buckets** — which is the control that makes the finding
  clean: cross-game parlays are overpriced relative to the product of leg
  prices *even when the legs themselves are priced right*, with median
  overpricing growing with leg count. The markup is a product-level
  phenomenon, not leg miscalibration.
- Mechanism is the oldest one in sports betting: parlays are lottery
  tickets, sportsbooks price large margins into them, and Kalshi's retail
  imported the demand (its "Penny Parlay" was publicly criticized as
  among the worst bets available, bought predominantly by the smallest
  accounts). Cross-game legs are near-independent, so product-of-legs
  *is* fair value — no correlation-modeling excuse protects the markup.
- Mechanics (practitioner documentation): combos are built via RFQ;
  quotes come from other participants peer-to-peer within seconds; filled
  combos trade on an order book afterward. The fade side exists.

## 3. Non-goals and exclusions

- **Cross-game combos only.** Same-game parlays have genuinely correlated
  legs; product-of-legs is not fair value there, and pricing the
  correlation is a different, harder theory. Excluded entirely in v1.
- No directional view on any leg — this theory is short the *markup*,
  not any outcome.
- The near-expiry TTE regime, where the paper finds leg calibration
  itself degrades, is excluded: fade only combos whose legs are in the
  well-calibrated mid-life regime, because the edge computation divides
  by leg prices that must be trustworthy.

## 4. Decision procedure

Fully mechanical.

- Screen: listed combo tickers (the paper worked from 5,918 listed combo
  tickers on one NBA slate, so they are API-visible — verify endpoint at
  implementation) with all legs cross-game, leg count 2–5, every leg in
  the mid-life TTE regime with a liquid quote.
- Fair value: product of contemporaneous leg mid-to-mid prices, with a
  haircut for leg-price uncertainty (spread-width-based).
- Candidate: combo bid (or an incoming RFQ level) exceeds fair value +
  fees + margin (start: 3 points) → sell/quote at that level; the
  position is exited at settlement or unwound when the gap closes.
  `edge_basis="model"` — the model is multiplication.
- Risk cap: max concurrent combos sharing any single leg (a shared-leg
  loss cascades across positions).

## 5. Data requirements

Kalshi combo-ticker quotes plus leg quotes — in-repo API tooling extended
to combo endpoints (verify exposure; the published research implies it).
No external data.

## 6. Backtest design

Tier A: for historical listed combos (or snapshots going forward if
history is thin), compute fair value from leg candlesticks at matched
timestamps, record the gap distribution by leg count, and simulate the
sell-at-gap rule settling each combo from its legs' outcomes. Lookahead
traps: leg prices must be contemporaneous with the combo quote (stale leg
marks manufacture fake gaps); the TTE-regime filter must use only
time-to-expiry, never realized outcomes.

## 7. Kill criteria

- If the observed gap is quoted-but-never-traded (markup exists in listed
  prices but no buyer lifts fadeable size), the edge is theoretical;
  measure fill-side volume before claiming anything.
- If combo history/API access proves too thin to measure, `paused` on
  that prerequisite, not dead — the paper's result stands either way.

## 8. Implementation plan

`theories/parlay_fade/{THEORY.md,combos.py,fair_value.py}` + tests.
`combos.py` (fetching combo tickers/quotes) is new API surface — build
theory-local per the promotion rule. Effort M, mostly API discovery.

## 9. Testing approach

Unit tests: product-of-legs fair value with spread haircuts, TTE-regime
filter, shared-leg exposure cap, gap computation against constructed
combo/leg fixtures with planted staleness (must be rejected).

## 10. Open risks

- **Workflow fit is the big one:** responding to RFQs within seconds is
  awkward for a manual user. The realistic expressions are resting
  sell-side combo orders on the post-RFQ order book and unwinding into
  retail demand — both slower than quoting, both untested here. The
  Assessment's applicability score prices this in.
- Sports-heavy inventory: this is deliberately a *pre-game, structural*
  sports trade (the repo's live-sports exclusions target in-play speed,
  which this avoids), but sports concentration still correlates the book
  during big slates — the shared-leg cap plus sizing must handle it.
- Kalshi could re-price or restructure combos (fee changes, house
  quoting) and the markup compresses; re-measure the gap distribution
  periodically.

## 11. Sources

- [arXiv 2607.14430 — Prices, Probabilities, and Parlays](https://arxiv.org/abs/2607.14430)
- [Sportico — Kalshi's RFQ parlays explainer](https://www.sportico.com/business/sports-betting/2025/kalshi-parlay-combo-rfq-explainer-1234877038/)
- [Gambling Insider — Penny Parlay criticism](https://www.gamblinginsider.com/news/180114/kalshi-penny-parlay-worst-bet-in-america-smallest-bettors-buying-it)
- [ParlayMarket — AMM design for joint contracts](https://arxiv.org/html/2603.22596v1) — the correlation-aware pricing frontier this spec deliberately avoids by staying cross-game.
