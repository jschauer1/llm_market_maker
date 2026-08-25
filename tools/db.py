"""SQLite connection and schema management for the market edge finder.

Every connection enforces foreign keys and returns dict-like rows.
All timestamps produced here are UTC ISO-8601 with a trailing Z.

Mutating helpers across the tools package wrap their writes in `write`,
which commits on success and rolls back on failure. Without the rollback a
failed statement leaves the connection inside an open transaction, and the
next writer on another connection blocks for the full busy timeout before
failing with "database is locked".
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"
DEFAULT_DB_PATH = REPO_ROOT / "db" / "market_edge.db"


def utcnow() -> str:
    """Current UTC time as an ISO-8601 string, e.g. 2026-08-23T17:30:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a connection with foreign keys enforced and named row access.

    WAL journalling lets a reader run concurrently with a writer, which the
    market connectors need; the busy timeout covers the brief moments when
    two writers do collide.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def write(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Commit the enclosed writes, or roll back and re-raise on failure."""
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    """Create any missing tables and migrate stale ones. Safe to call repeatedly."""
    # Runs BEFORE the schema script, which contains CREATE UNIQUE INDEX on
    # market_snapshots. A database holding the duplicates the old non-unique
    # index allowed would fail that statement and be unable to open at all,
    # so the duplicates have to go first.
    _dedupe_snapshots(conn)
    with write(conn):
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _migrate_theories(conn)
    _migrate_judgment_runs(conn)
    _add_column_if_missing(
        conn, "theories", "uses_llm_judgment", "INTEGER NOT NULL DEFAULT 0"
    )
    # Additive: every pre-existing row is a single-leg position, and these
    # defaults describe it exactly, so there is no backfill.
    _add_column_if_missing(
        conn, "opportunities", "position_kind", "TEXT NOT NULL DEFAULT 'single'"
    )
    _add_column_if_missing(
        conn, "opportunities", "leg_count", "INTEGER NOT NULL DEFAULT 1"
    )
    _add_column_if_missing(
        conn, "opportunities", "max_payout", "REAL NOT NULL DEFAULT 1.0"
    )


def _dedupe_snapshots(conn: sqlite3.Connection) -> None:
    """Make an older snapshot table safe for the unique index.

    Before that index existed, two saves landing in the same capture second
    each wrote a full set of rows, silently merging into one batch with every
    market duplicated. This removes those lowest-id-wins and drops the
    redundant non-unique index on the same three columns.

    A no-op on a fresh database (no table yet) and on an already-migrated one.
    """
    objects = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','index')"
        ).fetchall()
    }
    if "market_snapshots" not in objects:
        return
    if "idx_snapshots_unique" in objects and "idx_snapshots_market" not in objects:
        return
    with write(conn):
        conn.execute(
            """
            DELETE FROM market_snapshots WHERE id NOT IN (
                SELECT MIN(id) FROM market_snapshots
                 GROUP BY platform, market_id, captured_at
            )
            """
        )
        # Same three columns as the unique index the schema creates next.
        conn.execute("DROP INDEX IF EXISTS idx_snapshots_market")


def _migrate_judgment_runs(conn: sqlite3.Connection) -> None:
    """Widen an old `judgment_runs` stage CHECK to accept 'construction'.

    Databases created before construction-stage provenance existed carry
    the old four-value CHECK baked into their DDL, and
    `CREATE TABLE IF NOT EXISTS` will not touch an existing table. SQLite
    cannot alter a CHECK in place, so the table is rebuilt exactly as
    `_migrate_theories` rebuilds theories. Rows carry over unchanged --
    every legacy stage is still valid under the new set.

    The UNIQUE constraint lives inside the table DDL and comes across with
    it; the separate index does not, because dropping the renamed table
    takes it along, so it is recreated here.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='judgment_runs'"
    ).fetchone()
    if row is None or "construction" in (row[0] or ""):
        return

    ddl = schema_statement("judgment_runs")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.execute("BEGIN")
        try:
            conn.execute(
                "ALTER TABLE judgment_runs RENAME TO judgment_runs_legacy"
            )
            conn.execute(ddl)
            conn.execute(
                """
                INSERT INTO judgment_runs
                    (id, run_id, theory_id, theory_version, stage, model,
                     effort, prompt_path, prompt_sha256, prompt_text,
                     web_search, n_items, notes, created_at)
                SELECT id, run_id, theory_id, theory_version, stage, model,
                       effort, prompt_path, prompt_sha256, prompt_text,
                       web_search, n_items, notes, created_at
                FROM judgment_runs_legacy
                """
            )
            conn.execute("DROP TABLE judgment_runs_legacy")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_judgment_runs_run"
                " ON judgment_runs (theory_id, theory_version, run_id)"
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    finally:
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.execute("PRAGMA foreign_keys = ON")


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, decl: str
) -> None:
    """Additive migration for a nullable/defaulted column.

    SQLite supports ALTER TABLE ADD COLUMN directly, so unlike a CHECK change
    this needs no table rebuild.
    """
    existing = {
        row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column in existing:
        return
    with write(conn):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def schema_statement(table: str) -> str:
    """Return the `CREATE TABLE IF NOT EXISTS <table> (...)` text from schema.sql.

    Migrations rebuild a table from this rather than from a copy of the DDL,
    so the schema has exactly one definition and cannot drift from the
    migration that recreates it. Raises ValueError if the statement is not
    found in the expected shape.
    """
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    marker = f"CREATE TABLE IF NOT EXISTS {table} ("
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"no CREATE TABLE for {table!r} in {SCHEMA_PATH}")
    end = text.find("\n);", start)
    if end < 0:
        raise ValueError(f"unterminated CREATE TABLE for {table!r}")
    return text[start : end + 2]


def _migrate_theories(conn: sqlite3.Connection) -> None:
    """Widen an old `theories` table to the evidence-level status set.

    Databases created before theory status became an evidence level carry a
    CHECK constraint that rejects 'testing' and 'under_review', and lack the
    retirement-proposal columns. SQLite cannot alter a CHECK in place, so the
    table is rebuilt. Rows carry over unchanged: every legacy status is still
    valid under the new set.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='theories'"
    ).fetchone()
    if row is None or "under_review" in (row[0] or ""):
        return

    ddl = schema_statement("theories")
    conn.commit()
    # Child tables reference theories(id); legacy_alter_table stops the rename
    # from rewriting those clauses to point at the temporary name.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.execute("BEGIN")
        try:
            conn.execute("ALTER TABLE theories RENAME TO theories_legacy")
            conn.execute(ddl)
            conn.execute(
                """
                INSERT INTO theories
                    (id, name, version, status, path, created_at, updated_at)
                SELECT id, name, version, status, path, created_at, updated_at
                FROM theories_legacy
                """
            )
            conn.execute("DROP TABLE theories_legacy")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    finally:
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.execute("PRAGMA foreign_keys = ON")
