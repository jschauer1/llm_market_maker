import math
import sqlite3

import pytest

from tools import db, ledger, theories

TS = "2026-08-23T12:00:00Z"
LATER = "2026-08-24T12:00:00Z"
EVEN_LATER = "2026-08-25T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _record(conn, **overrides):
    kwargs = dict(
        theory_id="t1",
        theory_version=1,
        kalshi_ticker="KXTEST-26",
        outcome="yes",
        entry_price=0.40,
        edge_pts_net=6.0,
        rationale="looks mispriced",
        now=TS,
    )
    kwargs.update(overrides)
    return ledger.record_opportunity(conn, **kwargs)


def test_record_creates_a_row(conn):
    opp_id, created = _record(conn)
    assert created is True
    row = ledger.get_opportunity(conn, opp_id)
    assert row["kalshi_ticker"] == "KXTEST-26"
    assert row["entry_price"] == pytest.approx(0.40)
    assert row["times_seen"] == 1
    assert row["disposition"] == "screened"
    assert row["user_action"] == "untouched"
    assert row["run_id"] == "live"


def test_screen_edge_is_frozen_at_record_time(conn):
    opp_id, _ = _record(conn, edge_pts_net=6.0)
    row = ledger.get_opportunity(conn, opp_id)
    assert row["screen_edge_pts_net"] == pytest.approx(6.0)
    assert row["edge_pts_net"] == pytest.approx(6.0)


def test_resighting_updates_instead_of_duplicating(conn):
    first_id, first_created = _record(conn)
    second_id, second_created = _record(conn, now=LATER, edge_pts_net=7.5)

    assert second_created is False
    assert second_id == first_id
    assert len(ledger.list_opportunities(conn)) == 1


def test_resighting_preserves_the_original_entry(conn):
    opp_id, _ = _record(conn, entry_price=0.40)
    _record(conn, entry_price=0.55, now=LATER)

    row = ledger.get_opportunity(conn, opp_id)
    assert row["entry_price"] == pytest.approx(0.40), "entry must not drift"
    assert row["first_seen_at"] == TS
    assert row["last_seen_at"] == LATER
    assert row["times_seen"] == 2


def test_resighting_preserves_the_frozen_screen_edge(conn):
    opp_id, _ = _record(conn, edge_pts_net=6.0)
    _record(conn, edge_pts_net=9.0, now=LATER)

    row = ledger.get_opportunity(conn, opp_id)
    assert row["screen_edge_pts_net"] == pytest.approx(6.0)
    assert row["edge_pts_net"] == pytest.approx(9.0), "current edge refreshes"


def test_resighting_does_not_overwrite_an_interpreted_edge(conn):
    # Once interpret() has revised the edge, that is the current best
    # estimate. A later re-sighting from the mechanical screen must not
    # clobber it back down — that would silently discard stage-2 research
    # on the very next scan.
    opp_id, _ = _record(conn, edge_pts_net=6.0)
    ledger.interpret(conn, opp_id, "endorsed", "stronger than the screen "
                     "thought", revised_edge_pts_net=9.0, now=LATER)
    _record(conn, edge_pts_net=4.0, now=LATER)

    row = ledger.get_opportunity(conn, opp_id)
    assert row["edge_pts_net"] == pytest.approx(9.0)
    assert row["times_seen"] == 2
    assert row["last_seen_at"] == LATER


def test_resighting_an_uninterpreted_row_still_tracks_the_latest_screen(conn):
    # Without any interpretation, the row has no researched value to protect,
    # so a re-sighting should keep refreshing edge_pts_net from the screen.
    opp_id, _ = _record(conn, edge_pts_net=6.0)
    _record(conn, edge_pts_net=4.0, now=LATER)

    row = ledger.get_opportunity(conn, opp_id)
    assert row["edge_pts_net"] == pytest.approx(4.0)


