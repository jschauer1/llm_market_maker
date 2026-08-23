# Data Connectors Implementation Plan (Plan 2 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the system eyes — unauthenticated access to Kalshi market data (live and historical), Polymarket market and whale-trade data, first-party snapshot capture, and the mechanical cross-platform matching that turns a Polymarket finding into a Kalshi ticker candidate.

**Architecture:** Each platform gets a thin normalizing client that converts the provider's wire format into one stable internal dict shape. Normalization is the seam that protects everything downstream from schema drift — a real risk here, since Kalshi has already changed its field names once. Parsers fail loudly on unexpected shapes rather than silently returning zeros. No judgment lives in this layer: `match_market` produces a *shortlist*, never a decision.

**Tech Stack:** Python 3.11, `requests`, pytest. Network tests are marked and skippable.

**Spec:** `docs/superpowers/specs/2026-08-23-llm-market-edge-finder-design.md`

**Depends on:** Plan 1 (`tools/db.py`, `tools/sizing.py`) must be complete (111 tests).

## Global Constraints

- All endpoints in this plan are **public and unauthenticated**. Never add an API key, and never send the user's email or any identifier in a header, URL, or payload.
- All prices normalize to **decimal dollars in [0, 1]** as floats. Kalshi returns decimal-dollar *strings* (`"0.9300"`); Polymarket returns JSON-encoded string arrays (`'["0.006", "0.994"]'`). Both get parsed at the boundary — no raw provider strings escape a client module.
- **Fail loudly.** A missing or unparseable required field raises; it never silently becomes `0.0` or `None`. An optional field that is genuinely absent may be `None`. This is the mitigation for the schema-drift risk in spec section 19.
- Verified endpoint facts (2026-08-23), to be used exactly as written:
  - Kalshi base: `https://api.elections.kalshi.com/trade-api/v2`
  - Kalshi market fields: `yes_bid_dollars`, `yes_ask_dollars`, `no_bid_dollars`, `no_ask_dollars`, `last_price_dollars`, `volume_fp`, `volume_24h_fp`, `open_interest_fp`, `rules_primary`, `result`, `status`, `close_time`, `open_time`. Status is `active` when open and `finalized` when settled.
  - Kalshi candlesticks: `GET /series/{series_ticker}/markets/{ticker}/candlesticks?start_ts=&end_ts=&period_interval=` with `period_interval` in `{1, 60, 1440}` minutes. Each candle has `end_period_ts`, `volume_fp`, `open_interest_fp`, and nested `price`, `yes_bid`, `yes_ask` objects whose members are `open_dollars`/`high_dollars`/`low_dollars`/`close_dollars`. Verified to reach back at least ~12 months.
  - Polymarket Gamma: `https://gamma-api.polymarket.com/markets?closed=false&limit=&order=volumeNum&ascending=false`. Fields: `conditionId`, `question`, `slug`, `outcomes`, `outcomePrices`, `bestBid`, `bestAsk`, `volumeNum`, `liquidityNum`, `endDate`, `description`, `clobTokenIds`.
  - Polymarket trades: `https://data-api.polymarket.com/trades?limit=&filterAmount=&takerOnly=true`. `filterAmount` filters server-side by USD size — this is the whale filter. Fields: `proxyWallet`, `name`, `side`, `size`, `price`, `conditionId`, `title`, `timestamp`, `outcome`.
  - Polymarket holders: `https://data-api.polymarket.com/holders?market={conditionId}&limit=`.
- Rate limits are undocumented. Every client backs off on 429/5xx and every network test sleeps between calls. Network tests are marked `@pytest.mark.network` and must be skippable with `-m "not network"`.
- Commit after every task.

---

### Task 1: HTTP helper with backoff

**Files:**
- Create: `requirements.txt`
- Create: `tools/http.py`
- Create: `tests/test_http.py`
- Create: `pytest.ini`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `tools.http.get_json(url: str, params: dict | None = None, timeout: int = 30, max_retries: int = 4) -> dict | list`
  - `tools.http.HttpError(Exception)` — raised on a non-retryable status or after retries are exhausted

- [ ] **Step 1: Create `requirements.txt` and `pytest.ini`**

`requirements.txt`:
```
requests>=2.31
pytest>=8.0
```

`pytest.ini`:
```ini
[pytest]
markers =
    network: test performs a live network call (deselect with -m "not network")
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_http.py`:

```python
import pytest

from tools import http


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_returns_parsed_json_on_success(monkeypatch):
    monkeypatch.setattr(
        http.requests, "get",
        lambda *a, **k: FakeResponse(200, {"ok": True}),
    )
    assert http.get_json("https://example.test") == {"ok": True}


def test_passes_params_through(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        captured["url"] = url
        captured["params"] = params
        return FakeResponse(200, [])

    monkeypatch.setattr(http.requests, "get", fake_get)
    http.get_json("https://example.test", params={"limit": 5})
    assert captured["params"] == {"limit": 5}


def test_retries_on_429_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            return FakeResponse(429)
        return FakeResponse(200, {"ok": True})

    monkeypatch.setattr(http.requests, "get", fake_get)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    assert http.get_json("https://example.test") == {"ok": True}
    assert calls["n"] == 3


def test_retries_on_500_then_gives_up(monkeypatch):
    monkeypatch.setattr(
        http.requests, "get", lambda *a, **k: FakeResponse(503)
    )
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    with pytest.raises(http.HttpError, match="503"):
        http.get_json("https://example.test", max_retries=2)


def test_does_not_retry_on_404(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **k):
        calls["n"] += 1
        return FakeResponse(404)

    monkeypatch.setattr(http.requests, "get", fake_get)
    with pytest.raises(http.HttpError, match="404"):
        http.get_json("https://example.test")
    assert calls["n"] == 1, "client errors must not be retried"


def test_backoff_grows_between_attempts(monkeypatch):
    delays = []
    monkeypatch.setattr(
        http.requests, "get", lambda *a, **k: FakeResponse(429)
    )
    monkeypatch.setattr(http.time, "sleep", lambda s: delays.append(s))
    with pytest.raises(http.HttpError):
        http.get_json("https://example.test", max_retries=3)
    assert delays == sorted(delays)
    assert len(delays) >= 2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_http.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.http'`

- [ ] **Step 4: Write `tools/http.py`**

