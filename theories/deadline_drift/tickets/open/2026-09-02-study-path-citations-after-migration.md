---
title: Two study-path citations still point at the dissolved studies/ tree
lane: theory
theory: deadline_drift
created: 2026-09-02
created_by: sdd-study-ticket-pipeline-task-6
status: open
---
The 2026-09-01 study migration dissolved the top-level `studies/` tree: a
study is now a ticket directory, either inside the theory that owns it or
in `tickets/study/<state>/`. Every citation in the repo was repointed
except two in this theory's folder, which were left alone because a
session was live in them at the time and had only cleared `hazard.py` and
`screen.py` for editing.

Both are prose citations, not code paths -- nothing breaks at runtime:

- `theories/deadline_drift/THEORY.md` cites
  `studies/2026-08-29-structural-gate-payload-version/`, which is now
  `docs/2026-08-29-structural-gate-payload-version/`. That study was never
  a study -- it rules on a repo rule and mentions no theory -- so the
  migration filed it under `docs/`.
- `theories/deadline_drift/NOTES.md` cites
  `studies/2026-08-29-deadline-drift-classifier-audit/`, now
  `theories/deadline_drift/studies/answer/2026-08-29-deadline-drift-classifier-audit/`
  -- this theory owns it, so it moved into this folder.

The THEORY.md one is load-bearing for a test:
`tests/test_conventions.py::test_every_repo_path_named_in_docs_resolves`
scans `theories/*/THEORY.md` and reports it as an unresolvable path. That
test already fails on three unrelated `data/*.json` citations from this
theory's own in-flight work, so fixing this one alone will not turn it
green -- fix all four together.

NOTES.md is a lab notebook and append-only in spirit; correcting a path
inside an existing entry is a judgment call for whoever owns this theory.
The THEORY.md fix is unambiguous.
