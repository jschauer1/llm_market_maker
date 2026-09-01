"""taker_flow — follow sustained one-sided aggressive order flow.

Fully mechanical: the signal is a volume-weighted imbalance statistic over
Kalshi's published per-trade aggressor side, and the entry is a threshold.
No model anywhere in the decision path, so `edge_basis='model'` and the
replay is tier A.
"""

from __future__ import annotations

from datetime import datetime, timezone

from tools.buckets import fee_pts
from tools.domain import (
    Candidate,
    Edge,
    Fetch,
    Leg,
    ScoredCandidate,
    ScreenResult,
)
from tools.kalshi import trades as trades_client
from tools.theory import Theory, TheoryContext
from theories.taker_flow.features import (
    EXTREME_IMBALANCE,
    flow_bucket,
    is_single_name,
)

#: Liquidity floor. A price cap is deliberately NOT used: the 0.980-0.995
#: placeholder-ask trap that ruined series-bias pass 3 is a LIQUIDITY
#: artifact, so it is excluded with spread and open interest -- what
#: actually distinguishes a quote from an offer.
MIN_VOLUME_24H = 1000.0
MAX_SPREAD = 0.05
MIN_OPEN_INTEREST = 500.0

#: A position needs at least a day before close, because the whole point of
#: the 24h decision buffer in the replay is that this repo runs once a day.
#: The far bound keeps capital from being committed for months on a signal
#: measured over a 7-day window.
MIN_DAYS_TO_CLOSE = 1.0
MAX_DAYS_TO_CLOSE = 45.0

#: Flow window, and the minimum trades that must fall inside it.
LOOKBACK_DAYS = 7.0
MIN_TRADES = 20

#: The screen's entry threshold, pre-registered 2026-09-01 before the full
#: sample was read (NOTES.md, commit faf78ac).
MIN_IMBALANCE = 0.6

#: Gross edge in points measured by the tier A replay over 3,585 settled
#: decisions (58 settlement days, 1,931 event clusters), run
#: `backtest-2026-09-01-takerflow`. BASE RATES FROM MEASURED HISTORY, not
#: introspection -- which is what makes the basis `model`.
#:
#: The two are not a gradient. 'strong' is flat-to-negative and the entire
#: effect sits in the tail, which is why the split exists at all:
#:     strong  0.6-0.9   n=782  618 clusters   -0.78 pts  t=-0.60
#:     extreme >=0.9     n=323  280 clusters   +4.29 pts  t=+2.04
#:
#: THE EXTREME THRESHOLD WAS MINED FROM THAT SAME REPLAY, so the replay
#: cannot vouch for it. It is registered as the slice `extreme-imbalance`
#: with that run declared in `mined_from_run_ids`, which makes the
#: out-of-sample bookkeeping automatic.
MEASURED_GROSS_PTS = {"strong": -0.78, "extreme": 4.29}


def days_to_close(market, now: datetime) -> float | None:
    if not market.close_time:
        return None
    try:
        close = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (close - now).total_seconds() / 86400.0


def is_liquid(market, now: datetime) -> bool:
    if not market.is_open or market.yes_ask is None or market.no_ask is None:
        return False
    if (market.spread if market.spread is not None else 1.0) > MAX_SPREAD:
        return False
    if (market.volume_24h or 0.0) < MIN_VOLUME_24H:
        return False
    if (market.open_interest or 0.0) < MIN_OPEN_INTEREST:
        return False
    days = days_to_close(market, now)
    return days is not None and MIN_DAYS_TO_CLOSE <= days <= MAX_DAYS_TO_CLOSE


