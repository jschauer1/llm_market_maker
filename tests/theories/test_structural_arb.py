"""structural_arb: constructed violation fixtures and near-miss controls.

Every check gets both directions: a fixture that must fire, and a
near-miss (inside fees + buffer, or with an incompletable proof) that
must not. The proofs are conservative on purpose — a false positive here
is real money lost, a false negative is a missed lottery ticket.
"""

from datetime import datetime, timezone

import pytest

from theories.structural_arb import scan
from theories.structural_arb.theory import (MAX_FLAG_FETCHES,
                                            StructuralArbTheory, _flag_cache)
from tools import db as tdb
from tools import theories as theories_db
from tools.domain import Market
from tools.theory import TheoryContext

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def m(ticker: str, *, event: str = "EV-1", strike_type: str | None = None,
      floor: float | None = None, cap: float | None = None,
      yes_ask: float | None = None, no_ask: float | None = None,
      is_open: bool = True,
      title: str = "Will the metric land above the strike?") -> Market:
    raw: dict = {"ticker": ticker}
    if strike_type is not None:
        raw["strike_type"] = strike_type
    if floor is not None:
        raw["floor_strike"] = floor
    if cap is not None:
        raw["cap_strike"] = cap
    return Market(
        platform="kalshi", ticker=ticker, title=title,
        yes_ask=yes_ask, no_ask=no_ask,
        yes_bid=None, no_bid=None,
        status="active" if is_open else "closed", is_open=is_open,
        close_time="2026-08-30T00:00:00Z",
        event_ticker=event, series_ticker="KXTEST", volume=100.0,
        raw=raw,
    )


# ---------------------------------------------------------------- yes_set

def test_yes_set_each_strike_type():
    g = scan.yes_set(m("G", strike_type="greater", floor=10))
    assert (g.lo, g.hi, g.lo_closed, g.boundary_known) == (
        10.0, scan.POS_INF, False, True)
    ge = scan.yes_set(m("GE", strike_type="greater_or_equal", floor=10))
    assert ge.lo_closed is True
    lt = scan.yes_set(m("L", strike_type="less", cap=5))
    assert (lt.lo, lt.hi, lt.hi_closed) == (scan.NEG_INF, 5.0, False)
    le = scan.yes_set(m("LE", strike_type="less_or_equal", cap=5))
    assert le.hi_closed is True
    b = scan.yes_set(m("B", strike_type="between", floor=1, cap=2))
    assert (b.lo, b.hi, b.boundary_known) == (1.0, 2.0, False)


def test_yes_set_rejects_unusable():
    assert scan.yes_set(m("X", strike_type="structured")) is None
    assert scan.yes_set(m("X", strike_type="custom", floor=1)) is None
    assert scan.yes_set(m("X")) is None                       # no type
    assert scan.yes_set(m("X", strike_type="greater")) is None  # no floor
    assert scan.yes_set(
        m("X", strike_type="between", floor=5, cap=1)) is None  # inverted
    bad = m("X", strike_type="greater")
    bad.raw["floor_strike"] = True                            # bool is not a strike
    assert scan.yes_set(bad) is None


# ------------------------------------------------- containment/disjoint

def _ys(**kw):
    return scan.yes_set(m("T", **kw))


def test_containment_greater_chain():
    lo = _ys(strike_type="greater", floor=10)
    hi = _ys(strike_type="greater", floor=20)
    assert scan.proper_contains(lo, hi)
    assert not scan.proper_contains(hi, lo)


def test_containment_equal_floor_closure():
    g = _ys(strike_type="greater", floor=10)
    ge = _ys(strike_type="greater_or_equal", floor=10)
    assert scan.proper_contains(ge, g)      # [10,inf) ⊃ (10,inf)
    assert not scan.contains(g, ge)         # 10 itself is the difference


def test_containment_between_needs_strict_bounds():
    g15 = _ys(strike_type="greater", floor=15)
    b = _ys(strike_type="between", floor=15, cap=20)
    # between's closure at 15 is unknown: (15,inf) cannot provably cover it
    assert not scan.contains(g15, b)
    g10 = _ys(strike_type="greater", floor=10)
    assert scan.proper_contains(g10, b)     # strict at both ends


