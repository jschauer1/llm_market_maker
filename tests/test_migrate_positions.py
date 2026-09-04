"""Collapsing the legacy ledger without losing a judgment, a leg or a fill.

The shape reproduced here is the one in the real database: a full-coverage
run that recorded no confidence, and a later judged run that recorded a
confidence bucket for a subset of the same markets. The plan's original
"earliest row survives" rule would have kept the NULL and deleted every
label; this pins the opposite.

The attempt-fidelity spec (section 8) amends the migration five ways, and
each amendment has a test here: `opportunity_fills` is created (a), every
attempt column is backfilled from the row it came from (b), `judged_blind`
travels with the `confidence` it belongs to (c), and `user_action` /
`user_size` are recomputed from the fills rather than copied off the
earliest row (d). (e) belongs to the task that runs the migration.
"""

import pytest

from tools import db, ledger

TS = "2026-08-25T12:00:00Z"
TS2 = "2026-08-26T12:00:00Z"

OLD_SCHEMA = """
CREATE TABLE opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theory_id TEXT NOT NULL, theory_version INTEGER NOT NULL,
    run_mode TEXT NOT NULL, run_id TEXT NOT NULL, scan_id TEXT,
    kalshi_ticker TEXT NOT NULL, outcome TEXT NOT NULL,
    entry_price REAL NOT NULL,
    position_kind TEXT NOT NULL DEFAULT 'single',
    leg_count INTEGER NOT NULL DEFAULT 1,
    max_payout REAL NOT NULL DEFAULT 1.0,
    min_payout REAL NOT NULL DEFAULT 0.0,
    spread_at_call REAL, volume_at_call REAL, model_prob REAL,
    edge_pts_gross REAL, fee_pts REAL,
    screen_edge_pts_net REAL NOT NULL, edge_pts_net REAL NOT NULL,
    edge_basis TEXT NOT NULL DEFAULT 'prior',
    disposition TEXT NOT NULL DEFAULT 'screened',
    interpretation TEXT, interpreted_at TEXT, confidence TEXT,
    judged_blind INTEGER, rationale TEXT, suggested_size REAL,
    evidence_source TEXT, evidence_market_id TEXT,
    user_action TEXT NOT NULL DEFAULT 'untouched',
    user_size REAL, user_reason TEXT,
    first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
    times_seen INTEGER NOT NULL DEFAULT 1, extra_json TEXT,
    UNIQUE (theory_id, theory_version, run_id, kalshi_ticker, outcome)
);
CREATE INDEX idx_opportunities_theory
    ON opportunities (theory_id, theory_version, run_mode, disposition);
CREATE INDEX idx_opportunities_ticker ON opportunities (kalshi_ticker);
"""


def _legacy_row(conn, **kw):
    cols = {
        "theory_id": "t1", "theory_version": 3, "run_mode": "backtest",
        "scan_id": None, "outcome": "yes", "entry_price": 0.90,
        "screen_edge_pts_net": 2.0, "edge_pts_net": 2.0,
        "confidence": None, "first_seen_at": TS, "last_seen_at": TS,
        "extra_json": '{"entry_day_iso": "2026-08-20"}',
    }
    cols.update(kw)
    keys = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    conn.execute(
        f"INSERT INTO opportunities ({keys}) VALUES ({marks})",
        list(cols.values()),
    )
    conn.commit()


@pytest.fixture(scope="session")
def _legacy_template(tmp_path_factory):
    """The pre-migration database, built ONCE and copied per test.

    Built to a file rather than memory because `test_the_cli_reports_the_
    collapse` reopens `tmp_path / "legacy.db"` by path, so the per-test
    copy has to be a real file at that exact location.
    """
    path = tmp_path_factory.mktemp("legacy_template") / "legacy.db"
    c = db.connect(path)
    c.executescript(OLD_SCHEMA)
    c.execute(
        "CREATE TABLE opportunity_legs (opportunity_id INTEGER NOT NULL"
        " REFERENCES opportunities(id) ON DELETE CASCADE,"
        " leg_index INTEGER NOT NULL, kalshi_ticker TEXT NOT NULL,"
        " outcome TEXT NOT NULL, entry_price REAL NOT NULL,"
        " spread_at_call REAL, volume_at_call REAL,"
        " PRIMARY KEY (opportunity_id, leg_index))"
    )
    c.commit()
    db.close(c)          # checkpoints the WAL so the .db alone is complete
    return path


