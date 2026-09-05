import json

import pytest

from tools import cli, db, ledger, score, slices, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def dbpath(make_db_file):
    """A real database FILE, because the CLI reopens it by path.

    Copied from the session template rather than built per test: the file
    semantics the CLI needs are identical, the construction is not.
    """
    path = make_db_file()
    conn = db.connect(path)
    theories.register(conn, "t1", "Theory One", "theories/t1", now=TS)
    db.close(conn)
    return str(path)


def _run(capsys, *args):
    code = cli.main(list(args))
    out = capsys.readouterr().out
    return code, json.loads(out) if out.strip() else None


def test_score_report_save_persists_score_rows(dbpath, capsys):
    """--save closes the 'nothing writes scores' gap: state's EVIDENCE
    renders what sessions compute instead of an empty table."""
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="TK1",
        outcome="no", entry_price=0.85, edge_pts_net=4.0,
        edge_basis="model", run_mode="live", run_id="live",
        decision_date="2026-08-27", rationale="x",
    )
    score.record_settlement(conn, "TK1", "no",
                            resolved_at="2026-09-01T00:00:00Z")
    conn.close()

    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1",
                         "--save")
    assert code == 0
    assert payload["saved_score_ids"].keys() == {
        "all", "screened", "endorsed", "rejected"}

    conn = db.connect(dbpath)
    rows = conn.execute(
        "SELECT disposition, n FROM scores WHERE theory_id='t1'"
    ).fetchall()
    conn.close()
    assert {r["disposition"] for r in rows} == {
        "all", "screened", "endorsed", "rejected"}
    assert {r["n"] for r in rows if r["disposition"] == "all"} == {1}


def test_score_report_save_accepts_the_chain_pool(dbpath, capsys):
    """The refusal here was correct while the scores table could not say
    what a row pooled. It can now (`pooled_versions`), and since the
    2026-08-31 ruling a bump carries evidence forward by default, so
    --save pools the chain as a matter of course."""
    code, _ = _run(capsys, "--db", dbpath, "score", "report", "t1",
                   "--save", "--pool", "chain")
    assert code == 0

    conn = db.connect(dbpath)
    row = conn.execute(
        "SELECT pooled_versions FROM scores WHERE segment = 'aggregate'"
    ).fetchone()
    conn.close()
    assert row["pooled_versions"] == "1"


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
    code, payload = _run(capsys, "--db", dbpath, "theories", "bump", "t1",
                         "--justification", "new gate")
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


@pytest.mark.parametrize("actor", ["claude", "codex"])
def test_theories_status_retired_refuses_agent_providers(dbpath, capsys, actor):
    _run(capsys, "--db", dbpath, "theories", "propose-retirement", "t1",
         "--rationale", "no slice profitable")
    with pytest.raises(PermissionError):
        _run(capsys, "--db", dbpath, "theories", "status", "t1", "retired",
             "--authorized-by", actor)


def test_theories_status_accepts_codex_attribution(dbpath, capsys):
    _, payload = _run(capsys, "--db", dbpath, "theories", "status", "t1",
                      "under_review", "--authorized-by", "codex")
    assert payload["status"] == "under_review"


def test_theories_status_retired_needs_user_authorization(dbpath, capsys):
    _run(capsys, "--db", dbpath, "theories", "propose-retirement", "t1",
         "--rationale", "no slice profitable")
    code, payload = _run(capsys, "--db", dbpath, "theories", "status", "t1",
                         "retired", "--authorized-by", "user")
    assert payload["status"] == "retired"


def test_ideas_record_defaults_to_neutral_agent_source(dbpath, capsys):
    _, payload = _run(capsys, "--db", dbpath, "ideas", "record", "i1",
                      "Idea one")
    assert payload["source"] == "agent"


@pytest.mark.parametrize("source", ["claude", "codex"])
def test_ideas_record_accepts_provider_source(dbpath, capsys, source):
    _, payload = _run(capsys, "--db", dbpath, "ideas", "record", "i1",
                      "Idea one", "--source", source)
    assert payload["source"] == source


