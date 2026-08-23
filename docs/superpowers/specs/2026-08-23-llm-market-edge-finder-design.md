# LLM Market Edge Finder — Design Spec

Date: 2026-08-23

## 1. Mission

Build a repository that gives an LLM (Claude, operating this repo interactively
via Claude Code) the tools it needs to find Kalshi markets with the largest
edge — on its own initiative. The user opens a Claude Code session in this
repo and can ask things like "find me the markets with the largest edge right
now" or "how has theory X performed over the last quarter?" and get a real
answer, backed by real tooling, real data, and a real track record.

The system does not ship with a fixed strategy. It ships with:
- Infrastructure to observe two prediction-market platforms (Kalshi,
  Polymarket) and record what it finds.
- A lightweight, unopinionated format for capturing a trading **theory**
  (hypothesis) so ideas can be proposed, run, backtested, scored, and compared
  against each other over time.
- One theory ported from an existing project (`insider_bias`, from
  `kalshi_trader`) as a working reference example, including its real
  historical track record.

Claude is expected to **invent its own theories** going forward — the two
example ideas that motivated this project (comparing forecast-gap style
research bets, and copying Polymarket whale activity into equivalent Kalshi
markets) are illustrations of the *kind* of idea Claude should be able to
propose and test on its own, not features this build implements.

## 2. Non-goals

