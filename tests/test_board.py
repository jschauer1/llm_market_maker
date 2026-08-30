import json

import pytest

from tools import board, db, snapshot

NOW = "2026-08-24T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def _raw(ticker, event="EV", series="KXTHING", **kw):
    base = {
        "ticker": ticker, "event_ticker": event, "series_ticker": series,
        "title": f"title {ticker}", "rules_primary": "rules",
        "status": "active", "close_time": "2026-09-01T00:00:00Z",
        "yes_bid_dollars": "0.80", "yes_ask_dollars": "0.82",
        "no_bid_dollars": "0.18", "no_ask_dollars": "0.20",
        "volume_fp": "900", "open_interest_fp": "500",
        # Bulk the raw payload out the way the live API does.
        "junk_a": "x" * 500, "junk_b": list(range(50)),
    }
    base.update(kw)
    return base


def _board(n=3):
    from tools.kalshi import markets
    return [markets.normalize(_raw(f"T-{i}")) for i in range(n)]


# --- board_info -------------------------------------------------------


def test_board_info_is_none_with_no_snapshots(conn):
    assert board.board_info(conn, now=NOW) is None


def test_board_info_reports_age_and_size(conn):
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:00:00Z")
    info = board.board_info(conn, now=NOW)
    assert info["markets"] == 3
    assert info["age_minutes"] == pytest.approx(60.0)


def test_board_info_uses_only_the_freshest_batch(conn):
    snapshot.save_kalshi(conn, _board(5), now="2026-08-23T12:00:00Z")
    snapshot.save_kalshi(conn, _board(2), now="2026-08-24T11:30:00Z")
    info = board.board_info(conn, now=NOW)
    assert info["markets"] == 2
    assert info["age_minutes"] == pytest.approx(30.0)


# --- caching ----------------------------------------------------------


def test_fresh_snapshot_is_reused_without_fetching(conn, monkeypatch):
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:00:00Z")

    def boom():
        raise AssertionError("list_open must not be called on a cache hit")
    monkeypatch.setattr(board.kalshi_markets, "list_open", boom)

    got = board.get_board(conn, now=NOW)
    assert [m.ticker for m in got] == ["T-0", "T-1", "T-2"]


def test_stale_snapshot_triggers_a_fetch(conn, monkeypatch):
    snapshot.save_kalshi(conn, _board(3), now="2026-08-20T12:00:00Z")
    calls = []
    monkeypatch.setattr(board.kalshi_markets, "list_open",
                        lambda: calls.append(1) or _board(7))
    got = board.get_board(conn, now=NOW)
    assert len(calls) == 1
    assert len(got) == 7


def test_no_snapshot_at_all_fetches(conn, monkeypatch):
    calls = []
    monkeypatch.setattr(board.kalshi_markets, "list_open",
                        lambda: calls.append(1) or _board(4))
    assert len(board.get_board(conn, now=NOW)) == 4
    assert len(calls) == 1


def test_force_refetches_past_the_floor(conn, monkeypatch):
    # 31 minutes old: stale under the force floor, fresh under the
    # 4-hour default -- exactly the window where force must still act.
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:29:00Z")
    calls = []
    monkeypatch.setattr(board.kalshi_markets, "list_open",
                        lambda: calls.append(1) or _board(9))
    got = board.get_board(conn, force=True, now=NOW)
    assert len(calls) == 1 and len(got) == 9


def test_force_honours_an_explicitly_tighter_max_age(conn, monkeypatch):
    # 20 minutes old: within the 30-minute force floor, so a bare
    # force=True would reuse it -- but the caller passed max_age=10,
    # explicitly asking for something fresher than the floor guarantees,
    # and that must be honoured rather than overridden by force.
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:40:00Z")
    calls = []
    monkeypatch.setattr(board.kalshi_markets, "list_open",
                        lambda: calls.append(1) or _board(9))
    got = board.get_board(conn, force=True, max_age_minutes=10, now=NOW)
    assert len(calls) == 1 and len(got) == 9


def test_force_honours_the_floor_on_a_very_fresh_board(conn, monkeypatch):
    # Ruled 2026-08-29 (spec 5.3): concurrent sessions must reason over
    # the same board, so a force within the floor reuses, never refetches.
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:59:00Z")

    def boom():
        raise AssertionError("force within the floor must not refetch")
    monkeypatch.setattr(board.kalshi_markets, "list_open", boom)
    got = board.get_board(conn, force=True, now=NOW)
    assert [m.ticker for m in got] == ["T-0", "T-1", "T-2"]


def test_a_fetch_is_always_snapshotted(conn, monkeypatch):
    # The pull must never be lost -- that was the original complaint.
    monkeypatch.setattr(board.kalshi_markets, "list_open", lambda: _board(6))
    board.get_board(conn, now=NOW)
    assert board.board_info(conn, now=NOW)["markets"] == 6


def test_max_age_is_honoured(conn, monkeypatch):
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:00:00Z")
    monkeypatch.setattr(board.kalshi_markets, "list_open", lambda: _board(9))
    assert len(board.get_board(conn, max_age_minutes=30, now=NOW)) == 9
    assert len(board.get_board(conn, max_age_minutes=90, now=NOW)) == 9


