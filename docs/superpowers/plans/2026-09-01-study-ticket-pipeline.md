# Study Ticket Pipeline Implementation Plan (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a study from a folder in a top-level tree into a ticket with its own lifecycle (`question → investigation → answer`) living inside the theory that owns it, and dissolve top-level `studies/`.

**Architecture:** `tools/tickets.py` gains per-lane state sets and a study lane whose tickets are *directories* rather than files, routed to `<theory registry path>/studies/<state>/` when a theory owns the study and `tickets/study/<state>/` when none does. `tools/studies.py` stops parsing a `Status:` header and reads state from the directory instead. The migration keeps the repo green by having `survey()` walk legacy and new locations simultaneously, moving the 18 directories, then dropping legacy support.

**Tech Stack:** Python 3.11, stdlib only (`pathlib`, `re`), pytest, SQLite via `tools/db.py`. No new dependencies.

**Spec:** [`docs/superpowers/specs/2026-09-01-data-and-ticket-lifecycle-design.md`](../specs/2026-09-01-data-and-ticket-lifecycle-design.md) — Part 3 in full, plus the Part 7 top-level allowlist. Phases 2–5 (retirement, new-theory lifecycle, purge, the CLAUDE.md standard) get their own plans and are **out of scope here**.

## Global Constraints

- **Python 3.11, stdlib only.** No new dependencies; `requirements.txt` is untouched.
- **State is a directory, never a frontmatter field.** `STUDY.md` loses its `**Status:**` field entirely. This is the point of the phase — do not add a replacement field.
- **`answer/` is terminal and permanent.** The study lane has no `completed/`. Nothing in this phase may give it one.
- **A study ticket is a directory containing `STUDY.md`.** One file, carrying both the ticket frontmatter and the study header. Do not create a separate `TICKET.md` for the study lane.
- **Vocabulary:** the new field is `state`, not `status`. Per CLAUDE.md, prefer a new name to a redefined one — `status` still means open/done for the file-based lanes.
- **Every move uses `git mv`**, so history follows the file.
- **Run the full suite** (`python -m pytest -q`) before every commit, not just the new tests. This repo's conventions tests assert across the whole tree and are the backstop for missed citations.
- **Studies are never moved once cited.** A study in the root lane stays there even if its subject theory is built later.

---

### Task 1: Per-lane ticket states

Today `tickets.STATES` is a single global `("open", "completed")` and `ticket_dir` hardcodes it. The study lane needs three different states, so states become a per-lane fact.

**Files:**
- Modify: `tools/tickets.py:60-70` (the `STATES` constant and its comment)
- Modify: `tools/tickets.py:73-130` (`ticket_dir`)
- Test: `tests/test_tickets.py`

**Interfaces:**
- Consumes: nothing from earlier tasks — this is the first.
- Produces:
  - `tickets.LANE_STATES: dict[str, tuple[str, ...]]` — lane name → its ordered states.
  - `tickets.STATES: tuple[str, ...]` — kept as `("open", "completed")` for backward compatibility with existing callers.
  - `tickets.states_for(lane: str) -> tuple[str, ...]` — the states a lane declares; raises `ValueError` on an unknown lane.
  - `ticket_dir(root, lane, theory=None, state=None, theory_path=None, study=None) -> Path` — `state` now defaults to `None`, meaning "the lane's first state".

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_tickets.py`:

```python
def test_each_lane_declares_its_own_states():
    assert tickets.states_for("maintenance") == ("open", "completed")
    assert tickets.states_for("theory") == ("open", "completed")
    assert tickets.states_for("study") == ("question", "investigation",
                                           "answer")


def test_an_unknown_lane_has_no_states():
    with pytest.raises(ValueError, match="unknown lane"):
        tickets.states_for("nonsense")


def test_the_study_lane_has_no_completed_state():
    """Permanence is a consequence of the state names, not an exemption
    the purge has to remember: a finished study lives in `answer/`, so a
    query for `completed/` simply never matches one."""
    assert "completed" not in tickets.states_for("study")


def test_a_lane_refuses_a_state_belonging_to_another_lane(tmp_path):
    with pytest.raises(ValueError, match="has no state 'answer'"):
        tickets.ticket_dir(tmp_path, "maintenance", state="answer")
    with pytest.raises(ValueError, match="has no state 'open'"):
        tickets.ticket_dir(tmp_path, "study", state="open")


def test_omitting_the_state_uses_the_lanes_first(tmp_path):
    assert tickets.ticket_dir(tmp_path, "maintenance").name == "open"
    assert tickets.ticket_dir(tmp_path, "study").name == "question"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_tickets.py -k "lane_declares or unknown_lane or no_completed or belonging_to_another or first" -v`
Expected: FAIL — `AttributeError: module 'tools.tickets' has no attribute 'states_for'`

- [ ] **Step 3: Implement**

In `tools/tickets.py`, replace the `STATES` block with:

```python
#: A ticket's state IS a directory rather than a field. The backlog is
#: read by listing, so a finished ticket has to leave it physically --
#: with a status field alone, every session reads every ticket ever filed
#: to find the few still open, and the backlog gets slower and less
#: useful exactly as the repo gets more history.
#:
#: The STATES a lane has are the lane's own. `study` is the odd one and
#: deliberately so: a study is a measurement that answers a question, its
#: terminal state is `answer/`, and it has NO `completed/`. That is what
#: makes a study permanent -- the purge matches `completed/`, so a
#: finished study is simply not a thing the query can match. Permanence
#: falls out of the state names instead of being an exemption somebody
#: has to remember.
LANE_STATES: dict[str, tuple[str, ...]] = {
    "theory": ("open", "completed"),
    "maintenance": ("open", "completed"),
    "new-theory": ("open", "completed"),
    "study": ("question", "investigation", "answer"),
}