@pytest.fixture
def legacy(tmp_path, _legacy_template):
    """A database in the pre-migration shape -- a fresh copy per test."""
    import shutil
    dest = tmp_path / "legacy.db"
    shutil.copyfile(_legacy_template, dest)
    snap = db.snapshots_path_for(_legacy_template)
    if snap.exists():
        shutil.copyfile(snap, db.snapshots_path_for(dest))
    c = db.connect(dest)
    yield c
    c.close()


def _tables(conn):
    return {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def _rows(conn, table):
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]


def test_a_screened_and_a_judged_row_become_one_labelled_position(legacy):
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA",
                confidence=None)
    _legacy_row(legacy, run_id="judged-s200", kalshi_ticker="KXA",
                confidence="strong", last_seen_at=TS2)
    stats = db.migrate_positions(legacy)

    assert stats["before"] == 2 and stats["after"] == 1
    assert stats["labels_preserved"] == 1
    row = legacy.execute("SELECT * FROM opportunities").fetchone()
    assert row["confidence"] == "strong", "the judgment must survive"
    assert row["entry_price"] == 0.90
    assert row["times_seen"] == 2


def test_both_runs_survive_as_attempts(legacy):
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="judged-s200", kalshi_ticker="KXA",
                confidence="strong")
    db.migrate_positions(legacy)
    opp = legacy.execute("SELECT id FROM opportunities").fetchone()["id"]
    runs = [a["run_id"] for a in ledger.attempts(legacy, opp)]
    assert sorted(runs) == ["fullcov", "judged-s200"]


def test_experiments_do_not_merge_into_the_record(legacy):
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="exp/gated100", kalshi_ticker="KXA")
    db.migrate_positions(legacy)
    lanes = sorted(
        r["lane"] for r in legacy.execute("SELECT lane FROM opportunities")
    )
    assert lanes == ["exp/gated100", "main"]


def test_a_merged_basket_keeps_its_legs(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="BASKET:abc",
                outcome="basket", position_kind="basket", leg_count=2)
    _legacy_row(legacy, run_id="r2", kalshi_ticker="BASKET:abc",
                outcome="basket", position_kind="basket", leg_count=2)
    ids = [r["id"] for r in legacy.execute("SELECT id FROM opportunities")]
    for opp in ids:
        legacy.execute(
            "INSERT INTO opportunity_legs VALUES (?, 0, 'KXL1', 'yes',"
            " 0.4, NULL, NULL)", (opp,)
        )
    legacy.commit()

    db.migrate_positions(legacy)

    survivor = legacy.execute("SELECT id FROM opportunities").fetchone()["id"]
    legs = legacy.execute(
        "SELECT * FROM opportunity_legs WHERE opportunity_id = ?", (survivor,)
    ).fetchall()
    assert len(legs) == 1
    orphans = legacy.execute(
        "SELECT COUNT(*) FROM opportunity_legs WHERE opportunity_id"
        " NOT IN (SELECT id FROM opportunities)"
    ).fetchone()[0]
    assert orphans == 0


def test_legs_recorded_only_by_the_losing_row_are_repointed(legacy):
    """The case ON DELETE CASCADE would silently eat.

    The second run recorded the legs; the first is the row that survives.
    Dropping the loser without moving its legs first takes the whole
    basket's composition with it.
    """
    _legacy_row(legacy, run_id="r1", kalshi_ticker="BASKET:abc",
                outcome="basket", position_kind="basket", leg_count=2)
    _legacy_row(legacy, run_id="r2", kalshi_ticker="BASKET:abc",
                outcome="basket", position_kind="basket", leg_count=2,
                last_seen_at=TS2)
    loser = legacy.execute(
        "SELECT id FROM opportunities WHERE run_id = 'r2'"
    ).fetchone()["id"]
    for index, tick in enumerate(("KXL1", "KXL2")):
        legacy.execute(
            "INSERT INTO opportunity_legs VALUES (?, ?, ?, 'yes', 0.4,"
            " NULL, NULL)", (loser, index, tick)
        )
    legacy.commit()

    stats = db.migrate_positions(legacy)

    assert stats["legs_repointed"] == 2
    survivor = legacy.execute("SELECT id FROM opportunities").fetchone()["id"]
    legs = sorted(
        r["kalshi_ticker"] for r in legacy.execute(
            "SELECT kalshi_ticker FROM opportunity_legs"
            " WHERE opportunity_id = ?", (survivor,)
        )
    )
    assert legs == ["KXL1", "KXL2"]


