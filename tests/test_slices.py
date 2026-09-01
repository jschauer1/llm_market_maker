"""Registered slices — subset edges with their own credibility.

The mechanism under test (tools/slices.py, spec 2026-08-29-theory-
slices-design.md): a slice is a registered, mechanical sub-population
of one theory whose credibility counts only out-of-sample evidence, and
which — once past its readiness gates — partitions the theory's ranking
evidence into slice and complement. The fixtures below are the
insider_judgment shape in miniature: a strong/moderate-NO slice inside
a theory whose aggregate includes weak/YES rows.
"""

from __future__ import annotations

import json

import pytest

from tools import db, ledger, score, slices, theories


@pytest.fixture()
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    theories.register(c, "t", "T", "theories/t")
    return c


def _settled(
    c, ticker, *, outcome="no", confidence="strong", price=0.85,
    day="2026-08-27", run_id="live", run_mode="live", result=None,
    resolved="2026-09-01T00:00:00Z", extra=None,
):
    """One settled single-leg position with one attempt."""
    ledger.record_opportunity(
        c, theory_id="t", theory_version=1, kalshi_ticker=ticker,
        outcome=outcome, entry_price=price, edge_pts_net=4.0,
        edge_basis="model", run_mode=run_mode, run_id=run_id,
        decision_date=day, confidence=confidence, rationale="x",
        extra_json=json.dumps(extra) if extra else None,
    )
    score.record_settlement(
        c, ticker, result if result is not None else outcome,
        resolved_at=resolved,
    )


def _register(c, **kwargs):
    defaults = dict(
        predicate={"outcome": ["no"], "confidence": ["strong", "moderate"]},
        hypothesis="optimism tax: judged NO favorites are underpriced",
        origin="test fixture",
        registered_at="2026-08-26T00:00:00Z",
    )
    defaults.update(kwargs)
    slices.register_slice(c, "t", "strong-moderate-no", **defaults)


# --- matcher ---------------------------------------------------------------


def test_matcher_matches_on_outcome_and_confidence():
    m = slices.build_matcher(
        {"outcome": ["no"], "confidence": ["strong", "moderate"]}
    )
    assert m({"outcome": "no", "confidence": "strong"})
    assert m({"outcome": "NO", "confidence": "Moderate"}), "case-insensitive"
    assert not m({"outcome": "yes", "confidence": "strong"})
    assert not m({"outcome": "no", "confidence": "weak"})


def test_matcher_fails_a_confidence_clause_on_an_unjudged_row():
    m = slices.build_matcher({"confidence": ["strong"]})
    assert not m({"outcome": "no", "confidence": None}), (
        "the judgment the slice conditions on never happened"
    )


def test_matcher_price_band_is_inclusive():
    m = slices.build_matcher({"entry_price": {"min": 0.85, "max": 0.97}})
    assert m({"entry_price": 0.85}) and m({"entry_price": 0.97})
    assert not m({"entry_price": 0.84}) and not m({"entry_price": 0.98})


def test_matcher_extra_clause_reads_both_row_shapes():
    m = slices.build_matcher({"extra": {"rules_diverge_from_title": True}})
    assert m({"extra": {"rules_diverge_from_title": True}})
    assert m({"extra_json": '{"rules_diverge_from_title": true}'})
    assert not m({"extra": {"rules_diverge_from_title": False}})
    assert not m({"extra": {}}), "a missing feature is not a match"


def test_matcher_never_matches_a_basket():
    m = slices.build_matcher({"outcome": ["no"]})
    assert not m({"position_kind": "basket", "outcome": "no"})


def test_matcher_rejects_unknown_and_malformed_clauses():
    with pytest.raises(ValueError):
        slices.build_matcher({"side": ["no"]})
    with pytest.raises(ValueError):
        slices.build_matcher({})
    with pytest.raises(ValueError):
        slices.build_matcher({"outcome": "no"})
    with pytest.raises(ValueError):
        slices.build_matcher({"entry_price": {"lo": 0.8}})
    with pytest.raises(ValueError):
        slices.build_matcher({"extra": {}})


