-- Market Edge Finder schema.
-- All timestamps are UTC ISO-8601 TEXT. All prices are decimal dollars in [0,1].
-- All edge values are in percentage points.

-- Theory status is an evidence level, not an administrative flag:
--   proposed     hypothesis written, procedure unproven, not scanned
--   testing      procedure runs and accrues evidence; claims are not demonstrated
--   active       demonstrated positive net calibration edge
--   under_review failing its own bar; KEEPS RUNNING while it is diagnosed
--   paused       blocked on a missing prerequisite, not on evidence
--   retired      judged dead -- USER-ONLY, see tools/theories.py
-- retirement_proposed_at / _rationale hold a standing suggestion to the user
-- that a theory is dead. Claude writes them; only the user acts on them.
CREATE TABLE IF NOT EXISTS theories (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    status      TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed','testing','active',
                                  'under_review','paused','retired')),
    path        TEXT NOT NULL,
    retirement_proposed_at TEXT,
    retirement_rationale   TEXT,
    -- 1 when any LLM sits in this theory's decision path (gate, analysis, or
    -- final review). Theories that declare it cannot record opportunities for
    -- a run with no judgment_runs provenance -- see tools/provenance.py.
    uses_llm_judgment INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ideas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    slug           TEXT NOT NULL UNIQUE,
    title          TEXT NOT NULL,
    description    TEXT,
    status         TEXT NOT NULL DEFAULT 'considered'
                   CHECK (status IN ('considered','investigating','promoted',
                                     'parked','dead')),
    theory_id      TEXT REFERENCES theories(id),
    source         TEXT,
    what_was_tried TEXT,
    outcome        TEXT,
    revisit_angle  TEXT,
    revisit_after  TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    platform         TEXT NOT NULL CHECK (platform IN ('kalshi','polymarket')),
    market_id        TEXT NOT NULL,
    captured_at      TEXT NOT NULL,
    title            TEXT,
    implied_prob_yes REAL,
    yes_bid          REAL,
    yes_ask          REAL,
    volume           REAL,
    open_interest    REAL,
    close_time       TEXT,
    status           TEXT,
    raw_json         TEXT,
    -- The market's Kalshi event envelope (kalshi only), minus its nested
    -- `markets` list. Additive and nullable on purpose: NULL means the
    -- envelope was not captured, which is NOT the same as an envelope
    -- saying mutually_exclusive=false. Every capture before 2026-08-29 is
    -- NULL, because list_open fetched the envelope and discarded it.
    event_json       TEXT
);

-- One row per market per capture. `captured_at` has one-second resolution
-- and is the batch key a whole pull shares, so without this two saves inside
-- the same second silently merge into one batch with every market duplicated
-- -- a board that rebuilds to twice its size and still looks complete.
-- Doubles as the lookup index; the columns are the ones queries use anyway.
CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_unique
    ON market_snapshots (platform, market_id, captured_at);

