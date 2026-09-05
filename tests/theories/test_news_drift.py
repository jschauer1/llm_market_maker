from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

import theories.news_drift as news_drift_package
from theories.news_drift.signal import MoveSignal, detect
from theories.news_drift.theory import NewsDriftTheory
from tools.domain import Market
from tools.sizing import fee_pts
from tools.theory import TheoryContext


DAY = 86_400
ENTRY_TS = int(datetime(2026, 9, 5, tzinfo=timezone.utc).timestamp())
NOW = datetime.fromtimestamp(ENTRY_TS, tz=timezone.utc)


def candles(
    mids=(0.20, 0.22, 0.30, 0.50, 0.55),
    volumes=(10.0, 20.0, 30.0, 40.0, 5.0),
    *,
    spread=0.02,
    open_interest=200.0,
):
    start = ENTRY_TS - 4 * DAY
    return [
        {
            "end_ts": start + i * DAY,
            "yes_bid_close": mid - spread / 2,
            "yes_ask_close": mid + spread / 2,
            "volume": volumes[i],
            "open_interest": open_interest,
        }
        for i, mid in enumerate(mids)
    ]


def market(ticker="KXND-26JUL31-A", **updates):
    base = dict(
        platform="kalshi",
        ticker=ticker,
        title="Will the event occur?",
        yes_bid=0.54,
        yes_ask=0.56,
        no_bid=0.44,
        no_ask=0.46,
        mid=0.55,
        spread=0.02,
        volume=1000.0,
        volume_24h=25.0,
        open_interest=200.0,
        status="active",
        is_open=True,
        event_ticker="KXND-26JUL31",
        series_ticker="KXND",
        event={"category": "Politics"},
    )
    base.update(updates)
    return Market(**base)


def artifact(**updates):
    base = {
        "protocol": "ND-1",
        "approved": True,
        "eligible_for_production": True,
        "training_end": "2026-08-01T00:00:00+00:00",
        "residual": 0.05,
        "n": 30,
        "event_clusters": 10,
        "source_digest": "sha256:fixture",
        "population_categories": [
            "Politics", "Elections", "Economics", "Entertainment", "World"
        ],
        "validation_evidence": {
            "event_clusters": 30,
            "settlement_days": 10,
            "event_ci_low": 0.01,
            "day_ci_low": 0.01,
            "population_complete": True,
            "pending_n": 0,
            "validation_end": "2026-08-18T00:00:00+00:00",
            "source_digest": "sha256:validation-fixture",
            "run_id": "backtest/nd1-validation",
        },
    }
    base.update(updates)
    return base


