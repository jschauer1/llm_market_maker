"""Theory registry (spec sections 5, 10, 11).

This table is an index, not the source of truth. A theory's hypothesis and
procedure live in its THEORY.md; what lives here is enough to discover
theories programmatically and to track lifecycle state and version.

Version matters: any change to a theory's decision procedure must bump it,
so that scoring can segment on it and a mid-stream change cannot silently
merge two different theories into one track record.

Status is an evidence level, not an administrative flag, and `retired` is
reserved to the user. Claude diagnoses a failing theory and may *propose*
retirement; declaring one dead is a call the user makes. See
`propose_retirement` and `set_status`.
"""

from __future__ import annotations

import sqlite3

from tools.db import utcnow, write

#: proposed     -- hypothesis written, procedure unproven; not scanned
#: testing      -- procedure runs and accrues evidence; claims not demonstrated
#: active       -- demonstrated positive net calibration edge
#: under_review -- failing its own bar; keeps running while it is diagnosed
#: paused       -- blocked on a missing prerequisite, not on evidence
#: retired      -- judged dead; user-only
VALID_STATUSES = (
    "proposed",
    "testing",
    "active",
    "under_review",
    "paused",
    "retired",
)

#: Statuses only the user may assign. An underperforming theory is a research
#: object, not trash: the cases where it is salvageable (fees ate a real edge,
#: judgment is inverted but the screen is fine, one slice works, the sample is
#: too small to reject zero) all look identical to death from the outside.
#: Claude records a diagnosis via `propose_retirement`; the user rules.
USER_ONLY_STATUSES = ("retired",)

#: Statuses whose theories still run. `under_review` is deliberately in here:
#: a theory pulled off the board stops producing the evidence that would tell
#: you whether it was broken or merely unlucky.
SCANNABLE_STATUSES = ("testing", "active", "under_review")


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
    if status in USER_ONLY_STATUSES:
        raise PermissionError(
            f"cannot register a theory directly as {status!r}: "
            f"{USER_ONLY_STATUSES} are set by the user only. Register it at "
            "'proposed' and let the lifecycle move it."
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
    conn: sqlite3.Connection,
    status: str | None = None,
    running_only: bool = False,
) -> list[sqlite3.Row]:
    """List theories, optionally by exact status or restricted to those that run.

    `running_only` is what a scan wants: it includes `under_review`, because a
    theory being diagnosed stays on the board.
    """
    if running_only and status is not None:
        raise ValueError(
            "pass status or running_only, not both -- they would contradict"
        )
    if running_only:
        placeholders = ",".join("?" * len(SCANNABLE_STATUSES))
        return conn.execute(
            f"SELECT * FROM theories WHERE status IN ({placeholders})"
            " ORDER BY id",
            SCANNABLE_STATUSES,
        ).fetchall()
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
    authorized_by: str = "claude",
) -> None:
    """Move a theory to `status`.

    Assigning a status in `USER_ONLY_STATUSES` requires `authorized_by="user"`
    *and* a standing retirement proposal on the theory. The second condition
    is the one that matters: it makes "this is dead" unreachable without first
    writing down the diagnosis that says why, so a theory cannot be discarded
    on momentum.

    Moving a theory to any status other than `retired` or `under_review`
    clears a standing retirement proposal — the diagnosis no longer describes
    where the theory stands.
    """
    if status not in VALID_STATUSES:
        raise ValueError(
            f"invalid status {status!r}; expected one of {VALID_STATUSES}"
        )
    row = get(conn, theory_id)
    if row is None:
        raise KeyError(theory_id)
    if status in USER_ONLY_STATUSES:
        if authorized_by != "user":
            raise PermissionError(
                f"status {status!r} is the user's call, not yours. Diagnose "
                f"the theory, call propose_retirement(), and put it in front "
                f"of the user; they decide whether it is dead."
            )
        if row["retirement_proposed_at"] is None:
            raise ValueError(
                f"cannot retire {theory_id!r} with no retirement proposal on "
                "file; call propose_retirement() with the diagnosis first"
            )
    clear_proposal = status not in ("retired", "under_review")
    stamp = now or utcnow()
    with write(conn):
        if clear_proposal:
            conn.execute(
                """
                UPDATE theories
                   SET status = ?, updated_at = ?,
                       retirement_proposed_at = NULL,
                       retirement_rationale = NULL
                 WHERE id = ?
                """,
                (status, stamp, theory_id),
            )
        else:
            conn.execute(
                "UPDATE theories SET status = ?, updated_at = ? WHERE id = ?",
                (status, stamp, theory_id),
            )


def propose_retirement(
    conn: sqlite3.Connection,
    theory_id: str,
    rationale: str,
    now: str | None = None,
) -> None:
    """Record a standing suggestion to the user that a theory is dead.

    This does not change status — the theory keeps running while the user has
    not ruled, because more evidence can only sharpen the question. The
    proposal persists so that every session surfaces it until it is acted on
    or withdrawn.

    `rationale` must say what was actually ruled out, not just that the
    numbers are bad. It is what the user reads when deciding.
    """
    if not rationale or not rationale.strip():
        raise ValueError(
            "a retirement proposal needs a rationale: what did you diagnose, "
            "and what did you rule out?"
        )
    if get(conn, theory_id) is None:
        raise KeyError(theory_id)
    stamp = now or utcnow()
    with write(conn):
        conn.execute(
            """
            UPDATE theories
               SET retirement_proposed_at = ?,
                   retirement_rationale = ?,
                   updated_at = ?
             WHERE id = ?
            """,
            (stamp, rationale.strip(), stamp, theory_id),
        )


def withdraw_retirement(
    conn: sqlite3.Connection, theory_id: str, now: str | None = None
) -> None:
    """Clear a standing retirement proposal — the user kept the theory, or
    new evidence changed the diagnosis."""
    if get(conn, theory_id) is None:
        raise KeyError(theory_id)
    with write(conn):
        conn.execute(
            """
            UPDATE theories
               SET retirement_proposed_at = NULL,
                   retirement_rationale = NULL,
                   updated_at = ?
             WHERE id = ?
            """,
            (now or utcnow(), theory_id),
        )


def list_pending_retirement(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Theories Claude has proposed retiring that the user has not ruled on."""
    return conn.execute(
        """
        SELECT * FROM theories
         WHERE retirement_proposed_at IS NOT NULL AND status != 'retired'
         ORDER BY retirement_proposed_at
        """
    ).fetchall()


def set_uses_llm_judgment(
    conn: sqlite3.Connection,
    theory_id: str,
    uses_llm: bool,
    now: str | None = None,
) -> None:
    """Declare whether any LLM sits in this theory's decision path.

    Declaring it turns on the provenance requirement: opportunities cannot be
    recorded for a run until `tools/provenance.py` has captured the model and
    prompt for each judging stage. A fully mechanical theory leaves this off
    and has nothing to record — which is one more reason to prefer one.
    """
    if get(conn, theory_id) is None:
        raise KeyError(theory_id)
    with write(conn):
        conn.execute(
            "UPDATE theories SET uses_llm_judgment = ?, updated_at = ?"
            " WHERE id = ?",
            (int(bool(uses_llm)), now or utcnow(), theory_id),
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
