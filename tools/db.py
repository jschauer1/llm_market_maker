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
    with write(conn):
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _migrate_theories(conn)


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
