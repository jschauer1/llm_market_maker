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
import subprocess
from datetime import date
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
    # A new-theory ticket IS a spec, and it earns its way to a build
    # order. `evidence` is where the cheapest decisive measurement runs
    # against the bar the spec wrote before looking; `implement` means
    # that measurement cleared it. The stage is not optional -- a spec
    # that jumps from `open` to `implement` is a theory built on a thesis
    # nobody tested, which is the failure the whole new-theory lane
    # exists to prevent.
    "new-theory": ("open", "evidence", "implement", "completed"),
    "study": ("question", "investigation", "answer"),
}

#: The study lane's ticket filename. A study ticket is a DIRECTORY --
#: a measurement has code and data and they belong with it -- and this
#: is the one file inside it that is the ticket. It is `STUDY.md` rather
#: than `TICKET.md` because the study header and the ticket frontmatter
#: describe the same thing, and two files would mean two places to say
#: what this measurement is.
STUDY_FILE = "STUDY.md"

#: The four ways a new-theory spec can end, and the reason the vocabulary
#: is fixed: `disproven` and `underpowered` mean OPPOSITE things about
#: re-proposing, and today that distinction is invisible in free text.
#:
#:   built        became a running theory -- name it
#:   disproven    the bar was met and the thesis failed. Not re-proposable.
#:                `calendar-arb` and `smile-smoothing` are the worked
#:                examples: measured, and the answer was no.
#:   underpowered the measurement COULD NOT REACH the bar -- population too
#:                thin, history too short, liquidity too low. This is a
#:                different claim ("we could not tell"), and it IS
#:                re-proposable when conditions change.
#:   superseded   folded into another spec or theory
#:
#: Six months later a free-text resolution makes a dead thesis and an
#: unmeasured one look identical, which is how one gets rebuilt and the
#: other gets abandoned. The verdict is the resolution's first word, so
#: the sentence a session would have written anyway still fits after the
#: colon.
NEW_THEORY_RESOLUTIONS = ("built", "disproven", "underpowered", "superseded")

#: Closing one of these elevates the finding into the ideas registry
#: BEFORE the file may be deleted. See `close`.
_RESOLUTIONS_NEEDING_A_REGISTRY_ENTRY = ("disproven", "underpowered")


def states_for(lane: str) -> tuple[str, ...]:
    """The states this lane declares, in pipeline order."""
    try:
        return LANE_STATES[lane]
    except KeyError:
        raise ValueError(
            f"unknown lane {lane!r}; expected one of {LANES}"
        ) from None


def slug_of(path: Path) -> str:
    """A ticket's slug -- its filename minus the dated prefix.

    A study is the exception, and for the same reason `_scan` treats it as
    one: the ticket is the DIRECTORY and `STUDY.md` is only the file
    inside it, so the slug is the directory's name. Deriving it from the
    stem would call every study in the repo "STUDY".

    This is the identity a `new-theory` close looks an idea up by, so it
    has to agree with what a session typed at `ideas record` -- the slug,
    never the dated filename.
    """
    path = Path(path)
    name = path.parent.name if path.name == STUDY_FILE else path.stem
    match = _DATE_PREFIX.match(name)
    return match.group(2) if match else name


