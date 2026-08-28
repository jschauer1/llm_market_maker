"""Repo-wide conventions the OOP layer promises (spec sections 3.2, 4.2,
4.5c, 9): every theory package exposes a proper singleton, nobody
overrides the workflow, a Verdict can never grow a number, the migration
shim is gone for good, and the actually-running registry has no drift
between code and DB."""

import ast
import inspect
import pytest
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