def test_between_superset_equal_edge_rejected():
    outer = _ys(strike_type="between", floor=10, cap=20)
    inner = _ys(strike_type="between", floor=10, cap=15)
    # outer's closure at 10 unknown -> cannot prove it covers inner's 10
    assert not scan.contains(outer, inner)


def test_disjoint_touching_edges():
    lt = _ys(strike_type="less", cap=10)
    gt = _ys(strike_type="greater", floor=10)
    ge = _ys(strike_type="greater_or_equal", floor=10)
    le = _ys(strike_type="less_or_equal", cap=10)
    assert scan.disjoint(lt, gt)
    assert scan.disjoint(lt, ge)            # less is provably open at 10
    assert scan.disjoint(le, gt)            # greater provably open at 10
    assert not scan.disjoint(le, ge)        # both closed at 10
    b1 = _ys(strike_type="between", floor=5, cap=10)
    b2 = _ys(strike_type="between", floor=10, cap=15)
    assert not scan.disjoint(b1, b2)        # unknown closure at the touch
    b3 = _ys(strike_type="between", floor=11, cap=15)
    assert scan.disjoint(b1, b3)


def test_intersects_is_interior_only():
    b1 = _ys(strike_type="between", floor=5, cap=10)
    b2 = _ys(strike_type="between", floor=9, cap=15)
    assert scan.intersects(b1, b2)
    b3 = _ys(strike_type="between", floor=10, cap=15)
    assert not scan.intersects(b1, b3)      # only the doubtful endpoint


# ----------------------------------------------------------- DP selection

def test_max_weight_disjoint_beats_greedy():
    # One fat interval overlapping two thin ones whose combined weight wins.
    fat = (m("FAT"), _ys(strike_type="between", floor=0, cap=30), 0.5)
    thin1 = (m("T1"), _ys(strike_type="between", floor=1, cap=9), 0.3)
    thin2 = (m("T2"), _ys(strike_type="between", floor=11, cap=29), 0.3)
    chosen = scan._max_weight_disjoint([fat, thin1, thin2])
    assert {c[0].ticker for c in chosen} == {"T1", "T2"}
    # And the fat one wins when it outweighs both.
    fat_heavy = (fat[0], fat[1], 0.9)
    chosen = scan._max_weight_disjoint([fat_heavy, thin1, thin2])
    assert {c[0].ticker for c in chosen} == {"FAT"}


# ------------------------------------------------------ nested pair check

def test_nested_pair_fires_and_near_miss_does_not():
    sup = m("L-10", strike_type="greater", floor=10, yes_ask=0.40)
    sub = m("L-20", strike_type="greater", floor=20, no_ask=0.50)
    out = scan.scan_events({"EV-1": [sup, sub]})
    assert len(out.findings) == 1
    f = out.findings[0]
    assert f.kind == "nested_pair"
    assert f.min_payout == 1.0 and f.max_payout == 2.0
    assert f.profit_floor == pytest.approx(
        1.0 - 0.90 - scan._fee(0.40) - scan._fee(0.50), abs=1e-9)
    # Near miss: cost 0.99 leaves < 1c/leg after fees.
    sup2 = m("L-10", strike_type="greater", floor=10, yes_ask=0.49)
    sub2 = m("L-20", strike_type="greater", floor=20, no_ask=0.50)
    out2 = scan.scan_events({"EV-1": [sup2, sub2]})
    assert out2.findings == ()


def test_consistent_ladder_produces_nothing():
    ladder = [
        m("L-10", strike_type="greater", floor=10, yes_ask=0.80,
          no_ask=0.22),
        m("L-20", strike_type="greater", floor=20, yes_ask=0.55,
          no_ask=0.47),
        m("L-30", strike_type="greater", floor=30, yes_ask=0.30,
          no_ask=0.72),
    ]
    out = scan.scan_events({"EV-1": ladder})
    assert out.findings == ()
    assert out.flag_candidates == ()