def test_resighting_after_disposition_only_interpretation_freezes_edge(conn):
    # interpret() sets interpreted_at on every call, even one that only
    # records a disposition (no revised_edge_pts_net). That still counts as
    # "research has spoken" — the row is no longer purely mechanical — so a
    # later re-sighting must not resume overwriting edge_pts_net.
    opp_id, _ = _record(conn, edge_pts_net=6.0)
    ledger.interpret(conn, opp_id, "endorsed", "confirmed as screened",
                     now=LATER)
    _record(conn, edge_pts_net=4.0, now=LATER)

    row = ledger.get_opportunity(conn, opp_id)
    assert row["edge_pts_net"] == pytest.approx(6.0)


def test_different_outcome_is_a_different_opportunity(conn):
    _record(conn, outcome="yes")
    _record(conn, outcome="no")
    assert len(ledger.list_opportunities(conn)) == 2


def test_different_theory_version_is_a_different_opportunity(conn):
    _record(conn, theory_version=1)
    _record(conn, theory_version=2)
    assert len(ledger.list_opportunities(conn)) == 2


def test_backtest_runs_dedupe_to_one_position(conn):
    # Two backtest runs that both propose the same market are one position,
    # not two -- the old contract (run_id in the UNIQUE key) is exactly the
    # double-counting defect this position-identity work removes. What
    # distinguishes the runs now lives in the attempt list, not in a second
    # opportunities row: re-recording under "run-a" a second time is the
    # same decision seen again and updates its attempt in place, while
    # "run-b" is a genuinely different run and adds a second attempt.
    id_a, created_a = _record(conn, run_mode="backtest", run_id="run-a")
    id_again, created_again = _record(conn, run_mode="backtest", run_id="run-a")
    id_b, created_b = _record(conn, run_mode="backtest", run_id="run-b")

    assert id_a == id_again == id_b
    assert created_a is True
    assert created_again is False and created_b is False
    assert len(ledger.list_opportunities(conn, run_mode="backtest")) == 1
    assert len(ledger.attempts(conn, id_a)) == 2, (
        "one attempt per run that proposed it, not one per recording"
    )


def test_missing_kalshi_ticker_is_rejected(conn):
    with pytest.raises(ValueError, match="kalshi_ticker"):
        _record(conn, kalshi_ticker="")
    with pytest.raises(ValueError, match="kalshi_ticker"):
        _record(conn, kalshi_ticker=None)


def test_missing_edge_is_rejected(conn):
    with pytest.raises(ValueError, match="edge_pts_net"):
        _record(conn, edge_pts_net=None)


def test_backtest_without_run_id_is_rejected(conn):
    with pytest.raises(ValueError, match="run_id"):
        _record(conn, run_mode="backtest", run_id=None)


def test_backtest_cannot_claim_the_live_run_id(conn):
    # run_mode is not part of the dedup key, so a backtest writing under the
    # 'live' run_id would overwrite the live row's edge and leave run_mode
    # 'live' — backtest output scored as a live bet, with no trace.
    with pytest.raises(ValueError, match="reserved sentinel"):
        _record(conn, run_mode="backtest", run_id=ledger.LIVE_RUN_ID)


def test_outcome_case_does_not_create_a_second_row(conn):
    # The dedup key uses SQLite's binary collation but the win predicate
    # compares case-insensitively: three casings would be three rows and
    # three counted wins for one real bet. Each call lands on its own day so
    # each is counted as a distinct attempt -- times_seen now counts distinct
    # (decision_date, run_id) attempts, not raw recordings, so two calls on
    # the same day under the same run_id would otherwise collapse to one.
    _record(conn, outcome="yes")
    _record(conn, outcome="YES", now=LATER)
    _record(conn, outcome=" Yes ", now=EVEN_LATER)

    rows = ledger.list_opportunities(conn)
    assert len(rows) == 1
    assert rows[0]["times_seen"] == 3
    assert rows[0]["outcome"] == "yes"


