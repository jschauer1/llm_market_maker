"""tools.theories.prove_carry (enforcing-surfaces spec 2.4).

A `carry` bump is refused unless a replay of the theory's current
`decide` logic over the predecessor version's own recorded attempts
reproduces every decision output exactly. The harness (this module) owns
the fixture and the comparison; the theory owns the replay -- `decide` is
supplied by the caller and receives one joined attempt row (attempt
columns plus the parent position's `kalshi_ticker` and `outcome`).
"""

import json

import pytest

from tools import db, ledger, score, slices, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def conn(registered_conn):
    return registered_conn


def _record(conn, **overrides):
    kwargs = dict(
        theory_id="t1",
        theory_version=1,
        kalshi_ticker="KXTEST-26",
        outcome="yes",
        entry_price=0.40,
        edge_pts_net=6.0,
        model_prob=0.55,
        edge_pts_gross=8.0,
        confidence="strong",
        edge_basis="measured",
        rationale="looks mispriced",
        now=TS,
    )
    kwargs.update(overrides)
    return ledger.record_opportunity(conn, **kwargs)


def _echo_decide(row):
    """A decide that reproduces the recorded outputs exactly."""
    return {
        "outcome": row["outcome"], "disposition": row["disposition"],
        "model_prob": row["model_prob"], "confidence": row["confidence"],
        "edge_pts_gross": row["edge_pts_gross"],
        "edge_pts_net": row["edge_pts_net"], "edge_basis": row["edge_basis"],
    }


def test_identical_replay_passes(conn):
    # two recorded live attempts at v1
    _record(conn, kalshi_ticker="KXTEST-A", outcome="yes")
    _record(conn, kalshi_ticker="KXTEST-B", outcome="no")

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.passed and res.n_attempts == 2 and res.n_divergent == 0
    assert res.label.startswith("carry-proof/t1-v1-")


def test_single_divergence_fails_whatever_the_field(conn):
    _record(conn, kalshi_ticker="KXTEST-A", outcome="yes")

    def flip(row):
        out = _echo_decide(row)
        out["edge_basis"] = "model"
        return out

    res = theories.prove_carry(conn, "t1", 1, flip)
    assert not res.passed and res.n_divergent >= 1
    assert res.divergences[0][2] == "edge_basis"


def test_slice_predicated_extra_keys_are_compared(conn):
    # attempt recorded with extra_json {"family": "awards"}; decide returns
    # {"family": "sports"} under extra -> divergence on "extra.family"
    _record(
        conn, kalshi_ticker="KXTEST-C", outcome="yes",
        extra_json=json.dumps({"family": "awards"}),
    )

    def decide(row):
        out = _echo_decide(row)
        out["extra"] = {"family": "sports"}
        return out

    res = theories.prove_carry(conn, "t1", 1, decide,
                               slice_extra_keys=("family",))
    assert not res.passed and res.divergences[0][2] == "extra.family"


def test_empty_fixture_never_passes(conn):
    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.n_attempts == 0 and not res.passed


# --- coverage beyond the brief's skeletons ---


def test_default_slice_extra_keys_come_from_registered_slices(conn):
    # No slice_extra_keys argument at all: prove_carry must discover
    # "family" itself from the registered slice's predicate.
    slices.register_slice(
        conn, "t1", "awards-family",
        predicate={"extra": {"family": "awards"}},
        hypothesis="award-family markets carry a different edge",
        origin="test",
        now=TS,
    )
    _record(
        conn, kalshi_ticker="KXTEST-D", outcome="yes",
        extra_json=json.dumps({"family": "awards"}),
    )

    def decide(row):
        out = _echo_decide(row)
        out["extra"] = {"family": "sports"}
        return out

    res = theories.prove_carry(conn, "t1", 1, decide)
    assert not res.passed
    assert res.divergences[0][2] == "extra.family"


def test_numeric_tolerance_allows_tiny_float_drift(conn):
    _record(conn, kalshi_ticker="KXTEST-E", outcome="yes", edge_pts_net=6.0)

    def decide(row):
        out = _echo_decide(row)
        out["edge_pts_net"] = row["edge_pts_net"] + 1e-10
        return out

    res = theories.prove_carry(conn, "t1", 1, decide)
    assert res.passed


