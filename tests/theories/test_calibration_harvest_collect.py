"""calibration_harvest -- the settled-history collector.

The collector is the theory's tier-A replay. Its two jobs these tests pin:
reconstruct a point-in-time ask from candles with no lookahead, and write
incrementally so an interrupted multi-session walk resumes instead of
restarting. Kalshi archives settled markets ~60 days after close, so data a
crashed run failed to persist may be unrecoverable upstream by the time
anyone re-runs it.
"""

import json
from datetime import datetime, timezone

import pytest

from tools import db, score, theories
from theories.calibration_harvest import collect

TS = "2026-08-27T00:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    theories.register(c, "calibration_harvest", "Calibration Harvest",
                      "theories/calibration_harvest", now=TS)
    yield c
    c.close()


def _candle(ts, bid, ask, volume=1000):
    """A candle in the shape `history.candlesticks` normalizes to."""
    return {"end_ts": ts, "yes_bid_close": bid, "yes_ask_close": ask,
            "volume": volume}


CLOSE_TS = 1787000000          # arbitrary fixed close
DAY = 86400


# ---- point-in-time reconstruction ---------------------------------------

def test_observation_uses_the_candle_at_the_bins_entry_offset():
    """The 2d-1w bin enters 4 days out; it must read THAT candle."""
    candles = [
        _candle(CLOSE_TS - 5 * DAY, 0.60, 0.64),
        _candle(CLOSE_TS - 4 * DAY, 0.77, 0.80),   # the one it should use
        _candle(CLOSE_TS - 1 * DAY, 0.95, 0.97),
    ]
    obs = collect.observations_for(
        ticker="KXPOL-1", series="KXPOL", category="Politics",
        close_ts=CLOSE_TS, result="yes", candles=candles,
    )
    by_bin = {o["horizon_bin"]: o for o in obs}
    assert by_bin["2d-1w"]["entry_price"] == 0.80
    assert by_bin["2d-1w"]["cell"] == "politics|2d-1w|0.75-0.85"


def test_no_lookahead_a_bin_with_no_candle_yields_nothing():
    """A market that did not exist 14 days out contributes no 1w-1mo row."""
    candles = [_candle(CLOSE_TS - 1 * DAY, 0.90, 0.93)]
    obs = collect.observations_for(
        ticker="KXPOL-1", series="KXPOL", category="Politics",
        close_ts=CLOSE_TS, result="yes", candles=candles,
    )
    assert {o["horizon_bin"] for o in obs} == {"<=2d"}


def test_outcome_is_the_favorite_side_and_win_is_derived_from_result():
    candles = [_candle(CLOSE_TS - 1 * DAY, 0.20, 0.23)]
    obs = collect.observations_for(
        ticker="KXPOL-1", series="KXPOL", category="Politics",
        close_ts=CLOSE_TS, result="no", candles=candles,
    )
    assert obs[0]["outcome"] == "no"          # mid < 0.5 -> NO is favorite
    assert obs[0]["entry_price"] == pytest.approx(0.80)   # 1 - yes_bid 0.20
    assert obs[0]["won"] is True


def test_wide_spread_candle_is_skipped():
    candles = [_candle(CLOSE_TS - 1 * DAY, 0.60, 0.90)]
    obs = collect.observations_for(
        ticker="KXPOL-1", series="KXPOL", category="Politics",
        close_ts=CLOSE_TS, result="yes", candles=candles,
    )
    assert obs == []


def test_dead_middle_candle_yields_no_observation():
    candles = [_candle(CLOSE_TS - 1 * DAY, 0.48, 0.52)]
    obs = collect.observations_for(
        ticker="KXPOL-1", series="KXPOL", category="Politics",
        close_ts=CLOSE_TS, result="yes", candles=candles,
    )
    assert obs == []


