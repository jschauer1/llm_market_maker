## Learnings

Nothing measured yet. 2026-08-27: the design decision worth recording
before any data arrives is that the repo's *existing* full-coverage
settled data (`backtest-2026-08-25-*-fullcov`, 6,636 settled rows) cannot
serve this theory — that population was fetch-scoped to exclude Sports,
Crypto, Climate and Weather, Commodities, Economics, Elections and
Financials, and capped at 14 days to close, so it excludes **both**
domains whose contrast is this theory's central claim and every horizon
bin beyond two weeks. See `NOTES.md` 2026-08-27.
