# Test Suite Speed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut `python -m pytest` from 97s to under 30s without deleting, merging, or skipping a single test.

**Architecture:** Three levers, all in test setup rather than test bodies. (1) Deselect the four already-marked network tests by default. (2) Replace per-test on-disk SQLite construction (55.5ms) with a session-built schema template cloned into memory per test (0.84ms), via a new root `tests/conftest.py`; tests whose subject *is* the filesystem keep real files. (3) Walk and read the repo's source corpus once per session instead of once per scan test.

**Tech Stack:** pytest, stdlib `sqlite3` (`Connection.serialize`/`deserialize`, Python 3.11+). No new dependencies. No parallelism.

**Spec:** `docs/superpowers/specs/2026-09-02-test-suite-speed-design.md`

## Global Constraints

- **No test deleted, merged, renamed, or skipped.** Collected node IDs must be identical before and after (verified by the baseline captured in Task 1).
- **No test body changes.** Only fixtures, imports, and config. The one exception is Task 12, which changes how scan tests *acquire* files, never what they assert.
- **No new dependency.** `serialize`/`deserialize` are stdlib on Python 3.11+; this repo runs 3.11.5.
- **No parallelism.** `pytest-xdist` is explicitly out of scope.
- **A test whose subject is real file behavior keeps a real file.** Never "speed up" `test_backup.py`, `test_parallel_writes.py`, or a legacy-migration test by taking its files away — that deletes the test while appearing to keep it.
- **A CONCURRENT SESSION IS ACTIVE IN THIS REPO.** At plan time it had 23 modified files in the study/theory lane, including `tests/test_conventions.py`. Therefore: **never run `git add -A`** — always `git add` the exact paths the task names. And **do not modify `tests/test_conventions.py`** (Task 13 is deferred for this reason).
- **`tests/test_filelock.py` is another lane's deliberate RED spec** (`tools/filelock.py` does not exist). It breaks collection. **Do not implement it and do not convert it to a skip** — that is their TDD cycle. Every command in this plan therefore passes `--ignore=tests/test_filelock.py`.
- Baseline to beat: **97.45s / 1467 tests**.

---

### Task 1: Capture the equivalence baseline

This is the gate every later task is checked against. Do it first and do not skip it.

**Files:**
- Create: `docs/superpowers/plans/baseline-nodeids.txt` (temporary, deleted in Task 14)

- [ ] **Step 1: Capture the collected node IDs**

```bash
python -m pytest --collect-only -q -p no:cacheprovider \
  --ignore=tests/test_filelock.py \
  | grep "::" | sort > docs/superpowers/plans/baseline-nodeids.txt
wc -l docs/superpowers/plans/baseline-nodeids.txt
```

Expected: 1467 lines.

- [ ] **Step 2: Capture the baseline wall time**

```bash
python -m pytest -q -p no:cacheprovider --ignore=tests/test_filelock.py
```

Expected: `1467 passed in ~97s`. Record the number.

- [ ] **Step 3: Commit the baseline**

```bash
git add docs/superpowers/plans/baseline-nodeids.txt
git commit -m "test: capture node-ID baseline before the speed refactor"
```

---

### Task 2: Deselect network tests by default

**Files:**
- Modify: `pytest.ini`

**Interfaces:**
- Produces: the default `pytest` run no longer performs live network calls. `pytest -m network` runs them.

- [ ] **Step 1: Confirm the four network tests and their cost**

```bash
python -m pytest -q -p no:cacheprovider -m network --collect-only
```

Expected: 4 tests collected.

- [ ] **Step 2: Add addopts to pytest.ini**

The file currently reads:

```ini
[pytest]
markers =
    network: test performs a live network call (deselect with -m "not network")
```

Make it:

```ini
[pytest]
addopts = -m "not network"
markers =
    network: test performs a live network call (deselect with -m "not network")
```

- [ ] **Step 3: Verify the deselection and the escape hatch**

```bash
python -m pytest -q -p no:cacheprovider --ignore=tests/test_filelock.py
```
Expected: `1463 passed, 4 deselected`, ~17s faster (~80s).

