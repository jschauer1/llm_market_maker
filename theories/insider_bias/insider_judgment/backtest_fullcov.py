"""insider_judgment — tier A full-coverage backtest of screen + code gate.

The direct analogue of `mention_family/backtest.py` (2026-08-25), applied
to this theory's own population. The original tier-A evidence
(`backtest-2026-08-24-stage1-90d`) replayed a 600-of-18,430 systematic
sample and left this theory 84 non-mention rows — and the sibling's
full-coverage rerun then showed exactly how wrong a ~3% sample of this
screen's selection can be (its +5.48pts became -1.53 at full coverage).
This driver replays EVERY non-mention survivor in the API-reachable close
window (Kalshi archives settled markets ~60 days after close; see
`tools/kalshi/markets.py::list_settled`), so the screen's calibration and
the gate's selection value are measured on the population, not a sample.

What this measures, and what it cannot:

- **Stage 1 (shared screen) at scale** — same `replay_market()` as every
  other run of this machinery, entry at the daily candle's closing ask on
  the first qualifying day.
- **The code gate at scale** — `gate.classify` is a deterministic
  series-ticker regex, so every hit carries `gate_classification` /
  `gate_would_reject` in `extra_json` for free. The current evidence that
  "gate.py's filtering is doing real, measurable work" rests on n=37
  gate-plausible vs n=47 gated rows; this multiplies both.
- **Not the judgment stages.** No LLM runs here (tier A). Whether stage
  2/3 judgment adds edge on top of screen+gate needs a separate tier-B
  judged sample over these same settled rows (markets here resolved
  2026-06..08, after the judging model's cutoff, so that sample is
  genuinely tier B when run with web search off).

Mention-family series are excluded entirely: they are the sibling
theory's population, already covered at full depth by
`backtest-2026-08-25-mention-fullcov`, and their rows live under that
theory. `is_mention_family`, from the shared parent's `families.py`, is
the same classifier both theories share.

Run:
    python -m theories.insider_bias.insider_judgment.backtest_fullcov enumerate
    python -m theories.insider_bias.insider_judgment.backtest_fullcov run \
        --checkpoint <path>

Then:
    python -m tools.cli backtest record backtest-2026-08-25-insider-fullcov \
        insider_judgment 3 --tier A --notes "..."
    python -m tools.cli score report insider_judgment --run-mode backtest \
        --run-id backtest-2026-08-25-insider-fullcov
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from tools import db, ledger, provenance, score
from tools.kalshi import cache as history_cache
from tools.kalshi import history
from theories.insider_bias import replay as sibling
from theories.insider_bias.insider_judgment import gate
from theories.insider_bias.families import is_mention_family

THEORY_ID = "insider_judgment"
THEORY_VERSION = 3

RUN_ID = "backtest-2026-08-25-insider-fullcov"

#: Same reachable window as the sibling's full-coverage run, on purpose —
#: results from the two runs describe the same period of the same board,
#: split by family. Min sits below the archival floor knowingly (nothing
#: comes back there; if the floor is softer than measured, rows are kept).
WINDOW_MIN_CLOSE = int(datetime(2026, 5, 26, tzinfo=timezone.utc).timestamp())
WINDOW_MAX_CLOSE = int(
    datetime(2026, 8, 24, 21, 51, 52, tzinfo=timezone.utc).timestamp()
)

SERIES_RECENCY_DAYS = 450.0

RATIONALE = (
    "Tier A full-coverage backtest of stage 1 + the code gate: every "
    "non-mention survivor in the API-reachable close window "
    "(~2026-06-22 .. 2026-08-24), replayed by the sibling machinery's "
    "replay_market() unchanged — the original run sampled 600 of 18,430. "
    "First qualifying day within the screen's 14-day window, entry at the "
    "daily candle's closing ask. gate_classification in extra_json is "
    "deterministic (gate.py); no LLM stage ran. No probability claim -- "
    "screen.py makes none."
)


def candidate_series(now: datetime | None = None) -> list[dict]:
    """This theory's eligible series: the shared population rules, minus
    the sibling's mention family."""
    return [
        s
        for s in sibling.candidate_series(
            now=now, recency_days=SERIES_RECENCY_DAYS
        )
        if not is_mention_family(s.get("ticker") or "")
    ]


class _CandleCache:
    """Intercepts history.candlesticks for two jobs at once: keeps the last
    fetch visible so a None replay can be diagnosed without a second call
    (same as the sibling driver), and — since 2026-08-25 — writes every
    fetch through to the durable history cache (`tools/kalshi/cache.py`),
    so a variant re-test never has to re-walk the network and the raw data
    survives Kalshi's ~60-day archival."""

    def __init__(self, cache_conn: sqlite3.Connection) -> None:
        self._real = history.candlesticks
        self._cache_conn = cache_conn
        self.last: list[dict] | None = None

    def __call__(self, series_ticker, ticker, start_ts, end_ts,
                 period_interval=1440) -> list[dict]:
        self.last = history_cache.cached_candlesticks(
            self._cache_conn, series_ticker, ticker,
            start_ts=start_ts, end_ts=end_ts,
            period_interval=period_interval,
            fetch_candles=self._real,
        )
        return self.last

    def install(self) -> None:
        history.candlesticks = self  # type: ignore[assignment]

    def uninstall(self) -> None:
        history.candlesticks = self._real  # type: ignore[assignment]