```python
"""Shared HTTP helper for the public market-data APIs.

All endpoints this project uses are public and unauthenticated. Nothing here
sends credentials or any user identifier.

Rate limits on both providers are undocumented, so 429 and 5xx get an
exponential backoff. Client errors other than 429 are not retried — a 404 is
an answer, not a hiccup.
"""

from __future__ import annotations

import time

import requests

USER_AGENT = "market-edge-finder/1.0"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class HttpError(Exception):
    """A request failed permanently or ran out of retries."""


def get_json(
    url: str,
    params: dict | None = None,
    timeout: int = 30,
    max_retries: int = 4,
) -> dict | list:
    """GET a URL and return parsed JSON, retrying transient failures."""
    delay = 1.0
    last_status: int | None = None

    for attempt in range(max_retries):
        response = requests.get(
            url,
            params=params,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
        if response.status_code == 200:
            return response.json()

        last_status = response.status_code
        if last_status not in RETRYABLE_STATUS:
            raise HttpError(f"GET {url} failed with status {last_status}")

        if attempt < max_retries - 1:
            time.sleep(delay)
            delay *= 2

    raise HttpError(
        f"GET {url} failed with status {last_status} after {max_retries} attempts"
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_http.py -v`
Expected: PASS — 6 passed

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini tools/http.py tests/test_http.py
git commit -m "feat: add HTTP helper with exponential backoff"
```

---

### Task 2: Kalshi market client

**Files:**
- Create: `tools/kalshi/__init__.py`
- Create: `tools/kalshi/markets.py`
- Create: `tests/kalshi/__init__.py`
- Create: `tests/kalshi/test_markets.py`

**Interfaces:**
- Consumes: `tools.http.get_json`
- Produces:
  - `tools.kalshi.markets.normalize(raw: dict) -> dict` — one stable internal shape (keys below)
  - `tools.kalshi.markets.list_open(limit: int = 200, max_pages: int = 10) -> list[dict]`
  - `tools.kalshi.markets.list_settled(limit: int = 200, max_pages: int = 5) -> list[dict]`
  - `tools.kalshi.markets.quotes(tickers: list[str]) -> dict[str, dict]` — ticker → normalized market
  - `tools.kalshi.markets.BASE_URL: str`
  - Normalized keys: `platform`, `ticker`, `event_ticker`, `series_ticker`, `title`, `yes_bid`, `yes_ask`, `no_bid`, `no_ask`, `mid`, `spread`, `last_price`, `volume`, `volume_24h`, `open_interest`, `status`, `is_open`, `close_time`, `open_time`, `result`, `rules_primary`, `raw`

- [ ] **Step 1: Write the failing test**

Create `tests/kalshi/__init__.py` (empty) and `tools/kalshi/__init__.py` (empty), then `tests/kalshi/test_markets.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/kalshi/test_markets.py -v -m "not network"`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.kalshi.markets'`

- [ ] **Step 3: Write `tools/kalshi/markets.py`**

```python
"""Kalshi market data client (public, unauthenticated).

Kalshi's schema changed once already — prices moved from integer cents to
decimal-dollar strings (`yes_ask_dollars`) and sizes gained an `_fp` suffix.
`normalize` is the seam that absorbs that: everything downstream sees one
stable dict of floats, and a shape we do not recognize raises instead of
quietly producing zeros.
"""

from __future__ import annotations

from tools.http import get_json

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

OPEN_STATUSES = {"active", "open"}


def _price(raw: dict, key: str) -> float | None:
    """Parse a decimal-dollar string field. Absent is fine; garbage is not."""
    value = raw.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"could not parse {key}={value!r} as a number — "
            "Kalshi's schema may have changed"
        ) from exc


def normalize(raw: dict) -> dict:
    """Convert a raw Kalshi market into the internal shape."""
    ticker = raw.get("ticker")
    if not ticker:
        raise ValueError(
            f"market payload has no ticker — schema drift? keys={sorted(raw)}"
        )

    yes_bid = _price(raw, "yes_bid_dollars")
    yes_ask = _price(raw, "yes_ask_dollars")
    spread = (
        yes_ask - yes_bid if yes_bid is not None and yes_ask is not None else None
    )
    mid = (
        (yes_bid + yes_ask) / 2.0
        if yes_bid is not None and yes_ask is not None
        else None
    )
    status = raw.get("status")

    return {
        "platform": "kalshi",
        "ticker": ticker,
        "event_ticker": raw.get("event_ticker"),
        "series_ticker": raw.get("series_ticker"),
        "title": raw.get("title"),
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "no_bid": _price(raw, "no_bid_dollars"),
        "no_ask": _price(raw, "no_ask_dollars"),
        "mid": mid,
        "spread": spread,
        "last_price": _price(raw, "last_price_dollars"),
        "volume": _price(raw, "volume_fp"),
        "volume_24h": _price(raw, "volume_24h_fp"),
        "open_interest": _price(raw, "open_interest_fp"),
        "status": status,
        "is_open": status in OPEN_STATUSES,
        "close_time": raw.get("close_time"),
        "open_time": raw.get("open_time"),
        "result": raw.get("result") or None,
        "rules_primary": raw.get("rules_primary"),
        "raw": raw,
    }


def list_open(limit: int = 200, max_pages: int = 10) -> list[dict]:
    """All open markets, walked via the events endpoint.

    Events carry the series ticker, which the candlestick endpoint needs, so
    fetching this way rather than /markets keeps history reachable later.
    """
    out: list[dict] = []
    cursor = ""
    for _ in range(max_pages):
        params = {
            "status": "open",
            "with_nested_markets": "true",
            "limit": limit,
        }
        if cursor:
            params["cursor"] = cursor
        payload = get_json(f"{BASE_URL}/events", params=params)

        for event in payload.get("events", []):
            for raw in event.get("markets", []):
                market = normalize(raw)
                market["event_ticker"] = (
                    market["event_ticker"] or event.get("event_ticker")
                )
                market["series_ticker"] = event.get("series_ticker")
                if not market["title"]:
                    market["title"] = event.get("title")
                out.append(market)

        cursor = payload.get("cursor") or ""
        if not cursor:
            break
    return out


def list_settled(limit: int = 200, max_pages: int = 5) -> list[dict]:
    """Recently settled markets, with their results."""
    out: list[dict] = []
    cursor = ""
    for _ in range(max_pages):
        params = {"status": "settled", "limit": limit}
        if cursor:
            params["cursor"] = cursor
        payload = get_json(f"{BASE_URL}/markets", params=params)
        out.extend(normalize(raw) for raw in payload.get("markets", []))
        cursor = payload.get("cursor") or ""
        if not cursor:
            break
    return out


def quotes(tickers: list[str]) -> dict[str, dict]:
    """Live re-quote for specific tickers, keyed by ticker."""
    if not tickers:
        return {}
    payload = get_json(
        f"{BASE_URL}/markets", params={"tickers": ",".join(tickers)}
    )
    return {
        market["ticker"]: market
        for market in (normalize(raw) for raw in payload.get("markets", []))
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/kalshi/test_markets.py -v -m "not network"`
Expected: PASS — 15 passed, 1 deselected

- [ ] **Step 5: Run the network test once**

Run: `python -m pytest tests/kalshi/test_markets.py -v -m network`
Expected: PASS — 1 passed. If it fails on field names, the schema drifted again; fix `normalize` and re-run.

- [ ] **Step 6: Commit**

```bash
git add tools/kalshi/ tests/kalshi/
git commit -m "feat: add Kalshi market client with schema-drift guards"
```

---

### Task 3: Kalshi historical prices

Point-in-time reconstruction for backtesting (spec section 12). The candlesticks carry historical **bid/ask**, not just last trade, so backtest entry prices can be genuinely executable.

**Files:**
- Create: `tools/kalshi/history.py`
- Create: `tests/kalshi/test_history.py`

**Interfaces:**
- Consumes: `tools.http.get_json`, `tools.kalshi.markets.BASE_URL`
- Produces:
  - `tools.kalshi.history.candlesticks(series_ticker: str, ticker: str, start_ts: int, end_ts: int, period_interval: int = 1440) -> list[dict]` — normalized, ascending by time
  - `tools.kalshi.history.point_in_time(series_ticker: str, ticker: str, as_of_ts: int, lookback_days: int = 30) -> dict | None` — market state as of a past moment
  - `tools.kalshi.history.VALID_INTERVALS: tuple[int, ...]`
  - Normalized candle keys: `end_ts`, `open`, `high`, `low`, `close`, `mean`, `yes_bid_close`, `yes_ask_close`, `volume`, `open_interest`

