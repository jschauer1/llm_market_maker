# Tools

Small, single-purpose scripts. Not a framework — there is no base class to
learn and no plugin registry. Read one tool end to end and you know how to
write the next one.

## Conventions

- **One responsibility per file.** If you cannot describe a tool in one
  sentence, it is two tools.
- **JSON or SQLite in, JSON or SQLite out.** Nothing prints prose for a human
  to parse; `tools/cli.py` emits JSON, nothing more. Human-facing narration
  happens in the skills under `.claude/skills/`, which call the CLI and turn
  its output into prose. Do not build a pretty-printer into a tool — emit
  structured data and let the skill narrate it.
- **A module docstring that says what it does and why.** The "why" matters
  more than the "what" — the next reader needs to know what problem this
  existed to solve.
- **Injectable `now`.** Any function that needs a timestamp takes
  `now: str | None = None` defaulting to real UTC, so tests never assert
  against a wall clock.
- **Fail loudly.** A required field that is missing or unparseable raises.
  Never let a schema change turn silently into `0.0` — a wrong number is far
  worse than an exception, because it looks like an answer.
- **Prices are decimal dollars in [0, 1]. Edge is in percentage points.**
  Conversion happens at the API boundary; no provider's wire format escapes
  its client module.
- **A position may have legs.** `record_opportunity` writes a single
  position; `record_basket` writes a multi-leg one whose payoff is joint.
  A basket's `entry_price` is its total cost and is bounded by `max_payout`,
  not by 1.0. Scoring counts a basket once, and excludes it until every leg
  has settled — recording an arbitrage as N independent bets makes a certain
  payout read as a coin flip.
- **No credentials.** Every endpoint this project uses is public. Never add
  an API key, and never send any user identifier in a header, URL, or body.
- **Edge numbers carry a provenance tier.** Every edge is stamped with an
  `edge_basis`: `measured` (a confidence bucket's own realized win rate —
  see `buckets.py`), `model` (a mechanical calculation with no judgment
  step), or `prior` (a declared placeholder standing in until there is
  enough settled history to measure). There is deliberately no basis meaning
  "an LLM felt it was about right." Any new tool that produces an edge
  number must say which of the three it is.

## Writing a new tool

Copy the shape of an existing one. `tools/ideas.py` is a good model for a
database tool; `tools/polymarket/markets.py` is a good model for an API
client. Add tests in `tests/` mirroring the path.

## Where new code lives — and how it gets promoted

**New code starts in the theory that needs it.** A theory folder can hold any
Python it wants. Most theory code is specific to one hypothesis and belongs
nowhere else; generalizing early produces a shared layer full of
single-caller abstractions, which is worse than a little duplication.

**Promotion to `tools/` is earned.** A theory-local script becomes a
candidate when it actually has more than one real caller, or when a new
theory would obviously reach for it. This is a judgment call, not a rule that
fires on the second use — sometimes two theories want subtly different things
and should keep their own versions.

When you do promote:

1. Move it to `tools/`, generalizing only as far as the real callers require.
2. Give it the treatment above: docstring, tests, JSON/SQLite boundaries.
3. Update every theory that used a local copy to call the shared one, and
   delete the local copies. One implementation, not two.
4. Note it in each affected theory's `THEORY.md` changelog. If behavior
   changed at all in the move, that is a decision-procedure change — bump the
   theory version.

This mirrors how a heuristic graduates from stage 2 to stage 1: prove it in a
narrow context, then promote it once there is evidence it belongs.

## Tool map

| Tool | What it does |
|---|---|
| `cli.py` | Unified command line over everything below |
| `db.py` | Connection, schema, UTC timestamps |
| `theories.py` | Theory registry, evidence-level status, versioning, retirement proposals |
| `ideas.py` | Research memory — every hypothesis considered, and why it died |
| `ledger.py` | `record_opportunity`, `record_basket`, interpretation, user actions |
| `score.py` | Settlements, calibration edge, ROI, interpretation value |
| `rank.py` | Credibility-weighted ranking |
| `buckets.py` | Confidence-bucket win rates → measured edge, not guessed |
| `sizing.py` | Kalshi fee model, Kelly sizing |
| `board.py` | The session's shared Kalshi board — one pull per session, reused by every theory |
| `snapshot.py` | First-party market history capture |
| `provenance.py` | Which model judged and with which prompt — required for any theory with an LLM in its decision path |
| `match_market.py` | Non-Kalshi finding → Kalshi ticker shortlist |
| `http.py` | Retrying HTTP for the public APIs |
| `kalshi/markets.py` | Open/settled markets, live quotes, resolution rules |
| `kalshi/history.py` | Candlesticks, point-in-time reconstruction |
| `polymarket/markets.py` | Open/resolved markets |
| `polymarket/trades.py` | Trades, whale detection, holders |
