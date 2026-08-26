"""insider_judgment — tier B judged backtest over sampled fullcov events.

Judges a seeded random sample of gate-PLAUSIBLE events from the tier-A
full-coverage run (`backtest-2026-08-25-insider-fullcov`) with the
theory's real analysis stage, to measure whether judgment adds edge on
top of screen + gate. Markets here resolved 2026-06..08 — after the
judging model's knowledge cutoff — so with web search off this is
genuinely tier B.

**Built to lose usage at any moment (user requirement, 2026-08-25).**
The unit of survival is the batch:

1. `sample` writes everything the judgment needs to disk up front — a
   manifest and one blind payload file per batch of events — under
   `backtests/judged-<run>/` in this folder (committed, not scratch).
2. Each judgment subagent reads its payload file and writes its verdicts
   file itself; the orchestrating session then runs `ingest` on that one
   batch, which records the rows and settlements immediately. Only then
   is the next batch dispatched.
3. `ingest` is idempotent per batch (re-recording an already-ingested
   row is a dedup update, not a duplicate), and any batch whose verdicts
   file exists can be ingested by a *future* session even if the session
   that dispatched it died before ingesting.
4. `score` reports bucket calibration over however many batches landed.

Dispatch (done by the operator session, not this module): one subagent
per batch, model as agreed (sonnet), **web search off**, prompt =
`prompts/analysis.md` with `{input_path}`/`{output_path}` pointing at the
batch files and `{today}` set to the batch's `as_of` date from the
manifest — the entry-day as-of, not the real today, because telling the
model the real date leaks that tapings/votes/announcements "must have
happened by now". Record provenance at first ingest via `--model`.

Payload discipline: fields come from the history cache's settled-market
payloads (fetched live for any market the cache lacks), whitelisted and
checked by the same `pipeline.assert_blind` the live path uses.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from tools import db, ledger, provenance, score
from tools.http import get_json
from tools.kalshi import cache as history_cache
from tools.kalshi.markets import BASE_URL
from theories.insider_bias.insider_judgment import pipeline

THEORY_ID = "insider_judgment"
THEORY_VERSION = 3
SOURCE_RUN_ID = "backtest-2026-08-25-insider-fullcov"
RUN_ID = "backtest-2026-08-26-insider-judged-s200"

SAMPLE_EVENTS = 200
BATCH_SIZE = 25
SEED = 20260826

ROOT = Path(__file__).parent / "backtests" / "judged-s200"

BUCKETS = ("strong", "moderate", "weak")


def _market_payload(cache_conn: sqlite3.Connection, ticker: str) -> dict:
    """Raw market payload from the history cache, else fetched live."""
    row = cache_conn.execute(
        "SELECT payload FROM settled_markets WHERE ticker = ?", (ticker,)
    ).fetchone()
    if row is not None:
        return json.loads(row[0])
    payload = get_json(f"{BASE_URL}/markets/{ticker}")
    market = payload.get("market") or {}
    if not market:
        raise ValueError(f"no market payload retrievable for {ticker}")
    return market


def _source_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT o.kalshi_ticker, o.outcome, o.entry_price,
                  o.spread_at_call, o.volume_at_call, o.extra_json
           FROM opportunities o
           WHERE o.run_id = ? AND o.theory_id = ?""",
        (SOURCE_RUN_ID, THEORY_ID),
    ).fetchall()


