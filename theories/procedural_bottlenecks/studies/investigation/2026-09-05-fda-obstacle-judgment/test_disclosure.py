"""Synthetic disclosure controls; no real FDA cases used to fit extraction."""
from datetime import date
import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).with_name("disclosure.py")


@pytest.fixture
def baseline():
    assert MODULE.exists(), "The prespecified disclosure baseline is not implemented"
    spec = importlib.util.spec_from_file_location("fda_disclosure", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case(text, deadline="2027-01-01"):
    return {"subject_id": "test_drug", "aliases": ["TestDrug"],
            "deadline_date": deadline, "as_of": "2026-09-05T18:30:00Z",
            "sources": [{"source_id": "s1", "text": text}]}


@pytest.mark.parametrize("window,earliest", [
    ("in Q1 2027", "2027-01-01"),
    ("in the first quarter of 2027", "2027-01-01"),
    ("in the second half of 2027", "2027-07-01"),
    ("during October 2026", "2026-10-01"),
    ("on January 10, 2027", "2027-01-10"),
    ("in 2027", "2027-01-01"),
])
def test_submission_window_earliest_date(baseline, window, earliest):
    result = baseline.classify(case(f"We plan to submit the NDA for TestDrug {window}."))
    assert result["filing_windows"][0]["earliest"] == earliest
    assert result["primary_signal"] == (date.fromisoformat(earliest) >= date(2027, 1, 1))


@pytest.mark.parametrize("text", [
    "We expect to submit the NDA for TestDrug by Q1 2027.",
    "We may submit the NDA for TestDrug in 2027.",
    "We do not plan to submit the NDA for TestDrug in 2027.",
    "If successful, we plan to submit the NDA for TestDrug in 2027.",
    "TestDrug's NDA was submitted in 2025; we expect approval in 2027.",
    "OtherDrug has a planned NDA submission in 2027.",
    "TestDrug has a PDUFA goal date in March 2027.",
    "The advisory committee voted against TestDrug, but the decision is nonbinding.",
    "TestDrug received a complete response letter in 2025.",
    "TestDrug could receive a complete response letter if our facility fails inspection.",
    "We do not expect a complete response letter for TestDrug.",
])
def test_nonbinding_unknown_upper_bound_and_negated_controls(baseline, text):
    result = baseline.classify(case(text))
    assert not result["primary_signal"]
    assert not result["warning_signal"]


def test_warning_does_not_replace_deadline_specific_baseline(baseline):
    text = ("We expect a complete response letter for TestDrug. "
            "We plan to resubmit the NDA for TestDrug in Q4 2026.")
    before = baseline.classify(case(text, "2026-07-01"))
    after = baseline.classify(case(text, "2027-01-01"))
    assert before["primary_signal"] and before["warning_signal"]
    assert not after["primary_signal"] and after["warning_signal"]
    assert before["matches"][0]["source_id"] == "s1"


def test_explicit_inability_by_deadline(baseline):
    result = baseline.classify(case("TestDrug cannot receive FDA approval before January 1, 2027."))
    assert result["primary_signal"]


def test_earlier_explicit_inability_does_not_block_later_deadline(baseline):
    result = baseline.classify(case("TestDrug cannot receive FDA approval before October 1, 2026."))
    assert not result["primary_signal"]


def test_unknown_filing_window_remains_visible(baseline):
    result = baseline.classify(case("We plan to submit the NDA for TestDrug after receiving further feedback."))
    assert not result["primary_signal"]
    assert result["parsing_failures"]