def test_two_theories_on_one_ticker_stay_two_positions(legacy):
    _legacy_row(legacy, theory_id="t1", run_id="r1", kalshi_ticker="KXA")
    _legacy_row(legacy, theory_id="t2", run_id="r1", kalshi_ticker="KXA")
    db.migrate_positions(legacy)
    assert legacy.execute(
        "SELECT COUNT(*) FROM opportunities"
    ).fetchone()[0] == 2


def test_a_backup_table_is_written(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA")
    stats = db.migrate_positions(legacy)
    kept = legacy.execute(
        f"SELECT COUNT(*) FROM {stats['backup_table']}"
    ).fetchone()[0]
    assert kept == 1


def test_dry_run_changes_nothing(legacy):
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="judged", kalshi_ticker="KXA",
                confidence="strong")
    before = _tables(legacy)
    stats = db.migrate_positions(legacy, dry_run=True)
    assert stats["before"] == 2 and stats["after"] == 1
    assert stats["backup_table"] is None
    assert legacy.execute(
        "SELECT COUNT(*) FROM opportunities"
    ).fetchone()[0] == 2, "dry run must not write"
    assert _tables(legacy) == before, "a dry run creates no tables"
    assert db.has_legacy_position_key(legacy)


def test_migrating_twice_is_a_no_op(legacy):
    """A re-run must not rebuild -- rebuilding destroys the history.

    A naive second pass re-derives attempts from the *collapsed* rows, so
    a merged position's two attempts become one and the attempt that
    recorded no confidence inherits the rollup's label. Before/after counts
    cannot see that, so this pins the attempt rows themselves.
    """
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="judged-s200", kalshi_ticker="KXA",
                confidence="strong", judged_blind=1, last_seen_at=TS2)
    first = db.migrate_positions(legacy)
    opps_before = _rows(legacy, "opportunities")
    attempts_before = _rows(legacy, "opportunity_attempts")
    tables_before = _tables(legacy)

    again = db.migrate_positions(legacy)

    assert again["before"] == again["after"] == 1
    assert again["backup_table"] is None, "a no-op writes no second backup"
    assert again["attempts"] == first["attempts"] == 2
    assert _rows(legacy, "opportunity_attempts") == attempts_before, (
        "a re-run must not re-derive the attempt history"
    )
    assert _rows(legacy, "opportunities") == opps_before
    assert _tables(legacy) == tables_before


def test_money_already_recorded_becomes_a_fill(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA",
                user_action="taken", user_size=25.0,
                user_reason="thin but mispriced", last_seen_at=TS2)
    stats = db.migrate_positions(legacy)
    assert stats["fills_backfilled"] == 1
    opp = legacy.execute("SELECT * FROM opportunities").fetchone()
    assert opp["user_action"] == "taken" and opp["user_size"] == 25.0
    fill = ledger.fills(legacy, opp["id"])[0]
    assert fill["size"] == 25.0
    assert fill["filled_on"] == "2026-08-26"
    assert fill["price"] is None, "the legacy schema recorded no fill price"


# --- section 8 (a): the fills table has to be created -------------------


