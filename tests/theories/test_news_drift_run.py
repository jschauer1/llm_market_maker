from datetime import datetime, timedelta, timezone

import pytest


def test_record_collection_uses_quote_time_and_never_invents_an_edge(conn):
    from theories.news_drift.run import record_collection

    quoted = datetime(2026, 9, 4, tzinfo=timezone.utc)
    end = int(quoted.timestamp())
    bars = [{"end_ts": end - (4 - i) * 86400, "yes_bid_close": mid - .01,
             "yes_ask_close": mid + .01, "volume": vol, "open_interest": 200}
            for i, (mid, vol) in enumerate(zip([.3, .3, .3, .5, .55], [10, 10, 10, 20, 30]))]
    collection = {"quotes": {"fetch_completed_at": quoted.isoformat()},
                  "history": {"rows_by_ticker": {"KXTEST-A-Y": bars}},
                  "signals": [{"ticker": "KXTEST-A-Y", "event_ticker": "KXTEST-A",
                               "series_ticker": "KXTEST", "title": "test",
                               "event": {"category": "Politics"},
                               "quote": {"yes_bid": .54, "yes_ask": .56,
                                         "no_ask": .46, "status": "active",
                                         "open_interest": 200, "volume_24h": 30}}]}
    result = record_collection(conn, collection, now=quoted + timedelta(minutes=5))
    assert len(result.opportunity_ids) == 1
    assert result.scored[0].edge.pts_net == 0
    assert result.scored[0].edge.basis == "prior"
    attempt = conn.execute("SELECT decision_date, entry_price FROM opportunity_attempts").fetchone()
    assert attempt["decision_date"] == "2026-09-04"
    assert attempt["entry_price"] == .56
    with pytest.raises(ValueError, match="stale"):
        record_collection(conn, collection, now=quoted + timedelta(hours=2))
