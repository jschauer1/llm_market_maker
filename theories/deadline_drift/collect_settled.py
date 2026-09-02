"""Persist the settled allowlist history the hazard estimate rests on.

**Why this exists as a script and not as a one-off.** Kalshi archives
settled markets out of its public API roughly 60 days after close. The 112
markets this theory's first estimate used are not a sample -- they are the
entire fetchable history for this population, and it shrinks every day.
Anything not on disk when it is fetched is unrecoverable upstream later.

Writes three things, incrementally and resumably:

  data/settled_raw.json     complete list_settled payloads, untouched
  data/anchors.json         per market: parsed deadline, actual close, the
                            gap between them, result. The gap is the whole
                            correction in a6302a8 -- a NO market closes at
                            its deadline, a YES market closes when the event
                            fires, a median of 210 days earlier.
  data/candles.json         daily candles per market, with days measured
                            from BOTH anchors so the contaminated and
                            corrected views are both reconstructable, and
                            BOTH SIDES OF THE BOOK plus open interest.

**Why `yes_bid` is stored and not just `yes_ask`.** This theory buys NO.
The price a NO buyer actually pays is `no_ask = 1 - yes_bid`, so an edge
measured against `yes_ask` is optimistic by exactly the bid-ask spread --
on illiquid longshots that is the whole claimed edge. CLAUDE.md's rule
("entry prices are the ask you would actually pay, never the mid") binds
here through the *other* side of the book, which is easy to miss.
`open_interest` is stored for the same reason `calibration_harvest`
learned to on 2026-09-01: a liquidity slice is untestable if the
collector computes liquidity, filters on it, and throws it away.

Run: python -m theories.deadline_drift.collect_settled
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path

from tools import atomic_write
from tools.kalshi import history
from tools.kalshi import markets as km

DATA = Path(__file__).parent / "data"
ARCHIVE_DAYS = 60

_MON = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_DEADLINE = re.compile(
    rf"\b(?:before|by|on or before|no later than)\s+"
    rf"({_MON})\w*\s+(\d{{1,2}}),?\s*(\d{{4}})", re.IGNORECASE)
_MONI = {m: i + 1 for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def parse_deadline(rules: str | None) -> str | None:
    """The deadline STATED IN THE RULES -- the only sound time anchor.

    Actual close is a function of the outcome on a 'by D' market, so it can
    never define the decision point: see the 2026-08-29 correction in
    NOTES.md.
    """
    hit = _DEADLINE.search(rules or "")
    if not hit:
        return None
    return dt.datetime(int(hit.group(3)), _MONI[hit.group(1)[:3].title()],
                       int(hit.group(2)), tzinfo=dt.timezone.utc).isoformat()


def _load(name: str) -> dict:
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save(name: str, obj) -> None:
    """Atomic whole-file write, via `tools.atomic_write`.

    Was a local implementation: two failures on 2026-09-01 (a OneDrive
    handle killing a walk at 874/960 series, and a reader catching a
    half-written file) proved the shape here first. It is now shared —
    every collector built to the record-while-you-collect convention had
    the same exposure. Still no defence against a SECOND WRITER; that
    needs a lock, ticketed as
    `maintenance/collector-write-lock`.
    """
    atomic_write.write_json(DATA / name, obj)


def _ts(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def _rows(cs: list[dict], close_ts: int, dl_ts: int) -> list[dict]:
    """One stored row per candle. Both sides of the book, both anchors."""
    return [
        {"end_ts": c["end_ts"],
         "yes_ask": c["yes_ask_close"],
         # The side a NO buyer actually pays: no_ask = 1 - yes_bid.
         "yes_bid": c.get("yes_bid_close"),
         "volume": c["volume"],
         "open_interest": c.get("open_interest"),
         # Both anchors kept, so the contaminated and corrected
         # views are each reconstructable from disk.
         "days_to_close": round((close_ts - c["end_ts"]) / 86400.0, 2),
         "days_to_deadline": round((dl_ts - c["end_ts"]) / 86400.0, 2)}
        for c in cs
        if c.get("yes_ask_close") is not None
    ]


def _needs_bid_upgrade(stored) -> bool:
    """True for rows captured before `yes_bid` was persisted (pre-2026-09-01).

    Re-fetching is cheap and the upgrade is worth a second walk, but the
    ~60-day archive floor means some of these tickers no longer return
    candles at all. Those rows are STAMPED rather than dropped -- see
    `_stamp_unupgradable` -- so the schema is uniform, the missing value
    is explicit, and a later run does not retry them forever.
    """
    return (isinstance(stored, list) and bool(stored)
            and "yes_bid" not in stored[0])


def _stamp_unupgradable(stored: list[dict]) -> list[dict]:
    """Mark legacy rows the archive can no longer re-serve.

    Keeping them beats wiping: 33 of the 2026-08-29 capture's markets had
    already fallen past today's floor, so a wipe-and-refetch would have
    destroyed data no longer obtainable upstream from anyone.
    """
    for r in stored:
        r.setdefault("yes_bid", None)
        r.setdefault("open_interest", None)
        r["bid_unavailable"] = True
    return stored


class _SeriesTooLarge(Exception):
    """Raised out of `list_settled`'s `on_page` to abandon one runaway series.

    Kalshi hosts combinatorial "shard" products -- `KXMVECROSSCATEGORY`
    settles 400,000+ markets *per day* -- and a platform-wide walk hits
    them. There is no partial-fetch option on `list_settled` by design, so
    the only way to bound one series without bounding all of them is to
    raise from the page callback and catch it per series. A by-deadline
    series is small (the largest in the current store is under 200
    markets), so this can only ever discard a family this theory does not
    want.
    """


def platform_series(fetch=None) -> list[str]:
    """Every series Kalshi lists -- not just those with an open market today.

    **This is the correction to a survivorship bias, not an optimisation.**
    `superset_series` derives its list from the live board, so a series is
    reachable only while it still has something trading. For a theory about
    "will X happen by deadline D" that filter is not neutral: a series ends
    *because* its question resolved, so board-scoped capture systematically
    misses the families that already finished. Measured 2026-09-02: the
    board-scoped walk covered 170 series with results, against 13,733
    series on the platform.

    **Ordered by expected yield, not alphabetically.** Kalshi ticker
    prefixes sort digits and legacy names ahead of the `KX*` range that
    holds essentially every modern series, so an alphabetical walk spends
    hours on `10Y2Y`, `1SONG-*` and `538APPROVE*` before reaching anything
    this theory can use -- measured 2026-09-02: 256 series walked, 0
    by-deadline markets found, while the probe's likely-category sample
    yielded 0.14 per series. The walk is resumable and eventually covers
    everything either way; ordering only decides how soon the useful part
    arrives.
    """
    from tools.http import get_json
    payload = get_json(f"{km.BASE_URL}/series", params={"limit": 1000})
    #: Measured, not guessed: all 170 series that have ever yielded a
    #: by-deadline settled market carry the `KX` prefix, and 0 of the
    #: legacy non-KX names do. Category is a much weaker signal than it
    #: looks -- the productive set spans Politics (71) but also Financials
    #: (29) and Sports (19), so an earlier attempt to prioritise by a
    #: hand-picked category list ranked gas-price and approval-index
    #: series first and found nothing in 256 walks.
    CATEGORY_ORDER = ["Politics", "Financials", "Sports", "Entertainment",
                      "Science and Technology", "Elections", "Mentions",
                      "Economics", "Crypto", "Companies",
                      "Climate and Weather", "Commodities"]

    def rank(s):
        if not s["ticker"].startswith("KX"):
            return (1, len(CATEGORY_ORDER))
        c = s.get("category")
        return (0, CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER
                else len(CATEGORY_ORDER))

    rows = [s for s in payload.get("series", []) if s.get("ticker")]
    return [s["ticker"] for s in sorted(rows,
                                        key=lambda s: (rank(s), s["ticker"]))]


def collect(series: list[str], *, fetch=None, raw_filter=None,
            max_pages: int | None = None) -> dict:
    """Walk each series, persisting after every one. Resumable by design.

    `raw_filter` is handed to `list_settled` and runs before the expensive
    part of `normalize`, which is what makes a platform-wide walk tractable.
    `max_pages` abandons any single series exceeding it -- see
    `_SeriesTooLarge`.
    """
    raw = _load("settled_raw.json")
    anchors = _load("anchors.json")
    candles = _load("candles.json")
    floor = int(time.time()) - ARCHIVE_DAYS * 24 * 3600

    for s in series:
        if s not in raw:
            def _cap(pages, _n, _limit=max_pages, _s=s):
                if _limit is not None and pages >= _limit:
                    raise _SeriesTooLarge(_s)
            try:
                got = km.list_settled(series_ticker=s, min_close_ts=floor,
                                      fetch=fetch, raw_filter=raw_filter,
                                      on_page=_cap if max_pages else None)
                raw[s] = [m.raw for m in got if m.result]
            except _SeriesTooLarge:
                raw[s] = {"__error__": f"skipped: exceeded {max_pages} pages"}
            except Exception as exc:
                raw[s] = {"__error__": f"{type(exc).__name__}: {exc}"}
            _save("settled_raw.json", raw)

        rows = raw[s] if isinstance(raw[s], list) else []
        for m in rows:
            tk = m["ticker"]
            if tk not in anchors:
                dl = parse_deadline(m.get("rules_primary"))
                anchors[tk] = {
                    "series": s, "result": m.get("result"),
                    "close_time": m.get("close_time"), "deadline": dl,
                    "closed_early_days": (
                        round((_ts(dl) - _ts(m["close_time"])) / 86400.0, 2)
                        if dl and m.get("close_time") else None),
                }
                _save("anchors.json", anchors)
            if not anchors[tk].get("deadline"):
                continue
            if tk in candles and not _needs_bid_upgrade(candles[tk]):
                continue
            close_ts = _ts(anchors[tk]["close_time"])
            dl_ts = _ts(anchors[tk]["deadline"])
            try:
                cs = history.candlesticks(s, tk, close_ts - 45 * 86400,
                                          close_ts, 1440)
            except Exception as exc:
                if not isinstance(candles.get(tk), list):
                    candles[tk] = {"__error__": type(exc).__name__}
                    _save("candles.json", candles)
                continue
            fresh = _rows(cs, close_ts, dl_ts)
            if fresh:
                candles[tk] = fresh
            elif isinstance(candles.get(tk), list):
                # Archived out from under us: keep what we have.
                candles[tk] = _stamp_unupgradable(candles[tk])
            else:
                candles[tk] = fresh
            _save("candles.json", candles)
    return {"series": len(raw), "markets": len(anchors),
            "with_candles": sum(1 for v in candles.values()
                                if isinstance(v, list))}


FACT_KIND = "last_settled_capture"


def mark_captured(conn, when: str | None = None) -> None:
    """Stamp the capture date so any session's orient can see staleness."""
    from tools import db
    when = when or dt.datetime.now(dt.timezone.utc).isoformat()
    with db.write(conn):
        conn.execute(
            "INSERT OR REPLACE INTO theory_facts"
            " (theory_id, kind, key, value_json, established_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("deadline_drift", FACT_KIND, "all", json.dumps(when), when))


def days_since_capture(conn, now: str | None = None) -> float | None:
    """None if never captured. >14 means top it up -- see RUNBOOK.md."""
    row = conn.execute(
        "SELECT value_json FROM theory_facts WHERE theory_id='deadline_drift'"
        " AND kind=? AND key='all'", (FACT_KIND,)).fetchone()
    if row is None:
        return None
    then = dt.datetime.fromisoformat(json.loads(row[0]))
    ref = (dt.datetime.fromisoformat(now) if now
           else dt.datetime.now(dt.timezone.utc))
    return (ref - then).total_seconds() / 86400.0


def superset_series(board) -> list[str]:
    """Every series holding a by-deadline market, with NO exclusions applied.

    **Capture is not classification, and only capture is perishable.**
    The allowlist (70 series) is a *screen* decision -- it was chosen on
    2026-08-29 to keep tier A when a structural LLM gate still cost the
    tier, and it can be revisited any day. The settled payloads cannot:
    Kalshi archives them ~60 days after close, so a market outside
    today's screen that is wanted by tomorrow's is gone.

    So the walk is driven by the widest defensible rule -- the
    by-deadline phrasing alone -- and every exclusion (threshold,
    scheduled certainty, multi-destination, partition) is applied
    afterwards, offline, over payloads already on disk. Over-capturing
    costs a few minutes of fetches; under-capturing is unrecoverable.

    The excluded families are worth having for a second reason: they are
    the **negative control** for any gate that claims to remove them.
    """
    from theories.deadline_drift.screen import BY_DEADLINE
    return sorted({m.series_ticker for m in board
                   if m.series_ticker and BY_DEADLINE.search(m.rules_primary or "")})


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools import board as bt, db
    from theories.deadline_drift import screen as dd
    wide = "--wide" in sys.argv
    platform = "--platform" in sys.argv
    conn = db.connect()
    kwargs = {}
    if platform:
        # Platform-wide: the series list cannot be filtered by market text
        # up front (there is none until the walk fetches it), so the
        # by-deadline rule moves into `raw_filter` and runs per market,
        # before normalize. Page cap guards the combinatorial shards.
        import re as _re
        _BD = dd.BY_DEADLINE

        def _by_deadline(raw):
            text = " ".join(str(raw.get(k) or "") for k in
                            ("title", "subtitle", "yes_sub_title",
                             "rules_primary"))
            return bool(_BD.search(text))

        series = platform_series()
        kwargs = {"raw_filter": _by_deadline, "max_pages": 15}
        print(f"walking {len(series)} PLATFORM series "
              f"(by-deadline filtered at the page, 15-page cap)...")
    elif wide:
        board = bt.get_board(conn)
        series = superset_series(board)
        print(f"walking {len(series)} by-deadline series (WIDE superset)...")
    else:
        board = bt.get_board(conn)
        series = sorted({m.series_ticker for m in dd.population(board)})
        print(f"walking {len(series)} allowlist series...")
    print(collect(series, **kwargs))
    mark_captured(conn)
    print("capture date stamped in theory_facts")

    # The live screen's learned exclusions are derived from exactly the
    # data this walk just changed, so rebuilding them here is what keeps
    # them from going stale in the one direction that matters: a family
    # that starts settling like a partition stays in the population until
    # somebody remembers to rebuild. Coupling it to the capture means
    # nobody has to remember. Seconds, against a walk that takes minutes.
    from theories.deadline_drift import population as pop_facts
    f = pop_facts.save()
    print(f"population facts rebuilt from {f['built_from_markets']} markets: "
          f"{len(f['partition_families'])} partition families, "
          f"{len(f['branch_families'])} branch families")
