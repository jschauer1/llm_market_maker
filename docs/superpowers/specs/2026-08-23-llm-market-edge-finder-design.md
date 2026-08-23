# LLM Market Edge Finder — Design Spec

Date: 2026-08-23

## 1. Mission

Build a repository that gives an LLM (Claude, operating this repo interactively
via Claude Code) the tools it needs to find Kalshi markets with the largest
edge — on its own initiative. The user opens a Claude Code session in this
repo and can ask "find me the markets with the largest edge right now" or "how
has theory X held up over the last quarter?" and get a real answer, backed by
real tooling, real data, and a real track record.

The system does not ship with a fixed strategy. It ships with:

- Infrastructure to observe two prediction-market platforms (Kalshi,
  Polymarket) and record what it finds.
- A lightweight, unopinionated format for capturing a trading **theory**
  (hypothesis) so ideas can be proposed, run, backtested, scored, and compared
  against each other over time.
- A **ranking discipline** that converts a theory's *claimed* edge into a
  *credibility-weighted* one, so "largest edge" is an evidence-backed claim
  rather than whichever theory happens to sound most confident.
- One theory ported from an existing project (`insider_bias`, from
  `kalshi_trader`) as a working reference example, including its real
  historical track record.

Claude is expected to **invent its own theories** going forward. The two ideas
that motivated this project (research-driven forecast-gap bets, and copying
Polymarket whale activity into equivalent Kalshi markets) are illustrations of
the *kind* of idea Claude should propose and test unprompted — not features
this build implements.

The core inversion versus `kalshi_trader`: that repo is *one hypothesis*,
hardcoded into a pipeline, with a paid model doing bounded judgment inside
pre-defined slots. This repo is a *research environment* where the LLM is the
researcher — hypotheses are cheap to create, cheap to test, and cheap to kill,
and the accumulated track record is what makes any edge claim meaningful.

## 2. Non-goals

- **No fixed strategy beyond the one ported reference theory.** The system
  must not depend on the user supplying new strategy ideas. `propose-theory`
  is how new ideas get formalized, by Claude, at any point after this build.
- **No automated order execution.** This system produces recommendations. The
  user places bets on Kalshi manually. Nothing here submits orders.
- **No paid LLM API keys.** All judgment (classification, picking, market
  matching, backtest replay) is performed by the orchestrating Claude Code
  session or by subagents it spawns via the Agent tool, on the user's Claude
  subscription — never a metered OpenAI/Anthropic API call.
- **No rigid, one-size-fits-all theory pipeline.** `kalshi_trader`'s
  screen → classify → pick shape is *one* way a theory can work, not the
  mandated shape for all theories.
- **No pre-built Polymarket theory.** Polymarket-driven theories are welcome
  and expected — proposing them is Claude's job, not this build's. What ships
  here is the *tooling* (market data, trade/whale data, cross-platform
  matching), symmetric with the Kalshi tooling.

## 3. Architecture overview

The orchestrating Claude Code session is the judgment engine. It:

- Calls small, mechanical **tools** (Python CLI scripts) for anything not
  requiring reasoning: fetching market data, reading/writing SQLite, computing
  sizing and fee math, scoring settled outcomes.
- Spawns its own **subagents** (via the Agent tool) for anything requiring
  judgment: does this market fit the thesis, which candidates are best, are
  these two markets on different platforms really the same market, how would
  this theory have judged a historical market. Judgment that must scale across
  many candidates should be **batched** — tens of candidates per subagent call,
  not one subagent per candidate.
- Follows **Skills** (markdown procedures in `.claude/skills/`) encoding the
  standard workflows: find the current best edge, propose a theory, backtest a
  theory, score against settlements, compare theories.

A **theory** is free-form: its own folder, its own code, its own prompts, its
own notion of what "testing" means for that hypothesis. The only contract every
theory honors is `record_opportunity` (section 6) — the single point that makes
cross-theory comparison and shared scoring possible without constraining how
any individual theory thinks.

Kalshi and Polymarket are both first-class **tools**, symmetric in how they're
exposed — a theory can read either or both. But **every suggested bet must
resolve to a specific, tradeable Kalshi market.** The user can only wager on
Kalshi. Polymarket data can inform reasoning, but a finding is not an
opportunity until it's linked to a Kalshi market via `tools/match_market.py`
plus confirmation of the match. There is no Polymarket-only opportunity in this
system; `record_opportunity` enforces this by requiring a Kalshi ticker.