def test_the_fills_table_is_created_even_with_no_money_to_move(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA")
    db.migrate_positions(legacy)
    assert "opportunity_fills" in _tables(legacy)
    assert legacy.execute(
        "SELECT COUNT(*) FROM opportunity_fills"
    ).fetchone()[0] == 0


# --- section 8 (b): every attempt column is backfilled ------------------


FULL_ROW = {
    "scan_id": "scan-9",
    "spread_at_call": 0.03,
    "volume_at_call": 1200.0,
    "model_prob": 0.95,
    "edge_pts_gross": 5.0,
    "fee_pts": 1.0,
    "edge_pts_net": 4.0,
    "edge_basis": "model",
    "disposition": "endorsed",
    "confidence": "strong",
    "judged_blind": 1,
    "rationale": "the network already taped it",
    "suggested_size": 40.0,
    "evidence_source": "polymarket",
    "evidence_market_id": "0xabc",
    "extra_json": '{"entry_day_iso": "2026-08-20", "researched": true}',
}


def test_every_attempt_column_is_backfilled_from_its_own_row(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA", **FULL_ROW)
    db.migrate_positions(legacy)
    opp = legacy.execute("SELECT id FROM opportunities").fetchone()["id"]
    attempt = ledger.attempts(legacy, opp)[0]
    for column, expected in FULL_ROW.items():
        assert attempt[column] == expected, column
    assert attempt["decision_date"] == "2026-08-20"
    assert attempt["run_id"] == "r1"
    assert attempt["recorded_at"] == TS
    assert attempt["entry_price"] == 0.90


def test_each_attempt_keeps_its_own_rationale_and_features(legacy):
    """The 1,702 differing rationales and 1,680 differing extra_json blobs.

    Rolling both rows up onto the earliest would leave the later run's
    reasoning and its feature flags nowhere but a backup table nothing
    queries.
    """
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA",
                rationale=None,
                extra_json='{"entry_day_iso": "2026-08-20"}')
    _legacy_row(legacy, run_id="judged", kalshi_ticker="KXA",
                confidence="moderate", rationale="pre-taped",
                last_seen_at=TS2,
                extra_json='{"entry_day_iso": "2026-08-20",'
                           ' "rules_diverge_from_title": true}')
    db.migrate_positions(legacy)
    opp = legacy.execute("SELECT id FROM opportunities").fetchone()["id"]
    by_run = {a["run_id"]: a for a in ledger.attempts(legacy, opp)}
    assert by_run["fullcov"]["rationale"] is None
    assert by_run["fullcov"]["confidence"] is None
    assert by_run["judged"]["rationale"] == "pre-taped"
    assert "rules_diverge_from_title" in by_run["judged"]["extra_json"]
    assert "rules_diverge_from_title" not in by_run["fullcov"]["extra_json"]


def test_a_per_row_disposition_is_not_flattened(legacy):
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="researched", kalshi_ticker="KXA",
                disposition="rejected", last_seen_at=TS2)
    db.migrate_positions(legacy)
    opp = legacy.execute("SELECT id FROM opportunities").fetchone()["id"]
    by_run = {a["run_id"]: a for a in ledger.attempts(legacy, opp)}
    assert by_run["fullcov"]["disposition"] == "screened"
    assert by_run["researched"]["disposition"] == "rejected"


# --- section 8 (c): judged_blind travels with confidence ----------------


def test_judged_blind_comes_from_the_row_the_label_came_from(legacy):
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA",
                confidence=None, judged_blind=None)
    _legacy_row(legacy, run_id="judged", kalshi_ticker="KXA",
                confidence="strong", judged_blind=1, last_seen_at=TS2)
    db.migrate_positions(legacy)
    row = legacy.execute("SELECT * FROM opportunities").fetchone()
    assert row["confidence"] == "strong"
    assert row["judged_blind"] == 1, (
        "a labelled position with a NULL blind flag misreports how it was "
        "judged"
    )


# --- section 8 (d): the money rollup is recomputed, never copied --------


def test_a_later_take_is_not_left_as_an_untouched_position(legacy):
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="judged", kalshi_ticker="KXA",
                last_seen_at=TS2, user_action="taken", user_size=12.0,
                user_reason="worth it")
    stats = db.migrate_positions(legacy)
    assert stats["fills_backfilled"] == 1
    row = legacy.execute("SELECT * FROM opportunities").fetchone()
    assert row["user_action"] == "taken"
    assert row["user_size"] == 12.0
    assert row["user_reason"] == "worth it"
    assert len(ledger.fills(legacy, row["id"])) == 1


def test_a_position_with_no_fill_reports_no_size(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA",
                user_action="skipped", user_size=9.0, user_reason="too thin")
    db.migrate_positions(legacy)
    row = legacy.execute("SELECT * FROM opportunities").fetchone()
    assert row["user_action"] == "skipped"
    assert row["user_size"] is None, "user_size is a rollup of the fills"
    assert ledger.fills(legacy, row["id"]) == []


# --- research that has no attempt column must not be dropped ------------