def test_ideas_record_omitted_source_preserves_existing_attribution(
        dbpath, capsys):
    _run(capsys, "--db", dbpath, "ideas", "record", "i1", "Idea one",
         "--source", "claude")
    _, payload = _run(capsys, "--db", dbpath, "ideas", "record", "i1",
                      "Updated idea")
    assert payload["source"] == "claude"


def test_ideas_record_explicit_source_updates_existing_attribution(
        dbpath, capsys):
    _run(capsys, "--db", dbpath, "ideas", "record", "i1", "Idea one",
         "--source", "claude")
    _, payload = _run(capsys, "--db", dbpath, "ideas", "record", "i1",
                      "Idea one", "--source", "codex")
    assert payload["source"] == "codex"


def test_theories_propose_retirement_records_without_retiring(dbpath, capsys):
    code, payload = _run(
        capsys, "--db", dbpath, "theories", "propose-retirement", "t1",
        "--rationale", "gross and net both flat across every slice",
    )
    assert payload["status"] == "proposed"
    assert payload["retirement_rationale"].startswith("gross and net")


def test_provenance_record_accepts_an_exact_rendered_prompt_file(
        dbpath, capsys, tmp_path):
    template = tmp_path / "analysis.md"
    template.write_text("Judge {n} events.\n", encoding="utf-8")
    rendered = tmp_path / "rendered.txt"
    rendered.write_text("Judge 3 events.\n", encoding="utf-8")

    _, payload = _run(
        capsys, "--db", dbpath, "provenance", "record",
        "--theory", "t1", "--version", "1", "--run", "r1",
        "--stage", "analysis", "--model", "gpt-6-astra",
        "--prompt-path", str(template),
        "--rendered-prompt-file", str(rendered),
    )
    assert payload[0]["prompt_path"] == str(template)
    assert payload[0]["prompt_text"] == "Judge 3 events.\n"


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
    _run(capsys, "--db", dbpath, "theories", "bump", "t1",
        "--justification", "new gate")
    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1")
    assert payload["theory_version"] == 2


def test_score_report_run_id_scopes_the_sample(dbpath, capsys):
    conn = db.connect(dbpath)
    # Two backtest runs proposing the same market merge into one position
    # (position-identity dedup), so the unscoped report still reads n=1 --
    # a duplicate recording must not move it.
    for run in ("run-a", "run-b"):
        score.record_backtest_run(conn, run, "t1", 1, tier="A")
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


def _echo_decide(row):
    """A decide that reproduces the recorded outputs exactly (proves carry)."""
    return {
        "outcome": row["outcome"], "disposition": row["disposition"],
        "model_prob": row["model_prob"], "confidence": row["confidence"],
        "edge_pts_gross": row["edge_pts_gross"],
        "edge_pts_net": row["edge_pts_net"], "edge_basis": row["edge_basis"],
    }


def test_score_report_pool_chain_pools_across_a_proven_carry(dbpath, capsys):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXCH-A",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, model_prob=0.55,
        edge_pts_gross=8.0, confidence="strong", edge_basis="measured",
        rationale="looks mispriced", now=TS,
    )
    score.record_settlement(
        conn, "KXCH-A", "yes", resolved_at="2026-08-20T00:00:00Z"
    )

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.passed
    theories.bump_version(
        conn, "t1", kind="carry", justification="no-op refactor",
        equivalence=res,
    )

    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=2, kalshi_ticker="KXCH-B",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, model_prob=0.55,
        edge_pts_gross=8.0, confidence="strong", edge_basis="measured",
        rationale="looks mispriced", now=TS,
    )
    score.record_settlement(
        conn, "KXCH-B", "yes", resolved_at="2026-08-27T00:00:00Z"
    )
    conn.close()

    # --pool version: v1's predecessor never joins.
    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1",
                         "--pool", "version")
    assert payload["all"]["n"] == 1
    assert "chain_versions" not in payload["all"]
    assert payload["settlement_days"]["all"]["n"] == 1
    assert "chain_versions" not in payload["settlement_days"]["all"]

    # Default (--pool chain since the 2026-08-31 ruling): the carry pools
    # v1's row in, for both the score and the settlement-day clusters
    # alike -- no silent segment mismatch.
    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1")
    assert payload["all"]["n"] == 2
    assert payload["all"]["chain_versions"] == [1, 2]
    assert payload["settlement_days"]["all"]["n"] == 2
    assert payload["settlement_days"]["all"]["n_days"] == 2
    assert payload["settlement_days"]["all"]["chain_versions"] == [1, 2]