def test_ticker_case_does_not_create_a_second_row(conn):
    _record(conn, kalshi_ticker="kxtest-26")
    _record(conn, kalshi_ticker="KXTEST-26", now=LATER)

    rows = ledger.list_opportunities(conn)
    assert len(rows) == 1
    assert rows[0]["times_seen"] == 2
    assert rows[0]["kalshi_ticker"] == "KXTEST-26"


@pytest.mark.parametrize("bad_price", [40, -1.5, 1.7, "0.40"])
def test_entry_price_must_be_decimal_dollars(conn, bad_price):
    # 40 is the exact mistake the constraint exists to catch: cents passed
    # where dollars were meant, which scores as -3900 points of edge.
    with pytest.raises(ValueError, match="entry_price"):
        _record(conn, entry_price=bad_price)


def test_entry_price_nan_is_rejected(conn):
    # NaN compares False to every `>`/`<` check, so the range checks alone
    # let it through. Without an explicit isnan() check it is only rejected
    # by accident: sqlite3 binds a NaN float as SQL NULL, which trips the
    # entry_price NOT NULL constraint and raises IntegrityError instead of
    # this purpose-built ValueError.
    with pytest.raises(ValueError, match="entry_price"):
        _record(conn, entry_price=math.nan)


def test_entry_price_bounds_are_inclusive(conn):
    _record(conn, kalshi_ticker="LOW", entry_price=0.0)
    _record(conn, kalshi_ticker="HIGH", entry_price=1.0)
    assert len(ledger.list_opportunities(conn)) == 2


def test_failed_insert_leaves_no_open_transaction(conn):
    # Without a rollback the connection sits in an open transaction and the
    # next writer blocks for the whole busy timeout, then fails locked.
    with pytest.raises(sqlite3.IntegrityError):
        _record(conn, theory_id="no_such_theory")
    assert conn.in_transaction is False
    # The connection must still be usable for a legitimate write.
    _record(conn)
    assert len(ledger.list_opportunities(conn)) == 1


def test_polymarket_evidence_is_recorded_against_a_kalshi_ticker(conn):
    opp_id, _ = _record(
        conn,
        evidence_source="polymarket",
        evidence_market_id="0xabc123",
    )
    row = ledger.get_opportunity(conn, opp_id)
    assert row["kalshi_ticker"] == "KXTEST-26"
    assert row["evidence_source"] == "polymarket"
    assert row["evidence_market_id"] == "0xabc123"


def test_list_filters_by_theory_and_disposition(conn):
    _record(conn, kalshi_ticker="A")
    _record(conn, kalshi_ticker="B")
    assert len(ledger.list_opportunities(conn, theory_id="t1")) == 2
    assert len(ledger.list_opportunities(conn, theory_id="other")) == 0
    assert len(ledger.list_opportunities(conn, disposition="screened")) == 2
    assert len(ledger.list_opportunities(conn, disposition="endorsed")) == 0


def test_unsettled_only_excludes_settled_tickers(conn):
    from tools import score

    _record(conn, kalshi_ticker="SETTLED")
    _record(conn, kalshi_ticker="OPEN")
    score.record_settlement(conn, "SETTLED", "yes")

    rows = ledger.list_opportunities(conn, unsettled_only=True)
    assert [r["kalshi_ticker"] for r in rows] == ["OPEN"]


def test_unsettled_only_defaults_to_false(conn):
    from tools import score

    _record(conn, kalshi_ticker="SETTLED")
    score.record_settlement(conn, "SETTLED", "yes")

    assert len(ledger.list_opportunities(conn)) == 1


def test_edge_basis_defaults_to_prior(conn):
    opp_id, _ = _record(conn)
    assert ledger.get_opportunity(conn, opp_id)["edge_basis"] == "prior"


def test_edge_basis_records_where_the_number_came_from(conn):
    opp_id, _ = _record(conn, edge_basis="measured")
    assert ledger.get_opportunity(conn, opp_id)["edge_basis"] == "measured"


def test_invalid_edge_basis_is_rejected(conn):
    # There is deliberately no basis meaning "an LLM felt it was about 87%".
    with pytest.raises(ValueError, match="edge_basis"):
        _record(conn, edge_basis="vibes")


