import json

import pytest

from tools import cli, db, ideas, ledger, score, theories

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


def test_theories_list_running_flag(dbpath, capsys):
    _run(capsys, "--db", dbpath, "theories", "status", "t1", "under_review")
    code, payload = _run(
        capsys, "--db", dbpath, "theories", "list", "--running"
    )
    assert [t["id"] for t in payload] == ["t1"]
    _run(capsys, "--db", dbpath, "theories", "status", "t1", "paused")
    code, payload = _run(
        capsys, "--db", dbpath, "theories", "list", "--running"
    )
    assert payload == []


def test_theories_status_accepts_under_review(dbpath, capsys):
    code, payload = _run(
        capsys, "--db", dbpath, "theories", "status", "t1", "under_review"
    )
    assert payload["status"] == "under_review"


def test_theories_status_retired_defaults_to_refusing(dbpath, capsys):
    _run(capsys, "--db", dbpath, "theories", "propose-retirement", "t1",
         "--rationale", "no slice profitable")
    with pytest.raises(PermissionError):
        _run(capsys, "--db", dbpath, "theories", "status", "t1", "retired")


def test_theories_status_retired_needs_user_authorization(dbpath, capsys):
    _run(capsys, "--db", dbpath, "theories", "propose-retirement", "t1",
         "--rationale", "no slice profitable")
    code, payload = _run(capsys, "--db", dbpath, "theories", "status", "t1",
                         "retired", "--authorized-by", "user")
    assert payload["status"] == "retired"


def test_theories_propose_retirement_records_without_retiring(dbpath, capsys):
    code, payload = _run(
        capsys, "--db", dbpath, "theories", "propose-retirement", "t1",
        "--rationale", "gross and net both flat across every slice",
    )
    assert payload["status"] == "proposed"
    assert payload["retirement_rationale"].startswith("gross and net")


def test_theories_pending_retirement_lists_unruled_proposals(dbpath, capsys):
    code, payload = _run(
        capsys, "--db", dbpath, "theories", "pending-retirement"
    )
    assert payload == []
    _run(capsys, "--db", dbpath, "theories", "propose-retirement", "t1",
         "--rationale", "diagnosed")
    code, payload = _run(
        capsys, "--db", dbpath, "theories", "pending-retirement"
    )
    assert [t["id"] for t in payload] == ["t1"]


def test_theories_withdraw_retirement_clears_it(dbpath, capsys):
    _run(capsys, "--db", dbpath, "theories", "propose-retirement", "t1",
         "--rationale", "diagnosed")
    code, payload = _run(
        capsys, "--db", dbpath, "theories", "withdraw-retirement", "t1"
    )
    assert payload["retirement_proposed_at"] is None


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


def test_score_report_includes_theory_version(dbpath, capsys):
    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1")
    assert payload["theory_version"] == 1


def test_score_report_theory_version_reflects_a_bump(dbpath, capsys):
    _run(capsys, "--db", dbpath, "theories", "bump", "t1")
    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1")
    assert payload["theory_version"] == 2


def test_score_report_run_id_scopes_the_sample(dbpath, capsys):
    conn = db.connect(dbpath)
    # Two backtest runs proposing the same market merge into one position
    # (position-identity dedup), so the unscoped report still reads n=1 --
    # a duplicate recording must not move it.
    for run in ("run-a", "run-b"):
        ledger.record_opportunity(
            conn, theory_id="t1", theory_version=1, kalshi_ticker="A",
            outcome="yes", entry_price=0.50, edge_pts_net=6.0,
            run_mode="backtest", run_id=run, now=TS,
            decision_date=TS[:10],
        )
    score.record_settlement(conn, "A", "yes")
    conn.close()

    code, payload = _run(
        capsys, "--db", dbpath, "score", "report", "t1",
        "--run-mode", "backtest",
    )
    assert payload["all"]["n"] == 1, "a duplicate recording must not move n"

    # run-a is the surviving row's own stored run_id -- the first sighting
    # -- so it would still resolve under the old `o.run_id = ?` scoping and
    # prove nothing about --run-id actually working. run-b only resolves
    # through the new EXISTS-against-opportunity_attempts scoping.
    code, payload = _run(
        capsys, "--db", dbpath, "score", "report", "t1",
        "--run-mode", "backtest", "--run-id", "run-b",
    )
    assert payload["all"]["n"] == 1


def test_state_write_matches_printed_text(dbpath, tmp_path, monkeypatch,
                                          capsys):
    # _cmd_state must render once and reuse the text for both stdout and
    # STATE.md -- rendering twice would stamp two different `now`
    # timestamps if the wall clock ticks over between the two calls.
    monkeypatch.chdir(tmp_path)
    from tools import state as state_mod
    stamps = iter(["2026-08-29T12:00:00Z", "2026-08-29T12:00:05Z"])
    monkeypatch.setattr(state_mod, "utcnow", lambda: next(stamps))

    code = cli.main(["--db", dbpath, "state", "--write"])
    out = capsys.readouterr().out
    written = (tmp_path / "STATE.md").read_text(encoding="utf-8")
    assert code == 0
    assert out.strip() == written.strip()


def test_unknown_command_returns_nonzero(capsys):
    with pytest.raises(SystemExit):
        cli.main(["nonsense"])


