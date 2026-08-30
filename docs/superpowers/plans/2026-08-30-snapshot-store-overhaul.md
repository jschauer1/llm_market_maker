# Snapshot Store Overhaul Implementation Plan (spec §5.2 phases 2–4, sequencing phase 8)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the snapshot store's ~1.3–1.8 GB/active-day growth with zero information loss: dedup unchanged rows on write, retro-dedup history, zlib-compress payloads, and split `market_snapshots` into its own `db/snapshots.db` with per-file backup cadence, `db stats`, and a WAL checkpoint on close.

**Architecture:** A snapshot row gains a `[captured_at, last_seen_at]` validity interval. A pull that finds a market's payload byte-identical to its latest stored row extends that row's interval instead of inserting; the board becomes "rows carrying the latest pull stamp" instead of "rows sharing one `captured_at`". Payload columns become type-sniffed dual-format (TEXT = plain JSON, BLOB = zlib), read only through one decode helper. Finally the table moves to an `ATTACH`ed second database file, resolved unqualified so no query changes.

**Tech Stack:** Python 3 stdlib only (`sqlite3`, `zlib`, `hashlib`, `json`); pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-29-enforcing-surfaces-design.md` §5.2 (read the whole section, including the corrections block and the design gate). The design gate was already run (commit `6fe567a`, RESEARCH_LOG 2026-08-29 "Storage design gate measured"): **byte-exact dedup on full `raw_json`+`event_json` is 38.8%, no field exclusions are justified** — "unchanged" in this plan always means byte-exact on both payload columns, never the five material columns.

## Global Constraints

- **Zero information loss.** Every payload byte remains recoverable; retro-dedup deletes only rows byte-identical to their immediate predecessor for the same market, and the predecessor's interval absorbs the deleted row's stamp. "save as much as you can, while you can" (CLAUDE.md) stays true.
- **The four fidelity tests keep their assertions and fixtures at every phase** (spec §5.2 safety net): `tests/test_board.py::test_cache_and_fetch_boards_are_identical_raw_included`, `::test_rebuilt_board_matches_the_fetched_one`, `::test_uncommon_fields_survive_the_cache_round_trip`, `::test_snapshot_stores_the_complete_raw_payload`. One sanctioned mechanical exception, ruled by the controller from the spec's own phase-3 clause ("repoints every tools/ and tests/ reader through it"): a fidelity test that `SELECT`s `raw_json` directly may route that read through the decode helper in Task 4 — its fixture and its assertion do not change.
- **Only three tests may change meaning, and only in Task 2** (spec §5.2 phase 2): `test_re_saving_updates_rather_than_duplicating`, `test_separate_seconds_are_separate_batches`, `test_board_info_uses_only_the_freshest_batch`. Keep each test's *intent* while its fixture/assertions update.
- **Long-running data migrations write incrementally and resume** (CLAUDE.md data conventions): batched commits, idempotent re-runs, never memory-only with one final write.
- **Destructive migrations never fire from `init_db`** (precedent: `migrate_positions` in `tools/db.py`). Retro-dedup, retro-compress, and the split are explicit CLI commands; `init_db` only adds columns, backfills `last_seen_at`, and — after Task 5 — refuses loudly on an unsplit nonempty database, naming the command to run.
- **No theory version bumps.** Nothing here changes any theory's decision procedure; board reuse semantics changes are storage-layer (the §5.3 force-floor precedent).
- **Live-DB operations run only after Task 1's fresh backup exists** and never concurrently with another writing session. This session is currently the repo's only live session; re-verify with `ListAgents` (controller does this) before Tasks 3–5's live runs.
- Prices/timestamps conventions unchanged. Commits on master, one per task step where marked, each ending `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. `git add` only named files. The untracked `studies/2026-08-29-series-bias-mining/data/` is a third session's — never touch or stage it.
- Windows: all file I/O `encoding="utf-8"`; no PowerShell text cmdlets or sed on repo files.

## Measured baseline (2026-08-30, live DB)

1,390,328 rows, all `kalshi`, 13 batches, db file 5,539,033,088 bytes; 38 GB free on the target volume; suite 1,095 green. Re-measure in Task 1; quote the Task 1 numbers thereafter.

## File structure

- `tools/snapshot.py` — dedup-aware `_save` core; `payload_text()` decode helper; write-path compression; `dedup_history()` and `compress_history()` batch migrations (they live here because the snapshot store is this module's single responsibility; `tools/db.py` keeps only schema/connection concerns).
- `tools/board.py` — `board_info()` and `_rebuild()` move to `last_seen_at` semantics.
- `tools/db.py` — `last_seen_at` additive migration; in Task 5: `ATTACH` in `connect()`, snapshots-schema execution, unsplit-DB refusal, `split_snapshots()`, `close()` with WAL checkpoint.
- `db/schema.sql` — gains `last_seen_at` in the `market_snapshots` DDL (Task 2); loses the whole `market_snapshots` block to `db/schema_snapshots.sql` (Task 5).
- `tools/cli.py` — `db dedup-snapshots | compress-snapshots | split-snapshots | stats` under the existing `db` group (`_cmd_db`, parser at ~line 696).
- `tests/test_snapshot.py`, `tests/test_board.py` — updated per constraints; `tests/test_snapshot_store.py` — new, for the helper, migrations, split, and stats.
- 4 study write-ups + `tools/README.md` — one-line notes and the backup-cadence ruling.

---

### Task 1: Fresh ledger backup and baseline measurement (ops; no repo commit)

**Files:** none modified — this task produces a backup file outside the repo and a numbers block in the task report.

**Interfaces:**
- Produces: a dated backup in `%LOCALAPPDATA%\market_edge\backups\`, and the baseline numbers (rows, batches, db bytes, per-column payload bytes, consecutive byte-dup count) later tasks quote.

- [ ] **Step 1: Run the backup.**

```bash
python -m tools.cli db backup
```

Expected: JSON output naming the created `.db.gz` under `%LOCALAPPDATA%\market_edge\backups\`. Verify the file exists and is >10 MB.

- [ ] **Step 2: Measure the baseline** (read-only; ~1–2 min on 1.4M rows):

```bash
python - <<'EOF'
import sqlite3
conn = sqlite3.connect(r"db\market_edge.db")
c = conn.cursor()
print("rows", c.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0])
print("batches", c.execute("SELECT COUNT(DISTINCT captured_at) FROM market_snapshots").fetchone()[0])
print("raw bytes", c.execute("SELECT SUM(LENGTH(CAST(raw_json AS BLOB))) FROM market_snapshots").fetchone()[0])
print("event bytes", c.execute("SELECT SUM(LENGTH(CAST(event_json AS BLOB))) FROM market_snapshots").fetchone()[0])
dups = c.execute("""
    WITH o AS (SELECT market_id, raw_json, event_json,
                      LAG(raw_json) OVER w pr, LAG(event_json) OVER w pe
               FROM market_snapshots WHERE platform='kalshi'
               WINDOW w AS (PARTITION BY market_id ORDER BY captured_at))
    SELECT COUNT(*) FROM o WHERE raw_json = pr
       AND (event_json = pe OR (event_json IS NULL AND pe IS NULL))
""").fetchone()[0]
print("consecutive byte-dups", dups)
EOF
```

Expected: dup count ≈ 38–39% of rows (the design-gate figure). Record all numbers in the report; they are Task 3's and Task 6's before/after basis.

### Task 2: `last_seen_at` + dedup on write + board semantics

**Files:**
- Modify: `db/schema.sql:50-78` (add column to DDL + comment), `tools/db.py:59-133` (`init_db` additive migration + backfill), `tools/snapshot.py` (whole save path), `tools/board.py:56-120` (`board_info`, `_rebuild`)
- Test: `tests/test_snapshot.py`, `tests/test_board.py`, new `tests/test_snapshot_store.py`

**Interfaces:**
- Produces: `market_snapshots.last_seen_at TEXT` (backfilled `= captured_at`); `save_kalshi`/`save_polymarket` with unchanged→UPDATE semantics; `board_info()` whose `captured_at` key now carries `MAX(last_seen_at)` (the latest pull stamp) and whose `markets` counts rows holding that stamp; `_rebuild(conn, stamp)` selecting `last_seen_at = stamp`. Tasks 3–5 rely on exactly these semantics.

- [ ] **Step 1: Write the new failing tests** in `tests/test_snapshot_store.py`:

```python
import json

