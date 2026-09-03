"""Repo-wide conventions the OOP layer promises (spec sections 3.2, 4.2,
4.5c, 9): every theory package exposes a proper singleton, nobody
overrides the workflow, a Verdict can never grow a number, the migration
shim is gone for good, and the actually-running registry has no drift
between code and DB; and every repo path named in living docs resolves
(enforcing-surfaces spec 5.1)."""

import ast
import inspect
import pytest
import re
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

from tools import db, domain, ledger, registry
from tools.theory import Theory, TheoryRun

ROOT = Path(__file__).resolve().parents[1]


def test_every_theory_package_exposes_a_conforming_singleton():
    for tid, theory in registry.discover().items():
        assert isinstance(theory, Theory)
        assert theory.id == tid
        assert isinstance(theory.version, int)
        for stage, path in theory.prompts.items():
            from tools.provenance import VALID_STAGES
            assert stage in VALID_STAGES


def test_no_theory_overrides_the_inherited_workflow():
    for theory in registry.discover().values():
        for cls in type(theory).__mro__[:-3]:       # up to (not incl.) Theory
            assert "start" not in vars(cls)
            assert "finish" not in vars(cls)
    assert TheoryRun.__subclasses__() == []


def test_verdict_declares_no_numeric_field():
    """CLAUDE.md's 'never state a probability you introspected', as a type
    property: an out-of-process judge has no channel to hand back a number."""
    for f in fields(domain.Verdict):
        annotation = str(f.type)
        assert "float" not in annotation and "int" not in annotation, (
            f"Verdict.{f.name} is numeric -- a judge returns a category, "
            "never a number"
        )


def test_the_migration_shim_is_gone():
    """Phase 5 delivered: domain objects are not mappings. Dict-style
    access anywhere in production code is now a TypeError, not a wart."""
    for cls in (domain.Market, domain.PolymarketMarket, domain.Candidate):
        assert not hasattr(cls, "__getitem__")
        assert not hasattr(cls, "keys")
    assert not hasattr(domain, "SHIM_CALLERS")


def test_the_real_registry_has_no_drift():
    """registry.check_drift against the ACTUAL working database.

    tests/test_registry.py only exercises check_drift on synthetic
    tmp_path databases built to agree by construction -- nothing in the
    suite ever points it at db/market_edge.db, so a real class/DB mismatch
    (running v3 code while the DB still says v2 -- exactly the silent merge
    CLAUDE.md's versioning rule exists to prevent, or uses_llm_judgment
    flipped on one side only) would ship green. This closes that hole.

    Read-only: connects to the real DB but never calls init_db or writes
    to it. Skips cleanly if the file does not exist (a fresh clone, or CI
    with no working database) rather than creating one as a side effect of
    connecting -- `db.connect` would otherwise create an empty file.
    """
    if not db.DEFAULT_DB_PATH.exists():
        pytest.skip(
            f"{db.DEFAULT_DB_PATH} does not exist -- no working database "
            "to check for drift in this environment"
        )
    conn = db.connect(db.DEFAULT_DB_PATH)
    try:
        problems = registry.check_drift(conn)
    finally:
        conn.close()
    assert problems == [], (
        "the real theory registry has drifted between code and DB -- "
        "a run recorded under this state would be recorded under the "
        "wrong procedure identity:\n" + "\n".join(problems)
    )


def _absolute_module(path: Path, node: ast.ImportFrom) -> str:
    """The module an ImportFrom names, resolved if it is relative.

    `from ..mention_family import x` inside insider_judgment reaches a
    sibling exactly as an absolute import would; resolving it here means
    the rule cannot be dodged by writing the import the other way.
    """
    if not node.level:
        return node.module or ""
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    base = parts[:-1]                      # the file's own package
    for _ in range(node.level - 1):
        base = base[:-1]
    return ".".join(base + ([node.module] if node.module else []))