def test_missing_field_in_decide_output_is_a_divergence(conn):
    _record(conn, kalshi_ticker="KXTEST-F", outcome="yes")

    def decide(row):
        out = _echo_decide(row)
        del out["confidence"]
        return out

    res = theories.prove_carry(conn, "t1", 1, decide)
    assert not res.passed
    matches = [d for d in res.divergences if d[2] == "confidence"]
    assert len(matches) == 1
    assert matches[0][4] == "<absent>"


def test_experiment_lane_is_excluded_from_the_fixture(conn):
    # run_id starting with "exp/" lands in its own lane, never 'main' --
    # a variant being tried must never feed or block a carry proof.
    _record(conn, kalshi_ticker="KXTEST-G", outcome="yes", run_id="exp/try1")

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.n_attempts == 0


def test_backtest_attempts_in_the_main_lane_are_included(conn):
    _record(
        conn, kalshi_ticker="KXTEST-H", outcome="yes",
        run_mode="backtest", run_id="bt-1", decision_date="2026-08-20",
    )

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.n_attempts == 1
    assert res.passed


def test_tier_c_backtest_attempts_are_excluded_from_the_fixture(conn):
    # M3: a tier-C attempt is contaminated evidence -- it must not be able
    # to prove a carry either, mirroring segment_report's tier-C
    # exclusion. Recorded but never fed to `decide`.
    _record(
        conn, kalshi_ticker="KXTEST-TC", outcome="yes",
        run_mode="backtest", run_id="bt-c", decision_date="2026-08-20",
    )
    score.record_backtest_run(conn, "bt-c", "t1", 1, tier="C", now=TS)

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.n_attempts == 0


def test_tier_a_backtest_attempts_still_enter_the_fixture(conn):
    # A NULL tier (test_backtest_attempts_in_the_main_lane_are_included,
    # above) and an explicit A/B tier are both kept -- only 'C' is
    # excluded.
    _record(
        conn, kalshi_ticker="KXTEST-TA", outcome="yes",
        run_mode="backtest", run_id="bt-a", decision_date="2026-08-20",
    )
    score.record_backtest_run(conn, "bt-a", "t1", 1, tier="A", now=TS)

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.n_attempts == 1
    assert res.passed


def test_position_kind_is_exposed_on_the_replayed_row(conn):
    # M2: o.position_kind is joined into the fixture row so a `decide`
    # that needs to special-case a basket header can see it. No
    # comparison changes -- prove_carry itself never reads this field.
    _record(conn, kalshi_ticker="KXTEST-PK", outcome="yes")
    seen = []

    def decide(row):
        seen.append(row["position_kind"])
        return _echo_decide(row)

    res = theories.prove_carry(conn, "t1", 1, decide)
    assert res.passed
    assert seen == ["single"]


def test_other_theory_version_is_excluded_from_the_fixture(conn):
    _record(conn, kalshi_ticker="KXTEST-I", outcome="yes", theory_version=1)
    theories.bump_version(conn, "t1", now=TS, justification="unrelated bump")
    _record(conn, kalshi_ticker="KXTEST-J", outcome="yes", theory_version=2)

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.n_attempts == 1


def test_theories_row_extra_agrees_with_slices_on_extra_json_rows():
    # theories._row_extra is a deliberately narrower duplicate of
    # slices._row_extra -- slices' version also accepts a pre-parsed
    # "extra" mapping key (from score.observations dicts), which
    # theories' version does not need because prove_carry's fixture is
    # always a real opportunity_attempts row, which never carries one.
    # Restricted to the extra_json-only shape both parsers must agree on,
    # they need to return identically: two parsers silently disagreeing
    # about extra_json is the silent-merge shape CLAUDE.md warns about --
    # this test fails at the commit that forks them.
    cases = [
        {"extra_json": json.dumps({"family": "awards"})},  # valid extra_json
        {"extra_json": None},                               # no payload
        {"extra_json": "{not valid json"},                  # invalid JSON
        {},                                                  # key missing
    ]
    for row in cases:
        assert theories._row_extra(row) == slices._row_extra(row)


# --- theories.carry_chain (spec 2.5) ---


def test_carry_chain_v1_alone(conn):
    # v1's own row (from register()) is 'breaking' with no predecessor --
    # the walk stops on its first row and never leaves the requested
    # version.
    assert theories.carry_chain(conn, "t1", 1) == [1]


def test_carry_chain_missing_version_terminates(conn):
    # No row at all for a version that was never bumped to -- the walk
    # still returns the requested version itself, never raises.
    assert theories.carry_chain(conn, "t1", 99) == [99]


