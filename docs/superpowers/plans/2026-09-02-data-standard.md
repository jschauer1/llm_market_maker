# The Data Standard and Its Enforcement — Implementation Plan (Phase 5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** State the repo's data standard — what is worth saving, and whose folder it lands in — enforce it with tests, and make ticket backlog pressure a mechanical rule instead of a judgment call.

**Architecture:** This is the phase the whole spec was written for, and it is mostly prose plus two tests. The machinery it describes already exists: Phase 1 gave studies an owner, Phase 2 gave retired theories one, Phases 3-4 gave the ticket lanes their lifecycle. What is missing is the statement of the rule in `CLAUDE.md` — the file every agent in this repo reads and believes — and the tests that stop it drifting.

**Tech Stack:** Python 3.11, stdlib only. pytest. Markdown.

**Spec:** [`docs/superpowers/specs/2026-09-01-data-and-ticket-lifecycle-design.md`](../specs/2026-09-01-data-and-ticket-lifecycle-design.md) — Part 1 (the data standard), Part 6 (backlog pressure), Part 7 (enforcement). Parts 2-5 shipped in Phases 1-4.

## Global Constraints

- **Python 3.11, stdlib only.** No new dependencies.
- **`CLAUDE.md` is an interface, not a document.** Agents read it and act without asking what a term meant. Prefer a new name to a redefined one; widening what a rule covers is safe, changing what an existing rule means rewrites the past.
- **The existing "save as much as you can, while you can" principle is NOT being deleted or reversed.** It is being *scoped*. It was written about perishable source data and has been read as being about everything. Task 3 must make that unmistakable — a reader who skims must not come away thinking the repo now discards data.
- **Never `git add -A` or `git add .`** — other sessions work in this checkout. Stage explicit paths, run `git status --short`, confirm before committing.
- **Baseline:** `python -m pytest -q` reports **2 pre-existing failures** — `test_no_theory_imports_a_sibling_theory` and `test_every_repo_path_named_in_docs_resolves` — from another lane's `no_side_premium` work, ticketed, not yours. A third is yours.
- **`test_every_repo_path_named_in_docs_resolves` scans backticked paths in `CLAUDE.md` and requires them to resolve from the repo root.** Every path you backtick must exist. Paths containing `<` are skipped by the matcher, so `theories/<slug>/` is safe; `theories/retired/calibration_harvest` is safe because it exists.

## What already exists — do not rebuild

- `test_no_new_top_level_directory` shipped in Phase 1 (`tests/test_conventions.py:989`). The allowlist is `.claude`, `attic`, `db`, `docs`, `tests`, `theories`, `tickets`, `tools`, `user_reports`.
- Every tracked data file already sits with an owner — verified: `git ls-files | grep -E '\.(jsonl|csv|parquet|db)$'` outside `theories/`, `tickets/study/`, `db/`, `tests/` returns nothing.
- The two large corpora are gitignored by directory at `.gitignore:23` and `:27`.
- `tickets.backlog(root, *, lane, status, theory, brief, study)` and `tickets.render(entries)` exist and are what `cli tickets list` calls.

---

### Task 1: `test_data_files_live_with_their_owner`

**Files:**
- Modify: `tests/test_conventions.py`

**Interfaces:**
- Produces: `test_data_files_live_with_their_owner`.

- [ ] **Step 1: Write the test**

```python
#: Extensions that mean "collected data" rather than "code or prose".
_DATA_SUFFIXES = {".jsonl", ".csv", ".parquet", ".db"}

#: Where collected data is allowed to live. A theory folder or a study's
#: state directory OWNS its data; `db/` is the shared store; `tests/`
#: holds fixtures. Anywhere else is data that escaped the thing that
#: produced it, which is how a repo grows a pile nobody can attribute.
_DATA_OWNERS = ("theories/", "tickets/study/", "db/", "tests/")


def test_data_files_live_with_their_owner():
    """Collected data belongs to the theory or study that produced it.

    Not a tidiness rule. Data with no owner is data nobody can decide
    about later: whether it is still needed, whether it can be
    regenerated, whether deleting it loses something unrecoverable. The
    owner's folder answers all three by construction.

    Every tracked data file in this repo already satisfies this; the test
    exists so the first exception is a decision somebody makes rather
    than a file that appears.
    """
    stray = []
    for line in _tracked_files():
        if Path(line).suffix.lower() not in _DATA_SUFFIXES:
            continue
        if not line.startswith(_DATA_OWNERS):
            stray.append(line)
    assert stray == [], (
        "collected data is sitting outside the theory or study that "
        "produced it -- move it to its owner's folder, or say in the "
        "session report why it had to escape:\n" + "\n".join(stray)
    )
```

