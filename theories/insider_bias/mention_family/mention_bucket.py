"""mention_family — a fully mechanical theory, no LLM anywhere in it.

**Split out of `insider_bias` into its own theory on 2026-08-24.** It was
born as a side effect of backtesting `insider_bias`'s stage-1 screen
(`run_id=backtest-2026-08-24-stage1-90d` found this ticker family behaving
very differently from the rest of the screen's output), and for a few hours
lived inside `insider_bias` as a v3 sub-path. It moved out because it tests
a completely different kind of claim: `insider_bias`'s thesis is "a specific
identifiable group already knows," decided by LLM judgment; this theory's
claim is "this ticker-pattern family, priced by its own measured historical
win rate, beats its own price," decided by code. See THEORY.md's Hypothesis
section for the full reasoning on why one version number couldn't honestly
describe both. `insider_bias`'s v3 bump and its own Learnings/RUNBOOK.md
carry the discovery history; this theory's own history starts fresh from
that point, not from zero -- the backtest evidence moved with it (see
`migrate_from_insider_bias.py` in this folder, run once on 2026-08-24).

`screen.is_mention_family` used to live in `theories/insider_bias/screen.py`
and moved here in the same split -- it is this theory's classifier now, not
a stage of insider_bias's.

**Price-binned buckets, not one flat rate.** The first version of this
mechanism (while still inside insider_bias) used ONE probability (0.871,
the family's overall average) for every candidate regardless of price. That
was a real bug, caught by the user's own trading experience not matching
the model's output, and confirmed against the backtest data: win rate rises
sharply with price across the family --

    below 0.75:  n=37  win_rate=0.730  edge_net=+1.87pts  (barely above the price itself)
    0.75-0.85:   n=38  win_rate=0.868  edge_net=+6.38pts
    0.85+:       n=41  win_rate=1.000  edge_net=+7.88pts

`PRICE_BINS` below scores each candidate against its OWN bin, not a family
average.

**The `mention_family_85plus` bin's 100% win rate (n=41) is a striking
number and should be treated with real skepticism, not face value.** Zero
losses in 41 tries is strong evidence of a high win rate, not proof of
certainty -- the true rate is very likely below 100%, and `edge_for` will
compute a large edge for any 0.85-0.89 candidate in this bin precisely
because it takes the measured 1.0 at face value. This module applies no
shrinkage beyond `buckets.MIN_BUCKET_N` (the same convention every bucket
in this repo uses), so say this plainly whenever this bin's results are
reported.

**Volume is reported and used as a tiebreaker, not folded into the edge.**
Checked directly: the backtest data does not show volume as predictive of
win rate the way price does (bins bounce between +0.9 and +11pts with no
clean trend, and the highest-volume bin is n=4 -- too small to mean
anything). Higher volume matters for a different, real reason -- confidence
that the displayed price is actually fillable -- so `rank`/`rank_preview`
sort by `(edge_pts_net, volume)` descending: edge decides the ranking,
volume breaks ties and is always reported alongside so a human can weigh
execution risk themselves.

**Entry timing: most candidates only become eligible in the final days
before close, and this is structural, not a chosen delay strategy.** Of the
116 backtest hits, 36% first became screen-eligible on the literal last day
before close; only 12 were sitting as a favorite 10+ days out. Binned by
days-to-close at entry: `10-14d: n=12, edge_net=+10.2pts` /
`7-10d: n=9, edge_net=-2.2pts` / `4-7d: n=17, edge_net=-3.7pts` /
`0-4d: n=78, edge_net=+7.5pts` -- noisy and confounded (different markets
selected by when each crossed into favorite territory, not the same market
resampled at different entry times), but the practical upshot is real:
running this theory's screen only far in advance will miss most of what it
finds. It needs to run close to individual markets' close dates, ideally as
a recurring check.

**The measured rates are bootstrapped from one backtest window, not this
theory's own live history — say so every time they are reported.** They
held on one 90-day window and have never been tested going forward. Read
"measured" here as "measured once", not "proven durable".
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from tools import buckets, ledger, provenance, score
from tools.sizing import fee_pts
from theories.insider_bias import screen

THEORY_ID = "mention_family"
THEORY_VERSION = 1

#: (low, high, bucket_name) -- low inclusive, high exclusive except the last.
#: Boundaries chosen from where the backtest data actually breaks, not round
#: numbers: see module docstring for the per-bin win rates that justify them.
PRICE_BINS: tuple[tuple[float, float, str], ...] = (
    (0.65, 0.75, "mention_family_lt75"),
    (0.75, 0.85, "mention_family_75_85"),
    (0.85, 0.98, "mention_family_85plus"),
)

#: Where the measured rates come from -- the backtest run that discovered
#: this family, from when it was still inside insider_bias. See module
#: docstring and migrate_from_insider_bias.py.
MEASURED_RATE_RUN_MODE = "backtest"
MEASURED_RATE_RUN_ID = "backtest-2026-08-24-stage1-90d"

#: No prior needed for any bin: the backtest's smallest bin (n=37) already
#: clears buckets.MIN_BUCKET_N, so edge_for always returns a measured rate,
#: never a prior placeholder. Kept explicit so a caller passing PRIORS
#: doesn't have to guess what happens below MIN_BUCKET_N.
PRIORS: dict[str, float] = {name: 0.0 for _, _, name in PRICE_BINS}


def is_mention_family(series_ticker: str) -> bool:
    """True for "will X mention/say/do Y" series.

    Accepts either a series ticker (`KXTRUMPMENTION`) or a full market
    ticker (`KXTRUMPMENTION-26JUL01-MAKE`); the pattern only needs the
    series prefix, which a market ticker always carries.
    """
    return "MENTION" in series_ticker or series_ticker.endswith(("SAY", "ACT"))


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

    Reuses `theories.insider_bias.screen.screen()` unmodified (price band, spread, volume,
    `is_excluded`) and narrows to one family on top -- this theory does not
    define its own screen, it narrows the shared one. `max_days_ahead`
    defaults to the validated 14 days; pass a larger value to preview what
    is coming (see `rank_preview` -- a wider window changes what edge_basis
    a caller should honestly attach, so `rank`/`rank_preview` are two
    different functions on purpose, not one function with a flag that is
    easy to call the wrong way).
    """
    hits = screen.screen(board, now=now, max_days_ahead=max_days_ahead)
    return [
        h for h in hits
        if is_mention_family(h.get("series_ticker") or h["ticker"])
    ]


