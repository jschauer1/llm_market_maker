"""insider_bias — tier A backtest of the stage-1 screen alone.

THEORY.md's Status section names this the single most useful evidence this
theory could get right now: v2 sits at n=0 with every claimed edge a `prior`
placeholder, and the 44 live rows it does have will not settle until
Aug 24-Sep 5. This module answers a narrower but immediately-available
question with NO model anywhere in the decision path -- tier A, full
evidence, no contamination question to even ask: does the mechanical filter
in `screen.py` (price band, spread, volume, near-term close) select
favourites that beat their price? That is not the insider thesis itself
(the screen makes no claim about who knows what), but it is the floor stage
2 and 3 operate on, and THEORY.md's own Learnings already flag it as a live
candidate explanation for a flat historical record: "if 88% of what reaches
judgment cannot carry the thesis, near-zero measured edge is the expected
result." This measures the screen in isolation from that question.

Three things make a naive "replay the whole settled history" infeasible and
shape everything below:

1. Kalshi's settled-market listing has no series_ticker (only /events does),
   so the candlestick endpoint's `{series_ticker}/markets/{ticker}` path
   needs one extra lookup per event, cached by event_ticker
   (`series_ticker_for`).
2. A recent close-time window is enormous -- measured 2026-08-24, the last
   90 days alone is several million settled market rows before any
   filtering. `settled_survivors` applies the screen's cheap, SAFE
   pre-filters (ticker family, and a volume floor) on the settlement
   snapshot itself, with no extra API calls: `is_excluded` doesn't change
   over a market's life, and cumulative volume only grows, so final
   volume < MIN_VOLUME proves the live screen could never have fired either.
   Price band and spread cannot be checked this way and are evaluated later,
   per day, against real point-in-time candles.
3. Kalshi's candlestick `volume` field is that DAY's volume, not the
   cumulative market-to-date total the live screen actually reads
   (`market["volume"]` from `list_open`/`quotes`). `replay_market`
   reconstructs a running sum from `VOLUME_WARMUP_DAYS` before close, which
   can only ever UNDERCOUNT true lifetime volume (trading further back than
   the warm-up window is invisible to it) -- a conservative bias against
   finding an eligible day, never a false positive from inflated volume.

`no_ask` is approximated as `1 - yes_bid_close`, exactly as THEORY.md's "How
to backtest" section specifies.
"""

from __future__ import annotations

from datetime import datetime, timezone

from tools.http import get_json
from tools.kalshi import history, markets
from theories.insider_bias import screen

#: Extra days of candles pulled before a market enters the screen's own
#: MAX_DAYS_AHEAD=14 eligibility window, purely so the running volume sum
#: has time to warm up before it matters. Eligibility itself is never
#: evaluated outside the screen's own 14-day rule -- see module docstring
#: point 3.
VOLUME_WARMUP_DAYS = 45

_series_cache: dict[str, str | None] = {}


def _parse_ts(iso: str | None) -> int | None:
    if not iso:
        return None
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def _raw_volume(raw: dict) -> float:
    value = raw.get("volume_fp")
    try:
        return float(value) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def is_candidate(raw: dict) -> bool:
    """True if a settled market's own snapshot cannot rule out the screen.

    Applies `is_excluded` and the screen's volume floor on the settlement
    snapshot alone -- both safe, conservative checks that need no
    candlestick call (see module docstring point 2): a ticker's family
    never changes, and cumulative volume only grows, so final
    volume < MIN_VOLUME proves the live screen could never have fired
    either. Price band and spread cannot be checked this way and are left
    to the real point-in-time replay in `replay_market`.
    """
    ticker = raw.get("ticker") or ""
    if screen.is_excluded(ticker):
        return False
    return _raw_volume(raw) >= screen.MIN_VOLUME


def settled_survivors(
    min_close_ts: int,
    max_close_ts: int,
    on_page=None,
) -> list[dict]:
    """Settled markets in the window that could possibly clear the screen.

    Everything returned still needs the real per-day replay in
    `replay_market`; `is_candidate` only prunes what could not have passed
    under any circumstances.
    """
    return markets.list_settled(
        limit=1000,
        min_close_ts=min_close_ts,
        max_close_ts=max_close_ts,
        raw_filter=is_candidate,
        on_page=on_page,
    )


def series_ticker_for(event_ticker: str) -> str | None:
    """series_ticker for an event, via one cached GET /events/{ticker}.

    Sibling markets on the same event share this, so the cache turns what
    could be one lookup per candidate into one per event.
    """
    if event_ticker in _series_cache:
        return _series_cache[event_ticker]
    payload = get_json(f"{markets.BASE_URL}/events/{event_ticker}")
    event = payload.get("event", payload) if isinstance(payload, dict) else {}
    series = event.get("series_ticker") if isinstance(event, dict) else None
    _series_cache[event_ticker] = series
    return series


def replay_market(settled: dict, series_ticker: str) -> dict | None:
    """First day within the screen's 14-day window that clears it, or None.

    Walks daily candles ascending from `VOLUME_WARMUP_DAYS` before close,
    reconstructing each day's market state (see module docstring points 1-3)
    and running it through the real, unmodified `screen.screen()` with `now`
    pinned to that day -- this is not a reimplementation of the screen's
    rules, it is the same function the live pipeline calls.
    """
    close_ts = _parse_ts(settled.get("close_time"))
    if close_ts is None:
        return None
    start_ts = close_ts - int(VOLUME_WARMUP_DAYS * 86400)
    candles = history.candlesticks(
        series_ticker,
        settled["ticker"],
        start_ts=start_ts,
        end_ts=close_ts,
        period_interval=1440,
    )

    running_volume = 0.0
    for candle in candles:
        running_volume += candle.get("volume") or 0.0
        yes_bid = candle.get("yes_bid_close")
        yes_ask = candle.get("yes_ask_close")
        if yes_bid is None or yes_ask is None:
            continue

        market_view = {
            "ticker": settled["ticker"],
            "is_open": True,
            "mid": (yes_bid + yes_ask) / 2.0,
            "yes_ask": yes_ask,
            "no_ask": 1.0 - yes_bid,
            "spread": yes_ask - yes_bid,
            "volume": running_volume,
            "close_time": settled.get("close_time"),
        }
        as_of = datetime.fromtimestamp(candle["end_ts"], tz=timezone.utc)
        hits = screen.screen([market_view], now=as_of)
        if hits:
            hit = hits[0]
            return {
                "ticker": settled["ticker"],
                "event_ticker": settled.get("event_ticker"),
                "series_ticker": series_ticker,
                "entry_day_ts": candle["end_ts"],
                "fav_side": hit["fav_side"],
                "entry_price": hit["entry_price"],
                "spread_at_call": hit["spread"],
                "volume_at_call": hit["volume"],
                "days_to_close": hit["days_to_close"],
                "result": settled.get("result"),
            }
    return None


def systematic_sample(items: list[dict], n: int) -> list[dict]:
    """Evenly-spaced sample of up to `n` items, sorted by close_time.

    Sorting first means the sample spreads across the whole window instead
    of clustering wherever the settled-markets API happened to page through
    first -- a systematic sample over time, not an arbitrary prefix.
    """
    if n <= 0 or not items:
        return []
    ordered = sorted(items, key=lambda m: m.get("close_time") or "")
    if len(ordered) <= n:
        return ordered
    step = len(ordered) / n
    return [ordered[int(i * step)] for i in range(n)]
