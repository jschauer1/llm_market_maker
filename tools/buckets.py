"""Confidence buckets — measured probabilities instead of guessed ones.

LLMs are poorly calibrated probability estimators. They cluster on round
numbers, drift with phrasing, and anchor hard on any number already in
context — so asking a model for `q` while showing it the price mostly
measures the anchor.

This module is the alternative. A judgment step returns an ordinal bucket
("strong", "moderate", "weak"), and the bucket's own settled history
supplies the number.

**What a bucket contributes is an EDGE, not a probability.** "When this
theory says strong, the markets it picked beat their prices by 4 points"
is the transferable fact; "when it says strong it wins 78% of the time"
is not, because that 78% belongs to the particular prices those bets were
bought at. Reading the pooled win rate as a new candidate's probability
makes the claimed edge vary 1:1 with price — a constant, not a
calibration — which mechanically manufactures edge on anything cheaper
than the bucket rate and negative edge on anything dearer, whatever the
thesis says. That was the shape of this module until 2026-08-29 and it
produced two live runs' worth of junk on `insider_judgment`: 16 rows of
Taça de Portugal football, T20 cricket and app-download markets priced
just under a `weak` rate of 0.776.

The corrected formula also puts three things that had disagreed into
agreement:

- **the prior path**, which has always returned points of edge;
- **`score.compute_score`**, which GRADES a theory on
  `win_rate - price_implied_rate` — edge against the prices actually
  paid, exactly what `measured_gross` now returns;
- **`Edge.model_prob`**, which is now this candidate's own price plus the
  bucket's edge rather than a pooled rate describing other prices.

Until a bucket has both MIN_BUCKET_N settled results and MIN_BUCKET_DAYS
distinct settlement days, the theory's declared prior stands in and the
result is flagged `prior` so nobody mistakes a placeholder for a
measurement.
"""

from __future__ import annotations

from tools.sizing import fee_pts

MIN_BUCKET_N = 10

MIN_BUCKET_DAYS = 5
"""Distinct settlement days a bucket needs before it may speak.

Rows are not independent draws. The settlement-day clustering study
(`tickets/study/answer/2026-08-27-settlement-day-clustering/`) measured the same
screened population swinging +4.26 / −7.29 / +5.40 net across three
consecutive close-days, and `insider_judgment`'s `weak` bucket graduated
on 2026-08-28 from 17 rows that had **all settled on one night** — a
night of live-sport NO favourites that then defined what `weak` was
worth. A row count cannot see that; a day count can.

Five is a floor chosen to stop single-night graduation, not a power
calculation. `no_side_premium`'s pre-registration uses a stricter `n_days
>= 8` because it is resolving a specific 2-point claim; this bar only
decides whether a measurement replaces a placeholder.
"""


def measured_gross(
    bucket: str,
    rates: dict,
    min_n: int = MIN_BUCKET_N,
    min_days: int = MIN_BUCKET_DAYS,
) -> float | None:
    """The bucket's own realized gross edge in points, or None.

    None means "not measured yet" — too few settled rows, too few distinct
    settlement days, or a rates dict that cannot supply the mean entry
    price or day count the calculation needs. That last case **fails
    closed** on purpose: an unverifiable measurement is not a measurement,
    and silently treating one as measured is the same false-survival
    failure that let one night of football define a bucket.
    """
    measured = rates.get(bucket)
    if not measured or measured.get("n", 0) < min_n:
        return None
    mean_entry_price = measured.get("mean_entry_price")
    n_days = measured.get("n_days")
    if mean_entry_price is None or n_days is None or n_days < min_days:
        return None
    return (measured["win_rate"] - mean_entry_price) * 100.0


def edge_for(
    bucket: str,
    entry_price: float,
    rates: dict,
    priors: dict,
    min_n: int = MIN_BUCKET_N,
    min_days: int = MIN_BUCKET_DAYS,
) -> tuple[float, str]:
    """Net edge in points for a bucketed judgment, and where it came from.

    Returns (edge_pts_net, edge_basis) where edge_basis is "measured" when
    the bucket has enough settled history to speak for itself, otherwise
    "prior".

    The gross claim does not depend on `entry_price` — that is the whole
    correction. Only the fee does, because the fee genuinely is a function
    of the price this candidate would be bought at.
    """
    gross = measured_gross(bucket, rates, min_n, min_days)
    if gross is None:
        return float(priors.get(bucket, 0.0)), "prior"
    return gross - fee_pts(entry_price), "measured"