#: The file-based lanes' states, kept under the old name because callers
#: outside this module still ask for "the states a normal ticket has".
STATES = ("open", "completed")


def states_for(lane: str) -> tuple[str, ...]:
    """The states this lane declares, in pipeline order."""
    try:
        return LANE_STATES[lane]
    except KeyError:
        raise ValueError(
            f"unknown lane {lane!r}; expected one of {LANES}"
        ) from None
```

Then in `ticket_dir`, change the signature's `state: str = "open"` to `state: str | None = None` and replace the leading validation:

```python
    if lane not in LANES:
        raise ValueError(f"unknown lane {lane!r}; expected one of {LANES}")
    allowed = states_for(lane)
    if state is None:
        state = allowed[0]
    if state not in allowed:
        raise ValueError(
            f"lane {lane!r} has no state {state!r}; it declares {allowed}"
        )
```

Delete the old `if state not in STATES:` check that this replaces.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_tickets.py -v`
Expected: PASS. The pre-existing tests still pass — `ticket_dir(..., state="open")` is unchanged for every file-based lane.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/tickets.py tests/test_tickets.py
git commit -m "tickets: states are per-lane, and the study lane has no completed/

A study's terminal state is answer/, which is what makes it permanent:
the purge matches completed/, so a finished study is not a thing the
query can match. Permanence falls out of the state names rather than
being an exemption somebody has to remember."
```

---

### Task 2: A study ticket is a directory, routed to its owner

A measurement has code and data, so its ticket is a directory holding them. The directory carries one file, `STUDY.md`, with the ticket frontmatter and the study header together.

**Files:**
- Modify: `tools/tickets.py` — `ticket_dir` (study routing), `create`, `_scan`
- Test: `tests/test_tickets.py`

**Interfaces:**
- Consumes: `tickets.states_for`, `ticket_dir(root, lane, state=None, ...)` from Task 1.
- Produces:
  - `tickets.STUDY_FILE = "STUDY.md"` — the study lane's ticket filename.
  - `ticket_dir(root, "study", theory=..., theory_path=..., state=...)` → `<theory_path>/studies/<state>` when `theory_path` is given, else `tickets/study/<state>`.
  - `create(...)` returns the path to `STUDY.md` inside the new directory for the study lane, and the `.md` file itself for every other lane.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_study_owned_by_a_theory_lives_in_that_theory(tmp_path):
    got = tickets.ticket_dir(
        tmp_path, "study", theory="no_side_premium",
        theory_path="theories/no_side_premium", state="answer")
    assert got == tmp_path / "theories/no_side_premium/studies/answer"


def test_a_study_owned_by_nobody_lives_in_the_root_lane(tmp_path):
    got = tickets.ticket_dir(tmp_path, "study", state="investigation")
    assert got == tmp_path / "tickets/study/investigation"


def test_a_study_ticket_is_a_directory_holding_STUDY_md(tmp_path):
    path = tickets.create(
        tmp_path, lane="study", slug="entry-timing",
        title="Does entry timing matter?",
        body="Bar: a 2pt net difference at n>=200.",
        created="2026-09-02")
    assert path.name == "STUDY.md"
    assert path.parent.name == "2026-09-02-entry-timing"
    assert path.parent.parent.name == "question"
    assert path.read_text(encoding="utf-8").startswith("---\n")


def test_a_study_ticket_records_its_owning_theory(tmp_path):
    (tmp_path / "theories/no_side_premium").mkdir(parents=True)
    path = tickets.create(
        tmp_path, lane="study", slug="side-split",
        title="Does the side gap survive a tradeable book?",
        body="Bar: the gap holds at 100% coverage.",
        theory="no_side_premium",
        theory_path="theories/no_side_premium", created="2026-09-02")
    assert "theory: no_side_premium" in path.read_text(encoding="utf-8")
    assert path.parent.parent.parent.name == "studies"


def test_a_non_study_ticket_is_still_a_plain_file(tmp_path):
    path = tickets.create(
        tmp_path, lane="maintenance", slug="fix-thing", title="Fix it",
        body="Do the thing.", created="2026-09-02")
    assert path.name == "2026-09-02-fix-thing.md"
    assert path.parent.name == "open"


def test_the_backlog_finds_a_study_in_every_state(tmp_path):
    tickets.create(tmp_path, lane="study", slug="asked",
                   title="An open question", body="Bar: x.",
                   created="2026-09-02")
    rows = tickets.backlog(tmp_path, lane="study", status="open")
    assert [r["slug"] for r in rows] == ["asked"]
    assert rows[0]["state"] == "question"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_tickets.py -k "study" -v`
Expected: FAIL — `ticket_dir` still raises "a study ticket needs its study".

- [ ] **Step 3: Implement**

In `tools/tickets.py`, add near `STATES`:

```python
#: The study lane's ticket filename. A study ticket is a DIRECTORY --
#: a measurement has code and data and they belong with it -- and this
#: is the one file inside it that is the ticket. It is `STUDY.md` rather
#: than `TICKET.md` because the study header and the ticket frontmatter
#: describe the same thing, and two files would mean two places to say
#: what this measurement is.
STUDY_FILE = "STUDY.md"
```

Replace the whole `if lane == "study":` branch in `ticket_dir` with:

```python
    if lane == "study":
        # A study lives inside the theory that owns it, and in the root
        # `study` lane when no single theory does. Measured 2026-09-01:
        # of 15 studies, 7 served exactly one theory and 5 served none,
        # so both homes are load-bearing rather than one being a
        # fallback for the other.
        if theory_path:
            return Path(root) / theory_path / "studies" / state
        if theory:
            raise ValueError(
                f"a study owned by {theory!r} needs that theory's registry "
                "path, not its slug: pass "
                "theory_path=theories.get(conn, slug)['path']"
            )
        return Path(root) / "tickets" / "study" / state
```