def test_a_later_interpreted_row_keeps_its_research(legacy):
    """`interpretation` and `interpreted_at` are position-only (section 7).

    Nothing else holds them, so taking the earliest row's values would lose
    a stage-2 verdict outright rather than merely un-cache it. The rule is
    earliest-*interpreted*, so a group first judged by a later pass -- this
    one -- still keeps its verdict.
    """
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="researched", kalshi_ticker="KXA",
                last_seen_at=TS2, disposition="rejected",
                interpretation="the source can miss the close",
                interpreted_at=TS2, edge_pts_net=-3.0)
    db.migrate_positions(legacy)
    row = legacy.execute("SELECT * FROM opportunities").fetchone()
    assert row["disposition"] == "rejected"
    assert row["interpretation"] == "the source can miss the close"
    assert row["interpreted_at"] == TS2
    assert row["screen_edge_pts_net"] == 2.0, "the screen claim is an anchor"


def test_the_research_override_never_reaches_the_edge(legacy):
    """Price and edge move together, with no exception (section 4.4).

    `ledger.interpret` writes `edge_pts_net` alongside the verdict, so a
    verdict taken off another attempt used to drag that attempt's edge onto
    the earliest attempt's price -- the mismatched pair section 4.4 forbids,
    and the thing that keeps `_single_leg_observations` correct with no
    change to its SELECT.
    """
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA",
                entry_price=0.73, edge_pts_net=4.52)
    _legacy_row(legacy, run_id="researched", kalshi_ticker="KXA",
                last_seen_at=TS2, entry_price=0.77, edge_pts_net=-3.0,
                disposition="rejected", interpretation="worse ask now",
                interpreted_at=TS2)
    db.migrate_positions(legacy)
    row = legacy.execute("SELECT * FROM opportunities").fetchone()
    assert (row["entry_price"], row["edge_pts_net"]) == (0.73, 4.52)


def test_a_re_proposal_does_not_flip_the_verdict_the_money_was_taken_on(
    legacy,
):
    """The two positions in the live ledger that hold money have this shape.

    Endorsed on the 26th at 0.73, then declined on the 28th at 0.77 -- a
    judgement of a *different, worse price*, not a revision of the one the
    user is holding. Latest-wins turned both into `rejected`, which
    corrupts the endorsed/rejected control group at exactly the rows
    carrying money.
    """
    _legacy_row(legacy, run_id="live-26", kalshi_ticker="KXGROK",
                entry_price=0.73, edge_pts_net=4.52, disposition="endorsed",
                interpretation="nobody outside the lab knows yet",
                interpreted_at=TS, user_action="taken", user_size=25.0)
    _legacy_row(legacy, run_id="live-28", kalshi_ticker="KXGROK",
                last_seen_at=TS2, entry_price=0.77, edge_pts_net=2.0,
                disposition="rejected", interpretation="too rich now",
                interpreted_at=TS2)
    db.migrate_positions(legacy)
    row = legacy.execute("SELECT * FROM opportunities").fetchone()
    assert row["disposition"] == "endorsed"
    assert (row["entry_price"], row["edge_pts_net"]) == (0.73, 4.52)
    assert row["user_action"] == "taken"
    assert [a["disposition"] for a in ledger.attempts(legacy, row["id"])] == [
        "endorsed", "rejected"
    ], "the later decline is not lost -- it is its own attempt"


# --- the rebuilt table --------------------------------------------------


def test_a_superseded_interpretation_is_named_not_counted(legacy):
    """Keeping the earliest verdict is a call about somebody's research.

    A count cannot be checked. The names can: a reader sees which position
    lost which verdict while the migration is still a dry run and the
    decision is still reversible.
    """
    _legacy_row(legacy, run_id="first", kalshi_ticker="KXA",
                disposition="endorsed", interpretation="pre-taped",
                interpreted_at=TS, user_action="taken", user_size=25.0)
    _legacy_row(legacy, run_id="second", kalshi_ticker="KXA",
                last_seen_at=TS2, disposition="rejected",
                interpretation="the source can miss the close",
                interpreted_at=TS2)
    # A group with one interpretation is not superseding anything.
    _legacy_row(legacy, run_id="first", kalshi_ticker="KXB",
                disposition="endorsed", interpretation="pre-taped",
                interpreted_at=TS)
    _legacy_row(legacy, run_id="second", kalshi_ticker="KXB",
                last_seen_at=TS2)

    dry = db.migrate_positions(legacy, dry_run=True)
    assert dry["superseded_interpretation_count"] == 1
    assert dry["superseded_interpretations"] == [{
        "theory_id": "t1",
        "kalshi_ticker": "KXA",
        "outcome": "yes",
        "disposition_kept": "endorsed",
        "disposition_dropped": "rejected",
        "has_fill": True,
    }]
    stats = db.migrate_positions(legacy)
    assert stats["superseded_interpretations"] == dry[
        "superseded_interpretations"
    ]
    kept = legacy.execute(
        "SELECT interpretation FROM opportunities WHERE kalshi_ticker = 'KXA'"
    ).fetchone()["interpretation"]
    assert kept == "pre-taped"
    superseded = legacy.execute(
        f"SELECT COUNT(*) FROM {stats['backup_table']}"
        " WHERE interpretation = 'the source can miss the close'"
    ).fetchone()[0]
    assert superseded == 1, "the superseded verdict is still in the backup"


