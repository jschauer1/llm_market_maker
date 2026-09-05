"""Theory registry (spec sections 5, 10, 11).

This table is an index, not the source of truth. A theory's hypothesis and
procedure live in its THEORY.md; what lives here is enough to discover
theories programmatically and to track lifecycle state and version.

Version matters: any change to a theory's decision procedure must bump it,
so that scoring can segment on it and a mid-stream change cannot silently
merge two different theories into one track record.

Status is an evidence level, not an administrative flag, and `retired` is
reserved to the user. An agent diagnoses a failing theory and may *propose*
retirement; declaring one dead is a call the user makes. See
`propose_retirement` and `set_status`.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Callable, Mapping

from tools.db import utcnow, write
from tools.domain import EquivalenceResult

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
#: An agent records a diagnosis via `propose_retirement`; the user rules.
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
        # Re-registering (every scan that discovers theories on disk) must
        # not touch a v1 row that already exists -- OR IGNORE keys off the
        # (theory_id, version) primary key, so this is a no-op after the
        # first call.
        conn.execute(
            """
            INSERT OR IGNORE INTO theory_versions
                (theory_id, version, kind, predecessor, justification,
                 created_at)
            VALUES (?, 1, 'breaking', NULL, 'initial version', ?)
            """,
            (theory_id, stamp),
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
    authorized_by: str = "agent",
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
    """Theories an agent proposed retiring that the user has not ruled on."""
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


#: `bump_version`'s carry-proof parameter type (enforcing-surfaces spec
#: 2.4). `EquivalenceResult` (`tools/domain.py`) IS this type -- there is
#: no longer a duck-typed stand-in. `bump_version` enforces
#: `isinstance(equivalence, EquivalenceResult)` before it ever looks at
#: `.passed`, so an object that merely exposes the right attributes is
#: refused, not silently accepted. `_CarryProof` stays as a readable
#: alias at the call site below rather than spelling out
#: `EquivalenceResult | None` twice.
_CarryProof = EquivalenceResult


def bump_version(
    conn: sqlite3.Connection,
    theory_id: str,
    now: str | None = None,
    *,
    kind: str = "continues",
    justification: str,
    equivalence: _CarryProof | None = None,
) -> int:
    """Increment the theory's version and record what kind of bump it was.

    Every bump declares its relationship to its predecessor's EVIDENCE:

    - `continues` (the default) -- the decision procedure changed and the
      evidence still stands. No proof required.
    - `carry` -- the change provably could not alter any recorded
      decision. Refused unless `equivalence` is a passing replay over the
      predecessor's own attempts; assertion does not qualify, the proof
      is the permission (spec 2.4). Strictly stronger than `continues`
      and pools identically, so it is worth recording when it is true.
    - `breaking` -- an explicit sever. The new version starts from zero,
      and `justification` must say what makes the old evidence
      inapplicable.

    **`breaking` used to be the default** (spec 2.3), on the reasoning
    that a changed procedure is a different theory whose history should
    not be merged. That guarded against a real failure -- tuning a theory
    until its history looks good -- but it priced the guard wrong: the
    proof bar was high enough that almost nobody cleared it, and three of
    the four running theories reached n=0 discarding genuine evidence to
    prevent a merge nobody had attempted. Under the 2026-08-31 user
    ruling a version bump is no longer, by itself, a reason to disbelieve
    what a theory has demonstrated -- including a backtest run against an
    earlier version. Severing is still available and still honoured
    absolutely; it now has to argue for itself, which is the direction
    that deserves the burden.
    """
    if kind not in ("breaking", "carry", "continues"):
        raise ValueError(
            f"invalid kind {kind!r}; expected 'breaking', 'carry' or "
            "'continues'"
        )
    row = get(conn, theory_id)
    if row is None:
        raise KeyError(theory_id)
    equivalence_run = None
    if kind == "carry":
        if not isinstance(equivalence, EquivalenceResult) or not equivalence.passed:
            raise ValueError(
                "carry needs a passing equivalence proof -- the proof is "
                "the permission (spec 2.4)"
            )
        equivalence_run = equivalence.label
    new_version = row["version"] + 1
    stamp = now or utcnow()
    with write(conn):
        conn.execute(
            "UPDATE theories SET version = ?, updated_at = ? WHERE id = ?",
            (new_version, stamp, theory_id),
        )
        conn.execute(
            """
            INSERT INTO theory_versions
                (theory_id, version, kind, predecessor, justification,
                 equivalence_run, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (theory_id, new_version, kind, row["version"], justification,
             equivalence_run, stamp),
        )
    return new_version


