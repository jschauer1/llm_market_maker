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
- A **two-stage model** (section 7) that treats a theory's pipeline output as a
  candidate set to be researched and interpreted, not as a finished
  recommendation — and measures whether that interpretation actually adds
  value.
- A **ranking discipline** (section 8) that converts a *claimed* edge into a
  *credibility-weighted* one, so "largest edge" is an evidence-backed claim
  rather than whichever theory sounds most confident.
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
  CLAUDE.md                        Onboarding briefing (see section 15)
  RESEARCH_LOG.md                  Append-only session log — continuity across "go" runs
  .claude/
    skills/
      go/SKILL.md                  Autonomous research session (section 13)
      find-edge/SKILL.md           Scan, research, rank, report
      propose-theory/SKILL.md      Scaffold + register a new theory
      backtest-theory/SKILL.md     Tiered retroactive testing
      score-theories/SKILL.md      Settle outcomes, recompute scores
      compare-theories/SKILL.md    Cross-theory + interpretation-value report
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
    ledger.py                      record_opportunity, interpret, mark-taken
    ideas.py                       Idea registry — research memory (section 11)
    score.py                       Settlement fetch, calibration, ROI
    rank.py                        Credibility-weighted ranking (section 8)
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
| version | integer | starts at 1; bumped on any change to the decision procedure (section 10) |
| status | text | `proposed` \| `active` \| `paused` \| `retired` (section 11) |
| path | text | folder under `theories/` |
| created_at / updated_at | timestamp | |

### `ideas`
The research memory (section 11). Every hypothesis that gets *considered* is
recorded here, whether or not it ever becomes a theory. This is what stops the
system from re-deriving the same dead end every few months, and — just as
importantly — what lets it deliberately revisit an idea from a new angle rather
than abandoning it permanently.

| column | type | notes |
|---|---|---|
| id | integer PK | |
| slug | text UNIQUE | short handle, e.g. `polymarket-whale-copy` |
| title | text | |
| description | text | the hypothesis in a sentence or two |
| status | text | `considered` \| `investigating` \| `promoted` \| `parked` \| `dead` |
| theory_id | text FK, nullable | set when the idea becomes a theory |
| source | text | where it came from: `claude`, `user`, `divergence` (mined from `user_reason`), `observation` |
| what_was_tried | text, nullable | what investigation actually happened — not what was planned |
| outcome | text, nullable | what was learned; for a dead idea, *why* it died |
| revisit_angle | text, nullable | what a genuinely different approach would look like; null means exhausted |
| revisit_after | text, nullable | a date or a condition, e.g. "once 6 months of snapshots exist" |
| created_at / updated_at | timestamp | |

### `market_snapshots`
Forward-history engine. Time-series observations of market state, keeping a
flexible `raw_json` alongside normalized columns since Kalshi (binary, decimal
dollars) and Polymarket (possibly multi-outcome, 0–1 probabilities) don't share
a native shape.

This table has a specific job, not speculative: it is the hedge against either
platform's own historical API being too shallow, and it is what grows the clean
backtest window described in section 12. **Every `find-edge` run writes
snapshots of the markets it fetches as a side effect**, so history accumulates
from normal use even with no scheduler configured.

