import sqlite3

import pytest

from tools import db


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def test_all_tables_created(conn):
    # market_snapshots lives in the attached snapdb file, not main, since
    # the spec 5.2 phase 4 split -- an unqualified sqlite_master query
    # only ever sees main's own catalog (confirmed behaviorally), so this
    # checks both catalogs explicitly rather than assuming one query would
    # cover a table split across two database files.
    main_rows = conn.execute(
        "SELECT name FROM main.sqlite_master WHERE type='table'"
    ).fetchall()
    snap_rows = conn.execute(
        "SELECT name FROM snapdb.sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r["name"] for r in main_rows} | {r["name"] for r in snap_rows}
    expected = {
        "theories",
        "ideas",
        "market_snapshots",
        "opportunities",
        "settlements",
        "scores",
        "bucket_rates",
        "backtest_runs",
    }
    assert expected <= names


def test_init_db_is_idempotent(conn):
    db.init_db(conn)
    db.init_db(conn)
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table'"
    ).fetchone()["n"]
    assert count >= 8


def test_foreign_keys_are_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO opportunities ("
            " theory_id, theory_version, run_mode, run_id, kalshi_ticker,"
            " outcome, entry_price, screen_edge_pts_net, edge_pts_net,"
            " first_seen_at, last_seen_at"
            ") VALUES ('nonexistent', 1, 'live', 'live', 'TICK', 'yes',"
            " 0.5, 1.0, 1.0, '2026-08-23T00:00:00Z', '2026-08-23T00:00:00Z')"
        )
        conn.commit()


def test_rows_are_accessible_by_column_name(conn):
    conn.execute(
        "INSERT INTO theories (id, name, version, status, path,"
        " created_at, updated_at)"
        " VALUES ('t1', 'Test', 1, 'proposed', 'theories/t1',"
        " '2026-08-23T00:00:00Z', '2026-08-23T00:00:00Z')"
    )
    row = conn.execute("SELECT * FROM theories WHERE id='t1'").fetchone()
    assert row["name"] == "Test"


# --- schema statement extraction ---------------------------------------


def test_schema_statement_returns_a_single_create_table():
    stmt = db.schema_statement("theories")
    assert stmt.startswith("CREATE TABLE IF NOT EXISTS theories (")
    assert stmt.rstrip().endswith(")")
    # One statement, not a run-on into the next table.
    assert stmt.count("CREATE TABLE") == 1


def test_schema_statement_raises_for_an_unknown_table():
    with pytest.raises(ValueError):
        db.schema_statement("no_such_table")


# --- migrating a pre-evidence-level database ---------------------------

LEGACY_SCHEMA = """
CREATE TABLE theories (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    status      TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed','active','paused','retired')),
    path        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


def _legacy_db(tmp_path):
    """A database whose theories table predates the evidence-level statuses."""
    c = db.connect(tmp_path / "legacy.db")
    c.executescript(LEGACY_SCHEMA)
    c.execute(
        "INSERT INTO theories (id, name, version, status, path,"
        " created_at, updated_at)"
        " VALUES ('insider_bias', 'Insider Bias', 3, 'active',"
        " 'theories/insider_bias', '2026-01-01T00:00:00Z',"
        " '2026-02-01T00:00:00Z')"
    )
    c.commit()
    return c


def test_legacy_theories_table_rejects_the_new_statuses(tmp_path):
    # Establishes the problem the migration exists to solve.
    c = _legacy_db(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("UPDATE theories SET status='under_review'")
    c.close()


def test_init_db_migrates_a_legacy_theories_table(tmp_path):
    c = _legacy_db(tmp_path)
    db.init_db(c)
    c.execute("UPDATE theories SET status='under_review'")
    c.commit()
    row = c.execute("SELECT * FROM theories WHERE id='insider_bias'").fetchone()
    assert row["status"] == "under_review"
    assert row["retirement_proposed_at"] is None
    c.close()


def test_migration_preserves_existing_rows(tmp_path):
    c = _legacy_db(tmp_path)
    db.init_db(c)
    row = c.execute("SELECT * FROM theories WHERE id='insider_bias'").fetchone()
    assert row["name"] == "Insider Bias"
    assert row["version"] == 3
    assert row["status"] == "active"
    assert row["created_at"] == "2026-01-01T00:00:00Z"
    assert c.execute("SELECT COUNT(*) AS n FROM theories").fetchone()["n"] == 1
    c.close()


def test_migration_leaves_no_temporary_table_behind(tmp_path):
    c = _legacy_db(tmp_path)
    db.init_db(c)
    names = {
        r["name"]
        for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "theories_legacy" not in names
    c.close()


def test_migration_keeps_child_foreign_keys_pointing_at_theories(tmp_path):
    # The rename step must not rewrite `REFERENCES theories(id)` in the five
    # child tables to point at the temporary name.
    c = _legacy_db(tmp_path)
    db.init_db(c)
    ddl = c.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='opportunities'"
    ).fetchone()[0]
    assert "theories_legacy" not in ddl
    assert "REFERENCES theories(id)" in ddl
    with pytest.raises(sqlite3.IntegrityError):
        c.execute(
            "INSERT INTO opportunities ("
            " theory_id, theory_version, run_mode, run_id, kalshi_ticker,"
            " outcome, entry_price, screen_edge_pts_net, edge_pts_net,"
            " first_seen_at, last_seen_at"
            ") VALUES ('nonexistent', 1, 'live', 'live', 'TICK', 'yes',"
            " 0.5, 1.0, 1.0, '2026-08-23T00:00:00Z', '2026-08-23T00:00:00Z')"
        )
    c.close()


def test_migration_is_a_no_op_on_a_current_database(conn):
    before = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='theories'"
    ).fetchone()[0]
    db.init_db(conn)
    after = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='theories'"
    ).fetchone()[0]
    assert before == after


def test_utcnow_format():
    stamp = db.utcnow()
    assert stamp.endswith("Z")
    assert len(stamp) == 20
    assert stamp[4] == "-" and stamp[10] == "T"
