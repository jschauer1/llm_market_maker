# Position Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `opportunities` hold one position per theory version per market, with every re-proposal recorded as an attempt and every user fill recorded separately, so a duplicate recording can no longer move a theory's score.

**Architecture:** `run_id` leaves the UNIQUE key and becomes an attribute; a stored `lane` column replaces it for experiment quarantine. Two child tables hang off `opportunities` in the shape `opportunity_legs` already uses: `opportunity_attempts` (every time the theory proposed it, carrying the judgment fields so a merge coalesces rather than overwrites) and `opportunity_fills` (every time the user acted on it). A one-shot CLI migration collapses the existing 9,153 rows to ~7,467.

**Tech Stack:** Python 3.11, stdlib `sqlite3` (3.42), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-27-position-identity-design.md`

## Global Constraints

- **`theory_id` and `theory_version` stay in the UNIQUE key.** Two theories proposing one ticker are two forecasts and both get graded. Never dedupe across theories.
- New UNIQUE key, used verbatim everywhere: `(theory_id, theory_version, run_mode, lane, kalshi_ticker, outcome)`.
- `lane` = the full `run_id` when it starts with `exp/`, else `'main'`.
- Prices are decimal dollars in [0, 1]. Timestamps are UTC ISO-8601 with a trailing `Z`. Decision dates and fill dates are `'YYYY-MM-DD'`.
- Ordering for "earliest" and "latest" attempt is always `(decision_date, recorded_at)`. "Latest attempt carrying a judgment" means the last in that order with `confidence IS NOT NULL`; if none, the earliest attempt's values stand.
- No theory version bumps. This changes how the ledger counts, not any theory's decision procedure.
- Run the full suite at every commit: `python -m pytest -q`. It was green before this work started.

**Deviation from the spec, deliberate:** the spec writes the migration command as `db migrate-positions`. `tools/cli.py` has no `db` subcommand group — `init` sits at top level (line 237). The command is therefore **`python -m tools.cli migrate-positions`**, registered alongside `init`.

**Ordering note:** `db/market_edge.db` keeps the old key until Task 9. Between Task 3 and Task 9 the code expects the new key and the real database does not have it, so **do not run live scans or theory backtests against the real DB during implementation.** Tests use fresh temp databases and are unaffected.

---

### Task 1: Schema — `lane`, the new key, and the two child tables

**Files:**
- Modify: `db/schema.sql` (the `opportunities` table, lines 78–124)
- Modify: `tools/db.py:58` (`init_db`)
- Modify: `tools/ledger.py:42` (add `lane_for`)
- Test: `tests/test_position_identity_schema.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `ledger.lane_for(run_id: str | None) -> str`; tables `opportunity_attempts`, `opportunity_fills`; column `opportunities.lane`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_position_identity_schema.py`:

```python
"""Schema for position identity: the lane column and the two child tables."""

import pytest

from tools import db, ledger


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_opportunities_has_a_lane_column(conn):
    assert "lane" in _columns(conn, "opportunities")


def test_the_unique_key_no_longer_contains_run_id(conn):
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'opportunities'"
    ).fetchone()[0]
    assert "UNIQUE (theory_id, theory_version, run_mode, lane, " \
           "kalshi_ticker, outcome)" in " ".join(sql.split())


def test_the_attempt_table_exists_with_its_key(conn):
    assert _columns(conn, "opportunity_attempts") == {
        "opportunity_id", "decision_date", "run_id", "recorded_at",
        "entry_price", "edge_pts_net", "disposition", "confidence",
        "judged_blind",
    }


def test_the_fill_table_exists_with_its_key(conn):
    assert _columns(conn, "opportunity_fills") == {
        "id", "opportunity_id", "filled_on", "size", "price", "reason",
        "recorded_at",
    }


def test_a_live_run_is_the_main_lane(conn):
    assert ledger.lane_for("live-2026-08-26") == "main"
    assert ledger.lane_for(None) == "main"


def test_an_experiment_run_is_its_own_lane(conn):
    assert ledger.lane_for("exp/variant-a") == "exp/variant-a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_position_identity_schema.py -q`
Expected: FAIL — `lane` missing, no `opportunity_attempts` table, `ledger` has no `lane_for`.

- [ ] **Step 3: Add `lane` and the new UNIQUE to `db/schema.sql`**

In the `opportunities` table, add the column immediately after `run_id`:

```sql
    run_id              TEXT NOT NULL,
    -- Which track record this position belongs to. 'main' for the real
    -- record; the full run id for an experiment, so a variant being tried
    -- never merges into the record it is meant to be measured against.
    lane                TEXT NOT NULL DEFAULT 'main',
```

Replace the final constraint line:

```sql
    UNIQUE (theory_id, theory_version, run_mode, lane, kalshi_ticker, outcome)
```

- [ ] **Step 4: Add the two child tables to `db/schema.sql`**

Append after the `opportunity_legs` table:

```sql
-- Every time a theory proposed a position. The position row is the
-- identity; this is the evidence that it kept being proposed. Day
-- granularity is deliberate: two recordings of one decision an hour apart
-- collapse to one attempt, which is the unit the persistence signal is
-- wanted in. The judgment fields live here so that merging two runs that
-- saw one market coalesces their judgments instead of one overwriting the
-- other.
CREATE TABLE IF NOT EXISTS opportunity_attempts (
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id)
                   ON DELETE CASCADE,
    decision_date  TEXT NOT NULL,
    run_id         TEXT NOT NULL,
    recorded_at    TEXT NOT NULL,
    entry_price    REAL NOT NULL,
    edge_pts_net   REAL NOT NULL,
    disposition    TEXT NOT NULL DEFAULT 'screened'
                   CHECK (disposition IN ('screened','endorsed','rejected')),
    confidence     TEXT,
    judged_blind   INTEGER,
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
```

- [ ] **Step 5: Make `init_db` add `lane` to existing databases**

In `tools/db.py`, in `init_db`, alongside the other `_add_column_if_missing` calls:

```python
    # Additive. The UNIQUE key that uses this column cannot be changed in
    # place -- `migrate_positions` rebuilds the table for that -- but the
    # column has to exist first so the migration can populate it.
    _add_column_if_missing(
        conn, "opportunities", "lane", "TEXT NOT NULL DEFAULT 'main'"
    )
```

- [ ] **Step 6: Add `lane_for` to `tools/ledger.py`**

After the `EXPERIMENT_RUN_PREFIX` constant:

```python
def lane_for(run_id: str | None) -> str:
    """Which track record a run's rows belong to.

    Experiments are quarantined by run id, so a variant being tried never
    merges into the record it is meant to be measured against. Everything
    else shares the 'main' lane, which is what makes a position one row
    across all of a theory version's real runs.
    """
    resolved = run_id or LIVE_RUN_ID
    if resolved.startswith(EXPERIMENT_RUN_PREFIX):
        return resolved
    return "main"
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_position_identity_schema.py -q`
Expected: 6 passed.

- [ ] **Step 8: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass. Existing tests build fresh databases, which now get the new key; nothing yet writes to it under the old one.

- [ ] **Step 9: Commit**

```bash
git add db/schema.sql tools/db.py tools/ledger.py tests/test_position_identity_schema.py
git commit -m "schema: lane column, position-scoped unique key, attempts and fills tables"
```

---

### Task 2: `record_opportunity` writes attempts under the new key

**Files:**
- Modify: `tools/ledger.py:129-296` (`record_opportunity`)
- Test: `tests/test_position_dedup.py` (exists, currently failing by design)

**Interfaces:**
- Consumes: `ledger.lane_for` from Task 1.
- Produces: `record_opportunity(..., decision_date: str | None = None) -> tuple[int, bool]`; `ledger.attempts(conn, opportunity_id) -> list[sqlite3.Row]`; `ledger.attempt_dates(conn, opportunity_id) -> list[str]`.

- [ ] **Step 1: Run the existing failing tests to see the starting point**

Run: `python -m pytest tests/test_position_dedup.py -q`
Expected: FAIL — `record_opportunity() got an unexpected keyword argument 'decision_date'`.

