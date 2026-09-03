---
title: parse_deadline now has two theories calling it, which is the elevation trigger -- and the second caller is a sibling import the suite rejects
lane: maintenance
created: 2026-09-02
created_by: fleet-w3-g2
author_lane: maintenance
author_context: Found by tests/test_conventions.py::test_no_theory_imports_a_sibling_theory going red mid-session; the offending file is another session's UNTRACKED work-in-progress, so I did not touch it.
status: done
closed: 2026-09-03
resolution: DONE. parse_deadline elevated to tools/timeutil.py under the caller-count rule; local copy in theories/deadline_drift/collect_settled.py deleted and re-exported (noqa: F401), matching how days_until was elevated. no_side_premium/exposure_measure.py repointed at tools.timeutil, which clears tests/test_conventions.py::test_no_theory_imports_a_sibling_theory -- red since 2026-09-01. Migration verified behaviour-preserving by differential test over 2,598 inputs (0 mismatches, including 141 that raise identically), and regex/month-table asserted byte-identical before the local copy was removed. Tests added to tests/test_timeutil.py, including the same re-export-identity assertion days_until carries. The second half of this ticket (THEORY.md data/mine_cells_result.txt) is also fixed -- see theories/no_side_premium/tickets. Suite 1394p/2f -> 1405p/0f.
---
DO NOT COMMIT theories/no_side_premium/exposure_measure.py AS IT STANDS -- it fails the suite.

WHAT IS BROKEN. theories/no_side_premium/exposure_measure.py line 26 does:

    from theories.deadline_drift.collect_settled import parse_deadline

That is a theory importing a sibling theory's folder, which CLAUDE.md forbids ('The expert's contract: a theory folder contains everything its expert needs to run -- no imports from a sibling theory's folder') and which tests/test_conventions.py::test_no_theory_imports_a_sibling_theory fails on. Suite went 1410 passed / 1 failed the moment that file appeared.

STATE WHEN FOUND. The file was UNTRACKED (git status '??') -- live, uncommitted work by a peer session, landed between two suite runs 20 minutes apart. I did not edit it: clobbering another session's in-flight file in a shared tree is worse than the violation. That is the only reason this is a ticket and not a fix.

WHY THE FIX IS EASY AND ALREADY EARNED. parse_deadline (theories/deadline_drift/collect_settled.py:57) is eight lines: regex a 'by <Month> <D>, <YYYY>' deadline out of rules text and return it as a UTC ISO stamp. It is pure, has no deadline_drift state, and now has TWO real callers in two different theories -- which is exactly CLAUDE.md's elevation trigger ('a helper moves to tools/ once it has more than one real caller'). This is the rule firing as designed, not an exception to it.

WHAT TO DO.
  1. Move parse_deadline (and its _DEADLINE / _MONI module constants) to tools/ -- tools/timeutil.py is the natural home, it already holds shared time helpers.
  2. Repoint theories/deadline_drift/collect_settled.py at the tools/ version and DELETE the local copy (elevation is a migration -- one implementation, per CLAUDE.md, not a copy).
  3. Repoint exposure_measure.py's import.
  4. Add a test for parse_deadline in tests/test_timeutil.py; deadline_drift's own NOTES.md 2026-08-29 correction explains why the rules-stated deadline rather than close_time is the sound anchor, and that reasoning should survive the move.

COORDINATE FIRST. Step 3 touches a file another session may still be writing. Check whether no_side_premium's exposure work has landed before editing it, or do steps 1-2 (which are safe and self-contained) and leave step 3 to whoever finishes that work.

---

## Second, unrelated red test from the same in-flight work (added same session)

`tests/test_conventions.py::test_every_repo_path_named_in_docs_resolves`
also went red while this was being written, from the same peer's
uncommitted `no_side_premium` work:

```
THEORY.md: `data/mine_cells_result.txt`
```

**Not the same bug, and much smaller.** `theories/no_side_premium/THEORY.md`
names `data/mine_cells_result.txt` relative to its own folder, but the test
resolves every documented path from the **repo root**, so it looks for
`<root>/data/mine_cells_result.txt`. The real file exists at
`theories/no_side_premium/data/mine_cells_result.txt` — and that directory
is gitignored (`.gitignore:25`), so on a fresh clone it would not exist
under any spelling.

**Fix is one of two lines, and belongs to whoever owns that file:** write
the full repo-relative path in `THEORY.md`, or add it to
`_ALLOWED_MISSING` / `_DELIBERATELY_ABSENT` in `tests/test_conventions.py`
as the runtime artifact it is (the second is probably right, since the file
is a generated result that is deliberately not committed).

Recorded here rather than as its own ticket because the action is the same:
**`no_side_premium`'s in-flight work leaves the suite red in two ways and
should not be committed until both are resolved.** Suite as of
2026-09-01T23:5xZ: **1,422 passed, 2 failed**, and both failures name only
that theory's uncommitted files.
