---
title: The study lane shipped unclaimable; the lane migration's guard was a hardcoded sentinel
lane: maintenance
created: 2026-09-01
created_by: fleet-w3-g1
author_lane: study
author_focus: 2026-08-29-early-close-exposure-existing-backtests
author_context: Hit at lane-claim time: the first thing this session tried to do was claim the study lane, and it raised a bare sqlite3.IntegrityError.
status: open
---
FIXED IN THIS SESSION -- filed so the finding survives, and because the generalizable half is a repo-wide pattern worth someone re-checking, not just this one table.

WHAT WAS BROKEN. `python -m tools.cli lane claim --lane study` died with an unhandled `sqlite3.IntegrityError: CHECK constraint failed: lane IN ('floor','theory','new-theory','find-theories','maintenance')`. The study lane was added to `tools.lanes.LANES`, to go's lane table, and given a whole skill (`go-study`), `tools/studies.py`, `studies/README.md` and `tests/test_studies.py` -- but `db/schema.sql` was never widened. So the lane was unclaimable in EVERY database, freshly created ones included; this was not a stale-DB problem.

THE GENERALIZABLE HALF, which is the reason to read this. `_migrate_lane_claims` existed and would have handled it, but its guard was `if row is None or \"find-theories\" in (row[0] or \"\"): return` -- a hardcoded sentinel naming the lane the migration was written for. That guard is self-disabling: it stops firing permanently the moment that one lane lands, so every lane added afterwards silently fails to migrate. A migration keyed to a sentinel value only ever runs once, which is exactly what a migration must not be.

WHAT WAS DONE.
  1. `db/schema.sql`: `lane_claims` CHECK now includes 'study'.
  2. `tools/db.py`: added `_lane_check_values(ddl)` and rewrote the guard to diff the lane set accepted by the live DDL against the one in schema.sql, migrating whenever the live table is missing any. Each future lane now migrates itself with no code change.
  3. `tests/test_lanes.py`: `test_every_lane_go_dispatches_to_is_claimable` iterates `lanes.LANES` rather than naming lanes one at a time -- a per-lane test cannot catch this class of bug, because the missing lane is by definition the one nobody wrote a test for. Plus `test_a_database_predating_a_lane_is_migrated_rather_than_rejected`, which builds the narrow legacy DDL, migrates, claims 'study', and checks the legacy row survived the rebuild.
  4. Live `db/market_edge.db` migrated; the two open peer claims (fleet-w1-g1 theory/deadline_drift, fleet-w2-g1 maintenance) were preserved.

WHAT IS STILL WORTH DOING, and why this ticket is filed rather than closed silently.
  a. SWEEP THE OTHER MIGRATIONS FOR THE SAME SHAPE. `tools/db.py` carries several `_migrate_*` functions in this style. Any whose early-return tests for a specific literal value rather than comparing against schema.sql has the same self-disabling defect and will bite the next time that vocabulary is widened. `_migrate_theories` (the status CHECK) is the one to check first: theory `status` is load-bearing vocabulary under CLAUDE.md, and widening it is a plausible future change.
  b. A CONVENTION TEST would be stronger than fixing them one at a time: for every table whose schema.sql DDL carries a `CHECK (<col> IN (...))`, assert the live/migrated DB accepts every listed value. That generalizes the lanes test above to every enumerated vocabulary in the schema at once, which is precisely the set CLAUDE.md calls an interface.
  c. A BARE IntegrityError IS A BAD ERROR. `lanes.claim` validates the lane against `LANES` in Python and then lets SQLite raise if the DB disagrees. Those two lists disagreeing is a repo defect, not user error, so the traceback should say so -- 'lane X is in LANES but the database rejects it; run db.init_db to migrate' -- instead of a raw CHECK-constraint dump that reads like a bad argument.