- [ ] **Step 1: Write the failing test**

Create `tests/kalshi/test_history.py`:

```python
import time

import pytest

from tools.kalshi import history

RAW_CANDLE = {
    "end_period_ts": 1784952000,
    "open_interest_fp": "38434.75",
    "volume_fp": "236.31",
    "price": {
        "open_dollars": "0.8500",
        "high_dollars": "0.8600",
        "low_dollars": "0.8400",
        "close_dollars": "0.8500",
        "mean_dollars": "0.8500",
    },
    "yes_bid": {"close_dollars": "0.8300"},
    "yes_ask": {"close_dollars": "0.8600"},
}


def test_candlesticks_normalizes_nested_prices(monkeypatch):
    monkeypatch.setattr(
        history, "get_json",
        lambda *a, **k: {"candlesticks": [RAW_CANDLE]},
    )
    candles = history.candlesticks("S", "T", 0, 100)
    candle = candles[0]
    assert candle["close"] == pytest.approx(0.85)
    assert candle["high"] == pytest.approx(0.86)
    assert candle["yes_bid_close"] == pytest.approx(0.83)
    assert candle["yes_ask_close"] == pytest.approx(0.86)
    assert candle["volume"] == pytest.approx(236.31)
    assert candle["end_ts"] == 1784952000


def test_candlesticks_sorts_ascending(monkeypatch):
    late = dict(RAW_CANDLE, end_period_ts=200)
    early = dict(RAW_CANDLE, end_period_ts=100)
    monkeypatch.setattr(
        history, "get_json",
        lambda *a, **k: {"candlesticks": [late, early]},
    )
    assert [c["end_ts"] for c in history.candlesticks("S", "T", 0, 300)] == \
        [100, 200]


def test_candlesticks_rejects_invalid_interval():
    with pytest.raises(ValueError, match="period_interval"):
        history.candlesticks("S", "T", 0, 100, period_interval=5)


def test_candlesticks_handles_empty_response(monkeypatch):
    monkeypatch.setattr(history, "get_json", lambda *a, **k: {})
    assert history.candlesticks("S", "T", 0, 100) == []


def test_candlesticks_tolerates_missing_bid_ask(monkeypatch):
    raw = {k: v for k, v in RAW_CANDLE.items() if k not in ("yes_bid", "yes_ask")}
    monkeypatch.setattr(
        history, "get_json", lambda *a, **k: {"candlesticks": [raw]}
    )
    candle = history.candlesticks("S", "T", 0, 100)[0]
    assert candle["yes_bid_close"] is None
    assert candle["yes_ask_close"] is None
    assert candle["close"] == pytest.approx(0.85)


def test_point_in_time_returns_the_last_candle_at_or_before(monkeypatch):
    candles = [
        dict(RAW_CANDLE, end_period_ts=100),
        dict(RAW_CANDLE, end_period_ts=200),
        dict(RAW_CANDLE, end_period_ts=300),
    ]
    monkeypatch.setattr(
        history, "get_json", lambda *a, **k: {"candlesticks": candles}
    )
    state = history.point_in_time("S", "T", as_of_ts=250)
    assert state["end_ts"] == 200, "must not peek at the future candle"


def test_point_in_time_includes_the_exact_boundary(monkeypatch):
    candles = [dict(RAW_CANDLE, end_period_ts=100),
               dict(RAW_CANDLE, end_period_ts=200)]
    monkeypatch.setattr(
        history, "get_json", lambda *a, **k: {"candlesticks": candles}
    )
    assert history.point_in_time("S", "T", as_of_ts=200)["end_ts"] == 200


def test_point_in_time_returns_none_when_nothing_precedes(monkeypatch):
    monkeypatch.setattr(
        history, "get_json",
        lambda *a, **k: {"candlesticks": [dict(RAW_CANDLE,
                                               end_period_ts=500)]},
    )
    assert history.point_in_time("S", "T", as_of_ts=100) is None


def test_point_in_time_returns_none_for_no_data(monkeypatch):
    monkeypatch.setattr(history, "get_json", lambda *a, **k: {})
    assert history.point_in_time("S", "T", as_of_ts=100) is None


@pytest.mark.network
def test_live_candlesticks_reach_back_months():
    now = int(time.time())
    candles = history.candlesticks(
        "KXOAIANTH", "KXOAIANTH-40-ANTH",
        start_ts=now - 86400 * 180, end_ts=now, period_interval=1440,
    )
    assert len(candles) > 100, "expected months of daily history"
    assert candles[0]["end_ts"] < candles[-1]["end_ts"]
    assert any(c["yes_ask_close"] is not None for c in candles), \
        "historical ask is required for executable backtest prices"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/kalshi/test_history.py -v -m "not network"`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.kalshi.history'`

- [ ] **Step 3: Write `tools/kalshi/history.py`**

```python
"""Kalshi historical prices and point-in-time reconstruction.

Candlesticks carry historical yes_bid and yes_ask, not just the last trade.
That matters: a backtest priced at the mid is a backtest of a trade nobody
could have made. Entry prices reconstructed here use the ask.

point_in_time never looks past its as_of timestamp. That property is the
whole basis of a lookahead-free replay, so the boundary is tested explicitly.
"""

from __future__ import annotations

from tools.http import get_json
from tools.kalshi.markets import BASE_URL

VALID_INTERVALS = (1, 60, 1440)


def _nested(candle: dict, group: str, field: str) -> float | None:
    block = candle.get(group)
    if not isinstance(block, dict):
        return None
    value = block.get(field)
    if value is None or value == "":
        return None
    return float(value)


def _flat(candle: dict, key: str) -> float | None:
    value = candle.get(key)
    if value is None or value == "":
        return None
    return float(value)


def candlesticks(
    series_ticker: str,
    ticker: str,
    start_ts: int,
    end_ts: int,
    period_interval: int = 1440,
) -> list[dict]:
    """Normalized candles, ascending by end timestamp."""
    if period_interval not in VALID_INTERVALS:
        raise ValueError(
            f"period_interval must be one of {VALID_INTERVALS}, "
            f"got {period_interval}"
        )
    payload = get_json(
        f"{BASE_URL}/series/{series_ticker}/markets/{ticker}/candlesticks",
        params={
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": period_interval,
        },
    )
    candles = [
        {
            "end_ts": raw.get("end_period_ts"),
            "open": _nested(raw, "price", "open_dollars"),
            "high": _nested(raw, "price", "high_dollars"),
            "low": _nested(raw, "price", "low_dollars"),
            "close": _nested(raw, "price", "close_dollars"),
            "mean": _nested(raw, "price", "mean_dollars"),
            "yes_bid_close": _nested(raw, "yes_bid", "close_dollars"),
            "yes_ask_close": _nested(raw, "yes_ask", "close_dollars"),
            "volume": _flat(raw, "volume_fp"),
            "open_interest": _flat(raw, "open_interest_fp"),
        }
        for raw in payload.get("candlesticks", [])
    ]
    return sorted(candles, key=lambda c: c["end_ts"])


def point_in_time(
    series_ticker: str,
    ticker: str,
    as_of_ts: int,
    lookback_days: int = 30,
) -> dict | None:
    """Market state as of a past moment, or None if no candle precedes it.

    Returns the most recent candle at or before as_of_ts. Never returns a
    candle from after that moment — this is what keeps a replay honest.
    """
    candles = candlesticks(
        series_ticker,
        ticker,
        start_ts=as_of_ts - 86400 * lookback_days,
        end_ts=as_of_ts,
        period_interval=1440,
    )
    eligible = [c for c in candles if c["end_ts"] <= as_of_ts]
    return eligible[-1] if eligible else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/kalshi/test_history.py -v -m "not network"`
