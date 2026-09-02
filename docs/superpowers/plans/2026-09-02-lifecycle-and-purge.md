# New-Theory Lifecycle and the Purge — Implementation Plan (Phases 3+4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the `new-theory` lane the states `open → evidence → implement → completed` with four meaningful resolutions, couple closing to the ideas registry, and add a citation-checked purge that removes long-completed tickets from the working tree.

**Architecture:** Phases 3 and 4 are planned together because both live in `tools/tickets.py` and the second depends on the first: the purge is only safe because closing a spec elevates its finding into the ideas registry first. Phase 3 extends `LANE_STATES` for `new-theory`, adds resolution validation and the registry coupling. Phase 4 adds `purge()` with its citation check, `--dry-run` by default, and one step in the floor.

**Tech Stack:** Python 3.11, stdlib only. pytest. SQLite via `tools/db.py`. `git rm` via subprocess for the purge.

**Spec:** [`docs/superpowers/specs/2026-09-01-data-and-ticket-lifecycle-design.md`](../specs/2026-09-01-data-and-ticket-lifecycle-design.md) — Part 2 (lifecycle) and Part 5 (purge). Parts 1, 6 and 7 are Phase 5 and out of scope.

## Global Constraints

- **Python 3.11, stdlib only.** No new dependencies.
- **State is a directory, never a frontmatter field.** This holds for the new states exactly as it does for the study lane.
- **The study lane is untouched.** It has NO `completed/`, its terminal state is `answer/`, and **that is what makes a study permanent under the purge** — a finished study is simply not a thing the purge's query matches. Nothing in this plan may give the study lane a `completed/`, and the purge must not special-case studies to protect them. If you find yourself writing a study exemption in `purge()`, the design has been broken somewhere upstream.
- **`--dry-run` is the DEFAULT for `purge`.** Deleting files must never be a side effect of a flag somebody forgot to pass.
- **Never `git add -A` or `git add .`** — other sessions work in this checkout. Stage explicit paths, then `git status --short` before committing.
- **Baseline:** `python -m pytest -q` currently reports **2 pre-existing failures** — `test_no_theory_imports_a_sibling_theory` and `test_every_repo_path_named_in_docs_resolves` — both from another lane's `no_side_premium`/`deadline_drift` work, both ticketed, neither yours. A third failure is yours.
- This codebase writes long explanatory comments saying *why* a rule exists, often citing the incident that motivated it. Match that; terse code that drops the rationale is a defect here.

## Interfaces that already exist — do not rebuild

- `tickets.LANE_STATES: dict[str, tuple[str, ...]]`; today `new-theory` is `("open", "completed")` and `study` is `("question", "investigation", "answer")`
- `tickets.states_for(lane) -> tuple[str, ...]`
- `tickets.advance(path, *, to, note, now=None) -> Path` — moves a ticket forward, refuses backwards moves, refuses a state the lane lacks, and **already refuses `to == "completed"`** because that is `close()`'s job
- `tickets.close(path, *, resolution, now=None) -> Path` — refuses a lane with no `completed/` state, refuses a ticket already in `completed/`
- `tickets._lane_of(state_dir) -> str`, `tickets.STUDY_FILE`
- `ideas.record(conn, slug, title, ...)`, `ideas.update_status(conn, slug, status, what_was_tried=, outcome=, revisit_angle=, revisit_after=, theory_id=)`, `ideas.get(conn, slug)`, `ideas.VALID_STATUSES = ("considered", "investigating", "promoted", "parked", "dead")`

---

### Task 1: `new-theory` gains `evidence` and `implement`

**Files:**
- Modify: `tools/tickets.py` (`LANE_STATES`)
- Test: `tests/test_tickets.py`

**Interfaces:**
- Produces: `states_for("new-theory") == ("open", "evidence", "implement", "completed")`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_new_theory_lane_has_an_evidence_and_implement_stage():
    assert tickets.states_for("new-theory") == (
        "open", "evidence", "implement", "completed")


