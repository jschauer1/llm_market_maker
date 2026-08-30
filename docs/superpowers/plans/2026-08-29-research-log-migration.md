# RESEARCH_LOG.md Migration Implementation Plan (spec §6.8, phases 3–5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the one-time RESEARCH_LOG.md migration — pin the classification, fix the three double-`##` headings, land the citation guard test, move the 22 T entries to their theories' notebooks, split the 14 M entries one at a time, reconcile, and make the §6.5 promotion bar bind via the §6.7 CLAUDE.md rewrite.

**Architecture:** The migration acts on the companion classification table, never on judgment made up on the spot. T entries move verbatim (mechanical); M entries split one commit each (the only judgment-bearing step); X entries are untouched. Every moved entry leaves a stub at its original anchor with the `## ` heading line preserved **byte-for-byte** (the `rulings.log_entry` conventions test and the new citation test both key on headings). The citation test lands green *before* anything moves and runs after every commit.

**Tech Stack:** Python 3 + pytest, git, the repo's `tools/` CLI (`rulings record`), plain markdown editing. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-29-enforcing-surfaces-design.md` §6 (esp. §6.6–6.8) — read §6 in full before executing any task. **Input table (authoritative):** `docs/superpowers/specs/2026-08-29-enforcing-surfaces-log-classification.md` — the migration acts on that table's rows, owner column, split/pairing notes, and positional-reference list.

## Global Constraints

- **RESEARCH_LOG.md is append-only except for stubs.** A stub is an in-place edit that replaces an entry's *body*; the `## ` heading line is never reworded, reformatted, or deleted (except the three sanctioned joins in Task 2). Several `rulings.log_entry` rows cite headings verbatim; `tests/test_conventions.py::test_every_ruling_log_entry_resolves` enforces this.
- **Locate entries by heading text, never by line number.** Line numbers in this plan are as of commit `6fe567a` and shift after Task 2's joins and as the peer session appends entries.
- **One commit per owning theory in Task 4–9 (T moves); one commit per entry in Tasks 10–14 (M splits). Never batch M splits.**
- **After every commit: run the citation tests and the full suite** (`python -m pytest tests/ -x -q`, ~1,038 tests, <1 min). A broken citation must surface while the move that broke it is the newest commit (spec §6.8 step 5).
- **Anything appended to RESEARCH_LOG.md after the Task 1 pin is out of scope for this pass.** Do not classify, move, or stub it.
- **Files owned by the peer session (llm-market-identifier-21) — do not edit:** `tools/score.py`, `tools/theories.py`, `tools/slices.py`, `tools/snapshot.py`, `db/schema.sql`, `.claude/skills/`. `tests/test_conventions.py` is shared: peer appends phase-A/6/7 tests; our Task 3 appends at end of file; message the peer before editing it and rebase on their append if simultaneous.
- **CLAUDE.md:** the only edit this plan makes is Task 15's §6.7 in-place sentence rewrite. Message the peer session when it lands (their phase-B `go`-skill rule move waits on it).
- **Commits:** message style follows repo convention (`log: ...`, `test: ...`, `spec: ...`), each ending with the trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. Commit directly on `master`; the working tree is shared with a live peer session, so `git add` only the files your task names — never `git add -A`.
- **Encoding:** RESEARCH_LOG.md contains em-dashes (—) and other non-ASCII. All Python snippets must read/write `encoding="utf-8"`. On this Windows checkout, do not pipe file content through PowerShell cmdlets that re-encode; use the Read/Edit tools or Python.

## Shared reference: stub and notebook formats

