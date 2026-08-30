"""Registered sub-population slices — subset edges with their own credibility.

A theory's aggregate can be flat while a defined subset of its output
carries a real, mechanism-backed edge. The worked example is
`insider_judgment`: the whole screen is breakeven at scale, but the bet
rule pre-registered after its first judged round — strong-or-moderate
verdict, NO side — scored +4.92pts net (p=0.0008) on the events judged
after registration. One credibility number per theory buries that: the
proven subset ranks on the aggregate, and the unproven remainder borrows
whatever the subset earned.

A *slice* fixes both directions. It is a registered hypothesis that a
mechanical subset of one theory's output has its own edge:

- **The predicate is data, never judgment** — an AND of clauses over
  recorded ledger fields (`outcome`, `confidence` bucket, `entry_price`
  band, exact-match `extra` features). If a boundary cannot be written
  in that vocabulary, it is not a slice; it is a new theory.
- **Immutable once registered.** Editing a predicate would silently
  merge two hypotheses into one track record — the same merge theory
  versioning forbids. Supersede with a new slug and retire the old one;
  retiring is a governance call (user / supervisor), like retiring a
  theory. Registering a slice never bumps the theory's version: it
  changes which evidence row the *ranking layer* reads, not the
  theory's decision procedure. Facts are data, not procedure.
- **Credibility is out-of-sample only.** A pattern found by mining
  settled rows is a hypothesis, never an edge on the data that
  suggested it. An observation matching the predicate feeds the
  slice's credibility only if its **settlement day is strictly after
  the registration day** — an outcome unknowable when the hypothesis
  was registered cannot have suggested it — or one of its runs was
  designated out-of-sample at registration (`oos_run_ids`, with the
  argument recorded in `origin`; designation matches ANY run that
  proposed the position, because the first seer is often a mechanical
  screen and the designated run is the judged re-proposal). Tier-C
  runs never count, here as everywhere. Everything else lands in
  `in_sample` — visible for diagnosis, never in the credibility path.
  A backtest over already-settled history is in-sample *by default*,
  however recently it ran.
- **Readiness gates, then a partition.** A slice drives ranking only
  once its out-of-sample evidence clears `MIN_SLICE_CLUSTERS` event
  clusters and `MIN_SLICE_DAYS` distinct settlement days. Below the
  gates nothing changes. At them, the theory's evidence pool is
  partitioned: candidates matching a ready slice rank on the slice's
  own out-of-sample score, everything else ranks on the **complement**
  (observations matching no ready slice) — the remainder never borrows
  a slice's shine, and a ready slice that turns out bad drags exactly
  its own candidates down. `rank.credibility` is untouched; this module
  only selects which score row feeds it.

The evidence pool spans live and backtest run modes by default, because
for a judgment theory the demonstrated slice evidence usually *is*
tier-B backtest rows; every segment in one report comes from the same
pool, so the numbers are comparable. All identity, decision-attempt,
and cluster semantics are inherited from `score.observations`.

Design: docs/superpowers/specs/2026-08-29-theory-slices-design.md.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from typing import Callable, Mapping

from tools import score, theories
from tools.db import utcnow, write
from tools.rank import PROBATION_N

MIN_SLICE_CLUSTERS = PROBATION_N
"""Out-of-sample event clusters before a slice may drive ranking.

The same probation floor `rank.credibility` applies to a theory, on the
same cluster semantics — a slice holding fifty siblings of one event has
watched one event resolve.
"""

MIN_SLICE_DAYS = 5
"""Distinct out-of-sample settlement days before a slice may speak.

The same floor, for the same reason, as `buckets.MIN_BUCKET_DAYS`: the
settlement-day clustering study (`studies/2026-08-27-settlement-day-
clustering/`) measured one screen population swinging several points
between consecutive close-days, so one hot night must not define a
slice any more than it may define a bucket.
"""

DEFAULT_RUN_MODES = ("live", "backtest")

_PREDICATE_KEYS = ("outcome", "confidence", "entry_price", "extra")


def _field(row: Mapping | sqlite3.Row, key: str, default=None):
    """Read a field from a dict or an sqlite3.Row, absent-tolerant."""
    if isinstance(row, sqlite3.Row):
        return row[key] if key in row.keys() else default
    return row.get(key, default)


def _row_extra(row: Mapping | sqlite3.Row) -> dict:
    """The row's extra-features dict, from `extra` or parsed `extra_json`."""
    extra = _field(row, "extra")
    if isinstance(extra, dict):
        return extra
    raw = _field(row, "extra_json")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            pass
    return {}


