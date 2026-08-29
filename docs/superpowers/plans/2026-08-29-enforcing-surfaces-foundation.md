# Enforcing Surfaces — Plan 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the spec's foundation phases — ledger backup, doc hygiene + docs-path test, `mark-taken --ticker`, the `get_board` force floor, `cli state`, the `rulings` table with its twelve-ruling backfill, and the db/ relocation out of OneDrive.

**Architecture:** Everything lands in the existing `tools/` package + `db/schema.sql` + `tests/`, following the repo's established idioms: action-based CLI subparsers dispatching to `_cmd_*` functions, additive schema migrations in `db.init_db`, conventions tests that fail at the offending commit, and JSON-to-stdout output. No new frameworks, no new dependencies (stdlib only).

**Tech Stack:** Python 3 stdlib (sqlite3, argparse, gzip, pathlib), pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-enforcing-surfaces-design.md` — this plan implements its §9 phases 0, 1, 1b, and 2 (spec sections §3, §4.2, §5.1, §5.2 phases 0–1, §5.3). Read the spec sections for each task before implementing. Later phases (the log migration, carry-chains, question budget, storage phases 2–4, rule delivery A/B/C) get their own plans after this one lands.

## Global Constraints

- Suite must stay green: 1,005 tests passing as of 2026-08-29 (`python -m pytest -q`, ~42s).
- Timestamps are UTC ISO-8601 with trailing `Z` (`tools.db.utcnow()`).
- All CLI output is JSON to stdout via `_emit` (`tools/cli.py:19`) — `state` is the one deliberate exception: it renders text (spec §3.2), with `_emit` used only for errors.
- No API keys anywhere; nothing in this plan touches the network.
- The DB at `db/market_edge.db` is 5.5 GB and live — tests always use `tmp_path` fixtures; only conventions tests may open the real DB, read-only, following the skip-if-missing idiom in `tests/test_conventions.py:73`.
- CLAUDE.md edits in this plan are exactly the spec's §3.4 text — nothing else in CLAUDE.md changes here.
- Every commit message ends with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- New code follows the repo's comment idiom: comments state constraints and reasons, never narrate the next line.

---

### Task 1: `db backup` — dump the ledger without the snapshots

Spec §5.2 phase 0. The entire track record lives in one 5.5 GB WAL-mode file inside a OneDrive sync root. The backup is every table *except* `market_snapshots`, gzipped, written outside OneDrive (~30 MB).

**Files:**
- Create: `tools/backup.py`
- Modify: `tools/cli.py` (new `db` command group)
- Test: `tests/test_backup.py`

**Interfaces:**
- Consumes: `tools.db.connect`, `tools.db.utcnow`.
- Produces: `backup.backup_ledger(source_path: str | Path, dest_dir: str | Path, now: str | None = None) -> dict` returning `{"path": str, "tables": list[str], "bytes": int}`. CLI: `python -m tools.cli db backup [--dest DIR]`. Task 8 runs this for real before the relocation.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_backup.py
import gzip
import sqlite3

import pytest

from tools import backup, db


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.db"
    conn = db.connect(path)
    db.init_db(conn)
    with db.write(conn):
        conn.execute(
            "INSERT INTO market_snapshots (platform, market_id, captured_at,"
            " title, raw_json) VALUES ('kalshi', 'T-1',"
            " '2026-08-29T00:00:00Z', 't', '{}')"
        )
        conn.execute(
            "INSERT INTO settlements (kalshi_ticker, result)"
            " VALUES ('T-1', 'yes')"
        )
    conn.close()
    return path


def test_backup_holds_every_table_except_snapshots(source, tmp_path):
    result = backup.backup_ledger(source, tmp_path / "backups",
                                  now="2026-08-29T12:00:00Z")
    assert result["path"].endswith(".db.gz")
    assert "settlements" in result["tables"]
    assert "market_snapshots" not in result["tables"]

    from pathlib import Path
    raw = gzip.decompress(Path(result["path"]).read_bytes())
    restored = tmp_path / "restored.db"
    restored.write_bytes(raw)
    conn = sqlite3.connect(restored)
    try:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "settlements" in names and "opportunities" in names
        assert "market_snapshots" not in names
        assert conn.execute(
            "SELECT COUNT(*) FROM settlements").fetchone()[0] == 1
    finally:
        conn.close()


def test_backup_never_writes_into_the_source_directory(source, tmp_path):
    result = backup.backup_ledger(source, tmp_path / "elsewhere")
    assert str(tmp_path / "elsewhere") in result["path"]
    assert not list(source.parent.glob("*.gz"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_backup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.backup'`

- [ ] **Step 3: Implement `tools/backup.py`**

```python
"""Ledger backup: every table except market_snapshots, gzipped.

The working database is one WAL-mode file inside a OneDrive sync root —
a total-loss single point of failure for the entire track record. The
snapshots are excluded because they are 98% of the bytes and rebuildable
in spirit (prices re-fetch; judgments and settlements do not).
"""

from __future__ import annotations

import gzip
import os
import sqlite3
from pathlib import Path

from tools.db import DEFAULT_DB_PATH, utcnow


def default_dest() -> Path:
    """A non-synced local directory: %LOCALAPPDATA%\\market_edge\\backups."""
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "market_edge" / "backups"


def backup_ledger(
    source_path: str | Path = DEFAULT_DB_PATH,
    dest_dir: str | Path | None = None,
    now: str | None = None,
) -> dict:
    """Copy every table except market_snapshots into a gzipped SQLite file.

    Reads the source through a read-only URI so a backup can never write
    to the live database, and builds a real .db (not a text dump) so a
    restore is `gunzip` + open.
    """
    source_path = Path(source_path)
    dest_dir = Path(dest_dir) if dest_dir else default_dest()
    dest_dir.mkdir(parents=True, exist_ok=True)

    stamp = (now or utcnow()).replace("-", "").replace(":", "").replace("Z", "")
    raw_path = dest_dir / f"market_edge_ledger_{stamp}.db"

    src = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    out = sqlite3.connect(raw_path)
    tables: list[str] = []
    try:
        ddl_rows = src.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%' AND name != 'market_snapshots'"
            " AND sql IS NOT NULL"
        ).fetchall()
        # Parameterized plain-path ATTACH: a `file:...?mode=ro` URI string
        # is only honoured when the connection enables URIs, and silently
        # opens a literal file named `file:...` otherwise. The read-only
        # guarantee lives on `src` above; this handle only SELECTs.
        out.execute("ATTACH DATABASE ? AS src", (str(source_path),))
        for row in ddl_rows:
            out.execute(row["sql"])
            out.execute(
                f'INSERT INTO main."{row["name"]}"'
                f' SELECT * FROM src."{row["name"]}"'
            )
            tables.append(row["name"])
        out.commit()
        out.execute("DETACH DATABASE src")
    finally:
        out.close()
        src.close()

    gz_path = raw_path.with_suffix(".db.gz")
    with open(raw_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        while chunk := f_in.read(1 << 20):
            f_out.write(chunk)
    raw_path.unlink()
    return {
        "path": str(gz_path),
        "tables": sorted(tables),
        "bytes": gz_path.stat().st_size,
    }
```

