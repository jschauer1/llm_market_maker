# Refactoring the test suite for speed

**Date:** 2026-09-02
**Status:** design, awaiting approval
**Goal:** cut wall-clock time of `python -m pytest` as far as it will go
**Hard constraint:** every test survives, and each one still tests what it tested

---

## 1. Why this is worth doing

The suite is the thing every session runs before it commits. At 97 seconds
it is slow enough that sessions batch changes to avoid paying for it, which
is exactly the habit that lets a regression travel several commits before
anyone notices.

Nothing here changes a single assertion. The refactor is entirely in how a
test is *set up*, and the measurements below say that is where the time is.

---

## 2. The measurement

Baseline, full suite, this machine, 2026-09-02:

```
1467 passed in 97.45s
```

Broken down by pytest phase (`--durations=0`, aggregated):

| phase | time | share |
|---|---|---|
| `call` | 49.49s | 53.7% |
| `setup` | 37.74s | 40.9% |
| `teardown` | 4.94s | 5.4% |
| measured total | 92.17s | |

Collection and interpreter startup account for the ~5s remainder.

**There is no algorithmic hotspot.** Outside four network tests, the
slowest single test is 5.80s and everything else is under 1s. The cost is
per-test fixed overhead, levied ~1467 times. Three sources explain nearly
all of it.

### Lever 1 — the per-test database (dominant)

About 37 near-identical fixtures do this:

```python
@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    yield c
    c.close()
```

`db.connect()` creates a real file, ATTACHes a second real file for
`snapdb`, and puts both in WAL mode — six files per test once WAL and shm
are counted. `init_db()` then runs 18 `CREATE TABLE`s plus six
table-rebuild migration passes. Measured cost of that pair:

| strategy | per test |
|---|---|
| on-disk + `init_db()` — **today** | **55.5 ms** |
| `:memory:` + `init_db()` | 8.7 ms |
| build schema once, `serialize()`, `deserialize()` per test | **0.84 ms** |

The third row is 66x cheaper than today and reproduces the schema exactly:
all 18 `main` tables, the `snapdb` attachment with `market_snapshots`, and
`PRAGMA foreign_keys = ON`.

This was prototyped against the real suite, not just benchmarked. A
representative 350-test subset went **20.56s -> 5.47s (3.8x)**, and under a
blind global swap **1365 of 1467 tests passed with no other change**. Only
12 files objected — and those objections turn out to be a useful taxonomy
rather than an obstacle (section 4).

### Lever 2 — four network tests, 17% of the clock

| test | time |
|---|---|
| `kalshi/test_markets.py::test_live_open_markets_have_expected_shape` | 15.83s |
| `kalshi/test_history.py::test_live_candlesticks_reach_back_months` | 0.15s |
| `polymarket/test_trades.py::test_live_whale_trades_are_actually_large` | 0.12s |
| `polymarket/test_markets.py::test_live_open_markets_have_expected_shape` | 0.10s |
| **total** | **16.97s** |

The first pages the live Kalshi board to exhaustion (~60 requests). All
four already carry `@pytest.mark.network`, and `pytest.ini` already
documents the remedy in the marker's own help text: *"deselect with
-m 'not network'"*.

### Lever 3 — the same repo, walked and read over and over

| test | time |
|---|---|
| `test_conventions.py::test_every_dated_cross_citation_still_resolves` | 5.80s |
| `test_conventions.py::test_every_repo_path_named_in_code_resolves` | 0.95s |
| `test_db_discipline.py::test_no_forced_board_pull_in_production_code` | 0.86s |
| `test_db_discipline.py::test_no_direct_list_open_outside_the_sanctioned_call_sites` | 0.86s |
| ~8 tests in `test_toolkit.py` | ~1.6s |
| rest of `test_conventions.py` | ~1.2s |
| **total** | **~11s** |

Each of these independently calls `ROOT.rglob(...)` and re-reads the same
files. Walking and reading the entire corpus — 465 `.py` and `.md` files,
6.0 MB — costs **510 ms once**.

One test is worse than a re-read: `test_a_large_study_data_directory_is_actually_ignored`
calls `_dir_bytes()`, which `stat()`s every file under the matched
directories. A full `ROOT.rglob("*")` with `stat()` over this 3.5 GB
working tree costs **2.9s**; today it is saved only by the glob being
narrow, and it will degrade silently as study data grows.

