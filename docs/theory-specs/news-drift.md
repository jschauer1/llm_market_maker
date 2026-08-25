# news-drift — underreaction momentum from candlesticks

**Priority:** 5 of 12 · **Effort:** M · **LLM in decision path:** no ·
**Backtest tier:** A

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search "news-drift"`
> for status changes since this was written. Formalize via the
> `propose-theory` skill before writing procedure code.

## Thesis

When a Kalshi price moves sharply (new information arriving), it
underreacts: the move continues in the same direction over the following
hours-to-days. Enter in the direction of a large recent move, hold to
resolution (v1) or for a fixed horizon (v2).

## Why the edge should exist — and the honest caution

Underreaction and post-news drift are among the most robust findings in
behavioral finance (post-earnings-announcement drift; Hong–Stein slow
information diffusion). Angelini & De Angelis 2026 measured it *on Kalshi
directly* (NBA in-play markets, one-minute quotes vs a public-information
benchmark): prices adjust only **0.64-for-one on impact**, the missing
adjustment predicts drift over the following minutes, and underreaction is
worse when liquidity is thin and signals are salient. The caution is in the
same paper: **the minute-scale drift was not profitable net of bid–ask
costs.** So the only direct Kalshi test of this phenomenon found it real but
untradeable at that timescale. This idea's bet is therefore specifically
that *slower* drift — daily-scale moves on politics/econ/entertainment
markets, where information diffuses over days rather than seconds — is large
enough to clear the spread. That is plausible (the drift horizon in equities
is weeks, not minutes) but it is an extrapolation beyond the measured
setting, and the backtest exists to check exactly this.

## Procedure

Fully mechanical.

- Scope: **exclude live sports entirely** — that family is where the net
  drift is already measured dead, and it resolves too fast for manual bets
  anyway. Target domains where information arrives in stories, not
  scoreboard ticks: politics, econ, entertainment, world events.
- Signal: from candlesticks, a move of ≥ X points (start: 15) within ≤ 24h,
  with volume above the market's own trailing median (a price jump on no
  volume is a stale-quote artifact, not news). Price after the move within
  $0.15–$0.85 (room to drift; avoids resolved-in-fact markets).
- Entry: the **ask on the move side** as of the first candle after the
  signal completes — never the mid, and never a price inside the signal
  window.
- Edge: measured, not assumed — the backtest produces
  `P(resolves in move direction | signal)` vs the post-signal ask, binned by
  move size and post-move price. `edge_basis="measured"` once bins have n.

## Backtest

Tier A, candlesticks only. Lookahead traps: (a) the signal must be computed
from completed candles only; (b) entry at the *next* candle's ask, not the
signal candle's close; (c) exclude moves driven by the resolution event
itself (a move to $0.98 an hour before settlement is the outcome arriving,
not news to trade on — the price-band filter handles most of this, but check
close-time proximity too).

## Kill criteria

If drift exists gross but dies net of the spread + fees (the pattern the
in-play paper found at minute scale, and likely here too in thin markets),
record the gross/net split explicitly; that distinguishes "no phenomenon"
from "real phenomenon, untradeable here", which have different revisit
angles (the latter revives if Kalshi liquidity deepens).

## Build notes

`theories/news_drift/{THEORY.md,signal.py}` plus tests. Effort M.
Candlestick granularity (`tools/kalshi/history.py`) bounds how precise entry
timing can be — check the finest interval the API provides and state it in
THEORY.md before trusting the backtest.

## Sources

- [Angelini & De Angelis 2026 — When Do Markets Fully Process Public Information?](https://arxiv.org/pdf/2606.07811) (read in full) — the 0.64 impact coefficient, drift prediction, and the net-of-spread negative at minute scale.
- Post-earnings-announcement drift and slow-diffusion literature ([Hong & Stein 1999](http://www.columbia.edu/~hh2679/jf-mom.pdf), [PEAD overview](https://jkatz.caltech.edu/documents/28622/peads.pdf)) — the timescale extrapolation this thesis rests on.