def ticket_dir(
    root: Path, lane: str, theory: str | None = None, state: str | None = None,
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
    # Everything left is a ROOT_LANE: `lane in LANES` was checked at the
    # top and the study and theory branches above return. There used to
    # be a second `lane not in ROOT_LANES` raise here, unreachable by
    # construction -- and an unreachable guard is worse than none, because
    # a reader has to work out for themselves that it never fires.
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
    directory = ticket_dir(root, lane, theory, theory_path=theory_path)
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
    if lane != "study":
        # **The study lane gets NO `status:` field, and this exception is
        # the whole point of the lane.** Every other lane's ticket is a
        # flat file whose frontmatter is the ticket, and `close()` rewrites
        # `status: open` -> `status: done` as it moves the file, so the
        # field and the directory are written in the same operation and
        # cannot drift.
        #
        # Nothing rewrites a study's. A study moves by `advance()`, which
        # renames the directory and touches no frontmatter -- so a
        # `status: open` written at creation would still read `open` after
        # the study reached `answer/`, which is EXACTLY the defect this
        # phase existed to remove: series-bias-mining's header claimed
        # `**Status:** complete` while two open tickets said its phase-2
        # sweep was unfinished, and nothing could tell you which was right.
        # `_scan` derives `status` from the state directory, so no code is
        # fooled -- but a human reading the file is, and that human is the
        # one the duplicated field burned the first time.
        head.append("status: open")
    head += ["---", ""]
    path.write_text("\n".join(head) + body.strip() + "\n", encoding="utf-8")
    return path


#: A markdown document's first `# ` heading — the title a STUDY.md
#: carries when it carries no frontmatter. `tools/studies.py` reads a
#: study's title exactly this way; the pattern is duplicated rather than
#: imported because `studies` imports `tickets` and one of the two has to
#: not depend on the other.
_HEADING = re.compile(r"^#\s+(.+?)\s*$", re.M)


def _one_heading(raw: str) -> str:
    match = _HEADING.search(raw)
    return " ".join(match.group(1).split()) if match else ""


def _missing_frontmatter_is_normal(lane: str) -> bool:
    """Whether a file in this lane may legitimately have no frontmatter.

    **Only the study lane.** A study's `STUDY.md` is a study document
    first and a ticket second: it leads with a `# ` heading and a
    `**Date:** ... **Verdict:** ...` header that predate this pipeline,
    and 12 of the 15 studies migrated on 2026-09-01 have no ticket
    frontmatter at all. Flagging those made `tickets list --lane study
    --status done` print 12 `!! MALFORMED` rows with blank titles --
    a permanent false positive on the one signal that exists so a
    genuinely unreadable ticket is VISIBLE. An alarm that is always on
    is worse than no alarm, because the day a real one fires it is
    indistinguishable from the noise.

    For the file-based lanes the frontmatter genuinely IS the ticket --
    there is no other place a maintenance ticket's title, lane or author
    context lives -- so absent frontmatter there is still malformed.
    """
    return lane == "study"


def _parse(path: Path, lane: str, theory: str | None,
           brief: bool = False) -> dict:
    """One ticket as a dict. A file that cannot be parsed is REPORTED.

    Never skipped: a ticket nobody can read is work nobody will do, and
    dropping it silently is the one behaviour a backlog must not have.
    The directory still tells us the lane, so a malformed ticket is at
    least visible to the session that could fix it.

    **`malformed` means something different for the study lane**, and the
    difference is the point -- see `_missing_frontmatter_is_normal`.
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
        # A ticket may name a study it is work against, as three of
        # mention_family's do. That is a frontmatter cross-reference and
        # nothing else -- it is read off the file below, never seeded from
        # a caller's filter, which is how `backlog(study=...)` used to
        # match every ticket that had no `study:` line at all.
        "study": "",
        "title": "",
        "status": "",
        # Seeded EMPTY, not "open": `open` is not a state the study lane
        # declares, and a default that is wrong for a whole lane reads as
        # a fact rather than a placeholder. `_scan` sets both from the
        # state directory, which is the only thing entitled to say.
        "state": "",
        "created_by": "",
        "author_lane": "",
        "author_focus": "",
        "author_context": "",
        "malformed": False,
    }
    front = _FRONTMATTER.match(raw)
    if front is None:
        if _missing_frontmatter_is_normal(lane):
            entry["title"] = _one_heading(raw)
            return entry
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
    if not entry["title"] and _missing_frontmatter_is_normal(lane):
        entry["title"] = _one_heading(raw)
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


def _scan(directory: Path, lane: str, theory: str | None, state: str,
         brief: bool = False) -> list[dict]:
    """Every ticket in one state directory.

    `state` is REQUIRED rather than defaulted to `"open"`: it is the
    caller's own loop variable over `states_for(lane)`, and the study
    lane has no `open` state for a default to fall back to. A default
    that is wrong for an entire lane is a bug waiting for the one caller
    who forgets to pass it.

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
        entry = _parse(path, lane, theory, brief=brief)
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
                           None, st, brief=brief)
    for st in states_for("study"):
        if _reported_as("study", st) != wanted:
            continue
        found += _scan(root / "tickets" / "study" / st, "study", None, st,
                       brief=brief)
    theories_dir = root / "theories"
    if theories_dir.is_dir():
        for candidate in sorted(theories_dir.rglob("tickets")):
            if not candidate.is_dir():
                continue
            owner = candidate.parent.name
            for st in states_for("theory"):
                if _reported_as("theory", st) != wanted:
                    continue
                found += _scan(candidate / st, "theory", owner, st,
                               brief=brief)
        for candidate in sorted(theories_dir.rglob("studies")):
            if not candidate.is_dir():
                continue
            owner = candidate.parent.name
            for st in states_for("study"):
                if _reported_as("study", st) != wanted:
                    continue
                found += _scan(candidate / st, "study", owner, st,
                               brief=brief)
    if lane:
        found = [t for t in found if t["lane"] == lane]
    if theory:
        found = [t for t in found if t["theory"] == theory]
    if study:
        # A ticket may name a study it is work AGAINST -- three of
        # mention_family's do, all pointing at series-bias-mining. This
        # filter reads that frontmatter cross-reference and nothing else.
        # It used to be threaded down into `_parse`, which seeded
        # `entry["study"]` with the filter value, so every ticket WITHOUT
        # a `study:` line compared equal to it and `--study anything`
        # returned the whole backlog.
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
    lane = _lane_of(lane_dir)
    allowed = states_for(lane)
    here = lane_dir.name
    if to not in allowed:
        raise ValueError(
            f"lane {lane!r} has no state {to!r}; "
            f"it declares {allowed}"
        )
    if to == "completed":
        # **`advance()` must never be the way into `completed/`.** That
        # transition belongs to `close()`, which is the only thing that
        # records the required resolution -- and, before this branch
        # existed, `close()` was also the ONLY route into `completed/`,
        # which is what made its "is not open" guard sufficient.
        #
        # The hole `advance()` opened: it moved a file-based ticket into
        # `completed/` with its frontmatter still reading `status: open`.
        # `close()` on that file then computed
        # `path.parent.parent / "completed"` -- the directory the file was
        # ALREADY IN -- wrote the closed copy over the source, and
        # `path.unlink()`ed that same path. The ticket was deleted, exit
        # code 0, and `close()` returned a path that did not exist.
        # Reachable with two ordinary CLI calls and nothing to see
        # afterwards but an empty `completed/`.
        raise ValueError(
            f"advance() cannot move a ticket into {to!r}: that is close()'s "
            "transition, because closing is what records the resolution. "
            f"Use tickets.close(path, resolution=...) -- "
            f"`python -m tools.cli tickets close {item} --resolution '...'`."
        )
    if allowed.index(to) <= _state_index(allowed, here, lane_dir):
        raise ValueError(
            f"cannot move backwards: {here!r} -> {to!r}. Close the ticket "
            "or file a new one instead."
        )
    if lane == "new-theory" and here == "open" and to == "implement":
        # **The evidence stage is not skippable**, and this is the one
        # forwards move in the repo that is refused anyway. Every other
        # lane's states are bookkeeping; these two are the lane's whole
        # argument. A spec states a thesis and the bar that would falsify
        # it, `evidence/` is where the cheapest decisive measurement runs
        # against that bar, and `implement/` asserts the bar was cleared.
        # Allowing `open` -> `implement` would let a build order be issued
        # on a thesis nobody measured -- which is the failure this lane
        # exists to prevent, and the reason `calendar-arb` and
        # `smile-smoothing` died in an afternoon instead of a month.
        raise ValueError(
            "a spec cannot skip the evidence stage: advance it to "
            "'evidence' and run the measurement first. A build order "
            "issued on an unmeasured thesis is what this lane exists to "
            "prevent."
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


def _state_index(allowed: tuple[str, ...], here: str, state_dir: Path) -> int:
    """Where `here` sits in the lane's pipeline, or a usable error.

    A bare `tuple.index()` raises `ValueError: tuple.index(x): x not in
    tuple` and names neither the directory nor the lane, which is the
    least useful thing it could say to somebody holding a ticket that
    somehow landed in a directory no lane declares.
    """
    try:
        return allowed.index(here)
    except ValueError:
        raise ValueError(
            f"ticket sits in {state_dir}, but {_lane_of(state_dir)!r} "
            f"declares no state {here!r} -- it has {allowed}. Move it into "
            "one of those before advancing it."
        ) from None


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


def close(path: Path, *, resolution: str, now: str | None = None,
          conn=None) -> Path:
    """Mark a ticket done and MOVE it into `completed/`. Returns the new path.

    The file is kept, never deleted: a finished ticket is the record of
    what was asked for and why, which is exactly what a future session
    re-deriving the same problem wants. But it leaves the backlog
    physically, because the backlog is a directory listing -- a status
    field alone would make every session read every ticket ever filed to
    find the few still open.

    **A `new-theory` ticket is a spec, so its resolution is a vocabulary
    and not free text** (`NEW_THEORY_RESOLUTIONS`), and closing one
    `disproven` or `underpowered` requires the finding to ALREADY be in
    the ideas registry -- which is what `conn` is for. That coupling is
    the load-bearing part; `_require_idea` says why.
    """
    if not resolution or not resolution.strip():
        raise ValueError("a resolution is required: say what happened")
    path = Path(path)
    is_study = path.name == STUDY_FILE
    item = path.parent if is_study else path
    lane = _lane_of(item.parent)
    if "completed" not in states_for(lane):
        # close() assumes a flat file at `<state_dir>/<name>.md` and moves
        # it to `<lane root>/completed/` via `path.parent.parent`. A study
        # ticket breaks both assumptions: it is a DIRECTORY -- STUDY.md
        # plus whatever code and data the measurement collected -- and the
        # study lane declares NO `completed/` state at all (LANE_STATES
        # above), because a study is a permanent record and the later
        # purge phase matches only `completed/`. Giving the lane one, even
        # by accident, would make a "finished" study eligible for it.
        #
        # Before this guard, calling close() on a study's STUDY.md computed
        # `path.parent.parent / "completed"` blindly. For a study filed as
        # `.../question/<slug>/STUDY.md`, `path.parent.parent` is
        # `question/` -- the study's own CURRENT STATE directory, not the
        # lane root -- so it wrote an orphaned `question/completed/
        # STUDY.md`, deleted the original, stranded every sibling file
        # under `question/`, and left the study invisible to every future
        # `backlog()`/`_scan()` call. It raised nothing, because the
        # frontmatter still read `status: open` and the guard below passed.
        raise ValueError(
            f"close() cannot be used on this {lane!r}-lane ticket: the "
            f"{lane!r} lane has no 'completed' state. A study is finished "
            "by advancing it to 'answer' -- "
            "tickets.advance(path, to='answer', note=...) -- never by "
            "closing it."
        )
    if item.parent.name == "completed":
        # **A ticket already in `completed/` is never closed again**, and
        # this guard stands on its own rather than leaning on the
        # `status: open` check below.
        #
        # That is the whole lesson of the deletion bug: the two used to be
        # one guard. `close()` was the only route into `completed/` and it
        # rewrote `status: open` -> `status: done` on the way, so "already
        # completed" and "not open" were the same fact and checking either
        # caught both. `advance()` broke that equivalence by moving a
        # ticket into `completed/` with its frontmatter untouched --
        # whereupon `close()` computed `path.parent.parent / "completed"`,
        # got the directory the file was already in, wrote over the source
        # and then unlinked it. The ticket vanished silently.
        #
        # Independent guards, so neither depends on the other holding.
        raise ValueError(
            f"ticket {path} is already in completed/ -- it cannot be closed "
            "again. Closing writes into `<lane>/completed/`, which for a "
            "ticket already there is the file itself: the old code "
            "overwrote it and then deleted it."
        )
    raw = path.read_text(encoding="utf-8")
    if "status: open" not in raw:
        raise ValueError(f"ticket {path} is not open")
    if lane == "new-theory":
        # Checked BEFORE anything is written. A spec closed with prose
        # says what happened to whoever reads it next week and says
        # nothing at all to the session six months out asking the only
        # question that changes behaviour: may this thesis be proposed
        # again?
        word = resolution.strip().split(":")[0].strip().lower()
        if word not in NEW_THEORY_RESOLUTIONS:
            raise ValueError(
                f"a new-theory resolution starts with one of "
                f"{NEW_THEORY_RESOLUTIONS}, not {word!r}. `disproven` "
                "means the bar was met and the thesis failed; "
                "`underpowered` means the measurement could not reach "
                "the bar, which is a different claim and stays "
                "re-proposable."
            )
        if word in _RESOLUTIONS_NEEDING_A_REGISTRY_ENTRY:
            _require_idea(conn, slug_of(path), word)
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


def _require_idea(conn, slug: str, word: str) -> None:
    """Refuse the close unless the finding already elevated.

    This is not bookkeeping. `purge` deletes a completed ticket after a
    week, and that is only safe because the durable fact left the file
    first. Without this coupling, purging an uncited `underpowered` spec
    just lets somebody re-propose the same dead thesis in three weeks --
    the exact failure the ideas registry exists to prevent.

    Knowledge elevates by AUDIENCE, and a killed spec's audience is every
    future session that will have the same idea. The file is the audit
    trail; the registry row is the fact. Only one of the two is
    searchable, and only one of the two survives the purge.
    """
    if conn is None:
        raise ValueError(
            f"closing a spec {word!r} needs a database connection: the "
            "finding has to reach the ideas registry before the file may "
            "be deleted"
        )
    from tools import ideas
    row = ideas.get(conn, slug)
    if row is None:
        raise ValueError(
            f"no ideas-registry entry for {slug!r}. Record it first "
            "(`ideas record` then `ideas status`) with what was tried and "
            "what was learned -- the purge may delete this file in a week."
        )
    if not (row["what_was_tried"] or "").strip():
        raise ValueError(f"idea {slug!r} has no what_was_tried")
    if not (row["outcome"] or "").strip():
        raise ValueError(f"idea {slug!r} has no outcome")
    if word == "underpowered" and not (row["revisit_angle"] or "").strip():
        # The whole asymmetry between the two words lives here.
        # `disproven` closes the question, so there is nothing to say
        # about trying again. `underpowered` says only that we could not
        # tell, so the row has to carry what would have to change --
        # without it the idea reads as dead to the next session that
        # searches for it, which loses exactly the distinction this
        # vocabulary was introduced to keep.
        raise ValueError(
            f"idea {slug!r} has no revisit_angle. `underpowered` means "
            "the measurement could not reach the bar, so it stays "
            "re-proposable -- say what would have to change."
        )


#: Where a citation of a ticket can live. A ticket named by any of these
#: is KEPT, because deleting it would break the reference -- and a
#: reference is evidence somebody found it worth pointing at.
#:
#: `tickets/new-theory/README.md` is the case that made this check
#: non-negotiable. Its rule 0 cites `calendar-arb`, `smile-smoothing` and
#: `aggregation-gap` by slug as the worked examples of theses that were
#: measured properly and failed, and links their closed specs by path. A
#: purge that removed those files would leave the repo's own explanation
#: of why it does not re-propose them pointing at nothing.
#:
#: The repo root is swept as `*.md` rather than by naming `CLAUDE.md`,
#: `README.md`, `RESEARCH_LOG.md` and `FLEET_LOG.md` one at a time. A
#: markdown file at the top level IS repo-level knowledge by definition,
#: and an enumeration means the fifth one somebody adds silently stops
#: protecting the tickets it cites -- a failure that shows up as a
#: deletion, months later, in a file nobody thought to add to a list.
_CITATION_GLOBS = (
    "*.md",
    "docs/**/*.md", ".claude/skills/**/*.md", "tests/**/*.py",
    "theories/**/*.md", "tickets/**/*.md", "studies/**/*.md",
)

#: Free-text database columns that can name a ticket. A slice records
#: where its hypothesis came from, and "mined from the aggregation-gap
#: probe" in `theory_slices.origin` is a citation exactly as much as a
#: line in a markdown file is.
#:
#: A closed ticket's own `resolution:` frontmatter is a citation too, and
#: needs no entry here: it lives in a `.md` file under `tickets/` or a
#: theory folder, so `_CITATION_GLOBS` already reads it.
#:
#: **The ideas registry is deliberately NOT on this list**, even though
#: its rows are keyed by the same slug. A spec closed `disproven` or
#: `underpowered` cannot be closed at all until its finding is recorded
#: there (`_require_idea`) -- so counting the registry as a citation
#: would permanently keep exactly the specs the registry made safe to
#: delete. That is the design inverted: the row is what lets the file go,
#: not a reason to hold on to it.
_DB_CITATION_COLUMNS = (("theory_slices", "origin"),)

_CLOSED_LINE = re.compile(r"^closed:\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)


def _closed_on(path: Path) -> date | None:
    """The day this ticket was closed, or None if the file does not say.

    A ticket with no readable `closed:` date is not a purge candidate.
    Both failure directions were available and only one of them is cheap:
    a ticket wrongly kept costs one line of one listing, and a ticket
    wrongly deleted costs somebody knowing to run `git log
    --diff-filter=D` to find out it ever existed.
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _CLOSED_LINE.search(raw)
    if match is None:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _rel(root: Path, path: Path) -> str:
    """A repo-relative posix path — the form citations get reported in."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _citation_corpus(root: Path) -> list[tuple[str, str]]:
    """Every file a citation could live in, read once.

    Read once and searched N times, rather than re-globbed per candidate:
    the repo has ~30 completed tickets and several hundred markdown
    files, and a per-candidate walk is that same work done thirty times.
    """
    seen: dict[str, str] = {}
    for pattern in _CITATION_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            name = _rel(root, path)
            if name in seen:
                continue
            try:
                seen[name] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return list(seen.items())


def _db_citations(conn, slugs: set[str]) -> dict[str, list[str]]:
    """Which candidates are named by the database's free-text columns.

    A missing connection means the DB was not consulted and a missing
    table means it had nothing to say — neither is a reason to refuse the
    whole purge, and both leave the file-based check untouched.
    """
    import sqlite3

    hits: dict[str, set[str]] = {}
    if conn is None or not slugs:
        return {}
    for table, column in _DB_CITATION_COLUMNS:
        try:
            rows = conn.execute(
                f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL"
            ).fetchall()
        except sqlite3.Error:
            continue
        for row in rows:
            text = str(row[0])
            for slug in slugs:
                if slug in text:
                    hits.setdefault(slug, set()).add(f"db:{table}.{column}")
    return {slug: sorted(names) for slug, names in hits.items()}


def purge(root, *, older_than: int = 7, apply: bool = False,
          conn=None, now: str | None = None) -> dict:
    """Remove long-completed tickets that nothing cites. Dry run by default.

    A finished ticket is the record of what was asked for and why, which
    is why `close` keeps it rather than deleting it. But the backlog is
    read by listing, and a tree that only ever grows makes the cheapest,
    most-repeated read in the repo the largest. Git history is the
    durable record -- `git log --diff-filter=D` finds a purged ticket and
    `git show` retrieves it -- so a completed ticket nothing points at
    does not need to sit in the working tree forever.

    Deleting a `disproven` or `underpowered` spec is acceptable only
    because `close` already forced its finding into the ideas registry:
    the knowledge leaves the file before the file leaves the tree. That
    coupling is what this function stands on, and it is why the ideas
    registry is not itself a citation source (`_DB_CITATION_COLUMNS`).

    **Studies are never candidates, and not by exemption.** The study
    lane's terminal state is `answer/`, not `completed/`, so a finished
    study is simply not a thing this query matches. Permanence falls out
    of the state names. A study special-case appearing in this function
    would mean the state names had stopped carrying their meaning, and
    the fix would be upstream rather than another branch in here.

    Dry run is the DEFAULT and `apply` is what deletes: removing files
    must never be a side effect of a flag somebody forgot to pass.
    """
    root = Path(root)
    today = date.fromisoformat(now or _today())
    candidates: list[Path] = []
    for base in (root / "tickets", root / "theories"):
        if not base.is_dir():
            continue
        for state_dir in sorted(base.rglob("completed")):
            if not state_dir.is_dir():
                continue
            try:
                _lane_of(state_dir)
            except ValueError:
                # A `completed/` directory that no lane declares is not a
                # ticket state -- it is some other directory that happens
                # to share the name. Deciding by the lane vocabulary
                # rather than by the string is what keeps this walk from
                # wandering into, say, a theory's data folder.
                continue
            for path in sorted(state_dir.glob("*.md")):
                if path.name == "README.md":
                    continue
                closed = _closed_on(path)
                if closed is None or (today - closed).days < older_than:
                    continue
                candidates.append(path)
    purged: list[str] = []
    kept: list[dict] = []
    if candidates:
        corpus = _citation_corpus(root)
        db_hits = _db_citations(conn, {slug_of(p) for p in candidates})
        for path in candidates:
            slug = slug_of(path)
            here = _rel(root, path)
            # The candidate's own file is skipped: a completed ticket
            # sits under `tickets/` or a theory folder, both of which the
            # corpus reads, so a ticket whose body names its own slug
            # would vouch for itself and never become purgeable.
            #
            # A plain substring match, deliberately. It over-keeps --
            # `calendar-arb` matches a mention of
            # `calendar-arb-probe-exact-stamp-board` -- and over-keeping
            # is the recoverable direction: the cost is one stale file
            # sitting in `completed/`, against a broken reference nobody
            # notices for months.
            cited_by = [name for name, text in corpus
                        if name != here and slug in text]
            cited_by += db_hits.get(slug, [])
            if cited_by:
                kept.append({"path": str(path), "cited_by": cited_by})
            else:
                purged.append(str(path))
        if apply:
            for target in purged:
                # `git rm`, not `unlink`: the removal has to land in git
                # history, because git history IS the durable record that
                # makes deleting a completed ticket safe at all.
                subprocess.run(["git", "rm", "-q", "--", target],
                               cwd=root, check=True)
    return {"purged": purged, "kept": kept, "dry_run": not apply}


def render_purge(result: dict, root=None) -> str:
    """The purge as a listing a human reads BEFORE anyone passes --apply.

    The dry run is the whole verification, so the listing has to be
    readable: a proposed deletion of something rule 0 cites is how you
    find out the citation check is broken, and you only find it by
    looking.
    """
    root = Path(root) if root else None

    def show(path: str) -> str:
        return _rel(root, Path(path)) if root else path

    out = [
        "PURGE — dry run: nothing was deleted. Pass --apply to remove."
        if result["dry_run"] else
        "PURGE — applied: removed via `git rm`; `git log --diff-filter=D` "
        "finds them again.",
        "",
    ]
    purged = result["purged"]
    out.append(f"{'would remove' if result['dry_run'] else 'removed'} "
               f"({len(purged)})")
    out += [f"  {show(path)}" for path in purged] or ["  (none)"]
    out.append("")
    kept = result["kept"]
    out.append(f"kept — cited ({len(kept)})")
    if not kept:
        out.append("  (none)")
    for entry in kept:
        out.append(f"  {show(entry['path'])}")
        out.append("      cited by " + _clip(
            ", ".join(entry["cited_by"]), _WIDTH - 16))
    return "\n".join(out).rstrip() + "\n"


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