### The floor

`--collect-only` is 2.30s and a single trivial file is 1.07s, so roughly
**3s is irreducible** without touching imports.

---

## 3. What must not change

This is the constraint that shapes everything below.

- **No test is deleted, merged, renamed, or skipped.** The set of collected
  node IDs must be byte-identical before and after. This is the acceptance
  gate, and it is mechanical (section 8).
- **No test body changes.** The refactor touches fixtures and configuration
  only. Coverage equivalence is therefore close to true by construction:
  the same assertions run against the same code.
- **A test whose subject is real file behavior keeps a real file.** Tier 3
  below exists entirely to honor this. Speeding up `test_backup.py` by
  taking away its files would delete the test while appearing to keep it —
  the exact failure this constraint forbids.
- **No parallelism.** Ruled out by the user: the complexity is not wanted,
  and as the numbers above show it is not needed to get most of the win.
- **No new runtime dependency.** `serialize`/`deserialize` are stdlib
  `sqlite3` on Python 3.11+ (this repo runs 3.11.5).

---

## 4. Design: three fixture tiers in one root `conftest.py`

The 12 files that resisted the blind swap were not noise. Each was resisting
for one of two legitimate reasons, which gives a three-tier taxonomy that
covers the suite exactly.

There is currently **no root `conftest.py`** (only
`tests/characterization/conftest.py`, which is unrelated and stays). One is
added at `tests/conftest.py` holding all three fixtures. The 37 duplicated
local fixtures are deleted in favor of it — so the change is mostly
subtraction.

### Tier 1 — `conn`: template clone into memory (default, 0.84 ms)

For every test that just needs a working database. This is ~1365 of 1467
tests.

The schema is built **once per session** and captured as two byte strings;
each test deserializes them into a fresh private in-memory connection.

```python
@pytest.fixture(scope="session")
def _schema_blobs():
    t = db.connect(":memory:")
    db.init_db(t)
    return t.serialize(name="main"), t.serialize(name="snapdb")

@pytest.fixture
def conn(_schema_blobs):
    main, snap = _schema_blobs
    c = sqlite3.connect(":memory:", timeout=30.0)
    c.row_factory = sqlite3.Row
    c.execute("ATTACH DATABASE ':memory:' AS snapdb")
    c.deserialize(main, name="main")
    c.deserialize(snap, name="snapdb")
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()
```

Isolation is *stronger* than today, not weaker: each test gets a private
database that cannot outlive it, with no shared temp directory and nothing
to clean up.

Many local fixtures also seed a theory (`theories.register(c, "t1", ...)`).
That stays a local concern: a `registered_conn` fixture in the root
conftest layers the common seed on top of `conn`, and files needing a
different seed keep their own thin fixture that depends on `conn`.

**Precedent:** nine test files already call `db.connect(":memory:")`, and
`db.connect()` documents the `:memory:` special case as existing "for a
disposable schema". Tier 1 generalizes an established pattern.

### Tier 2 — `db_url`: shared-cache in memory (8.17 ms)

For tests where the **code under test reopens the database by path**, so a
per-connection private database is wrong by construction. `test_cli.py` is
the whole story here: a `dbpath` fixture writes a file, closes it, and then
`cli.main(["--db", dbpath, ...])` opens it again — 84 times across the file.
This is why 43 of the 70 prototype failures were in one file.

The fix is a shared-cache URI, where every connection naming the same
database sees the same data:

```python
sqlite3.connect("file:t1?mode=memory&cache=shared", uri=True)
```

Verified working: a second connection by name reads the first's committed
rows, and `snapdb` attaches as its own shared-cache database. The fixture
holds one keep-alive connection so the database outlives each `close()`
inside the code under test.

**This tier requires one production change** and is therefore deferred to
its own phase. `db.connect()` must recognize the URI form the way it
already special-cases `":memory:"`, because it currently does
`Path(path)` and `snapshots_path_for(path)`, which a URI string does not
survive. Per CLAUDE.md this is a **widening** of what the argument may hold
— new accepted form, no existing form's meaning changed — which is the safe
kind of change. It is still a change to shipped code to serve a test, so it
is optional and last (section 7, phase 4), and its payoff is the smallest
of the four.