Add a `_tracked_files()` helper if none exists: run `git ls-files` via `subprocess.run` from `ROOT`, return the split lines. Skip the test if git is unavailable rather than failing — this suite must stay runnable outside a checkout.

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_conventions.py::test_data_files_live_with_their_owner -v`
Expected: PASS — every tracked data file already sits with an owner.

- [ ] **Step 3: Prove it can fail**

Temporarily `git add` an empty `scratch.csv` at the repo root, re-run, confirm it FAILS naming that file, then `git rm --cached` it and delete it. A test that has never been seen red is not known to work. Record the failure message in the report.

- [ ] **Step 4: Full suite and commit**

```bash
python -m pytest -q
git add tests/test_conventions.py
git commit -m "conventions: collected data lives with the thing that produced it"
```

---

### Task 2: `test_ticket_states_match_their_lane`

**Files:**
- Modify: `tests/test_conventions.py`

- [ ] **Step 1: Write the test**

```python
def test_ticket_states_match_their_lane():
    """Each lane's state directories are its own and nothing else's.

    The lanes deliberately disagree: `study` has no `completed/` (its
    terminal state is `answer/`, which is what makes a finished study
    permanent -- `purge` matches `completed/`, so the query cannot reach
    it), and `new-theory` has `evidence/` and `implement/` that no other
    lane has. A stray directory in the wrong lane is a ticket nobody
    lists and a state nothing advances out of.

    `tickets/new-theory/reference/` is NOT a state and is excluded on
    purpose: it holds the lane's shared reference material, and it was
    moved out of `evidence/` precisely because being scanned as a state
    made `backlog()` report three permanent malformed rows.
    """
    from tools import tickets

    allowed_extra = {"README.md", "reference"}
    problems = []
    for lane, dirname in tickets.ROOT_LANES.items():
        base = ROOT / "tickets" / dirname
        if not base.is_dir():
            continue
        legal = set(tickets.states_for(lane)) | allowed_extra
        for child in sorted(base.iterdir()):
            if child.name not in legal:
                problems.append(f"tickets/{dirname}/{child.name}")
    for base in sorted((ROOT / "tickets" / "study").glob("*")):
        if base.is_dir() and base.name not in tickets.states_for("study"):
            problems.append(f"tickets/study/{base.name}")
    assert problems == [], (
        "a ticket state directory does not belong to its lane:\n"
        + "\n".join(problems)
    )
```

Check `tickets.ROOT_LANES` — it maps lane name to directory name and may or may not now include `study`. Adjust the loop so `study` is covered exactly once, not twice or zero times.

- [ ] **Step 2: Run, prove it can fail, full suite, commit**

Same discipline as Task 1: create `tickets/maintenance/answer/` temporarily, confirm the test names it, remove it.

```bash
git add tests/test_conventions.py
git commit -m "conventions: a lane's state directories are its own"
```

---

### Task 3: The data standard in CLAUDE.md

The centrepiece. **Read the spec's Part 1 in full before writing** — this task states its rule, and the wording matters more than the code in this phase.

**Files:**
- Modify: `CLAUDE.md` (the "Data conventions" section, which currently opens at line 941)

- [ ] **Step 1: Read what is there now**

`CLAUDE.md`'s Data conventions section opens with *"The governing principle: save as much as you can, while you can."* That principle is correct and stays. It is **unscoped**, and that is the defect: written about perishable source data, read as being about everything.

- [ ] **Step 2: Rewrite the section's opening**

Replace the unscoped principle with the scoped one. It must say, in this order:

1. **Two kinds of data, split by one test:** *can a future session regenerate this from what is already on disk?*
   - **No → source data.** Kalshi payloads, candles, per-trade corpora, LLM judgments already paid for in tokens. Unbuyable — Kalshi ages settled markets out of its public API after ~60 days, and a model's verdicts cost tokens that are not spent twice. **Capture aggressively. This is the existing rule, unchanged, and it still governs.**
   - **Yes → derived data.** Intermediates, re-runnable aggregates, scratch analysis, a second copy of a number the ledger already holds. **Earns its keep two ways only: expensive to regenerate, or something cites it.**
   - State the asymmetry explicitly: losing source data is unrecoverable, losing derived data costs CPU. Where the test is genuinely unclear, keep it.

2. **Data lands in the thing that produced it.** Two owners: a theory (at its **registry path**, which is not always `theories/<slug>`) or a study (its state directory). Reading stays open everywhere — that is already the rule and nothing here narrows it. A session may read any theory's notes or any study's data at any time; it may not deposit new files there.

3. **The shared sinks, as a closed list:** the database through the `tools/` APIs; `RESEARCH_LOG.md` (append only); **tickets, any lane, without restriction** — the one broad exception, because a ticket is how a focused session tells another owner something without spending their attention; `user_reports/<date>/` (floor only); `tests/` and fixtures (an elevation, which is a migration under the caller-count rule).

4. **The escape hatch, and its narrowness:** *"my task is impossible otherwise"* — not inconvenient, not slower. A session that takes it says so in its report and files a ticket naming what it wrote and where.

5. **A data directory over 10MB adds its own `.gitignore` entry naming the DIRECTORY, not a filename** — for the reason the existing `series-bias-mining` entry already gives: the `-journal`, the WAL and the per-run logs were all still untracked, so `git add -A` would have staged them.

**Keep every existing bullet in that section that this does not replace** — the SQLite/THEORY.md/NOTES.md sources of truth, prices as decimal dollars, the basket rule, the arbitrage rule, one board per session, snapshots, and "record while you collect". Those are unaffected and deleting them would lose real rules.

- [ ] **Step 3: Verify the paths you backticked resolve**

Run: `python -m pytest tests/test_conventions.py::test_every_repo_path_named_in_docs_resolves -v`
Expected: fails on exactly the 4 pre-existing `no_side_premium` spans and nothing you added. If your additions appear in the failure list, fix the paths — do not add exceptions.

- [ ] **Step 4: Full suite and commit**

```bash
python -m pytest -q
git add CLAUDE.md
git commit -m "CLAUDE.md: scope the save-everything principle, and say where data lands