def flow_features(
    ticker: str, now: datetime, fetch: Fetch | None = None
) -> dict | None:
    """Imbalance and window stats for one market, or None if too thin.

    A pure function of the ticker and the clock, so `screen` and `price`
    can each call it without either holding state between them -- the
    Theory stays stateless and per-run state stays on the TheoryRun.
    `price` sees only what survived the screen, so the second call is a
    handful of requests, not another pass over the board.
    """
    cutoff = now.timestamp() - LOOKBACK_DAYS * 86400
    rows = trades_client.trades(ticker, max_pages=1, fetch=fetch)
    window = [
        t
        for t in rows
        if datetime.fromisoformat(
            t.created_time.replace("Z", "+00:00")
        ).timestamp()
        >= cutoff
    ]
    if len(window) < MIN_TRADES:
        return None
    imbalance = trades_client.imbalance(window)
    if imbalance is None:
        return None
    return {
        "imbalance": round(imbalance, 4),
        "flow_bucket": flow_bucket(imbalance),
        "window_trades": len(window),
        "window_volume": round(sum(t.count for t in window), 2),
        "single_name": is_single_name(ticker),
    }


class TakerFlowTheory(Theory):
    id = "taker_flow"
    name = "Taker Flow"
    version = 2

    def __init__(self, fetch: Fetch | None = None) -> None:
        #: Injected transport, per the theory contract for anything that
        #: fetches external data. Not per-run state -- it is the same
        #: object for every run of this instance.
        self.fetch = fetch

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        now = ctx.now if ctx.now.tzinfo else ctx.now.replace(tzinfo=timezone.utc)
        board = list(ctx.board)
        liquid = [m for m in board if is_liquid(m, now)]

        candidates: list[Candidate] = []
        thin = 0
        below = 0
        unpayable = 0
        for market in liquid:
            features = flow_features(market.ticker, now, self.fetch)
            if features is None:
                thin += 1
                continue
            if abs(features["imbalance"]) < MIN_IMBALANCE:
                below += 1
                continue
            side = "yes" if features["imbalance"] > 0 else "no"
            ask = market.yes_ask if side == "yes" else market.no_ask
            # An ask of 1.00 costs exactly what it can pay, so its maximum
            # profit is zero -- not a liquidity judgement but arithmetic,
            # which is why it is excluded here rather than by a price cap.
            if not 0.0 < ask < 1.0:
                unpayable += 1
                continue
            candidates.append(
                Candidate(
                    legs=(
                        Leg(
                            market=market,
                            side=side,
                            price=ask,
                        ),
                    ),
                    days_to_close=days_to_close(market, now),
                )
            )

        return ScreenResult(
            candidates=tuple(candidates),
            funnel={
                "board": len(board),
                "liquid": len(liquid),
                "thin_flow": thin,
                "below_threshold": below,
                "unpayable_ask": unpayable,
                "candidates": len(candidates),
            },
        )

    def price(self, ctx, cands, verdicts=None) -> list[ScoredCandidate]:
        now = ctx.now if ctx.now.tzinfo else ctx.now.replace(tzinfo=timezone.utc)
        scored: list[ScoredCandidate] = []
        for cand in cands:
            leg = cand.legs[0]
            features = flow_features(leg.market.ticker, now, self.fetch) or {}
            bucket = features.get("flow_bucket", "strong")
            # The most a position bought at `entry` can gain is (1 - entry)
            # in points. A measured population average applied blindly to a
            # 0.97 ask would claim an edge the contract cannot pay and imply
            # a probability above 1, so the claim is capped by the payout.
            headroom = (1.0 - leg.price) * 100.0
            gross = min(MEASURED_GROSS_PTS[bucket], headroom)
            fee = fee_pts(leg.price)
            scored.append(
                ScoredCandidate(
                    candidate=cand,
                    edge=Edge(
                        pts_net=gross - fee,
                        basis="model",
                        pts_gross=gross,
                        fee_pts=fee,
                        model_prob=leg.price + gross / 100.0,
                    ),
                    confidence=bucket,
                    rationale=(
                        f"taker imbalance {features.get('imbalance')} over "
                        f"{features.get('window_trades')} trades in the "
                        f"trailing {LOOKBACK_DAYS:.0f}d; taking the aggressor "
                        f"side ({leg.side}) at {leg.price:.2f}. Bucket "
                        f"'{bucket}' measured {gross:+.2f}pts gross by "
                        f"backtest-2026-09-01-takerflow."
                    ),
                    disposition="screened",
                    extra={
                        **features,
                        "days_to_close_at_entry": cand.days_to_close,
                        "series_ticker": leg.market.series_ticker,
                    },
                )
            )
        return scored