Expected: PASS — 9 passed, 1 deselected

- [ ] **Step 5: Run the network test**

Run: `python -m pytest tests/kalshi/test_history.py -v -m network`
Expected: PASS — 1 passed

- [ ] **Step 6: Commit**

```bash
git add tools/kalshi/history.py tests/kalshi/test_history.py
git commit -m "feat: add Kalshi historical prices and point-in-time lookup"
```

---

### Task 4: Polymarket market client

**Files:**
- Create: `tools/polymarket/__init__.py`
- Create: `tools/polymarket/markets.py`
- Create: `tests/polymarket/__init__.py`
- Create: `tests/polymarket/test_markets.py`

**Interfaces:**
- Consumes: `tools.http.get_json`
- Produces:
  - `tools.polymarket.markets.normalize(raw: dict) -> dict`
  - `tools.polymarket.markets.list_open(limit: int = 100, order: str = "volumeNum") -> list[dict]`
  - `tools.polymarket.markets.list_resolved(limit: int = 100) -> list[dict]`
  - `tools.polymarket.markets.GAMMA_URL: str`
  - Normalized keys: `platform`, `market_id`, `question`, `slug`, `outcomes`, `outcome_prices`, `implied_prob_yes`, `best_bid`, `best_ask`, `volume`, `liquidity`, `end_date`, `closed`, `description`, `raw`

- [ ] **Step 1: Write the failing test**

Create `tests/polymarket/__init__.py` (empty) and `tools/polymarket/__init__.py` (empty), then `tests/polymarket/test_markets.py`:

```python
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
    assert m["outcomes"] == ["Yes", "No"]
    assert m["outcome_prices"] == [pytest.approx(0.006), pytest.approx(0.994)]


def test_normalize_uses_condition_id_as_market_id():
    assert markets.normalize(RAW)["market_id"] == RAW["conditionId"]


def test_normalize_extracts_implied_yes_probability():
    assert markets.normalize(RAW)["implied_prob_yes"] == pytest.approx(0.006)


def test_normalize_handles_non_binary_markets():
    raw = dict(
        RAW,
        outcomes='["A", "B", "C"]',
        outcomePrices='["0.2", "0.3", "0.5"]',
    )
    m = markets.normalize(raw)
    assert len(m["outcomes"]) == 3
    assert m["implied_prob_yes"] is None, \
        "implied_prob_yes is only meaningful for a Yes/No market"


def test_normalize_carries_numeric_fields():
    m = markets.normalize(RAW)
    assert m["volume"] == pytest.approx(83447614.07)
    assert m["liquidity"] == pytest.approx(19441.20)
    assert m["best_ask"] == pytest.approx(0.007)


def test_normalize_keeps_description_for_resolution_research():
    assert "June 1, 2026" in markets.normalize(RAW)["description"]


def test_normalize_tolerates_already_parsed_lists():
    raw = dict(RAW, outcomes=["Yes", "No"], outcomePrices=["0.4", "0.6"])
    m = markets.normalize(raw)
    assert m["outcomes"] == ["Yes", "No"]
    assert m["implied_prob_yes"] == pytest.approx(0.4)


def test_normalize_tolerates_missing_prices():
    raw = {k: v for k, v in RAW.items() if k != "outcomePrices"}
    m = markets.normalize(raw)
    assert m["outcome_prices"] == []
    assert m["implied_prob_yes"] is None


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


@pytest.mark.network
def test_live_open_markets_have_expected_shape():
    result = markets.list_open(limit=10)
    assert result, "Polymarket returned no open markets"
    sample = result[0]
    assert sample["platform"] == "polymarket"
    assert sample["market_id"].startswith("0x")
    assert sample["question"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/polymarket/test_markets.py -v -m "not network"`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.polymarket.markets'`

- [ ] **Step 3: Write `tools/polymarket/markets.py`**

```python
"""Polymarket market data via the public Gamma API.

Polymarket is a research and signal source, never a bet destination — the
user can only wager on Kalshi. Anything found here must be resolved to a
Kalshi ticker through tools/match_market.py before it can be recorded as an
opportunity.

Gamma returns `outcomes` and `outcomePrices` as JSON-encoded STRINGS rather
than arrays, which is the main parsing wrinkle. The API is public but
undocumented enough that shapes may shift, so parse failures raise.
"""

from __future__ import annotations

import json

from tools.http import get_json

GAMMA_URL = "https://gamma-api.polymarket.com/markets"

YES_NO = ("yes", "no")


def _string_array(raw: dict, key: str) -> list:
    """Gamma encodes arrays as JSON strings; tolerate both forms."""
    value = raw.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"could not parse {key}={value!r} as JSON — "
            "Polymarket's schema may have changed"
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError(f"{key} did not decode to a list: {parsed!r}")
    return parsed


def _number(raw: dict, key: str) -> float | None:
    value = raw.get(key)
    if value is None or value == "":
        return None
    return float(value)


def normalize(raw: dict) -> dict:
    """Convert a raw Gamma market into the internal shape."""
    market_id = raw.get("conditionId")
    if not market_id:
        raise ValueError(
            f"market payload has no conditionId — schema drift? "
            f"keys={sorted(raw)}"
        )

    outcomes = _string_array(raw, "outcomes")
    prices = [float(p) for p in _string_array(raw, "outcomePrices")]

    implied_yes = None
    if len(outcomes) == 2 and len(prices) == 2:
        labels = [str(o).strip().lower() for o in outcomes]
        if labels == list(YES_NO):
            implied_yes = prices[0]
        elif labels == list(reversed(YES_NO)):
            implied_yes = prices[1]

    return {
        "platform": "polymarket",
        "market_id": market_id,
        "question": raw.get("question"),
        "slug": raw.get("slug"),
        "outcomes": outcomes,
        "outcome_prices": prices,
        "implied_prob_yes": implied_yes,
        "best_bid": _number(raw, "bestBid"),
        "best_ask": _number(raw, "bestAsk"),
        "volume": _number(raw, "volumeNum"),
        "liquidity": _number(raw, "liquidityNum"),
        "end_date": raw.get("endDate"),
        "closed": bool(raw.get("closed")),
        "description": raw.get("description"),
        "raw": raw,
    }


def _fetch(params: dict) -> list[dict]:
    payload = get_json(GAMMA_URL, params=params)
    rows = payload if isinstance(payload, list) else payload.get("data", [])
    out = []
    for raw in rows:
        try:
            out.append(normalize(raw))
        except ValueError:
            # One malformed row should not sink the page. The shape guard
            # still fires for anything that reaches a caller.
            continue
    return out


def list_open(limit: int = 100, order: str = "volumeNum") -> list[dict]:
    """Open markets, most-traded first by default."""
    return _fetch(
        {
            "closed": "false",
            "limit": limit,
            "order": order,
            "ascending": "false",
        }
    )


def list_resolved(limit: int = 100) -> list[dict]:
    """Closed markets. Note that resolution encoding in `outcomePrices` is
    inconsistent for older markets, so treat these as signal, not truth."""
    return _fetch({"closed": "true", "limit": limit})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/polymarket/test_markets.py -v -m "not network"`