def test_the_named_list_is_capped_but_the_count_is_not(legacy):
    """A dry run has to stay readable; the total has to stay honest."""
    for i in range(db._SUPERSEDED_CAP + 3):
        _legacy_row(legacy, run_id="first", kalshi_ticker=f"KX{i}",
                    disposition="endorsed", interpretation="pre-taped",
                    interpreted_at=TS)
        _legacy_row(legacy, run_id="second", kalshi_ticker=f"KX{i}",
                    last_seen_at=TS2, disposition="rejected",
                    interpretation="declined", interpreted_at=TS2)
    dry = db.migrate_positions(legacy, dry_run=True)
    assert dry["superseded_interpretation_count"] == db._SUPERSEDED_CAP + 3
    assert len(dry["superseded_interpretations"]) == db._SUPERSEDED_CAP


def test_a_position_holding_money_is_named_before_the_cap_bites(legacy):
    """The cap must never be the reason a money position goes unreported."""
    for i in range(db._SUPERSEDED_CAP + 3):
        _legacy_row(legacy, run_id="first", kalshi_ticker=f"KX{i}",
                    disposition="endorsed", interpretation="pre-taped",
                    interpreted_at=TS)
        _legacy_row(legacy, run_id="second", kalshi_ticker=f"KX{i}",
                    last_seen_at=TS2, disposition="rejected",
                    interpretation="declined", interpreted_at=TS2)
    # Recorded last, so insertion order alone would push it past the cap.
    _legacy_row(legacy, run_id="first", kalshi_ticker="KXMONEY",
                disposition="endorsed", interpretation="pre-taped",
                interpreted_at=TS, user_action="taken", user_size=25.0)
    _legacy_row(legacy, run_id="second", kalshi_ticker="KXMONEY",
                last_seen_at=TS2, disposition="rejected",
                interpretation="declined", interpreted_at=TS2)

    dry = db.migrate_positions(legacy, dry_run=True)
    assert dry["superseded_interpretations"][0]["kalshi_ticker"] == "KXMONEY"
    assert dry["superseded_interpretations"][0]["has_fill"] is True


def test_a_take_with_no_size_is_refused_before_anything_is_written(legacy):
    """opportunity_fills.size is NOT NULL.

    Left alone this raises IntegrityError partway through the rebuild of a
    database that only gets migrated once. The dry run reports it, and the
    real run refuses while the ledger is still untouched.
    """
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="r2", kalshi_ticker="KXB",
                user_action="taken", user_size=None, user_reason="oops")
    tables = _tables(legacy)

    dry = db.migrate_positions(legacy, dry_run=True)
    assert dry["takes_missing_size"] == 1

    with pytest.raises(ValueError, match="no user_size"):
        db.migrate_positions(legacy)

    assert legacy.execute(
        "SELECT COUNT(*) FROM opportunities"
    ).fetchone()[0] == 2
    assert _tables(legacy) == tables, "refused before the backup is written"
    assert db.has_legacy_position_key(legacy)


def test_a_take_with_a_size_reports_nothing_missing(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA",
                user_action="taken", user_size=25.0)
    assert db.migrate_positions(
        legacy, dry_run=True
    )["takes_missing_size"] == 0
    assert db.migrate_positions(legacy)["fills_backfilled"] == 1


def test_the_rebuilt_table_keeps_its_indexes(legacy):
    """DROP TABLE takes the renamed table's indexes with it."""
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA")
    db.migrate_positions(legacy)
    indexes = {
        r[0] for r in legacy.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
    }
    assert {"idx_opportunities_theory", "idx_opportunities_ticker"} <= indexes
    # The attempt and fill tables are created by this migration, so their
    # indexes are its job too -- a per-run consumer query would otherwise
    # full-scan every attempt until the next init_db.
    assert {"idx_attempts_run", "idx_fills_opportunity"} <= indexes