# --- registration ----------------------------------------------------------


def test_register_and_list(conn):
    _register(conn)
    row = slices.get_slice(conn, "t", "strong-moderate-no")
    assert row is not None and row["status"] == "registered"
    assert [r["slug"] for r in slices.list_slices(conn, "t")] == [
        "strong-moderate-no"
    ]


def test_slices_are_immutable_once_registered(conn):
    _register(conn)
    with pytest.raises(ValueError, match="immutable"):
        _register(conn, predicate={"outcome": ["yes"]})


def test_register_fails_loudly_on_missing_pieces(conn):
    with pytest.raises(ValueError):
        slices.register_slice(
            conn, "nope", "s", predicate={"outcome": ["no"]},
            hypothesis="h", origin="o",
        )
    with pytest.raises(ValueError):
        _register(conn, hypothesis="  ")
    with pytest.raises(ValueError):
        _register(conn, origin="")
    with pytest.raises(ValueError):
        _register(conn, predicate={"bad": 1})


def test_retire_requires_a_reason_and_happens_once(conn):
    _register(conn)
    with pytest.raises(ValueError):
        slices.retire_slice(conn, "t", "strong-moderate-no", reason=" ")
    slices.retire_slice(conn, "t", "strong-moderate-no", reason="superseded")
    assert slices.get_slice(conn, "t", "strong-moderate-no")["status"] == \
        "retired"
    with pytest.raises(ValueError, match="already retired"):
        slices.retire_slice(conn, "t", "strong-moderate-no", reason="again")


# --- evidence split --------------------------------------------------------


def test_oos_split_by_settlement_day_designation_and_tier(conn):
    """The core discipline: a row vouches for a slice when it is
    evidence rather than the data that suggested it — settled after
    registration, designated at registration, or replayed by a tier A/B
    backtest (ruling 2026-08-31). A live row settled on or before the
    registration day does not, and tier C vouches for nothing."""
    score.record_backtest_run(conn, "bt-oos", "t", 1, tier="B")
    score.record_backtest_run(conn, "bt-in", "t", 1, tier="B")
    score.record_backtest_run(conn, "bt-c", "t", 1, tier="C")
    _register(conn, oos_run_ids=["bt-oos"])

    # Settled after registration -> out of sample: the hypothesis could
    # not have been fit to an outcome that did not exist yet.
    _settled(conn, "KXA-1", day="2026-08-27",
             resolved="2026-09-01T00:00:00Z")
    # Settled before registration -> in sample, live or not.
    _settled(conn, "KXB-1", day="2026-08-24", confidence="moderate",
             resolved="2026-08-25T00:00:00Z")
    # Settled ON the registration day -> in sample (ambiguity resolves
    # against the slice).
    _settled(conn, "KXG-1", day="2026-08-25",
             resolved="2026-08-26T12:00:00Z")
    # Designated run -> out of sample despite historical settlement.
    _settled(conn, "KXC-1", day="2026-06-01", run_id="bt-oos",
             run_mode="backtest", resolved="2026-06-05T00:00:00Z")
    # Undesignated tier-B backtest -> out of sample. A replayed edge is
    # evidence exactly as a forward-settled one is; the tier is what
    # rules out a model recalling outcomes it was trained on.
    _settled(conn, "KXD-1", day="2026-06-02", run_id="bt-in",
             run_mode="backtest", resolved="2026-06-06T00:00:00Z")
    # Tier C -> excluded from every segment.
    _settled(conn, "KXE-1", day="2026-06-03", run_id="bt-c",
             run_mode="backtest", resolved="2026-06-07T00:00:00Z")
    # Non-matching row -> aggregate only.
    _settled(conn, "KXF-1", outcome="yes", confidence="weak",
             day="2026-08-27", resolved="2026-09-01T00:00:00Z")

    report = slices.segment_report(conn, "t")
    entry = report["slices"][0]
    assert entry["oos"]["n"] == 3, (
        "KXA (forward) + KXC (designated) + KXD (tier-B replay)"
    )
    assert entry["in_sample"]["n"] == 2, (
        "KXB (settled pre-registration) + KXG (settled ON it)"
    )
    assert report["tier_c_excluded_rows"] == 1
    assert report["aggregate"]["n"] == 6, "everything but the tier-C row"
    assert entry["ready"] is False
    assert report["complement"] is None, (
        "no ready slice -> no partition; rank on the aggregate as before"
    )


