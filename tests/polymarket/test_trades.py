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


def test_recent_skips_unparseable_trades(monkeypatch):
    # One bad row must not sink the whole page.
    monkeypatch.setattr(
        trades, "get_json",
        lambda *a, **k: [RAW, {"size": 1, "price": 0.5}],
    )
    assert len(trades.recent()) == 1


def test_recent_raises_when_every_row_is_unparseable(monkeypatch):
    # A page that is entirely malformed is schema drift, not "no trades".
    monkeypatch.setattr(
        trades, "get_json",
        lambda *a, **k: [{"size": 1, "price": 0.5},
                         {"size": 2, "price": 0.4}],
    )
    with pytest.raises(ValueError, match="none parsed"):
        trades.recent()


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