In `create`, after `directory = ticket_dir(...)`, branch on the lane:

```python
    directory.mkdir(parents=True, exist_ok=True)
    if lane == "study":
        # The ticket is the directory; STUDY.md inside it is the file.
        holder = directory / f"{day}-{slug}"
        if holder.exists():
            raise ValueError(f"study already exists: {holder}")
        holder.mkdir(parents=True)
        path = holder / STUDY_FILE
    else:
        path = directory / f"{day}-{slug}.md"
        if path.exists():
            raise ValueError(f"ticket already exists: {path}")
```

Delete the two lines this replaces (`path = directory / f"{day}-{slug}.md"` and its `if path.exists()` guard).

Rewrite `_scan` so it knows both shapes, and so every entry carries its state:

```python
def _scan(directory: Path, lane: str, theory: str | None,
         brief: bool = False, study: str | None = None,
         state: str = "open") -> list[dict]:
    """Every ticket in one state directory.

    The study lane's tickets are directories holding a STUDY.md; every
    other lane's are plain .md files. Both are parsed the same way once
    found -- only the glob differs.
    """
    if not directory.is_dir():
        return []
    if lane == "study":
        found = sorted(
            child / STUDY_FILE for child in directory.iterdir()
            if child.is_dir() and (child / STUDY_FILE).is_file()
        )
    else:
        found = [p for p in sorted(directory.glob("*.md"))
                 if p.name != "README.md"]
    rows = []
    for path in found:
        entry = _parse(path, lane, theory, brief=brief, study=study)
        if lane == "study":
            # The slug is the DIRECTORY's name; STUDY.md carries no date.
            match = _DATE_PREFIX.match(path.parent.name)
            created, slug = (match.groups() if match
                             else ("", path.parent.name))
            entry["created"], entry["slug"] = created, slug
        entry["state"] = state
        rows.append(entry)
    return rows
```

Add `"state": "open"` to the `entry` dict built in `_parse`, so a row always carries the key.

Finally, teach `backlog` to walk every state of every lane. Replace its body's state resolution:

```python
    root = Path(root)
    wanted = "completed" if status == "done" else "open"
    found: list[dict] = []
    for lane_name, dirname in ROOT_LANES.items():
        for st in states_for(lane_name):
            if _reported_as(lane_name, st) != wanted:
                continue
            found += _scan(root / "tickets" / dirname / st, lane_name,
                           None, brief=brief, state=st)
    for st in states_for("study"):
        if _reported_as("study", st) != wanted:
            continue
        found += _scan(root / "tickets" / "study" / st, "study", None,
                       brief=brief, state=st)
```

and add the helper above `backlog`:

```python
def _reported_as(lane: str, state: str) -> str:
    """Which of open/done a state counts as, for callers that filter on
    the old two-value vocabulary.

    A study being measured is OPEN work -- it is not finished until it
    has an answer -- so `question` and `investigation` report as open and
    only `answer` reports as done. This keeps `--status open` meaning
    "work still to do" across every lane.
    """
    if lane != "study":
        return "done" if state == "completed" else "open"
    return "done" if state == "answer" else "open"
```

Then extend the theories walk in `backlog` so a theory's `studies/<state>/` directories are scanned alongside its `tickets/<state>/`:

```python
    theories_dir = root / "theories"
    if theories_dir.is_dir():
        for candidate in sorted(theories_dir.rglob("tickets")):
            if not candidate.is_dir():
                continue
            owner = candidate.parent.name
            for st in states_for("theory"):
                if _reported_as("theory", st) != wanted:
                    continue
                found += _scan(candidate / st, "theory", owner,
                               brief=brief, state=st)
        for candidate in sorted(theories_dir.rglob("studies")):
            if not candidate.is_dir():
                continue
            owner = candidate.parent.name
            for st in states_for("study"):
                if _reported_as("study", st) != wanted:
                    continue
                found += _scan(candidate / st, "study", owner,
                               brief=brief, state=st)
```

Delete the old `studies_dir` block that walked `studies/<slug>/tickets/` — the concept of "a ticket about a study" is gone.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_tickets.py -v`
Expected: PASS for the new tests. **The old study-lane tests will fail** — they assert `studies/<slug>/tickets/open/`, which no longer exists. Delete `test_a_study_ticket_lands_in_that_study` and any sibling asserting that path (around `tests/test_tickets.py:35`, `:398`, `:459`); they test a concept this phase removes. Note in the commit message that they were removed rather than fixed.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/tickets.py tests/test_tickets.py
git commit -m "tickets: a study is a directory ticket, owned by its theory

A measurement has code and data, so its ticket is a directory holding
them, with STUDY.md inside carrying both the frontmatter and the study
header. Routed to the owning theory when there is one and the root study
lane when there is not -- measured 2026-09-01, 7 of 15 studies served
exactly one theory and 5 served none.

Removes 'a ticket about a study': chores against a running measurement
are ordinary theory tickets. The tests asserting that path are deleted
rather than fixed, because the concept is gone."
```

---

### Task 3: `advance` — move a ticket to its next state

**Files:**
- Modify: `tools/tickets.py` (add `advance` next to `close`)
- Test: `tests/test_tickets.py`

**Interfaces:**
- Consumes: `states_for`, `STUDY_FILE`, `ticket_dir` from Tasks 1–2.
- Produces: `tickets.advance(path: Path, *, to: str, note: str, now: str | None = None) -> Path` — moves the ticket (file or directory) into the `to` state directory and returns its new path. Appends a dated `## <to>` section carrying `note` to the body.

- [ ] **Step 1: Write the failing tests**