```bash
python -m pytest -q -p no:cacheprovider -m network
```
Expected: `4 passed`. This proves nothing was lost.

- [ ] **Step 4: Verify node-ID identity**

`-m ""` clears the new default so the full set is collected again:

```bash
python -m pytest --collect-only -q -p no:cacheprovider -m "" \
  --ignore=tests/test_filelock.py | grep "::" | sort \
  > /tmp/now.txt
diff docs/superpowers/plans/baseline-nodeids.txt /tmp/now.txt && echo IDENTICAL
```

Expected: `IDENTICAL`.

- [ ] **Step 5: Commit**

```bash
git add pytest.ini
git commit -m "test: deselect the four network tests by default, -17s

They page the live Kalshi board (one is 15.8s of a 97s suite). All four
already carry @pytest.mark.network and pytest.ini already documented this
exact deselection; this promotes a documented option to the default.
Nothing is deleted -- pytest -m network still runs them."
```

---

### Task 3: The root conftest — tier 1 and tier 3 fixtures

**Files:**
- Create: `tests/conftest.py`

**Interfaces:**
- Produces, for every later task:
  - `conn` — function-scoped `sqlite3.Connection`, full schema, `snapdb` attached, `foreign_keys` ON, private in-memory, 0.84ms.
  - `registered_conn` — `conn` plus `theories.register(c, "t1", "Theory One", "theories/t1", now="2026-08-23T12:00:00Z")`.
  - `conn_disk` — function-scoped connection backed by a real file under `tmp_path`, identical to today's behavior, for tests whose subject is the filesystem.
  - `db_file` — the `Path` of the file `conn_disk` uses, for tests that need the path itself.

- [ ] **Step 1: Write the failing test**

Create `tests/test_conftest_fixtures.py`:

```python
"""The shared DB fixtures must be indistinguishable from a real database.

These are the tests that let ~40 files trust `conn`.
"""
import sqlite3

import pytest

from tools import db, ledger, theories

TS = "2026-08-23T12:00:00Z"


def _tables(c, schema="main"):
    return {r[0] for r in c.execute(
        f"select name from {schema}.sqlite_master where type='table'")}


def test_conn_has_every_table_a_real_database_has(conn):
    real = db.connect(":memory:")
    db.init_db(real)
    assert _tables(conn) == _tables(real)
    assert _tables(conn, "snapdb") == _tables(real, "snapdb")


def test_conn_enforces_foreign_keys(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_conn_returns_rows_by_name(conn):
    theories.register(conn, "t1", "T", "p", now=TS)
    row = conn.execute("select * from theories").fetchone()
    assert row["id"] == "t1"


def test_conn_actually_persists_writes_within_a_test(conn):
    theories.register(conn, "t1", "T", "p", now=TS)
    assert conn.execute("select count(*) from theories").fetchone()[0] == 1


def test_conn_is_isolated_between_tests_part_one(conn):
    theories.register(conn, "leaky", "T", "p", now=TS)


def test_conn_is_isolated_between_tests_part_two(conn):
    assert conn.execute(
        "select count(*) from theories where id='leaky'").fetchone()[0] == 0


def test_registered_conn_seeds_the_standard_theory(registered_conn):
    row = registered_conn.execute("select * from theories").fetchone()
    assert row["id"] == "t1"


def test_conn_supports_the_ledger_contract(conn):
    theories.register(conn, "t1", "T", "p", now=TS)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="TK1",
        outcome="no", entry_price=0.85, edge_pts_net=4.0,
        edge_basis="model", run_mode="live", run_id="live",
        decision_date="2026-08-27", rationale="x",
    )
    assert conn.execute(
        "select count(*) from opportunities").fetchone()[0] == 1


def test_conn_disk_is_backed_by_a_real_file(conn_disk, db_file):
    assert db_file.exists()
    assert _tables(conn_disk) == _tables(conn_disk)


def test_conn_disk_is_reopenable_by_path(conn_disk, db_file):
    theories.register(conn_disk, "t1", "T", "p", now=TS)
    conn_disk.commit()
    other = db.connect(db_file)
    assert other.execute("select count(*) from theories").fetchone()[0] == 1
    other.close()
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
python -m pytest tests/test_conftest_fixtures.py -q -p no:cacheprovider
```