Expected: PASS — 13 passed, 1 deselected

- [ ] **Step 5: Run the network test**

Run: `python -m pytest tests/polymarket/test_markets.py -v -m network`
Expected: PASS — 1 passed

- [ ] **Step 6: Commit**

```bash
git add tools/polymarket/ tests/polymarket/
git commit -m "feat: add Polymarket market client"
```

---

### Task 5: Polymarket trades and whale detection

The raw material for whale-following theories. `filterAmount` filters by USD size server-side, so whale detection does not require pulling the whole tape.

**Files:**
- Create: `tools/polymarket/trades.py`
- Create: `tests/polymarket/test_trades.py`

**Interfaces:**
- Consumes: `tools.http.get_json`
- Produces:
  - `tools.polymarket.trades.normalize_trade(raw: dict) -> dict`
  - `tools.polymarket.trades.recent(limit: int = 100, min_usd: float | None = None, taker_only: bool = True) -> list[dict]`
  - `tools.polymarket.trades.whales(min_usd: float = 10000, limit: int = 100) -> list[dict]`
  - `tools.polymarket.trades.holders(market_id: str, limit: int = 20) -> list[dict]`
  - `tools.polymarket.trades.by_wallet(trades: list[dict]) -> dict[str, list[dict]]`
  - `tools.polymarket.trades.DATA_URL: str`
  - Normalized trade keys: `wallet`, `name`, `side`, `size`, `price`, `usd`, `market_id`, `title`, `outcome`, `timestamp`, `raw`

- [ ] **Step 1: Write the failing test**

Create `tests/polymarket/test_trades.py`:

```python
import pytest

from tools.polymarket import trades

RAW = {
    "proxyWallet": "0x86dab59a8a6e7f9947282d2117aab3429b706428",
    "name": "bigspending",
    "pseudonym": "Careful-Otter",
    "side": "BUY",
    "size": 126393.79,
    "price": 0.63,
    "conditionId": "0x59583f325944adf331",
    "title": "Will Atalanta BC win on 2026-08-23?",
    "outcome": "Yes",
    "outcomeIndex": 0,
    "timestamp": 1787505834,
}


def test_normalize_trade_maps_fields():
    t = trades.normalize_trade(RAW)
    assert t["wallet"] == RAW["proxyWallet"]
    assert t["name"] == "bigspending"
    assert t["side"] == "BUY"
    assert t["market_id"] == "0x59583f325944adf331"
    assert t["outcome"] == "Yes"
    assert t["timestamp"] == 1787505834


def test_normalize_trade_computes_usd_notional():
    # size 126393.79 shares at 0.63 = 79628.09 USD
    t = trades.normalize_trade(RAW)
    assert t["usd"] == pytest.approx(126393.79 * 0.63)


def test_normalize_trade_falls_back_to_pseudonym():
    raw = {k: v for k, v in RAW.items() if k != "name"}
    assert trades.normalize_trade(raw)["name"] == "Careful-Otter"


def test_normalize_trade_raises_without_a_wallet():
    with pytest.raises(ValueError, match="proxyWallet"):
        trades.normalize_trade({"size": 1, "price": 0.5})


def test_normalize_trade_handles_missing_size_or_price():
    t = trades.normalize_trade(dict(RAW, size=None))
    assert t["usd"] is None


def test_recent_passes_the_size_filter_through(monkeypatch):
    captured = {}

    def fake_get(url, params=None, **kwargs):
        captured.update(params or {})
        return [RAW]

    monkeypatch.setattr(trades, "get_json", fake_get)
    trades.recent(limit=25, min_usd=5000)
    assert captured["filterAmount"] == 5000
    assert captured["limit"] == 25
    assert captured["takerOnly"] == "true"


def test_recent_omits_the_filter_when_not_requested(monkeypatch):
    captured = {}

    def fake_get(url, params=None, **kwargs):
        captured.update(params or {})
        return [RAW]

    monkeypatch.setattr(trades, "get_json", fake_get)
    trades.recent(limit=25)
    assert "filterAmount" not in captured


def test_whales_uses_a_default_threshold(monkeypatch):
    captured = {}

    def fake_get(url, params=None, **kwargs):
        captured.update(params or {})
        return [RAW]

    monkeypatch.setattr(trades, "get_json", fake_get)
    result = trades.whales()
    assert captured["filterAmount"] == 10000
    assert result[0]["usd"] > 0


def test_whales_sorts_largest_first(monkeypatch):
    small = dict(RAW, size=100.0, price=0.5)
    large = dict(RAW, size=100000.0, price=0.5)
    monkeypatch.setattr(
        trades, "get_json", lambda *a, **k: [small, large]
    )
    result = trades.whales()
    assert result[0]["usd"] > result[1]["usd"]


def test_by_wallet_groups_trades():
    a1 = trades.normalize_trade(dict(RAW, proxyWallet="0xA"))
    a2 = trades.normalize_trade(dict(RAW, proxyWallet="0xA"))
    b1 = trades.normalize_trade(dict(RAW, proxyWallet="0xB"))
    grouped = trades.by_wallet([a1, a2, b1])
    assert set(grouped) == {"0xA", "0xB"}
    assert len(grouped["0xA"]) == 2


def test_holders_unwraps_the_nested_response(monkeypatch):
    monkeypatch.setattr(
        trades, "get_json",
        lambda *a, **k: [
            {
                "token": "27146956652877944551",
                "holders": [
                    {"proxyWallet": "0xA", "name": "0xwhaleshark",
                     "amount": 4008.4, "outcomeIndex": 0},
                    {"proxyWallet": "0xB", "name": "minnow",
                     "amount": 12.0, "outcomeIndex": 0},
                ],
            }
        ],
    )
    result = trades.holders("0xcondition")
    assert len(result) == 2
    assert result[0]["name"] == "0xwhaleshark"
    assert result[0]["amount"] == pytest.approx(4008.4)


def test_holders_handles_empty_response(monkeypatch):
    monkeypatch.setattr(trades, "get_json", lambda *a, **k: [])
    assert trades.holders("0xcondition") == []


@pytest.mark.network
def test_live_whale_trades_are_actually_large():
    result = trades.whales(min_usd=10000, limit=5)
    assert result, "no whale trades returned"
    for trade in result:
        assert trade["wallet"].startswith("0x")
        assert trade["usd"] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/polymarket/test_trades.py -v -m "not network"`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.polymarket.trades'`

- [ ] **Step 3: Write `tools/polymarket/trades.py`**

