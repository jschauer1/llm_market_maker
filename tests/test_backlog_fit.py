"""The section 3.2 litmus test widened: one stub per shape the backlog
review found the first draft could not express. A test is how the four
shapes STAY expressible -- if a change to the contract breaks one of these,
the contract got tighter than the backlog allows, and the contract is what
is wrong (spec section 8.6)."""

import json

import pytest

from tools import db, ledger, theories
from tools.domain import Candidate, Edge, Leg, Market, ScoredCandidate
from tools.theory import Theory, TheoryContext

from tests.test_theory import NOW, TS, fake_ctx, mkm


def _seed(conn, tid):
    theories.register(conn, tid, tid, "x", now=TS)
    with db.write(conn):
        conn.execute("UPDATE theories SET status='testing' WHERE id=?",
                     (tid,))


def test_a_basket_producer_records_one_position_with_legs(conn):
    """structural-arb-like: a NO pair whose asks sum under the payout.

    Deliberately ALL-OR-NOTHING (max_payout 1.0 over a mutually exclusive
    pair), so it never depends on the variable-payout scoring decision
    still open as multi-leg spec section 10.1. A basket with a payout
    floor records fine but cannot yet be scored -- that guard is not this
    migration's to touch."""

    class BasketArb(Theory):
        id, name, version = "stub_basket", "Stub Basket", 1

        def screen(self, ctx):
            legs = tuple(Leg(market=m, side="no", price=m.no_ask)
                         for m in ctx.board)
            return [Candidate(legs=legs, days_to_close=1.0, max_payout=1.0)]

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(
                candidate=c,
                edge=Edge(pts_net=(c.max_payout - c.cost) * 100.0,
                          basis="model"))
                for c in cands if c.cost < c.max_payout]

    _seed(conn, "stub_basket")
    board = [mkm("KXA-26", event="KXE"), mkm("KXB-26", event="KXE")]
    board = [Market(platform="kalshi", ticker=m.ticker, no_ask=0.45,
                    is_open=True, event_ticker="KXE", raw={}) for m in board]
    ctx = TheoryContext.build(conn=conn, board=board, now=NOW)
    result = BasketArb().start(ctx).finish()
    assert len(result.opportunity_ids) == 1
    row = ledger.get_opportunity(conn, result.opportunity_ids[0])
    assert row["position_kind"] == "basket"
    assert row["leg_count"] == 2
    assert row["entry_price"] == pytest.approx(0.90)
    assert len(ledger.get_legs(conn, result.opportunity_ids[0])) == 2


def test_an_external_source_theory_takes_fetch(conn):
    """vol-crossing-like: fetches Coinbase-style candles through the Fetch
    seam; a canned payload replaces the network with no monkeypatch."""

    class VolCrossing(Theory):
        id, name, version = "stub_vol", "Stub Vol", 1

        def __init__(self, fetch):
            self.fetch = fetch          # instance CONFIG, not run state

        def screen(self, ctx):
            candles = self.fetch("https://example.invalid/candles")
            if max(c["high"] for c in candles) < 60000:
                return []
            m = Market(platform="kalshi", ticker="KXBTC-26", is_open=True,
                       raw={})
            return [Candidate(legs=(Leg(market=m, side="yes", price=0.3),),
                              days_to_close=1.0)]

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(candidate=c,
                                    edge=Edge(pts_net=6.0, basis="model"))
                    for c in cands]

    canned = lambda url, params=None, timeout=30: [
        {"high": 61000}, {"high": 59000}]
    result = VolCrossing(canned).start(fake_ctx()).finish(dry_run=True)
    assert result.funnel["scored"] == 1


def test_a_pair_store_theory_reads_theory_facts_mechanically(conn):
    """metaculus-gap-like: a model confirmed the pair once at construction
    time; every per-run decision is pure arithmetic, so
    uses_llm_judgment=False and the run needs no per-run provenance."""
    _seed(conn, "stub_pairs")
    with db.write(conn):
        conn.execute(
            "INSERT INTO theory_facts (theory_id, kind, key, value_json,"
            " established_at) VALUES ('stub_pairs', 'market_pair',"
            " 'KXCPI-26', ?, ?)",
            (json.dumps({"kalshi": "KXCPI-26", "external_prob": 0.62}), TS))

    class PairStore(Theory):
        id, name, version = "stub_pairs", "Stub Pairs", 1

        def screen(self, ctx):
            rows = ctx.conn.execute(
                "SELECT value_json FROM theory_facts"
                " WHERE theory_id='stub_pairs' AND kind='market_pair'"
            ).fetchall()
            out = []
            for r in rows:
                pair = json.loads(r["value_json"])
                m = Market(platform="kalshi", ticker=pair["kalshi"],
                           is_open=True, raw={})
                out.append(Candidate(
                    legs=(Leg(market=m, side="yes", price=0.5),),
                    days_to_close=2.0))
            return out

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(candidate=c,
                                    edge=Edge(pts_net=12.0, basis="model",
                                              model_prob=0.62))
                    for c in cands]

    ctx = TheoryContext.build(conn=conn, board=[], now=NOW)
    result = PairStore().start(ctx).finish()
    assert len(result.opportunity_ids) == 1
    assert ledger.get_opportunity(
        conn, result.opportunity_ids[0])["kalshi_ticker"] == "KXCPI-26"


def test_a_non_board_theory_ignores_ctx_board_entirely():
    """whale-follow-like: its universe is Polymarket flow, not the board."""

    class WhaleFollow(Theory):
        id, name, version = "stub_whale", "Stub Whale", 1

        def screen(self, ctx):
            assert ctx.board == []      # never touched; nothing to touch
            m = Market(platform="kalshi", ticker="KXWHALE-26", is_open=True,
                       raw={})
            return [Candidate(legs=(Leg(market=m, side="yes", price=0.4),),
                              days_to_close=3.0)]

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(candidate=c,
                                    edge=Edge(pts_net=5.0, basis="model"))
                    for c in cands]

    result = WhaleFollow().start(fake_ctx()).finish(dry_run=True)
    assert result.funnel["scored"] == 1
