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
  slice's credibility if any of three things holds: its **settlement
  day is strictly after the registration day** (an outcome unknowable
  when the hypothesis was registered cannot have suggested it); one of
  its runs was **designated out-of-sample at registration**
  (`oos_run_ids`, with the argument recorded in `origin`; designation
  matches ANY run that proposed the position, because the first seer is
  often a mechanical screen and the designated run is the judged
  re-proposal); or it was **replayed by a tier A or tier B backtest**.
  That third clause is the 2026-08-31 user ruling: a backtested edge is
  evidence exactly as a forward-settled one is, for a slice as much as
  for a whole theory, and it must never be described as weaker for
  being backtested. Tier-C runs never count, here as everywhere, and
  neither does a replay whose tier was never recorded — unknown
  provenance resolves against the slice, as an ambiguous settlement
  date does.

  What the ruling did *not* relax: **the runs a slice was mined from,
  named in `mined_from_run_ids` at registration, never vouch for it**,
  whatever their tier. Before the ruling that guard was implicit — a
  replay of settled history always failed the date test — so the
  bookkeeping is now inverted: declare the mining run rather than
  designating the confirming ones. Everything excluded lands in
  `in_sample`: visible for diagnosis, never in the credibility path.

  Every segment score carries `n_backtest`, the count of its rows that
  came from a replay. That is **disclosure, not a discount** — the user
  asked to be told when a bet rests on replayed history, and the
  reporting surfaces say so; nothing in the ranking math reads it.
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

**A slice is MAINTAINED, not absorbed.** Once ready it is already the
decision point for the rows its predicate matches: `ranking_segment`
routes a matching candidate to the slice's own score row and `promote`
ranks it there. So there is nothing to promote a proven slice to, and
the parent's screen is never rewritten to produce only the slice's
population. Folding the predicate into the parent buys an identical bet
and costs two things that cannot be recovered -- the complement (the
control group that says whether the slice is still the part that works)
and the out-of-sample split below (`registered_at`,
`mined_from_run_ids`), without which the slice's own number means
nothing. A slice orphaned by a version bump is fixed by relinking the
chain (`theories.reclassify_bump`), never by adoption; a slice whose
parent is retired is proposed as its own theory, starting at n=0 and
citing its measurements rather than inheriting them.

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