def test_a_spec_advances_open_to_evidence_to_implement(tmp_path):
    path = tickets.create(
        tmp_path, lane="new-theory", slug="some-thesis",
        title="A thesis", body="The mechanism, the population, the bar.",
        created="2026-09-02")
    at_evidence = tickets.advance(
        path, to="evidence", note="Probing dispersion on one board.",
        now="2026-09-03")
    assert at_evidence.parent.name == "evidence"
    at_implement = tickets.advance(
        at_evidence, to="implement", note="Cleared the bar at n=240.",
        now="2026-09-04")
    assert at_implement.parent.name == "implement"


def test_a_spec_cannot_skip_the_evidence_stage(tmp_path):
    """The evidence stage is not optional for a spec nobody has measured.
    Jumping straight to a build order is exactly how a theory gets built
    on a thesis that was never tested."""
    path = tickets.create(
        tmp_path, lane="new-theory", slug="unmeasured", title="T",
        body="b", created="2026-09-02")
    with pytest.raises(ValueError, match="evidence"):
        tickets.advance(path, to="implement", note="skipping")


def test_advance_still_refuses_completed_for_new_theory(tmp_path):
    """close() owns the transition into completed/, because close() is
    what records the resolution."""
    path = tickets.create(
        tmp_path, lane="new-theory", slug="x", title="T", body="b",
        created="2026-09-02")
    with pytest.raises(ValueError):
        tickets.advance(path, to="completed", note="nope")
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_tickets.py -k "new_theory or evidence_stage" -v`
Expected: FAIL — `new-theory` still declares only `("open", "completed")`.

- [ ] **Step 3: Implement**

In `tools/tickets.py`, change the `new-theory` entry in `LANE_STATES`:

```python
    # A new-theory ticket IS a spec, and it earns its way to a build
    # order. `evidence` is where the cheapest decisive measurement runs
    # against the bar the spec wrote before looking; `implement` means
    # that measurement cleared it. The stage is not optional -- a spec
    # that jumps from `open` to `implement` is a theory built on a thesis
    # nobody tested, which is the failure the whole new-theory lane
    # exists to prevent.
    "new-theory": ("open", "evidence", "implement", "completed"),
```

Then add the skip guard to `advance`, after the backwards check:

```python
    if lane == "new-theory" and here == "open" and to == "implement":
        raise ValueError(
            "a spec cannot skip the evidence stage: advance it to "
            "'evidence' and run the measurement first. A build order "
            "issued on an unmeasured thesis is what this lane exists to "
            "prevent."
        )
```

- [ ] **Step 4: Run to verify they pass, then the full suite**

Run: `python -m pytest tests/test_tickets.py -v` then `python -m pytest -q`
Expected: PASS; suite at 2 pre-existing failures.

- [ ] **Step 5: Create the state directories**

```bash
mkdir -p tickets/new-theory/evidence tickets/new-theory/implement
```

Both need a `.gitkeep` so they survive a fresh clone — `tickets/new-theory/evidence/` currently holds the lane's shared reference material (the graded evidence ledger and two reading-note files), so check whether it already exists before creating it.

- [ ] **Step 6: Commit**

```bash
git add tools/tickets.py tests/test_tickets.py tickets/new-theory/
git status --short
git commit -m "tickets: a new-theory spec earns its way to a build order

