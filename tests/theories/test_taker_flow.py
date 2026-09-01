from datetime import datetime, timedelta, timezone

import pytest

from theories.taker_flow import backtest, features
from theories.taker_flow.theory import TakerFlowTheory, flow_features, is_liquid
from tools.domain import Market
from tools.theory import TheoryContext

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def market(ticker="KXTEST-26SEP01-ABC", **kw):
    base = dict(
        platform="kalshi",
        ticker=ticker,
        yes_ask=0.40,
        no_ask=0.62,
        spread=0.02,
        volume_24h=5000.0,
        open_interest=2000.0,
        is_open=True,
        status="active",
        close_time=(NOW + timedelta(days=5)).isoformat().replace("+00:00", "Z"),
    )
    base.update(kw)
    return Market(**base)


def raw_trade(side, price=0.40, count=10.0, minutes_ago=60):
    stamp = (NOW - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    return {
        "ticker": "KXTEST-26SEP01-ABC",
        "trade_id": f"t{side}{minutes_ago}{count}",
        "created_time": stamp,
        "taker_side": side,
        "taker_outcome_side": side,
        "taker_book_side": "bid" if side == "yes" else "ask",
        "count_fp": str(count),
        "yes_price_dollars": f"{price:.4f}",
        "no_price_dollars": f"{1 - price:.4f}",
        "is_block_trade": False,
    }


def feed(trades):
    def fetch(url, params):
        return {"trades": trades, "cursor": ""}

    return fetch


# ---- the structural split ----------------------------------------------

def test_numeric_strikes_are_broad_based():
    assert features.is_single_name("KXHIGHTSFO-26AUG01-T73") is False
    assert features.is_single_name("KXLOWTPHIL-26JUL15-B74.5") is False
    assert features.is_single_name("KXNFLWINS-27BAL-12") is False


def test_named_strikes_are_single_name():
    assert features.is_single_name("KXPRESNOMD-28-KH") is True
    assert features.is_single_name("KXALIENS-27") is True


def test_event_key_groups_siblings_of_one_event():
    """Clustering treats one event's strikes as a single draw."""
    assert backtest.event_key("KXHIGHTSFO-26AUG01-T73") == "KXHIGHTSFO-26AUG01"
    assert backtest.event_key("KXHIGHTSFO-26AUG01-T75") == "KXHIGHTSFO-26AUG01"


def test_flow_bucket_splits_at_the_measured_discontinuity():
    assert features.flow_bucket(0.89) == "strong"
    assert features.flow_bucket(0.90) == "extreme"
    assert features.flow_bucket(-0.95) == "extreme"


# ---- the replay is lookahead-free --------------------------------------

def test_build_records_reads_nothing_after_the_decision_point():
    """The whole basis of a tier A replay: the window stops at the buffer.

    A trade one hour before resolution is 23 hours PAST a 24h decision
    point. If it leaked in, the imbalance would be built from information
    the decision could not have had.
    """
    resolved = "2026-08-20T00:00:00Z"
    def t(hours_before, side):
        stamp = (datetime(2026, 8, 20, tzinfo=timezone.utc)
                 - timedelta(hours=hours_before))
        return {"t": stamp.isoformat().replace("+00:00", "Z"),
                "s": side, "c": 10.0, "p": 0.5, "b": False}

    rows = [{
        "ticker": "KXTEST-26AUG20-ABC",
        "resolved_at": resolved,
        "result": "yes",
        # 30 no-trades safely inside the window, then 30 yes-trades that
        # land AFTER the decision point and must be ignored entirely.
        "trades": ([t(48, "no")] * 30) + ([t(1, "yes")] * 30),
    }]
    recs = backtest.build_records(rows, buffer_hours=24.0, lookback_days=7.0,
                                  min_trades=20)
    assert len(recs) == 1
    assert recs[0]["imbalance"] == pytest.approx(-1.0)
    assert recs[0]["n_trades"] == 30


def test_build_records_drops_markets_with_too_little_flow():
    rows = [{
        "ticker": "KXTEST-26AUG20-ABC",
        "resolved_at": "2026-08-20T00:00:00Z",
        "result": "yes",
        "trades": [{"t": "2026-08-18T00:00:00Z", "s": "yes", "c": 1.0,
                    "p": 0.5, "b": False}] * 5,
    }]
    assert backtest.build_records(rows, min_trades=20) == []


def test_follow_pnl_pays_out_on_the_side_the_flow_took():
    yes_flow_won = {"imbalance": 0.95, "price": 0.40, "won_yes": 1}
    yes_flow_lost = {"imbalance": 0.95, "price": 0.40, "won_yes": 0}
    no_flow_won = {"imbalance": -0.95, "price": 0.40, "won_yes": 0}
    assert backtest.follow_pnl(yes_flow_won) == pytest.approx(60.0)
    assert backtest.follow_pnl(yes_flow_lost) == pytest.approx(-40.0)
    # buying NO at 0.60 and winning pays 40 points
    assert backtest.follow_pnl(no_flow_won) == pytest.approx(40.0)


def test_evaluate_clusters_by_event_not_by_row():
    """Fifty siblings of one event must not read as fifty draws."""
    recs = [
        {"imbalance": 0.95, "price": 0.5, "won_yes": 1,
         "event": "E1", "day": "2026-08-20"}
        for _ in range(50)
    ]
    out = backtest.evaluate(recs, threshold=0.6)
    assert out["n"] == 50
    assert out["n_clusters"] == 1


# ---- the live screen ----------------------------------------------------

def test_illiquid_markets_are_screened_out():
    assert is_liquid(market(), NOW) is True
    assert is_liquid(market(spread=0.20), NOW) is False
    assert is_liquid(market(volume_24h=10.0), NOW) is False
    assert is_liquid(market(open_interest=1.0), NOW) is False
    assert is_liquid(market(is_open=False), NOW) is False


def test_markets_closing_within_the_decision_buffer_are_excluded():
    """The replay decides 24h out, so a market closing sooner is untradeable
    on this theory's own terms."""
    soon = market(close_time=(NOW + timedelta(hours=6)).isoformat().replace("+00:00", "Z"))
    assert is_liquid(soon, NOW) is False


def test_flow_features_needs_enough_trades_in_the_window():
    thin = feed([raw_trade("yes") for _ in range(5)])
    assert flow_features("KXTEST-26SEP01-ABC", NOW, thin) is None


def test_flow_features_ignores_trades_older_than_the_lookback():
    old = feed([raw_trade("yes", minutes_ago=60 * 24 * 30) for _ in range(40)])
    assert flow_features("KXTEST-26SEP01-ABC", NOW, old) is None


def test_screen_takes_the_aggressor_side_and_prices_at_that_ask():
    theory = TakerFlowTheory(fetch=feed([raw_trade("no") for _ in range(40)]))
    ctx = TheoryContext(conn=None, board=[market()], now=NOW)
    result = theory.screen(ctx)
    assert len(result.candidates) == 1
    leg = result.candidates[0].legs[0]
    assert leg.side == "no"
    assert leg.price == pytest.approx(0.62)


def test_balanced_flow_produces_no_candidate():
    balanced = [raw_trade("yes", minutes_ago=i) for i in range(20)]
    balanced += [raw_trade("no", minutes_ago=i) for i in range(20)]
    theory = TakerFlowTheory(fetch=feed(balanced))
    ctx = TheoryContext(conn=None, board=[market()], now=NOW)
    result = theory.screen(ctx)
    assert result.candidates == ()
    assert result.funnel["below_threshold"] == 1


def test_price_records_the_bucket_and_a_model_basis():
    theory = TakerFlowTheory(fetch=feed([raw_trade("yes") for _ in range(40)]))
    ctx = TheoryContext(conn=None, board=[market()], now=NOW)
    cands = list(theory.screen(ctx).candidates)
    scored = theory.price(ctx, cands)
    assert len(scored) == 1
    sc = scored[0]
    assert sc.edge.basis == "model"
    assert sc.confidence == "extreme"
    # extreme's measured gross, net of the fee at this ask
    assert sc.edge.pts_gross == pytest.approx(4.29)
    assert sc.edge.pts_net < sc.edge.pts_gross
    assert sc.disposition == "screened"


def test_extra_carries_flow_bucket_so_the_slice_can_route_it():
    """`extreme-imbalance` matches on extra.flow_bucket; a row without it
    is invisible to the slice and silently ranks on the parent."""
    theory = TakerFlowTheory(fetch=feed([raw_trade("yes") for _ in range(40)]))
    ctx = TheoryContext(conn=None, board=[market()], now=NOW)
    scored = theory.price(ctx, list(theory.screen(ctx).candidates))
    assert scored[0].extra["flow_bucket"] == "extreme"


def test_nothing_in_the_decision_path_uses_judgment():
    assert TakerFlowTheory.uses_llm_judgment is False
    assert TakerFlowTheory.prompts == {}


# ---- v2: a position must be able to pay what is claimed ----------------

def test_an_ask_of_one_is_not_a_position():
    """Paying 1.00 for a contract that pays at most 1.00 cannot profit.

    This is arithmetic, not a liquidity judgement -- which is why it is a
    screen exclusion rather than the price cap the theory deliberately
    avoids.
    """
    theory = TakerFlowTheory(fetch=feed([raw_trade("yes") for _ in range(40)]))
    ctx = TheoryContext(conn=None, board=[market(yes_ask=1.0)], now=NOW)
    result = theory.screen(ctx)
    assert result.candidates == ()
    assert result.funnel["unpayable_ask"] == 1


def test_claimed_edge_never_exceeds_what_the_contract_can_pay():
    """A 4.29-point claim on a 0.97 ask would imply a probability above 1."""
    theory = TakerFlowTheory(fetch=feed([raw_trade("yes") for _ in range(40)]))
    ctx = TheoryContext(conn=None, board=[market(yes_ask=0.97)], now=NOW)
    scored = theory.price(ctx, list(theory.screen(ctx).candidates))
    sc = scored[0]
    assert sc.edge.pts_gross == pytest.approx(3.0)      # (1 - 0.97) * 100
    assert sc.edge.model_prob <= 1.0


def test_headroom_cap_leaves_normal_prices_untouched():
    theory = TakerFlowTheory(fetch=feed([raw_trade("yes") for _ in range(40)]))
    ctx = TheoryContext(conn=None, board=[market(yes_ask=0.40)], now=NOW)
    scored = theory.price(ctx, list(theory.screen(ctx).candidates))
    assert scored[0].edge.pts_gross == pytest.approx(4.29)