```python
def test_advance_moves_a_study_to_the_next_state(tmp_path):
    path = tickets.create(tmp_path, lane="study", slug="entry-timing",
                          title="Does entry timing matter?",
                          body="Bar: 2pt net at n>=200.", created="2026-09-02")
    moved = tickets.advance(path, to="investigation",
                            note="Collecting 60 days of candles.",
                            now="2026-09-03")
    assert moved.parent.parent.name == "investigation"
    assert not path.parent.exists()
    assert "Collecting 60 days of candles." in moved.read_text(encoding="utf-8")


def test_advance_carries_the_whole_directory(tmp_path):
    path = tickets.create(tmp_path, lane="study", slug="probe",
                          title="Q", body="Bar: x.", created="2026-09-02")
    (path.parent / "collect.py").write_text("# code\n", encoding="utf-8")
    moved = tickets.advance(path, to="investigation", note="Running.",
                            now="2026-09-03")
    assert (moved.parent / "collect.py").is_file()


def test_advance_refuses_a_state_the_lane_does_not_have(tmp_path):
    path = tickets.create(tmp_path, lane="study", slug="q", title="Q",
                          body="Bar: x.", created="2026-09-02")
    with pytest.raises(ValueError, match="has no state 'completed'"):
        tickets.advance(path, to="completed", note="nope")


def test_advance_refuses_to_go_backwards(tmp_path):
    path = tickets.create(tmp_path, lane="study", slug="q", title="Q",
                          body="Bar: x.", created="2026-09-02")
    moved = tickets.advance(path, to="answer", note="Done.", now="2026-09-03")
    with pytest.raises(ValueError, match="cannot move backwards"):
        tickets.advance(moved, to="question", note="reopening")


def test_advance_requires_a_note(tmp_path):
    path = tickets.create(tmp_path, lane="study", slug="q", title="Q",
                          body="Bar: x.", created="2026-09-02")
    with pytest.raises(ValueError, match="a note is required"):
        tickets.advance(path, to="investigation", note="  ")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_tickets.py -k advance -v`
Expected: FAIL — `AttributeError: module 'tools.tickets' has no attribute 'advance'`

- [ ] **Step 3: Implement**

Add to `tools/tickets.py`, directly above `close`:

```python
def advance(path: Path, *, to: str, note: str,
            now: str | None = None) -> Path:
    """Move a ticket into its next state. Returns the new path.

    The note is required and is appended to the body under a dated
    heading, because a state change nobody explained is a state change
    the next session has to reverse-engineer. For a study moving to
    `investigation`, the note is what the measurement is about to do;
    moving to `answer`, it is what it found.

    Moving BACKWARDS is refused. A pipeline that can run in reverse is a
    status field wearing a directory's clothes, and the whole reason
    state is a directory here is that a field lets two places disagree
    about where the work stands.
    """
    if not note or not note.strip():
        raise ValueError("a note is required: say why it moved")
    path = Path(path)
    is_study = path.name == STUDY_FILE
    item = path.parent if is_study else path
    lane_dir = item.parent
    allowed = states_for(_lane_of(lane_dir))
    here = lane_dir.name
    if to not in allowed:
        raise ValueError(
            f"lane {_lane_of(lane_dir)!r} has no state {to!r}; "
            f"it declares {allowed}"
        )
    if allowed.index(to) <= allowed.index(here):
        raise ValueError(
            f"cannot move backwards: {here!r} -> {to!r}. Close the ticket "
            "or file a new one instead."
        )
    target = lane_dir.parent / to
    target.mkdir(parents=True, exist_ok=True)
    moved = target / item.name
    if moved.exists():
        raise ValueError(f"already present in {to}: {moved}")
    item.rename(moved)
    body_file = moved / STUDY_FILE if is_study else moved
    raw = body_file.read_text(encoding="utf-8").rstrip()
    stamp = now or _today()
    body_file.write_text(
        f"{raw}\n\n## {to} — {stamp}\n\n{note.strip()}\n", encoding="utf-8")
    return body_file


def _lane_of(state_dir: Path) -> str:
    """The lane a state directory belongs to, from its container.

    `<owner>/studies/answer` and `tickets/study/answer` are both the
    study lane; `tickets/maintenance/open` is maintenance. The container
    directory names the lane, which is the same fact `ticket_dir` writes
    down in the other direction.
    """
    container = state_dir.parent.name
    if container in ("studies", "study"):
        return "study"
    for lane, dirname in ROOT_LANES.items():
        if container == dirname:
            return lane
    if container == "tickets":
        return "theory"
    raise ValueError(f"cannot tell which lane {state_dir} belongs to")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_tickets.py -k advance -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/tickets.py tests/test_tickets.py
git commit -m "tickets: advance() moves a ticket to its next state

Refuses to move backwards. A pipeline that runs in reverse is a status
field wearing a directory's clothes, and state is a directory here
precisely so two places cannot disagree about where the work stands."
```

---

### Task 4: `survey()` reads state from the directory, walking legacy and new

The repo must stay green across the migration, so this task teaches `survey` **both** layouts. Task 6 migrates; Task 7 removes the legacy walk.

**Files:**
- Modify: `tools/studies.py:68-97` (`survey`), `:104-125` (`render`)
- Modify: `tools/floor.py:206` — the one other consumer of a survey row
- Test: `tests/test_studies.py`, `tests/test_floor.py`

**The consumer that must not break silently:** `floor.required_coverage`
reads `study["status"]` to list in-flight studies, and `floor complete`
refuses a report that omits one. If this keeps reading a key that no
longer exists it raises `KeyError` at the end of a floor run; if it were
left defaulting, the guard would silently stop guarding. Change it in the
same commit as `survey`.

