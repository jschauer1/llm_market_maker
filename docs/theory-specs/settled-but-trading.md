# settled-but-trading — the answer is public, the price hasn't moved

**Priority:** 8 of 12 · **Effort:** M for the first family, S per additional
· **LLM in decision path:** no · **Backtest tier:** A

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search
> "settled-but-trading"` for status changes since this was written. Formalize
> via the `propose-theory` skill before writing procedure code.

## Thesis

Some markets resolve on machine-readable public data with a known release
moment (econ prints, official weather observations, published
rankings/charts). In the window between "the determining fact is public" and
"the market reprices to ~$0.99", buying the determined side is close to free
money at retail speed — minutes to hours, not milliseconds.

## Why the edge should exist

Kalshi settlement lags its sources, and casual markets have nobody assigned
to reprice them at release time. The edge decays with venue maturity but
re-arises with every new listed family. Unlike HFT races, the user's
manual-betting workflow can actually capture hour-scale staleness.

## Procedure

Per-family resolvers, pure code:

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

## Backtest

Tier A and unusually clean: historical release timestamps are public,
candlesticks show the price path after each release. Measure: how often was
the determined side buyable ≤ $0.97 at T+30min after release, and did it
ever *lose* (a resolver bug or a rules subtlety — e.g., Kalshi resolving on
a revised figure, or a different station than the resolver read). Any
historical loss is a resolver defect to fix before going live.

## Kill criteria

Per family: if the T+30min buyable rate is ~zero across history, that family
is efficiently repriced; move to the next family. The theory dies only when
several families in a row show no window.

## Build notes

`theories/settled_trading/{THEORY.md,resolvers/}`. Effort M for the first
family, then S per additional family. The rules-reading per family is the
risk — each resolver's first version should be validated against 20+
historical settlements before its output is ever bettable.

## Sources

Mechanism-based (settlement mechanics), no external study. Keyless source
examples: [api.weather.gov](https://api.weather.gov) (NWS observations),
BLS/BEA scheduled release calendars.
