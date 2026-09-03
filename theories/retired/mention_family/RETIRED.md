# mention_family — retired 2026-08-27, migrated 2026-09-02

**Status:** retired · **Retired:** 2026-08-27 · **Migrated:** 2026-09-02 ·
**Versions:** v1 (the only one)
**Code at:** `450db428ec0e7542852fae6484ab8370aaeddfad`

Retired by the user on 2026-08-27, on a standing retirement proposal
filed 2026-08-25 by the session that ran the full-coverage backtest. The
migration into this folder happened **six days later**: the retired-theory
folder convention did not exist until 2026-09-01, `calibration_harvest`
was migrated to it on 2026-09-02, and this theory was carried until then
by an explicit, self-checking exemption
(`tests/test_conventions.py::_UNMIGRATED_RETIREMENTS`) whose whole design
was to fail the suite the moment somebody did the migration. Deleting
that one-slug set is part of this change.

What follows distils the retirement rationale recorded on the theory's
registry row; it does not revise it. The rationale itself is the
authority and is still readable in full:

    python -c "from tools import db, theories; c=db.connect(); print(theories.get(c,'mention_family')['retirement_rationale'])"

## Why it was retired

**The full-coverage rerun measured the edge out of existence.**
`backtest-2026-08-25-mention-fullcov` (tier A) replayed *every*
mention-family survivor in the API-reachable window — 11,084 survivors
across 379 series, **3,441 screen hits, all settled** — against the
**n=116** systematic sample the price bins had been fit on. Win rate
**0.797** against mean price **0.802**: `calibration_edge` **−0.49**
gross, **−1.53** net, `roi_all` **−1.9%**. Fresh rows only, excluding the
original 116: **−1.78** net. `RESULTS.md` beside this file carries the
per-bin and per-sub-family tables.

**The diagnosis ruled out every alternative explanation** the
`score-theories` checklist names, and did so before the proposal was
filed: not small n (3,441), not a fee artifact (gross is negative too),
not inversion (no side or bin is significantly positive), not one good
slice (per-series means at n≤25 scatter +22 to −45, mean-zero, and no
slice was pre-registered), not version mixing (v1 throughout), not regime
change (the same window as the bootstrap, by construction).

**The 85plus bin is the clearest single fact.** Its bootstrap was 41/41,
zero losses, and the theory's own `THEORY.md` had already flagged that
number as one to distrust. At full coverage it lands at n=1,190, win rate
**0.913** against price **0.909** — *perfectly calibrated*. The 41/41 was
sampling luck in a ~3% sample, exactly as the morning's skeptical audit
had suspected.

**The first live out-of-sample settlement agreed.**
`KXTRUMPMENTION-26AUG24B-IRAN`, no @0.89, resolved yes — lost.

## The method lesson, which outlived the theory

A ~3% systematic sample (116 rows) produced **+5.48pts net with an
all-positive bin table** on the same window where full coverage measures
**−1.53**. Small backtest samples of a screen's own selection are not
weak evidence of the sample's claim — **they can be confidently wrong.**
Prefer full coverage of a scoped population wherever the fetch allows,
and treat any sampled result as unconfirmed until it survives the full
walk.

## What is NOT claimed

**Not that the population is uninteresting.** The retirement rationale
names the residual open question itself: whether any single recurring
series is persistently mispriced. That is a *new, pre-registered,
per-series* question and it was never this theory's — this theory's
both-sides price-bin procedure is what was measured dead.

## What survives, and where it went

- **`no_side_premium` came off this theory.** The same-day pattern-mining
  pass over the 3,441 dead rows found NO favorites at ask ≥0.90 reading
  **+2.25pts net** (n=450, 213 events) while YES favorites are overpriced
  in every band. It was recorded as a hypothesis to pre-register, not as
  a revival, and became its own theory. Note what that carried: ledger
  rows are keyed to `theory_id`, so `no_side_premium` started at n=0 and
  **cites** this measurement as founding evidence rather than inheriting
  it.
- **`theories/insider_bias/families.py` stays where it is.**
  `is_mention_family` is not this theory's code any more and was not
  deleted with it: `theories/insider_bias/backfill_history.py` and
  `insider_judgment/backtest_fullcov.py` both call it — the latter to
  define its *complement* population. A ticker family on the board does
  not stop existing when a theory built on it does. The same goes for the
  `mention_family` **negative control** in the series-bias-mining study.
- **The series-bias-mining study did not retire with the theory.** It was
  still in `investigation` and other studies read its 368MB corpus, so it
  moved out to the root study lane and is now **ownerless** at
  `tickets/study/investigation/2026-08-29-series-bias-mining/`. Retiring
  a theory must not retire a live measurement other work depends on. Its
  three tickets moved to `tickets/maintenance/{open,completed}/` for the
  same reason.

## Retrieving what was deleted