- [ ] **Step 2: Add the `decision_date` parameter and lane computation**

In `record_opportunity`'s signature, after `extra_json`:

```python
    extra_json: str | None = None,
    decision_date: str | None = None,
    now: str | None = None,
```

After the existing `resolved_run_id` / `stamp` lines:

```python
    resolved_run_id = run_id or LIVE_RUN_ID
    stamp = now or utcnow()
    lane = lane_for(resolved_run_id)
    # The as-of day of the decision, not the wall-clock recording time.
    # Two runs an hour apart replaying the same day are one decision.
    day = decision_date or stamp[:10]
```

- [ ] **Step 3: Replace the single ON CONFLICT statement with insert-then-update**

Replace the whole `with write(conn): conn.execute("""INSERT INTO opportunities ... """)` block and the trailing `SELECT id, times_seen` with:

```python
    with write(conn):
        # INSERT ... DO NOTHING RETURNING is an atomic creation test: no
        # SELECT-then-INSERT window for a concurrent writer to slip through,
        # and an unambiguous answer to "was this the first sighting" that
        # does not depend on reading a counter back.
        created = conn.execute(
            """
            INSERT INTO opportunities (
                theory_id, theory_version, run_mode, run_id, lane, scan_id,
                kalshi_ticker, outcome, entry_price, spread_at_call,
                volume_at_call, model_prob, edge_pts_gross, fee_pts,
                screen_edge_pts_net, edge_pts_net, edge_basis, disposition,
                confidence, judged_blind,
                rationale, suggested_size, evidence_source,
                evidence_market_id,
                user_action, first_seen_at, last_seen_at, times_seen,
                extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      'screened', ?, ?, ?, ?, ?, ?, 'untouched', ?, ?, 1, ?)
            ON CONFLICT (theory_id, theory_version, run_mode, lane,
                         kalshi_ticker, outcome) DO NOTHING
            RETURNING id
            """,
            (
                theory_id, theory_version, run_mode, resolved_run_id, lane,
                scan_id, kalshi_ticker, outcome, entry_price, spread_at_call,
                volume_at_call, model_prob, edge_pts_gross, fee_pts,
                edge_pts_net, edge_pts_net, edge_basis, confidence,
                1 if judged_blind else (0 if judged_blind is not None else None),
                rationale, suggested_size, evidence_source,
                evidence_market_id, stamp, stamp, extra_json,
            ),
        ).fetchone()

        if created is not None:
            opportunity_id = created["id"]
        else:
            # A re-sighting. entry_price, first_seen_at, run_id and
            # screen_edge_pts_net are deliberately absent from this UPDATE:
            # they record the first sighting and must not drift.
            conn.execute(
                """
                UPDATE opportunities SET
                    last_seen_at = ?,
                    edge_pts_net = CASE
                        WHEN interpreted_at IS NULL THEN ?
                        ELSE edge_pts_net
                    END,
                    model_prob = COALESCE(?, model_prob),
                    edge_pts_gross = COALESCE(?, edge_pts_gross),
                    fee_pts = COALESCE(?, fee_pts),
                    spread_at_call = COALESCE(?, spread_at_call),
                    volume_at_call = COALESCE(?, volume_at_call),
                    confidence = COALESCE(?, confidence),
                    rationale = COALESCE(?, rationale),
                    suggested_size = COALESCE(?, suggested_size)
                WHERE theory_id = ? AND theory_version = ? AND run_mode = ?
                  AND lane = ? AND kalshi_ticker = ? AND outcome = ?
                """,
                (
                    stamp, edge_pts_net, model_prob, edge_pts_gross, fee_pts,
                    spread_at_call, volume_at_call, confidence, rationale,
                    suggested_size,
                    theory_id, theory_version, run_mode, lane,
                    kalshi_ticker, outcome,
                ),
            )
            opportunity_id = conn.execute(
                """
                SELECT id FROM opportunities
                WHERE theory_id = ? AND theory_version = ? AND run_mode = ?
                  AND lane = ? AND kalshi_ticker = ? AND outcome = ?
                """,
                (theory_id, theory_version, run_mode, lane, kalshi_ticker,
                 outcome),
            ).fetchone()["id"]

        _record_attempt(
            conn, opportunity_id, day, resolved_run_id, stamp, entry_price,
            edge_pts_net, confidence, judged_blind,
        )

    return opportunity_id, created is not None
```

- [ ] **Step 4: Add the attempt writer and the two readers**

Add above `record_opportunity`:

```python
def _record_attempt(
    conn: sqlite3.Connection,
    opportunity_id: int,
    decision_date: str,
    run_id: str,
    recorded_at: str,
    entry_price: float,
    edge_pts_net: float,
    confidence: str | None,
    judged_blind: bool | None,
) -> None:
    """Record one proposal of a position, and refresh its attempt count.

    Called inside the caller's `write` block. Re-recording the same decision
    in the same run updates that attempt rather than adding one, which is
    what makes two recordings an hour apart count once.
    """
    conn.execute(
        """
        INSERT INTO opportunity_attempts (
            opportunity_id, decision_date, run_id, recorded_at,
            entry_price, edge_pts_net, disposition, confidence, judged_blind
        ) VALUES (?, ?, ?, ?, ?, ?, 'screened', ?, ?)
        ON CONFLICT (opportunity_id, decision_date, run_id) DO UPDATE SET
            recorded_at = excluded.recorded_at,
            entry_price = excluded.entry_price,
            edge_pts_net = excluded.edge_pts_net,
            confidence = COALESCE(excluded.confidence,
                                  opportunity_attempts.confidence),
            judged_blind = COALESCE(excluded.judged_blind,
                                    opportunity_attempts.judged_blind)
        """,
        (
            opportunity_id, decision_date, run_id, recorded_at, entry_price,
            edge_pts_net, confidence,
            1 if judged_blind else (0 if judged_blind is not None else None),
        ),
    )
    # times_seen counts distinct attempts, never recordings -- the whole
    # point of the attempt table is that repetition is counted once per
    # decision.
    conn.execute(
        """
        UPDATE opportunities SET times_seen =
            (SELECT COUNT(*) FROM opportunity_attempts
             WHERE opportunity_id = ?)
        WHERE id = ?
        """,
        (opportunity_id, opportunity_id),
    )


def attempts(
    conn: sqlite3.Connection, opportunity_id: int
) -> list[sqlite3.Row]:
    """Every recorded proposal of a position, oldest first."""
    return conn.execute(
        """
        SELECT * FROM opportunity_attempts WHERE opportunity_id = ?
        ORDER BY decision_date, recorded_at
        """,
        (opportunity_id,),
    ).fetchall()


def attempt_dates(conn: sqlite3.Connection, opportunity_id: int) -> list[str]:
    """The distinct days a position was proposed, oldest first.

    Derived rather than stored: `len(attempt_dates(...))` is the persistence
    signal, and keeping it beside the attempt table would be two places
    holding overlapping truth.
    """
    return [
        row["decision_date"]
        for row in conn.execute(
            """
            SELECT DISTINCT decision_date FROM opportunity_attempts
            WHERE opportunity_id = ? ORDER BY decision_date
            """,
            (opportunity_id,),
        ).fetchall()
    ]
```

- [ ] **Step 5: Run the dedup tests**

Run: `python -m pytest tests/test_position_dedup.py -q`
Expected: the identity, lane, attempt-list and first-sighting tests pass. The four score tests (`test_a_duplicate_recording_does_not_change_the_score`, `test_a_repeated_winner_cannot_book_two_wins`, `test_score_reports_how_many_attempts_backed_it`, `test_a_position_is_in_every_run_that_proposed_it`) still fail — `n_attempts` and attempt-aware `--run-id` land in Task 4.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: pass except the four noted above. If any *other* test fails, stop and report it — the likely cause is a caller depending on `was_created` meaning "first sighting in this run".

- [ ] **Step 7: Commit**

```bash
git add tools/ledger.py
git commit -m "ledger: record_opportunity keys on position, writes an attempt per proposal"
```

