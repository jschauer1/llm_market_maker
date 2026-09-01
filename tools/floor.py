"""Floor duty — one session runs the daily floor, and the rest can tell.

`go`'s floor is the repo's one standing guarantee: every running theory
sees today's board through its complete procedure. It needs to happen
once a day, not once per session — four sessions collided on 2026-08-30
under a message-only protocol, and the defective duplicate run that came
out of it is still quarantined in the ledger because a DELETE needs the
user.

So the claim is a row, not a message. A session asks `status()` whether
the floor is due, `claim()` for the right to run it, and `complete()`
when the report has landed. Every session reaches the same answer from
the same table, including one that started while another was mid-run and
one that never received any peer's message at all.

Two clocks, and they answer different questions:

- **FLOOR_INTERVAL_HOURS** — how long a *completed* floor satisfies the
  requirement. The user's rule: nobody runs another one for 24 hours
  unless explicitly asked, and `force=True` is that asking.
- **CLAIM_LEASE_HOURS** — how long an *unfinished* claim blocks other
  sessions. Without it, a session that claims the floor and dies costs
  the repo a whole day of evidence, which is a worse failure than the
  duplicate run the claim exists to prevent. Past the lease the claim is
  taken over, and the abandoned row stays as the audit trail.

The lease is deliberately longer than a floor takes and far shorter than
the interval: a real floor is a board pull plus a settle run plus every
theory's runbook, which is minutes to a couple of hours with subagents,
so a claim still open after four is a dead session, not a slow one.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from tools.db import utcnow, write

#: A completed floor satisfies the daily requirement for this long.
FLOOR_INTERVAL_HOURS = 24

#: An unfinished claim blocks other sessions for this long, then expires.
CLAIM_LEASE_HOURS = 4


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))


def _hours_between(earlier: str, later: str) -> float:
    return (_parse(later) - _parse(earlier)).total_seconds() / 3600.0


def _latest_completed(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM floor_runs WHERE completed_at IS NOT NULL"
        " ORDER BY completed_at DESC LIMIT 1"
    ).fetchone()


def _open_claim(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM floor_runs WHERE completed_at IS NULL"
        " ORDER BY claimed_at DESC LIMIT 1"
    ).fetchone()


def status(conn: sqlite3.Connection, now: str | None = None) -> dict:
    """Whether the floor is due, who holds it, and when it last landed.

    `due` is the whole answer a session needs: True means run it (after
    winning `claim`), False means somebody already did or is doing it.
    `reason` says which, in words meant for a report.
    """
    now = now or utcnow()
    done = _latest_completed(conn)
    held = _open_claim(conn)

    holder = None
    if held is not None:
        age = _hours_between(held["claimed_at"], now)
        if age < CLAIM_LEASE_HOURS:
            holder = held["session"]

    since = None if done is None else _hours_between(done["completed_at"], now)

    if holder is not None:
        due, reason = False, (
            f"claimed by {holder} at {held['claimed_at']} "
            f"({age:.1f}h ago, lease {CLAIM_LEASE_HOURS}h)"
        )
    elif since is not None and since < FLOOR_INTERVAL_HOURS:
        due, reason = False, (
            f"last completed {since:.1f} hours ago; next due in "
            f"{FLOOR_INTERVAL_HOURS - since:.1f} hours"
        )
    elif since is None:
        due, reason = True, "no floor has ever completed"
    else:
        due, reason = True, f"last completed {since:.1f} hours ago"

    if holder is None and held is not None:
        reason += (
            f" (claim by {held['session']} at {held['claimed_at']} "
            "expired unfinished)"
        )

    return {
        "due": due,
        "reason": reason,
        "holder": holder,
        "hours_since_completed": since,
        "last_completed_at": None if done is None else done["completed_at"],
        "last_completed_by": None if done is None else done["session"],
        "last_report_path": None if done is None else done["report_path"],
        "interval_hours": FLOOR_INTERVAL_HOURS,
        "lease_hours": CLAIM_LEASE_HOURS,
    }


def claim(
    conn: sqlite3.Connection,
    session: str,
    *,
    now: str | None = None,
    force: bool = False,
) -> sqlite3.Row | None:
    """Take floor duty, or return None if it is not this session's to take.

    None is a complete answer, not an error: the floor already ran, or
    another session is running it. The caller goes and does research
    instead. `force=True` is the user explicitly asking for a floor
    inside the interval; it still refuses to cut in on a live claim,
    because two sessions running the floor at once is the exact
    collision this table exists to prevent.
    """
    if not session or not session.strip():
        raise ValueError("a session name is required to claim floor duty")
    now = now or utcnow()
    with write(conn):
        # Re-read inside the transaction: two sessions starting together
        # must not both see an unclaimed floor. `write` opens BEGIN
        # IMMEDIATE, so the loser blocks here and then sees the winner's
        # row rather than an empty table.
        state = status(conn, now=now)
        if state["holder"] is not None:
            return None
        if not state["due"] and not force:
            return None
        cur = conn.execute(
            "INSERT INTO floor_runs (session, claimed_at, forced)"
            " VALUES (?, ?, ?)",
            (session, now, 1 if force else 0),
        )
        claim_id = cur.lastrowid
    return get(conn, claim_id)


def complete(
    conn: sqlite3.Connection,
    claim_id: int,
    *,
    now: str | None = None,
    report_path: str | None = None,
    summary: str | None = None,
) -> sqlite3.Row:
    """Record that the floor ran and the report landed.

    This is what starts the 24-hour clock — claiming does not, because a
    claim is an intention and the guarantee is about work actually done.
    """
    row = get(conn, claim_id)
    if row is None:
        raise KeyError(claim_id)
    if row["completed_at"] is not None:
        raise ValueError(
            f"floor run {claim_id} was already completed at "
            f"{row['completed_at']}"
        )
    with write(conn):
        conn.execute(
            "UPDATE floor_runs SET completed_at = ?, report_path = ?,"
            " summary = ? WHERE id = ?",
            (now or utcnow(), report_path, summary, claim_id),
        )
    return get(conn, claim_id)


def get(conn: sqlite3.Connection, claim_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM floor_runs WHERE id = ?", (claim_id,)
    ).fetchone()


def recent(conn: sqlite3.Connection, limit: int = 10) -> list[sqlite3.Row]:
    """The last few floor runs, newest first — completed and abandoned."""
    return conn.execute(
        "SELECT * FROM floor_runs ORDER BY claimed_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