def _imported_modules(path: Path) -> list[str]:
    """Every module path a file imports, however it spells the import.

    An ImportFrom contributes its module AND module.name per alias: the
    sibling-reaching `from theories.insider_bias import mention_family`
    names the sibling in the alias, not the module, and that spelling is
    one word away from the legitimate `... import screen` this tree
    already uses.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = _absolute_module(path, node)
            names.append(module)
            names.extend(f"{module}.{alias.name}" for alias in node.names)
    return names


def _theory_package(cls: type) -> str:
    """The package a theory class belongs to.

    A class defined in the package's own `__init__.py` already has the
    package as its `__module__`; one defined in `theory.py` needs the last
    segment dropped. Getting this wrong silently widens or narrows the set
    of packages treated as siblings.
    """
    module = sys.modules[cls.__module__]
    filename = Path(getattr(module, "__file__", "") or "").name
    if filename == "__init__.py":
        return cls.__module__
    return cls.__module__.rsplit(".", 1)[0]


def test_no_theory_imports_a_sibling_theory():
    """A theory folder stays self-sufficient to run.

    Shared ancestry goes through a shared parent module -- for the
    insider_bias family, screen.py / replay.py / families.py -- or through
    tools/. Never through a sibling theory's folder, which would make
    understanding one theory require reading two. Parsed with ast, so
    checking this imports nothing.
    """
    packages = {
        _theory_package(type(theory))
        for theory in registry.discover().values()
    }
    problems = []
    for pkg in sorted(packages):
        pkg_dir = ROOT.joinpath(*pkg.split("."))
        siblings = packages - {pkg}
        for path in sorted(pkg_dir.rglob("*.py")):
            for name in _imported_modules(path):
                for other in siblings:
                    if name == other or name.startswith(other + "."):
                        rel = path.relative_to(ROOT).as_posix()
                        problems.append(f"{rel} imports {name}")
    assert problems == [], (
        "a theory imports a sibling theory's folder -- route shared code "
        "through a shared parent module or tools/ instead:\n"
        + "\n".join(problems)
    )

def test_every_recorded_prompt_path_still_resolves():
    """Provenance survives a refactor, or it was never provenance.

    A judgment_runs row says which prompt judged a set of rows. Moving or
    renaming that file silently turns the row into a dangling pointer, and
    the loss is invisible until someone tries to reproduce a result -- by
    which time the move is buried in history. This catches it at the commit
    that moves the file.

    prompt_sha256 remains the authority on WHAT ran: a path may legitimately
    point at a file whose content has since changed, and each such row's
    notes carry the git command that retrieves the exact version. This test
    only asserts the pointer still lands somewhere real.

    Read-only against the working database, and skipped where there is none
    (a fresh clone, or CI) rather than creating one as a side effect.
    """
    if not db.DEFAULT_DB_PATH.exists():
        pytest.skip(
            f"{db.DEFAULT_DB_PATH} does not exist -- no recorded provenance "
            "to check in this environment"
        )
    conn = db.connect(db.DEFAULT_DB_PATH)
    try:
        rows = list(conn.execute(
            "SELECT run_id, stage, prompt_path FROM judgment_runs "
            "WHERE prompt_path IS NOT NULL"
        ))
    finally:
        conn.close()
    missing = [
        f"{r['run_id']} ({r['stage']}) -> {r['prompt_path']}"
        for r in rows if not (ROOT / r["prompt_path"]).exists()
    ]
    assert missing == [], (
        "a recorded prompt path no longer resolves -- the run it judged is "
        "no longer reproducible from the ledger alone. Repoint the row to "
        "the file's new home and record the original path (and, if the "
        "content also changed, the git command that retrieves the version "
        "that ran) in its notes:\n" + "\n".join(missing)
    )


def test_every_ruling_log_entry_resolves():
    """A ruling row points back at RESEARCH_LOG.md's reasoning for it, or it
    was never traceable. `rulings.log_entry` names the log's date heading
    that explains a binding ruling; a heading that gets edited, retitled,
    or moved out from under it silently turns the ruling into a claim with
    no audit trail -- the same failure `test_every_recorded_prompt_path_
    still_resolves` above catches for provenance, here for rulings.

    Headings can wrap onto one line in the log (a long title stays on its
    `## ` line), so this matches on substring containment of the stored
    heading text within the file, not an exact line match.

    Read-only against the working database, and skipped where there is
    none (a fresh clone, or CI) rather than creating one as a side effect.
    """
    if not db.DEFAULT_DB_PATH.exists():
        pytest.skip(
            f"{db.DEFAULT_DB_PATH} does not exist -- no recorded rulings "
            "to check in this environment"
        )
    conn = db.connect(db.DEFAULT_DB_PATH)
    try:
        rows = list(conn.execute(
            "SELECT id, log_entry FROM rulings WHERE log_entry IS NOT NULL"
        ))
    finally:
        conn.close()
    log_text = (ROOT / "RESEARCH_LOG.md").read_text(encoding="utf-8")
    missing = [
        f"ruling {r['id']} -> {r['log_entry']!r}"
        for r in rows if r["log_entry"] not in log_text
    ]
    assert missing == [], (
        "a ruling's log_entry no longer appears in RESEARCH_LOG.md -- the "
        "reasoning behind a binding ruling is no longer traceable from the "
        "ledger alone. Repoint the row to the heading's new text:\n"
        + "\n".join(missing)
    )


#: `record_opportunity`'s identity parameters -- these key the position row
#: (`opportunities.UNIQUE`) or steer the write itself, and have no per-call
#: value to lose on a merge, so they carry no `opportunity_attempts` column.
_RECORD_OPPORTUNITY_IDENTITY_PARAMS = frozenset({
    "theory_id", "theory_version", "run_mode", "kalshi_ticker", "outcome",
    "run_id", "decision_date", "now",
})


def test_every_record_opportunity_param_has_an_attempt_column():
    """Full parity, enforced (attempt-fidelity spec section 4).

    `opportunity_attempts` exists so that a re-sighting of a position never
    loses a value the run supplied -- the position row is a rollup, the
    attempt is the record. That guarantee only holds if every argument
    `record_opportunity` accepts, other than the ones that identify *which*
    position/attempt this is, has somewhere on the attempt row to land.
    Without this test, a future parameter can be added to
    `record_opportunity`, threaded only onto the `opportunities` row, and
    silently dropped on every re-sighting -- exactly the defect this table
    exists to close -- and nothing would fail until someone went looking
    for a value that was never recorded.

    Checked against a freshly created database's real schema (not a
    hand-maintained list of column names), so a schema change and a
    signature change are compared against each other directly.
    """
    sig = inspect.signature(ledger.record_opportunity)
    params = {
        name for name in sig.parameters
        if name != "conn" and name not in _RECORD_OPPORTUNITY_IDENTITY_PARAMS
    }

    conn = db.connect(":memory:")
    try:
        db.init_db(conn)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(opportunity_attempts)")
        }
    finally:
        conn.close()

    missing = sorted(params - columns)
    assert missing == [], (
        "record_opportunity accepts a parameter with no matching "
        "opportunity_attempts column -- its value would be recorded on the "
        "position row (if at all) and lost on the next re-sighting. Add a "
        "column in db/schema.sql and thread it through "
        "ledger._record_attempt:\n" + "\n".join(missing)
    )


#: Docs whose backticked repo paths must resolve. Spec §5.1; later plans
#: add theories/*/CLAUDE.md (§7.9) and the dated-citation check (§6.6).
#:
#: Deliberately excludes nested theories/*/*/THEORY.md (e.g.
#: theories/insider_bias/insider_judgment/THEORY.md,
#: theories/insider_bias/mention_family/THEORY.md): `_doc_paths` only
#: globs one level deep (`theories/*/THEORY.md`), so a family's nested
#: THEORY.md files never enter this check. That is on purpose, not an
#: oversight -- a nested theory doc's backticked paths are written
#: relative to ITS OWN directory (e.g. `screen.py` meaning
#: `theories/insider_bias/insider_judgment/screen.py`), while this test
#: resolves every span against the repo ROOT. Checking them as written
#: produced 13 false positives on paths that are perfectly real, just not
#: root-relative. The real fix is resolving each span against the doc's
#: own directory instead of ROOT; that is deferred, so nested THEORY.md
#: files stay out of scope here rather than fail on their own correct
#: paths.
_DOC_FILES = ("README.md", "CLAUDE.md", "tools/README.md")

#: Paths that legitimately exist only at runtime (gitignored artifacts).
#: `STATE\.md` is deliberately NOT listed here: `_PATH_LIKE` below requires
#: at least one `/`, so a bare `STATE.md` span is never matched by it and
#: never reaches this regex at all -- an alternative here for it would be
#: dead code. `STATE.md` is written as a bare filename in the docs that
#: mention it (see CLAUDE.md), so it never needs this exception.
_ALLOWED_MISSING = re.compile(r"^db/.*\.(db|db-wal|db-shm)$")

#: Paths a doc names specifically to assert they must NEVER exist -- the
#: opposite of `_ALLOWED_MISSING`, which excuses a real runtime artifact
#: that just isn't checked out yet. `tools/backtest.py` is CLAUDE.md's and
#: tools/README.md's worked example of a shared backtest engine the
#: architecture deliberately never builds ("there is no tools/backtest.py
#: replay engine, and none gets built"). Excluded from the "must resolve"
#: check below, and the test asserts the opposite instead: that it stays
#: absent, so a future change that quietly builds the very file the docs
#: argue against is caught here rather than discovered by someone reading
#: the docs and being told the opposite of what the repo now does.
_DELIBERATELY_ABSENT = {"tools/backtest.py"}

_PATH_LIKE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*(/[A-Za-z0-9_.\-]+)+/?$")


def _retired_doc(path: Path) -> bool:
    """Is this THEORY.md the record of a theory that has been retired?

    A retired theory's THEORY.md names modules, payloads and runbook
    sections that were DELETED at retirement, on purpose: it is the
    record of what the theory claimed and how it decided, and those
    paths still resolve at the git rev its RETIRED.md names. Holding it
    to root-relative path resolution would demand editing the record
    into agreement with the deletion, which is the one thing retirement
    must not do.

    This is an EXPLICIT exclusion because until now it was an accident
    of glob depth: `theories/*/THEORY.md` is one level deep, so
    `theories/retired/calibration_harvest/THEORY.md` simply never
    entered the check. Anyone deepening that glob to `**` -- the obvious
    fix for the nested-family docs it misses, see the note on
    `_DOC_FILES` -- would turn the retired doc red for reasons nobody
    would connect to their change. Stated here, deepening the glob stays
    a decision about nested theories and nothing else.
    """
    return registry.RETIRED_DIRNAME in path.relative_to(ROOT / "theories").parts


def _doc_paths():
    docs = [ROOT / f for f in _DOC_FILES]
    docs += [p for p in sorted(ROOT.glob("theories/*/THEORY.md"))
             if not _retired_doc(p)]
    for doc in docs:
        for span in re.findall(r"`([^`\n]+)`", doc.read_text(encoding="utf-8")):
            # Only bare repo paths: no spaces/flags, at least one slash, no
            # placeholders (<slug>), globs, code, or URLs.
            if " " in span or "://" in span or "<" in span or "*" in span:
                continue
            if not _PATH_LIKE.match(span):
                continue
            yield doc.name, span


def test_every_repo_path_named_in_docs_resolves():
    """A doc that names a path nobody can open is worse than no doc: it
    sends the next session somewhere that does not exist. Fails at the
    commit that breaks the path, not months later."""
    missing = [
        f"{doc}: `{span}`"
        for doc, span in _doc_paths()
        if not (ROOT / span).exists()
        and not _ALLOWED_MISSING.match(span)
        and span not in _DELIBERATELY_ABSENT
    ]
    assert missing == [], (
        "a doc names a repo path that does not resolve -- fix the doc or "
        "add a deliberate runtime-artifact exception:\n" + "\n".join(missing)
    )


def test_deliberately_absent_paths_stay_absent():
    """The other direction of `_DELIBERATELY_ABSENT`: a doc that argues a
    file must never exist is broken the moment that file shows up, exactly
    as broken as a doc pointing at a path that resolves to nothing. This
    is the guard for `tools/backtest.py` specifically -- CLAUDE.md and
    tools/README.md both say, in prose, that no shared backtest engine
    gets built; this is that claim enforced."""
    present = [
        f"{doc}: `{span}`"
        for doc, span in _doc_paths()
        if span in _DELIBERATELY_ABSENT and (ROOT / span).exists()
    ]
    assert present == [], (
        "a doc asserts a path must never exist, but it does now -- this is "
        "an architecture decision to revisit deliberately, not to let "
        "drift silently past the docs that argue against it:\n"
        + "\n".join(present)
    )


#: Task-time rules relocated out of CLAUDE.md into the skill that owns the
#: activity (enforcing-surfaces spec 7.2, user-ruled 2026-08-29). One home
#: per rule: the marked block must exist in the owning skill, and
#: CLAUDE.md's skill map must still name that skill. Populated one entry
#: per move commit; an entry here without its block is a dropped rule.
_MOVED_RULES: dict[str, str] = {
    "backtest-web-search-off": "backtest-theory",
    "structural-gate-conditions": "backtest-theory",
    "record-the-tier-claim": "backtest-theory",
    "judge-blind": "find-edge",
    "batch-and-dedupe": "find-edge",
    "buckets-from-deep-stage": "find-edge",
    "facts-are-data": "propose-theory",
    "search-the-registry": "propose-theory",
    "revisit-angle": "propose-theory",
    # Rehomed 2026-09-01: `go` became a dispatcher that chooses a lane
    # and hands off, so the rule about what a theory writes where
    # belongs with the lane that writes it.
    "notes-theory-log-split": "go-theory",
}


#: The marker CLAUDE.md's own map paragraph opens with, under "How the
#: user drives this" -- `_skill_map_paragraph` uses it to find that one
#: paragraph among all the others.
_SKILL_MAP_ANCHOR = "When a task has a skill, invoke it before starting."


def _skill_map_paragraph(claude_md: str) -> str:
    """Return the single paragraph in CLAUDE.md that maps activities to
    skills via `->` arrows (e.g. `` Backtesting -> `backtest-theory`. ``),
    isolated by splitting on blank lines and keeping the one that opens
    with `_SKILL_MAP_ANCHOR`. Checking within just this paragraph -- rather
    than a bare backtick-wrapped-name search over the whole file -- is what
    makes the check below notice a skill's map entry going missing: the
    skill's name legitimately turns up elsewhere in CLAUDE.md (prose,
    worked examples) even after its own `-> \\`skill\\`` line is deleted, so
    a whole-file substring search never trips."""
    for para in claude_md.split("\n\n"):
        if _SKILL_MAP_ANCHOR in para:
            return para
    raise AssertionError(
        "CLAUDE.md has no paragraph opening with "
        f"{_SKILL_MAP_ANCHOR!r} -- the skill map itself is gone"
    )


def test_every_moved_rule_lives_in_its_owning_skill():
    """Each relocated rule has exactly one home: its marked block exists
    in the owning skill, and CLAUDE.md's skill-map paragraph (the
    "-> `skill`" paragraph under "How the user drives this", see
    `_skill_map_paragraph`) still carries that skill's own arrow entry --
    not just a mention of the skill's name anywhere in the file. A rule
    dropped in a move, or a skill dropped from the map itself, fails at
    the dropping commit."""
    claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    map_paragraph = _skill_map_paragraph(claude_md)
    problems = []
    for slug, skill in sorted(_MOVED_RULES.items()):
        skill_file = ROOT / ".claude" / "skills" / skill / "SKILL.md"
        if f"<!-- rule: {slug} " not in skill_file.read_text(encoding="utf-8"):
            problems.append(f"{slug}: no marked block in {skill}/SKILL.md")
        if not re.search(r"→\s*`" + re.escape(skill) + "`", map_paragraph):
            problems.append(f"{slug}: CLAUDE.md's map no longer names {skill}")
    assert problems == [], (
        "a relocated rule lost its single home:\n" + "\n".join(problems)
    )


_DATE = re.compile(r"20\d{2}-\d{2}-\d{2}")
#: `\b` before the alternation (deviation from the brief's literal regex):
#: without it, `re.findall` happily matches the *tail* of an unrelated word
#: -- `backtests/RESULTS.md` contains `tests/RESULTS.md` as a substring
#: (`backTESTS`), so the unanchored version reports a real, resolvable
#: citation (theory_slices row insider_judgment/strong-moderate-no, whose
#: origin reads "...backtests/RESULTS.md carries the Holm-corrected
#: family...") as citing a nonexistent `tests/RESULTS.md`. `\b` requires a
#: word boundary immediately before `theories|studies|docs|tools|tests`,
#: which the `k`/`t` junction in `backtests` does not have, so the false
#: match disappears while every genuine path mention (preceded by
#: whitespace, punctuation, or start-of-string) still matches.
_CITED_PATH = re.compile(
    r"\b(?:theories|studies|docs|tools|tests)/[A-Za-z0-9_./\-]*[A-Za-z0-9_\-]"
)


#: Strips a leading list marker (`-` or `*`, and any run of `-`/`*`/
#: whitespace after it -- covers a bold marker glued onto a dash, e.g.
#: `- **2026-08-26**: ...`) so the remainder can be checked for a
#: date immediately at its front.
_LIST_MARKER = re.compile(r"^[\-*\s]+")


def _file_contains_date_heading(path, date):
    """True when `date` sits on an entry-anchor line of `path`: a line
    whose stripped text starts with '#' or '**' and contains the date
    anywhere (a `## <date> -- ...` heading, or a bold-lead paragraph --
    both short enough that "contains" and "leads with" coincide in
    practice), OR a line led by another list marker (`-`, `*`) where the
    date leads the text immediately after that marker (and after a bold
    marker glued to it, e.g. `- **2026-08-26**: ...`). A body line that
    merely mentions the date in passing -- inside a run id
    (`` `backtest-2026-08-26-insider-judged-s200` ``), a parenthetical
    aside ("see 2026-08-26 log"), or anywhere past the first few visible
    characters of a list item -- does NOT satisfy this, on purpose: that
    is the distinction between an entry citing its own date and an entry
    merely mentioning one, which the plain-containment version below
    could not tell apart.

    History: first loosened from the brief's original `#`/`**`-only
    heuristic to plain whole-file containment, because that heuristic
    missed a real, repo-wide citation format -- THEORY.md 'Learnings'
    entries are Markdown list items, `- 2026-08-26 -- **headline
    text...**`, which start with `-`, not `#` or `**` (see
    theories/insider_bias/insider_judgment/THEORY.md and
    theories/insider_bias/mention_family/THEORY.md). Plain containment
    fixed that false alarm but broke the test's actual job: reviewed and
    rejected (2026-08-29) because it cannot tell an entry's own dated
    anchor from an unrelated mention of the same date elsewhere in the
    file. Reproduced concretely: insider_judgment/THEORY.md carries two
    2026-08-26 Learnings bullets (~585, ~594) plus an incidental
    2026-08-26 inside a run id in prose (~623); under plain containment,
    silently deleting the entire cited bullet at ~594-613 left the date
    still present via the other two mentions, and the slice-origin test
    stayed green -- exactly the silent-move failure this test exists to
    catch, undetected. This function restores anchor-line granularity
    (list markers included, not just `#`/`**`) so that case fails again,
    while still recognizing the Learnings bullet format that motivated
    the original loosening.

    Accepted residual (spec 6.6's own bar: the cited file must "still
    contain that date heading" -- a stub suffices, entry-content matching
    is out of scope): when a file carries more than one anchor entry for
    the same date, deleting one of them without a stub still passes, as
    long as another anchor for that date survives elsewhere in the file
    -- the check operates at date-anchor granularity, not per-entry
    identity. `insider_judgment/THEORY.md`'s two 2026-08-26 bullets are
    exactly this case, and are a deliberate limit, not a bug: telling
    those two entries apart would mean matching entry *content*, which
    this test was never designed to do and the controller ruling (2026-
    08-29) explicitly declined to add."""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#") or stripped.startswith("**"):
            if date in line:
                return True
        elif stripped.startswith("-") or stripped.startswith("*"):
            if _LIST_MARKER.sub("", stripped).startswith(date):
                return True
    return False


def test_every_slice_origin_citation_still_resolves():
    """A slice's origin is its pre-registration provenance (CLAUDE.md,
    'Subset edges'). It cites files and dated section headings in prose;
    nothing else enforces them, so a notebook migration could silently
    orphan the provenance of a registered slice. Every repo path named in
    an origin must exist, and every date named must still appear as a
    heading in at least one of the cited files. A stub or a migrated
    heading satisfies this; a silent move does not. (spec 6.6)

    Read-only against the working database, skipped where there is none --
    same idiom as test_every_recorded_prompt_path_still_resolves."""
    if not db.DEFAULT_DB_PATH.exists():
        pytest.skip("no working database in this environment")
    conn = db.connect(db.DEFAULT_DB_PATH)
    try:
        rows = list(conn.execute("SELECT theory_id, slug, origin FROM theory_slices"))
    finally:
        conn.close()
    problems = []
    for r in rows:
        origin = r["origin"] or ""
        cited = [p.rstrip(".") for p in _CITED_PATH.findall(origin)]
        files = []
        for p in cited:
            if not (ROOT / p).exists():
                problems.append(f"{r['theory_id']}/{r['slug']}: cites missing `{p}`")
            elif (ROOT / p).is_file():
                files.append(ROOT / p)
        for date in set(_DATE.findall(origin)):
            if files and not any(_file_contains_date_heading(f, date) for f in files):
                problems.append(
                    f"{r['theory_id']}/{r['slug']}: date {date} no longer a "
                    f"heading in any cited file"
                )
    assert problems == [], (
        "a registered slice's origin citation no longer resolves -- "
        "restore the heading (a stub suffices) or repoint the origin's "
        "citation deliberately:\n" + "\n".join(problems)
    )


#: Files whose prose cites other files' dated entries. RESEARCH_LOG.md is
#: scanned for citations INTO notebooks; notebooks and THEORY.md files for
#: citations into each other and back into the log.
_CITING_GLOBS = ("RESEARCH_LOG.md", "theories/*/NOTES.md", "theories/*/*/NOTES.md",
                 "theories/*/THEORY.md", "theories/*/*/THEORY.md")
_CITE_LINE = re.compile(
    r"(?P<file>[A-Za-z0-9_./\-]*(?:NOTES\.md|THEORY\.md|RESEARCH_LOG\.md))"
)


#: Follow a citation into a theory that has since been retired.
#:
#: A retired theory's documents move to `theories/retired/<slug>/`, and the
#: prose that cited them stays exactly where it is -- RESEARCH_LOG.md is
#: append-only history, so a line reading "Narrative moved 2026-08-29 to
#: `theories/calibration_harvest/NOTES.md`" records what was true when it
#: was written and rewriting it would falsify the record. Four such lines
#: broke the instant calibration_harvest's folder moved (2026-09-02).
#:
#: Following the move is right rather than lenient: retirement is the
#: opposite of the silent move this test exists to catch. It leaves a
#: RETIRED.md marker in the new folder and a `retired` registry row saying
#: where the theory went, so the pointer is recoverable by anything that
#: looks -- which is the standard the docstring above sets for a stub. A
#: span that resolves at NEITHER home still fails, and the date-heading
#: check below runs against the retired copy unchanged.
#:
#: Scope -- stated because the resolver runs over every citing doc while
#: only one kind of doc justifies it. The redirect exists for APPEND-ONLY
#: history: RESEARCH_LOG.md, and dated entries already written into a
#: notebook, which record what was true when they were written and cannot
#: be corrected without falsifying the record. It is NOT a licence for
#: prose written from here on. A newly written citation names the retired
#: path directly, and the four editable citations calibration_harvest's
#: move broke were hand-edited to the new path rather than left to this
#: fallback -- that is the standard.
#:
#: It is deliberately not narrowed by file name, because an append-only
#: dated entry lives in a notebook as readily as in the log, and a check
#: guessing which lines were editable would be wrong in both directions.
#: So the limit is documented rather than enforced, and the known cost is
#: that an editable doc written from now on can name a stale
#: theories/<slug>/... path and pass here silently.
def _retired_home(span: str) -> Path | None:
    """`theories/<slug>/x` -> `theories/retired/<slug>/x`, if that exists."""
    parts = span.split("/")
    if len(parts) < 3 or parts[0] != "theories":
        return None
    moved = ROOT.joinpath("theories", registry.RETIRED_DIRNAME, *parts[1:])
    return moved if moved.exists() else None


def test_every_dated_cross_citation_still_resolves():
    """Notebooks, THEORY.md files and the log cite each other's entries by
    date ('NOTES.md 2026-08-26'). A migration moves entries between these
    files, and a date citation breaks silently because the date still
    exists somewhere. Any line that names one of these files AND a date
    must point at a file that still carries that date as a heading. A stub
    keeps the heading, so stubs pass; a silent move fails. (spec 6.6)

    Resolution: an explicit path in the citation wins; a bare NOTES.md /
    THEORY.md resolves to the citing file's own directory when possible;
    otherwise every file of that name is searched and ANY hit passes --
    deliberately loose, because prose citations name theories in words
    ('mention_family's NOTES.md') that a regex should not guess at."""
    problems = []
    for pattern in _CITING_GLOBS:
        for doc in sorted(ROOT.glob(pattern)):
            for line in doc.read_text(encoding="utf-8").splitlines():
                m = _CITE_LINE.search(line)
                dates = _DATE.findall(line)
                if not m or not dates:
                    continue
                span = m.group("file")
                retired = _retired_home(span) if "/" in span else None
                if "/" in span and (ROOT / span).exists():
                    targets = [ROOT / span]
                elif retired is not None:
                    targets = [retired]
                elif "/" in span:
                    problems.append(f"{doc.relative_to(ROOT)}: cites missing `{span}`")
                    continue
                elif (doc.parent / span).exists():
                    targets = [doc.parent / span]
                else:
                    targets = sorted(ROOT.glob(f"**/{span}"))
                for date in dates:
                    if targets and not any(
                        _file_contains_date_heading(t, date) for t in targets
                    ):
                        problems.append(
                            f"{doc.relative_to(ROOT)}: `{span}` {date} -- no "
                            f"target still carries that date as a heading"
                        )
    assert problems == [], (
        "a dated cross-citation no longer resolves -- the entry it cites "
        "was moved without a stub, or its heading was reworded:\n"
        + "\n".join(problems)
    )


def test_theory_versions_ledger_is_complete_and_proven():
    """`theory_versions` is the carry-chain ledger (enforcing-surfaces spec
    2.6, 10): every bump declares its lineage kind, and a `carry` claim
    holds only with proof behind it. Two belt-and-braces checks the schema
    and `bump_version` already enforce at write time, re-asserted here so a
    raw INSERT or a stale schema cannot slip past unnoticed:

    (a) every `carry` row has a non-null `equivalence_run` -- the proof is
        the permission (spec 2.4); an assertion never qualifies.
    (b) every theory in `theories` has a `theory_versions` row for every
        version 1..current_version -- a gap means a bump landed on
        `theories.version` with no matching row, which silently truncates
        `carry_chain`'s walk and `score.compute_score(pool='chain')`.

    Read-only against the working database, skipped where there is none --
    same idiom as test_every_recorded_prompt_path_still_resolves."""
    if not db.DEFAULT_DB_PATH.exists():
        pytest.skip("no working database in this environment")
    conn = db.connect(db.DEFAULT_DB_PATH)
    try:
        unproven_carries = list(conn.execute(
            "SELECT theory_id, version FROM theory_versions"
            " WHERE kind = 'carry' AND equivalence_run IS NULL"
        ))
        theories = list(conn.execute("SELECT id, version FROM theories"))
        have = {
            (r["theory_id"], r["version"])
            for r in conn.execute(
                "SELECT theory_id, version FROM theory_versions"
            )
        }
    finally:
        conn.close()

    assert unproven_carries == [], (
        "a theory_versions row claims kind='carry' with no equivalence_run "
        "-- the proof is the permission (spec 2.4), never an assertion:\n"
        + "\n".join(f"{r['theory_id']} v{r['version']}" for r in unproven_carries)
    )

    missing = [
        (t["id"], v)
        for t in theories
        for v in range(1, t["version"] + 1)
        if (t["id"], v) not in have
    ]
    assert missing == [], (
        "a theory's version history has a gap in theory_versions -- every "
        "version 1..current needs a row (backfilled once for pre-existing "
        "bumps per spec 2.6; any bump since must go through bump_version, "
        "never write theories.version directly), or carry_chain's walk and "
        "score.compute_score(pool='chain') silently stop short:\n"
        + "\n".join(f"{tid} v{v}" for tid, v in missing)
    )


def test_claude_md_points_at_the_generated_toolkit_listing():
    """CLAUDE.md must tell a session how to find out what tools exist.

    It deliberately does NOT enumerate them any more: it carried the list
    by hand and named ten modules out of twenty-five, so everything added
    afterwards was invisible to any session that trusted the file. The
    guarantee moved from "the list is complete" (which nothing could
    enforce) to "the way to get the list is named here" (which this can),
    with `tools/toolkit.py` generating it off disk. Losing this pointer
    would leave a session with no route to the toolkit at all.
    """
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "tools.cli tools" in claude, (
        "CLAUDE.md must name `python -m tools.cli tools` -- it is the only "
        "route a session has to what tools exist"
    )


def test_claude_md_does_not_name_a_tool_that_is_gone():
    """The mirror failure: a session told to use a module that no longer
    exists wastes a turn discovering the file is missing, and a rule
    written around it is unenforceable."""
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    named = set(re.findall(r"`(tools/[\w/]+\.py)`", claude))
    # Named to forbid it, not to offer it -- see "there is no
    # tools/backtest.py replay engine ... and neither gets built".
    named.discard("tools/backtest.py")
    absent = sorted(n for n in named if not (ROOT / n).exists())
    assert not absent, f"CLAUDE.md names tools that do not exist: {absent}"


#: Like `_PATH_LIKE`, but a leading dot is allowed. A skill naming
#: another skill's own file -- `.claude/skills/supervise/worker-brief.md`
#: -- would otherwise be skipped by the anchor and never checked, which
#: is exactly the citation most worth checking: it is read at runtime.
_SKILL_PATH_LIKE = re.compile(
    r"^\.?[A-Za-z0-9_][A-Za-z0-9_.\-]*(/[A-Za-z0-9_.\-]+)+/?$"
)


def _skill_paths():
    for skill_md in sorted(ROOT.glob(".claude/skills/*/*.md")):
        text = skill_md.read_text(encoding="utf-8")
        for span in re.findall(r"`([^`\n]+)`", text):
            # Same filter as `_doc_paths`: bare repo paths only, no
            # flags, placeholders, globs or URLs.
            if " " in span or "://" in span or "<" in span or "*" in span:
                continue
            if not _SKILL_PATH_LIKE.match(span):
                continue
            yield skill_md, span


def _skill_path_resolves(span: str) -> bool:
    if (ROOT / span).exists():
        return True
    # propose-theory names the theory template relative to `theories/`
    # (`_TEMPLATE/THEORY.md`), which is how a session reads it in
    # context. Resolving that fallback keeps the citation honest without
    # hardcoding an exception -- if the template moves, this still fails.
    return (ROOT / "theories" / span).exists()


def test_every_repo_path_named_in_a_skill_resolves():
    """Skills carry the operating procedure for every session, and a
    skill citing a file it no longer ships is invisible until a session
    tries to open it -- mid-run, with no way to recover the instruction.

    `_DOC_FILES` covers only README.md, CLAUDE.md and tools/README.md,
    so nothing watched `.claude/skills/` at all. Same failure mode
    `test_every_recorded_prompt_path_still_resolves` guards for judging
    prompts, applied to the skills that read a second file at runtime.
    """
    missing = [
        f"{md.parent.name}/{md.name}: `{span}`"
        for md, span in _skill_paths()
        if not _skill_path_resolves(span)
        and not _ALLOWED_MISSING.match(span)
        and span not in _DELIBERATELY_ABSENT
    ]
    assert missing == [], (
        "a skill names a repo path that does not resolve -- fix the skill "
        "or add a deliberate exception:\n" + "\n".join(missing)
    )


# --- the board reconstruction that stopped being a board ---

#: A file may filter market_snapshots on an exact capture stamp only with
#: this marker on the same line or the line before, naming why. Frozen
#: as-run study probes qualify; new analysis does not.
EXACT_STAMP_MARKER = "EXACT-STAMP-OK:"

_EXACT_STAMP = re.compile(r"captured_at\s*=\s*\?")


def _sql_literals(tree):
    """Every SQL string handed to a `.execute`/`.executemany` call, with the
    line it starts on.

    Matched through the AST rather than by scanning lines, because the
    files most likely to mention this query are the ones *documenting* the
    trap -- three of the first five line-level hits were prose warning
    against it. A guard that cries wolf on its own documentation gets
    muted.
    """
    import ast as _ast

    out = []
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        func = node.func
        if not isinstance(func, _ast.Attribute):
            continue
        if func.attr not in ("execute", "executemany"):
            continue
        if not node.args:
            continue
        parts = []

        def collect(n):
            if isinstance(n, _ast.Constant) and isinstance(n.value, str):
                parts.append(n.value)
            elif isinstance(n, _ast.BinOp):
                collect(n.left)
                collect(n.right)
            elif isinstance(n, _ast.JoinedStr):
                for v in n.values:
                    collect(v)

        collect(node.args[0])
        if parts:
            out.append((node.lineno, " ".join(parts)))
    return out


def test_no_new_code_rebuilds_a_board_by_exact_capture_stamp():
    """`WHERE captured_at = ?` silently stopped meaning "the board".

    Dedup-on-write (spec 5.2 phase 2, shipped 2026-08-30) means a pull
    writes NO row for a market whose payload did not change, so an
    exact-stamp filter returns *the markets that moved at that pull*. On
    this project's DB the 2026-08-31T00:38:34Z capture holds 53,613 rows
    against a 99,064-market board -- 46% missing, no error, and the missing
    subset is correlated with liquidity and therefore with price, side and
    volume. `tools.snapshot.board_as_of` is the reconstruction that is
    right; this test exists because the wrong query reads correct and
    cannot be caught by review a second time.

    Frozen as-run study probes and the one function that deliberately keeps
    the wrong query to size its own error carry the marker rather than
    being edited, so the record of what was actually run stays intact.
    """
    import ast as _ast

    offenders = []
    for path in sorted(ROOT.glob("**/*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(("tools/snapshot.py", "tests/", ".venv/")):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "captured_at" not in text:
            continue
        try:
            tree = _ast.parse(text)
        except SyntaxError:
            continue
        lines = text.splitlines()
        for lineno, sql in _sql_literals(tree):
            if not _EXACT_STAMP.search(sql):
                continue
            if "market_snapshots" not in sql:
                continue
            # The marker sits on, or in the comment block just above, the
            # statement -- close enough that it cannot drift onto an
            # unrelated query, wide enough for a real explanation.
            window = chr(10).join(lines[max(0, lineno - 12):lineno + 2])
            if EXACT_STAMP_MARKER in window:
                continue
            offenders.append(f"{rel}:{lineno}")
    assert not offenders, (
        "these rebuild a board with `captured_at = ?`, which returns the "
        "markets that MOVED at that pull, not the board. Use "
        "tools.snapshot.board_as_of(conn, platform, at), or mark a frozen "
        f"as-run record with `# {EXACT_STAMP_MARKER} <why>`: "
        + ", ".join(offenders)
    )


def test_the_exact_stamp_marker_is_not_a_blanket_opt_out():
    """A marker has to say why, so an exception stays auditable."""
    for path in sorted(ROOT.glob("**/*.py")):
        if path.relative_to(ROOT).as_posix().startswith("tests/"):
            continue
        for i, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines()
        ):
            if EXACT_STAMP_MARKER not in line:
                continue
            reason = line.split(EXACT_STAMP_MARKER, 1)[1].strip()
            assert len(reason) >= 20, (
                f"{path.relative_to(ROOT).as_posix()}:{i + 1} opts out of the "
                "board-reconstruction guard without saying why"
            )


_TOP_LEVEL = {
    ".claude", "attic", "db", "docs", "tests", "theories", "tickets",
    "tools", "user_reports",
}


def test_no_new_top_level_directory():
    """The top level is an allowlist. A new directory here is an
    architecture decision, not a side effect of somebody needing
    somewhere to put a file.

    `studies` is deliberately absent: it was dissolved on 2026-09-01
    when a study became a ticket living inside the theory that owns it,
    and this test is what stops it growing back one stray `mkdir` at a
    time.
    """
    skip = {"__pycache__", ".git", ".pytest_cache", ".venv",
            ".worktrees", ".superpowers"}
    found = set()
    for p in ROOT.iterdir():
        if not p.is_dir():
            continue
        if p.name.startswith(".") and p.name != ".claude":
            continue
        if p.name in skip:
            continue
        found.add(p.name)
    assert found <= _TOP_LEVEL, (
        "a new top-level directory appeared -- decide deliberately "
        f"whether it belongs: {sorted(found - _TOP_LEVEL)}"
    )


#: What a retired theory is allowed to keep. RETIRED.md is the death
#: certificate; THEORY.md is what it claimed; NOTES.md is the lab
#: notebook that proves it was tried; RESULTS.md is the DISTILLED
#: backtest performance -- the user's ruling of 2026-09-01 was "theory +
#: notes + backtest performance with details, not the entire backtest".
#: A `studies/` subtree is allowed because a retired theory's studies
#: retire with it.
_RETIRED_ALLOWED = {"RETIRED.md", "THEORY.md", "NOTES.md", "RESULTS.md"}


def test_a_retired_theory_holds_only_its_record():
    """A retired theory is a record, not a codebase.

    Its modules, runbook, prompts and raw backtest payloads are deleted
    at retirement and stay retrievable by git rev -- RETIRED.md names the
    rev. Without this test the folder quietly reacquires code one
    convenient file at a time, and the deletion is undone by drift rather
    than by decision.
    """
    retired_root = ROOT / "theories" / registry.RETIRED_DIRNAME
    if not retired_root.is_dir():
        pytest.skip("no theory has been retired into the tree yet")
    problems = []
    for folder in sorted(retired_root.iterdir()):
        if not folder.is_dir():
            continue
        if not (folder / registry.RETIRED_MARKER).is_file():
            problems.append(f"{folder.name}: no RETIRED.md marker")
        for path in folder.rglob("*"):
            if path.is_dir() or "studies" in path.relative_to(folder).parts:
                continue
            if path.name not in _RETIRED_ALLOWED:
                rel = path.relative_to(retired_root)
                problems.append(f"{rel}: not one of {sorted(_RETIRED_ALLOWED)}")
    assert problems == [], (
        "a retired theory holds more than its record -- retirement "
        "deletes the code and keeps the findings:\n" + "\n".join(problems)
    )


#: Theories the DB calls `retired` that have NOT been migrated into
#: `theories/retired/`, and are exempted from the test below.
#:
#: `mention_family` was retired 2026-08-26, five days before the folder
#: convention existed (user ruling 2026-09-01), and never moved. Its
#: migration is real outstanding work and is not free: it sits inside the
#: shared `theories/insider_bias/` family parent alongside
#: `insider_judgment`, it still owns a `studies/` subtree and open
#: tickets, and `no_side_premium` came off it -- so moving it is its own
#: change with its own review, not a side effect of a test run.
#:
#: This set is that debt made visible rather than hidden. The test below
#: checks every slug listed here is genuinely still un-migrated, so the
#: exemption cannot rot: whoever migrates `mention_family` deletes this
#: line in the same commit, or the suite tells them to.
_UNMIGRATED_RETIREMENTS = {"mention_family"}


def test_every_retired_theory_lives_under_theories_retired():
    """The converse of the test above, and the reason that one is not enough.

    `test_a_retired_theory_holds_only_its_record` inspects only folders
    ALREADY under `theories/retired/`, and skips entirely when that
    directory is absent. Nothing asserted the other direction, which left
    the exact failure this convention exists to prevent uncaught:

        the user retires `taker_flow`, and nobody migrates it.
        `theories/taker_flow/` keeps all nine of its modules.
        `registry.discover()` imports it exactly as before -- `retired`
        is not a scannable state. `registry.check_drift` returns [],
        because the class-side loop compares version and
        `uses_llm_judgment` and both still match. The folder never
        enters the test above, because it is not under
        `theories/retired/`. Every check in this file stays green while
        866K of a dead theory's code sits in the live tree -- precisely
        the state this branch was written to end.

    So this test starts from the DB rather than the filesystem: a row
    whose status is `retired` must have a `path` under
    `theories/retired/`, that folder must carry the RETIRED.md death
    certificate naming the git rev its deleted code lived at, and the
    theory must no longer be importable as a live one.

    Read-only, and skips cleanly if the working database is absent (a
    fresh clone, or CI) rather than creating one as a side effect of
    connecting -- `db.connect` would otherwise leave an empty file
    behind. Same pattern as `test_the_real_registry_has_no_drift` above.
    """
    if not db.DEFAULT_DB_PATH.exists():
        pytest.skip(
            f"{db.DEFAULT_DB_PATH} does not exist -- no working database "
            "to check retired-theory homes against in this environment"
        )
    conn = db.connect(db.DEFAULT_DB_PATH)
    try:
        rows = conn.execute(
            "SELECT id, path FROM theories WHERE status = 'retired'"
        ).fetchall()
    finally:
        conn.close()

    live = set(registry.discover())
    home = f"theories/{registry.RETIRED_DIRNAME}/"
    problems = []
    stale_exemptions = []

    for row in rows:
        slug = row["id"]
        path = (row["path"] or "").replace("\\", "/")
        migrated = path.startswith(home)
        if slug in _UNMIGRATED_RETIREMENTS:
            # The exemption has to keep earning itself. Once the theory
            # is migrated, the entry above is dead weight that would
            # silently excuse a future un-migrated retirement filed
            # under the same slug.
            if migrated and slug not in live:
                stale_exemptions.append(
                    f"{slug}: now migrated to `{path}` -- remove it from "
                    "_UNMIGRATED_RETIREMENTS"
                )
            continue
        if not migrated:
            problems.append(
                f"{slug}: status `retired` but its registry path is "
                f"`{path}` -- a retired theory moves to `{home}{slug}/`"
            )
        elif not (ROOT / path / registry.RETIRED_MARKER).is_file():
            problems.append(
                f"{slug}: `{path}` carries no {registry.RETIRED_MARKER} -- "
                "the death certificate is what names the git rev the "
                "deleted code is retrievable at"
            )
        if slug in live:
            problems.append(
                f"{slug}: status `retired` but registry.discover() still "
                "imports it -- its package was left behind in the live tree"
            )

    assert problems == [], (
        "a retired theory is still filed as a live one -- retirement "
        "moves the folder and deletes the code, it does not only change "
        "a status column:\n" + "\n".join(problems)
    )
    assert stale_exemptions == [], (
        "_UNMIGRATED_RETIREMENTS names a theory that has since been "
        "migrated -- delete the entry so it cannot excuse a future "
        "un-migrated retirement:\n" + "\n".join(stale_exemptions)
    )


def _tracked_files() -> list[str]:
    """Every path git tracks, repo-root-relative and forward-slashed.

    Shells out to `git ls-files` rather than walking the filesystem: an
    untracked scratch file sitting in a working tree is not a convention
    violation -- committing it is the moment somebody actually decided to
    keep it, and that is the moment this suite cares about. Skipped
    rather than failed when git itself is unavailable, because this
    suite has to stay runnable outside a checkout (a source tarball, an
    environment with no `.git` directory) and "no git" is a fact about
    the environment, not a violation of anything.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
        )
    except OSError:
        pytest.skip("git is not available in this environment")
    if proc.returncode != 0:
        pytest.skip("git ls-files failed in this environment")
    return [line for line in proc.stdout.splitlines() if line]


#: Extensions that mean "collected data" rather than "code or prose".
_DATA_SUFFIXES = {".jsonl", ".csv", ".parquet", ".db"}

#: Where collected data is allowed to live. A theory folder or a study's
#: state directory OWNS its data; `db/` is the shared store; `tests/`
#: holds fixtures. Anywhere else is data that escaped the thing that
#: produced it, which is how a repo grows a pile nobody can attribute.
_DATA_OWNERS = ("theories/", "tickets/study/", "db/", "tests/")


def test_data_files_live_with_their_owner():
    """Collected data belongs to the theory or study that produced it.

    Not a tidiness rule. Data with no owner is data nobody can decide
    about later: whether it is still needed, whether it can be
    regenerated, whether deleting it loses something unrecoverable. The
    owner's folder answers all three by construction.

    Every tracked data file in this repo already satisfies this; the test
    exists so the first exception is a decision somebody makes rather
    than a file that appears.
    """
    stray = []
    for line in _tracked_files():
        if Path(line).suffix.lower() not in _DATA_SUFFIXES:
            continue
        if not line.startswith(_DATA_OWNERS):
            stray.append(line)
    assert stray == [], (
        "collected data is sitting outside the theory or study that "
        "produced it -- move it to its owner's folder, or say in the "
        "session report why it had to escape:\n" + "\n".join(stray)
    )


def test_ticket_states_match_their_lane():
    """Each lane's state directories are its own and nothing else's.

    The lanes deliberately disagree: `study` has no `completed/` (its
    terminal state is `answer/`, which is what makes a finished study
    permanent -- `purge` matches `completed/`, so the query cannot reach
    it), and `new-theory` has `evidence/` and `implement/` that no other
    lane has. A stray directory in the wrong lane is a ticket nobody
    lists and a state nothing advances out of.

    `tickets/new-theory/reference/` is NOT a state and is excluded on
    purpose: it holds the lane's shared reference material, and it was
    moved out of `evidence/` precisely because being scanned as a state
    made `backlog()` report three permanent malformed rows.
    """
    from tools import tickets

    allowed_extra = {"README.md", "reference"}
    problems = []
    for lane, dirname in tickets.ROOT_LANES.items():
        base = ROOT / "tickets" / dirname
        if not base.is_dir():
            continue
        legal = set(tickets.states_for(lane)) | allowed_extra
        for child in sorted(base.iterdir()):
            if child.name not in legal:
                problems.append(f"tickets/{dirname}/{child.name}")
    for base in sorted((ROOT / "tickets" / "study").glob("*")):
        if base.is_dir() and base.name not in tickets.states_for("study"):
            problems.append(f"tickets/study/{base.name}")
    assert problems == [], (
        "a ticket state directory does not belong to its lane:\n"
        + "\n".join(problems)
    )