def test_carry_chain_carry_links_v2_to_v1(conn):
    _record(conn, kalshi_ticker="KXTEST-K", outcome="yes")
    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.passed

    theories.bump_version(
        conn, "t1", kind="carry", justification="no-op refactor",
        equivalence=res,
    )

    assert theories.carry_chain(conn, "t1", 2) == [1, 2]
    # A chain requested from the predecessor itself never reaches forward.
    assert theories.carry_chain(conn, "t1", 1) == [1]


def test_carry_chain_breaking_isolates(conn):
    theories.bump_version(conn, "t1", now=TS, kind="breaking",
                          justification="real change")

    assert theories.carry_chain(conn, "t1", 2) == [2]


def test_carry_chain_mixed_two_carries_reach_all_the_way_back(conn):
    # v1 -> v2 is carry, v2 -> v3 is carry: the chain requested from v3
    # is [1, 2, 3], NOT [2, 3] -- v2's own row (kind='carry') is what
    # pulls v1 in while the walk passes through v2, exactly as it does
    # when v2 is the requested version on its own (the case above).
    _record(conn, kalshi_ticker="KXTEST-L", outcome="yes")
    res_1_to_2 = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res_1_to_2.passed
    theories.bump_version(
        conn, "t1", kind="carry", justification="v1->v2 no-op",
        equivalence=res_1_to_2,
    )

    _record(conn, kalshi_ticker="KXTEST-M", outcome="yes", theory_version=2)
    res_2_to_3 = theories.prove_carry(conn, "t1", 2, _echo_decide)
    assert res_2_to_3.passed
    theories.bump_version(
        conn, "t1", kind="carry", justification="v2->v3 no-op",
        equivalence=res_2_to_3,
    )

    assert theories.carry_chain(conn, "t1", 3) == [1, 2, 3]
    # A chain requested mid-run only sees what precedes it.
    assert theories.carry_chain(conn, "t1", 2) == [1, 2]


def test_carry_chain_breaking_in_the_middle_stops_the_walk(conn):
    # v1 -> v2 carry, v2 -> v3 breaking: the chain from v3 stops at v3
    # itself, because v3's own row is what the walk consults first and it
    # says 'breaking' -- v1 and v2's earlier carry link never matters.
    _record(conn, kalshi_ticker="KXTEST-N", outcome="yes")
    res_1_to_2 = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res_1_to_2.passed
    theories.bump_version(
        conn, "t1", kind="carry", justification="v1->v2 no-op",
        equivalence=res_1_to_2,
    )
    theories.bump_version(conn, "t1", now=TS, kind="breaking",
                          justification="real change")

    assert theories.carry_chain(conn, "t1", 3) == [3]
    assert theories.carry_chain(conn, "t1", 2) == [1, 2]


def test_carry_chain_refuses_a_malformed_cycle_row(conn):
    # bump_version can never write this -- it always names a predecessor
    # strictly less than the version being bumped to -- but a raw INSERT
    # (a hand-edited fixture, a future writer that bypasses bump_version)
    # is not guaranteed that. A self-referential row (v2's own predecessor
    # is v2) is the simplest cycle: walking it would loop forever without
    # the guard (M1).
    with db.write(conn):
        conn.execute(
            """
            INSERT INTO theory_versions
                (theory_id, version, kind, predecessor, justification,
                 equivalence_run, created_at)
            VALUES ('t1', 2, 'carry', 2, 'malformed fixture', 'fake', ?)
            """,
            (TS,),
        )
    with pytest.raises(ValueError, match="predecessor"):
        theories.carry_chain(conn, "t1", 2)


# --- score.compute_score(pool=...) evidence pooling (spec 2.5) ---


def test_compute_score_pools_across_a_proven_carry_chain(conn):
    _record(conn, kalshi_ticker="KXTEST-O", outcome="yes")
    score.record_settlement(conn, "KXTEST-O", "yes", resolved_at=TS)

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.passed
    theories.bump_version(
        conn, "t1", kind="carry", justification="no-op refactor",
        equivalence=res,
    )

    _record(conn, kalshi_ticker="KXTEST-P", outcome="yes", theory_version=2)
    score.record_settlement(conn, "KXTEST-P", "yes", resolved_at=TS)

    by_version = score.compute_score(conn, "t1", 2, pool="version")
    assert by_version["n"] == 1
    assert "chain_versions" not in by_version

    by_chain = score.compute_score(conn, "t1", 2, pool="chain")
    assert by_chain["n"] == 2
    assert by_chain["chain_versions"] == [1, 2]