**T-entry stub** (replaces the entire body between the entry's heading line and the next `## ` line; heading kept verbatim):

```markdown
Moved 2026-08-29 to `<notebook path>` under the heading
`## <date> — <heading> (migrated from RESEARCH_LOG.md)`, per the
enforcing-surfaces migration (spec §6.8).
```

**Notebook entry** (appended at end of the owner's NOTES.md; entries appended in date order relative to each other; body verbatim, not summarized, not reflowed):

```markdown
## <date> — <heading> (migrated from RESEARCH_LOG.md)

<original body, verbatim>
```

Where `<date> — <heading>` is the joined single-line heading text exactly as it stands in the log after Task 2.

**M-entry stub** (replaces the body; heading kept verbatim): one paragraph carrying the extracted repo-level fact, then the pointer line. Example shape:

```markdown
<One paragraph: the repo-level fact this entry established, stated
directly — e.g. "Kalshi archives settled markets out of its public API
~60 days after close; backward extension of any settled dataset is
impossible. This constraint is now stated in CLAUDE.md's data
conventions.">

Narrative moved 2026-08-29 to `<notebook or study path>` under
`## <date> — <heading> (migrated from RESEARCH_LOG.md)` (spec §6.8).
```

**Owner → notebook path map:**

| owner | notebook |
|---|---|
| insider_judgment | `theories/insider_bias/insider_judgment/NOTES.md` |
| mention_family | `theories/insider_bias/mention_family/NOTES.md` |
| structural_arb | `theories/structural_arb/NOTES.md` |
| deadline_drift | `theories/deadline_drift/NOTES.md` |
| no_side_premium | `theories/no_side_premium/NOTES.md` |
| calibration_harvest | `theories/calibration_harvest/NOTES.md` |
| studies/2026-08-29-smile-smoothing-ladder-flatness/ | that folder's `STUDY.md` |
| studies/2026-08-29-series-bias-mining/ | that folder's `STUDY.md` |

---

### Task 1: Pin the classification (spec §6.8 step 1)

**Files:**
- Modify: `docs/superpowers/specs/2026-08-29-enforcing-surfaces-log-classification.md` (extend the `## Addendum` table at the end)

**Interfaces:**
- Produces: the pinned input table every later task reads. The addendum gains one row per log entry appended after the existing addendum row ("slice sweep", log line ~2868), each classified T/M/X with owner and word count, plus a pin line naming the git revision classified against.

- [ ] **Step 1: Enumerate the unclassified entries.** Run:

```bash
grep -n '^## ' RESEARCH_LOG.md
```

Every heading after `## 2026-08-29 (cont.) — slice sweep: ...` is unclassified. As of `6fe567a` these are 8 entries (lines 2909, 2943, 2960, 2983, 3003, 3023, 3039, 3080 — spec review, three RULING entries, architecture-written-in, foundation shipped, storage gate measured); the peer session may have appended more — include everything present at `git rev-parse HEAD`.

- [ ] **Step 2: Read each entry in full and classify it** under the companion file's legend (T / M / X, owner, word count). Word count per entry:

```python
import re
text = open("RESEARCH_LOG.md", encoding="utf-8").read()
parts = re.split(r"^(## .+)$", text, flags=re.M)
# parts alternates: preamble, heading, body, heading, body...
for h, b in zip(parts[1::2], parts[2::2]):
    print(len(b.split()), h[:80])
```

Expected: all 8 are X (governance/tooling — rulings, spec review, foundation, storage gate) with owner `—`. If any turns out T or M, it joins the corresponding later task's worklist — say so in the addendum row and in the task's commit message.

- [ ] **Step 3: Append the rows to the addendum table** in the companion file, preceded by a pin line: `Pinned 2026-08-29 against <sha of git rev-parse HEAD>; entries appended after this revision are out of scope for the migration pass (spec §6.8 step 1).`

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-08-29-enforcing-surfaces-log-classification.md
git commit -m "spec: pin the log classification — addendum covers entries through <short-sha> (spec 6.8 step 1)"
```

### Task 2: Join the three double-`##` headings (spec §6.8 step 2)

**Files:**
- Modify: `RESEARCH_LOG.md` (three heading pairs; nothing else)

**Interfaces:**
- Produces: every entry heading on one `## ` line, so heading-anchored stubs, citations, and counts are stable. All later tasks assume the joined form.

- [ ] **Step 1: Join each pair with the Edit tool** — exact in-place replacements (as of `6fe567a`, lines 290–291, 359–360, 471–472):

Replace:
```
## 2026-08-24 — First tier A backtest of the stage-1 screen, after a false
## start that took 47 minutes to fail
```
with:
```
## 2026-08-24 — First tier A backtest of the stage-1 screen, after a false start that took 47 minutes to fail
```

Replace:
```
## 2026-08-24 — Two follow-ups from user questions: a corrected Big Brother
## bet, and a new mechanical path for the MENTION-family edge
```
with:
```
## 2026-08-24 — Two follow-ups from user questions: a corrected Big Brother bet, and a new mechanical path for the MENTION-family edge
```

Replace:
```
## 2026-08-24 — mention_family becomes a real, separate theory; insider_bias
## renamed insider_judgment and folded into a shared parent folder
```
with:
```
## 2026-08-24 — mention_family becomes a real, separate theory; insider_bias renamed insider_judgment and folded into a shared parent folder
```

- [ ] **Step 2: Verify the count.** `grep -c '^## ' RESEARCH_LOG.md` must drop by exactly 3 from the Task 1 measurement (77 → 74 as of `6fe567a`; if the peer appended N entries since, 77+N → 74+N).

- [ ] **Step 3: Run the guard tests**

Run: `python -m pytest tests/test_conventions.py -q`
Expected: PASS — no ruling cites these three headings (verified 2026-08-29: all cited headings are single-line X entries), but this proves it.

- [ ] **Step 4: Commit**

```bash
git add RESEARCH_LOG.md
git commit -m "log: join the three double-## headings in place (spec 6.8 step 2)"
```

### Task 3: Citation sweep + the citation guard test (spec §6.8 step 3, §6.6)

**Files:**
- Create: `docs/superpowers/specs/2026-08-29-enforcing-surfaces-citation-sweep.txt` (the saved sweep output)
- Modify: `tests/test_conventions.py` (append two tests at end of file; coordinate with the peer session before editing — they may be appending phase-A/6/7 tests)
- Test: `tests/test_conventions.py`

**Interfaces:**
- Consumes: the existing idioms in `tests/test_conventions.py` — `ROOT`, the DB-read-and-skip pattern of `test_every_recorded_prompt_path_still_resolves` (line ~173), and the doc-scan style of `_doc_paths()` (line ~351).
- Produces: `test_every_slice_origin_citation_still_resolves` and `test_every_dated_cross_citation_still_resolves` — the migration's only real safety net; every later task runs them.

- [ ] **Step 1: Message the peer session** (SendMessage to llm-market-identifier-21): about to append to `tests/test_conventions.py`; hold their edits until this task's commit lands.

- [ ] **Step 2: Run the sweep and save the output:**

```bash
{ grep -rn 'THEORY.md Learnings\|NOTES.md 20\|RESEARCH_LOG' --include='*.md' --include='*.py' . ; \
  grep -n 'entry above\|entry two above\|entries above\|see above' RESEARCH_LOG.md ; \
  python -m tools.cli slices list ; } > docs/superpowers/specs/2026-08-29-enforcing-surfaces-citation-sweep.txt 2>&1
```

Read the output. Expected positional references (companion file, "Positional references" section): log lines ~68, ~1511, ~2242, ~2682 — only ~2242 (the politics CORRECTION) crosses a move boundary, and its handling is bound by Task 9/10's pairing rules. Any *new* positional reference crossing a move boundary must be added to the companion file's pairing notes before Task 4 runs.

- [ ] **Step 3: Write the two failing-by-construction tests** (they must pass against the current tree — the point is they run *before* the first move and keep passing after every move; a silent move breaks them). Append to `tests/test_conventions.py`:

```python
_DATE = re.compile(r"20\d{2}-\d{2}-\d{2}")
_CITED_PATH = re.compile(
    r"(?:theories|studies|docs|tools|tests)/[A-Za-z0-9_./\-]*[A-Za-z0-9_\-]"
)


def _file_contains_date_heading(path, date):
    """True when `date` appears on a heading-ish line of `path`: a line
    starting with '#', or a bolded '**' section lead. Notebook headings,
    THEORY.md section titles, and log stubs all satisfy this; a body-text
    mention does not, which is what makes a silent move visible."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if date in line and (line.lstrip().startswith("#")
                             or line.lstrip().startswith("**")):
            return True
    return False


def test_every_slice_origin_citation_still_resolves():
    """A slice's origin is its pre-registration provenance (CLAUDE.md,
    'Subset edges'). It cites files and dated section headings in prose;
    nothing else enforces them, so a notebook migration could silently
    orphan the provenance of a registered slice. Every repo path named in
    an origin must exist, and every date named must still appear as a
    heading in at least one of the cited files. A stub or a migrated
    heading satisfies this; a silent move does not. (spec 6.6)

    Read-only against the working database, skipped where there is none —
    same idiom as test_every_recorded_prompt_path_still_resolves."""
    if not db.DEFAULT_DB_PATH.exists():
        pytest.skip("no working database in this environment")
    conn = db.connect(db.DEFAULT_DB_PATH)
    try:
        rows = list(conn.execute("SELECT theory_id, slug, origin FROM theory_slices"))
    finally:
        conn.close()
    problems = []
    for r in rows:
        origin = r["origin"] or ""
        cited = [p.rstrip(".") for p in _CITED_PATH.findall(origin)]
        files = []
        for p in cited:
            if not (ROOT / p).exists():
                problems.append(f"{r['theory_id']}/{r['slug']}: cites missing `{p}`")
            elif (ROOT / p).is_file():
                files.append(ROOT / p)
        for date in set(_DATE.findall(origin)):
            if files and not any(_file_contains_date_heading(f, date) for f in files):
                problems.append(
                    f"{r['theory_id']}/{r['slug']}: date {date} no longer a "
                    f"heading in any cited file"
                )
    assert problems == [], (
        "a registered slice's origin citation no longer resolves -- "
        "restore the heading (a stub suffices) or repoint the origin's "
        "citation deliberately:\n" + "\n".join(problems)
    )


#: Files whose prose cites other files' dated entries. RESEARCH_LOG.md is
#: scanned for citations INTO notebooks; notebooks and THEORY.md files for
#: citations into each other and back into the log.
_CITING_GLOBS = ("RESEARCH_LOG.md", "theories/*/NOTES.md", "theories/*/*/NOTES.md",
                 "theories/*/THEORY.md", "theories/*/*/THEORY.md")
_CITE_LINE = re.compile(
    r"(?P<file>[A-Za-z0-9_./\-]*(?:NOTES\.md|THEORY\.md|RESEARCH_LOG\.md))"
)


def test_every_dated_cross_citation_still_resolves():
    """Notebooks, THEORY.md files and the log cite each other's entries by
    date ('NOTES.md 2026-08-26'). A migration moves entries between these
    files, and a date citation breaks silently because the date still
    exists somewhere. Any line that names one of these files AND a date
    must point at a file that still carries that date as a heading. A stub
    keeps the heading, so stubs pass; a silent move fails. (spec 6.6)

    Resolution: an explicit path in the citation wins; a bare NOTES.md /
    THEORY.md resolves to the citing file's own directory when possible;
    otherwise every file of that name is searched and ANY hit passes --
    deliberately loose, because prose citations name theories in words
    ('mention_family's NOTES.md') that a regex should not guess at."""
    problems = []
    for pattern in _CITING_GLOBS:
        for doc in sorted(ROOT.glob(pattern)):
            for line in doc.read_text(encoding="utf-8").splitlines():
                m = _CITE_LINE.search(line)
                dates = _DATE.findall(line)
                if not m or not dates:
                    continue
                span = m.group("file")
                if "/" in span and (ROOT / span).exists():
                    targets = [ROOT / span]
                elif "/" in span:
                    problems.append(f"{doc.relative_to(ROOT)}: cites missing `{span}`")
                    continue
                elif (doc.parent / span).exists():
                    targets = [doc.parent / span]
                else:
                    targets = sorted(ROOT.glob(f"**/{span}"))
                for date in dates:
                    if targets and not any(
                        _file_contains_date_heading(t, date) for t in targets
                    ):
                        problems.append(
                            f"{doc.relative_to(ROOT)}: `{span}` {date} -- no "
                            f"target still carries that date as a heading"
                        )
    assert problems == [], (
        "a dated cross-citation no longer resolves -- the entry it cites "
        "was moved without a stub, or its heading was reworded:\n"
        + "\n".join(problems)
    )
```

- [ ] **Step 4: Run the new tests against the untouched tree**

Run: `python -m pytest tests/test_conventions.py -q`
Expected: PASS. If either fails on the *current* tree, the failure is a pre-existing broken citation: fix the citation (or, if the heading-line heuristic produces a false positive on a real citation format, loosen `_file_contains_date_heading` to any-line containment **and record why in its docstring**). Nothing moves until both are green.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: all pass (~1,038 + 2).

- [ ] **Step 6: Commit**

```bash
git add tests/test_conventions.py docs/superpowers/specs/2026-08-29-enforcing-surfaces-citation-sweep.txt
git commit -m "test: dated cross-citations and slice origins must keep resolving; sweep saved (spec 6.8 step 3)"
```

### Task 4: Move insider_judgment's 10 T entries (spec §6.8 steps 4–5)

**Files:**
- Modify: `RESEARCH_LOG.md` (10 stubs), `theories/insider_bias/insider_judgment/NOTES.md` (10 appended entries)

**Interfaces:**
- Consumes: the stub/notebook formats and owner map from "Shared reference" above; the companion table's T rows for owner `insider_judgment`.

- [ ] **Step 1: Locate the 10 entries by heading text** (companion table T rows, owner insider_judgment):
  1. `2026-08-23 — \`insider_bias\` is \`active\` but already past its review trigger`
  2. `2026-08-23 — First live run: the screen has almost no thesis alignment`
  3. `2026-08-24 — First tier A backtest of the stage-1 screen, after a false start that took 47 minutes to fail`
  4. `2026-08-25 — insider_judgment tier-A full coverage: the gate separates, but what it keeps is only breakeven; judged sample launched`
  5. `2026-08-26 — Tier-B judged sample complete: judgment orders outcomes; strong-NO and the rules-divergence flag are the standouts`
  6. `2026-08-26 — Strong-YES autopsy: the bleed was sealed-tabulation award markets; excluding them repairs YES to breakeven, NO-rule strengthens`
  7. `2026-08-26 — Uniform "enter 3-2 days before close" repriced from the candle cache: waiting KILLS the moderate edge, only strong-NO survives late entry`
  8. `2026-08-26 — FULL POPULATION JUDGED: the pre-registered NO-side rule REPLICATED out of sample`
  9. `2026-08-26 — Gate validation: 100 gated-out events judged, 99 weak / 1 moderate / 0 strong; the session's autonomous arc is complete`
  10. `2026-08-29 (cont.) — gate.py reads resolution rules; 130 survivors → 18`

- [ ] **Step 2: For each, in date order:** append the full body verbatim to the notebook under the migrated-heading format, then replace the log body with the T-stub. Body = everything between the heading line and the next `^## ` line (or EOF), including sub-headings, tables, and any `**Addendum**` blocks — verbatim.

- [ ] **Step 3: Verify no content was lost.** For each moved entry, the word count of the appended notebook section must equal the word count of the original body (use the Task 1 Step 2 snippet on a pre-move copy, or `git show HEAD:RESEARCH_LOG.md`).

- [ ] **Step 4: Run the citation tests and full suite**

Run: `python -m pytest tests/test_conventions.py -q && python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add RESEARCH_LOG.md theories/insider_bias/insider_judgment/NOTES.md
git commit -m "log: migrate insider_judgment's 10 theory-local entries to its NOTES.md (spec 6.8 step 4)"
```

### Task 5: Move mention_family's 3 T entries — includes the two-theory pairing

**Files:**
- Modify: `RESEARCH_LOG.md` (3 stubs), `theories/insider_bias/mention_family/NOTES.md` (3 appended entries), `theories/insider_bias/insider_judgment/NOTES.md` (1 dated pointer)

**Interfaces:**
- Consumes: shared formats; companion table T rows for owner `mention_family *`, and its "Two follow-ups" pairing note.

- [ ] **Step 1: Move, in date order** (same procedure as Task 4 steps 2–3):
  1. `2026-08-24 — Two follow-ups from user questions: a corrected Big Brother bet, and a new mechanical path for the MENTION-family edge` — **moves whole to mention_family's notebook** (pairing note: the bulk is mention_family's origin story).
  2. `2026-08-25 — mention_family edge audited on user suspicion: mechanics clean, inference weak, live slate mismatched`
  3. `2026-08-25 — Full-coverage rerun: mention_family has no edge; under_review, retirement proposed`