## 4. Repository structure

```
LLM_market_identifier/
  CLAUDE.md                        Onboarding briefing (see section 13)
  .claude/
    skills/
      find-edge/SKILL.md           Main entrypoint: scan, rank, report
      propose-theory/SKILL.md      Scaffold + register a new theory
      backtest-theory/SKILL.md     Tiered retroactive testing
      score-theories/SKILL.md      Settle outcomes, recompute scores
      compare-theories/SKILL.md    Cross-theory performance report
  db/
    schema.sql                     SQLite schema (source of truth)
    market_edge.db                 The database (gitignored — data, not code)
  tools/
    README.md                      Tool-writing conventions, for extensibility
    db.py                          Connection helper + migration runner
    kalshi/
      markets.py                   Open/settled markets, live quotes
      history.py                   Candlesticks, point-in-time reconstruction
    polymarket/
      markets.py                   Open/resolved markets
      trades.py                    Trade history, large/whale-trade filtering
    match_market.py                Non-Kalshi finding -> Kalshi ticker shortlist
    ledger.py                      record_opportunity, mark-taken, queries
    score.py                       Settlement fetch, calibration, ROI
    rank.py                        Credibility-weighted ranking (section 7)
    sizing.py                      Fee model, Kelly, portfolio caps
    snapshot.py                    Market snapshot capture (forward history)
  theories/
    _TEMPLATE/THEORY.md
    insider_bias/                  Ported reference theory + its own code
  migrate_kalshi_trader.py         One-time import of kalshi_trader history
  docs/superpowers/specs/          Design specs (this file)
```

## 5. Data layer

