---
title: Between the determining fact becoming public and the market repricing to $0.99, the determined side is cheap
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: done
closed: 2026-09-02
resolution: KILLED AS SPECIFIED, 2026-09-02, on two independent negatives -- with a narrower successor named rather than left implied. BOTH HALVES OF SECTION 4's DECISION PROCEDURE FAILED WHERE THEY WERE MEASURED. (1) THE MOST FAVOURABLE INSTANCE PRICES AT 1.000. accumulation-decay (idea 31, closed dead 2026-09-01) tested the KXALBUMEQUIV weekly family, which is this spec's category (a) at its purest: window closed, count fixed in Luminate's data, not yet published, market still trading -- a determined outcome, a KNOWN publication lag, and zero wording latitude. Median cost to buy the favorite in that POST-window bucket is 1.000; it is quoted >=0.97 on 94.7% of observations and the favorite wins 99.5% of the time. THE KILLER NUMBER: a PERFECT forecaster buying at the executable ask in that bucket nets mean +0.45 pts, MEDIAN +0.00. That is the ceiling with zero forecasting cost, so no resolver, data source, or speed advantage can beat it. Not a one-sided-book artifact: 107 YES-favorites and 102 NO-favorites, both median exactly 1.000. Evidence: tickets/new-theory/evidence/2026-09-01-accumulation-decay-probe/. (2) THE RESIDUAL PRICE IS RULES AMBIGUITY, NOT STALENESS. A live check during insider_judgment's v4 run found five markets trading at 0.77-0.96 AFTER their determining fact was public -- exactly the window this spec targets -- and in EVERY case the residual was the market pricing RULES AMBIGUITY rather than a repricing lag. A resolver firing on 'the determining fact is public' takes the WRONG SIDE of all five. See theories/insider_bias/insider_judgment/NOTES.md, 2026-08-31 entry, item 3. That is a direct falsification measured on live rows, not an inference from a class. TAKEN TOGETHER the spec has no case left in the middle: where the fact is unambiguous the market already quotes 1.000 and there is nothing to buy, and where a gap exists the gap IS the ambiguity and buying it loses. Section 3's own exclusion of racing ('families whose staleness window is measured in seconds are out of scope by design') removes the sub-second end where the cited literature says the money actually is -- 73% of profits to sub-100ms bots on crypto-linked markets -- so the spec had deliberately scoped itself to the half that has now measured flat. WHAT SURVIVES, and it was never in this spec: THRESHOLD families -- a published number against a stated bar, where 'determined' is arithmetic rather than interpretation, so the rules-ambiguity residual that took the wrong side of all five cannot arise. The insider_judgment note names that split explicitly and calls it out as absent from the spec. Anyone picking it up files it as its OWN spec with its own pre-registration and its own population; it does not inherit this ticket's, and it must clear rule 0f (executable prices) before any build, because that is what both negatives above turned on. FREE AND KEPT for whoever does: the accumulation probe established that KXALBUMEQUIV's tracking window is derivable from the TICKER alone (suffix date = window END, window = END-6d..END, market closes END+3d), verified 33/33 against title text on board events and parsing 238/238 settled tickers, so that family's event clock costs nothing; and its candles.jsonl holds full daily executable candle series that are now PAST Kalshi's ~60-day archive and no longer re-fetchable upstream.
---
Effort: M first family, S per additional · LLM in decision path: no · Backtest tier: A

