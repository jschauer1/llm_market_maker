"""calibration_harvest -- the cell grid and its edge arithmetic.

A "cell" is (domain x horizon x price bin). The theory's whole claim is that
each cell has its own signed miscalibration, so the grid IS the decision
procedure: change a boundary here and the theory's version must bump.

Three design choices are worth stating, because each is a direct response to
something this repo already got wrong once.

**Wilson lower bounds, never raw rates.** `mention_family` scored its 0.85+
price bin at a raw 41/41 = 1.000 and computed edges against that. Its own
NOTES flagged the unshrunk 1.000 as a defect at the time; full coverage later
measured the family at -1.53 net and the theory was retired. A raw rate is
the most optimistic reading of a cell, and a grid of cells guarantees some
cell looks golden. `wilson_lower` takes the pessimistic end of the interval
instead, so a thin cell has to earn its edge by being both high AND populous.

**Two floors before a cell is `measured`, not one.** `n >= 30` is the row
floor. `n_days >= 8` is the settlement-day floor, and it is the one that
matters more: Kalshi settles in day-clumps, and measured over three
consecutive close-days on the shared insider_bias population
(`studies/2026-08-27-settlement-day-clustering/`) the day-level favorite edge
ran +4.26 / -7.29 / +5.40 net -- a swing wider than any edge this theory
hopes to harvest. 400 rows spread over 3 days is 3 draws, not 400, and
calling that `measured` would be the mention_family mistake with a bigger n.

**The dead middle is unbinned on purpose.** `price_bin` returns None between
0.35 and 0.65. The documented bias lives at the extremes; the middle is where
fees are worst (`min(0.07*P*(1-P), 0.035)` peaks at P=0.5) and where the
compression evidence is weakest. A cell nobody claims is better than a cell
that exists only because a grid had to be exhaustive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tools.sizing import fee_pts

__all__ = [
    "price_bin", "horizon_bin", "domain_for", "cell_key",
    "wilson_lower", "effective_n", "cell_edge", "fee_pts",
    "CLUSTER_RHO",
    "PRICE_BINS", "HORIZON_BINS", "DOMAINS",
    "MIN_CELL_N", "MIN_CELL_DAYS", "UNMAPPED",
]

#: Favorite-side bins plus the mirrored fade band. Half-open [lo, hi) except
#: the top bin, which includes 0.97 so the screen's own ceiling is not a
#: hole. The gap between 0.35 and 0.65 is deliberate -- see module docstring.
PRICE_BINS: tuple[tuple[float, float, str], ...] = (
    (0.03, 0.15, "0.03-0.15"),
    (0.15, 0.35, "0.15-0.35"),
    (0.65, 0.75, "0.65-0.75"),
    (0.75, 0.85, "0.75-0.85"),
    (0.85, 0.92, "0.85-0.92"),
    (0.92, 0.97, "0.92-0.97"),
)

#: Upper bounds in days, ascending; the last bin is open-ended. There is
#: deliberately NO cap: Le 2026's universal horizon component rises
#: monotonically with time to close (0.99 at 0-1h to 1.32 at 1mo+), so the
#: long-dated cells are where the effect is strongest. insider_bias caps at
#: 14 days for its own thesis; inheriting that cap here would discard the
#: best cells before measuring them.
HORIZON_BINS: tuple[tuple[float, str], ...] = (
    (2.0, "<=2d"),
    (7.0, "2d-1w"),
    (30.0, "1w-1mo"),
    (math.inf, "1mo+"),
)

#: Kalshi's series categories collapsed to the domains the evidence actually
#: distinguishes. Politics and Elections are one domain because Le 2026's
#: "politics" spans both and their mechanism is identical; weather is its own
#: because its measured slope has the OPPOSITE sign inside 12h, which is the
#: single most important fact in this theory. Everything unmapped falls to
#: "other" rather than being guessed into a domain whose sign it may not
#: share.
DOMAINS: dict[str, str] = {
    "Politics": "politics",
    "Elections": "politics",
    "Climate and Weather": "weather",
    "Economics": "economics",
    "Financials": "financials",
    "Crypto": "crypto",
    "Sports": "sports",
    "Entertainment": "entertainment",
    "Companies": "companies",
    "Science and Technology": "sci_tech",
    "Health": "health",
    "World": "world",
}

#: Row floor and settlement-day floor. Both must clear before a cell's rate
#: is allowed to call itself `measured`.
MIN_CELL_N = 30
MIN_CELL_DAYS = 8

#: Domain for a series the run's category map did not cover. Deliberately
#: NOT `other` -- see `domain_for`. Rows carrying it are a run defect made
#: visible, never a measurement.
UNMAPPED = "unmapped"

#: 1.96 -> a one-sided 97.5% lower bound. Deliberately not a tunable: a
#: confidence level chosen per cell is a free parameter to overfit with.
_Z = 1.959963984540054

#: Intracluster correlation of outcomes within one settlement day, used to
#: turn a cell's row count into an effective sample size. ONE pooled number
#: for the whole grid, for the same reason `_Z` is not tunable: a rho chosen
#: per cell is a free parameter per cell.
#:
#: Measured 2026-09-01 by ANOVA ICC over the 20 cells of both complete
#: populations that clear both floors -- mean 0.0667, median 0.0266, max
#: 0.3151. This is the **90th percentile**, ~3.5x the mean and ~9x the
#: median, chosen deliberately pessimistic: under-claiming is the safe
#: direction for the number that decides a bet.
#:
#: Weather cells (mbar 12-16) measured rho -0.007..+0.016; politics cells
#: (mbar 2.6-5.3) measured -0.34..+0.32. The ordering is the mechanism: a
#: weather cell's same-day rows are different cities, close to independent
#: draws, while same-day politics markets often share an underlying event.
CLUSTER_RHO = 0.2326


def price_bin(price: float | None) -> str | None:
    """The price bin for an ask, or None if it falls in no claimed band."""
    if price is None:
        return None
    for lo, hi, label in PRICE_BINS:
        if lo <= price < hi:
            return label
    # The top bin closes at the screen's own ceiling rather than at 1.0, so
    # an ask of exactly 0.97 belongs to it instead of falling out.
    if price == PRICE_BINS[-1][1]:
        return PRICE_BINS[-1][2]
    return None


def horizon_bin(days_to_close: float | None) -> str | None:
    """The horizon bin for a time-to-close in days, or None if negative."""
    if days_to_close is None or days_to_close < 0:
        return None
    for upper, label in HORIZON_BINS:
        if days_to_close <= upper:
            return label
    return HORIZON_BINS[-1][1]


def domain_for(category: str | None) -> str:
    """Kalshi's series category collapsed to an evidence domain.

    `other` and `unmapped` are two different facts and must never share a
    name. `other` is a category this grid deliberately does not bin --
    Commodities, Social, Transportation, Exotics, Education -- a real,
    small residual (102 of 9,220 survivors on the 2026-09-01 board).
    `unmapped` means the *run's* category map never covered this series,
    which is a defect in the run, not a fact about the market.

    They were both `other` until 2026-09-01, and that is how the domain
    axis collapsed silently three times: the 2026-08-30 `live` run passed
    no map at all, and the 2026-08-29..09-01 floors drove the screen twice
    with a weather-only and a politics-only map, each labelling the other's
    population `other`. 9,123 of 9,220 survivors in the weather run looked
    exactly like a legitimate residual. Split, a partial map produces a
    conspicuous `unmapped|*` cell instead.

    Callers already carry the distinction and always did: `screen.py` looks
    the series up with `categories.get(...)`, so an uncovered series arrives
    as None while a covered-but-unbinned one arrives as its real string.
    """
    if not category:
        return UNMAPPED
    return DOMAINS.get(category, "other")


def cell_key(
    price: float | None,
    days_to_close: float | None,
    category: str | None,
) -> str | None:
    """The cell a candidate belongs to, or None if any axis is unclaimed."""
    pb = price_bin(price)
    hb = horizon_bin(days_to_close)
    if pb is None or hb is None:
        return None
    return f"{domain_for(category)}|{hb}|{pb}"


def wilson_lower(wins: int, n: int) -> float:
    """Lower end of the Wilson score interval for a win rate.

    Preferred over the normal approximation because it behaves at the
    boundary: at 41/41 the normal interval has zero width and hands back
    1.000 -- exactly the number that flattered mention_family -- while
    Wilson returns something honestly below 1.
    """
    if n <= 0:
        return 0.0
    p = wins / n
    z2 = _Z * _Z
    denom = 1.0 + z2 / n
    centre = p + z2 / (2 * n)
    margin = _Z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


def effective_n(n: int, n_days: int) -> int:
    """A cell's rows discounted to an effective sample size.

    The standard survey design effect. Rows inside one settlement day are
    not independent draws, so the honest sample size is

        mbar  = n / n_days                 rows per settlement day
        DEFF  = 1 + (mbar - 1) * rho       Kish's design effect
        n_eff = n / DEFF

    **The two estimators this theory has already shipped are the endpoints
    of this formula, not alternatives to it.** At rho = 1 (total within-day
    dependence) DEFF is exactly mbar and `n_eff` collapses to `n_days` --
    that is v2/v3's day-Wilson. At rho = 0 (independence) DEFF is 1 and
    `n_eff` is `n` -- that is v1's row-Wilson. v3 did not choose a
    conservative bound so much as pin a measurable parameter at 1.0, and
    the measurement (`CLUSTER_RHO`) says the truth is nowhere near it.

    Why that mattered: at rho = 1 the bound was *infeasible at this
    theory's own gate*. `MIN_CELL_DAYS` is 8, but a cell priced at 0.80
    needs 17 settlement days before a positive edge is arithmetically
    possible at ANY realized rate, 0.92 needs 48, and 0.95 needs 79 --
    against a reachable history of 58 days. The whole 0.92-0.97 band, the
    band this theory's thesis says is richest, could never fire from a
    backtest. See NOTES.md 2026-09-01 (later) for the frontier tables.

    Clamped into `[1, n]`: DEFF below 1 would claim more information than
    there are rows, which no amount of negative measured rho earns.
    """
    if n <= 0 or n_days <= 0:
        return 0
    mbar = n / n_days
    deff = max(1.0, 1.0 + (mbar - 1.0) * CLUSTER_RHO)
    return max(1, min(int(n), int(round(n / deff))))


@dataclass(frozen=True)
class CellEdge:
    """A cell's edge in points, with the basis it has actually earned."""

    pts_net: float
    pts_gross: float
    fee_pts: float
    basis: str            # "measured" | "model"
    model_prob: float     # the Wilson bound actually used
    n: int
    n_days: int