def validation_artifact(tmp_path, *, run_id="nd1-clean/holdout",
                        eligible_for_production=False):
    protocol = tmp_path / "PROTOCOL.md"
    protocol.write_text("frozen clean validation", encoding="utf-8")
    protocol_digest = hashlib.sha256(protocol.read_bytes()).hexdigest()
    source_digest = "c" * 64
    series = ["KXND"]
    manifest = {
        "run_id": run_id,
        "source_digest": source_digest,
        "protocol_digest": protocol_digest,
        "population_series": series,
        "training_end": "2026-05-01T00:00:00+00:00",
        "validation_start": "2026-05-01T00:00:00+00:00",
        "validation_end": "2026-09-01T00:00:00+00:00",
        "population_complete": True,
        "confirmation_excluded_events": [],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    membership = [
        {
            "ticker": f"KXND-VALID-{i}",
            "side": "yes",
            "entry_ts": int(datetime(2026, 5, 1 + i % 20,
                                     tzinfo=timezone.utc).timestamp()),
            "event_ticker": f"EVENT-{i}",
        }
        for i in range(40)
    ]
    membership_path = tmp_path / "validation_membership.json"
    membership_path.write_text(json.dumps(membership), encoding="utf-8")
    return {
        "protocol": "ND-1",
        "approved": True,
        "eligible_for_production": eligible_for_production,
        "training_end": manifest["training_end"],
        "residual": 0.05,
        "n": 30,
        "event_clusters": 10,
        "source_digest": source_digest,
        "population_series": series,
        "validation_plan": {
            "run_id": run_id,
            "start": manifest["validation_start"],
            "end": manifest["validation_end"],
            "source_digest": source_digest,
            "protocol_digest": protocol_digest,
            "population_series": series,
            "usable_for_validation": True,
            "population_complete": True,
            "protocol_path": protocol.name,
            "manifest_path": manifest_path.name,
            "manifest_digest": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "membership_path": membership_path.name,
            "membership_digest": hashlib.sha256(
                membership_path.read_bytes()
            ).hexdigest(),
        },
    }


def set_confirmation_exclusions(calibration, tmp_path, events):
    manifest_path = tmp_path / calibration["validation_plan"]["manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["confirmation_excluded_events"] = list(events)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    calibration["validation_plan"]["manifest_digest"] = hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()


def record_validation_rows(conn, calibration, *, count=40):
    from tools import ledger, score

    plan = calibration["validation_plan"]
    for i in range(count):
        decision = datetime(2026, 5, 1 + i % 20, tzinfo=timezone.utc)
        ticker = f"KXND-VALID-{i}"
        price = 0.40
        model_prob = 0.60
        fee = fee_pts(price)
        extra = {
            "protocol": "ND-1",
            "series_ticker": "KXND",
            "event_ticker": f"EVENT-{i}",
            "entry_ts": int(decision.timestamp()),
            "current_directional_mid": 0.55,
            "calibration_source_digest": calibration["source_digest"],
            "calibration_residual": calibration["residual"],
            "calibration_status": "usable_validation",
        }
        ledger.record_opportunity(
            conn, theory_id="news_drift", theory_version=1,
            kalshi_ticker=ticker, outcome="yes", entry_price=price,
            model_prob=model_prob, edge_pts_gross=20.0, fee_pts=fee,
            edge_pts_net=20.0 - fee, edge_basis="model",
            run_mode="backtest", run_id=plan["run_id"],
            decision_date=decision.date().isoformat(),
            extra_json=json.dumps(extra),
        )
        score.record_settlement(
            conn, ticker, "yes",
            resolved_at=datetime(2026, 6, 1 + i % 10,
                                 tzinfo=timezone.utc).isoformat(),
        )


def ctx(board, *, now=NOW, run_mode="backtest", run_id="exp/nd-fixture"):
    return TheoryContext(
        conn=None,
        board=list(board),
        now=now,
        run_mode=run_mode,
        run_id=run_id,
    )


def screened(theory, context):
    result = theory.screen(context)
    assert len(result.candidates) == 1
    return result.candidates[0]


# ---- pure signal -------------------------------------------------------


def test_detects_a_continuation_entry_at_the_yes_ask():
    signal = detect(candles(), ENTRY_TS)

    assert isinstance(signal, MoveSignal)
    assert signal.side == "yes"
    assert signal.signal_ts == ENTRY_TS - DAY
    assert signal.entry_ts == ENTRY_TS
    assert signal.move == pytest.approx(0.20)
    assert signal.directional_mid == pytest.approx(0.55)
    assert signal.entry_price == pytest.approx(0.56)
    assert signal.prior_volume_median == pytest.approx(20.0)


def test_detects_a_down_move_and_buys_no_at_one_minus_yes_bid():
    rows = candles(mids=(0.78, 0.75, 0.70, 0.50, 0.45))
    signal = detect(rows, ENTRY_TS)

    assert signal.side == "no"
    assert signal.move == pytest.approx(-0.20)
    assert signal.directional_mid == pytest.approx(0.55)
    assert signal.entry_price == pytest.approx(0.56)


@pytest.mark.parametrize(
    "rows",
    [
        candles(mids=(0.20, 0.22, 0.30, 0.44, 0.45)),
        candles(volumes=(10.0, 20.0, 30.0, 20.0, 5.0)),
        candles(mids=(0.20, 0.22, 0.30, 0.90, 0.80)),
        candles(mids=(0.20, 0.22, 0.30, 0.50, 0.90)),
    ],
    ids=["move-under-15pts", "signal-volume-not-above-median",
         "signal-terminal", "entry-terminal"],
)
def test_noise_and_out_of_population_moves_do_not_signal(rows):
    assert detect(rows, ENTRY_TS) is None


def test_a_timing_gap_is_not_interpolated():
    rows = candles()
    rows[2] = {**rows[2], "end_ts": rows[2]["end_ts"] - 1}
    assert detect(rows, ENTRY_TS) is None


def test_future_candles_are_excluded_before_validation():
    future = {
        "end_ts": ENTRY_TS + DAY,
        "yes_bid_close": 2.0,
        "yes_ask_close": -1.0,
        "volume": -1.0,
        "open_interest": 0.0,
    }
    signal = detect(candles() + [future], ENTRY_TS)
    assert signal is not None
    assert signal.entry_ts == ENTRY_TS


def test_an_entry_one_full_day_old_is_stale():
    assert detect(candles(), ENTRY_TS + DAY) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("yes_bid_close", float("nan")),
        ("yes_ask_close", 1.01),
        ("volume", -1.0),
    ],
)
def test_all_five_candles_must_have_valid_quotes_and_volume(field, value):
    rows = candles()
    rows[0] = {**rows[0], field: value}
    assert detect(rows, ENTRY_TS) is None


