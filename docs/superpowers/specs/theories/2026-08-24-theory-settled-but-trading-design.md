# Settled But Trading — Theory Design Spec

Date: 2026-08-24
Status: backlog — not yet proposed as a theory
Registry slug: `settled-but-trading` · Priority: 14 of 22 · Effort: M
first family, S per additional · LLM in decision path: no ·
Backtest tier: A

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "settled-but-trading"` for status
changes, then formalize via the `propose-theory` skill.

## Assessment

**Applicability 4/5 · Implementability 3/5 · Likelihood of success 3/5 ·
Composite 10/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
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