---

### Task 3: `record_basket` gets the same treatment

**Files:**
- Modify: `tools/ledger.py:381-570` (`record_basket`)
- Test: `tests/test_basket_dedup.py` (create)

**Interfaces:**
- Consumes: `_record_attempt`, `lane_for` from Task 2.
- Produces: `record_basket(..., decision_date: str | None = None) -> tuple[int, bool]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_basket_dedup.py`:

```python
"""A basket seen by two runs is one position, and keeps its legs."""

import pytest

from tools import db, ledger, theories

TS = "2026-08-26T12:00:00Z"
TS2 = "2026-08-27T12:00:00Z"

LEGS = [
    {"kalshi_ticker": "KXA-T1", "outcome": "yes", "entry_price": 0.40},
    {"kalshi_ticker": "KXA-T2", "outcome": "no", "entry_price": 0.50},
]


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _basket(conn, run_id, now=TS, decision_date=None):
    return ledger.record_basket(
        conn, theory_id="t1", theory_version=1, legs=LEGS,
        edge_pts_net=5.0, run_id=run_id, now=now,
        decision_date=decision_date,
    )


def test_two_runs_seeing_one_basket_make_one_position(conn):
    a, made_a = _basket(conn, "live-2026-08-26")
    b, made_b = _basket(conn, "live-2026-08-26-eve")
    assert a == b
    assert made_a is True and made_b is False
    rows = conn.execute("SELECT * FROM opportunities").fetchall()
    assert len(rows) == 1


def test_the_merged_basket_keeps_exactly_one_set_of_legs(conn):
    opp, _ = _basket(conn, "live-2026-08-26")
    _basket(conn, "live-2026-08-26-eve")
    legs = ledger.get_legs(conn, opp)
    assert [leg["kalshi_ticker"] for leg in legs] == ["KXA-T1", "KXA-T2"]
    orphans = conn.execute(
        """
        SELECT COUNT(*) FROM opportunity_legs
        WHERE opportunity_id NOT IN (SELECT id FROM opportunities)
        """
    ).fetchone()[0]
    assert orphans == 0


def test_a_basket_records_an_attempt_per_decision_day(conn):
    opp, _ = _basket(conn, "r1", now=TS, decision_date="2026-08-26")
    _basket(conn, "r2", now=TS2, decision_date="2026-08-27")
    assert ledger.attempt_dates(conn, opp) == ["2026-08-26", "2026-08-27"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_basket_dedup.py -q`
Expected: FAIL — `record_basket() got an unexpected keyword argument 'decision_date'`.

- [ ] **Step 3: Apply the same changes to `record_basket`**

Add to the signature after `extra_json`:

```python
    extra_json: str | None = None,
    decision_date: str | None = None,
    now: str | None = None,
```

After the existing `resolved_run_id` / `stamp` lines:

```python
    resolved_run_id = run_id or LIVE_RUN_ID
    stamp = now or utcnow()
    lane = lane_for(resolved_run_id)
    day = decision_date or stamp[:10]
```

Add `lane` to the INSERT column list (after `run_id`), add one `?` to the VALUES tuple in the matching position, add `lane` to the parameter tuple after `resolved_run_id`, and change the conflict clause and the read-back exactly as in Task 2 — `ON CONFLICT (theory_id, theory_version, run_mode, lane, kalshi_ticker, outcome) DO NOTHING RETURNING id`, with the re-sighting UPDATE keyed on `... AND lane = ? AND kalshi_ticker = ? AND outcome = 'basket'`.

Then, after the `executemany` that writes the legs and still inside the `with write(conn):` block:

```python
        _record_attempt(
            conn, opportunity_id, day, resolved_run_id, stamp, cost,
            edge_pts_net, confidence, judged_blind,
        )

    return opportunity_id, created is not None
```

The basket's attempt `entry_price` is `cost` — the basket's total cost — which is what the header row's `entry_price` holds.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_basket_dedup.py -q`
Expected: 3 passed.

- [ ] **Step 5: Run the basket suite**

Run: `python -m pytest tests/test_baskets.py tests/test_basket_dedup.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/ledger.py tests/test_basket_dedup.py
git commit -m "ledger: record_basket keys on position and records attempts"
```

---

### Task 4: Scoring reads lanes and attempts

**Files:**
- Modify: `tools/score.py:108-131` (`_segment_filter`), `tools/score.py:132-180` (`_single_leg_observations`), `tools/score.py:181-...` (`_basket_observations`), `_aggregate`
- Test: `tests/test_position_dedup.py` (the four remaining failures)

**Interfaces:**
- Consumes: `opportunity_attempts` from Task 2.
- Produces: `compute_score(...)` result gains key `n_attempts: int`.

- [ ] **Step 1: Run the four remaining failing tests**

Run: `python -m pytest tests/test_position_dedup.py -q -k "score or run or attempts or winner"`
Expected: FAIL — `KeyError: 'n_attempts'` and wrong `n` for `--run-id`.

- [ ] **Step 2: Switch the experiment exclusion to `lane`**

In `_segment_filter`, replace the `else` branch:

```python
    if run_id is not None:
        # A position is in a run if any attempt named that run. The join in
        # the observation queries supplies the attempt; this only narrows.
        sql += " AND EXISTS (SELECT 1 FROM opportunity_attempts a" \
               " WHERE a.opportunity_id = o.id AND a.run_id = ?)"
        params.append(run_id)
    else:
        # Pooled scoring never sees experiments (OOP spec section 3.3a):
        # a variant being tried must not contaminate the record it will
        # be judged against. Keyed on the stored lane rather than on the
        # run_id prefix, because after a merge the surviving row's run_id
        # is whichever run saw it first.
        sql += " AND o.lane = 'main'"
    return sql, params
```

- [ ] **Step 3: Price a run-scoped observation at that run's attempt**

In `_single_leg_observations`, replace the query construction and execution. The `run_id` placeholder comes first because the `LEFT JOIN` appears before the `WHERE` clause `_segment_filter` built:

```python
    where, params = _segment_filter(
        theory_id, theory_version, run_mode, disposition, run_id
    )
    sql = (
        "SELECT o.outcome, o.user_action,"
        " COALESCE(a.entry_price, o.entry_price) AS entry_price,"
        " COALESCE(a.edge_pts_net, o.edge_pts_net) AS edge_pts_net,"
        " s.result FROM opportunities o"
        " JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker"
        " LEFT JOIN opportunity_attempts a"
        "   ON a.opportunity_id = o.id AND a.run_id = ?"
        + where
        + " AND o.position_kind = 'single'"
    )
    rows = conn.execute(sql, [run_id] + params).fetchall()
```

Then iterate `rows` instead of `conn.execute(sql, params).fetchall()`. When `run_id` is None the LEFT JOIN matches nothing, both `COALESCE`s fall through to the position row, and pooled scoring reads exactly what it reads today.

Apply the identical `LEFT JOIN` + `COALESCE` + `[run_id] + params` change to `_basket_observations`.

- [ ] **Step 4: Add `n_attempts` to the score dict**

In `_single_leg_observations` and `_basket_observations`, add to each observation dict:

```python
            "n_attempts": row["n_attempts"],
```

and add to both SELECT lists:

```python
        " (SELECT COUNT(*) FROM opportunity_attempts x"
        "  WHERE x.opportunity_id = o.id) AS n_attempts,"
```

In `_aggregate`, after `result` is built, add:

```python
    # How many proposals stand behind these positions. n counts positions,
    # because one settlement is one draw; this makes the collapse visible
    # instead of silent.
    result["n_attempts"] = sum(r.get("n_attempts", 1) for r in all_rows)
```

where `all_rows` is the concatenation of the riskless and non-riskless lists — capture it at the top of `_aggregate` as `all_rows = list(rows)` **before** the riskless split, so nothing is lost.

- [ ] **Step 5: Add `n_attempts` to the empty-result template**

`tools/score.py:46` holds the zero-observation defaults. Add:

```python
    "n_attempts": 0,
```

- [ ] **Step 5b: Switch `bucket_rates`' own experiment filter to `lane`**