### Tier 3 — `conn_disk` / `db_file`: a real file (55 ms, unchanged)

For tests whose subject *is* the filesystem. These stay exactly as they are
and are expected to stay slow, because their slowness is the thing they
measure:

| file | what genuinely needs disk |
|---|---|
| `test_backup.py` | copying a real database file |
| `test_parallel_writes.py` | two connections, WAL, real locking |
| `test_snapshot_store.py` (part) | `split_snapshots`, sibling-file derivation |
| `test_db.py` (part) | legacy-schema construction, then migration |
| `test_migrate_positions.py` | builds a pre-migration database on disk |
| `test_conventions.py`, `test_board.py`, `test_theory_facts.py`, `test_tickets.py`, `test_baskets.py`, `test_promotion.py` | one or two tests each |

Roughly 20-30 tests. The root conftest provides the fixture so the intent
is named rather than incidental, but the behavior is today's behavior.

**Tiers are assigned per test, not per file.** Several files span two
tiers: `test_promotion.py` has two CLI-reopen tests (tier 2) and a dozen
ordinary ones (tier 1); `test_snapshot_store.py` and `test_db.py` each mix
file-behavior tests with ordinary ones. A file appearing in the table above
means *some* of its tests need disk, never all of them. Converting a file
means classifying its tests, not moving the file wholesale.

### Why explicit fixtures rather than a global patch

A one-line `db.connect = fast_connect` in conftest would deliver most of
the win with a far smaller diff. It is rejected on this repo's own stated
grounds: CLAUDE.md warns that this codebase is operated by agents that
"read a name, believe it, and act", and that a vocabulary which quietly
changes meaning "does not produce an error; it produces months of
confidently wrong decisions". A test reading `db.connect(tmp_path/"t.db")`
and silently receiving an in-memory database is that failure mode exactly.

The explicit version also makes the tier *greppable*: which fixture a test
requests states which guarantees it has. And the diff is mostly deletion —
37 duplicated fixtures become 3 shared ones.

---

## 5. The source-corpus cache

Lever 3 is fixed with one session-scoped, read-only fixture in the root
conftest, replacing the ad-hoc `rglob` in each scan test:

```python
@pytest.fixture(scope="session")
def source_corpus():
    """Every .py and .md in the repo, walked once, read once."""
```

It returns an immutable mapping of `Path -> text` plus the pre-filtered
path lists the scan tests want (`py_files`, `md_files`, `tools_modules`).
Skips `.git`, `__pycache__`, `attic`, `db`, `.pytest_cache`.

Read-only by contract, which is what makes session scope safe — the scan
tests only ever read.

Expected: ~11s of repeated walking and reading collapses to ~0.5s once,
plus each test's own logic.

`_dir_bytes()` gets the same treatment via a session-scoped memo, which
also removes the latent 2.9s cliff as study data grows.

---

## 6. Network tests

Add to `pytest.ini`:

```ini
addopts = -m "not network"
```

Nothing is deleted or skipped; the four tests still run under
`pytest -m network`, which becomes the documented command for verifying
live API shape. The marker's existing help text already advertises this
deselection, so this promotes a documented option to the default.

**This is the one place the "strict" constraint is interpreted rather than
applied literally**, and it is called out here so the decision is visible:
the default run stops making live network calls. The user approved this
directly. If it is ever regretted, reverting is one line.

A consequence worth naming: nothing then exercises the live API unless
someone asks. That is a feature for a test suite — the four tests assert
that Kalshi's payload *shape* has not changed, which is a monitoring
question, not a regression question, and it does not belong on the critical
path of every commit.

---

## 7. Migration plan

Four phases, each independently valuable, ordered by payoff over risk. Each
lands green and is committed separately.

**Phase 0 — unblock collection.** `tests/test_filelock.py` imports
`tools.filelock`, which does not exist; the suite currently **fails
collection entirely**, so `python -m pytest` runs nothing at all. This is a
deliberate committed RED spec (`201d113`), but it means no one can run the
suite today. Resolve it — implement `tools/filelock.py`, or mark the module
`pytest.importorskip` until it exists. This is a precondition for measuring
anything, and it is why every baseline in this document is quoted with
`--ignore=tests/test_filelock.py`.

