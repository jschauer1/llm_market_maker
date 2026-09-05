"""The idea registry — research memory (spec section 11).

Every hypothesis that gets considered is recorded here, whether or not it
ever becomes a theory. Without this the system has no memory: a session six
months from now re-derives a hypothesis that was already tested and killed,
burns the same effort, and reaches the same dead end.

Three fields carry the weight:

  what_was_tried  what investigation ACTUALLY happened, not what was planned
  outcome         what was learned; for a dead idea, specifically why it died
  revisit_angle   what a genuinely different approach would look like

The last one is the difference between "don't try this again" and "don't try
this again the same way". A null revisit_angle means exhausted; a populated
one means the idea is waiting for someone to come at it differently.
"""

from __future__ import annotations

import sqlite3

from tools.db import utcnow, write

VALID_STATUSES = (
    "considered",
    "investigating",
    "promoted",
    "parked",
    "dead",
)


def record(
    conn: sqlite3.Connection,
    slug: str,
    title: str,
    description: str = "",
    source: str | None = None,
    status: str = "considered",
    now: str | None = None,
) -> int:
    """Record an idea. Re-recording an existing slug updates it in place
    without resetting its status or accumulated findings. An omitted source
    becomes ``agent`` for a new row and preserves an existing attribution."""
    if status not in VALID_STATUSES:
        raise ValueError(
            f"invalid status {status!r}; expected one of {VALID_STATUSES}"
        )
    stamp = now or utcnow()
    with write(conn):
        conn.execute(
            """
            INSERT INTO ideas (slug, title, description, status, source,
                               created_at, updated_at)
            VALUES (?, ?, ?, ?, COALESCE(?, 'agent'), ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                source = COALESCE(?, ideas.source),
                updated_at = excluded.updated_at
            """,
            (slug, title, description, status, source, stamp, stamp, source),
        )
    return conn.execute(
        "SELECT id FROM ideas WHERE slug = ?", (slug,)
    ).fetchone()["id"]


def get(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM ideas WHERE slug = ?", (slug,)).fetchone()


def search(conn: sqlite3.Connection, keyword: str) -> list[sqlite3.Row]:
    """Case-insensitive search over slug, title, and description.

    Call this BEFORE proposing a theory. An idea matching a dead one needs a
    real revisit_angle to justify running again.
    """
    pattern = f"%{keyword.lower()}%"
    return conn.execute(
        """
        SELECT * FROM ideas
        WHERE LOWER(slug) LIKE ?
           OR LOWER(title) LIKE ?
           OR LOWER(COALESCE(description, '')) LIKE ?
        ORDER BY id
        """,
        (pattern, pattern, pattern),
    ).fetchall()


def update_status(
    conn: sqlite3.Connection,
    slug: str,
    status: str,
    what_was_tried: str | None = None,
    outcome: str | None = None,
    revisit_angle: str | None = None,
    revisit_after: str | None = None,
    theory_id: str | None = None,
    now: str | None = None,
) -> None:
    """Move an idea along and record what was learned.

    Fields left as None are preserved, so a later update does not erase an
    earlier finding.
    """
    if status not in VALID_STATUSES:
        raise ValueError(
            f"invalid status {status!r}; expected one of {VALID_STATUSES}"
        )
    if get(conn, slug) is None:
        raise KeyError(slug)
    with write(conn):
        conn.execute(
            """
            UPDATE ideas SET
                status = ?,
                what_was_tried = COALESCE(?, what_was_tried),
                outcome = COALESCE(?, outcome),
                revisit_angle = COALESCE(?, revisit_angle),
                revisit_after = COALESCE(?, revisit_after),
                theory_id = COALESCE(?, theory_id),
                updated_at = ?
            WHERE slug = ?
            """,
            (
                status,
                what_was_tried,
                outcome,
                revisit_angle,
                revisit_after,
                theory_id,
                now or utcnow(),
                slug,
            ),
        )


def list_revisitable(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Ideas worth another look: parked ones (whose blocking condition may
    now be met) and dead ones that still carry a revisit_angle."""
    return conn.execute(
        """
        SELECT * FROM ideas
        WHERE status = 'parked'
           OR (status = 'dead' AND revisit_angle IS NOT NULL)
        ORDER BY updated_at
        """
    ).fetchall()
