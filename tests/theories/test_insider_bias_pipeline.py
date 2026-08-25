"""The mechanical stages, and the blind-payload guarantee in particular."""

import json

import pytest

from theories.insider_bias.insider_judgment import pipeline
from tools.domain import Candidate, Leg, Market


def _cand(ticker, event, series="KXTHING", **kw):
    base = {
        "platform": "kalshi", "is_open": True,
        "ticker": ticker, "event_ticker": event, "series_ticker": series,
        "title": f"title for {ticker}", "rules_primary": "rules text",
        "close_time": "2026-09-01T00:00:00Z",
        "yes_bid": 0.80, "yes_ask": 0.82, "no_bid": 0.18, "no_ask": 0.20,
        "mid": 0.81, "spread": 0.02, "last_price": 0.81, "volume": 900.0,
    }
    base.update(kw)
    market = Market.from_mapping(base)
    return Candidate(legs=(Leg(market=market, side="yes",
                              price=base["yes_ask"]),),
                     days_to_close=5.0)


# --- dedup ------------------------------------------------------------


def test_dedupe_keeps_one_per_event_in_order():
    cands = [_cand("A-1", "A"), _cand("A-2", "A"), _cand("B-1", "B")]
    out = pipeline.dedupe_by_event(cands)
    assert [c.ticker for c in out] == ["A-1", "B-1"]


def test_dedupe_falls_back_to_ticker_when_event_missing():
    # Two independently-built candidates with no event_ticker: Candidate.key
    # falls back to the market ticker, so both share one key and dedupe.
    c = _cand("A-1", None)
    assert len(pipeline.dedupe_by_event([c, _cand("A-1", None)])) == 1


# --- the blind guarantee ----------------------------------------------


def test_payload_carries_no_price_fields():
    cands = [_cand("A-1", "A"), _cand("A-2", "A")]
    events = pipeline.dedupe_by_event(cands)
    payload = pipeline.build_blind_payload(events, cands)
    blob = json.dumps(payload)
    for banned in pipeline.BANNED_KEYS:
        assert f'"{banned}"' not in blob, banned


def test_payload_still_carries_what_judgment_needs():
    cands = [_cand("A-1", "A"), _cand("A-2", "A")]
    payload = pipeline.build_blind_payload(pipeline.dedupe_by_event(cands),
                                           cands)
    assert len(payload) == 1
    e = payload[0]
    assert e["event_ticker"] == "A"
    assert e["title"] == "title for A-1"
    assert e["close_time"] == "2026-09-01T00:00:00Z"
    # Both sibling markets, with their rules -- that is what gets judged.
    assert [m["ticker"] for m in e["markets"]] == ["A-1", "A-2"]
    assert e["markets"][0]["rules_primary"] == "rules text"


def test_whitelist_drops_a_newly_added_price_field():
    # The reason this is a whitelist: a blacklist starts leaking silently the
    # day the Kalshi client grows a field nobody thought to ban. A Market is
    # frozen/slotted, so a hypothetical unmodeled field can only arrive the
    # way an unrecognized wire field actually would -- inside raw, never as
    # a new top-level attribute.
    c = _cand("A-1", "A", raw={"some_new_yes_ask_variant": 0.99})
    payload = pipeline.build_blind_payload([c], [c])
    assert "some_new_yes_ask_variant" not in json.dumps(payload)


def test_assert_blind_raises_on_a_leaked_price():
    leaky = [{"event_ticker": "A", "yes_ask": 0.82}]
    with pytest.raises(pipeline.BlindPayloadError, match="yes_ask"):
        pipeline.assert_blind(leaky)


def test_assert_blind_catches_a_price_nested_deeper():
    leaky = [{"event_ticker": "A", "markets": [{"ticker": "A-1",
                                                "mid": 0.5}]}]
    with pytest.raises(pipeline.BlindPayloadError, match="mid"):
        pipeline.assert_blind(leaky)


def test_assert_blind_passes_a_clean_payload():
    pipeline.assert_blind([{"event_ticker": "A", "title": "t",
                            "markets": [{"ticker": "A-1"}]}])


def test_assert_blind_does_not_trip_on_prose_containing_a_banned_word():
    # Resolution text may legitimately discuss a "spread"; only a JSON *key*
    # is a leak.
    pipeline.assert_blind([{"event_ticker": "A",
                            "title": "Will the spread of flu exceed X?",
                            "markets": [{"rules_primary": "the mid point"}]}])


# --- the funnel -------------------------------------------------------


def test_run_mechanical_stages_reports_the_whole_funnel(monkeypatch):
    board = [_cand("A-1", "A", "KXBTCD"), _cand("B-1", "B", "KXTHING")]
    monkeypatch.setattr(pipeline.screen, "screen",
                        lambda markets, now=None: markets)
    out = pipeline.run_mechanical_stages(board)
    assert out["board_markets"] == 2
    assert out["screened_markets"] == 2
    assert out["events"] == 2
    assert out["gated_out"] == 1          # KXBTCD is a crypto strike ladder
    assert out["survivors"] == 1
    assert out["gate_counts"]["future price: crypto"] == 1
    assert [e["event_ticker"] for e in out["payload"]] == ["B"]


def test_funnel_payload_is_blind(monkeypatch):
    board = [_cand("B-1", "B", "KXTHING")]
    monkeypatch.setattr(pipeline.screen, "screen",
                        lambda markets, now=None: markets)
    out = pipeline.run_mechanical_stages(board)
    assert "yes_ask" not in json.dumps(out["payload"])
