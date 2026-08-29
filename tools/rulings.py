"""Rulings as rows (enforcing-surfaces spec 3.3).

A ruling buried in the log tail stops binding the first week nobody
scrolls to it. The row carries the binding text and its authority; the
log entry it names keeps the reasoning. Only 'user' and 'supervisor'
rule -- research sessions propose, they never rule.
"""

from __future__ import annotations

import sqlite3

from tools.db import utcnow, write


def record(
    conn: sqlite3.Connection,
    ruling: str,
    *,
    authority: str,
    subject: str,
    ruled_at: str | None = None,
    scope_out: str | None = None,
    status: str = "binding",
    log_entry: str | None = None,
) -> int:
    with write(conn):
        cur = conn.execute(
            """
            INSERT INTO rulings
                (ruled_at, authority, subject, ruling, scope_out, status,
                 log_entry)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ruled_at or utcnow(), authority, subject, ruling.strip(),
             scope_out, status, log_entry),
        )
    return cur.lastrowid


def list_rulings(
    conn: sqlite3.Connection, status: str | None = None
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM rulings"
    params: list = []
    if status is not None:
        sql += " WHERE status = ?"
        params.append(status)
    return conn.execute(sql + " ORDER BY ruled_at, id", params).fetchall()


def set_status(conn: sqlite3.Connection, ruling_id: int, status: str) -> None:
    with write(conn):
        cur = conn.execute(
            "UPDATE rulings SET status = ? WHERE id = ?", (status, ruling_id)
        )
        if cur.rowcount == 0:
            raise KeyError(ruling_id)
