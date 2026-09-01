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
#: **The directory is named for the lane.** `new-theory` used to file
#: into `research/`, which meant every session had to know the two
#: were the same thing -- and a reader looking for "the new-theory
#: backlog" had to be told where it lived.
ROOT_LANES = {"maintenance": "maintenance", "new-theory": "new-theory"}

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
_DATE_PREFIX = re.compile(r"\A(\d{4}-\d{2}-\d{2})-(.+)\Z")


def _today() -> str:
    from tools.db import utcnow

    return utcnow()[:10]


#: A ticket is open or completed, and that is a DIRECTORY rather than a
#: field. The backlog is read by listing, so a finished ticket has to
#: leave it physically -- with a status field alone, every session reads
#: every ticket ever filed to find the few still open, and the backlog
#: gets slower and less useful exactly as the repo gets more history.
STATES = ("open", "completed")


def ticket_dir(
    root: Path, lane: str, theory: str | None = None, state: str = "open",
    theory_path: str | None = None,
) -> Path:
    """Where a ticket for this lane and state belongs.

    **A theory ticket lives inside that theory's own folder**, at
    `<theory path>/tickets/<state>/` -- never under the repo-level
    `tickets/` tree, and never at `theories/<slug>/`.

    `theory_path` is REQUIRED for the theory lane and must come from the
    theory's registry row (`theories.get(conn, slug)["path"]`), because a
    theory's folder is wherever that row says it is. `insider_judgment`
    lives at `theories/insider_bias/insider_judgment`, under a shared
    family parent, so its slug is not its path.

    This used to fall back to `theories/{theory}` when the caller omitted
    the path, and the fallback did real damage: it silently created
    `theories/insider_judgment/`, a phantom directory holding nothing but
    tickets, sitting beside the real theory and invisible as an error.
    A missing path now raises instead, so a caller that forgets gets told
    at once rather than filing work where its theory's expert will never
    look.
    """
    if state not in STATES:
        raise ValueError(f"unknown state {state!r}; expected one of {STATES}")
    if lane == "theory":
        if not theory:
            raise ValueError(
                "a theory ticket needs its theory: theory work lives in that "
                "theory's own folder, never in the main tickets directory"
            )
        if not theory_path:
            raise ValueError(
                f"a theory ticket needs the registry path for {theory!r}, not its "
                "slug: pass theory_path=theories.get(conn, slug)['path']. "
                "A theory folder is wherever its row says -- insider_judgment "
                "lives at theories/insider_bias/insider_judgment -- so "
                "deriving it from the slug creates a phantom directory "
                "beside the real theory."
            )
        return Path(root) / theory_path / "tickets" / state
    if lane not in ROOT_LANES:
        raise ValueError(f"unknown lane {lane!r}; expected one of {LANES}")
    return Path(root) / "tickets" / ROOT_LANES[lane] / state


