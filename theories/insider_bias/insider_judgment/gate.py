"""insider_bias — mechanical family gate (v2, 2026-08-23).

`THEORY.md` documents a cheap LLM gate over every screened candidate. On the
first live run that gate was replaced with the deterministic classifier
below, because the screen's output turned out to be dominated by whole market
families that this theory's own written rules reject outright — crypto and
commodity strike ladders, weather, live sport, scheduled indicators, and
aggregates of many independent people. Deciding those with a model is paying
for judgment on a question a regex answers.

Committing it here is not a procedure change; it is the same classifier that
actually ran on 2026-08-23, moved out of an ad-hoc shell heredoc and into
version control where a change to it shows up in `git diff`. It produced the
headline finding of that run: **242 of 274 candidate events (88%) fall in
categories the theory is written to reject.**

Patterns match the `series_ticker`, not the event or market ticker. That
distinction bit once already: `KXRT-BUD`'s series is `KXRT`, so a pattern
written as `RT-` silently failed to match and leaked five Rotten Tomatoes
events into the survivor set. Anchor short families with `$`.

This gate is deliberately coarse and errs toward *keeping* a candidate: a
family it does not recognise falls through to `PLAUSIBLE` and reaches the
expensive stage. Missing a real candidate costs edge; passing a junk one
costs tokens.
"""

from __future__ import annotations

import re

from tools.domain import Candidate

#: (label, series-ticker pattern) for families this theory's gating rules
#: answer "no" for. Order matters only for reporting -- the categories are
#: mutually exclusive in practice.
NO_RULES: tuple[tuple[str, str], ...] = (
    ("future price: crypto",
     r"^KX(BTC|ETH|SOL|XRP|DOGE|BNB|NEAR|HYPE)"),
    ("future price: commodity/FX/rates",
     r"^KX(GOLD|SILVER|BRENT|WTI|NATGAS|COPPER|USDJPY|UST\d|AAAGAS|SPRLVL)"),
    ("future price: compute/collectible",
     r"^KX(A100|B200|H100|H200|RTX5090|POKEMON|ARNAULTNW)"),
    ("weather / natural event",
     r"^KX(HIGH|LOWT|RAIN|AVGTK|HOBBYTEMP|NEXTCAT5|EARTHQUAKE)"),
    ("live sport / esport",
     r"^KX(APFDDH|BSN|CFL|COPADOBRASIL|DFBPOKAL|DIMAYOR|ECULP|LEAGUESCUP"
     r"|LIGAEXP|LMB|LNBP|NPB|NWSL|PERLIGA|SCOTTISHPREM|TESTMATCH|UCL|UECL"
     r"|UEL|URYPD|USLGAME|WNBA|VALORANT)"),
    ("scheduled economic indicator",
     r"^KX(ADP|PAYROLLS|U3|ECONSTAT|EMPLOYMENTCOMBO|JOBLESSCLAIMS|PCECORE"
     r"|NHSALES|BRAZILGDP|UE$|JPSGINFL|DATACENTCON|CHAICUTS|CBDECISION"
     r"|CBDISRAEL)"),
    ("aggregate of many independent people",
     r"^KX(YTVIEWS|YTMONTHLY|ALBUMEQUIV|PUREALBUMS|BILLBOARD|NETFLIX|RT$"
     r"|TSAW|HORMUZ|PANAMA|SUEZ|BABELMANDEB|MAXSHIPS|FEAR|APRPOTUS"
     r"|TRUTHSOCIAL|TRUMPDELETE|TRUMPSAY|MAMDANIMENTION|TRUMPENDORSE|NYTHEAD"
     r"|PRESSBRIEFINGCOUNT|DCGOLFVISIT|NJGOLFVISIT|TRUMPNUMSTATES|LAUNCHES"
     r"|SPACEXCOUNT|BILLSCOUNT|EOWEEK|PARDONSTRUMP|CHINAAI|MATHAI|OPENINTAI"
     r"|TOPMODEL)"),
    ("retail price index",
     r"^KX(BKNUGGETS|CFACHICKSAND|CHIPBURRITO|DDCOLDBREW|POPCHICKSAND|SBUXSAR"
     r"|TBCRUNCHWRAP)"),
)

PLAUSIBLE = "PLAUSIBLE"

_COMPILED = tuple((label, re.compile(pat)) for label, pat in NO_RULES)


def classify(series_ticker: str | None) -> str:
    """Category for a series, or PLAUSIBLE if the thesis could apply.

    Pass the **series** ticker (`KXRT`), not the event (`KXRT-BUD`) or market
    (`KXRT-BUD-90`) ticker.
    """
    for label, pattern in _COMPILED:
        if pattern.match(series_ticker or ""):
            return label
    return PLAUSIBLE


def is_gated_out(series_ticker: str | None) -> bool:
    """True when the theory's own rules answer 'no' for this whole family."""
    return classify(series_ticker) != PLAUSIBLE


def partition(
    candidates: list[Candidate],
) -> tuple[list[Candidate], dict[str, int]]:
    """Split screened candidates into survivors and a per-category count.

    Returns `(survivors, counts)`. `counts` includes the PLAUSIBLE bucket, so
    it always sums to `len(candidates)` — a gate that quietly drops things is
    how a scan reports 88% coverage it never had.
    """
    survivors: list[Candidate] = []
    counts: dict[str, int] = {}
    for candidate in candidates:
        label = classify(candidate.legs[0].market.series_ticker)
        counts[label] = counts.get(label, 0) + 1
        if label == PLAUSIBLE:
            survivors.append(candidate)
    return survivors, counts