- [ ] **Step 4: Wire the CLI group**

In `tools/cli.py`, add after `_cmd_rank` (around line 285):

```python
def _cmd_db(args) -> int:
    from tools import backup as backup_mod
    if args.action == "backup":
        _emit(backup_mod.backup_ledger(
            args.db or db.DEFAULT_DB_PATH, dest_dir=args.dest
        ))
    return 0
```

And in `build_parser()`, before `return parser`:

```python
    p = sub.add_parser("db", help="database operations")
    p.set_defaults(func=_cmd_db)
    dbsub = p.add_subparsers(dest="action", required=True)
    dbackup = dbsub.add_parser(
        "backup",
        help="gzip every table except market_snapshots to a non-synced dir",
    )
    dbackup.add_argument(
        "--dest", default=None,
        help=r"destination directory (default %LOCALAPPDATA%\market_edge\backups)",
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_backup.py -v`
Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add tools/backup.py tools/cli.py tests/test_backup.py
git commit -m "feat: db backup — ledger dump excluding snapshots (spec phase 0)"
```

---

### Task 2: §5.1 hygiene + the docs-path conventions test

Fix the three doc drifts, move the migration artifacts out of the top level, and land the test that catches the next broken path at the commit that breaks it.

**Files:**
- Modify: `README.md:60` (the `docs/theory-specs/` row)
- Modify: `docs/DEDUP_PLAN.md:1-6` (header)
- Move: `migrate_kalshi_trader.py` → `attic/kalshi_trader_migration/migrate_kalshi_trader.py`; `db/opportunities.json` → `attic/kalshi_trader_migration/opportunities.json`
- Create: `attic/kalshi_trader_migration/README.md`
- Test: `tests/test_conventions.py` (new test appended)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `test_every_repo_path_named_in_docs_resolves` — later plans extend its scan set (spec §6.6, §7.9); keep its `_DOC_FILES` and `_ALLOWED_MISSING` module-level so extension is one-line.

- [ ] **Step 1: Write the failing test** (append to `tests/test_conventions.py`)

```python
import re

#: Docs whose backticked repo paths must resolve. Spec §5.1; later plans
#: add theories/*/CLAUDE.md (§7.9) and the dated-citation check (§6.6).
_DOC_FILES = ("README.md", "CLAUDE.md", "tools/README.md")

#: Paths that legitimately exist only at runtime (gitignored artifacts).
_ALLOWED_MISSING = re.compile(r"^(db/.*\.(db|db-wal|db-shm)|STATE\.md)$")

_PATH_LIKE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*(/[A-Za-z0-9_.\-]+)+/?$")


def _doc_paths():
    docs = [ROOT / f for f in _DOC_FILES]
    docs += sorted(ROOT.glob("theories/*/THEORY.md"))
    for doc in docs:
        for span in re.findall(r"`([^`\n]+)`", doc.read_text(encoding="utf-8")):
            # Only bare repo paths: no spaces/flags, at least one slash, no
            # placeholders (<slug>), globs, code, or URLs.
            if " " in span or "://" in span or "<" in span or "*" in span:
                continue
            if not _PATH_LIKE.match(span):
                continue
            yield doc.name, span


def test_every_repo_path_named_in_docs_resolves():
    """A doc that names a path nobody can open is worse than no doc: it
    sends the next session somewhere that does not exist. Fails at the
    commit that breaks the path, not months later."""
    missing = [
        f"{doc}: `{span}`"
        for doc, span in _doc_paths()
        if not (ROOT / span).exists() and not _ALLOWED_MISSING.match(span)
    ]
    assert missing == [], (
        "a doc names a repo path that does not resolve — fix the doc or "
        "add a deliberate runtime-artifact exception:\n" + "\n".join(missing)
    )
```

- [ ] **Step 2: Run it to verify it fails on the known drift**

Run: `python -m pytest tests/test_conventions.py::test_every_repo_path_named_in_docs_resolves -v`
Expected: FAIL naming at least `README.md: docs/theory-specs/`. If it also names paths this plan does not know about, fix each the same way: correct the doc if the path moved, or extend `_ALLOWED_MISSING` only for genuine runtime artifacts.

- [ ] **Step 3: Fix the drift**

In `README.md`, change line 60:

```
| `docs/theory-specs/` | Sketches of proposed theories not yet built |
```
to
```
| `docs/superpowers/specs/theories/` | Sketches of proposed theories not yet built |
```

In `docs/DEDUP_PLAN.md`, change the header lines 3–4 from:

```
**Session:** 2026-08-27. **Status:** diagnosed and designed; tests written and
failing by design; **implementation not started.**
```
to
```
**Session:** 2026-08-27. **Status:** SUPERSEDED — implemented in `f6a1047`;
the authoritative design is `docs/superpowers/specs/2026-08-27-position-identity-design.md`.
Kept as the diagnostic narrative behind that spec.
```

- [ ] **Step 4: Move the migration artifacts**

```bash
mkdir -p attic/kalshi_trader_migration
git mv migrate_kalshi_trader.py attic/kalshi_trader_migration/
git mv db/opportunities.json attic/kalshi_trader_migration/opportunities.json
grep -rn "migrate_kalshi_trader\|db/opportunities.json" --include='*.py' --include='*.md' . | grep -v RESEARCH_LOG.md | grep -v attic/
```

Fix any hit the grep returns outside `RESEARCH_LOG.md` (the log is append-only history and is never edited for this). Then create `attic/kalshi_trader_migration/README.md`:

```markdown
# kalshi_trader migration (one-time, completed 2026-08-23)