open -> evidence -> implement -> completed. The evidence stage is not
optional: a spec jumping straight to `implement` is a theory built on a
thesis nobody measured, which is the failure this lane exists to prevent."
```

---

### Task 2: Four resolutions, and closing elevates the knowledge first

The heart of Phase 3. `disproven` and `underpowered` mean opposite things about re-proposing, and that distinction is invisible today.

**Files:**
- Modify: `tools/tickets.py` (`close`)
- Modify: `tools/cli.py` (pass a connection into close)
- Test: `tests/test_tickets.py`

**Interfaces:**
- Produces: `tickets.NEW_THEORY_RESOLUTIONS = ("built", "disproven", "underpowered", "superseded")`; `close(path, *, resolution, now=None, conn=None)` — `conn` required when closing a `new-theory` ticket with `disproven` or `underpowered`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_new_theory_close_requires_a_known_resolution(tmp_path):
    path = tickets.create(tmp_path, lane="new-theory", slug="x", title="T",
                          body="b", created="2026-09-02")
    with pytest.raises(ValueError, match="built|disproven|underpowered"):
        tickets.close(path, resolution="did not work out")


def test_built_and_superseded_need_no_registry_entry(tmp_path):
    path = tickets.create(tmp_path, lane="new-theory", slug="x", title="T",
                          body="b", created="2026-09-02")
    done = tickets.close(path, resolution="built: now theories/x")
    assert done.parent.name == "completed"


def test_disproven_refuses_without_an_ideas_entry(tmp_path, conn):
    """The purge may delete a completed spec after a week. That is only
    safe because the finding elevated OUT of the file first -- otherwise
    somebody re-proposes the same dead thesis in three weeks, which is
    exactly what the ideas registry exists to prevent."""
    path = tickets.create(tmp_path, lane="new-theory", slug="deadidea",
                          title="T", body="b", created="2026-09-02")
    with pytest.raises(ValueError, match="ideas"):
        tickets.close(path, resolution="disproven: zero violations",
                      conn=conn)


def test_underpowered_needs_a_revisit_angle(tmp_path, conn):
    """`underpowered` means we could not tell, not that the thesis is
    dead -- so it is re-proposable, and the registry has to say what
    would have to change before anyone tries again."""
    ideas.record(conn, "thinpop", "Thin population thesis")
    ideas.update_status(conn, "thinpop", "parked",
                        what_was_tried="probed one board",
                        outcome="only 4 markets qualified")
    path = tickets.create(tmp_path, lane="new-theory", slug="thinpop",
                          title="T", body="b", created="2026-09-02")
    with pytest.raises(ValueError, match="revisit_angle"):
        tickets.close(path, resolution="underpowered: 4 markets",
                      conn=conn)
    ideas.update_status(conn, "thinpop", "parked",
                        revisit_angle="retry when the series lists weekly")
    done = tickets.close(path, resolution="underpowered: 4 markets",
                         conn=conn)
    assert done.parent.name == "completed"


def test_other_lanes_keep_free_text_resolutions(tmp_path):
    path = tickets.create(tmp_path, lane="maintenance", slug="x", title="T",
                          body="b", created="2026-09-02")
    done = tickets.close(path, resolution="not a bug, the caller was wrong")
    assert done.parent.name == "completed"
```

Add a `conn` fixture if `tests/test_tickets.py` has none — `db.connect(tmp_path / "t.db")` then `db.init_db(conn)`.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_tickets.py -k "resolution or disproven or underpowered or superseded" -v`

- [ ] **Step 3: Implement**

Add near the top of `tools/tickets.py`:

```python
#: The four ways a new-theory spec can end, and the reason the vocabulary
#: is fixed: `disproven` and `underpowered` mean OPPOSITE things about
#: re-proposing, and today that distinction is invisible in free text.
#:
#:   built        became a running theory -- name it
#:   disproven    the bar was met and the thesis failed. Not re-proposable.
#:                `calendar-arb` and `smile-smoothing` are the worked
#:                examples: measured, and the answer was no.
#:   underpowered the measurement COULD NOT REACH the bar -- population too
#:                thin, history too short, liquidity too low. This is a
#:                different claim ("we could not tell"), and it IS
#:                re-proposable when conditions change.
#:   superseded   folded into another spec or theory
NEW_THEORY_RESOLUTIONS = ("built", "disproven", "underpowered", "superseded")

#: Closing one of these elevates the finding into the ideas registry
#: BEFORE the file may be deleted. See `close`.
_RESOLUTIONS_NEEDING_A_REGISTRY_ENTRY = ("disproven", "underpowered")
```

Then in `close`, after the existing guards and before any write:

```python
    if lane == "new-theory":
        word = resolution.strip().split(":")[0].strip().lower()
        if word not in NEW_THEORY_RESOLUTIONS:
            raise ValueError(
                f"a new-theory resolution starts with one of "
                f"{NEW_THEORY_RESOLUTIONS}, not {word!r}. `disproven` "
                "means the bar was met and the thesis failed; "
                "`underpowered` means the measurement could not reach "
                "the bar, which is a different claim and stays "
                "re-proposable."
            )
        if word in _RESOLUTIONS_NEEDING_A_REGISTRY_ENTRY:
            _require_idea(conn, slug_of(path), word)