- [ ] **Step 2: The pairing pointer.** Append to `theories/insider_bias/insider_judgment/NOTES.md`:

```markdown
## 2026-08-24 — pointer: the corrected Big Brother bet (migrated entry lives in mention_family's notebook)

Item (1) of `## 2026-08-24 — Two follow-ups from user questions: a
corrected Big Brother bet, and a new mechanical path for the
MENTION-family edge (migrated from RESEARCH_LOG.md)` in
`theories/insider_bias/mention_family/NOTES.md` is insider_judgment's:
the Big Brother correction and the stage-3 checklist item.
```

- [ ] **Step 3: Run citation tests + full suite** (as Task 4 step 4). Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add RESEARCH_LOG.md theories/insider_bias/mention_family/NOTES.md theories/insider_bias/insider_judgment/NOTES.md
git commit -m "log: migrate mention_family's 3 theory-local entries; Big Brother pointer in insider_judgment (spec 6.8 step 4)"
```

### Task 6: Move structural_arb's 5 T entries

**Files:**
- Modify: `RESEARCH_LOG.md` (5 stubs), `theories/structural_arb/NOTES.md` (5 appended entries)

- [ ] **Step 1: Move, in date order** (procedure of Task 4 steps 2–3):
  1. `2026-08-26 — structural_arb implemented from backlog; first live riskless find recorded`
  2. `2026-08-27 — structural_arb v2: depth gate mechanical; queue re-quoted, mostly decayed`
  3. `2026-08-29 (cont.) — structural_arb: six violations in 11 snapshots, and all three kinds are sterile`
  4. `2026-08-29 (cont.) — structural_arb v3: the sterile classes screened at stage 1`
  5. `2026-08-29 (cont.) — structural_arb v4: the guard is free, and now complete`

- [ ] **Step 2: Run citation tests + full suite.** Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add RESEARCH_LOG.md theories/structural_arb/NOTES.md
git commit -m "log: migrate structural_arb's 5 theory-local entries to its NOTES.md (spec 6.8 step 4)"
```

