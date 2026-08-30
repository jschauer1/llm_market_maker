-- Snapshot store schema. Lives in its own database file, ATTACHed as
-- snapdb by tools/db.connect() (spec 5.2 phase 4), so the
-- precious-and-small ledger and the large history can have different
-- backup cadences.

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
    event_json       TEXT,
    -- Validity interval close (dedup-on-write, spec 5.2 phase 2): the last
    -- pull at which this exact payload was observed. A row covers
    -- [captured_at, last_seen_at]. Backfilled = captured_at for rows
    -- written before dedup existed.
    last_seen_at     TEXT
);

-- One row per market per capture. `captured_at` has one-second resolution
-- and is the batch key a whole pull shares, so without this two saves inside
-- the same second silently merge into one batch with every market duplicated
-- -- a board that rebuilds to twice its size and still looks complete.
-- Doubles as the lookup index; the columns are the ones queries use anyway.
CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_unique
    ON market_snapshots (platform, market_id, captured_at);
