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

from tools import db, ledger, slices, theories

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
