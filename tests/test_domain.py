from dataclasses import FrozenInstanceError, asdict, fields

import pytest

from tools.domain import (Candidate, Edge, Leg, Market, PolymarketMarket,
                          ScoredCandidate, ScreenResult, Verdict)


def mk(ticker="KXT-26", **over):
    base = dict(platform="kalshi", ticker=ticker, title="t", yes_ask=0.8,
                no_ask=0.25, mid=0.78, spread=0.04, volume=900.0,
                is_open=True, close_time="2026-09-01T00:00:00Z",
                event_ticker="KXT", series_ticker="KXT",
                raw={"ticker": ticker})
    base.update(over)
    return Market(**base)


def leg(ticker="KXT-26", side="yes", price=0.8):
    return Leg(market=mk(ticker), side=side, price=price)


def single(**over):
    return Candidate(legs=(leg(),), days_to_close=3.0, **over)


def basket():
    return Candidate(legs=(leg("KXB-26", "yes", 0.4),
                           leg("KXA-26", "no", 0.5)), days_to_close=3.0)


# --- Market -----------------------------------------------------------


def test_market_requires_a_ticker():
    with pytest.raises(ValueError, match="ticker"):
        mk(ticker="")


def test_market_is_frozen():
    with pytest.raises(FrozenInstanceError):
        mk().ticker = "X"


def test_market_raw_is_passed_through_by_identity_and_excluded_from_eq():
    payload = {"ticker": "KXT-26", "anything": [1, 2]}
    a, b = mk(raw=payload), mk(raw={})
    assert a.raw is payload
    assert a == b            # compare=False on raw


def test_market_from_mapping_round_trips():
    m = mk()
    assert Market.from_mapping(asdict(m)) == m


def test_market_from_mapping_ignores_unknown_keys():
    m = Market.from_mapping({"platform": "kalshi", "ticker": "KXT-26",
                             "some_future_field": 1})
    assert m.ticker == "KXT-26"


def test_polymarket_market_requires_an_id_and_keeps_lists():
    with pytest.raises(ValueError, match="market_id"):
        PolymarketMarket(platform="polymarket", market_id="")
    p = PolymarketMarket(platform="polymarket", market_id="0xabc",
                         outcomes=["Yes", "No"], outcome_prices=[0.6, 0.4])
    assert p.outcomes == ["Yes", "No"]      # list, not tuple


# --- Leg / Candidate --------------------------------------------------


def test_leg_validates_side_and_price():
    with pytest.raises(ValueError, match="side"):
        Leg(market=mk(), side="over", price=0.5)
    for bad in (40, float("nan"), True, -0.1, 1.5, "0.5", None):
        with pytest.raises(ValueError, match="decimal dollars|price"):
            Leg(market=mk(), side="yes", price=bad)


def test_candidate_needs_a_leg():
    with pytest.raises(ValueError, match="leg"):
        Candidate(legs=(), days_to_close=1.0)


@pytest.mark.parametrize("bad", [0, -1.0, None, "1.0", True, float("nan")])
def test_candidate_rejects_a_nonsense_max_payout(bad):
    """Mirrors ledger.record_basket's own check: a basket that can never
    pay anything is not a position."""
    with pytest.raises(ValueError, match="max_payout"):
        Candidate(legs=(leg(),), days_to_close=1.0, max_payout=bad)


def test_single_leg_conveniences():
    c = single()
    assert (c.ticker, c.fav_side, c.entry_price) == ("KXT-26", "yes", 0.8)
    assert c.is_basket is False
    assert c.cost == pytest.approx(0.8)
    assert c.key == "KXT"            # event_ticker wins
    assert c.event_key == "KXT"
    assert c.title == "t"
    assert c.max_payout == 1.0


def test_key_falls_back_to_ticker_without_an_event():
    c = Candidate(legs=(Leg(market=mk(event_ticker=None), side="yes",
                            price=0.8),), days_to_close=1.0)
    assert c.key == "KXT-26"


def test_basket_conveniences_raise_rather_than_guess():
    """Closes the multi-leg spec's deferred success criterion 4: a
    single-leg convenience on a basket must raise, never silently return
    leg 0 and drop the rest."""
    b = basket()
    assert b.is_basket is True
    assert b.cost == pytest.approx(0.9)
    assert b.key == "KXA-26+KXB-26"  # sorted leg tickers, order-independent
    for prop in ("ticker", "entry_price", "fav_side", "title", "event_key"):
        with pytest.raises(ValueError, match="basket"):
            getattr(b, prop)


def test_basket_key_is_independent_of_leg_order():
    a = Candidate(legs=(leg("KXA-26", "no", 0.5), leg("KXB-26", "yes", 0.4)),
                  days_to_close=3.0)
    assert a.key == basket().key


# --- Edge / Verdict / ScoredCandidate ---------------------------------


def test_edge_validates_basis():
    with pytest.raises(ValueError, match="basis"):
        Edge(pts_net=1.0, basis="vibes")


def test_edge_from_bucket_measured_and_prior():
    from tools.sizing import fee_pts
    rates = {"strong": {"n": 20, "win_rate": 0.9, "mean_entry_price": 0.8}}
    priors = {"strong": 4.0, "weak": 0.0}

    e = Edge.from_bucket("strong", 0.8, rates, priors)
    assert e.basis == "measured"
    assert e.model_prob == pytest.approx(0.9)
    assert e.pts_net == pytest.approx((0.9 - 0.8) * 100.0 - fee_pts(0.8))

    p = Edge.from_bucket("weak", 0.8, rates, priors)
    assert (p.basis, p.pts_net, p.model_prob) == ("prior", 0.0, None)


def test_edge_from_bucket_falls_back_to_prior_below_min_n():
    rates = {"strong": {"n": 2, "win_rate": 1.0, "mean_entry_price": 0.8}}
    e = Edge.from_bucket("strong", 0.8, rates, {"strong": 4.0})
    assert e.basis == "prior" and e.pts_net == pytest.approx(4.0)


def test_verdict_requires_a_bucket_and_carries_no_number():
    """CLAUDE.md's 'never state a probability you introspected', as a
    property of the type: a judge has no numeric field to answer in."""
    with pytest.raises(ValueError, match="bucket"):
        Verdict(bucket="  ")
    assert {f.name for f in fields(Verdict)} == {"bucket", "rationale"}


def test_scored_candidate_validates_disposition():
    with pytest.raises(ValueError, match="disposition"):
        ScoredCandidate(candidate=single(), edge=Edge(1.0, "model"),
                        disposition="maybe")


def test_scored_candidate_defaults_to_screened():
    sc = ScoredCandidate(candidate=single(), edge=Edge(1.0, "model"))
    assert sc.disposition == "screened"
    assert sc.judged_blind is None


def test_screen_result_defaults():
    sr = ScreenResult(candidates=(single(),))
    assert sr.funnel == {} and sr.gate_removed == {}


def test_slots_prevent_attribute_injection():
    """The point of slots=True: the {**c, 'new_key': ...} pattern these
    types replace cannot come back as attribute injection."""
    with pytest.raises((AttributeError, TypeError)):
        object.__setattr__(mk(), "new_key", 1)
