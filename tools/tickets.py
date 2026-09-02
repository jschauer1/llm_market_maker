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
#:
#: `theory` and `study` are the OWNED lanes: their tickets live inside
#: the thing they are about, never in the repo-level backlog. A theory
#: folder and a study folder are each supposed to hold everything their
#: expert needs, and queued work against them is part of that.
LANES = ("theory", "study", "new-theory", "maintenance")

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


#: A ticket's state IS a directory rather than a field. The backlog is
#: read by listing, so a finished ticket has to leave it physically --
#: with a status field alone, every session reads every ticket ever filed
#: to find the few still open, and the backlog gets slower and less
#: useful exactly as the repo gets more history.
#:
#: The STATES a lane has are the lane's own. `study` is the odd one and
#: deliberately so: a study is a measurement that answers a question, its
#: terminal state is `answer/`, and it has NO `completed/`. That is what
#: makes a study permanent -- the purge matches `completed/`, so a
#: finished study is simply not a thing the query can match. Permanence
#: falls out of the state names instead of being an exemption somebody
#: has to remember.
LANE_STATES: dict[str, tuple[str, ...]] = {
    "theory": ("open", "completed"),
    "maintenance": ("open", "completed"),
    "new-theory": ("open", "completed"),
    "study": ("question", "investigation", "answer"),
}

#: The file-based lanes' states, kept under the old name because callers
#: outside this module still ask for "the states a normal ticket has".
STATES = ("open", "completed")

#: The study lane's ticket filename. A study ticket is a DIRECTORY --
#: a measurement has code and data and they belong with it -- and this
#: is the one file inside it that is the ticket. It is `STUDY.md` rather
#: than `TICKET.md` because the study header and the ticket frontmatter
#: describe the same thing, and two files would mean two places to say
#: what this measurement is.
STUDY_FILE = "STUDY.md"


def states_for(lane: str) -> tuple[str, ...]:
    """The states this lane declares, in pipeline order."""
    try:
        return LANE_STATES[lane]
    except KeyError:
        raise ValueError(
            f"unknown lane {lane!r}; expected one of {LANES}"
        ) from None


def ticket_dir(
    root: Path, lane: str, theory: str | None = None, state: str | None = None,
    theory_path: str | None = None, study: str | None = None,
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
    if lane not in LANES:
        raise ValueError(f"unknown lane {lane!r}; expected one of {LANES}")
    allowed = states_for(lane)
    if state is None:
        state = allowed[0]
    if state not in allowed:
        raise ValueError(
            f"lane {lane!r} has no state {state!r}; it declares {allowed}"
        )
    if lane == "study":
        # A study lives inside the theory that owns it, and in the root
        # `study` lane when no single theory does. Measured 2026-09-01:
        # of 15 studies, 7 served exactly one theory and 5 served none,
        # so both homes are load-bearing rather than one being a
        # fallback for the other.
        if theory_path:
            return Path(root) / theory_path / "studies" / state
        if theory:
            raise ValueError(
                f"a study owned by {theory!r} needs that theory's registry "
                "path, not its slug: pass "
                "theory_path=theories.get(conn, slug)['path']"
            )
        return Path(root) / "tickets" / "study" / state
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
    study: str | None = None,
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
                           theory_path=theory_path, study=study)
    directory.mkdir(parents=True, exist_ok=True)
    if lane == "study":
        # The ticket is the directory; STUDY.md inside it is the file.
        holder = directory / f"{day}-{slug}"
        if holder.exists():
            raise ValueError(f"study already exists: {holder}")
        holder.mkdir(parents=True)
        path = holder / STUDY_FILE
    else:
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
    if study:
        head.append(f"study: {study}")
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
           brief: bool = False, study: str | None = None) -> dict:
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
        "study": study,
        "title": "",
        "status": "open",
        "state": "open",
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
                   "study", "resolution", "author_lane", "author_focus",
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
         brief: bool = False, study: str | None = None,
         state: str = "open") -> list[dict]:
    """Every ticket in one state directory.

    The study lane's tickets are directories holding a STUDY.md; every
    other lane's are plain .md files. Both are parsed the same way once
    found -- only the glob differs.
    """
    if not directory.is_dir():
        return []
    if lane == "study":
        found = sorted(
            child / STUDY_FILE for child in directory.iterdir()
            if child.is_dir() and (child / STUDY_FILE).is_file()
        )
    else:
        found = [p for p in sorted(directory.glob("*.md"))
                 if p.name != "README.md"]
    rows = []
    for path in found:
        entry = _parse(path, lane, theory, brief=brief, study=study)
        if lane == "study":
            # The slug is the DIRECTORY's name; STUDY.md carries no date.
            match = _DATE_PREFIX.match(path.parent.name)
            created, slug = (match.groups() if match
                             else ("", path.parent.name))
            entry["created"], entry["slug"] = created, slug
        entry["state"] = state
        # The directory a ticket sits in, not its frontmatter, is what
        # `backlog(status=...)` filters on below -- nothing rewrites a
        # moved ticket's `status:` field, so a study sitting in `answer/`
        # would otherwise keep `status: open` forever and be dropped from
        # a `--status done` query even though the walk found it there.
        # Deriving `status` from the state directory keeps the two from
        # ever being able to disagree, which is the entire point of
        # making state a directory instead of a field.
        entry["status"] = _reported_as(lane, state)
        rows.append(entry)
    return rows