def create(
    root: Path,
    *,
    lane: str,
    slug: str,
    title: str,
    body: str,
    theory: str | None = None,
    theory_path: str | None = None,
    created: str | None = None,
    created_by: str | None = None,
    author_lane: str | None = None,
    author_focus: str | None = None,
    author_context: str | None = None,
) -> Path:
    """Write a ticket. Returns its path.

    `body` is required and is the whole point: the next session has only
    this file to work from, so a title with nothing under it is a note
    someone will delete rather than a task someone will do.

    The author fields say what the filing session was DOING, which is the
    context a reader cannot reconstruct and the part that makes an
    unfamiliar ticket actionable. `created_by` alone answers "who" and
    not "what they were looking at when they hit this" -- a crash found
    while replaying a 90-day backtest and the same crash found while
    reading docs are different reports of different urgency.
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
    directory = ticket_dir(root, lane, theory,
                           theory_path=theory_path)
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
    ]
    if author_lane:
        head.append(f"author_lane: {author_lane}")
    if author_focus:
        head.append(f"author_focus: {author_focus}")
    if author_context:
        head.append(f"author_context: {author_context.strip()}")
    head += [
        "status: open",
        "---",
        "",
    ]
    path.write_text("\n".join(head) + body.strip() + "\n", encoding="utf-8")
    return path


def _parse(path: Path, lane: str, theory: str | None,
           brief: bool = False) -> dict:
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
        "author_lane": "",
        "author_focus": "",
        "author_context": "",
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
                   "resolution", "author_lane", "author_focus",
                   "author_context"):
            entry[key] = value
    body = front.group(2).strip()
    # A brief entry reports the body's SIZE and not its text. The
    # backlog is read at the start of every session, and once a ticket
    # carries a full spec the bodies dominate everything else in the
    # listing -- so the cheap read has to be the default one.
    if brief:
        entry["body_chars"] = len(body)
    else:
        entry["body"] = body
    return entry


def _scan(directory: Path, lane: str, theory: str | None,
          brief: bool = False) -> list[dict]:
    if not directory.is_dir():
        return []
    return [
        _parse(p, lane, theory, brief=brief)
        for p in sorted(directory.glob("*.md"))
        if p.name != "README.md"
    ]


def backlog(
    root: Path,
    *,
    lane: str | None = None,
    status: str = "open",
    theory: str | None = None,
    brief: bool = False,
) -> list[dict]:
    """Every ticket, oldest first — the list a session chooses work from.

    Oldest first on purpose: a backlog sorted newest-first quietly
    becomes a stack, and the ticket nobody got to is the one that most
    needs picking up.
    """
    root = Path(root)
    # The state IS the directory, so the listing only touches the tickets
    # in the state being asked about -- a repo with a thousand completed
    # tickets reads its open backlog as fast as an empty one.
    state = "completed" if status == "done" else "open"
    found: list[dict] = []
    for lane_name, dirname in ROOT_LANES.items():
        found += _scan(root / "tickets" / dirname / state, lane_name, None,
                       brief=brief)
    theories_dir = root / "theories"
    if theories_dir.is_dir():
        for candidate in sorted(theories_dir.rglob("tickets")):
            if not candidate.is_dir():
                continue
            candidate = candidate / state
            if not candidate.is_dir():
                continue
            owner = candidate.parent.parent.name
            found += _scan(candidate, "theory", owner, brief=brief)
    if lane:
        found = [t for t in found if t["lane"] == lane]
    if theory:
        found = [t for t in found if t["theory"] == theory]
    if status:
        found = [t for t in found if t["status"] == status]
    found.sort(key=lambda t: (t["created"], t["slug"]))
    return found


def close(path: Path, *, resolution: str, now: str | None = None) -> Path:
    """Mark a ticket done and MOVE it into `completed/`. Returns the new path.

    The file is kept, never deleted: a finished ticket is the record of
    what was asked for and why, which is exactly what a future session
    re-deriving the same problem wants. But it leaves the backlog
    physically, because the backlog is a directory listing -- a status
    field alone would make every session read every ticket ever filed to
    find the few still open.
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
    done_dir = path.parent.parent / "completed"
    done_dir.mkdir(parents=True, exist_ok=True)
    done = done_dir / path.name
    done.write_text(raw, encoding="utf-8")
    path.unlink()
    return done


#: Width the rendered backlog is wrapped to. A ticket that does not fit
#: on one line is truncated rather than wrapped: the listing exists to
#: let a session SEE every ticket, and the moment one entry takes two
#: lines the scan stops being a scan.
_WIDTH = 96


def _clip(text: str, width: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= width else text[: width - 1] + "\u2026"


def render(entries: list[dict]) -> str:
    """The backlog as a scannable table — the read a session opens with.

    One line per ticket, grouped by lane, oldest first inside each
    group. What a session needs in order to CHOOSE is the date, the
    slug, and the title; what it needs in order to *do* the work is in
    the file, and it opens the file.

    This is the default because the alternative stopped being usable.
    Tickets carry their design in full -- that is what makes a ticket a
    spec rather than a note -- and dumping every body into the listing
    meant the cheapest, most-repeated read in the repo was also the
    largest, growing with every ticket ever filed.
    """
    if not entries:
        return "no open tickets"
    by_lane: dict[str, list[dict]] = {}
    for entry in entries:
        by_lane.setdefault(entry["lane"], []).append(entry)
    out: list[str] = []
    for lane in ("new-theory", "theory", "maintenance"):
        rows = by_lane.pop(lane, [])
        if not rows:
            continue
        out.append(f"{lane.upper()}  ({len(rows)})")
        for row in rows:
            owner = f" [{row['theory']}]" if row.get("theory") else ""
            head = f"  {row['created']}  {row['slug']}{owner}"
            flag = "  !! MALFORMED" if row.get("malformed") else ""
            out.append(head + flag)
            out.append("      " + _clip(row.get("title"), _WIDTH - 6))
        out.append("")
    for lane, rows in by_lane.items():  # a lane this renderer never heard of
        out.append(f"{lane.upper()}  ({len(rows)})")
        for row in rows:
            out.append(f"  {row['created']}  {row['slug']}")
    return "\n".join(out).rstrip() + "\n"