**Interfaces:**
- Consumes: `tickets.states_for`, `tickets.STUDY_FILE` from Tasks 1–2.
- Produces: `studies.survey(root) -> list[dict]` where each row has `slug`, `date`, `title`, `state`, `complete`, `verdict`, `tier`, `owner`, `path`. **`status` and `open_tickets` are gone.**

- [ ] **Step 1: Write the failing tests**

Replace the `repo` fixture in `tests/test_studies.py` and add:

```python
@pytest.fixture()
def repo(tmp_path):
    def add(where, slug, header, *, body=""):
        d = tmp_path / where / slug
        d.mkdir(parents=True)
        (d / "STUDY.md").write_text(header + "\n" + body, encoding="utf-8")
        return d

    add("tickets/study/answer", "2026-08-27-calendar-arb-firing-rate",
        "# calendar-arb does not fire, and its premise is false\n\n"
        "**Date:** 2026-08-27 · **Tier:** A · "
        "**Verdict:** do not build the spec as written")
    add("tickets/study/investigation", "2026-08-30-parlay-markup",
        "# Parlay markup — pre-registration\n\n"
        "**Date:** 2026-08-30 · **Tier:** A")
    add("theories/no_side_premium/studies/answer",
        "2026-09-01-side-split-60day-obs",
        "# Splitting the 60-day observation set by side\n\n"
        "**Date:** 2026-09-01 · **Tier:** A · **Verdict:** a composition "
        "artifact explains it")
    return tmp_path


def test_the_state_comes_from_the_directory_not_a_header(repo):
    rows = {r["slug"]: r for r in studies.survey(repo)}
    assert rows["2026-08-27-calendar-arb-firing-rate"]["state"] == "answer"
    assert rows["2026-08-30-parlay-markup"]["state"] == "investigation"


def test_only_an_answered_study_is_complete(repo):
    rows = {r["slug"]: r for r in studies.survey(repo)}
    assert rows["2026-08-27-calendar-arb-firing-rate"]["complete"] is True
    assert rows["2026-08-30-parlay-markup"]["complete"] is False


def test_a_study_carries_the_theory_that_owns_it(repo):
    rows = {r["slug"]: r for r in studies.survey(repo)}
    assert rows["2026-09-01-side-split-60day-obs"]["owner"] == "no_side_premium"
    assert rows["2026-08-30-parlay-markup"]["owner"] is None


def test_a_status_header_is_ignored_entirely(tmp_path):
    """The Status field is gone. A stale one left in a file must not be
    able to contradict the directory -- that contradiction is the exact
    failure this pipeline removes (series-bias-mining read 'complete'
    while two open tickets said the sweep was unfinished)."""
    d = tmp_path / "tickets/study/investigation" / "2026-08-29-stale"
    d.mkdir(parents=True)
    (d / "STUDY.md").write_text(
        "# Stale\n\n**Date:** 2026-08-29 · **Status:** complete · "
        "**Tier:** A\n", encoding="utf-8")
    row = studies.survey(tmp_path)[0]
    assert row["state"] == "investigation"
    assert row["complete"] is False
    assert "status" not in row


def test_the_render_names_the_owner(repo):
    out = studies.render(studies.survey(repo))
    assert "no_side_premium" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_studies.py -v`
Expected: FAIL — `survey` returns `[]` because nothing lives under `studies/` in the fixture.

- [ ] **Step 3: Implement**

Rewrite `survey` in `tools/studies.py`:

```python
def survey(root: Path) -> list[dict]:
    """Every study, oldest first, with what its own STUDY.md says.

    **State comes from the directory, never from a header field.** A
    study carried a `**Status:**` line until 2026-09-01, and it drifted
    exactly as a duplicated status field always does: series-bias-mining
    read `complete -- result: not measured` while two open tickets said
    the phase-2 sweep was unfinished and pass 4's filter was reversed.
    The header and the work disagreed, and nothing could tell you which
    was right. Now the directory is the only claim.
    """
    from tools import tickets

    root = Path(root)
    out: list[dict] = []
    for holder, owner in _study_homes(root):
        for state in tickets.states_for("study"):
            directory = holder / state
            if not directory.is_dir():
                continue
            for folder in sorted(directory.iterdir()):
                marker = folder / tickets.STUDY_FILE
                if not marker.is_file():
                    continue
                out.append(_row(folder, marker, state, owner, root))
    # LEGACY: the pre-2026-09-01 tree, read so the repo stays green
    # across the migration. Removed once nothing lives here.
    legacy = root / "studies"
    if legacy.is_dir():
        for folder in sorted(legacy.iterdir()):
            marker = folder / "STUDY.md"
            if marker.is_file():
                out.append(_row(folder, marker, "answer", None, root))
    out.sort(key=lambda r: (r["date"], r["slug"]))
    return out


def _study_homes(root: Path):
    """Every directory that can hold study state dirs, with its owner."""
    yield root / "tickets" / "study", None
    theories = root / "theories"
    if theories.is_dir():
        for candidate in sorted(theories.rglob("studies")):
            if candidate.is_dir():
                yield candidate, candidate.parent.name


def _row(folder: Path, marker: Path, state: str, owner: str | None,
         root: Path) -> dict:
    raw = marker.read_text(encoding="utf-8", errors="replace")
    match = _SLUG_DATE.match(folder.name)
    return {
        "slug": folder.name,
        "date": match.group(1) if match else _one(_DATE, raw),
        "title": _one(_TITLE, raw),
        "state": state,
        "complete": state == "answer",
        "verdict": _one(_VERDICT, raw),
        "tier": _one(_TIER, raw),
        "owner": owner,
        "path": str(folder.relative_to(root)).replace("\\", "/"),
    }
```

Delete the module-level `_STATUS` regex and the `_COMPLETE` tuple — nothing reads a status header any more.