# ---- theory screen -----------------------------------------------------


def test_screen_reports_category_and_missing_history_coverage():
    good = market()
    missing = market("KXND-26JUL31-B")
    sports = market("KXND-26JUL31-C", event={"category": "Sports"})
    unknown = market("KXND-26JUL31-D", event={})
    closed = market("KXND-26JUL31-E", is_open=False)

    def loader(m, now):
        assert now == NOW
        return None if m.ticker == missing.ticker else candles()

    theory = NewsDriftTheory(history_loader=loader, calibration=artifact())
    result = theory.screen(ctx([good, missing, sports, unknown, closed]))

    assert [c.ticker for c in result.candidates] == [good.ticker]
    assert result.funnel["board"] == 5
    assert result.funnel["eligible_category"] == 3
    assert result.funnel["missing_history_coverage"] == 1
    assert result.gate_removed == {
        "category:Sports": 1,
        "category:unknown": 1,
        "not_open": 1,
        "missing_history_coverage": 1,
    }


def test_replay_uses_the_point_in_time_candle_ask_and_ignores_close_fields():
    historical = market(status="closed", result="yes", close_time="2026-07-30T00:00:00Z")
    theory = NewsDriftTheory(history_loader=lambda m, now: candles(),
                             calibration=artifact())
    candidate = screened(theory, ctx([historical]))

    assert candidate.entry_price == pytest.approx(0.56)
    features = candidate.legs[0].market.raw["_news_drift"]
    assert features["entry_source"] == "daily_candle"
    assert features["deadline_unknown"] is True
    assert features["signal_ts"] == ENTRY_TS - DAY
    assert features["entry_ts"] == ENTRY_TS


def test_live_uses_fresh_payable_quote_and_records_daily_deviation():
    live = market(yes_bid=0.56, yes_ask=0.58, no_bid=0.42, no_ask=0.44,
                  mid=0.57)
    theory = NewsDriftTheory(history_loader=lambda m, now: candles(),
                             calibration=artifact())
    candidate = screened(theory, ctx([live], run_mode="live", run_id="live"))

    assert candidate.entry_price == pytest.approx(0.58)
    features = candidate.legs[0].market.raw["_news_drift"]
    assert features["entry_source"] == "live_quote"
    assert features["current_directional_mid"] == pytest.approx(0.57)
    assert features["daily_to_current_mid_deviation"] == pytest.approx(0.02)