def reclassify_bump(
    conn: sqlite3.Connection,
    theory_id: str,
    version: int,
    *,
    kind: str,
    reason: str,
    equivalence: _CarryProof | None = None,
    now: str | None = None,
) -> sqlite3.Row:
    """Correct how a recorded bump relates to its predecessor's evidence.

    Exists for one situation and should stay rare: a bump whose `kind`
    records the old default rather than a decision anyone made. Every
    multi-version theory in this repo carries rows justified
    "pre-dates the carry ruling; not adjudicated" -- which is not a
    finding that the evidence was inapplicable, it is the absence of a
    finding, frozen into the schema because `breaking` used to be what
    you got for saying nothing. Under the 2026-08-31 ruling that default
    is wrong, and leaving those rows would mean the ruling changed
    nothing for any theory that already exists.

    **It never erases the original justification.** The prior wording is
    kept and the reason appended, because a correction to a governance
    record whose earlier text is gone cannot be audited -- and the point
    of correcting a default is that someone can see it was a default.

    `carry` keeps its full bar here: a correction is not a side door
    around the equivalence replay.
    """
    if kind not in ("breaking", "carry", "continues"):
        raise ValueError(
            f"invalid kind {kind!r}; expected 'breaking', 'carry' or "
            "'continues'"
        )
    if not reason or not reason.strip():
        raise ValueError(
            "a reason is required: say what makes the recorded kind wrong"
        )
    row = conn.execute(
        "SELECT * FROM theory_versions WHERE theory_id = ? AND version = ?",
        (theory_id, version),
    ).fetchone()
    if row is None:
        raise KeyError((theory_id, version))
    equivalence_run = row["equivalence_run"]
    if kind == "carry":
        if not isinstance(equivalence, EquivalenceResult) or not equivalence.passed:
            raise ValueError(
                "carry needs a passing equivalence proof -- the proof is "
                "the permission, and a reclassification is no exception"
            )
        equivalence_run = equivalence.label
    elif row["kind"] == "carry":
        # Dropping a carry claim drops the proof that licensed it; leaving
        # the label behind would credit a replay the row no longer rests on.
        equivalence_run = None
    stamp = now or utcnow()
    justification = (
        f"{row['justification']} [reclassified {row['kind']} -> {kind} on "
        f"{stamp[:10]}: {reason}]"
    )
    with write(conn):
        conn.execute(
            "UPDATE theory_versions SET kind = ?, justification = ?,"
            " equivalence_run = ? WHERE theory_id = ? AND version = ?",
            (kind, justification, equivalence_run, theory_id, version),
        )
    return conn.execute(
        "SELECT * FROM theory_versions WHERE theory_id = ? AND version = ?",
        (theory_id, version),
    ).fetchone()


def list_versions(
    conn: sqlite3.Connection, theory_id: str
) -> list[sqlite3.Row]:
    """A theory's version history, oldest first."""
    return conn.execute(
        "SELECT * FROM theory_versions WHERE theory_id = ? ORDER BY version",
        (theory_id,),
    ).fetchall()


