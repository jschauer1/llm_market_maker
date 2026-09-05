import pytest

from tools import db, state


def test_state_renders_every_panel_header(conn):
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    for panel in ("THEORIES", "STANDING", "EVIDENCE", "WINDOWS",
                  "QUEUE", "FRESHNESS"):
        assert panel in text


def test_absent_tables_render_stubs_not_errors(conn):
    # theory_versions (phase 6) and data_windows (phase 7) do not exist
    # yet -- the shape is stable from day one and panels light up as
    # phases land (spec 3.2).
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "not yet tracked — table data_windows" in text


def _queue_row(
    conn, ticker, *, version=1, outcome="no", run_mode="live",
    run_id="live", edge=2.0, decision_date=None,
):
    from tools import ledger

    return ledger.record_opportunity(
        conn, theory_id="t", theory_version=version,
        kalshi_ticker=ticker, outcome=outcome, entry_price=0.85,
        edge_pts_net=edge, edge_basis="prior", run_mode=run_mode,
        run_id=run_id, decision_date=decision_date,
    )[0]


def test_queue_omits_an_old_endorsement_replaced_at_current_version(conn):
    """The v4 incident must not remain in the orientation queue.

    Promotion already classifies the old fork as R6. The queue is a
    separate SQL surface, so it must apply the same current-version
    successor rule instead of selecting every endorsed old row.
    """
    from tools import ledger, theories

    theories.register(conn, "t", "T", "theories/t", status="testing")
    old = _queue_row(conn, "FORK")
    ledger.interpret(conn, old, "endorsed", "old recommendation")
    theories.bump_version(conn, "t", kind="continues", justification="re-decided")
    _queue_row(conn, "FORK", version=2, edge=-1.0)

    lines = state._queue_panel(conn)
    assert not any("FORK" in line for line in lines)
    assert lines[-1] == "  (0 endorsed, untouched, unsettled in total)"


def test_queue_keeps_an_old_endorsement_without_a_successor(conn):
    """A version bump alone does not prove that a position was re-decided."""
    from tools import ledger, theories

    theories.register(conn, "t", "T", "theories/t", status="testing")
    old = _queue_row(conn, "LONELY")
    ledger.interpret(conn, old, "endorsed", "still live")
    theories.bump_version(conn, "t", kind="continues", justification="procedure changed")

    lines = state._queue_panel(conn)
    assert any("LONELY" in line for line in lines)
    assert lines[-1] == "  (1 endorsed, untouched, unsettled in total)"


def test_queue_does_not_hide_a_row_from_a_future_version(conn):
    """The comparator must not treat a lower current version as a successor."""
    from tools import ledger, theories

    theories.register(conn, "t", "T", "theories/t", status="testing")
    _queue_row(conn, "FUTURE", version=1)
    future = _queue_row(conn, "FUTURE", version=2)
    ledger.interpret(conn, future, "endorsed", "future recommendation")

    lines = state._queue_panel(conn)
    assert any("FUTURE" in line for line in lines)
    assert lines[-1] == "  (1 endorsed, untouched, unsettled in total)"


def test_queue_successor_matching_keeps_other_position_identities(conn):
    """Replay, experiment, and opposite-side rows do not supersede live NO."""
    from tools import ledger, theories

    theories.register(conn, "t", "T", "theories/t", status="testing")
    for ticker, outcome in (("REPLAY", "no"), ("EXPERIMENT", "no"),
                            ("SIDES", "no")):
        old = _queue_row(conn, ticker, outcome=outcome)
        ledger.interpret(conn, old, "endorsed", "live recommendation")
    theories.bump_version(conn, "t", kind="continues", justification="re-decided")
    _queue_row(conn, "REPLAY", version=2, run_mode="backtest",
               run_id="bt/test", decision_date="2026-09-01")
    _queue_row(conn, "EXPERIMENT", version=2, run_id="exp/test")
    _queue_row(conn, "SIDES", version=2, outcome="yes")

    lines = state._queue_panel(conn)
    assert all(any(ticker in line for line in lines)
               for ticker in ("REPLAY", "EXPERIMENT", "SIDES"))
    assert lines[-1] == "  (3 endorsed, untouched, unsettled in total)"


