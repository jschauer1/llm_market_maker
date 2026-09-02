# calibration_harvest — retired 2026-09-01

**Status:** retired · **Retired:** 2026-09-01 · **Versions:** v1–v4
**Code at:** `d3ef5c6cfb571979586da9c60ad87aba174ba447`

Retired on the user's explicit delegation of 2026-09-01 ("if you think it
should be retired do it"), given after they were shown the full proposal
**including** the Sports counter-argument. What follows distils the
retirement rationale recorded on the theory's registry row; it does not
revise it. The rationale itself is the authority and is still readable in
full:

    python -c "from tools import db, theories; c=db.connect(); print(theories.get(c,'calibration_harvest')['retirement_rationale'])"

## Why it was retired

**The pre-registered kill criterion is met.** `THEORY.md` fixed it before
the data existed: *"No cell clears fees out-of-sample at n ≥ 30 AND
n_days ≥ 8."* The third population came back complete
(`backtest-2026-09-01-calharvest-econfin`, 1,181/1,181 series, 2,666 obs,
five mapped domains, walked **after** the grid was drawn): 27 cells clear
both floors, **zero** clear fees, net −6.57 to −25.29.

**The test is fair.** Until its last session the theory had a real excuse:
`cell_edge` was bounded on `n_days` with the design effect pinned at
rho = 1, and at that value the rule was *arithmetically incapable* of
firing — a theory that cannot express an edge and one that has none produce
identical empty reports. v4 fixed that on a structural argument (measured
rho median 0.027 against the assumed 1.0), demonstrably without changing
anything bettable, and only then did the fresh population come back empty.

**Sports — the one open counter-argument — was checked, and points the same
way.** The true domain of all 7,000 settled live rows was re-derived
read-only: 6,102 (87%) are Sports, reading −6.69 gross over 4 settlement
days. Wrong sign. To rescue the theory that sign would have to flip *and*
reach +3.5 to clear the v4 frontier; nothing suggests it, and the mechanism
gives no reason to expect it — lottery appetite and capital-lockup aversion
are domain-agnostic, and sports is Kalshi's most liquid ESPN-settled
category, so the prior is *more* efficient pricing. The theory's −2.87
headline was an unlabelled sports number; labelled, it did not improve.

**And the sports walk is not affordable.** `collect size` hit a 429 after
21 *Sports* series, having already spent 9,270 candlestick fetches (8,911
from `KXMLBKS` alone). Sports is an order of magnitude dearer than any
population walked, and rate-limited in practice rather than only in theory.

**The full record:** six domains, ~7,500 collected rows, three complete
populations, 47 cells past both floors, **zero positive net edges.** The
only axis that ever showed structure (horizon) reverses sign out of sample
— `1mo+` +9.38 on weather+politics, −5.09 on econfin — having already been
retracted once on 2026-08-29 as a pre-registration failure. 0 of 27 econfin
cells survives Holm. The liquidity split shows no ordering in either
direction.

## What is NOT claimed

**Not proof of absence.** Sports and Entertainment are unwalked at tier A
and 12 of 20 domain-band cells are underpowered. A future session with days
of budget could walk them; this record says so, so a revival is a matter of
evidence rather than archaeology.

## What survives

`cells.effective_n` and the design-effect argument (a conservative default
is a modelling assumption, and an unmeasured one can silently disable the
thing it protects); the `collect size` cost probe; the liquidity fields the
collector now persists; and three complete tier-A calibration populations
any future theory can read for free.

## Retrieving what was deleted

Everything deleted at retirement is in git at the rev named at the top of
this file. That rev is the only thing that makes it findable — a retired
theory's code is not lost, but nothing else in the tree points at it:

    git show d3ef5c6cfb571979586da9c60ad87aba174ba447:theories/calibration_harvest/screen.py
    git show d3ef5c6cfb571979586da9c60ad87aba174ba447:theories/calibration_harvest/backtests/econfin.json
    git show d3ef5c6cfb571979586da9c60ad87aba174ba447:tests/theories/test_calibration_harvest_cells.py

    # everything the folder held, at that rev
    git ls-tree -r --name-only d3ef5c6cfb571979586da9c60ad87aba174ba447 theories/calibration_harvest

**Deleted at retirement:** 9 modules (`cells.py`, `collect.py`,
`forward_cells.py`, `gradient.py`, `read_cells.py`, `regress_variants.py`,
`screen.py`, `theory.py`, `verify_gradient_review.py`) plus `__init__.py`;
`RUNBOOK.md`; 5 backtest payloads (504K of JSON —
`weather.json`, `politics.json`, `econfin.json`,
`econfin.json.pre-volume-bak`, `size.json`); 3 completed tickets under
`tickets/completed/`; and **76 tests** across
`tests/theories/test_calibration_harvest_{cells,collect,forward_cells,screen}.py`.
The findings those payloads carried are in `RESULTS.md`.

**`THEORY.md` and `NOTES.md` still name modules, payloads and runbook
sections that no longer exist in this folder.** That is deliberate: they are
the record of what the theory claimed and how it decided, and **no reference
to a deleted module or payload was edited into agreement with the
deletion.** The only edits either file took at retirement were repointing the
gradient-review study to its new path (1 line in `THEORY.md`, 2 in
`NOTES.md`). Every path they name resolves at the rev above.

`tests/test_timeutil.py` kept its coverage but lost one of its three
re-export fixtures with this deletion; the comment there says so.

## What is still live elsewhere

- The registry row (`theories`.`calibration_harvest`, status `retired`,
  version 4) — including the full retirement rationale.
- Every ledger row, score and backtest run this theory recorded. Retirement
  deletes code, never evidence.
- The three tier-A calibration populations it collected, in the database.
- `studies/answer/2026-08-29-calibration-harvest-gradient-review/` — the
  peer review of the politics gradient, which retired with the theory.
