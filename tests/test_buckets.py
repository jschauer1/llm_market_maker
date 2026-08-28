import pytest

from tools import buckets, db, ledger, score, theories

TS = "2026-08-23T12:00:00Z"

PRIORS = {"strong": 4.0, "moderate": 2.0, "weak": 0.0}


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _bet(conn, ticker, entry_price, bucket, won, edge=4.0):
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker=ticker,
        outcome="yes", entry_price=entry_price, edge_pts_net=edge,
        confidence=bucket, now=TS,
    )
    score.record_settlement(conn, ticker, "yes" if won else "no")
    return opp_id


def test_unmeasured_bucket_falls_back_to_the_prior():
    edge, basis = buckets.edge_for("strong", 0.80, rates={}, priors=PRIORS)
    assert edge == pytest.approx(4.0)
    assert basis == "prior"


def test_thin_bucket_still_uses_the_prior():
    rates = {"strong": {"n": 3, "win_rate": 1.0, "mean_entry_price": 0.8}}
    edge, basis = buckets.edge_for("strong", 0.80, rates, PRIORS)
    assert basis == "prior", "3 settled results is not a measurement"
    assert edge == pytest.approx(4.0)


def test_measured_bucket_replaces_the_prior():
    # 'strong' wins 90% of the time; at a price of 0.80 that is 10 points
    # gross, minus the fee at 0.80 (1.12 points).
    rates = {"strong": {"n": 25, "win_rate": 0.90, "mean_entry_price": 0.78}}
    edge, basis = buckets.edge_for("strong", 0.80, rates, PRIORS)
    assert basis == "measured"
    assert edge == pytest.approx(10.0 - 1.12, abs=0.01)


def test_measured_bucket_can_produce_negative_edge():
    # A bucket that underperforms its prices must be able to say so.
    rates = {"strong": {"n": 25, "win_rate": 0.60, "mean_entry_price": 0.80}}
    edge, basis = buckets.edge_for("strong", 0.80, rates, PRIORS)
    assert basis == "measured"
    assert edge < 0


def test_unknown_bucket_gets_zero_edge():
    edge, basis = buckets.edge_for("wildly-confident", 0.80, {}, PRIORS)
    assert edge == pytest.approx(0.0)
    assert basis == "prior"


def test_bucket_rates_are_computed_per_bucket(conn):
    _bet(conn, "A", 0.50, "strong", won=True)
    _bet(conn, "B", 0.50, "strong", won=True)
    _bet(conn, "C", 0.50, "weak", won=False)

    rates = score.bucket_rates(conn, "t1", 1)
    assert rates["strong"]["n"] == 2
    assert rates["strong"]["win_rate"] == pytest.approx(1.0)
    assert rates["weak"]["n"] == 1
    assert rates["weak"]["win_rate"] == pytest.approx(0.0)


def test_bucket_rates_capture_mean_entry_price(conn):
    _bet(conn, "A", 0.40, "strong", won=True)
    _bet(conn, "B", 0.60, "strong", won=True)
    rates = score.bucket_rates(conn, "t1", 1)
    assert rates["strong"]["mean_entry_price"] == pytest.approx(0.50)


def test_bucket_rates_ignore_unsettled_opportunities(conn):
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="UNSETTLED",
        outcome="yes", entry_price=0.5, edge_pts_net=4.0,
        confidence="strong", now=TS,
    )
    assert score.bucket_rates(conn, "t1", 1) == {}


def test_bucket_rates_ignore_opportunities_without_a_bucket(conn):
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="NOBUCKET",
        outcome="yes", entry_price=0.5, edge_pts_net=4.0, now=TS,
    )
    score.record_settlement(conn, "NOBUCKET", "yes")
    assert score.bucket_rates(conn, "t1", 1) == {}


def test_bucket_rates_are_segmented_by_version(conn):
    _bet(conn, "A", 0.50, "strong", won=True)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=2, kalshi_ticker="B",
        outcome="yes", entry_price=0.5, edge_pts_net=4.0,
        confidence="strong", now=TS,
    )
    score.record_settlement(conn, "B", "no")

    assert score.bucket_rates(conn, "t1", 1)["strong"]["win_rate"] == \
        pytest.approx(1.0)
    assert score.bucket_rates(conn, "t1", 2)["strong"]["win_rate"] == \
        pytest.approx(0.0)


def test_bucket_rates_are_segmented_by_run_mode(conn):
    # Backtest results must not silently redefine what a live bucket means.
    _bet(conn, "A", 0.50, "strong", won=True)
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="B",
        outcome="yes", entry_price=0.5, edge_pts_net=4.0,
        confidence="strong", run_mode="backtest", run_id="bt-1", now=TS,
    )
    score.record_settlement(conn, "B", "no")

    live = score.bucket_rates(conn, "t1", 1)
    backtest = score.bucket_rates(conn, "t1", 1, run_mode="backtest")
    assert live["strong"]["n"] == 1
    assert live["strong"]["win_rate"] == pytest.approx(1.0)
    assert backtest["strong"]["n"] == 1
    assert backtest["strong"]["win_rate"] == pytest.approx(0.0)


def test_bucket_rates_can_be_scoped_to_a_single_run(conn):
    # Two backtest runs proposing the same market merge into one position
    # (position-identity dedup), so pooled still counts it once -- one
    # settlement is one draw, however many runs proposed it.
    for run in ("run-a", "run-b"):
        ledger.record_opportunity(
            conn, theory_id="t1", theory_version=1, kalshi_ticker="A",
            outcome="yes", entry_price=0.5, edge_pts_net=4.0,
            confidence="strong", run_mode="backtest", run_id=run, now=TS,
        )
    score.record_settlement(conn, "A", "yes")

    pooled = score.bucket_rates(conn, "t1", 1, run_mode="backtest")
    assert pooled["strong"]["n"] == 1

    # run-a is the surviving row's own stored run_id -- the first sighting
    # -- so scoping to it would still pass under the old `o.run_id = ?`
    # filter and prove nothing about the fix. run-b only matches through
    # the new EXISTS-against-opportunity_attempts scoping, since the merged
    # row's stored run_id never becomes "run-b".
    for run in ("run-a", "run-b"):
        scoped = score.bucket_rates(
            conn, "t1", 1, run_mode="backtest", run_id=run
        )
        assert scoped["strong"]["n"] == 1


def test_save_bucket_rates_persists_rows(conn):
    _bet(conn, "A", 0.50, "strong", won=True)
    rates = score.bucket_rates(conn, "t1", 1)
    assert score.save_bucket_rates(conn, "t1", 1, rates, now=TS) == 1

    row = conn.execute("SELECT * FROM bucket_rates").fetchone()
    assert row["confidence"] == "strong"
    assert row["n"] == 1
    assert row["computed_at"] == TS


def test_end_to_end_measurement_replaces_the_prior(conn):
    # Before any settled results, 'strong' is worth its prior.
    edge, basis = buckets.edge_for(
        "strong", 0.80, score.bucket_rates(conn, "t1", 1), PRIORS
    )
    assert basis == "prior"

    # After 12 settled 'strong' calls that won 75% of the time, the bucket
    # speaks for itself.
    for i in range(12):
        _bet(conn, f"T{i}", 0.50, "strong", won=i < 9)

    rates = score.bucket_rates(conn, "t1", 1)
    assert rates["strong"]["n"] == 12
    assert rates["strong"]["win_rate"] == pytest.approx(0.75)

    edge, basis = buckets.edge_for("strong", 0.50, rates, PRIORS)
    assert basis == "measured"
    assert edge == pytest.approx(25.0 - 1.75, abs=0.01)