# -------------------------------------------------- geometry NO baskets

def test_scalar_no_basket_fires():
    ms = [
        m("N-1", strike_type="less", cap=10, no_ask=0.30),
        m("N-2", strike_type="between", floor=11, cap=19, no_ask=0.30),
        m("N-3", strike_type="greater", floor=20, no_ask=0.30),
    ]
    out = scan.scan_events({"EV-1": ms})
    assert len(out.findings) == 1
    f = out.findings[0]
    assert f.kind == "no_basket"
    assert len(f.legs) == 3
    assert f.min_payout == 2.0 and f.max_payout == 3.0
    assert all(leg.side == "no" for leg in f.legs)
    assert f.clears_buffer


def test_scalar_no_basket_respects_unprovable_boundary():
    # Bands touch at 10: closure unknown, so they never share a basket.
    ms = [
        m("P-1", strike_type="between", floor=0, cap=10, no_ask=0.10),
        m("P-2", strike_type="between", floor=10, cap=20, no_ask=0.10),
    ]
    out = scan.scan_events({"EV-1": ms})
    assert out.findings == ()


def test_fairly_priced_partition_produces_nothing():
    # NO asks sum to k-1 + spread: no free lunch to find.
    ms = [
        m("N-1", strike_type="less", cap=10, no_ask=0.72),
        m("N-2", strike_type="between", floor=11, cap=19, no_ask=0.62),
        m("N-3", strike_type="greater", floor=20, no_ask=0.72),
    ]
    out = scan.scan_events({"EV-1": ms})
    assert out.findings == ()


# ------------------------------------------------------ flag NO baskets

def test_flag_candidate_separated_and_contradiction_voids():
    cats = [
        m("C1", strike_type="structured", no_ask=0.40),
        m("C2", strike_type="structured", no_ask=0.40),
        m("C3", strike_type="structured", no_ask=0.40),
    ]
    out = scan.scan_events({"EV-1": cats})
    assert out.findings == ()               # geometry can't prove ME
    assert len(out.flag_candidates) == 1
    assert out.flag_candidates[0].min_payout == 2.0
    # Two provably-overlapping scalar legs contradict any ME flag.
    mix = [
        m("G-10", strike_type="greater", floor=10, no_ask=0.10),
        m("G-20", strike_type="greater", floor=20, no_ask=0.10),
        m("C1", strike_type="structured", no_ask=0.10),
    ]
    out2 = scan.scan_events({"EV-2": mix})
    assert out2.flag_candidates == ()


# ------------------------------------------------------- theory adapter

def _fake_fetch(me_flags: dict[str, bool], fresh_quotes: list[dict],
                orderbooks: dict[str, dict] | None = None):
    def fetch(url, params=None):
        if "/events/" in url:
            ev = url.rsplit("/", 1)[1]
            if ev not in me_flags:
                raise RuntimeError("no such event")
            return {"event": {"event_ticker": ev,
                              "mutually_exclusive": me_flags[ev]}}
        if url.endswith("/orderbook"):
            if orderbooks is None:
                raise AssertionError(f"unexpected fetch {url}")
            ticker = url.rsplit("/", 2)[-2]
            if ticker not in orderbooks:
                raise RuntimeError("orderbook unavailable")
            return {"orderbook_fp": orderbooks[ticker]}
        if url.endswith("/markets"):
            return {"markets": fresh_quotes}
        raise AssertionError(f"unexpected fetch {url}")
    return fetch


def _ctx(board, run_mode="backtest"):
    return TheoryContext(conn=None, board=board, now=NOW,
                         run_id="exp/test", run_mode=run_mode)


def setup_function(_fn):
    _flag_cache.clear()