### Task 7: Move deadline_drift's 1 T entry

**Files:**
- Modify: `RESEARCH_LOG.md` (1 stub), `theories/deadline_drift/NOTES.md` (1 appended entry)

- [ ] **Step 1: Move** `2026-08-29 (cont.) — deadline-drift's classifier audited three times; the spec is missing its biggest exclusion` (procedure of Task 4 steps 2–3).
- [ ] **Step 2: Run citation tests + full suite.** Expected: PASS.
- [ ] **Step 3: Commit**

```bash
git add RESEARCH_LOG.md theories/deadline_drift/NOTES.md
git commit -m "log: migrate deadline_drift's classifier-audit entry to its NOTES.md (spec 6.8 step 4)"
```

### Task 8: Move no_side_premium's 1 T entry

**Files:**
- Modify: `RESEARCH_LOG.md` (1 stub), `theories/no_side_premium/NOTES.md` (1 appended entry)

- [ ] **Step 1: Move** `2026-08-29 (session 3, item 2) — no_side_premium: a sharper estimator, and a contaminated control caught` (procedure of Task 4 steps 2–3).
- [ ] **Step 2: Run citation tests + full suite.** Expected: PASS.
- [ ] **Step 3: Commit**

```bash
git add RESEARCH_LOG.md theories/no_side_premium/NOTES.md
git commit -m "log: migrate no_side_premium's estimator entry to its NOTES.md (spec 6.8 step 4)"
```

