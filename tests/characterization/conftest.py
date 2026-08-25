"""Shared loaders and the canonical projection for the golden tests.

Goldens are stored as JSON. Live values are projected to the same JSON
before comparison: a dict projects as itself, and the domain dataclasses
that appear during the OOP migration project to the legacy dict shapes
they replace.

That indirection is the whole reason the migration can prove itself.
Phase 2 changes `normalize()`'s return *type* from dict to `Market`, so
literal equality across that phase is impossible by definition -- the very
change the phase exists to make would fail it. Field-level equality
through `proj` is the pass condition instead, and **the golden FILES never
change**: a diff means behavior moved, which is a bug to fix or a version
bump to escalate, never a file to regenerate.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
GOLDENS = HERE / "goldens"

# The fixture and the largest golden are ~9 MB each; re-parsing them per
# test costs more than every assertion combined. Cached because nothing
# here mutates what it is handed -- the screen copies, the gate and the
# payload builder only read.


@lru_cache(maxsize=None)
def load_fixture() -> list[dict]:
    """The committed board sample, as raw normalize()-shaped dicts."""
    return json.loads((FIXTURES / "board_sample.json").read_text("utf-8"))


@lru_cache(maxsize=None)
def _meta() -> dict:
    return json.loads((FIXTURES / "meta.json").read_text("utf-8"))


def frozen_now() -> datetime:
    """The board's capture moment. Nothing here reads a wall clock."""
    return datetime.fromisoformat(_meta()["frozen_now"].replace("Z", "+00:00"))


def frozen_rates() -> dict:
    """mention_family's measured bucket rates, frozen at fixture time."""
    return _meta()["rates"]


def preview_days() -> float:
    """Horizon the mention_family coverage goldens use. See build_fixture."""
    return _meta()["preview_days"]


def board_input() -> list:
    """The fixture in whatever shape the current screen consumes.

    Task 12 switched this from raw dicts to domain.Market objects, matching
    board.get_board()'s real return type. The golden files are untouched by
    that switch -- proj() is what keeps them comparable.
    """
    from tools.domain import Market
    return [Market.from_mapping(m) for m in load_fixture()]


def event_key(c) -> str:
    """Event identity of a screen candidate, dict- and domain-shaped.

    Phase 0 candidates are dicts; from Task 12 they are domain.Candidate.
    Harness plumbing handles both so the golden files never change.
    """
    if isinstance(c, dict):
        return c.get("event_ticker") or c.get("ticker")
    return c.key


@lru_cache(maxsize=None)
def load_golden(name: str):
    return json.loads((GOLDENS / f"{name}.json").read_text("utf-8"))


def dump_golden(name: str, value) -> None:
    GOLDENS.mkdir(exist_ok=True)
    path = GOLDENS / f"{name}.json"
    if path.exists():
        raise RuntimeError(
            f"golden {name!r} already exists. Goldens are immutable after "
            "Phase 0: a diff is a behavior change to fix or escalate, never "
            "a file to regenerate (OOP spec section 8.2)."
        )
    path.write_text(
        json.dumps(proj(value), sort_keys=True, indent=1), encoding="utf-8"
    )


@lru_cache(maxsize=1)
def _domain():
    """tools.domain once it exists, else None. Cached because proj()
    recurses over every field of every market -- resolving the import per
    call dominated the whole suite's runtime."""
    try:
        from tools import domain
    except ImportError:                      # before Phase 1: dicts only
        return None
    return domain


def proj(x):
    """Project a live value onto its canonical JSON shape.

    Grows a branch per domain type as the migration introduces them. Lives
    in the harness, never in the code under test.
    """
    domain = _domain()

    if domain is not None:
        if isinstance(x, domain.ScoredCandidate):
            return {
                **proj(x.candidate),
                "edge_pts_net": x.edge.pts_net,
                "edge_basis": x.edge.basis,
                "bucket": x.confidence,
            }
        if isinstance(x, domain.Candidate):
            leg = x.legs[0]
            return {
                **proj(leg.market),
                "fav_side": leg.side,
                "entry_price": leg.price,
                "days_to_close": x.days_to_close,
            }
        if isinstance(x, (domain.Market, domain.PolymarketMarket)):
            from dataclasses import asdict

            return proj(asdict(x))

    if isinstance(x, dict):
        return {k: proj(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [proj(v) for v in x]
    return x
