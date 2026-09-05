"""The promotion key evaluator — what the user is told about, by rung.

The mechanism under test (tools/promotion.py, spec 2026-08-30-go-session-
structure-design.md §5–§6): every recorded candidate classifies onto a
named rung of docs/promotion-key.md, mechanically, from the same evidence
rows ranking already uses. Sessions cite rungs; they never decide
report-worthiness themselves. Fixtures mirror tests/test_slices.py: a
strong/moderate-NO slice inside a theory whose aggregate also holds
weak/YES rows.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools import db, ledger, promotion, score, slices, theories

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture()
def conn(conn):
    c = conn
    theories.register(c, "t", "T", "theories/t", status="testing")
    return c


def _record(
    c, ticker, *, outcome="no", confidence="strong", price=0.85,
    edge=4.0, day="2026-08-27", run_id="live", run_mode="live",
    disposition=None,
):
    ledger.record_opportunity(
        c, theory_id="t", theory_version=1, kalshi_ticker=ticker,
        outcome=outcome, entry_price=price, edge_pts_net=edge,
        edge_basis="model", run_mode=run_mode, run_id=run_id,
        decision_date=day, confidence=confidence, rationale="x",
    )
    opp_id = c.execute(
        "SELECT id FROM opportunities WHERE kalshi_ticker = ?", (ticker,)
    ).fetchone()["id"]
    if disposition in ("endorsed", "rejected"):
        ledger.interpret(c, opp_id, disposition, "test")
    return opp_id


def _settle(c, ticker, result, resolved="2026-09-01T00:00:00Z"):
    score.record_settlement(c, ticker, result, resolved_at=resolved)


def _evidence(
    c, *, n=12, days=6, win=True, outcome="no", confidence="strong",
    price=0.85, prefix="EV",
):
    """`n` settled positions spread over `days` distinct settlement days."""
    lose = "yes" if outcome == "no" else "no"
    for i in range(n):
        ticker = f"{prefix}{i}"
        _record(
            c, ticker, outcome=outcome, confidence=confidence, price=price,
        )
        _settle(
            c, ticker, outcome if win else lose,
            resolved=f"2026-09-{(i % days) + 1:02d}T00:00:00Z",
        )


# --- rungs from evidence ---------------------------------------------------


def test_measured_segment_recommends(conn):
    _evidence(conn)                       # 12 clusters, 6 days, winners
    opp = _record(conn, "OPEN1")
    result = promotion.promote(conn, opp)
    assert result.rung == "R1"
    assert result.quoted is False         # no market passed; must be flagged
    assert result.ranked_edge > 0
    assert result.rank_inputs["n"] >= 10


def test_a_recommendation_resting_on_replayed_history_says_so(conn):
    """Ruling 2026-08-31: backtested evidence promotes exactly as
    forward evidence does — and the user is told when it did."""
    score.record_backtest_run(conn, "bt-1", "t", 1, tier="A")
    for i in range(12):
        ticker = f"BT{i}"
        _record(conn, ticker, run_id="bt-1", run_mode="backtest")
        _settle(conn, ticker, "no",
                resolved=f"2026-06-{(i % 6) + 1:02d}T00:00:00Z")

    opp = _record(conn, "OPEN1")
    result = promotion.promote(conn, opp)

    assert result.rung == "R1", "a replayed edge promotes like any other"
    assert any("backtest" in r.lower() for r in result.reasons), (
        "the user must be told the evidence behind this is replayed"
    )


def test_a_recommendation_on_forward_evidence_makes_no_backtest_claim(conn):
    _evidence(conn)
    opp = _record(conn, "OPEN1")
    result = promotion.promote(conn, opp)
    assert result.rung == "R1"
    assert not any("backtest" in r.lower() for r in result.reasons)


def test_measured_against_suppresses_even_a_positive_claim(conn):
    _evidence(conn, win=False)            # measured and negative, past gates
    opp = _record(conn, "OPEN1", edge=6.0)
    result = promotion.promote(conn, opp)
    assert result.rung == "R5"


def test_below_gates_positive_is_provisional(conn):
    _evidence(conn, n=4, days=3)          # positive but 4 clusters / 3 days
    opp = _record(conn, "OPEN1")
    result = promotion.promote(conn, opp)
    assert result.rung == "R3"
    assert any("n_clusters" in r for r in result.reasons)


def test_under_three_settlement_days_is_not_a_measurement(conn):
    _evidence(conn, n=12, days=2)         # ruling 14: no usable error bar
    opp = _record(conn, "OPEN1")
    result = promotion.promote(conn, opp)
    assert result.rung == "R4"


def test_no_evidence_accrues(conn):
    opp = _record(conn, "OPEN1")
    result = promotion.promote(conn, opp)
    assert result.rung == "R4"


# --- the sub-theory rule ---------------------------------------------------


def test_ready_slice_promotes_while_complement_fails(conn):
    _evidence(conn, prefix="NO")                          # strong-NO winners
    _evidence(conn, prefix="YS", outcome="yes", confidence="weak",
              price=0.50, win=False)                      # weak-YES losers
    slices.register_slice(
        conn, "t", "strong-moderate-no",
        predicate={"outcome": ["no"], "confidence": ["strong", "moderate"]},
        hypothesis="optimism tax", origin="test",
        registered_at="2026-08-26T00:00:00Z",
    )
    in_slice = promotion.promote(conn, _record(conn, "OPEN1"))
    outside = promotion.promote(
        conn, _record(conn, "OPEN2", outcome="yes", confidence="weak",
                      price=0.50, edge=5.0))
    assert in_slice.rung == "R1"
    assert in_slice.segment == "slice:strong-moderate-no"
    assert outside.rung == "R5"
    assert outside.segment == "complement"


# --- rows that are never bets ----------------------------------------------


def test_rejected_rows_are_control(conn):
    opp = _record(conn, "OPEN1", disposition="rejected")
    assert promotion.promote(conn, opp).rung == "R6"


def test_observation_rows_never_promote(conn):
    _evidence(conn)
    opp = _record(conn, "OPEN1", edge=0.0)  # ruling 13: accrual, not a bet
    result = promotion.promote(conn, opp)
    assert result.rung == "R6"
    assert any("observation" in r for r in result.reasons)


def test_settled_rows_never_promote(conn):
    _evidence(conn)
    opp = _record(conn, "GONE")
    _settle(conn, "GONE", "no")
    result = promotion.promote(conn, opp)
    assert result.rung == "R6"
    assert any("settled" in r for r in result.reasons)


def _judgment_theory(conn):
    """Theory `t` as an LLM-judged theory with stage-2 provenance on file."""
    from tools import provenance

    theories.set_uses_llm_judgment(conn, "t", True)
    provenance.record_judgment_run(
        conn, run_id="live", theory_id="t", theory_version=1,
        stage="analysis", model="test-model", prompt_text="p",
    )


def test_judgment_theory_row_without_a_bucket_awaits_stage_two(conn):
    """The gate asks whether stage 2 ran, which is what a bucket records.

    A row carrying no confidence bucket never reached the judging stage,
    so nothing interpretable is being withheld -- it is waiting.
    """
    _judgment_theory(conn)
    _evidence(conn)
    opp = _record(conn, "OPEN1", confidence=None)       # stage 2 never ran
    result = promotion.promote(conn, opp)
    assert result.rung == "R4"
    assert any("stage 2" in r for r in result.reasons)


def test_judgment_theory_bucketed_row_is_not_held_at_the_gate(conn):
    """A bucket IS the interpretation; no endorsement is owed on top of it.

    Key v3 (2026-09-01): the gate reads the bucket, not the disposition,
    so a judged row falls through to its segment and is ranked on the
    evidence rather than held for a second model's approval.
    """
    _judgment_theory(conn)
    _evidence(conn)
    opp = _record(conn, "OPEN1")            # screened, bucket 'strong'
    result = promotion.promote(conn, opp)
    assert result.rung == "R1"


# --- riskless --------------------------------------------------------------


def test_riskless_basket(conn):
    ledger.record_basket(
        conn, theory_id="t", theory_version=1,
        legs=[
            {"kalshi_ticker": "L1", "outcome": "no", "entry_price": 0.45},
            {"kalshi_ticker": "L2", "outcome": "no", "entry_price": 0.50},
        ],
        edge_pts_net=4.0, min_payout=1.0, max_payout=2.0, fee_pts=1.0,
        edge_basis="model", run_id="live", rationale="arb",
    )
    opp = conn.execute(
        "SELECT id FROM opportunities WHERE position_kind = 'basket'"
    ).fetchone()["id"]
    assert promotion.promote(conn, opp).rung == "R2"


# --- today's ask and executability -----------------------------------------


def test_quote_kills_a_stale_edge(conn):
    _evidence(conn)
    opp = _record(conn, "OPEN1")            # NO at 0.85, claimed +4.0
    result = promotion.promote(
        conn, opp, market={"yes_bid": 0.05, "yes_ask": 0.10})
    assert result.quoted is True
    assert result.rung == "R4"              # NO now costs 0.95: edge gone
    assert result.claimed_edge_pts < 0


@pytest.mark.parametrize("first_price, latest_price", [(0.86, 0.81), (0.81, 0.86)])
def test_requote_uses_latest_attempt_price_with_its_edge(conn, first_price, latest_price):
    """A cheaper reobservation is not a second windfall on its new forecast."""
    _evidence(conn)
    opp = _record(conn, "RESEEN", price=first_price, edge=4.0,
                  day="2026-08-27", run_id="first")
    _record(conn, "RESEEN", price=latest_price, edge=0.75,
            day="2026-08-28", run_id="latest")
    result = promotion.promote(
        conn, opp, market={"yes_bid": 1 - latest_price,
                          "yes_ask": 1 - latest_price + 0.01})
    assert result.claimed_edge_pts == pytest.approx(0.75)
    assert result.rung == "R4"  # the real claim is inside the one-point spread
    assert ledger.get_opportunity(conn, opp)["entry_price"] == first_price


def test_older_attempt_ingested_later_does_not_replace_current_decision(conn):
    _evidence(conn)
    opp = _record(conn, "REORDERED", price=0.81, edge=0.75,
                  day="2026-08-28", run_id="latest")
    _record(conn, "REORDERED", price=0.86, edge=4.0,
            day="2026-08-27", run_id="older-recovered")
    result = promotion.promote(
        conn, opp, market={"yes_bid": 0.19, "yes_ask": 0.20})
    assert result.claimed_edge_pts == pytest.approx(0.75)
    assert result.rung == "R4"


@pytest.mark.parametrize("model_prob", [1.0019, float("inf"), -0.01])
def test_legacy_impossible_probability_cannot_be_recommended(conn, model_prob):
    _evidence(conn)
    opp, _ = ledger.record_opportunity(
        conn, theory_id="t", theory_version=1, kalshi_ticker="IMPOSSIBLE",
        outcome="no", entry_price=0.96, edge_pts_net=3.92,
        model_prob=model_prob, edge_basis="measured", confidence="strong",
    )
    result = promotion.promote(conn, opp,
                               market={"yes_bid": 0.04, "yes_ask": 0.05})
    assert result.rung == "R4"
    assert any("probability" in reason for reason in result.reasons)


def test_prior_claim_cannot_exceed_binary_payout_headroom(conn):
    _evidence(conn)
    opp = _record(conn, "IMPOSSIBLE-PRIOR", price=0.99, edge=4.0)
    result = promotion.promote(conn, opp)
    assert result.rung == "R4"
    assert any("payout" in reason for reason in result.reasons)


def test_spread_wider_than_edge_is_not_takeable(conn):
    _evidence(conn)
    opp = _record(conn, "OPEN1")
    result = promotion.promote(
        conn, opp, market={"yes_bid": 0.14, "yes_ask": 0.20})
    assert result.rung == "R4"              # ~3 pts edge inside a 6 pt spread
    assert any("spread" in r for r in result.reasons)


# --- orphaned evidence -----------------------------------------------------


def test_orphaned_evidence_surfaces_prior_version_slices(conn):
    _evidence(conn)
    slices.register_slice(
        conn, "t", "strong-moderate-no",
        predicate={"outcome": ["no"], "confidence": ["strong", "moderate"]},
        hypothesis="optimism tax", origin="test",
        registered_at="2026-08-26T00:00:00Z",
    )
    theories.bump_version(conn, "t", kind="breaking",
                          justification="new population")
    orphans = promotion.orphaned_evidence(conn, "t")
    assert [o["slug"] for o in orphans] == ["strong-moderate-no"]
    assert orphans[0]["ready_at_version"] == 1


def test_no_orphans_while_the_slice_is_ready_at_current_version(conn):
    _evidence(conn)
    slices.register_slice(
        conn, "t", "strong-moderate-no",
        predicate={"outcome": ["no"], "confidence": ["strong", "moderate"]},
        hypothesis="optimism tax", origin="test",
        registered_at="2026-08-26T00:00:00Z",
    )
    assert promotion.orphaned_evidence(conn, "t") == []


# --- batch and key ---------------------------------------------------------


def test_promote_run_reaches_resighted_positions(conn):
    """Keyed on attempts, not opportunities.run_id (the first-seer trap)."""
    _evidence(conn)
    opp = _record(conn, "OPEN1", run_id="live", day="2026-08-27")
    ledger.record_opportunity(
        conn, theory_id="t", theory_version=1, kalshi_ticker="OPEN1",
        outcome="no", entry_price=0.85, edge_pts_net=4.0,
        edge_basis="model", run_mode="live", run_id="live-2026-08-30",
        decision_date="2026-08-30", confidence="strong", rationale="x",
    )
    results = promotion.promote_run(conn, "live-2026-08-30")
    assert [r.opportunity_id for r in results] == [opp]


def test_cli_promote_emits_rung_and_key_version(tmp_path, capsys):
    import json as _json

    from tools import cli

    path = str(tmp_path / "t.db")
    c = db.connect(path)
    db.init_db(c)
    theories.register(c, "t", "T", "theories/t", status="testing")
    _evidence(c)
    opp = _record(c, "OPEN1")
    c.close()
    code = cli.main(["--db", path, "promote", str(opp), "--no-quote"])
    payload = _json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["key_version"] == promotion.KEY_VERSION
    assert payload["results"][0]["rung"] == "R1"
    assert payload["escalations"] == []


def test_cli_promote_run_batches_and_escalates(tmp_path, capsys):
    import json as _json

    from tools import cli

    path = str(tmp_path / "t.db")
    c = db.connect(path)
    db.init_db(c)
    theories.register(c, "t", "T", "theories/t", status="testing")
    _evidence(c)
    slices.register_slice(
        c, "t", "strong-moderate-no",
        predicate={"outcome": ["no"], "confidence": ["strong", "moderate"]},
        hypothesis="optimism tax", origin="test",
        registered_at="2026-08-26T00:00:00Z",
    )
    theories.bump_version(c, "t", kind="breaking",
                          justification="new population")
    c.close()
    code = cli.main(["--db", path, "promote", "--run", "live", "--no-quote"])
    payload = _json.loads(capsys.readouterr().out)
    assert code == 0
    assert len(payload["results"]) == 12          # every position live touched
    assert [o["slug"] for o in payload["escalations"]] == [
        "strong-moderate-no"
    ]


def test_key_version_matches_the_key_document():
    text = (REPO / "docs" / "promotion-key.md").read_text(encoding="utf-8")
    match = re.search(r"Key version:\s*(\d+)", text)
    assert match, "docs/promotion-key.md must declare 'Key version: <n>'"
    assert int(match.group(1)) == promotion.KEY_VERSION


def test_every_rung_in_the_key_document_exists_in_code():
    text = (REPO / "docs" / "promotion-key.md").read_text(encoding="utf-8")
    for rung, name in promotion.RUNGS.items():
        assert rung in text and name in text, (
            f"{rung} {name} missing from docs/promotion-key.md"
        )


# --- superseded positions (key v4) ------------------------------------------
#
# Incident 2026-09-01: opportunity 13663 (insider_judgment v4,
# KXPRESSSECANNOUNCE-26AUG-SEP08 NO, endorsed, edge_basis='prior' +2.0)
# returned R1 RECOMMENDED while the SAME market, re-judged that hour at v6
# with fresh research, recorded as 109994 -- `weak`, edge_basis='measured',
# -1.02 -- and returned R6. Two live rows on one market, promoting R1 and R6
# at once, and the R1 was the stale one.
#
# The position rollup keys on (theory_id, theory_version, ...), so a version
# bump does not supersede a position, it FORKS it. The old row stops
# receiving attempts and freezes at its last interpretation, and promote's
# staleness checks were all about PRICE, never about whether the
# interpretation behind the row is still the current procedure's. It also
# preferentially preserves ENDORSEMENTS: v5 deleted the only path to
# disposition='endorsed', so every endorsed row is stranded at v4 or
# earlier -- exactly the rows most likely to clear R1.


def _record_at(
    c, ticker, *, version, outcome="no", confidence="strong", price=0.85,
    edge=4.0, run_mode="live", run_id="live", disposition=None,
):
    """Record one row at an explicit theory version."""
    ledger.record_opportunity(
        c, theory_id="t", theory_version=version, kalshi_ticker=ticker,
        outcome=outcome, entry_price=price, edge_pts_net=edge,
        edge_basis="model", run_mode=run_mode, run_id=run_id,
        decision_date="2026-08-27", confidence=confidence, rationale="x",
    )
    return c.execute(
        "SELECT id FROM opportunities WHERE kalshi_ticker = ? AND "
        "theory_version = ? AND run_mode = ?",
        (ticker, version, run_mode),
    ).fetchone()["id"]


def test_superseded_row_at_an_old_version_is_not_recommended(conn):
    """The 13663/109994 shape: the stale fork must not outrank its successor.

    Without this, the stale row promotes R1 forever -- it never settles
    while the market is open, nothing ages it out, and every further
    version bump strands another one behind it.
    """
    _evidence(conn)                       # segment past its gates, positive
    stale = _record_at(conn, "FORK", version=1, edge=4.0)
    theories.bump_version(conn, "t", kind="continues",
                          justification="re-decided the population")
    fresh = _record_at(conn, "FORK", version=2, edge=4.0)

    p = promotion.promote(conn, stale)
    assert p.rung == "R6", f"stale fork promoted {p.rung}"
    assert any(str(fresh) in r for r in p.reasons), p.reasons
    assert any("supersede" in r.lower() for r in p.reasons), p.reasons

    # the successor is the row that carries the decision
    assert promotion.promote(conn, fresh).rung == "R1"


def test_old_version_row_without_a_successor_is_still_promotable(conn):
    """Fix (a), not the blunter fix (b) the ticket warned against.

    Suppressing every row merely behind the registry's current version
    would silently bin candidates whose market simply was not screened
    today -- a market that stopped qualifying, or a run that did not
    reach it. Only a REAL replacement supersedes.
    """
    _evidence(conn)
    old = _record_at(conn, "LONELY", version=1, edge=4.0)
    theories.bump_version(conn, "t", kind="continues",
                          justification="re-decided the population")

    assert promotion.promote(conn, old).rung == "R1"


def test_a_backtest_row_never_supersedes_a_live_position(conn):
    """A replay is not a decision about today's market.

    Positions are identified by (theory, version, run_mode, lane, ticker,
    outcome). A tier A/B replay row landing at the current version says
    nothing about whether the live position is still the procedure's
    answer, so it must not suppress one.
    """
    _evidence(conn)
    live_old = _record_at(conn, "REPLAY", version=1, edge=4.0)
    theories.bump_version(conn, "t", kind="continues",
                          justification="re-decided the population")
    _record_at(conn, "REPLAY", version=2, run_mode="backtest",
               run_id="bt/2026-09-01", edge=4.0)

    assert promotion.promote(conn, live_old).rung == "R1"


def test_supersession_is_per_outcome_side(conn):
    """A fresh YES row does not supersede a live NO position on the
    same ticker -- they are different positions, not two views of one."""
    _evidence(conn)
    no_old = _record_at(conn, "SIDES", version=1, outcome="no", edge=4.0)
    theories.bump_version(conn, "t", kind="continues",
                          justification="re-decided the population")
    _record_at(conn, "SIDES", version=2, outcome="yes", edge=4.0)

    assert promotion.promote(conn, no_old).rung == "R1"