def test_score_report_default_pool_matches_explicit_version(dbpath, capsys):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXNP-A",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, now=TS,
    )
    score.record_settlement(conn, "KXNP-A", "yes", resolved_at=TS)
    conn.close()

    code, implicit = _run(capsys, "--db", dbpath, "score", "report", "t1")
    code, explicit = _run(
        capsys, "--db", dbpath, "score", "report", "t1", "--pool", "version",
    )
    assert implicit == explicit


def test_slices_report_pool_chain_pools_across_a_proven_carry(dbpath, capsys):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXCP-A",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, now=TS,
    )
    score.record_settlement(
        conn, "KXCP-A", "yes", resolved_at="2026-08-20T00:00:00Z"
    )

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.passed
    theories.bump_version(
        conn, "t1", kind="carry", justification="no-op refactor",
        equivalence=res,
    )

    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=2, kalshi_ticker="KXCQ-A",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, now=TS,
    )
    score.record_settlement(
        conn, "KXCQ-A", "yes", resolved_at="2026-08-27T00:00:00Z"
    )
    conn.close()

    # --pool version: v1's predecessor never joins.
    code, payload = _run(capsys, "--db", dbpath, "slices", "report", "t1",
                         "--pool", "version")
    assert payload["aggregate"]["n"] == 1
    assert "chain_versions" not in payload

    # Default (--pool chain since the 2026-08-31 ruling): the carry pools
    # v1's row in.
    code, payload = _run(capsys, "--db", dbpath, "slices", "report", "t1")
    assert payload["aggregate"]["n"] == 2
    assert payload["chain_versions"] == [1, 2]


def test_slices_match_pool_chain_pools_across_a_proven_carry(dbpath, capsys):
    conn = db.connect(dbpath)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXCM-A",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, now=TS,
    )
    score.record_settlement(
        conn, "KXCM-A", "yes", resolved_at="2026-08-20T00:00:00Z"
    )

    res = theories.prove_carry(conn, "t1", 1, _echo_decide)
    assert res.passed
    theories.bump_version(
        conn, "t1", kind="carry", justification="no-op refactor",
        equivalence=res,
    )

    opp_id2, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=2, kalshi_ticker="KXCN-A",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, now=TS,
    )
    score.record_settlement(
        conn, "KXCN-A", "yes", resolved_at="2026-08-27T00:00:00Z"
    )
    conn.close()

    # --pool version: v1's predecessor never joins the ranking segment
    # -- distinct ticker prefixes so n_clusters (what rank_inputs
    # reports) really does differ below.
    code, payload = _run(
        capsys, "--db", dbpath, "slices", "match", str(opp_id2),
        "--pool", "version",
    )
    assert payload["rank_inputs"]["n"] == 1
    assert "chain_versions" not in payload

    # Default (--pool chain since the 2026-08-31 ruling): the carry pools
    # v1's row in, and the ranking segment discloses it.
    code, payload = _run(
        capsys, "--db", dbpath, "slices", "match", str(opp_id2),
    )
    assert payload["rank_inputs"]["n"] == 2
    assert payload["chain_versions"] == [1, 2]


def test_slices_match_default_pool_matches_explicit_version(dbpath, capsys):
    conn = db.connect(dbpath)
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXCO-A",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, now=TS,
    )
    score.record_settlement(conn, "KXCO-A", "yes", resolved_at=TS)
    conn.close()

    code, implicit = _run(
        capsys, "--db", dbpath, "slices", "match", str(opp_id),
    )
    code, explicit = _run(
        capsys, "--db", dbpath, "slices", "match", str(opp_id),
        "--pool", "version",
    )
    assert implicit == explicit


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


