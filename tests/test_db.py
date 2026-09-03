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


# ============================================ the self-disabling sentinel
# The bug class behind `study` shipping unclaimable in EVERY database: a
# migration that widens an enumerated CHECK guards itself with an early
# return keyed to one literal value. That guard stops firing permanently
# the moment that value lands, so every value added afterwards silently
# fails to migrate -- and the symptom is not an error at migration time,
# it is a bare `sqlite3.IntegrityError: CHECK constraint failed` at some
# unrelated caller weeks later.
#
# A per-value test cannot catch this, because the value that fails is by
# definition the one nobody thought to write a test for. So these tests
# derive their cases from `schema.sql` itself.

#: Every table whose CHECK vocabulary has a widening migration, and the
#: column that migration exists to widen. Each of these is a vocabulary
#: CLAUDE.md calls an interface ("recorded rows are only interpretable
#: through those definitions"), which is why they are the ones that got
#: migrations in the first place.
_MIGRATED_CHECKS = [
    ("theories", "status", "_migrate_theories"),
    ("theory_versions", "kind", "_migrate_theory_versions"),
    ("judgment_runs", "stage", "_migrate_judgment_runs"),
    ("lane_claims", "lane", "_migrate_lane_claims"),
]


def _ddl_without(ddl: str, column: str, value: str) -> str:
    """`ddl` with one value dropped from its `CHECK (column IN (...))`.

    This is how a legacy database looks: identical to today's schema
    except that it predates one value.
    """
    import re

    m = re.search(rf"CHECK\s*\(\s*{re.escape(column)}\s+IN\s*\((.*?)\)",
                  ddl, re.DOTALL | re.IGNORECASE)
    assert m, f"no enumerated CHECK on {column}"
    kept = [v for v in re.findall(r"'([^']*)'", m.group(1)) if v != value]
    assert kept, "cannot build a legacy DDL with no values left"
    return ddl[:m.start(1)] + ",".join(f"'{v}'" for v in kept) + ddl[m.end(1):]


def _canonical(table, column):
    return sorted(db.check_values(db.schema_statement(table), column))


@pytest.mark.parametrize("table,column,fn_name", _MIGRATED_CHECKS)
def test_every_value_of_a_migrated_check_survives_a_legacy_database(
        tmp_path, table, column, fn_name):
    """A database predating ANY ONE value must end up accepting it.

    Parametrised over the values in `schema.sql` rather than a list
    written here, so a value added tomorrow is covered the day it lands.
    Against the old sentinel guards this fails for every value except the
    sentinel itself: `_migrate_theories` returned early whenever
    'under_review' was already present, so a database missing 'paused'
    was never widened.
    """
    migrate = getattr(db, fn_name)
    canonical = db.check_values(db.schema_statement(table), column)
    for value in sorted(canonical):
        c = db.connect(tmp_path / f"legacy-{value}.db")
        db.init_db(c)
        try:
            c.execute("PRAGMA foreign_keys = OFF")
            c.execute(f"DROP TABLE {table}")
            c.execute(_ddl_without(db.schema_statement(table), column, value))
            c.commit()
            migrate(c)
            live = c.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table,)).fetchone()
            assert value in db.check_values(live[0], column), (
                f"{fn_name} left {table}.{column} rejecting {value!r}: a "
                f"database predating that value stays broken forever. This "
                f"is the self-disabling-sentinel guard -- diff the accepted "
                f"sets against schema.sql instead of testing for a literal."
            )
        finally:
            c.close()


@pytest.mark.parametrize("table,column,fn_name", _MIGRATED_CHECKS)
def test_a_widening_migration_preserves_the_rows_it_rebuilds(
        tmp_path, table, column, fn_name):
    """SQLite cannot alter a CHECK in place, so every one of these
    migrations RENAMEs, recreates and copies. That is a data-moving
    operation on live evidence -- `theories` and `judgment_runs` both
    carry rows nothing can regenerate -- so the copy is asserted, not
    assumed."""
    migrate = getattr(db, fn_name)
    canonical = sorted(db.check_values(db.schema_statement(table), column))
    c = db.connect(tmp_path / "legacy.db")
    db.init_db(c)
    try:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
        before = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute(f"DROP TABLE {table}")
        c.execute(_ddl_without(db.schema_statement(table), column,
                               canonical[-1]))
        c.commit()
        migrate(c)
        after = [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
        assert set(cols) <= set(after), (
            f"{fn_name} rebuilt {table} without every column it had")
        assert c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] \
            == before
    finally:
        c.close()


