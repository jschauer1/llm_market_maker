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
    assert m.yes_bid == pytest.approx(0.92)
    assert m.yes_ask == pytest.approx(0.93)
    assert m.last_price == pytest.approx(0.93)


def test_normalize_parses_fp_sizes():
    m = markets.normalize(RAW)
    assert m.volume == pytest.approx(175581.15)
    assert m.open_interest == pytest.approx(40225.58)


def test_normalize_derives_spread_and_mid():
    m = markets.normalize(RAW)
    assert m.spread == pytest.approx(0.01)
    assert m.mid == pytest.approx(0.925)


def test_normalize_marks_active_markets_open():
    assert markets.normalize(RAW).is_open is True


def test_normalize_marks_finalized_markets_closed():
    raw = dict(RAW, status="finalized", result="yes")
    m = markets.normalize(raw)
    assert m.is_open is False
    assert m.result == "yes"


def test_normalize_turns_blank_result_into_none():
    assert markets.normalize(RAW).result is None


def test_normalize_keeps_resolution_rules():
    # Stage 2 research depends on this text; it must survive normalization.
    assert "Anthropic" in markets.normalize(RAW).rules_primary


def test_normalize_keeps_the_raw_payload():
    assert markets.normalize(RAW).raw["volume_fp"] == "175581.15"


def test_normalize_tolerates_missing_optional_fields():
    raw = {"ticker": "X", "status": "active"}
    m = markets.normalize(raw)
    assert m.yes_bid is None
    assert m.spread is None
    assert m.mid is None
    assert m.volume is None


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
    assert [m.ticker for m in result] == ["A", "B", "C"]
    assert result[0].series_ticker == "S1"
    assert result[2].series_ticker == "S2"


def test_list_open_keeps_the_markets_own_series_ticker(monkeypatch):
    # series_ticker must not be nulled out by an event that lacks one, just
    # like event_ticker already isn't.
    monkeypatch.setattr(
        markets, "get_json",
        lambda *a, **k: {
            "events": [
                {
                    "event_ticker": "E1",
                    "title": "Event one",
                    "markets": [dict(RAW, ticker="A", series_ticker="OWN")],
                }
            ],
            "cursor": "",
        },
    )
    result = markets.list_open()
    assert result[0].series_ticker == "OWN"


def test_list_open_pages_past_ten(monkeypatch):
    # list_open used to cap at 10 pages by default, which on the real board
    # is a heavily biased slice (see FetchError's docstring). There is no
    # cap at all now -- the walk must page to exhaustion regardless of size.
    total_pages = 12

    def fake_get(url, params=None, **kwargs):
        page_num = int((params or {}).get("cursor") or "0")
        next_num = page_num + 1
        cursor = str(next_num) if next_num < total_pages else ""
        return {
            "events": [{"markets": [dict(RAW, ticker=f"T{page_num}")]}],
            "cursor": cursor,
        }

    monkeypatch.setattr(markets, "get_json", fake_get)
    result = markets.list_open()
    assert len(result) == total_pages
    assert [m.ticker for m in result] == [f"T{n}" for n in range(total_pages)]