def test_score_report_save_pools_live_and_backtest_by_default(dbpath, capsys):
    """What `state` displays must be what `promote` decides from, and
    promote ranks on the pooled live+backtest segment. A saved score
    scoped to live alone would show less evidence than the bet actually
    rests on -- and after the 2026-08-31 ruling a backtested edge is
    evidence in full."""
    conn = db.connect(dbpath)
    db.init_db(conn)
    theories.register(conn, "t1", "T1", "theories/t1", status="testing")
    score.record_backtest_run(conn, "bt-1", "t1", 1, tier="B")
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="BT1",
        outcome="no", entry_price=0.8, edge_pts_net=3.0, edge_basis="model",
        run_mode="backtest", run_id="bt-1", decision_date="2026-06-01",
        rationale="x",
    )
    score.record_settlement(conn, "BT1", "no",
                            resolved_at="2026-06-05T00:00:00Z")
    conn.close()

    code, _ = _run(capsys, "--db", dbpath, "score", "report", "t1", "--save")
    assert code == 0

    conn = db.connect(dbpath)
    row = conn.execute(
        "SELECT run_mode, n FROM scores"
        " WHERE theory_id='t1' AND disposition='all' AND segment='aggregate'"
    ).fetchone()
    conn.close()
    assert row["run_mode"] == "pooled"
    assert row["n"] == 1, "the backtest settlement is evidence in full"


def test_score_report_shows_all_the_evidence_a_theory_has(dbpath, capsys):
    """`score report <id>` is the obvious command for "how is this theory
    doing", so it must not answer a narrower question than it appears to.

    Defaulting to live-only and version-only made it print n=9 for a
    theory holding 3,484 observations, 3,279 of them replayed. An agent
    reading that concludes the theory has no evidence and passes up a
    backtest that already exists -- which is the exact way a version bump
    used to silently discard a track record.
    """
    conn = db.connect(dbpath)
    db.init_db(conn)
    theories.register(conn, "t1", "T1", "theories/t1", status="testing")
    score.record_backtest_run(conn, "bt-1", "t1", 1, tier="A")
    for i in range(6):
        ledger.record_opportunity(
            conn, theory_id="t1", theory_version=1, kalshi_ticker=f"BT{i}-X",
            outcome="no", entry_price=0.8, edge_pts_net=3.0,
            edge_basis="model", run_mode="backtest", run_id="bt-1",
            decision_date="2026-06-01", rationale="x",
        )
        score.record_settlement(conn, f"BT{i}-X", "no",
                                resolved_at=f"2026-06-0{i + 1}T00:00:00Z")
    theories.bump_version(conn, "t1", justification="tightened a threshold")
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=2, kalshi_ticker="LIVE1-X",
        outcome="no", entry_price=0.8, edge_pts_net=3.0, edge_basis="model",
        run_mode="live", run_id="live", decision_date="2026-08-27",
        rationale="x",
    )
    score.record_settlement(conn, "LIVE1-X", "no",
                            resolved_at="2026-09-01T00:00:00Z")
    conn.close()

    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1")
    assert code == 0
    assert payload["all"]["n"] == 7, (
        "six replayed settlements at v1 plus one live at v2 -- a bump does "
        "not discard evidence, and a backtest is evidence"
    )
    assert payload["settlement_days"]["all"]["n"] == 7
    assert payload["settlement_days"]["all"]["n_days"] == 7


@pytest.mark.parametrize("run_filter", [(), ("--run-id", "bt-one")])
def test_score_report_segments_use_the_same_requested_sample(dbpath, capsys, run_filter):
    conn = db.connect(dbpath)
    slices.register_slice(
        conn, "t1", "no-side", predicate={"outcome": ["no"]},
        hypothesis="fixture NO subset", origin="independent fixture",
        registered_at="2026-01-01T00:00:00Z",
    )
    for run_id, mode in (("bt-one", "backtest"), ("bt-two", "backtest"), ("live", "live")):
        if mode == "backtest":
            score.record_backtest_run(conn, run_id, "t1", 1, tier="A")
        ledger.record_opportunity(
            conn, theory_id="t1", theory_version=1, kalshi_ticker=run_id.upper(),
            outcome="no", entry_price=0.8, edge_pts_net=3.0, edge_basis="model",
            run_mode=mode, run_id=run_id, decision_date="2026-06-01",
        )
        score.record_settlement(conn, run_id.upper(), "no", resolved_at="2026-06-02T00:00:00Z")
    conn.close()

    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1",
                         "--run-mode", "backtest", *run_filter)
    assert code == 0
    expected = 1 if run_filter else 2
    assert payload["all"]["n"] == expected
    assert payload["segments"]["slice:no-side"]["n"] == expected
    assert payload["settlement_days"]["all"]["n"] == expected