```python
"""Polymarket trade and holder data — the raw material for whale-following.

Polymarket exposes per-trade wallet identity publicly, which Kalshi does not.
That asymmetry is the point: a theory can watch who is betting what here and
then look for the equivalent Kalshi market to actually trade.

`filterAmount` filters by USD notional server-side, so finding large trades
does not require pulling the whole tape.
"""

from __future__ import annotations

from collections import defaultdict

from tools.http import get_json

DATA_URL = "https://data-api.polymarket.com"
DEFAULT_WHALE_USD = 10000


def normalize_trade(raw: dict) -> dict:
    """Convert a raw trade into the internal shape, with USD notional."""
    wallet = raw.get("proxyWallet")
    if not wallet:
        raise ValueError(
            f"trade has no proxyWallet — schema drift? keys={sorted(raw)}"
        )

    size = raw.get("size")
    price = raw.get("price")
    usd = None
    if size is not None and price is not None:
        usd = float(size) * float(price)

    return {
        "wallet": wallet,
        "name": raw.get("name") or raw.get("pseudonym"),
        "side": raw.get("side"),
        "size": float(size) if size is not None else None,
        "price": float(price) if price is not None else None,
        "usd": usd,
        "market_id": raw.get("conditionId"),
        "title": raw.get("title"),
        "outcome": raw.get("outcome"),
        "timestamp": raw.get("timestamp"),
        "raw": raw,
    }


def recent(
    limit: int = 100,
    min_usd: float | None = None,
    taker_only: bool = True,
) -> list[dict]:
    """Recent trades, optionally filtered by USD notional server-side."""
    params: dict = {"limit": limit}
    if taker_only:
        params["takerOnly"] = "true"
    if min_usd is not None:
        params["filterAmount"] = min_usd

    payload = get_json(f"{DATA_URL}/trades", params=params)
    rows = payload if isinstance(payload, list) else []
    out = []
    for raw in rows:
        try:
            out.append(normalize_trade(raw))
        except ValueError:
            continue
    return out


def whales(
    min_usd: float = DEFAULT_WHALE_USD, limit: int = 100
) -> list[dict]:
    """Large recent trades, biggest first."""
    found = recent(limit=limit, min_usd=min_usd)
    return sorted(found, key=lambda t: t["usd"] or 0.0, reverse=True)


def holders(market_id: str, limit: int = 20) -> list[dict]:
    """Largest position holders in a market, across both outcome tokens."""
    payload = get_json(
        f"{DATA_URL}/holders", params={"market": market_id, "limit": limit}
    )
    rows = payload if isinstance(payload, list) else []
    out = []
    for block in rows:
        token = block.get("token") if isinstance(block, dict) else None
        for holder in (block or {}).get("holders", []):
            out.append(
                {
                    "wallet": holder.get("proxyWallet"),
                    "name": holder.get("name") or holder.get("pseudonym"),
                    "amount": holder.get("amount"),
                    "outcome_index": holder.get("outcomeIndex"),
                    "token": token,
                }
            )
    return out


def by_wallet(trade_list: list[dict]) -> dict[str, list[dict]]:
    """Group normalized trades by wallet, for per-trader analysis."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for trade in trade_list:
        grouped[trade["wallet"]].append(trade)
    return dict(grouped)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/polymarket/test_trades.py -v -m "not network"`
Expected: PASS — 12 passed, 1 deselected

- [ ] **Step 5: Run the network test**

Run: `python -m pytest tests/polymarket/test_trades.py -v -m network`
Expected: PASS — 1 passed

- [ ] **Step 6: Commit**

```bash
git add tools/polymarket/trades.py tests/polymarket/test_trades.py
git commit -m "feat: add Polymarket trade and whale-detection client"
```

---

### Task 6: Snapshot capture

Spec section 5: the forward-history engine. `find-edge` calls this as a side effect so history accrues from ordinary use, with no scheduler.

**Files:**
- Create: `tools/snapshot.py`
- Create: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: `tools.db`, `tools.kalshi.markets`, `tools.polymarket.markets`
- Produces:
  - `tools.snapshot.save_kalshi(conn, markets: list[dict], now: str | None = None) -> int` — rows written
  - `tools.snapshot.save_polymarket(conn, markets: list[dict], now: str | None = None) -> int`
  - `tools.snapshot.history_for(conn, platform: str, market_id: str) -> list[sqlite3.Row]` — ascending by `captured_at`
  - `tools.snapshot.capture_kalshi_open(conn, limit: int = 200, max_pages: int = 5, now: str | None = None) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_snapshot.py`:

```python
import json

import pytest

from tools import db, snapshot

TS = "2026-08-23T12:00:00Z"
LATER = "2026-08-24T12:00:00Z"

KALSHI_MARKET = {
    "platform": "kalshi",
    "ticker": "KXTEST-26",
    "title": "Test market",
    "yes_bid": 0.40,
    "yes_ask": 0.42,
    "mid": 0.41,
    "volume": 1000.0,
    "open_interest": 500.0,
    "status": "active",
    "is_open": True,
    "close_time": "2026-12-01T00:00:00Z",
    "raw": {"ticker": "KXTEST-26", "volume_fp": "1000.00"},
}

POLY_MARKET = {
    "platform": "polymarket",
    "market_id": "0xabc",
    "question": "Test question?",
    "implied_prob_yes": 0.35,
    "best_bid": 0.34,
    "best_ask": 0.36,
    "volume": 5000.0,
    "end_date": "2026-12-01T00:00:00Z",
    "closed": False,
    "raw": {"conditionId": "0xabc"},
}


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def test_save_kalshi_writes_a_row(conn):
    assert snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS) == 1
    row = conn.execute("SELECT * FROM market_snapshots").fetchone()
    assert row["platform"] == "kalshi"
    assert row["market_id"] == "KXTEST-26"
    assert row["yes_bid"] == pytest.approx(0.40)
    assert row["yes_ask"] == pytest.approx(0.42)
    assert row["captured_at"] == TS


def test_save_kalshi_uses_mid_as_implied_probability(conn):
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    row = conn.execute("SELECT * FROM market_snapshots").fetchone()
    assert row["implied_prob_yes"] == pytest.approx(0.41)


def test_save_kalshi_maps_status_to_open(conn):
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    assert conn.execute(
        "SELECT status FROM market_snapshots"
    ).fetchone()["status"] == "open"


def test_save_kalshi_maps_finalized_to_settled(conn):
    settled = dict(KALSHI_MARKET, status="finalized", is_open=False)
    snapshot.save_kalshi(conn, [settled], now=TS)
    assert conn.execute(
        "SELECT status FROM market_snapshots"
    ).fetchone()["status"] == "settled"


def test_save_kalshi_preserves_the_raw_payload(conn):
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    row = conn.execute("SELECT raw_json FROM market_snapshots").fetchone()
    assert json.loads(row["raw_json"])["volume_fp"] == "1000.00"


def test_save_polymarket_writes_a_row(conn):
    assert snapshot.save_polymarket(conn, [POLY_MARKET], now=TS) == 1
    row = conn.execute("SELECT * FROM market_snapshots").fetchone()
    assert row["platform"] == "polymarket"
    assert row["market_id"] == "0xabc"
    assert row["implied_prob_yes"] == pytest.approx(0.35)
    assert row["title"] == "Test question?"


def test_snapshots_accumulate_rather_than_overwrite(conn):
    # This is the whole point: kalshi_trader overwrote its dump every fetch.
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    snapshot.save_kalshi(conn, [dict(KALSHI_MARKET, yes_ask=0.55)], now=LATER)

    history = snapshot.history_for(conn, "kalshi", "KXTEST-26")
    assert len(history) == 2
    assert history[0]["captured_at"] == TS
    assert history[1]["yes_ask"] == pytest.approx(0.55)


def test_history_for_is_ascending_by_time(conn):
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=LATER)
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    history = snapshot.history_for(conn, "kalshi", "KXTEST-26")
    assert [r["captured_at"] for r in history] == [TS, LATER]


def test_history_for_filters_by_market(conn):
    snapshot.save_kalshi(conn, [KALSHI_MARKET], now=TS)
    snapshot.save_kalshi(conn, [dict(KALSHI_MARKET, ticker="OTHER")], now=TS)
    assert len(snapshot.history_for(conn, "kalshi", "KXTEST-26")) == 1


def test_save_handles_an_empty_list(conn):
    assert snapshot.save_kalshi(conn, [], now=TS) == 0


def test_capture_kalshi_open_persists_what_it_fetches(conn, monkeypatch):
    monkeypatch.setattr(
        snapshot.kalshi_markets, "list_open",
        lambda **kwargs: [KALSHI_MARKET, dict(KALSHI_MARKET, ticker="B")],
    )
    assert snapshot.capture_kalshi_open(conn, now=TS) == 2
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM market_snapshots"
    ).fetchone()["n"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.snapshot'`