def carry_chain(
    conn: sqlite3.Connection, theory_id: str, version: int
) -> list[int]:
    """The versions whose evidence pools with `version` (spec 2.5) --
    what `score.compute_score(pool="chain")` widens its segment filter
    over.

    Walks `theory_versions` backwards from `version`, and **keeps walking
    until an explicit `breaking` row stops it** (user ruling
    2026-08-31). A predecessor joins while the CURRENT version's own row
    says `kind='carry'` or `kind='continues'` -- that row is what links a
    version to its predecessor, so a row recorded at v3 (predecessor v2)
    pulls v2 in when walking from v3, not the other way round.

    Three things stop the walk: a `breaking` row, a missing predecessor,
    or no row at all. That last case is an unregistered version, whose
    relationship to its predecessor was never recorded -- unknown is not
    the same as continuous, and it resolves against pooling. `version`
    itself is always included, so a caller never has to special-case an
    isolated version. The result is ascending.

    A bump is no longer by itself a reason to discard evidence: a
    backtest run against an earlier version stays valid evidence for
    the current one unless a `breaking` bump says otherwise. See
    `bump_version` for why the default flipped.

    `bump_version` only ever writes a predecessor strictly less than the
    version being bumped to, so a well-formed table can never cycle. A
    row written outside `bump_version` (a raw INSERT, a hand-edited
    fixture) is not guaranteed that, and a cycle here would loop
    forever -- so each step is guarded: the predecessor named by the
    current version's row must be strictly older than it, and must not
    be a version already walked. Either violation raises `ValueError`
    naming the offending row rather than hanging or silently truncating
    the chain.
    """
    chain = [version]
    visited = {version}
    current = version
    while True:
        row = conn.execute(
            "SELECT kind, predecessor FROM theory_versions"
            " WHERE theory_id = ? AND version = ?",
            (theory_id, current),
        ).fetchone()
        if (row is None or row["kind"] == "breaking"
                or row["predecessor"] is None):
            break
        predecessor = row["predecessor"]
        if predecessor >= current or predecessor in visited:
            raise ValueError(
                f"malformed theory_versions row: {theory_id!r} v{current} "
                f"names predecessor {predecessor!r}, which is not strictly "
                "older than it -- carry_chain refuses to walk a cycle"
            )
        current = predecessor
        visited.add(current)
        chain.append(current)
    return sorted(chain)


#: Top-level decision-output fields `prove_carry` compares (spec 2.4). The
#: side lives on the parent `opportunities` row (`outcome`); everything
#: else lives on the attempt itself. `decision_date` and `entry_price` are
#: the replay's stored INPUTS, not outputs it proves, so neither is here.
_CARRY_FIELDS = (
    "outcome",
    "disposition",
    "model_prob",
    "confidence",
    "edge_pts_gross",
    "edge_pts_net",
    "edge_basis",
)

#: Compared with float tolerance; every other _CARRY_FIELDS entry (and
#: every extra.<key> field) is compared exactly.
_CARRY_NUMERIC_FIELDS = frozenset({"model_prob", "edge_pts_gross", "edge_pts_net"})

_CARRY_TOLERANCE = 1e-9

#: Sentinel for "this field was not present at all" -- distinct from an
#: explicit None, and distinct on both the recorded and the replayed side.
_MISSING = object()

_ABSENT_LABEL = "<absent>"

_MAX_DIVERGENCES = 50


def _row_extra(row: sqlite3.Row) -> dict:
    """An attempt row's extra-features dict, parsed from `extra_json`.

    Deliberately narrower than `slices._row_extra`, which also accepts a
    pre-parsed `extra` mapping key and falls back to `extra_json` only
    when that is absent -- this one accepts only `extra_json`, because
    `prove_carry`'s fixture is always a real `opportunity_attempts` row,
    which never carries a pre-parsed `extra` key. Duplicated rather than
    imported because `slices.py` already imports `theories`; importing it
    back here would invert that dependency.
    """
    raw = row["extra_json"] if "extra_json" in row.keys() else None
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _default_slice_extra_keys(
    conn: sqlite3.Connection, theory_id: str
) -> tuple[str, ...]:
    """Keys named by an `extra` clause in every slice registered on this
    theory (spec 2.8) -- the `extra_json` fields a carry proof must
    compare because a slice's membership depends on them, whatever its
    status."""
    keys: set[str] = set()
    for row in conn.execute(
        "SELECT predicate_json FROM theory_slices WHERE theory_id = ?",
        (theory_id,),
    ).fetchall():
        try:
            predicate = json.loads(row["predicate_json"])
        except (ValueError, TypeError):
            continue
        extra = predicate.get("extra") if isinstance(predicate, dict) else None
        if isinstance(extra, dict):
            keys.update(extra.keys())
    return tuple(sorted(keys))


def _carry_fields_equal(field: str, recorded, replayed) -> bool:
    """Compare one field's recorded value against `decide`'s replayed
    value. Either side may be `_MISSING`; both must be to count as equal.
    Numeric fields tolerate `_CARRY_TOLERANCE`; everything else compares
    exactly."""
    if recorded is _MISSING or replayed is _MISSING:
        return recorded is _MISSING and replayed is _MISSING
    if field in _CARRY_NUMERIC_FIELDS:
        if recorded is None or replayed is None:
            return recorded == replayed
        try:
            return abs(float(recorded) - float(replayed)) <= _CARRY_TOLERANCE
        except (TypeError, ValueError):
            return recorded == replayed
    return recorded == replayed