def test_screen_backtest_flag_paths():
    board = [
        # geometry find
        m("L-10", event="EV-G", strike_type="greater", floor=10,
          yes_ask=0.40),
        m("L-20", event="EV-G", strike_type="greater", floor=20,
          no_ask=0.50),
        # flag-confirmed categorical basket
        m("A1", event="EV-ME", strike_type="structured", no_ask=0.30),
        m("A2", event="EV-ME", strike_type="structured", no_ask=0.30),
        m("A3", event="EV-ME", strike_type="structured", no_ask=0.30),
        # non-ME categorical: arithmetic fires, flag kills it
        m("P-1", event="EV-FREE", strike_type="structured", no_ask=0.30),
        m("P-2", event="EV-FREE", strike_type="structured", no_ask=0.30),
        m("P-3", event="EV-FREE", strike_type="structured", no_ask=0.30),
    ]
    theory = StructuralArbTheory(
        fetch=_fake_fetch({"EV-ME": True, "EV-FREE": False}, []))
    res = theory.screen(_ctx(board))
    assert res.funnel["flag_confirmed"] == 1
    assert res.gate_removed.get("not_mutually_exclusive") == 1
    kinds = {c.key: (c.min_payout, c.max_payout) for c in res.candidates}
    assert len(res.candidates) == 2
    assert kinds["A1+A2+A3"] == (2.0, 3.0)
    # candidates sorted by profit floor: the 3-leg basket dominates
    assert res.candidates[0].key == "A1+A2+A3"


def test_screen_live_reverify_kills_stale_quote():
    board = [
        m("L-10", event="EV-G", strike_type="greater", floor=10,
          yes_ask=0.40),
        m("L-20", event="EV-G", strike_type="greater", floor=20,
          no_ask=0.50),
    ]
    fresh = [
        {"ticker": "L-10", "status": "active", "yes_ask_dollars": "0.55",
         "strike_type": "greater", "floor_strike": 10,
         "event_ticker": "EV-G"},
        {"ticker": "L-20", "status": "active", "no_ask_dollars": "0.50",
         "strike_type": "greater", "floor_strike": 20,
         "event_ticker": "EV-G"},
    ]
    theory = StructuralArbTheory(fetch=_fake_fetch({}, fresh))
    res = theory.screen(_ctx(board, run_mode="live"))
    assert res.candidates == ()
    assert res.gate_removed.get("stale_quote") == 1


def test_screen_live_reverify_keeps_real_violation():
    board = [
        m("L-10", event="EV-G", strike_type="greater", floor=10,
          yes_ask=0.40),
        m("L-20", event="EV-G", strike_type="greater", floor=20,
          no_ask=0.50),
    ]
    fresh = [
        {"ticker": "L-10", "status": "active", "yes_ask_dollars": "0.41",
         "strike_type": "greater", "floor_strike": 10,
         "event_ticker": "EV-G"},
        {"ticker": "L-20", "status": "active", "no_ask_dollars": "0.50",
         "strike_type": "greater", "floor_strike": 20,
         "event_ticker": "EV-G"},
    ]
    theory = StructuralArbTheory(fetch=_fake_fetch({}, fresh))
    res = theory.screen(_ctx(board, run_mode="live"))
    assert len(res.candidates) == 1
    # priced at the FRESH ask, not the stale board ask
    assert res.candidates[0].legs[0].price == pytest.approx(0.41)


def test_price_is_riskless_arithmetic():
    board = [
        m("L-10", event="EV-G", strike_type="greater", floor=10,
          yes_ask=0.40),
        m("L-20", event="EV-G", strike_type="greater", floor=20,
          no_ask=0.50),
    ]
    theory = StructuralArbTheory(fetch=_fake_fetch({}, []))
    run = theory.start(_ctx(board))
    assert not run.needs_judgment
    result = run.finish(dry_run=True)
    assert result.funnel["scored"] == 1
    sc = result.scored[0]
    assert sc.edge.basis == "model"
    assert sc.disposition == "screened"
    cost = sc.candidate.cost
    fee = sum(scan._fee(leg.price) for leg in sc.candidate.legs)
    assert cost + fee <= sc.candidate.min_payout
    expected = 100.0 * (1.0 - cost - fee) / (cost + fee)
    assert sc.edge.pts_net == pytest.approx(expected)
    assert "riskless" in sc.rationale
    assert "Verify every leg" in sc.rationale