import pytest

from tools import board, db, snapshot
from tools.kalshi import markets as kalshi_markets

NOW = "2026-08-24T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def _mk(ticker, **kw):
    raw = {
        "ticker": ticker, "event_ticker": "EV", "series_ticker": "KXTHING",
        "title": f"title {ticker}", "status": "active",
        "close_time": "2026-09-01T00:00:00Z",
        "yes_bid_dollars": "0.80", "yes_ask_dollars": "0.82",
        "no_bid_dollars": "0.18", "no_ask_dollars": "0.20",
        "volume_fp": "900", "open_interest_fp": "500",
    }
    raw.update(kw)
    return kalshi_markets.normalize(raw)


def test_unchanged_resave_extends_the_interval_instead_of_inserting(conn):
    # The 56.5%-measured waste (spec 5.2): a market that moved nothing
    # used to write a full new row every pull. Now the existing row's
    # validity interval absorbs the pull.
    snapshot.save_kalshi(conn, [_mk("T-0")], now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0")], now=NOW)
    rows = conn.execute(
        "SELECT captured_at, last_seen_at FROM market_snapshots"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["captured_at"] == "2026-08-24T11:00:00Z"
    assert rows[0]["last_seen_at"] == NOW


def test_changed_payload_still_inserts_a_new_row(conn):
    snapshot.save_kalshi(conn, [_mk("T-0")], now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0", yes_ask_dollars="0.90")], now=NOW)
    rows = conn.execute(
        "SELECT captured_at, last_seen_at FROM market_snapshots"
        " ORDER BY captured_at"
    ).fetchall()
    assert len(rows) == 2
    # The old row's interval is NOT extended by a changed pull.
    assert rows[0]["last_seen_at"] == "2026-08-24T11:00:00Z"
    assert rows[1]["captured_at"] == rows[1]["last_seen_at"] == NOW


def test_unchanged_only_means_byte_exact_full_payload(conn):
    # Design gate (6fe567a): rules text, close_time — everything — counts.
    # A change in a field no material column carries must still insert.
    snapshot.save_kalshi(conn, [_mk("T-0", rules_primary="old rules")],
                         now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0", rules_primary="NEW rules")],
                         now=NOW)
    n = conn.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0]
    assert n == 2


def test_out_of_order_stamp_never_regresses_last_seen_at(conn):
    # Tests pass historical now= stamps; an "unchanged" save with an older
    # stamp must not shrink the interval or collapse history.
    snapshot.save_kalshi(conn, [_mk("T-0")], now=NOW)
    snapshot.save_kalshi(conn, [_mk("T-0")], now="2026-08-23T12:00:00Z")
    rows = conn.execute(
        "SELECT captured_at, last_seen_at FROM market_snapshots"
        " ORDER BY captured_at"
    ).fetchall()
    assert len(rows) == 2          # older stamp inserts as history
    assert rows[1]["last_seen_at"] == NOW


def test_point_in_time_resolves_via_the_interval(conn):
    # The structural-gate guarantee (spec 5.2): market text at time T is
    # the row whose [captured_at, last_seen_at] spans T.
    snapshot.save_kalshi(conn, [_mk("T-0", rules_primary="v1")],
                         now="2026-08-24T10:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0", rules_primary="v1")],
                         now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0", rules_primary="v2")], now=NOW)
    t = "2026-08-24T10:30:00Z"
    row = conn.execute(
        "SELECT raw_json FROM market_snapshots"
        " WHERE platform='kalshi' AND market_id='T-0'"
        "   AND captured_at <= ? AND last_seen_at >= ?",
        (t, t),
    ).fetchone()
    assert json.loads(row["raw_json"])["rules_primary"] == "v1"


def test_board_reports_the_pull_even_when_nothing_changed(conn):
    # A pull where every market is unchanged writes no row; the board must
    # still be that pull: full size, fresh age.
    snapshot.save_kalshi(conn, [_mk("T-0"), _mk("T-1")],
                         now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, [_mk("T-0"), _mk("T-1")], now=NOW)
    info = board.board_info(conn, now=NOW)
    assert info["markets"] == 2
    assert info["age_minutes"] == pytest.approx(0.0)
    got = board.get_board(conn, now=NOW)
    assert sorted(m.ticker for m in got) == ["T-0", "T-1"]


def test_mixed_pull_rebuilds_current_rows_only(conn):
    # One market changed, one didn't, one left the board: the rebuilt
    # board is exactly the pull's two markets at their current payloads.
    snapshot.save_kalshi(
        conn, [_mk("T-0"), _mk("T-1"), _mk("T-GONE")],
        now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(
        conn, [_mk("T-0"), _mk("T-1", yes_ask_dollars="0.95")], now=NOW)
    got = board.get_board(conn, now=NOW)
    assert sorted(m.ticker for m in got) == ["T-0", "T-1"]
    assert {m.ticker: m.yes_ask for m in got}["T-1"] == pytest.approx(0.95)


def test_backfill_gives_legacy_rows_their_captured_at(conn):
    with db.write(conn):
        conn.execute(
            "INSERT INTO market_snapshots"
            " (platform, market_id, captured_at, title, raw_json,"
            "  last_seen_at)"
            " VALUES ('kalshi', 'L-1', ?, 't', '{}', NULL)", (NOW,))
    db.init_db(conn)
    row = conn.execute(
        "SELECT last_seen_at FROM market_snapshots WHERE market_id='L-1'"
    ).fetchone()
    assert row["last_seen_at"] == NOW
```

- [ ] **Step 2: Run them to verify failure.** `python -m pytest tests/test_snapshot_store.py -q` — expect failures on missing column / old semantics (the fixture's `init_db` may fail first on the schema change not yet made: fine, that is the failing state).

- [ ] **Step 3: Schema + migration.** In `db/schema.sql`, extend the `market_snapshots` DDL (after `event_json TEXT`):

```sql
    -- Validity interval close (dedup-on-write, spec 5.2 phase 2): the last
    -- pull at which this exact payload was observed. A row covers
    -- [captured_at, last_seen_at]. Backfilled = captured_at for rows
    -- written before dedup existed.
    last_seen_at     TEXT
```

In `tools/db.py::init_db`, after the `event_json` line (~93), add:

```python
    _add_column_if_missing(conn, "market_snapshots", "last_seen_at", "TEXT")
    # Backfill: a pre-dedup row was seen exactly once, at its capture.
    with write(conn):
        conn.execute(
            "UPDATE market_snapshots SET last_seen_at = captured_at"
            " WHERE last_seen_at IS NULL"
        )
```

- [ ] **Step 4: Rewrite the save path in `tools/snapshot.py`.** Replace `_INSERT` and both save functions with a shared core (keep `_kalshi_snapshot_status`, the payload-completeness comment block, `history_for`, `capture_*` as they are; `save_kalshi`/`save_polymarket` keep their signatures and row-building, then call `_save`):

```python
import hashlib
import zlib  # used from Task 4; harmless to import now

_INSERT = """
    INSERT INTO market_snapshots (
        platform, market_id, captured_at, title, implied_prob_yes,
        yes_bid, yes_ask, volume, open_interest, close_time, status,
        raw_json, event_json, last_seen_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (platform, market_id, captured_at) DO UPDATE SET
        title            = excluded.title,
        implied_prob_yes = excluded.implied_prob_yes,
        yes_bid          = excluded.yes_bid,
        yes_ask          = excluded.yes_ask,
        volume           = excluded.volume,
        open_interest    = excluded.open_interest,
        close_time       = excluded.close_time,
        status           = excluded.status,
        raw_json         = excluded.raw_json,
        event_json       = excluded.event_json,
        last_seen_at     = excluded.last_seen_at
"""


def _payload_key(raw_text: str | None, event_text: str | None) -> bytes:
    """Byte-exact identity of one capture's full payload.

    The design gate (2026-08-29, commit 6fe567a) measured dedup on the
    complete raw_json+event_json and ruled out field exclusions: rules
    text, close_time, everything counts. NULL event_json is distinct
    from '{}' and from 'null' by construction here.
    """
    h = hashlib.sha256()
    h.update(b"\x00" if raw_text is None else raw_text.encode("utf-8"))
    h.update(b"\x1f")
    h.update(b"\x00" if event_text is None else event_text.encode("utf-8"))
    return h.digest()


def _latest_rows(conn, platform: str) -> dict[str, tuple[str, bytes]]:
    """market_id -> (captured_at, payload key) of each market's latest row."""
    out = {}
    for row in conn.execute(
        """
        SELECT market_id, captured_at, raw_json, event_json
          FROM market_snapshots
         WHERE platform = ? AND id IN (
               SELECT MAX(id) FROM market_snapshots
                WHERE platform = ? GROUP BY market_id)
        """,
        (platform, platform),
    ):
        out[row["market_id"]] = (
            row["captured_at"],
            _payload_key(payload_text(row["raw_json"]),
                         payload_text(row["event_json"])),
        )
    return out


def _save(conn, platform: str, rows: list[tuple], stamp: str) -> int:
    """Dedup-aware write of one pull (spec 5.2 phase 2).

    Each incoming row is compared byte-exactly against the market's
    latest stored payload:
      unchanged and stamp is not older -> UPDATE last_seen_at (interval
        extends; no new row);
      anything else -> INSERT (same-second re-save still lands on the
        (platform, market_id, captured_at) upsert, last write wins).
    An *older* stamp never extends an interval backwards: it inserts as
    history, which is what a backfill save means.
    Returns rows physically written or updated (unchanged bumps count).
    """
    latest = _latest_rows(conn, platform)
    inserts, bumps = [], []
    for r in rows:
        market_id, raw_text, event_text = r[1], r[11], r[12]
        seen = latest.get(market_id)
        if (seen is not None and seen[1] == _payload_key(raw_text, event_text)
                and stamp >= seen[0]):
            bumps.append((stamp, platform, market_id))
        else:
            inserts.append(r + (stamp,))
    with write(conn):
        if inserts:
            conn.executemany(_INSERT, inserts)
        if bumps:
            conn.executemany(
                """
                UPDATE market_snapshots SET last_seen_at = MAX(last_seen_at, ?)
                 WHERE platform = ? AND market_id = ? AND id = (
                       SELECT MAX(id) FROM market_snapshots
                        WHERE platform = ? AND market_id = ?)
                """,
                [(s, p, m, p, m) for s, p, m in bumps],
            )
    return len(inserts) + len(bumps)
```

`save_kalshi` / `save_polymarket` build the same 13-tuples as today (no `last_seen_at`; `_save` appends the stamp) and end with `return _save(conn, "kalshi", rows, stamp)` / `_save(conn, "polymarket", rows, stamp)`. `payload_text` does not exist until Task 4 — in this task define the pass-through version in `tools/snapshot.py`:

```python
def payload_text(value):
    """A payload column's JSON text. Identity for TEXT rows; Task 4
    extends this to decode zlib BLOB rows."""
    return value
```

- [ ] **Step 5: Board semantics in `tools/board.py`.** Replace `board_info`'s query and `_rebuild`'s query (docstrings updated to say interval semantics; everything else, including `get_board`, unchanged):

```python
def board_info(conn, now=None):
    """Age and size of the freshest stored board, or None if there is none.

    A pull where nothing changed writes no rows (spec 5.2 phase 2), so
    the board is not "rows sharing one captured_at": it is the rows
    whose interval reaches the latest pull stamp. `captured_at` in the
    returned dict is that pull stamp (kept under its old key: it is the
    batch identity every caller already treats it as).
    """
    row = conn.execute(
        """
        SELECT MAX(last_seen_at) AS stamp, COUNT(*) AS n
          FROM market_snapshots
         WHERE platform = 'kalshi'
           AND last_seen_at = (SELECT MAX(last_seen_at)
                                 FROM market_snapshots
                                WHERE platform = 'kalshi')
        """
    ).fetchone()
    if row is None or row["stamp"] is None:
        return None
    age = (_parse(now or utcnow()) - _parse(row["stamp"])).total_seconds()
    return {"captured_at": row["stamp"], "markets": row["n"],
            "age_minutes": age / 60.0}
```

and in `_rebuild`, the SELECT becomes:

```python
        SELECT raw_json, event_json FROM market_snapshots
         WHERE platform = 'kalshi' AND last_seen_at = ?
```

with `json.loads(...)` calls routed as `json.loads(snapshot.payload_text(row["raw_json"]) or "{}")` and `json.loads(snapshot.payload_text(row["event_json"]) or "null")`.

- [ ] **Step 6: Update the three sanctioned tests in `tests/test_board.py`,** keeping each one's intent:
  - `test_board_info_uses_only_the_freshest_batch` (line 52): same fixture and assertions still express the intent under the new semantics (batch 2's two unchanged markets bump `last_seen_at`; the three absent markets stay behind) — verify it passes as written; if the `_board(5)`/`_board(2)` payload identity makes `markets` come out different from 2, adjust the second save to changed payloads (`_raw(..., yes_ask_dollars="0.83")`) so the intent ("only the freshest pull counts") stays exact.
  - `test_separate_seconds_are_separate_batches` (line 226) becomes:

```python
def test_unchanged_pull_extends_the_batch_rather_than_duplicating_it(conn):
    # Pre-dedup, two identical pulls a second apart wrote 6 rows in 2
    # batches. Now the second pull writes nothing and the stored board
    # is simply re-stamped (spec 5.2 phase 2).
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:00:01Z")
    assert conn.execute(
        "SELECT COUNT(*) n FROM market_snapshots").fetchone()["n"] == 3
    info = board.board_info(conn, now=NOW)
    assert info["markets"] == 3
    assert info["captured_at"] == "2026-08-24T11:00:01Z"
```

  - `test_re_saving_updates_rather_than_duplicating` (line 215): should pass unchanged (same-second changed payload hits the upsert). Verify; add one assertion that `last_seen_at == NOW` on the surviving row.

- [ ] **Step 7: Run the full gates.**

Run: `python -m pytest tests/test_snapshot_store.py tests/test_board.py tests/test_snapshot.py -q` then `python -m pytest tests/ -q`
Expected: all green — explicitly including the four fidelity tests untouched, `test_saving_twice_in_one_second_does_not_duplicate`, `test_snapshots_accumulate_rather_than_overwrite`, and `test_history_for_is_ascending_by_time` (the out-of-order guard exists for it).

- [ ] **Step 8: Commit**

```bash
git add db/schema.sql tools/db.py tools/snapshot.py tools/board.py tests/test_snapshot.py tests/test_board.py tests/test_snapshot_store.py
git commit -m "feat: snapshot dedup on write — rows carry a validity interval (spec 5.2 phase 2)"
```

### Task 3: Retro-dedup of existing history (`db dedup-snapshots`)

**Files:**
- Modify: `tools/snapshot.py` (add `dedup_history`), `tools/cli.py:349-356` (`_cmd_db`) and the `db` parser block (~696)
- Test: `tests/test_snapshot_store.py`

**Interfaces:**
- Consumes: `_payload_key`, `payload_text` (Task 2).
- Produces: `snapshot.dedup_history(conn, batch_markets=2000) -> dict` with keys `markets`, `deleted`, `kept`; CLI `python -m tools.cli db dedup-snapshots`.

- [ ] **Step 1: Failing tests** (append to `tests/test_snapshot_store.py`):

```python
def _insert_legacy(conn, market_id, captured_at, raw, event=None):
    with db.write(conn):
        conn.execute(
            "INSERT INTO market_snapshots (platform, market_id, captured_at,"
            " raw_json, event_json, last_seen_at) VALUES"
            " ('kalshi', ?, ?, ?, ?, ?)",
            (market_id, captured_at, raw, event, captured_at))


def test_dedup_history_collapses_consecutive_identical_rows(conn):
    _insert_legacy(conn, "H-1", "2026-08-20T10:00:00Z", '{"a":1}')
    _insert_legacy(conn, "H-1", "2026-08-20T11:00:00Z", '{"a":1}')
    _insert_legacy(conn, "H-1", "2026-08-20T12:00:00Z", '{"a":1}')
    _insert_legacy(conn, "H-1", "2026-08-20T13:00:00Z", '{"a":2}')
    stats = snapshot.dedup_history(conn)
    assert stats["deleted"] == 2
    rows = conn.execute(
        "SELECT captured_at, last_seen_at, raw_json FROM market_snapshots"
        " ORDER BY captured_at").fetchall()
    assert len(rows) == 2
    # The survivor's interval absorbed both deleted stamps.
    assert rows[0]["captured_at"] == "2026-08-20T10:00:00Z"
    assert rows[0]["last_seen_at"] == "2026-08-20T12:00:00Z"
    assert rows[1]["captured_at"] == "2026-08-20T13:00:00Z"


def test_dedup_history_keeps_a_reverted_payload(conn):
    # a -> b -> a is three observations, not two: only CONSECUTIVE equals
    # collapse, or the reversion at 12:00 would be erased from history.
    _insert_legacy(conn, "H-2", "2026-08-20T10:00:00Z", '{"p":"a"}')
    _insert_legacy(conn, "H-2", "2026-08-20T11:00:00Z", '{"p":"b"}')
    _insert_legacy(conn, "H-2", "2026-08-20T12:00:00Z", '{"p":"a"}')
    stats = snapshot.dedup_history(conn)
    assert stats["deleted"] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM market_snapshots").fetchone()[0] == 3


def test_dedup_history_distinguishes_null_event_from_empty(conn):
    _insert_legacy(conn, "H-3", "2026-08-20T10:00:00Z", '{"a":1}', None)
    _insert_legacy(conn, "H-3", "2026-08-20T11:00:00Z", '{"a":1}', "{}")
    assert snapshot.dedup_history(conn)["deleted"] == 0


def test_dedup_history_is_idempotent(conn):
    _insert_legacy(conn, "H-4", "2026-08-20T10:00:00Z", '{"a":1}')
    _insert_legacy(conn, "H-4", "2026-08-20T11:00:00Z", '{"a":1}')
    assert snapshot.dedup_history(conn)["deleted"] == 1
    assert snapshot.dedup_history(conn)["deleted"] == 0


def test_dedup_history_preserves_point_in_time_reads(conn):
    _insert_legacy(conn, "H-5", "2026-08-20T10:00:00Z", '{"r":"v1"}')
    _insert_legacy(conn, "H-5", "2026-08-20T11:00:00Z", '{"r":"v1"}')
    _insert_legacy(conn, "H-5", "2026-08-20T12:00:00Z", '{"r":"v2"}')
    snapshot.dedup_history(conn)
    t = "2026-08-20T11:00:00Z"
    row = conn.execute(
        "SELECT raw_json FROM market_snapshots WHERE market_id='H-5'"
        " AND captured_at <= ? AND last_seen_at >= ?", (t, t)).fetchone()
    assert json.loads(row["raw_json"])["r"] == "v1"
```

- [ ] **Step 2: Run to verify failure.** `python -m pytest tests/test_snapshot_store.py -q` — the new tests fail on missing `dedup_history`.

- [ ] **Step 3: Implement** in `tools/snapshot.py`:

```python
def dedup_history(conn, batch_markets: int = 2000) -> dict:
    """Collapse consecutive byte-identical rows per market (spec 5.2).

    For each market, walk its rows oldest-first; a row whose full payload
    (raw_json + event_json, byte-exact — the design gate ruled out field
    exclusions) equals its immediate predecessor's is deleted and the
    predecessor's last_seen_at absorbs its stamp. Only consecutive equals
    collapse: a reverted payload is a new observation.

    Incremental and idempotent (data conventions): commits per batch of
    markets, so an interrupted run resumes by simply re-running — already
    collapsed markets yield nothing on the second pass.
    """
    stats = {"markets": 0, "deleted": 0, "kept": 0}
    market_ids = [r[0] for r in conn.execute(
        "SELECT DISTINCT market_id FROM market_snapshots ORDER BY market_id")]
    for i in range(0, len(market_ids), batch_markets):
        chunk = market_ids[i:i + batch_markets]
        with write(conn):
            for mid in chunk:
                rows = conn.execute(
                    "SELECT id, captured_at, last_seen_at, raw_json,"
                    " event_json FROM market_snapshots"
                    " WHERE market_id = ? ORDER BY captured_at, id",
                    (mid,)).fetchall()
                stats["markets"] += 1
                keeper, keeper_key, keeper_reach = None, None, None
                doomed, reaches = [], {}
                for row in rows:
                    key = _payload_key(payload_text(row["raw_json"]),
                                       payload_text(row["event_json"]))
                    if keeper is not None and key == keeper_key:
                        doomed.append(row["id"])
                        keeper_reach = max(keeper_reach,
                                           row["last_seen_at"] or
                                           row["captured_at"])
                        reaches[keeper] = keeper_reach
                    else:
                        keeper, keeper_key = row["id"], key
                        keeper_reach = (row["last_seen_at"] or
                                        row["captured_at"])
                for kid, reach in reaches.items():
                    conn.execute(
                        "UPDATE market_snapshots SET last_seen_at = ?"
                        " WHERE id = ?", (reach, kid))
                if doomed:
                    conn.executemany(
                        "DELETE FROM market_snapshots WHERE id = ?",
                        [(d,) for d in doomed])
                stats["deleted"] += len(doomed)
                stats["kept"] += len(rows) - len(doomed)
    return stats
```

- [ ] **Step 4: Wire the CLI.** In `tools/cli.py::_cmd_db` add a branch; in the parser add the subcommand:

```python
    if args.action == "dedup-snapshots":
        from tools import snapshot as snapshot_mod
        conn = _connect(args)
        try:
            _emit(snapshot_mod.dedup_history(conn))
        finally:
            conn.close()
```

```python
    dbsub.add_parser(
        "dedup-snapshots",
        help="collapse consecutive byte-identical snapshot rows into"
             " validity intervals (spec 5.2 phase 2, one-time)",
    )
```

(Match `_cmd_db`'s existing style; `_connect`/`_emit` are the file's existing helpers — read their signatures before using.)

- [ ] **Step 5: Tests green, suite green.** `python -m pytest tests/test_snapshot_store.py -q && python -m pytest tests/ -q`

- [ ] **Step 6: Commit**

```bash
git add tools/snapshot.py tools/cli.py tests/test_snapshot_store.py
git commit -m "feat: db dedup-snapshots — retro-collapse of unchanged history rows (spec 5.2 phase 2)"
```

- [ ] **Step 7: LIVE RUN** (controller confirms no other session first): `python -m tools.cli db dedup-snapshots` (minutes). Record `deleted`/`kept` in the report — expect deleted ≈ the Task 1 dup count (~38.8%). Then sanity: `python -m tools.cli state` renders; `python -c` re-count rows; the db FILE does not shrink yet (freed pages are reclaimed at Task 5's VACUUM — say so in the report).

### Task 4: Payload compression (`db compress-snapshots`) + reader repoint

**Files:**
- Modify: `tools/snapshot.py` (`payload_text` real version, write-path compress, `compress_history`), `tools/board.py` (already routed via helper in Task 2 — verify only), `tools/cli.py` (subcommand), `tests/test_board.py:166-174` (fidelity read via helper — sanctioned), 4 study write-ups
- Test: `tests/test_snapshot_store.py`

**Interfaces:**
- Consumes: `payload_text` pass-through (Task 2).
- Produces: `payload_text(value) -> str|None` decoding zlib BLOBs; saves write zlib BLOBs; `snapshot.compress_history(conn, batch_rows=20000) -> dict` (`compressed`, `already`, `bytes_before`, `bytes_after`); CLI `db compress-snapshots`.

- [ ] **Step 1: Failing tests** (append to `tests/test_snapshot_store.py`):

```python
import zlib


def test_payload_text_decodes_blob_and_passes_text_and_none(conn):
    assert snapshot.payload_text(None) is None
    assert snapshot.payload_text('{"a":1}') == '{"a":1}'
    blob = zlib.compress('{"a":1}'.encode("utf-8"))
    assert snapshot.payload_text(blob) == '{"a":1}'
    assert snapshot.payload_text(memoryview(blob)) == '{"a":1}'


def test_new_saves_store_compressed_payloads(conn):
    snapshot.save_kalshi(conn, [_mk("C-0")], now=NOW)
    row = conn.execute(
        "SELECT raw_json FROM market_snapshots").fetchone()
    assert isinstance(row["raw_json"], bytes)          # BLOB = zlib codec
    assert json.loads(snapshot.payload_text(row["raw_json"]))["ticker"] == "C-0"


def test_dedup_compares_across_codecs(conn):
    # A plain-text legacy row and a compressed re-save of the SAME payload
    # must still count as unchanged: identity is the decoded text.
    raw = '{"ticker": "X-1", "v": 1}'
    _insert_legacy(conn, "X-1", "2026-08-24T11:00:00Z", raw)
    key_old = snapshot._payload_key(raw, None)
    key_new = snapshot._payload_key(
        snapshot.payload_text(zlib.compress(raw.encode("utf-8"))), None)
    assert key_old == key_new


def test_compress_history_converts_text_rows_in_place(conn):
    _insert_legacy(conn, "C-1", "2026-08-24T11:00:00Z", '{"a": 1}', '{"e": 2}')
    stats = snapshot.compress_history(conn)
    assert stats["compressed"] == 1
    row = conn.execute("SELECT raw_json, event_json FROM market_snapshots"
                       " WHERE market_id='C-1'").fetchone()
    assert isinstance(row["raw_json"], bytes)
    assert json.loads(snapshot.payload_text(row["raw_json"]))["a"] == 1
    assert json.loads(snapshot.payload_text(row["event_json"]))["e"] == 2
    assert snapshot.compress_history(conn)["compressed"] == 0   # idempotent


def test_board_rebuild_reads_mixed_codecs(conn):
    # One legacy text row and one compressed row in the same board.
    m0, m1 = _mk("C-2"), _mk("C-3")
    snapshot.save_kalshi(conn, [m0, m1], now=NOW)     # compressed writes
    with db.write(conn):                               # revert one to text
        conn.execute(
            "UPDATE market_snapshots SET raw_json = ? WHERE market_id='C-2'",
            (json.dumps(m0.raw),))
    got = board.get_board(conn, now=NOW)
    assert sorted(m.ticker for m in got) == ["C-2", "C-3"]
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement.** In `tools/snapshot.py`: replace `payload_text` and compress on write:

```python
def payload_text(value):
    """A payload column's JSON text, whatever its stored codec.

    The cell's TYPE is the codec (spec 5.2 phase 3 allows a codec column
    or a sniff; the sqlite value type is the sniff with no magic bytes):
    TEXT rows are pre-compression plain JSON and pass through; BLOB rows
    are zlib. None stays None. ALL reads of raw_json/event_json go
    through here — a direct json.loads() on the column breaks on any row
    written after 2026-08-30.
    """
    if value is None or isinstance(value, str):
        return value
    return zlib.decompress(bytes(value)).decode("utf-8")


def _encode(text: str | None):
    return None if text is None else zlib.compress(text.encode("utf-8"))
```

In `_save`, the incoming row tuples still carry plain text (built by `save_kalshi`/`save_polymarket`); hash on the text, store encoded — inserts become `r[:11] + (_encode(r[11]), _encode(r[12]), stamp)` (adjust indices to the actual tuple layout; add a comment naming the layout). `_latest_rows` already decodes via `payload_text` (Task 2 wrote it that way), so cross-codec comparison works. Then add:

```python
def compress_history(conn, batch_rows: int = 20000) -> dict:
    """Convert plain-text payload rows to zlib BLOBs, in batches.

    Incremental and idempotent: selects only rows still TEXT-typed, so an
    interrupted run resumes where it stopped (data conventions).
    """
    stats = {"compressed": 0, "already": 0,
             "bytes_before": 0, "bytes_after": 0}
    while True:
        rows = conn.execute(
            "SELECT id, raw_json, event_json FROM market_snapshots"
            " WHERE typeof(raw_json) = 'text'"
            "    OR typeof(event_json) = 'text'"
            " LIMIT ?", (batch_rows,)).fetchall()
        if not rows:
            break
        updates = []
        for row in rows:
            raw, event = row["raw_json"], row["event_json"]
            before = (len(raw) if isinstance(raw, str) else 0) + \
                     (len(event) if isinstance(event, str) else 0)
            raw_out = _encode(raw) if isinstance(raw, str) else raw
            event_out = _encode(event) if isinstance(event, str) else event
            after = (len(raw_out) if isinstance(raw_out, bytes) else 0) + \
                    (len(event_out) if isinstance(event_out, bytes) else 0)
            stats["bytes_before"] += before
            stats["bytes_after"] += after
            updates.append((raw_out, event_out, row["id"]))
        with write(conn):
            conn.executemany(
                "UPDATE market_snapshots SET raw_json = ?, event_json = ?"
                " WHERE id = ?", updates)
        stats["compressed"] += len(updates)
    stats["already"] = conn.execute(
        "SELECT COUNT(*) FROM market_snapshots").fetchone()[0] - stats["compressed"]
    return stats
```

- [ ] **Step 4: Repoint the direct readers.** Run the rot-proof sweep the spec mandates at ship time: `grep -rn "raw_json\|event_json" --include='*.py' . | grep -v .superpowers` — repoint every `tools/` and `tests/` hit that parses the column (as of planning: `tools/board.py` done in Task 2; `tests/test_board.py:168` — `json.loads(snapshot.payload_text(...))`, the sanctioned fidelity-read exception, assertion untouched; `tests/test_snapshot.py:99` same treatment; fixtures in `tests/test_state.py`/`tests/test_backup.py` write plain text — valid mixed-codec input, leave them). Studies are historical artifacts: do NOT edit their `.py`; instead append one line to each affected study's `STUDY.md` (`studies/2026-08-29-structural-arb-violation-liquidity/`, `2026-08-29-structural-gate-payload-version/`, `2026-08-29-side-asymmetry-extension/`, `2026-08-27-calendar-arb-firing-rate/`): `Note (2026-08-30): re-running this probe against post-compression snapshot rows requires routing raw_json/event_json reads through tools.snapshot.payload_text (spec 5.2 phase 3).`

- [ ] **Step 5: Gates.** `python -m pytest tests/test_snapshot_store.py tests/test_board.py tests/test_snapshot.py -q && python -m pytest tests/ -q` — the four fidelity tests' assertions/fixtures byte-unchanged (only the two sanctioned read-routings), all green.

- [ ] **Step 6: Commit**

```bash
git add tools/snapshot.py tools/cli.py tests/test_snapshot_store.py tests/test_board.py tests/test_snapshot.py studies/2026-08-29-structural-arb-violation-liquidity/STUDY.md studies/2026-08-29-structural-gate-payload-version/STUDY.md studies/2026-08-29-side-asymmetry-extension/STUDY.md studies/2026-08-27-calendar-arb-firing-rate/STUDY.md
git commit -m "feat: zlib payload codec + db compress-snapshots; every reader through payload_text (spec 5.2 phase 3)"
```

(CLI subcommand `compress-snapshots` wired same as Task 3's — include it in this commit.)

- [ ] **Step 7: LIVE RUN**: `python -m tools.cli db compress-snapshots` (expect ~5–15 min over ~850k rows; it commits per batch — if interrupted, re-run). Record `compressed`/`bytes_before`/`bytes_after` (expect ~8× on the JSON). File still does not shrink until VACUUM — note it. Then `python -m tools.cli state` and a `get_board`-path smoke: `python -c "from tools import db, board; c=db.connect(); print(len(board.get_board(c)))"` — must rebuild the cached board from mixed rows without fetching (or fetch if stale — either way, no traceback).

### Task 5: The split — `db/snapshots.db`, `db stats`, checkpoint on close (`db split-snapshots`)

**Files:**
- Create: `db/schema_snapshots.sql`
- Modify: `db/schema.sql` (remove the `market_snapshots` block + its index), `tools/db.py` (`connect` ATTACH, `init_db` snap-schema + refusal, `split_snapshots`, `close`), `tools/cli.py` (`split-snapshots`, `stats`), `tools/backup.py` (only if its table enumeration needs the exclusion dropped — read it; after the split, main has no `market_snapshots`, so its exclusion logic simply never fires — prefer no change), `tools/README.md` (cadence ruling)
- Test: `tests/test_snapshot_store.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `db.connect(path)` returns a connection with `snapdb` attached (file `<path's stem>.snapshots.db`... no — exact name: sibling file named `snapshots.db` when path's name is `market_edge.db`, else `<name>.snapshots.db` — see Step 3); `db.split_snapshots(conn, main_path) -> dict`; `db.close(conn)`; CLI `db split-snapshots` and `db stats`.

- [ ] **Step 1: Failing tests** (append to `tests/test_snapshot_store.py`):

```python
def test_fresh_db_puts_snapshots_in_the_attached_file(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    snapshot.save_kalshi(c, [_mk("S-0")], now=NOW)
    # Unqualified name resolves to the attached table...
    assert c.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0] == 1
    # ...because main genuinely does not have one.
    assert c.execute(
        "SELECT COUNT(*) FROM main.sqlite_master WHERE name='market_snapshots'"
    ).fetchone()[0] == 0
    assert c.execute(
        "SELECT COUNT(*) FROM snapdb.sqlite_master WHERE name='market_snapshots'"
    ).fetchone()[0] == 1
    assert (tmp_path / "test.snapshots.db").exists()
    db.close(c)


def test_unsplit_database_is_refused_loudly(tmp_path):
    # Build a pre-split DB shape by hand: table in main, rows present.
    import sqlite3 as raw_sqlite
    legacy = raw_sqlite.connect(tmp_path / "old.db")
    legacy.execute("CREATE TABLE market_snapshots (id INTEGER PRIMARY KEY,"
                   " platform TEXT, market_id TEXT, captured_at TEXT,"
                   " raw_json TEXT, last_seen_at TEXT)")
    legacy.execute("INSERT INTO market_snapshots"
                   " (platform, market_id, captured_at, raw_json)"
                   " VALUES ('kalshi','L','2026-08-24T11:00:00Z','{}')")
    legacy.commit(); legacy.close()
    c = db.connect(tmp_path / "old.db")
    with pytest.raises(RuntimeError, match="split-snapshots"):
        db.init_db(c)
    c.close()


def test_split_snapshots_moves_rows_and_drops_main(tmp_path):
    import sqlite3 as raw_sqlite
    legacy = raw_sqlite.connect(tmp_path / "old.db")
    legacy.execute("CREATE TABLE market_snapshots (id INTEGER PRIMARY KEY,"
                   " platform TEXT, market_id TEXT, captured_at TEXT,"
                   " title TEXT, implied_prob_yes REAL, yes_bid REAL,"
                   " yes_ask REAL, volume REAL, open_interest REAL,"
                   " close_time TEXT, status TEXT, raw_json TEXT,"
                   " event_json TEXT, last_seen_at TEXT)")
    legacy.execute("INSERT INTO market_snapshots"
                   " (platform, market_id, captured_at, raw_json, last_seen_at)"
                   " VALUES ('kalshi','M','2026-08-24T11:00:00Z','{\"a\":1}',"
                   " '2026-08-24T11:00:00Z')")
    legacy.commit(); legacy.close()
    c = db.connect(tmp_path / "old.db")
    stats = db.split_snapshots(c, tmp_path / "old.db")
    assert stats["moved"] == 1
    assert c.execute("SELECT COUNT(*) FROM snapdb.market_snapshots"
                     ).fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM main.sqlite_master"
                     " WHERE name='market_snapshots'").fetchone()[0] == 0
    db.init_db(c)          # now passes: main is split
    snapshot.save_kalshi(c, [_mk("S-1")], now=NOW)   # writes land attached
    assert c.execute("SELECT COUNT(*) FROM market_snapshots"
                     ).fetchone()[0] == 2
    db.close(c)


def test_db_close_checkpoints_the_wal(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    snapshot.save_kalshi(c, [_mk("S-2")], now=NOW)
    db.close(c)
    # After a TRUNCATE checkpoint the -wal files are empty or gone.
    for name in ("test.db-wal", "test.snapshots.db-wal"):
        p = tmp_path / name
        assert (not p.exists()) or p.stat().st_size == 0
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement in `tools/db.py`.**

Move the whole `market_snapshots` CREATE TABLE block and its `idx_snapshots_unique` index out of `db/schema.sql` into new `db/schema_snapshots.sql` (verbatim text, `last_seen_at` included; header comment: `-- Snapshot store schema. Lives in its own database file, ATTACHed as snapdb by tools/db.connect() (spec 5.2 phase 4), so the precious-and-small ledger and the large history can have different backup cadences.`). Then:

```python
SNAP_SCHEMA_PATH = REPO_ROOT / "db" / "schema_snapshots.sql"


def snapshots_path_for(path: str | Path) -> Path:
    """db/market_edge.db -> db/snapshots.db; any other name gets a
    <stem>.snapshots.db sibling so test databases never collide."""
    path = Path(path)
    if path.name == "market_edge.db":
        return path.with_name("snapshots.db")
    return path.with_name(path.stem + ".snapshots.db")
```

In `connect()`, after the PRAGMAs:

```python
    snap = snapshots_path_for(path)
    conn.execute("ATTACH DATABASE ? AS snapdb", (str(snap),))
    conn.execute("PRAGMA snapdb.journal_mode = WAL")
```

In `init_db()`, immediately after the legacy-position-key check:

```python
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
```

Note `_dedupe_snapshots` (`tools/db.py:135`) runs before the schema script today and queries `sqlite_master` unqualified — after the split it must look at BOTH catalogs or it will miss/re-run; simplest correct change: make it a no-op when main has no `market_snapshots` table (the attached store was born deduped), keeping its legacy behavior for the refusal path only. Also `init_db`'s existing `_add_column_if_missing(conn, "market_snapshots", ...)` lines (`event_json`, `last_seen_at`): `PRAGMA table_info` resolves unqualified — verify it sees the attached table (it does once main has none) and the backfill UPDATE targets it; add `snapdb.`-qualification only if a test proves resolution wrong.

`split_snapshots` and `close`:

```python
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
```

CLI: `db split-snapshots` branch calls `backup_mod.backup_ledger(...)` FIRST (the precondition is mechanical, not a reminder), then `db.split_snapshots(conn, args.db or db.DEFAULT_DB_PATH)`; `db stats` prints, per attached database (`PRAGMA database_list`), file path, file bytes, and per-table `COUNT(*)` plus — when the `dbstat` module is available (`SELECT name FROM pragma_module_list WHERE name='dbstat'`) — per-table bytes via `SELECT SUM(pgsize) FROM dbstat WHERE ...`, else the page-count estimate `PRAGMA page_count * page_size` per file with a `"per_table_bytes": "unavailable (dbstat not compiled in)"` marker. Repoint `tools/cli.py`'s connection teardown to `db.close(conn)` **only** in `_cmd_db`/`_cmd_state` (the two long-data paths touched here); a global sweep of every `conn.close()` is out of scope — note that in the commit message.

- [ ] **Step 4: `tools/README.md` cadence note** (append under its data-conventions section):

```markdown
### Backup cadence (ruled at spec 5.2 phase 4, 2026-08-30)

`db/market_edge.db` (the ledger — small, irreplaceable): `python -m
tools.cli db backup` before any schema migration or destructive
maintenance command (`split-snapshots` runs one itself), and at the start
of any session that will settle or migrate. `db/snapshots.db` (large,
prices re-fetchable in spirit): no automatic backup; copy the file
manually if a study depends on a specific historical window.
```

- [ ] **Step 5: Gates.** Full suite: `python -m pytest tests/ -q`. Every existing test that opens `db.connect(tmp_path/...)` now creates a sibling `.snapshots.db` — expect no assertion changes anywhere (unqualified queries resolve to the attached table); if any test asserts on `sqlite_master` contents of main, fix the test's query to say which catalog it means. Conventions suite green (`db/schema_snapshots.sql` is a new repo path — the docs-path test only checks paths named in docs; name the new file in `tools/README.md`'s map so it is discoverable AND resolvable).

- [ ] **Step 6: Commit**

```bash
git add db/schema.sql db/schema_snapshots.sql tools/db.py tools/cli.py tools/README.md tests/test_snapshot_store.py
git commit -m "feat: snapshots split into db/snapshots.db (ATTACH), db stats, checkpoint on close (spec 5.2 phase 4)"
```

- [ ] **Step 7: LIVE RUN** (controller re-confirms sole-writer): `python -m tools.cli db split-snapshots` (backup runs first; copy ~minutes; VACUUM of main afterwards is quick once the big table is gone — but budget for the copy: the compressed store is roughly 0.5–1 GB against 38 GB free). Then `python -m tools.cli db stats` (record both files' sizes), `python -m tools.cli state`, and the board smoke from Task 4 Step 7. Record every number.

### Task 6: Reconcile, log entry, spec done-marker

**Files:**
- Modify: `docs/superpowers/specs/2026-08-29-enforcing-surfaces-design.md` (one status line at the top of §5.2), `RESEARCH_LOG.md` (one appended entry)

**Interfaces:**
- Consumes: every live-run number recorded in Tasks 1, 3, 4, 5 reports.

- [ ] **Step 1: Verify end state.** `python -m pytest tests/ -q` green; `python -m tools.cli db stats` shows main file at ledger scale (tens of MB) and `db/snapshots.db` holding every surviving row; `python -c "from tools import db, board; c=db.connect(); print(board.board_info(c))"` sane.

- [ ] **Step 2: Spec done-marker.** In §5.2, after the phase-4 paragraph, add one line: `**Status: phases 0–4 all shipped** — 0–1 in the foundation plan (2026-08-29); 2–4 in docs/superpowers/plans/2026-08-30-snapshot-store-overhaul.md (2026-08-30), with the live-run numbers in RESEARCH_LOG.md's entry of that date.` (§5.1's done-marker from `4f80344` is the precedent for the form.)

- [ ] **Step 3: Log entry** appended to RESEARCH_LOG.md — it passes the §6.5 bar (repo-level mechanism + a data-source constraint change). Heading: `## 2026-08-30 — snapshot store overhauled: dedup intervals, zlib payloads, own database file (spec 5.2 complete)`. Body: the before/after numbers (rows deleted by retro-dedup vs the 38.8% gate figure; bytes before/after compression; main-file and snapshots-file sizes after the split), the new invariants a future session must know (a row is an interval `[captured_at, last_seen_at]`; "unchanged" is byte-exact full payload; ALL `raw_json`/`event_json` reads go through `tools.snapshot.payload_text`; the store lives ATTACHed as `snapdb` and unqualified queries keep working; the backup cadence), and pointers to this plan and the four study notes. Do not use the literal string `migrated from RESEARCH_LOG.md`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-08-29-enforcing-surfaces-design.md RESEARCH_LOG.md
git commit -m "log: snapshot-store overhaul reconciled — spec 5.2 phases 2-4 shipped with live-run numbers"
```

---

## Self-review notes (kept for the executor)

- Spec coverage: phase 2 → Tasks 2–3 (write path + retro), the design gate → already ruled (38.8%, byte-exact, no exclusions) and encoded in `_payload_key`'s docstring and `test_unchanged_only_means_byte_exact_full_payload`; phase 3 → Task 4 (helper, write path, retro, reader repoint, study notes, ship-time sweep); phase 4 → Task 5 (split, `db stats`, checkpoint, cadence); safety net → Global Constraints (four fidelity tests; three sanctioned changes); point-in-time guarantee → tests in Tasks 2–3.
- The three sanctioned test changes all happen in Task 2; Task 4's fidelity-read routing is the one controller-ruled mechanical exception, justified by the spec's own repoint clause.
- `_save` tuple layout: `save_kalshi` builds 13-field tuples (indices 0–12; payloads at 11–12); `_save` appends `stamp` as field 13 (`last_seen_at`). Task 4 changes only how 11–12 are encoded at insert time.
- Known risk, held deliberately: `PRAGMA table_info(market_snapshots)` and unqualified DML resolving to `snapdb` relies on main not having the table — which the refusal in `init_db` guarantees. The test `test_fresh_db_puts_snapshots_in_the_attached_file` pins the resolution behavior.