def replay_series(
    series_ticker: str, survivors: list, cache: _CandleCache
) -> dict:
    hits: list[dict] = []
    no_candles = 0
    no_quotes = 0
    never_qualified = 0
    for settled in survivors:
        cache.last = None
        hit = sibling.replay_market(settled, series_ticker)
        if hit is not None:
            hits.append(hit)
        elif not cache.last:
            no_candles += 1
        elif not any(
            c.get("yes_bid_close") is not None
            and c.get("yes_ask_close") is not None
            for c in cache.last
        ):
            no_quotes += 1
        else:
            never_qualified += 1
    return {
        "series_ticker": series_ticker,
        "n_survivors": len(survivors),
        "n_hits": len(hits),
        "no_candles": no_candles,
        "no_quotes": no_quotes,
        "never_qualified": never_qualified,
        "hits": hits,
    }


def record_run_provenance(conn: sqlite3.Connection) -> None:
    """The only stage that classifies anything in this run is the
    deterministic gate; recorded so `record_opportunity`'s provenance
    requirement is satisfied by the artifact that actually governed the
    decision, same convention as gate.py's live runs."""
    provenance.record_judgment_run(
        conn,
        run_id=RUN_ID,
        theory_id=THEORY_ID,
        theory_version=THEORY_VERSION,
        stage="gate",
        model="none (deterministic)",
        prompt_path="theories/insider_bias/insider_judgment/gate.py",
        web_search=False,
    )


def record_hits(conn: sqlite3.Connection, hits: list[dict]) -> int:
    written = 0
    for h in hits:
        entry_day = datetime.fromtimestamp(h["entry_day_ts"], tz=timezone.utc)
        classification = gate.classify(h["series_ticker"])
        ledger.record_opportunity(
            conn,
            theory_id=THEORY_ID,
            theory_version=THEORY_VERSION,
            kalshi_ticker=h["ticker"],
            outcome=h["fav_side"],
            entry_price=h["entry_price"],
            edge_pts_net=0.0,
            run_mode="backtest",
            run_id=RUN_ID,
            spread_at_call=h["spread_at_call"],
            volume_at_call=h["volume_at_call"],
            edge_basis="prior",
            rationale=RATIONALE,
            evidence_source="kalshi",
            extra_json=json.dumps(
                {
                    "backtest_run": RUN_ID,
                    "series_ticker": h["series_ticker"],
                    "event_ticker": h["event_ticker"],
                    "entry_day_ts": h["entry_day_ts"],
                    "entry_day_iso": entry_day.isoformat(),
                    "days_to_close_at_entry": h["days_to_close"],
                    "gate_classification": classification,
                    "gate_would_reject": classification != gate.PLAUSIBLE,
                    "is_mention_family": False,
                }
            ),
        )
        if h["result"]:
            score.record_settlement(conn, h["ticker"], h["result"])
        written += 1
    return written


def load_checkpoint(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"series": {}}


def save_checkpoint(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["enumerate", "run"])
    parser.add_argument("--checkpoint", type=Path, default=None,
                        help="state file; required for mode=run")
    parser.add_argument("--limit-series", type=int, default=None,
                        help="stop after N series (smoke-testing)")
    args = parser.parse_args()

    series_list = candidate_series()
    print(f"{len(series_list)} non-mention candidate series "
          f"(window {WINDOW_MIN_CLOSE}..{WINDOW_MAX_CLOSE})")
    if args.limit_series:
        series_list = series_list[: args.limit_series]

    if args.mode == "enumerate":
        total = 0
        for ticker, survivors in sibling.iter_settled_survivors(
            series_list, WINDOW_MIN_CLOSE, WINDOW_MAX_CLOSE
        ):
            if survivors:
                print(f"  {ticker:30s} {len(survivors)} survivors")
            total += len(survivors)
        print(f"total survivors: {total}")
        return

    if args.checkpoint is None:
        parser.error("--checkpoint is required for mode=run")
    state = load_checkpoint(args.checkpoint)
    conn = db.connect()
    record_run_provenance(conn)
    cache_conn = history_cache.connect()
    cache = _CandleCache(cache_conn)
    cache.install()
    try:
        for ticker, survivors in sibling.iter_settled_survivors(
            series_list, WINDOW_MIN_CLOSE, WINDOW_MAX_CLOSE
        ):
            if ticker in state["series"]:
                continue
            # Raw listing payloads first, so they are saved even if the
            # replay of this series is interrupted partway.
            history_cache.store_settled_markets(cache_conn, survivors)
            outcome = replay_series(ticker, survivors, cache)
            record_hits(conn, outcome["hits"])
            state["series"][ticker] = outcome
            save_checkpoint(args.checkpoint, state)
            print(
                f"  {ticker:30s} survivors={outcome['n_survivors']:4d} "
                f"hits={outcome['n_hits']:3d} "
                f"no_candles={outcome['no_candles']:3d} "
                f"no_quotes={outcome['no_quotes']:3d} "
                f"never_qualified={outcome['never_qualified']:4d}"
            )
    finally:
        cache.uninstall()
        cache_conn.close()
        conn.close()

    done = state["series"].values()
    print(
        f"done: {len(done)} series, "
        f"{sum(s['n_survivors'] for s in done)} survivors, "
        f"{sum(s['n_hits'] for s in done)} hits, "
        f"{sum(s['no_candles'] for s in done)} no_candles"
    )


if __name__ == "__main__":
    main()