def test_exact_value_pathology_is_unusable():
    # Live example: KXSTARSHIPSPACE-26-8.0 declares strike_type='less'
    # with floor=cap=8 while meaning "exactly 8". Both bounds on a
    # one-sided type -> no proof.
    assert scan.yes_set(
        m("S-8.0", strike_type="less", floor=8, cap=8)) is None
    assert scan.yes_set(
        m("S-8.0", strike_type="greater", floor=8, cap=8)) is None
    # The real tails keep working.
    assert scan.yes_set(m("S-2", strike_type="less", cap=2)) is not None


def test_cross_underlying_strikes_never_pair():
    # Two players' hit ladders in one event: numerically nested floors,
    # unrelated quantities. Titles differ once digits are masked.
    serven1 = m("MLB-1", strike_type="greater", floor=0.5, yes_ask=0.01,
                title="Brian Serven: 1+ hits?")
    hernaiz2 = m("MLB-2", strike_type="greater", floor=1.5, no_ask=0.01,
                 title="Darell Hernaiz: 2+ hits?")
    out = scan.scan_events({"EV-1": [serven1, hernaiz2]})
    assert out.findings == ()
    # Same player (same masked title) pairs fine.
    serven2 = m("MLB-2", strike_type="greater", floor=1.5, no_ask=0.01,
                title="Brian Serven: 2+ hits?")
    out2 = scan.scan_events({"EV-1": [serven1, serven2]})
    assert len(out2.findings) == 1


def test_letters_in_strike_segment_never_pair():
    # KXNCAAFTEAMTOTAL-style: the tail carries identity (SJSU20/USC28),
    # not just a threshold — even with identical titles they must split.
    a = m("TT-SJSU20", strike_type="greater", floor=19.5, yes_ask=0.10)
    b = m("TT-USC28", strike_type="greater", floor=27.5, no_ask=0.10)
    out = scan.scan_events({"EV-1": [a, b]})
    assert out.findings == ()


def test_refresh_finding_sheds_dead_basket_legs():
    ms = [
        m("N-1", strike_type="less", cap=10, no_ask=0.30),
        m("N-2", strike_type="between", floor=11, cap=19, no_ask=0.30),
        m("N-3", strike_type="greater", floor=20, no_ask=0.30),
    ]
    out = scan.scan_events({"EV-1": ms})
    f = out.findings[0]
    # MID's NO is now expensive; LO and HI still clear on their own.
    fresh = {
        "N-1": m("N-1", strike_type="less", cap=10, no_ask=0.30),
        "N-2": m("N-2", strike_type="between", floor=11, cap=19,
                 no_ask=0.995),
        "N-3": m("N-3", strike_type="greater", floor=20, no_ask=0.30),
    }
    nf = scan.refresh_finding(f, fresh)
    assert nf is not None
    assert {leg.market.ticker for leg in nf.legs} == {"N-1", "N-3"}
    assert nf.min_payout == 1.0 and nf.max_payout == 2.0
    # Down to one live leg -> dead.
    fresh["N-3"] = m("N-3", strike_type="greater", floor=20, no_ask=0.995)
    assert scan.refresh_finding(f, fresh) is None


def test_refresh_finding_nested_pair_needs_both_legs():
    sup = m("L-10", strike_type="greater", floor=10, yes_ask=0.40)
    sub = m("L-20", strike_type="greater", floor=20, no_ask=0.50)
    out = scan.scan_events({"EV-1": [sup, sub]})
    f = out.findings[0]
    assert scan.refresh_finding(f, {"L-10": sup, "L-20": sub}) is not None
    assert scan.refresh_finding(f, {"L-10": sup}) is None  # missing quote


