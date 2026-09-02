# Theory Retirement Implementation Plan (Phase 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A retired theory leaves `theories/` for `theories/retired/<slug>/`, keeping only what proves it was tried — and `calibration_harvest` is migrated as the worked example.

**Architecture:** `tools/registry.py` learns to skip the `theories/retired/` subtree so `discover()` stops importing a package whose code is gone. A `RETIRED.md` marker makes a retired folder self-describing, mirroring how `STUDY.md` already marks a study. The theory's registry `path` is repointed so ticket filing keeps working. Then `calibration_harvest` — retired 2026-09-01, still sitting in `theories/` at 866K — is migrated.

**Tech Stack:** Python 3.11, stdlib only. pytest. SQLite via `tools/db.py`.

**Spec:** [`docs/superpowers/specs/2026-09-01-data-and-ticket-lifecycle-design.md`](../specs/2026-09-01-data-and-ticket-lifecycle-design.md) — Part 4 in full. Phases 3-5 are out of scope.

## Global Constraints

- **Python 3.11, stdlib only.** No new dependencies.
- **`RETIRED.md` marks a retired folder**, the way `STUDY.md` marks a study. It is the death certificate and it **must name the git rev the deleted code lived at**, so retrieval is a command rather than archaeology.
- **What survives is exactly four files:** `RETIRED.md`, `THEORY.md`, `NOTES.md`, `RESULTS.md`. Everything else goes.
- **The raw backtest payloads do NOT survive; their findings do.** This is the user ruling of 2026-09-01 — *"theory + notes + backtest performance with details, not the entire backtest."* Distillation, not deletion of knowledge.
- **Only the user retires a theory.** This plan migrates one the user ALREADY retired (`calibration_harvest`, status `retired` in the DB since 2026-09-01). Nothing here retires anything new, and no theory's status is changed.
- **Never `git add -A` or `git add .`** — other sessions work in this checkout. Stage explicit paths, then `git status --short` before committing.
- **Use `git rm` and `git mv`** so history follows; deleted code must stay retrievable by rev.
- **Baseline: `python -m pytest -q` currently reports 2 pre-existing failures** — `test_no_theory_imports_a_sibling_theory` and `test_every_repo_path_named_in_docs_resolves`, both from another lane's `no_side_premium` work, both ticketed. They are NOT yours. Task 3 is expected to FIX the first of them incidentally (see its notes). A failure that is neither of these is yours.

---

### Task 1: `theories/retired/` is excluded from discovery

`registry.discover()` walks `rglob("THEORY.md")` and **imports every match**, raising if the package exposes no `THEORY` singleton. A retired folder keeps its `THEORY.md` (it is what the theory claimed) but has no code, so discovery must skip the subtree or the drift check breaks the moment Task 3 lands.

**Files:**
- Modify: `tools/registry.py:28-37` (`_theory_packages`)
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `registry.RETIRED_DIRNAME = "retired"` and `registry.RETIRED_MARKER = "RETIRED.md"`; `_theory_packages` skips any folder under `theories/retired/` and any folder carrying `RETIRED.md`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_registry.py`:

```python
def test_a_retired_theory_is_not_discovered(tmp_path):
    """A retired theory keeps its THEORY.md -- it is the record of what
    the theory claimed -- but its code is gone, so importing it would
    raise. Discovery has to skip the subtree, exactly as it already skips
    a folder marked STUDY.md."""
    root = tmp_path / "theories"
    (root / "retired" / "dead_theory").mkdir(parents=True)
    (root / "retired" / "dead_theory" / "THEORY.md").write_text(
        "# Dead\n", encoding="utf-8")
    (root / "retired" / "dead_theory" / "RETIRED.md").write_text(
        "# Retired\n", encoding="utf-8")
    assert registry._theory_packages(root) == []


def test_a_retired_marker_excludes_a_folder_wherever_it_sits(tmp_path):
    """Belt and braces: the path check catches the normal case, the
    marker catches a retired theory somebody files somewhere else."""
    root = tmp_path / "theories"
    (root / "stray").mkdir(parents=True)
    (root / "stray" / "THEORY.md").write_text("# Stray\n", encoding="utf-8")
    (root / "stray" / "RETIRED.md").write_text("# Retired\n", encoding="utf-8")
    assert registry._theory_packages(root) == []