def test_one_market_can_populate_several_horizon_bins():
    """Deliberate: same outcome, different prices. Day clustering is what
    keeps the SE honest, since all rows of one market settle the same day."""
    candles = [
        _candle(CLOSE_TS - 20 * DAY, 0.66, 0.69),
        _candle(CLOSE_TS - 4 * DAY, 0.77, 0.80),
        _candle(CLOSE_TS - 1 * DAY, 0.90, 0.93),
    ]
    obs = collect.observations_for(
        ticker="KXPOL-1", series="KXPOL", category="Politics",
        close_ts=CLOSE_TS, result="yes", candles=candles,
    )
    assert {o["horizon_bin"] for o in obs} == {"1w-1mo", "2d-1w", "<=2d"}
    assert all(o["won"] for o in obs)


def test_entry_day_iso_is_close_minus_the_horizon_offset():
    """Backtest attempts must be dated by the day being decided about
    (attempt-fidelity spec section 5). entry_day_iso is derived from
    close_iso and days_to_close specifically so it stays reconstructable
    from what is actually persisted (settlements.resolved_at, extra_json),
    without needing the raw candle timestamp."""
    candles = [_candle(CLOSE_TS - 4 * DAY, 0.77, 0.80)]
    obs = collect.observations_for(
        ticker="KXPOL-1", series="KXPOL", category="Politics",
        close_ts=CLOSE_TS, result="yes", candles=candles,
    )
    by_bin = {o["horizon_bin"]: o for o in obs}
    row = by_bin["2d-1w"]
    close = datetime.fromisoformat(row["close_iso"].replace("Z", "+00:00"))
    entry = datetime.fromisoformat(
        row["entry_day_iso"].replace("Z", "+00:00"))
    assert (close - entry).days == row["days_to_close"]


# ---- persistence --------------------------------------------------------

def test_record_writes_rows_and_settlements(conn):
    obs = [{
        "ticker": "KXPOL-1", "series": "KXPOL", "category": "Politics",
        "cell": "politics|2d-1w|0.75-0.85", "horizon_bin": "2d-1w",
        "price_bin": "0.75-0.85", "domain": "politics",
        "entry_price": 0.80, "outcome": "yes", "won": True,
        "result": "yes", "days_to_close": 4.0,
        "close_iso": "2026-08-20T00:00:00Z",
        "entry_day_iso": "2026-08-16T00:00:00Z",
    }]
    n = collect.record(conn, obs, run_id="backtest-test")
    assert n == 1

    row = conn.execute(
        "SELECT * FROM opportunities WHERE run_id = 'backtest-test'"
    ).fetchone()
    assert row["run_mode"] == "backtest"
    assert row["edge_basis"] == "model"
    extra = json.loads(row["extra_json"])
    assert extra["cell"] == "politics|2d-1w|0.75-0.85"

    settled = conn.execute(
        "SELECT result, resolved_at FROM settlements "
        "WHERE kalshi_ticker = 'KXPOL-1'"
    ).fetchone()
    assert settled["result"] == "yes"
    # resolved_at drives day clustering, so it must be the CLOSE date --
    # without it every collected row lands in one nameless cluster.
    assert settled["resolved_at"] == "2026-08-20T00:00:00Z"


# --- the two liquidity fields, kept from 2026-09-01 ---------------------
#
# `observations_for` computes volume-at-entry and spread-at-entry in order
# to APPLY the screen's liquidity floor, then threw both away. They are the
# two fields any liquidity slice of this theory would need, they are
# point-in-time by construction, and they are UNRECOVERABLE later -- Kalshi
# archives settled markets out of the API at ~58 days, so the window a walk
# sees today is not the window a re-walk sees tomorrow. There is no
# backfill for a collection run, only capture-or-lose.


def test_observation_keeps_the_liquidity_it_filtered_on():
    candles = [_candle(CLOSE_TS - 4 * DAY, bid=0.78, ask=0.82, volume=900)]
    out = collect.observations_for(
        ticker="KXPOL-1", series="KXPOL", category="Politics",
        close_ts=CLOSE_TS, result="yes", candles=candles,
    )
    assert out, "the fixture must clear the floor or it tests nothing"
    assert out[0]["volume_at_entry"] == 900
    assert out[0]["spread_at_entry"] == pytest.approx(0.04)