def test_flag_persists_to_theory_facts(tmp_path):
    conn = tdb.connect(tmp_path / "t.db")
    tdb.init_db(conn)
    theories_db.register(conn, "structural_arb", "Structural Arb",
                         "theories/structural_arb")
    calls: list[str] = []

    def fetch(url, params=None):
        calls.append(url)
        return {"event": {"mutually_exclusive": True}}

    board = [m(f"A{j}", event="EV-ME", strike_type="structured",
               no_ask=0.30) for j in range(3)]
    theory = StructuralArbTheory(fetch=fetch)
    ctx = TheoryContext(conn=conn, board=board, now=NOW,
                        run_id="exp/t", run_mode="backtest")
    res = theory.screen(ctx)
    assert len(res.candidates) == 1
    assert len(calls) == 1
    _flag_cache.clear()                      # kill the session cache
    res2 = theory.screen(ctx)
    assert len(res2.candidates) == 1
    assert len(calls) == 1                   # served from theory_facts
    conn.close()


def test_flag_fetch_cap_reported():
    board = []
    for i in range(MAX_FLAG_FETCHES + 3):
        for j in range(2):
            board.append(m(f"E{i}M{j}", event=f"EV-{i}",
                           strike_type="structured", no_ask=0.20))
    theory = StructuralArbTheory(fetch=_fake_fetch(
        {f"EV-{i}": False for i in range(MAX_FLAG_FETCHES + 3)}, []))
    res = theory.screen(_ctx(board))
    assert res.gate_removed.get("flag_fetch_capped") == 3
    assert res.gate_removed.get("not_mutually_exclusive") == MAX_FLAG_FETCHES


# ------------------------------------------------------------- depth gate
# v2: top-of-book existence and fillable size are different claims (opps
# 9248 and 9309 both died 0.3-0.5 contracts deep). Live pricing reads the
# orderbook for every finalist leg and rejects baskets whose fillable
# riskless profit is dust.

def _depth_board():
    return [
        m("L-10", event="EV-G", strike_type="greater", floor=10,
          yes_ask=0.40),
        m("L-20", event="EV-G", strike_type="greater", floor=20,
          no_ask=0.50),
    ]


_DEPTH_FRESH = [
    {"ticker": "L-10", "status": "active", "yes_ask_dollars": "0.41",
     "strike_type": "greater", "floor_strike": 10, "event_ticker": "EV-G"},
    {"ticker": "L-20", "status": "active", "no_ask_dollars": "0.50",
     "strike_type": "greater", "floor_strike": 20, "event_ticker": "EV-G"},
]


def test_implied_ask_ladder_converts_opposite_bids():
    fp = {"yes_dollars": [["0.5000", "0.47"], ["0.0200", "40.00"]],
          "no_dollars": [["0.5900", "5.00"], ["0.0100", "50.00"]]}
    yes = scan.implied_ask_ladder(fp, "yes")
    no = scan.implied_ask_ladder(fp, "no")
    assert [(round(p, 4), s) for p, s in yes] == [(0.41, 5.0), (0.99, 50.0)]
    assert [(round(p, 4), s) for p, s in no] == [(0.5, 0.47), (0.98, 40.0)]


def test_implied_ask_ladder_missing_side_is_empty():
    assert scan.implied_ask_ladder({"yes_dollars": []}, "yes") == []
    assert scan.implied_ask_ladder(None, "no") == []


def test_fillable_floor_stops_where_book_uncrosses():
    a = [(0.41, 5.0), (0.99, 50.0)]
    b = [(0.50, 0.47), (0.98, 40.0)]
    baskets, profit = scan.fillable_floor([a, b], 1.0)
    per = 1.0 - (0.41 + 0.50 + scan._fee(0.41) + scan._fee(0.50))
    assert baskets == pytest.approx(0.47)
    assert profit == pytest.approx(0.47 * per)


