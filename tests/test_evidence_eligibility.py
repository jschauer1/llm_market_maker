"""Production evidence admits live outcomes and documented tier A/B replays.

These tests use the private in-memory database fixture.  They deliberately run
the same rows through scoring, bucket pricing, and registered-slice evaluation
so one consumer cannot quietly drift from the others again.
"""

from __future__ import annotations

import pytest

from tools import buckets, ledger, score, slices, theories


@pytest.fixture
def conn(conn):
    theories.register(conn, "t", "T", "theories/t")
    return conn


def _settled(
    conn,
    ticker: str,
    *,
    run_mode: str = "live",
    run_id: str = "live",
    day: str = "2026-08-01",
    won: bool = True,
    version: int = 1,
) -> None:
    ledger.record_opportunity(
        conn,
        theory_id="t",
        theory_version=version,
        kalshi_ticker=ticker,
        outcome="yes",
        entry_price=0.50,
        edge_pts_net=10.0,
        edge_basis="model",
        confidence="strong",
        run_mode=run_mode,
        run_id=run_id,
        decision_date=day,
        now="2026-09-04T00:00:00Z",
    )
    score.record_settlement(
        conn,
        ticker,
        "yes" if won else "no",
        resolved_at=f"{day}T12:00:00Z",
    )


def _backtest(conn, run_id: str, tier: str | None) -> None:
    score.record_backtest_run(conn, run_id, "t", 1, tier=tier)


def test_production_score_excludes_each_undocumented_or_contaminated_replay(conn):
    """Removing any exclusion branch would let its losing replay dilute 100%."""
    _backtest(conn, "bt-a", "A")
    _backtest(conn, "bt-b", "B")
    _backtest(conn, "bt-c", "C")
    _backtest(conn, "bt-null", None)

    _settled(conn, "LIVE-1")
    _settled(conn, "A-1", run_mode="backtest", run_id="bt-a")
    _settled(conn, "B-1", run_mode="backtest", run_id="bt-b")
    _settled(conn, "C-1", run_mode="backtest", run_id="bt-c", won=False)
    _settled(conn, "NULL-1", run_mode="backtest", run_id="bt-null", won=False)
    _settled(conn, "MISSING-1", run_mode="backtest", run_id="bt-missing", won=False)

    result = score.compute_score(conn, "t", 1, ("live", "backtest"))
    days = score.settlement_day_clusters(conn, "t", 1, "backtest")

    assert result["n"] == 3
    assert result["win_rate"] == pytest.approx(1.0)
    assert result["n_backtest"] == 2
    assert result["evidence_exclusions"] == {
        "total": 3,
        "tier_c": 1,
        "missing_tier": 1,
        "unregistered_run": 1,
    }
    assert days["n"] == 2
    assert days["evidence_exclusions"]["total"] == 3


def test_selector_retains_excluded_rows_and_reasons_for_diagnostics(conn):
    """Deleting diagnostic rows would make an exclusion impossible to audit."""
    from tools import evidence

    _backtest(conn, "bt-a", "A")
    _backtest(conn, "bt-c", "C")
    _backtest(conn, "bt-null", None)
    _settled(conn, "A-1", run_mode="backtest", run_id="bt-a")
    _settled(conn, "C-1", run_mode="backtest", run_id="bt-c")
    _settled(conn, "NULL-1", run_mode="backtest", run_id="bt-null")
    _settled(conn, "MISSING-1", run_mode="backtest", run_id="bt-missing")

    raw = score.observations(conn, "t", 1, "backtest")
    for row in raw:
        row["run_mode"] = "backtest"
    selected = evidence.select_eligible(conn, raw)

    assert [row["kalshi_ticker"] for row in selected.eligible] == ["A-1"]
    assert {
        item.row["kalshi_ticker"]: item.reasons for item in selected.excluded
    } == {
        "C-1": ("tier_c",),
        "NULL-1": ("missing_tier",),
        "MISSING-1": ("unregistered_run",),
    }