Expected: every test ERRORs with `fixture 'conn' not found`.

- [ ] **Step 3: Write the conftest**

Create `tests/conftest.py`:

```python
"""Shared database fixtures for the whole suite.

Three tiers, because tests want three different things from a database:

  `conn`        a working database, nothing more. The overwhelming
                majority. Built by cloning a schema template into memory:
                0.84ms, against 55.5ms for the on-disk construction this
                replaces.

  `conn_disk`   a database that is genuinely a FILE, for the handful of
                tests whose subject is file behaviour -- backup, WAL,
                split_snapshots, legacy-schema migration. These are
                expected to stay slow. Their slowness is what they measure.

  `db_file`     the path `conn_disk` uses, for tests that pass a path to
                the code under test.

Tier is a per-test property, not a per-file one: several files hold both
kinds. Ask for what the test actually needs.

`serialize`/`deserialize` require Python 3.11+.
"""
from __future__ import annotations

import sqlite3
import sys

import pytest

from tools import db, theories

TS = "2026-08-23T12:00:00Z"

if sys.version_info < (3, 11):            # pragma: no cover - environment
    raise RuntimeError(
        "tests/conftest.py needs sqlite3.Connection.serialize (Python 3.11+)"
    )


@pytest.fixture(scope="session")
def _schema_blobs() -> tuple[bytes, bytes]:
    """The initialised schema, captured once, as raw SQLite pages.

    Session-scoped and safe because what it hands out is immutable
    `bytes`. Never session-scope a connection.
    """
    template = db.connect(":memory:")
    db.init_db(template)
    blobs = (template.serialize(name="main"),
             template.serialize(name="snapdb"))
    template.close()
    return blobs


@pytest.fixture
def conn(_schema_blobs):
    """A private, schema-complete, in-memory database."""
    main, snap = _schema_blobs
    c = sqlite3.connect(":memory:", timeout=30.0)
    c.row_factory = sqlite3.Row
    c.execute("ATTACH DATABASE ':memory:' AS snapdb")
    c.deserialize(main, name="main")
    c.deserialize(snap, name="snapdb")
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()


@pytest.fixture
def registered_conn(conn):
    """`conn` with the standard single theory already registered."""
    theories.register(conn, "t1", "Theory One", "theories/t1", now=TS)
    return conn


@pytest.fixture
def db_file(tmp_path):
    """Path for a real on-disk test database."""
    return tmp_path / "test.db"


@pytest.fixture
def conn_disk(db_file):
    """A database that is genuinely a file. Slow on purpose."""
    c = db.connect(db_file)
    db.init_db(c)
    yield c
    c.close()
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest tests/test_conftest_fixtures.py -q -p no:cacheprovider
```

Expected: `11 passed`.

- [ ] **Step 5: Verify the rest of the suite is undisturbed**

Adding a conftest must not change any existing test.

```bash
python -m pytest -q -p no:cacheprovider --ignore=tests/test_filelock.py
```

Expected: `1474 passed, 4 deselected` (1463 + the 11 new).

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_conftest_fixtures.py
git commit -m "test: add the shared three-tier database fixtures

conn clones a session-built schema template into memory (0.84ms vs 55.5ms
for the per-test on-disk build it will replace). conn_disk keeps a real
file for the tests whose subject IS the filesystem. Proven equivalent to a
real database by tests/test_conftest_fixtures.py before anything adopts it."
```

---

### Tasks 4-11: Convert the files, in batches

Every one of these tasks is the same mechanical edit, and the batches exist
only so a failure is easy to localise. **The conversion never touches a test
body and never changes a fixture's name**, so no call site changes.

The edit replaces a local fixture like this:

```python
@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()
```

with this — a module fixture that *overrides by depending on* the conftest
fixture of the same name, which pytest supports directly:

```python
@pytest.fixture
def conn(registered_conn):
    return registered_conn