def test_record_persists_volume_and_spread_as_first_class_columns(conn):
    """Not extra_json: `opportunity_attempts` already has typed columns for
    both, and a slice predicate over a JSON blob is a query nobody writes."""
    obs = [{
        "ticker": "KXPOL-9", "series": "KXPOL", "category": "Politics",
        "cell": "politics|2d-1w|0.75-0.85", "horizon_bin": "2d-1w",
        "price_bin": "0.75-0.85", "domain": "politics",
        "entry_price": 0.80, "outcome": "yes", "won": True,
        "result": "yes", "days_to_close": 4.0,
        "close_iso": "2026-08-20T00:00:00Z",
        "entry_day_iso": "2026-08-16T00:00:00Z",
        "volume_at_entry": 1234.0, "spread_at_entry": 0.04,
    }]
    collect.record(conn, obs, run_id="backtest-liq")
    row = conn.execute(
        "SELECT volume_at_call, spread_at_call FROM opportunity_attempts "
        "WHERE run_id = 'backtest-liq'").fetchone()
    assert row["volume_at_call"] == 1234.0
    assert row["spread_at_call"] == pytest.approx(0.04)


def test_collected_rows_cluster_by_settlement_day(conn):
    obs = []
    # entry_day_iso is close_iso minus the 4-day 2d-1w offset.
    entry_for = {"2026-08-20": "2026-08-16", "2026-08-21": "2026-08-17"}
    for day in ("2026-08-20", "2026-08-21"):
        for i in range(3):
            obs.append({
                "ticker": f"KX-{day}-{i}", "series": "KXPOL",
                "category": "Politics",
                "cell": "politics|2d-1w|0.75-0.85", "horizon_bin": "2d-1w",
                "price_bin": "0.75-0.85", "domain": "politics",
                "entry_price": 0.80, "outcome": "yes", "won": True,
                "result": "yes", "days_to_close": 4.0,
                "close_iso": f"{day}T00:00:00Z",
                "entry_day_iso": f"{entry_for[day]}T00:00:00Z",
            })
    collect.record(conn, obs, run_id="backtest-test")
    out = score.settlement_day_clusters(
        conn, "calibration_harvest", 1, run_mode="backtest",
        run_id="backtest-test",
    )
    assert out["n"] == 6
    assert out["n_days"] == 2


def test_record_is_idempotent_so_a_resumed_run_does_not_double_count(conn):
    obs = [{
        "ticker": "KXPOL-1", "series": "KXPOL", "category": "Politics",
        "cell": "politics|2d-1w|0.75-0.85", "horizon_bin": "2d-1w",
        "price_bin": "0.75-0.85", "domain": "politics",
        "entry_price": 0.80, "outcome": "yes", "won": True,
        "result": "yes", "days_to_close": 4.0,
        "close_iso": "2026-08-20T00:00:00Z",
        "entry_day_iso": "2026-08-16T00:00:00Z",
    }]
    collect.record(conn, obs, run_id="backtest-test")
    collect.record(conn, obs, run_id="backtest-test")
    n = conn.execute(
        "SELECT COUNT(*) c FROM opportunities WHERE run_id = 'backtest-test'"
    ).fetchone()["c"]
    assert n == 1


# ---- checkpointing ------------------------------------------------------

def test_checkpoint_roundtrips_and_defaults_empty(tmp_path):
    path = tmp_path / "cp.json"
    assert collect.load_checkpoint(path) == {"series": {}}
    collect.save_checkpoint(path, {"series": {"KXPOL": {"n_obs": 3}}})
    assert collect.load_checkpoint(path)["series"]["KXPOL"]["n_obs"] == 3


