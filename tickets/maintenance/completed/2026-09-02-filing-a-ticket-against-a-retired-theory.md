---
title: Filing a ticket against a retired theory creates a file that fails the conventions test
lane: maintenance
created: 2026-09-02
created_by: sdd-retirement
author_lane: maintenance
author_focus: phase 2 theory retirement
status: done
closed: 2026-09-03
resolution: DONE, as the ticket specified: refuse at filing, do NOT widen the allowlist. ticket_dir() gains an optional theory_status and raises for 'retired', with a message naming the route that IS still open (cli tickets new --lane new-theory, how no_side_premium came off mention_family). cli tickets new passes the status from the registry lookup it already does for path, so the refusal fires end-to-end -- verified against the real calibration_harvest row. Keyed to the REGISTRY STATUS, never a path prefix, so insider_judgment under its family parent is unaffected; a parametrised control asserts all five live statuses still file normally, including under_review and paused. Covers the study lane too, since studies retire with their theory. Tests: 5 in tests/test_tickets.py (rule) + 2 in tests/test_cli.py (wiring, which is the line a refactor drops). NOTE FOR FUTURE CLI TESTS: cli.main resolves ticket paths from db.REPO_ROOT, a module constant, NOT the cwd -- monkeypatch.chdir does not contain it, and a tickets-new test without redirection writes a real ticket into the real repo. That happened here; the stray theories/t1/ was removed and a documented repo_root fixture now prevents it.
---
`tickets.ticket_dir` reads the registry `path` column, which now resolves to `theories/retired/<slug>` for a retired theory. So `cli tickets new --lane theory --theory calibration_harvest` would create `theories/retired/calibration_harvest/tickets/open/<file>.md`.

But `tickets` is not in `_RETIRED_ALLOWED` in `tests/test_conventions.py::test_a_retired_theory_holds_only_its_record`, and is not covered by the `studies/` exemption. The ticket files successfully, then the suite goes red.

Flagged independently by the Task 3 implementer and its reviewer during the 2026-09-02 retirement migration.

**The fix is to refuse at filing, not to widen the allowlist.** You should not be able to queue work against a dead theory: `ticket_dir` should raise for a theory whose registry status is `retired`, with a message saying that a retired theory's remaining work is a *new theory proposal* (`cli tickets new --lane new-theory`), which is how `no_side_premium` came off `mention_family`. Widening the allowlist would instead let a retired theory quietly reacquire a live backlog, which is the thing retirement exists to end.

This is lifecycle work and belongs with the new-theory state machine (Phase 3 of the data-and-ticket-lifecycle spec). It is not urgent — nothing files tickets against calibration_harvest today — but it must be resolved before a second theory is retired.