def test_confidence_bucket_is_stored_for_later_measurement(conn):
    opp_id, _ = _record(conn, confidence="strong")
    assert ledger.get_opportunity(conn, opp_id)["confidence"] == "strong"


def test_judged_blind_is_recorded(conn):
    blind, _ = _record(conn, kalshi_ticker="A", judged_blind=True)
    seeing, _ = _record(conn, kalshi_ticker="B", judged_blind=False)
    unknown, _ = _record(conn, kalshi_ticker="C")

    assert ledger.get_opportunity(conn, blind)["judged_blind"] == 1
    assert ledger.get_opportunity(conn, seeing)["judged_blind"] == 0
    assert ledger.get_opportunity(conn, unknown)["judged_blind"] is None


def test_interpret_endorses_an_opportunity(conn):
    opp_id, _ = _record(conn)
    ledger.interpret(
        conn, opp_id, "endorsed",
        "Reality TV market; resolution language is unusually loose.",
        now=LATER,
    )
    row = ledger.get_opportunity(conn, opp_id)
    assert row["disposition"] == "endorsed"
    assert "Reality TV" in row["interpretation"]
    assert row["interpreted_at"] == LATER


def test_interpret_rejects_and_keeps_the_row_as_a_control(conn):
    opp_id, _ = _record(conn)
    ledger.interpret(conn, opp_id, "rejected", "Resolution requires an "
                     "official source that rarely publishes in time.")
    row = ledger.get_opportunity(conn, opp_id)
    assert row["disposition"] == "rejected"
    # The row must survive: rejected candidates are the control group.
    assert len(ledger.list_opportunities(conn)) == 1


def test_interpret_can_revise_the_edge_without_touching_the_screen_edge(conn):
    opp_id, _ = _record(conn, edge_pts_net=6.0)
    ledger.interpret(conn, opp_id, "endorsed", "Stronger than the screen "
                     "thought.", revised_edge_pts_net=9.0)
    row = ledger.get_opportunity(conn, opp_id)
    assert row["edge_pts_net"] == pytest.approx(9.0)
    assert row["screen_edge_pts_net"] == pytest.approx(6.0)


def test_interpret_without_revision_leaves_edge_alone(conn):
    opp_id, _ = _record(conn, edge_pts_net=6.0)
    ledger.interpret(conn, opp_id, "endorsed", "Confirmed as screened.")
    row = ledger.get_opportunity(conn, opp_id)
    assert row["edge_pts_net"] == pytest.approx(6.0)


def test_interpret_rejects_invalid_disposition(conn):
    opp_id, _ = _record(conn)
    with pytest.raises(ValueError):
        ledger.interpret(conn, opp_id, "maybe", "hmm")


def test_interpret_rejects_unknown_opportunity(conn):
    with pytest.raises(KeyError):
        ledger.interpret(conn, 9999, "endorsed", "nope")


def test_mark_user_action_records_a_taken_bet(conn):
    opp_id, _ = _record(conn)
    ledger.mark_user_action(conn, opp_id, "taken", size=25.0,
                            reason="reality TV markets are soft",
                            theory_id="t1")
    row = ledger.get_opportunity(conn, opp_id)
    assert row["user_action"] == "taken"
    assert row["user_size"] == pytest.approx(25.0)
    assert row["user_reason"] == "reality TV markets are soft"


def test_mark_user_action_records_a_skip_with_reason(conn):
    opp_id, _ = _record(conn)
    ledger.mark_user_action(conn, opp_id, "skipped", reason="too illiquid")
    row = ledger.get_opportunity(conn, opp_id)
    assert row["user_action"] == "skipped"
    assert row["user_reason"] == "too illiquid"


def test_mark_user_action_rejects_invalid_action(conn):
    opp_id, _ = _record(conn)
    with pytest.raises(ValueError):
        ledger.mark_user_action(conn, opp_id, "pondered")
