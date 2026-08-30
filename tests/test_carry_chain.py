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
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


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


def test_other_theory_version_is_excluded_from_the_fixture(conn):
    _record(conn, kalshi_ticker="KXTEST-I", outcome="yes", theory_version=1)
    theories.bump_version(conn, "t1", now=TS, justification="unrelated bump")
    _record(conn, kalshi_ticker="KXTEST-J", outcome="yes", theory_version=2)

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.n_attempts == 1


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
    theories.bump_version(conn, "t1", now=TS, justification="real change")

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
    theories.bump_version(conn, "t1", now=TS, justification="real change")

    assert theories.carry_chain(conn, "t1", 3) == [3]
    assert theories.carry_chain(conn, "t1", 2) == [1, 2]


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
    theories.bump_version(conn, "t1", now=TS, justification="real change")
    _record(conn, kalshi_ticker="KXTEST-Q", outcome="yes", theory_version=2)
    score.record_settlement(conn, "KXTEST-Q", "yes", resolved_at=TS)

    by_chain = score.compute_score(conn, "t1", 2, pool="chain")
    assert by_chain["n"] == 1
    assert "chain_versions" not in by_chain


def test_compute_score_invalid_pool_rejected(conn):
    with pytest.raises(ValueError):
        score.compute_score(conn, "t1", 1, pool="bogus")