def test_score_report_can_still_be_narrowed_explicitly(dbpath, capsys):
    conn = db.connect(dbpath)
    db.init_db(conn)
    theories.register(conn, "t1", "T1", "theories/t1", status="testing")
    score.record_backtest_run(conn, "bt-1", "t1", 1, tier="A")
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="BT0-X",
        outcome="no", entry_price=0.8, edge_pts_net=3.0, edge_basis="model",
        run_mode="backtest", run_id="bt-1", decision_date="2026-06-01",
        rationale="x",
    )
    score.record_settlement(conn, "BT0-X", "no",
                            resolved_at="2026-06-01T00:00:00Z")
    conn.close()

    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1",
                         "--run-mode", "live")
    assert payload["all"]["n"] == 0, "live-only is still available, by asking"


def test_score_report_includes_sub_theory_performance(dbpath, capsys):
    """"How is this theory doing" is not answered by the parent alone. A
    sub-theory can be strongly supported while the theory around it is
    flat, so the command that answers that question must show both."""
    conn = db.connect(dbpath)
    db.init_db(conn)
    theories.register(conn, "t1", "T1", "theories/t1", status="testing")
    slices.register_slice(
        conn, "t1", "strong-no",
        predicate={"outcome": ["no"], "confidence": ["strong"]},
        hypothesis="the NO subset carries the edge", origin="test",
        registered_at="2026-08-26T00:00:00Z",
    )
    for i in range(12):
        ledger.record_opportunity(
            conn, theory_id="t1", theory_version=1, kalshi_ticker=f"SUB{i}-X",
            outcome="no", entry_price=0.85, edge_pts_net=4.0,
            edge_basis="model", run_mode="live", run_id="live",
            decision_date="2026-08-27", confidence="strong", rationale="x",
        )
        score.record_settlement(conn, f"SUB{i}-X", "no",
                                resolved_at=f"2026-09-{(i % 6) + 1:02d}T00:00:00Z")
    conn.close()

    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1")
    assert code == 0
    segments = payload["segments"]
    assert "slice:strong-no" in segments
    assert segments["slice:strong-no"]["n"] == 12
    assert segments["slice:strong-no"]["ready"] is True


def test_cli_bump_default_kind_matches_the_python_api_default(dbpath, capsys):
    """The CLI's default bump kind must BE the Python API's default.

    These drifted: `theories.bump_version` took `kind='continues'` as its
    default from the 2026-08-31 ruling, while the CLI kept `breaking` --
    the pre-ruling default -- and did not even offer `continues` as a
    choice. A session bumping through the CLI therefore severed its
    theory's evidence by accident, which is the exact failure the ruling
    was made to stop; three of four running theories reached n=0 that way
    before it. Pinned here so the two cannot drift apart again silently.
    """
    import inspect

    api_default = inspect.signature(theories.bump_version).parameters["kind"].default
    assert api_default == "continues"

    code, payload = _run(capsys, "--db", dbpath, "theories", "bump", "t1",
                         "--justification", "changed a threshold")
    assert code == 0
    assert payload["version"] == 2

    conn = db.connect(dbpath)
    kind = conn.execute(
        "SELECT kind FROM theory_versions WHERE theory_id='t1' AND version=2"
    ).fetchone()["kind"]
    conn.close()
    assert kind == api_default


