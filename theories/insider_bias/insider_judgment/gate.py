r"""insider_bias — mechanical family gate (v3, 2026-08-29).

`THEORY.md` and `RUNBOOK.md` specify the deterministic classifier below. It
replaced the original design's cheap LLM gate on the first live run, because
the screen's output turned out to be dominated by whole market
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

## v3 (2026-08-29) — the gate reads resolution rules, not only tickers

A prefix allowlist only knows families it has already seen, and Kalshi
adds families faster than anyone updates a regex. Measured over the whole
117,272-market board: the allowlist removed 198 of 328 screened events,
and **109 of the surviving 130 were still families the thesis rejects
outright** — 84% junk reaching the expensive stage. The leaks were whole
categories, not stragglers: 39 Carbon Arc vendor-panel events, 47 sport
fixtures across a dozen leagues nobody had enumerated, 7 OpenRouter
share events, 3 Metacritic events.

`RULES_NO_RULES` fixes that by matching the market's **resolution rules**,
which is where the mechanics actually live. A vendor panel says "Carbon
Arc" in its own rules whatever its ticker is called, so the rule covers
every such series Kalshi ever adds without an edit. Every pattern below
was measured against every series on that board before being written, and
catches only its named family:

| rule | series caught | markets | false positives |
|---|---|---|---|
| sport fixture (rules) | 611 | ~23,000 | none |
| Carbon Arc vendor panel | 77 | 956 | none |
| statistical release (rules) | 29 | ~1,000 | none |
| OpenRouter aggregate | 10 | 70 | none |
| Metascore aggregate | 1 | 52 | none |

**Net effect on the same board: 130 survivors -> 18.** Eighteen is what
the expensive stage should have been seeing all along; every one of them
is an event a human reading THEORY.md would agree is at least arguable.
The removed 112 are checked in both directions -- no series on the whole
117,272-market board that the thesis can apply to is eliminated by any
rule here, asserted by
`test_the_rejected_rules_false_positives_still_survive`.

## Two rules were measured and REJECTED — do not re-add them

Both looked obvious and both silently kill real candidates. This is the
gate's documented failure mode ("inside a matched family it drops
silently") caught before it cost anything, and it is why patterns here
are validated against the whole board rather than against intuition.

1. **Ticker-suffix sport rule** `(GAME|MATCH|SPREAD|TOTAL|BTTS|TOP\d+|RACE)$`
   — catches 496 series, *fewer* than the rules-text rule's 611, and kills
   `KXRACE` ("Will Ferrari N.V. report Above 3225 total car shipments in
   Q3 2026" — a company that knows its own shipments, squarely this
   theory's thesis) and `KXXAIGAME` ("Will xAI release a video game before
   2027" — a company that knows its own roadmap). It also mislabels
   `KXHOUSERACE` and four Billboard/DJ-Mag ranking series as "live sport".
2. **Substring statistical-release rule** `^KX.*(CPI|PPI|INF|GDP|SALES|KWH)`
   — "Phili**PPI**nes" matches `PPI`, so it eliminates
   `KXPHILIPPINESPRES/HOUSE/SENATE`; "LAYOFFSY**INF**O" matches `INF`; and
   `KXGTASALES RECORD` ("Will GTA 6 break the record for the
   highest-grossing videogame in 24 hours" — Take-Two knows its own
   first-day sales) dies on `SALES`. Statistical releases are still gated
   by the explicit `scheduled economic indicator` prefixes below; the
   remaining leaks there are named families, not a pattern.
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
     r"^KX(GOLD|SILVER|BRENT|WTI|NATGAS|COPPER|USDJPY|UST\d|AAAGAS|SPRLVL"
     r"|DIESEL)"),
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
     # CPI and USGASCPI are the two releases whose rules text never says
     # "Consumer Price Index" -- KXCPICOMBO reads "Headline: Exactly 0.3%,
     # Core: 0.1% or below" and KXUSGASCPI reads "Gasoline (All Types) in
     # U.S. City Average". Named here as ANCHORED prefixes, which is the
     # safe form; the unanchored substring version is the rejected rule in
     # the docstring.
     r"|CPI|USGASCPI"
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
     r"|FRAGRANCE"
     r"|TBCRUNCHWRAP)"),
)

#: Sports named in Kalshi's fixture template. Kept as one alternation so
#: the two sport clauses below stay in sync.
_SPORTS = (r"soccer|basketball|football|cricket|hockey|tennis|baseball"
           r"|rugby|volleyball|handball|lacrosse|darts|golf|esport")

#: (label, resolution-rules pattern) for families identifiable from what
#: the market actually resolves on. Searched (not matched) against
#: `rules_primary`. See the module docstring for the board-scale
#: measurement behind each one, and for the two patterns that were
#: measured and rejected.
RULES_NO_RULES: tuple[tuple[str, str], ...] = (
    ("live sport / esport",
     # Three shapes, all fixture-scoped: the "professional <sport>
     # game/match" template; any "A vs B ... originally scheduled for",
     # which is how both-teams-to-score and period markets read; and a
     # motorsport finishing position.
     rf"professional .{{0,60}}(?:{_SPORTS}) (?:game|match)"
     r"|\bvs\.?\b.{0,90}\boriginally scheduled for\b"
     r"|\bfinishes? (?:in )?(?:first|the top \d+) in the (?:main )?race\b"),
    ("vendor panel metric",
     # Carbon Arc card spend / app downloads / foot traffic / point of
     # sale: a month of millions of consumers' behaviour, computed by a
     # data vendor after the fact. Nobody holds the answer in advance.
     r"\bCarbon Arc\b"),
    ("aggregate of many independent people",
     # OpenRouter weekly share and token totals; Metacritic Metascores.
     r"\bOpenRouter\b|\bMetascore\b"),
    ("scheduled economic indicator",
     # Agency statistical releases. This is the SAFE version of the
     # substring rule the docstring records as rejected: it names the
     # published series and the publishing agency, both of which appear in
     # the rules text, instead of hunting "CPI"/"PPI"/"GDP" inside a ticker
     # where "PhiliPPInes" is a match. Measured: 29 series on the
     # 2026-08-29 board, every one a genuine release, no false positives.
     r"Consumer Price Index"
     r"|Producer Price Index"
     r"|Bureau of Labor Statistics"
     r"|\binflation rate\b"
     r"|\bGDP growth rate\b"
     r"|seasonally adjusted annual rate"
     r"|\bexisting home sales\b|\bnew home sales\b"
     r"|Median Sales Price of Existing Homes"
     r"|average price of electricity per kilowatt-hour"),
)

PLAUSIBLE = "PLAUSIBLE"

_COMPILED = tuple((label, re.compile(pat)) for label, pat in NO_RULES)
# Case-insensitive: these match prose, where Kalshi capitalises
# inconsistently ("the Main race" and "the main race" appear in the same
# series). The ticker patterns above stay case-sensitive -- tickers are
# uppercase by construction, and a loose match there is exactly how a
# substring rule eats a real family.
_COMPILED_RULES = tuple(
    (label, re.compile(pat, re.IGNORECASE)) for label, pat in RULES_NO_RULES
)


def classify(series_ticker: str | None,
             rules_primary: str | None = None) -> str:
    """Category for a market, or PLAUSIBLE if the thesis could apply.

    Pass the **series** ticker (`KXRT`), not the event (`KXRT-BUD`) or market
    (`KXRT-BUD-90`) ticker.

    `rules_primary` is optional so the ticker allowlist stays usable on its
    own, but pass it when you have it: it is what catches families nobody
    has enumerated yet. The ticker check runs first because it is anchored
    and cheap.
    """
    for label, pattern in _COMPILED:
        if pattern.match(series_ticker or ""):
            return label
    for label, pattern in _COMPILED_RULES:
        if pattern.search(rules_primary or ""):
            return label
    return PLAUSIBLE


def is_gated_out(series_ticker: str | None,
                 rules_primary: str | None = None) -> bool:
    """True when the theory's own rules answer 'no' for this whole family."""
    return classify(series_ticker, rules_primary) != PLAUSIBLE


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
        market = candidate.legs[0].market
        label = classify(market.series_ticker, market.rules_primary)
        counts[label] = counts.get(label, 0) + 1
        if label == PLAUSIBLE:
            survivors.append(candidate)
    return survivors, counts
