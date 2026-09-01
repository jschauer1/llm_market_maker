"""Studies — what has been measured, read off disk rather than indexed.

**A study is a measurement that answers a question. It never bets.**
That is the whole definition, and it is what separates a study from a
theory: a `Theory` screens the board, prices candidates, records
opportunities and is scored on whether it made money; a study runs a
measurement over history, writes down what it found, and stops. No
ledger row, no ticker, no score. `STUDY.md` marks the folder.

You run one when you need to know something *before* you act — whether
an idea is worth building (`calendar-arb-firing-rate` found zero
violations across ten snapshots and killed a spec in an afternoon),
whether a theory's number is real (`settlement-day-clustering` found two
theories' strong results were both one settlement day), or how something
should work for everything at once (`entry-timing`). The payoff is
asymmetric: a study that finds nothing has still stopped you building
the wrong thing, at a day's cost instead of a month's.

**This module surveys; it does not index.** Every fact here is read from
the study's own `STUDY.md` at display time, because a hand-maintained
index of documents that live elsewhere is precisely what rotted on the
theory spec tree — 22 documents still reading "not yet proposed as a
theory" weeks after four had become theories, one was retired and two
were dead. One source of truth, read when asked.

The survey exists because a study's verdict was reachable *only* by
opening it, which breaks the supervisor contract in CLAUDE.md: every
fact a supervisor needs in order to supervise has to surface in a shared
structure.
"""

from __future__ import annotations

import re
from pathlib import Path

#: `**Status:** complete · **Tier:** A · **Verdict:** ...` — the header
#: every STUDY.md carries. Parsed leniently: a study whose header does
#: not match is REPORTED with an empty status rather than dropped, on the
#: same principle as a malformed ticket. A study nobody can classify is
#: still a study somebody has to look at.
_FIELD = r"\*\*{name}:?\*\*:?\s*(.+?)(?:\s*·|$)"
_DATE = re.compile(_FIELD.format(name="Date"), re.M)
_STATUS = re.compile(_FIELD.format(name="Status"), re.M)
_VERDICT = re.compile(_FIELD.format(name="Verdict"), re.M)
_TIER = re.compile(_FIELD.format(name="Tier"), re.M)
_TITLE = re.compile(r"^#\s+(.+?)\s*$", re.M)
_SLUG_DATE = re.compile(r"\A(\d{4}-\d{2}-\d{2})-(.+)\Z")

#: A study is finished when its own header says so. Anything else --
#: `collecting`, a pre-registration written but not yet run, no header at
#: all -- is work in flight, and the distinction is what the floor
#: reports on.
_COMPLETE = ("complete", "done", "closed")


def _clean(text: str) -> str:
    """Strip the markdown a header field carries around its value."""
    text = re.sub(r"\*\*|`|~~", "", str(text or "")).strip()
    return " ".join(text.split())


def _one(pattern: re.Pattern, raw: str) -> str:
    match = pattern.search(raw)
    return _clean(match.group(1)) if match else ""


def survey(root: Path) -> list[dict]:
    """Every study, oldest first, with what its own STUDY.md says."""
    from tools import tickets

    root = Path(root)
    directory = root / "studies"
    if not directory.is_dir():
        return []
    out: list[dict] = []
    for folder in sorted(directory.iterdir()):
        marker = folder / "STUDY.md"
        if not marker.is_file():
            continue                      # __pycache__, data dirs, strays
        raw = marker.read_text(encoding="utf-8", errors="replace")
        match = _SLUG_DATE.match(folder.name)
        status = _one(_STATUS, raw)
        open_tickets = len(tickets.backlog(root, study=folder.name))
        out.append({
            "slug": folder.name,
            "date": match.group(1) if match else _one(_DATE, raw),
            "title": _one(_TITLE, raw),
            "status": status,
            "complete": status.lower().startswith(_COMPLETE),
            "verdict": _one(_VERDICT, raw),
            "tier": _one(_TIER, raw),
            "open_tickets": open_tickets,
            "path": f"studies/{folder.name}",
        })
    return out


def _clip(text: str, width: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= width else text[: width - 1] + "…"


def render(rows: list[dict]) -> str:
    """The survey as a scannable block — what the floor reports."""
    if not rows:
        return "no studies\n"
    out: list[str] = []
    for row in rows:
        mark = " " if row["complete"] else "*"
        tickets_note = (f"  {row['open_tickets']} open"
                        if row["open_tickets"] else "")
        head = f"{mark} {row['slug']}"
        state = row["status"] or "(no status line)"
        out.append(f"{head}  [{_clip(state, 34)}]{tickets_note}")
        detail = row["verdict"] or row["title"]
        if detail:
            out.append(f"      {_clip(detail, 84)}")
    flight = sum(1 for r in rows if not r["complete"])
    if flight:
        out.append(f"  (* {flight} not complete — in flight, not forgotten)")
    return "\n".join(out) + "\n"