def test_an_undesignated_tier_ab_backtest_counts_as_out_of_sample(conn):
    """User ruling 2026-08-31: a backtested edge is evidence exactly as
    a forward-settled one is. A tier A/B replay no longer has to be
    hand-designated at registration to reach the credibility path."""
    score.record_backtest_run(conn, "bt-plain", "t", 1, tier="B")
    _register(conn)

    _settled(conn, "KXD-1", day="2026-06-02", run_id="bt-plain",
             run_mode="backtest", resolved="2026-06-06T00:00:00Z")

    entry = slices.segment_report(conn, "t")["slices"][0]
    assert entry["oos"]["n"] == 1
    assert entry["in_sample"]["n"] == 0


def test_the_run_a_slice_was_mined_from_never_vouches_for_it(conn):
    """The one exception the ruling keeps: a pattern found by slicing a
    run's own rows cannot cite that run as its evidence."""
    score.record_backtest_run(conn, "bt-mine", "t", 1, tier="B")
    score.record_backtest_run(conn, "bt-confirm", "t", 1, tier="B")
    _register(conn, mined_from_run_ids=["bt-mine"])

    _settled(conn, "KXM-1", day="2026-06-02", run_id="bt-mine",
             run_mode="backtest", resolved="2026-06-06T00:00:00Z")
    _settled(conn, "KXN-1", day="2026-06-03", run_id="bt-confirm",
             run_mode="backtest", resolved="2026-06-07T00:00:00Z")

    entry = slices.segment_report(conn, "t")["slices"][0]
    assert entry["oos"]["n"] == 1, "the confirming replay counts"
    assert entry["in_sample"]["n"] == 1, "the mining replay never does"


def test_a_mining_run_can_be_declared_after_registration(conn):
    """Slices registered before the 2026-08-31 ruling documented their
    mining run only in `origin` prose, because the field did not exist —
    and the old default excluded every replay anyway. Declaring it later
    restores the exclusion the registration always meant."""
    score.record_backtest_run(conn, "bt-mine", "t", 1, tier="B")
    _register(conn)
    _settled(conn, "KXM-1", day="2026-06-02", run_id="bt-mine",
             run_mode="backtest", resolved="2026-06-06T00:00:00Z")
    assert slices.segment_report(conn, "t")["slices"][0]["oos"]["n"] == 1

    slices.declare_mined_from(conn, "t", "strong-moderate-no", ["bt-mine"])

    entry = slices.segment_report(conn, "t")["slices"][0]
    assert entry["oos"]["n"] == 0
    assert entry["in_sample"]["n"] == 1


def test_a_declared_mining_run_can_never_be_withdrawn(conn):
    """The declaration only ever restricts a slice's evidence, which is
    what makes setting it after registration safe at all. Removing one
    would hand a slice back the rows that suggested it."""
    _register(conn, mined_from_run_ids=["bt-mine"])

    with pytest.raises(ValueError, match="never withdrawn"):
        slices.declare_mined_from(conn, "t", "strong-moderate-no", [])

    slices.declare_mined_from(conn, "t", "strong-moderate-no", ["bt-other"])
    row = slices.get_slice(conn, "t", "strong-moderate-no")
    assert sorted(json.loads(row["mined_from_run_ids"])) == [
        "bt-mine", "bt-other"
    ], "declaring is additive — a second call widens the exclusion"