Rewrite `render`:

```python
def render(rows: list[dict]) -> str:
    """The survey as a scannable block — what the floor reports."""
    if not rows:
        return "no studies\n"
    out: list[str] = []
    for row in rows:
        mark = " " if row["complete"] else "*"
        owner = f"  [{row['owner']}]" if row["owner"] else "  [no owner]"
        out.append(f"{mark} {row['slug']}  ({row['state']}){owner}")
        detail = row["verdict"] or row["title"]
        if detail:
            out.append(f"      {_clip(detail, 84)}")
    flight = sum(1 for r in rows if not r["complete"])
    if flight:
        out.append(f"  (* {flight} not answered — in flight, not forgotten)")
    return "\n".join(out) + "\n"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_studies.py -v`
Expected: PASS.

- [ ] **Step 4b: Update `floor.required_coverage`**

In `tools/floor.py`, the study branch of `required_coverage` becomes:

```python
    for study in studies_mod.survey(root if root is not None else REPO_ROOT):
        if study["complete"]:
            continue
        out.append({
            "kind": "study",
            "name": study["slug"],
            "theory": study["owner"],
            "status": study["state"],
        })
```

`theory` now carries the owning theory rather than `None`, which is
strictly better: the floor's coverage check can say which theory an
in-flight study belongs to. The outer key stays `status` because that is
`required_coverage`'s own vocabulary for every row kind it returns, not
the study's.

Add to `tests/test_floor.py`:

```python
def test_required_coverage_names_an_unanswered_study(tmp_path, conn):
    d = tmp_path / "tickets/study/investigation" / "2026-08-30-parlay-markup"
    d.mkdir(parents=True)
    (d / "STUDY.md").write_text(
        "# Parlay markup

**Date:** 2026-08-30 · **Tier:** A
",
        encoding="utf-8")
    rows = floor.required_coverage(conn, root=tmp_path)
    study = next(r for r in rows if r["kind"] == "study")
    assert study["name"] == "2026-08-30-parlay-markup"
    assert study["status"] == "investigation"
```

- [ ] **Step 5: Verify the real repo still renders**

Run: `python -m tools.cli studies`
Expected: all 15 existing studies still listed, via the legacy walk, each showing `(answer)` and `[no owner]`. Nothing lost.

- [ ] **Step 6: Run the full suite and commit**

Run: `python -m pytest -q`

```bash
git add tools/studies.py tests/test_studies.py
git commit -m "studies: state comes from the directory, not a header field

The Status field drifted exactly as a duplicated status field always
does -- series-bias-mining read 'complete' while two open tickets said
its sweep was unfinished. The directory is now the only claim, and the
survey carries the owning theory.

Keeps a legacy walk over the old studies/ tree so the repo stays green
until the migration lands."
```

---

### Task 5: CLI — file, advance and list studies

**Files:**
- Modify: `tools/cli.py:162-200` (`_cmd_tickets`), `:847-880` (the tickets parser)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `tickets.create`, `tickets.advance`, `studies.survey` from Tasks 2–4.
- Produces: `cli tickets new --lane study [--theory <slug>]`, `cli tickets advance <path> --to <state> --note <text>`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
def test_filing_a_study_creates_a_directory_ticket(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "REPO_ROOT", tmp_path)
    rc = cli.main(["tickets", "new", "--lane", "study", "--slug", "probe",
                   "--title", "Does it fire?", "--body", "Bar: 10 hits."])
    assert rc == 0
    made = list((tmp_path / "tickets/study/question").iterdir())
    assert len(made) == 1 and (made[0] / "STUDY.md").is_file()


def test_advancing_a_study_moves_it(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "REPO_ROOT", tmp_path)
    cli.main(["tickets", "new", "--lane", "study", "--slug", "probe",
              "--title", "Q", "--body", "Bar: x."])
    made = next((tmp_path / "tickets/study/question").iterdir())
    rc = cli.main(["tickets", "advance", str(made / "STUDY.md"),
                   "--to", "investigation", "--note", "Collecting."])
    assert rc == 0
    assert (tmp_path / "tickets/study/investigation").is_dir()
    assert not any((tmp_path / "tickets/study/question").iterdir())
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_cli.py -k "study" -v`
Expected: FAIL — `advance` is not a valid `tickets` action.

- [ ] **Step 3: Implement**

In `_cmd_tickets`, add before the `close` branch:

```python
    elif args.action == "advance":
        path = tickets.advance(pathlib.Path(args.path), to=args.to,
                               note=args.note)
        _emit({"advanced": str(path), "state": args.to})
```

In the parser, after `tnew`'s arguments:

```python
    tadv = tsub.add_parser(
        "advance", help="move a ticket to its next state")
    tadv.add_argument("path")
    tadv.add_argument("--to", required=True,
                      help="the state to move into; the lane declares "
                           "which it has (study: question, investigation, "
                           "answer)")
    tadv.add_argument("--note", required=True,
                      help="why it moved — appended to the body under a "
                           "dated heading")
```

Change `tnew`'s `--study` help text, since the flag no longer targets an existing study folder:

```python
    tnew.add_argument("--study", default=None,
                      help=argparse.SUPPRESS)   # retired with the study tree
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite and commit**

Run: `python -m pytest -q`

```bash
git add tools/cli.py tests/test_cli.py
git commit -m "cli: file and advance study tickets"
```

---

### Task 6: Migrate all 18 directories

The repo-changing task. Every move is `git mv` so history follows.

**Files:**
- Move: 15 directories out of `studies/`, 3 out of `tickets/new-theory/evidence/`
- Modify: `tests/test_series_bias_mining.py:21`, `tests/test_series_bias_pass3.py:27` (real path loads), plus ~13 docstring citations
- Delete: `studies/README.md` (content moves to `tickets/study/README.md`)

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: a repo where `studies/` does not exist and `cli studies` lists 18 studies with owners.