def test_live_rechecks_open_interest_spread_band_and_activity():
    variants = [
        market("KXND-26JUL31-OI", open_interest=99.0),
        market("KXND-26JUL31-SPREAD", yes_bid=0.50, yes_ask=0.56,
               spread=0.06),
        market("KXND-26JUL31-BAND", yes_bid=0.09, yes_ask=0.11, mid=0.10),
        market("KXND-26JUL31-ACTIVE", volume_24h=0.0),
    ]
    theory = NewsDriftTheory(history_loader=lambda m, now: candles(),
                             calibration=artifact())
    result = theory.screen(ctx(variants, run_mode="live", run_id="live"))

    assert result.candidates == ()
    assert result.gate_removed["live_open_interest"] == 1
    assert result.gate_removed["live_spread"] == 1
    assert result.gate_removed["live_entry_band"] == 1
    assert result.gate_removed["live_no_activity"] == 1


def test_live_activity_falls_back_to_the_entry_candle_only_when_unknown():
    live = market(volume_24h=None)
    theory = NewsDriftTheory(history_loader=lambda m, now: candles(),
                             calibration=artifact())
    candidate = screened(theory, ctx([live], run_mode="live", run_id="live"))

    features = candidate.legs[0].market.raw["_news_drift"]
    assert features["live_activity_source"] == "entry_candle"


# ---- calibration and executable pricing -------------------------------


def test_approved_calibration_prices_from_current_directional_mid_and_fees():
    theory = NewsDriftTheory(history_loader=lambda m, now: candles(),
                             calibration=artifact(
                                 residual=0.05, eligible_for_production=False))
    context = ctx([market()])
    scored = theory.price(context, [screened(theory, context)])

    assert len(scored) == 1
    row = scored[0]
    assert row.edge.basis == "model"
    assert row.edge.model_prob == pytest.approx(0.60)
    assert row.edge.pts_gross == pytest.approx(4.0)
    assert row.edge.fee_pts == pytest.approx(fee_pts(0.56))
    assert row.edge.pts_net == pytest.approx(4.0 - fee_pts(0.56))
    assert row.disposition == "screened"
    assert row.extra["protocol"] == "ND-1"
    assert row.extra["calibration_source_digest"] == "sha256:fixture"
    assert row.extra["calibration_approved"] is True
    assert row.extra["category"] == "Politics"
    assert row.extra["event_ticker"] == "KXND-26JUL31"
    assert row.extra["series_ticker"] == "KXND"
    assert row.extra["calibration_scope"]["population_categories"] == [
        "Politics", "Elections", "Economics", "Entertainment", "World"
    ]


def test_fee_erased_modeled_effect_is_recorded_as_a_rejected_control():
    theory = NewsDriftTheory(history_loader=lambda m, now: candles(),
                             calibration=artifact(
                                 residual=0.02, eligible_for_production=False))
    context = ctx([market()])
    row = theory.price(context, [screened(theory, context)])[0]

    assert row.edge.basis == "model"
    assert row.edge.pts_gross == pytest.approx(1.0)
    assert row.edge.pts_net < 0.0
    assert row.disposition == "rejected"


@pytest.mark.parametrize(
    "bad_artifact",
    [
        {},
        artifact(approved=False),
        artifact(protocol="ND-2"),
        artifact(n=29),
        artifact(event_clusters=9),
        artifact(source_digest=""),
        artifact(training_end="2026-10-01T00:00:00+00:00"),
        artifact(eligible_for_production=False),
    ],
    ids=["missing", "unapproved", "wrong-protocol", "too-few-tickers",
         "too-few-clusters", "missing-digest", "future-cutoff",
         "nonproduction-on-ordinary-run"],
)
def test_unusable_calibration_records_zero_edge_observations(bad_artifact):
    theory = NewsDriftTheory(history_loader=lambda m, now: candles(),
                             calibration=bad_artifact)
    context = ctx([market()], run_id="backtest/ordinary")
    row = theory.price(context, [screened(theory, context)])[0]

    assert row.edge.pts_net == 0.0
    assert row.edge.basis == "prior"
    assert row.edge.model_prob is None
    assert row.disposition == "screened"
    assert row.extra["calibration_status"] != "usable"