```

And the helper, with the reasoning that makes it load-bearing:

```python
def _require_idea(conn, slug: str, word: str) -> None:
    """Refuse the close unless the finding already elevated.

    This is not bookkeeping. `purge` deletes a completed ticket after a
    week, and that is only safe because the durable fact left the file
    first. Without this coupling, purging an uncited `underpowered` spec
    just lets somebody re-propose the same dead thesis in three weeks --
    the exact failure the ideas registry exists to prevent.
    """
    if conn is None:
        raise ValueError(
            f"closing a spec {word!r} needs a database connection: the "
            "finding has to reach the ideas registry before the file may "
            "be deleted"
        )
    from tools import ideas
    row = ideas.get(conn, slug)
    if row is None:
        raise ValueError(
            f"no ideas-registry entry for {slug!r}. Record it first "
            "(`ideas record` then `ideas status`) with what was tried and "
            "what was learned -- the purge may delete this file in a week."
        )
    if not (row["what_was_tried"] or "").strip():
        raise ValueError(f"idea {slug!r} has no what_was_tried")
    if not (row["outcome"] or "").strip():
        raise ValueError(f"idea {slug!r} has no outcome")
    if word == "underpowered" and not (row["revisit_angle"] or "").strip():
        raise ValueError(
            f"idea {slug!r} has no revisit_angle. `underpowered` means "
            "the measurement could not reach the bar, so it stays "
            "re-proposable -- say what would have to change."
        )
```

Add a `slug_of(path)` helper (strip the dated prefix from the stem, or the parent directory's name for a study) if one does not already exist, and derive `lane` with the existing `_lane_of`.

Wire `conn` through `cli.py`'s `close` branch: open a connection and pass it.

- [ ] **Step 4: Run tests, then the full suite**

Run: `python -m pytest tests/test_tickets.py tests/test_cli.py -v` then `python -m pytest -q`

- [ ] **Step 5: Commit**

```bash
git add tools/tickets.py tools/cli.py tests/
git status --short
git commit -m "tickets: four resolutions, and closing elevates the finding first

disproven and underpowered mean opposite things about re-proposing, and
free text made that invisible. Closing either now requires the finding in
the ideas registry -- which is what makes the purge safe: the file may go
because the durable fact already left it."
```

---

### Task 3: `purge` — citation-checked, dry-run by default

**Files:**
- Modify: `tools/tickets.py` (add `purge`)
- Modify: `tools/cli.py` (add the subcommand)
- Test: `tests/test_tickets.py`

**Interfaces:**
- Produces: `tickets.purge(root, *, older_than=7, apply=False, conn=None, now=None) -> dict` returning `{"purged": [...], "kept": [{"path":..., "cited_by":...}], "dry_run": bool}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_purge_is_dry_run_by_default(tmp_path):
    """Deleting files must never be a side effect of a flag somebody
    forgot to pass."""
    path = _completed_ticket(tmp_path, "old-one", closed="2026-08-01")
    result = tickets.purge(tmp_path, now="2026-09-02")
    assert result["dry_run"] is True
    assert path.exists()
    assert str(path) in [p for p in result["purged"]]


def test_purge_keeps_a_ticket_something_cites(tmp_path):
    path = _completed_ticket(tmp_path, "cited-one", closed="2026-08-01")
    (tmp_path / "NOTES.md").write_text(
        "see 2026-08-01-cited-one for why\n", encoding="utf-8")
    result = tickets.purge(tmp_path, apply=True, now="2026-09-02")
    assert path.exists()
    assert any("cited-one" in k["path"] for k in result["kept"])


def test_purge_leaves_a_recent_ticket_alone(tmp_path):
    path = _completed_ticket(tmp_path, "fresh", closed="2026-09-01")
    tickets.purge(tmp_path, apply=True, now="2026-09-02")
    assert path.exists()


def test_purge_never_matches_a_study(tmp_path):
    """Not by exemption -- the study lane's terminal state is `answer/`,
    so a finished study is not a thing this query can match. If a study
    exemption ever appears in purge(), the design broke upstream."""
    study = tickets.create(tmp_path, lane="study", slug="a-study",
                           title="Q", body="bar", created="2026-01-01")
    answered = tickets.advance(study, to="answer", note="done",
                               now="2026-01-02")
    tickets.purge(tmp_path, apply=True, now="2026-09-02")
    assert answered.exists()