def test_a_backtest_run_with_no_recorded_tier_does_not_vouch(conn):
    """Only a run whose tier was actually recorded as A or B counts. An
    untiered replay has unknown provenance, and unknown resolves against
    the slice exactly as an ambiguous settlement date does."""
    _register(conn)

    _settled(conn, "KXU-1", day="2026-06-02", run_id="bt-untiered",
             run_mode="backtest", resolved="2026-06-06T00:00:00Z")

    entry = slices.segment_report(conn, "t")["slices"][0]
    assert entry["oos"]["n"] == 0
    assert entry["in_sample"]["n"] == 1


def test_segment_score_discloses_how_much_evidence_is_backtested(conn):
    """The user must be told when a bet rests on replayed history rather
    than on settlements that came in forward."""
    score.record_backtest_run(conn, "bt-plain", "t", 1, tier="A")
    _register(conn)

    _settled(conn, "KXD-1", day="2026-06-02", run_id="bt-plain",
             run_mode="backtest", resolved="2026-06-06T00:00:00Z")
    _settled(conn, "KXA-1", day="2026-08-27",
             resolved="2026-09-01T00:00:00Z")

    entry = slices.segment_report(conn, "t")["slices"][0]
    assert entry["oos"]["n"] == 2
    assert entry["oos"]["n_backtest"] == 1, "one replayed, one forward"


def test_designation_reaches_a_position_first_seen_by_a_screen_run(conn):
    """The insider_judgment shape: a mechanical screen run records the
    position first (no confidence), a designated judged run labels it
    later. The position's own run_id is the screen's, so designation
    must match ANY run that proposed it — first-seer alone would file
    the whole judged campaign as in-sample."""
    score.record_backtest_run(conn, "bt-screen", "t", 1, tier="A")
    score.record_backtest_run(conn, "bt-oos", "t", 1, tier="B")
    _register(conn, oos_run_ids=["bt-oos"])

    ledger.record_opportunity(
        conn, theory_id="t", theory_version=1, kalshi_ticker="KXS-1",
        outcome="no", entry_price=0.85, edge_pts_net=4.0,
        edge_basis="model", run_mode="backtest", run_id="bt-screen",
        decision_date="2026-06-01", rationale="screen",
    )
    ledger.record_opportunity(
        conn, theory_id="t", theory_version=1, kalshi_ticker="KXS-1",
        outcome="no", entry_price=0.85, edge_pts_net=4.0,
        edge_basis="model", run_mode="backtest", run_id="bt-oos",
        decision_date="2026-06-02", confidence="strong",
        rationale="judged",
    )
    score.record_settlement(conn, "KXS-1", "no",
                            resolved_at="2026-06-05T00:00:00Z")

    entry = slices.segment_report(conn, "t")["slices"][0]
    assert entry["oos"]["n"] == 1, (
        "the judged run's designation carries the position, whichever "
        "run saw it first"
    )
    assert entry["in_sample"]["n"] == 0


def _ready_fixture(conn, *, tickers=None, days=6):
    """Twelve forward slice wins across distinct events and days, plus
    two non-matching rows."""
    _register(conn)
    tickers = tickers or [f"KXR{i}-X" for i in range(12)]
    for i, ticker in enumerate(tickers):
        _settled(
            conn, ticker, day="2026-08-27",
            resolved=f"2026-09-{(i % days) + 1:02d}T00:00:00Z",
        )
    _settled(conn, "KXY-1", outcome="yes", confidence="weak",
             day="2026-08-27")
    _settled(conn, "KXY-2", outcome="yes", confidence="weak",
             day="2026-08-27")


