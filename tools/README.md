# Tools

Small, single-purpose scripts, plus one deliberate exception. Leaf tools
are plain functions — read one end to end and you know how to write the
next one, and there is still no framework to learn at that layer. The
**theory layer** (`domain.py`, `theory.py`, `registry.py`) has a base
class, because this file's own promotion criterion — more than one real
caller — was met: two theories with unrelated entry points, and twenty-two
more specced. A theory inherits *what to do* (`start`, `finish`) and is
handed *what it may touch* (`TheoryContext`); everything below that
boundary stays plain functions, and every tool remains directly callable
without the contract.

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
- **Long collections record as they go.** Anything that fetches for more
  than a minute — a settled-history walk, a multi-series candle replay, a
  paged crawl — writes its results incrementally (per series, per page,
  per market) to the DB or a checkpoint file it resumes from, so an
  interruption costs seconds of work, not the run. Never accumulate an
  hour of fetches in memory with a single write at the end. This is not
  only about wasted time: source data expires — Kalshi archives settled
  markets out of its public API ~60 days after close (see
  `kalshi/markets.py::list_settled`) — so rows lost to a crash may no
  longer exist upstream by the time the run is repeated. The worked
  examples: `iter_settled_survivors` in
  `theories/insider_bias/replay.py` is a generator *precisely so* the
  driver can checkpoint after every series, and `theories/insider_bias/
  mention_family/backtest.py` records hits and saves its checkpoint file
  per series, skipping completed series on resume. The rule covers
  **token spend the same as network time**: LLM usage can cut out at any
  moment, so judgment work is batched, each batch's inputs are written to
  disk before any model runs, each subagent writes its own verdicts to a
  file, and every batch is ingested and committed before the next one is
  dispatched — a future session that never saw this one can ingest a
  stranded verdicts file and score however far the run got.
  `theories/insider_bias/insider_judgment/backtest_judged.py` is the
  worked example (sample → per-batch payload files → dispatch →
  per-batch idempotent ingest → score-what-landed). Raw fetched payloads
  worth keeping go through `tools/kalshi/cache.py`
  (`db/history_cache.db`) so a variant re-test never re-walks the
  network.
- **Prices are decimal dollars in [0, 1]. Edge is in percentage points.**
  Conversion happens at the API boundary; no provider's wire format escapes
  its client module.
- **A position may have legs.** `record_opportunity` writes a single
  position; `record_basket` writes a multi-leg one whose payoff is joint.
  A basket's `entry_price` is its total cost and is bounded by `max_payout`,
  not by 1.0. Scoring counts a basket once, and excludes it until every leg
  has settled — recording an arbitrage as N independent bets makes a certain
  payout read as a coin flip. A position also declares `min_payout`, its
  guaranteed floor, alongside `max_payout`; both default to the
  single-position case (`0.0` and `1.0`), which is why every row recorded
  before floors existed scores identically. Scoring grades only the portion
  at risk — `implied_rate = (entry_price − min_payout) /
  (max_payout − min_payout)`, using the fee-exclusive entry price so
  `mean_fee_pts` subtracts fees exactly once instead of folding them into
  the rate too. `won` means the position paid its full `max_payout`. A
  position whose fee-inclusive cost is covered by its floor
  (`cost <= min_payout`) cannot lose: it is scored on return only, reported
  as `riskless_n` / `riskless_roi`, and excluded from `n`, `win_rate`, and
  `calibration_edge(_net)` rather than pooled with calibrated positions. It
  still counts toward `roi_all` unconditionally, and toward `roi_taken` only
  if it was actually marked taken — the money is real either way, it is just
  never mistaken for a forecast. A settled payout outside
  `{min_payout, max_payout}` raises — the decomposition still assumes the
  at-risk portion is binary.
- **A position is identified by theory version, not by run.**
  `opportunities` is keyed `(theory_id, theory_version, run_mode, lane,
  kalshi_ticker, outcome)` — `run_id` stays on the row as an attribute
  (which run first saw this), never as identity, so the same bet
  re-proposed by five runs across five sessions is one position, not
  five. `lane` is `'main'` for every real run and the full run id for an
  `exp/` run, so a variant under test never merges into the record it is
  measured against — the mechanism behind the "`exp/` run ids are
  experiments" rule below, now enforced by the key itself rather than
  only by a filter.
- **`opportunity_attempts` holds what actually happened; `opportunities`
  is a rollup, not the record.** Every re-sighting of a position — one row
  per `(opportunity_id, decision_date, run_id)` — is an attempt, carrying
  its own `entry_price`, `edge_pts_net`, `confidence`, `judged_blind`,
  `disposition`, `rationale`, and `extra_json`. The position row can only
  hold one value per column, so a merge may overwrite the rollup but may
  never lose an attempt's value — that is what lets a theory's feature
  flags and per-run reasoning survive a re-proposal instead of being
  silently discarded by whichever run happened to record last.
  `decision_date` is the day the theory was deciding about, never the day
  the code ran: a backtest **must** pass it explicitly
  (`record_opportunity`/`record_basket` raise on a backtest with no
  `decision_date`), or a replay covering many days stamps every attempt
  with the same wall-clock date and the primary key silently collapses
  many decisions into one row.
