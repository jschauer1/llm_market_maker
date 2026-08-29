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
"""

from __future__ import annotations

from theories.insider_bias import screen
from theories.insider_bias.insider_judgment import gate, pipeline
from theories.insider_bias.mention_family import mention_bucket
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
    want = cz.load_golden("gate_partition")
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
    assert cz.proj(got) == cz.load_golden("blind_payload")


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
    for key, want in cz.load_golden("run_mechanical_stages").items():
        assert got[key] == want, f"funnel key {key!r} changed"


def test_mention_family_validated_window_matches_golden():
    family = mention_bucket.find_candidates(
        cz.board_input(), now=cz.frozen_now()
    )
    assert cz.proj(family) == cz.load_golden("mention_find_candidates")
    got = mention_bucket.rank(family, cz.frozen_rates())
    assert cz.proj(got) == cz.load_golden("mention_rank")


def test_mention_family_wide_horizon_matches_goldens():
    """The goldens that actually lock this theory's arithmetic -- its
    validated 14-day window is routinely empty (see build_fixture)."""
    wide = mention_bucket.find_candidates(
        cz.board_input(), now=cz.frozen_now(),
        max_days_ahead=cz.preview_days(),
    )
    assert wide, "wide-horizon fixture coverage vanished"
    assert cz.proj(wide) == cz.load_golden("mention_find_candidates_wide")

    ranked = mention_bucket.rank(wide, cz.frozen_rates(), top_n=len(wide))
    assert cz.proj(ranked) == cz.load_golden(
        "mention_rank_wide_edge_corrected")

    preview = mention_bucket.rank_preview(
        wide, cz.frozen_rates(), top_n=len(wide)
    )
    assert cz.proj(preview) == cz.load_golden("mention_rank_preview_wide")


def test_the_bucket_edge_correction_is_visible_in_the_goldens():
    """2026-08-29: `buckets.edge_for` stopped differencing a bucket's
    pooled win rate against the CANDIDATE's price and started carrying the
    bucket's own realized edge.

    `mention_rank_wide.json` is deliberately kept, unmodified, as the
    record of the pre-correction arithmetic -- goldens are immutable, so
    the corrected behaviour got a new file rather than overwriting the
    old one. This test locks the difference itself, which is the most
    useful thing either file can do: under the old formula the ranking
    sorted by CHEAPNESS (every candidate in a bin was repriced against
    that bin's win rate, so the cheapest looked best); under the
    corrected one every candidate in a bin claims the same gross edge and
    the ranking is decided by fees and volume instead.
    """
    old = cz.load_golden("mention_rank_wide")
    new = cz.load_golden("mention_rank_wide_edge_corrected")
    assert len(old) == len(new), "same candidate set, different arithmetic"

    # The old top pick was the cheaper market; the corrected one is not.
    assert old[0]["entry_price"] < new[0]["entry_price"]
    assert old[0]["edge_pts_net"] > new[0]["edge_pts_net"]

    # Under the correction, claimed gross edge is a property of the
    # bucket, so every row sharing a bucket claims the same gross number
    # and differs only by its own fee.
    from tools.sizing import fee_pts

    by_bucket: dict[str, set] = {}
    for row in new:
        gross = row["edge_pts_net"] + fee_pts(row["entry_price"])
        by_bucket.setdefault(row["bucket"], set()).add(round(gross, 6))
    assert by_bucket, "the corrected golden carries no bucketed rows"
    for bucket, grosses in by_bucket.items():
        assert len(grosses) == 1, (
            f"{bucket} claims {len(grosses)} different gross edges; a "
            "bucket's realized edge does not depend on the candidate"
        )


def test_rank_and_rank_preview_stay_two_different_functions():
    """They exist separately on purpose: a wider horizon changes what
    edge_basis a caller may honestly attach. Collapsing them into one
    function with a flag is the regression the OOP spec's non-regression
    list names explicitly."""
    ranked = cz.load_golden("mention_rank_wide")
    preview = cz.load_golden("mention_rank_preview_wide")
    assert {r["edge_basis"] for r in preview} == {"model"}
    assert ranked != preview


def test_normalize_matches_golden_for_every_fixture_row():
    want = cz.load_golden("normalize")
    for row in cz.load_fixture():
        assert cz.proj(markets.normalize(row["raw"])) == want[row["ticker"]]


def test_normalize_preserves_the_complete_raw_payload():
    """Spec section 8.1: a thinner `raw` would make a theory reading an
    uncommon field work on a forced pull and return None on a cached one."""
    for row in cz.load_fixture()[:200]:
        assert markets.normalize(row["raw"]).raw == row["raw"]