CREATE TABLE IF NOT EXISTS opportunities (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    theory_id           TEXT NOT NULL REFERENCES theories(id),
    theory_version      INTEGER NOT NULL,
    run_mode            TEXT NOT NULL CHECK (run_mode IN ('live','backtest')),
    run_id              TEXT NOT NULL,
    -- Which track record this position belongs to. 'main' for the real
    -- record; the full run id for an experiment, so a variant being tried
    -- never merges into the record it is meant to be measured against.
    lane                TEXT NOT NULL DEFAULT 'main',
    scan_id             TEXT,
    kalshi_ticker       TEXT NOT NULL,
    outcome             TEXT NOT NULL,
    entry_price         REAL NOT NULL,
    position_kind       TEXT NOT NULL DEFAULT 'single'
                        CHECK (position_kind IN ('single','basket')),
    leg_count           INTEGER NOT NULL DEFAULT 1,
    max_payout          REAL NOT NULL DEFAULT 1.0,
    -- The least this position can pay. Scoring grades only the portion
    -- above it: implied_rate = (cost - min_payout) / (max_payout -
    -- min_payout). Default 0.0 makes that identical to the plain
    -- cost/max_payout every existing row was scored by. Unlike
    -- max_payout, which is only a declaration, this one is checked
    -- against settlements -- a payout below the declared floor means the
    -- declaration was wrong and scoring raises.
    min_payout          REAL NOT NULL DEFAULT 0.0,
    spread_at_call      REAL,
    volume_at_call      REAL,
    model_prob          REAL,
    edge_pts_gross      REAL,
    fee_pts             REAL,
    screen_edge_pts_net REAL NOT NULL,
    edge_pts_net        REAL NOT NULL,
    edge_basis          TEXT NOT NULL DEFAULT 'prior'
                        CHECK (edge_basis IN ('measured','prior','model')),
    disposition         TEXT NOT NULL DEFAULT 'screened'
                        CHECK (disposition IN ('screened','endorsed','rejected')),
    interpretation      TEXT,
    interpreted_at      TEXT,
    confidence          TEXT,
    judged_blind        INTEGER,
    rationale           TEXT,
    suggested_size      REAL,
    evidence_source     TEXT,
    evidence_market_id  TEXT,
    user_action         TEXT NOT NULL DEFAULT 'untouched'
                        CHECK (user_action IN ('untouched','taken','skipped')),
    user_size           REAL,
    user_reason         TEXT,
    first_seen_at       TEXT NOT NULL,
    last_seen_at        TEXT NOT NULL,
    times_seen          INTEGER NOT NULL DEFAULT 1,
    extra_json          TEXT,
    UNIQUE (theory_id, theory_version, run_mode, lane, kalshi_ticker, outcome)
);

CREATE INDEX IF NOT EXISTS idx_opportunities_theory
    ON opportunities (theory_id, theory_version, run_mode, disposition);

CREATE INDEX IF NOT EXISTS idx_opportunities_ticker
    ON opportunities (kalshi_ticker);

CREATE TABLE IF NOT EXISTS opportunity_legs (
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id)
                   ON DELETE CASCADE,
    leg_index      INTEGER NOT NULL,
    kalshi_ticker  TEXT NOT NULL,
    outcome        TEXT NOT NULL,
    entry_price    REAL NOT NULL,
    spread_at_call REAL,
    volume_at_call REAL,
    PRIMARY KEY (opportunity_id, leg_index)
);

CREATE INDEX IF NOT EXISTS idx_opportunity_legs_ticker
    ON opportunity_legs (kalshi_ticker);

-- Every time a theory proposed a position. The position row is a rollup --
-- current identity, first-sighting anchors, a cached best view -- and the
-- attempt is the record: full parity with every argument
-- ledger.record_opportunity accepts that is not part of the position's
-- identity (theory_id, theory_version, run_mode, kalshi_ticker, outcome,
-- run_id, decision_date, now). A merge may overwrite the rollup; it may
-- never lose an attempt's value (attempt-fidelity spec, 2026-08-27).
--
-- Day granularity is deliberate: two recordings of one decision an hour
-- apart collapse to one attempt, which is the unit the persistence signal
-- is wanted in. decision_date is the day the theory was DECIDING about,
-- never the day the code ran -- a backtest replaying sixty days in one
-- session must stamp sixty different decision_dates or the primary key
-- collapses them into one row.
--
-- extra_json is each theory's escape hatch: a theory can add a feature
-- without the ledger needing to know about it, and without that feature
-- being lost on the next merge.
CREATE TABLE IF NOT EXISTS opportunity_attempts (
    opportunity_id     INTEGER NOT NULL REFERENCES opportunities(id)
                       ON DELETE CASCADE,
    decision_date      TEXT NOT NULL,
    run_id             TEXT NOT NULL,
    recorded_at        TEXT NOT NULL,
    scan_id            TEXT,
    entry_price        REAL NOT NULL,
    spread_at_call     REAL,
    volume_at_call     REAL,
    model_prob         REAL,
    edge_pts_gross     REAL,
    fee_pts            REAL,
    edge_pts_net       REAL NOT NULL,
    edge_basis         TEXT NOT NULL DEFAULT 'prior'
                       CHECK (edge_basis IN ('measured','prior','model')),
    disposition        TEXT NOT NULL DEFAULT 'screened'
                       CHECK (disposition IN ('screened','endorsed','rejected')),
    confidence         TEXT,
    judged_blind       INTEGER,
    rationale          TEXT,
    suggested_size     REAL,
    evidence_source    TEXT,
    evidence_market_id TEXT,
    extra_json         TEXT,
    PRIMARY KEY (opportunity_id, decision_date, run_id)
);