Everything deleted at retirement is in git at the rev named at the top of
this file. That rev is the only thing that makes it findable — a retired
theory's code is not lost, but nothing else in the tree points at it:

    git show 450db428ec0e7542852fae6484ab8370aaeddfad:theories/insider_bias/mention_family/mention_bucket.py
    git show 450db428ec0e7542852fae6484ab8370aaeddfad:tests/characterization/goldens/mention_rank_wide.json

    # everything the folder held, at that rev
    git ls-tree -r --name-only 450db428ec0e7542852fae6484ab8370aaeddfad theories/insider_bias/mention_family

**Deleted at retirement:** 4 modules — `mention_bucket.py` (322 lines,
the whole decision procedure: `PRICE_BINS`, `bucket_for_price`,
`find_candidates`, `rank`, `rank_preview`, `measured_rate`),
`backtest.py` (304 lines, the family-scoped driver that established
Kalshi's ~60-day archival floor), `theory.py` (49) and `__init__.py`;
`RUNBOOK.md`; and **29 tests** across
`tests/theories/test_mention_family_{mention_bucket,theory}.py`.

## The characterization goldens: why six were deleted rather than kept

This is the one judgment call in the migration, and it is recorded here
because it is the part a future reader is most likely to want to argue
with.

`tests/characterization/test_goldens.py` imported `mention_bucket`, and
**6 of its 13 goldens were `mention_*`** — `mention_find_candidates`,
`mention_find_candidates_wide`, `mention_rank`, `mention_rank_wide`,
`mention_rank_preview_wide`, `mention_rank_wide_edge_corrected`, 2.5MB in
total. Keeping `mention_bucket.py` alive somewhere so those stayed green
was considered and **rejected**:

- **There is no honest home for it.** `theories/insider_bias/README.md`
  sets the bar for the shared family parent at *"both siblings actually
  depend on it"*. `insider_judgment` does not use `mention_bucket`.
  Parking a dead theory's module in the family parent to keep a test
  passing would break the exact rule that folder exists to enforce.
- **The goldens' own docstring says what they are**: the pass condition
  for the theory-layer OOP migration. That migration is complete, so a
  golden over a deleted theory locks nothing that can still move.
- **A characterization test over code nobody can call is not coverage.**
  It asserts that a deleted module still behaves as it did, which is true
  by construction.

**The 7 goldens covering live code are untouched and still pass** —
`screen`, `dedupe_by_event`, `normalize`, `gate_partition`,
`gate_partition_v3`, `run_mechanical_stages_v3`, `blind_payload_v3`.

**And one thing was deliberately NOT cleaned up.** `build_fixture.py`
used to run a wide-horizon `mention_family` pass, and it put **163
markets into `fixtures/board_sample.json`** that are still there — the
`normalize` golden has one entry per fixture row, so removing them would
rewrite a golden and every funnel count downstream of it. The fixture is
still needed by all seven survivors. So the rows stay, `meta.json` keeps
its `rates` / `preview_days` / `family_survivors` keys as the record of
how the fixture was built, and `build_fixture.py` now states in its
docstring that it can no longer reproduce the committed fixture's shape.
That was already true of any re-run — a different board and a different
clock give a different fixture — but the *shape* difference is new and is
written down rather than left to be rediscovered by whoever runs it next.

## Documents kept as written

**`THEORY.md` and `NOTES.md` still name modules and a runbook that no
longer exist in this folder.** That is deliberate: they are the record of
what the theory claimed and how it decided, and **no reference to a
deleted module was edited into agreement with the deletion.** Every path
they name resolves at the rev above. **Both files moved byte-for-byte:
neither took a single content edit at migration** — verified by
`git diff` over the move, which reports pure adds at the new path and
nothing else. Neither happened to name the series-bias-mining study, so
even the one edit `calibration_harvest` took (repointing its study) had
no counterpart here.

`THEORY.md`'s "Confidence buckets" table carries an **INVALIDATED**
banner written on 2026-08-25 by the session that killed it. Read the
banner, not the table.

## What is still live elsewhere

- The registry row (`theories`.`mention_family`, status `retired`,
  version 1) — including the full retirement rationale, and now a `path`
  pointing here.
- Every ledger row, score and backtest run this theory recorded.
  Retirement deletes code, never evidence. That includes the 3,441
  `backtest-2026-08-25-mention-fullcov` rows every number in `RESULTS.md`
  came from, and the ~39 live preview rows that settled Aug 28–Sep 15.
- Its three `judgment_runs` provenance rows. One names
  `theories/insider_bias/screen.py` and still resolves. The other two —
  the `live-2026-08-24-mention-preview30` and `...-v2` runs — named
  `mention_bucket.py` and were **repointed to this file** at migration,
  with the deletion, the retrieving `git show` and the reminder that
  `prompt_sha256` stays the authority appended to each row's `notes`.
  Both had already been repointed once, on 2026-08-26, when the module
  moved in the theory split; that note is kept above the new one rather
  than replaced. (The theory declared `uses_llm_judgment=False`; these
  rows record its *mechanical* decision procedure, `model='none
  (deterministic)'`, which is why they name a `.py` module and not a
  prompt.)
- `theories/insider_bias/families.py`, `screen.py`, `replay.py` and
  `backfill_history.py` — the shared parent, untouched.
