import pytest

from tools import db, ideas, theories

TS = "2026-08-23T12:00:00Z"
LATER = "2026-09-01T12:00:00Z"


def test_record_creates_an_idea(conn):
    ideas.record(
        conn,
        "polymarket-whale-copy",
        "Copy Polymarket whales into Kalshi",
        "Large Polymarket traders may be informed; mirror them on Kalshi.",
        now=TS,
    )
    row = ideas.get(conn, "polymarket-whale-copy")
    assert row["title"] == "Copy Polymarket whales into Kalshi"
    assert row["status"] == "considered"
    assert row["source"] == "agent"
    assert row["theory_id"] is None


def test_record_accepts_explicit_codex_source(conn):
    ideas.record(conn, "codex-idea", "Codex idea", source="codex", now=TS)
    assert ideas.get(conn, "codex-idea")["source"] == "codex"


def test_re_record_without_source_preserves_historical_attribution(conn):
    ideas.record(conn, "legacy", "Legacy idea", source="claude", now=TS)
    ideas.record(conn, "legacy", "Updated title", now=LATER)
    row = ideas.get(conn, "legacy")
    assert row["title"] == "Updated title"
    assert row["source"] == "claude"


def test_re_record_with_explicit_source_updates_attribution(conn):
    ideas.record(conn, "handoff", "Handoff", source="claude", now=TS)
    ideas.record(conn, "handoff", "Handoff", source="codex", now=LATER)
    assert ideas.get(conn, "handoff")["source"] == "codex"


def test_get_returns_none_for_unknown_idea(conn):
    assert ideas.get(conn, "never-thought-of-this") is None


def test_search_finds_by_keyword_across_fields(conn):
    ideas.record(conn, "whale-copy", "Whale copying",
                 "Follow large Polymarket traders.", now=TS)
    ideas.record(conn, "weather-arb", "Weather arbitrage",
                 "NOAA forecasts versus Kalshi temperature markets.", now=TS)

    assert [r["slug"] for r in ideas.search(conn, "whale")] == ["whale-copy"]
    assert [r["slug"] for r in ideas.search(conn, "polymarket")] == \
        ["whale-copy"]
    assert [r["slug"] for r in ideas.search(conn, "NOAA")] == ["weather-arb"]


def test_search_is_case_insensitive(conn):
    ideas.record(conn, "whale-copy", "Whale copying", "Polymarket.", now=TS)
    assert len(ideas.search(conn, "WHALE")) == 1
    assert len(ideas.search(conn, "wHaLe")) == 1


def test_search_returns_empty_for_no_match(conn):
    ideas.record(conn, "whale-copy", "Whale copying", "Polymarket.", now=TS)
    assert ideas.search(conn, "cricket") == []


def test_dead_idea_records_why_it_died(conn):
    ideas.record(conn, "whale-copy", "Whale copying", "...", now=TS)
    ideas.update_status(
        conn,
        "whale-copy",
        "dead",
        what_was_tried="Screened 400 markets over 3 months; only 6 matched "
                       "a Kalshi equivalent and none had edge after fees.",
        outcome="Cross-platform overlap is too thin to trade.",
        now=LATER,
    )
    row = ideas.get(conn, "whale-copy")
    assert row["status"] == "dead"
    assert "400 markets" in row["what_was_tried"]
    assert "too thin" in row["outcome"]
    assert row["updated_at"] == LATER


def test_dead_idea_with_a_revisit_angle_stays_revisitable(conn):
    ideas.record(conn, "whale-copy", "Whale copying", "...", now=TS)
    ideas.update_status(
        conn, "whale-copy", "dead",
        outcome="Matching was too crude to find real equivalents.",
        revisit_angle="Retry once match_market compares resolution criteria "
                      "rather than title keywords.",
        now=LATER,
    )
    revisitable = ideas.list_revisitable(conn)
    assert [r["slug"] for r in revisitable] == ["whale-copy"]


def test_exhausted_dead_idea_is_not_revisitable(conn):
    ideas.record(conn, "coin-flip", "Bet coin flips", "...", now=TS)
    ideas.update_status(
        conn, "coin-flip", "dead",
        outcome="There is no signal here by construction.",
        now=LATER,
    )
    assert ideas.list_revisitable(conn) == []


def test_parked_idea_is_revisitable_with_its_condition(conn):
    ideas.record(conn, "snapshot-drift", "Price drift from our snapshots",
                 "...", now=TS)
    ideas.update_status(
        conn, "snapshot-drift", "parked",
        outcome="Not enough first-party history yet.",
        revisit_after="once 6 months of snapshots exist",
        now=LATER,
    )
    revisitable = ideas.list_revisitable(conn)
    assert len(revisitable) == 1
    assert revisitable[0]["revisit_after"] == "once 6 months of snapshots exist"


def test_promoting_an_idea_links_it_to_a_theory(conn):
    theories.register(conn, "insider_bias", "Insider Bias",
                      "theories/insider_bias", now=TS)
    ideas.record(conn, "insider-bias", "Insider bias", "...", now=TS)
    ideas.update_status(conn, "insider-bias", "promoted",
                        theory_id="insider_bias", now=LATER)

    row = ideas.get(conn, "insider-bias")
    assert row["status"] == "promoted"
    assert row["theory_id"] == "insider_bias"


def test_promoted_ideas_are_not_revisitable(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    ideas.record(conn, "i1", "Idea one", "...", now=TS)
    ideas.update_status(conn, "i1", "promoted", theory_id="t1", now=LATER)
    assert ideas.list_revisitable(conn) == []


def test_update_status_rejects_invalid_status(conn):
    ideas.record(conn, "i1", "Idea one", "...", now=TS)
    with pytest.raises(ValueError):
        ideas.update_status(conn, "i1", "vibes")


def test_update_status_rejects_unknown_idea(conn):
    with pytest.raises(KeyError):
        ideas.update_status(conn, "nope", "dead")


def test_update_preserves_fields_not_being_set(conn):
    ideas.record(conn, "i1", "Idea one", "...", now=TS)
    ideas.update_status(conn, "i1", "investigating",
                        what_was_tried="Ran an initial screen.", now=LATER)
    ideas.update_status(conn, "i1", "dead",
                        outcome="No signal.", now=LATER)

    row = ideas.get(conn, "i1")
    assert row["what_was_tried"] == "Ran an initial screen."
    assert row["outcome"] == "No signal."


def test_record_is_idempotent_on_slug(conn):
    ideas.record(conn, "i1", "Idea one", "first description", now=TS)
    ideas.record(conn, "i1", "Idea one revised", "second description",
                 now=LATER)
    assert len(ideas.search(conn, "Idea one")) == 1
    assert ideas.get(conn, "i1")["description"] == "second description"


def test_record_does_not_reset_status(conn):
    ideas.record(conn, "i1", "Idea one", "...", now=TS)
    ideas.update_status(conn, "i1", "dead", outcome="No signal.", now=LATER)
    ideas.record(conn, "i1", "Idea one", "...", now=LATER)
    assert ideas.get(conn, "i1")["status"] == "dead"