CREATE INDEX IF NOT EXISTS idx_attempts_run
    ON opportunity_attempts(run_id);

-- Every time the user actually bought. The mirror of opportunity_attempts:
-- that table is what the theory proposed, this is what the user did. No
-- uniqueness on (opportunity_id, filled_on) -- two buys on one day at two
-- prices are two real fills, and collapsing them would lose money history.
CREATE TABLE IF NOT EXISTS opportunity_fills (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id)
                   ON DELETE CASCADE,
    filled_on      TEXT NOT NULL,
    size           REAL NOT NULL,
    price          REAL,
    reason         TEXT,
    recorded_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fills_opportunity
    ON opportunity_fills(opportunity_id);

CREATE TABLE IF NOT EXISTS settlements (
    kalshi_ticker TEXT PRIMARY KEY,
    resolved_at   TEXT,
    result        TEXT NOT NULL,
    settle_price  REAL
);

CREATE TABLE IF NOT EXISTS scores (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    theory_id          TEXT NOT NULL REFERENCES theories(id),
    theory_version     INTEGER NOT NULL,
    run_mode           TEXT NOT NULL,
    disposition        TEXT NOT NULL,
    backtest_tier      TEXT,
    window_start       TEXT,
    window_end         TEXT,
    n                  INTEGER NOT NULL,
    win_rate           REAL,
    price_implied_rate REAL,
    calibration_edge   REAL,
    calibration_edge_net REAL,
    mean_claimed_edge  REAL,
    realization        REAL,
    roi_all            REAL,
    roi_taken          REAL,
    riskless_n         INTEGER NOT NULL DEFAULT 0,
    riskless_roi       REAL,
    computed_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bucket_rates (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    theory_id         TEXT NOT NULL REFERENCES theories(id),
    theory_version    INTEGER NOT NULL,
    confidence        TEXT NOT NULL,
    n                 INTEGER NOT NULL,
    win_rate          REAL,
    mean_entry_price  REAL,
    -- Distinct settlement days behind the rate. NULL means unknown (rows
    -- that settled before resolved_at was recorded); tools/buckets.py
    -- fails closed on unknown rather than treating it as measured.
    n_days            INTEGER,
    computed_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id            TEXT PRIMARY KEY,
    theory_id         TEXT NOT NULL REFERENCES theories(id),
    theory_version    INTEGER NOT NULL,
    as_of_start       TEXT,
    as_of_end         TEXT,
    tier              TEXT CHECK (tier IN ('A','B','C')),
    uses_llm_judgment INTEGER,
    model_cutoff      TEXT,
    notes             TEXT,
    created_at        TEXT NOT NULL
);

-- Provenance for every LLM judgment in a theory's decision path.
--
-- An edge you cannot reproduce is an anecdote. A theory that declares
-- uses_llm_judgment must record, per run and per stage, exactly which model
-- judged and exactly which prompt it was given -- otherwise the version
-- number promises a decision procedure that was never written down, and two
-- runs at the same version can silently be two different theories.
--
-- prompt_sha256 is required. Exactly one of prompt_path (a file in the repo,
-- so a change shows up in git diff) or prompt_text (inline capture) must be
-- present, so the prompt is always recoverable.
CREATE TABLE IF NOT EXISTS judgment_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT NOT NULL,
    theory_id      TEXT NOT NULL REFERENCES theories(id),
    theory_version INTEGER NOT NULL,
    -- 'construction' is judgment that established a durable theory_fact --
    -- a confirmed market pairing, an implication edge -- rather than a
    -- per-run verdict. A theory whose only model ran at construction time
    -- has no model in its per-trade decision path and still backtests at
    -- tier A, but the judgment that built its fact store must stay
    -- recoverable, so it is recorded here and pointed at by
    -- theory_facts.provenance_id.
    stage          TEXT NOT NULL
                   CHECK (stage IN ('gate','analysis','final_review',
                                    'construction','other')),
    model          TEXT NOT NULL,
    effort         TEXT,
    prompt_path    TEXT,
    prompt_sha256  TEXT NOT NULL,
    prompt_text    TEXT,
    web_search     INTEGER,
    n_items        INTEGER,
    notes          TEXT,
    created_at     TEXT NOT NULL,
    CHECK (prompt_path IS NOT NULL OR prompt_text IS NOT NULL),
    UNIQUE (run_id, theory_id, theory_version, stage, model, prompt_sha256)
);

