import pytest

from tools.kalshi import markets

RAW = {
    "ticker": "KXOAIANTH-40-ANTH",
    "event_ticker": "KXOAIANTH-40",
    "title": "Will OpenAI or Anthropic IPO first?",
    "status": "active",
    "yes_bid_dollars": "0.9200",
    "yes_ask_dollars": "0.9300",
    "no_bid_dollars": "0.0700",
    "no_ask_dollars": "0.0800",
    "last_price_dollars": "0.9300",
    "volume_fp": "175581.15",
    "volume_24h_fp": "1200.00",
    "open_interest_fp": "40225.58",
    "close_time": "2040-01-01T04:59:00Z",
    "open_time": "2025-08-07T12:00:00Z",
    "result": "",
    "rules_primary": "If Anthropic confirms an IPO first, resolves Yes.",
}


def test_normalize_parses_decimal_dollar_strings():
    m = markets.normalize(RAW)
    assert m["yes_bid"] == pytest.approx(0.92)
    assert m["yes_ask"] == pytest.approx(0.93)
    assert m["last_price"] == pytest.approx(0.93)


def test_normalize_parses_fp_sizes():
    m = markets.normalize(RAW)
    assert m["volume"] == pytest.approx(175581.15)
    assert m["open_interest"] == pytest.approx(40225.58)


def test_normalize_derives_spread_and_mid():
    m = markets.normalize(RAW)
    assert m["spread"] == pytest.approx(0.01)
    assert m["mid"] == pytest.approx(0.925)


def test_normalize_marks_active_markets_open():
    assert markets.normalize(RAW)["is_open"] is True


def test_normalize_marks_finalized_markets_closed():
    raw = dict(RAW, status="finalized", result="yes")
    m = markets.normalize(raw)
    assert m["is_open"] is False
    assert m["result"] == "yes"


def test_normalize_turns_blank_result_into_none():
    assert markets.normalize(RAW)["result"] is None


def test_normalize_keeps_resolution_rules():
    # Stage 2 research depends on this text; it must survive normalization.
    assert "Anthropic" in markets.normalize(RAW)["rules_primary"]


def test_normalize_keeps_the_raw_payload():
    assert markets.normalize(RAW)["raw"]["volume_fp"] == "175581.15"


def test_normalize_tolerates_missing_optional_fields():
    raw = {"ticker": "X", "status": "active"}
    m = markets.normalize(raw)
    assert m["yes_bid"] is None
    assert m["spread"] is None
    assert m["mid"] is None
    assert m["volume"] is None


def test_normalize_raises_without_a_ticker():
    # Fail loudly on schema drift rather than emitting a useless row.
    with pytest.raises(ValueError, match="ticker"):
        markets.normalize({"status": "active"})


def test_normalize_raises_on_unparseable_price():
    with pytest.raises(ValueError, match="yes_bid_dollars"):
        markets.normalize(dict(RAW, yes_bid_dollars="not-a-number"))


def test_list_open_paginates_and_flattens(monkeypatch):
    pages = [
        {
            "events": [
                {
                    "event_ticker": "E1",
                    "series_ticker": "S1",
                    "title": "Event one",
                    "markets": [dict(RAW, ticker="A"), dict(RAW, ticker="B")],
                }
            ],
            "cursor": "next",
        },
        {
            "events": [
                {
                    "event_ticker": "E2",
                    "series_ticker": "S2",
                    "title": "Event two",
                    "markets": [dict(RAW, ticker="C")],
                }
            ],
            "cursor": "",
        },
    ]
    calls = {"n": 0}

    def fake_get(url, params=None, **kwargs):
        page = pages[calls["n"]]
        calls["n"] += 1
        return page

    monkeypatch.setattr(markets, "get_json", fake_get)
    result = markets.list_open()
    assert [m["ticker"] for m in result] == ["A", "B", "C"]
    assert result[0]["series_ticker"] == "S1"
    assert result[2]["series_ticker"] == "S2"


def test_list_open_respects_max_pages(monkeypatch):
    monkeypatch.setattr(
        markets, "get_json",
        lambda *a, **k: {"events": [{"markets": [dict(RAW)]}],
                         "cursor": "always-more"},
    )
    result = markets.list_open(max_pages=3)
    assert len(result) == 3


def test_quotes_maps_tickers_to_markets(monkeypatch):
    monkeypatch.setattr(
        markets, "get_json",
        lambda *a, **k: {"markets": [dict(RAW, ticker="A"),
                                     dict(RAW, ticker="B")]},
    )
    result = markets.quotes(["A", "B"])
    assert set(result) == {"A", "B"}
    assert result["A"]["yes_ask"] == pytest.approx(0.93)


def test_quotes_returns_empty_for_no_tickers(monkeypatch):
    assert markets.quotes([]) == {}


@pytest.mark.network
def test_live_open_markets_have_expected_shape():
    result = markets.list_open(limit=20, max_pages=1)
    assert result, "Kalshi returned no open markets"
    sample = result[0]
    assert sample["platform"] == "kalshi"
    assert sample["ticker"]
    assert sample["is_open"] is True