def test_the_surviving_row_keeps_its_original_id(legacy):
    """Ids are cited by campaign write-ups and pointed at by the legs table.

    Reassigning them would also alias: a rebuilt AUTOINCREMENT table hands
    out ids that legacy rows still hold, so repointing legs by id would
    move rows belonging to another group.
    """
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="judged", kalshi_ticker="KXA",
                last_seen_at=TS2)
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXB")
    expected = legacy.execute(
        "SELECT MIN(id) FROM opportunities WHERE kalshi_ticker = 'KXA'"
    ).fetchone()[0]
    db.migrate_positions(legacy)
    kept = legacy.execute(
        "SELECT id FROM opportunities WHERE kalshi_ticker = 'KXA'"
    ).fetchone()["id"]
    assert kept == expected


def test_sqlite_sequence_is_restored_past_the_premigration_max(legacy):
    """A deleted id must never be handed to a different market.

    Constructed so the highest id in the pre-migration table (2) belongs to
    the LOSING row of a group: KXA's later, judged row is dropped in favor
    of the earlier one (id 1), so nothing in the rebuild ever re-inserts id
    2 -- SQLite's own AUTOINCREMENT bookkeeping only sees what actually
    landed in the new table, which tops out at id 1. Left alone, the next
    row written after this migration would be handed id 2 -- the exact id
    the backup table already assigned to KXA's judged attempt.
    """
    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="judged", kalshi_ticker="KXA",
                confidence="strong", last_seen_at=TS2)
    pre_migration_max = legacy.execute(
        "SELECT MAX(id) FROM opportunities"
    ).fetchone()[0]
    assert pre_migration_max == 2, "the losing row must hold the max id"

    db.migrate_positions(legacy)

    survivor_max = legacy.execute(
        "SELECT MAX(id) FROM opportunities"
    ).fetchone()[0]
    assert survivor_max == 1, "sanity: the losing row's id (2) is gone"

    seq = legacy.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = 'opportunities'"
    ).fetchone()[0]
    assert seq >= pre_migration_max, (
        "sqlite_sequence must not fall below the pre-migration max, or the "
        "next position written reuses an id the backup table already "
        "assigned to a different market"
    )

    # Prove it end to end: the next row autoincremented into the table (no
    # explicit id, exactly how ledger.record_opportunity inserts) must not
    # collide with id 2. The rebuilt opportunities table FK-references
    # theories(id) with foreign_keys back ON post-migration, so the parent
    # row has to exist for this insert to be legal at all.
    legacy.execute("CREATE TABLE theories (id TEXT PRIMARY KEY)")
    legacy.execute("INSERT INTO theories (id) VALUES ('t1')")
    new_id = legacy.execute(
        "INSERT INTO opportunities ("
        " theory_id, theory_version, run_mode, run_id, kalshi_ticker,"
        " outcome, entry_price, screen_edge_pts_net, edge_pts_net,"
        " first_seen_at, last_seen_at"
        ") VALUES ('t1', 1, 'live', 'live', 'KXNEW', 'yes', 0.5, 1.0, 1.0,"
        " ?, ?)",
        (TS, TS),
    ).lastrowid
    legacy.commit()
    assert new_id > pre_migration_max, (
        f"id {new_id} was already assigned to a different market "
        f"(KXA's judged attempt) in the backup table"
    )


def test_restore_sequence_ceiling_inserts_a_row_when_none_exists(tmp_path):
    """`_restore_sequence_ceiling` must not assume a row already exists.

    In `migrate_positions` itself the loop's explicit-id inserts always
    create the row first, so this branch is unreachable through that call
    path -- exercised directly here instead, on a table that has never had
    an AUTOINCREMENT write at all.
    """
    c = db.connect(tmp_path / "seq.db")
    c.execute(
        "CREATE TABLE opportunities (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " x TEXT)"
    )
    c.commit()
    assert c.execute(
        "SELECT * FROM sqlite_sequence WHERE name = 'opportunities'"
    ).fetchone() is None

    db._restore_sequence_ceiling(c, "opportunities", 10529)
    c.commit()

    seq = c.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = 'opportunities'"
    ).fetchone()[0]
    assert seq == 10529
    c.close()