```

or, where the file seeds nothing:

```python
# (delete the local fixture entirely; the conftest `conn` applies)
```

or, where the file seeds something non-standard, keep the seed and take the
fast base:

```python
@pytest.fixture
def conn(conn):            # noqa: F811 - overrides the conftest fixture
    ...
```

**Use this form for a non-standard seed** (pytest cannot have a fixture
request itself by the same name in the same module, so rename the base):

```python
@pytest.fixture
def conn(registered_conn):
    for slug in ("t2",):
        theories.register(registered_conn, slug, slug,
                          f"theories/{slug}", now=TS)
    return registered_conn
```

**After EVERY file in a batch**, run that file:

```bash
python -m pytest tests/<file> -q -p no:cacheprovider
```

If a file fails, that file has a test needing tier 3. Do not force it —
give that specific test `conn_disk`/`db_file` and leave the rest on `conn`.

**Do not convert these files** (they are dominated by disk-dependent tests
and are handled in Task 11, or not at all):
`test_backup.py`, `test_parallel_writes.py`, `test_migrate_positions.py`,
`test_cli.py`, `test_conventions.py`, `test_filelock.py`.

- [ ] **Task 4 — no-seed files.** `test_backlog_fit.py`, `test_board.py`,
  `test_ideas.py`, `test_context.py`, `test_registry.py`, `test_rulings.py`,
  `test_snapshot.py`, `test_studies.py`, `test_lanes.py`, `test_floor.py`.
  Run each; commit the batch as
  `test: point the no-seed conn fixtures at the shared in-memory one`.

- [ ] **Task 5 — standard-seed files, part 1.** `test_at_risk_scoring.py`,
  `test_basket_dedup.py`, `test_baskets.py`, `test_buckets.py`,
  `test_carry_chain.py`. Run each; commit.

- [ ] **Task 6 — standard-seed files, part 2.** `test_ledger.py`,
  `test_score.py`, `test_score_characterization.py`, `test_segment_scores.py`,
  `test_slices.py`, `test_settlement_days.py`. Run each; commit.

- [ ] **Task 7 — standard-seed files, part 3.** `test_state.py`,
  `test_theories.py`, `test_theory.py`, `test_theory_run.py`,
  `test_provenance.py`, `test_version_continuity.py`. Run each; commit.

- [ ] **Task 8 — custom-seed files.** `test_experiment_lane.py`,
  `test_fills_and_attribution.py`, `test_attempt_scoring.py`,
  `test_position_dedup.py`, `test_position_identity_schema.py`,
  `test_stub_theory.py`. Each seeds something non-standard — keep the seed,
  swap only the construction. Run each; commit.

- [ ] **Task 9 — theory tests.** `tests/theories/test_deadline_drift.py`,
  `tests/theories/test_insider_judgment_theory.py`,
  `tests/theories/test_structural_arb.py`. Run each; commit.

- [ ] **Task 10 — remaining single-fixture files.** Find them with:

```bash
grep -rln "db.connect(" tests/ --include=*.py
```

Convert whatever is left that is not on the do-not-convert list. Run each;
commit.

- [ ] **Task 11 — mixed files: split by tier.** `test_db.py`,
  `test_snapshot_store.py`, `test_theory_facts.py`, `test_tickets.py`,
  `test_promotion.py`, `test_baskets.py`. Each has a *few* tests that need a
  real file; the prototype named them exactly:

```
test_db.py::test_init_db_migrates_a_legacy_theories_table
test_db.py::test_legacy_theories_table_rejects_the_new_statuses
test_db.py::test_migration_keeps_child_foreign_keys_pointing_at_theories
test_db.py::test_migration_leaves_no_temporary_table_behind
test_db.py::test_migration_preserves_existing_rows
test_snapshot_store.py::test_backfill_gives_legacy_rows_their_captured_at
test_snapshot_store.py::test_fresh_db_puts_snapshots_in_the_attached_file
test_snapshot_store.py::test_split_snapshots_is_rerun_safe_after_success
test_snapshot_store.py::test_split_snapshots_moves_rows_and_drops_main
test_snapshot_store.py::test_split_snapshots_resumes_after_drop_before_vacuum
test_snapshot_store.py::test_unsplit_database_is_refused_loudly
test_theory_facts.py::test_a_legacy_database_is_migrated_to_accept_construction
test_tickets.py::test_the_cli_files_a_theory_ticket_under_its_registry_path
test_promotion.py::test_cli_promote_emits_rung_and_key_version
test_promotion.py::test_cli_promote_run_batches_and_escalates
test_baskets.py::test_basket_write_is_atomic_on_leg_insert_failure
test_board.py::test_split_snapshots_dedupes_a_legacy_main_table
```

  Give exactly these tests `conn_disk` / `db_file`; leave every other test in
  those files on `conn`. Run each file; commit.

---

### Task 12: The session source corpus

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_db_discipline.py`, `tests/test_toolkit.py`

