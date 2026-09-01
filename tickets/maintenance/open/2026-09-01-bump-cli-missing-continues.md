---
title: theories bump CLI still defaults to breaking and cannot record continues
lane: maintenance
created: 2026-09-01
created_by: unknown
author_lane: theory
author_focus: insider_judgment
author_context: Hit while bumping insider_judgment to v5; had to drop to the Python API because the CLI cannot express the default kind.
status: open
---
`python -m tools.cli theories bump` still says:

    --kind {breaking,carry}   breaking (default) resets the track record

That predates the 2026-08-31 ruling. `theories.bump_version` in Python has had `kind='continues'` as its default since, and 'continues' is not even an accepted CLI choice -- so the CLI cannot record the kind that is supposed to be the default, and its help text advertises the old default as current.

The consequence is the exact failure the ruling was made to stop. A session that bumps through the CLI either severs the theory's evidence by accident or picks `carry` and gets refused for lack of an equivalence proof. Three of four running theories reached n=0 that way before the ruling; the CLI is still pointed at that outcome.

Fix: add `continues` to the choices, make it the default, and reword the help to match tools/theories.py::bump_version's docstring (continues = the procedure changed and the evidence stands; carry = provably could not alter a recorded decision, needs a proof that only exists from Python; breaking = an explicit sever whose justification must say what makes the old evidence inapplicable).

Worth a test that pins the CLI's default kind to the Python API's default, so the two cannot drift apart again silently.