def test_restore_sequence_ceiling_never_lowers_an_existing_seq(tmp_path):
    c = db.connect(tmp_path / "seq.db")
    c.execute(
        "CREATE TABLE opportunities (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " x TEXT)"
    )
    c.execute("INSERT INTO opportunities (id, x) VALUES (500, 'a')")
    c.commit()

    db._restore_sequence_ceiling(c, "opportunities", 10)
    c.commit()

    seq = c.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = 'opportunities'"
    ).fetchone()[0]
    assert seq == 500, "a lower minimum must never pull the ceiling down"
    c.close()


def test_restore_sequence_ceiling_is_a_noop_for_a_zero_minimum(tmp_path):
    c = db.connect(tmp_path / "seq.db")
    c.execute(
        "CREATE TABLE opportunities (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " x TEXT)"
    )
    c.commit()

    db._restore_sequence_ceiling(c, "opportunities", 0)
    c.commit()

    assert c.execute(
        "SELECT * FROM sqlite_sequence WHERE name = 'opportunities'"
    ).fetchone() is None
    c.close()


def test_a_failed_migration_leaves_the_database_untouched(legacy, monkeypatch):
    """The rollback must undo work that had already landed, not nothing.

    A failure on the first group proves very little -- there is no
    half-built table to discard. This one fires while the *second* group is
    being rolled up, so a whole position, its attempts and its fill are
    already in the rebuilt tables when the exception goes off, and the
    witness below records that they really were there.
    """
    for ticker in ("KXA", "KXB", "KXC"):
        _legacy_row(legacy, run_id="fullcov", kalshi_ticker=ticker)
        _legacy_row(legacy, run_id="judged", kalshi_ticker=ticker,
                    confidence="strong", last_seen_at=TS2,
                    user_action="taken", user_size=5.0)
    before = _rows(legacy, "opportunities")
    tables = _tables(legacy)

    real_day = db._decision_day
    witness = {}

    def explode(row):
        # `opportunities` is the rebuilt table only once the rename has
        # happened. Waiting for both of the first group's attempts means a
        # whole group -- position, fill and attempts -- is on disk before
        # the exception goes off.
        renamed = legacy.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'opportunities_legacy'"
        ).fetchone()
        if renamed is not None:
            witness["positions"] = legacy.execute(
                "SELECT COUNT(*) FROM opportunities"
            ).fetchone()[0]
            witness["attempts"] = legacy.execute(
                "SELECT COUNT(*) FROM opportunity_attempts"
            ).fetchone()[0]
            witness["fills"] = legacy.execute(
                "SELECT COUNT(*) FROM opportunity_fills"
            ).fetchone()[0]
            if witness["attempts"] >= 2:
                raise RuntimeError("usage cut out mid-migration")
        return real_day(row)

    monkeypatch.setattr(db, "_decision_day", explode)
    with pytest.raises(RuntimeError):
        db.migrate_positions(legacy)

    assert witness["positions"] >= 1, "the failure must land after an INSERT"
    assert witness["attempts"] >= 2 and witness["fills"] >= 1

    assert _rows(legacy, "opportunities") == before
    assert _tables(legacy) == tables
    assert "opportunity_attempts" not in _tables(legacy), "rebuilt tables go"
    assert "opportunity_fills" not in _tables(legacy)
    assert db.has_legacy_position_key(legacy)


# --- the CLI command and the init_db guard -------------------------------


def test_init_db_refuses_a_legacy_database(legacy):
    with pytest.raises(RuntimeError, match="migrate-positions"):
        db.init_db(legacy)


def test_init_db_is_happy_once_migrated(legacy):
    _legacy_row(legacy, run_id="r1", kalshi_ticker="KXA")
    db.migrate_positions(legacy)
    db.init_db(legacy)  # must not raise


def test_the_cli_reports_the_collapse(legacy, tmp_path, capsys):
    from tools import cli

    _legacy_row(legacy, run_id="fullcov", kalshi_ticker="KXA")
    _legacy_row(legacy, run_id="judged", kalshi_ticker="KXA",
                confidence="strong")
    legacy.commit()
    legacy.close()

    rc = cli.main([
        "--db", str(tmp_path / "legacy.db"), "migrate-positions", "--dry-run",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"before": 2' in out and '"after": 1' in out
