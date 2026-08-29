import json

import pytest
import requests

from tools import http


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    """Stands in for the pooled requests.Session the module now keeps."""

    def __init__(self, get):
        self.get = get


def patch_get(monkeypatch, get):
    """Point tools.http at a fake session whose .get is `get`."""
    session = FakeSession(get)
    monkeypatch.setattr(http, "_session", lambda: session)
    return session


def test_returns_parsed_json_on_success(monkeypatch):
    patch_get(monkeypatch,
        lambda *a, **k: FakeResponse(200, {"ok": True}),
    )
    assert http.get_json("https://example.test") == {"ok": True}


def test_passes_params_through(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        captured["url"] = url
        captured["params"] = params
        return FakeResponse(200, [])

    patch_get(monkeypatch, fake_get)
    http.get_json("https://example.test", params={"limit": 5})
    assert captured["params"] == {"limit": 5}


def test_retries_on_429_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            return FakeResponse(429)
        return FakeResponse(200, {"ok": True})

    patch_get(monkeypatch, fake_get)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    assert http.get_json("https://example.test") == {"ok": True}
    assert calls["n"] == 3


def test_retries_on_500_then_gives_up(monkeypatch):
    patch_get(monkeypatch, lambda *a, **k: FakeResponse(503))
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    with pytest.raises(http.HttpError, match="503"):
        http.get_json("https://example.test", max_retries=2)


def test_does_not_retry_on_404(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **k):
        calls["n"] += 1
        return FakeResponse(404)

    patch_get(monkeypatch, fake_get)
    with pytest.raises(http.HttpError, match="404"):
        http.get_json("https://example.test")
    assert calls["n"] == 1, "client errors must not be retried"


def test_retries_on_connection_error_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.exceptions.ConnectionError("boom")
        return FakeResponse(200, {"ok": True})

    sleeps = []
    patch_get(monkeypatch, fake_get)
    monkeypatch.setattr(http.time, "sleep", lambda s: sleeps.append(s))
    assert http.get_json("https://example.test") == {"ok": True}
    assert calls["n"] == 3
    assert sleeps, "expected a backoff sleep between retries"


def test_raises_http_error_after_exhausting_retries_on_connection_error(
    monkeypatch,
):
    def fake_get(*a, **k):
        raise requests.exceptions.ConnectionError("boom")

    patch_get(monkeypatch, fake_get)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    with pytest.raises(http.HttpError):
        http.get_json("https://example.test", max_retries=2)


def test_raises_http_error_on_non_json_response(monkeypatch):
    class BadJsonResponse(FakeResponse):
        def json(self):
            raise json.JSONDecodeError("Expecting value", "<html>", 0)

    patch_get(monkeypatch, lambda *a, **k: BadJsonResponse(200))
    with pytest.raises(http.HttpError):
        http.get_json("https://example.test")


def test_backoff_grows_between_attempts(monkeypatch):
    delays = []
    patch_get(monkeypatch, lambda *a, **k: FakeResponse(429))
    monkeypatch.setattr(http.time, "sleep", lambda s: delays.append(s))
    with pytest.raises(http.HttpError):
        http.get_json("https://example.test", max_retries=3)
    assert delays == sorted(delays)
    assert len(delays) >= 2


def test_one_pooled_session_is_reused_across_calls(monkeypatch):
    """Connection reuse, not politeness: the calibration_harvest collector
    spends 99.5% of its wall clock in per-market candlestick GETs, and a
    fresh TLS handshake per call was most of that 244ms."""
    seen = []

    def fake_get(*a, **k):
        seen.append(object())
        return FakeResponse(200, {"ok": True})

    session = patch_get(monkeypatch, fake_get)
    for _ in range(5):
        http.get_json("https://example.test")
    assert len(seen) == 5
    assert http._session() is session


def test_the_real_session_is_created_once_per_thread():
    http._local.__dict__.pop("session", None)
    first = http._session()
    assert http._session() is first
    assert isinstance(first, requests.Session)

    # requests.Session is not thread-safe, so each thread gets its own --
    # and each thread gets the SAME one on every call, which is the half
    # that makes pooling work.
    import threading

    seen = []

    def in_thread():
        seen.append((http._session(), http._session()))

    threads = [threading.Thread(target=in_thread) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(seen) == 2
    for a, b in seen:
        assert a is b, "one session per thread, reused"
        assert a is not first, "not shared with the calling thread"
    assert seen[0][0] is not seen[1][0], "the two threads differ"