**Interfaces:**
- Consumes: `tests/conftest.py` from Task 3.
- Produces: `source_corpus` — session-scoped, read-only, with attributes
  `text: dict[Path, str]`, `py_files: tuple[Path, ...]`,
  `md_files: tuple[Path, ...]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_conftest_fixtures.py`:

```python
def test_source_corpus_reads_every_python_file_once(source_corpus):
    assert len(source_corpus.py_files) > 150
    assert all(p.suffix == ".py" for p in source_corpus.py_files)
    assert all(p in source_corpus.text for p in source_corpus.py_files)


def test_source_corpus_skips_the_noise_directories(source_corpus):
    noisy = {".git", "__pycache__", "attic", ".pytest_cache"}
    for p in source_corpus.py_files:
        assert not (noisy & set(p.parts)), p


def test_source_corpus_includes_markdown(source_corpus):
    assert len(source_corpus.md_files) > 100
```

- [ ] **Step 2: Run it to verify it fails**

```bash
python -m pytest tests/test_conftest_fixtures.py -q -p no:cacheprovider -k corpus
```

Expected: ERROR `fixture 'source_corpus' not found`.

- [ ] **Step 3: Add the fixture to tests/conftest.py**

```python
SKIP_DIRS = {".git", "__pycache__", "attic", ".pytest_cache",
             ".pytest_cache", "node_modules"}


class _Corpus:
    """The repo's source, walked once and read once per session.

    Read-only by contract -- which is what makes session scope safe. The
    scan tests that use it only ever read. Replaces ~11s of repeated
    rglob-and-read with a single 510ms pass.
    """

    __slots__ = ("text", "py_files", "md_files")

    def __init__(self, text, py_files, md_files):
        self.text = text
        self.py_files = py_files
        self.md_files = md_files


@pytest.fixture(scope="session")
def source_corpus():
    root = db.REPO_ROOT
    text, py, md = {}, [], []
    for path in root.rglob("*"):
        if SKIP_DIRS & set(path.parts):
            continue
        if path.suffix not in (".py", ".md") or not path.is_file():
            continue
        text[path] = path.read_text("utf-8", errors="replace")
        (py if path.suffix == ".py" else md).append(path)
    return _Corpus(text, tuple(sorted(py)), tuple(sorted(md)))
```

- [ ] **Step 4: Run to verify it passes**

```bash
python -m pytest tests/test_conftest_fixtures.py -q -p no:cacheprovider -k corpus
```

Expected: `3 passed`.

- [ ] **Step 5: Convert the two scan files**

In `tests/test_db_discipline.py` and `tests/test_toolkit.py`, replace each
per-test `rglob` + `read_text` with a lookup in `source_corpus`. **The
assertions do not change** — only where the file list and text come from.
The two hot ones are
`test_no_forced_board_pull_in_production_code` and
`test_no_direct_list_open_outside_the_sanctioned_call_sites` (0.86s each).

- [ ] **Step 6: Verify**

```bash
python -m pytest tests/test_db_discipline.py tests/test_toolkit.py -q -p no:cacheprovider
```