def measured_rate(conn: sqlite3.Connection) -> dict:
    """The bucket_rates() dict `buckets.edge_for` expects, all PRICE_BINS
    keys at once (one query returns every confidence bucket recorded under
    this run, not just one)."""
    return score.bucket_rates(
        conn, THEORY_ID, THEORY_VERSION,
        run_mode=MEASURED_RATE_RUN_MODE, run_id=MEASURED_RATE_RUN_ID,
    )


def _sort_key(c: dict) -> tuple[float, float]:
    return (c["edge_pts_net"], c.get("volume") or 0.0)


def rank(candidates: list[dict], rates: dict, top_n: int = 20) -> list[dict]:
    """Candidates with mechanical edge attached, best first.

    Each candidate is scored against its OWN price bin's measured rate
    (`bucket_for_price`), not one family-wide average. Sorted by
    `(edge_pts_net, volume)` descending: edge decides the ranking, volume
    only breaks ties (see module docstring on why volume is not itself part
    of the edge).
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
    only ever evaluated eligibility inside the 14-day window. Applying a
    bin's 14-day rate here is a modeling assumption (nothing about the
    mention family obviously changes with days-to-close, but that is an
    assumption, not something this specific horizon has demonstrated), so
    it is labeled `'model'`, honest about being a calculation rather than
    borrowing `'measured'`'s stronger claim. Same price-bin lookup and
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
    """This theory declares no LLM judgment (`uses_llm_judgment=False`), so
    `record_opportunity` does not require this -- called anyway for the same
    reason `gate.py` records itself despite being code: the artifact that
    governed a decision should be recoverable, not just optional metadata.
    `model='none (deterministic)'`, same convention as insider_bias's gate.
    """
    provenance.record_judgment_run(
        conn,
        run_id=run_id,
        theory_id=THEORY_ID,
        theory_version=THEORY_VERSION,
        stage="other",
        model="none (deterministic)",
        prompt_path="theories/insider_bias/mention_family/mention_bucket.py",
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
        bin_rate_note = f"measured rate for bucket {c['bucket']} ({MEASURED_RATE_RUN_ID})"
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
            theory_version=THEORY_VERSION,
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
