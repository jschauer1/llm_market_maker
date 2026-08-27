"""no_side_premium: cell assignment, prior honesty, population pinning.

The theory is a pre-registered forward test; what these tests protect is
the pre-registration itself — cell boundaries, dispositions, and the
population parameters the originating backtests used.
"""

from datetime import datetime, timezone

import pytest

from theories.insider_bias import screen as ib_screen
from theories.no_side_premium.theory import (CELL_A_MIN_NO_ASK,
                                             CELL_A_PRIOR_NET, CELL_B_BAND,
                                             CELL_B_PRIOR_NET,
                                             NoSidePremiumTheory, _cell)
from tools.domain import Market
from tools.theory import TheoryContext

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def m(ticker: str, series: str, yes_ask: float, *,
      volume: float = 5000.0) -> Market:
    return Market(
        platform="kalshi", ticker=ticker, title=f"title {ticker}",
        yes_bid=round(yes_ask - 0.02, 2), yes_ask=yes_ask,
        no_bid=round(1 - yes_ask - 0.02, 2), no_ask=round(1 - yes_ask, 2),
        mid=round(yes_ask - 0.01, 2), spread=0.02, volume=volume,
        is_open=True, status="active",
        close_time="2026-08-30T00:00:00Z",
        event_ticker=f"{series}-EV", series_ticker=series,
        raw={"ticker": ticker},
    )


def test_population_parameters_are_pinned():
    """The forward cells were measured on THIS population. If the shared
    screen's defaults move, this theory must decide whether to follow —
    with a version bump — rather than drift silently."""
    assert ib_screen.MIN_FAVORITE_PRICE == 0.65
    assert ib_screen.MAX_FAVORITE_PRICE == 0.97
    assert ib_screen.MAX_SPREAD == 0.07
    assert ib_screen.MIN_VOLUME == 500.0
    assert ib_screen.MAX_DAYS_AHEAD == 14.0
    assert CELL_A_MIN_NO_ASK == 0.85
    assert CELL_B_BAND == (0.80, 0.90)


def _board():
    return [
        # cell A: mention series, NO favorite (yes_ask 0.10 -> no_ask 0.90)
        m("KXTRUMPSAY-26AUG31-CRYP", "KXTRUMPSAY", 0.10),
        # mention NO favorite below the 0.85 line (no_ask 0.80): no cell
        m("KXTRUMPSAY-26AUG31-WALL", "KXTRUMPSAY", 0.20),
        # mention YES favorite: no cell (cell A is NO-side only)
        m("KXTRUMPMENTION-26AUG31-BORD", "KXTRUMPMENTION", 0.85),
        # cell B: non-mention YES favorite at 0.85
        m("KXALBUM-26SEP03-5K", "KXALBUM", 0.85),
        # non-mention YES favorite outside the band: no cell
        m("KXALBUM-26SEP03-9K", "KXALBUM", 0.95),
        # non-mention NO favorite: no cell (cell B is YES-side only)
        m("KXALBUM-26SEP03-1K", "KXALBUM", 0.10),
    ]


def test_screen_assigns_the_two_cells():
    theory = NoSidePremiumTheory()
    ctx = TheoryContext(conn=None, board=_board(), now=NOW,
                        run_id="exp/t", run_mode="backtest")
    res = theory.screen(ctx)
    assert res.funnel["cell_a"] == 1
    assert res.funnel["cell_b"] == 1
    tickers = {c.ticker for c in res.candidates}
    assert tickers == {"KXTRUMPSAY-26AUG31-CRYP", "KXALBUM-26SEP03-5K"}


def test_price_records_priors_and_dispositions():
    theory = NoSidePremiumTheory()
    ctx = TheoryContext(conn=None, board=_board(), now=NOW,
                        run_id="exp/t", run_mode="backtest")
    result = theory.start(ctx).finish(dry_run=True)
    by_ticker = {sc.candidate.ticker: sc for sc in result.scored}
    a = by_ticker["KXTRUMPSAY-26AUG31-CRYP"]
    assert a.disposition == "screened"
    assert a.candidate.fav_side == "no"
    assert a.edge.basis == "prior"
    assert a.edge.pts_net == CELL_A_PRIOR_NET
    assert "NOT a bet" in a.rationale
    b = by_ticker["KXALBUM-26SEP03-5K"]
    assert b.disposition == "rejected"
    assert b.candidate.fav_side == "yes"
    assert b.edge.basis == "prior"
    assert b.edge.pts_net == CELL_B_PRIOR_NET
    assert "AVOID" in b.rationale


def test_live_reprice_uses_fresh_ask_and_enforces_cells():
    fresh = {
        # cell A row: fresh no_ask 0.93 (still in cell, new entry)
        "KXTRUMPSAY-26AUG31-CRYP": {
            "ticker": "KXTRUMPSAY-26AUG31-CRYP", "status": "active",
            "yes_ask_dollars": "0.08", "no_ask_dollars": "0.93",
            "yes_bid_dollars": "0.07", "no_bid_dollars": "0.92"},
        # cell B row: fresh yes_ask 0.95 leaves the band -> dropped
        "KXALBUM-26SEP03-5K": {
            "ticker": "KXALBUM-26SEP03-5K", "status": "active",
            "yes_ask_dollars": "0.95", "no_ask_dollars": "0.06",
            "yes_bid_dollars": "0.94", "no_bid_dollars": "0.05"},
    }

    def fetch(url, params=None):
        want = params["tickers"].split(",")
        return {"markets": [fresh[t] for t in want if t in fresh]}

    theory = NoSidePremiumTheory(fetch=fetch)
    ctx = TheoryContext(conn=None, board=_board(), now=NOW,
                        run_id="exp/t", run_mode="live")
    res = theory.screen(ctx)
    assert len(res.candidates) == 1
    c = res.candidates[0]
    assert c.ticker == "KXTRUMPSAY-26AUG31-CRYP"
    assert c.entry_price == pytest.approx(0.93)
    assert res.gate_removed["reprice_moved_out_of_cell"] == 1


def test_cell_boundaries_exact():
    def cand(series, yes_ask):
        board = [m(f"{series}-T", series, yes_ask)]
        pop = ib_screen.screen(board, now=NOW)
        assert len(pop) == 1
        return pop[0]

    assert _cell(cand("KXTRUMPSAY", 0.15)) == "A"      # no_ask 0.85 inclusive
    assert _cell(cand("KXTRUMPSAY", 0.16)) is None     # no_ask 0.84
    assert _cell(cand("KXOTHER", 0.80)) == "B"         # band inclusive low
    assert _cell(cand("KXOTHER", 0.90)) == "B"         # band inclusive high
    assert _cell(cand("KXOTHER", 0.91)) is None
