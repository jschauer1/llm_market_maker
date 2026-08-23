"""Theory registry (spec sections 5, 10, 11).

This table is an index, not the source of truth. A theory's hypothesis and
procedure live in its THEORY.md; what lives here is enough to discover
theories programmatically and to track lifecycle state and version.

Version matters: any change to a theory's decision procedure must bump it,
so that scoring can segment on it and a mid-stream change cannot silently
merge two different theories into one track record.
"""

from __future__ import annotations

import sqlite3

from tools.db import utcnow, write

VALID_STATUSES = ("proposed", "active", "paused", "retired")


def register(
    conn: sqlite3.Connection,
    theory_id: str,
    name: str,
    path: str,
    status: str = "proposed",
    now: str | None = None,
) -> None:
    """Create or update a theory's registry entry. Never resets version."""
    if status not in VALID_STATUSES:
        raise ValueError(
            f"invalid status {status!r}; expected one of {VALID_STATUSES}"
        )
    stamp = now or utcnow()
    with write(conn):
        conn.execute(
            """
            INSERT INTO theories (id, name, version, status, path,
                                  created_at, updated_at)
            VALUES (?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                path = excluded.path,
                updated_at = excluded.updated_at
            """,
            (theory_id, name, status, path, stamp, stamp),
        )


def get(conn: sqlite3.Connection, theory_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM theories WHERE id = ?", (theory_id,)
    ).fetchone()


def list_theories(
    conn: sqlite3.Connection, status: str | None = None
) -> list[sqlite3.Row]:
    if status is None:
        return conn.execute("SELECT * FROM theories ORDER BY id").fetchall()
    return conn.execute(
        "SELECT * FROM theories WHERE status = ? ORDER BY id", (status,)
    ).fetchall()


def set_status(
    conn: sqlite3.Connection,
    theory_id: str,
    status: str,
    now: str | None = None,
) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(
            f"invalid status {status!r}; expected one of {VALID_STATUSES}"
        )
    if get(conn, theory_id) is None:
        raise KeyError(theory_id)
    with write(conn):
        conn.execute(
            "UPDATE theories SET status = ?, updated_at = ? WHERE id = ?",
            (status, now or utcnow(), theory_id),
        )


def bump_version(
    conn: sqlite3.Connection, theory_id: str, now: str | None = None
) -> int:
    """Increment the theory's version and return the new value."""
    row = get(conn, theory_id)
    if row is None:
        raise KeyError(theory_id)
    new_version = row["version"] + 1
    with write(conn):
        conn.execute(
            "UPDATE theories SET version = ?, updated_at = ? WHERE id = ?",
            (new_version, now or utcnow(), theory_id),
        )
    return new_version