def prove_carry(
    conn: sqlite3.Connection,
    theory_id: str,
    from_version: int,
    decide: Callable[[sqlite3.Row], Mapping],
    *,
    slice_extra_keys: tuple[str, ...] | None = None,
    now: str | None = None,
) -> EquivalenceResult:
    """Replay `decide` over `from_version`'s own recorded attempts and
    report whether it reproduces every decision exactly (spec 2.4).

    The harness never decides anything itself -- `decide` is theory-
    supplied. It receives one joined attempt row (attempt columns plus
    the parent position's `kalshi_ticker`, `outcome`, and
    `position_kind`) and must not consult a fresh board -- point-in-time
    market state comes from snapshots (`tools/snapshot.py`), so the
    proof is reproducible offline. This function only selects the
    fixture, compares field-exactly, and reports: a carry claim earns
    its permission from the comparison, never from an assertion.

    The fixture is every attempt recorded against `(theory_id,
    from_version)` in the theory's real track record -- live and
    backtest, `lane='main'` only, so a variant being tried under
    `run_id="exp/..."` never feeds or blocks a carry proof. A backtest
    attempt whose run is recorded `tier='C'` in `backtest_runs` is
    excluded from the fixture entirely -- contaminated evidence proves
    nothing about equivalence, mirroring `segment_report`'s tier-C
    exclusion. A NULL tier or tier A/B is kept, and a live attempt
    (which never appears in `backtest_runs`) is unaffected.
    `slice_extra_keys` defaults to the keys every slice registered on
    this theory predicates on under its `extra` clause; the parameter
    exists so a test (or a slice-free theory) does not need one
    registered to exercise this path. A single divergence on any
    compared field -- including a key `decide` simply omitted -- fails
    the whole proof, whatever else matched.
    """
    if slice_extra_keys is None:
        slice_extra_keys = _default_slice_extra_keys(conn, theory_id)

    rows = conn.execute(
        """
        SELECT o.kalshi_ticker AS kalshi_ticker, o.outcome AS outcome,
               o.position_kind AS position_kind, a.*
          FROM opportunity_attempts a
          JOIN opportunities o ON o.id = a.opportunity_id
          LEFT JOIN backtest_runs br ON br.run_id = a.run_id
         WHERE o.theory_id = ? AND o.theory_version = ? AND o.lane = 'main'
           AND o.run_mode IN ('live', 'backtest')
           AND (br.tier IS NULL OR br.tier != 'C')
         ORDER BY a.decision_date, a.opportunity_id
        """,
        (theory_id, from_version),
    ).fetchall()

    divergences: list[tuple] = []
    n_divergent = 0

    for row in rows:
        replayed = decide(row)

        for field in _CARRY_FIELDS:
            recorded = row[field]
            replayed_value = replayed[field] if field in replayed else _MISSING
            if not _carry_fields_equal(field, recorded, replayed_value):
                n_divergent += 1
                if len(divergences) < _MAX_DIVERGENCES:
                    divergences.append((
                        row["opportunity_id"],
                        row["decision_date"],
                        field,
                        recorded,
                        _ABSENT_LABEL if replayed_value is _MISSING
                        else replayed_value,
                    ))

        recorded_extra = _row_extra(row)
        replayed_extra = replayed.get("extra")
        if not isinstance(replayed_extra, dict):
            replayed_extra = {}
        for key in slice_extra_keys:
            field = f"extra.{key}"
            recorded_value = (
                recorded_extra[key] if key in recorded_extra else _MISSING
            )
            replayed_value = (
                replayed_extra[key] if key in replayed_extra else _MISSING
            )
            if not _carry_fields_equal(field, recorded_value, replayed_value):
                n_divergent += 1
                if len(divergences) < _MAX_DIVERGENCES:
                    divergences.append((
                        row["opportunity_id"],
                        row["decision_date"],
                        field,
                        _ABSENT_LABEL if recorded_value is _MISSING
                        else recorded_value,
                        _ABSENT_LABEL if replayed_value is _MISSING
                        else replayed_value,
                    ))

    stamp = now or utcnow()
    label = (
        f"carry-proof/{theory_id}-v{from_version}-{stamp[:10].replace('-', '')}"
    )
    return EquivalenceResult(
        theory_id=theory_id,
        from_version=from_version,
        n_attempts=len(rows),
        divergences=tuple(divergences),
        n_divergent=n_divergent,
        label=label,
    )
