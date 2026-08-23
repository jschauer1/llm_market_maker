import json

import pytest

from tools import cli, db, ideas, ledger, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def dbpath(tmp_path):
    path = tmp_path / "test.db"
    conn = db.connect(path)
    db.init_db(conn)
    theories.register(conn, "t1", "Theory One", "theories/t1", now=TS)
    conn.close()
    return str(path)


def _run(capsys, *args):
    code = cli.main(list(args))
    out = capsys.readouterr().out
    return code, json.loads(out) if out.strip() else None


def test_init_creates_the_database(tmp_path, capsys):
    path = tmp_path / "fresh.db"
    code, payload = _run(capsys, "--db", str(path), "init")
    assert code == 0
    assert payload["ok"] is True
    assert path.exists()


def test_theories_list_outputs_json(dbpath, capsys):
    code, payload = _run(capsys, "--db", dbpath, "theories", "list")
    assert code == 0
    assert [t["id"] for t in payload] == ["t1"]


def test_theories_list_filters_by_status(dbpath, capsys):
    _run(capsys, "--db", dbpath, "theories", "status", "t1", "active")
    code, payload = _run(
        capsys, "--db", dbpath, "theories", "list", "--status", "active"
    )
    assert [t["id"] for t in payload] == ["t1"]

    code, payload = _run(
        capsys, "--db", dbpath, "theories", "list", "--status", "retired"
    )
    assert payload == []


def test_theories_register_creates_one(dbpath, capsys):
    _run(capsys, "--db", dbpath, "theories", "register", "t2", "Two",
         "theories/t2")
    code, payload = _run(capsys, "--db", dbpath, "theories", "list")
    assert {t["id"] for t in payload} == {"t1", "t2"}


def test_theories_bump_increments_version(dbpath, capsys):
    code, payload = _run(capsys, "--db", dbpath, "theories", "bump", "t1")
    assert payload["version"] == 2


def test_ideas_record_and_search(dbpath, capsys):
    _run(capsys, "--db", dbpath, "ideas", "record", "whale-copy",
         "Copy Polymarket whales", "--description", "Follow large traders.")
    code, payload = _run(capsys, "--db", dbpath, "ideas", "search", "whale")
    assert [i["slug"] for i in payload] == ["whale-copy"]


def test_ideas_search_returns_empty_for_no_match(dbpath, capsys):
    code, payload = _run(capsys, "--db", dbpath, "ideas", "search", "nothing")
    assert payload == []


def test_ideas_status_records_the_outcome(dbpath, capsys):
    _run(capsys, "--db", dbpath, "ideas", "record", "i1", "Idea one")
    _run(capsys, "--db", dbpath, "ideas", "status", "i1", "dead",
         "--outcome", "No signal found.",
         "--revisit-angle", "Retry with better matching.")
    code, payload = _run(capsys, "--db", dbpath, "ideas", "revisitable")
    assert payload[0]["slug"] == "i1"
    assert "better matching" in payload[0]["revisit_angle"]


def test_opportunities_list_is_empty_initially(dbpath, capsys):
    code, payload = _run(capsys, "--db", dbpath, "opportunities", "list")
    assert payload == []


def test_opportunities_list_shows_recorded_rows(dbpath, capsys):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXA",
        outcome="yes", entry_price=0.4, edge_pts_net=6.0, now=TS,
    )
    conn.close()
    code, payload = _run(capsys, "--db", dbpath, "opportunities", "list")
    assert payload[0]["kalshi_ticker"] == "KXA"


def test_rank_applies_credibility_shrinkage(capsys):
    code, payload = _run(capsys, "rank", "--edge", "12", "--n", "0")
    assert payload["ranked_edge"] == pytest.approx(3.0)
    assert payload["credibility"] == pytest.approx(0.25)


def test_rank_uses_measured_realization(capsys):
    code, payload = _run(
        capsys, "rank", "--edge", "6", "--n", "40",
        "--calibration-edge-net", "6", "--mean-claimed-edge", "6",
    )
    assert payload["ranked_edge"] == pytest.approx(4.0, abs=0.01)


def test_score_report_outputs_all_dispositions(dbpath, capsys):
    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1")
    assert set(payload) >= {"all", "endorsed", "rejected"}
    assert payload["all"]["n"] == 0


def test_unknown_command_returns_nonzero(capsys):
    with pytest.raises(SystemExit):
        cli.main(["nonsense"])