`bucket_rates` builds its own WHERE clause and carries a second copy of the experiment exclusion at `tools/score.py:590-598`. It must change the same way, or a merged row whose surviving `run_id` no longer starts with `exp/` would leak an experiment's judgments into the measured bucket rates:

```python
    if run_id is not None:
        sql += (
            " AND EXISTS (SELECT 1 FROM opportunity_attempts a"
            " WHERE a.opportunity_id = o.id AND a.run_id = ?)"
        )
        params.append(run_id)
    else:
        # Pooled scoring never sees experiments (OOP spec section 3.3a):
        # a variant being tried must not contaminate the record it will
        # be judged against. Keyed on lane, not on the run_id prefix --
        # after a merge the surviving row's run_id is whichever run saw
        # the position first.
        sql += " AND o.lane = 'main'"
```

`bucket_rates` needs no attempt join for pricing: it counts positions and
reads `confidence` from the position's rollup, because one settlement is one
draw — the same rule calibration uses.

Add a test to `tests/test_position_dedup.py`:

```python
def test_bucket_rates_count_positions_not_recordings(conn):
    _rec(conn, ticker="A", price=0.50, run_id="r1")
    conn.execute(
        "UPDATE opportunities SET confidence = 'strong' WHERE kalshi_ticker = 'A'"
    )
    conn.commit()
    _settle(conn, "A", "yes")
    _rec(conn, ticker="A", price=0.50, run_id="r2")
    rates = score.bucket_rates(conn, "t1", 1)
    assert rates["strong"]["n"] == 1, "one settlement is one draw"
```

- [ ] **Step 6: Run the dedup tests**

Run: `python -m pytest tests/test_position_dedup.py -q`
Expected: 15 passed.

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass. **If `tests/test_score_characterization.py` fails, stop.** Print the failing assertion's expected and actual values and report them — that file pins numbers this work may legitimately change, and re-baselining it is a decision for the user, not a fix to apply.

- [ ] **Step 8: Commit**

```bash
git add tools/score.py
git commit -m "score: filter on lane, price run-scoped observations from attempts, report n_attempts"
```

---

### Task 5: Fills and theory attribution

**Files:**
- Modify: `tools/ledger.py:759-786` (`mark_user_action`)
- Modify: `tools/cli.py:142-147`, `tools/cli.py:347-353`
- Test: `tests/test_fills_and_attribution.py` (create)

**Interfaces:**
- Consumes: `opportunity_fills` from Task 1.
- Produces: `mark_user_action(conn, opportunity_id, action, size=None, reason=None, theory_id=None, price=None, filled_on=None, now=None) -> None`; `ledger.fills(conn, opportunity_id) -> list[sqlite3.Row]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_fills_and_attribution.py`:

```python
"""Taking a bet names its theory, and every fill is kept."""

import pytest

from tools import db, ledger, theories

TS = "2026-08-26T12:00:00Z"
TS2 = "2026-08-29T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    for slug in ("t1", "t2"):
        theories.register(c, slug, slug, f"theories/{slug}", now=TS)
    yield c
    c.close()


def _rec(conn, theory="t1", ticker="A", price=0.60):
    opp, _ = ledger.record_opportunity(
        conn, theory_id=theory, theory_version=1, kalshi_ticker=ticker,
        outcome="yes", entry_price=price, edge_pts_net=6.0, now=TS,
    )
    return opp


def test_taking_a_bet_requires_naming_the_theory(conn):
    opp = _rec(conn)
    with pytest.raises(ValueError, match="--theory"):
        ledger.mark_user_action(conn, opp, "taken", size=25)


def test_naming_the_wrong_theory_raises(conn):
    opp = _rec(conn, theory="t1")
    with pytest.raises(ValueError, match="t2"):
        ledger.mark_user_action(
            conn, opp, "taken", size=25, theory_id="t2"
        )


def test_skipping_does_not_require_a_theory(conn):
    opp = _rec(conn)
    ledger.mark_user_action(conn, opp, "skipped", reason="too thin")
    assert ledger.get_opportunity(conn, opp)["user_action"] == "skipped"


def test_a_second_theory_cannot_also_take_the_same_market(conn):
    a = _rec(conn, theory="t1")
    b = _rec(conn, theory="t2")
    ledger.mark_user_action(conn, a, "taken", size=25, theory_id="t1", now=TS)
    with pytest.raises(ValueError, match="already taken"):
        ledger.mark_user_action(
            conn, b, "taken", size=25, theory_id="t2", now=TS
        )


def test_two_fills_are_both_kept(conn):
    opp = _rec(conn)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, price=0.80, theory_id="t1", now=TS,
    )
    ledger.mark_user_action(
        conn, opp, "taken", size=10, price=0.90, theory_id="t1", now=TS2,
    )
    got = [(f["filled_on"], f["size"], f["price"])
           for f in ledger.fills(conn, opp)]
    assert got == [("2026-08-26", 25.0, 0.80), ("2026-08-29", 10.0, 0.90)]


def test_user_size_is_the_sum_of_fills(conn):
    opp = _rec(conn)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, theory_id="t1", now=TS,
    )
    ledger.mark_user_action(
        conn, opp, "taken", size=10, theory_id="t1", now=TS2,
    )
    row = ledger.get_opportunity(conn, opp)
    assert row["user_size"] == 35.0
    assert row["user_action"] == "taken"


def test_unmarking_clears_the_fills(conn):
    opp = _rec(conn)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, theory_id="t1", now=TS,
    )
    ledger.mark_user_action(conn, opp, "untouched")
    assert ledger.fills(conn, opp) == []
    row = ledger.get_opportunity(conn, opp)
    assert row["user_action"] == "untouched"
    assert row["user_size"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fills_and_attribution.py -q`
Expected: FAIL — `mark_user_action() got an unexpected keyword argument 'theory_id'`.

- [ ] **Step 3: Rewrite `mark_user_action`**

Replace the function body in `tools/ledger.py`:

```python
def mark_user_action(
    conn: sqlite3.Connection,
    opportunity_id: int,
    action: str,
    size: float | None = None,
    reason: str | None = None,
    *,
    theory_id: str | None = None,
    price: float | None = None,
    filled_on: str | None = None,
    now: str | None = None,
) -> None:
    """Record what the user actually did with a bet.

    Taking names the theory it is taken for. Two theories proposing one
    market are two forecasts and one bet: both stay graded on calibration,
    but only the named one books the money, so `roi_taken` counts a single
    purchase once.

    A take appends a fill rather than overwriting, so scaling into a
    position keeps both entries. `user_action` and `user_size` on the
    position are maintained rollups of the fills.

    The reason matters: divergence between what the system endorsed and what
    the user bet is usually an unencoded heuristic, and those get mined into
    new theory candidates.
    """
    if action not in VALID_USER_ACTIONS:
        raise ValueError(
            f"invalid action {action!r}; expected one of {VALID_USER_ACTIONS}"
        )
    row = get_opportunity(conn, opportunity_id)
    if row is None:
        raise KeyError(opportunity_id)

    stamp = now or utcnow()

    if action == "taken":
        if not theory_id:
            raise ValueError(
                "taking a bet must name the theory it is taken for: pass "
                "--theory. Two theories can propose one market, and only "
                "the named one books the money."
            )
        if theory_id != row["theory_id"]:
            raise ValueError(
                f"opportunity {opportunity_id} belongs to "
                f"{row['theory_id']!r}, not {theory_id!r}"
            )
        holder = conn.execute(
            """
            SELECT id, theory_id FROM opportunities
            WHERE kalshi_ticker = ? AND outcome = ? AND user_action = 'taken'
              AND id != ?
            """,
            (row["kalshi_ticker"], row["outcome"], opportunity_id),
        ).fetchone()
        if holder is not None:
            raise ValueError(
                f"{row['kalshi_ticker']} {row['outcome']} is already taken "
                f"under theory {holder['theory_id']!r} (opportunity "
                f"{holder['id']}). One real position, one theory credited — "
                f"unmark that one first if the attribution is wrong."
            )
        if size is None:
            raise ValueError("taking a bet requires --size")

    with write(conn):
        if action == "taken":
            conn.execute(
                """
                INSERT INTO opportunity_fills (
                    opportunity_id, filled_on, size, price, reason,
                    recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (opportunity_id, filled_on or stamp[:10], size, price,
                 reason, stamp),
            )
        else:
            # Skipping or unmarking retires the money record: a position the
            # user is no longer in has no fills.
            conn.execute(
                "DELETE FROM opportunity_fills WHERE opportunity_id = ?",
                (opportunity_id,),
            )
        conn.execute(
            """
            UPDATE opportunities SET
                user_action = ?,
                user_size = (SELECT SUM(size) FROM opportunity_fills
                             WHERE opportunity_id = ?),
                user_reason = COALESCE(?, user_reason)
            WHERE id = ?
            """,
            (action, opportunity_id, reason, opportunity_id),
        )


def fills(conn: sqlite3.Connection, opportunity_id: int) -> list[sqlite3.Row]:
    """Every recorded purchase of a position, oldest first."""
    return conn.execute(
        """
        SELECT * FROM opportunity_fills WHERE opportunity_id = ?
        ORDER BY filled_on, id
        """,
        (opportunity_id,),
    ).fetchall()
```