def test_nonproduction_artifact_is_usable_only_in_exp_backtest():
    theory = NewsDriftTheory(
        history_loader=lambda m, now: candles(),
        calibration=artifact(eligible_for_production=False),
    )
    context = ctx([market()], run_mode="backtest", run_id="exp/nd-holdout")
    row = theory.price(context, [screened(theory, context)])[0]

    assert row.edge.basis == "model"
    assert row.extra["eligible_for_production"] is False
    assert row.extra["calibration_status"] == "usable_experiment"


def test_exp_artifact_needs_no_production_validation_evidence_or_scope():
    diagnostic = artifact(eligible_for_production=False)
    diagnostic.pop("validation_evidence")
    diagnostic.pop("population_categories")
    theory = NewsDriftTheory(
        history_loader=lambda m, now: candles(), calibration=diagnostic
    )
    context = ctx([market()], run_mode="backtest", run_id="exp/nd-diagnostic")
    row = theory.price(context, [screened(theory, context)])[0]

    assert row.edge.basis == "model"
    assert row.extra["calibration_status"] == "usable_experiment"
    assert row.extra["calibration_scope"] == {"kind": "all_nd1_categories"}


def test_flipping_production_boolean_without_validation_proof_cannot_price():
    falsely_promoted = artifact()
    falsely_promoted.pop("validation_evidence")
    theory = NewsDriftTheory(
        history_loader=lambda m, now: candles(), calibration=falsely_promoted
    )
    context = ctx([market()], run_mode="live", run_id="live")
    row = theory.price(context, [screened(theory, context)])[0]

    assert row.edge.basis == "prior"
    assert row.edge.pts_net == 0.0
    assert row.extra["calibration_reason"] == "validation_plan"


def test_population_series_blocks_out_of_scope_candidates(tmp_path, monkeypatch):
    from tools import db, score, theories
    import theories.news_drift.theory as theory_module

    monkeypatch.setattr(theory_module, "REPO_ROOT", tmp_path)
    conn = db.connect(":memory:")
    db.init_db(conn)
    theories.register(conn, "news_drift", "News Drift", "theories/news_drift")
    subset = validation_artifact(tmp_path)
    plan = subset["validation_plan"]
    score.record_backtest_run(conn, plan["run_id"], "news_drift", 1,
                              tier="A", uses_llm_judgment=False,
                              as_of_start=plan["start"], as_of_end=plan["end"])
    theory = NewsDriftTheory(history_loader=lambda m, now: candles(),
                             calibration=subset)
    context = TheoryContext.build(
        conn, [market()], datetime(2026, 6, 1, tzinfo=timezone.utc),
        run_mode="backtest", run_id=plan["run_id"],
    )
    outside = market(series_ticker="KXOTHER")
    candidate = screened(theory, ctx([outside]))
    row = theory.price(context, [candidate])[0]

    assert row.edge.basis == "prior"
    assert row.edge.pts_net == 0.0
    assert row.extra["calibration_reason"] == "outside_population_scope"
    assert row.extra["calibration_scope"] == {
        "kind": "series",
        "population_series": ["KXND"],
    }