SQLite (`db/market_edge.db`), schema in `db/schema.sql`. Chosen over flat CSVs
(`kalshi_trader`'s approach) because that repo overwrites its raw market dump on
every fetch with no history retained, and a system meant to run for a year,
compare many theories, and query calibration over time needs real history and
joins.

### `theories`
Registry index. The source of truth for a theory's hypothesis and procedure is
its `THEORY.md`; this table makes theories programmatically discoverable and
carries lifecycle state.

| column | type | notes |
|---|---|---|
| id | text PK | slug, e.g. `insider_bias` |
| name | text | |
| version | integer | starts at 1; bumped on any change to the decision procedure (section 9) |
| status | text | `proposed` \| `active` \| `paused` \| `retired` (section 10) |
| path | text | folder under `theories/` |
| created_at / updated_at | timestamp | |

### `market_snapshots`
Forward-history engine. Time-series observations of market state, keeping a
flexible `raw_json` alongside normalized columns since Kalshi (binary, cents)
and Polymarket (possibly multi-outcome, 0–1 probabilities) don't share a native
shape.

This table has a specific job, not speculative: it is the hedge against either
platform's own historical API being too shallow, and it is what grows the clean
backtest window described in section 11. **Every `find-edge` run writes
snapshots of the markets it fetches as a side effect**, so history accumulates
from normal use even with no scheduler configured.

| column | type | notes |
|---|---|---|
| id | integer PK | |
| platform | text | `kalshi` \| `polymarket` |
| market_id | text | ticker (Kalshi) or market/condition id (Polymarket) |
| captured_at | timestamp | |
| title | text | |
| implied_prob_yes | real, nullable | normalized convenience field for binary markets |
| yes_bid / yes_ask | real, nullable | needed to reconstruct executable prices, not just mid |
| volume | real, nullable | |
| open_interest | real, nullable | |
| close_time | timestamp, nullable | |
| status | text | `open` \| `closed` \| `settled` |
| raw_json | text | full original payload |

Index on `(platform, market_id, captured_at)`.

### `opportunities`
The shared spine. See section 6 for the full contract, including the dedup key
and the definition of edge.

| column | type | notes |
|---|---|---|
| id | integer PK | |
| theory_id | text FK → theories.id | |
| theory_version | integer | stamped at record time; scoring segments on this |
| run_mode | text | `live` \| `backtest` |
| run_id | text NOT NULL | `'live'` for live scans; a run uuid for backtests |
| scan_id | text | which individual scan first surfaced this (audit trail) |
| kalshi_ticker | text NOT NULL | the tradeable market this suggestion is for |
| outcome | text NOT NULL | `yes` \| `no`, or an outcome label |
| entry_price | real NOT NULL | **executable** price for this side (ask), not mid |
| spread_at_call | real, nullable | for executability filtering |
| volume_at_call | real, nullable | for executability filtering |
| model_prob | real, nullable | theory's probability estimate, if it makes one |
| edge_pts_gross | real, nullable | `(model_prob − entry_price) × 100` |
| fee_pts | real, nullable | estimated Kalshi fee in points, from `sizing.py` |
| edge_pts_net | real NOT NULL | **the ranking number** — gross minus fees (section 6) |
| confidence | text, nullable | theory's own scale — free text |
| rationale | text | |
| suggested_size | real, nullable | |
| evidence_source | text, nullable | `kalshi` \| `polymarket` \| other — where the signal originated |
| evidence_market_id | text, nullable | e.g. the Polymarket id that triggered the finding |
| user_action | text | `untouched` \| `taken` \| `skipped` (section 6) |
| user_size | real, nullable | what the user actually staked, if taken |
| first_seen_at | timestamp | entry timestamp; `entry_price` is from this moment |
| last_seen_at | timestamp | updated on re-sighting |
| times_seen | integer | incremented on re-sighting |
| extra_json | text, nullable | anything theory-specific |

`UNIQUE (theory_id, theory_version, run_id, kalshi_ticker, outcome)` — the
dedup key (section 6).

### `settlements`
Kalshi-only, since every opportunity resolves to a Kalshi ticker.

| column | type | notes |
|---|---|---|
| kalshi_ticker | text PK | |
| resolved_at | timestamp | |
| result | text | winning outcome label |
| settle_price | real, nullable | |

### `scores`
Recomputable performance summaries per theory *version*. Derived data — safe to
delete and rebuild from `opportunities` + `settlements`.

| column | type | notes |
|---|---|---|
| id | integer PK | |
| theory_id | text FK | |
| theory_version | integer | |
| run_mode | text | `live` \| `backtest` |
| backtest_tier | text, nullable | `A` \| `B` \| `C` (section 11) |
| window_start / window_end | timestamp | |
| n | integer | settled sample size |
| win_rate | real | |
| price_implied_rate | real | mean entry price of the settled sample |
| calibration_edge | real | `win_rate − price_implied_rate` — the key metric |
| mean_claimed_edge | real | mean `edge_pts_net` claimed at call time |
| realization | real | `calibration_edge / mean_claimed_edge`, clamped (section 7) |
| roi_all | real | hypothetical ROI across all suggestions, net of fees |
| roi_taken | real, nullable | realized ROI across `user_action = 'taken'` only |
| computed_at | timestamp | |

### `backtest_runs`
| column | type | notes |
|---|---|---|
| run_id | text PK | |
| theory_id | text FK | |
| theory_version | integer | |
| as_of_start / as_of_end | timestamp | historical window replayed |
| tier | text | `A` \| `B` \| `C` — **derived, not self-reported** (section 11) |
| uses_llm_judgment | boolean | did the decision path invoke a subagent |
| model_cutoff | date | knowledge cutoff used to compute the tier |
| notes | text | |
| created_at | timestamp | |

## 6. The opportunity contract

This is the one interface every theory implements, and the reason the system
can compare hypotheses at all. Four rules make it work.

**It must be tradeable on Kalshi.** `kalshi_ticker` is `NOT NULL`. A theory
whose signal came from Polymarket resolves it through `tools/match_market.py`
and confirms the match before recording; it keeps the provenance in
`evidence_source`/`evidence_market_id`.

**Edge is net, and priced at what you'd actually pay.** `entry_price` is the
*executable* price for the side being bought (the ask), not the mid — a claimed
edge measured against mid is partly fictional. `edge_pts_net` is
`edge_pts_gross − fee_pts`, using the shared Kalshi fee model in `sizing.py`,
and it is the only number ranking uses. Theories that derive edge some other
way (structural arbitrage, for instance) may leave `model_prob` and
`edge_pts_gross` null, but must still state an `edge_pts_net` — it is the
common currency across theories.

**Executability is a first-class filter.** `spread_at_call` and
`volume_at_call` are recorded so `find-edge` can drop suggestions that aren't
really takeable. A 3-point edge on a market with a 6-point spread and $80 of
volume is not an opportunity. Default thresholds live in `find-edge`, are
overridable per theory, and any filtered-out candidates are reported as a count
so nothing disappears silently.

**Re-sighting updates, it does not duplicate.** `record_opportunity` is an
upsert on `(theory_id, theory_version, run_id, kalshi_ticker, outcome)`. Live
scans use the literal `run_id = 'live'`, so a market that stays mispriced for a
week produces one row with `times_seen = 7`, not seven rows — `first_seen_at`
and `entry_price` preserve the entry you'd actually have gotten. Backtests pass
a real run uuid, so dedup is per-run while separate runs stay comparable.
Without this rule, repeat sightings silently multiply and calibration becomes
meaningless. (`kalshi_trader` hit exactly this and deduped at scoring time; here
it is prevented at the data layer.)

**Suggested is not the same as taken.** The user places bets manually and may
skip many. `ledger.py mark-taken` sets `user_action`/`user_size`. Scoring then
reports two distinct numbers: **theory calibration** over all suggestions (which
measures the theory) and **realized ROI** over taken ones (which measures the
account). Conflating them would report hypothetical money as real.

## 7. Ranking: from claimed edge to defensible edge

A theory Claude invented this morning claiming 12 points of edge and a theory
with 40 settled bets and a *measured* calibration edge are not the same kind of
number. `find-edge` ranks on a shrunk edge:

```
ranked_edge = edge_pts_net × credibility

realization  = clamp(calibration_edge / mean_claimed_edge, 0, 1.5)   # 1.0 if n = 0
credibility  = 0.25                            if n < 10   (probationary floor)
             = (n / (n + 20)) × realization    if n >= 10
```

Worked through: a brand-new theory claiming 12pt ranks as 3.0pt — visible, able
to beat a proven theory's weak suggestion, unable to dominate. A theory with
n=40 that realizes its full claimed edge gets credibility 0.67, so a 6pt claim
ranks 4.0pt. A theory with n=40 that realizes *none* of its claimed edge gets
credibility 0 and sinks — the probationary floor deliberately does not protect
a theory that has been measured and found wanting.

Two supporting rules:

- **Never hide the shrinkage.** Output shows claimed edge, ranked edge, `n`,
  and realization side by side. The user should always be able to see that a
  top-ranked suggestion is top-ranked because of evidence, or in spite of having
  none.
- **Which settlements count toward `n`.** Live settlements always count.
  Backtest settlements count at full weight for tiers A and B; tier C is
  excluded from credibility entirely (section 11), because contaminated
  results are not evidence of edge.

**Cross-theory convergence.** When several theories independently surface the
same ticker and side, `find-edge` collapses them into one line and reports the
agreement — convergent independent evidence is a genuine positive signal, and
listing it three times would otherwise inflate one bet into three. Conversely,
when many top suggestions cluster on correlated markets (several Fed-linked
markets, say), that concentration is called out, since a portfolio of
correlated bets is not diversified regardless of individual edge.

## 8. Tools

Flat, small, single-purpose scripts — not a framework. `tools/README.md`
documents the convention (JSON/SQLite in and out, a `--help` describing what the
tool does, no shared base classes) precisely so Claude can read one tool
end-to-end and write a new one in the same shape — "fetch weather data," "fetch
congressional trading disclosures" — without first learning an abstraction
layer.

- **`tools/kalshi/markets.py`** — open markets, settled markets with
  resolution, live re-quote by ticker (bid/ask, not just mid). Ported from
  `kalshi_trader`'s `fetch_kalshi_markets.py`; Kalshi market data needs no auth.
- **`tools/kalshi/history.py`** — historical candlesticks (1min/1hr/1day, public
  API) plus point-in-time market-state reconstruction built on them.
- **`tools/polymarket/markets.py`** — open/resolved markets via Polymarket's
  public Gamma API. *Endpoint shapes unverified at design time* (section 17).
- **`tools/polymarket/trades.py`** — trade history and large/whale-trade
  filtering via the public CLOB/data API. Also unverified at design time.
- **`tools/match_market.py`** — the required bridge from a non-Kalshi finding to
  an actionable suggestion. Returns a mechanically-generated shortlist of
  plausible Kalshi equivalents (keyword/category/date overlap). Deliberately
  does *not* make the final "same market?" call — that judgment belongs to
  Claude or a subagent reading the shortlist, and it must check resolution
  criteria, not just topic: two markets about the same event with different
  settlement rules are not the same market.
- **`tools/ledger.py`** — `record-opportunity` (upserts per section 6; rejects a
  call with no `kalshi_ticker` or no `edge_pts_net`), `mark-taken`,
  `list-opportunities`.
- **`tools/score.py`** — `settle` (fetch outcomes for opportunities that have
  resolved) and `report` (win rate, price-implied rate, calibration edge,
  realization, ROI split by all-vs-taken, segmented by theory version).
- **`tools/rank.py`** — the section 7 credibility calculation, factored out so
  `find-edge` and `compare-theories` rank identically.
- **`tools/sizing.py`** — Kalshi fee model, Kelly sizing, portfolio caps, ported
  from `kalshi_trader`. A theory may use these or size its own way, but
  `fee_pts` always comes from here so edge is defined consistently.
- **`tools/snapshot.py`** — capture current market state into
  `market_snapshots`. Callable directly; also invoked automatically by
  `find-edge` so forward history accrues from normal use.

## 9. Theory format and versioning

A theory is a folder under `theories/<slug>/`. The only required file is
`THEORY.md`:

```markdown
# <Theory name>

## Hypothesis
What's the thesis? Why would this produce edge — what mistake is the market
making, and why would it persist?

## Data sources
Which platforms/tools does this theory use?

## Status
proposed | active | paused | retired — with a journal of changes and why.

## Version
Current version number, and a changelog of what changed at each bump.

## How to scan for live candidates
A procedure for Claude to follow: which tools to call, what to filter for,
when to spawn a subagent for judgment, how results reach record_opportunity.
If the signal originates outside Kalshi, this must include the
tools/match_market.py step — record_opportunity has no Kalshi-less path.

## How to backtest
A procedure for Claude to follow using the point-in-time tools (section 11).
State plainly whether the decision path uses LLM judgment, since that
determines the backtest tier.

## Learnings
Running journal — what worked, what didn't, surprises.
```

Everything else in the folder is theory-owned: Python scripts, prompt templates,
notebooks, fixture data — whatever the hypothesis needs. There is no mandated
internal shape and no required functions. A structural arbitrage theory might be
deterministic math with no LLM at all; a whale-copy theory might be almost
entirely subagent judgment across both platforms; a research theory might lean
on web search. `_TEMPLATE/` carries the empty `THEORY.md` and a note describing
this freedom, so a theory scaffolded via `propose-theory` isn't tempted to copy
`insider_bias`'s specific shape as though it were mandatory.

**Versioning exists to prevent silent drift.** Any change to a theory's decision
procedure — thresholds, prompts, scan logic — bumps `theories.version` and adds
a changelog entry. Every opportunity stamps `theory_version`, and scoring
segments on it. Without this, tweaking a theory after 20 settled bets silently
merges two different theories into one track record, which both destroys the
long-time-span testing this project exists for and invites the classic
overfitting trap of tuning until the history looks good. `compare-theories`
shows versions separately and flags any version whose `n` is too small to mean
much.

## 10. Theory lifecycle

Status transitions have default bars. Claude may override any of them, but must
record the reason in `THEORY.md` — the point is that drift and accumulation are
visible, not that Claude lacks agency.

- **`proposed` → `active`** — requires either a tier A or tier B backtest
  showing positive calibration edge, or an explicit user override. This keeps
  untested ideas from immediately consuming scan budget.
- **`active` → review** — at `n = 20` settled, `score-theories` flags any theory
  whose calibration edge is ≤ 0 for a look.
- **`active` → `paused`** — at `n = 50` settled with calibration edge still
  ≤ 0. (`kalshi_trader`'s own strategy notes argue for flat stakes until 50+
  settled bets before trusting a result; the same threshold applies to
  disbelieving one.)
- **`paused` → `retired`** — reviewed and judged dead. Retired theories stay on
  disk: a hypothesis that failed is evidence, and re-testing a retired idea
  later against more data is legitimate.

Retired and paused theories are skipped by `find-edge` by default.

## 11. Backtesting and hindsight contamination

Backtesting is a toolkit a theory's own procedure draws on, not one rigid replay
engine, because testing means different things for different hypotheses:

- Point-in-time market state (`tools/kalshi/history.py`, extendable to
  Polymarket, supplemented by `market_snapshots`) — what did this market look
  like as of a past date.
- Settlement lookup (`tools/score.py`) — what actually happened.
- The same `record_opportunity` contract with `run_mode = backtest` and a real
  `run_id`, so results land in the shared scorer but stay separable from live.

**The contamination problem.** A subagent judging an already-resolved market may
simply know how it turned out, from training data or from live search. A
backtest built on that measures recall, not edge. The mitigation is not a
self-reported honesty field — it is a **tier derived from facts observable at
run time**, computed and recorded by `backtest-theory`:

- **Tier A — clean.** The theory's decision path invokes no LLM judgment
  (deterministic screens, price/volume rules, structural arbitrage, monotonicity
  checks). No contamination is possible. Backtest over all available history;
  results count as full evidence.
- **Tier B — quarantined.** The decision path uses LLM judgment, but replay is
  restricted to markets that resolved *after* the judging model's knowledge
  cutoff, with web search disabled in the subagent. Small sample today (the
  window is roughly the months since the cutoff) but genuinely valid, and it
  grows every month — which is what makes ongoing snapshot collection worth
  doing.
- **Tier C — indicative only.** LLM judgment against pre-cutoff markets.
  Explicitly labeled contaminated, **excluded from credibility in section 7**,
  and usable only to sanity-check the *screening* stage — never as evidence of
  edge.

**Contamination probe.** Before trusting anything from a tier C run, a cheap
per-market test: ask a subagent to state the outcome directly, given only the
market question and no price data. If it knows, that market is contaminated and
its replay result is discarded. This turns an unfalsifiable worry into a
measurement, and can rescue individual obscure markets from a tier C run.

Web search must be disabled in any backtest judgment subagent regardless of
tier, since live search trivially reveals historical outcomes.

## 12. Skills

- **`find-edge`** — the headline entrypoint. Selects theories by scope (default:
  `active` only, prioritized by credibility); follows each `THEORY.md` scan
  procedure within a **scan budget** (a default cap on subagent batches per
  invocation, so the run stays interactive as the theory count grows); writes
  snapshots as a side effect; filters unexecutable candidates and reports how
  many were dropped; collapses cross-theory duplicates; ranks by section 7; and
  reports a table of ticker, side, entry price, claimed edge, ranked edge, `n`,
  realization, theory, suggested size, and rationale — plus flags on correlated
  clustering. Accepts a scope override to run all theories or named ones.
- **`propose-theory`** — scaffolds `theories/<slug>/` from `_TEMPLATE`, registers
  it at `status=proposed`, `version=1`, and works through the hypothesis, data
  sources, and both procedures. Prompts for what would *falsify* the thesis,
  not just support it.
- **`backtest-theory`** — determines the tier from the theory's decision path
  and the market resolution dates, enforces the web-search prohibition, runs the
  replay, records `backtest_runs`, and scores the result with the tier's caveat
  attached.
- **`score-theories`** — settles resolved opportunities, recomputes `scores` per
  theory version, and surfaces lifecycle flags from section 10.
- **`compare-theories`** — ranks theories by demonstrated calibration edge with
  sample sizes, versions kept separate, live vs. backtest kept separate, tier C
  clearly marked, and small-`n` caveats attached.

## 13. CLAUDE.md

A substantial onboarding briefing for whichever Claude session opens this repo,
since "what can I actually do here" must be explicit rather than inferred:

1. **Mission** — find the largest edge; propose your own theories; don't wait to
   be told what to test.
2. **Non-goals** — no fixed strategy ships here; inventing new ones is your job.
3. **Platform roles** — Kalshi is where bets get placed; Polymarket is an
   equally first-class research tool. Every suggestion must resolve to a Kalshi
   ticker via a confirmed match.
4. **Toolkit map** — one paragraph per tool: what it does, when to reach for it.
5. **The opportunity contract** — section 6 in brief: net edge at executable
   prices, dedup by upsert, executability filtering, suggested ≠ taken.
6. **How ranking works** — section 7, so Claude understands why a confident new
   theory doesn't automatically top the list, and doesn't try to game it.
7. **Theory lifecycle and versioning** — including the requirement to bump
   version on any procedure change.
8. **Backtest tiers** — what's trustworthy, what's indicative, why web search is
   off during replay.
9. **Subagent usage** — when to spawn, how to batch, and why (no API keys; this
   runs on the user's subscription).
10. **Data conventions** — SQLite is the source of truth for structured facts;
    `THEORY.md` is the source of truth for a hypothesis and its procedure.
11. **Getting started** — `find-edge` is the default entrypoint.

## 14. Migration from kalshi_trader

- **Reusable code ported into `tools/`**: Kalshi market fetching, deterministic
  filter patterns, sizing/fee math, and the settlement + calibration-edge
  scoring approach — generalized to be theory-agnostic and to write SQLite
  rather than CSVs.
- **`insider_bias` ported as the reference theory**: its prompts and config
  become the basis of its `THEORY.md` scan procedure; its classify/pick judgment
  moves from OpenAI API calls to orchestrating-Claude/subagent judgment. It
  starts at `version=1` with imported history attributed to that version.
- **`migrate_kalshi_trader.py`** — one-time import of
  `ledger/bets_ledger.csv` and `kalshi_data_backtest/scored_*.csv` into
  `opportunities`/`settlements`, tagged `theory_id=insider_bias`,
  `run_mode=live`, preserving original timestamps, and **applying the section 6
  dedup rule** (that ledger contains repeat recommendations across runs, so a
  naive import would import the very duplication problem this design fixes).
  Imported rows get `user_action='untouched'` unless the user can say otherwise;
  their `entry_price` uses the recorded price, flagged in `extra_json` where mid
  versus executable is ambiguous in the source data.
- The original `kalshi_trader` repo is left untouched.
- `obvious_mispricing` and the theories cataloged in `LLM_EDGE_STRATEGIES.md` /
  `FORECAST_GAP_IMPLEMENTATION_PLAN.md` are **not** ported — `insider_bias`
  alone proves the harness end to end. Anything further is `propose-theory` work.

## 15. Testing approach

- Unit tests (pytest) for deterministic pieces: `sizing.py` (fee/Kelly math),
  `rank.py` (credibility formula, including the disproven-theory and n=0 cases
  worked through in section 7), `db.py` (migrations), `ledger.py` (upsert
  semantics — verify a re-sighting increments `times_seen` and preserves
  `entry_price` rather than inserting), `score.py` (calibration/ROI against
  fixtures).
- Rate-limit-conscious smoke tests for `kalshi/*` and `polymarket/*` against the
  real public endpoints (no auth required).
- Skills are LLM-followed procedures, not code — verified by an end-to-end dry
  run of `find-edge` against the ported `insider_bias` theory.

## 16. Out of scope for this build

- Any theory beyond `insider_bias` — deliberately left as `propose-theory` work.
- A scheduler for `snapshot.py`. The tool exists and `find-edge` writes
  snapshots as a side effect, so history accumulates from use; wiring a
  recurring job is a follow-up.
- A rendered dashboard. Chat-based reporting is the interface for now.
- Real-money order execution.

## 17. Open risks

- **Polymarket API specifics** (Gamma/CLOB endpoint shapes, rate limits) were
  not verified live during design and need confirming when the tools are built.
- **Kalshi historical depth is unverified.** The candlestick endpoint exists and
  needs no auth, but how far back it reaches and how completely it covers
  settled markets is unknown. This directly bounds tier A backtesting on day
  one, and is the main reason `market_snapshots` exists. Confirm early — it may
  change how much backtesting is possible before forward collection matters.
- **Tier B's window is thin today** (months since the model cutoff), so
  judgment-based theories will have weak backtest evidence initially and must
  lean on live results accumulating.
- **The ranking constants** (probationary floor 0.25, shrinkage denominator 20,
  `n=10` probation threshold, realization clamp 1.5) are reasoned defaults, not
  empirically derived. Revisit once several theories have real track records.
- **Scan budget sizing** for `find-edge` needs tuning against real candidate
  volumes and theory counts.