### Task 9: Move calibration_harvest's 2 T entries — the politics half of the bound pair. Deliberately last among T moves.

**Files:**
- Modify: `RESEARCH_LOG.md` (2 stubs), `theories/calibration_harvest/NOTES.md` (2 appended entries)

**Interfaces:**
- Consumes: the companion table's "politics + CORRECTION" pairing note. This task moves the T target; Task 10 (the very next commit) moves the CORRECTION's narrative adjacent to it, minimizing the window in which the correction's positional reference ("the entry two above") points at a stub.

- [ ] **Step 1: Move, in date order** (procedure of Task 4 steps 2–3):
  1. `2026-08-29 (cont.) — calibration_harvest's first population lands; weather is fairly priced; two defects fixed`
  2. `2026-08-29 (cont.) — politics: the horizon gradient is REAL, and nothing is bettable`

- [ ] **Step 2: The politics stub names its correction by date and heading** (pairing rule — never by position). Its stub's pointer paragraph must end with:

```markdown
Note: this entry is retracted by `## 2026-08-29 (CORRECTION) — the
politics headline was wrong; the pre-registered test failed` (below in
this log); the correction's narrative sits adjacent to this entry's in
the notebook.
```

- [ ] **Step 3: Run citation tests + full suite.** Expected: PASS.
- [ ] **Step 4: Commit, then proceed IMMEDIATELY to Task 10** (do not let peer log-appends or other work interleave between these two commits).