def test_valid_validation_subset_artifact_prices_in_scope_series(tmp_path,
                                                                 monkeypatch):
    from tools import db, score, theories
    import theories.news_drift.theory as theory_module

    monkeypatch.setattr(theory_module, "REPO_ROOT", tmp_path)
    conn = db.connect(":memory:")
    db.init_db(conn)
    theories.register(conn, "news_drift", "News Drift", "theories/news_drift")
    subset = validation_artifact(tmp_path)
    plan = subset["validation_plan"]
    score.record_backtest_run(conn, plan["run_id"], "news_drift", 1,
                              tier="A", uses_llm_judgment=False,
                              as_of_start=plan["start"], as_of_end=plan["end"])
    theory = NewsDriftTheory(history_loader=lambda m, now: candles(),
                             calibration=subset)
    context = TheoryContext.build(
        conn, [market()], datetime(2026, 6, 1, tzinfo=timezone.utc),
        run_mode="backtest", run_id=plan["run_id"],
    )
    candidate = screened(theory, ctx([market()]))
    row = theory.price(context, [candidate])[0]

    assert row.edge.basis == "model"
    assert row.extra["calibration_status"] == "usable_validation"
    assert row.extra["calibration_scope"]["kind"] == "series"


def test_training_cutoff_must_be_known_by_the_replayed_decision_time():
    before_training_cutoff = datetime(2026, 7, 31, tzinfo=timezone.utc)
    theory = NewsDriftTheory(history_loader=lambda m, now: candles(),
                             calibration=artifact())
    candidate = screened(theory, ctx([market()]))
    pricing_context = ctx([market()], now=before_training_cutoff,
                          run_id="backtest/pre-training")
    row = theory.price(pricing_context, [candidate])[0]

    assert row.edge.basis == "prior"
    assert row.edge.pts_net == 0.0


def test_theory_is_fully_mechanical():
    assert NewsDriftTheory.uses_llm_judgment is False
    assert NewsDriftTheory.prompts == {}
    assert isinstance(news_drift_package.THEORY, NewsDriftTheory)


def test_registered_validation_run_uses_its_frozen_variable_cutoff(tmp_path,
                                                                   monkeypatch):
    """Reintroducing one hard-coded campaign cutoff makes this fail."""
    from tools import db, score, theories
    import theories.news_drift.theory as theory_module

    monkeypatch.setattr(theory_module, "REPO_ROOT", tmp_path)

    conn = db.connect(":memory:")
    db.init_db(conn)
    theories.register(conn, "news_drift", "News Drift", "theories/news_drift")
    calibration = validation_artifact(tmp_path)
    plan = calibration["validation_plan"]
    score.record_backtest_run(
        conn, plan["run_id"], "news_drift", 1, tier="A",
        uses_llm_judgment=False, as_of_start=plan["start"],
        as_of_end=plan["end"],
    )
    theory = NewsDriftTheory(
        history_loader=lambda m, now: candles(), calibration=calibration
    )
    candidate = screened(theory, ctx([market()]))
    validation_ctx = TheoryContext.build(
        conn, [market()], datetime(2026, 6, 1, tzinfo=timezone.utc),
        run_mode="backtest", run_id=plan["run_id"],
    )

    row = theory.price(validation_ctx, [candidate])[0]

    assert row.edge.basis == "model"
    assert row.extra["calibration_status"] == "usable_validation"


def test_validation_run_must_match_the_frozen_manifest(tmp_path, monkeypatch):
    from tools import db, score, theories
    import theories.news_drift.theory as theory_module

    monkeypatch.setattr(theory_module, "REPO_ROOT", tmp_path)
    conn = db.connect(":memory:")
    db.init_db(conn)
    theories.register(conn, "news_drift", "News Drift", "theories/news_drift")
    calibration = validation_artifact(tmp_path)
    plan = calibration["validation_plan"]
    plan["run_id"] = "nd1-clean/redirected"
    score.record_backtest_run(
        conn, plan["run_id"], "news_drift", 1, tier="A",
        uses_llm_judgment=False, as_of_start=plan["start"],
        as_of_end=plan["end"],
    )
    theory = NewsDriftTheory(
        history_loader=lambda m, now: candles(), calibration=calibration
    )
    validation_ctx = TheoryContext.build(
        conn, [market()], datetime(2026, 6, 1, tzinfo=timezone.utc),
        run_mode="backtest", run_id=plan["run_id"],
    )

    candidate = screened(theory, ctx([market()]))
    row = theory.price(validation_ctx, [candidate])[0]

    assert row.edge.basis == "prior"
    assert row.extra["calibration_reason"] == "validation_manifest"


