"""Mechanical cross-platform market matching (spec sections 3, 6, 9).

This tool narrows thousands of Kalshi markets to a handful of plausible
equivalents for a Polymarket (or other non-Kalshi) finding. It deliberately
stops there.

Deciding whether two markets are REALLY the same is a judgment call and
belongs to Claude or a subagent reading this shortlist — and that judgment
must compare RESOLUTION CRITERIA, not just topic. Two markets about the same
event with different settlement rules are different markets, and a keyword
score cannot see the difference. That is why `rules_primary` travels with
every candidate.
"""

from __future__ import annotations

import re
from datetime import datetime

STOPWORDS = frozenset(
    """
    a an the will be is are was were do does did to of in on at by for from
    with and or if then than that this these those it its as into over under
    before after between during about who whom which what when where how
    """.split()
)

DATE_WEIGHT = 0.2
TOKEN_WEIGHT = 0.8
_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set[str]:
    """Lowercase content words, stopwords removed."""
    if not text:
        return set()
    return {
        word
        for word in _WORD.findall(text.lower())
        if word not in STOPWORDS and len(word) > 1
    }


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        # TypeError/ValueError: malformed timestamp text. AttributeError:
        # stamp wasn't a string at all (e.g. an int epoch), so .replace
        # doesn't exist. All three mean "treat this like a missing date."
        return None


def _date_similarity(source_end: str | None, candidate_end: str | None) -> float:
    """1.0 for same-day, decaying to 0 across a year apart."""
    left, right = _parse(source_end), _parse(candidate_end)
    if left is None or right is None:
        return 0.5  # unknown: neither reward nor punish
    try:
        days = abs((left - right).days)
    except TypeError:
        # One parsed naive, the other timezone-aware: can't subtract.
        # Not confident enough to compare, so treat as unavailable.
        return 0.5
    return max(0.0, 1.0 - days / 365.0)


def score_pair(
    source_text: str,
    candidate_text: str,
    source_end: str | None = None,
    candidate_end: str | None = None,
) -> float:
    """Similarity in [0, 1]: Jaccard token overlap plus date proximity."""
    left, right = tokenize(source_text), tokenize(candidate_text)
    if not left or not right:
        return 0.0
    overlap = len(left & right) / len(left | right)
    if overlap == 0.0:
        return 0.0
    left_dt, right_dt = _parse(source_end), _parse(candidate_end)
    if left_dt is None or right_dt is None:
        # No usable date on at least one side — whether the field was
        # absent or just unparseable garbage, judge on tokens alone rather
        # than diluting a strong token match with a neutral guess.
        return overlap
    return TOKEN_WEIGHT * overlap + DATE_WEIGHT * _date_similarity(
        source_end, candidate_end
    )


def _text_of(market: dict) -> str:
    return market.get("question") or market.get("title") or ""


def _end_of(market: dict) -> str | None:
    return market.get("end_date") or market.get("close_time")


def shortlist(
    source: dict,
    candidates: list[dict],
    top_n: int = 5,
    min_score: float = 0.1,
) -> list[dict]:
    """Plausible Kalshi equivalents for `source`, best first.

    A shortlist, not a decision. Every entry carries `rules_primary` so the
    judgment step can compare settlement criteria rather than topic alone.
    """
    source_text = _text_of(source)
    source_end = _end_of(source)

    scored = []
    for market in candidates:
        score = score_pair(
            source_text, _text_of(market), source_end, _end_of(market)
        )
        if score < min_score:
            continue
        scored.append(
            {
                "ticker": market.get("ticker"),
                "title": market.get("title"),
                "score": score,
                "rules_primary": market.get("rules_primary"),
                "close_time": market.get("close_time"),
                "market": market,
            }
        )

    scored.sort(key=lambda entry: entry["score"], reverse=True)
    return scored[:top_n]
