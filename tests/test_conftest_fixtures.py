"""The shared DB fixtures must be indistinguishable from a real database.

These are the tests that let ~40 files trust `conn`. If a fixture in
`tests/conftest.py` ever stops matching what `db.connect()` + `db.init_db()`
produce, this file is what says so -- before forty other files start
passing for the wrong reason.
"""

import pytest

from tools import db, ledger, theories

TS = "2026-08-23T12:00:00Z"


def _tables(c, schema="main"):
    return {r[0] for r in c.execute(
        f"select name from {schema}.sqlite_master where type='table'")}


def test_conn_has_every_table_a_real_database_has(conn):
    real = db.connect(":memory:")
    db.init_db(real)
    assert _tables(conn) == _tables(real)
    assert _tables(conn, "snapdb") == _tables(real, "snapdb")
    real.close()


def test_conn_enforces_foreign_keys(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_conn_returns_rows_by_name(conn):
    theories.register(conn, "t1", "T", "p", now=TS)
    row = conn.execute("select * from theories").fetchone()
    assert row["id"] == "t1"


def test_conn_actually_persists_writes_within_a_test(conn):
    theories.register(conn, "t1", "T", "p", now=TS)
    assert conn.execute("select count(*) from theories").fetchone()[0] == 1


def test_conn_is_isolated_between_tests_part_one(conn):
    """Writes a row the next test asserts it cannot see."""
    theories.register(conn, "leaky", "T", "p", now=TS)


def test_conn_is_isolated_between_tests_part_two(conn):
    assert conn.execute(
        "select count(*) from theories where id='leaky'").fetchone()[0] == 0


def test_registered_conn_seeds_the_standard_theory(registered_conn):
    row = registered_conn.execute("select * from theories").fetchone()
    assert row["id"] == "t1"


def test_conn_supports_the_ledger_contract(conn):
    """The real contract every recorded bet passes through."""
    theories.register(conn, "t1", "T", "p", now=TS)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="TK1",
        outcome="no", entry_price=0.85, edge_pts_net=4.0,
        edge_basis="model", run_mode="live", run_id="live",
        decision_date="2026-08-27", rationale="x",
    )
    assert conn.execute(
        "select count(*) from opportunities").fetchone()[0] == 1


def test_conn_disk_is_backed_by_a_real_file(conn_disk, db_file):
    assert db_file.exists()


def test_conn_disk_is_reopenable_by_path(conn_disk, db_file):
    """The property tier 1 deliberately does NOT have, which is why the
    handful of tests whose code reopens the database by path keep a file."""
    theories.register(conn_disk, "t1", "T", "p", now=TS)
    conn_disk.commit()
    other = db.connect(db_file)
    assert other.execute("select count(*) from theories").fetchone()[0] == 1
    other.close()


def test_source_corpus_reads_every_python_file_once(source_corpus):
    assert len(source_corpus.py_files) > 150
    assert all(p.suffix == ".py" for p in source_corpus.py_files)
    assert all(p in source_corpus.text for p in source_corpus.py_files)


def test_source_corpus_skips_the_noise_directories(source_corpus):
    noisy = {".git", "__pycache__", "attic", ".pytest_cache"}
    for p in source_corpus.py_files:
        assert not (noisy & set(p.parts)), p


def test_source_corpus_includes_markdown(source_corpus):
    assert len(source_corpus.md_files) > 100
