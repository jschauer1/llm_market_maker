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
shape everything below -- the first was discovered the expensive way, by
watching a naive walk run for 47 minutes without finishing:

1. **A close-time window alone does not bound the fetch.** Measured
   2026-08-24, one series -- `KXMVECROSSCATEGORY`, a combinatorial "shard"
   product -- alone settles 400,000+ markets *per day*, so even a 30-day
   `min_close_ts`/`max_close_ts` window on the unscoped `/markets` listing is
   tens of millions of rows before any filtering, dwarfing every other
   series on the platform combined. `candidate_series` sidesteps this
   entirely by querying Kalshi's `/series` listing (one cheap call, ~13k
   rows) and filtering server-side-relevant series *before* ever touching
   `/markets` -- then `iter_settled_survivors` scopes each settled-market
   walk to one series via `series_ticker`, which Kalshi's API honours
   directly and which keeps every individual walk small. `KXMVECROSSCATEGORY`
   itself never gets queried: its category isn't in `NO_CATEGORIES` by name,
   but `screen.is_excluded` already rejects its `KXMVE` prefix, and
   `candidate_series` applies that same check before issuing any settled-
   market request for a series, not just after receiving results.
2. **The category pre-filter is a fetch-scoping decision, not part of the
   screen being tested.** `screen.screen()` itself is unchanged and still
   the only thing that decides whether a candidate clears stage 1.
   `NO_CATEGORIES` only decides which series are worth querying at all, using
   Kalshi's own series `category` field as a coarser, more complete analogue
   of `gate.py`'s regex families (Sports, Crypto, Climate and Weather,
   Commodities, Economics, Elections, Financials -- all series
   `screen.is_excluded` and `gate.py`'s own NO_RULES already treat as "no"
   once they reach judgment). This means the backtest measures the screen
   over a category-narrowed slice of the platform, not literally every
   settled market ever -- report that scope alongside any result from this
   module. A series with no `category` or a stale `last_updated_ts` is kept
   rather than dropped, erring toward inclusion the same way `gate.py` does.
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

from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterator

from tools.http import get_json
from tools.kalshi import history, markets
from theories.insider_bias import screen

#: Extra days of candles pulled before a market enters the screen's own
#: MAX_DAYS_AHEAD=14 eligibility window, purely so the running volume sum
#: has time to warm up before it matters. Eligibility itself is never
#: evaluated outside the screen's own 14-day rule -- see module docstring
#: point 3.
VOLUME_WARMUP_DAYS = 45

#: Series categories Kalshi itself labels as families the thesis cannot
#: apply to -- see module docstring point 2. This is a fetch-scoping
#: decision, applied before any settled-market request, not a change to
#: `screen.screen()`.
NO_CATEGORIES = frozenset({
    "Sports", "Crypto", "Climate and Weather", "Commodities", "Economics",
    "Elections", "Financials",
})

#: A series untouched this long is treated as unlikely to have anything
#: settling inside a recent backtest window -- purely a call-count
#: optimization, not a claim about the thesis.
DEFAULT_RECENCY_DAYS = 60


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


def _is_recent(series: dict, cutoff_ts: float) -> bool:
    ts = _parse_ts(series.get("last_updated_ts"))
    return ts is None or ts >= cutoff_ts


def candidate_series(
    now: datetime | None = None,
    recency_days: float = DEFAULT_RECENCY_DAYS,
) -> list[dict]:
    """Series worth querying for settled markets at all -- see module
    docstring point 1. One GET /series call, then three cheap, safe-to-err-
    toward-inclusion filters: not `screen.is_excluded` by ticker prefix, not
    in `NO_CATEGORIES`, and touched within `recency_days`.
    """
    now = now or datetime.now(timezone.utc)
    cutoff_ts = now.timestamp() - recency_days * 86400
    payload = get_json(f"{markets.BASE_URL}/series", params={"limit": 1000})
    all_series = payload.get("series", [])
    return [
        s for s in all_series
        if not screen.is_excluded(s.get("ticker") or "")
        and s.get("category") not in NO_CATEGORIES
        and _is_recent(s, cutoff_ts)
    ]


def iter_settled_survivors(
    series_list: list[dict],
    min_close_ts: int,
    max_close_ts: int,
) -> Iterator[tuple[str, list[dict]]]:
    """Per-series settled-market survivors, yielded as each series finishes.

    A generator, not a single big return, so a long-running driver can
    checkpoint to disk after every series instead of holding everything in
    memory until the very end and losing it all to an interruption -- see
    module docstring point 1 on why an unscoped walk is not an option here.
    Each survivor is tagged with `series_ticker` (not present on the raw
    settled-market payload) since the caller already knows it and the
    candlestick replay needs it. `Market` is frozen, so the tag is applied
    by replacement rather than in place; the value is identical either way.
    """
    for series in series_list:
        ticker = series.get("ticker")
        if not ticker:
            continue
        survivors = markets.list_settled(
            limit=1000,
            min_close_ts=min_close_ts,
            max_close_ts=max_close_ts,
            series_ticker=ticker,
            raw_filter=is_candidate,
        )
        yield ticker, [replace(s, series_ticker=ticker) for s in survivors]


def settled_survivors(
    min_close_ts: int,
    max_close_ts: int,
    series_list: list[dict] | None = None,
) -> list[dict]:
    """Convenience wrapper: every survivor across `series_list`, collected.

    Prefer `iter_settled_survivors` directly for a long run that should
    checkpoint as it goes; this is for tests and short runs where holding
    the whole result in memory is fine. `series_list` defaults to
    `candidate_series()` -- pass a fixed list in a test to avoid the network
    call that entails.
    """
    if series_list is None:
        series_list = candidate_series()
    out: list[dict] = []
    for _ticker, survivors in iter_settled_survivors(
        series_list, min_close_ts, max_close_ts
    ):
        out.extend(survivors)
    return out


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