def test_a_live_theory_beside_a_retired_one_is_still_discovered(tmp_path):
    root = tmp_path / "theories"
    (root / "retired" / "dead").mkdir(parents=True)
    (root / "retired" / "dead" / "THEORY.md").write_text("#\n", encoding="utf-8")
    (root / "retired" / "dead" / "RETIRED.md").write_text("#\n", encoding="utf-8")
    (root / "alive").mkdir(parents=True)
    (root / "alive" / "THEORY.md").write_text("#\n", encoding="utf-8")
    assert registry._theory_packages(root) == ["theories.alive"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_registry.py -k retired -v`
Expected: FAIL — the retired folders are returned as importable packages.

- [ ] **Step 3: Implement**

In `tools/registry.py`, add beside `THEORIES_ROOT`:

```python
#: Retired theories live here, and discovery never imports them. A
#: retired theory KEEPS its THEORY.md -- that document is the record of
#: what it claimed and how it decided -- but its code is deleted, so
#: `importlib.import_module` on it would raise. The subtree is skipped
#: by path, and `RETIRED.md` is checked as well so a retired theory
#: filed anywhere else is still excluded. Same shape as the STUDY.md
#: exclusion right below it, and for the same reason: a folder with a
#: THEORY.md that is not a runnable theory.
RETIRED_DIRNAME = "retired"
RETIRED_MARKER = "RETIRED.md"
```

Then in `_theory_packages`, extend the skip:

```python
    for marker in sorted(root.rglob("THEORY.md")):
        folder = marker.parent
        if folder.name == "_TEMPLATE" or (folder / "STUDY.md").exists():
            continue
        if (folder / RETIRED_MARKER).exists():
            continue
        rel = folder.relative_to(root.parent)
        if RETIRED_DIRNAME in rel.parts:
            continue
        out.append(".".join(rel.parts))
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_registry.py -v`
Expected: PASS, including the pre-existing tests.

- [ ] **Step 5: Full suite**

Run: `python -m pytest -q`
Expected: 2 failures, the pre-existing pair.

- [ ] **Step 6: Commit**

```bash
git add tools/registry.py tests/test_registry.py
git commit -m "registry: never import a retired theory

A retired theory keeps its THEORY.md because that document is the record
of what it claimed, but its code is deleted -- so discovery, which
imports every THEORY.md folder it finds, has to skip the subtree. Same
shape as the STUDY.md exclusion beside it."
```

---

### Task 2: A conventions test pins what a retired folder may contain

Without this, a retired folder slowly reacquires code and the deletion is undone one convenient file at a time.

**Files:**
- Modify: `tests/test_conventions.py`

**Interfaces:**
- Consumes: `registry.RETIRED_DIRNAME`, `registry.RETIRED_MARKER` from Task 1.
- Produces: `test_a_retired_theory_holds_only_its_record`.

- [ ] **Step 1: Write the test**

```python
#: What a retired theory is allowed to keep. RETIRED.md is the death
#: certificate; THEORY.md is what it claimed; NOTES.md is the lab
#: notebook that proves it was tried; RESULTS.md is the DISTILLED
#: backtest performance -- the user's ruling of 2026-09-01 was "theory +
#: notes + backtest performance with details, not the entire backtest".
#: A `studies/` subtree is allowed because a retired theory's studies
#: retire with it.
_RETIRED_ALLOWED = {"RETIRED.md", "THEORY.md", "NOTES.md", "RESULTS.md"}


def test_a_retired_theory_holds_only_its_record():
    """A retired theory is a record, not a codebase.

    Its modules, runbook, prompts and raw backtest payloads are deleted
    at retirement and stay retrievable by git rev -- RETIRED.md names the
    rev. Without this test the folder quietly reacquires code one
    convenient file at a time, and the deletion is undone by drift rather
    than by decision.
    """
    retired_root = ROOT / "theories" / registry.RETIRED_DIRNAME
    if not retired_root.is_dir():
        pytest.skip("no theory has been retired into the tree yet")
    problems = []
    for folder in sorted(retired_root.iterdir()):
        if not folder.is_dir():
            continue
        if not (folder / registry.RETIRED_MARKER).is_file():
            problems.append(f"{folder.name}: no RETIRED.md marker")
        for path in folder.rglob("*"):
            if path.is_dir() or "studies" in path.relative_to(folder).parts:
                continue
            if path.name not in _RETIRED_ALLOWED:
                rel = path.relative_to(retired_root)
                problems.append(f"{rel}: not one of {sorted(_RETIRED_ALLOWED)}")
    assert problems == [], (
        "a retired theory holds more than its record -- retirement "
        "deletes the code and keeps the findings:\n" + "\n".join(problems)
    )
```

Ensure `registry` and `pytest` are imported in that module (both already are).

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_conventions.py::test_a_retired_theory_holds_only_its_record -v`
Expected: PASS by skip — `theories/retired/` does not exist yet. Task 3 makes it assert for real.

- [ ] **Step 3: Full suite, then commit**

```bash
python -m pytest -q
git add tests/test_conventions.py
git commit -m "conventions: a retired theory holds only its record"
```

---

### Task 3: Migrate `calibration_harvest`

The live case. Retired by the user on 2026-09-01 with a ~3KB rationale already in the registry; its 866K folder is still in `theories/`.

**Files:**
- Create: `theories/retired/calibration_harvest/{RETIRED.md,RESULTS.md}`
- Move: `THEORY.md`, `NOTES.md`
- Delete: 8 `.py` modules, `__init__.py`, `RUNBOOK.md`, 5 backtest JSONs, 3 completed tickets, 4 test files
- Modify: `tests/test_timeutil.py`, the registry `path` column

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: a migrated retired theory; `test_a_retired_theory_holds_only_its_record` now asserts rather than skips.

- [ ] **Step 1: Capture the rev the code lived at**

```bash
git rev-parse HEAD
```

Record it — `RETIRED.md` must name it, and it is the only thing that makes the deleted code findable later. Every `git show <rev>:<path>` instruction in `RETIRED.md` uses it.

- [ ] **Step 2: Read the retirement rationale**

```bash
python -c "
from tools import db, theories
c = db.connect()
print(theories.get(c, 'calibration_harvest')['retirement_rationale'])
"
```

This is the user's own reasoning, ~3KB, written when they retired it. `RETIRED.md` distils it — **do not rewrite its conclusions or soften them.**

- [ ] **Step 3: Write `RESULTS.md` from the backtest payloads**

Read `theories/calibration_harvest/backtests/{econfin,politics,size,weather}.json` and the rationale, and write `theories/retired/calibration_harvest/RESULTS.md`: the populations walked, how many cells cleared both floors, how many cleared fees, the net edge ranges, and the horizon sign reversal. The rationale already states the headline numbers — three complete populations, 47 cells past both floors, **zero** positive net edges, net −6.57 to −25.29 on econfin.

**This is a distillation, not a summary you invent.** Every number must come from the payloads or the rationale. If a number is not in either, leave it out rather than estimating.

- [ ] **Step 4: Write `RETIRED.md`**

```markdown
# calibration_harvest — retired 2026-09-01

**Status:** retired · **Retired:** 2026-09-01 · **Versions:** v1–v4
**Code at:** `<rev from Step 1>`

<distilled rationale — the pre-registered kill criterion and that it was met,
that the test was fair, the Sports counter-argument and how it was checked,
what is NOT claimed, and what survives>

## Retrieving what was deleted

    git show <rev>:theories/calibration_harvest/screen.py
    git show <rev>:theories/calibration_harvest/backtests/econfin.json
    git show <rev>:tests/theories/test_calibration_harvest_cells.py

Deleted at retirement: 8 modules, `RUNBOOK.md`, 5 backtest payloads
(508K), 3 completed tickets, and 76 tests across 4 files. The findings
those payloads carried are in `RESULTS.md`.
```

- [ ] **Step 5: Move what survives**

```bash
mkdir -p theories/retired/calibration_harvest
git mv theories/calibration_harvest/THEORY.md theories/retired/calibration_harvest/
git mv theories/calibration_harvest/NOTES.md  theories/retired/calibration_harvest/
```

- [ ] **Step 6: Delete the code, the payloads and the tickets**

```bash
git rm -r theories/calibration_harvest
```

Verify nothing survived that should not: `ls theories/calibration_harvest 2>&1` must report no such directory.

- [ ] **Step 7: Delete the tests that tested the deleted code**

```bash
git rm tests/theories/test_calibration_harvest_cells.py \
       tests/theories/test_calibration_harvest_collect.py \
       tests/theories/test_calibration_harvest_forward_cells.py \
       tests/theories/test_calibration_harvest_screen.py
```

That is 76 tests. They test code that no longer exists, so keeping them would break the suite and testing deleted code is not a thing. `RETIRED.md` records the count and the rev.

- [ ] **Step 8: Fix the one test that merely BORROWED the theory**

`tests/test_timeutil.py:19` imports `theories.calibration_harvest.screen` and line 30 uses `ch_screen.days_until` as one of three re-export checks. This test is about `timeutil`, not about `calibration_harvest` — it borrowed the module as a fixture. **Rewrite it, do not delete it:** drop the import and remove `ch_screen.days_until` from `REEXPORTS`, leaving the other two. Add a one-line comment saying the third re-export went with `calibration_harvest`'s retirement.

- [ ] **Step 9: Repoint the registry path**

```bash
python -c "
from tools import db
c = db.connect()
with db.write(c):
    c.execute(\"UPDATE theories SET path = ? WHERE id = ?\",
              ('theories/retired/calibration_harvest', 'calibration_harvest'))
print(dict(c.execute(\"SELECT id, path, status FROM theories WHERE id='calibration_harvest'\").fetchone()))
"
```

Without this, `cli tickets new --theory calibration_harvest` files into a phantom directory beside a theory that no longer exists — the exact bug this repo already fixed once, in the other direction.

- [ ] **Step 10: Move the parked study**

`tickets/study/answer/2026-08-29-calibration-harvest-gradient-review/` was parked in the root study lane during Phase 1 because `theories/retired/` did not exist. It does now. A retired theory's studies retire with it:

```bash
mkdir -p theories/retired/calibration_harvest/studies/answer
git mv tickets/study/answer/2026-08-29-calibration-harvest-gradient-review \
       theories/retired/calibration_harvest/studies/answer/
```

Then update any citation of the old path. `python -m tools.cli studies` must still list 17.

- [ ] **Step 11: Update citations**

```bash
grep -rln "theories/calibration_harvest" --include="*.md" --include="*.py" . \
  | grep -v "^./.superpowers" | grep -v "^./RESEARCH_LOG.md" \
  | grep -v "^./docs/superpowers/"
```

Update each hit to `theories/retired/calibration_harvest`. **Leave `RESEARCH_LOG.md` and `docs/superpowers/` alone** — the log is append-only history and old specs record what was true when written.

- [ ] **Step 12: Verify**

```bash
python -m pytest -q
python -m tools.cli studies
python -m tools.cli state
python -c "from tools import registry, db; c=db.connect(); print(registry.check_drift(c))"
```

Expected:
- `check_drift` returns `[]` — the retired theory is no longer discovered, and its DB row is `retired` so the status side skips it too
- `cli studies` lists 17
- **the suite drops to 1 pre-existing failure, not 2.** `test_no_theory_imports_a_sibling_theory` was failing on `no_side_premium`'s import of `deadline_drift`, which this task does not touch — so if it still fails, that is correct and expected. Check which of the two remain and say so explicitly in the report rather than assuming.
- `test_a_retired_theory_holds_only_its_record` now ASSERTS instead of skipping, and passes

- [ ] **Step 13: Commit**

```bash
git add theories/ tests/ tickets/
git status --short          # confirm nothing foreign is staged
git commit -m "retire: calibration_harvest leaves theories/ for theories/retired/

Keeps RETIRED.md, THEORY.md, NOTES.md and a distilled RESULTS.md. The 8
modules, RUNBOOK, 5 backtest payloads and 76 tests are deleted and
retrievable at the rev RETIRED.md names -- the user's ruling was theory
plus notes plus backtest performance with details, not the entire
backtest.

Registry path repointed so ticket filing keeps resolving."
```

## What this deliberately does not do

- **Retires nothing.** Only the user retires a theory. This migrates one already retired on 2026-09-01.
- **No `cli theories retire` command.** One migration is not two callers. When a second theory retires and the steps are demonstrably the same, that is the time to build it — the repo's own elevation rule.
- **Does not touch the two pre-existing failures' root causes.** They belong to another lane and are ticketed.
