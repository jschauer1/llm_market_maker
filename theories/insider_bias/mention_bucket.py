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
measured bucket rates from real settled history, and `tools.buckets.edge_for`
turns those into a mechanical `edge_pts_net`. `edge_basis='measured'` —
candidates from this path arrive with an edge already attached and are
recommendable without a research pass, per CLAUDE.md's "pipelines propose,
judgment disposes": a theory that computes its edge mechanically needs no
interpretation, unlike `insider_bias`'s main path, where a screen hit is
only a candidate until Stage 3 reviews it.

Why this bumped the theory to v3 rather than folding into v2: it is a
different decision procedure sitting *alongside* the LLM-judged path, not a
change to it. `gate.py`, the prompts, and Stage 3 are untouched; the 44 live
v2 rows (settling Aug 24-Sep 5) stay their own comparable cohort.

**The measured rate is bootstrapped from a backtest, not this path's own
live history — say so every time it is reported.** It held on one 90-day
window and has never been tested going forward. Read "measured" here as
"measured once", not "proven durable".

**Price-binned buckets, not one flat rate — this was a real bug, caught and
fixed 2026-08-24.** The first version of this module used ONE probability
(0.871, the mention family's overall average) for every candidate regardless
of price. That is wrong, and the backtest data says so directly: win rate
rises sharply with price across the family --

    below 0.75:  n=37  win_rate=0.730  edge_net=+1.87pts  (barely above the price itself)
    0.75-0.85:   n=38  win_rate=0.868  edge_net=+6.38pts
    0.85+:       n=41  win_rate=1.000  edge_net=+7.88pts

Treating a $0.65 favorite as equally likely to hit as a $0.95 one (both
"the mention family's 87.1%") overstated the cheap end's edge and
understated the strong end's -- the first live run ranked $0.65-0.70
candidates highest, which the data says is close to the WORST place to be
in this family, not the best. `PRICE_BINS` below fixes this: each candidate
is scored against ITS OWN bin's measured rate, not the family average.

**The `mention_family_85plus` bin's 100% win rate (n=41) is a striking
number and should be treated with real skepticism, not face value.** Zero
losses in 41 tries is strong evidence of a high win rate, not proof of
certainty -- the true rate is very likely below 100%, and `edge_for` will
compute a large edge for any 0.85-0.89 candidate in this bin precisely
because it takes the measured 1.0 at face value. This module does not apply
any shrinkage beyond `buckets.MIN_BUCKET_N` (the same convention every other
bucket in this repo uses -- inventing bespoke shrinkage for one bucket would
be an inconsistent, one-off fix), so say this plainly whenever this bin's
results are reported rather than let a future reader treat +8pts as as solid
as the 0.75-0.85 bin's +6.38pts.

**Volume is reported and used as a tiebreaker, not folded into the edge.**
Checked directly: the backtest data does not show volume as predictive of
win rate the way price does (bins bounce between +0.9 and +11pts with no
clean trend, and the highest-volume bin is n=4 -- too small to mean
anything). Higher volume matters for a different, real reason -- confidence
that the displayed price is actually fillable -- so `rank`/`rank_preview`
sort by `(edge_pts_net, volume)` descending: edge decides the ranking,
volume breaks ties and is always reported alongside so a human can weigh
execution risk themselves.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from tools import buckets, ledger, provenance, score
from tools.sizing import fee_pts
from theories.insider_bias import screen

THEORY_ID = "insider_bias"
LIVE_VERSION = 3

#: (low, high, bucket_name) -- low inclusive, high exclusive except the last.
#: Boundaries chosen from where the backtest data actually breaks, not round
#: numbers: see module docstring for the per-bin win rates that justify them.
PRICE_BINS: tuple[tuple[float, float, str], ...] = (
    (0.65, 0.75, "mention_family_lt75"),
    (0.75, 0.85, "mention_family_75_85"),
    (0.85, 0.98, "mention_family_85plus"),
)

#: Where the measured rates come from -- a specific backtest run at v2, not
#: this path's own history. See module docstring.
MEASURED_RATE_THEORY_VERSION = 2
MEASURED_RATE_RUN_MODE = "backtest"
MEASURED_RATE_RUN_ID = "backtest-2026-08-24-stage1-90d"

#: No prior needed for any bin: the backtest's smallest bin (n=37) already
#: clears buckets.MIN_BUCKET_N, so edge_for always returns a measured rate,
#: never a prior placeholder. Kept explicit so a caller passing PRIORS
#: doesn't have to guess what happens below MIN_BUCKET_N.
PRIORS: dict[str, float] = {name: 0.0 for _, _, name in PRICE_BINS}


def bucket_for_price(price: float) -> str:
    """Which PRICE_BINS bucket a price falls into.

    Below the lowest bin's floor or at/above the highest bin's ceiling
    should not happen for anything that passed `screen.screen()` (favorite
    band is [0.65, 0.97]), but clamps rather than raises if it does --
    a boundary mismatch should not crash a live run.
    """
    for lo, hi, name in PRICE_BINS:
        if lo <= price < hi:
            return name
    return PRICE_BINS[0][2] if price < PRICE_BINS[0][0] else PRICE_BINS[-1][2]


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
    """The bucket_rates() dict `buckets.edge_for` expects, all PRICE_BINS
    keys at once (one query returns every confidence bucket recorded under
    this run, not just one)."""
    return score.bucket_rates(
        conn, THEORY_ID, MEASURED_RATE_THEORY_VERSION,
        run_mode=MEASURED_RATE_RUN_MODE, run_id=MEASURED_RATE_RUN_ID,
    )


def _sort_key(c: dict) -> tuple[float, float]:
    return (c["edge_pts_net"], c.get("volume") or 0.0)


def rank(candidates: list[dict], rates: dict, top_n: int = 20) -> list[dict]:
    """Candidates with mechanical edge attached, best first.

    Each candidate is scored against its OWN price bin's measured rate
    (`bucket_for_price`), not one family-wide average -- see module
    docstring on why that was a real bug in the first version of this
    module. Sorted by `(edge_pts_net, volume)` descending: edge decides
    the ranking, volume only breaks ties (see module docstring on why
    volume is not itself part of the edge).
    """
    scored = []
    for c in candidates:
        bucket = bucket_for_price(c["entry_price"])
        edge_pts_net, edge_basis = buckets.edge_for(
            bucket, c["entry_price"], rates, PRIORS
        )
        scored.append({
            **c, "edge_pts_net": edge_pts_net, "edge_basis": edge_basis,
            "bucket": bucket,
        })
    scored.sort(key=_sort_key, reverse=True)
    return scored[:top_n]


def rank_preview(
    candidates: list[dict],
    validated_rates: dict,
    top_n: int = 20,
) -> list[dict]:
    """Edge estimate for candidates OUTSIDE the backtest-validated 14-day
    window (find_candidates called with max_days_ahead > screen.MAX_DAYS_AHEAD).

    Always returns `edge_basis='model'`, never `'measured'`. `'measured'` is
    reserved for a bucket's own accumulated evidence (`tools/buckets.py`),
    and no market has ever settled from this wider horizon -- the backtest
    only ever evaluated eligibility inside the 14-day window (see
    `backtest.py` module docstring point 3). Applying a bin's 14-day rate
    here is a modeling assumption (nothing about the mention family
    obviously changes with days-to-close, but that is an assumption, not
    something this specific horizon has demonstrated), so it is labeled
    `'model'`, honest about being a calculation rather than borrowing
    `'measured'`'s stronger claim. Same price-bin lookup and
    `(edge_pts_net, volume)` sort as `rank`.
    """
    scored = []
    for c in candidates:
        bucket = bucket_for_price(c["entry_price"])
        measured = validated_rates.get(bucket)
        if measured and measured.get("n", 0) >= buckets.MIN_BUCKET_N:
            gross = (measured["win_rate"] - c["entry_price"]) * 100.0
            edge_pts_net = gross - fee_pts(c["entry_price"])
        else:
            edge_pts_net = 0.0
        scored.append({
            **c, "edge_pts_net": edge_pts_net, "edge_basis": "model",
            "bucket": bucket,
        })
    scored.sort(key=_sort_key, reverse=True)
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
    confidence_suffix: str = "",
) -> list[int]:
    """Write `ranked` to the ledger. Returns the opportunity ids.

    `disposition` stays the default `'screened'` -- for `edge_basis=
    'measured'` rows that means nothing needed to interpret them (see
    CLAUDE.md: "screened... because nothing interpreted them, read that as
    needed no interpretation"); for `'model'` rows from `rank_preview` it
    means the same mechanically, though the honest caveat about an untested
    horizon travels in `rationale` either way.

    Each row's `confidence` is its own price bin (`c["bucket"]`, set by
    `rank`/`rank_preview`) plus `confidence_suffix`. Pass a suffix (e.g.
    `"_preview_30d"`) for anything from `rank_preview` so a future
    `score.bucket_rates()` call never pools an untested-horizon population
    into the validated 14-day bins' measured rates. Leave it empty for
    `rank()` output, where that pooling into the validated bins is exactly
    what is wanted.
    """
    record_provenance(conn, run_id)
    ids = []
    for c in ranked:
        bin_rate_note = (
            f"measured rate for bucket {c['bucket']} "
            f"({MEASURED_RATE_RUN_ID})"
        )
        basis_note = (
            f"{bin_rate_note}, applied directly"
            if c["edge_basis"] == "measured"
            else (
                f"{bin_rate_note} APPLIED AS AN EXTRAPOLATION to a "
                f"days-to-close horizon the backtest never tested "
                f"(>{screen.MAX_DAYS_AHEAD:.0f} days) -- a modeling "
                f"assumption, not a measurement of this population"
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
            confidence=f"{c['bucket']}{confidence_suffix}",
            rationale=(
                f"Mechanical mention_family bucket, no judgment applied: "
                f"{basis_note}. Volume (${c.get('volume', 0):,.0f}) is a "
                f"tiebreaker only, not part of the edge -- see "
                f"mention_bucket.py module docstring."
            ),
            evidence_source="kalshi",
        )
        ids.append(opp_id)
    return ids
