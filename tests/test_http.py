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