The principle was written about perishable source data and read as being
about everything. Split by one test -- can a future session regenerate
this? -- with source data still captured aggressively and derived data
earning its keep. Two owners, a closed list of shared sinks, and tickets
as the one unrestricted exception."
```

---

### Task 4: Backlog pressure

**Files:**
- Modify: `tools/tickets.py` (`render`)
- Modify: `.claude/skills/go/SKILL.md`
- Test: `tests/test_tickets.py`

- [ ] **Step 1: Add age to the rendered backlog**

`render(entries)` prints one line per ticket with date, slug and title. Add the ticket's age in days, computed from `created` against today, and a **pressure line** per lane when either threshold is crossed: **a ticket open more than 14 days, or 5 or more open tickets in that lane.**

`render` currently takes only `entries`. Add an optional `now` parameter so the test can pin a date rather than depending on the clock — a test that changes behaviour with the calendar is a test that will fail mysteriously in three weeks.

- [ ] **Step 2: Test it**

```python
def test_the_backlog_flags_a_lane_under_pressure(tmp_path):
    for i in range(5):
        tickets.create(tmp_path, lane="maintenance", slug=f"t{i}",
                       title=f"Ticket {i}", body="b", created="2026-09-01")
    out = tickets.render(tickets.backlog(tmp_path, brief=True),
                         now="2026-09-02")
    assert "PRESSURE" in out


def test_a_quiet_lane_is_not_flagged(tmp_path):
    tickets.create(tmp_path, lane="maintenance", slug="only", title="T",
                   body="b", created="2026-09-01")
    out = tickets.render(tickets.backlog(tmp_path, brief=True),
                         now="2026-09-02")
    assert "PRESSURE" not in out


def test_one_old_ticket_is_enough_to_flag_a_lane(tmp_path):
    tickets.create(tmp_path, lane="maintenance", slug="ancient", title="T",
                   body="b", created="2026-08-01")
    out = tickets.render(tickets.backlog(tmp_path, brief=True),
                         now="2026-09-02")
    assert "PRESSURE" in out
```

- [ ] **Step 3: The rule in the `go` skill**

In `.claude/skills/go/SKILL.md`, where the session chooses its lane, add: **a lane holding a ticket open more than 14 days, or 5 or more open tickets, is either taken or explicitly declined with a reason in the session report.** And: **the floor is never displaced by ticket pressure** — it is a daily guarantee, not a discretionary lane.

Say the numbers are a starting point rather than a measurement, so a future session tunes them deliberately instead of treating them as derived.

- [ ] **Step 4: Check it against the real backlog**

Run: `python -m tools.cli tickets list`
Read the output. Report which lanes are flagged. **`new-theory` is expected to flag immediately** — it has ~16 open specs. Say in the report whether that reads as useful signal or as noise, since that is the open question the user was asked to rule on and has not.

- [ ] **Step 5: Full suite and commit**

```bash
python -m pytest -q
git add tools/tickets.py tests/test_tickets.py .claude/skills/go/SKILL.md
git commit -m "tickets: show age and flag a lane under backlog pressure"
```

## What this deliberately does not do

- **Does not delete the save-everything principle.** It scopes it. A reader who skims must not conclude the repo now discards data.
- **Does not touch `RESEARCH_LOG.md` or `docs/superpowers/`.** Append-only history and records of what was true when written.
- **Does not resolve the two pre-existing test failures.** They belong to another lane and are ticketed.
- **Does not tune the pressure numbers.** 14 days and 5 tickets are the spec's starting point; Task 4 Step 4 reports how they land so the user can rule.
