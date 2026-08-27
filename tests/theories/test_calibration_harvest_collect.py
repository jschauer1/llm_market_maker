"""calibration_harvest -- the settled-history collector.

The collector is the theory's tier-A replay. Its two jobs these tests pin:
reconstruct a point-in-time ask from candles with no lookahead, and write
incrementally so an interrupted multi-session walk resumes instead of
restarting. Kalshi archives settled markets ~60 days after close, so data a
crashed run failed to persist may be unrecoverable upstream by the time
anyone re-runs it.
"""

import json

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


# ---- persistence --------------------------------------------------------

def test_record_writes_rows_and_settlements(conn):
    obs = [{
        "ticker": "KXPOL-1", "series": "KXPOL", "category": "Politics",
        "cell": "politics|2d-1w|0.75-0.85", "horizon_bin": "2d-1w",
        "price_bin": "0.75-0.85", "domain": "politics",
        "entry_price": 0.80, "outcome": "yes", "won": True,
        "result": "yes", "days_to_close": 4.0,
        "close_iso": "2026-08-20T00:00:00Z",
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


def test_collected_rows_cluster_by_settlement_day(conn):
    obs = []
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
        })
    collect.record(conn, obs, run_id="backtest-test")
    rates = collect.cell_rates(conn, run_id="backtest-test")
    cell = rates["politics|2d-1w|0.75-0.85"]
    assert cell["n"] == 10
    assert cell["wins"] == 9
    assert cell["n_days"] == 10
