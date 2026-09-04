---
title: test_conventions.py scan tests should memoize their repo walk
lane: maintenance
created: 2026-09-03
created_by: unknown
status: done
closed: 2026-09-04
resolution: Done in 73a0124, once the concurrent session released the file. Four lru_cache memos (file walk, per-basename glob, per-file text and lines) with every scan's selection logic untouched. test_conventions.py 3.63s -> 1.06s; the citation test 2.69s -> 0.35s.
---
The largest remaining item in the test suite: 3.54s, of which 2.71s is
`test_every_dated_cross_citation_still_resolves`. Each scan test
independently re-walks the repo and re-reads the same files, and
`_dir_bytes()` stat()s a 3.5 GB tree (2.9s for a full walk) -- saved today
only by its glob being narrow, which will stop being true as study data
grows.

Deferred from the 2026-09-02 test-speed refactor for one reason only: a
concurrent session held this file modified for the entire session, and
editing it would have clobbered their work.

Apply exactly what `tests/test_db_discipline.py` got in commit 975a074:
memoize the read and the AST parse per session, and **do not change which
files are selected**. A repo-guard test that quietly scans a different set
is worse than a slow one. A session-scoped `source_corpus` fixture already
exists in `tests/conftest.py` if a shared corpus is wanted, but selection
must still be decided by this file's own logic.

Spec: docs/superpowers/specs/2026-09-02-test-suite-speed-design.md (section 5)