`migrate_kalshi_trader.py` imported the predecessor project's track record
from `opportunities.json`. It ran once; it is kept because the v1 data it
can regenerate was deleted on the user's instruction (RESEARCH_LOG.md,
2026-08-23 v2-bump addendum) and this script is the only way back. If it
must run again, note it wrote to the pre-position-identity schema and
will need `migrate-positions` run afterwards.
```

- [ ] **Step 5: Run the test to verify it passes, then the full suite**

Run: `python -m pytest tests/test_conventions.py -v` then `python -m pytest -q`
Expected: all PASS (moving the script must not break any import — the grep in Step 4 is what catches one).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: fix doc drift, retire migration artifacts to attic/, add docs-path conventions test (spec 5.1)"
```

---

### Task 3: `mark-taken --ticker` — one less lookup

Spec §4.2. `--ticker` resolves to the most recent open position on that ticker; ambiguity (two theories open on one ticker, no `--theory`) refuses with the candidate list rather than guessing — the CLI is used by non-interactive agents, so "asking for confirmation" means a refusal that names what to pass.

**Files:**
- Modify: `tools/ledger.py` (new resolver function, after `get_opportunity` around line 866)
- Modify: `tools/cli.py` (`_cmd_opportunities` lines 154–160 and the `mark` parser lines 412–427)
- Test: `tests/test_ledger.py` (append; follow the file's existing fixture style — read its top before writing)

**Interfaces:**
- Consumes: `ledger.get_opportunity`, `ledger.mark_user_action` (signature at `tools/ledger.py:1061`), `ledger.VALID_USER_ACTIONS`.
- Produces: `ledger.resolve_ticker(conn, ticker: str, theory_id: str | None = None) -> sqlite3.Row` — returns the single matching open-position row or raises `ValueError` listing candidates as `theory_id:id` pairs. Raises `KeyError(ticker)` when nothing matches.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_ledger.py`, reusing that file's existing `conn` fixture and record helpers — mirror how its other tests create opportunities)

```python
def test_resolve_ticker_finds_the_latest_attempt(conn):
    _record(conn, kalshi_ticker="KXFOO-T1", theory_id="t1")
    row = ledger.resolve_ticker(conn, "KXFOO-T1")
    assert row["kalshi_ticker"] == "KXFOO-T1"


def test_resolve_ticker_refuses_ambiguity_without_theory(conn):
    _record(conn, kalshi_ticker="KXFOO-T1", theory_id="t1")
    _record(conn, kalshi_ticker="KXFOO-T1", theory_id="t2")
    with pytest.raises(ValueError, match="pass --theory"):
        ledger.resolve_ticker(conn, "KXFOO-T1")
    row = ledger.resolve_ticker(conn, "KXFOO-T1", theory_id="t2")
    assert row["theory_id"] == "t2"


def test_resolve_ticker_unknown_raises_keyerror(conn):
    with pytest.raises(KeyError):
        ledger.resolve_ticker(conn, "KXNOPE-T1")
```

(`_record(conn, **overrides)` already exists at `tests/test_ledger.py:22` — it wraps `ledger.record_opportunity` with defaults `theory_id="t1"`, `kalshi_ticker="KXTEST-26"`, `outcome="yes"`, `entry_price=0.40`, `edge_pts_net=6.0` and returns `(opp_id, created)`. Reuse it as-is.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ledger.py -k resolve_ticker -v`
Expected: FAIL with `AttributeError: ... no attribute 'resolve_ticker'`

- [ ] **Step 3: Implement `ledger.resolve_ticker`** (place after `get_opportunity`)

```python
def resolve_ticker(
    conn: sqlite3.Connection, ticker: str, theory_id: str | None = None
) -> sqlite3.Row:
    """The open position `mark-taken --ticker` should act on.

    Most recent sighting wins. More than one theory open on the ticker is
    a refusal, not a guess — marking the wrong theory's row corrupts the
    only realized-ROI signal this system gets — so the error names each
    candidate and the flag that disambiguates.
    """
    rows = conn.execute(
        """
        SELECT * FROM opportunities
         WHERE kalshi_ticker = ? AND (? IS NULL OR theory_id = ?)
         ORDER BY last_seen_at DESC
        """,
        (ticker, theory_id, theory_id),
    ).fetchall()
    if not rows:
        raise KeyError(ticker)
    theories_open = {r["theory_id"] for r in rows}
    if len(theories_open) > 1:
        names = ", ".join(
            f"{r['theory_id']}:{r['id']}" for r in rows
        )
        raise ValueError(
            f"{ticker} has open positions under more than one theory "
            f"({names}); pass --theory to say which one you acted on"
        )
    return rows[0]
```

- [ ] **Step 4: Wire the CLI**

In `_cmd_opportunities` (`tools/cli.py:154`), replace the `mark-taken` branch:

```python
        elif args.action == "mark-taken":
            opp_id = args.id
            if opp_id is None:
                if not args.ticker:
                    raise SystemExit("pass an opportunity id or --ticker")
                row = ledger.resolve_ticker(
                    conn, args.ticker, theory_id=args.mark_theory
                )
                opp_id = row["id"]
                print(
                    f"matched {row['kalshi_ticker']} -> opportunity "
                    f"{opp_id} ({row['theory_id']} v{row['theory_version']})",
                    file=sys.stderr,
                )
            ledger.mark_user_action(
                conn, opp_id, args.value, size=args.size,
                reason=args.reason, theory_id=args.mark_theory,
                price=args.price,
            )
            _emit(dict(ledger.get_opportunity(conn, opp_id)))
```

In the parser (line 415), make `id` optional and add `--ticker`:

```python
    mark.add_argument("id", type=int, nargs="?", default=None)
    mark.add_argument(
        "--ticker", default=None,
        help="resolve the position by Kalshi ticker instead of id "
             "(latest open attempt wins; ambiguity across theories refuses "
             "and lists candidates)",
    )
```

- [ ] **Step 5: Run the tests and the full suite**

Run: `python -m pytest tests/test_ledger.py -k resolve_ticker -v && python -m pytest -q`
Expected: PASS, suite green.

- [ ] **Step 6: Commit**

```bash
git add tools/ledger.py tools/cli.py tests/test_ledger.py
git commit -m "feat: mark-taken --ticker resolves the position without a listing (spec 4.2)"
```

---

### Task 4: the force floor on `get_board` (spec §5.3, phase 1b)

Ruled 2026-08-29: `force=True` honors a ~30-minute floor. With concurrent sessions, unconditional force means sessions reasoning over *different boards*; comparability is the point, storage is incidental.

**Files:**
- Modify: `tools/board.py` (constant + `get_board` lines 116–140)
- Test: `tests/test_board.py` (modify `test_force_refetches_even_when_fresh` line 92; add one test)

**Interfaces:**
- Consumes: `board.board_info`, `board._rebuild` (both exist).
- Produces: `board.FORCE_FLOOR_MINUTES = 30` (module constant other code may cite).

- [ ] **Step 1: Update/write the tests**

Replace `test_force_refetches_even_when_fresh` (its *intent* — force can refetch inside the 4-hour window — survives; the fixture moves past the floor):

```python
def test_force_refetches_past_the_floor(conn, monkeypatch):
    # 31 minutes old: stale under the force floor, fresh under the
    # 4-hour default -- exactly the window where force must still act.
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:29:00Z")
    calls = []
    monkeypatch.setattr(board.kalshi_markets, "list_open",
                        lambda: calls.append(1) or _board(9))
    got = board.get_board(conn, force=True, now=NOW)
    assert len(calls) == 1 and len(got) == 9


def test_force_honours_the_floor_on_a_very_fresh_board(conn, monkeypatch):
    # Ruled 2026-08-29 (spec 5.3): concurrent sessions must reason over
    # the same board, so a force within the floor reuses, never refetches.
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:59:00Z")

    def boom():
        raise AssertionError("force within the floor must not refetch")
    monkeypatch.setattr(board.kalshi_markets, "list_open", boom)
    got = board.get_board(conn, force=True, now=NOW)
    assert [m.ticker for m in got] == ["T-0", "T-1", "T-2"]
```

- [ ] **Step 2: Run to verify the new test fails**

Run: `python -m pytest tests/test_board.py -k force -v`
Expected: `test_force_honours_the_floor_on_a_very_fresh_board` FAILS (refetches); `test_force_refetches_past_the_floor` PASSES.

- [ ] **Step 3: Implement the floor**

In `tools/board.py`, add below `DEFAULT_MAX_AGE_MINUTES`:

```python
#: The floor `force=True` honours. Ruled 2026-08-29 (enforcing-surfaces
#: spec 5.3): with 4-5 concurrent sessions, unconditional force makes
#: them reason over *different* boards; a board younger than this is the
#: session's board, force or not. Re-quoting a handful of tickers is
#: `markets.quotes()`, which no floor touches.
FORCE_FLOOR_MINUTES = 30
```

In `get_board`, replace the `if not force:` block:

```python
    info = board_info(conn, now=now)
    floor = FORCE_FLOOR_MINUTES if force else max_age_minutes
    if info is not None and info["age_minutes"] <= floor:
        return _rebuild(conn, info["captured_at"])
```

Also extend the docstring's `force=True` sentence with: `A board younger than FORCE_FLOOR_MINUTES is reused even under force (ruled 2026-08-29).`

- [ ] **Step 4: Run the board tests and full suite**

Run: `python -m pytest tests/test_board.py -v && python -m pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/board.py tests/test_board.py
git commit -m "feat: get_board force honours a 30-minute floor (ruled 2026-08-29, spec 5.3)"
```

---

### Task 5: `cli state` — orientation from the DB

Spec §3.2. One command rendering six panels from the DB; each panel prints from its table if it exists and a one-line `not yet tracked` stub if not (the degradation contract is behaviour and is tested). `--write` emits `STATE.md` (gitignored).

**Files:**
- Create: `tools/state.py`
- Modify: `tools/cli.py` (new `state` command), `.gitignore` (add `STATE.md`)
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `db._table_exists(conn, name)` (`tools/db.py:305`), `theories.list_theories`, `theories.list_pending_retirement`, `ledger.list_opportunities`.
- Produces: `state.render_state(conn, now: str | None = None) -> str`. Task 6 re-runs its STANDING panel against the new `rulings` table. The spec's panel/source map is the §3.2 table — implement exactly those sources.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_state.py
import pytest

from tools import db, state


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def test_state_renders_every_panel_header(conn):
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    for panel in ("THEORIES", "STANDING", "EVIDENCE", "WINDOWS",
                  "QUEUE", "FRESHNESS"):
        assert panel in text


def test_absent_tables_render_stubs_not_errors(conn):
    # rulings (phase 2), theory_versions (phase 6) and data_windows
    # (phase 7) do not exist yet -- the shape is stable from day one and
    # panels light up as phases land (spec 3.2).
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "not yet tracked" in text


def test_state_reflects_theories_and_freshness(conn):
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    with db.write(conn):
        conn.execute(
            "INSERT INTO market_snapshots (platform, market_id, captured_at,"
            " title, raw_json) VALUES ('kalshi', 'T-1',"
            " '2026-08-29T10:00:00Z', 't', '{}')"
        )
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "demo_theory" in text
    assert "last board pull" in text and "2026-08-29T10:00:00Z" in text


def test_write_flag_emits_state_md(conn, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state.write_state(conn, now="2026-08-29T12:00:00Z")
    assert (tmp_path / "STATE.md").read_text(encoding="utf-8").startswith("#")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.state'`

- [ ] **Step 3: Implement `tools/state.py`**

```python
"""The session's orientation surface, rendered from the DB (spec 3.2).

Replaces "read the last ~30 lines of RESEARCH_LOG.md": the log is the
audit trail, this is the state. Each panel names its table and renders a
one-line stub when that table has not shipped yet -- the shape is stable
from day one, panels light up as phases land. Text output on purpose:
this is the one CLI surface built for human orientation, not parsing.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from tools import theories
from tools.db import utcnow, _table_exists

_STUB = "  (not yet tracked — table {table} has not shipped)"


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))


def _age_days(stamp: str | None, now: str) -> str:
    if not stamp:
        return "never"
    days = max(0.0, (_parse(now) - _parse(stamp)).total_seconds() / 86400.0)
    return f"{days:.1f}d ago ({stamp})"


def _one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def _theories_panel(conn) -> list[str]:
    lines = []
    for t in theories.list_theories(conn):
        settled = _one(conn, """
            SELECT COUNT(*) FROM opportunities o
              JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
             WHERE o.theory_id = ? AND o.theory_version = ?
        """, (t["id"], t["version"]))
        rows = _one(conn,
                    "SELECT COUNT(*) FROM opportunities"
                    " WHERE theory_id = ? AND theory_version = ?",
                    (t["id"], t["version"]))
        chain = "chain n/a"
        if _table_exists(conn, "theory_versions"):
            chain = "chain ready"          # phase 6 replaces this with chain n
        lines.append(
            f"  {t['id']:<22} {t['status']:<13} v{t['version']}"
            f"  rows {rows}  settled {settled}  [{chain}]"
        )
    return lines or ["  (no theories registered)"]


def _standing_panel(conn) -> list[str]:
    lines = []
    for t in theories.list_pending_retirement(conn):
        lines.append(f"  pending retirement: {t['id']} — {t['retirement_rationale']}")
    if _table_exists(conn, "rulings"):
        for r in conn.execute(
            "SELECT ruled_at, authority, subject, ruling FROM rulings"
            " WHERE status = 'binding' ORDER BY ruled_at"
        ):
            lines.append(
                f"  ruling [{r['subject']}] ({r['authority']},"
                f" {str(r['ruled_at'])[:10]}): {r['ruling'][:100]}"
            )
    else:
        lines.append(_STUB.format(table="rulings"))
    parked = _one(conn, "SELECT COUNT(*) FROM ideas WHERE status = 'parked'")
    paused = _one(conn, "SELECT COUNT(*) FROM theories WHERE status = 'paused'")
    lines.append(f"  blocked: {parked or 0} parked idea(s), {paused or 0} paused theory(ies)")
    return lines


def _evidence_panel(conn) -> list[str]:
    lines = []
    for t in theories.list_theories(conn, running_only=True):
        row = conn.execute(
            """
            SELECT calibration_edge_net, n, n_clusters FROM scores
             WHERE theory_id = ? AND theory_version = ?
               AND run_mode = 'live' AND disposition = 'all'
             ORDER BY computed_at DESC LIMIT 1
            """,
            (t["id"], t["version"]),
        ).fetchone()
        tier = _one(conn,
                    "SELECT tier FROM backtest_runs WHERE theory_id = ?"
                    " ORDER BY created_at DESC LIMIT 1", (t["id"],))
        if row is None:
            lines.append(f"  {t['id']:<22} no live score at v{t['version']}"
                         f"  [best backtest tier {tier or '—'}]")
        else:
            lines.append(
                f"  {t['id']:<22} edge_net {row['calibration_edge_net']}"
                f"  n {row['n']}  clusters {row['n_clusters']}"
                f"  [tier {tier or '—'}]"
            )
    return lines or ["  (no running theories)"]


def _windows_panel(conn) -> list[str]:
    if not _table_exists(conn, "data_windows"):
        return [_STUB.format(table="data_windows")]
    return [
        f"  {w['slug']:<40} questions {q}"
        for w in conn.execute("SELECT slug FROM data_windows ORDER BY slug")
        for q in [_one(conn,
                       "SELECT COUNT(*) FROM hypothesis_tests"
                       " WHERE window_slug = ?", (w["slug"],))]
    ] or ["  (no windows registered)"]


def _queue_panel(conn) -> list[str]:
    rows = conn.execute(
        """
        SELECT o.id, o.theory_id, o.kalshi_ticker, o.first_seen_at
          FROM opportunities o
          LEFT JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
         WHERE o.disposition = 'endorsed' AND o.user_action = 'untouched'
           AND s.kalshi_ticker IS NULL
         ORDER BY o.first_seen_at DESC LIMIT 10
        """
    ).fetchall()
    total = _one(conn, """
        SELECT COUNT(*) FROM opportunities o
          LEFT JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
         WHERE o.disposition = 'endorsed' AND o.user_action = 'untouched'
           AND s.kalshi_ticker IS NULL
    """)
    lines = [f"  {r['id']:>6}  {r['theory_id']:<22} {r['kalshi_ticker']}"
             f"  since {str(r['first_seen_at'])[:10]}" for r in rows]
    lines.append(f"  ({total or 0} endorsed, untouched, unsettled in total)")
    return lines


def _freshness_panel(conn, now: str) -> list[str]:
    board = _one(conn, "SELECT MAX(captured_at) FROM market_snapshots"
                       " WHERE platform = 'kalshi'")
    settle = _one(conn, "SELECT MAX(resolved_at) FROM settlements")
    taken = _one(conn, "SELECT MAX(recorded_at) FROM opportunity_fills") \
        if _table_exists(conn, "opportunity_fills") else None
    return [
        f"  last board pull:  {_age_days(board, now)}",
        f"  last settlement:  {_age_days(settle, now)}",
        f"  last mark-taken:  {_age_days(taken, now)}",
        "  last bets render: (not yet tracked — raise-lane spec)",
    ]


def render_state(conn: sqlite3.Connection, now: str | None = None) -> str:
    now = now or utcnow()
    sections = (
        ("THEORIES", _theories_panel(conn)),
        ("STANDING", _standing_panel(conn)),
        ("EVIDENCE", _evidence_panel(conn)),
        ("WINDOWS", _windows_panel(conn)),
        ("QUEUE", _queue_panel(conn)),
        ("FRESHNESS", _freshness_panel(conn, now)),
    )
    out = [f"# state @ {now}"]
    for name, lines in sections:
        out.append(f"\n{name}")
        out.extend(lines)
    return "\n".join(out) + "\n"


def write_state(conn: sqlite3.Connection, now: str | None = None) -> Path:
    path = Path("STATE.md")
    path.write_text(render_state(conn, now=now), encoding="utf-8")
    return path
```

(If `test_state_reflects_theories_and_freshness` fails because `theories.register` requires more arguments, match its real signature from `tools/theories.py` — the CLI calls it as `theories.register(conn, args.id, args.name, args.path)`.)

- [ ] **Step 4: Wire the CLI and gitignore**

In `tools/cli.py`:

```python
def _cmd_state(args) -> int:
    from tools import state as state_mod
    conn = _connect(args)
    try:
        text = state_mod.render_state(conn)
        print(text)
        if args.write:
            state_mod.write_state(conn)
    finally:
        conn.close()
    return 0
```

Parser (before `return parser`):

```python
    p = sub.add_parser(
        "state",
        help="current research state from the DB — the orientation surface",
    )
    p.add_argument("--write", action="store_true",
                   help="also write STATE.md (gitignored) for humans")
    p.set_defaults(func=_cmd_state)
```

Append `STATE.md` on its own line to `.gitignore`.

- [ ] **Step 5: Run the tests, then eyeball the real thing**

Run: `python -m pytest tests/test_state.py -v && python -m tools.cli state`
Expected: tests PASS; the live render shows the five real theories, the stub lines for `rulings`/`data_windows`, and plausible freshness stamps. Paste the live output into the task summary.

- [ ] **Step 6: Make the docs point here (spec §3.4 — the offsetting deletion)**

In `CLAUDE.md`, replace the `RESEARCH_LOG.md` bullet under **Data conventions**:

```
- **`RESEARCH_LOG.md`** carries continuity between sessions — read its tail
  when starting, append when finishing.
```
with:
```
- **`RESEARCH_LOG.md`** carries continuity between sessions — append when
  finishing. It is append-only and now too large to read; orient with
  `python -m tools.cli state`, which renders current state from the DB, and
  read the log for the reasoning behind a specific ruling it names.
```

In `.claude/skills/go/SKILL.md`, replace lines 45–46:

```
Read the last ~30 lines of `RESEARCH_LOG.md` for what the previous session
was doing. For each theory that runs, `python -m tools.cli score report <id>`.
```
with:
```
Run `python -m tools.cli state` — the orientation surface, rendered from
the DB. For each theory that runs, `python -m tools.cli score report <id>`.
```

- [ ] **Step 7: Full suite and commit**

Run: `python -m pytest -q`
Expected: green.

```bash
git add tools/state.py tools/cli.py tests/test_state.py .gitignore CLAUDE.md .claude/skills/go/SKILL.md
git commit -m "feat: cli state — orientation renders from the DB; CLAUDE.md and go point at it (spec 3.2, 3.4)"
```

---

### Task 6: the `rulings` table + twelve-ruling backfill

Spec §3.3. Rulings become rows; the log keeps the reasoning; `state` STANDING lights up.

**Files:**
- Modify: `db/schema.sql` (new table, after `theory_facts`)
- Create: `tools/rulings.py`
- Modify: `tools/cli.py` (new `rulings` group)
- Test: `tests/test_rulings.py`
- Modify: `tests/test_state.py` (STANDING now renders rulings on a fresh DB — the stub assertion in `test_absent_tables_render_stubs_not_errors` must switch to `data_windows`' stub only; update that test's comment accordingly)

**Interfaces:**
- Consumes: `db.schema_statement` pattern (table must end with `\n);` for it), `state._standing_panel` (already reads the table if present).
- Produces: `rulings.record(conn, ruling: str, authority: str, subject: str, ruled_at: str | None = None, scope_out: str | None = None, status: str = "binding", log_entry: str | None = None) -> int` (returns row id); `rulings.list_rulings(conn, status: str | None = None) -> list[sqlite3.Row]`; `rulings.set_status(conn, ruling_id: int, status: str) -> None`. CLI: `rulings record|list|status`.

- [ ] **Step 1: Add the table to `db/schema.sql`** (spec §3.3 schema, verbatim, with a CHECK in the repo's idiom)

```sql
-- Binding rulings, extracted from prose (enforcing-surfaces spec 3.3).
-- The log keeps the reasoning; this row carries the binding text, so a
-- session can know what binds without reading a 25k-word journal.
CREATE TABLE IF NOT EXISTS rulings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ruled_at  TEXT NOT NULL,
    authority TEXT NOT NULL CHECK (authority IN ('user', 'supervisor')),
    subject   TEXT NOT NULL,
    ruling    TEXT NOT NULL,
    scope_out TEXT,
    status    TEXT NOT NULL DEFAULT 'binding'
              CHECK (status IN ('binding', 'implemented', 'superseded')),
    log_entry TEXT
);
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_rulings.py
import pytest

from tools import db, rulings


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def test_record_and_list_roundtrip(conn):
    rid = rulings.record(
        conn, "clustered SEs are reported beside every score",
        authority="supervisor", subject="scoring",
        ruled_at="2026-08-29T00:00:00Z",
        log_entry="2026-08-29 (cont.) — attempt-level scoring landed",
    )
    rows = rulings.list_rulings(conn)
    assert [r["id"] for r in rows] == [rid]
    assert rows[0]["status"] == "binding"


def test_status_transitions_and_filtering(conn):
    rid = rulings.record(conn, "x", authority="user", subject="schema")
    rulings.set_status(conn, rid, "implemented")
    assert rulings.list_rulings(conn, status="binding") == []
    assert rulings.list_rulings(conn, status="implemented")[0]["id"] == rid


def test_bad_authority_refused(conn):
    with pytest.raises(Exception):
        rulings.record(conn, "x", authority="claude", subject="schema")


def test_state_standing_shows_binding_rulings(conn):
    from tools import state
    rulings.record(conn, "the force floor is adopted", authority="user",
                   subject="lifecycle", ruled_at="2026-08-29T00:00:00Z")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "force floor" in text
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_rulings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.rulings'`

- [ ] **Step 4: Implement `tools/rulings.py`**

```python
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
```

- [ ] **Step 5: Wire the CLI group**

```python
def _cmd_rulings(args) -> int:
    from tools import rulings as rulings_mod
    conn = _connect(args)
    try:
        if args.action == "record":
            rid = rulings_mod.record(
                conn, args.ruling, authority=args.authority,
                subject=args.subject, ruled_at=args.ruled_at,
                scope_out=args.scope_out, log_entry=args.log_entry,
            )
            _emit({"id": rid})
        elif args.action == "list":
            _emit(_rows(rulings_mod.list_rulings(conn, status=args.status)))
        elif args.action == "status":
            rulings_mod.set_status(conn, args.id, args.value)
            _emit({"id": args.id, "status": args.value})
    finally:
        conn.close()
    return 0
```

Parser:

```python
    p = sub.add_parser("rulings", help="binding rulings extracted from prose")
    p.set_defaults(func=_cmd_rulings)
    rsub = p.add_subparsers(dest="action", required=True)
    rrec = rsub.add_parser("record")
    rrec.add_argument("ruling", help="the binding text, one sentence or two")
    rrec.add_argument("--authority", required=True,
                      choices=("user", "supervisor"))
    rrec.add_argument("--subject", required=True,
                      help="e.g. scoring | schema | lifecycle | governance")
    rrec.add_argument("--ruled-at", dest="ruled_at", default=None)
    rrec.add_argument("--scope-out", dest="scope_out", default=None,
                      help="what the ruling explicitly excluded")
    rrec.add_argument("--log-entry", dest="log_entry", default=None,
                      help="the RESEARCH_LOG.md date heading with the reasoning")
    rlist = rsub.add_parser("list")
    rlist.add_argument("--status", default=None,
                       choices=("binding", "implemented", "superseded"))
    rst = rsub.add_parser("status")
    rst.add_argument("id", type=int)
    rst.add_argument("value", choices=("binding", "implemented", "superseded"))
```

- [ ] **Step 6: Run tests, fix the state stub test**

Run: `python -m pytest tests/test_rulings.py tests/test_state.py -v`
`test_absent_tables_render_stubs_not_errors` now sees a real (empty) rulings table — assert the `data_windows` stub specifically:

```python
def test_absent_tables_render_stubs_not_errors(conn):
    # theory_versions (phase 6) and data_windows (phase 7) do not exist
    # yet -- the shape is stable from day one and panels light up as
    # phases land (spec 3.2).
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "not yet tracked — table data_windows" in text
```

Expected: all PASS.

- [ ] **Step 7: Backfill the twelve rulings against the real DB**

The eight from the 2026-08-29 spec review, exact commands (authority `user`, `--ruled-at 2026-08-29T00:00:00Z` on each):

```bash
python -m tools.cli rulings record "Theory-local RESEARCH_LOG.md content migrates into the owning theory's NOTES.md when possible: T entries wholesale, M entries split one at a time, X entries stay (reverses theory-locality plan §22)." --authority user --subject governance --ruled-at 2026-08-29T00:00:00Z --log-entry "2026-08-29 — Enforcing-surfaces spec reviewed and corrected; user ruled: migrate the log, adopt the bar"
python -m tools.cli rulings record "The log promotion bar is adopted: an entry is earned by a fact that changes how a session that never touched this theory would act — mechanisms, rulings, precedents, constraints, breakthroughs, corrections; theory results are a headline plus a pointer." --authority user --subject governance --ruled-at 2026-08-29T00:00:00Z --log-entry "2026-08-29 — Enforcing-surfaces spec reviewed and corrected; user ruled: migrate the log, adopt the bar"
python -m tools.cli rulings record "No paper lane: user_action stays untouched/taken/skipped; divergence input comes from the raise lane's raised-but-never-taken population." --authority user --subject scoring --ruled-at 2026-08-29T00:00:00Z --log-entry "2026-08-29 — Three more user rulings on the enforcing-surfaces spec"
python -m tools.cli rulings record "db/ leaves OneDrive by relocation plus NTFS junction (default %LOCALAPPDATA%\\market_edge\\db), with junction-sync verification and a no-open-sessions window." --authority user --subject schema --ruled-at 2026-08-29T00:00:00Z --log-entry "2026-08-29 — Three more user rulings on the enforcing-surfaces spec"
python -m tools.cli rulings record "get_board(force=True) honours a ~30-minute floor; comparability across concurrent sessions is the point." --authority user --subject lifecycle --ruled-at 2026-08-29T00:00:00Z --log-entry "2026-08-29 — Three more user rulings on the enforcing-surfaces spec"
python -m tools.cli rulings record "The prefer-mechanical rule is reframed as a division of labour: a model categorizes, measurement quantifies; any edge an LLM-judged theory claims must trace to backtesting or settled history, never the model guessing; interpretive theories stay first-class." --authority user --subject governance --ruled-at 2026-08-29T00:00:00Z --log-entry "2026-08-29 — RULING: the prefer-mechanical rule reframed as a division of labour, consolidation performed"
python -m tools.cli rulings record "Task-time rules have one home — the skill that owns the activity, not CLAUDE.md: the ten owned task-time rules move atomically, held by a single-home manifest test; approval is scoped to exactly those ten." --authority user --subject governance --ruled-at 2026-08-29T00:00:00Z --log-entry "2026-08-29 — RULING: task-time rules get one home — their skill, not CLAUDE.md"
python -m tools.cli rulings record "The expert-agent architecture is the repo's stated architecture: a theory expert boots from the cardinal CLAUDE.md + skills + theory folder; the supervisor supervises from shared structures alone; theory-level CLAUDE.md and theory-scoped skills are the mechanisms." --authority user --subject governance --ruled-at 2026-08-29T00:00:00Z --log-entry "2026-08-29 — RULING: the expert-agent architecture — theory-level context and skills"
```

The four older ones live in the log at these headings (verified 2026-08-29): `RESEARCH_LOG.md:2696` "supervisor rulings: attempt-level scoring; the anchor rule at scale", `:2733` "scoring ruling completed: dedupe, non-decisions, clustering", `:2770` "attempt-level scoring landed; schema ruling for cluster-n" (this entry also carries the `bucket_rates` carve-out and the blocked skill edits). Read those three entries, extract per ruling: (1) attempt-level scoring, (2) the cluster-`n` schema ruling, (3) the `bucket_rates` out-of-scope carve-out (record the carve-out in `--scope-out` of the clustering ruling OR as its own row — its own row, `subject scoring`), (4) the blocked skill edits (subject `governance`, status stays `binding`). Record each with `--authority supervisor` (they were supervisor rulings under the standing delegation), the entry's date, and `--log-entry` set to the exact heading text. Then verify:

```bash
python -m tools.cli rulings list
python -m tools.cli state
```

Expected: 12 rows; STANDING shows them.

- [ ] **Step 8: Full suite and commit**

```bash
python -m pytest -q
git add db/schema.sql tools/rulings.py tools/cli.py tests/test_rulings.py tests/test_state.py
git commit -m "feat: rulings become rows, backfilled with the twelve on record (spec 3.3)"
```

---

### Task 7: run the real backup, then relocate db/ out of OneDrive

Spec §5.2 phases 0–1, ruled: relocation + junction. **This task changes where the live database lives. It runs only with the user's go-ahead in the moment, because every other Claude session and open tool on this machine must be closed first.**

**Files:** none in-repo except `.gitignore` sanity; this is an ops task.

**Interfaces:**
- Consumes: Task 1's `db backup`.
- Produces: `db/` as an NTFS junction to `%LOCALAPPDATA%\market_edge\db\`; a verified `.db.gz` ledger backup.

- [ ] **Step 1: Take the real backup**

```bash
python -m tools.cli db backup
```

Expected: JSON naming a `.db.gz` (~tens of MB) under `%LOCALAPPDATA%\market_edge\backups\`. Verify it restores: `python -c "import gzip,sqlite3,tempfile,os; raw=gzip.decompress(open(r'<path from output>','rb').read()); p=tempfile.mktemp(suffix='.db'); open(p,'wb').write(raw); c=sqlite3.connect(p); print(c.execute('SELECT COUNT(*) FROM opportunities').fetchone()); c.close(); os.unlink(p)"` — expect `(32607,)` or higher.

- [ ] **Step 2: STOP — confirm with the user**

Ask the user to confirm: (a) no other Claude/agent sessions are running, (b) no tool has `db/market_edge.db` open, (c) OneDrive is up so its behaviour can be observed afterwards. Do not proceed on your own judgment — a WAL-mode file moved while open is exactly the corruption phase 1 exists to prevent.

- [ ] **Step 3: Move and junction** (PowerShell; the repo root is the OneDrive path)

```powershell
# from the repo root
if (Test-Path "db\market_edge.db-wal") { python -c "import sqlite3; c=sqlite3.connect('db/market_edge.db'); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close()" }
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\market_edge" | Out-Null
Move-Item db "$env:LOCALAPPDATA\market_edge\db"
cmd /c mklink /J db "$env:LOCALAPPDATA\market_edge\db"
```

- [ ] **Step 4: Verify the repo still works through the junction**

```bash
python -m tools.cli state
python -m pytest -q
git status --short
```

Expected: `state` renders the same as before the move; suite green; `git status` shows no unexpected changes (`db/schema.sql` is tracked *through* the junction — it must still appear tracked and unmodified; `db/opportunities.json` left in Task 2).

**Note:** `db/schema.sql` is version-controlled and now lives physically outside the repo — this is the one real cost of the junction. If `git status` shows anything odd about `db/schema.sql`, stop and report; the fallback is moving only `*.db*` files out and pointing `tools/db.py::DEFAULT_DB_PATH` at the new location instead (one-line change, spec §5.2 phase 1 names it).

- [ ] **Step 5: Verify OneDrive is not syncing the junction target**

Watch OneDrive's activity (system tray → activity) for ~5 minutes and check the OneDrive web UI's copy of the repo folder: `db` should appear as an empty item or not update, and no multi-GB upload should start. OneDrive clients have historically *followed* junctions; if upload activity on `db/` starts, undo (`Remove-Item db; Move-Item "$env:LOCALAPPDATA\market_edge\db" db`) and use the fallback in Step 4's note instead.

- [ ] **Step 6: Record the outcome**

Append a short entry to `RESEARCH_LOG.md` (it passes the bar: a repo-level operational change): what moved, where, which verification passed, and where the backup lives. Mark the relocation ruling implemented:

```bash
python -m tools.cli rulings list   # find the relocation ruling's id
python -m tools.cli rulings status <id> implemented
git add RESEARCH_LOG.md
git commit -m "ops: ledger backed up; db/ relocated out of OneDrive behind a junction (spec 5.2 phases 0-1)"
```

---

### Task 8: close out Plan 1

- [ ] **Step 1: Full verification**

```bash
python -m pytest -q
python -m tools.cli state
python -m tools.cli rulings list --status binding
```

Expected: suite green (1,005 + the ~15 new tests); `state` renders all six panels with only `data_windows`/chain-n/bets-render stubs remaining; force-floor and relocation rulings show `implemented`.

- [ ] **Step 2: Mark implemented rulings**

The force-floor ruling (Task 4) is now implemented — `rulings status <id> implemented`. The migration/bar/architecture rulings stay `binding` (their implementing plans have not run).

- [ ] **Step 3: Log and commit**

Append the plan-completion entry to `RESEARCH_LOG.md`: one paragraph, phases 0/1/1b/2 shipped, pointer to this plan file. Commit:

```bash
git add RESEARCH_LOG.md
git commit -m "log: enforcing-surfaces foundation (phases 0, 1, 1b, 2) shipped"
```

- [ ] **Step 4: Report**

Tell the user: what shipped, the live `state` output, where the backup lives, the OneDrive verification result, and that the next plan (phases 3–5: the log migration) is ready to be written.