- **No fixed theory beyond the one ported reference implementation.** The
  system must not need the user (or this spec's author) to keep supplying new
  strategy ideas. `propose-theory` is how new ideas get formalized, by Claude,
  at any point after this build is done.
- **No automated order execution.** This system produces recommendations. The
  user places real bets on Kalshi manually. Nothing in this build submits
  orders.
- **No paid LLM API keys.** All judgment (classification, picking, matching,
  backtest replay judgment) is performed by the orchestrating Claude Code
  session itself, or by subagents it spawns via the Agent tool, running on the
  user's Claude subscription — never a separate OpenAI/Anthropic API call
  billed per token.
- **No rigid, one-size-fits-all theory pipeline.** kalshi_trader's
  screen → classify → pick shape is *one example* of how a theory can work,
  not the mandated shape for all theories.
- **No Polymarket-specific theory logic.** Polymarket access is built as
  general-purpose infrastructure (a tool), symmetric with the Kalshi tooling.
  What to *do* with it (e.g. whale-copying) is left for Claude to propose.

## 3. Architecture overview

The orchestrating Claude Code session is the judgment engine. It:

- Calls small, mechanical **tools** (Python CLI scripts) for anything that
  doesn't require reasoning: fetching market data from Kalshi/Polymarket,
  reading/writing the shared SQLite database, computing sizing math, scoring
  settled outcomes.
- Spawns its own **subagents** (via the Agent tool) for anything that
  requires judgment: classifying whether a market fits a thesis, picking the
  best candidates from a shortlist, deciding whether two markets on different
  platforms are "the same" market, judging a historical replay for a
  backtest. Judgment work that needs to scale across many candidates (a
  bulk scan, a backtest over hundreds of historical markets) should be
  **batched** into a reasonable number of subagent calls (e.g. tens of
  candidates per call) rather than one subagent per candidate, to keep
  subagent volume sane.
- Follows **Skills** (markdown procedures, `.claude/skills/`) that encode the
  standard workflows — find the current best edge, propose a new theory,
  backtest a theory, score theories against real settlements, compare
  theories — the same pattern the `superpowers` skill set itself uses.

A **theory** is free-form: its own folder, its own code, its own prompts, its
own idea of what "testing" even means for that hypothesis. The *only*
contract every theory must honor is calling one shared tool —
`record_opportunity` — when it finds something worth surfacing. That single
contract point is what makes cross-theory comparison and shared scoring
possible without constraining how any individual theory thinks or works.

Kalshi and Polymarket are both first-class **tools** available to any theory,
symmetric in how they're exposed. The one real-world asymmetry: only Kalshi
positions are ever sized/recorded as real, placeable bets, since that's the
only platform the user can actually wager on. Polymarket is a legitimate
research/signal source with equal tooling support, not a second-class data
source.

## 4. Repository structure

```
LLM_market_identifier/
  CLAUDE.md                        Rich onboarding briefing (see section 9)
  .claude/
    skills/
      find-edge/SKILL.md           Main entrypoint: scan active theories, rank opportunities
      propose-theory/SKILL.md      Scaffold + register a new theory
      backtest-theory/SKILL.md     Guidance + building blocks for retroactive testing
      score-theories/SKILL.md      Fetch settlements, compute calibration/ROI
      compare-theories/SKILL.md    Cross-theory performance report
  db/
    schema.sql                     SQLite schema (source of truth for tables)
    market_edge.db                 The database itself (gitignored — data, not code)
  tools/
    README.md                      Tool-writing conventions, for extensibility
    db.py                          Connection helper + schema migration runner
    kalshi/
      markets.py                   List open/settled markets, live quotes
      history.py                   Candlesticks, point-in-time state reconstruction
    polymarket/
      markets.py                   List open/resolved markets
      trades.py                    Trade history, large/whale-trade filtering
    match_market.py                Cross-platform candidate shortlist (mechanical
                                    retrieval only — matching judgment is Claude's)
    ledger.py                      record_opportunity, list/query opportunities
    score.py                       Settlement fetch + calibration edge / ROI
    sizing.py                      Optional Kelly/fee-model helpers
    snapshot.py                    On-demand market snapshot capture (build our
                                    own history over time)
  theories/
    _TEMPLATE/
      THEORY.md
    insider_bias/
      THEORY.md                    Ported from kalshi_trader's insider_bias
      ...                          Whatever code/prompts it needs
  migrate_kalshi_trader.py         One-time import of kalshi_trader's ledger history
  docs/
    superpowers/specs/             Design specs (this file)
```

## 5. Data layer

SQLite (`db/market_edge.db`), schema defined in `db/schema.sql`. Chosen over
flat CSVs (kalshi_trader's approach) because: the raw market dump in
kalshi_trader is overwritten on every fetch with no history retained, and a
system meant to run for a year, compare many theories, and query calibration
over time needs proper history retention and joins — not something CSVs do
well.

### `theories`
Lightweight registry index — the source of truth for a theory's hypothesis
and procedure is its `THEORY.md`, not the database. This table just makes
theories programmatically discoverable.

| column | type | notes |
|---|---|---|
| id | text PK | slug, e.g. `insider_bias` |
| name | text | |
| status | text | `proposed` \| `active` \| `paused` \| `retired` |
| path | text | folder path under `theories/` |
| created_at | timestamp | |
| updated_at | timestamp | |

### `market_snapshots`
Time-series raw observations, platform-agnostic. Stores a flexible
`raw_json` payload alongside a few normalized columns, since Kalshi
(binary yes/no, prices in cents) and Polymarket (potentially multi-outcome,
prices as 0–1 probabilities) don't share one native shape.

| column | type | notes |
|---|---|---|
| id | integer PK | |
| platform | text | `kalshi` \| `polymarket` |
| market_id | text | ticker (Kalshi) or market/condition id (Polymarket) |
| captured_at | timestamp | |
| title | text | |
| implied_prob_yes | real, nullable | normalized convenience field for binary markets |
| volume | real, nullable | |
| close_time | timestamp, nullable | |
| status | text | `open` \| `closed` \| `settled` |
| raw_json | text | full original payload |

### `opportunities`
The shared spine — the `record_opportunity` contract. Every theory writes
here, in whatever mix of these fields makes sense for it; nothing is
mandatory beyond identifying the theory, market, and rationale.

| column | type | notes |
|---|---|---|
| id | integer PK | |
| theory_id | text FK → theories.id | |
| run_mode | text | `live` \| `backtest` |
| run_id | text | groups opportunities from one scan/backtest execution |
| platform | text | `kalshi` \| `polymarket` \| `cross_platform` |
| market_id | text | |
| outcome | text | free text: `yes`/`no`, or an outcome label for multi-outcome markets |
| model_prob | real, nullable | theory's estimated probability, if it produces one |
| edge_pts | real, nullable | theory's estimated edge in percentage points, if it produces one |
| confidence | text, nullable | theory's own scale — free text, not fixed to one enum |
| rationale | text | |
| suggested_size | real, nullable | |
| market_price_at_call | real, nullable | price observed when recorded — needed later for scoring |
| extra_json | text, nullable | anything theory-specific that doesn't fit the columns above |
| created_at | timestamp | |

### `settlements`
| column | type | notes |
|---|---|---|
| platform | text | |
| market_id | text | |
| resolved_at | timestamp | |
| result | text | winning outcome label |
| settle_price | real, nullable | |

### `scores`
Recomputable performance summaries per theory, over a window.

| column | type | notes |
|---|---|---|
| id | integer PK | |
| theory_id | text FK | |
| run_mode | text | `live` \| `backtest` |
| window_start / window_end | timestamp | |
| n | integer | sample size |
| win_rate | real | |
| price_implied_rate | real | |
| calibration_edge | real | win_rate − price_implied_rate |
| roi | real | net of fees |
| computed_at | timestamp | |

### `backtest_runs`
Metadata for a backtest execution, linked via `opportunities.run_id`.

| column | type | notes |
|---|---|---|
| run_id | text PK | |
| theory_id | text FK | |
| as_of_start / as_of_end | timestamp | historical window being replayed |
| hindsight_risk | text | `low` \| `medium` \| `high` — see section 7 |
| notes | text | |
| created_at | timestamp | |

## 6. Tools

Flat, small, single-purpose scripts — not a framework. `tools/README.md`
documents the convention (JSON/SQLite in and out, a docstring/`--help`
describing what the tool does, no shared base classes) precisely so that
Claude can read one existing tool end-to-end and write a new one in the same
shape (e.g. "fetch weather data," "fetch congressional trading disclosures")
without first learning an abstraction layer.

- **`tools/kalshi/markets.py`** — list open markets, list settled markets
  (with resolution), live re-quote by ticker. Ported from kalshi_trader's
  `fetch_kalshi_markets.py`; Kalshi's market data endpoints require no
  authentication.
- **`tools/kalshi/history.py`** — historical candlesticks (1min/1hr/1day
  resolution, confirmed available via Kalshi's public API) and a
  point-in-time market-state reconstruction helper built on top of them.
- **`tools/polymarket/markets.py`** — list open/resolved markets. Uses
  Polymarket's public Gamma API. *Exact endpoint shapes were not verified
  live during design and need confirming during implementation* — flagged as
  a risk in section 11.
- **`tools/polymarket/trades.py`** — trade history and large/whale-trade
  filtering, via Polymarket's public CLOB/data API (also to be confirmed
  during implementation).
- **`tools/match_market.py`** — given a market on one platform, returns a
  mechanically-generated shortlist of plausible equivalents on the other
  platform (keyword/category/date overlap). Deliberately does *not* make the
  final "is this really the same market" call — that judgment belongs to the
  orchestrating Claude or a subagent it spawns, reading the shortlist.
- **`tools/ledger.py`** — `record-opportunity` (the shared contract) and
  `list-opportunities`.
- **`tools/score.py`** — `settle` (fetch settlement outcomes for open
  opportunities that have since resolved) and `report` (compute win rate,
  price-implied rate, calibration edge, ROI for a theory/window).
- **`tools/sizing.py`** — optional Kelly/fee-model helpers, ported from
  kalshi_trader's `sizing.py`. A theory may use these or size its own way.
- **`tools/snapshot.py`** — on-demand capture of current market state into
  `market_snapshots`, for building first-party history over time (useful
  beyond what either platform's own historical API retains). No scheduler is
  wired up in this build (see section 10) — it's a tool the user or Claude
  can invoke any time.

## 7. Theory format

A theory is a folder under `theories/<slug>/`. The only required file is
`THEORY.md`:

```markdown
# <Theory name>

## Hypothesis
What's the thesis? Why would this produce edge?

## Data sources
Which platforms/tools does this theory use?

## Status
proposed | active | paused | retired — journal of status changes and why.

## How to scan for live candidates
A written procedure for Claude to follow: which tools to call, what to
filter for, when/how to spawn a subagent for judgment, and how the result
gets written via `record_opportunity`.

## How to backtest
A written procedure for Claude to follow, using the point-in-time helper
tools (section 8). Note the theory's `hindsight_risk` honestly (see below).

## Learnings
Running journal — what's worked, what hasn't, surprises.
```

Everything else in the folder is theory-owned: Python scripts, prompt
templates, notebooks, fixture data — whatever the hypothesis needs. There is
no mandated internal pipeline shape (no required `screen()`/`classify()`
functions). A purely structural/arbitrage theory might be pure deterministic
math with no LLM involved at all; a whale-copy theory might be almost
entirely subagent judgment calling both platform tools; a research theory
might lean on web search. `_TEMPLATE/` provides the empty `THEORY.md` shape
plus a short comment describing this freedom, so Claude scaffolding a new
theory via `propose-theory` isn't tempted to copy `insider_bias`'s specific
shape as if it were mandatory.

## 8. Backtesting

Not one rigid replay engine — a **toolkit** a theory's own backtest procedure
draws on, because "testing" means different things for different theories:

- Point-in-time market state reconstruction (`tools/kalshi/history.py`,
  extendable to Polymarket) — what did this market look like as of a past
  date, using each platform's own historical price data.
- Settlement lookup (`tools/score.py`) — what actually happened.
- The same `record_opportunity` contract, tagged `run_mode=backtest` and a
  `run_id` linked to a `backtest_runs` row, so backtest results land in the
  same shared scorer as live results but stay clearly separated from them.

**Hindsight-bias risk is real and must be surfaced, not hidden.** A
subagent judging a historical, already-settled market may already "know" (from
training data or live search) how it actually turned out — contaminating any
backtest that depends on the subagent guessing an outcome-correlated
probability. Purely deterministic/structural theories (price/volume rules,
arbitrage checks) don't have this problem and backtest cleanly. Theories that
lean on LLM judgment to estimate a probability should record their
`backtest_runs.hindsight_risk` honestly (`medium`/`high`) and their results
should be read as directional signal on the *screening* logic, not proof the
judgment step itself would perform the same live. `compare-theories` surfaces
this caveat wherever it's relevant rather than presenting backtest ROI at
face value across the board.

## 9. Skills

- **`find-edge`** — the headline entrypoint. Lists active theories from the
  registry; for each, opens its `THEORY.md` and follows its "how to scan for
  live candidates" procedure; collects the resulting `opportunities`; pulls
  each theory's latest `calibration_edge` from `scores` to weight confidence
  in the presentation; reports a ranked list of opportunities across *all*
  theories with rationale, price, suggested size, and track-record context
  (including an explicit caveat when a theory has little or no live history
  yet).
- **`propose-theory`** — scaffolds `theories/<slug>/` from `_TEMPLATE`,
  registers it in the `theories` table with `status=proposed`, and walks
  through filling in the hypothesis/data sources/procedures.
- **`backtest-theory`** — guidance on using the point-in-time toolkit,
  assessing and recording hindsight risk, tagging results correctly, and
  scoring them.
- **`score-theories`** — runs `tools/score.py settle` across all theories
  with open positions, refreshing the `scores` table.
- **`compare-theories`** — pulls `scores` across theories and presents a
  comparison (calibration edge, ROI, sample size, live vs. backtest,
  small-sample-size caveats).

## 10. CLAUDE.md

A substantial onboarding briefing for whichever Claude session opens this
repo, since "what can I actually do here" needs to be explicit and
discoverable rather than inferred. Sections:

1. **Mission** — find the markets with the largest edge; propose your own
   theories; don't wait to be told what to test.
2. **Non-goals** — no fixed strategy is provided beyond the one reference
   theory; you are expected to invent new ones.
3. **Platform roles** — Kalshi is where real bets get placed; Polymarket is
   an equally first-class data/research tool, not tradeable directly.
4. **Toolkit map** — one paragraph per tool: what it does, when to reach
   for it.
5. **Theory lifecycle** — propose → run live → backtest → score → compare →
   promote or retire, and where each step is encoded as a skill.
6. **Subagent usage** — when and how to spawn subagents for judgment,
   batching guidance for scale, and why (no API keys — this runs on the
   user's subscription).
7. **Data conventions** — SQLite is the source of truth for structured
   facts (opportunities, settlements, scores); a theory's own `THEORY.md` is
   the source of truth for its hypothesis and procedure.
8. **Getting started** — pointer to `find-edge` as the default entrypoint
   for "what's the best edge right now."

## 11. Migration from kalshi_trader

- **Reusable code ported into `tools/`**: Kalshi market-fetch logic
  (`fetch_kalshi_markets.py`), deterministic filtering patterns
  (`filter_kalshi_markets.py`), sizing math (`sizing.py`), and the
  settlement/calibration scoring approach (`score_results.py`) — generalized
  to be theory-agnostic and to write into the new SQLite schema instead of
  CSVs.
- **`insider_bias` ported as the one reference theory**: its prompts/config
  (`configs/insider_bias/*`) become the basis for its `THEORY.md` scan
  procedure; its actual classify/pick judgment moves from OpenAI API calls to
  orchestrating-Claude/subagent judgment.
- **`migrate_kalshi_trader.py`** — one-time script, run once during
  implementation, importing `kalshi_trader/ledger/bets_ledger.csv` and
  `kalshi_trader/kalshi_data_backtest/scored_*.csv` into the new
  `opportunities`/`settlements` tables, tagged `theory_id=insider_bias`,
  `run_mode=live`, preserving original timestamps — so `insider_bias`'s real
  track record carries forward instead of starting from zero.
- The original `kalshi_trader` repository is left untouched; nothing is
  deleted or modified there.
- `obvious_mispricing` (also present in kalshi_trader) and the theories
  cataloged in `LLM_EDGE_STRATEGIES.md`/`FORECAST_GAP_IMPLEMENTATION_PLAN.md`
  are **not** ported in this build — `insider_bias` alone is enough to prove
  the harness works end to end. Anything further is `propose-theory` work
  for later.

## 12. Testing approach

- Unit tests (pytest) for pure/deterministic pieces: `tools/sizing.py`
  (fee/Kelly math), `tools/db.py` (schema migrations), `tools/ledger.py`
  (record/query round-trip), `tools/score.py` (calibration/ROI computation
  against fixture data).
- Lighter integration-style smoke tests for `tools/kalshi/*` and
  `tools/polymarket/*` against the real public endpoints (no auth needed),
  kept rate-limit-conscious.
- Skills are LLM-followed procedures, not code — verified via an end-to-end
  manual dry run (running `find-edge` against the ported `insider_bias`
  theory) rather than automated tests.

## 13. Explicitly out of scope for this build

- Any theory beyond `insider_bias` (`obvious_mispricing`, `forecast_gap`,
  any Polymarket-based theory, or any other idea) — these are `propose-theory`
  work, deliberately left for Claude/the user to do later, not pre-built here.
- Scheduled/automated data collection — `tools/snapshot.py` is on-demand only;
  wiring up a recurring job (Task Scheduler, a scheduled cloud agent, etc.)
  is a future step once there's a concrete need for it.
- A rendered dashboard (kalshi_trader's `view_picks.py` HTML view) — chat-based
  reporting via `find-edge`/`compare-theories` is the primary interface for now.
- Real-money order execution automation.

## 14. Open risks / items to confirm during implementation

- **Polymarket API specifics** (exact Gamma/CLOB endpoint shapes, any rate
  limits) were not verified live during this design pass and need confirming
  when `tools/polymarket/*` is actually built.
- **Subagent batching size** for large-scale scans/backtests isn't fixed by
  this spec — needs tuning once real candidate volumes are seen.
- **Hindsight-bias mitigation** (section 8) is procedural, not a technical
  guarantee — it depends on `backtest-theory` and theory authors honestly
  assessing and recording risk.
