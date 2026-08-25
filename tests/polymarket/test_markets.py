import pytest

from tools.polymarket import markets

RAW = {
    "id": "2063134",
    "conditionId": "0x7d0aaf81bbd3fd73b6a1651cce08a452c0cbf9c0",
    "question": "Will Adanech Abiebie be the next PM of Ethiopia?",
    "slug": "will-adanech-abiebie-be-next-pm",
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["0.006", "0.994"]',
    "bestBid": 0.005,
    "bestAsk": 0.007,
    "volumeNum": 83447614.07,
    "liquidityNum": 19441.20,
    "endDate": "2026-06-01T00:00:00Z",
    "closed": False,
    "description": "General elections are scheduled for June 1, 2026.",
}


def test_normalize_parses_json_encoded_string_arrays():
    m = markets.normalize(RAW)
    assert m.outcomes == ["Yes", "No"]
    assert m.outcome_prices == [pytest.approx(0.006), pytest.approx(0.994)]


def test_normalize_uses_condition_id_as_market_id():
    assert markets.normalize(RAW).market_id == RAW["conditionId"]


def test_normalize_extracts_implied_yes_probability():
    assert markets.normalize(RAW).implied_prob_yes == pytest.approx(0.006)


def test_normalize_handles_reversed_outcome_order():
    # Not every market lists Yes first — reading the wrong index silently
    # inverts the probability, so this must be exercised explicitly.
    raw = dict(RAW, outcomes='["No", "Yes"]', outcomePrices='["0.994", "0.006"]')
    m = markets.normalize(raw)
    assert m.implied_prob_yes == pytest.approx(0.006)


def test_normalize_handles_non_binary_markets():
    raw = dict(
        RAW,
        outcomes='["A", "B", "C"]',
        outcomePrices='["0.2", "0.3", "0.5"]',
    )
    m = markets.normalize(raw)
    assert len(m.outcomes) == 3
    assert m.implied_prob_yes is None, \
        "implied_prob_yes is only meaningful for a Yes/No market"


def test_normalize_carries_numeric_fields():
    m = markets.normalize(RAW)
    assert m.volume == pytest.approx(83447614.07)
    assert m.liquidity == pytest.approx(19441.20)
    assert m.best_ask == pytest.approx(0.007)


def test_normalize_keeps_description_for_resolution_research():
    assert "June 1, 2026" in markets.normalize(RAW).description


def test_normalize_tolerates_already_parsed_lists():
    raw = dict(RAW, outcomes=["Yes", "No"], outcomePrices=["0.4", "0.6"])
    m = markets.normalize(raw)
    assert m.outcomes == ["Yes", "No"]
    assert m.implied_prob_yes == pytest.approx(0.4)


def test_normalize_tolerates_missing_prices():
    raw = {k: v for k, v in RAW.items() if k != "outcomePrices"}
    m = markets.normalize(raw)
    assert m.outcome_prices == []
    assert m.implied_prob_yes is None


def test_normalize_raises_without_a_condition_id():
    with pytest.raises(ValueError, match="conditionId"):
        markets.normalize({"question": "orphan"})


def test_normalize_raises_on_malformed_outcomes():
    with pytest.raises(ValueError, match="outcomes"):
        markets.normalize(dict(RAW, outcomes="{not json"))


def test_list_open_requests_unclosed_markets(monkeypatch):
    captured = {}

    def fake_get(url, params=None, **kwargs):
        captured.update(params or {})
        return [RAW]

    monkeypatch.setattr(markets, "get_json", fake_get)
    result = markets.list_open(limit=50)
    assert captured["closed"] == "false"
    assert captured["limit"] == 50
    assert len(result) == 1


def test_list_resolved_requests_closed_markets(monkeypatch):
    captured = {}

    def fake_get(url, params=None, **kwargs):
        captured.update(params or {})
        return [dict(RAW, closed=True)]

    monkeypatch.setattr(markets, "get_json", fake_get)
    markets.list_resolved(limit=10)
    assert captured["closed"] == "true"


def test_list_skips_unparseable_markets(monkeypatch):
    # One bad row must not sink an entire page.
    monkeypatch.setattr(
        markets, "get_json",
        lambda *a, **k: [RAW, {"question": "no condition id"}],
    )
    assert len(markets.list_open()) == 1


def test_list_raises_when_every_row_is_unparseable(monkeypatch):
    # A page that is entirely malformed is schema drift, not "no markets".
    monkeypatch.setattr(
        markets, "get_json",
        lambda *a, **k: [{"question": "no condition id"},
                         {"question": "also no condition id"}],
    )
    with pytest.raises(ValueError, match="none parsed"):
        markets.list_open()


@pytest.mark.network
def test_live_open_markets_have_expected_shape():
    result = markets.list_open(limit=10)
    assert result, "Polymarket returned no open markets"
    sample = result[0]
    assert sample.platform == "polymarket"
    assert sample.market_id.startswith("0x")
    assert sample.question


def test_normalize_returns_a_polymarket_market():
    from tools.domain import PolymarketMarket
    raw = {"conditionId": "0xabc", "question": "Will X?",
           "outcomes": '["Yes", "No"]', "outcomePrices": '["0.6", "0.4"]',
           "bestBid": "0.59", "bestAsk": "0.61", "volumeNum": 1000,
           "endDate": "2026-09-01T00:00:00Z", "closed": False}
    m = markets.normalize(raw)
    assert isinstance(m, PolymarketMarket)
    assert m.market_id == "0xabc"
    assert m.question == "Will X?"
    assert m.outcomes == ["Yes", "No"]         # stays a list
    assert m.implied_prob_yes == pytest.approx(0.6)
    assert m.raw is raw


def test_fetch_seam_injects_without_monkeypatch():
    def fake(url, params=None, timeout=30):
        return [{"conditionId": "0x1", "question": "q",
                 "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]'}]
    got = markets.list_open(fetch=fake)
    assert [m.market_id for m in got] == ["0x1"]