def cell_edge(wins: int, n: int, n_days: int, ask: float) -> CellEdge:
    """Signed edge for buying at `ask` in a cell that went `wins`/`n`.

    `basis` is "measured" only when the cell clears BOTH floors. A cell that
    clears neither still gets an edge computed and reported -- knowing a thin
    cell looks good is useful -- but "model" is what stops it being
    recommended, exactly as CLAUDE.md requires.

    The edge is deliberately not clamped at zero: a strongly negative cell is
    the theory's most interesting output, since it names the mirrored fade
    trade the spec asks for.
    """
    # The bound counts an EFFECTIVE sample size, not rows and not days.
    #
    # Rows inside one settlement day are not independent draws: a screen's
    # whole near-term board settles within hours of itself, and the
    # 2026-08-27 clustering study measured the resulting day-level swings
    # directly. v1 ignored that and bounded on `n`. v2 over-corrected and
    # bounded on `n_days`, which is the same design-effect formula pinned
    # at rho = 1 -- total within-day dependence.
    #
    # v4 measures rho instead of assuming it (`effective_n`). This is the
    # refinement v2's own comment booked as owed: "a proper cluster-robust
    # interval would sit somewhere between `n_days` and `n`." It does, and
    # for weather it sits near the `n` end -- that cell's same-day rows are
    # different cities, not one event seen fourteen times.
    #
    # Worked example, weather `<=2d|0.75-0.85`: 628/789 over 59 days at an
    # ask of 0.794. Row-counted the bound claimed +1.64pts; day-counted
    # -7.27; DEFF-counted -7.18. The fix is a correction, not a loosening:
    # across all 20 measured cells it moves exactly one across zero, and
    # that one is in-sample, thin, and belongs to a retracted claim.
    n_eff = effective_n(n, n_days)
    if n_eff <= 0 or n <= 0:
        prob = 0.0
    else:
        prob = wilson_lower(round((wins / n) * n_eff), n_eff)
    gross = (prob - ask) * 100.0
    fee = fee_pts(ask)
    measured = n >= MIN_CELL_N and n_days >= MIN_CELL_DAYS
    return CellEdge(
        pts_net=gross - fee,
        pts_gross=gross,
        fee_pts=fee,
        basis="measured" if measured else "model",
        model_prob=prob,
        n=n,
        n_days=n_days,
    )