def test_cli_bump_can_record_continues_explicitly(dbpath, capsys):
    """`continues` must be an accepted --kind choice, not just the default.

    A session following a ticket that says "bump, kind 'continues'" passes
    the flag explicitly. Before the fix argparse rejected the value
    outright, so the documented instruction was unrunnable.
    """
    code, payload = _run(capsys, "--db", dbpath, "theories", "bump", "t1",
                         "--kind", "continues",
                         "--justification", "widened the population")
    assert code == 0

    conn = db.connect(dbpath)
    kind = conn.execute(
        "SELECT kind FROM theory_versions WHERE theory_id='t1' AND version=2"
    ).fetchone()["kind"]
    conn.close()
    assert kind == "continues"


def test_cli_bump_breaking_still_available_as_an_explicit_sever(dbpath, capsys):
    """Severing stays available and absolute -- it just has to be asked for."""
    code, payload = _run(capsys, "--db", dbpath, "theories", "bump", "t1",
                         "--kind", "breaking",
                         "--justification", "population is unrecognisable")
    assert code == 0

    conn = db.connect(dbpath)
    kind = conn.execute(
        "SELECT kind FROM theory_versions WHERE theory_id='t1' AND version=2"
    ).fetchone()["kind"]
    conn.close()
    assert kind == "breaking"


def test_score_report_flags_a_riskless_bucket_that_is_entirely_rejections(
        dbpath, capsys):
    """A riskless return nobody could have taken must not read as a headline.

    `structural_arb`'s report showed `riskless_roi=+0.550` on `all` --
    +55% -- from two KXWTAGTOTAL findings whose own rationales read
    "~0.01 baskets fillable at riskless prices, ~$0.00 floor profit".
    Every row the theory has ever recorded was rejected, so `all` and
    `rejected` were identical, while `state`'s EVIDENCE line showed
    "n 0" and hid it in the other direction.

    This is narrower than "rejections count in roi_all", which is
    deliberate and documented: for a judgment theory a rejected winner is
    real counterfactual information -- the screen was right and the
    judgment cost you. A depth rejection is different in kind. "Not
    fillable at any size" means there was no position to take, so the
    counterfactual is IMPOSSIBLE rather than merely untaken.

    Report-only by design (option (a) of the ticket): no stored score
    changes, no vocabulary is redefined, and `riskless_roi` still means
    what every recorded row was written under.
    """
    conn = db.connect(dbpath)
    opp, _ = ledger.record_basket(
        conn, theory_id="t1", theory_version=1,
        legs=[{"kalshi_ticker": "ARB-A", "outcome": "yes", "entry_price": 0.40},
              {"kalshi_ticker": "ARB-B", "outcome": "no", "entry_price": 0.50}],
        max_payout=1.0, min_payout=1.0, edge_pts_net=5.0,
        edge_basis="model", run_mode="live", run_id="live",
        decision_date="2026-08-27", rationale="~0.01 baskets fillable",
    )
    ledger.interpret(conn, opp, "rejected", "not fillable at any size")
    score.record_settlement(conn, "ARB-A", "yes",
                            resolved_at="2026-09-01T00:00:00Z")
    score.record_settlement(conn, "ARB-B", "yes",
                            resolved_at="2026-09-01T00:00:00Z")
    conn.close()

    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1")
    assert code == 0
    assert payload["all"]["riskless_n"] == 1
    assert payload["all"]["riskless_roi"] is not None

    notes = payload.get("notes") or []
    assert any("riskless" in n.lower() and "reject" in n.lower()
               for n in notes), f"no annotation on the riskless bucket: {notes}"