CREATE INDEX IF NOT EXISTS idx_judgment_runs_run
    ON judgment_runs (theory_id, theory_version, run_id);

-- Registered sub-population slices -- subset edges with their own
-- credibility (tools/slices.py; spec docs/superpowers/specs/
-- 2026-08-29-theory-slices-design.md).
--
-- A slice is a HYPOTHESIS that a mechanical subset of one theory's
-- output carries a different edge than the aggregate. Its predicate is
-- data over recorded ledger fields, never judgment. A slice is
-- IMMUTABLE once registered -- editing a predicate would silently merge
-- two hypotheses into one track record, the same merge theory
-- versioning forbids -- so a change is a new slug plus retirement of
-- the old one, and retiring is a governance call like retiring a
-- theory. Registering a slice never bumps the theory version: it
-- changes which evidence row the RANKING layer reads, not the theory's
-- decision procedure.
--
-- oos_run_ids (JSON array) are the runs designated out-of-sample AT
-- registration; the argument for why lives in `origin`, alongside the
-- citation for any registered_at earlier than the row's created_at.
-- Everything else matching the predicate counts as in-sample unless its
-- decision date postdates registration -- see tools/slices.py.
CREATE TABLE IF NOT EXISTS theory_slices (
    theory_id      TEXT NOT NULL REFERENCES theories(id),
    slug           TEXT NOT NULL,
    predicate_json TEXT NOT NULL,
    hypothesis     TEXT NOT NULL,
    origin         TEXT NOT NULL,
    registered_at  TEXT NOT NULL,
    oos_run_ids    TEXT,
    priority       INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'registered'
                   CHECK (status IN ('registered','retired')),
    retired_at     TEXT,
    retired_reason TEXT,
    created_at     TEXT NOT NULL,
    PRIMARY KEY (theory_id, slug)
);

-- Durable per-theory facts: confirmed market pairings, implication edges,
-- per-wallet scores -- things a theory establishes once and reuses on
-- every run. One shared table rather than five theories inventing five
-- schemas.
--
-- FACTS ARE DATA, NOT PROCEDURE. Adding a confirmed pair does NOT bump the
-- theory's version; changing how facts are *derived* (the matching prompt,
-- the confirmation threshold, the scoring formula) does. Versioning
-- protects the decision procedure, not the evidence it has accumulated --
-- without that rule written down, a pair store orphans its own track
-- record every time a pair is added.
--
-- provenance_id records the construction-stage judgment that established a
-- model-proposed fact, keyed to the fact rather than to a run.
CREATE TABLE IF NOT EXISTS theory_facts (
    theory_id      TEXT NOT NULL REFERENCES theories(id),
    kind           TEXT NOT NULL,      -- 'market_pair', 'implication', ...
    key            TEXT NOT NULL,
    value_json     TEXT NOT NULL,
    evidence_json  TEXT,
    established_at TEXT NOT NULL,
    provenance_id  INTEGER REFERENCES judgment_runs(id),
    PRIMARY KEY (theory_id, kind, key)
);