def test_compute_score_chain_of_one_adds_no_key(conn):
    # v2 is 'breaking' -- carry_chain(..., 2) == [2], nothing pooled -- so
    # pool="chain" must report identically to pool="version" and must not
    # claim a pooling that never happened.
    theories.bump_version(conn, "t1", now=TS, kind="breaking",
                          justification="real change")
    _record(conn, kalshi_ticker="KXTEST-Q", outcome="yes", theory_version=2)
    score.record_settlement(conn, "KXTEST-Q", "yes", resolved_at=TS)

    by_chain = score.compute_score(conn, "t1", 2, pool="chain")
    assert by_chain["n"] == 1
    assert "chain_versions" not in by_chain


def test_compute_score_invalid_pool_rejected(conn):
    with pytest.raises(ValueError):
        score.compute_score(conn, "t1", 1, pool="bogus")


# --- score.settlement_day_clusters(pool=...) evidence pooling (spec 2.5) ---
# Same widening as compute_score above, at the same _segment_filter seam --
# a report whose scores pool across a chain while its day-clusters stay
# per-version would be a silent segment inconsistency.


def test_settlement_day_clusters_pools_across_a_proven_carry_chain(conn):
    _record(conn, kalshi_ticker="KXTEST-O2", outcome="yes")
    score.record_settlement(
        conn, "KXTEST-O2", "yes", resolved_at="2026-08-20T00:00:00Z"
    )

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.passed
    theories.bump_version(
        conn, "t1", kind="carry", justification="no-op refactor",
        equivalence=res,
    )

    _record(conn, kalshi_ticker="KXTEST-P2", outcome="yes", theory_version=2)
    score.record_settlement(
        conn, "KXTEST-P2", "yes", resolved_at="2026-08-27T00:00:00Z"
    )

    by_version = score.settlement_day_clusters(conn, "t1", 2, pool="version")
    assert by_version["n"] == 1
    assert by_version["n_days"] == 1
    assert "chain_versions" not in by_version

    by_chain = score.settlement_day_clusters(conn, "t1", 2, pool="chain")
    assert by_chain["n"] == 2
    assert by_chain["n_days"] == 2, "v1's day and v2's day are distinct clusters"
    assert by_chain["chain_versions"] == [1, 2]


def test_settlement_day_clusters_chain_of_one_adds_no_key(conn):
    # v2 is 'breaking' -- carry_chain(..., 2) == [2], nothing pooled -- so
    # pool="chain" must report identically to pool="version" and must not
    # claim a pooling that never happened.
    theories.bump_version(conn, "t1", now=TS, kind="breaking",
                          justification="real change")
    _record(conn, kalshi_ticker="KXTEST-Q2", outcome="yes", theory_version=2)
    score.record_settlement(conn, "KXTEST-Q2", "yes", resolved_at=TS)

    by_chain = score.settlement_day_clusters(conn, "t1", 2, pool="chain")
    assert by_chain["n"] == 1
    assert "chain_versions" not in by_chain


def test_settlement_day_clusters_invalid_pool_rejected(conn):
    with pytest.raises(ValueError):
        score.settlement_day_clusters(conn, "t1", 1, pool="bogus")


def test_settlement_day_clusters_pool_version_is_byte_identical_to_default(conn):
    # pool="chain" is new; the implicit default must still be exactly what
    # settlement_day_clusters always returned, byte for byte.
    _record(conn, kalshi_ticker="KXTEST-R3", outcome="yes")
    score.record_settlement(conn, "KXTEST-R3", "yes", resolved_at=TS)

    assert score.settlement_day_clusters(conn, "t1", 1) == \
        score.settlement_day_clusters(conn, "t1", 1, pool="version")


# --- slices.segment_report(pool=...) evidence pooling (spec 2.8) ---