def test_opportunities_mark_taken_persists_action_size_and_reason(
    dbpath, capsys
):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXA",
        outcome="yes", entry_price=0.4, edge_pts_net=6.0, now=TS,
    )
    opp_id = ledger.list_opportunities(conn)[0]["id"]
    conn.close()

    code, payload = _run(
        capsys, "--db", dbpath, "opportunities", "mark-taken", str(opp_id),
        "taken", "--size", "25", "--reason", "reality TV markets are soft",
        "--theory", "t1",
    )
    assert code == 0
    assert payload["user_action"] == "taken"
    assert payload["user_size"] == pytest.approx(25.0)
    assert payload["user_reason"] == "reality TV markets are soft"


def test_opportunities_mark_taken_resolves_by_ticker(dbpath, capsys):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXA",
        outcome="yes", entry_price=0.4, edge_pts_net=6.0, now=TS,
    )
    conn.close()

    code = cli.main(
        ["--db", dbpath, "opportunities", "mark-taken",
         "--ticker", "KXA", "taken", "--size", "10", "--theory", "t1"]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert payload["user_action"] == "taken"
    assert "KXA" in captured.err
    assert "yes" in captured.err
    assert "live/main" in captured.err


def test_opportunities_mark_taken_rejects_both_id_and_ticker(dbpath, capsys):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXA",
        outcome="yes", entry_price=0.4, edge_pts_net=6.0, now=TS,
    )
    opp_id = ledger.list_opportunities(conn)[0]["id"]
    conn.close()

    with pytest.raises(SystemExit):
        cli.main(["--db", dbpath, "opportunities", "mark-taken", str(opp_id),
                  "--ticker", "KXA", "taken", "--size", "10",
                  "--theory", "t1"])


def test_opportunities_mark_taken_unknown_ticker_exits_cleanly(dbpath, capsys):
    with pytest.raises(SystemExit, match="no open live position on KXNOPE"):
        cli.main(["--db", dbpath, "opportunities", "mark-taken",
                  "--ticker", "KXNOPE", "taken", "--size", "10",
                  "--theory", "t1"])


def test_opportunities_mark_taken_ambiguous_ticker_exits_cleanly(
    dbpath, capsys
):
    conn = db.connect(dbpath)
    theories.register(conn, "t2", "Theory Two", "theories/t2", now=TS)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXA",
        outcome="yes", entry_price=0.4, edge_pts_net=6.0, now=TS,
    )
    ledger.record_opportunity(
        conn, theory_id="t2", theory_version=1, kalshi_ticker="KXA",
        outcome="yes", entry_price=0.4, edge_pts_net=6.0, now=TS,
    )
    conn.close()

    with pytest.raises(SystemExit, match="pass --theory"):
        cli.main(["--db", dbpath, "opportunities", "mark-taken",
                  "--ticker", "KXA", "taken", "--size", "10"])


def test_opportunities_mark_taken_rejects_invalid_action(dbpath, capsys):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXA",
        outcome="yes", entry_price=0.4, edge_pts_net=6.0, now=TS,
    )
    opp_id = ledger.list_opportunities(conn)[0]["id"]
    conn.close()

    with pytest.raises(SystemExit):
        cli.main(["--db", dbpath, "opportunities", "mark-taken", str(opp_id),
                  "pondered"])


def test_backtest_record_persists_a_run(dbpath, capsys):
    code, payload = _run(
        capsys, "--db", dbpath, "backtest", "record", "run-a", "t1", "1",
        "--tier", "A", "--model-cutoff", "2026-01-01",
        "--notes", "stage-1 screen only",
    )
    assert code == 0
    assert payload["run_id"] == "run-a"
    assert payload["theory_id"] == "t1"
    assert payload["theory_version"] == 1
    assert payload["tier"] == "A"
    assert payload["model_cutoff"] == "2026-01-01"
    assert payload["notes"] == "stage-1 screen only"
    assert payload["uses_llm_judgment"] is None


def test_backtest_record_stores_uses_llm_judgment_flag(dbpath, capsys):
    code, payload = _run(
        capsys, "--db", dbpath, "backtest", "record", "run-b", "t1", "1",
        "--tier", "B", "--uses-llm-judgment",
    )
    assert payload["uses_llm_judgment"] == 1


def _seed_positions(dbpath):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXS-26",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS,
    )
    ledger.record_basket(
        conn, theory_id="t1", theory_version=1, edge_pts_net=5.0,
        edge_basis="model", now=TS,
        legs=[
            {"kalshi_ticker": "KXA-26", "outcome": "yes",
             "entry_price": 0.40},
            {"kalshi_ticker": "KXB-26", "outcome": "no",
             "entry_price": 0.55},
        ],
    )
    conn.close()


def test_opportunities_list_omits_legs_by_default(dbpath, capsys):
    _seed_positions(dbpath)
    code, payload = _run(capsys, "--db", dbpath, "opportunities", "list")
    assert code == 0
    assert len(payload) == 2
    assert all("legs" not in row for row in payload)


def test_opportunities_list_with_legs_includes_them(dbpath, capsys):
    _seed_positions(dbpath)
    code, payload = _run(
        capsys, "--db", dbpath, "opportunities", "list", "--with-legs"
    )
    assert code == 0
    basket = [r for r in payload if r["position_kind"] == "basket"][0]
    assert len(basket["legs"]) == basket["leg_count"] == 2
    assert all(leg["kalshi_ticker"] for leg in basket["legs"])
    single = [r for r in payload if r["position_kind"] == "single"][0]
    assert single["legs"] == []