from tools import evidence, score, theories
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
settlement-day clustering study
(`tickets/study/answer/2026-08-27-settlement-day-clustering/`) measured one screen population swinging several points
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
    mined_from_run_ids: tuple[str, ...] | list[str] = (),
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

    `mined_from_run_ids` names the runs whose rows *suggested* this
    slice. They are excluded from its credibility permanently — a
    pattern cannot vouch for itself — and naming them is the whole
    discipline now that a tier A/B backtest counts as evidence by
    default (user ruling 2026-08-31). If the pattern came out of a
    replay, say so here; `origin` should carry the same citation in
    prose.
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
    mined = list(mined_from_run_ids)
    if not all(isinstance(r, str) and r for r in mined):
        raise ValueError(
            f"mined_from_run_ids must be run-id strings, got {mined!r}"
        )
    overlap = set(ids) & set(mined)
    if overlap:
        raise ValueError(
            f"run(s) {sorted(overlap)} are named both out-of-sample and "
            "mined-from; a run cannot both vouch for a slice and be the "
            "data that suggested it"
        )
    stamp = now or utcnow()
    try:
        with write(conn):
            conn.execute(
                """
                INSERT INTO theory_slices (
                    theory_id, slug, predicate_json, hypothesis, origin,
                    registered_at, oos_run_ids, mined_from_run_ids,
                    priority, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    theory_id, slug, json.dumps(predicate), hypothesis,
                    origin, registered_at or stamp,
                    json.dumps(ids) if ids else None,
                    json.dumps(mined) if mined else None, priority, stamp,
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


def declare_mined_from(
    conn: sqlite3.Connection,
    theory_id: str,
    slug: str,
    run_ids: tuple[str, ...] | list[str],
) -> list[str]:
    """Declare runs whose rows suggested this slice. Returns the new set.

    Slices are immutable, and this is the one field that may be set
    after registration — because it can only ever *restrict* a slice's
    evidence, never widen it. Declaring a mining run takes rows out of
    the credibility path; nothing here can put one back. That invariant
    is what makes a late declaration safe, so it is enforced: the call
    is additive, and withdrawing a declared run raises.

    It exists for the 2026-08-31 ruling. Slices registered before it
    named their mining run only in `origin` prose, because the field did
    not exist and the old default excluded every replay anyway. Flipping
    that default would silently promote exactly those rows into the
    evidence they were never allowed to be — so a pre-ruling slice with
    a documented mining run declares it here, and the registration means
    afterwards what it always said it meant.
    """
    row = get_slice(conn, theory_id, slug)
    if row is None:
        raise ValueError(f"no slice {theory_id}/{slug}")
    ids = list(run_ids)
    if not all(isinstance(r, str) and r for r in ids):
        raise ValueError(f"run ids must be non-empty strings, got {ids!r}")
    if not ids:
        # The only way to ask for less. There is no call that removes a
        # declared run, so an empty declaration is either a mistake or an
        # attempt at one; both deserve the same answer.
        raise ValueError(
            f"nothing to declare for {theory_id}/{slug}: mining runs are "
            "never withdrawn. A slice may only ever exclude more of its "
            "own evidence, never reclaim what it already gave up"
        )
    existing = set(
        json.loads(row["mined_from_run_ids"])
        if row["mined_from_run_ids"] else []
    )
    merged = sorted(existing | set(ids))
    oos = set(json.loads(row["oos_run_ids"]) if row["oos_run_ids"] else [])
    overlap = oos & set(merged)
    if overlap:
        raise ValueError(
            f"run(s) {sorted(overlap)} are designated out-of-sample for "
            f"{theory_id}/{slug}; a run cannot both vouch for a slice and "
            "be the data that suggested it"
        )
    with write(conn):
        conn.execute(
            "UPDATE theory_slices SET mined_from_run_ids = ?"
            " WHERE theory_id = ? AND slug = ?",
            (json.dumps(merged), theory_id, slug),
        )
    return merged


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
    # Disclosure, not a discount. A backtested edge counts exactly as a
    # forward one does (user ruling 2026-08-31), but the user asked to be
    # told when a bet rests on replayed history, so every segment score
    # carries the split and the report surfaces it.
    result["n_backtest"] = sum(
        1 for o in obs if o.get("run_mode") == "backtest"
    )
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
    """One slice's evidence split over an already-tier-filtered pool.

    Every backtest observation in `obs` has already passed the shared
    production selector, so it is documented tier A/B evidence in full.
    """
    predicate = json.loads(srow["predicate_json"])
    matcher = build_matcher(predicate)
    oos_ids = set(
        json.loads(srow["oos_run_ids"]) if srow["oos_run_ids"] else []
    )
    # A row read from a database migrated only to the previous schema has
    # no such column; treat that as "nothing declared", never as a crash.
    mined_raw = (
        srow["mined_from_run_ids"]
        if "mined_from_run_ids" in srow.keys() else None
    )
    mined_ids = set(json.loads(mined_raw) if mined_raw else [])
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
        # Out-of-sample means the row is evidence rather than the data
        # that suggested the hypothesis. Three ways to qualify:
        # settled strictly after the registration day; proposed by a run
        # designated at registration; or replayed by a tier A/B backtest
        # (user ruling 2026-08-31 — a backtested edge is evidence
        # exactly as a forward-settled one is, and the tier is what
        # already rules out a model recalling outcomes it was trained
        # on). Untiered and contaminated replays were removed by the
        # shared selector before this slice-specific split.
        #
        # The mining exception overrides all three. A pattern found by
        # slicing a run's own rows can never cite that run, however good
        # its tier — that is the whole of what the old
        # backtests-are-in-sample default was protecting, kept explicit
        # now that the default is gone.
        if runs & mined_ids:
            in_sample.append(o)
        elif (
            (runs & oos_ids)
            or (day and str(day) > registered_day)
            or o.get("run_mode") == "backtest"
        ):
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
    pool: str = "chain",
) -> dict:
    """Every ranking segment of one theory, from one shared evidence pool.

    Returns `aggregate` (the whole pool), one entry per slice (its
    out-of-sample and in-sample scores, each with `n_days`, plus the
    readiness verdict), and `complement` — the pool minus every READY
    slice's matches, or None when no slice is ready (rank on the
    aggregate then, exactly as before slices existed). Shared production
    eligibility is applied before slice-specific mining/OOS logic: tier C,
    NULL-tier, unregistered, and mismatched replay registrations feed no
    segment. `evidence_exclusions` reports each reason; the older
    `tier_c_excluded_rows` key remains as a compatibility view.

    `pool="version"` restricts the sample to the requested version.
    The default `pool="chain"` widens the evidence
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

    raw_obs: list[dict] = []
    for mode in run_modes:
        rows = score.observations(
            conn, theory_id, theory_version, mode, disposition,
            run_id=run_id, pool=pool,
        )
        # The mode is known only here, where it was queried. Tagging it
        # onto the row is what lets a slice tell a replayed settlement
        # from one that came in forward -- and what lets a segment score
        # disclose how much of its evidence is which.
        for o in rows:
            o["run_mode"] = mode
        raw_obs.extend(rows)

    selected = evidence.select_eligible(conn, raw_obs)
    obs = selected.eligible

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
        # Compatibility key retained for callers written before the shared
        # selector distinguished every exclusion reason.
        "tier_c_excluded_rows": selected.counts.get("tier_c", 0),
        "evidence_exclusions": selected.counts,
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
    pool: str = "chain",
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

    `pool` is forwarded to `segment_report` when this call computes its
    own report (a `report` passed in was already built with whatever
    pool its caller chose, so `pool` is ignored then). `pool="version"`
    (default) is today's behaviour, unchanged. `pool="chain"` widens
    every segment — the aggregate, each slice's oos/in_sample, and the
    complement — the same way `segment_report(pool="chain")` does (spec
    2.5), and the returned dict gains `chain_versions` whenever the
    underlying report has it, whether the candidate ranked on a slice,
    the complement, or the aggregate — a pooled ranking input can never
    be read without seeing what was pooled into it.
    """
    if theory_id is None:
        theory_id = _field(row, "theory_id")
    if theory_version is None:
        theory_version = _field(row, "theory_version")
    if report is None:
        report = segment_report(
            conn, theory_id, theory_version,
            disposition=disposition, run_modes=run_modes, pool=pool,
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

    result = {
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
    if "chain_versions" in report:
        result["chain_versions"] = report["chain_versions"]
    return result