def test_check_values_reads_a_vocabulary_out_of_a_ddl():
    ddl = "CREATE TABLE t (a TEXT CHECK (a IN ('x','y')), b TEXT)"
    assert db.check_values(ddl, "a") == {"x", "y"}
    # No enumerated CHECK on that column -> empty, so a guard written as
    # `if not (canonical - live): return` degrades to a no-op instead of
    # raising on a table that never had one.
    assert db.check_values(ddl, "b") == set()
    assert db.check_values("", "a") == set()


def test_the_interface_vocabularies_are_what_claude_md_says_they_are():
    """CLAUDE.md: these names are an interface, and changing what an
    existing value MEANS rewrites every row already recorded under the old
    meaning. Widening is safe and this test permits it; REMOVING or
    RENAMING a value is the breaking change, and this is where it gets
    caught -- at the commit that does it, rather than months later in a
    query that quietly started answering a different question."""
    required = {
        ("theories", "status"): {
            "proposed", "testing", "active", "under_review", "paused",
            "retired"},
        ("theory_versions", "kind"): {"breaking", "carry", "continues"},
        ("opportunities", "edge_basis"): {"measured", "prior", "model"},
        ("opportunities", "disposition"): {
            "screened", "endorsed", "rejected"},
        ("opportunities", "run_mode"): {"live", "backtest"},
        ("opportunities", "user_action"): {"untouched", "taken", "skipped"},
        ("backtest_runs", "tier"): {"A", "B", "C"},
        ("lane_claims", "lane"): {
            "floor", "theory", "study", "new-theory", "find-theories",
            "maintenance"},
    }
    for (table, column), expected in required.items():
        live = db.check_values(db.schema_statement(table), column)
        assert expected <= live, (
            f"{table}.{column} no longer accepts {sorted(expected - live)}. "
            f"Recorded rows were written under the old vocabulary; migrate "
            f"them explicitly and separately, and say so in RESEARCH_LOG.md."
        )


@pytest.mark.parametrize("table,column", [(t, c) for t, c, _ in _MIGRATED_CHECKS])
def test_a_guard_reads_the_constraint_and_not_the_comments_around_it(
        table, column):
    """The sharper half of the sentinel bug, found 2026-09-03.

    `sqlite_master.sql` stores the CREATE TABLE text VERBATIM, SQL
    comments included. Two guards substring-matched their sentinel against
    that whole blob, and in both cases the word appears in a comment
    documenting the very vocabulary being checked:

        theory_versions:  --   continues -- the DEFAULT: procedure changed
        judgment_runs:    -- 'construction' is judgment that established

    So `"continues" in ddl` was True for a database whose CHECK accepted
    only ('breaking','carry'). Those two migrations were not merely
    self-disabling after their value landed -- they were **dead from birth
    and could never fire in any database**. It stayed latent only because
    the live DB happened to be rebuilt from schema.sql after both values
    existed; a database created before the 2026-08-31 `continues` ruling
    would have rejected every non-breaking bump with a bare IntegrityError
    and no migration would ever have repaired it.

    `check_values` parses the CHECK clause itself, so prose can no longer
    vote. This test proves that by putting every value in a comment while
    the constraint accepts none of them.
    """
    canonical = db.check_values(db.schema_statement(table), column)
    commented = (
        f"CREATE TABLE {table} (\n"
        + "".join(f"    -- {v} is a valid {column}\n" for v in sorted(canonical))
        + f"    {column} TEXT CHECK ({column} IN ('legacy_only'))\n)"
    )
    assert db.check_values(commented, column) == {"legacy_only"}, (
        "a comment naming a value made the guard believe the constraint "
        "accepted it; parse the CHECK clause, never the whole DDL blob"
    )
    # ...and the guard built on it therefore still sees work to do.
    assert canonical - db.check_values(commented, column) == canonical