def test_segment_report_pools_slice_evidence_across_a_proven_carry_chain(conn):
    # R1 (v1) settles BEFORE registration -> in-sample; R2 (v2) settles
    # AFTER -> out-of-sample. A bucket swap (either row landing in the
    # wrong pile) must fail this, not just the total.
    slices.register_slice(
        conn, "t1", "strong-yes",
        predicate={"outcome": ["yes"], "confidence": ["strong"]},
        hypothesis="strong-confidence yes calls carry an edge",
        origin="test",
        registered_at="2026-08-25T00:00:00Z",
    )

    _record(conn, kalshi_ticker="KXTEST-R1", outcome="yes")
    score.record_settlement(
        conn, "KXTEST-R1", "yes", resolved_at="2026-08-20T00:00:00Z"
    )

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.passed
    theories.bump_version(
        conn, "t1", kind="carry", justification="no-op refactor",
        equivalence=res,
    )

    _record(conn, kalshi_ticker="KXTEST-R2", outcome="yes", theory_version=2)
    score.record_settlement(
        conn, "KXTEST-R2", "yes", resolved_at="2026-08-27T00:00:00Z"
    )

    by_version = slices.segment_report(conn, "t1", 2, pool="version")
    assert by_version["aggregate"]["n"] == 1, "v1's row must not pool in"
    slice_by_version = by_version["slices"][0]
    # Only R2 (v2, out-of-sample) is visible under pool="version".
    assert slice_by_version["oos"]["n"] == 1
    assert slice_by_version["in_sample"]["n"] == 0
    assert "chain_versions" not in by_version

    by_chain = slices.segment_report(conn, "t1", 2, pool="chain")
    assert by_chain["aggregate"]["n"] == 2, "proven carry pools v1's row in"
    slice_by_chain = by_chain["slices"][0]
    # Pooled: R1 (v1, in-sample) and R2 (v2, out-of-sample) land in the
    # exact opposite piles -- a bucket swap would flip either count.
    assert slice_by_chain["oos"]["n"] == 1, "R2 (v2) settled after registration"
    assert slice_by_chain["in_sample"]["n"] == 1, "R1 (v1) settled before it"
    assert by_chain["chain_versions"] == [1, 2]


