"""Input isolation tests: future material and operator fields must not leak."""
import importlib.util
from pathlib import Path

import pytest


def subject_module():
    path = Path(__file__).with_name("run_diagnostic.py")
    assert path.exists(), "Packet isolation is not implemented"
    spec = importlib.util.spec_from_file_location("fda_diagnostic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def packet(published="2026-05-14"):
    return {"subject_id": "test", "as_of": "2026-05-15T12:00:00Z",
            "result": "yes", "baseline": True,
            "sources": [{"source_id": "s", "title": "Source", "text": "Original text.",
                         "published_at": published, "captured_at": "2026-09-05T18:00:00Z",
                         "url": "https://example.org/source", "result": "yes", "yes_bid": .7}],
            "coverage": {"missing": ["FDA document"]}}


def test_only_declared_source_fields_reach_judge():
    module = subject_module()
    result = module.blind_sources(packet())
    assert len(result["sources"]) == 1
    assert not {"result", "baseline"} & result.keys()
    assert not {"result", "yes_bid"} & result["sources"][0].keys()
    assert result["sources"][0]["text"] == "Original text."


@pytest.mark.parametrize("published", ["2026-05-16", "2026-05-15", "2026-05-15T13:00:00Z", ""])
def test_future_unknown_and_undated_same_day_sources_are_excluded(published):
    result = subject_module().blind_sources(packet(published))
    assert not result["sources"]
    assert result["excluded_sources"]


def test_precise_predecision_timestamp_is_eligible():
    result = subject_module().blind_sources(packet("2026-05-15T11:59:00Z"))
    assert len(result["sources"]) == 1