Expected: all pass, noticeably faster.

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/test_conftest_fixtures.py \
        tests/test_db_discipline.py tests/test_toolkit.py
git commit -m "test: walk and read the source corpus once per session"
```

---

### Task 13: test_conventions.py — DEFERRED

**Do not do this task while the concurrent session holds
`tests/test_conventions.py` modified.** It is the largest single win left
(7.94s, of which 5.80s is `test_every_dated_cross_citation_still_resolves`),
but editing a file another lane is mid-edit on will produce a conflict or
silently clobber their work.

When their change has landed and `git status` shows the file clean, convert
its scan tests to `source_corpus` exactly as Task 12 did, and memoize
`_dir_bytes()` at session scope. File a maintenance ticket to track it:

```bash
python -m tools.cli tickets new --lane maintenance \
  --title "test_conventions.py scan tests should use the session source corpus"
```

---

### Task 14: Verify, measure, and clean up

- [ ] **Step 1: Prove node-ID identity**

```bash
python -m pytest --collect-only -q -p no:cacheprovider -m "" \
  --ignore=tests/test_filelock.py | grep "::" | sort > /tmp/final.txt
diff <(grep -v test_conftest_fixtures docs/superpowers/plans/baseline-nodeids.txt) \
     <(grep -v test_conftest_fixtures /tmp/final.txt) && echo IDENTICAL
```

Expected: `IDENTICAL`. The `grep -v` excludes only the fixtures' own new
tests, which are additions, not changes to existing coverage.

- [ ] **Step 2: Full green, including network**

```bash
python -m pytest -q -p no:cacheprovider --ignore=tests/test_filelock.py
python -m pytest -q -p no:cacheprovider -m network
```

Expected: both green.

- [ ] **Step 3: Measure and record**

```bash
python -m pytest -q -p no:cacheprovider --ignore=tests/test_filelock.py --durations=15
```

Record the new wall time against the 97.45s baseline.

- [ ] **Step 4: Confirm no test body was changed**

```bash
git diff <baseline-commit>..HEAD -- tests/ | grep "^[-+]" | grep -v "^[-+][-+]" | grep "assert " | head -40
```

Expected: only additions in `tests/test_conftest_fixtures.py`. Any removed
`assert` outside that file must be justified or reverted.

- [ ] **Step 5: Remove the baseline artifact and log the work**

```bash
git rm docs/superpowers/plans/baseline-nodeids.txt
```

Append a dated entry to `RESEARCH_LOG.md` recording the before/after
numbers and the three levers.

- [ ] **Step 6: Commit**

```bash
git add -u docs/superpowers/plans/ RESEARCH_LOG.md
git commit -m "test: record the speed refactor result"
```

---

## Self-Review

**Spec coverage.** Spec section 2 lever 1 -> Tasks 3-11. Lever 2 -> Task 2.
Lever 3 -> Tasks 12-13. Section 3 constraints -> Global Constraints and
Task 14 steps 1 and 4. Section 4 tier 1 -> Task 3; tier 3 -> Task 3 and
Task 11; tier 2 -> **deliberately not planned**, matching the spec's phase 4
being optional and last (it is the only phase touching production code, and
its projected saving is ~4s). Section 5 -> Task 12. Section 6 -> Task 2.
Section 7 phase 0 -> Global Constraints, which resolves it by ignoring the
other lane's RED spec rather than trampling it. Section 8 -> Tasks 1 and 14.

**Known gap, accepted:** spec phase 4 (tier 2 / `test_cli.py`, ~4s) is not
planned. `test_cli.py` stays on disk. Reaching ~31s rather than ~27s without
touching production code is the better trade.

**Placeholder scan:** clean — every code step carries real code, and the
file lists in Tasks 4-11 are explicit.

**Type consistency:** `conn`, `registered_conn`, `conn_disk`, `db_file`,
`source_corpus`, `_schema_blobs`, `_Corpus.text/py_files/md_files` are used
under those exact names in Tasks 3, 11, 12 and 14.
