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

SAMPLE_EVENTS = 200
BATCH_SIZE = 25

#: Per-variant config: (run_id, seed). A second sample (`s200b`) replays
#: the identical procedure on fresh events — pass earlier variants'
#: manifests via --exclude-events-from so the samples never overlap, which
#: is what makes round two a true replication (its pre-registered cells
#: carry full weight, no post-hoc discount).
VARIANTS = {
    "s200": ("backtest-2026-08-26-insider-judged-s200", 20260826),
    "s200b": ("backtest-2026-08-26-insider-judged-s200b", 20260827),
    # s57: the remainder — with s200 and s200b excluded this drains the
    # pool, completing 100% judgment coverage of the gate-plausible
    # population in backtest-2026-08-25-insider-fullcov.
    "s57": ("backtest-2026-08-26-insider-judged-s57", 20260828),
    # g100: a GATE-VALIDATION experiment, not a bet-rule run — samples the
    # GATED-OUT population to measure the gate's false-negative rate (does
    # judgment find conviction in what the gate discards?). exp/ run id on
    # purpose: pooled scores and bucket_rates exclude it by convention, so
    # a different population can never leak into the theory's track record.
    "g100": ("exp/2026-08-26-insider-judged-gated100", 20260829),
}

#: Which side of the gate each variant samples, and how many events.
VARIANT_POOL = {"g100": "gated"}  # default: "plausible"
VARIANT_SIZE = {"g100": 100}      # default: SAMPLE_EVENTS

BUCKETS = ("strong", "moderate", "weak")


def variant_paths(variant: str) -> tuple[str, int, Path]:
    run_id, seed = VARIANTS[variant]
    return run_id, seed, Path(__file__).parent / "backtests" / f"judged-{variant}"


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
    # Reads the fullcov run's own attempt, not the position rollup: today
    # this works "by luck" because fullcov happens to be the earliest run
    # for every one of these positions, so opportunities.run_id still
    # equals SOURCE_RUN_ID -- but a position-identity merge always keeps
    # the *earliest* run_id on the rollup, so filtering there breaks the
    # moment fullcov is not first (attempt fidelity spec, 2026-08-27 sec
    # 9). o.kalshi_ticker/o.outcome/o.theory_id are identity, not
    # per-attempt. fullcov records exactly one decision_date per market
    # (replay_market returns the first qualifying day only), so this exact
    # run_id match cannot fan out one position into more than one row.
    return conn.execute(
        """SELECT o.kalshi_ticker, o.outcome, a.entry_price,
                  a.spread_at_call, a.volume_at_call, a.extra_json
           FROM opportunity_attempts a
           JOIN opportunities o ON o.id = a.opportunity_id
           WHERE a.run_id = ? AND o.theory_id = ?""",
        (SOURCE_RUN_ID, THEORY_ID),
    ).fetchall()


def sample(conn: sqlite3.Connection, run_id: str, seed: int, root: Path,
           excluded: set[str], pool: str = "plausible",
           n_events: int = SAMPLE_EVENTS) -> None:
    """Draw the event sample and write manifest + per-batch payloads."""
    by_event: dict[str, list[dict]] = defaultdict(list)
    for r in _source_rows(conn):
        x = json.loads(r["extra_json"])
        if pool == "plausible" and x.get("gate_would_reject"):
            continue
        if pool == "gated" and not x.get("gate_would_reject"):
            continue
        if x["event_ticker"] in excluded:
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
    rng = random.Random(seed)
    chosen = sorted(rng.sample(events, min(n_events, len(events))))
    print(f"{pool} events after exclusions: {len(events)} "
          f"({len(excluded)} excluded); sampled: {len(chosen)}")

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
    root.mkdir(parents=True, exist_ok=True)
    manifest = {"run_id": run_id, "source_run": SOURCE_RUN_ID, "seed": seed,
                "sampled_events": len(entries), "batches": []}
    for i in range(0, len(entries), BATCH_SIZE):
        batch = entries[i:i + BATCH_SIZE]
        bid = i // BATCH_SIZE + 1
        payload = [{k: e[k] for k in
                    ("event_ticker", "series_ticker", "title", "close_time",
                     "markets")} for e in batch]
        pipeline.assert_blind(payload)
        ppath = root / f"batch_{bid:02d}.payload.json"
        ppath.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        manifest["batches"].append({
            "batch": bid, "n_events": len(batch),
            "n_markets": sum(len(e["markets"]) for e in batch),
            "as_of": max(e["as_of"] for e in batch),
            "payload": ppath.name,
            "verdicts": f"batch_{bid:02d}.verdicts.json",
            "events": [e["event_ticker"] for e in batch],
        })
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8")
    (root / "row_index.json").write_text(json.dumps(
        {ev: by_event[ev] for ev in chosen}, indent=1), encoding="utf-8")
    print(f"wrote {len(manifest['batches'])} batch payloads to {root}")


def ingest(conn: sqlite3.Connection, batch: int, model: str | None,
           run_id: str, root: Path) -> None:
    """Record one batch's verdicts. Idempotent; safe to re-run."""
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    row_index = json.loads(
        (root / "row_index.json").read_text(encoding="utf-8"))
    spec = next(b for b in manifest["batches"] if b["batch"] == batch)
    vpath = root / spec["verdicts"]
    verdicts = {v["event_ticker"]: v
                for v in json.loads(vpath.read_text(encoding="utf-8"))}
    missing = [e for e in spec["events"] if e not in verdicts]
    if missing:
        raise ValueError(f"batch {batch} verdicts missing events: {missing}")

    if model:
        provenance.record_judgment_run(
            conn, run_id=run_id, theory_id=THEORY_ID,
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
                run_mode="backtest", run_id=run_id,
                decision_date=r["entry_day_iso"][:10],
                spread_at_call=r["spread_at_call"],
                volume_at_call=r["volume_at_call"],
                edge_basis="prior", confidence=v["bucket"],
                judged_blind=True,
                rationale=(f"[batch {batch}] insider_group="
                           f"{v.get('insider_group')!r}: {v.get('rationale')}"),
                evidence_source="kalshi",
                extra_json=json.dumps({
                    "backtest_run": run_id, "source_run": SOURCE_RUN_ID,
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
          f"{written} rows recorded under {run_id}")


def status(root: Path) -> None:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for b in manifest["batches"]:
        have = (root / b["verdicts"]).exists()
        print(f"batch {b['batch']:02d}: events={b['n_events']:3d} "
              f"as_of={b['as_of']} verdicts={'YES' if have else 'no'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["sample", "ingest", "status"])
    parser.add_argument("--variant", choices=sorted(VARIANTS),
                        default="s200")
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--model", default=None,
                        help="judging model id; required on first ingest")
    parser.add_argument("--exclude-events-from", type=Path, action="append",
                        default=[],
                        help="manifest.json of an earlier sample whose "
                             "events must not be re-drawn (repeatable)")
    args = parser.parse_args()
    run_id, seed, root = variant_paths(args.variant)
    if args.mode == "status":
        status(root)
        return
    conn = db.connect()
    try:
        if args.mode == "sample":
            excluded: set[str] = set()
            for mpath in args.exclude_events_from:
                m = json.loads(mpath.read_text(encoding="utf-8"))
                for b in m["batches"]:
                    excluded.update(b["events"])
            sample(conn, run_id, seed, root, excluded,
                   pool=VARIANT_POOL.get(args.variant, "plausible"),
                   n_events=VARIANT_SIZE.get(args.variant, SAMPLE_EVENTS))
        else:
            if args.batch is None:
                parser.error("--batch is required for ingest")
            ingest(conn, args.batch, args.model, run_id, root)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
