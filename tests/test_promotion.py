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
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
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


def test_judgment_theory_screened_row_awaits_endorsement(conn):
    from tools import provenance

    theories.set_uses_llm_judgment(conn, "t", True)
    provenance.record_judgment_run(
        conn, run_id="live", theory_id="t", theory_version=1,
        stage="analysis", model="test-model", prompt_text="p",
    )
    _evidence(conn)
    opp = _record(conn, "OPEN1")            # screened, never interpreted
    result = promotion.promote(conn, opp)
    assert result.rung == "R4"
    assert any("endorse" in r for r in result.reasons)


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
    theories.bump_version(conn, "t", justification="test bump")
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
    theories.bump_version(c, "t", justification="test bump")
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
