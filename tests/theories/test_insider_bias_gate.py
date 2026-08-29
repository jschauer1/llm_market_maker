"""The mechanical family gate, including the leak that produced the one
classification bug on the 2026-08-23 run."""

import pytest

from theories.insider_bias.insider_judgment import gate
from tools.domain import Candidate, Leg, Market


def _candidate(series_ticker, ticker):
    market = Market(platform="kalshi", ticker=ticker,
                    series_ticker=series_ticker, is_open=True)
    return Candidate(legs=(Leg(market=market, side="yes", price=0.80),),
                     days_to_close=5.0)


@pytest.mark.parametrize("series,expected", [
    ("KXBTCD", "future price: crypto"),
    ("KXETHD", "future price: crypto"),
    ("KXGOLDMON", "future price: commodity/FX/rates"),
    ("KXWTIW", "future price: commodity/FX/rates"),
    ("KXH100MON", "future price: compute/collectible"),
    ("KXPOKEMON", "future price: compute/collectible"),
    ("KXHIGHNY", "weather / natural event"),
    ("KXRAINMIAM", "weather / natural event"),
    ("KXWNBAGAME", "live sport / esport"),
    ("KXTESTMATCH", "live sport / esport"),
    ("KXPAYROLLS", "scheduled economic indicator"),
    ("KXYTVIEWSHIGH", "aggregate of many independent people"),
    ("KXTRUMPSAYMONTH", "aggregate of many independent people"),
    ("KXBKNUGGETS", "retail price index"),
])
def test_families_the_thesis_rejects(series, expected):
    assert gate.classify(series) == expected
    assert gate.is_gated_out(series)


@pytest.mark.parametrize("series", [
    "KXBIGBROTHERELIMINATION",
    "KXVIDEOLENGTH",
    "KXIPOSHEIN",
    "KXNEWDRUGAPPNTLA",
    "KXKASHANNOUNCEOUT",
    "KXCABLEAVE",
    "KXALBUMRELEASEDATE",
])
def test_families_the_thesis_can_apply_to(series):
    assert gate.classify(series) == gate.PLAUSIBLE
    assert not gate.is_gated_out(series)


def test_short_family_names_are_anchored():
    # Regression: patterns were first written as "RT-" and "UE-", matching the
    # EVENT ticker shape. The series ticker is bare ("KXRT"), so those never
    # matched and five Rotten Tomatoes events plus a Russian unemployment
    # event leaked into the survivor set on 2026-08-23.
    assert gate.classify("KXRT") == "aggregate of many independent people"
    assert gate.classify("KXUE") == "scheduled economic indicator"


def test_anchoring_does_not_swallow_longer_families():
    # "KXRT$" must not eat KXRTX5090, and "KXUE$" must not eat KXUECL.
    assert gate.classify("KXRTX5090WS") == "future price: compute/collectible"
    assert gate.classify("KXUECLGAME") == "live sport / esport"


def test_unknown_family_falls_through_to_the_expensive_stage():
    # Erring toward keeping: a missed candidate costs edge, a junk one costs
    # tokens.
    assert gate.classify("KXSOMETHINGBRANDNEW") == gate.PLAUSIBLE
    assert gate.classify(None) == gate.PLAUSIBLE
    assert gate.classify("") == gate.PLAUSIBLE


def test_partition_splits_and_counts_everything():
    candidates = [
        _candidate("KXBTCD", "a"),
        _candidate("KXBTCD", "b"),
        _candidate("KXWNBAGAME", "c"),
        _candidate("KXBIGBROTHERELIMINATION", "d"),
    ]
    survivors, counts = gate.partition(candidates)
    assert [c.ticker for c in survivors] == ["d"]
    assert counts["future price: crypto"] == 2
    assert counts["live sport / esport"] == 1
    assert counts[gate.PLAUSIBLE] == 1
    # Nothing may vanish: a gate that silently drops rows lets a scan claim
    # coverage it never had.
    assert sum(counts.values()) == len(candidates)


def test_partition_handles_an_empty_board():
    survivors, counts = gate.partition([])
    assert survivors == []
    assert counts == {}


# --- v5: the gate reads resolution rules, not only ticker prefixes -------
#
# Measured over the whole 117,272-market board on 2026-08-29. The prefix
# allowlist removed 198 of 328 screened events, but 109 of the 130
# survivors were still families the thesis rejects outright -- 84% junk
# reaching the expensive stage. Every rule below was checked against every
# series on that board before being written; see gate.py's docstring for
# what was measured and what was rejected.


def _ruled(series_ticker, rules_primary, ticker="T-1"):
    market = Market(platform="kalshi", ticker=ticker,
                    series_ticker=series_ticker, is_open=True,
                    rules_primary=rules_primary)
    return Candidate(legs=(Leg(market=market, side="yes", price=0.80),),
                     days_to_close=5.0)


SPORT_RULES = [
    # The fixture template, which the ticker allowlist never saw for these
    # leagues: Taca de Portugal, Chile, Korea, Croatia, Malaysia, Egypt.
    "If Fafe wins the Pacos Ferreira vs Fafe professional Taca de Portugal "
    "soccer game originally scheduled for Aug 29, 2026 after 90 minutes "
    "plus stoppage time, then the market resolves to Yes.",
    "If Palestino wins the Cobresal vs Palestino professional Chile Liga de "
    "Primera soccer game originally scheduled for Aug 28, 2026, then the "
    "market resolves to Yes.",
    # Both-teams-to-score rules never say "professional <sport> game"; they
    # are caught by the A-vs-B fixture clause instead.
    "If Ottawa and Inter Toronto both score a goal in the Ottawa vs Inter "
    "Toronto Canadian Premier League match originally scheduled for Aug 28, "
    "2026 after 90 minutes plus stoppage time, then the market resolves "
    "to Yes.",
    # Motorsport finishing positions.
    "If Alex Palou finishes in first in the Main race at the 2026 Milwaukee "
    "Mile 1 originally scheduled for Aug 29, 2026, then the market resolves "
    "to Yes.",
    "If David Malukas finishes in the top 10 in the main race at the 2026 "
    "Milwaukee Mile 1 originally scheduled for Aug 29, 2026, then the "
    "market resolves to Yes.",
]


