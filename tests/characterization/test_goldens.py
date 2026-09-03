"""The pass condition for every phase of the theory-layer OOP migration.

These are characterization tests: they assert that today's code produces
exactly what it produced when the goldens were recorded, field for field,
through `conftest.proj`. They are not a specification of correct behavior
-- they are a lock on *current* behavior, which is what makes a
restructuring provably behavior-preserving.

Whole-value equality everywhere except `run_mechanical_stages`, which is a
subset match on its Phase-0 keys: Task 7 of the migration is licensed to
ADD a `survivor_candidates` key, and only to add (OOP spec section 4.7).

A failure here is never fixed by regenerating a golden. It means the phase
under way changed behavior, which is either a bug to fix or a theory
version bump to escalate to the user (OOP spec section 8.2).

**Six goldens and four tests were deleted here on 2026-09-02**, when
`mention_family` (retired by the user 2026-08-27) was migrated out of the
live tree and `mention_bucket.py` was deleted with the rest of its code.
Keeping the module alive purely to keep those four tests green was
considered and rejected on three grounds:

  * `theories/insider_bias/README.md` sets the bar for the shared family
    parent at "both siblings actually depend on it". `insider_judgment`
    does not use `mention_bucket`, so elevating it there to keep a test
    passing would have broken the rule the folder exists to enforce.
  * this docstring says what these files are: the pass condition for the
    theory-layer OOP migration. That migration is complete, so the
    goldens for a deleted theory lock nothing that can still move.
  * a characterization test over code nobody can call is not coverage.
    It is 2.5MB of JSON asserting that a deleted module still behaves the
    way it did, which is true by construction.

The seven goldens covering live code -- screen, dedupe_by_event,
gate_partition, gate_partition_v3, run_mechanical_stages_v3,
blind_payload_v3, normalize -- are untouched, and the fixture they read
still contains the 163 markets the deleted mention_family pass put there
(see build_fixture). Retrieve the deleted tests and goldens with

    git show 450db428ec0e7542852fae6484ab8370aaeddfad:tests/characterization/test_goldens.py
    git show 450db428ec0e7542852fae6484ab8370aaeddfad:tests/characterization/goldens/mention_rank_wide.json
"""

from __future__ import annotations

from theories.insider_bias import screen
from theories.insider_bias.insider_judgment import gate, pipeline
from tools.kalshi import markets

from tests.characterization import conftest as cz


def _screened():
    return screen.screen(cz.board_input(), now=cz.frozen_now())


def test_screen_matches_golden():
    assert cz.proj(_screened()) == cz.load_golden("screen")


def test_dedupe_by_event_matches_golden():
    got = pipeline.dedupe_by_event(_screened())
    assert cz.proj(got) == cz.load_golden("dedupe_by_event")


def test_gate_partition_matches_golden():
    survivors, counts = gate.partition(pipeline.dedupe_by_event(_screened()))
    want = cz.load_golden("gate_partition_v3")
    assert cz.proj(survivors) == want["survivors"]
    assert cz.proj(counts) == want["counts"]


def test_gate_counts_still_sum_to_what_was_gated():
    """CLAUDE.md requires a code gate to report what it removed by
    category; a gate that drops silently is how a scan reports coverage it
    never had."""
    events = pipeline.dedupe_by_event(_screened())
    _, counts = gate.partition(events)
    assert sum(counts.values()) == len(events)


def test_blind_payload_matches_golden():
    candidates = _screened()
    survivors, _ = gate.partition(pipeline.dedupe_by_event(candidates))
    keys = {cz.event_key(s) for s in survivors}
    kept = [c for c in candidates if cz.event_key(c) in keys]
    got = pipeline.build_blind_payload(survivors, kept)
    assert cz.proj(got) == cz.load_golden("blind_payload_v3")


def test_blind_payload_carries_no_price():
    """The guard behind every judged_blind=True record. Cheap to re-assert
    here, and this is the fixture the migration actually runs it on."""
    candidates = _screened()
    survivors, _ = gate.partition(pipeline.dedupe_by_event(candidates))
    keys = {cz.event_key(s) for s in survivors}
    kept = [c for c in candidates if cz.event_key(c) in keys]
    pipeline.assert_blind(pipeline.build_blind_payload(survivors, kept))


def test_run_mechanical_stages_subset_matches_golden():
    got = cz.proj(
        pipeline.run_mechanical_stages(cz.board_input(), cz.frozen_now())
    )
    for key, want in cz.load_golden(
            "run_mechanical_stages_v3").items():
        assert got[key] == want, f"funnel key {key!r} changed"


def test_normalize_matches_golden_for_every_fixture_row():
    want = cz.load_golden("normalize")
    for row in cz.load_fixture():
        assert cz.proj(markets.normalize(row["raw"])) == want[row["ticker"]]


def test_normalize_preserves_the_complete_raw_payload():
    """Spec section 8.1: a thinner `raw` would make a theory reading an
    uncommon field work on a forced pull and return None on a cached one."""
    for row in cz.load_fixture()[:200]:
        assert markets.normalize(row["raw"]).raw == row["raw"]


def test_the_gate_v3_rules_reading_is_visible_in_the_goldens():
    """2026-08-29: gate.py started reading resolution rules, not only
    series-ticker prefixes.

    `gate_partition.json` is kept unmodified as the record of the
    prefix-only gate; the rules-reading behaviour got `_v3` files rather
    than overwriting them. This test locks the difference.

    Its two former companions -- `blind_payload.json` and
    `run_mechanical_stages.json` -- were deleted 2026-08-31: no test ever
    loaded them, so they cost 754K to assert nothing. `git show
    0b761b9:tests/characterization/goldens/blind_payload.json` retrieves
    either one if the pre-v3 payload shape is ever needed again.

    On the fixture board the old gate classified **every** screened event
    as PLAUSIBLE -- it recognised none of these families -- which is
    exactly the failure the change addresses: an allowlist only knows what
    someone has already typed into it.
    """
    old = cz.load_golden("gate_partition")
    new = cz.load_golden("gate_partition_v3")

    assert old["counts"] == {"PLAUSIBLE": len(old["survivors"])}, (
        "the pre-v3 gate recognised no family on this fixture"
    )
    assert len(new["survivors"]) < len(old["survivors"])

    # Every category the new gate reports must be one it can name, and the
    # counts must still account for every event -- a gate that drops
    # silently is how a scan claims coverage it never had.
    assert set(new["counts"]) - {"PLAUSIBLE"}, "v3 removed nothing"
    assert sum(new["counts"].values()) == sum(old["counts"].values())

    # Nothing survived v3 that did not survive the looser v2 gate: the
    # change may only remove, never resurrect.
    old_keys = {cz.event_key(s) for s in old["survivors"]}
    new_keys = {cz.event_key(s) for s in new["survivors"]}
    assert new_keys < old_keys