**This ticket is the spec.** Before starting, run
`python -m tools.cli ideas search "settled-but-trading"` in case the status
moved, and read [the backlog's shared contracts](../README.md)
first — rules 0 through 0e there have killed more ideas in this
repo than any single spec's own kill criteria have.

## Assessment

**Applicability 4/5 · Implementability 3/5 · Likelihood of success 3/5 ·
Composite 10/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 4:* when the window exists, the flagged bet is
  near-certain and immediately actionable at retail speed — exactly the
  user's workflow; coverage grows with each resolver family.
- *Implementability 3:* each resolver is bespoke with a 20+-settlement
  validation burden; first family M, each additional S.
- *Likelihood 3:* the open question is whether hour-scale windows still
  exist per family — sub-second versions are measured fully competed, and
  the slow families may be quietly efficient too. The per-family backtest
  answers this directly and cheaply before anything goes live, and a
  measured window converts almost surely into realized profit.

## 1. Hypothesis

Some markets resolve on machine-readable public data with a known release
moment (econ prints, official weather observations, published
rankings/charts). In the window between "the determining fact is public"
and "the market reprices to ~$0.99", buying the determined side is close
to free money at retail speed — minutes to hours, not milliseconds.

## 2. Evidence

Kalshi settlement lags its sources, and casual markets have nobody
assigned to reprice them at release time. The edge decays with venue
maturity but re-arises with every newly listed family. Unlike HFT races,
the user's manual-betting workflow can actually capture hour-scale
staleness. (The temporal-lag arbitrage literature documents the
sub-second end of this spectrum being fully competed — 73% of profits to
sub-100ms bots on crypto-linked markets — which is exactly why this spec
targets the slow families those bots don't watch.)

## 3. Non-goals and exclusions

- No family goes live before its resolver is validated against 20+
  historical settlements — resolver false positives are instant losses.
- No racing: families whose staleness window is measured in seconds
  (crypto prints) are out of scope by design.
- Sources must be keyless and structured; the repo's no-API-keys rule
  permits keyless public endpoints only.

## 4. Decision procedure

Per-family resolvers, pure code:

- Start with one family where the source is keyless and structured —
  NWS/NOAA observations for settled-weather markets (api.weather.gov,
  keyless) or scheduled federal releases (BLS/BEA fixed timestamps).
- Resolver contract: given a market's rules, compute the resolved side
  from the source, or return "not determinable" — conservative by
  construction. Candidate = resolver says determined AND ask of the
  determined side ≤ $0.97. `edge_basis="model"`.
- Report per-family coverage (how many board markets the resolver can
  read) every run, gate-report style.

## 5. Data requirements

Per family: the resolution source endpoint and its historical archive
(NWS observation history; BLS release archives with timestamps). In-repo:
board, candlesticks, rules text.

## 6. Backtest design

Tier A and unusually clean: historical release timestamps are public;
candlesticks show the price path after each release. Measure: how often
was the determined side buyable ≤ $0.97 at T+30min after release, and did
it ever *lose* (a resolver bug or rules subtlety — Kalshi resolving on a
revised figure, or a different station than the resolver read). Any
historical loss is a resolver defect to fix before going live.

## 7. Kill criteria

Per family: T+30min buyable rate ~zero across history → that family is
efficiently repriced; move to the next. The theory dies only when several
families in a row show no window.

## 8. Implementation plan

`theories/settled_trading/{THEORY.md,resolvers/}` + tests. Effort M for
the first family, S per additional.

## 9. Testing approach

Per resolver: the 20+-settlement historical validation is a test suite,
not a one-off — pinned fixtures of source payloads and the expected
resolution, so a source-format change breaks tests instead of betting
wrong. Unit tests for the "not determinable" conservatism paths.

## 10. Open risks

- Rules subtleties are the whole risk surface: revised figures, station
  mismatches, timezone boundaries in "on date X" phrasing. The resolver
  validation set must include known-tricky settlements, not a random 20.
- The staleness window shrinks as Kalshi matures; per-family windows
  should be re-measured quarterly and the theory expects its own decay.

## 11. Sources

Mechanism-based (settlement mechanics). Keyless sources:
[api.weather.gov](https://api.weather.gov), BLS/BEA release calendars.
Temporal-lag competition context:
[PredictionTalk 40-paper survey](https://predictiontalk.org/d/14-ai-parsed-40-papers-on-pm-inefficiencies-here-are-5-im-going-to-trade/).