def test_self_reported_validation_numbers_cannot_authorize_live_pricing():
    """Deleting the database evidence check must make this test fail."""
    theory = NewsDriftTheory(
        history_loader=lambda m, now: candles(), calibration=artifact()
    )
    live_ctx = ctx([market()], run_mode="live", run_id="live")

    row = theory.price(live_ctx, [screened(theory, live_ctx)])[0]

    assert row.edge.basis == "prior"
    assert row.extra["calibration_reason"] == "validation_plan"


def test_live_pricing_requires_real_complete_positive_validation(tmp_path,
                                                                  monkeypatch):
    """Replacing derived proof with booleans or summary counts makes this fail."""
    from tools import db, ledger, score, theories
    import theories.news_drift.theory as theory_module

    monkeypatch.setattr(theory_module, "REPO_ROOT", tmp_path)

    conn = db.connect(":memory:")
    db.init_db(conn)
    theories.register(conn, "news_drift", "News Drift", "theories/news_drift")
    calibration = validation_artifact(tmp_path, eligible_for_production=True)
    plan = calibration["validation_plan"]
    score.record_backtest_run(
        conn, plan["run_id"], "news_drift", 1, tier="A",
        uses_llm_judgment=False, as_of_start=plan["start"],
        as_of_end=plan["end"],
    )
    for i in range(40):
        decision = datetime(2026, 5, 1 + i % 20, tzinfo=timezone.utc)
        ticker = f"KXND-VALID-{i}"
        price = 0.40
        model_prob = 0.60
        fee = fee_pts(price)
        extra = {
            "protocol": "ND-1",
            "series_ticker": "KXND",
            "event_ticker": f"EVENT-{i}",
            "current_directional_mid": 0.55,
            "calibration_source_digest": calibration["source_digest"],
            "calibration_residual": calibration["residual"],
            "calibration_status": "usable_validation",
            "entry_ts": int(decision.timestamp()),
        }
        ledger.record_opportunity(
            conn, theory_id="news_drift", theory_version=1,
            kalshi_ticker=ticker, outcome="yes", entry_price=price,
            model_prob=model_prob, edge_pts_gross=20.0, fee_pts=fee,
            edge_pts_net=20.0 - fee, edge_basis="model",
            run_mode="backtest", run_id=plan["run_id"],
            decision_date=decision.date().isoformat(),
            extra_json=json.dumps(extra),
        )
        score.record_settlement(
            conn, ticker, "yes",
            resolved_at=datetime(2026, 6, 1 + i % 10,
                                 tzinfo=timezone.utc).isoformat(),
        )

    theory = NewsDriftTheory(
        history_loader=lambda m, now: candles(), calibration=calibration
    )
    live_ctx = TheoryContext.build(
        conn, [market()], datetime(2026, 9, 5, tzinfo=timezone.utc),
        run_mode="live", run_id="live",
    )
    row = theory.price(live_ctx, [screened(theory, live_ctx)])[0]

    assert row.edge.basis == "model"
    assert row.extra["calibration_status"] == "usable"