- [ ] **Step 4: Wire the CLI**

In `tools/cli.py`, extend the `mark-taken` parser (line 347):

```python
    mark.add_argument("id", type=int)
    mark.add_argument("value", choices=ledger.VALID_USER_ACTIONS)
    mark.add_argument("--size", type=float, default=None)
    mark.add_argument("--reason", default=None)
    mark.add_argument(
        "--theory", dest="mark_theory", default=None,
        help="theory this bet is taken for; required for 'taken'",
    )
    mark.add_argument(
        "--price", type=float, default=None,
        help="what you actually paid; defaults to the proposed ask",
    )
```

and the dispatch (line 142):

```python
        elif args.action == "mark-taken":
            ledger.mark_user_action(
                conn, args.id, args.value, size=args.size,
                reason=args.reason, theory_id=args.mark_theory,
                price=args.price,
            )
            _emit(dict(ledger.get_opportunity(conn, args.id)))
```

`--theory` uses `dest="mark_theory"` because the sibling `opportunities list` parser already defines a `--theory` with dest `theory`; a shared dest across sibling subparsers is confusing to read even where argparse tolerates it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_fills_and_attribution.py -q`
Expected: 7 passed.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass. `tests/test_cli.py` and `tests/test_ledger.py` both call `mark_user_action`; if either fails it is because a `taken` call there now needs `theory_id=` — add it, since that is the new contract, and mention it in the commit.

- [ ] **Step 7: Commit**

```bash
git add tools/ledger.py tools/cli.py tests/test_fills_and_attribution.py
git commit -m "ledger: taking a bet names its theory and appends a fill"
```

---

### Task 6: `roi_taken` uses actual fill prices

**Files:**
- Modify: `tools/score.py` (`_single_leg_observations`, `_basket_observations`, `_aggregate`)
- Test: `tests/test_fills_and_attribution.py` (extend)

**Interfaces:**
- Consumes: `opportunity_fills` from Task 5.
- Produces: no signature change; `roi_taken` semantics change.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_fills_and_attribution.py`:

```python
def test_roi_taken_uses_the_price_actually_paid(conn):
    from tools import score

    opp = _rec(conn, ticker="A", price=0.50)
    score.record_settlement(conn, "A", "yes", resolved_at=TS)
    # Proposed at 0.50, actually bought at 0.25. ROI must reflect the 0.25.
    ledger.mark_user_action(
        conn, opp, "taken", size=10, price=0.25, theory_id="t1", now=TS,
    )
    result = score.compute_score(conn, "t1", 1)
    # Won a dollar on a 0.25 entry: roughly +3.0 before fees, and in any
    # case far above the +1.0 a 0.50 entry would have produced.
    assert result["roi_taken"] > 2.0


def test_roi_taken_falls_back_to_the_proposed_ask(conn):
    from tools import score

    opp = _rec(conn, ticker="B", price=0.50)
    score.record_settlement(conn, "B", "yes", resolved_at=TS)
    ledger.mark_user_action(
        conn, opp, "taken", size=10, theory_id="t1", now=TS,
    )
    result = score.compute_score(conn, "t1", 1)
    assert 0.8 < result["roi_taken"] < 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fills_and_attribution.py -q -k roi_taken`
Expected: FAIL — the first test's `roi_taken` comes out near 0.9, because scoring uses the proposed ask.

- [ ] **Step 3: Carry the fill price into the observation**

In both `_single_leg_observations` and `_basket_observations`, add to the SELECT list:

```python
        " (SELECT SUM(f.size * COALESCE(f.price, o.entry_price))"
        "    / NULLIF(SUM(f.size), 0)"
        "  FROM opportunity_fills f"
        "  WHERE f.opportunity_id = o.id) AS fill_price,"
```

and to each observation dict:

```python
            "fill_price": row["fill_price"],
```

- [ ] **Step 4: Use it in `_aggregate`'s taken totals**

In `_aggregate`, both places that accumulate taken money currently read `r["cost"]`. Replace each with a fill-aware cost:

```python
        if r["user_action"] == "taken":
            has_taken = True
            # The money number uses what was actually paid. `cost` prices
            # the proposal; a fill prices the purchase. They differ whenever
            # the market moved between the call and the entry.
            paid = r.get("fill_price")
            taken_cost += (
                r["cost"] if paid is None
                else paid + fee_pts(paid) / 100.0
            )
            taken_return += r["payout"]
```

Apply the same substitution in the riskless accumulation block. `fee_pts` is already imported in `tools/score.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_fills_and_attribution.py -q`
Expected: 9 passed.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add tools/score.py tests/test_fills_and_attribution.py
git commit -m "score: roi_taken prices positions at what was actually paid"
```

---

### Task 7: The migration

**Files:**
- Modify: `tools/db.py` (add `migrate_positions`)
- Test: `tests/test_migrate_positions.py` (create)

**Interfaces:**
- Consumes: everything above.
- Produces: `db.migrate_positions(conn, dry_run: bool = False) -> dict` returning `{"before": int, "after": int, "attempts": int, "labels_preserved": int, "legs_repointed": int, "backup_table": str | None}`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_migrate_positions.py`:

```python
"""Collapsing the legacy ledger without losing a judgment or a leg.

The shape reproduced here is the one in the real database: a full-coverage
run that recorded no confidence, and a later judged run that recorded a
confidence bucket for a subset of the same markets. The plan's original
"earliest row survives" rule would have kept the NULL and deleted every
label; this pins the opposite.
"""

import pytest

from tools import db, ledger, theories

TS = "2026-08-25T12:00:00Z"
TS2 = "2026-08-26T12:00:00Z"

OLD_SCHEMA = """
CREATE TABLE opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theory_id TEXT NOT NULL, theory_version INTEGER NOT NULL,
    run_mode TEXT NOT NULL, run_id TEXT NOT NULL, scan_id TEXT,
    kalshi_ticker TEXT NOT NULL, outcome TEXT NOT NULL,
    entry_price REAL NOT NULL,
    position_kind TEXT NOT NULL DEFAULT 'single',
    leg_count INTEGER NOT NULL DEFAULT 1,
    max_payout REAL NOT NULL DEFAULT 1.0,
    min_payout REAL NOT NULL DEFAULT 0.0,
    spread_at_call REAL, volume_at_call REAL, model_prob REAL,
    edge_pts_gross REAL, fee_pts REAL,
    screen_edge_pts_net REAL NOT NULL, edge_pts_net REAL NOT NULL,
    edge_basis TEXT NOT NULL DEFAULT 'prior',
    disposition TEXT NOT NULL DEFAULT 'screened',
    interpretation TEXT, interpreted_at TEXT, confidence TEXT,
    judged_blind INTEGER, rationale TEXT, suggested_size REAL,
    evidence_source TEXT, evidence_market_id TEXT,
    user_action TEXT NOT NULL DEFAULT 'untouched',
    user_size REAL, user_reason TEXT,
    first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
    times_seen INTEGER NOT NULL DEFAULT 1, extra_json TEXT,
    UNIQUE (theory_id, theory_version, run_id, kalshi_ticker, outcome)
);
"""


def _legacy_row(conn, **kw):
    cols = {
        "theory_id": "t1", "theory_version": 3, "run_mode": "backtest",
        "scan_id": None, "outcome": "yes", "entry_price": 0.90,
        "screen_edge_pts_net": 2.0, "edge_pts_net": 2.0,
        "confidence": None, "first_seen_at": TS, "last_seen_at": TS,
        "extra_json": '{"entry_day_iso": "2026-08-20"}',
    }
    cols.update(kw)
    keys = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    conn.execute(
        f"INSERT INTO opportunities ({keys}) VALUES ({marks})",
        list(cols.values()),
    )
    conn.commit()


@pytest.fixture
def legacy(tmp_path):
    """A database in the pre-migration shape."""
    c = db.connect(tmp_path / "legacy.db")
    c.executescript(OLD_SCHEMA)
    c.execute(
        "CREATE TABLE opportunity_legs (opportunity_id INTEGER NOT NULL"
        " REFERENCES opportunities(id) ON DELETE CASCADE,"
        " leg_index INTEGER NOT NULL, kalshi_ticker TEXT NOT NULL,"
        " outcome TEXT NOT NULL, entry_price REAL NOT NULL,"
        " spread_at_call REAL, volume_at_call REAL,"
        " PRIMARY KEY (opportunity_id, leg_index))"
    )
    c.commit()
    yield c
    c.close()


def test_a_screened_and_a_judged_row_become_one_labelled_position(legacy):
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA",
                confidence=None)
    _legacy_row(legacy, run_id="judged-s200", kalshi_ticker="KXA",
                confidence="strong", last_seen_at=TS2)
    stats = db.migrate_positions(legacy)

    assert stats["before"] == 2 and stats["after"] == 1
    assert stats["labels_preserved"] == 1
    row = legacy.execute("SELECT * FROM opportunities").fetchone()
    assert row["confidence"] == "strong", "the judgment must survive"
    assert row["entry_price"] == 0.90
    assert row["times_seen"] == 2


def test_both_runs_survive_as_attempts(legacy):
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="judged-s200", kalshi_ticker="KXA",
                confidence="strong")
    db.migrate_positions(legacy)
    opp = legacy.execute("SELECT id FROM opportunities").fetchone()["id"]
    runs = [a["run_id"] for a in ledger.attempts(legacy, opp)]
    assert sorted(runs) == ["fullcov", "judged-s200"]


def test_experiments_do_not_merge_into_the_record(legacy):
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="exp/gated100", kalshi_ticker="KXA")
    db.migrate_positions(legacy)
    lanes = sorted(
        r["lane"] for r in legacy.execute("SELECT lane FROM opportunities")
    )
    assert lanes == ["exp/gated100", "main"]


def test_a_merged_basket_keeps_its_legs(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="BASKET:abc",
                outcome="basket", position_kind="basket", leg_count=2)
    _legacy_row(legacy, run_id="r2", kalshi_ticker="BASKET:abc",
                outcome="basket", position_kind="basket", leg_count=2)
    ids = [r["id"] for r in legacy.execute("SELECT id FROM opportunities")]
    for opp in ids:
        legacy.execute(
            "INSERT INTO opportunity_legs VALUES (?, 0, 'KXL1', 'yes',"
            " 0.4, NULL, NULL)", (opp,)
        )
    legacy.commit()

    db.migrate_positions(legacy)

    survivor = legacy.execute("SELECT id FROM opportunities").fetchone()["id"]
    legs = legacy.execute(
        "SELECT * FROM opportunity_legs WHERE opportunity_id = ?", (survivor,)
    ).fetchall()
    assert len(legs) == 1
    orphans = legacy.execute(
        "SELECT COUNT(*) FROM opportunity_legs WHERE opportunity_id"
        " NOT IN (SELECT id FROM opportunities)"
    ).fetchone()[0]
    assert orphans == 0


def test_two_theories_on_one_ticker_stay_two_positions(legacy):
    _legacy_row(legacy, theory_id="t1", run_id="r1", kalshi_ticker="KXA")
    _legacy_row(legacy, theory_id="t2", run_id="r1", kalshi_ticker="KXA")
    db.migrate_positions(legacy)
    assert legacy.execute(
        "SELECT COUNT(*) FROM opportunities"
    ).fetchone()[0] == 2


def test_a_backup_table_is_written(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA")
    stats = db.migrate_positions(legacy)
    kept = legacy.execute(
        f"SELECT COUNT(*) FROM {stats['backup_table']}"
    ).fetchone()[0]
    assert kept == 1


def test_dry_run_changes_nothing(legacy):
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="judged", kalshi_ticker="KXA",
                confidence="strong")
    stats = db.migrate_positions(legacy, dry_run=True)
    assert stats["before"] == 2 and stats["after"] == 1
    assert stats["backup_table"] is None
    assert legacy.execute(
        "SELECT COUNT(*) FROM opportunities"
    ).fetchone()[0] == 2, "dry run must not write"


def test_migrating_twice_is_a_no_op(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA")
    db.migrate_positions(legacy)
    again = db.migrate_positions(legacy)
    assert again["before"] == again["after"] == 1


def test_money_already_recorded_becomes_a_fill(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA",
                user_action="taken", user_size=25.0,
                user_reason="thin but mispriced", last_seen_at=TS2)
    stats = db.migrate_positions(legacy)
    assert stats["fills_backfilled"] == 1
    opp = legacy.execute("SELECT * FROM opportunities").fetchone()
    assert opp["user_action"] == "taken" and opp["user_size"] == 25.0
    fill = ledger.fills(legacy, opp["id"])[0]
    assert fill["size"] == 25.0
    assert fill["filled_on"] == "2026-08-26"
    assert fill["price"] is None, "the legacy schema recorded no fill price"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migrate_positions.py -q`
Expected: FAIL — `module 'tools.db' has no attribute 'migrate_positions'`.

- [ ] **Step 3: Implement `migrate_positions`**

Add to `tools/db.py`:

