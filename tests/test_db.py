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
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r["name"] for r in rows}
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


def test_utcnow_format():
    stamp = db.utcnow()
    assert stamp.endswith("Z")
    assert len(stamp) == 20
    assert stamp[4] == "-" and stamp[10] == "T"