```

Write a `_completed_ticket(root, slug, closed)` helper that creates a ticket and closes it, then rewrites the `closed:` line to the given date.

- [ ] **Step 2: Run to verify they fail**

- [ ] **Step 3: Implement**

```python
#: Where a citation of a ticket can live. A ticket cited by any of these
#: is KEPT, because deleting it would break the reference -- and a
#: reference is evidence somebody found it worth pointing at.
_CITATION_GLOBS = (
    "CLAUDE.md", "README.md", "RESEARCH_LOG.md", "FLEET_LOG.md",
    "docs/**/*.md", ".claude/skills/**/*.md", "tests/**/*.py",
    "theories/**/*.md", "tickets/**/*.md",
)


def purge(root, *, older_than: int = 7, apply: bool = False,
          conn=None, now: str | None = None) -> dict:
    """Remove long-completed tickets that nothing cites. Dry run by default.

    A finished ticket is the record of what was asked for and why, which
    is why `close` keeps it rather than deleting it. But the backlog is
    read by listing, and a tree that only ever grows makes the cheapest,
    most-repeated read in the repo the largest. Git history is the
    durable record -- `git log --diff-filter=D` finds a purged ticket and
    `git show` retrieves it -- so a completed ticket nothing points at
    does not need to sit in the working tree forever.

    **Studies are never candidates, and not by exemption.** The study
    lane's terminal state is `answer/`, not `completed/`, so a finished
    study is simply not a thing this query matches. Permanence falls out
    of the state names.
    """
```

Body: walk every `completed/` directory under `tickets/` and `theories/`; parse each ticket's `closed:` date; skip any closed fewer than `older_than` days before `now`; for each candidate, search the citation globs and the DB's citation-bearing text (`theory_slices.origin`, ticket `resolution` fields) for the slug; keep it if found; otherwise record it. When `apply` is true, `git rm` each purged path via `subprocess.run(["git", "rm", "-q", "--", str(p)], cwd=root, check=True)`.

Add the CLI subcommand with `--apply` and `--older-than`, defaulting to a dry run, printing what would go and what was kept and why.

- [ ] **Step 4: Run tests and the full suite**

- [ ] **Step 5: Verify against the real repo, read-only**

```bash
python -m tools.cli tickets purge
```

Expected: a dry-run listing. **Read it and sanity-check it before anyone ever runs `--apply`** — this repo has ~30 completed tickets and several are cited from `tickets/new-theory/README.md`'s rule 0. If the listing proposes deleting a ticket that rule 0 cites, the citation check is broken and that is a Critical finding to fix before committing.

- [ ] **Step 6: Commit**

```bash
git add tools/tickets.py tools/cli.py tests/test_tickets.py
git status --short
git commit -m "tickets: purge long-completed, uncited tickets. Dry run by default."
```

---

### Task 4: The floor runs the purge

**Files:**
- Modify: `.claude/skills/go-floor/SKILL.md`

- [ ] **Step 1: Add the step**

In the **Floor record** section (section 5, the receipt), add running `python -m tools.cli tickets purge --apply` and reporting the count and names. Keep it in the receipt section, not the bets section — it is bookkeeping, not something the user acts on.

Say explicitly in the skill text that the purge is citation-checked and that git history retains anything removed, so a reader does not think the floor is destroying records.

- [ ] **Step 2: Verify the skill's paths still resolve**

Run: `python -m pytest tests/test_conventions.py -q`
Expected: no new failures — `test_every_repo_path_named_in_a_skill_resolves` covers this file.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/go-floor/SKILL.md
git commit -m "go-floor: run the citation-checked purge and report it in the receipt"
```

## What this deliberately does not do

- **No study exemption in `purge`.** Studies are safe because their terminal state is `answer/`. Writing an exemption would mean the state names had stopped carrying the meaning, and the right fix would be upstream.
- **No retroactive bulk purge.** The 7-day clock runs from each ticket's own `closed:` date. The first `--apply` will find a backlog; that is why the dry run is the default and why Task 3 Step 5 requires reading the listing first.
- **Does not resolve the retired-theory ticket gap** (`tickets/maintenance/open/2026-09-02-filing-a-ticket-against-a-retired-theory.md`). That is a real conflict, but it is about `ticket_dir` refusing a retired theory, and it is cleaner as its own change than smuggled into the lifecycle work.