**Phase 1 — network deselection.** One line in `pytest.ini`. Expect
-17s. No test changes.

**Phase 2 — tiers 1 and 3 (the bulk).** Add `tests/conftest.py` with
`conn`, `registered_conn` and `conn_disk`. Delete the ~37 local fixtures
and point their files at the shared ones. Assign the 12 known objectors to
tier 3, leaving `test_cli.py` and `test_promotion.py` on disk for now
(phase 4 moves them). Expect -35 to -45s. Convert file by file, running
that file after each conversion.

**Phase 3 — the source-corpus cache.** Rewrite the scan tests in
`test_conventions.py`, `test_db_discipline.py` and `test_toolkit.py` to
take `source_corpus`. Assertions unchanged. Expect -9s.

**Phase 4 — tier 2 (optional).** Widen `db.connect()` to accept a
shared-cache URI, add the `db_url` fixture, move `test_cli.py` and
`test_promotion.py` onto it. Expect -4s. Do this last, or not at all: it is
the only phase touching production code and it has the worst
payoff-to-risk ratio of the four. Dropping it costs ~4s and the suite is
still ~4x faster.

### Projection

| after | expected |
|---|---|
| baseline | 97s |
| phase 1 | ~80s |
| phase 2 | ~40s |
| phase 3 | ~31s |
| phase 4 | ~27s |

Target: **under 30s, from 97s, with no test removed and no parallelism.**
Phases 1-3 alone reach ~31s without touching a line of production code.

---

## 8. How equivalence is proven

The claim "same tests, faster" is checked mechanically, not asserted.

1. **Node-ID identity.** Before phase 1, capture
   `pytest --collect-only -q` (with `-m ""` so nothing is deselected) to a
   file. After every phase, re-capture and `diff`. The sets must be
   identical. This catches an accidentally dropped, renamed or skipped
   test, which is the only way "strict" can be violated when test bodies
   are untouched.
2. **Green after every phase**, including the four network tests run
   explicitly via `-m network`.
3. **Test bodies unchanged.** `git diff` for phases 1-2 should show changes
   confined to fixtures, imports and config. Any diff inside a `def test_`
   body is a red flag to justify or revert. (Phase 3 is the exception: it
   rewrites how scan tests *acquire* files, though not what they assert.)
4. **Tier 3 stays honest.** Every test moved to tier 3 must still be one
   whose failure mode requires a real file. A test parked in tier 3 merely
   because converting it was awkward is a bug in the migration, not a
   result — leave it in tier 1 and fix the real problem.

---

## 9. Risks

- **A test passing for the wrong reason after conversion.** The main
  hazard: a test that silently depended on file-backed behavior now passes
  trivially in memory. Mitigated by converting file by file, and by the
  tier-3 honesty check above. The blind-swap prototype already surfaced
  the population that cares (12 files); the risk is a 13th that fails to
  fail.
- **Session-scoped state leaking between tests.** The two session-scoped
  fixtures are read-only by contract: `_schema_blobs` returns immutable
  `bytes`, `source_corpus` returns an immutable mapping. Never hand a test
  a session-scoped *connection*.
- **`deserialize` and Python version.** Requires 3.11+. The repo runs
  3.11.5. Worth a note in `tests/conftest.py` so a future downgrade fails
  loudly rather than mysteriously.
- **Phase 4 widens production code to serve tests.** Real, which is why it
  is optional, last, and separately committed.
- **Concurrent sessions.** This repo runs a fleet. Phase 2 touches ~40 test
  files; land it as one focused maintenance-lane commit rather than letting
  it straddle other work.

---

## 10. Out of scope

- Parallelism (`pytest-xdist`) — explicitly ruled out by the user.
- Any new dependency.
- Merging, deleting or rewriting tests to reduce their number.
- Reducing the ~2.3s collection floor by restructuring imports. It is 2% of
  the target end state and not worth the coupling.
- The study test files under `tickets/study/investigation/` that the root
  collection currently picks up. Whether a study's own tests belong in the
  main suite is a governance question, not a speed question; it is worth a
  separate maintenance ticket, and is deliberately not decided here.
