from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest


STUDY_DIR = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, STUDY_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


batches = _load("batches")
capture_books = _load("capture_books")


def _prepare(tmp_path: Path, markets: list[dict]) -> tuple[Path, Path]:
    census = tmp_path / "census.json"
    census.write_text(
        json.dumps(
            {
                "as_of": "2026-09-05T15:45:16Z",
                "events": [{"event_key": "EV", "markets": markets}],
            }
        ),
        encoding="utf-8",
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Classify without prices", encoding="utf-8")
    root = tmp_path / "judgments"
    batches.prepare(census, root, prompt)
    return root, root / "batch-000"


def _verdict(key: str, bucket: str) -> dict:
    return {
        "key": key,
        "bucket": bucket,
        "subject_key": key.lower(),
        "family": "test-family",
        "rationale": "Dated evidence was checked.",
        "sources": [] if bucket == "insufficient_evidence" else [{"url": "https://example.test"}],
    }


def test_depth_uses_complementary_bids_and_rounds_multiplier_fee_per_level():
    orderbook = {
        "yes_dollars": [["0.70", "25"], ["0.65", "50"]],
        "no_dollars": [["0.60", "60"], ["0.50", "100"]],
    }
    fee = capture_books.FeeSpec.quadratic(multiplier=2)

    curves = capture_books.depth_curves(orderbook, fee, targets=(100,))

    yes = curves["buy_yes"]["100"]
    assert yes["best_ask"] == pytest.approx(0.40)
    assert yes["worst_ask"] == pytest.approx(0.50)
    assert yes["average_price"] == pytest.approx(0.44)
    # Per-level fees: ceil($2.016) + ceil($1.400), not one fee at VWAP.
    assert yes["fee_dollars"] == pytest.approx(3.42)
    assert yes["average_payable"] == pytest.approx(0.4742)
    no = curves["buy_no"]["100"]
    assert no["best_ask"] == pytest.approx(0.30)
    assert no["filled_contracts"] == pytest.approx(75)
    assert no["fill_complete"] is False
    assert no["fee_dollars"] is None
    assert no["average_payable"] is None


def test_complement_does_not_add_a_cent_at_exact_fee_boundary():
    book = {'yes_dollars': [['0.70', '100']], 'no_dollars': [['0.60', '100']]}
    curve = capture_books.depth_curves(book, capture_books.FeeSpec.quadratic(1), targets=(100,))['buy_no']['100']
    assert curve['best_ask'] == .30
    assert curve['fee_dollars'] == 1.47


def test_unknown_or_unsupported_fee_never_becomes_a_number():
    orderbook = {"yes_dollars": [["0.70", "100"]], "no_dollars": [["0.60", "100"]]}

    for fee in (capture_books.FeeSpec.unknown("missing"), capture_books.FeeSpec.unknown("linear")):
        row = capture_books.depth_curves(orderbook, fee, targets=(100,))["buy_yes"]["100"]
        assert row["fill_complete"] is True
        assert row["average_price"] == pytest.approx(0.40)
        assert row["fee_dollars"] is None
        assert row["average_payable"] is None


def test_incomplete_first_output_is_not_read_for_capture(tmp_path):
    root, batch = _prepare(
        tmp_path,
        [
            {"key": "TICKER-A", "series": "SERIES", "title": "A"},
            {"key": "TICKER-B", "series": "SERIES", "title": "B"},
        ],
    )
    (batch / "first-output.jsonl").write_text(
        json.dumps(_verdict("TICKER-A", "insufficient_evidence")) + "\n",
        encoding="utf-8",
    )
    calls = []

    summary = capture_books.capture_completed_batches(
        root, fetch=lambda *args, **kwargs: calls.append((args, kwargs))
    )

    assert summary == {"captured_batches": 0, "skipped_incomplete": 1, "skipped_existing": 0}
    assert calls == []
    assert not (batch / "book-capture.json").exists()


def test_capture_keeps_all_labels_missing_books_mtime_and_resumes(tmp_path):
    root, batch = _prepare(
        tmp_path,
        [
            {"key": "TICKER-A", "series": "SERIES", "title": "A"},
            {"key": "TICKER-B", "series": "SERIES", "title": "B"},
        ],
    )
    output = batch / "first-output.jsonl"
    output.write_text(
        "\n".join(
            [
                json.dumps(_verdict("TICKER-A", "substantive_barrier")),
                json.dumps(_verdict("TICKER-B", "not_applicable")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    exact_mtime_ns = 1_788_624_000_123_456_789
    os.utime(output, ns=(exact_mtime_ns, exact_mtime_ns))
    stored_mtime_ns = output.stat().st_mtime_ns
    calls: list[str] = []

    def fake_fetch(url, *, params=None, raw_dir, label):
        calls.append(url)
        receipt = {
            "url": url,
            "captured_utc": "2026-09-05T17:00:01Z",
            "status": 200,
            "sha256": "a" * 64,
            "response_path": f"raw/{label}.json",
        }
        if url.endswith("/markets/TICKER-A"):
            return {
                "market": {
                    "ticker": "TICKER-A",
                    "event_ticker": "EV",
                    "series_ticker": "SERIES",
                    "title": "Fresh A",
                    "rules_primary": "Fresh rule A",
                    "rules_secondary": "Secondary A",
                    "status": "active",
                }
            }, [receipt]
        if url.endswith("/markets/TICKER-B"):
            return {
                "market": {
                    "ticker": "TICKER-B",
                    "event_ticker": "EV",
                    "series_ticker": "SERIES",
                    "title": "Fresh B",
                    "rules_primary": "Fresh rule B",
                    "rules_secondary": "Secondary B",
                    "status": "active",
                }
            }, [receipt]
        if url.endswith("/markets/TICKER-A/orderbook"):
            return {
                "orderbook_fp": {
                    "yes_dollars": [["0.70", "1000"]],
                    "no_dollars": [["0.60", "1000"]],
                }
            }, [receipt]
        if url.endswith("/markets/TICKER-B/orderbook"):
            raise capture_books.CaptureFailure("book unavailable", [dict(receipt, status=503)])
        if url.endswith("/series/SERIES"):
            return {
                "series": {
                    "ticker": "SERIES",
                    "fee_type": "quadratic",
                    "fee_multiplier": 2,
                    "last_updated_ts": "2026-09-05T16:59:00Z",
                }
            }, [receipt]
        if url.endswith("/series/fee_changes"):
            assert params == {"series_ticker": "SERIES", "show_historical": "true"}
            return {"series_fee_change_arr": []}, [receipt]
        raise AssertionError(url)

    now = lambda: datetime(2026, 9, 5, 17, 0, tzinfo=timezone.utc)
    first = capture_books.capture_completed_batches(root, fetch=fake_fetch, now=now, workers=4)
    saved_bytes = (batch / "book-capture.json").read_bytes()
    second = capture_books.capture_completed_batches(root, fetch=fake_fetch, now=now, workers=4)
    captured = json.loads(saved_bytes)

    assert first == {"captured_batches": 1, "skipped_incomplete": 0, "skipped_existing": 0}
    assert second == {"captured_batches": 0, "skipped_incomplete": 0, "skipped_existing": 1}
    assert saved_bytes == (batch / "book-capture.json").read_bytes()
    assert captured["candidate_keys"] == ["TICKER-A", "TICKER-B"]
    assert captured["judgments"]["TICKER-A"]["bucket"] == "substantive_barrier"
    assert captured["judgments"]["TICKER-B"]["bucket"] == "not_applicable"
    assert captured["first_output"]["mtime_ns"] == stored_mtime_ns
    assert captured["capture_lag_seconds"] == pytest.approx(
        datetime(2026, 9, 5, 17, 0, tzinfo=timezone.utc).timestamp()
        - stored_mtime_ns / 1_000_000_000
    )
    assert captured["markets"]["TICKER-A"]["rules_status"] == {
        "status": "active",
        "rules_primary": "Fresh rule A",
        "rules_secondary": "Secondary A",
    }
    assert captured["markets"]["TICKER-A"]["depth_curves"]["buy_yes"]["100"]["fee_dollars"] == pytest.approx(3.36)
    assert captured["markets"]["TICKER-B"]["depth_curves"] is None
    assert captured["markets"]["TICKER-B"]["failures"][0]["status"] == 503
    assert calls.count(capture_books.BASE_URL + "/series/SERIES") == 1
    assert calls.count(capture_books.BASE_URL + "/series/fee_changes") == 1
    assert len(calls) == 6  # The resume performs no HTTP work.


class _Response:
    def __init__(self, status: int, body: bytes, url: str):
        self.status_code = status
        self.content = body
        self.url = url
        self.headers = {}


def test_fetch_retries_and_preserves_every_response_body(tmp_path):
    responses = iter(
        [
            _Response(503, b'{"error":"later"}', "https://example.test/endpoint"),
            _Response(200, b'{"ok":true}', "https://example.test/endpoint"),
        ]
    )

    payload, receipts = capture_books.fetch_json(
        "https://example.test/endpoint",
        raw_dir=tmp_path,
        label="endpoint",
        request=lambda *args, **kwargs: next(responses),
        sleep=lambda _: None,
        now=lambda: datetime(2026, 9, 5, 17, 0, tzinfo=timezone.utc),
    )

    assert payload == {"ok": True}
    assert [row["status"] for row in receipts] == [503, 200]
    for index, body in enumerate((b'{"error":"later"}', b'{"ok":true}'), 1):
        receipt = receipts[index - 1]
        assert (tmp_path / f"endpoint-attempt-{index}.json").read_bytes() == body
        assert receipt["url"] == "https://example.test/endpoint"
        assert receipt["captured_utc"] == "2026-09-05T17:00:00.000000Z"
        assert receipt["sha256"] == hashlib.sha256(body).hexdigest()