def test_segment_report_chain_pools_a_slice_past_its_readiness_gates(conn):
    # Neither version alone clears MIN_SLICE_CLUSTERS (10) or
    # MIN_SLICE_DAYS (5) out of sample: 6 clusters / 3 days at v1, 6
    # clusters / 3 days at v2. Only pool="chain" combines them into 12
    # clusters across 6 distinct days -- past both gates -- so this drives
    # the complement-widening partition path that inspection alone can't
    # verify. Every settlement lands after the slice's registration day,
    # so all matching rows are out-of-sample by construction.
    slices.register_slice(
        conn, "t1", "gate-crossing",
        predicate={"outcome": ["yes"], "confidence": ["strong"]},
        hypothesis="strong-confidence yes calls carry an edge",
        origin="test",
        registered_at="2026-08-24T00:00:00Z",
    )

    v1_days = [
        "2026-08-28T00:00:00Z", "2026-08-29T00:00:00Z",
        "2026-08-30T00:00:00Z",
    ]
    v2_days = [
        "2026-08-31T00:00:00Z", "2026-09-01T00:00:00Z",
        "2026-09-02T00:00:00Z",
    ]

    # v1: six matching clusters (two per day) + one non-matching row.
    for i in range(6):
        ticker = f"KXC{i}-A"
        _record(conn, kalshi_ticker=ticker, outcome="yes")
        score.record_settlement(
            conn, ticker, "yes", resolved_at=v1_days[i // 2]
        )
    _record(conn, kalshi_ticker="KXNM1-A", outcome="no")
    score.record_settlement(
        conn, "KXNM1-A", "no", resolved_at=v1_days[0]
    )

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.passed
    theories.bump_version(
        conn, "t1", kind="carry", justification="no-op refactor",
        equivalence=res,
    )

    # v2: six more matching clusters (two per day, distinct days from v1)
    # + one more non-matching row.
    for i in range(6):
        ticker = f"KXD{i}-A"
        _record(conn, kalshi_ticker=ticker, outcome="yes", theory_version=2)
        score.record_settlement(
            conn, ticker, "yes", resolved_at=v2_days[i // 2]
        )
    _record(conn, kalshi_ticker="KXNM2-A", outcome="no", theory_version=2)
    score.record_settlement(
        conn, "KXNM2-A", "no", resolved_at=v2_days[0]
    )

    by_version = slices.segment_report(conn, "t1", 2, pool="version")
    entry_by_version = by_version["slices"][0]
    assert entry_by_version["oos"]["n_clusters"] == 6
    assert entry_by_version["oos"]["n_days"] == 3
    assert entry_by_version["ready"] is False, (
        "v2 alone is below both gates -- reports as accruing"
    )
    assert by_version["complement"] is None, (
        "no ready slice under pool=\"version\" -> no partition"
    )

    by_chain = slices.segment_report(conn, "t1", 2, pool="chain")
    entry_by_chain = by_chain["slices"][0]
    assert entry_by_chain["oos"]["n_clusters"] == 12, (
        "pooled across the proven carry, v1's six clusters join v2's six"
    )
    assert entry_by_chain["oos"]["n_days"] == 6
    assert entry_by_chain["ready"] is True, (
        "the gates clear only once the chain pools both versions' evidence"
    )
    assert by_chain["complement"] is not None, (
        "a ready slice under pool=\"chain\" partitions the pooled pool"
    )
    assert by_chain["complement"]["n"] == 2, (
        "the complement widened too -- one non-matching row from each "
        "version, not just v2's own"
    )


def test_segment_report_chain_of_one_adds_no_key(conn):
    # v2 is 'breaking' -- carry_chain(..., 2) == [2], nothing pooled -- so
    # pool="chain" must report identically to pool="version" and must not
    # claim a pooling that never happened.
    theories.bump_version(conn, "t1", now=TS, kind="breaking",
                          justification="real change")
    _record(conn, kalshi_ticker="KXTEST-T", outcome="yes", theory_version=2)
    score.record_settlement(conn, "KXTEST-T", "yes", resolved_at=TS)

    by_chain = slices.segment_report(conn, "t1", 2, pool="chain")
    assert by_chain["aggregate"]["n"] == 1
    assert "chain_versions" not in by_chain


def test_segment_report_invalid_pool_rejected(conn):
    with pytest.raises(ValueError):
        slices.segment_report(conn, "t1", 1, pool="bogus")


def test_segment_report_pool_version_is_byte_identical_to_default(conn):
    # pool="chain" is new (spec 2.8); the implicit default must still be
    # exactly what segment_report always returned, byte for byte.
    slices.register_slice(
        conn, "t1", "strong-yes",
        predicate={"outcome": ["yes"], "confidence": ["strong"]},
        hypothesis="strong-confidence yes calls carry an edge",
        origin="test",
        registered_at=TS,
    )
    _record(conn, kalshi_ticker="KXTEST-U", outcome="yes")
    score.record_settlement(conn, "KXTEST-U", "yes", resolved_at=TS)

    assert slices.segment_report(conn, "t1", 1) == \
        slices.segment_report(conn, "t1", 1, pool="version")


# --- slices.ranking_segment(pool=...) evidence pooling (spec 2.5, I1) ---
# ranking_segment is the seam an agent actually ranks candidates through
# (`slices match`) -- segment_report supporting pool="chain" is not
# enough on its own if the thing that feeds `rank` never asks for it.


def test_ranking_segment_pool_chain_widens_the_segment_and_discloses_it(conn):
    _record(conn, kalshi_ticker="KXALPHA-A", outcome="yes")
    score.record_settlement(
        conn, "KXALPHA-A", "yes", resolved_at="2026-08-20T00:00:00Z"
    )

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.passed
    theories.bump_version(
        conn, "t1", kind="carry", justification="no-op refactor",
        equivalence=res,
    )

    opp_id, _ = _record(
        conn, kalshi_ticker="KXBETA-A", outcome="yes", theory_version=2
    )
    score.record_settlement(
        conn, "KXBETA-A", "yes", resolved_at="2026-08-27T00:00:00Z"
    )
    row = ledger.get_opportunity(conn, opp_id)

    # pool="version": only v2's own row counts -- distinct ticker
    # prefixes (KXALPHA vs KXBETA) so n_clusters, not just n, actually
    # differs between the two calls.
    scoped_seg = slices.ranking_segment(conn, row, pool="version")
    assert scoped_seg["segment"] == "aggregate"
    assert scoped_seg["rank_inputs"]["n"] == 1
    assert "chain_versions" not in scoped_seg

    # Default (pool="chain", since the 2026-08-31 ruling): v1 pools in
    # too, and the widening is disclosed on the returned dict itself.
    chained_seg = slices.ranking_segment(conn, row)
    assert chained_seg["rank_inputs"]["n"] == 2
    assert chained_seg["chain_versions"] == [1, 2]


def test_ranking_segment_pool_version_is_byte_identical_to_default(conn):
    # pool="chain" is new; the implicit default must still be exactly
    # what ranking_segment always returned, byte for byte.
    opp_id, _ = _record(conn, kalshi_ticker="KXGAMMA-A", outcome="yes")
    score.record_settlement(conn, "KXGAMMA-A", "yes", resolved_at=TS)
    row = ledger.get_opportunity(conn, opp_id)

    assert slices.ranking_segment(conn, row) == \
        slices.ranking_segment(conn, row, pool="version")