def test_cell_rates_reads_back_what_was_collected(conn):
    obs = []
    for day in range(10):
        obs.append({
            "ticker": f"KX-{day}", "series": "KXPOL", "category": "Politics",
            "cell": "politics|2d-1w|0.75-0.85", "horizon_bin": "2d-1w",
            "price_bin": "0.75-0.85", "domain": "politics",
            "entry_price": 0.80, "outcome": "yes",
            "won": day != 0, "result": "yes" if day != 0 else "no",
            "days_to_close": 4.0,
            "close_iso": f"2026-08-{10 + day:02d}T00:00:00Z",
            "entry_day_iso": f"2026-08-{6 + day:02d}T00:00:00Z",
        })
    collect.record(conn, obs, run_id="backtest-test")
    rates = collect.cell_rates(conn, run_id="backtest-test")
    cell = rates["politics|2d-1w|0.75-0.85"]
    assert cell["n"] == 10
    assert cell["wins"] == 9
    assert cell["n_days"] == 10


def _obs(ticker, cell, horizon, days, entry_day, close="2026-08-20"):
    return {
        "ticker": ticker, "series": "KXPOL", "category": "Politics",
        "cell": cell, "horizon_bin": horizon, "price_bin": "0.75-0.85",
        "domain": "politics", "entry_price": 0.80, "outcome": "yes",
        "won": True, "result": "yes", "days_to_close": days,
        "close_iso": f"{close}T00:00:00Z",
        "entry_day_iso": f"{entry_day}T00:00:00Z",
    }


def test_cell_rates_counts_a_market_in_every_cell_it_fed(conn):
    """One market contributes one observation per horizon bin, by design.

    The bins land in different cells, but they share a ticker and a side,
    so they are one position holding two attempts -- and the position row
    carries only the first attempt's `extra_json`. Reading the rollup
    counted this market in exactly one of the two cells it measured.
    """
    collect.record(conn, [
        _obs("KX-A", "politics|2d-1w|0.75-0.85", "2d-1w", 4.0, "2026-08-16"),
        _obs("KX-A", "politics|1w-1mo|0.75-0.85", "1w-1mo", 14.0,
             "2026-08-06"),
    ], run_id="backtest-test")

    assert conn.execute(
        "SELECT COUNT(*) FROM opportunities"
    ).fetchone()[0] == 1, "one ticker and one side is one position"
    rates = collect.cell_rates(conn, run_id="backtest-test")
    assert rates["politics|2d-1w|0.75-0.85"]["n"] == 1
    assert rates["politics|1w-1mo|0.75-0.85"]["n"] == 1
    assert rates["politics|1w-1mo|0.75-0.85"]["n_days"] == 1


def test_cell_rates_sees_a_ticker_a_later_run_re_collected(conn):
    """The merged position keeps the FIRST run's run_id.

    A collection walk that resumes under a new run id re-touches markets
    the earlier one already wrote; filtering on the position's `run_id`
    drops every one of them from the later run's rates, silently.
    """
    collect.record(conn, [
        _obs("KX-A", "politics|2d-1w|0.75-0.85", "2d-1w", 4.0, "2026-08-16"),
    ], run_id="run-one")
    collect.record(conn, [
        _obs("KX-A", "politics|2d-1w|0.75-0.85", "2d-1w", 4.0, "2026-08-16"),
        _obs("KX-B", "politics|2d-1w|0.75-0.85", "2d-1w", 4.0, "2026-08-16"),
    ], run_id="run-two")

    assert conn.execute(
        "SELECT run_id FROM opportunities WHERE kalshi_ticker = 'KX-A'"
    ).fetchone()["run_id"] == "run-one"
    assert collect.cell_rates(
        conn, run_id="run-two")["politics|2d-1w|0.75-0.85"]["n"] == 2
    assert collect.cell_rates(
        conn, run_id="run-one")["politics|2d-1w|0.75-0.85"]["n"] == 1


# ---- the volume floor: the replay must reconstruct the LIVE decision ------

def test_entry_below_the_volume_floor_yields_no_observation():
    """screen.py requires volume >= 500; the replay must apply it too.

    Without this the collector measures a population the live screen would
    never have traded, and every cell rate describes markets the theory
    cannot actually bet.
    """
    candles = [_candle(CLOSE_TS - 1 * DAY, 0.90, 0.93, volume=10)]
    obs = collect.observations_for(
        ticker="KXPOL-1", series="KXPOL", category="Politics",
        close_ts=CLOSE_TS, result="yes", candles=candles,
    )
    assert obs == []


