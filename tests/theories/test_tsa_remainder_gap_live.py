from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json

import pytest

from tools.theory import TheoryContext

from tests.theories.test_tsa_remainder_gap import WEEK_END, _counts, _market


UTC = timezone.utc


def test_live_wrong_time_stops_before_any_orderbook_fetch():
    from theories.tsa_remainder_gap.theory import TsaRemainderGapTheory

    calls = []
    theory = TsaRemainderGapTheory(_counts(), fetch=lambda *a, **k: calls.append(a))
    result = theory.start(TheoryContext(
        conn=None, board=[_market()],
        now=datetime(2026, 9, 4, 14, 59, tzinfo=UTC),
        run_id="live", run_mode="live",
    )).finish(dry_run=True)

    assert result.scored == ()
    assert result.gate_removed == {"outside_entry_window": 1}
    assert calls == []


@pytest.mark.parametrize(
    ("size", "expected_n"),
    [(9, 0), (10, 1)],
)
def test_live_requires_ten_contracts_at_the_exact_best_ask(
    size, expected_n
):
    from theories.tsa_remainder_gap.theory import TsaRemainderGapTheory

    def fetch(url, params=None, timeout=30):
        return {"orderbook_fp": {"yes_dollars": [], "no_dollars": [["0.80", str(size)]]}}

    theory = TsaRemainderGapTheory(_counts(), fetch=fetch)
    result = theory.start(TheoryContext(
        conn=None, board=[_market()],
        now=datetime(2026, 9, 4, 15, 5, tzinfo=UTC),
        run_id="live", run_mode="live",
    )).finish(dry_run=True)

    assert len(result.scored) == expected_n
    if expected_n:
        assert result.scored[0].edge.basis == "model"
        assert result.scored[0].extra["best_ask_depth"] == size


def test_live_shallow_top_gap_does_not_block_liquid_runner_up():
    from theories.tsa_remainder_gap.theory import TsaRemainderGapTheory

    def fetch(url, params=None, timeout=30):
        ticker = url.rsplit("/", 2)[-2]
        if ticker.endswith("-B"):
            return {"orderbook_fp": {"yes_dollars": [], "no_dollars": [["0.90", "9"]]}}
        return {"orderbook_fp": {"yes_dollars": [], "no_dollars": [["0.80", "10"]]}}

    board = [
        _market("KXTSAW-26SEP06-B", ask=.10, bid=.05),
        _market("KXTSAW-26SEP06-A", ask=.20, bid=.15),
    ]
    result = TsaRemainderGapTheory(_counts(), fetch=fetch).start(TheoryContext(
        conn=None, board=board,
        now=datetime(2026, 9, 4, 15, 5, tzinfo=UTC),
        run_id="live", run_mode="live",
    )).finish(dry_run=True)

    assert [row.candidate.ticker for row in result.scored] == ["KXTSAW-26SEP06-A"]