def test_queue_reports_total_before_limiting_visible_rows(conn):
    from tools import ledger, theories

    theories.register(conn, "t", "T", "theories/t", status="testing")
    for i in range(12):
        opp = _queue_row(conn, f"QUEUE-{i}")
        ledger.interpret(conn, opp, "endorsed", "recommendation")

    lines = state._queue_panel(conn)
    assert len(lines) == 11                 # ten rows plus the total line
    assert lines[-1] == "  (12 endorsed, untouched, unsettled in total)"


def test_queue_and_ledger_agree_when_a_basket_finishes_settling(conn):
    """The synthetic header never settles; completion follows every leg."""
    from tools import ledger, promotion, score, theories

    theories.register(conn, "t", "T", "theories/t", status="testing")
    basket, _ = ledger.record_basket(
        conn, theory_id="t", theory_version=1,
        legs=[{"kalshi_ticker": ticker, "outcome": "no", "entry_price": 0.45}
              for ticker in ("LEG-A", "LEG-B")],
        max_payout=2.0, edge_pts_net=4.0, edge_basis="model", run_id="live",
    )
    ledger.interpret(conn, basket, "endorsed", "two-leg recommendation")
    for ticker in (None, "LEG-A"):
        if ticker:
            score.record_settlement(conn, ticker, "no")
        assert [row["id"] for row in ledger.list_opportunities(
            conn, unsettled_only=True)] == [basket]
        assert state._queue_panel(conn)[-1].startswith("  (1 endorsed")

    score.record_settlement(conn, "LEG-B", "yes")
    assert ledger.list_opportunities(conn, unsettled_only=True) == []
    assert promotion.promote(conn, basket).rung == "R6"
    assert state._queue_panel(conn) == ["  (0 endorsed, untouched, unsettled in total)"]


def test_state_reflects_theories_and_freshness(conn):
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    with db.write(conn):
        conn.execute(
            "INSERT INTO market_snapshots (platform, market_id, captured_at,"
            " title, raw_json) VALUES ('kalshi', 'T-1',"
            " '2026-08-29T10:00:00Z', 't', '{}')"
        )
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "demo_theory" in text
    assert "last board pull" in text and "2026-08-29T10:00:00Z" in text


