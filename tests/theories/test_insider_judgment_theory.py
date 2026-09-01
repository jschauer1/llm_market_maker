from datetime import datetime, timezone

import pytest

from tests.characterization import conftest as cz
from tools import db, ledger, provenance, theories
from tools.domain import ScreenResult, Verdict
from tools.theory import TheoryContext

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
TS = "2026-08-24T12:00:00Z"


def _theory():
    from theories.insider_bias.insider_judgment import THEORY
    return THEORY


def fake_ctx(board, conn=None, judge_model=None):
    return TheoryContext(conn=conn, board=board, now=cz.frozen_now(),
                         judge_model=judge_model)


def test_screen_reproduces_the_golden_funnel():
    result = _theory().screen(fake_ctx(cz.board_input()))
    assert isinstance(result, ScreenResult)
    want = cz.load_golden("run_mechanical_stages_v3")
    for key in ("board_markets", "screened_markets", "events", "gated_out",
                "survivors", "survivor_markets"):
        assert result.funnel[key] == want[key]
    # gate_removed: every category except PLAUSIBLE, summing to gated_out
    assert "PLAUSIBLE" not in result.gate_removed
    assert sum(result.gate_removed.values()) == want["gated_out"]
    assert len(result.candidates) == want["survivor_markets"]


def test_judgment_payload_equals_the_golden_blind_payload():
    theory = _theory()
    run = theory.start(fake_ctx(cz.board_input()))
    assert run.payload == cz.load_golden("blind_payload_v3")


def test_judgment_payload_is_none_when_nothing_survives():
    assert _theory().judgment_payload([]) is None


def _seed(conn):
    theories.register(conn, "insider_judgment", "Insider Judgment",
                      "theories/insider_bias/insider_judgment", now=TS)
    with db.write(conn):
        conn.execute(
            "UPDATE theories SET version = 3, status = 'testing' "
            "WHERE id = 'insider_judgment'")
    theories.set_uses_llm_judgment(conn, "insider_judgment", True)


def _tiny_board():
    """Two sibling strikes on one event that clear every screen threshold
    and the gate (KXFAKE matches no NO_RULES family)."""
    from tools.domain import Market
    def m(ticker):
        return Market(platform="kalshi", ticker=ticker, title="t?",
                      yes_bid=0.78, yes_ask=0.80, no_bid=0.20, no_ask=0.22,
                      mid=0.79, spread=0.02, volume=900.0, is_open=True,
                      close_time="2026-08-26T00:00:00Z", status="active",
                      event_ticker="KXFAKE-26", series_ticker="KXFAKE",
                      rules_primary="r", raw={"ticker": ticker})
    return [m("KXFAKE-26-A"), m("KXFAKE-26-B")]


def test_one_verdict_reaches_every_sibling_and_records(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    _seed(conn)
    ctx = TheoryContext.build(conn=conn, board=_tiny_board(), now=NOW,
                              judge_model="test-model")
    run = _theory().start(ctx)
    assert run.needs_judgment and len(run.candidates) == 2
    result = run.apply(
        {"KXFAKE-26": Verdict(bucket="strong", rationale="pre-taped")}
    ).finish()
    assert len(result.opportunity_ids) == 2       # siblings share the verdict
    for opp_id in result.opportunity_ids:
        row = ledger.get_opportunity(conn, opp_id)
        assert row["confidence"] == "strong"
        assert row["judged_blind"] == 1
        assert row["edge_basis"] == "prior"       # no measured rates yet
        assert row["edge_pts_net"] == pytest.approx(4.0)   # THEORY.md prior
        assert row["theory_version"] == 6
    runs = provenance.list_judgment_runs(conn, theory_id="insider_judgment")
    # v5 removed stage 6: analysis is the only judging stage left.
    assert {r["stage"] for r in runs} == {"analysis"}
    assert all(r["model"] == "test-model" for r in runs)
    conn.close()


def test_an_unknown_bucket_is_refused(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    _seed(conn)
    ctx = TheoryContext.build(conn=conn, board=_tiny_board(), now=NOW,
                              judge_model="test-model")
    run = _theory().start(ctx)
    run.apply({"KXFAKE-26": Verdict(bucket="certain")})
    with pytest.raises(ValueError, match="scale"):
        run.finish(dry_run=True)
    conn.close()


def test_naively_serializing_a_candidate_trips_assert_blind():
    """A Candidate composes a Market carrying every price field. Dumping
    one into a judgment payload must trip the guard -- this proves the
    refactor made the mistake easier to commit but no easier to get away
    with (spec section 8.3)."""
    from dataclasses import asdict

    from theories.insider_bias.insider_judgment import pipeline
    from tools.domain import Candidate, Leg

    cand = Candidate(legs=(Leg(market=_tiny_board()[0], side="yes",
                               price=0.80),), days_to_close=2.0)
    with pytest.raises(pipeline.BlindPayloadError):
        pipeline.assert_blind([asdict(cand)])
