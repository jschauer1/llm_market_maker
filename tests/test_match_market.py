import pytest

from tools import match_market


def _kalshi(ticker, title, close_time="2026-11-03T00:00:00Z", rules="Rules."):
    return {
        "platform": "kalshi",
        "ticker": ticker,
        "title": title,
        "close_time": close_time,
        "rules_primary": rules,
    }


def _poly(question, end_date="2026-11-03T00:00:00Z"):
    return {
        "platform": "polymarket",
        "market_id": "0xabc",
        "question": question,
        "end_date": end_date,
    }


def test_tokenize_lowercases_and_splits():
    assert match_market.tokenize("Will Biden Win?") >= {"biden", "win"}


def test_tokenize_drops_stopwords():
    tokens = match_market.tokenize("Will the president be elected?")
    assert "will" not in tokens
    assert "the" not in tokens
    assert "president" in tokens


def test_tokenize_handles_punctuation_and_empty():
    assert match_market.tokenize("U.S. election -- 2026!") >= {"election", "2026"}
    assert match_market.tokenize("") == set()


def test_score_pair_is_high_for_near_identical_text():
    score = match_market.score_pair(
        "Will Anthropic IPO before 2030?",
        "Will Anthropic IPO before 2030?",
    )
    assert score > 0.9


def test_score_pair_is_zero_for_unrelated_text():
    score = match_market.score_pair(
        "Will Anthropic IPO before 2030?",
        "Highest temperature in Miami on Tuesday",
    )
    assert score == pytest.approx(0.0)


def test_score_pair_rewards_close_end_dates():
    near = match_market.score_pair(
        "Anthropic IPO", "Anthropic IPO",
        source_end="2026-11-03T00:00:00Z",
        candidate_end="2026-11-04T00:00:00Z",
    )
    far = match_market.score_pair(
        "Anthropic IPO", "Anthropic IPO",
        source_end="2026-11-03T00:00:00Z",
        candidate_end="2029-11-04T00:00:00Z",
    )
    assert near > far


def test_score_pair_tolerates_missing_dates():
    score = match_market.score_pair("Anthropic IPO", "Anthropic IPO")
    assert score > 0.0


def test_score_pair_treats_unparseable_date_same_as_absent_date():
    # "TBD" (garbage) and no date field at all both mean "no usable date
    # information" and must score identically, not just similarly.
    unparseable = match_market.score_pair(
        "Anthropic IPO", "Anthropic IPO",
        source_end="2026-11-03T00:00:00Z", candidate_end="TBD",
    )
    absent = match_market.score_pair(
        "Anthropic IPO", "Anthropic IPO",
        source_end="2026-11-03T00:00:00Z", candidate_end=None,
    )
    assert unparseable == pytest.approx(absent)


def test_score_pair_tolerates_a_non_string_date_value():
    # An int epoch timestamp (rather than an ISO string) must not raise —
    # it should be treated the same as an unparseable/absent date.
    score = match_market.score_pair(
        "Anthropic IPO", "Anthropic IPO",
        source_end=1780000000, candidate_end="2026-11-03T00:00:00Z",
    )
    assert score == pytest.approx(1.0)


def test_score_pair_scores_identical_same_day_dates_at_one():
    score = match_market.score_pair(
        "Anthropic IPO", "Anthropic IPO",
        source_end="2026-11-03T00:00:00Z",
        candidate_end="2026-11-03T00:00:00Z",
    )
    assert score == pytest.approx(1.0)


def test_shortlist_ranks_the_best_match_first():
    source = _poly("Will Anthropic IPO before 2030?")
    candidates = [
        _kalshi("WEATHER-1", "Highest temperature in Miami"),
        _kalshi("IPO-ANTH", "Will Anthropic IPO before 2030?"),
        _kalshi("IPO-OAI", "Will OpenAI IPO before 2030?"),
    ]
    result = match_market.shortlist(source, candidates)
    assert result[0]["ticker"] == "IPO-ANTH"


def test_shortlist_respects_top_n():
    source = _poly("Anthropic IPO 2030")
    candidates = [_kalshi(f"T{i}", "Anthropic IPO 2030") for i in range(10)]
    assert len(match_market.shortlist(source, candidates, top_n=3)) == 3


def test_shortlist_drops_candidates_below_min_score():
    source = _poly("Will Anthropic IPO before 2030?")
    candidates = [_kalshi("WEATHER-1", "Highest temperature in Miami")]
    assert match_market.shortlist(source, candidates) == []


def test_shortlist_includes_resolution_rules_for_judgment():
    # The whole point: Claude must compare settlement rules, not just topic.
    source = _poly("Will Anthropic IPO before 2030?")
    candidates = [
        _kalshi("IPO-ANTH", "Will Anthropic IPO before 2030?",
                rules="Resolves Yes if an S-1 is publicly filed.")
    ]
    result = match_market.shortlist(source, candidates)
    assert "S-1" in result[0]["rules_primary"]


def test_shortlist_handles_a_kalshi_source():
    # Matching should work in either direction.
    source = _kalshi("IPO-ANTH", "Will Anthropic IPO before 2030?")
    candidates = [_kalshi("IPO-ANTH-2", "Will Anthropic IPO before 2030?")]
    assert match_market.shortlist(source, candidates)[0]["score"] > 0.9


def test_shortlist_handles_empty_candidates():
    assert match_market.shortlist(_poly("anything"), []) == []


def test_shortlist_returns_the_full_market_for_downstream_use():
    source = _poly("Will Anthropic IPO before 2030?")
    candidates = [_kalshi("IPO-ANTH", "Will Anthropic IPO before 2030?")]
    result = match_market.shortlist(source, candidates)
    assert result[0]["market"]["ticker"] == "IPO-ANTH"