def test_fillable_floor_walks_deeper_riskless_levels():
    a = [(0.40, 5.0), (0.41, 5.0)]
    b = [(0.50, 5.0), (0.51, 5.0)]
    baskets, profit = scan.fillable_floor([a, b], 1.0)
    lvl1 = 1.0 - (0.40 + 0.50 + scan._fee(0.40) + scan._fee(0.50))
    lvl2 = 1.0 - (0.41 + 0.51 + scan._fee(0.41) + scan._fee(0.51))
    assert baskets == pytest.approx(10.0)
    assert profit == pytest.approx(5 * lvl1 + 5 * lvl2)


def test_fillable_floor_empty_leg_is_zero():
    assert scan.fillable_floor([[(0.4, 5.0)], []], 1.0) == (0.0, 0.0)


def test_price_live_rejects_depth_dust_basket():
    orderbooks = {
        "L-10": {"yes_dollars": [["0.1000", "5.00"]],
                 "no_dollars": [["0.5900", "200.00"]]},
        "L-20": {"yes_dollars": [["0.5000", "0.47"], ["0.0200", "40.00"]],
                 "no_dollars": [["0.0100", "5.00"]]},
    }
    theory = StructuralArbTheory(
        fetch=_fake_fetch({}, _DEPTH_FRESH, orderbooks))
    run = theory.start(_ctx(_depth_board(), run_mode="live"))
    result = run.finish(dry_run=True)
    assert len(result.scored) == 1
    sc = result.scored[0]
    assert sc.disposition == "rejected"
    assert "fillable" in sc.rationale


def test_price_live_screens_deep_book_and_notes_depth():
    orderbooks = {
        "L-10": {"yes_dollars": [["0.1000", "5.00"]],
                 "no_dollars": [["0.5900", "200.00"]]},
        "L-20": {"yes_dollars": [["0.5000", "200.00"]],
                 "no_dollars": [["0.0100", "5.00"]]},
    }
    theory = StructuralArbTheory(
        fetch=_fake_fetch({}, _DEPTH_FRESH, orderbooks))
    run = theory.start(_ctx(_depth_board(), run_mode="live"))
    result = run.finish(dry_run=True)
    sc = result.scored[0]
    assert sc.disposition == "screened"
    assert "fillable" in sc.rationale


def test_price_backtest_never_fetches_orderbooks():
    # orderbooks=None makes any orderbook fetch an AssertionError; the
    # backtest path prices the snapshot and must not touch the book.
    theory = StructuralArbTheory(fetch=_fake_fetch({}, []))
    run = theory.start(_ctx(_depth_board(), run_mode="backtest"))
    result = run.finish(dry_run=True)
    sc = result.scored[0]
    assert sc.disposition == "screened"
    assert "UNVERIFIED" not in sc.rationale


def test_price_live_orderbook_failure_records_unverified():
    orderbooks = {
        "L-10": {"yes_dollars": [["0.1000", "5.00"]],
                 "no_dollars": [["0.5900", "200.00"]]},
        # L-20 missing: fetch raises RuntimeError
    }
    theory = StructuralArbTheory(
        fetch=_fake_fetch({}, _DEPTH_FRESH, orderbooks))
    run = theory.start(_ctx(_depth_board(), run_mode="live"))
    result = run.finish(dry_run=True)
    sc = result.scored[0]
    assert sc.disposition == "screened"
    assert "UNVERIFIED" in sc.rationale


def test_price_live_orderbook_budget_caps_fetches(monkeypatch):
    import theories.structural_arb.theory as sa_theory
    monkeypatch.setattr(sa_theory, "MAX_ORDERBOOK_FETCHES", 1)
    orderbooks = {
        "L-10": {"yes_dollars": [["0.1000", "5.00"]],
                 "no_dollars": [["0.5900", "200.00"]]},
        "L-20": {"yes_dollars": [["0.5000", "200.00"]],
                 "no_dollars": [["0.0100", "5.00"]]},
    }
    theory = StructuralArbTheory(
        fetch=_fake_fetch({}, _DEPTH_FRESH, orderbooks))
    run = theory.start(_ctx(_depth_board(), run_mode="live"))
    result = run.finish(dry_run=True)
    sc = result.scored[0]
    assert sc.disposition == "screened"
    assert "UNVERIFIED" in sc.rationale
