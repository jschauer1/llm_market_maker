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
    # 'strong' won 90% of markets bought at a mean of 0.78, i.e. it beat
    # its own prices by 12 points gross -- minus the fee at this
    # candidate's price of 0.80 (1.12 points). Until 2026-08-29 this read
    # `10.0 - 1.12`, differencing the bucket rate against the CANDIDATE's
    # price rather than the bucket's own; see tools/buckets.py.
    rates = {"strong": {"n": 25, "win_rate": 0.90,
                        "mean_entry_price": 0.78, "n_days": 9}}
    edge, basis = buckets.edge_for("strong", 0.80, rates, PRIORS)
    assert basis == "measured"
    assert edge == pytest.approx(12.0 - 1.12, abs=0.01)


def test_measured_bucket_can_produce_negative_edge():
    # A bucket that underperforms its prices must be able to say so.
    rates = {"strong": {"n": 25, "win_rate": 0.60,
                        "mean_entry_price": 0.80, "n_days": 9}}
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
        decision_date=TS[:10],
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
            decision_date=TS[:10],
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

    # After 12 settled 'strong' calls that won 75% of the time -- spread
    # over 12 distinct settlement days, since one night of results is not
    # a measurement however many rows it holds -- the bucket speaks for
    # itself.
    for i in range(12):
        _bet(conn, f"T{i}", 0.50, "strong", won=i < 9)
        score.record_settlement(conn, f"T{i}", "yes" if i < 9 else "no",
                                resolved_at=f"2026-08-{i + 1:02d}T12:00:00Z")

    rates = score.bucket_rates(conn, "t1", 1)
    assert rates["strong"]["n"] == 12
    assert rates["strong"]["win_rate"] == pytest.approx(0.75)
    assert rates["strong"]["n_days"] == 12

    # The bucket bought at 0.50 and won 75%: 25 points of realized edge,
    # which is what a new candidate inherits, minus its own fee.
    edge, basis = buckets.edge_for("strong", 0.50, rates, PRIORS)
    assert basis == "measured"
    assert edge == pytest.approx(25.0 - 1.75, abs=0.01)

    # ... and the same 25 points at a different price, not 25 points
    # rescaled by that price. Only the fee moves.
    dear, _ = buckets.edge_for("strong", 0.90, rates, PRIORS)
    assert dear == pytest.approx(25.0 - 0.63, abs=0.01)


# --- the bucket contributes an EDGE, not a probability (2026-08-29) -------
#
# Diagnosed live on two consecutive insider_judgment runs. The old formula
# was `(bucket_win_rate - this candidate's price)`, which treats the
# bucket's pooled win rate as this candidate's probability and therefore
# varies 1:1 with price -- a constant, not a calibration. It claimed edge
# on everything cheaper than the bucket rate and negative edge on
# everything dearer, regardless of the thesis. It also disagreed with how
# `score.compute_score` GRADES the same theory (win_rate minus the prices
# actually paid) and with the prior path, which already returns points of
# edge. All three now agree.

MEASURED = {"n": 25, "win_rate": 0.90, "mean_entry_price": 0.78, "n_days": 9}


def test_measured_edge_is_the_buckets_realized_edge_not_a_reprice():
    # The bucket beat the prices it was actually bought at by 12 points
    # (0.90 vs 0.78). That is what transfers to a new candidate -- minus
    # the fee at the new candidate's own price, which does depend on it.
    edge, basis = buckets.edge_for("strong", 0.80, {"strong": MEASURED},
                                   PRIORS)
    assert basis == "measured"
    assert edge == pytest.approx(12.0 - 1.12, abs=0.01)


def test_measured_edge_does_not_move_one_for_one_with_price():
    cheap, _ = buckets.edge_for("strong", 0.50, {"strong": MEASURED}, PRIORS)
    dear, _ = buckets.edge_for("strong", 0.95, {"strong": MEASURED}, PRIORS)
    # Only the fee differs; the claimed gross edge is the same 12 points.
    assert cheap == pytest.approx(12.0 - 1.75, abs=0.01)
    assert dear == pytest.approx(12.0 - 0.3325, abs=0.01)


