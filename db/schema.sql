-- Market Edge Finder schema.
-- All timestamps are UTC ISO-8601 TEXT. All prices are decimal dollars in [0,1].
-- All edge values are in percentage points.

CREATE TABLE IF NOT EXISTS theories (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    status      TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed','active','paused','retired')),
    path        TEXT NOT NULL,
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
    raw_json         TEXT
);

CREATE INDEX IF NOT EXISTS idx_snapshots_market
    ON market_snapshots (platform, market_id, captured_at);

CREATE TABLE IF NOT EXISTS opportunities (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    theory_id           TEXT NOT NULL REFERENCES theories(id),
    theory_version      INTEGER NOT NULL,
    run_mode            TEXT NOT NULL CHECK (run_mode IN ('live','backtest')),
    run_id              TEXT NOT NULL,
    scan_id             TEXT,
    kalshi_ticker       TEXT NOT NULL,
    outcome             TEXT NOT NULL,
    entry_price         REAL NOT NULL,
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
    UNIQUE (theory_id, theory_version, run_id, kalshi_ticker, outcome)
);

CREATE INDEX IF NOT EXISTS idx_opportunities_theory
    ON opportunities (theory_id, theory_version, run_mode, disposition);

CREATE INDEX IF NOT EXISTS idx_opportunities_ticker
    ON opportunities (kalshi_ticker);

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