@pytest.mark.parametrize("rules", SPORT_RULES)
def test_a_sport_fixture_is_gated_out_by_its_rules(rules):
    survivors, counts = gate.partition([_ruled("KXBRANDNEWLEAGUE", rules)])
    assert survivors == []
    assert counts["live sport / esport"] == 1


def test_a_vendor_panel_metric_is_gated_out_by_its_rules():
    rules = ("If the Carbon Arc Amazon Monthly Credit Card Spend (August "
             "2026) for August 2026 is above 104, then the market resolves "
             "to Yes.")
    survivors, counts = gate.partition([_ruled("KXAMZNCC", rules)])
    assert survivors == []
    assert counts["vendor panel metric"] == 1


def test_an_openrouter_share_is_gated_out_by_its_rules():
    rules = ("If Anthropic scores above 2.5% on OpenRouter Market Share by "
             "model author week of Aug 24, 2026, then the market resolves "
             "to Yes.")
    _, counts = gate.partition([_ruled("KXANTHSHARE", rules)])
    assert counts["aggregate of many independent people"] == 1


def test_a_metacritic_score_is_gated_out_by_its_rules():
    rules = ("If the Metascore for Onimusha: Way of the Sword is Above 70 "
             "seven days after release at 10:00AM ET, then the market "
             "resolves to Yes.")
    _, counts = gate.partition([_ruled("KXMC", rules)])
    assert counts["aggregate of many independent people"] == 1


# These are the false eliminations that killed the two rules gate.py's
# docstring records as measured-and-rejected. Each is a genuine thesis
# case: a company that knows its own shipments, its own product launch,
# or its own first-day sales.
@pytest.mark.parametrize("series,rules", [
    ("KXRACE",
     "If Ferrari N.V. reports above 3225 total number of car shipments in "
     "Q3 2026, then the market resolves to Yes."),
    ("KXXAIGAME",
     "If xAI releases a video game before 2027, then the market resolves "
     "to Yes."),
    ("KXGTASALESRECORD",
     "If GTA 6 breaks the record for the highest-grossing videogame in 24 "
     "hours, then the market resolves to Yes."),
    ("KXPHILIPPINESPRES",
     "If the Liberal Party wins the next Philippine presidential election, "
     "then the market resolves to Yes."),
])
def test_the_rejected_rules_false_positives_still_survive(series, rules):
    survivors, _ = gate.partition([_ruled(series, rules)])
    assert len(survivors) == 1, (
        f"{series} is a thesis case; a ticker-suffix or substring rule "
        "would have silently eliminated it"
    )


def test_rules_matching_never_hides_a_candidate_from_the_counts():
    candidates = [
        _ruled("KXAMZNCC", "If the Carbon Arc Amazon Monthly Credit Card "
                           "Spend for August 2026 is above 104, ..."),
        _ruled("KXBRANDNEWLEAGUE", SPORT_RULES[0]),
        _ruled("KXBIGBROTHERELIMINATION", "If Drew is eliminated, ..."),
        _candidate("KXBTCD", "e"),
    ]
    survivors, counts = gate.partition(candidates)
    assert len(survivors) == 1
    assert sum(counts.values()) == len(candidates)


def test_a_candidate_with_no_rules_text_is_still_classified_by_ticker():
    # rules_primary is not always populated; the prefix allowlist must keep
    # working on its own.
    survivors, counts = gate.partition([_ruled("KXWNBAGAME", None)])
    assert survivors == []
    assert counts["live sport / esport"] == 1


@pytest.mark.parametrize("series,rules", [
    ("KXCPIYOY",
     "If the Consumer Price Index (CPI) increases by more than 3.2% in the "
     "twelve months ending August 2026 (as represented by the one-decimal "
     "place value reported by the Bureau of Labor Statistics), then the "
     "market resolves to Yes."),
    ("KXARMOMINF",
     "If the Argentina inflation rate MoM for August 2026 is above 1.6%, "
     "then the market resolves to Yes."),
    ("KXSAGDPQOQ",
     "If the South Africa GDP growth rate QoQ for Q2 2026 is above 0.0%, "
     "then the market resolves to Yes."),
    ("KXEHSALES",
     "If US existing home sales for August 2026 (seasonally adjusted annual "
     "rate, millions of homes) is above 3.80M, then the market resolves "
     "to Yes."),
    ("KXPOWERKWH",
     "If the average price of electricity per kilowatt-hour in the U.S. "
     "city average for August 2026 is above 19.4c, then the market resolves "
     "to Yes."),
])
def test_a_statistical_release_is_gated_out_by_its_rules(series, rules):
    _, counts = gate.partition([_ruled(series, rules)])
    assert counts["scheduled economic indicator"] == 1


@pytest.mark.parametrize("series,expected", [
    ("KXDIESELD", "future price: commodity/FX/rates"),
    ("KXFRAGRANCE", "retail price index"),
])
def test_named_price_families_added_at_v3(series, expected):
    assert gate.classify(series) == expected