def _str_list(predicate: dict, key: str) -> list[str] | None:
    values = predicate.get(key)
    if values is None:
        return None
    if (
        not isinstance(values, list)
        or not values
        or not all(isinstance(v, str) and v for v in values)
    ):
        raise ValueError(
            f"predicate clause {key!r} must be a non-empty list of strings, "
            f"got {values!r}"
        )
    return [v.lower() for v in values]


def build_matcher(predicate: dict) -> Callable[[Mapping], bool]:
    """Turn a predicate dict into a callable over a ledger/observation row.

    Clauses AND together; unknown keys raise, because a silently ignored
    clause is a slice matching a different population than the one that
    was registered. A basket never matches — the vocabulary is
    single-leg. A row whose `confidence` is NULL fails a `confidence`
    clause (the judgment the slice conditions on never happened).

    Accepts both shapes this repo produces: `score.observations` dicts
    (with `extra` already parsed) and ledger rows (with `extra_json`).
    """
    if not isinstance(predicate, dict) or not predicate:
        raise ValueError(
            f"predicate must be a non-empty dict of clauses, got {predicate!r}"
        )
    unknown = set(predicate) - set(_PREDICATE_KEYS)
    if unknown:
        raise ValueError(
            f"unknown predicate clause(s) {sorted(unknown)}; "
            f"supported: {list(_PREDICATE_KEYS)}"
        )

    outcomes = _str_list(predicate, "outcome")
    confidences = _str_list(predicate, "confidence")

    price = predicate.get("entry_price")
    if price is not None:
        if (
            not isinstance(price, dict)
            or not price
            or set(price) - {"min", "max"}
            or not all(isinstance(v, (int, float)) for v in price.values())
        ):
            raise ValueError(
                "predicate clause 'entry_price' must be a dict with numeric "
                f"'min' and/or 'max', got {price!r}"
            )

    extra = predicate.get("extra")
    if extra is not None and (not isinstance(extra, dict) or not extra):
        raise ValueError(
            f"predicate clause 'extra' must be a non-empty dict, got {extra!r}"
        )

    def matches(row: Mapping) -> bool:
        if _field(row, "position_kind", "single") == "basket":
            return False
        if outcomes is not None:
            value = _field(row, "outcome")
            if value is None or str(value).lower() not in outcomes:
                return False
        if confidences is not None:
            value = _field(row, "confidence")
            if value is None or str(value).lower() not in confidences:
                return False
        if price is not None:
            value = _field(row, "entry_price")
            if value is None:
                return False
            if "min" in price and value < price["min"]:
                return False
            if "max" in price and value > price["max"]:
                return False
        if extra is not None:
            row_extra = _row_extra(row)
            for key, expected in extra.items():
                if key not in row_extra or row_extra[key] != expected:
                    return False
        return True

    return matches