- **Scoring keys on the ATTEMPT, never on the position's disposition**
  (ruling 2026-08-29; `tools/score.py::_DECISION_ATTEMPTS`,
  `tests/test_attempt_scoring.py`). An attempt joins the pool of *its
  own* disposition, so a position endorsed on Monday and rejected on
  Tuesday earns settlement feedback in **both** pools — two decisions
  were really made, and each is priced at the decision it records.
  `opportunities.disposition` is the **current view only**, for display
  and live decisions; grouping scores on it let a later run retroactively
  erase an earlier run's published decision, which is the
  disposition-form of the silent merge the versioning rule exists to
  prevent (re-see your losers, flip them to `rejected`, launder the
  endorsed pool). Two refinements keep it honest: consecutive
  same-disposition attempts collapse to their **first** — a
  re-affirmation at a drifted price is the standing decision re-observed,
  not a new one, and first-of-run is also the least drift-contaminated
  price — while keying on *changes* rather than on (position,
  disposition) means a genuine flip-back scores twice. And a `screened`
  attempt on a position that already carries an interpreted verdict is a
  **non-decision**: it records the scan re-seeing the market without
  stage 2 engaging, so it stays in the ledger but is not scored. A
  `screened` attempt *before* any interpretation does score — that is the
  real stage-1 baseline, and dropping it would bias the screened pool
  toward never-interpreted positions. For a fully mechanical theory the
  whole rule is a no-op.
- **Uncertainty is clustered at the EVENT, and credibility keys on the
  CLUSTER count** (ruling 2026-08-29). Sibling markets of one Kalshi
  event share an outcome driver, so rows overstate evidence by roughly
  the sibling count — session 78's hazard estimate ran z≈9 naive against
  1.34 clustered, on 2,805 rows that were only 48 clusters. So
  `compute_score` emits `n_clusters` (the effective sample size),
  `clustered_se` (between-cluster SE of the net calibration edge, `None`
  below two clusters because one cluster says nothing about spread), and
  `unclustered_rows`. `rank.credibility(n, ...)` takes the **cluster**
  count: a theory holding fifty siblings of one event must not clear
  probation as n=50 when it has watched one event resolve. The event is
  derived from `extra_json.event_ticker`, else the ticker minus its last
  dash-segment; unrecoverable rows cluster alone and are counted, never
  silently bucketed. **Schema migration:** `scores.n_clusters` and
  `scores.clustered_se` are additive and nullable, and historical rows
  are deliberately **not** backfilled — a stored score row records what
  was computed then, so NULL means "not computed under this semantics"
  and must never be read as a cluster count of 0.
- **`opportunity_fills` is the money-side mirror of attempts.** Every
  `mark-taken ... taken` appends a fill rather than overwriting, so
  scaling into a position on two different days at two different prices
  keeps both, and `roi_taken` is computed from what was actually paid.
  `mark-taken` now **requires `--theory`** for a `taken` action (not for
  `skipped` — only money can be double-counted): two theories can both
  propose the same market, but only the named one is credited with the
  purchase, which is what stops `roi_taken` from crediting every theory
  that happened to see it.
- **No credentials.** Every endpoint this project uses is public. Never add
  an API key, and never send any user identifier in a header, URL, or body.
- **Edge numbers carry a provenance tier.** Every edge is stamped with an
  `edge_basis`: `measured` (a confidence bucket's own realized win rate —
  see `buckets.py`), `model` (a mechanical calculation with no judgment
  step), or `prior` (a declared placeholder standing in until there is
  enough settled history to measure). There is deliberately no basis meaning
  "an LLM felt it was about right." Any new tool that produces an edge
  number must say which of the three it is.
- **Any code that fetches external data takes `fetch: Fetch | None = None`**
  (resolved to `http.get_json` at call time). One parameter makes a theory
  testable against a canned payload with no network and no monkeypatch —
  the same discipline as injectable `now`, applied to transports.
- **Facts are data, not procedure.** A theory's durable facts live in
  `theory_facts`; adding one (a confirmed pair, an implication edge) never
  bumps its version. Changing how facts are *derived* does. A
  model-established fact carries `construction`-stage provenance.
- **`Theory` is for things that produce bets.** A study produces theories
  (mark its folder with `STUDY.md`; discovery skips it); an execution
  policy decorates candidates. Neither is a `Theory` subclass.
- **A theory's ranking evidence can be partitioned by registered
  slices** (`slices.py`, `theory_slices`). A slice is an immutable,
  pre-registered hypothesis that a mechanical subset of one theory's
  output (predicate over recorded fields: outcome, confidence, price
  band, `extra_json`) carries its own edge. Its credibility counts only
  out-of-sample evidence — settlements after registration, or runs
  designated at registration (any run that proposed the position, not
  just the first seer); tier-C rows feed no segment. Past its gates
  (≥ 10 out-of-sample event clusters, ≥ 5 settlement days) it splits
  ranking into slice and complement; below them nothing changes.
  Registering one never bumps the theory version. `score.observations`
  + `score.aggregate` are the seam it consumes — partitioning that list
  and aggregating a part IS `compute_score` on that part.