def test_volume_accumulates_up_to_the_entry_candle():
    """Kalshi candle volume is per-period, so the floor is the running sum.

    Cumulative volume at entry is what the live screen saw; summing only to
    the entry candle is what keeps that lookahead-free.
    """
    candles = [
        _candle(CLOSE_TS - 6 * DAY, 0.77, 0.80, volume=300),
        _candle(CLOSE_TS - 4 * DAY, 0.77, 0.80, volume=300),   # cum 600
        _candle(CLOSE_TS - 1 * DAY, 0.90, 0.93, volume=10_000),
    ]
    obs = collect.observations_for(
        ticker="KXPOL-1", series="KXPOL", category="Politics",
        close_ts=CLOSE_TS, result="yes", candles=candles,
    )
    bins = {o["horizon_bin"] for o in obs}
    assert "2d-1w" in bins          # 600 cumulative at the 4-day entry


def test_later_volume_does_not_leak_back_to_an_earlier_entry():
    """The 1w-1mo entry must not see volume that only arrived later."""
    candles = [
        _candle(CLOSE_TS - 14 * DAY, 0.77, 0.80, volume=5),
        _candle(CLOSE_TS - 1 * DAY, 0.90, 0.93, volume=50_000),
    ]
    obs = collect.observations_for(
        ticker="KXPOL-1", series="KXPOL", category="Politics",
        close_ts=CLOSE_TS, result="yes", candles=candles,
    )
    assert {o["horizon_bin"] for o in obs} == {"<=2d"}


def test_settled_market_below_the_floor_is_skipped_before_any_candle_call():
    """Cumulative volume only grows, so a final volume under the floor
    proves the screen could never have fired -- and skipping it avoids the
    candlestick call, which is the collector's dominant cost."""
    assert collect.worth_fetching(volume=10.0) is False
    assert collect.worth_fetching(volume=5000.0) is True
    assert collect.worth_fetching(volume=None) is False


# ---- the complete category map ------------------------------------------
#
# `target_series` filters `/series` down to the categories being COLLECTED.
# Reusing it to label a board-wide live screen is what collapsed the domain
# axis: every series outside the collected categories arrived with no
# category at all. The label map and the collection population are two
# different questions, so they get two different functions.

_SERIES_PAYLOAD = {"series": [
    {"ticker": "KXWEATHER", "category": "Climate and Weather",
     "last_updated_ts": "2026-08-26T00:00:00Z"},
    {"ticker": "KXPOL", "category": "Politics",
     "last_updated_ts": "2026-08-26T00:00:00Z"},
    {"ticker": "KXOIL", "category": "Commodities",
     "last_updated_ts": "2026-08-26T00:00:00Z"},
    {"ticker": "KXSTALE", "category": "Sports",
     "last_updated_ts": "2020-01-01T00:00:00Z"},
]}


def test_all_series_categories_covers_every_category(monkeypatch):
    """One `/series` fetch returns all 13,687 series with no cursor, so a
    complete map costs exactly what the partial one cost."""
    monkeypatch.setattr(collect, "get_json",
                        lambda *a, **k: _SERIES_PAYLOAD)
    m = collect.all_series_categories()
    assert m == {"KXWEATHER": "Climate and Weather", "KXPOL": "Politics",
                 "KXOIL": "Commodities", "KXSTALE": "Sports"}


def test_all_series_categories_keeps_stale_series(monkeypatch):
    """`target_series` drops series untouched in 58 days because they
    cannot contribute settled history. A LABEL map must keep them: a stale
    series can still have an open market on today's board, and dropping it
    is exactly how a market loses its domain."""
    monkeypatch.setattr(collect, "get_json",
                        lambda *a, **k: _SERIES_PAYLOAD)
    assert "KXSTALE" in collect.all_series_categories()
    now = datetime(2026, 8, 27, tzinfo=timezone.utc)
    assert "KXSTALE" not in {
        s["ticker"] for s in collect.target_series({"Sports"}, now=now)
    }
