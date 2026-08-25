"""insider_bias — the mechanical half of the pipeline, as runnable code.

Stages 1 and 2a (screen, event dedup, family gate, blind-payload build) are
deterministic and belong in code. Everything here can be re-run against a
board and will produce the same candidate set, which is what makes a result
this theory reports reproducible rather than a story about one afternoon.

The stages a script cannot do — dispatching judgment subagents and the main
model's final review — are documented in `RUNBOOK.md` with the exact prompt
files and models. Together those two artifacts are the whole procedure.

**Why the blind payload lives here.** THEORY.md requires judgment to run
blind to price, and every opportunity records `judged_blind=True`. That claim
is only worth something if the payload provably carried no price. On the
first live run the check existed as an inline assertion in a shell heredoc —
so the claim rested on code that was never committed and could not be
re-checked. `build_blind_payload` is that check, made permanent.

The payload is built by **whitelist**, not by deleting known price fields. A
blacklist silently starts leaking the day the Kalshi client adds a field; a
whitelist cannot. `assert_blind` then re-scans the serialized payload as a
belt-and-braces check against a price arriving inside some nested structure.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from theories.insider_bias import screen
from theories.insider_bias.insider_judgment import gate
from tools.domain import Candidate, Market

#: Fields allowed into a judgment payload. Anything not listed is dropped.
EVENT_FIELDS = ("event_ticker", "series_ticker", "title", "close_time")
MARKET_FIELDS = ("ticker", "title", "rules_primary", "rules_secondary",
                 "close_time")

#: Substrings that must never appear in a serialized blind payload. This is
#: the second line of defence behind the whitelist, not the first.
BANNED_KEYS = ("yes_bid", "yes_ask", "no_bid", "no_ask", "mid", "spread",
               "last_price", "fav_side", "fav_price", "implied_prob",
               "entry_price")


class BlindPayloadError(AssertionError):
    """A judgment payload carried price information."""


def dedupe_by_event(candidates: list[Candidate]) -> list[Candidate]:
    """One representative candidate per event, order preserved.

    Sibling strikes on one event share a gate verdict and a thesis judgment —
    different contestants in one show, different dates for one announcement —
    so paying for each separately is waste. On 2026-08-23 this cut 765
    candidates to 274 events.
    """
    seen: set[str] = set()
    out: list[Candidate] = []
    for c in candidates:
        if c.key in seen:
            continue
        seen.add(c.key)
        out.append(c)
    return out


def build_blind_payload(events: list[Candidate],
                        candidates: list[Candidate]) -> list[dict]:
    """Event-level payload for the judgment stage, with no price anywhere.

    Each event carries its title, resolution rules, close time and the list
    of market tickers underneath it — everything needed to judge whether a
    specific group already knows, and nothing about what it costs.
    """
    by_event: dict[str, list[Candidate]] = {}
    for c in candidates:
        by_event.setdefault(c.key, []).append(c)

    payload = []
    for e in events:
        rep = e.legs[0].market
        entry = {f: getattr(rep, f, None) for f in EVENT_FIELDS}
        entry["markets"] = [
            {f: getattr(c.legs[0].market, f, None) for f in MARKET_FIELDS}
            for c in by_event.get(e.key, [])
        ]
        payload.append(entry)
    assert_blind(payload)
    return payload


def assert_blind(payload: list[dict]) -> None:
    """Raise unless the serialized payload is free of price information."""
    blob = json.dumps(payload, default=str)
    hits = sorted({k for k in BANNED_KEYS
                   if re.search(rf'"{re.escape(k)}"', blob)})
    if hits:
        raise BlindPayloadError(
            f"judgment payload carries price fields {hits}. THEORY.md requires "
            "judgment blind to price, and every opportunity records "
            "judged_blind=True — a payload that leaks price makes that record "
            "false. Fix the whitelist rather than the assertion."
        )


def run_mechanical_stages(board: list[Market],
                          now: datetime | None = None) -> dict:
    """Screen → dedupe → gate → blind payload. Returns the full funnel.

    `board` is `tools.board.get_board()` output. The returned dict is the
    reproducible record of what the mechanical half decided:

        {"board_markets", "screened_markets", "events", "gate_counts",
         "gated_out", "survivors", "survivor_markets", "survivor_candidates",
         "payload"}
    """
    now = now or datetime.now(timezone.utc)
    candidates = screen.screen(board, now=now)
    events = dedupe_by_event(candidates)
    survivors, counts = gate.partition(events)
    survivor_keys = {s.key for s in survivors}
    kept = [c for c in candidates if c.key in survivor_keys]
    return {
        "board_markets": len(board),
        "screened_markets": len(candidates),
        "events": len(events),
        "gate_counts": counts,
        "gated_out": len(events) - len(survivors),
        "survivors": len(survivors),
        "survivor_markets": len(kept),
        "survivor_candidates": kept,
        "payload": build_blind_payload(survivors, kept),
    }