```bash
git add RESEARCH_LOG.md theories/calibration_harvest/NOTES.md
git commit -m "log: migrate calibration_harvest's 2 theory-local entries; politics stub names its correction by date (spec 6.8 step 4)"
```

### Task 10: M split — the politics CORRECTION (bound pair; first M split)

**Files:**
- Modify: `RESEARCH_LOG.md` (1 M-stub), `theories/calibration_harvest/NOTES.md` (correction narrative appended adjacent to the politics entry)
- Modify: `docs/superpowers/specs/2026-08-29-enforcing-surfaces-log-classification.md` (M-split record — see Step 4)

**Interfaces:**
- Consumes: Task 9's migrated politics entry (the correction lands directly after it, same file, date order); the pairing note ("A correction never separates from its target").
- Produces: the `## M-split record` section in the companion file, which Tasks 11–14 extend and Task 15 reconciles against.

- [ ] **Step 1: Read the full entry** `2026-08-29 (CORRECTION) — the politics headline was wrong; the pre-registered test failed` (~499 words). Identify the repo-level fact: a published headline was retracted after peer review — the pre-registered politics test failed; the retraction and what it teaches about multiple split points is the §1 evidence CLAUDE.md's mining discipline cites.

- [ ] **Step 2: Split.** Append the narrative verbatim to `theories/calibration_harvest/NOTES.md` under the migrated-heading format, **immediately after** the politics entry Task 9 appended (adjacent, date order — same file). The narrative's opening "Retracting the entry two above" is preserved verbatim (append-only notebook), but the migrated heading directly above it and the politics entry adjacent make the referent unambiguous; the M-stub carries the positional reference's dated resolution.

- [ ] **Step 3: Write the M-stub.** One paragraph: the retraction as a correction to a published result (the politics horizon-gradient headline was wrong; the pre-registered test failed; best-of-three split points reported as pre-registered — the multiple-comparisons instance the enforcing-surfaces spec §1 cites), naming the target by date and heading: `## 2026-08-29 (cont.) — politics: the horizon gradient is REAL, and nothing is bettable`. Then the pointer line to the notebook.

- [ ] **Step 4: Start the M-split record.** Append to the companion file:

```markdown
## M-split record (spec §6.8 step 6; extended one row per split commit)

| entry | fact extracted, and where it went | narrative destination |
|---|---|---|
| 2026-08-29 (CORRECTION) — the politics headline was wrong... | retraction-of-published-result, stated in the M-stub paragraph in the log itself | calibration_harvest NOTES.md, adjacent to its target |
```

- [ ] **Step 5: Run citation tests + full suite.** Expected: PASS — this is the commit the `RESEARCH_LOG.md:2242` positional reference was flagged for; the citation test plus the pairing handling above is its resolution.

- [ ] **Step 6: Commit**

```bash
git add RESEARCH_LOG.md theories/calibration_harvest/NOTES.md docs/superpowers/specs/2026-08-29-enforcing-surfaces-log-classification.md
git commit -m "log: split the politics CORRECTION — retraction stated in place, narrative adjacent to its target (spec 6.8 step 6)"
```

### Task 11: M splits — insider_judgment's 6 entries (one commit each)

**Files (per entry):**
- Modify: `RESEARCH_LOG.md` (M-stub), `theories/insider_bias/insider_judgment/NOTES.md` (narrative), companion file (M-split record row); possibly `python -m tools.cli rulings record` (DB, no file)

**Interfaces:**
- Consumes: shared M-stub format; the companion table's split notes for `all three theories current`.
- Produces: one commit per entry, M-split record rows.