- [ ] **Step 1: Create the state directories**

```bash
mkdir -p tickets/study/{question,investigation,answer}
for t in no_side_premium structural_arb deadline_drift; do
  mkdir -p "theories/$t/studies/answer"
done
mkdir -p theories/insider_bias/mention_family/studies/investigation
```

- [ ] **Step 2: Move the seven theory-owned studies**

```bash
git mv studies/2026-08-29-side-asymmetry-extension            theories/no_side_premium/studies/answer/
git mv studies/2026-09-01-side-split-60day-obs                theories/no_side_premium/studies/answer/
git mv studies/2026-09-01-liquidity-filtered-side-split       theories/no_side_premium/studies/answer/
git mv studies/2026-08-29-structural-arb-violation-liquidity  theories/structural_arb/studies/answer/
git mv studies/2026-08-29-deadline-drift-classifier-audit     theories/deadline_drift/studies/answer/
git mv studies/2026-08-29-series-bias-mining                  theories/insider_bias/mention_family/studies/investigation/
```

`calibration-harvest-gradient-review` waits for Phase 2 (its theory has no `retired/` home yet). Park it in the root lane for now and leave a note:

```bash
git mv studies/2026-08-29-calibration-harvest-gradient-review tickets/study/answer/
```

- [ ] **Step 3: Move the six ownerless studies and the in-flight one**

```bash
git mv studies/2026-08-27-calendar-arb-firing-rate                 tickets/study/answer/
git mv studies/2026-08-29-smile-smoothing-ladder-flatness          tickets/study/answer/
git mv studies/2026-08-27-settlement-day-clustering                tickets/study/answer/
git mv studies/2026-08-29-early-close-exposure-existing-backtests  tickets/study/answer/
git mv studies/2026-09-01-early-close-exposure-in-the-bettable-slice tickets/study/answer/
git mv studies/2026-08-30-entry-timing                             tickets/study/answer/
git mv studies/2026-08-30-parlay-markup                            tickets/study/investigation/
```

- [ ] **Step 4: Move the governance doc and the three probes**

```bash
git mv studies/2026-08-29-structural-gate-payload-version docs/2026-08-29-structural-gate-payload-version
git mv tickets/new-theory/evidence/2026-09-01-aggregation-gap-probe     tickets/study/answer/
git mv tickets/new-theory/evidence/2026-09-01-accumulation-decay-probe  tickets/study/answer/
git mv tickets/new-theory/evidence/2026-09-01-block-trade-probe         tickets/study/answer/
```

- [ ] **Step 5: Give the three probes a `STUDY.md`**

Each probe has a `RESULT.md` but no `STUDY.md`, so `survey` cannot see it. Write one per probe, taking the verdict **verbatim from that probe's `RESULT.md`** — re-file the finding, never re-derive it. Shape:

```markdown
---
title: <the question the probe asked>
lane: study
created: 2026-09-01
created_by: migration
---

# <the question the probe asked>

**Date:** 2026-09-01 · **Tier:** A · **Verdict:** <copied from RESULT.md>

Filed as a probe under `tickets/new-theory/evidence/` before the study
pipeline existed; re-filed 2026-09-02 with no change to the finding.
See `RESULT.md` for the measurement and `PREREG.md` for the bar.
```

The three verdicts, read from each `RESULT.md` on 2026-09-01 so the
implementer does not have to judge what the finding was:

| probe | title line | verdict |
|---|---|---|
| `aggregation-gap-probe` | The NFL-wins conservation law holds inside the spread | both riskless baskets fail at executable prices; the House-seats companion is not an identity at all |
| `accumulation-decay-probe` | Kalshi prices the accumulation collapse in real time — there is no lag to harvest | **DO NOT BUILD `accumulation-decay`** — reached on branch 1 of the rule pre-registered before any calibration number existed; 222 settled `KXALBUMEQUIV` markets, 28 events, 1,046 liquid observations |
| `block-trade-probe` | `is_block_trade` is real, and it fires ~3 times per 67 days board-wide | **DO NOT BUILD `block-trade-whale-follow`** — reached on the rule pre-registered before any per-ticker number existed |

Use the `# ` heading of each `RESULT.md` as the study's title and the
**Verdict** column above as its `**Verdict:**` field.

- [ ] **Step 6: Strip the `Status:` field from all 15 migrated `STUDY.md` files**

```bash
python - <<'PY'
import pathlib, re
for p in pathlib.Path(".").rglob("STUDY.md"):
    if "attic" in p.parts:
        continue
    raw = p.read_text(encoding="utf-8")
    out = re.sub(r"\s*·?\s*\*\*Status:?\*\*:?[^·\n]*(·\s*)?", 
                 lambda m: " · " if m.group(1) else "", raw, count=1)
    if out != raw:
        p.write_text(out, encoding="utf-8")
        print("stripped", p)
PY
```

Then read each modified header back and fix any doubled or trailing ` · ` by hand — there are 15 files and the regex is not worth perfecting.

- [ ] **Step 7: Fix the two real code path loads**

`tests/test_series_bias_mining.py:21` and `tests/test_series_bias_pass3.py:27` load `mine.py` by path. Update both to:

```python
ROOT / "theories/insider_bias/mention_family/studies/investigation"
     / "2026-08-29-series-bias-mining"
```

- [ ] **Step 8: Update the docstring citations**