```python
def _decision_day(row: sqlite3.Row) -> str:
    """The as-of day of a legacy row's decision.

    `extra_json.entry_day_iso` is what the theory recorded as the day it was
    deciding about; `first_seen_at` is wall-clock recording time and is a
    fallback only. Using the recording time would split one decision
    recorded by two runs an hour apart into two attempts.
    """
    import json

    raw = row["extra_json"]
    if raw:
        try:
            day = json.loads(raw).get("entry_day_iso")
            if day:
                return str(day)[:10]
        except (ValueError, TypeError, AttributeError):
            pass
    return str(row["first_seen_at"])[:10]


def _rollup(group: list[sqlite3.Row]) -> tuple[sqlite3.Row, str | None, int]:
    """Pick the surviving row's values for one duplicate group.

    First sighting owns price and edge, so the pair can never be
    mismatched. The judgment comes from the latest attempt that carried
    one, which is what stops a merge from deleting a confidence label
    recorded by a later judged run.
    """
    ordered = sorted(group, key=lambda r: (_decision_day(r), r["last_seen_at"]))
    earliest = ordered[0]
    judged = [r for r in ordered if r["confidence"]]
    label = judged[-1]["confidence"] if judged else None
    return earliest, label, len(judged)


def has_legacy_position_key(conn: sqlite3.Connection) -> bool:
    """True if `opportunities` still carries run_id in its UNIQUE key."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='opportunities'"
    ).fetchone()
    if row is None:
        return False
    return "run_id, kalshi_ticker" in " ".join((row[0] or "").split())


def migrate_positions(
    conn: sqlite3.Connection, dry_run: bool = False
) -> dict:
    """Collapse run-scoped opportunity rows into positions with attempts.

    `opportunities` was keyed on run_id, so one bet re-recorded by a second
    run became two rows: pooled scoring counted it twice, and `times_seen`
    never incremented. This rebuilds the table under the position-scoped key
    and turns every duplicate row into an attempt.

    Deliberately not run from `init_db`. Unlike `_migrate_theories`, which
    carries every row over unchanged, this one deletes rows, and a
    row-collapsing migration that fires unattended on whatever database
    happens to be opened is the kind of thing you only get to be wrong about
    once.
    """
    stats = {
        "before": 0, "after": 0, "attempts": 0, "labels_preserved": 0,
        "legs_repointed": 0, "fills_backfilled": 0, "backup_table": None,
    }
    rows = conn.execute("SELECT * FROM opportunities").fetchall()
    stats["before"] = len(rows)

    groups: dict[tuple, list[sqlite3.Row]] = {}
    for row in rows:
        run_id = row["run_id"]
        lane = run_id if run_id.startswith("exp/") else "main"
        key = (
            row["theory_id"], row["theory_version"], row["run_mode"], lane,
            row["kalshi_ticker"], row["outcome"],
        )
        groups.setdefault(key, []).append(row)

    stats["after"] = len(groups)
    stats["attempts"] = sum(
        len({(_decision_day(r), r["run_id"]) for r in g})
        for g in groups.values()
    )
    stats["labels_preserved"] = sum(
        1 for g in groups.values() if any(r["confidence"] for r in g)
    )
    if dry_run:
        return stats

    stamp = utcnow().replace("-", "").replace(":", "").replace("Z", "")
    backup = f"opportunities_premigration_{stamp}"
    stats["backup_table"] = backup

    columns = [r[1] for r in conn.execute("PRAGMA table_info(opportunities)")]
    ddl = schema_statement("opportunities")
    attempts_ddl = schema_statement("opportunity_attempts")

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.execute("BEGIN")
        try:
            conn.execute(
                f"CREATE TABLE {backup} AS SELECT * FROM opportunities"
            )
            conn.execute(
                f"CREATE TABLE {backup}_legs AS SELECT * FROM opportunity_legs"
            )
            conn.execute("ALTER TABLE opportunities RENAME TO opportunities_legacy")
            conn.execute(ddl)
            conn.execute(attempts_ddl)

            # `lane` is appended explicitly rather than copied, so this
            # works whether or not the legacy table already had the column.
            shared = [c for c in columns if c not in ("id", "lane")]
            insert_cols = ", ".join(shared + ["lane"])
            marks = ", ".join("?" for _ in shared) + ", ?"

            for key, group in groups.items():
                lane = key[3]
                earliest, label, _ = _rollup(group)
                seen = {(_decision_day(r), r["run_id"]) for r in group}
                values = [earliest[c] for c in shared]
                # The judgment is the one field taken from a later row.
                values[shared.index("confidence")] = label
                values[shared.index("times_seen")] = len(seen)
                values[shared.index("last_seen_at")] = max(
                    r["last_seen_at"] for r in group
                )
                cur = conn.execute(
                    f"INSERT INTO opportunities ({insert_cols})"
                    f" VALUES ({marks})",
                    values + [lane],
                )
                new_id = cur.lastrowid

                # Money the user already recorded becomes a fill, so the
                # rollup on the surviving row stays true and roi_taken keeps
                # seeing it. Undated in the legacy schema -- there was no
                # take-date column -- so last_seen_at is the best available
                # stand-in.
                taken = [r for r in group if r["user_action"] == "taken"]
                if taken:
                    latest = max(taken, key=lambda r: r["last_seen_at"])
                    conn.execute(
                        """
                        INSERT INTO opportunity_fills (
                            opportunity_id, filled_on, size, price, reason,
                            recorded_at
                        ) VALUES (?, ?, ?, NULL, ?, ?)
                        """,
                        (
                            new_id, str(latest["last_seen_at"])[:10],
                            latest["user_size"], latest["user_reason"],
                            latest["last_seen_at"],
                        ),
                    )
                    stats["fills_backfilled"] += 1

                for row in group:
                    conn.execute(
                        """
                        INSERT INTO opportunity_attempts (
                            opportunity_id, decision_date, run_id,
                            recorded_at, entry_price, edge_pts_net,
                            disposition, confidence, judged_blind
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (opportunity_id, decision_date, run_id)
                        DO NOTHING
                        """,
                        (
                            new_id, _decision_day(row), row["run_id"],
                            row["last_seen_at"], row["entry_price"],
                            row["edge_pts_net"], row["disposition"],
                            row["confidence"], row["judged_blind"],
                        ),
                    )
                    # Legs are repointed BEFORE the legacy table goes.
                    # opportunity_legs is ON DELETE CASCADE, so dropping the
                    # losing row of a merged basket would silently eat its
                    # legs.
                    moved = conn.execute(
                        "UPDATE opportunity_legs SET opportunity_id = ?"
                        " WHERE opportunity_id = ?",
                        (new_id, row["id"]),
                    ).rowcount
                    stats["legs_repointed"] += moved

            # A merged basket's groups all wrote the same leg_index rows to
            # the survivor; keep one set.
            conn.execute(
                """
                DELETE FROM opportunity_legs WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM opportunity_legs
                    GROUP BY opportunity_id, leg_index
                )
                """
            )
            conn.execute("DROP TABLE opportunities_legacy")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    finally:
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.execute("PRAGMA foreign_keys = ON")

    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_migrate_positions.py -q`
Expected: 9 passed.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/db.py tests/test_migrate_positions.py
git commit -m "db: migrate_positions collapses run-scoped rows, keeping judgments and legs"
```

---

### Task 8: CLI command and the `init_db` guard

**Files:**
- Modify: `tools/cli.py:237` (register the command), plus a `_cmd_migrate_positions` handler
- Modify: `tools/db.py:58` (`init_db`)
- Test: `tests/test_migrate_positions.py` (extend)

**Interfaces:**
- Consumes: `db.migrate_positions`, `db.has_legacy_position_key` from Task 7.
- Produces: `python -m tools.cli migrate-positions [--dry-run]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_migrate_positions.py`:

```python
def test_init_db_refuses_a_legacy_database(legacy):
    with pytest.raises(RuntimeError, match="migrate-positions"):
        db.init_db(legacy)