def test_ready_slice_partitions_ranking_into_slice_and_complement(conn):
    _ready_fixture(conn)
    report = slices.segment_report(conn, "t")
    entry = report["slices"][0]
    assert entry["oos"]["n_clusters"] == 12
    assert entry["oos"]["n_days"] == 6
    assert entry["oos"]["day_clustered_se"] is not None, (
        "a segment must be readable at the day level"
    )
    assert entry["ready"] is True
    assert report["complement"]["n"] == 2, "the weak-YES remainder"

    in_slice = {"theory_id": "t", "theory_version": 1, "outcome": "no",
                "confidence": "strong", "entry_price": 0.85}
    picked = slices.ranking_segment(conn, in_slice, report=report)
    assert picked["segment"] == "slice:strong-moderate-no"
    assert picked["rank_inputs"]["n"] == 12, "clusters, not rows"

    remainder = dict(in_slice, confidence="weak", outcome="yes")
    picked = slices.ranking_segment(conn, remainder, report=report)
    assert picked["segment"] == "complement"
    assert picked["score"]["n"] == 2


def test_one_event_cannot_clear_the_cluster_gate(conn):
    _ready_fixture(conn, tickers=[f"KXONE-{i}" for i in range(12)])
    entry = slices.segment_report(conn, "t")["slices"][0]
    assert entry["oos"]["n"] == 12 and entry["oos"]["n_clusters"] == 1
    assert entry["ready"] is False, (
        "twelve siblings of one event have watched one event resolve"
    )


def test_one_settlement_day_cannot_clear_the_day_gate(conn):
    _ready_fixture(conn, days=1)
    entry = slices.segment_report(conn, "t")["slices"][0]
    assert entry["oos"]["n_days"] == 1
    assert entry["oos"]["day_clustered_se"] is None, (
        "one day carries no information about between-day spread"
    )
    assert entry["ready"] is False, "one hot night must not define a slice"


def test_unready_slice_changes_nothing_but_is_annotated(conn):
    _register(conn)
    _settled(conn, "KXA-1", day="2026-08-27")
    report = slices.segment_report(conn, "t")
    row = {"theory_id": "t", "theory_version": 1, "outcome": "no",
           "confidence": "strong", "entry_price": 0.85}
    picked = slices.ranking_segment(conn, row, report=report)
    assert picked["segment"] == "aggregate"
    assert picked["matched_slice"] == "strong-moderate-no"
    assert picked["matched_slice_ready"] is False
    assert "below its evidence gates" in picked["note"]


def test_retiring_a_slice_cannot_hide_its_record(conn):
    _ready_fixture(conn)
    slices.retire_slice(conn, "t", "strong-moderate-no",
                        reason="superseded by test")
    report = slices.segment_report(conn, "t")
    entry = report["slices"][0]
    assert entry["status"] == "retired"
    assert entry["oos"]["n"] == 12, "the evidence still reports"
    assert entry["ready"] is False, "but it no longer drives ranking"
    assert report["complement"] is None

    row = {"theory_id": "t", "theory_version": 1, "outcome": "no",
           "confidence": "strong", "entry_price": 0.85}
    picked = slices.ranking_segment(conn, row, report=report)
    assert picked["segment"] == "aggregate"
    assert picked["retired_matches"] == ["strong-moderate-no"]


def test_priority_breaks_overlapping_slice_ties(conn):
    _register(conn)  # priority 0
    slices.register_slice(
        conn, "t", "strong-no-only",
        predicate={"outcome": ["no"], "confidence": ["strong"]},
        hypothesis="the sharper cell", origin="test fixture",
        registered_at="2026-08-26T00:00:00Z", priority=1,
    )
    ordered = [r["slug"] for r in slices.list_slices(conn, "t")]
    assert ordered == ["strong-no-only", "strong-moderate-no"], (
        "higher priority is consulted first"
    )


def test_slice_scores_agree_with_compute_score_on_the_same_rows(conn):
    """A slice's segments are compute_score on a partition — same
    identity, decision, and cluster semantics, because same rows."""
    _ready_fixture(conn)
    report = slices.segment_report(conn, "t")
    whole = score.compute_score(conn, "t", 1, "live", "all")
    assert report["aggregate"]["n"] == whole["n"]
    assert report["aggregate"]["calibration_edge_net"] == pytest.approx(
        whole["calibration_edge_net"]
    )
    entry = report["slices"][0]
    assert entry["oos"]["n"] + entry["in_sample"]["n"] + \
        report["complement"]["n"] == whole["n"]
