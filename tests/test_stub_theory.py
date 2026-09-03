"""The spec section 3.2 litmus test, mechanised: a stub implementing only
screen() and price() runs end to end and records; a stub that ignores ctx
entirely still runs. The contract is a floor, not a cage."""

import pytest

from tests.test_theory import NOW, TS, Mechanical, fake_ctx, mkm
from tools import db, ledger, theories
from tools.domain import Candidate, Edge, Leg, Market, ScoredCandidate
from tools.theory import Theory, TheoryContext


@pytest.fixture
def conn(conn):
    c = conn
    theories.register(c, "stub_mech", "Stub Mechanical", "x",
                      status="proposed", now=TS)
    theories.set_status(c, "stub_mech", "testing", now=TS)
    return c


def test_two_required_methods_are_enough_to_record(conn):
    board = [mkm("KXT-1", yes_ask=0.4, event="KXE1"),
             mkm("KXT-2", yes_ask=0.9, event="KXE2")]
    ctx = TheoryContext.build(conn=conn, board=board, now=NOW)
    result = Mechanical().start(ctx).finish()
    assert result.status == "testing"
    assert len(result.opportunity_ids) == 1
    row = ledger.get_opportunity(conn, result.opportunity_ids[0])
    assert row["kalshi_ticker"] == "KXT-1"
    assert row["outcome"] == "yes"
    assert row["entry_price"] == pytest.approx(0.4)
    assert row["edge_basis"] == "model"
    assert row["run_id"] == "live"


def test_a_theory_may_ignore_ctx_and_bring_its_own_data():
    class OwnSource(Theory):
        id, name, version = "own_source", "Own Source", 1

        def screen(self, ctx):
            m = Market(platform="kalshi", ticker="KXW-26", is_open=True,
                       raw={})          # from anywhere: a file, an API, ...
            return [Candidate(legs=(Leg(market=m, side="no", price=0.2),),
                              days_to_close=1.0)]

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(candidate=c,
                                    edge=Edge(pts_net=3.0, basis="model"))
                    for c in cands]

    result = OwnSource().start(fake_ctx()).finish(dry_run=True)
    assert result.funnel["scored"] == 1