Process the 6 entries **one at a time, each its own commit**, oldest first. For each: read the entry in full; extract the repo-level fact upward; move the narrative to the notebook; write the M-stub; append the M-split record row; run citation tests + full suite; commit `log: split M entry '<short heading>' (spec 6.8 step 6)`. Upward destinations decided by what the fact *is* (spec §6.8 step 6): a ruling → `python -m tools.cli rulings record "<binding text>" --authority <user|supervisor> --subject <subject> --log-entry "<exact heading>"`; a durable theory fact → `theory_facts` INSERT; narrative context → the M-stub's own paragraph (that IS the "one-paragraph replacement entry"). Expected extraction per entry — verify by reading, and record what was actually done:

1. `2026-08-26 — Formal multiplicity pass (user-prompted): Holm + event clustering` — fact: the Holm + event-clustering methodological precedent (already cited by CLAUDE.md's mining discipline); stub paragraph states it. Narrative → notebook.
2. `2026-08-26 — Contamination audit of the judged runs (user-prompted): no hints found; one timing wrinkle bounded` — fact: the contamination-probe precedent and its clean result; stub paragraph. Narrative → notebook.
3. `2026-08-26 — First live scan under the campaign rule: 8 endorsed NO bets; board-cache identity bug found and fixed on the way` — fact: the board-cache identity bug (repo defect, fixed); stub paragraph. Narrative → notebook.
4. `2026-08-29 — all three theories current; six endorsed bets settled (all won, one day); the bucket defect survives a 4x bigger sample` — per split note: fact up = the bucket defect; the other theories' status lines become dated pointers (in the stub paragraph); narrative → notebook.
5. `2026-08-29 (cont.) — the bucket layer was differencing against the wrong price; insider_judgment v4` — fact: the bucket-pricing defect and the v4 bump it forced (THEORY.md already records v4; stub paragraph points there). Narrative → notebook.
6. `2026-08-29 (session 3) — the version-bump gap, and what v4's clean gate revealed` — fact: the version-bump-outruns-settlements gap — the finding that produced spec §2 (peer's phase 6); stub paragraph names the spec section. Narrative → notebook.

- [ ] **Step 1: Entry 1 — split, record, test, commit** (procedure above)
- [ ] **Step 2: Entry 2 — split, record, test, commit**
- [ ] **Step 3: Entry 3 — split, record, test, commit**
- [ ] **Step 4: Entry 4 — split, record, test, commit** (apply the split note)
- [ ] **Step 5: Entry 5 — split, record, test, commit**
- [ ] **Step 6: Entry 6 — split, record, test, commit**

### Task 12: M splits — mention_family's 3 entries (one commit each)

**Files (per entry):** `RESEARCH_LOG.md`, `theories/insider_bias/mention_family/NOTES.md`, companion file; entry 3 also touches `theories/no_side_premium/NOTES.md` (dated pointer)

Same per-entry procedure as Task 11, oldest first:

1. `2026-08-24 — mention_family becomes a real, separate theory; insider_bias renamed insider_judgment and folded into a shared parent folder` — fact: the rename and shared-parent restructure (already CLAUDE.md architecture; stub paragraph states it happened here and when). Narrative → notebook.
2. `2026-08-25 — Kalshi archives settled markets after ~60 days; backward extension impossible; full-coverage rerun launched instead` — fact: the ~60-day archive constraint (already in CLAUDE.md data conventions; stub paragraph states it and that this entry established it). Narrative → notebook.
3. `2026-08-25 — Pattern-mining the fullcov rows: timing and price-level dead, but a side asymmetry survives every stress and feeds no-side-premium` — per split note: narrative → mention_family notebook; the surviving side asymmetry is no_side_premium's founding evidence, so append a dated pointer entry to `theories/no_side_premium/NOTES.md` (`## 2026-08-25 — pointer: founding evidence (migrated entry lives in mention_family's notebook)` + one sentence) alongside the stub-paragraph extraction.

- [ ] **Step 1: Entry 1 — split, record, test, commit**
- [ ] **Step 2: Entry 2 — split, record, test, commit**
- [ ] **Step 3: Entry 3 — split, record, test, commit** (with the no_side_premium pointer)

### Task 13: M splits — calibration_harvest's settlement-day clustering + no_side_premium's forward test (one commit each)

**Files (per entry):** `RESEARCH_LOG.md`, owner notebook, companion file

1. `2026-08-27 (evening) — settlement-day clustering confounds both live theories; calibration_harvest built; calendar-arb killed` (~905 words — the widest split; read its pairing note carefully). Fact up: the settlement-day-clustering confound as a methodological precedent (stub paragraph; if reading shows it was a ruling, record it via `rulings record` instead and say so in the M-split record). Narrative → `theories/calibration_harvest/NOTES.md` (this entry records the theory's founding). **The session-stop addendum (\"Addendum (session stop, 00:20Z)\") moves with the body it annotates — never separates.** The clustering evidence about the two live theories becomes dated pointers in the stub paragraph; calendar-arb's kill is already in the idea registry (verify with `python -m tools.cli ideas search calendar`; note the id in the M-split record).
2. `2026-08-26 (cont.) — no_side_premium forward test implemented and running; polymarket whale filter fixed` — fact: the polymarket whale-filter fix (repo tooling); stub paragraph. Narrative → `theories/no_side_premium/NOTES.md`.

- [ ] **Step 1: Entry 1 — split, record, test, commit** (addendum stays with narrative)
- [ ] **Step 2: Entry 2 — split, record, test, commit**

### Task 14: M splits — the 2 study-owned entries (one commit each)

**Files (per entry):** `RESEARCH_LOG.md`, the study's `STUDY.md`, companion file

Study-owned rows split the same way, with the study's own write-up as the notebook-equivalent (spec §6.6):

1. `2026-08-29 (session 3, item 4) — smile-smoothing killed at step one; tools/ladders.py survives it` — fact: `tools/ladders.py` survives its study (repo tooling fact); stub paragraph. Narrative → appended section in `studies/2026-08-29-smile-smoothing-ladder-flatness/STUDY.md` under the migrated-heading format.
2. `2026-08-29 (session 3, item 5) — series-bias-mining: not measured, and my own bar was the defect` — fact: the bar defect finding (a correction to this project's own methodology); stub paragraph. Narrative → appended section in `studies/2026-08-29-series-bias-mining/STUDY.md`.

- [ ] **Step 1: Entry 1 — split, record, test, commit**
- [ ] **Step 2: Entry 2 — split, record, test, commit**

### Task 15: Reconcile, the §6.7 CLAUDE.md rewrite, the migration log entry, peer notification (spec §6.8 steps 8–9)

**Files:**
- Modify: `RESEARCH_LOG.md` (one appended migration entry), `CLAUDE.md` (the §6.7 in-place rewrite), companion file (reconciliation numbers)

**Interfaces:**
- Consumes: every prior task's stubs and M-split record.
- Produces: the binding promotion bar; the signal the peer session's phase-B `go`-skill move waits on.

- [ ] **Step 1: Reconcile the counts.** Stub count must equal moved-row count: 22 T stubs + 14 M stubs = 36 (adjust if Task 1's addendum reclassified anything — use the pinned table's own totals). Count stubs:

```bash
grep -c 'migrated from RESEARCH_LOG.md' RESEARCH_LOG.md
```

(every stub's pointer names the migrated heading, so this counts stubs; cross-check against the companion table row count). Also verify: `python -m tools.cli state` renders; full suite green.

- [ ] **Step 2: Record the reconciliation** in the companion file under the M-split record: total stubs, total words moved per class, any row where execution deviated from the table and why.

- [ ] **Step 3: The §6.7 CLAUDE.md rewrite.** In CLAUDE.md's "What lives in a theory, and what gets elevated" section, replace exactly this text:

```
`RESEARCH_LOG.md` stays cross-theory: when a session's work sits inside one
theory, the log entry is a pointer to that theory's `NOTES.md` entry, not a
copy of it.
```

with (spec §6.7's ruled text, verbatim):

```
`RESEARCH_LOG.md` stays cross-theory: a log entry is earned by a fact that
changes how a session that never touched this theory would act — a mechanism,
a ruling, a precedent, a constraint, a breakthrough, a correction. A result inside one theory
is a headline and a pointer into its `NOTES.md`, never a copy. This was
forward-only from 2026-08-25 and produced 5,838 words of copies anyway,
because the log was what got read; it binds now because `state` is.
```

(Wrap to the file's prevailing line width; wording verbatim. If the sentence text differs on disk from the block above, STOP and re-read the current section — the peer session's phase B must not have moved it yet; coordinate before editing.)

- [ ] **Step 4: Append the migration log entry** to RESEARCH_LOG.md — it must itself pass the §6.5 bar (it does: repo-level change). One entry: heading `## 2026-08-29 — RESEARCH_LOG migration complete: the canon left the journal (spec 6.8)`, body carrying the reconciliation numbers (entries moved per class, words, stub count, commits), the statement that the promotion bar binds from this commit forward, and the pointer to the companion file.

- [ ] **Step 5: Run the full suite one final time.** Expected: green.

- [ ] **Step 6: Commit**

```bash
git add RESEARCH_LOG.md CLAUDE.md docs/superpowers/specs/2026-08-29-enforcing-surfaces-log-classification.md
git commit -m "log: migration reconciled — 36 stubs, bar binds; CLAUDE.md 6.7 rewrite in place (spec 6.8 steps 8-9)"
```

- [ ] **Step 7: Notify the peer session** (SendMessage to llm-market-identifier-21): §6.7 has landed at commit `<sha>` — their phase-B `go`-skill rule-32 move is unblocked and must move the NEW bar text, not the old sentence. Also report phases 3–5 complete, so phase C (theory CLAUDE.md seeds, sourced from the now-migrated notebooks) is unblocked for whichever session is free.