def test_mismatched_tier_c_registration_reports_both_reasons(conn):
    """A scope mismatch must not hide the legacy count of tier-C exclusions."""
    theories.register(conn, "other", "Other", "theories/other")
    score.record_backtest_run(conn, "wrong-c", "other", 1, tier="C")
    _settled(conn, "WRONG-C", run_mode="backtest", run_id="wrong-c")

    report = slices.segment_report(conn, "t", 1)
    assert report["aggregate"]["n"] == 0
    assert report["evidence_exclusions"] == {
        "total": 1, "tier_c": 1, "mismatched_registration": 1,
    }
    assert report["tier_c_excluded_rows"] == 1


def test_valid_ab_replays_alone_measure_buckets_and_clear_slice_gates(conn):
    """Filtering all replays would leave A/B-only theories stuck on priors."""
    _backtest(conn, "bt-a", "A")
    _backtest(conn, "bt-b", "B")
    _backtest(conn, "bt-c", "C")
    _backtest(conn, "bt-null", None)
    slices.register_slice(
        conn,
        "t",
        "strong-yes",
        predicate={"outcome": ["yes"], "confidence": ["strong"]},
        hypothesis="documented fixture",
        origin="test",
        registered_at="2026-09-01T00:00:00Z",
    )

    for index in range(10):
        _settled(
            conn,
            f"VALID{index}-X",
            run_mode="backtest",
            run_id="bt-a" if index % 2 == 0 else "bt-b",
            day=f"2026-08-{(index % 5) + 1:02d}",
        )
    _settled(
        conn, "BAD-C-X", run_mode="backtest", run_id="bt-c",
        day="2026-08-06", won=False,
    )
    _settled(
        conn, "BAD-NULL-X", run_mode="backtest", run_id="bt-null",
        day="2026-08-07", won=False,
    )
    _settled(
        conn, "BAD-MISSING-X", run_mode="backtest", run_id="bt-missing",
        day="2026-08-08", won=False,
    )

    scored = score.compute_score(conn, "t", 1, "backtest")
    rates = score.bucket_rates(conn, "t", 1, "backtest")
    edge, basis = buckets.edge_for("strong", 0.50, rates, {"strong": 1.0})
    report = slices.segment_report(conn, "t", run_modes=("backtest",))

    assert scored["n"] == 10
    assert scored["n_clusters"] == 10
    assert rates["strong"] == {
        "n": 10,
        "win_rate": 1.0,
        "mean_entry_price": 0.5,
        "n_days": 5,
    }
    assert basis == "measured"
    assert edge > 0
    assert report["aggregate"]["n"] == 10
    assert report["evidence_exclusions"]["total"] == 3
    assert report["slices"][0]["oos"]["n"] == 10
    assert report["slices"][0]["ready"] is True


def test_all_touching_backtest_runs_must_be_eligible(conn):
    """A later C touch can supply roll-up fields, so an A touch cannot cleanse it."""
    _backtest(conn, "bt-a", "A")
    _backtest(conn, "bt-b", "B")
    _backtest(conn, "bt-c", "C")

    _settled(conn, "AB-X", run_mode="backtest", run_id="bt-a")
    _settled(conn, "AB-X", run_mode="backtest", run_id="bt-b",
             day="2026-08-02")
    _settled(conn, "AC-X", run_mode="backtest", run_id="bt-a")
    _settled(conn, "AC-X", run_mode="backtest", run_id="bt-c",
             day="2026-08-02")

    result = score.compute_score(conn, "t", 1, "backtest")
    assert result["n"] == 1
    assert result["evidence_exclusions"]["total"] == 1
    assert result["evidence_exclusions"]["tier_c"] == 1


