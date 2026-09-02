---
title: THEORY.md cites theory-relative data paths that the conventions test resolves from repo root
lane: theory
theory: no_side_premium
created: 2026-09-02
created_by: sdd-study-pipeline
author_lane: maintenance
author_focus: study ticket pipeline migration
status: open
---
`tests/test_conventions.py::test_every_repo_path_named_in_docs_resolves` fails on two spans in no_side_premium/THEORY.md: `data/preplatform_seen.json` and `data/mine_cells_result.txt`. Both files exist, at theories/no_side_premium/data/, but the test resolves backticked path spans from the REPO ROOT, so a theory-relative path never resolves.

Also failing alongside it: test_no_theory_imports_a_sibling_theory.

Both were already red before the study-ticket-pipeline branch was cut (confirmed by stashing against a clean baseline), and both come from the exposure/mine_cells work in flight. Fix is either to write the spans repo-relative in THEORY.md, or to stop backticking them if they are meant as folder-relative prose.

Filed from the study-pipeline migration lane, which must not touch another theory's docs.

---

`tests/test_conventions.py::test_every_repo_path_named_in_docs_resolves` fails on
two backticked spans in `theories/no_side_premium/THEORY.md`:
`data/preplatform_seen.json` and `data/mine_cells_result.txt`. Both files exist,
at `theories/no_side_premium/data/`, but the test resolves backticked path spans
from the REPO ROOT, so a theory-relative path can never resolve.

Fix: write both spans repo-relative (`theories/no_side_premium/data/...`), or stop
backticking them if they are meant as folder-relative prose. `_PATH_LIKE` in the
test only matches spans containing a `/`, so unbacktciked prose is not scanned.

**Scope narrowed 2026-09-02.** This ticket originally also covered
`test_no_theory_imports_a_sibling_theory`, which fails because
`exposure_measure.py` imports `theories.deadline_drift.collect_settled`. That
half is already specified in
`tickets/maintenance/open/2026-09-02-parse-deadline-earned-elevation.md`
(move `parse_deadline` to `tools/`, repoint both callers). Narrowed at the
suggestion of session `llm-market-identifier-6f` so neither failure ends up
orphaned between two tickets that each assume the other has it.

Both failures predate the `study-ticket-pipeline` branch and are the reason that
branch treats "2 failures" rather than "0" as its green baseline.
