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

#: `**Tier:** A · **Verdict:** ...` — the header every STUDY.md carries.
#: Parsed leniently: a study whose header does not match is REPORTED with
#: an empty field rather than dropped, on the same principle as a
#: malformed ticket. A study nobody can classify is still a study
#: somebody has to look at.
#:
#: There is deliberately no `Status` field here any more. See `survey`'s
#: docstring for why: it drifted from the directory it was supposed to
#: describe, and the fix was to stop recording the fact twice.
_FIELD = r"\*\*{name}:?\*\*:?\s*(.+?)(?:\s*·|$)"
_DATE = re.compile(_FIELD.format(name="Date"), re.M)
_VERDICT = re.compile(_FIELD.format(name="Verdict"), re.M)
_TIER = re.compile(_FIELD.format(name="Tier"), re.M)
_TITLE = re.compile(r"^#\s+(.+?)\s*$", re.M)
_SLUG_DATE = re.compile(r"\A(\d{4}-\d{2}-\d{2})-(.+)\Z")


def _clean(text: str) -> str:
    """Strip the markdown a header field carries around its value."""
    text = re.sub(r"\*\*|`|~~", "", str(text or "")).strip()
    return " ".join(text.split())


def _one(pattern: re.Pattern, raw: str) -> str:
    match = pattern.search(raw)
    return _clean(match.group(1)) if match else ""


def survey(root: Path) -> list[dict]:
    """Every study, oldest first, with what its own STUDY.md says.

    **State comes from the directory, never from a header field.** A
    study carried a `**Status:**` line until 2026-09-01, and it drifted
    exactly as a duplicated status field always does: series-bias-mining
    read `complete -- result: not measured` while two open tickets said
    the phase-2 sweep was unfinished and pass 4's filter was reversed.
    The header and the work disagreed, and nothing could tell you which
    was right. Now the directory is the only claim.
    """
    from tools import tickets

    root = Path(root)
    out: list[dict] = []
    for holder, owner in _study_homes(root):
        for state in tickets.states_for("study"):
            directory = holder / state
            if not directory.is_dir():
                continue
            for folder in sorted(directory.iterdir()):
                marker = folder / tickets.STUDY_FILE
                if not marker.is_file():
                    continue
                out.append(_row(folder, marker, state, owner, root))
    # LEGACY: the pre-2026-09-01 tree, read so the repo stays green
    # across the migration. Removed once nothing lives here.
    legacy = root / "studies"
    if legacy.is_dir():
        for folder in sorted(legacy.iterdir()):
            marker = folder / "STUDY.md"
            if marker.is_file():
                out.append(_row(folder, marker, "answer", None, root))
    out.sort(key=lambda r: (r["date"], r["slug"]))
    return out


def _study_homes(root: Path):
    """Every directory that can hold study state dirs, with its owner."""
    yield root / "tickets" / "study", None
    theories = root / "theories"
    if theories.is_dir():
        for candidate in sorted(theories.rglob("studies")):
            if candidate.is_dir():
                yield candidate, candidate.parent.name


def _row(folder: Path, marker: Path, state: str, owner: str | None,
        root: Path) -> dict:
    raw = marker.read_text(encoding="utf-8", errors="replace")
    match = _SLUG_DATE.match(folder.name)
    return {
        "slug": folder.name,
        "date": match.group(1) if match else _one(_DATE, raw),
        "title": _one(_TITLE, raw),
        "state": state,
        "complete": state == "answer",
        "verdict": _one(_VERDICT, raw),
        "tier": _one(_TIER, raw),
        "owner": owner,
        "path": str(folder.relative_to(root)).replace("\\", "/"),
    }


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
        owner = f"  [{row['owner']}]" if row["owner"] else "  [no owner]"
        out.append(f"{mark} {row['slug']}  ({row['state']}){owner}")
        detail = row["verdict"] or row["title"]
        if detail:
            out.append(f"      {_clip(detail, 84)}")
    flight = sum(1 for r in rows if not r["complete"])
    if flight:
        out.append(f"  (* {flight} not answered — in flight, not forgotten)")
    return "\n".join(out) + "\n"