- [ ] **Step 3: Write `tools/snapshot.py`**

```python
"""First-party market history capture (spec section 5).

kalshi_trader overwrote its raw market dump on every fetch, so it retained no
history at all. This table accumulates instead — every capture is a new row.

Two reasons it matters. It hedges against either platform's own historical
API being too shallow, and it grows the clean (tier B) backtest window over
time, since markets that resolve after today are uncontaminated by any
model's training data.

find-edge calls capture_kalshi_open as a side effect, so history accrues from
ordinary use without any scheduler.
"""

from __future__ import annotations

import json
import sqlite3

from tools.db import utcnow
from tools.kalshi import markets as kalshi_markets
from tools.polymarket import markets as poly_markets

_INSERT = """
    INSERT INTO market_snapshots (
        platform, market_id, captured_at, title, implied_prob_yes,
        yes_bid, yes_ask, volume, open_interest, close_time, status, raw_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def save_kalshi(
    conn: sqlite3.Connection, markets: list[dict], now: str | None = None
) -> int:
    """Persist normalized Kalshi markets. Returns rows written."""
    stamp = now or utcnow()
    rows = [
        (
            "kalshi",
            m["ticker"],
            stamp,
            m.get("title"),
            m.get("mid"),
            m.get("yes_bid"),
            m.get("yes_ask"),
            m.get("volume"),
            m.get("open_interest"),
            m.get("close_time"),
            "open" if m.get("is_open") else "settled",
            json.dumps(m.get("raw", {})),
        )
        for m in markets
    ]
    if not rows:
        return 0
    conn.executemany(_INSERT, rows)
    conn.commit()
    return len(rows)


def save_polymarket(
    conn: sqlite3.Connection, markets: list[dict], now: str | None = None
) -> int:
    """Persist normalized Polymarket markets. Returns rows written."""
    stamp = now or utcnow()
    rows = [
        (
            "polymarket",
            m["market_id"],
            stamp,
            m.get("question"),
            m.get("implied_prob_yes"),
            m.get("best_bid"),
            m.get("best_ask"),
            m.get("volume"),
            None,
            m.get("end_date"),
            "settled" if m.get("closed") else "open",
            json.dumps(m.get("raw", {})),
        )
        for m in markets
    ]
    if not rows:
        return 0
    conn.executemany(_INSERT, rows)
    conn.commit()
    return len(rows)


def history_for(
    conn: sqlite3.Connection, platform: str, market_id: str
) -> list[sqlite3.Row]:
    """Every snapshot of one market, oldest first."""
    return conn.execute(
        """
        SELECT * FROM market_snapshots
        WHERE platform = ? AND market_id = ?
        ORDER BY captured_at
        """,
        (platform, market_id),
    ).fetchall()


def capture_kalshi_open(
    conn: sqlite3.Connection,
    limit: int = 200,
    max_pages: int = 5,
    now: str | None = None,
) -> int:
    """Fetch and persist the current open Kalshi board."""
    found = kalshi_markets.list_open(limit=limit, max_pages=max_pages)
    return save_kalshi(conn, found, now=now)


def capture_polymarket_open(
    conn: sqlite3.Connection, limit: int = 100, now: str | None = None
) -> int:
    """Fetch and persist the current open Polymarket board."""
    found = poly_markets.list_open(limit=limit)
    return save_polymarket(conn, found, now=now)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_snapshot.py -v`
Expected: PASS — 11 passed

- [ ] **Step 5: Commit**

```bash
git add tools/snapshot.py tests/test_snapshot.py
git commit -m "feat: add market snapshot capture for forward history"
```

---

### Task 7: Cross-platform market matching

The required bridge from a Polymarket finding to a tradeable Kalshi ticker (spec sections 3, 6, 9). This tool produces a **shortlist and nothing more** — deciding whether two markets are really the same is Claude's judgment, and it must compare resolution criteria, not just topic.

**Files:**
- Create: `tools/match_market.py`
- Create: `tests/test_match_market.py`

**Interfaces:**
- Consumes: `tools.kalshi.markets`
- Produces:
  - `tools.match_market.tokenize(text: str) -> set[str]`
  - `tools.match_market.score_pair(source_text: str, candidate_text: str, source_end: str | None = None, candidate_end: str | None = None) -> float`
  - `tools.match_market.shortlist(source: dict, candidates: list[dict], top_n: int = 5, min_score: float = 0.1) -> list[dict]` — each entry `{"ticker", "title", "score", "rules_primary", "close_time", "market"}`
  - `tools.match_market.STOPWORDS: frozenset[str]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_match_market.py`:

