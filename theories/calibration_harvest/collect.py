"""calibration_harvest -- tier-A settled-history collector.

This is the theory's replay, and it lives here rather than in `tools/`
because everything about it is thesis-specific (CLAUDE.md, "What lives in a
theory"): which slice of history is reachable, how an entry price is
reconstructed for *this* theory's horizon bins, and which approximations
that forces.

It is a **collector**, not a one-shot replay, because its population is much
larger than one session can fetch: the two pre-registered domains alone span
~2,650 series (Politics 1,060 + Elections 1,444 + Climate and Weather 154,
recency-filtered, measured 2026-08-27). So it checkpoints per series and
writes every observation to the DB as the series completes. An interrupted
run resumes; it never restarts from zero. That is not politeness -- Kalshi
archives settled markets out of its public API ~60 days after close, so a
market whose rows a crashed run failed to persist may be unrecoverable
upstream by the time anyone re-runs.

**The reconstruction.** For each settled market, for each horizon bin, read
the daily candle at that bin's entry offset and take the ask as of that
candle's close. No candle at that offset means no observation for that bin
-- a market that did not exist 14 days before close contributes nothing to
`1w-1mo`, which is the correct answer and not a gap to fill by
interpolation.

**One market can contribute to several bins, deliberately.** The rows share
an outcome, so they are not independent -- but every row of one market
settles on the same day, so the day-clustered SE this theory mandates
already absorbs that dependence. Documented in THEORY.md's known biases: the
point estimate can still be tilted by markets that contribute unequal
numbers of rows, which is second-order and is why the `n_days` floor, not
`n`, is the gate on calling a cell measured.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools import atomic_write, db, ledger, score
from tools.kalshi import history, markets
from tools.http import get_json
from theories.calibration_harvest import cells

#: Entry offset in days before close, per horizon bin. Each is comfortably
#: inside its bin so a one-candle timing slip cannot move an observation
#: into a neighbouring cell.
ENTRY_OFFSET_DAYS: dict[str, float] = {
    "<=2d": 1.0,
    "2d-1w": 4.0,
    "1w-1mo": 14.0,
    "1mo+": 45.0,
}

MAX_SPREAD = 0.07
MIN_VOLUME = 500.0

#: Matches the screen's exclusion, for the same reason: `mention_family`'s
#: population must not be pooled into this theory's evidence.
MENTION_MARKERS = ("MENTION", "SAY", "ACT")

#: Kalshi archives settled markets ~60 days after close; a longer window
#: just returns nothing. Measured 2026-08-25 by the sibling fullcov runs.
REACHABLE_DAYS = 58.0


def _is_mention(series: str | None) -> bool:
    s = (series or "").upper()
    return any(marker in s for marker in MENTION_MARKERS)


def worth_fetching(volume: float | None) -> bool:
    """True if a settled market could ever have cleared the volume floor.

    Cumulative volume only grows, so a market whose FINAL volume is below
    the floor was below it at every earlier moment too -- the live screen
    could never have fired on it. Checking the settlement snapshot first
    skips the candlestick call entirely, which is the collector's dominant
    cost. Same reasoning as `insider_bias.replay.is_candidate`.
    """
    return volume is not None and volume >= MIN_VOLUME


def _candle_at(candles: list[dict], target_ts: int) -> tuple[dict, float] | None:
    """The last candle at or before `target_ts`, and volume accumulated to it.

    "At or before" is what makes this lookahead-free: a candle whose period
    ends after the entry moment already contains information the entry
    decision could not have had. The running volume is summed over exactly
    those same candles, so an entry never sees liquidity that arrived after
    it -- Kalshi's candle volume is per-period, not cumulative, so the sum
    is what the live screen's `volume` field would have shown.
    """
    best = None
    running = 0.0
    for candle in sorted(candles, key=lambda c: c.get("end_ts") or 0):
        ts = candle.get("end_ts")
        if ts is None or ts > target_ts:
            continue
        running += candle.get("volume") or 0.0
        best = candle
    if best is None:
        return None
    return best, running


def observations_for(
    ticker: str,
    series: str,
    category: str | None,
    close_ts: int,
    result: str,
    candles: list[dict],
) -> list[dict]:
    """One observation per horizon bin this market can actually support."""
    out: list[dict] = []
    close_iso = datetime.fromtimestamp(close_ts, timezone.utc) \
        .isoformat().replace("+00:00", "Z")

    for bin_label, offset in ENTRY_OFFSET_DAYS.items():
        target = close_ts - int(offset * 86400)
        found = _candle_at(candles, target)
        if found is None:
            continue
        candle, volume_at_entry = found

        # The live screen's liquidity floor, reconstructed. Without it the
        # collector measures markets `screen.py` would never have surfaced,
        # and every cell rate would describe a population the theory cannot
        # actually trade.
        if volume_at_entry < MIN_VOLUME:
            continue

        yes_bid = candle.get("yes_bid_close")
        yes_ask = candle.get("yes_ask_close")
        if yes_bid is None or yes_ask is None:
            continue

        spread = yes_ask - yes_bid
        if spread > MAX_SPREAD or spread < 0:
            continue

        mid = (yes_bid + yes_ask) / 2.0
        if mid >= 0.5:
            side, price = "yes", yes_ask
        else:
            # The NO ask is the complement of the YES bid: to buy NO you
            # lift the resting YES bid from the other side of the book.
            side, price = "no", round(1.0 - yes_bid, 6)

        key = cells.cell_key(price=price, days_to_close=offset,
                             category=category)
        if key is None:
            continue

        # The as-of day this observation entered, derived from the two
        # fields that are already persisted (close_iso via settlements,
        # days_to_close via extra_json) so a future session can reconstruct
        # it without the raw candle timestamp. Backtest attempts must be
        # dated by the day being decided about, not the collector's
        # wall-clock run day (attempt-fidelity spec section 5).
        entry_day_iso = (
            datetime.fromisoformat(close_iso.replace("Z", "+00:00"))
            - timedelta(days=offset)
        ).isoformat().replace("+00:00", "Z")

        out.append({
            "ticker": ticker,
            "series": series,
            "category": category,
            "cell": key,
            "domain": cells.domain_for(category),
            "horizon_bin": bin_label,
            "price_bin": cells.price_bin(price),
            "entry_price": price,
            "outcome": side,
            "result": result,
            "won": side == result,
            "days_to_close": offset,
            "close_iso": close_iso,
            "entry_day_iso": entry_day_iso,
            # Both are computed above to APPLY the screen's liquidity
            # floor and then were thrown away until 2026-09-01. They are
            # point-in-time by construction (`_candle_at` sums only
            # candles at or before the entry moment), they are the two
            # fields a liquidity slice of this theory would need, and
            # they are unrecoverable later: Kalshi archives settled
            # markets out of the API at ~58 days, so the window this walk
            # sees today is not the window a re-walk sees tomorrow. There
            # is no backfill, only capture-or-lose.
            "volume_at_entry": volume_at_entry,
            "spread_at_entry": spread,
        })
    return out


def record(conn, observations: list[dict], run_id: str) -> int:
    """Write observations plus their settlements. Idempotent by ticker.

    Rows land in `opportunities` with `run_mode='backtest'` rather than in a
    bespoke table so the existing scoring path -- including
    `score.settlement_day_clusters`, which this theory depends on -- works
    with no new machinery. `edge_basis='model'` because a collected row is a
    measurement input, never a recommendation; the cell rate it feeds is
    what may later earn `measured`.

    `resolved_at` is the market's close time, which is what makes day
    clustering meaningful -- omit it and every collected row falls into one
    undated cluster and `n_days` becomes a lie.

    `decision_date` is `entry_day_iso`'s date, not the day this collector
    happens to run -- a multi-session collection walk must date each
    observation by the day it was entered, or same-run same-day fallback
    collapses distinct entries into one attempt (attempt-fidelity spec
    section 5).
    """
    written = 0
    for obs in observations:
        _, created = ledger.record_opportunity(
            conn,
            theory_id="calibration_harvest",
            theory_version=1,
            kalshi_ticker=obs["ticker"],
            outcome=obs["outcome"],
            entry_price=obs["entry_price"],
            edge_pts_net=0.0,
            edge_basis="model",
            run_mode="backtest",
            run_id=run_id,
            decision_date=obs["entry_day_iso"][:10],
            volume_at_call=obs.get("volume_at_entry"),
            spread_at_call=obs.get("spread_at_entry"),
            rationale=(
                f"tier-A collection row for cell {obs['cell']} "
                f"(entry {obs['days_to_close']:.0f}d before close); "
                f"measurement input, not a recommendation"
            ),
            extra_json=json.dumps({
                "cell": obs["cell"],
                "domain": obs["domain"],
                "horizon_bin": obs["horizon_bin"],
                "price_bin": obs["price_bin"],
                "series_ticker": obs["series"],
                "category": obs["category"],
                "days_to_close_at_entry": obs["days_to_close"],
            }),
        )
        score.record_settlement(
            conn, obs["ticker"], obs["result"], resolved_at=obs["close_iso"]
        )
        if created:
            written += 1
    conn.commit()
    return written


def cell_rates(conn, run_id: str) -> dict[str, dict]:
    """Per-cell wins / n / n_days, read back from what was collected.

    `n_days` counts distinct settlement days, not rows -- the floor that
    decides whether a cell may call itself `measured`.

    Reads the collection run's own attempt rows, never the position rollup
    (attempt-fidelity spec section 9 -- this is a fourth per-run consumer
    the spec's table missed). Two things break when this reads
    `opportunities`:

    - A second collection run touching an already-collected ticker merges
      onto the existing position, whose `run_id` stays the *earlier* run's.
      `cell_rates(later_run)` then silently misses every re-touched market.
    - One market contributes an observation per horizon bin it can support,
      deliberately (see this module's docstring), and those observations
      can land in different cells. They share a ticker and a side, so they
      are one position holding several attempts -- and the position row
      carries only the first attempt's `extra_json`, so a market feeding
      two cells was counted in exactly one of them.

    That second point is why this consumer, unlike the four in section 9,
    keeps **every** attempt of the run rather than the earliest per
    `(opportunity_id, run_id)`. There, several attempts under one run_id
    would be one judgment recorded twice and deduping is what stops a
    settlement being counted twice. Here they are distinct measurements at
    distinct offsets, which is the whole design; the primary key already
    makes a same-day re-recording impossible, so there is no fan-out to
    guard against, and the dependence between rows of one market is
    absorbed by `n_days` (and by the day-clustered SE this theory
    mandates), not by dropping the rows.
    """
    sql = """
        SELECT a.extra_json, o.outcome, s.result,
               SUBSTR(COALESCE(s.resolved_at, ''), 1, 10) AS day
        FROM opportunity_attempts a
        JOIN opportunities o ON o.id = a.opportunity_id
        JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
        WHERE o.theory_id = 'calibration_harvest' AND a.run_id = ?
    """
    acc: dict[str, dict] = {}
    for row in conn.execute(sql, (run_id,)).fetchall():
        extra = json.loads(row["extra_json"] or "{}")
        key = extra.get("cell")
        if not key:
            continue
        cell = acc.setdefault(key, {"wins": 0, "n": 0, "_days": set()})
        cell["n"] += 1
        if row["outcome"] == row["result"]:
            cell["wins"] += 1
        if row["day"]:
            cell["_days"].add(row["day"])
    return {
        key: {"wins": c["wins"], "n": c["n"], "n_days": len(c["_days"])}
        for key, c in acc.items()
    }


# ---- the driver ----------------------------------------------------------

def load_checkpoint(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"series": {}}


def save_checkpoint(path: Path, state: dict) -> None:
    atomic_write.write_json(path, state, indent=1)


def all_series_categories() -> dict[str, str]:
    """Every Kalshi series ticker -> its category. The live screen's label map.

    Distinct from `target_series`, which answers a different question:
    *which series should this collection walk?* Reusing that answer as a
    label map is what collapsed the domain axis. `target_series` filters to
    the categories being collected and drops anything untouched in
    `REACHABLE_DAYS`, both correct for a settled-history walk and both
    wrong for labelling a board -- an uncollected or stale series can still
    have an open market today, and dropping it strips that market's domain.

    Cheap: `/series` returns all 13,687 series in one response with no
    cursor, so the complete map costs exactly what the partial one did.
    Mention-family series are kept; `screen.py` drops them by ticker
    pattern, and a label map that quietly omits rows is the bug this
    function exists to prevent.
    """
    payload = get_json(f"{markets.BASE_URL}/series", params={"limit": 1000})
    return {s["ticker"]: s.get("category")
            for s in payload.get("series", []) if s.get("ticker")}


def target_series(categories: set[str], now: datetime | None = None,
                  recency_days: float = REACHABLE_DAYS) -> list[dict]:
    """Series in the target categories, touched recently enough to matter."""
    now = now or datetime.now(timezone.utc)
    cutoff = now.timestamp() - recency_days * 86400
    payload = get_json(f"{markets.BASE_URL}/series", params={"limit": 1000})
    out = []
    for series in payload.get("series", []):
        if series.get("category") not in categories:
            continue
        if _is_mention(series.get("ticker")):
            continue
        ts = series.get("last_updated_ts")
        if ts:
            try:
                parsed = datetime.fromisoformat(
                    str(ts).replace("Z", "+00:00")
                ).timestamp()
                if parsed < cutoff:
                    continue
            except ValueError:
                pass
        out.append(series)
    return out


def _parse_ts(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return int(datetime.fromisoformat(
            iso.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def size_series(series: dict, min_close_ts: int, max_close_ts: int) -> dict:
    """Cost of walking one series, without walking it.

    One `list_settled` call (~82ms) answers how many candlestick calls the
    real walk would make, because `worth_fetching` reads the settlement
    snapshot's final volume and cumulative volume only grows. The 2026-08-29
    profiling note asks for exactly this before committing to a population:
    the per-series distribution is brutally skewed (five weather series were
    40% of that walk), so sampling a few series and extrapolating is wrong by
    an order of magnitude in either direction.
    """
    ticker = series.get("ticker")
    settled = markets.list_settled(
        limit=1000, min_close_ts=min_close_ts, max_close_ts=max_close_ts,
        series_ticker=ticker,
    )
    fetches = sum(
        1 for m in settled
        if m.result and _parse_ts(m.close_time) is not None
        and worth_fetching(m.volume)
    )
    return {"n_settled": len(settled), "fetches": fetches}


def collect_series(conn, series: dict, min_close_ts: int, max_close_ts: int,
                   run_id: str) -> dict:
    """Walk one series' settled markets and persist their observations."""
    ticker = series.get("ticker")
    category = series.get("category")
    settled = markets.list_settled(
        limit=1000, min_close_ts=min_close_ts, max_close_ts=max_close_ts,
        series_ticker=ticker,
    )

    observations: list[dict] = []
    no_candles = 0
    below_floor = 0
    for market in settled:
        if not market.result:
            continue
        close_ts = _parse_ts(market.close_time)
        if close_ts is None:
            continue
        if not worth_fetching(market.volume):
            below_floor += 1
            continue
        candles = history.candlesticks(
            ticker, market.ticker,
            start_ts=close_ts - int(60 * 86400),
            end_ts=close_ts,
            period_interval=1440,
        )
        if not candles:
            no_candles += 1
            continue
        observations.extend(observations_for(
            ticker=market.ticker, series=ticker, category=category,
            close_ts=close_ts, result=market.result, candles=candles,
        ))

    written = record(conn, observations, run_id=run_id)
    return {
        "n_settled": len(settled),
        "n_obs": len(observations),
        "written": written,
        "no_candles": no_candles,
        "below_floor": below_floor,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",
                        choices=["enumerate", "size", "run", "rates"])
    parser.add_argument("--categories", default="Politics,Elections",
                        help="comma-separated Kalshi series categories")
    parser.add_argument("--run-id", default="backtest-2026-08-27-calharvest")
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--limit-series", type=int, default=None)
    args = parser.parse_args()

    conn = db.connect()
    try:
        if args.mode == "rates":
            for key, rate in sorted(cell_rates(conn, args.run_id).items()):
                print(f"  {key:44s} {rate['wins']:5d}/{rate['n']:<5d} "
                      f"days={rate['n_days']:3d}")
            return

        cats = {c.strip() for c in args.categories.split(",") if c.strip()}
        series_list = target_series(cats)
        print(f"{len(series_list)} series in {sorted(cats)}")
        if args.limit_series:
            series_list = series_list[: args.limit_series]

        if args.mode == "enumerate":
            for series in series_list:
                print(f"  {series.get('ticker'):32s} "
                      f"{series.get('category')}")
            return

        now = datetime.now(timezone.utc)
        max_close = int(now.timestamp())
        min_close = int(max_close - REACHABLE_DAYS * 86400)

        if args.mode == "size":
            # Persisted per series as it goes: the probe is minutes long on a
            # big category and a killed run must not restart from zero.
            path = args.checkpoint or Path(
                "theories/calibration_harvest/backtests/size.json")
            state = load_checkpoint(path)
            for series in series_list:
                ticker = series.get("ticker")
                if not ticker or ticker in state["series"]:
                    continue
                out = size_series(series, min_close, max_close)
                out["category"] = series.get("category")
                state["series"][ticker] = out
                save_checkpoint(path, state)
            rows = [(k, v) for k, v in state["series"].items()
                    if v.get("category") in cats]
            fetches = sum(v["fetches"] for _, v in rows)
            settled = sum(v["n_settled"] for _, v in rows)
            print(f"  settled in window: {settled}")
            print(f"  candlestick fetches: {fetches}")
            print(f"  est wall clock: {fetches * 0.22 / 3600:.2f} h "
                  f"(at the measured, irreducible 220ms)")
            for tick, v in sorted(rows, key=lambda kv: -kv[1]["fetches"])[:8]:
                print(f"    {tick:32s} settled={v['n_settled']:6d} "
                      f"fetches={v['fetches']:6d}")
            return

        if args.checkpoint is None:
            parser.error("--checkpoint is required for mode=run")

        state = load_checkpoint(args.checkpoint)
        for series in series_list:
            ticker = series.get("ticker")
            if not ticker or ticker in state["series"]:
                continue
            outcome = collect_series(
                conn, series, min_close, max_close, args.run_id
            )
            state["series"][ticker] = outcome
            save_checkpoint(args.checkpoint, state)
            if outcome["n_obs"]:
                print(f"  {ticker:32s} settled={outcome['n_settled']:4d} "
                      f"obs={outcome['n_obs']:4d} "
                      f"thin={outcome['below_floor']:4d} "
                      f"no_candles={outcome['no_candles']:3d}")

        done = state["series"].values()
        print(f"done: {len(state['series'])} series, "
              f"{sum(s['n_obs'] for s in done)} observations")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