| column | type | notes |
|---|---|---|
| id | integer PK | |
| platform | text | `kalshi` \| `polymarket` |
| market_id | text | ticker (Kalshi) or condition id (Polymarket) |
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
The shared spine. See section 6 for the contract and section 7 for the
screen-versus-interpretation distinction the disposition columns encode.

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
| model_prob | real, nullable | probability estimate — only from a **mechanical** model, never LLM introspection (section 7) |
| edge_pts_gross | real, nullable | `(model_prob − entry_price) × 100` |
| fee_pts | real, nullable | estimated Kalshi fee in points, from `sizing.py` |
| screen_edge_pts_net | real NOT NULL | what stage 1 claimed — frozen, never revised |
| edge_pts_net | real NOT NULL | current best estimate; **the ranking number** (section 6) |
| edge_basis | text | `measured` (from this bucket's realized rate), `prior` (bucket not yet measured), or `model` (mechanical) — section 7 |
| disposition | text | `screened` \| `endorsed` \| `rejected` (section 7) |
| interpretation | text, nullable | Claude's research notes and reasoning at stage 2 |
| interpreted_at | timestamp, nullable | null if never researched |
| confidence | text, nullable | the theory's declared ordinal bucket, e.g. `strong` — scoring groups on this |
| judged_blind | integer, nullable | 1 if the judgment step did not see the price (section 7) |
| rationale | text | the theory's own reasoning at screen time |
| suggested_size | real, nullable | |
| evidence_source | text, nullable | `kalshi` \| `polymarket` \| other — where the signal originated |
| evidence_market_id | text, nullable | e.g. the Polymarket id that triggered the finding |
| user_action | text | `untouched` \| `taken` \| `skipped` (section 6) |
| user_size | real, nullable | what the user actually staked, if taken |
| user_reason | text, nullable | why the user diverged — mined for new theories (section 7) |
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
Recomputable performance summaries, segmented by theory version **and
disposition** so the value of interpretation is measurable (section 7). Derived
data — safe to delete and rebuild from `opportunities` + `settlements`.

| column | type | notes |
|---|---|---|
| id | integer PK | |
| theory_id | text FK | |
| theory_version | integer | |
| run_mode | text | `live` \| `backtest` |
| disposition | text | `all` \| `screened` \| `endorsed` \| `rejected` |
| backtest_tier | text, nullable | `A` \| `B` \| `C` (section 12) |
| window_start / window_end | timestamp | |
| n | integer | settled sample size |
| win_rate | real | |
| price_implied_rate | real | mean entry price of the settled sample |
| calibration_edge | real | `(win_rate − price_implied_rate) × 100` — gross of fees, in points. How wrong the market's prices were |
| calibration_edge_net | real | `calibration_edge − mean fee_pts(entry_price)`. What a trader actually kept, and the only figure comparable with a net claim |
| mean_claimed_edge | real | mean `edge_pts_net` claimed at call time — net of fees by definition |
| realization | real | `calibration_edge_net / mean_claimed_edge`, clamped (section 8) |
| roi_all | real | hypothetical ROI across all suggestions, net of fees |
| roi_taken | real, nullable | realized ROI across `user_action = 'taken'` only |
| computed_at | timestamp | |

### `bucket_rates`
The measured meaning of a theory's confidence buckets (section 7). Derived and
recomputable from `opportunities` + `settlements`; this table caches it.

| column | type | notes |
|---|---|---|
| id | integer PK | |
| theory_id | text FK | |
| theory_version | integer | |
| confidence | text | the bucket label, e.g. `strong` |
| n | integer | settled sample size in this bucket |
| win_rate | real | **this is the bucket's empirical probability** |
| mean_entry_price | real | |
| computed_at | timestamp | |

### `backtest_runs`
| column | type | notes |
|---|---|---|
| run_id | text PK | |
| theory_id | text FK | |
| theory_version | integer | |
| as_of_start / as_of_end | timestamp | historical window replayed |
| tier | text | `A` \| `B` \| `C` — **derived, not self-reported** (section 12) |
| uses_llm_judgment | boolean | did the decision path invoke a subagent |
| model_cutoff | date | knowledge cutoff used to compute the tier |
| notes | text | |
| created_at | timestamp | |

## 6. The opportunity contract

This is the one interface every theory implements, and the reason the system
can compare hypotheses at all. Five rules make it work.

**It must be tradeable on Kalshi.** `kalshi_ticker` is `NOT NULL`. A theory
whose signal came from Polymarket resolves it through `tools/match_market.py`
and confirms the match before recording; it keeps the provenance in
`evidence_source`/`evidence_market_id`.

**Edge is net, and priced at what you'd actually pay.** `entry_price` is the
*executable* price for the side being bought (the ask), not the mid — a claimed
edge measured against mid is partly fictional. `edge_pts_net` is the gross edge
minus `fee_pts`, using the shared Kalshi fee model in `sizing.py`, and it is
the only number ranking uses. It is the common currency across theories, so
every recorded opportunity must state one.

`edge_basis` says where that number came from, and the three sources are not
equally trustworthy: `measured` (a confidence bucket's own realized win rate),
`model` (a mechanical calculation), or `prior` (a declared placeholder for a
bucket with too few settled results yet). **No path produces an LLM-introspected
probability** — see section 7. `screen_edge_pts_net` freezes what stage 1
claimed so a later interpretive revision stays comparable against the original.

**Executability is a first-class filter.** `spread_at_call` and
`volume_at_call` are recorded so `find-edge` can drop suggestions that aren't
really takeable. A 3-point edge on a market with a 6-point spread and $80 of
volume is not an opportunity. Default thresholds live in `find-edge`, are
overridable per theory, and filtered-out candidates are reported as a count so
nothing disappears silently.

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
skip many. `ledger.py mark-taken` sets `user_action`/`user_size`/`user_reason`.
Scoring reports two distinct numbers: **theory calibration** over all
suggestions (which measures the theory) and **realized ROI** over taken ones
(which measures the account). Conflating them would report hypothetical money
as real.

## 7. Pipelines propose, judgment disposes

**The aspiration:** a theory is a deterministic pipeline. Run it, and out come
markets with a quantified edge — reproducible, cheap, no interpretation needed.
That is the target every theory should be pushed toward, because anything
encoded in code is testable, repeatable, and scales to thousands of markets for
free.

**The reality:** that is rarely the whole story, and pretending otherwise
produces bad bets. `insider_bias` is the worked example. It emits ranked picks,
but those picks are not bet as given. What actually happens is that a human
reads the output and recognizes something the pipeline never encoded — a
reality-TV market is *structurally* vulnerable in a way a general
"insider knowledge" screen does not capture. The edge lives partly in the
pipeline and partly in the pattern recognition applied to its output.

So every theory is understood as two stages, and the system must never collapse
them:

**Stage 1 — mechanical screen.** Deterministic, reproducible, cheap over
thousands of markets: filters, thresholds, structural checks, cross-platform
matching, whatever the theory can express in code. This narrows the universe.
Anything that *can* be encoded here should be — pushing work from stage 2 into
stage 1 is how a theory gets better over time.

**Stage 2 — interpretive judgment.** Contextual research on the narrowed set:
what kind of market is this really, what does the resolution language actually
require, is this market type structurally soft or structurally dangerous, does
recent news change the picture. This is Claude reading the output rather than
trusting it, and it is expected to be the norm rather than the exception.

**Pipeline output is a candidate set, not a recommendation.** `find-edge` must
present the two layers distinctly — what the screen surfaced, and what research
concluded about it — and must never present unresearched screen output as a
recommended bet. Because stage 2 costs real time, it is applied within the scan
budget to the highest-ranked candidates, and the count of screened-but-not-yet-
researched candidates is always reported so the unexamined remainder is visible.

### What to ask a subagent for — and what not to

LLMs are poorly calibrated probability estimators. They cluster on round
numbers, shift with prompt phrasing, have no stable internal scale across
sessions, and — worst for this system — **anchor hard on any number already in
context.** Show a model the market price and ask for its own probability and it
reliably returns the price plus a small delta, manufacturing "edge" that is
nothing but anchoring noise. `kalshi_trader` did exactly this: its pick prompt
displayed `bet=SIDE@price` and `mid`, then asked for a `q`.

So this system does not ask for probabilities. It asks for what LLMs are
actually good at and derives the numbers from measured outcomes.

**Ask a judgment step for:**

- **Categorical classification** against a stated definition — "is there a
  specific, identifiable group who already knows the outcome?"
- **Structural features** — "is this pre-taped?", "do the resolution rules
  differ from what the title implies?", "could the resolution source fail to
  publish before close?"
- **An ordinal confidence bucket** on a scale the theory declares (for example
  `strong` / `moderate` / `weak`).
- **Relative ranking** within a candidate set — which of these is the better
  bet, not what each one's probability is.
- **Reading comprehension over resolution text** — genuinely a strength, and
  the highest-value thing stage 2 does.

**Do not ask a judgment step for:**

- A point probability (`q = 0.87`).
- A numeric edge estimate in points.
- Anything needing fine-grained numeric discrimination.

**Judge blind to price.** Wherever a theory allows it, the judgment step must
not see the market price, the mid, or any implied probability. Get the
classification and confidence bucket first, reveal the price second, compute
edge mechanically. This is the single highest-value rule here, because
anchoring is the largest contaminant of LLM judgment — and it costs nothing to
follow.

**Numbers come from measurement, not introspection.** A confidence bucket is
converted to a probability by that bucket's *own realized track record*:

```
bucket_prob   = wins / n           for (theory, version, confidence bucket)
edge_pts_net  = (bucket_prob − entry_price) × 100 − fee_pts(entry_price)
```

After enough settled bets, "when this theory says `strong`, it wins 78% of the
time" is a fact, not a guess — and it is exactly the number the edge
calculation needs. `tools/score.py` computes these bucket rates alongside the
existing per-theory scores.

**Cold start.** Before a bucket has enough settled results (default: 10), the
theory's declared **prior edge** for that bucket is used instead, and the
opportunity is flagged as resting on a prior rather than a measurement. Priors
should be deliberately conservative — a theory claiming 12 points from an
unmeasured bucket is claiming to know something it has not yet demonstrated.
The section 8 credibility floor already prevents such claims from dominating,
so the two mechanisms compound rather than overlap.

**Mechanically derived probabilities remain welcome.** The objection is to
*LLM-introspected* numbers, not to arithmetic. A theory that computes a
probability from base rates, a Poisson process, sibling-strike monotonicity,
or any explicit model should absolutely do so and record it in `model_prob` —
that number is reproducible and auditable in a way an LLM's felt sense is not.
A theory whose edge rests on a mechanical model is generally *stronger* than
one resting on judgment, and it also backtests at tier A (section 12).

**Measuring whether interpretation earns its keep.** Every opportunity carries a
`disposition`: `screened` (the pipeline surfaced it, no research yet),
`endorsed` (researched and recommended), or `rejected` (researched and
declined). Rejected candidates stay in the database and still settle, which
makes them a free control group. Scoring therefore reports calibration three
ways per theory — across all screened, across endorsed only, and across
rejected only — and the comparison answers a question neither stage can answer
alone:

- **Endorsed clearly outperforms rejected** → interpretation is adding edge.
  The pipeline is a candidate generator; the judgment is the product.
- **Endorsed and rejected perform alike** → interpretation is adding nothing.
  Either strengthen stage 1 or trust the pipeline and save the research time.
- **Rejected outperforms endorsed** → interpretation is destroying value, which
  is worth discovering early rather than never.

**Mining divergence for new theories.** When the user takes a bet the system did
not endorse, or skips one it did, that gap is usually an unencoded heuristic —
exactly like "reality TV markets are soft." `mark-taken` captures an optional
`user_reason`, and `compare-theories` surfaces recurring patterns in those
reasons as candidate theories. This is one of the most direct routes to Claude
proposing genuinely new hypotheses: tacit intuition becomes an explicit,
testable theory, and if it survives scoring it graduates from stage 2 judgment
into stage 1 code.

## 8. Ranking: from claimed edge to defensible edge

A theory Claude invented this morning claiming 12 points of edge and a theory
with 40 settled bets and a *measured* calibration edge are not the same kind of
number. `find-edge` ranks on a shrunk edge:

```
ranked_edge = edge_pts_net × credibility

realization  = clamp(calibration_edge_net / mean_claimed_edge, 0, 1.5)  # 1.0 if n = 0
credibility  = 0.25                            if n < 10   (probationary floor)
             = (n / (n + 20)) × realization    if n >= 10
```

**Realization must use the NET calibration edge.** `mean_claimed_edge`
averages `edge_pts_net`, which is net of fees by definition, so comparing it
against the gross `calibration_edge` credits a theory with edge it never
kept. A theory delivering exactly its claimed 6.0 net points would score
realization 1.29, and a theory breaking exactly even after fees would post a
positive calibration edge — clearing the "pause if calibration edge ≤ 0"
lifecycle rule and out-ranking an untested idea on zero profit. `scores`
stores both figures: the gross one because market miscalibration is worth
reporting on its own, the net one because it is the one that may be compared
against a claim, and it is the figure the lifecycle thresholds read.

Worked through: a brand-new theory claiming 12pt ranks as 3.0pt — visible, able
to beat a proven theory's weak suggestion, unable to dominate. A theory with
n=40 that realizes its full claimed edge gets credibility 0.67, so a 6pt claim
ranks 4.0pt. A theory with n=40 that realizes *none* of its claimed edge gets
credibility 0 and sinks — the probationary floor deliberately does not protect
a theory that has been measured and found wanting.

Three supporting rules:

- **Never hide the shrinkage.** Output shows claimed edge, ranked edge, `n`,
  and realization side by side, so the user can always see whether a top-ranked
  suggestion earned its place on evidence or in the absence of any.
- **Credibility uses the matching disposition.** For an endorsed opportunity,
  `realization` comes from the theory's *endorsed* score row, not its
  all-candidates row — a theory whose screen is mediocre but whose interpreted
  picks are good should be credited for the latter.
- **Which settlements count toward `n`.** Live settlements always count.
  Backtest settlements count at full weight for tiers A and B; tier C is
  excluded from credibility entirely (section 12), because contaminated results
  are not evidence of edge.

**Cross-theory convergence.** When several theories independently surface the
same ticker and side, `find-edge` collapses them into one line and reports the
agreement — convergent independent evidence is a genuine positive signal, and
listing it three times would inflate one bet into three. Conversely, when many
top suggestions cluster on correlated markets (several Fed-linked markets, say),
that concentration is called out, since a portfolio of correlated bets is not
diversified regardless of individual edge.

## 9. Tools

Flat, small, single-purpose scripts — not a framework. `tools/README.md`
documents the convention (JSON/SQLite in and out, a `--help` describing what the
tool does, no shared base classes) precisely so Claude can read one tool
end-to-end and write a new one in the same shape — "fetch weather data," "fetch
congressional trading disclosures" — without first learning an abstraction
layer.

**New code starts local; promotion is earned, not automatic.** When a theory
needs something, the default home for it is that theory's own folder. Most
theory code is specific to one hypothesis and belongs nowhere else — generalizing
it prematurely produces a shared layer full of near-duplicates and
single-caller abstractions, which is worse than a little duplication.

A theory-local script becomes a candidate for promotion to `tools/` when it is
actually being used by more than one theory, or when Claude judges that a new
theory would obviously reach for it. Promotion is a **researcher judgment call**,
not a rule that fires automatically on a second use — sometimes two theories
genuinely want slightly different things and should keep their own versions.
When promoting:

- Move the script to `tools/`, generalize only as far as the real callers
  require, and give it the `tools/README.md` treatment (docstring, `--help`,
  JSON/SQLite in and out).
- Update the theories that used the local copy to call the shared one, and
  delete the local copies so there is one implementation.
- Note the promotion in each affected theory's `THEORY.md` changelog. If the
  behavior changed at all in the process, that is a decision-procedure change
  and bumps the theory version (section 10).

This mirrors the stage 2 → stage 1 migration in section 7: a thing proves itself
in a narrow context first, then graduates to the shared layer once there is
evidence it belongs there.

All Kalshi and Polymarket endpoints used here were verified live during design
(2026-08-23) and require **no authentication**. Field shapes are documented in
the implementation plan; note that Kalshi's current schema returns prices as
decimal-dollar strings (`yes_ask_dollars`) and sizes as `_fp` strings, which
differs from the older integer-cent schema `kalshi_trader` was written against.

- **`tools/kalshi/markets.py`** — open markets, settled markets with
  resolution, live re-quote by ticker (bid/ask, not just mid), plus each
  market's `rules_primary` resolution text, which stage 2 research depends on.
- **`tools/kalshi/history.py`** — historical candlesticks (1min/1hr/1day) which
  include **historical bid/ask**, not just last trade — so point-in-time
  reconstruction can produce genuinely executable prices for backtests.
  Verified to reach back at least ~12 months.
- **`tools/polymarket/markets.py`** — open/resolved markets via the public
  Gamma API (`conditionId`, `question`, `outcomePrices`, `bestBid`/`bestAsk`,
  `volumeNum`, `endDate`, `description`).
- **`tools/polymarket/trades.py`** — trade history and large/whale-trade
  filtering via the public data API, including per-trade wallet identity and
  per-market holder positions — the raw material for whale-following theories.
- **`tools/match_market.py`** — the required bridge from a non-Kalshi finding to
  an actionable suggestion. Returns a mechanically-generated shortlist of
  plausible Kalshi equivalents (keyword/category/date overlap). Deliberately
  does *not* make the final "same market?" call — that judgment belongs to
  Claude or a subagent reading the shortlist, and it must compare resolution
  criteria, not just topic: two markets about the same event with different
  settlement rules are not the same market.
- **`tools/ledger.py`** — `record-opportunity` (upserts per section 6; rejects a
  call with no `kalshi_ticker` or no `edge_pts_net`), `interpret` (sets
  disposition, interpretation text, and any revised edge — section 7),
  `mark-taken`, `list-opportunities`.
- **`tools/ideas.py`** — the research memory: `record`, `search` (by keyword,
  so a proposal can be checked against prior art before any work starts),
  `update-status`, `list-revisitable` (parked ideas whose `revisit_after`
  condition may now be met, plus dead ones that still carry a `revisit_angle`).
- **`tools/score.py`** — `settle` (fetch outcomes for opportunities that have
  resolved), `report` (win rate, price-implied rate, calibration edge,
  realization, ROI split by all-vs-taken, segmented by theory version and
  disposition), and `bucket-rates` (realized win rate per confidence bucket —
  the measured probability that replaces a guessed one, section 7).
- **`tools/rank.py`** — the section 8 credibility calculation, factored out so
  `find-edge` and `compare-theories` rank identically.
- **`tools/sizing.py`** — Kalshi fee model, Kelly sizing, portfolio caps, ported
  from `kalshi_trader`. A theory may size its own way, but `fee_pts` always
  comes from here so edge is defined consistently.
- **`tools/snapshot.py`** — capture current market state into
  `market_snapshots`. Callable directly; also invoked by `find-edge` so forward
  history accrues from normal use.

## 10. Theory format and versioning

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

## Stage 1 — mechanical screen
What this theory can encode deterministically: which tools to call, what
filters and thresholds, how candidates reach record_opportunity. If the
signal originates outside Kalshi, this must include the
tools/match_market.py step — record_opportunity has no Kalshi-less path.

## Stage 2 — what needs judgment
What this theory cannot encode, and what Claude should look for when reading
its output: market types that are structurally soft or dangerous,
resolution-language traps, context worth researching before endorsing.
Anything here that proves reliable should eventually migrate into stage 1.

Ask for classifications, structural features, and a confidence bucket —
never a probability (section 7). State whether judgment happens blind to
price; it should wherever possible.

## Confidence buckets
The ordinal scale this theory's judgment step uses, and a conservative prior
edge (in points) for each, used only until that bucket has enough settled
results to measure. Example:

| bucket | meaning | prior edge (pts) |
|---|---|---|
| strong | concrete named group that already knows | 4.0 |
| moderate | plausible informed group, less specific | 2.0 |
| weak | thesis is a stretch | 0.0 |

## How to backtest
A procedure using the point-in-time tools (section 12). State plainly whether
the decision path uses LLM judgment, since that determines the tier.

## Learnings
Running journal — what worked, what didn't, surprises.
```

Everything else in the folder is theory-owned: Python scripts, prompt templates,
notebooks, fixture data — whatever the hypothesis needs. There is no mandated
internal shape and no required functions. A structural arbitrage theory might be
deterministic math with no LLM at all (and an empty stage 2); a whale-copy
theory might be almost entirely subagent judgment across both platforms; a
research theory might lean on web search. `_TEMPLATE/` carries the empty
`THEORY.md` and a note describing this freedom, so a scaffolded theory isn't
tempted to copy `insider_bias`'s specific shape as though it were mandatory.

**Versioning exists to prevent silent drift.** Any change to a theory's decision
procedure — thresholds, prompts, scan logic, or migrating a stage 2 heuristic
into stage 1 — bumps `theories.version` and adds a changelog entry. Every
opportunity stamps `theory_version`, and scoring segments on it. Without this,
tweaking a theory after 20 settled bets silently merges two different theories
into one track record, which both destroys the long-time-span testing this
project exists for and invites the classic overfitting trap of tuning until the
history looks good. `compare-theories` shows versions separately and flags any
version whose `n` is too small to mean much.

## 11. Idea and theory lifecycle

### The idea registry — research memory

An idea does not need to become a theory to be worth remembering. Most won't:
some are investigated for ten minutes and dismissed, some are good but blocked
on data that doesn't exist yet, some are tried properly and fail. **All of them
get recorded in `ideas`.** Without this the system has no research memory — a
session six months from now cheerfully re-derives a hypothesis that was already
tested and killed, burns the same effort, and reaches the same dead end.

Every idea carries three fields that do the real work:

- **`what_was_tried`** — what investigation *actually happened*, not what was
  planned. "Screened 400 markets, found only 6 candidates, none survived
  research" is useful; "investigated whale-copying" is not.
- **`outcome`** — what was learned, and for a dead idea specifically *why* it
  died. The failure mode matters more than the failure: an idea that died
  because the signal wasn't there is finished, while one that died because the
  matching step was too crude is a tooling problem wearing an idea's clothes.
- **`revisit_angle`** — what a genuinely *different* approach would look like.
  This is the field that distinguishes "don't try this again" from "don't try
  this again *the same way*." A null `revisit_angle` means the idea is
  exhausted; a populated one means it's waiting for someone to come at it
  differently.

`revisit_after` holds a date or a condition (`"once 6 months of snapshots
exist"`, `"if Kalshi lists more reality-TV markets"`) for ideas that are sound
but premature. Those are among the highest-value work a research session can
pick up, because the blocking condition may now be satisfied.

**Statuses:** `considered` (recorded, not yet investigated) → `investigating` →
either `promoted` (became a theory; `theory_id` links them), `parked` (not now,
with a reason and ideally a revisit condition), or `dead` (tried and failed,
with the why).

**Two hard rules.** Before proposing a new theory, Claude **must** search the
idea registry first — a new idea that matches a `dead` one needs a real
`revisit_angle` to justify running again, and one that matches a `parked` one
should check whether its `revisit_after` condition is now met. And when a theory
is retired (below), its originating idea is updated to `dead` with the reason,
so the failure is recorded where the next proposal will actually look for it.

Retiring a theory without writing down why it failed is how a system forgets.

### Theory statuses

Status transitions have default bars. Claude may override any of them but must
record the reason in `THEORY.md` — the point is that drift and accumulation stay
visible, not that Claude lacks agency.

- **`proposed` → `active`** — requires either a tier A or tier B backtest
  showing positive *net* calibration edge, or an explicit user override. This
  keeps untested ideas from consuming scan budget.
- **`active` → review** — at `n = 20` settled, `score-theories` flags any theory
  whose *net* calibration edge is ≤ 0 for a look.
- **`active` → `paused`** — at `n = 50` settled with *net* calibration edge
  still ≤ 0.
  (`kalshi_trader`'s own strategy notes argue for flat stakes until 50+ settled
  bets before trusting a result; the same threshold applies to disbelieving
  one.) Before pausing, check the section 7 breakdown: a theory whose *endorsed*
  subset performs well while its overall screen does not is not dead — it is a
  theory whose stage 1 needs tightening.
- **`paused` → `retired`** — reviewed and judged dead. Retired theories stay on
  disk: a failed hypothesis is evidence, and re-testing it later against more
  data is legitimate.

Retired and paused theories are skipped by `find-edge` by default.

## 12. Backtesting and hindsight contamination

Backtesting is a toolkit a theory's own procedure draws on, not one rigid replay
engine, because testing means different things for different hypotheses:

- Point-in-time market state (`tools/kalshi/history.py`, supplemented by
  `market_snapshots`) — what did this market look like as of a past date,
  including its bid/ask so entry prices stay executable rather than notional.
- Settlement lookup (`tools/score.py`) — what actually happened.
- The same `record_opportunity` contract with `run_mode = backtest` and a real
  `run_id`, so results land in the shared scorer but stay separable from live.

**The contamination problem.** A subagent judging an already-resolved market may
simply know how it turned out, from training data or from live search. A
backtest built on that measures recall, not edge. The mitigation is not a
self-reported honesty field — it is a **tier derived from facts observable at
run time**, computed and recorded by `backtest-theory`:

- **Tier A — clean.** The decision path invokes no LLM judgment (deterministic
  screens, price/volume rules, structural arbitrage, monotonicity checks). No
  contamination is possible. Backtest over all available history; results count
  as full evidence. Verified: Kalshi candlesticks reach back at least ~12
  months, so tier A has real runway from day one.
- **Tier B — quarantined.** The decision path uses LLM judgment, but replay is
  restricted to markets that resolved *after* the judging model's knowledge
  cutoff, with web search disabled in the subagent. Small sample today (roughly
  the months since the cutoff) but genuinely valid, and it grows every month —
  which is what makes ongoing snapshot collection worth doing.
- **Tier C — indicative only.** LLM judgment against pre-cutoff markets.
  Explicitly labeled contaminated, **excluded from credibility in section 8**,
  and usable only to sanity-check the *screening* stage — never as evidence of
  edge.

**Contamination probe.** Before trusting anything from a tier C run, a cheap
per-market test: ask a subagent to state the outcome directly, given only the
market question and no price data. If it knows, that market is contaminated and
its replay result is discarded. This turns an unfalsifiable worry into a
measurement, and can rescue individual obscure markets from a tier C run.

Web search must be disabled in any backtest judgment subagent regardless of
tier, since live search trivially reveals historical outcomes.

## 13. Operating modes

Two ways the user drives this repo. Both must work without ceremony.

### "Go" — an autonomous research session

The user opens the repo and says `go`. Claude then works the research loop on
its own initiative: sees what has happened since last time, judges where the
marginal value is right now, does that work, and reports back. The goal is that
this is genuinely useful with zero further direction — but *structured* enough
that Claude doesn't flounder or default to the same action every session.

**Always start by orienting.** Cheap and mechanical, no judgment required:
active theories and their versions, opportunities still open, anything that has
settled since the last session, current scores and lifecycle flags, and the tail
of `RESEARCH_LOG.md` for what the previous session was in the middle of. This
takes one pass over the database and costs almost nothing.

**Then choose where the value is.** This is a judgment call, not a checklist,
and it is the part that makes a research session worth running. The standing
menu of work:

- Settle resolved opportunities and refresh scores.
- Hunt for live edge with the active theories, and research the top candidates
  (`find-edge`).
- Backtest a theory that is running on claims rather than evidence.
- Propose a new theory — from an observed market pattern, from a gap in what the
  current theories cover, or from a recurring `user_reason` divergence. Check
  the idea registry first (section 11).
- Revisit a parked idea whose blocking condition may now be met, or a dead one
  that still carries a `revisit_angle` worth trying from a different direction.
- Tighten an existing theory: migrate a stage 2 heuristic that keeps proving
  itself into stage 1 code, or promote a theory-local tool that multiple
  theories now use (section 9).
- Pause or retire a theory the evidence has killed.

**Prefer work that changes a decision.** If nothing has settled since yesterday,
re-scoring is busywork — go hunt instead. If every active theory is unproven,
another scan adds unproven suggestions while a backtest adds evidence. If the
same theory has been scanned three sessions running with no settlements yet,
the marginal value is in a *new* theory, not a fourth scan of the old one. Say
which you picked and why in one line, so the user can redirect cheaply.

**Always leave a trail.** A session ends by appending to `RESEARCH_LOG.md`: what
was done, what was learned, what is worth picking up next. Without this, every
`go` starts cold and the system has no memory across sessions — the log is what
makes a year of autonomous research accumulate into something rather than
repeating itself. Theory-specific findings additionally go in that theory's
`THEORY.md` Learnings section; the log is for cross-cutting observations and
continuity.

**Report for a human, not a machine.** End with what the user actually needs:
any bets worth placing right now, anything that changed about a theory's
standing, and anything that needs their judgment. Not a transcript of every tool
call.

A session is free to be short. "Nothing has settled, no theory needs
backtesting, here are two candidates I researched and rejected and why" is a
perfectly good outcome, and better than manufacturing work.

### Asking questions

The user can also just open the repo and ask: "how is `insider_bias` holding
up?", "what's the best bet right now?", "why did we retire that theory?", "does
anything on Polymarket look mispriced against Kalshi?". These get answered
directly using the tools and the database — no research session, no ceremony,
no running the full loop because someone asked a question. `CLAUDE.md` orients
Claude well enough that ordinary questions route to the right tool without a
skill invocation.

## 14. Skills

- **`go`** — the autonomous research session described above: orient, choose,
  act, log, report. Deliberately thin on prescription — it establishes the
  opening move and the standing menu, and leaves the choice to Claude.
- **`find-edge`** — the headline entrypoint. Selects theories by scope (default:
  `active` only, prioritized by credibility); runs each theory's stage 1 screen
  within a **scan budget** (a cap on subagent batches per invocation, so the run
  stays interactive as the theory count grows); writes snapshots as a side
  effect; filters unexecutable candidates and reports how many were dropped;
  collapses cross-theory duplicates; then applies **stage 2 research** to the
  top-ranked candidates and records each as endorsed or rejected with reasoning.
  Reports in two clearly separated layers: **endorsed** bets (ticker, side,
  entry price, claimed edge, ranked edge, `n`, realization, theory, suggested
  size, interpretation) and the **unresearched remainder** (count plus top few),
  so the user can see both what was recommended and what went unexamined.
  Rejected candidates and their reasons are available on request. Accepts a
  scope override to run all theories or named ones.
- **`propose-theory`** — **starts by searching the idea registry** (section 11):
  if this hypothesis has been tried before, the prior `outcome` and
  `revisit_angle` decide whether to proceed, proceed differently, or stop. Then
  records the idea, scaffolds `theories/<slug>/` from `_TEMPLATE`, registers it
  at `status=proposed`, `version=1`, links the idea to it, and works through the
  hypothesis, data sources, and both stages. Asks explicitly what belongs in
  stage 1 versus stage 2, and what would *falsify* the thesis rather than only
  support it. An idea that is investigated and dropped before ever becoming a
  theory is still recorded, with what was tried and why it was dropped.
- **`backtest-theory`** — determines the tier from the theory's decision path
  and market resolution dates, enforces the web-search prohibition, runs the
  replay, records `backtest_runs`, and scores with the tier's caveat attached.
- **`score-theories`** — settles resolved opportunities, recomputes `scores` per
  theory version and disposition, and surfaces lifecycle flags from section 11.
- **`compare-theories`** — ranks theories by demonstrated calibration edge with
  sample sizes, versions separate, live vs. backtest separate, tier C marked,
  and small-`n` caveats attached. Also reports the **interpretation-value
  breakdown** from section 7 (endorsed vs. rejected vs. all) and any recurring
  patterns in `user_reason` divergences that might deserve to become theories.

## 15. CLAUDE.md

A substantial onboarding briefing for whichever Claude session opens this repo,
since "what can I actually do here" must be explicit rather than inferred:

1. **Mission** — find the largest edge; propose your own theories; don't wait to
   be told what to test.
2. **Non-goals** — no fixed strategy ships here; inventing new ones is your job.
3. **Platform roles** — Kalshi is where bets get placed; Polymarket is an
   equally first-class research tool. Every suggestion must resolve to a Kalshi
   ticker via a confirmed match.
4. **Pipelines propose, judgment disposes** — section 7 as a core operating
   principle: screen output is a candidate set, never a finished recommendation;
   research before endorsing; record rejections so the value of your own
   judgment stays measurable. **Never state a probability you introspected** —
   give a classification and a confidence bucket, judge blind to price where
   you can, and let measured bucket rates supply the number.
5. **How the user drives this** — section 13: `go` starts an autonomous
   research session; plain questions get answered directly without running the
   loop. Both are normal.
6. **Toolkit map** — one paragraph per tool: what it does, when to reach for it.
   Plus the promotion path: new code starts in the theory that needs it and
   moves to `tools/` only once it has more than one real caller (section 9).
7. **The opportunity contract** — section 6 in brief: net edge at executable
   prices, dedup by upsert, executability filtering, suggested ≠ taken.
8. **How ranking works** — section 8, so Claude understands why a confident new
   theory doesn't automatically top the list, and doesn't try to game it.
9. **Theory lifecycle and versioning** — including bumping version on any
   procedure change, and migrating proven stage 2 heuristics into stage 1.
10. **Backtest tiers** — what's trustworthy, what's indicative, why web search is
    off during replay.
11. **Subagent usage** — when to spawn, how to batch, and why (no API keys; this
    runs on the user's subscription).
12. **Research memory** — section 11: search the idea registry before proposing
    anything, record every idea you consider (including the ones you drop and
    why), and write a `revisit_angle` rather than closing a door permanently.
    Never retire a theory without recording why it failed.
13. **Data conventions** — SQLite is the source of truth for structured facts;
    `THEORY.md` is the source of truth for a hypothesis and its procedure;
    `RESEARCH_LOG.md` carries continuity between sessions — read its tail when
    starting, append to it when finishing.
14. **Getting started** — say `go` for a research session, or just ask a
    question.

## 16. Migration from kalshi_trader

- **Reusable code ported into `tools/`**: Kalshi market fetching, deterministic
  filter patterns, sizing/fee math, and the settlement + calibration-edge
  scoring approach — generalized to be theory-agnostic and to write SQLite
  rather than CSVs. **The fetch code needs updating to Kalshi's current field
  schema** (`yes_ask_dollars`/`volume_fp` decimal strings, status `active`/
  `finalized`), which differs from what `kalshi_trader` was written against.
- **`insider_bias` ported as the reference theory**: its prompts and config
  become its `THEORY.md` stage 1 screen; its classify/pick judgment moves from
  OpenAI API calls to orchestrating-Claude/subagent judgment. Its known
  unencoded heuristics — the reality-TV-vulnerability pattern being the
  motivating example — are written into **stage 2**, where they belong until
  they prove out well enough to migrate into stage 1. Starts at `version=1`
  with imported history attributed to that version.
- **`migrate_kalshi_trader.py`** — one-time import of `ledger/bets_ledger.csv`
  and `kalshi_data_backtest/scored_*.csv` into `opportunities`/`settlements`,
  tagged `theory_id=insider_bias`, `run_mode=live`, preserving original
  timestamps, and **applying the section 6 dedup rule** (that ledger contains
  repeat recommendations across runs, so a naive import would import the very
  duplication problem this design fixes). Imported rows get
  `disposition='screened'` and `user_action='untouched'` unless the user can say
  otherwise — the historical ledger records what was *suggested*, and the user
  has said they did not bet it as given.
- The original `kalshi_trader` repo is left untouched.
- `obvious_mispricing` and the theories cataloged in `LLM_EDGE_STRATEGIES.md` /
  `FORECAST_GAP_IMPLEMENTATION_PLAN.md` are **not** ported — `insider_bias`
  alone proves the harness end to end. Anything further is `propose-theory` work.

## 17. Testing approach

- Unit tests (pytest) for deterministic pieces: `sizing.py` (fee/Kelly math),
  `rank.py` (credibility formula, including the disproven-theory and n=0 cases
  worked through in section 8), `db.py` (migrations), `ledger.py` (upsert
  semantics — a re-sighting must increment `times_seen` and preserve
  `entry_price` rather than insert; `interpret` must set disposition without
  disturbing `screen_edge_pts_net`), `score.py` (calibration/ROI against
  fixtures, including the disposition split).
- Rate-limit-conscious smoke tests for `kalshi/*` and `polymarket/*` against the
  real public endpoints (no auth required).
- Skills are LLM-followed procedures, not code — verified by an end-to-end dry
  run of `find-edge` against the ported `insider_bias` theory.

## 18. Out of scope for this build

- Any theory beyond `insider_bias` — deliberately left as `propose-theory` work.
- A scheduler for `snapshot.py`. The tool exists and `find-edge` writes
  snapshots as a side effect, so history accumulates from use; wiring a
  recurring job is a follow-up.
- A rendered dashboard. Chat-based reporting is the interface for now.
- Real-money order execution.

## 19. Open risks

- **Interpretation value is unmeasurable early.** The section 7 endorsed-vs-
  rejected comparison needs a meaningful number of *both* to have settled before
  it says anything. Until then it's noise, and stage 2 runs on judgment alone.
- **Tier B's window is thin today** (months since the model cutoff), so
  judgment-based theories will have weak backtest evidence initially and must
  lean on live results accumulating.
- **The ranking constants** (probationary floor 0.25, shrinkage denominator 20,
  `n=10` threshold, realization clamp 1.5) are reasoned defaults, not
  empirically derived. Revisit once several theories have real track records.
- **Scan budget sizing** for `find-edge` needs tuning against real candidate
  volumes and theory counts, especially since stage 2 research is the expensive
  part.
- **Polymarket endpoint stability.** The Gamma and data APIs are public and
  verified working, but undocumented enough that field shapes may shift; the
  tools should fail loudly rather than silently mis-parse.
- **Kalshi schema drift.** Already observed once (integer cents → decimal-dollar
  strings). Parsing should be defensive and version-aware.