- **`exp/` run ids are experiments.** Pooled `compute_score` and
  `bucket_rates` exclude them; score one explicitly by passing its
  `run_id`. This is what makes variant-testing free — a subclass and a
  run id, no version bump, no registration (see CLAUDE.md).
- **A basket must still pay floor-or-ceiling to be *scored*.** Any
  `Candidate` shape records fine, but `score._basket_observations` raises
  on a settled basket paying strictly between its `min_payout` and
  `max_payout` — the at-risk decomposition assumes that portion is binary.
  A basket that can genuinely land in between needs a different definition
  of `won` for a multi-outcome position; that is not built.
- **For a backtest, this layer owns time, bookkeeping and scoring; the
  theory owns the replay.** `tools/kalshi/history.py` and `tools/snapshot.py`
  (point-in-time truth), the `run_mode`/`run_id` plumbing through
  `theory.finish()`, the `backtest_runs` table, and `score.py` are the
  whole shared contribution. **There is no `tools/backtest.py` replay
  engine, and none gets built** — `theories/insider_bias/replay.py` shows
  why: most of its design handles quirks (a combinatorial series settling
  400,000 markets a day, per-day candle volume that must be summed into a
  lifetime total, a fetch-scoping filter that must not leak into the screen
  under test) belonging to replaying *this* screen over Kalshi's
  settled-market API — a theory with a different thesis inherits none of
  them. A shared engine would have to either anticipate every such quirk or
  paper over it silently, and a second theory-local backtest resembling the
  first is not evidence that it could. Narrow primitives still promote one
  at a time under the rule below — `systematic_sample`, a checkpointed
  per-series iterator, a candle-walk state reconstructor — as plain
  functions, never as a framework that inverts control over the theory.
- **Code elevates by caller count; knowledge elevates by audience.** The
  promotion rule below moves a helper into `tools/` when a second theory
  really calls it. A research note moves instead into whatever the *repo
  level* reads: `THEORY.md` if it changes the theory's claims, the database
  if it is a fact or a result, `RESEARCH_LOG.md` if it is session
  narrative. Raw notes (a theory's `NOTES.md`) never move at all — they get
  summarized, and the raw entry stays as the audit trail. See CLAUDE.md,
  "What lives in a theory, and what gets elevated".

### Backup cadence (ruled at spec 5.2 phase 4, 2026-08-30)

`db/market_edge.db` (the ledger — small, irreplaceable; schema in
`db/schema.sql`): `python -m tools.cli db backup` before any schema
migration or destructive maintenance command (`split-snapshots` runs one
itself), and at the start of any session that will settle or migrate.
`db/snapshots.db` (large, prices re-fetchable in spirit; schema in
`db/schema_snapshots.sql`, ATTACHed as `snapdb` by `db.connect()`): no
automatic backup; copy the file manually if a study depends on a specific
historical window.

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
| `domain.py` | Frozen value types: `Market`, `Candidate`, `Verdict`, `Edge`, `ScanResult` |
| `theory.py` | The theory contract: `Theory`, `TheoryRun`, `TheoryContext` |
| `registry.py` | Discovery; drift check between code and the DB registry |
| `theories.py` | Theory registry, evidence-level status, versioning, retirement proposals |
| `ideas.py` | Research memory — every hypothesis considered, and why it died |
| `ledger.py` | `record_opportunity`, `record_basket`, interpretation, user actions |
| `score.py` | Settlements, calibration edge, ROI, interpretation value |
| `rank.py` | Credibility-weighted ranking |
| `promotion.py` | The promotion-key evaluator (`docs/promotion-key.md`) — which rung a recorded candidate sits on, and orphaned-evidence escalations |
| `slices.py` | Registered subset edges — per-slice out-of-sample credibility and the slice/complement ranking partition |
| `buckets.py` | Confidence-bucket win rates → measured edge, not guessed |
| `sizing.py` | Kalshi fee model, Kelly sizing |
| `board.py` | The session's shared Kalshi board — one pull per session, reused by every theory |
| `snapshot.py` | First-party market history capture |
| `provenance.py` | Which model judged and with which prompt — required for any theory with an LLM in its decision path |
| `match_market.py` | Non-Kalshi finding → Kalshi ticker shortlist |
| `http.py` | Retrying HTTP for the public APIs |
| `backup.py` | Ledger backup — gzipped copy of every table except `market_snapshots`, restorable by `gunzip` + `db.init_db` |
| `state.py` | The orientation surface — renders THEORIES/STANDING/EVIDENCE/WINDOWS/QUEUE/FRESHNESS from the DB |
| `rulings.py` | Binding rulings as rows — `record`/`list`/`status`, so a ruling stops binding only until nobody scrolls to it in the log |
| `tools/kalshi/markets.py` | Open/settled markets, live quotes, resolution rules |
| `tools/kalshi/history.py` | Candlesticks, point-in-time reconstruction |
| `tools/polymarket/markets.py` | Open/resolved markets |
| `tools/polymarket/trades.py` | Trades, whale detection, holders |