def test_score_report_does_not_flag_a_riskless_bucket_with_live_rows(
        dbpath, capsys):
    """The annotation must fire only when EVERY riskless row was rejected.

    A theory with a genuinely takeable arbitrage alongside a rejected one
    is reporting real money, and warning about it would train readers to
    ignore the note.
    """
    conn = db.connect(dbpath)
    for i, disp in enumerate(("rejected", None)):
        opp, _ = ledger.record_basket(
            conn, theory_id="t1", theory_version=1,
            legs=[{"kalshi_ticker": f"ARB{i}-A", "outcome": "yes",
                   "entry_price": 0.40},
                  {"kalshi_ticker": f"ARB{i}-B", "outcome": "no",
                   "entry_price": 0.50}],
            max_payout=1.0, min_payout=1.0, edge_pts_net=5.0,
            edge_basis="model", run_mode="live", run_id="live",
            decision_date="2026-08-27", rationale="x",
        )
        if disp:
            ledger.interpret(conn, opp, disp, "not fillable")
        score.record_settlement(conn, f"ARB{i}-A", "yes",
                                resolved_at="2026-09-01T00:00:00Z")
        score.record_settlement(conn, f"ARB{i}-B", "yes",
                                resolved_at="2026-09-01T00:00:00Z")
    conn.close()

    code, payload = _run(capsys, "--db", dbpath, "score", "report", "t1")
    assert code == 0
    assert payload["all"]["riskless_n"] == 2
    notes = payload.get("notes") or []
    assert not any("riskless" in n.lower() for n in notes), notes


def test_filing_a_study_creates_a_directory_ticket(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "REPO_ROOT", tmp_path)
    rc = cli.main(["tickets", "new", "--lane", "study", "--slug", "probe",
                   "--title", "Does it fire?", "--body", "Bar: 10 hits."])
    assert rc == 0
    made = list((tmp_path / "tickets/study/question").iterdir())
    assert len(made) == 1 and (made[0] / "STUDY.md").is_file()


def test_advancing_a_study_moves_it(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "REPO_ROOT", tmp_path)
    cli.main(["tickets", "new", "--lane", "study", "--slug", "probe",
              "--title", "Q", "--body", "Bar: x."])
    made = next((tmp_path / "tickets/study/question").iterdir())
    rc = cli.main(["tickets", "advance", str(made / "STUDY.md"),
                   "--to", "investigation", "--note", "Collecting."])
    assert rc == 0
    assert (tmp_path / "tickets/study/investigation").is_dir()
    assert not any((tmp_path / "tickets/study/question").iterdir())


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    """Point the CLI's write root at a temp dir.

    `cli.main` resolves ticket paths from `db.REPO_ROOT`, a module
    constant -- NOT from the working directory, so `monkeypatch.chdir`
    does not contain it. A `tickets new` test without this fixture writes
    a real ticket into the real repository and leaves it there as an
    untracked file. That happened while these tests were being written.
    """
    monkeypatch.setattr(db, "REPO_ROOT", tmp_path)
    return tmp_path


def test_tickets_new_refuses_a_retired_theory(dbpath, repo_root):
    """The WIRING, not the rule: `ticket_dir` can only refuse if the CLI
    hands it the status, and that lookup is one line away from being
    dropped in a refactor. `tests/test_tickets.py` covers the rule itself.

    Without this, filing against a retired theory succeeds and then
    `test_a_retired_theory_holds_only_its_record` fails at some later
    commit that looks unrelated.
    """
    conn = db.connect(dbpath)
    theories.register(conn, "dead", "Dead Theory", "theories/retired/dead",
                      now=TS)
    theories.propose_retirement(conn, "dead", rationale="diagnosed and dead")
    theories.set_status(conn, "dead", "retired", authorized_by="user")
    assert theories.get(conn, "dead")["status"] == "retired"
    conn.close()

    with pytest.raises(ValueError, match="retired"):
        cli.main(["--db", dbpath, "tickets", "new", "--lane", "theory",
                  "--theory", "dead", "--slug", "s", "--title", "t",
                  "--body", "b", "--session", "sess"])
    assert not (repo_root / "theories" / "retired" / "dead" /
                "tickets").exists(), "the refusal must not leave a directory"


def test_tickets_new_still_files_against_a_live_theory(dbpath, repo_root,
                                                       capsys):
    """The control. A refusal keyed to the wrong thing -- a path prefix, a
    truthy status -- would take every theory down with it, and that would
    look identical from the retired case alone."""
    code, payload = _run(capsys, "--db", dbpath, "tickets", "new",
                         "--lane", "theory", "--theory", "t1",
                         "--slug", "alive", "--title", "t", "--body", "b",
                         "--session", "sess")
    assert payload["created"].startswith("theories/t1/tickets/open/")
    assert (repo_root / payload["created"]).exists()