def sample(conn: sqlite3.Connection) -> None:
    """Draw the event sample and write manifest + per-batch payloads."""
    by_event: dict[str, list[dict]] = defaultdict(list)
    for r in _source_rows(conn):
        x = json.loads(r["extra_json"])
        if x.get("gate_would_reject"):
            continue
        by_event[x["event_ticker"]].append({
            "ticker": r["kalshi_ticker"], "outcome": r["outcome"],
            "entry_price": r["entry_price"],
            "spread_at_call": r["spread_at_call"],
            "volume_at_call": r["volume_at_call"],
            "series_ticker": x["series_ticker"],
            "event_ticker": x["event_ticker"],
            "entry_day_iso": x["entry_day_iso"],
            "days_to_close_at_entry": x["days_to_close_at_entry"],
        })
    events = sorted(by_event)
    rng = random.Random(SEED)
    chosen = sorted(rng.sample(events, min(SAMPLE_EVENTS, len(events))))
    print(f"gate-plausible events: {len(events)}; sampled: {len(chosen)}")

    cache_conn = history_cache.connect()
    entries = []
    for ev in chosen:
        rows = by_event[ev]
        markets = []
        for r in rows:
            raw = _market_payload(cache_conn, r["ticker"])
            markets.append({
                "ticker": r["ticker"],
                "title": raw.get("title"),
                "rules_primary": raw.get("rules_primary"),
                "rules_secondary": raw.get("rules_secondary"),
                "close_time": raw.get("close_time"),
            })
        first = rows[0]
        entries.append({
            "event_ticker": ev,
            "series_ticker": first["series_ticker"],
            "title": (markets[0].get("title") or "").split(" - ")[0] or None,
            "close_time": markets[0].get("close_time"),
            # judge as-of the earliest entry among the event's hits: the
            # conservative as-of (nothing "must have happened by now")
            "as_of": min(r["entry_day_iso"] for r in rows)[:10],
            "markets": markets,
        })
    cache_conn.close()

    # Batch by as_of so each subagent call carries one honest {today}.
    entries.sort(key=lambda e: (e["as_of"], e["event_ticker"]))
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {"run_id": RUN_ID, "source_run": SOURCE_RUN_ID, "seed": SEED,
                "sampled_events": len(entries), "batches": []}
    for i in range(0, len(entries), BATCH_SIZE):
        batch = entries[i:i + BATCH_SIZE]
        bid = i // BATCH_SIZE + 1
        payload = [{k: e[k] for k in
                    ("event_ticker", "series_ticker", "title", "close_time",
                     "markets")} for e in batch]
        pipeline.assert_blind(payload)
        ppath = ROOT / f"batch_{bid:02d}.payload.json"
        ppath.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        manifest["batches"].append({
            "batch": bid, "n_events": len(batch),
            "n_markets": sum(len(e["markets"]) for e in batch),
            "as_of": max(e["as_of"] for e in batch),
            "payload": ppath.name,
            "verdicts": f"batch_{bid:02d}.verdicts.json",
            "events": [e["event_ticker"] for e in batch],
        })
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8")
    (ROOT / "row_index.json").write_text(json.dumps(
        {ev: by_event[ev] for ev in chosen}, indent=1), encoding="utf-8")
    print(f"wrote {len(manifest['batches'])} batch payloads to {ROOT}")


def ingest(conn: sqlite3.Connection, batch: int, model: str | None) -> None:
    """Record one batch's verdicts. Idempotent; safe to re-run."""
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    row_index = json.loads(
        (ROOT / "row_index.json").read_text(encoding="utf-8"))
    spec = next(b for b in manifest["batches"] if b["batch"] == batch)
    vpath = ROOT / spec["verdicts"]
    verdicts = {v["event_ticker"]: v
                for v in json.loads(vpath.read_text(encoding="utf-8"))}
    missing = [e for e in spec["events"] if e not in verdicts]
    if missing:
        raise ValueError(f"batch {batch} verdicts missing events: {missing}")

    if model:
        provenance.record_judgment_run(
            conn, run_id=RUN_ID, theory_id=THEORY_ID,
            theory_version=THEORY_VERSION, stage="analysis", model=model,
            prompt_path="theories/insider_bias/insider_judgment/prompts/analysis.md",
            web_search=False,
        )
    written = 0
    for ev in spec["events"]:
        v = verdicts[ev]
        if v["bucket"] not in BUCKETS:
            raise ValueError(f"{ev}: bad bucket {v['bucket']!r}")
        for r in row_index[ev]:
            ledger.record_opportunity(
                conn, theory_id=THEORY_ID, theory_version=THEORY_VERSION,
                kalshi_ticker=r["ticker"], outcome=r["outcome"],
                entry_price=r["entry_price"], edge_pts_net=0.0,
                run_mode="backtest", run_id=RUN_ID,
                spread_at_call=r["spread_at_call"],
                volume_at_call=r["volume_at_call"],
                edge_basis="prior", confidence=v["bucket"],
                judged_blind=True,
                rationale=(f"[batch {batch}] insider_group="
                           f"{v.get('insider_group')!r}: {v.get('rationale')}"),
                evidence_source="kalshi",
                extra_json=json.dumps({
                    "backtest_run": RUN_ID, "source_run": SOURCE_RUN_ID,
                    "batch": batch,
                    "event_ticker": ev,
                    "series_ticker": r["series_ticker"],
                    "entry_day_iso": r["entry_day_iso"],
                    "days_to_close_at_entry": r["days_to_close_at_entry"],
                    "rules_diverge_from_title":
                        v.get("rules_diverge_from_title"),
                    "researched": v.get("researched"),
                }),
            )
            written += 1
    print(f"batch {batch}: {len(spec['events'])} events, "
          f"{written} rows recorded under {RUN_ID}")


def status() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    for b in manifest["batches"]:
        have = (ROOT / b["verdicts"]).exists()
        print(f"batch {b['batch']:02d}: events={b['n_events']:3d} "
              f"as_of={b['as_of']} verdicts={'YES' if have else 'no'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["sample", "ingest", "status"])
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--model", default=None,
                        help="judging model id; required on first ingest")
    args = parser.parse_args()
    if args.mode == "status":
        status()
        return
    conn = db.connect()
    try:
        if args.mode == "sample":
            sample(conn)
        else:
            if args.batch is None:
                parser.error("--batch is required for ingest")
            ingest(conn, args.batch, args.model)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
