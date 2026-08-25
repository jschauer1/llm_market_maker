"""The mechanical family gate, including the leak that produced the one
classification bug on the 2026-08-23 run."""

import pytest

from theories.insider_bias.insider_judgment import gate


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
        {"series_ticker": "KXBTCD", "ticker": "a"},
        {"series_ticker": "KXBTCD", "ticker": "b"},
        {"series_ticker": "KXWNBAGAME", "ticker": "c"},
        {"series_ticker": "KXBIGBROTHERELIMINATION", "ticker": "d"},
    ]
    survivors, counts = gate.partition(candidates)
    assert [c["ticker"] for c in survivors] == ["d"]
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