def register_slice(
    conn: sqlite3.Connection,
    theory_id: str,
    slug: str,
    *,
    predicate: dict,
    hypothesis: str,
    origin: str,
    oos_run_ids: tuple[str, ...] | list[str] = (),
    priority: int = 0,
    registered_at: str | None = None,
    now: str | None = None,
) -> None:
    """Register a slice. The registration IS the pre-registration.

    `hypothesis` is the mechanism claim — why this subset should differ
    from the aggregate; a slice with no mechanism is curve-fitting with
    a slug. `origin` says where the pattern was found (run ids, study,
    notes entry). `registered_at` defaults to now; passing an earlier
    date is an evidentiary claim and `origin` MUST cite the auditable
    record for it (a dated THEORY.md entry, a study, git history) —
    likewise the argument for every run in `oos_run_ids`. Slices are
    immutable: a duplicate slug raises, because changing a registered
    predicate would merge two hypotheses into one track record.
    """
    if theories.get(conn, theory_id) is None:
        raise ValueError(f"unknown theory {theory_id!r}")
    if not slug or not slug.strip():
        raise ValueError("slug is required")
    if not hypothesis or not hypothesis.strip():
        raise ValueError(
            "hypothesis is required: state the mechanism, not just the cut"
        )
    if not origin or not origin.strip():
        raise ValueError(
            "origin is required: where was this pattern found, and what "
            "justifies any backdated registration or oos_run_ids"
        )
    build_matcher(predicate)  # fail loudly now, not at first scoring
    ids = list(oos_run_ids)
    if not all(isinstance(r, str) and r for r in ids):
        raise ValueError(f"oos_run_ids must be run-id strings, got {ids!r}")
    stamp = now or utcnow()
    try:
        with write(conn):
            conn.execute(
                """
                INSERT INTO theory_slices (
                    theory_id, slug, predicate_json, hypothesis, origin,
                    registered_at, oos_run_ids, priority, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    theory_id, slug, json.dumps(predicate), hypothesis,
                    origin, registered_at or stamp,
                    json.dumps(ids) if ids else None, priority, stamp,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError(
            f"slice {theory_id}/{slug} already exists and slices are "
            "immutable — register a new slug and retire the old one"
        ) from exc


def retire_slice(
    conn: sqlite3.Connection,
    theory_id: str,
    slug: str,
    *,
    reason: str,
    now: str | None = None,
) -> None:
    """Retire a slice — a governance call, like retiring a theory.

    Claude proposes; the user (or the supervisor session the user has
    delegated to) authorizes. A retired slice stops driving ranking but
    keeps reporting, so a slice cannot make a bad out-of-sample record
    disappear by being retired — its rows rejoin the complement, and
    `segment_report` still shows the retired slice's evidence.
    """
    if not reason or not reason.strip():
        raise ValueError("a retirement reason is required")
    row = get_slice(conn, theory_id, slug)
    if row is None:
        raise ValueError(f"no slice {theory_id}/{slug}")
    if row["status"] == "retired":
        raise ValueError(f"slice {theory_id}/{slug} is already retired")
    with write(conn):
        conn.execute(
            """
            UPDATE theory_slices
            SET status = 'retired', retired_at = ?, retired_reason = ?
            WHERE theory_id = ? AND slug = ?
            """,
            (now or utcnow(), reason, theory_id, slug),
        )


def get_slice(
    conn: sqlite3.Connection, theory_id: str, slug: str
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM theory_slices WHERE theory_id = ? AND slug = ?",
        (theory_id, slug),
    ).fetchone()


def list_slices(
    conn: sqlite3.Connection, theory_id: str | None = None
) -> list[sqlite3.Row]:
    """All slices, in ranking precedence order (priority, then age)."""
    sql = "SELECT * FROM theory_slices"
    params: list[object] = []
    if theory_id is not None:
        sql += " WHERE theory_id = ?"
        params.append(theory_id)
    sql += " ORDER BY priority DESC, registered_at ASC, slug ASC"
    return conn.execute(sql, params).fetchall()


def _n_days(obs: list[dict]) -> int | None:
    """Distinct settlement days behind a group, or None when undatable.

    None (not zero) when no member carries a resolved day, matching
    `score.bucket_rates`: unknown must read as unknown, and the
    readiness gate fails closed on it.
    """
    days = {o.get("resolved_day") for o in obs if o.get("resolved_day")}
    return len(days) or None


def _with_days(obs: list[dict]) -> dict:
    """A segment score plus its settlement-day view.

    `day_clustered_se` is the between-day SE of the per-day net
    calibration edge — the same statistic `score.settlement_day_clusters`
    reports, computed here because a segment is an arbitrary observation
    subset. It exists because this population's judged backtests flipped
    sign purely on how days were weighted (NOTES.md 2026-08-27): a
    segment must be readable at the day level or it is not readable.
    None below two days — one cluster says nothing about spread.
    """
    result = score.aggregate(obs)
    result["n_days"] = _n_days(obs)
    by_day: dict[str, list[float]] = {}
    for o in obs:
        day = o.get("resolved_day")
        if not day or o.get("riskless") or o.get("implied_rate") is None:
            continue
        by_day.setdefault(day, []).append(
            (o["won"] - o["implied_rate"]) * 100.0 - o["fee_pts"]
        )
    if len(by_day) >= 2:
        means = [statistics.mean(v) for v in by_day.values()]
        # Day-weighted, so it deliberately differs from the row-weighted
        # calibration_edge_net above — the SE describes THIS mean, per
        # `score.settlement_day_clusters`' convention.
        result["day_mean_edge_net"] = statistics.mean(means)
        result["day_clustered_se"] = (
            statistics.stdev(means) / len(means) ** 0.5
        )
    else:
        result["day_mean_edge_net"] = None
        result["day_clustered_se"] = None
    return result


def _evaluate(
    srow: sqlite3.Row, obs: list[dict]
) -> tuple[dict, Callable[[Mapping], bool]]:
    """One slice's evidence split over an already-tier-filtered pool."""
    predicate = json.loads(srow["predicate_json"])
    matcher = build_matcher(predicate)
    oos_ids = set(
        json.loads(srow["oos_run_ids"]) if srow["oos_run_ids"] else []
    )
    registered_day = str(srow["registered_at"])[:10]

    oos: list[dict] = []
    in_sample: list[dict] = []
    for o in obs:
        if not matcher(o):
            continue
        runs = set(o.get("run_ids") or [])
        if not runs and o.get("run_id"):
            runs = {o["run_id"]}
        day = o.get("resolved_day")
        # Out-of-sample means the outcome could not have suggested the
        # hypothesis: settled strictly after the registration day, or
        # proposed by a run designated at registration. Settlement ON
        # the registration day is ambiguous, and ambiguity — like a
        # missing settlement date — resolves against the slice.
        if (runs & oos_ids) or (day and str(day) > registered_day):
            oos.append(o)
        else:
            in_sample.append(o)

    oos_score = _with_days(oos)
    ready = (
        srow["status"] == "registered"
        and (oos_score["n_clusters"] or 0) >= MIN_SLICE_CLUSTERS
        and (oos_score["n_days"] or 0) >= MIN_SLICE_DAYS
    )
    return {
        "slug": srow["slug"],
        "status": srow["status"],
        "predicate": predicate,
        "hypothesis": srow["hypothesis"],
        "origin": srow["origin"],
        "registered_at": srow["registered_at"],
        "priority": srow["priority"],
        "oos": oos_score,
        "in_sample": _with_days(in_sample),
        "ready": ready,
        "ready_gates": {
            "min_clusters": MIN_SLICE_CLUSTERS,
            "min_days": MIN_SLICE_DAYS,
        },
        "retired_reason": srow["retired_reason"],
    }, matcher


def segment_report(
    conn: sqlite3.Connection,
    theory_id: str,
    theory_version: int | None = None,
    *,
    disposition: str = "all",
    run_modes: tuple[str, ...] = DEFAULT_RUN_MODES,
    run_id: str | None = None,
    pool: str = "version",
) -> dict:
    """Every ranking segment of one theory, from one shared evidence pool.

    Returns `aggregate` (the whole pool), one entry per slice (its
    out-of-sample and in-sample scores, each with `n_days`, plus the
    readiness verdict), and `complement` — the pool minus every READY
    slice's matches, or None when no slice is ready (rank on the
    aggregate then, exactly as before slices existed). Tier-C rows are
    excluded from the entire pool — contaminated evidence feeds no
    segment — and counted in `tier_c_excluded_rows`.

    `pool="version"` (default) is today's behaviour, unchanged — no
    existing caller's meaning moves. `pool="chain"` widens the evidence
    pool the same way `score.compute_score(pool="chain")` does (spec
    2.5): every observation query runs over the maximal run of
    consecutive versions a proven `carry` bump links back to
    `theory_version` (`theories.carry_chain`), so a slice's segments —
    aggregate, each slice's oos/in_sample, and the complement — pool a
    predecessor's rows in too. The returned dict then gains
    `chain_versions` so a pooled report can never be read without seeing
    what was pooled into it; a chain of one version (nothing proven
    carry) adds no key, since nothing was pooled.
    """
    if pool not in ("version", "chain"):
        raise ValueError(f"invalid pool {pool!r}; expected 'version' or 'chain'")

    if theory_version is None:
        trow = theories.get(conn, theory_id)
        if trow is None:
            raise ValueError(f"unknown theory {theory_id!r}")
        theory_version = trow["version"]

    tiers = {
        r["run_id"]: r["tier"]
        for r in conn.execute("SELECT run_id, tier FROM backtest_runs")
    }
    raw_obs: list[dict] = []
    for mode in run_modes:
        raw_obs.extend(
            score.observations(
                conn, theory_id, theory_version, mode, disposition,
                run_id=run_id, pool=pool,
            )
        )

    def _touched_by_tier_c(o: dict) -> bool:
        # ANY touching run, not just the first seer: a position's rollup
        # (its confidence, in particular) can come from a later run, so a
        # tier-C touch contaminates the row wherever it sits.
        runs = o.get("run_ids") or ([o["run_id"]] if o.get("run_id") else [])
        return any(tiers.get(r) == "C" for r in runs)

    obs = [o for o in raw_obs if not _touched_by_tier_c(o)]

    evaluated: list[dict] = []
    ready_matchers: list[Callable[[Mapping], bool]] = []
    for srow in list_slices(conn, theory_id):
        result, matcher = _evaluate(srow, obs)
        evaluated.append(result)
        if result["ready"]:
            ready_matchers.append(matcher)

    complement = None
    if ready_matchers:
        complement = _with_days(
            [o for o in obs if not any(m(o) for m in ready_matchers)]
        )

    report = {
        "theory_id": theory_id,
        "theory_version": theory_version,
        "disposition": disposition,
        "run_modes": list(run_modes),
        "tier_c_excluded_rows": len(raw_obs) - len(obs),
        "aggregate": _with_days(obs),
        "slices": evaluated,
        "complement": complement,
    }
    if pool == "chain":
        chain = theories.carry_chain(conn, theory_id, theory_version)
        if len(chain) > 1:
            report["chain_versions"] = chain
    return report


def ranking_segment(
    conn: sqlite3.Connection,
    row: Mapping | sqlite3.Row,
    *,
    theory_id: str | None = None,
    theory_version: int | None = None,
    disposition: str = "all",
    run_modes: tuple[str, ...] = DEFAULT_RUN_MODES,
    report: dict | None = None,
) -> dict:
    """Which evidence row ranks this candidate, and why.

    `row` is a ledger opportunity row (or any mapping carrying the
    predicate fields). The returned `rank_inputs` maps 1:1 onto
    `python -m tools.cli rank` — `n` is already the CLUSTER count.
    Candidates matching a ready slice rank on that slice's out-of-sample
    score; when any slice is ready, everything else ranks on the
    complement (the pool its settlement would join); with no ready
    slice, on the aggregate, exactly as before slices existed. Pass
    `report` (one `segment_report` call) when ranking a whole
    candidate list, rather than recomputing per row.
    """
    if theory_id is None:
        theory_id = _field(row, "theory_id")
    if theory_version is None:
        theory_version = _field(row, "theory_version")
    if report is None:
        report = segment_report(
            conn, theory_id, theory_version,
            disposition=disposition, run_modes=run_modes,
        )

    matched = None
    retired_matches: list[str] = []
    for entry in report["slices"]:
        if not build_matcher(entry["predicate"])(row):
            continue
        if entry["status"] == "retired":
            retired_matches.append(entry["slug"])
            continue
        if matched is None:
            matched = entry

    any_ready = any(
        s["ready"] and s["status"] == "registered" for s in report["slices"]
    )
    note = None
    if matched is not None and matched["ready"]:
        segment, seg_score = "slice:" + matched["slug"], matched["oos"]
    elif any_ready:
        segment, seg_score = "complement", report["complement"]
        if matched is not None:
            note = (
                f"matches slice {matched['slug']!r}, which is registered "
                "but below its evidence gates; ranking on the complement "
                "it still belongs to"
            )
    else:
        segment, seg_score = "aggregate", report["aggregate"]
        if matched is not None:
            note = (
                f"matches slice {matched['slug']!r}, which is registered "
                "but below its evidence gates; ranking on the aggregate"
            )

    return {
        "segment": segment,
        "matched_slice": matched["slug"] if matched else None,
        "matched_slice_ready": bool(matched and matched["ready"]),
        "retired_matches": retired_matches,
        "note": note,
        "score": seg_score,
        "rank_inputs": {
            "n": seg_score["n_clusters"],
            "calibration_edge_net": seg_score["calibration_edge_net"],
            "mean_claimed_edge": seg_score["mean_claimed_edge"],
        },
    }
