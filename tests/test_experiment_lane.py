"""The experiment lane (spec section 3.3a): trying a variant of a theory
is a subclass and an exp/ run id -- no version bump, no registration --
and the production track record provably cannot see it."""

import pytest

from tests.test_theory import NOW, TS, Mechanical, mkm
from tools import db, ledger, score, theories
from tools.domain import Candidate, Leg
from tools.theory import TheoryContext


@pytest.fixture
def conn(conn):
    c = conn
    theories.register(c, "stub_mech", "Stub Mechanical", "x", now=TS)
    with db.write(c):
        c.execute("UPDATE theories SET status='testing'"
                  " WHERE id='stub_mech'")
    return c


def _record(conn, run_id, ticker):
    ledger.record_opportunity(
        conn, theory_id="stub_mech", theory_version=1, kalshi_ticker=ticker,
        outcome="yes", entry_price=0.5, edge_pts_net=3.0, run_id=run_id,
        confidence="strong", now=TS)


def test_pooled_scores_exclude_experiment_runs(conn):
    _record(conn, "live", "KXA-26")
    _record(conn, "exp/wider-band", "KXB-26")
    score.record_settlement(conn, "KXA-26", "yes", resolved_at=TS)
    score.record_settlement(conn, "KXB-26", "no", resolved_at=TS)

    pooled = score.compute_score(conn, "stub_mech", 1)
    assert pooled["n"] == 1                    # the experiment's loss is
    assert pooled["win_rate"] == 1.0           # invisible to the pool...

    exp = score.compute_score(conn, "stub_mech", 1, run_id="exp/wider-band")
    assert exp["n"] == 1                       # ...but fully scoreable
    assert exp["win_rate"] == 0.0


def test_pooled_bucket_rates_exclude_experiment_runs(conn):
    _record(conn, "live", "KXA-26")
    _record(conn, "exp/wider-band", "KXB-26")
    score.record_settlement(conn, "KXA-26", "yes", resolved_at=TS)
    score.record_settlement(conn, "KXB-26", "no", resolved_at=TS)

    pooled = score.bucket_rates(conn, "stub_mech", 1)
    assert pooled["strong"]["n"] == 1          # an experiment teaches no
    assert pooled["strong"]["win_rate"] == 1.0  # production bucket its rate

    exp = score.bucket_rates(conn, "stub_mech", 1, run_id="exp/wider-band")
    assert exp["strong"]["n"] == 1


def test_a_subclass_variant_is_all_an_experiment_takes(conn):
    class WiderBand(Mechanical):
        """The whole experiment: one overridden method. Same id, same
        version, no registration -- the exp/ run id is the isolation."""

        def screen(self, ctx):
            return [Candidate(legs=(Leg(market=m, side="yes",
                                        price=m.yes_ask),),
                              days_to_close=1.0)
                    for m in ctx.board if (m.yes_ask or 1.0) <= 0.9]

    board = [mkm("KXV-26", yes_ask=0.7, event="KXV")]
    # The parent's own screen (threshold 0.5) would skip this market:
    assert Mechanical().screen(
        TheoryContext(conn=None, board=board, now=NOW)) == []

    ctx = TheoryContext.build(conn=conn, board=board, now=NOW,
                              run_id="exp/wider-band")
    result = WiderBand().start(ctx).finish()
    assert len(result.opportunity_ids) == 1
    row = ledger.get_opportunity(conn, result.opportunity_ids[0])
    assert row["theory_id"] == "stub_mech"     # records under the parent
    assert row["theory_version"] == 1          # no bump
    assert row["run_id"] == "exp/wider-band"

    score.record_settlement(conn, "KXV-26", "yes", resolved_at=TS)
    assert score.compute_score(conn, "stub_mech", 1)["n"] == 0      # pooled: blind
    assert score.compute_score(conn, "stub_mech", 1,
                               run_id="exp/wider-band")["n"] == 1   # on demand