def test_live_proof_rejects_an_incomplete_validation_membership(tmp_path,
                                                                monkeypatch):
    """Dropping a planned losing row from the replay must never improve proof."""
    from tools import db, score, theories
    import theories.news_drift.theory as theory_module

    monkeypatch.setattr(theory_module, "REPO_ROOT", tmp_path)
    conn = db.connect(":memory:")
    db.init_db(conn)
    theories.register(conn, "news_drift", "News Drift", "theories/news_drift")
    calibration = validation_artifact(tmp_path, eligible_for_production=True)
    plan = calibration["validation_plan"]
    score.record_backtest_run(
        conn, plan["run_id"], "news_drift", 1, tier="A",
        uses_llm_judgment=False, as_of_start=plan["start"],
        as_of_end=plan["end"],
    )
    record_validation_rows(conn, calibration, count=39)
    theory = NewsDriftTheory(
        history_loader=lambda m, now: candles(), calibration=calibration
    )
    live_ctx = TheoryContext.build(
        conn, [market()], datetime(2026, 9, 5, tzinfo=timezone.utc),
        run_mode="live", run_id="live",
    )

    row = theory.price(live_ctx, [screened(theory, live_ctx)])[0]

    assert row.edge.basis == "prior"
    assert row.extra["calibration_reason"] == "validation_membership"


def test_confirmation_exclusions_must_clear_the_full_evidence_bar(tmp_path,
                                                                  monkeypatch):
    from tools import db, score, theories
    import theories.news_drift.theory as theory_module

    monkeypatch.setattr(theory_module, "REPO_ROOT", tmp_path)
    conn = db.connect(":memory:")
    db.init_db(conn)
    theories.register(conn, "news_drift", "News Drift", "theories/news_drift")
    calibration = validation_artifact(tmp_path, eligible_for_production=True)
    set_confirmation_exclusions(
        calibration, tmp_path, [f"EVENT-{i}" for i in range(11)]
    )
    plan = calibration["validation_plan"]
    score.record_backtest_run(
        conn, plan["run_id"], "news_drift", 1, tier="A",
        uses_llm_judgment=False, as_of_start=plan["start"],
        as_of_end=plan["end"],
    )
    record_validation_rows(conn, calibration)
    theory = NewsDriftTheory(
        history_loader=lambda m, now: candles(), calibration=calibration
    )
    live_ctx = TheoryContext.build(
        conn, [market()], datetime(2026, 9, 5, tzinfo=timezone.utc),
        run_mode="live", run_id="live",
    )

    row = theory.price(live_ctx, [screened(theory, live_ctx)])[0]

    assert row.edge.basis == "prior"
    assert row.extra["calibration_reason"] == (
        "confirmation_validation_event_clusters"
    )


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("UPDATE opportunity_attempts SET model_prob = 0.61 WHERE rowid = "
         "(SELECT MIN(rowid) FROM opportunity_attempts)", "validation_pricing"),
        ("DELETE FROM settlements WHERE kalshi_ticker = 'KXND-VALID-0'",
         "validation_pending"),
        ("UPDATE settlements SET resolved_at = '2026-09-06T00:00:00+00:00' "
         "WHERE kalshi_ticker = 'KXND-VALID-0'", "validation_settlement_time"),
    ],
)
def test_live_proof_is_derived_from_actual_predictions_and_settlements(
        tmp_path, monkeypatch, mutation, reason):
    from tools import db, score, theories
    import theories.news_drift.theory as theory_module

    monkeypatch.setattr(theory_module, "REPO_ROOT", tmp_path)
    conn = db.connect(":memory:")
    db.init_db(conn)
    theories.register(conn, "news_drift", "News Drift", "theories/news_drift")
    calibration = validation_artifact(tmp_path, eligible_for_production=True)
    plan = calibration["validation_plan"]
    score.record_backtest_run(
        conn, plan["run_id"], "news_drift", 1, tier="A",
        uses_llm_judgment=False, as_of_start=plan["start"],
        as_of_end=plan["end"],
    )
    record_validation_rows(conn, calibration)
    conn.execute(mutation)
    conn.commit()
    theory = NewsDriftTheory(
        history_loader=lambda m, now: candles(), calibration=calibration
    )
    live_ctx = TheoryContext.build(
        conn, [market()], datetime(2026, 9, 5, tzinfo=timezone.utc),
        run_mode="live", run_id="live",
    )

    row = theory.price(live_ctx, [screened(theory, live_ctx)])[0]

    assert row.edge.basis == "prior"
    assert row.extra["calibration_reason"] == reason