def test_write_flag_emits_state_md(conn, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state.write_state(conn, now="2026-08-29T12:00:00Z")
    assert (tmp_path / "STATE.md").read_text(encoding="utf-8").startswith("#")


def test_write_state_reuses_a_passed_rendering(conn, tmp_path, monkeypatch):
    # tools/cli.py's `state --write` renders once and passes the text
    # through, so the printed output and STATE.md agree byte for byte --
    # rendering twice would stamp two different `now` timestamps.
    monkeypatch.chdir(tmp_path)
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    state.write_state(conn, now="2026-08-29T23:59:59Z", text=text)
    assert (tmp_path / "STATE.md").read_text(encoding="utf-8") == text


def test_evidence_reports_honest_line_when_scores_never_written(conn):
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    theories.set_status(conn, "demo_theory", "testing")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "scores never written — run score-theories" in text
    assert "no live score at v" not in text
    assert "last settle run:  never" in text


def test_standing_truncates_long_rulings_and_shows_footer(conn):
    from tools import rulings
    long_text = "x" * 150
    rulings.record(
        conn, long_text, authority="user", subject="test-subject",
        ruled_at="2026-08-29T00:00:00Z",
    )
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert ("x" * 100 + "…") in text
    assert ("x" * 101) not in text
    assert (
        "full text: python -m tools.cli rulings list --status binding"
    ) in text


def test_standing_does_not_add_ellipsis_when_not_truncated(conn):
    from tools import rulings
    rulings.record(
        conn, "short ruling", authority="user", subject="test-subject",
        ruled_at="2026-08-29T00:00:00Z",
    )
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "short ruling…" not in text
    assert "short ruling" in text


def test_theories_panel_shows_chain_1_for_a_fresh_theory(conn):
    # I3: register() alone writes v1's own theory_versions row -- carry_
    # chain(..., 1) is [1], so the panel must show the real figure, not
    # the old "chain ready" placeholder.
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "[chain 1]" in text
    assert "chain ready" not in text


def test_theories_panel_shows_chain_n_for_a_proven_carry(conn):
    from tools import theories
    from tools.domain import EquivalenceResult
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    proof = EquivalenceResult(
        theory_id="demo_theory", from_version=1, n_attempts=1,
        divergences=(), n_divergent=0, label="carry-proof/demo-v1-to-v2",
    )
    theories.bump_version(
        conn, "demo_theory", kind="carry", justification="no-op refactor",
        equivalence=proof,
    )
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "[chain 2]" in text


def test_theories_panel_stubs_when_theory_versions_is_absent(conn):
    # Defensive path (mirrors every other panel's _table_exists guard):
    # an older DB that predates this table must stub, not error, even
    # though a theory was registered before the table went away.
    from tools import db as db_mod, theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    with db_mod.write(conn):
        conn.execute("DROP TABLE theory_versions")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "[chain n/a]" in text


def test_freshness_says_the_floor_is_due_when_none_has_run(conn):
    text = state.render_state(conn, now="2026-08-31T12:00:00Z")
    assert "floor duty:" in text
    assert "DUE" in text


def test_freshness_reports_a_completed_floor_and_when_the_next_is_due(conn):
    from tools import floor
    claim = floor.claim(conn, "sess-a", now="2026-08-31T01:00:00Z")
    floor.complete(conn, claim["id"], now="2026-08-31T02:00:00Z")

    text = state.render_state(conn, now="2026-08-31T06:00:00Z")
    assert "floor duty:" in text
    assert "DUE" not in text, "a floor that ran 4h ago is not due"
    assert "sess-a" in text


def test_evidence_shows_a_sub_theory_with_its_own_record(conn):
    """A sub-theory can be strong while its parent is flat. If EVIDENCE
    shows only the parent, the session orienting on it never learns the
    subset is bettable -- which is how a proven slice goes orphaned."""
    from tools import ledger, score, slices, theories

    theories.register(conn, "t", "T", "theories/t", status="testing")
    slices.register_slice(
        conn, "t", "strong-moderate-no",
        predicate={"outcome": ["no"], "confidence": ["strong", "moderate"]},
        hypothesis="the NO subset carries the edge the aggregate hides",
        origin="test fixture", registered_at="2026-08-26T00:00:00Z",
    )
    for i in range(12):
        ledger.record_opportunity(
            conn, theory_id="t", theory_version=1, kalshi_ticker=f"SUB{i}",
            outcome="no", entry_price=0.85, edge_pts_net=4.0,
            edge_basis="model", run_mode="live", run_id="live",
            decision_date="2026-08-27", confidence="strong", rationale="x",
        )
        score.record_settlement(
            conn, f"SUB{i}", "no",
            resolved_at=f"2026-09-{(i % 6) + 1:02d}T00:00:00Z")
    score.save_segment_scores(conn, "t", 1)

    text = state.render_state(conn, now="2026-09-10T12:00:00Z")
    assert "strong-moderate-no" in text, (
        "a sub-theory's record must surface in the orient path"
    )


def test_evidence_never_shows_a_sub_theorys_numbers_as_the_theorys(conn):
    """The parent line must read the aggregate row and only that. A
    sub-theory's score sitting in the same table with a later
    computed_at must never be picked up as the theory's own record."""
    from tools import score, theories

    theories.register(conn, "t", "T", "theories/t", status="testing")
    aggregate = dict(
        n=100, win_rate=0.5, price_implied_rate=0.5, calibration_edge=-9.0,
        calibration_edge_net=-9.0, mean_claimed_edge=0.0, realization=0.0,
        roi_all=0.0, roi_taken=None, riskless_n=0, riskless_roi=None,
        n_clusters=90, clustered_se=1.0,
    )
    subset = {**aggregate, "n": 3, "calibration_edge_net": 42.0,
              "n_clusters": 2}
    score.save_score(conn, "t", 1, "live", "all", aggregate,
                     now="2026-09-01T00:00:00Z", segment="aggregate")
    score.save_score(conn, "t", 1, "live", "all", subset,
                     now="2026-09-01T00:00:01Z", segment="slice:sub")

    text = state.render_state(conn, now="2026-09-10T12:00:00Z")
    lines = text.splitlines()
    start = lines.index("EVIDENCE")
    end = next(i for i in range(start + 1, len(lines))
               if lines[i] and not lines[i].startswith(" "))
    evidence = lines[start + 1:end]
    parent = [ln for ln in evidence if "sub:" not in ln][0]
    assert "-9.0" in parent, f"parent line took the subset's number: {parent}"
    assert "42.0" not in parent


def test_evidence_shows_what_share_of_a_record_is_backtested(conn):
    """Backtesting is worth doing and the panel should show it paying
    off. A replayed edge counts in full, so this is disclosure, not a
    caveat -- but a theory whose evidence exists BECAUSE someone ran a
    backtest should visibly say so."""
    from tools import score, theories

    theories.register(conn, "t", "T", "theories/t", status="testing")
    result = dict(
        n=40, win_rate=0.6, price_implied_rate=0.5, calibration_edge=10.0,
        calibration_edge_net=8.0, mean_claimed_edge=5.0, realization=1.0,
        roi_all=0.1, roi_taken=None, riskless_n=0, riskless_roi=None,
        n_clusters=30, clustered_se=1.0, n_backtest=32,
    )
    score.save_score(conn, "t", 1, "pooled", "all", result)

    text = state.render_state(conn, now="2026-09-10T12:00:00Z")
    assert "32 backtested" in text


# ---- a `continues` bump must not blank the orientation surface ----------
#
# The 2026-08-31 ruling flipped the default bump kind from `breaking` to
# `continues`, so a bump no longer discards evidence. These three panels
# were written when `breaking` was the default, and each counts at
# `theory_version = <current>` exactly. Under the old default that was
# right; under the new one it reports a theory's whole record as zero the
# moment anybody bumps it.
#
# Measured on the real DB, 2026-09-01, immediately after two `continues`
# bumps landed:
#
#   calibration_harvest  chain [1,2,3]      rows v1=14,473 v2=14,436 -> "rows 0"
#   insider_judgment     chain [1,2,3,4,5]  rows v2=128 v3=4,084 v4=63 -> "rows 0"
#
# and insider_judgment's `strong-moderate-no` sub-theory -- the repo's
# best-evidenced result -- disappeared from EVIDENCE entirely.

def _bump(conn, tid, n=1):
    from tools import theories
    for _ in range(n):
        theories.bump_version(conn, tid, kind="continues",
                              justification="procedure changed")


def _score(conn, tid, version, *, segment="aggregate", edge=3.5, n=90):
    from tools import db as db_mod
    with db_mod.write(conn):
        conn.execute(
            "INSERT INTO scores (theory_id, theory_version, disposition,"
            " segment, run_mode, calibration_edge_net, n, n_clusters,"
            " computed_at)"
            " VALUES (?, ?, 'all', ?, 'live', ?, ?, ?,"
            " '2026-08-30T00:00:00Z')",
            (tid, version, segment, edge, n, n),
        )


def _opportunity(conn, tid, version, ticker):
    from tools import ledger
    ledger.record_opportunity(
        conn, theory_id=tid, theory_version=version, kalshi_ticker=ticker,
        outcome="yes", entry_price=0.9, edge_pts_net=1.0, run_mode="live",
        run_id=f"live-{ticker}", edge_basis="model",
    )


def test_ledger_rows_survive_a_continues_bump_in_the_theories_panel(conn):
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    _opportunity(conn, "demo_theory", 1, "KX-1")
    _opportunity(conn, "demo_theory", 1, "KX-2")
    _bump(conn, "demo_theory")            # v1 -> v2, evidence pools
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "rows 0" not in text
    assert "rows 2" in text


def test_settled_count_survives_a_continues_bump(conn):
    from tools import score, theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    _opportunity(conn, "demo_theory", 1, "KX-1")
    score.record_settlement(conn, "KX-1", "yes",
                            resolved_at="2026-08-28T00:00:00Z")
    _bump(conn, "demo_theory")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "settled 1" in text


def test_a_breaking_bump_does_reset_the_counts(conn):
    """The complement, and the reason this cannot just count everything:
    `breaking` severs, so its predecessor's rows must NOT be pooled."""
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    _opportunity(conn, "demo_theory", 1, "KX-1")
    theories.bump_version(conn, "demo_theory", kind="breaking",
                          justification="different population entirely")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "rows 0" in text


def test_evidence_falls_back_to_the_newest_score_in_the_chain(conn):
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    theories.set_status(conn, "demo_theory", "testing")
    _score(conn, "demo_theory", 1, edge=3.5, n=90)
    _bump(conn, "demo_theory")            # v1 -> v2; no v2 score yet
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "no live score at v2" not in text
    assert "edge_net 3.5" in text
    # and it says where the number came from, rather than implying v2
    assert "scored at v1" in text


def test_evidence_prefers_the_current_versions_own_score(conn):
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    theories.set_status(conn, "demo_theory", "testing")
    _score(conn, "demo_theory", 1, edge=3.5, n=90)
    _bump(conn, "demo_theory")
    _score(conn, "demo_theory", 2, edge=-1.25, n=10)
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "edge_net -1.25" in text
    assert "scored at v1" not in text


def test_a_breaking_bump_does_not_borrow_the_predecessors_score(conn):
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    theories.set_status(conn, "demo_theory", "testing")
    _score(conn, "demo_theory", 1, edge=3.5, n=90)
    theories.bump_version(conn, "demo_theory", kind="breaking",
                          justification="severed")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "no live score at v2" in text
    assert "edge_net 3.5" not in text


def test_a_sub_theory_survives_a_continues_bump(conn):
    """The one that actually bit. insider_judgment's `strong-moderate-no`
    is the best-evidenced result in the repo, and the v5 bump made it
    vanish from the surface every session orients with."""
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    theories.set_status(conn, "demo_theory", "testing")
    _score(conn, "demo_theory", 1, segment="aggregate", edge=-1.3, n=900)
    _score(conn, "demo_theory", 1, segment="slice:proven-subset",
           edge=3.76, n=328)
    _bump(conn, "demo_theory")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "sub: proven-subset" in text
    assert "edge_net 3.76" in text


def test_freshness_reports_long_running_collections(conn, monkeypatch):
    """A stalled multi-hour collector was invisible to every orientation
    surface in the repo; it took a session running the study's own status
    subcommand by hand to find a 5.7-hour hole, twice (backfill-restart-loop)."""
    from tools import collectors

    fake = collectors.Collection(
        name="demo walk",
        db="does-not-exist.db",
        phase="prices",
        unit="series",
        command="python demo.py prices",
    )
    monkeypatch.setattr(collectors, "REGISTRY", (fake,))
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "collections:" in text
    assert "demo walk" in text


def test_a_broken_collection_read_cannot_break_orientation(conn, monkeypatch):
    """`cli state` is what every session runs first. A collector holding
    its own SQLite file must never take orientation down with it."""
    from tools import collectors

    monkeypatch.setattr(
        collectors, "statuses",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "FRESHNESS" in text
    assert "collections:" in text