def test_list_open_deduplicates_tickers_across_pages(monkeypatch):
    pages = [
        {
            "events": [{"markets": [dict(RAW, ticker="A"),
                                    dict(RAW, ticker="B")]}],
            "cursor": "next",
        },
        {
            # "A" reappears -- Kalshi's feed can re-surface a market across
            # pages during a walk; it must not be counted twice.
            "events": [{"markets": [dict(RAW, ticker="A"),
                                    dict(RAW, ticker="C")]}],
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
    assert [m.ticker for m in result] == ["A", "B", "C"]


def test_list_open_raises_when_the_cursor_stops_advancing(monkeypatch):
    # A server-side bug that keeps returning the same cursor must not spin
    # forever, since there is no page cap to bound the walk.
    monkeypatch.setattr(
        markets, "get_json",
        lambda *a, **k: {"events": [{"markets": [dict(RAW)]}],
                         "cursor": "stuck"},
    )
    with pytest.raises(markets.FetchError, match="same cursor"):
        markets.list_open()


def test_list_settled_pages_to_exhaustion(monkeypatch):
    # list_settled used to hardcode max_pages=5, silently truncating the
    # walk. It must page to exhaustion just like list_open.
    total_pages = 7

    def fake_get(url, params=None, **kwargs):
        page_num = int((params or {}).get("cursor") or "0")
        next_num = page_num + 1
        cursor = str(next_num) if next_num < total_pages else ""
        return {
            "markets": [dict(RAW, ticker=f"T{page_num}")],
            "cursor": cursor,
        }

    monkeypatch.setattr(markets, "get_json", fake_get)
    result = markets.list_settled()
    assert len(result) == total_pages
    assert [m.ticker for m in result] == [f"T{n}" for n in range(total_pages)]


def test_list_settled_deduplicates_tickers_across_pages(monkeypatch):
    pages = [
        {"markets": [dict(RAW, ticker="A"), dict(RAW, ticker="B")],
         "cursor": "next"},
        {
            # "A" reappears -- must not be counted twice.
            "markets": [dict(RAW, ticker="A"), dict(RAW, ticker="C")],
            "cursor": "",
        },
    ]
    calls = {"n": 0}

    def fake_get(url, params=None, **kwargs):
        page = pages[calls["n"]]
        calls["n"] += 1
        return page

    monkeypatch.setattr(markets, "get_json", fake_get)
    result = markets.list_settled()
    assert [m.ticker for m in result] == ["A", "B", "C"]


def test_list_settled_raises_when_the_cursor_stops_advancing(monkeypatch):
    monkeypatch.setattr(
        markets, "get_json",
        lambda *a, **k: {"markets": [dict(RAW)], "cursor": "stuck"},
    )
    with pytest.raises(markets.FetchError, match="same cursor"):
        markets.list_settled()


def test_quotes_maps_tickers_to_markets(monkeypatch):
    monkeypatch.setattr(
        markets, "get_json",
        lambda *a, **k: {"markets": [dict(RAW, ticker="A"),
                                     dict(RAW, ticker="B")]},
    )
    result = markets.quotes(["A", "B"])
    assert set(result) == {"A", "B"}
    assert result["A"].yes_ask == pytest.approx(0.93)


def test_quotes_sends_a_limit_matching_the_ticker_count(monkeypatch):
    captured = {}

    def fake_get(url, params=None, **kwargs):
        captured.update(params or {})
        return {"markets": [dict(RAW, ticker="A"), dict(RAW, ticker="B"),
                            dict(RAW, ticker="C")]}

    monkeypatch.setattr(markets, "get_json", fake_get)
    markets.quotes(["A", "B", "C"])
    assert captured["limit"] == 3


def test_quotes_returns_empty_for_no_tickers(monkeypatch):
    assert markets.quotes([]) == {}


def test_quotes_chunks_large_ticker_lists(monkeypatch):
    # Kalshi answers /markets?tickers=... with 414 once the URL grows past
    # its limit, which a settle pass hits as soon as the ledger holds a few
    # hundred unsettled tickers. quotes() must chunk rather than make the
    # caller do it.
    calls = []

    def fake_get(url, params=None, **kwargs):
        asked = (params or {})["tickers"].split(",")
        calls.append(asked)
        return {"markets": [dict(RAW, ticker=t) for t in asked]}

    monkeypatch.setattr(markets, "get_json", fake_get)
    tickers = [f"T{i:04d}" for i in range(250)]
    result = markets.quotes(tickers)

    assert set(result) == set(tickers)
    assert len(calls) > 1, "expected more than one request for 250 tickers"
    assert all(len(c) <= markets.QUOTE_CHUNK for c in calls)
    assert [t for c in calls for t in c] == tickers


@pytest.mark.network
def test_live_open_markets_have_expected_shape():
    # list_open takes no cap: it always pages to exhaustion (~60 requests
    # against the live board), matching how this is actually called.
    result = markets.list_open()
    assert result, "Kalshi returned no open markets"
    sample = result[0]
    assert sample.platform == "kalshi"
    assert sample.ticker
    assert sample.is_open is True


# --- domain type and the fetch seam (OOP migration, phase 2) ----------


def test_normalize_returns_a_market_with_raw_by_identity():
    from tools.domain import Market
    m = markets.normalize(RAW)
    assert isinstance(m, Market)
    assert m.raw is RAW
    assert m.yes_ask == pytest.approx(0.93)
    assert m.ticker == "KXOAIANTH-40-ANTH"
    assert m.is_open is True


def test_list_open_accepts_an_injected_fetch_without_monkeypatch():
    """The seam that makes a theory testable against a canned payload --
    monkeypatch works in pytest and is unavailable to a backtest harness
    or a replay."""
    calls = []

    def fake(url, params=None, timeout=30):
        calls.append(url)
        return {"events": [{"event_ticker": "KXOAIANTH-40", "title": "evt",
                            "markets": [dict(RAW)]}], "cursor": ""}

    got = markets.list_open(fetch=fake)
    assert [m.ticker for m in got] == ["KXOAIANTH-40-ANTH"]
    assert calls and calls[0].endswith("/events")


def test_list_open_enriches_missing_event_fields_from_the_event():
    """Market is frozen, so enrichment replaces rather than mutates."""
    raw = {k: v for k, v in RAW.items() if k != "event_ticker"}

    def fake(url, params=None, timeout=30):
        return {"events": [{"event_ticker": "KXFROMEVT",
                            "series_ticker": "KXSER", "title": "evt title",
                            "markets": [raw]}], "cursor": ""}

    got = markets.list_open(fetch=fake)
    assert got[0].event_ticker == "KXFROMEVT"
    assert got[0].series_ticker == "KXSER"
    assert got[0].title == RAW["title"]      # own title wins over the event's


def test_quotes_accepts_an_injected_fetch():
    def fake(url, params=None, timeout=30):
        return {"markets": [dict(RAW)]}

    got = markets.quotes(["KXOAIANTH-40-ANTH"], fetch=fake)
    assert got["KXOAIANTH-40-ANTH"].yes_ask == pytest.approx(0.93)


def test_list_settled_accepts_an_injected_fetch():
    def fake(url, params=None, timeout=30):
        return {"markets": [dict(RAW, status="finalized", result="yes")]}

    got = markets.list_settled(fetch=fake)
    assert [m.result for m in got] == ["yes"]
