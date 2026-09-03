---
title: mention_family is retired in the DB but still lives in the live tree
lane: maintenance
created: 2026-09-02
created_by: unknown
author_lane: maintenance
author_focus: final fix wave, 2026-09-02 theory-retirement branch
author_context: Adding the converse conventions guard for Important 1 of the final review; the new test fails on mention_family, so it needed an exemption and this ticket.
status: done
closed: 2026-09-03
resolution: Migrated 2026-09-02 on branch retire-mention-family. mention_family now lives at theories/retired/mention_family/ holding exactly RETIRED.md, THEORY.md, NOTES.md, RESULTS.md; registry path repointed; code deleted at rev 450db428ec0e7542852fae6484ab8370aaeddfad. All three decision points this ticket said had to be decided rather than assumed: (1) nothing in theories/insider_bias/ or insider_judgment imported the sibling package -- families.py stays put because backfill_history.py and insider_judgment/backtest_fullcov.py call is_mention_family; (2) no live caller imports the module, only its concept; (3) the studies/ subtree went OWNERLESS to tickets/study/investigation/2026-08-29-series-bias-mining (368MB intact) rather than retiring with its theory, and its three tickets became maintenance tickets. _UNMIGRATED_RETIREMENTS is now empty, as its own self-checking design required.
---
`mention_family` has status `retired` in the registry (retired 2026-08-26,
rationale on its row) but still lives at `theories/insider_bias/mention_family`
with all of its code: `theory.py`, `backtest.py`, `mention_bucket.py`,
`__init__.py`, `RUNBOOK.md`, a `studies/` subtree and open tickets.
`registry.discover()` still imports it as a live theory.

That is exactly the state the 2026-09-01 retirement convention exists to end,
and it predates it by five days -- `calibration_harvest` was migrated on
2026-09-02, `mention_family` never was.

Found while adding `tests/test_conventions.py::test_every_retired_theory_lives_
under_theories_retired` (the converse guard: a `retired` row must have a path
under `theories/retired/`). The new test would fail on `mention_family`, so it
carries an explicit, self-checking exemption -- `_UNMIGRATED_RETIREMENTS` --
that goes stale (and fails the suite) the moment the migration happens. That
set is the debt made visible; this ticket is the debt itself.

**The migration is not a copy of calibration_harvest's.** Three differences
have to be decided rather than assumed:

1. It sits inside the shared family parent `theories/insider_bias/`, next to
   `insider_judgment`. Moving it to `theories/retired/mention_family/` takes
   it out of that parent -- check nothing in `theories/insider_bias/` (README,
   `screen.py`, `replay.py`, `families.py`) or in `insider_judgment` depends on
   the sibling package existing.
2. `no_side_premium` came off it, and `tools/` code has carried
   mention-family exclusions (`_is_mention_family` and the screen's matching
   exclusion). Those are live callers of a dead theory's *concept*, not its
   package -- confirm none import the module.
3. It owns open tickets under `theories/insider_bias/mention_family/tickets/`
   -- including a series-bias sweep. Retirement does not silently delete live
   work; decide where each goes first. Note the related open maintenance
   ticket `2026-09-02-filing-a-ticket-against-a-retired-theory.md`: `tickets`
   is not in `_RETIRED_ALLOWED`, so a retired theory cannot carry a ticket
   folder at all.

The migration must produce a `RETIRED.md` naming the git rev the deleted code
lived at, and a `RESULTS.md` distilling the full-coverage backtest
(`backtest-2026-08-25-mention-fullcov`, n=3,441) -- the payloads themselves do
not survive. CLAUDE.md's "Theory lifecycle and versioning" section now carries
the rule.

Not urgent: the theory records nothing and nobody runs it. It must be resolved
before anyone trusts `theories/` to mean "the live theories".