These are prose, not path loads, but the conventions tests check them. Update the `studies/2026-…` spans in: `theories/calibration_harvest/cells.py:22`, `theories/deadline_drift/hazard.py:48,381`, `theories/deadline_drift/screen.py:35`, `theories/no_side_premium/exposure.py:3,10`, `theories/no_side_premium/exposure_measure.py:6`, `tests/test_book.py:89`, `tests/theories/test_structural_arb.py:580`, plus every `THEORY.md` and `NOTES.md` hit from:

```bash
grep -rln "studies/2026" --include="*.md" --include="*.py" . \
  | grep -v "^./docs/superpowers/" | grep -v "^./RESEARCH_LOG.md" \
  | grep -v "^./.superpowers/"
```

**Leave `RESEARCH_LOG.md` and `docs/superpowers/` alone** — the log is append-only history and the old specs are records of what was true when written.

- [ ] **Step 9: Move the studies README**

```bash
git mv studies/README.md tickets/study/README.md
```

Rewrite its opening to describe the pipeline (`question → investigation → answer`), keep the definition and the three worked examples, and delete the "Tickets about a study live in the study" section — that concept is gone.

- [ ] **Step 10: Confirm `studies/` is empty and remove it**

```bash
ls -A studies/ ; rmdir studies
```

Expected: no output from `ls`, then the directory is gone. If anything remains, it was missed above — move it, do not delete it.

- [ ] **Step 11: Verify**

```bash
python -m pytest -q
python -m tools.cli studies
```

Expected: suite green; 18 studies listed (15 migrated + 3 probes), `parlay-markup` and `series-bias-mining` showing `(investigation)` with a `*`, the rest `(answer)`, and the seven theory-owned ones naming their owner.

- [ ] **Step 12: Commit**

**Never `git add -A` or `git add .` in this tree.** Other sessions run
collectors here that hold megabytes of half-written JSON mid-flush; a
repo-wide add sweeps their in-flight capture into this migration commit
and makes both the migration and their run harder to review or revert.
This repo's fleet rules already ban it — on 2026-09-01 the tree held 83
dirty entries from three sessions at once. Stage the migration's own
paths explicitly:

```bash
git add tickets/ theories/ docs/ tests/ tools/
git status --short          # confirm nothing foreign is staged
git commit -m "migrate: studies become ticket-pipeline directories, studies/ is gone

15 studies and 3 probe dirs moved. Seven land in the theory that owns
them, the rest in the root study lane; structural-gate-payload-version
was never a study (zero theory mentions, it rules on a repo rule) and
goes to docs/.

series-bias-mining lands in investigation/, not answer/: its header said
complete while two open tickets said the sweep was unfinished. The
pipeline has nowhere to hold both claims."
```

---

### Task 7: Drop the legacy walk and forbid `studies/` growing back

**Files:**
- Modify: `tools/studies.py` (remove the legacy block from Task 4)
- Modify: `tests/test_conventions.py`
- Test: `tests/test_studies.py`, `tests/test_conventions.py`

**Interfaces:**
- Consumes: a migrated repo from Task 6.
- Produces: `test_no_new_top_level_directory` in `tests/test_conventions.py`.

- [ ] **Step 1: Write the failing test**

```python
_TOP_LEVEL = {
    ".claude", "attic", "db", "docs", "tests", "theories", "tickets",
    "tools", "user_reports",
}


def test_no_new_top_level_directory():
    """The top level is an allowlist. A new directory here is an
    architecture decision, not a side effect of somebody needing
    somewhere to put a file.

    `studies` is deliberately absent: it was dissolved on 2026-09-01
    when a study became a ticket living inside the theory that owns it,
    and this is what stops it growing back one stray mkdir at a time.
    """
    found = {
        p.name for p in ROOT.iterdir()
        if p.is_dir() and not p.name.startswith(".")
        or p.name == ".claude"
    }
    found -= {"__pycache__", ".git", ".pytest_cache", ".venv",
              ".worktrees", ".superpowers"}
    assert found <= _TOP_LEVEL, (
        "a new top-level directory appeared -- decide deliberately "
        f"whether it belongs: {sorted(found - _TOP_LEVEL)}"
    )
```

- [ ] **Step 2: Run to verify it passes already**

Run: `python -m pytest tests/test_conventions.py::test_no_new_top_level_directory -v`
Expected: PASS — Task 6 already removed `studies/`. If it FAILS naming `studies`, Task 6 step 10 was not completed.

- [ ] **Step 3: Remove the legacy walk**

Delete the `# LEGACY:` block from `survey` in `tools/studies.py` and its trailing comment.

- [ ] **Step 4: Verify nothing was relying on it**

Run: `python -m pytest -q && python -m tools.cli studies`
Expected: still 18 studies. A drop to zero means the migration left them where the legacy walk was finding them.

- [ ] **Step 5: Commit**

```bash
git add tools/studies.py tests/test_conventions.py
git commit -m "studies: drop the legacy tree walk, and pin the top level

The migration is done, so survey() no longer reads studies/. The
allowlist test is what stops the directory growing back one stray mkdir
at a time."
```

---

## Deferred to later phases

- **`theories/retired/` and `calibration_harvest`** (Phase 2). Until it exists, `2026-08-29-calibration-harvest-gradient-review` sits in the root study lane; Phase 2 moves it under the retired theory.
- **new-theory `evidence/` and `implement/` states, the four resolutions, the ideas-registry coupling** (Phase 3). This phase leaves `new-theory` at `open → completed`.
- **`tickets purge`** (Phase 4).
- **The CLAUDE.md data standard, the skill edits, the backlog-pressure rule, and the remaining two conventions tests** (Phase 5).

## Open questions carried forward

- **`series-bias-mining` sits in `investigation/`.** The user asked to be brought back to this once the pipeline is live and it can be seen sitting there. It is 355MB, its collector is infrastructure other studies read, and its two open tickets become ordinary `mention_family` tickets in Task 2. Raise it after Task 6.
