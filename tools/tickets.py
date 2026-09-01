"""Tickets — one markdown file per unit of work, read as a backlog.

`go` gives a session four lanes and asks it to pick one and stay in it.
Tickets are what make that affordable: work you notice but are not in the
lane for gets written down instead of done, so focus costs nothing and
nothing is lost.

**A ticket lives next to the thing it is about.** Theory work goes in
that theory's own `tickets/` folder, because a theory folder is supposed
to hold everything its expert needs and queued work is part of that.
Everything else goes under `tickets/<lane>/` at the repo root, where the
lane is the directory — so "what maintenance is open" is a listing, not a
query.

It is also the low-interrupt channel between sessions. A message costs a
working peer their focus; a ticket costs them nothing and waits. Message
a peer when they must act now, and file a ticket for everything else.

Fields live in YAML-ish frontmatter and the body is the task itself,
written for a session that was not there when it was filed.
"""

from __future__ import annotations

import re
from pathlib import Path

#: The lanes a session can be in. `floor` files no tickets -- it runs a
#: fixed procedure daily -- but may write them for any other lane.
LANES = ("theory", "new-theory", "maintenance")

#: Lanes whose tickets live at the repo root, one directory each.
ROOT_LANES = {"maintenance": "maintenance", "new-theory": "research"}

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
_DATE_PREFIX = re.compile(r"\A(\d{4}-\d{2}-\d{2})-(.+)\Z")


def _today() -> str:
    from tools.db import utcnow

    return utcnow()[:10]


def ticket_dir(root: Path, lane: str, theory: str | None = None) -> Path:
    """Where a ticket for this lane belongs."""
    if lane == "theory":
        if not theory:
            raise ValueError(
                "a theory ticket needs its theory: theory work lives in that "
                "theory's own folder, never in the main tickets directory"
            )
        return Path(root) / "theories" / theory / "tickets"
    if lane not in ROOT_LANES:
        raise ValueError(f"unknown lane {lane!r}; expected one of {LANES}")
    return Path(root) / "tickets" / ROOT_LANES[lane]


def create(
    root: Path,
    *,
    lane: str,
    slug: str,
    title: str,
    body: str,
    theory: str | None = None,
    created: str | None = None,
    created_by: str | None = None,
) -> Path:
    """Write a ticket. Returns its path.

    `body` is required and is the whole point: the next session has only
    this file to work from, so a title with nothing under it is a note
    someone will delete rather than a task someone will do.
    """
    if lane not in LANES:
        raise ValueError(f"unknown lane {lane!r}; expected one of {LANES}")
    if not slug or not slug.strip():
        raise ValueError("a slug is required")
    if not title or not title.strip():
        raise ValueError("a title is required")
    if not body or not body.strip():
        raise ValueError(
            "a body is required: say what to do, for a session that was "
            "not here when you filed this"
        )
    day = created or _today()
    directory = ticket_dir(root, lane, theory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{day}-{slug}.md"
    if path.exists():
        raise ValueError(f"ticket already exists: {path}")
    head = [
        "---",
        f"title: {title.strip()}",
        f"lane: {lane}",
    ]
    if theory:
        head.append(f"theory: {theory}")
    head += [
        f"created: {day}",
        f"created_by: {created_by or 'unknown'}",
        "status: open",
        "---",
        "",
    ]
    path.write_text("\n".join(head) + body.strip() + "\n", encoding="utf-8")
    return path


def _parse(path: Path, lane: str, theory: str | None) -> dict:
    """One ticket as a dict. A file that cannot be parsed is REPORTED.

    Never skipped: a ticket nobody can read is work nobody will do, and
    dropping it silently is the one behaviour a backlog must not have.
    The directory still tells us the lane, so a malformed ticket is at
    least visible to the session that could fix it.
    """
    raw = path.read_text(encoding="utf-8")
    stem = path.stem
    match = _DATE_PREFIX.match(stem)
    created, slug = match.groups() if match else ("", stem)
    entry = {
        "path": str(path),
        "slug": slug,
        "created": created,
        "lane": lane,
        "theory": theory,
        "title": "",
        "status": "open",
        "created_by": "",
        "malformed": False,
    }
    front = _FRONTMATTER.match(raw)
    if front is None:
        entry["malformed"] = True
        return entry
    for line in front.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key in ("title", "status", "created_by", "created", "theory",
                   "resolution"):
            entry[key] = value
    entry["body"] = front.group(2).strip()
    return entry


def _scan(directory: Path, lane: str, theory: str | None) -> list[dict]:
    if not directory.is_dir():
        return []
    return [
        _parse(p, lane, theory)
        for p in sorted(directory.glob("*.md"))
        if p.name != "README.md"
    ]


def backlog(
    root: Path,
    *,
    lane: str | None = None,
    status: str = "open",
    theory: str | None = None,
) -> list[dict]:
    """Every ticket, oldest first — the list a session chooses work from.

    Oldest first on purpose: a backlog sorted newest-first quietly
    becomes a stack, and the ticket nobody got to is the one that most
    needs picking up.
    """
    root = Path(root)
    found: list[dict] = []
    for lane_name, dirname in ROOT_LANES.items():
        found += _scan(root / "tickets" / dirname, lane_name, None)
    theories_dir = root / "theories"
    if theories_dir.is_dir():
        for candidate in sorted(theories_dir.rglob("tickets")):
            if not candidate.is_dir():
                continue
            owner = candidate.parent.name
            found += _scan(candidate, "theory", owner)
    if lane:
        found = [t for t in found if t["lane"] == lane]
    if theory:
        found = [t for t in found if t["theory"] == theory]
    if status:
        found = [t for t in found if t["status"] == status]
    found.sort(key=lambda t: (t["created"], t["slug"]))
    return found


def close(path: Path, *, resolution: str, now: str | None = None) -> Path:
    """Mark a ticket done, keeping the file.

    A finished ticket is the record of what was asked for and why;
    deleting it loses the only trace of the request, which is exactly
    what a future session re-deriving the same problem would want.
    """
    if not resolution or not resolution.strip():
        raise ValueError("a resolution is required: say what happened")
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    if "status: open" not in raw:
        raise ValueError(f"ticket {path} is not open")
    raw = raw.replace("status: open", "status: done", 1)
    raw = raw.replace(
        "\n---\n",
        f"\nclosed: {now or _today()}\nresolution: {resolution.strip()}\n---\n",
        1,
    ) if raw.count("\n---\n") >= 1 else raw
    path.write_text(raw, encoding="utf-8")
    return path