```python
import pytest

from tools import match_market


def _kalshi(ticker, title, close_time="2026-11-03T00:00:00Z", rules="Rules."):
    return {
        "platform": "kalshi",
        "ticker": ticker,
        "title": title,
        "close_time": close_time,
        "rules_primary": rules,
    }


def _poly(question, end_date="2026-11-03T00:00:00Z"):
    return {
        "platform": "polymarket",
        "market_id": "0xabc",
        "question": question,
        "end_date": end_date,
    }


def test_tokenize_lowercases_and_splits():
    assert match_market.tokenize("Will Biden Win?") >= {"biden", "win"}


def test_tokenize_drops_stopwords():
    tokens = match_market.tokenize("Will the president be elected?")
    assert "will" not in tokens
    assert "the" not in tokens
    assert "president" in tokens


def test_tokenize_handles_punctuation_and_empty():
    assert match_market.tokenize("U.S. election -- 2026!") >= {"election", "2026"}
    assert match_market.tokenize("") == set()


def test_score_pair_is_high_for_near_identical_text():
    score = match_market.score_pair(
        "Will Anthropic IPO before 2030?",
        "Will Anthropic IPO before 2030?",
    )
    assert score > 0.9


def test_score_pair_is_zero_for_unrelated_text():
    score = match_market.score_pair(
        "Will Anthropic IPO before 2030?",
        "Highest temperature in Miami on Tuesday",
    )
    assert score == pytest.approx(0.0)


def test_score_pair_rewards_close_end_dates():
    near = match_market.score_pair(
        "Anthropic IPO", "Anthropic IPO",
        source_end="2026-11-03T00:00:00Z",
        candidate_end="2026-11-04T00:00:00Z",
    )
    far = match_market.score_pair(
        "Anthropic IPO", "Anthropic IPO",
        source_end="2026-11-03T00:00:00Z",
        candidate_end="2029-11-04T00:00:00Z",
    )
    assert near > far


def test_score_pair_tolerates_missing_dates():
    score = match_market.score_pair("Anthropic IPO", "Anthropic IPO")
    assert score > 0.0


def test_shortlist_ranks_the_best_match_first():
    source = _poly("Will Anthropic IPO before 2030?")
    candidates = [
        _kalshi("WEATHER-1", "Highest temperature in Miami"),
        _kalshi("IPO-ANTH", "Will Anthropic IPO before 2030?"),
        _kalshi("IPO-OAI", "Will OpenAI IPO before 2030?"),
    ]
    result = match_market.shortlist(source, candidates)
    assert result[0]["ticker"] == "IPO-ANTH"


def test_shortlist_respects_top_n():
    source = _poly("Anthropic IPO 2030")
    candidates = [_kalshi(f"T{i}", "Anthropic IPO 2030") for i in range(10)]
    assert len(match_market.shortlist(source, candidates, top_n=3)) == 3


def test_shortlist_drops_candidates_below_min_score():
    source = _poly("Will Anthropic IPO before 2030?")
    candidates = [_kalshi("WEATHER-1", "Highest temperature in Miami")]
    assert match_market.shortlist(source, candidates) == []


def test_shortlist_includes_resolution_rules_for_judgment():
    # The whole point: Claude must compare settlement rules, not just topic.
    source = _poly("Will Anthropic IPO before 2030?")
    candidates = [
        _kalshi("IPO-ANTH", "Will Anthropic IPO before 2030?",
                rules="Resolves Yes if an S-1 is publicly filed.")
    ]
    result = match_market.shortlist(source, candidates)
    assert "S-1" in result[0]["rules_primary"]


def test_shortlist_handles_a_kalshi_source():
    # Matching should work in either direction.
    source = _kalshi("IPO-ANTH", "Will Anthropic IPO before 2030?")
    candidates = [_kalshi("IPO-ANTH-2", "Will Anthropic IPO before 2030?")]
    assert match_market.shortlist(source, candidates)[0]["score"] > 0.9


def test_shortlist_handles_empty_candidates():
    assert match_market.shortlist(_poly("anything"), []) == []


def test_shortlist_returns_the_full_market_for_downstream_use():
    source = _poly("Will Anthropic IPO before 2030?")
    candidates = [_kalshi("IPO-ANTH", "Will Anthropic IPO before 2030?")]
    result = match_market.shortlist(source, candidates)
    assert result[0]["market"]["ticker"] == "IPO-ANTH"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_match_market.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.match_market'`

- [ ] **Step 3: Write `tools/match_market.py`**

```python
"""Mechanical cross-platform market matching (spec sections 3, 6, 9).

This tool narrows thousands of Kalshi markets to a handful of plausible
equivalents for a Polymarket (or other non-Kalshi) finding. It deliberately
stops there.

Deciding whether two markets are REALLY the same is a judgment call and
belongs to Claude or a subagent reading this shortlist — and that judgment
must compare RESOLUTION CRITERIA, not just topic. Two markets about the same
event with different settlement rules are different markets, and a keyword
score cannot see the difference. That is why `rules_primary` travels with
every candidate.
"""

from __future__ import annotations

import re
from datetime import datetime

STOPWORDS = frozenset(
    """
    a an the will be is are was were do does did to of in on at by for from
    with and or if then than that this these those it its as into over under
    before after between during about who whom which what when where how
    """.split()
)

DATE_WEIGHT = 0.2
TOKEN_WEIGHT = 0.8
_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set[str]:
    """Lowercase content words, stopwords removed."""
    if not text:
        return set()
    return {
        word
        for word in _WORD.findall(text.lower())
        if word not in STOPWORDS and len(word) > 1
    }


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def _date_similarity(source_end: str | None, candidate_end: str | None) -> float:
    """1.0 for same-day, decaying to 0 across a year apart."""
    left, right = _parse(source_end), _parse(candidate_end)
    if left is None or right is None:
        return 0.5  # unknown: neither reward nor punish
    days = abs((left - right).days)
    return max(0.0, 1.0 - days / 365.0)


def score_pair(
    source_text: str,
    candidate_text: str,
    source_end: str | None = None,
    candidate_end: str | None = None,
) -> float:
    """Similarity in [0, 1]: Jaccard token overlap plus date proximity."""
    left, right = tokenize(source_text), tokenize(candidate_text)
    if not left or not right:
        return 0.0
    overlap = len(left & right) / len(left | right)
    if overlap == 0.0:
        return 0.0
    date_score = _date_similarity(source_end, candidate_end)
    return TOKEN_WEIGHT * overlap + DATE_WEIGHT * date_score


def _text_of(market: dict) -> str:
    return market.get("question") or market.get("title") or ""


def _end_of(market: dict) -> str | None:
    return market.get("end_date") or market.get("close_time")


def shortlist(
    source: dict,
    candidates: list[dict],
    top_n: int = 5,
    min_score: float = 0.1,
) -> list[dict]:
    """Plausible Kalshi equivalents for `source`, best first.

    A shortlist, not a decision. Every entry carries `rules_primary` so the
    judgment step can compare settlement criteria rather than topic alone.
    """
    source_text = _text_of(source)
    source_end = _end_of(source)

    scored = []
    for market in candidates:
        score = score_pair(
            source_text, _text_of(market), source_end, _end_of(market)
        )
        if score < min_score:
            continue
        scored.append(
            {
                "ticker": market.get("ticker"),
                "title": market.get("title"),
                "score": score,
                "rules_primary": market.get("rules_primary"),
                "close_time": market.get("close_time"),
                "market": market,
            }
        )

    scored.sort(key=lambda entry: entry["score"], reverse=True)
    return scored[:top_n]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_match_market.py -v`
Expected: PASS — 14 passed

- [ ] **Step 5: Run the full offline suite**

Run: `python -m pytest -m "not network" -v`
Expected: PASS — 191 passed (111 from Plan 1, plus 6 http + 15 kalshi markets + 9 kalshi history + 13 polymarket markets + 12 polymarket trades + 11 snapshot + 14 match_market)

- [ ] **Step 6: Run the network suite once**

Run: `python -m pytest -m network -v`
Expected: PASS — 4 passed. A failure here means a provider schema changed; fix the affected `normalize` and note it in the theory or spec risks.

- [ ] **Step 7: Commit**

```bash
git add tools/match_market.py tests/test_match_market.py
git commit -m "feat: add mechanical cross-platform market matching"
```

---

## Definition of done for Plan 2

- `python -m pytest -m "not network"` passes with no failures.
- `python -m pytest -m network` passes against the live public APIs.
- No API key, credential, or user identifier appears anywhere in `tools/`.
- Kalshi markets normalize decimal-dollar strings and `_fp` sizes to floats, expose `spread` and `mid`, carry `rules_primary`, and raise on an unrecognized shape rather than emitting zeros.
- `history.point_in_time` never returns a candle after its `as_of_ts`.
- Polymarket markets parse JSON-encoded string arrays, and whale trades filter server-side by USD notional.
- Snapshots accumulate across captures rather than overwriting.
- `match_market.shortlist` returns ranked candidates carrying `rules_primary`, and makes no matching decision of its own.