def _collection(tmp_path):
    counts = _counts()
    receipts = []
    identities = []
    for year in (2025, 2026):
        rows = "".join(
            f"<tr><td>{date.fromisoformat(day):%m/%d/%Y}</td><td>{value:,}</td></tr>"
            for day, value in sorted(counts.items())
            if date.fromisoformat(day).year == year
        )
        payload = f"<table><tr><th>Date</th><th>{year}</th></tr>{rows}</table>"
        receipt = tmp_path / f"tsa-{year}.html"
        receipt.write_text(payload, encoding="utf-8")
        digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
        url = f"https://example.test/tsa/{year}"
        receipts.append({
            "path": str(receipt), "sha256": digest, "url": url, "year": year,
        })
        identities.append({"url": url, "sha256": digest})
    source_digest = hashlib.sha256(json.dumps(
        identities, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    source_at = datetime(2026, 9, 4, 15, 2, tzinfo=UTC)
    quoted_at = datetime(2026, 9, 4, 15, 5, tzinfo=UTC)
    collection = {
        "status": "complete",
        "protocol": "TRG-1",
        "week_end": WEEK_END.isoformat(),
        "source_fetch_completed_at": source_at.isoformat(),
        "quote_fetch_completed_at": quoted_at.isoformat(),
        "source_digest": source_digest,
        "source_receipts": receipts,
        "daily_counts": counts,
        "board": [asdict(_market())],
        "orderbooks": {
            "KXTSAW-26SEP06-A": {
                "orderbook_fp": {"yes_dollars": [], "no_dollars": [["0.80", "10"]]}
            }
        },
    }
    collection["board"][0]["raw"]["source_digest"] = source_digest
    return collection


def test_record_collection_rejects_counts_changed_after_receipt_parse(conn, tmp_path):
    from theories.tsa_remainder_gap.run import record_collection

    collection = _collection(tmp_path)
    collection["daily_counts"]["2026-09-03"] += 1

    with pytest.raises(ValueError, match="daily counts do not match"):
        record_collection(
            conn, collection,
            now=datetime(2026, 9, 4, 15, 10, tzinfo=UTC),
        )


def test_record_collection_atomically_dedupes_the_week_across_repeated_runs(
    conn, tmp_path
):
    from theories.tsa_remainder_gap.run import record_collection

    collection = _collection(tmp_path)
    now = datetime(2026, 9, 4, 15, 10, tzinfo=UTC)
    first = record_collection(conn, collection, now=now)
    second = record_collection(conn, collection, now=now + timedelta(minutes=1))

    assert len(first["opportunity_ids"]) == 1
    assert second["opportunity_ids"] == []
    assert second["duplicate_weeks"] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM opportunity_attempts"
    ).fetchone()[0] == 1


def test_record_collection_refuses_1530_even_when_source_and_quote_are_fresh(
    conn, tmp_path
):
    from theories.tsa_remainder_gap.run import record_collection

    collection = _collection(tmp_path)
    with pytest.raises(ValueError, match="entry window"):
        record_collection(
            conn, collection,
            now=datetime(2026, 9, 4, 15, 30, tzinfo=UTC),
        )


def test_collect_live_outside_window_does_not_touch_board_or_sources(conn):
    from theories.tsa_remainder_gap.run import collect_live

    calls = []
    result = collect_live(
        conn,
        now=datetime(2026, 9, 4, 14, 59, tzinfo=UTC),
        fetch=lambda *a, **k: calls.append("json"),
        fetch_html=lambda *a, **k: calls.append("html"),
    )

    assert result["status"] == "outside_entry_window"
    assert calls == []


def test_collect_live_reparses_fresh_quote_rules_and_excludes_changed_source(
    conn, tmp_path, monkeypatch
):
    from theories.tsa_remainder_gap import run

    monkeypatch.setattr(run.board_store, "get_board", lambda conn: [_market()])
    counts = _counts()

    def html(url):
        year = 2025 if url.endswith("/2025") else 2026
        rows = "".join(
            f"<tr><td>{date.fromisoformat(day):%m/%d/%Y}</td><td>{value:,}</td></tr>"
            for day, value in sorted(counts.items())
            if date.fromisoformat(day).year == year
        )
        return f"<table><tr><th>Date</th><th>{year}</th></tr>{rows}</table>".encode()

    def fetch(url, params=None, timeout=30):
        assert url.endswith("/markets")
        raw = dict(_market().raw)
        raw.update({
            "rules_primary": "This changed contract resolves from a private survey.",
            "yes_bid_dollars": "0.15", "yes_ask_dollars": "0.20",
            "no_bid_dollars": "0.80", "no_ask_dollars": "0.85",
            "open_interest_fp": "200", "volume_fp": "10",
            "volume_24h_fp": "10", "status": "open",
        })
        return {"markets": [raw]}

    times = iter([
        datetime(2026, 9, 4, 15, 2, tzinfo=UTC),
        datetime(2026, 9, 4, 15, 5, tzinfo=UTC),
    ])
    result = run.collect_live(
        conn, now=datetime(2026, 9, 4, 15, tzinfo=UTC),
        fetch=fetch, fetch_html=html, clock=lambda: next(times),
        data_dir=tmp_path,
    )

    assert result["board"] == []
    assert result["gate_removed"]["fresh_contract_invalid"] == 1


def test_collect_cli_retains_inputs_without_recording(monkeypatch, capsys):
    from theories.tsa_remainder_gap import run

    class Connection:
        def close(self):
            pass

    monkeypatch.setattr(run.db, "connect", lambda: Connection())
    initialized = []
    monkeypatch.setattr(run.db, "init_db", lambda conn: initialized.append(conn))
    monkeypatch.setattr(run, "collect_live", lambda *a, **k: {
        "status": "complete", "protocol": "TRG-1",
        "collection_path": "capture.json", "funnel": {"candidates": 1},
    })
    monkeypatch.setattr(
        run, "record_collection",
        lambda *a, **k: pytest.fail("--collect must not write the ledger"),
    )

    assert run.main(["--collect"]) == 0
    assert len(initialized) == 1
    assert json.loads(capsys.readouterr().out)["collection_path"] == "capture.json"