def test_a_bucket_that_lost_money_claims_negative_edge_at_every_price():
    # insider_judgment's live `weak` bucket as of 2026-08-29: it won 77.6%
    # of markets bought at a mean of 0.845, i.e. it LOST 6.9 points. The
    # old formula called that +4.2 points on a 0.72 candidate.
    lost = {"n": 67, "win_rate": 0.7761, "mean_entry_price": 0.8446,
            "n_days": 9}
    for price in (0.66, 0.72, 0.85, 0.96):
        edge, basis = buckets.edge_for("weak", price, {"weak": lost}, PRIORS)
        assert basis == "measured"
        assert edge < 0, f"a losing bucket claimed positive edge at {price}"


def test_a_bucket_measured_on_too_few_settlement_days_stays_a_prior():
    # Settlement-day clustering, not row count, is what a bucket rate has
    # to survive: one lucky night graduated insider_judgment's `weak`
    # bucket on 17 rows that all settled 2026-08-27.
    one_night = {"n": 67, "win_rate": 0.94, "mean_entry_price": 0.81,
                 "n_days": 1}
    edge, basis = buckets.edge_for("strong", 0.80, {"strong": one_night},
                                   PRIORS)
    assert basis == "prior"
    assert edge == pytest.approx(4.0)


def test_a_rates_dict_missing_its_day_count_fails_closed_to_the_prior():
    no_days = {"n": 67, "win_rate": 0.90, "mean_entry_price": 0.78}
    _, basis = buckets.edge_for("strong", 0.80, {"strong": no_days}, PRIORS)
    assert basis == "prior", "an unverifiable measurement is not a measurement"


def test_a_rates_dict_missing_its_mean_price_fails_closed_to_the_prior():
    no_price = {"n": 67, "win_rate": 0.90, "n_days": 9}
    _, basis = buckets.edge_for("strong", 0.80, {"strong": no_price}, PRIORS)
    assert basis == "prior"


def test_bucket_rates_report_distinct_settlement_days(conn):
    _bet(conn, "A", 0.50, "strong", won=True)
    score.record_settlement(conn, "A", "yes", resolved_at="2026-08-27T23:59:00Z")
    _bet(conn, "B", 0.50, "strong", won=True)
    score.record_settlement(conn, "B", "yes", resolved_at="2026-08-27T20:00:00Z")
    _bet(conn, "C", 0.50, "strong", won=False)
    score.record_settlement(conn, "C", "no", resolved_at="2026-08-28T03:59:00Z")

    rates = score.bucket_rates(conn, "t1", 1)
    assert rates["strong"]["n"] == 3
    assert rates["strong"]["n_days"] == 2


def test_bucket_rates_day_count_is_none_when_no_row_carries_a_date(conn):
    # Older backtest rows settled without a resolved_at; an unknown day
    # count must read as unknown, and edge_for fails closed on it.
    _bet(conn, "A", 0.50, "strong", won=True)
    rates = score.bucket_rates(conn, "t1", 1)
    assert rates["strong"]["n_days"] is None


def test_edge_from_bucket_carries_gross_fee_and_this_candidates_probability():
    from tools.domain import Edge
    edge = Edge.from_bucket("strong", 0.80, {"strong": MEASURED}, PRIORS)
    assert edge.basis == "measured"
    assert edge.pts_gross == pytest.approx(12.0)
    assert edge.fee_pts == pytest.approx(1.12, abs=0.01)
    # The implied probability for THIS candidate is its own price plus the
    # bucket's edge -- not the bucket's pooled win rate, which describes a
    # different set of prices.
    assert edge.model_prob == pytest.approx(0.92)


def test_saved_bucket_rates_carry_the_day_count(conn):
    _bet(conn, "A", 0.50, "strong", won=True)
    score.record_settlement(conn, "A", "yes", resolved_at="2026-08-27T12:00:00Z")
    _bet(conn, "B", 0.50, "strong", won=True)
    score.record_settlement(conn, "B", "yes", resolved_at="2026-08-28T12:00:00Z")

    rates = score.bucket_rates(conn, "t1", 1)
    score.save_bucket_rates(conn, "t1", 1, rates, now=TS)
    row = conn.execute(
        "SELECT n, n_days FROM bucket_rates WHERE confidence = 'strong'"
    ).fetchone()
    assert (row["n"], row["n_days"]) == (2, 2)
