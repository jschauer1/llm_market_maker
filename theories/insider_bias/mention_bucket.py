"""insider_bias v3 — the mechanical MENTION-family sub-path.

**This is an EXTENSION of insider_bias, not a replacement of it, a revision
of it, or a new version of its thesis.** The informed-minority hypothesis in
THEORY.md's Hypothesis section is untouched; `gate.py`, the prompts, and
Stage 3 are untouched; the 44 v1/v2 LLM-judged live rows are untouched and
remain their own comparable cohort. This module adds a second, independent
way for the insider_bias *theory folder* to produce opportunities, discovered
as a side effect of backtesting the first path's screen -- it does not
supersede anything already there.

A second, wholly separate decision path alongside the theory's LLM-judged
main pipeline (screen -> gate -> analysis -> final review). This one has no
judgment stage at all: `screen.is_mention_family` identifies the family, the
2026-08-24 tier A backtest (`run_id=backtest-2026-08-24-stage1-90d`) supplies
a MEASURED bucket rate from real settled history (n=116, win_rate=87.1%),
and `tools.buckets.edge_for` turns that into a mechanical `edge_pts_net`.
`edge_basis='measured'` — candidates from this path arrive with an edge
already attached and are recommendable without a research pass, per
CLAUDE.md's "pipelines propose, judgment disposes": a theory that computes
its edge mechanically needs no interpretation, unlike `insider_bias`'s main
path, where a screen hit is only a candidate until Stage 3 reviews it.

Why this bumped the theory to v3 rather than folding into v2: it is a
different decision procedure sitting *alongside* the LLM-judged path, not a
change to it. `gate.py`, the prompts, and Stage 3 are untouched; the 44 live
v2 rows (settling Aug 24-Sep 5) stay their own comparable cohort.

**The measured rate is bootstrapped from a backtest, not this path's own
live history — say so every time it is reported.** It held on one 90-day
window and has never been tested going forward. Read "measured" here as
"measured once", not "proven durable". The MEASURED_RATE_RUN_ID constant
below names exactly which run it came from, so that claim stays checkable.

**Every candidate in this bucket gets the SAME probability (0.871).** There
is no per-market signal distinguishing one mention market from another --
the model only knows the family's aggregate historical rate, not which
specific market is more likely to hit. Ranking by `edge_pts_net` is
therefore equivalent to ranking by *lowest entry price* within the
qualifying band: cheaper favorites have more room between their price and
0.871. That is the best a purely mechanical model can do; it is not the
same claim as "these 20 are individually more likely to win than those
other 20" — every candidate in the bucket is equally likely to win, by
construction. Say this plainly when reporting results, not just here.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from tools import buckets, ledger, provenance, score
from tools.sizing import fee_pts
from theories.insider_bias import screen

BUCKET = "mention_family"
THEORY_ID = "insider_bias"
LIVE_VERSION = 3

#: Where the measured rate for BUCKET comes from -- a specific backtest run
#: at v2, not this path's own history. See module docstring.
MEASURED_RATE_THEORY_VERSION = 2
MEASURED_RATE_RUN_MODE = "backtest"
MEASURED_RATE_RUN_ID = "backtest-2026-08-24-stage1-90d"

#: No prior needed: the backtest's n=116 already clears buckets.MIN_BUCKET_N,
#: so edge_for always returns the measured rate for this bucket, never a
#: prior placeholder. Kept explicit (not omitted) so a caller passing PRIORS
#: doesn't have to guess what happens below MIN_BUCKET_N.
PRIORS = {BUCKET: 0.0}


def find_candidates(
    board: list[dict],
    now: datetime | None = None,
    max_days_ahead: float = screen.MAX_DAYS_AHEAD,
) -> list[dict]:
    """Live board -> screen-eligible markets in the mention family.

    Reuses `screen.screen()` unmodified (price band, spread, volume,
    `is_excluded`) and narrows to one family on top -- this is not a new
    screen, it is the existing one filtered further. `max_days_ahead`
    defaults to the screen's own validated 14 days; pass a larger value to
    preview what is coming (see `rank_preview` -- a wider window changes
    what edge_basis a caller should honestly attach, so `rank`/`rank_preview`
    are two different functions on purpose, not one function with a flag
    that is easy to call the wrong way).
    """
    hits = screen.screen(board, now=now, max_days_ahead=max_days_ahead)
    return [
        h for h in hits
        if screen.is_mention_family(h.get("series_ticker") or h["ticker"])
    ]


def measured_rate(conn: sqlite3.Connection) -> dict:
    """The bucket_rates() dict `buckets.edge_for` expects, for BUCKET only."""
    return score.bucket_rates(
        conn, THEORY_ID, MEASURED_RATE_THEORY_VERSION,
        run_mode=MEASURED_RATE_RUN_MODE, run_id=MEASURED_RATE_RUN_ID,
    )


def rank(candidates: list[dict], rates: dict, top_n: int = 20) -> list[dict]:
    """Candidates with mechanical edge attached, best edge first.

    Every candidate shares BUCKET's one measured probability, so this is
    equivalent to sorting by lowest entry price within the qualifying band
    -- see module docstring on why that is not the same as "most likely to
    win" market-by-market.
    """
    scored = []
    for c in candidates:
        edge_pts_net, edge_basis = buckets.edge_for(
            BUCKET, c["entry_price"], rates, PRIORS
        )
        scored.append({**c, "edge_pts_net": edge_pts_net, "edge_basis": edge_basis})
    scored.sort(key=lambda c: c["edge_pts_net"], reverse=True)
    return scored[:top_n]


def rank_preview(
    candidates: list[dict],
    validated_rates: dict,
    top_n: int = 20,
) -> list[dict]:
    """Edge estimate for candidates OUTSIDE the backtest-validated 14-day
    window (find_candidates called with max_days_ahead > screen.MAX_DAYS_AHEAD).

    Always returns `edge_basis='model'`, never `'measured'`.  `'measured'` is
    reserved for a bucket's own accumulated evidence (`tools/buckets.py`),
    and no market has ever settled from this wider horizon -- the backtest
    only ever evaluated eligibility inside the 14-day window (see
    `backtest.py` module docstring point 3). Applying that 14-day rate here
    is a modeling assumption (nothing about the mention family obviously
    changes with days-to-close, but that is an assumption, not something
    this specific horizon has demonstrated), so it is labeled `'model'`,
    which is honest about being a calculation rather than borrowing
    `'measured'`'s stronger claim.
    """
    measured = validated_rates.get(BUCKET)
    probability = (
        measured["win_rate"]
        if measured and measured.get("n", 0) >= buckets.MIN_BUCKET_N
        else None
    )

    scored = []
    for c in candidates:
        if probability is None:
            edge_pts_net = 0.0
        else:
            gross = (probability - c["entry_price"]) * 100.0
            edge_pts_net = gross - fee_pts(c["entry_price"])
        scored.append({**c, "edge_pts_net": edge_pts_net, "edge_basis": "model"})
    scored.sort(key=lambda c: c["edge_pts_net"], reverse=True)
    return scored[:top_n]


def record_provenance(conn: sqlite3.Connection, run_id: str) -> None:
    """This path has no LLM anywhere in it, but the theory-level
    `uses_llm_judgment` flag applies to every run regardless of which path
    produced it (see `tools/provenance.py`), so every run_id still needs a
    row -- `model='none (deterministic)'`, same convention as `gate.py`.
    """
    provenance.record_judgment_run(
        conn,
        run_id=run_id,
        theory_id=THEORY_ID,
        theory_version=LIVE_VERSION,
        stage="other",
        model="none (deterministic)",
        prompt_path="theories/insider_bias/mention_bucket.py",
        web_search=False,
    )


def record(
    conn: sqlite3.Connection,
    ranked: list[dict],
    run_id: str,
    run_mode: str = "live",
    confidence: str = BUCKET,
) -> list[int]:
    """Write `ranked` to the ledger. Returns the opportunity ids.

    `disposition` stays the default `'screened'` -- for `edge_basis=
    'measured'` rows that means nothing needed to interpret them (see
    CLAUDE.md: "screened... because nothing interpreted them, read that as
    needed no interpretation"); for `'model'` rows from `rank_preview` it
    means the same mechanically, though the honest caveat about an untested
    horizon travels in `rationale` either way.

    Pass `confidence` explicitly for anything from `rank_preview` -- a
    distinct bucket name (e.g. `f"{BUCKET}_preview_30d"`) so a future
    `score.bucket_rates()` call never pools an untested-horizon population
    into the validated 14-day bucket's measured rate. Defaults to `BUCKET`
    for `rank()` output, where that pooling is exactly what is wanted.
    """
    record_provenance(conn, run_id)
    ids = []
    for c in ranked:
        basis_note = (
            f"measured win_rate=0.871 (n=116, {MEASURED_RATE_RUN_ID})"
            if c["edge_basis"] == "measured"
            else (
                f"win_rate=0.871 from {MEASURED_RATE_RUN_ID} APPLIED AS AN "
                f"EXTRAPOLATION to a days-to-close horizon the backtest "
                f"never tested (>{screen.MAX_DAYS_AHEAD:.0f} days) -- a "
                f"modeling assumption, not a measurement of this population"
            )
        )
        opp_id, _ = ledger.record_opportunity(
            conn,
            theory_id=THEORY_ID,
            theory_version=LIVE_VERSION,
            kalshi_ticker=c["ticker"],
            outcome=c["fav_side"],
            entry_price=c["entry_price"],
            edge_pts_net=c["edge_pts_net"],
            run_mode=run_mode,
            run_id=run_id,
            spread_at_call=c.get("spread"),
            volume_at_call=c.get("volume"),
            edge_basis=c["edge_basis"],
            confidence=confidence,
            rationale=(
                f"Mechanical mention_family bucket, no judgment applied: "
                f"{basis_note}. See mention_bucket.py module docstring for "
                f"why every candidate in this bucket carries the same "
                f"probability."
            ),
            evidence_source="kalshi",
        )
        ids.append(opp_id)
    return ids