def test_init_db_is_happy_once_migrated(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA")
    db.migrate_positions(legacy)
    db.init_db(legacy)  # must not raise


def test_the_cli_reports_the_collapse(legacy, tmp_path, capsys):
    from tools import cli

    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="judged", kalshi_ticker="KXA",
                confidence="strong")
    legacy.commit()
    legacy.close()

    rc = cli.main([
        "--db", str(tmp_path / "legacy.db"), "migrate-positions", "--dry-run",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"before": 2' in out and '"after": 1' in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migrate_positions.py -q -k "init_db or cli"`
Expected: FAIL — `init_db` does not raise; the CLI has no `migrate-positions`.

- [ ] **Step 3: Add the guard to `init_db`**

At the very top of `init_db`, before `_dedupe_snapshots`:

```python
    # A legacy ledger cannot simply be extended: its UNIQUE key still
    # contains run_id, so every write would land on the wrong identity and
    # the double-counting this migration exists to end would continue
    # silently. Fail loudly and name the fix.
    if has_legacy_position_key(conn):
        raise RuntimeError(
            "this database still keys opportunities on run_id, which "
            "double-counts a bet seen by two runs. Run "
            "`python -m tools.cli migrate-positions --dry-run` to see what "
            "would change, then drop --dry-run to apply it."
        )
```

- [ ] **Step 4: Register the CLI command**

In `tools/cli.py`, beside the `init` registration (line 237):

```python
    mp = sub.add_parser(
        "migrate-positions",
        help="collapse run-scoped opportunity rows into positions",
    )
    mp.add_argument(
        "--dry-run", dest="dry_run", action="store_true",
        help="report what would change without writing",
    )
    mp.set_defaults(func=_cmd_migrate_positions)
```

And the handler, beside the other `_cmd_*` functions:

```python
def _cmd_migrate_positions(args) -> int:
    # Deliberately not routed through `_connect`: that helper calls
    # `init_db` (tools/cli.py:29), and `init_db` refuses a legacy database
    # on purpose. This command is the thing that fixes it.
    conn = db.connect(args.db) if args.db else db.connect()
    try:
        _emit(db.migrate_positions(conn, dry_run=args.dry_run))
    finally:
        conn.close()
    return 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_migrate_positions.py -q`
Expected: 12 passed.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add tools/cli.py tools/db.py tests/test_migrate_positions.py
git commit -m "cli: migrate-positions command, and init_db refuses a legacy ledger"
```

---

### Task 9: Migrate the real database

**Files:**
- Modify: `db/market_edge.db` (data only)
- Create: `docs/superpowers/plans/2026-08-27-migration-report.md`

**Interfaces:**
- Consumes: the CLI from Task 8.
- Produces: a migrated `db/market_edge.db` and a report of what changed.

**This task writes to the user's real data. Do not batch it with others; stop and report after it.**

- [ ] **Step 1: Back up the database file**

```bash
cp db/market_edge.db "db/market_edge.db.bak-$(date +%Y%m%d%H%M%S)"
ls -la db/*.bak-*
```

- [ ] **Step 2: Capture the before picture**

```bash
python -m tools.cli score report insider_judgment --version 3 --run-mode backtest > /tmp/before-pooled.json
python -m tools.cli score report insider_judgment --version 3 --run-mode backtest \
    --run-id backtest-2026-08-25-insider-fullcov > /tmp/before-fullcov.json
cat /tmp/before-pooled.json /tmp/before-fullcov.json
```

Expected: pooled `n=4759`, `calibration_edge_net ≈ -0.588`; fullcov `n=3195`, `≈ -1.149`.

- [ ] **Step 3: Dry run**

```bash
python -m tools.cli migrate-positions --dry-run
```

Expected: `before: 9153`, `after: 7467`, `labels_preserved: 1564`, `fills_backfilled: 2`.
**If any of those three numbers differ, stop and report — do not apply.**

- [ ] **Step 4: Apply**

```bash
python -m tools.cli migrate-positions
```

- [ ] **Step 5: Verify nothing was lost**

```bash
python - <<'PY'
import sqlite3
c = sqlite3.connect("db/market_edge.db"); c.row_factory = sqlite3.Row
q = lambda s: c.execute(s).fetchall()
print("rows          :", q("SELECT COUNT(*) FROM opportunities")[0][0])
print("attempts      :", q("SELECT COUNT(*) FROM opportunity_attempts")[0][0])
print("labels        :", q("SELECT COUNT(*) FROM opportunities WHERE confidence IS NOT NULL")[0][0])
print("orphan legs   :", q("SELECT COUNT(*) FROM opportunity_legs WHERE opportunity_id NOT IN (SELECT id FROM opportunities)")[0][0])
print("times_seen>1  :", q("SELECT COUNT(*) FROM opportunities WHERE times_seen > 1")[0][0])
print("lanes         :", [dict(r) for r in q("SELECT lane, COUNT(*) n FROM opportunities GROUP BY 1")])
PY
```

Expected: rows 7467; labels **at least 1564**; orphan legs **0**; `times_seen > 1` on 1,686 rows; lanes `main` and `exp/2026-08-26-insider-judged-gated100`.

- [ ] **Step 6: Confirm the score moved the way the spec predicts**

```bash
python -m tools.cli score report insider_judgment --version 3 --run-mode backtest
```

Expected: `n=3195`, `calibration_edge_net ≈ -1.149`, `n_attempts=4759` — the pooled figure has become the fullcov figure, which is the honest reading.

- [ ] **Step 7: Write the migration report**

Create `docs/superpowers/plans/2026-08-27-migration-report.md` recording the before/after numbers from Steps 2, 5 and 6, the backup table name printed in Step 4, and the `.bak-*` file name from Step 1.

- [ ] **Step 8: Commit**

```bash
git add docs/superpowers/plans/2026-08-27-migration-report.md
git commit -m "migrate: collapse the live ledger to positions — 9,153 rows to 7,467"
```

The `.db` and `.bak-*` files are data, not source. Check `git status` first; if `db/market_edge.db` is tracked, commit it with the report, and never commit the `.bak-*` file.

---

### Task 10: Correct the stale write-ups and pre-register the gradient

**Files:**
- Modify: `theories/insider_bias/insider_judgment/backtests/RESULTS.md`
- Modify: `theories/insider_bias/insider_judgment/NOTES.md`
- Modify: `theories/insider_bias/mention_family/NOTES.md`
- Modify: `RESEARCH_LOG.md`

**Interfaces:**
- Consumes: the verified numbers from Task 9.
- Produces: no code.

- [ ] **Step 1: Find every stale number**

```bash
grep -rn "4,759\|4759\|-0\.59\|-0\.588" theories/ RESEARCH_LOG.md
```

- [ ] **Step 2: Annotate rather than overwrite**

For each hit, append a dated correction beneath the original — leave the original text in place, since it is the audit trail of what was believed at the time:

```markdown
> **Corrected 2026-08-27.** This figure pooled duplicate rows: `run_id` was in
> the `opportunities` UNIQUE key, so the judged sub-runs re-counted markets the
> full-coverage run had already recorded. The honest figure for v3 backtest is
> the full-coverage run alone: `n=3,195, calibration_edge_net -1.15`. See
> `docs/superpowers/specs/2026-08-27-position-identity-design.md`.
```

- [ ] **Step 3: Record the confidence gradient as a hypothesis, not a finding**

```bash
python -m tools.cli ideas search "confidence gradient"
python -m tools.cli ideas search "bucket monotonic"
```

If nothing matches, record it — and phrase it as pre-registration, because it was surfaced post-hoc on the same data:

```bash
python -m tools.cli ideas record \
  --theory insider_judgment \
  --title "insider_judgment confidence buckets are monotone in realized edge" \
  --detail "Merging the fullcov and judged backtest runs made bucket_rates over the judged backtest computable for the first time (the labels and the settlements previously sat on different rows): weak n=770 -0.29 pts, moderate n=565 +2.51, strong n=229 +3.95, all gross, n=1,564. Monotone in the direction the theory claims. Found post-hoc on the data that suggested it, so it is a hypothesis to test forward, not an edge to bet." \
  --revisit-angle "Needs an out-of-sample walk or a forward run before it counts. Re-check whether the gradient survives net of fees and holds inside single settlement-day clusters, since settlement-day clustering already confounded both live theories' first scores."
```

Check `python -m tools.cli ideas record --help` first and match the real flag names.

- [ ] **Step 4: Append a `RESEARCH_LOG.md` entry**

Cross-theory narrative belongs here; the detail stays in the spec and each theory's `NOTES.md`. One short entry pointing at the spec, the migration report, and the corrected figure.

- [ ] **Step 5: Run the full suite one last time**

Run: `python -m pytest -q`
Expected: all pass, including `tests/test_conventions.py`.

- [ ] **Step 6: Commit**

```bash
git add theories/ RESEARCH_LOG.md
git commit -m "notes: correct the pooled backtest figures, pre-register the confidence gradient"
```

---

## Verification checklist

Run at the end. Every line must hold before the work is called done.

- [ ] `python -m pytest -q` — full suite green
- [ ] `python -m tools.cli score report insider_judgment --version 3 --run-mode backtest` reports `n=3195`, `n_attempts=4759`
- [ ] `SELECT COUNT(*) FROM opportunities WHERE times_seen > 1` returns 1686
- [ ] `SELECT COUNT(*) FROM opportunity_legs WHERE opportunity_id NOT IN (SELECT id FROM opportunities)` returns 0
- [ ] `SELECT COUNT(*) FROM opportunities WHERE confidence IS NOT NULL` is at least 1564
- [ ] `python -m tools.cli opportunities mark-taken <id> taken --size 1` fails asking for `--theory`
- [ ] No theory version was bumped: `git diff master --stat -- theories/*/THEORY.md` shows no version changes