def test_rebuilt_board_matches_the_fetched_one(conn):
    original = _board(3)
    snapshot.save_kalshi(conn, original, now="2026-08-24T11:00:00Z")
    rebuilt = board.get_board(conn, now=NOW)
    for a, b in zip(original, rebuilt):
        for field in ("ticker", "event_ticker", "series_ticker", "title",
                      "yes_bid", "yes_ask", "no_bid", "no_ask", "mid",
                      "spread", "volume", "open_interest", "status",
                      "is_open", "close_time", "rules_primary"):
            assert getattr(a, field) == getattr(b, field), field


def test_unrebuildable_snapshot_fails_loudly(conn):
    snapshot.save_kalshi(conn, _board(2), now="2026-08-24T11:00:00Z")
    with db.write(conn):
        conn.execute("UPDATE market_snapshots SET raw_json = '{}'")
    # A short board that looks complete would silently starve a screen.
    with pytest.raises(ValueError, match="cannot be rebuilt"):
        board.get_board(conn, now=NOW)


# --- raw payload is stored whole -------------------------------------


def test_snapshot_stores_the_complete_raw_payload(conn):
    snapshot.save_kalshi(conn, _board(1), now=NOW)
    stored = json.loads(conn.execute(
        "SELECT raw_json FROM market_snapshots").fetchone()["raw_json"])
    # Nothing is dropped -- including fields no current code reads. An
    # earlier projection cost us momentum and order-book depth precisely by
    # scoping storage to what the code read at the time.
    assert stored == _raw("T-0")
    assert "junk_a" in stored and "junk_b" in stored


def test_rebuilt_board_has_the_same_raw_as_a_fetched_one(conn):
    original = _board(2)
    snapshot.save_kalshi(conn, original, now="2026-08-24T11:00:00Z")
    rebuilt = board.get_board(conn, now=NOW)
    for a, b in zip(original, rebuilt):
        assert a.raw == b.raw


def test_uncommon_fields_survive_the_cache_round_trip(conn):
    # The fields the bad projection destroyed, specifically.
    from tools.kalshi import markets
    raw = _raw("T-9", previous_yes_bid_dollars="0.75",
               yes_bid_size_fp="1200", can_close_early=True,
               early_close_condition="if the event concludes early")
    snapshot.save_kalshi(conn, [markets.normalize(raw)],
                         now="2026-08-24T11:00:00Z")
    got = board.get_board(conn, now=NOW)[0]
    assert got.raw["previous_yes_bid_dollars"] == "0.75"
    assert got.raw["yes_bid_size_fp"] == "1200"
    assert got.raw["can_close_early"] is True
    assert got.raw["early_close_condition"] == "if the event concludes early"


# --- one row per market per capture ----------------------------------


def test_saving_twice_in_one_second_does_not_duplicate(conn):
    # captured_at has one-second resolution and is the batch key a whole
    # pull shares. Without the unique index these merged into one batch with
    # every market duplicated -- a board that rebuilds to twice its size and
    # still looks complete.
    snapshot.save_kalshi(conn, _board(3), now=NOW)
    snapshot.save_kalshi(conn, _board(3), now=NOW)
    assert board.board_info(conn, now=NOW)["markets"] == 3
    got = board.get_board(conn, now=NOW)
    assert len(got) == 3 == len({m.ticker for m in got})