def test_registration_must_match_the_observations_theory_and_version(conn):
    """A valid tier attached to a different track record proves nothing here."""
    theories.register(conn, "other", "Other", "theories/other")
    score.record_backtest_run(conn, "bt-other", "other", 1, tier="A")
    score.record_backtest_run(conn, "bt-v1", "t", 1, tier="B")

    _settled(conn, "WRONG-THEORY-X", run_mode="backtest", run_id="bt-other")
    ledger.record_opportunity(
        conn,
        theory_id="t",
        theory_version=2,
        kalshi_ticker="WRONG-VERSION-X",
        outcome="yes",
        entry_price=0.50,
        edge_pts_net=10.0,
        edge_basis="model",
        confidence="strong",
        run_mode="backtest",
        run_id="bt-v1",
        decision_date="2026-08-01",
    )
    score.record_settlement(
        conn, "WRONG-VERSION-X", "yes", resolved_at="2026-08-01T12:00:00Z"
    )

    wrong_theory = score.compute_score(conn, "t", 1, "backtest")
    wrong_version = score.compute_score(conn, "t", 2, "backtest")

    assert wrong_theory["n"] == 0
    assert wrong_theory["evidence_exclusions"] == {
        "total": 1,
        "mismatched_registration": 1,
    }
    assert wrong_version["n"] == 0
    assert wrong_version["evidence_exclusions"] == {
        "total": 1,
        "mismatched_registration": 1,
    }


def test_baskets_follow_the_same_backtest_eligibility_rule(conn):
    """Leaving baskets unclassified would create a second scoring policy."""
    _backtest(conn, "bt-a", "A")
    _backtest(conn, "bt-c", "C")

    for suffix, run_id in (("GOOD", "bt-a"), ("BAD", "bt-c")):
        ledger.record_basket(
            conn,
            theory_id="t",
            theory_version=1,
            legs=[
                {
                    "kalshi_ticker": f"{suffix}-1",
                    "outcome": "yes",
                    "entry_price": 0.40,
                },
                {
                    "kalshi_ticker": f"{suffix}-2",
                    "outcome": "yes",
                    "entry_price": 0.40,
                },
            ],
            edge_pts_net=10.0,
            max_payout=2.0,
            edge_basis="model",
            run_mode="backtest",
            run_id=run_id,
            decision_date="2026-08-01",
        )
        score.record_settlement(conn, f"{suffix}-1", "yes")
        score.record_settlement(conn, f"{suffix}-2", "yes")

    result = score.compute_score(conn, "t", 1, "backtest")
    assert result["n"] == 1
    assert result["evidence_exclusions"] == {"total": 1, "tier_c": 1}


def test_day_clusters_pool_the_same_mode_tuple_as_the_score(conn):
    """A backtest-only record must contribute days to a pooled report."""
    _backtest(conn, "bt-a", "A")
    _backtest(conn, "bt-c", "C")
    _settled(conn, "LIVE-X", day="2026-08-01")
    _settled(
        conn, "VALID-X", run_mode="backtest", run_id="bt-a",
        day="2026-08-02",
    )
    _settled(
        conn, "INVALID-X", run_mode="backtest", run_id="bt-c",
        day="2026-08-03",
    )

    result = score.settlement_day_clusters(
        conn, "t", 1, ("live", "backtest")
    )

    assert result["n"] == 2
    assert result["n_days"] == 2
    assert result["n_backtest"] == 1
    assert result["evidence_exclusions"] == {"total": 1, "tier_c": 1}


def test_eligible_backtests_preserve_chains_and_explicit_experiment_scoring(conn):
    """Filtering must not sever carried A/B evidence or hide a scoped experiment."""
    _backtest(conn, "bt-v1", "A")
    _settled(conn, "V1-X", run_mode="backtest", run_id="bt-v1", version=1)
    theories.bump_version(
        conn,
        "t",
        kind="continues",
        justification="procedure changed; evidence still applies",
    )
    score.record_backtest_run(conn, "bt-v2", "t", 2, tier="B")
    _settled(
        conn, "V2-X", run_mode="backtest", run_id="bt-v2", version=2,
        day="2026-08-02",
    )
    score.record_backtest_run(conn, "exp/variant", "t", 2, tier="A")
    _settled(
        conn, "EXP-X", run_mode="backtest", run_id="exp/variant", version=2,
        day="2026-08-03",
    )

    chained = score.compute_score(conn, "t", 2, "backtest", pool="chain")
    experiment = score.compute_score(
        conn, "t", 2, "backtest", run_id="exp/variant",
    )

    assert chained["n"] == 2
    assert chained["chain_versions"] == [1, 2]
    assert experiment["n"] == 1
