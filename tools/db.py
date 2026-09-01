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

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"
SNAP_SCHEMA_PATH = REPO_ROOT / "db" / "schema_snapshots.sql"
DEFAULT_DB_PATH = REPO_ROOT / "db" / "market_edge.db"


def utcnow() -> str:
    """Current UTC time as an ISO-8601 string, e.g. 2026-08-23T17:30:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshots_path_for(path: str | Path) -> Path:
    """The sibling snapshot-store file ATTACHed alongside `path` as snapdb.

    db/market_edge.db -> db/snapshots.db; any other name gets a
    <stem>.snapshots.db sibling so test databases never collide.
    """
    path = Path(path)
    if path.name == "market_edge.db":
        return path.with_name("snapshots.db")
    return path.with_name(path.stem + ".snapshots.db")


def connect(path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a connection with foreign keys enforced and named row access.

    WAL journalling lets a reader run concurrently with a writer, which the
    market connectors need; the busy timeout covers the brief moments when
    two writers do collide.

    The market-snapshot table lives in its own file, ATTACHed here as
    `snapdb` (spec 5.2 phase 4): the precious-and-small ledger and the
    large, re-fetchable history can then have different backup cadences.
    Every unqualified reference to `market_snapshots` elsewhere in this
    codebase resolves here because `main` no longer has a table of that
    name once a database is split -- see `init_db`'s refusal below for the
    unsplit case.

    `:memory:` is special-cased (several tests use it for a disposable
    schema): the attached side is its own private `:memory:` database
    rather than a computed sibling file, since ":memory:" is not a real
    path `snapshots_path_for` could derive a sibling from.
    """
    is_memory = str(path) == ":memory:"
    if is_memory:
        snap = ":memory:"
    else:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        snap = str(snapshots_path_for(path))
    conn = sqlite3.connect(":memory:" if is_memory else str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("ATTACH DATABASE ? AS snapdb", (snap,))
    conn.execute("PRAGMA snapdb.journal_mode = WAL")
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
    # A legacy ledger cannot simply be extended: its UNIQUE key still
    # contains run_id, so every write would land on the wrong identity and
    # the double-counting this migration exists to end would continue
    # silently. Fail loudly and name the fix.
    if has_legacy_position_key(conn):
        raise RuntimeError(
            "this database still keys opportunities on run_id, which "
            "double-counts a bet seen by two runs. Run "
            "`python -m tools.cli migrate-positions --dry-run` to see what "
            "would change, then drop --dry-run to apply it."
        )
    # The snapshot store lives in the attached file (spec 5.2 phase 4).
    # Unqualified references resolve there because main has no table of
    # that name -- which is exactly why an unsplit main is refused rather
    # than silently shadowing the attached one.
    _init_snap_schema(conn)
    unsplit = conn.execute(
        "SELECT 1 FROM main.sqlite_master WHERE type='table'"
        " AND name='market_snapshots'").fetchone()
    if unsplit is not None:
        n = conn.execute(
            "SELECT COUNT(*) FROM main.market_snapshots").fetchone()[0]
        if n:
            raise RuntimeError(
                "market_snapshots still lives in the main database file. "
                "Run `python -m tools.cli db split-snapshots` once to move "
                "it into db/snapshots.db -- refused here because a silent "
                "second copy in the attached file would shadow "
                f"{n} live rows."
            )
        with write(conn):
            conn.execute("DROP TABLE main.market_snapshots")
    # Runs BEFORE the schema script, which (pre-split) contained CREATE
    # UNIQUE INDEX on market_snapshots. A database holding the duplicates
    # the old non-unique index allowed would fail that statement and be
    # unable to open at all, so the duplicates have to go first. Harmless
    # after the split too -- see _dedupe_snapshots's own docstring.
    _dedupe_snapshots(conn)
    with write(conn):
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _migrate_theories(conn)
    _migrate_judgment_runs(conn)
    _migrate_theory_versions(conn)
    _migrate_lane_claims(conn)
    _add_column_if_missing(
        conn, "theories", "uses_llm_judgment", "INTEGER NOT NULL DEFAULT 0"
    )
    # Additive and nullable on purpose: a rate snapshot taken before
    # settlement days were counted has an UNKNOWN day count, not a zero.
    # `buckets.measured_gross` fails closed on unknown, so a legacy row
    # can never be mistaken for a measurement.
    _add_column_if_missing(conn, "bucket_rates", "n_days", "INTEGER")
    # Additive and nullable: a slice registered before the 2026-08-31
    # ruling declared no mining run because it did not have to -- under
    # the old default every backtest was in-sample anyway. NULL therefore
    # means "nothing declared", which is exactly right for those rows:
    # their oos_run_ids already say which replays were designated.
    _add_column_if_missing(conn, "theory_slices", "mined_from_run_ids", "TEXT")
    # Additive with a default that preserves meaning: every pre-existing
    # score row is the theory's own aggregate, which is what 'aggregate'
    # says. Sub-theory rows are new, never a reinterpretation of old ones.
    _add_column_if_missing(
        conn, "scores", "segment", "TEXT NOT NULL DEFAULT 'aggregate'"
    )
    # Additive and nullable: a score written before evidence could span
    # versions covered exactly the one version its row names, and a score
    # written before backtest rows were counted has an UNKNOWN backtest
    # share, not a zero.
    _add_column_if_missing(conn, "scores", "pooled_versions", "TEXT")
    _add_column_if_missing(conn, "scores", "n_backtest", "INTEGER")
    # Additive and nullable for the same reason: a capture taken before the
    # event envelope was kept has an UNKNOWN mutually_exclusive, not a
    # false one. Reading absent as false loses real structural_arb
    # violations; reading it as true manufactures riskless-looking baskets.
    _add_column_if_missing(conn, "market_snapshots", "event_json", "TEXT")
    _add_column_if_missing(conn, "market_snapshots", "last_seen_at", "TEXT")
    # Backfill: a pre-dedup row was seen exactly once, at its capture.
    with write(conn):
        conn.execute(
            "UPDATE market_snapshots SET last_seen_at = captured_at"
            " WHERE last_seen_at IS NULL"
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
    # Additive: absent this column, every pre-existing row's floor is
    # unknown, and 0.0 (no guaranteed floor) is exactly what a plain
    # single-outcome position or an existing basket already implied.
    _add_column_if_missing(
        conn, "opportunities", "min_payout", "REAL NOT NULL DEFAULT 0.0"
    )
    # Additive. The UNIQUE key that uses this column cannot be changed in
    # place -- `migrate_positions` rebuilds the table for that -- but the
    # column has to exist first so the migration can populate it.
    _add_column_if_missing(
        conn, "opportunities", "lane", "TEXT NOT NULL DEFAULT 'main'"
    )
    # Additive: no pre-existing score row ever scored a floor basket, so
    # every one of them truly had zero riskless positions -- these defaults
    # describe that history exactly, with no backfill needed.
    _add_column_if_missing(
        conn, "scores", "riskless_n", "INTEGER NOT NULL DEFAULT 0"
    )
    _add_column_if_missing(
        conn, "scores", "riskless_roi", "REAL"
    )
    # Additive and NULLABLE on purpose (ruling 2026-08-29). A stored score
    # row is a record of what was computed THEN; rewriting it is the
    # silent merge in storage form. So historical rows keep n_clusters
    # NULL, meaning "not computed under this semantics" -- never
    # backfilled, and never confused with a genuine cluster count of 0.
    _add_column_if_missing(conn, "scores", "n_clusters", "INTEGER")
    _add_column_if_missing(conn, "scores", "clustered_se", "REAL")


def _init_snap_schema(conn: sqlite3.Connection) -> None:
    """Create the snapshot table/index in the attached file if missing.

    executescript() runs against main, so the DDL is rewritten to target
    snapdb explicitly rather than trusting name resolution.
    """
    ddl = SNAP_SCHEMA_PATH.read_text(encoding="utf-8")
    ddl = ddl.replace("CREATE TABLE IF NOT EXISTS market_snapshots",
                      "CREATE TABLE IF NOT EXISTS snapdb.market_snapshots")
    ddl = ddl.replace("CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_unique",
                      "CREATE UNIQUE INDEX IF NOT EXISTS"
                      " snapdb.idx_snapshots_unique")
    with write(conn):
        conn.executescript(ddl)


def split_snapshots(conn: sqlite3.Connection, main_path: str | Path,
                    batch_rows: int = 50000) -> dict:
    """Move market_snapshots out of main into the attached snapdb file.

    One-time, explicit (never from init_db -- migrate_positions
    precedent). Copies in batches with per-batch commits (resumable: the
    copy is keyed on id, so a re-run continues past MAX(snapdb id)),
    then drops the main table and VACUUMs main to reclaim the bytes.
    """
    stats = {"moved": 0, "vacuumed_bytes_before": Path(main_path).stat().st_size}
    _init_snap_schema(conn)
    # Rerun-safety guard (review finding, 2026-08-30): once main no
    # longer has the table -- either a prior run already finished, or the
    # process died between the committed DROP TABLE and the VACUUM below
    # -- `PRAGMA main.table_info(market_snapshots)` returns an EMPTY
    # result with no error (a missing table is not a PRAGMA error), which
    # would make `col_list` "" and the INSERT below malformed SQL
    # (`OperationalError: near ")"`). Detecting the crash window
    # explicitly, rather than letting that syntax error be the symptom,
    # is what keeps the operator's obvious recovery step -- run
    # split-snapshots again -- actually resumable: VACUUM is idempotent,
    # so re-running it finishes whatever the interrupted run left undone.
    if conn.execute(
        "SELECT 1 FROM main.sqlite_master WHERE type='table'"
        " AND name='market_snapshots'"
    ).fetchone() is None:
        conn.execute("VACUUM main")
        stats["vacuumed_bytes_after"] = Path(main_path).stat().st_size
        stats["note"] = "main already split; vacuum only"
        return stats
    # A genuinely pre-unique-index legacy main table can still hold
    # duplicate rows the snapdb table's own unique index would reject
    # outright -- dedupe main's copy first so the bulk copy below can
    # never hit a UNIQUE constraint violation partway through a batch.
    # This is the "refusal path" _dedupe_snapshots's own docstring names:
    # the only route left to a database init_db has already refused.
    _dedupe_snapshots(conn)
    cols = [r[1] for r in conn.execute(
        "PRAGMA main.table_info(market_snapshots)")]
    col_list = ", ".join(cols)
    while True:
        top = conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM snapdb.market_snapshots"
        ).fetchone()[0]
        with write(conn):
            cur = conn.execute(
                f"INSERT INTO snapdb.market_snapshots ({col_list})"
                f" SELECT {col_list} FROM main.market_snapshots"
                f" WHERE id > ? ORDER BY id LIMIT ?", (top, batch_rows))
        if cur.rowcount == 0:
            break
        stats["moved"] += cur.rowcount
    with write(conn):
        conn.execute("DROP TABLE main.market_snapshots")
    conn.execute("VACUUM main")
    stats["vacuumed_bytes_after"] = Path(main_path).stat().st_size
    return stats


def close(conn: sqlite3.Connection) -> None:
    """Checkpoint both WALs, then close (spec 5.2 phase 4).

    A long session's WAL can hold hundreds of MB; TRUNCATE folds it into
    the database files so what sits on disk is the databases, not a
    journal a crash would have to replay.
    """
    try:
        conn.execute("PRAGMA main.wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA snapdb.wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _dedupe_snapshots(conn: sqlite3.Connection) -> None:
    """Make an older snapshot table safe for the unique index.

    Before that index existed, two saves landing in the same capture second
    each wrote a full set of rows, silently merging into one batch with every
    market duplicated. This removes those lowest-id-wins and drops the
    redundant non-unique index on the same three columns.

    A no-op on a fresh database (no table yet), on an already-migrated one,
    and -- after the split (spec 5.2 phase 4) -- on every database, full
    stop, because the query below is explicitly `main.sqlite_master`.
    Unlike an ordinary unqualified table reference (which SQLite resolves
    by searching main, then each ATTACHed database in turn), a bare or
    schema-qualified `sqlite_master` reference is never resolved that way
    -- `main.sqlite_master` names main's own catalog specifically and can
    never see a table that lives only in the attached snapdb file
    (confirmed behaviorally, spec 5.2 phase 4 review). So once a database
    is split, main's catalog no longer has a `market_snapshots` entry to
    find, and this becomes a permanent no-op -- the attached store is
    born deduped. Its legacy behavior survives intact for the one case
    that still matters: `split_snapshots` calls this on main's own copy,
    before the bulk copy into the attached (uniquely indexed) table, so a
    genuinely pre-unique-index database -- the only shape `init_db` still
    refuses over -- can be migrated without a mid-copy UNIQUE violation.
    """
    objects = {
        r[0] for r in conn.execute(
            "SELECT name FROM main.sqlite_master WHERE type IN ('table','index')"
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


def _migrate_theory_versions(conn: sqlite3.Connection) -> None:
    """Widen an old `theory_versions` kind CHECK to accept 'continues'.

    Databases created before the 2026-08-31 ruling carry the two-value
    CHECK ('breaking','carry') baked into their DDL, and `CREATE TABLE IF
    NOT EXISTS` will not touch an existing table. SQLite cannot alter a
    CHECK in place, so the table is rebuilt exactly as
    `_migrate_judgment_runs` rebuilds its own. Rows carry over unchanged:
    every legacy kind is still valid under the new set, and a bump
    recorded `breaking` keeps saying `breaking` until somebody
    deliberately reclassifies it (`theories.reclassify_bump`). Widening
    what MAY be recorded is not the same as rewriting what WAS.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='theory_versions'"
    ).fetchone()
    if row is None or "continues" in (row[0] or ""):
        return

    ddl = schema_statement("theory_versions")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.execute("BEGIN")
        try:
            conn.execute(
                "ALTER TABLE theory_versions RENAME TO theory_versions_legacy"
            )
            conn.execute(ddl)
            conn.execute(
                """
                INSERT INTO theory_versions
                    (theory_id, version, kind, predecessor, justification,
                     equivalence_run, created_at)
                SELECT theory_id, version, kind, predecessor, justification,
                       equivalence_run, created_at
                FROM theory_versions_legacy
                """
            )
            conn.execute("DROP TABLE theory_versions_legacy")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    finally:
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.execute("PRAGMA foreign_keys = ON")


def _lane_check_values(ddl: str) -> set[str]:
    """The lane names a `lane_claims` DDL's CHECK constraint accepts."""
    import re

    m = re.search(r"CHECK\s*\(\s*lane\s+IN\s*\((.*?)\)", ddl or "",
                  re.DOTALL | re.IGNORECASE)
    if not m:
        return set()
    return set(re.findall(r"'([^']*)'", m.group(1)))


def _migrate_lane_claims(conn: sqlite3.Connection) -> None:
    """Widen an old `lane_claims` lane CHECK to whatever schema.sql accepts.

    `CREATE TABLE IF NOT EXISTS` will not touch an existing table, so a
    database created before a lane existed keeps the narrower CHECK in its
    DDL and rejects claims on the new lane outright. Rebuilt exactly as
    `_migrate_theory_versions` rebuilds its own; every legacy row is still
    valid under the wider set.

    **The trigger is a comparison against schema.sql, not a sentinel lane
    name.** It used to short-circuit on `"find-theories" in ddl`, which
    meant the migration stopped firing the moment that one lane landed:
    `study` was then added to `tools.lanes.LANES` and to schema.sql's
    successor without any database ever widening, so `lane claim --lane
    study` raised a bare `sqlite3.IntegrityError` in every database, new
    and old alike. Diffing the accepted sets makes each future lane
    migrate itself.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='lane_claims'"
    ).fetchone()
    if row is None:
        return

    ddl = schema_statement("lane_claims")
    if not (_lane_check_values(ddl) - _lane_check_values(row[0] or "")):
        return
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.execute("BEGIN")
        try:
            conn.execute(
                "ALTER TABLE lane_claims RENAME TO lane_claims_legacy")
            conn.execute(ddl)
            conn.execute(
                """
                INSERT INTO lane_claims
                    (id, lane, session, focus, claimed_at, released_at,
                     summary, joined, join_reason)
                SELECT id, lane, session, focus, claimed_at, released_at,
                       summary, joined, join_reason
                FROM lane_claims_legacy
                """
            )
            conn.execute("DROP TABLE lane_claims_legacy")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lane_claims_open"
                " ON lane_claims(lane, released_at)"
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


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone() is not None


def _decision_day(row: sqlite3.Row) -> str:
    """The as-of day of a legacy row's decision.

    `extra_json.entry_day_iso` is what the theory recorded as the day it was
    deciding about; `first_seen_at` is wall-clock recording time and is a
    fallback only. Using the recording time would split one decision
    recorded by two runs an hour apart into two attempts.
    """
    raw = row["extra_json"]
    if raw:
        try:
            day = json.loads(raw).get("entry_day_iso")
            if day:
                return str(day)[:10]
        except (ValueError, TypeError, AttributeError):
            pass
    return str(row["first_seen_at"])[:10]


def _ordered(group: list[sqlite3.Row]) -> list[sqlite3.Row]:
    """One duplicate group, oldest decision first.

    The same order the position row's rollup and the attempt table use:
    the day the theory was deciding about, then wall-clock recording time
    to break a tie within a day.
    """
    return sorted(group, key=lambda r: (_decision_day(r), r["last_seen_at"]))


def _rollup(
    group: list[sqlite3.Row],
) -> tuple[sqlite3.Row, str | None, int | None, sqlite3.Row | None]:
    """Pick the surviving row's values for one duplicate group.

    First sighting owns price **and** edge, with no exception, so the pair
    can never be mismatched -- which is what keeps
    `score._single_leg_observations` correct with no change to its SELECT
    (position-identity spec section 4.4). An `edge_pts_net` computed
    against a later, worse ask sitting on the earliest ask is exactly the
    mismatch that rule exists to forbid, so the research override below
    stops at the three research columns and never reaches the edge.

    Two things are deliberately taken from a row other than the earliest:

    - The judgment -- `confidence` AND the `judged_blind` that belongs with
      it (attempt-fidelity spec section 8c), from the LATEST attempt
      carrying a label. Taking the label from the latest attempt that
      carried one is what stops a merge from deleting a confidence recorded
      by a later judged run; leaving the blind flag on the earliest row's
      value would label a position `strong` while claiming nothing is known
      about how it was judged.
    - The stage-2 research, from the EARLIEST attempt carrying an
      interpretation. `interpretation` and `interpreted_at` are
      position-only by design (spec section 7), so unlike every other
      varying field they have no attempt row to fall back on: taking the
      earliest row's NULLs would lose a verdict outright rather than merely
      un-cache it. Earliest-*interpreted* rather than simply earliest, so a
      group first judged by a later pass still keeps its verdict.

      Earliest rather than latest because a re-proposal is a judgment of a
      *different price*, not a revision of the one the position holds: the
      two live money positions in the ledger were endorsed at 0.73 and 0.75
      and then declined a day later at 0.77 and 0.94, and latest-wins
      flipped both to `rejected` -- corrupting the endorsed/rejected control
      group at precisely the rows carrying money. The later verdict is not
      lost: it is on its own attempt row, in the backup table, and named in
      `migrate_positions`' report.

    Returns (earliest, label, judged_blind, researched-or-None).
    """
    ordered = _ordered(group)
    earliest = ordered[0]
    judged = [r for r in ordered if r["confidence"]]
    label = judged[-1]["confidence"] if judged else None
    blind = judged[-1]["judged_blind"] if judged else earliest["judged_blind"]
    interpreted = [r for r in ordered if r["interpretation"]]
    return earliest, label, blind, (interpreted[0] if interpreted else None)


def _superseded(group: list[sqlite3.Row]) -> dict | None:
    """What verdict this group drops, named -- or None if it drops none.

    A group holding two interpreted rows keeps the earlier verdict
    (`_rollup`) and supersedes every later one. That is a judgement call
    about somebody's research, so it is reported by name rather than by
    count: a decision like this has to be visible while it is still
    reversible, and "21 interpretations superseded" is not something anyone
    can check. When a group holds more than two, the last one -- the verdict
    a latest-wins rule would have kept -- is the one named.
    """
    interpreted = [r for r in _ordered(group) if r["interpretation"]]
    if len(interpreted) < 2:
        return None
    kept, dropped = interpreted[0], interpreted[-1]
    return {
        "theory_id": kept["theory_id"],
        "kalshi_ticker": kept["kalshi_ticker"],
        "outcome": kept["outcome"],
        "disposition_kept": kept["disposition"],
        "disposition_dropped": dropped["disposition"],
        "has_fill": _fill_row(group) is not None,
    }


def _fill_row(group: list[sqlite3.Row]) -> sqlite3.Row | None:
    """The taken row whose money becomes this position's single fill.

    Shared by the counting pass and the rebuild so a dry run reports on
    exactly the row the real run would write.
    """
    taken = [r for r in group if r["user_action"] == "taken"]
    return max(taken, key=lambda r: r["last_seen_at"]) if taken else None


def has_legacy_position_key(conn: sqlite3.Connection) -> bool:
    """True if `opportunities` still carries run_id in its UNIQUE key."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='opportunities'"
    ).fetchone()
    if row is None:
        return False
    return "run_id, kalshi_ticker" in " ".join((row[0] or "").split())


# Every `opportunity_attempts` column copied straight across from the legacy
# row of the same name (attempt-fidelity spec section 4). The four not
# listed are the ones with no same-named source: `opportunity_id` (the
# surviving position), `decision_date` (derived), `run_id` (already the key
# the group is split on) and `recorded_at` (the legacy table has no
# per-attempt recording time, so `last_seen_at` stands in).
#
# The INSERT below builds its column list and its value list from this one
# tuple, in this one order, so the two cannot fall out of alignment.
_ATTEMPT_COPIED = (
    "scan_id", "entry_price", "spread_at_call", "volume_at_call",
    "model_prob", "edge_pts_gross", "fee_pts", "edge_pts_net", "edge_basis",
    "disposition", "confidence", "judged_blind", "rationale",
    "suggested_size", "evidence_source", "evidence_market_id", "extra_json",
)


# How many superseded verdicts `migrate_positions` names before it stops
# and leaves the rest to the count beside them. The list is for a human
# reading CLI output; past this it stops being readable and the count is
# the honest summary.
_SUPERSEDED_CAP = 50


def _restore_sequence_ceiling(
    conn: sqlite3.Connection, table: str, minimum: int
) -> None:
    """Ensure AUTOINCREMENT on `table` never hands out an id below `minimum`.

    A rebuild that only re-inserts a group's SURVIVING id can leave
    `sqlite_sequence` tracking the highest id actually re-inserted -- lower
    than the highest id the table ever handed out whenever the row holding
    that max id lost its dedup group and was dropped. Left alone, the next
    row written reuses an id a backup table already assigned to something
    else. Never lowers the ceiling -- only ever raises it to `minimum`.
    """
    if minimum <= 0:
        return
    existing = conn.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)",
            (table, minimum),
        )
    elif existing["seq"] < minimum:
        conn.execute(
            "UPDATE sqlite_sequence SET seq = ? WHERE name = ?",
            (minimum, table),
        )


def migrate_positions(
    conn: sqlite3.Connection, dry_run: bool = False
) -> dict:
    """Collapse run-scoped opportunity rows into positions with attempts.

    `opportunities` was keyed on run_id, so one bet re-recorded by a second
    run became two rows: pooled scoring counted it twice, and `times_seen`
    never incremented. This rebuilds the table under the position-scoped key
    and turns every duplicate row into an attempt, at the full column parity
    the attempt table declares -- the pre-migration rows are in hand while
    this runs, so every rationale and every extra_json feature lands in
    `opportunity_attempts` rather than only in a backup table nothing
    queries.

    Deliberately not run from `init_db`. Unlike `_migrate_theories`, which
    carries every row over unchanged, this one deletes rows, and a
    row-collapsing migration that fires unattended on whatever database
    happens to be opened is the kind of thing you only get to be wrong about
    once.

    Idempotent in the strong sense: on an already-migrated database this
    reports the current shape and does nothing at all. Rebuilding there
    would be worse than useless -- it would re-derive attempts from the
    *collapsed* rows, so a position holding two real attempts would come
    back holding one, and the before/after counts would still match.
    """
    stats: dict = {
        "before": 0, "after": 0, "attempts": 0, "labels_preserved": 0,
        "legs_repointed": 0, "fills_backfilled": 0,
        "superseded_interpretation_count": 0,
        "superseded_interpretations": [], "takes_missing_size": 0,
        "backup_table": None,
    }
    if not has_legacy_position_key(conn):
        if not _table_exists(conn, "opportunities"):
            return stats
        stats["before"] = stats["after"] = conn.execute(
            "SELECT COUNT(*) FROM opportunities"
        ).fetchone()[0]
        stats["labels_preserved"] = conn.execute(
            "SELECT COUNT(*) FROM opportunities WHERE confidence IS NOT NULL"
        ).fetchone()[0]
        if _table_exists(conn, "opportunity_attempts"):
            stats["attempts"] = conn.execute(
                "SELECT COUNT(*) FROM opportunity_attempts"
            ).fetchone()[0]
        return stats

    rows = conn.execute("SELECT * FROM opportunities").fetchall()
    stats["before"] = len(rows)
    # Captured now, before the table is renamed and dropped: the rebuild
    # below only ever re-inserts a group's SURVIVING id, so a row that lost
    # its dedup never lands in the new table again and SQLite's own
    # AUTOINCREMENT bookkeeping only sees what actually got re-inserted --
    # which can be lower than the highest id this table ever handed out.
    pre_migration_max_id = max((r["id"] for r in rows), default=0)

    groups: dict[tuple, list[sqlite3.Row]] = {}
    for row in rows:
        run_id = row["run_id"]
        lane = run_id if run_id.startswith("exp/") else "main"
        key = (
            row["theory_id"], row["theory_version"], row["run_mode"], lane,
            row["kalshi_ticker"], row["outcome"],
        )
        groups.setdefault(key, []).append(row)

    stats["after"] = len(groups)
    stats["attempts"] = sum(
        len({(_decision_day(r), r["run_id"]) for r in g})
        for g in groups.values()
    )
    stats["labels_preserved"] = sum(
        1 for g in groups.values() if any(r["confidence"] for r in g)
    )
    # A merge keeps the earliest interpreted row's verdict; every later one
    # is superseded. Those verdicts are not lost -- each is on its own
    # attempt row and in the backup table -- but nobody will know to look
    # unless the migration says which positions they were, so they are
    # NAMED here, in the pass a dry run also makes, while the decision is
    # still reversible. Positions holding money sort first so the cap can
    # never be what hides one.
    superseded = [s for g in groups.values() if (s := _superseded(g)) is not None]
    superseded.sort(
        key=lambda s: (not s["has_fill"], s["kalshi_ticker"], s["outcome"])
    )
    stats["superseded_interpretation_count"] = len(superseded)
    stats["superseded_interpretations"] = superseded[:_SUPERSEDED_CAP]
    # opportunity_fills.size is NOT NULL, so a taken row carrying no
    # user_size would raise IntegrityError halfway through the rebuild.
    # Counted before the transaction so a dry run can warn, and refused
    # below rather than discovered mid-flight.
    sizeless = [
        g for g in groups.values()
        if (row := _fill_row(g)) is not None and row["user_size"] is None
    ]
    stats["takes_missing_size"] = len(sizeless)
    if dry_run:
        return stats
    if sizeless:
        names = ", ".join(
            sorted(_fill_row(g)["kalshi_ticker"] for g in sizeless)[:5]
        )
        raise ValueError(
            f"{len(sizeless)} taken position(s) have no user_size, and a "
            f"fill must have one: {names}"
            f"{' ...' if len(sizeless) > 5 else ''}. Set the size with "
            f"`opportunities mark-taken <id> taken --theory <slug> "
            f"--size <N>` first -- "
            f"refused here rather than raising IntegrityError partway "
            f"through the rebuild."
        )

    stamp = utcnow().replace("-", "").replace(":", "").replace("Z", "")
    backup = f"opportunities_premigration_{stamp}"

    columns = [r[1] for r in conn.execute("PRAGMA table_info(opportunities)")]
    ddl = schema_statement("opportunities")
    attempts_ddl = schema_statement("opportunity_attempts")
    # The live database holds only `opportunities` and `opportunity_legs`,
    # and the taken rows below are written as fills, so the fills table has
    # to be created here -- nothing else will have made it by then
    # (attempt-fidelity spec section 8a).
    fills_ddl = schema_statement("opportunity_fills")

    # `lane` and `id` are appended explicitly rather than copied. `lane` so
    # this works whether or not the legacy table already had the column;
    # `id` because the surviving row keeps the id it already had. A rebuilt
    # AUTOINCREMENT table restarts at 1 and hands out ids that legacy rows
    # still hold, which would make repointing legs by id move rows
    # belonging to another group -- and ids are cited outside the database,
    # in campaign write-ups and notes.
    shared = [c for c in columns if c not in ("id", "lane")]
    insert_sql = (
        f"INSERT INTO opportunities ({', '.join(shared + ['lane', 'id'])})"
        f" VALUES ({', '.join('?' for _ in shared)}, ?, ?)"
    )
    copied = [c for c in _ATTEMPT_COPIED if c in columns]
    attempt_cols = [
        "opportunity_id", "decision_date", "run_id", "recorded_at", *copied
    ]
    attempt_sql = (
        f"INSERT INTO opportunity_attempts ({', '.join(attempt_cols)})"
        f" VALUES ({', '.join('?' for _ in attempt_cols)})"
        " ON CONFLICT (opportunity_id, decision_date, run_id) DO NOTHING"
    )

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA legacy_alter_table = ON")
    try:
        conn.execute("BEGIN")
        try:
            # The backup comes first, and everything destructive happens
            # after it inside the same transaction -- so a failure anywhere
            # below leaves the database exactly as it was found.
            conn.execute(
                f"CREATE TABLE {backup} AS SELECT * FROM opportunities"
            )
            conn.execute(
                f"CREATE TABLE {backup}_legs AS SELECT * FROM opportunity_legs"
            )
            conn.execute(
                "ALTER TABLE opportunities RENAME TO opportunities_legacy"
            )
            conn.execute(ddl)
            conn.execute(attempts_ddl)
            conn.execute(fills_ddl)
            # Both tables are created here rather than by the schema
            # script, so their indexes are this migration's job too --
            # without idx_attempts_run every per-run consumer query
            # full-scans 9,732 attempts until the next init_db.
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_attempts_run"
                " ON opportunity_attempts(run_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fills_opportunity"
                " ON opportunity_fills(opportunity_id)"
            )

            for key, group in groups.items():
                lane = key[3]
                earliest, label, blind, research = _rollup(group)
                survivor = earliest["id"]
                seen = {(_decision_day(r), r["run_id"]) for r in group}

                # Money the user already recorded becomes a fill, so the
                # rollup on the surviving row stays true and roi_taken keeps
                # seeing it. Undated in the legacy schema -- there was no
                # take-date column -- so last_seen_at is the best available
                # stand-in.
                skipped = [r for r in group if r["user_action"] == "skipped"]
                fill_row = _fill_row(group)
                money = fill_row or (
                    max(skipped, key=lambda r: r["last_seen_at"])
                    if skipped else None
                )

                values = [earliest[c] for c in shared]
                # The judgment and the blind flag that belongs with it are
                # the fields taken from a later row (spec section 8c).
                values[shared.index("confidence")] = label
                values[shared.index("judged_blind")] = blind
                values[shared.index("times_seen")] = len(seen)
                values[shared.index("last_seen_at")] = max(
                    r["last_seen_at"] for r in group
                )
                # The money rollup is recomputed from what became a fill,
                # never copied off the earliest row (spec section 8d): a
                # later `taken` row must not land as an `untouched` position
                # holding a fill, and `user_size` is the sum of the fills,
                # which is nothing when there are none.
                values[shared.index("user_action")] = (
                    money["user_action"] if money else "untouched"
                )
                values[shared.index("user_size")] = (
                    fill_row["user_size"] if fill_row else None
                )
                if money is not None:
                    values[shared.index("user_reason")] = money["user_reason"]
                # `edge_pts_net` is NOT in this list: price and edge move
                # together from the earliest attempt (spec section 4.4), so
                # an edge computed against a later ask can never land on
                # the first-sighting price.
                if research is not None:
                    for column in (
                        "disposition", "interpretation", "interpreted_at",
                    ):
                        values[shared.index(column)] = research[column]
                conn.execute(insert_sql, values + [lane, survivor])

                if fill_row is not None:
                    conn.execute(
                        """
                        INSERT INTO opportunity_fills (
                            opportunity_id, filled_on, size, price, reason,
                            recorded_at
                        ) VALUES (?, ?, ?, NULL, ?, ?)
                        """,
                        (
                            survivor, str(fill_row["last_seen_at"])[:10],
                            fill_row["user_size"], fill_row["user_reason"],
                            fill_row["last_seen_at"],
                        ),
                    )
                    stats["fills_backfilled"] += 1

                for row in group:
                    conn.execute(
                        attempt_sql,
                        [
                            survivor, _decision_day(row), row["run_id"],
                            row["last_seen_at"],
                            *(row[c] for c in copied),
                        ],
                    )
                    if row["id"] == survivor:
                        continue
                    # Legs are repointed BEFORE the legacy table goes.
                    # opportunity_legs is ON DELETE CASCADE, so dropping the
                    # losing row of a merged basket would silently eat its
                    # legs. OR IGNORE covers the other half of a merge: both
                    # rows of one basket describe the same legs at the same
                    # indexes and (opportunity_id, leg_index) is the primary
                    # key, so the survivor's copy stands and the loser's
                    # duplicate is dropped rather than colliding.
                    stats["legs_repointed"] += conn.execute(
                        "UPDATE OR IGNORE opportunity_legs"
                        " SET opportunity_id = ? WHERE opportunity_id = ?",
                        (survivor, row["id"]),
                    ).rowcount
                    conn.execute(
                        "DELETE FROM opportunity_legs WHERE opportunity_id = ?",
                        (row["id"],),
                    )

            conn.execute("DROP TABLE opportunities_legacy")
            # The rename carried the old table's indexes with it and the
            # drop took them along; CREATE TABLE does not bring them back,
            # and a `CREATE INDEX IF NOT EXISTS` before the drop would have
            # been silently skipped while the names were still taken.
            # Restore what this migration destroyed; indexes on the tables
            # it created are the schema script's job, as for any new table.
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_opportunities_theory"
                " ON opportunities"
                " (theory_id, theory_version, run_mode, disposition)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_opportunities_ticker"
                " ON opportunities (kalshi_ticker)"
            )
            # Restore the ceiling explicitly. Left alone, sqlite_sequence
            # tracks only the highest SURVIVOR id the loop above actually
            # re-inserted -- lower than the pre-migration max whenever the
            # row holding that max id lost its dedup group -- and the next
            # position written would be handed an id the backup table
            # already assigned to a different market. Ids are preserved on
            # purpose (they are cited in campaign write-ups and notes), so
            # handing a deleted one to a different market defeats that.
            _restore_sequence_ceiling(
                conn, "opportunities", pre_migration_max_id
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    finally:
        conn.execute("PRAGMA legacy_alter_table = OFF")
        conn.execute("PRAGMA foreign_keys = ON")

    stats["backup_table"] = backup
    return stats