def test_re_saving_updates_rather_than_duplicating(conn):
    from tools.kalshi import markets
    snapshot.save_kalshi(conn, _board(1), now=NOW)
    moved = markets.normalize(_raw("T-0", yes_ask_dollars="0.91",
                                   yes_bid_dollars="0.89"))
    snapshot.save_kalshi(conn, [moved], now=NOW)
    rows = conn.execute(
        "SELECT yes_ask, last_seen_at FROM market_snapshots"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["yes_ask"] == pytest.approx(0.91)   # last write wins
    assert rows[0]["last_seen_at"] == NOW


def test_unchanged_pull_extends_the_batch_rather_than_duplicating_it(conn):
    # Pre-dedup, two identical pulls a second apart wrote 6 rows in 2
    # batches. Now the second pull writes nothing and the stored board
    # is simply re-stamped (spec 5.2 phase 2).
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:00:00Z")
    snapshot.save_kalshi(conn, _board(3), now="2026-08-24T11:00:01Z")
    assert conn.execute(
        "SELECT COUNT(*) n FROM market_snapshots").fetchone()["n"] == 3
    info = board.board_info(conn, now=NOW)
    assert info["markets"] == 3
    assert info["captured_at"] == "2026-08-24T11:00:01Z"


def test_migration_dedupes_a_legacy_database(tmp_path):
    # A database written before the unique index, holding the duplicates it
    # allowed. CREATE UNIQUE INDEX would fail on these, so the migration must
    # remove them first or the database becomes permanently un-migratable.
    import sqlite3
    path = tmp_path / "legacy.db"
    c = db.connect(path)
    db.init_db(c)
    c.execute("DROP INDEX IF EXISTS idx_snapshots_unique")
    c.execute("CREATE INDEX idx_snapshots_market"
              " ON market_snapshots (platform, market_id, captured_at)")
    for _ in range(2):
        c.execute(
            "INSERT INTO market_snapshots (platform, market_id, captured_at,"
            " status, raw_json) VALUES ('kalshi','T-0',?, 'open','{}')", (NOW,))
    c.commit()
    assert c.execute("SELECT COUNT(*) n FROM market_snapshots").fetchone()["n"] == 2

    db.init_db(c)   # migration runs
    assert c.execute("SELECT COUNT(*) n FROM market_snapshots").fetchone()["n"] == 1
    idx = {r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_snapshots_unique" in idx
    assert "idx_snapshots_market" not in idx   # redundant, same columns
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO market_snapshots (platform, market_id,"
                  " captured_at, status) VALUES ('kalshi','T-0',?, 'open')",
                  (NOW,))
    c.close()


def test_cache_and_fetch_boards_are_identical_raw_included(conn, monkeypatch):
    """Spec section 8.1, the highest-severity risk: a cached board that
    returned a thinner `raw` would make a theory reading an uncommon field
    work on a forced pull and silently return None on a cached one."""
    fetched = _board(3)
    monkeypatch.setattr(board.kalshi_markets, "list_open", lambda: fetched)
    first = board.get_board(conn, force=True, now=NOW)     # fetch + snapshot
    rebuilt = board.get_board(conn, now=NOW)               # cache hit

    assert rebuilt == first
    for a, b in zip(first, rebuilt):
        assert a.raw == b.raw      # raw is compare=False, so check it here
        assert a.raw["junk_b"] == list(range(50))


def test_rebuilt_board_derives_identity_the_raw_payload_lacks(conn, monkeypatch):
    """Regression, 2026-08-26: the live API carries series/event identity on
    the EVENT envelope, not the market payload — `list_open` patches it onto
    each Market, but the snapshot stores only the market's own raw. A rebuilt
    board therefore had series_ticker=None on every market, which silently
    disabled every family classifier downstream (gate.py passed 349/349
    events on a cached board vs 100/349 on the same board freshly fetched).
    The rebuild must derive identity from the ticker when raw lacks it."""
    from dataclasses import replace
    from tools.kalshi import markets

    raw = _raw("KXWIDGET-26SEP01-STRIKE")
    del raw["series_ticker"], raw["event_ticker"]
    fetched = replace(
        markets.normalize(raw),
        series_ticker="KXWIDGET",              # list_open's envelope patch
        event_ticker="KXWIDGET-26SEP01",
    )
    monkeypatch.setattr(board.kalshi_markets, "list_open", lambda: [fetched])
    board.get_board(conn, force=True, now=NOW)          # fetch + snapshot
    rebuilt = board.get_board(conn, now=NOW)            # cache hit

    assert rebuilt[0].series_ticker == "KXWIDGET"
    assert rebuilt[0].event_ticker == "KXWIDGET-26SEP01"


# --- event envelope ---------------------------------------------------


def _enveloped(ticker="T-0", **event_kw):
    from tools.kalshi import markets
    envelope = {
        "event_ticker": "EV", "series_ticker": "KXTHING",
        "title": "an event", "category": "Politics",
        "mutually_exclusive": True, "strike_period": "",
    }
    envelope.update(event_kw)
    return markets.normalize(_raw(ticker), envelope)


def test_rebuilt_board_keeps_the_event_envelope(conn):
    # board.py guarantees a cached board and a fetched board are identical.
    # That held for the market payload and silently failed for the event
    # envelope, which list_open discarded before the snapshot ever saw it.
    snapshot.save_kalshi(conn, [_enveloped()], now="2026-08-24T11:59:00Z")
    rebuilt = board.get_board(conn, now=NOW)
    assert rebuilt[0].event["mutually_exclusive"] is True
    assert rebuilt[0].event["category"] == "Politics"


def test_rebuilt_board_reports_unknown_not_false_for_pre_envelope_captures(conn):
    # The sharp edge: absent is not False. Captures taken before the
    # envelope was kept must read as UNKNOWN, so a future replay can tell
    # "Kalshi said not exclusive" from "we weren't storing it yet".
    # Reading absent as False loses real violations; as True it manufactures
    # riskless-looking baskets that lose money.
    from tools.kalshi import markets
    legacy = markets.normalize(_raw("T-0"))          # no envelope, as before
    snapshot.save_kalshi(conn, [legacy], now="2026-08-24T11:59:00Z")
    rebuilt = board.get_board(conn, now=NOW)
    assert rebuilt[0].event == {}
    assert rebuilt[0].event.get("mutually_exclusive") is None


def test_rebuilt_board_keeps_a_false_flag_distinct_from_a_missing_one(conn):
    snapshot.save_kalshi(conn, [_enveloped(mutually_exclusive=False)],
                         now="2026-08-24T11:59:00Z")
    rebuilt = board.get_board(conn, now=NOW)
    assert rebuilt[0].event.get("mutually_exclusive") is False