def _reported_as(lane: str, state: str) -> str:
    """Which of open/done a state counts as, for callers that filter on
    the old two-value vocabulary.

    A study being measured is OPEN work -- it is not finished until it
    has an answer -- so `question` and `investigation` report as open and
    only `answer` reports as done. This keeps `--status open` meaning
    "work still to do" across every lane.
    """
    if lane != "study":
        return "done" if state == "completed" else "open"
    return "done" if state == "answer" else "open"


def backlog(
    root: Path,
    *,
    lane: str | None = None,
    status: str = "open",
    theory: str | None = None,
    brief: bool = False,
    study: str | None = None,
) -> list[dict]:
    """Every ticket, oldest first — the list a session chooses work from.

    Oldest first on purpose: a backlog sorted newest-first quietly
    becomes a stack, and the ticket nobody got to is the one that most
    needs picking up.
    """
    root = Path(root)
    # The state IS the directory, so the listing only touches the tickets
    # in the states being asked about -- a repo with a thousand completed
    # tickets reads its open backlog as fast as an empty one. Every lane
    # can have more than two states (the study lane has three), so this
    # walks every state the lane declares and keeps the ones that report
    # as the wanted bucket, rather than assuming "open" and "completed"
    # are the only names in play.
    wanted = "done" if status == "done" else "open"
    found: list[dict] = []
    for lane_name, dirname in ROOT_LANES.items():
        for st in states_for(lane_name):
            if _reported_as(lane_name, st) != wanted:
                continue
            found += _scan(root / "tickets" / dirname / st, lane_name,
                           None, brief=brief, state=st)
    for st in states_for("study"):
        if _reported_as("study", st) != wanted:
            continue
        found += _scan(root / "tickets" / "study" / st, "study", None,
                       brief=brief, state=st)
    theories_dir = root / "theories"
    if theories_dir.is_dir():
        for candidate in sorted(theories_dir.rglob("tickets")):
            if not candidate.is_dir():
                continue
            owner = candidate.parent.name
            for st in states_for("theory"):
                if _reported_as("theory", st) != wanted:
                    continue
                found += _scan(candidate / st, "theory", owner,
                               brief=brief, state=st)
        for candidate in sorted(theories_dir.rglob("studies")):
            if not candidate.is_dir():
                continue
            owner = candidate.parent.name
            for st in states_for("study"):
                if _reported_as("study", st) != wanted:
                    continue
                found += _scan(candidate / st, "study", owner,
                               brief=brief, state=st)
    if lane:
        found = [t for t in found if t["lane"] == lane]
    if theory:
        found = [t for t in found if t["theory"] == theory]
    if study:
        found = [t for t in found if t["study"] == study]
    if status:
        found = [t for t in found if t["status"] == status]
    found.sort(key=lambda t: (t["created"], t["slug"]))
    return found


def advance(path: Path, *, to: str, note: str,
           now: str | None = None) -> Path:
    """Move a ticket into its next state. Returns the new path.

    The note is required and is appended to the body under a dated
    heading, because a state change nobody explained is a state change
    the next session has to reverse-engineer. For a study moving to
    `investigation`, the note is what the measurement is about to do;
    moving to `answer`, it is what it found.

    Moving BACKWARDS is refused. A pipeline that can run in reverse is a
    status field wearing a directory's clothes, and the whole reason
    state is a directory here is that a field lets two places disagree
    about where the work stands.
    """
    if not note or not note.strip():
        raise ValueError("a note is required: say why it moved")
    path = Path(path)
    is_study = path.name == STUDY_FILE
    item = path.parent if is_study else path
    lane_dir = item.parent
    allowed = states_for(_lane_of(lane_dir))
    here = lane_dir.name
    if to not in allowed:
        raise ValueError(
            f"lane {_lane_of(lane_dir)!r} has no state {to!r}; "
            f"it declares {allowed}"
        )
    if allowed.index(to) <= allowed.index(here):
        raise ValueError(
            f"cannot move backwards: {here!r} -> {to!r}. Close the ticket "
            "or file a new one instead."
        )
    target = lane_dir.parent / to
    target.mkdir(parents=True, exist_ok=True)
    moved = target / item.name
    if moved.exists():
        raise ValueError(f"already present in {to}: {moved}")
    item.rename(moved)
    body_file = moved / STUDY_FILE if is_study else moved
    raw = body_file.read_text(encoding="utf-8").rstrip()
    stamp = now or _today()
    body_file.write_text(
        f"{raw}\n\n## {to} — {stamp}\n\n{note.strip()}\n", encoding="utf-8")
    return body_file


def _lane_of(state_dir: Path) -> str:
    """The lane a state directory belongs to, from its container.

    `<owner>/studies/answer` and `tickets/study/answer` are both the
    study lane; `tickets/maintenance/open` is maintenance. The container
    directory names the lane, which is the same fact `ticket_dir` writes
    down in the other direction.
    """
    container = state_dir.parent.name
    if container in ("studies", "study"):
        return "study"
    for lane, dirname in ROOT_LANES.items():
        if container == dirname:
            return lane
    if container == "tickets":
        return "theory"
    raise ValueError(f"cannot tell which lane {state_dir} belongs to")


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
    for lane in ("new-theory", "theory", "study", "maintenance"):
        rows = by_lane.pop(lane, [])
        if not rows:
            continue
        out.append(f"{lane.upper()}  ({len(rows)})")
        for row in rows:
            owner = row.get("theory") or row.get("study") or ""
            owner = f" [{owner}]" if owner else ""
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
