import sqlite3

import pytest

from tools import db, ledger, score, theories
from tools.sizing import fee_pts

TS = "2026-08-23T12:00:00Z"
LATER = "2026-08-24T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_opportunities_has_the_basket_columns(conn):
    cols = _columns(conn, "opportunities")
    assert {"position_kind", "leg_count", "max_payout"} <= cols


def test_opportunity_legs_table_exists(conn):
    cols = _columns(conn, "opportunity_legs")
    assert cols == {
        "opportunity_id", "leg_index", "kalshi_ticker", "outcome",
        "entry_price", "spread_at_call", "volume_at_call",
    }


def test_existing_single_leg_row_defaults_are_correct(conn):
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXTEST-26",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, now=TS,
    )
    row = ledger.get_opportunity(conn, opp_id)
    assert row["position_kind"] == "single"
    assert row["leg_count"] == 1
    assert row["max_payout"] == pytest.approx(1.0)


def test_position_kind_rejects_an_unknown_value(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO opportunities (theory_id, theory_version, run_mode,"
            " run_id, kalshi_ticker, outcome, entry_price,"
            " screen_edge_pts_net, edge_pts_net, position_kind,"
            " first_seen_at, last_seen_at)"
            " VALUES ('t1', 1, 'live', 'live', 'X', 'yes', 0.4, 1.0, 1.0,"
            " 'combo', ?, ?)",
            (TS, TS),
        )


def test_basket_key_is_stable_across_leg_order():
    a = [{"kalshi_ticker": "AAA", "outcome": "yes"},
         {"kalshi_ticker": "BBB", "outcome": "no"}]
    b = list(reversed(a))
    assert ledger.basket_key(a) == ledger.basket_key(b)


def test_basket_key_normalizes_case():
    a = [{"kalshi_ticker": "aaa", "outcome": "YES"}]
    b = [{"kalshi_ticker": "AAA", "outcome": "yes"}]
    assert ledger.basket_key(a) == ledger.basket_key(b)


def test_basket_key_differs_on_different_legs():
    a = [{"kalshi_ticker": "AAA", "outcome": "yes"}]
    b = [{"kalshi_ticker": "AAA", "outcome": "no"}]
    assert ledger.basket_key(a) != ledger.basket_key(b)


def test_basket_key_shape():
    key = ledger.basket_key([{"kalshi_ticker": "AAA", "outcome": "yes"}])
    assert key.startswith("BASKET:")
    assert len(key) == len("BASKET:") + 16


def test_basket_key_raises_on_missing_ticker():
    with pytest.raises(ValueError, match="leg 0.*kalshi_ticker.*required"):
        ledger.basket_key([{"kalshi_ticker": None, "outcome": "yes"}])


def test_basket_key_raises_on_missing_outcome():
    with pytest.raises(ValueError, match="leg 0.*outcome.*required"):
        ledger.basket_key([{"kalshi_ticker": "AAA", "outcome": None}])


def test_basket_key_prevents_delimiter_collision():
    # Without escaping, these two would produce the same hash with string joining.
    # With json.dumps(), they must be different.
    a = [{"kalshi_ticker": "123", "outcome": "yes"},
         {"kalshi_ticker": "456", "outcome": "no"}]
    b = [{"kalshi_ticker": "123", "outcome": "yes|456:no"}]
    assert ledger.basket_key(a) != ledger.basket_key(b)


def _legs():
    return [
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.40},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.55},
    ]


def _basket(conn, **overrides):
    kwargs = dict(
        theory_id="t1", theory_version=1, legs=_legs(),
        edge_pts_net=5.0, edge_basis="model", now=TS,
    )
    kwargs.update(overrides)
    return ledger.record_basket(conn, **kwargs)


def test_basket_writes_one_header_and_n_leg_rows(conn):
    opp_id, created = _basket(conn)
    assert created is True
    row = ledger.get_opportunity(conn, opp_id)
    assert row["position_kind"] == "basket"
    assert row["leg_count"] == 2
    assert row["outcome"] == "basket"
    assert row["kalshi_ticker"].startswith("BASKET:")
    assert len(ledger.get_legs(conn, opp_id)) == 2


def test_basket_entry_price_is_the_summed_cost(conn):
    opp_id, _ = _basket(conn)
    row = ledger.get_opportunity(conn, opp_id)
    assert row["entry_price"] == pytest.approx(0.95)


def test_basket_legs_are_normalized_and_ordered(conn):
    opp_id, _ = _basket(conn, legs=[
        {"kalshi_ticker": " kxa-26 ", "outcome": "YES", "entry_price": 0.40},
        {"kalshi_ticker": "KXB-26", "outcome": " No ", "entry_price": 0.55},
    ])
    legs = ledger.get_legs(conn, opp_id)
    assert [l["leg_index"] for l in legs] == [0, 1]
    assert legs[0]["kalshi_ticker"] == "KXA-26"
    assert legs[0]["outcome"] == "yes"
    assert legs[1]["outcome"] == "no"


def test_resighting_a_basket_updates_rather_than_inserts(conn):
    first, created_a = _basket(conn)
    second, created_b = _basket(conn, now=LATER, edge_pts_net=7.0)
    assert created_a is True and created_b is False
    assert first == second
    row = ledger.get_opportunity(conn, first)
    assert row["times_seen"] == 2
    assert row["last_seen_at"] == LATER
    assert len(ledger.get_legs(conn, first)) == 2


def test_resighting_with_reordered_legs_is_the_same_basket(conn):
    first, _ = _basket(conn)
    second, created = _basket(conn, legs=list(reversed(_legs())), now=LATER)
    assert created is False
    assert first == second


def test_resighting_freezes_entry_price_on_header_and_legs(conn):
    """A re-sighting at new prices must not let the ledger's own header
    row and its legs drift onto different vintages of the same bet."""
    first, _ = _basket(conn)
    second, created = _basket(conn, now=LATER, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.10},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.15},
    ])
    assert created is False
    assert first == second

    row = ledger.get_opportunity(conn, first)
    assert row["entry_price"] == pytest.approx(0.95)

    legs = ledger.get_legs(conn, first)
    assert legs[0]["entry_price"] == pytest.approx(0.40)
    assert legs[1]["entry_price"] == pytest.approx(0.55)


def test_resighting_refreshes_leg_quote_fields(conn):
    opp_id, _ = _basket(conn, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.40,
         "spread_at_call": 0.02, "volume_at_call": 100},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.55,
         "spread_at_call": 0.03, "volume_at_call": 200},
    ])
    _basket(conn, now=LATER, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.10,
         "spread_at_call": 0.09, "volume_at_call": 900},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.15,
         "spread_at_call": 0.08, "volume_at_call": 800},
    ])
    legs = ledger.get_legs(conn, opp_id)
    assert legs[0]["spread_at_call"] == pytest.approx(0.09)
    assert legs[0]["volume_at_call"] == pytest.approx(900)
    assert legs[1]["spread_at_call"] == pytest.approx(0.08)
    assert legs[1]["volume_at_call"] == pytest.approx(800)
    # entry_price stays frozen even while the quote fields refresh.
    assert legs[0]["entry_price"] == pytest.approx(0.40)
    assert legs[1]["entry_price"] == pytest.approx(0.55)


def test_resighting_keeps_header_cost_consistent_with_legs(conn):
    """The invariant the bug broke: header entry_price (the summed cost at
    first sighting) must still equal sum(leg entry_price) after a
    re-sighting at different prices, not a mix of first- and latest-seen
    values."""
    opp_id, _ = _basket(conn)
    _basket(conn, now=LATER, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.10},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.15},
    ])
    row = ledger.get_opportunity(conn, opp_id)
    legs = ledger.get_legs(conn, opp_id)
    assert row["entry_price"] == pytest.approx(
        sum(l["entry_price"] for l in legs)
    )


def test_basket_cost_above_one_is_allowed_when_payout_allows_it(conn):
    opp_id, _ = _basket(conn, max_payout=2.0, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "no", "entry_price": 0.80},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.85},
    ])
    assert ledger.get_opportunity(conn, opp_id)["entry_price"] == pytest.approx(1.65)


def test_basket_cost_above_max_payout_is_refused(conn):
    with pytest.raises(ValueError, match="exceeds max_payout"):
        _basket(conn, max_payout=1.0, legs=[
            {"kalshi_ticker": "KXA-26", "outcome": "no", "entry_price": 0.80},
            {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.85},
        ])


def test_basket_cost_equal_to_max_payout_is_refused_and_says_so(conn):
    """Break-even is refused, and the message does not claim "exceeds".

    0.1 + 0.2 is 0.30000000000000004, so a cost that is exactly max_payout
    compares as greater and used to report the self-contradicting "basket
    cost 0.3000 exceeds max_payout 0.3000". The refusal is correct -- a
    basket whose best branch returns what it cost cannot profit, and fees
    make it a loss -- but the reason has to be stated truthfully.
    """
    with pytest.raises(ValueError, match="equals max_payout") as excinfo:
        _basket(conn, max_payout=0.3, legs=[
            {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.1},
            {"kalshi_ticker": "KXB-26", "outcome": "yes", "entry_price": 0.2},
        ])
    assert "exceeds" not in str(excinfo.value)


def test_basket_refuses_empty_legs(conn):
    with pytest.raises(ValueError, match="at least one leg"):
        _basket(conn, legs=[])


def test_basket_refuses_a_leg_with_no_ticker(conn):
    with pytest.raises(ValueError, match="kalshi_ticker"):
        _basket(conn, legs=[
            {"kalshi_ticker": "", "outcome": "yes", "entry_price": 0.40},
        ])


def test_basket_refuses_a_leg_with_no_outcome(conn):
    with pytest.raises(ValueError, match="outcome"):
        _basket(conn, legs=[
            {"kalshi_ticker": "KXA-26", "outcome": "", "entry_price": 0.40},
        ])


def test_basket_refuses_a_leg_price_in_cents(conn):
    with pytest.raises(ValueError, match="decimal dollars"):
        _basket(conn, legs=[
            {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 40},
        ])


def test_basket_write_is_atomic_on_leg_insert_failure(tmp_path):
    """A failure after the header write must not leave a headless row.

    The header INSERT and the leg INSERTs share one `write(conn)` block, so
    sqlite's implicit transaction has not been committed when the leg insert
    raises -- `write`'s rollback must undo the header write too, not just
    leave the legs missing. `sqlite3.Connection.executemany` cannot be
    monkeypatched directly (it is a read-only C-level attribute), so this
    forces the failure through a Connection subclass instead.
    """

    class BoomConnection(sqlite3.Connection):
        def executemany(self, sql, params=()):
            if "INSERT INTO opportunity_legs" in sql:
                raise sqlite3.IntegrityError("forced failure for atomicity test")
            return super().executemany(sql, params)

    path = tmp_path / "atomic.db"
    setup = db.connect(path)
    db.init_db(setup)
    theories.register(setup, "t1", "Theory One", "theories/t1", now=TS)
    setup.close()

    boom_conn = sqlite3.connect(str(path), timeout=30.0, factory=BoomConnection)
    boom_conn.row_factory = sqlite3.Row
    boom_conn.execute("PRAGMA foreign_keys = ON")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            _basket(boom_conn)

        assert boom_conn.execute(
            "SELECT COUNT(*) FROM opportunities"
        ).fetchone()[0] == 0
        assert boom_conn.execute(
            "SELECT COUNT(*) FROM opportunity_legs"
        ).fetchone()[0] == 0
    finally:
        boom_conn.close()


def _settle(conn, pairs):
    for ticker, result in pairs:
        score.record_settlement(conn, ticker, result, resolved_at=TS)


def test_basket_with_an_unsettled_leg_is_excluded(conn):
    _basket(conn)
    _settle(conn, [("KXA-26", "yes")])
    assert score.compute_score(conn, "t1", 1)["n"] == 0


def test_fully_settled_basket_counts_once(conn):
    _basket(conn)
    _settle(conn, [("KXA-26", "yes"), ("KXB-26", "yes")])
    assert score.compute_score(conn, "t1", 1)["n"] == 1


def test_profitable_basket_scores_as_a_win(conn):
    # legs cost 0.95; KXA yes wins ($1), KXB no loses ($0). Payout 1.00.
    _basket(conn)
    _settle(conn, [("KXA-26", "yes"), ("KXB-26", "yes")])
    r = score.compute_score(conn, "t1", 1)
    assert r["win_rate"] == pytest.approx(1.0)
    cost = 0.95 + (fee_pts(0.40) + fee_pts(0.55)) / 100.0
    assert r["roi_all"] == pytest.approx((1.0 - cost) / cost)


def test_losing_basket_scores_as_a_loss(conn):
    # Both legs lose: KXA settles no (we hold yes), KXB settles yes (we hold no).
    _basket(conn)
    _settle(conn, [("KXA-26", "no"), ("KXB-26", "yes")])
    r = score.compute_score(conn, "t1", 1)
    assert r["win_rate"] == pytest.approx(0.0)
    assert r["roi_all"] < 0


def test_basket_implied_rate_is_normalized_by_max_payout(conn):
    _basket(conn, max_payout=2.0, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "no", "entry_price": 0.80},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.85},
    ])
    _settle(conn, [("KXA-26", "no"), ("KXB-26", "no")])
    r = score.compute_score(conn, "t1", 1)
    assert r["price_implied_rate"] == pytest.approx(1.65 / 2.0)


def test_baskets_and_singles_pool_into_one_score(conn):
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXS-26",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS,
    )
    _basket(conn)
    _settle(conn, [("KXS-26", "yes"), ("KXA-26", "yes"), ("KXB-26", "yes")])
    assert score.compute_score(conn, "t1", 1)["n"] == 2


def test_a_basket_missing_a_leg_row_raises_rather_than_scoring(conn):
    opp_id, _ = _basket(conn)
    conn.execute(
        "DELETE FROM opportunity_legs WHERE opportunity_id = ? AND leg_index = 1",
        (opp_id,),
    )
    conn.commit()
    _settle(conn, [("KXA-26", "yes"), ("KXB-26", "yes")])
    with pytest.raises(ValueError, match="leg_count"):
        score.compute_score(conn, "t1", 1)


def test_basket_mean_fee_pts_is_normalized_by_max_payout(conn):
    # Fee review fix 1: fee_pts must live on the same /max_payout scale as
    # implied_rate, or calibration_edge_net mixes units. Hand-derived, in
    # the style of tests/test_score_characterization.py, rather than
    # restated from the implementation.
    _basket(conn, max_payout=2.0, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "no", "entry_price": 0.80},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.85},
    ])
    _settle(conn, [("KXA-26", "no"), ("KXB-26", "no")])
    r = score.compute_score(conn, "t1", 1)
    expected_mean_fee = (fee_pts(0.80) + fee_pts(0.85)) / 2.0
    assert r["mean_fee_pts"] == pytest.approx(expected_mean_fee)


def test_basket_three_leg_fee_accumulation(conn):
    # Fee review fix 3: fee accumulation must use an explicit += loop, not
    # sum(), matching _aggregate's contract. Two-leg baskets can't tell
    # naive and compensated summation apart; three legs can.
    _basket(conn, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.20},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.30},
        {"kalshi_ticker": "KXC-26", "outcome": "yes", "entry_price": 0.15},
    ])
    # Exactly one leg wins, so payout is 1.00 = the default max_payout: with
    # three legs any other settlement pattern lands strictly between 0 and
    # max_payout, which scoring now refuses (see the payout-floor tests
    # below). The fee arithmetic under test does not depend on which legs
    # won -- fees are paid on entry either way.
    _settle(conn, [
        ("KXA-26", "yes"), ("KXB-26", "yes"), ("KXC-26", "no"),
    ])
    r = score.compute_score(conn, "t1", 1)
    expected_mean_fee = fee_pts(0.20) + fee_pts(0.30) + fee_pts(0.15)
    assert r["mean_fee_pts"] == pytest.approx(expected_mean_fee)


def test_record_basket_rejects_zero_max_payout(conn):
    with pytest.raises(ValueError, match="max_payout"):
        _basket(conn, max_payout=0.0)


def test_record_basket_rejects_negative_max_payout(conn):
    with pytest.raises(ValueError, match="max_payout"):
        _basket(conn, max_payout=-1.0)


def test_record_basket_rejects_none_max_payout(conn):
    with pytest.raises(ValueError, match="max_payout"):
        _basket(conn, max_payout=None)


def _calendar_arb_basket(conn):
    """The calendar-arb nesting position: buy YES on the later deadline,
    buy NO on the earlier one. Cost 0.95 against a $2 joint maximum."""
    return ledger.record_basket(
        conn, theory_id="t1", theory_version=1, edge_pts_net=4.0,
        edge_basis="model", now=TS, max_payout=2.0,
        legs=[
            {"kalshi_ticker": "KXLATE-26", "outcome": "yes",
             "entry_price": 0.60},
            {"kalshi_ticker": "KXEARLY-26", "outcome": "no",
             "entry_price": 0.35},
        ],
    )


def test_nesting_branch_where_both_legs_win_pays_the_full_max_payout(conn):
    """The calendar-arb payoff matrix, branch 1 of 3: the event happens
    between the two deadlines, so NO-early and YES-late both win.

    Payout is exactly max_payout, which is the all-or-nothing case scoring
    supports, so this branch scores. Under nesting (early YES implies late
    YES) the fourth cell of the matrix, (early=yes, late=no), is impossible
    and is therefore absent here rather than expected to fail.
    """
    _calendar_arb_basket(conn)
    _settle(conn, [("KXEARLY-26", "no"), ("KXLATE-26", "yes")])

    obs = score._basket_observations(conn, "t1", 1, "live", "all", None)
    assert len(obs) == 1
    assert obs[0]["payout"] == pytest.approx(2.0)


@pytest.mark.parametrize(
    "early_result,late_result",
    [
        ("no", "no"),    # event never happens: NO-early wins, YES-late loses
        ("yes", "yes"),  # happens before the early deadline: YES-late wins
    ],
)
def test_nesting_branch_with_a_payout_floor_is_unsupported_and_raises(
    conn, early_result, late_result
):
    """The calendar-arb payoff matrix, branches 2 and 3 of 3 -- and the
    reason this feature does not yet support its own motivating example.

    Exactly one leg wins in each of these branches, so the basket pays $1
    against a declared max_payout of $2: strictly between, which is the
    payout-floor case scoring refuses. This documents an UNSUPPORTED case
    awaiting a scoring-model decision, not a passing feature. Calibration
    prices a basket as all-or-nothing (implied_rate = cost / max_payout),
    so a $1 payout here would be scored against a rate that describes a $2
    one, inflating calibration_edge_net by roughly an order of magnitude.
    Raising is the honest behavior until the spec says how a variable
    payout should be scored; when it does, this test becomes the assertion
    of whatever it decides.
    """
    _calendar_arb_basket(conn)
    _settle(conn, [("KXEARLY-26", early_result), ("KXLATE-26", late_result)])

    with pytest.raises(ValueError) as excinfo:
        score._basket_observations(conn, "t1", 1, "live", "all", None)

    # Assert the payout VALUE, not merely that it raised. Both floor
    # branches pay exactly $1 against the declared $2, and a regression that
    # changed the payout while still raising would otherwise pass here --
    # which would hollow out the audit this test exists to be.
    message = str(excinfo.value)
    assert "1.0000" in message and "2.0000" in message


def test_payout_floor_error_names_the_numbers_and_the_spec(conn):
    """The refusal has to be actionable: it names the position, both
    payout figures, and where the undecided design question lives."""
    opp_id, _ = _calendar_arb_basket(conn)
    _settle(conn, [("KXEARLY-26", "no"), ("KXLATE-26", "no")])

    with pytest.raises(ValueError) as excinfo:
        score.compute_score(conn, "t1", 1)
    message = str(excinfo.value)
    assert f"opportunity {opp_id}" in message
    assert "1.0000" in message and "2.0000" in message
    assert "all-or-nothing" in message
    assert "2026-08-24-multi-leg-positions-design.md" in message


def test_a_basket_that_would_have_lost_is_visible_as_a_loss(conn):
    """The classifier-bug detector: a mis-classified pair scores negative."""
    ledger.record_basket(
        conn, theory_id="t1", theory_version=1, edge_pts_net=4.0,
        edge_basis="model", now=TS,
        legs=[
            {"kalshi_ticker": "KXP-26", "outcome": "yes", "entry_price": 0.60},
            {"kalshi_ticker": "KXQ-26", "outcome": "yes", "entry_price": 0.35},
        ],
    )
    # Both legs lose -- no nesting relationship held.
    _settle(conn, [("KXP-26", "no"), ("KXQ-26", "no")])
    r = score.compute_score(conn, "t1", 1)
    assert r["n"] == 1
    assert r["win_rate"] == pytest.approx(0.0)
    assert r["roi_all"] == pytest.approx(-1.0)


def test_basket_refuses_duplicate_legs(conn):
    """The same contract and side twice is a size-2 position, which the
    ledger does not represent -- and it would pay double the declared
    maximum while `basket_key` collapsed the pair into one hash."""
    with pytest.raises(ValueError, match="duplicates"):
        _basket(conn, legs=[
            {"kalshi_ticker": "KXD-26", "outcome": "yes", "entry_price": 0.20},
            {"kalshi_ticker": "KXD-26", "outcome": "yes", "entry_price": 0.20},
        ])


def test_basket_refuses_duplicate_legs_after_normalization(conn):
    """Casing and whitespace are normalized before the duplicate test, so
    "kxd-26"/"YES" and "KXD-26 "/"yes" are the same leg."""
    with pytest.raises(ValueError, match="duplicates"):
        _basket(conn, legs=[
            {"kalshi_ticker": "kxd-26", "outcome": "YES",
             "entry_price": 0.20},
            {"kalshi_ticker": "KXD-26 ", "outcome": " yes ",
             "entry_price": 0.20},
        ])


def test_basket_allows_the_same_ticker_on_opposite_sides(conn):
    """Only (ticker, outcome) pairs must be distinct: YES and NO on one
    market are two different contracts and a legitimate basket."""
    opp_id, _ = _basket(conn, legs=[
        {"kalshi_ticker": "KXD-26", "outcome": "yes", "entry_price": 0.40},
        {"kalshi_ticker": "KXD-26", "outcome": "no", "entry_price": 0.55},
    ])
    assert len(ledger.get_legs(conn, opp_id)) == 2


def test_payout_above_max_payout_raises_rather_than_scoring(conn):
    """The other half of the duplicate-leg guard: if a payout ever exceeds
    the declared maximum, the declaration was wrong and scoring must say
    so rather than book an impossible return."""
    _basket(conn, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.20},
        {"kalshi_ticker": "KXB-26", "outcome": "yes", "entry_price": 0.20},
        {"kalshi_ticker": "KXC-26", "outcome": "no", "entry_price": 0.15},
    ])
    # Two legs win against max_payout = 1.0.
    _settle(conn, [("KXA-26", "yes"), ("KXB-26", "yes"), ("KXC-26", "yes")])
    with pytest.raises(ValueError, match="max_payout"):
        score.compute_score(conn, "t1", 1)


def test_fully_settled_basket_is_not_unsettled(conn):
    """The bug that made settlement unreachable: the header's synthetic
    BASKET: ticker never appears in `settlements`, so testing it reported
    even a resolved basket as unsettled forever."""
    _basket(conn)
    _settle(conn, [("KXA-26", "yes"), ("KXB-26", "yes")])
    assert ledger.list_opportunities(conn, unsettled_only=True) == []


def test_basket_with_one_leg_settled_is_still_unsettled(conn):
    _basket(conn)
    _settle(conn, [("KXA-26", "yes")])
    rows = ledger.list_opportunities(conn, unsettled_only=True)
    assert [r["position_kind"] for r in rows] == ["basket"]


def test_basket_missing_its_leg_rows_stays_unsettled(conn):
    """A corrupt basket must surface in the queue rather than vanish from
    it: `leg_count` is the authority on how many settlements it needs."""
    opp_id, _ = _basket(conn)
    conn.execute(
        "DELETE FROM opportunity_legs WHERE opportunity_id = ?", (opp_id,)
    )
    conn.commit()
    _settle(conn, [("KXA-26", "yes"), ("KXB-26", "yes")])
    assert len(ledger.list_opportunities(conn, unsettled_only=True)) == 1


def test_tickers_awaiting_settlement_returns_legs_not_the_header(conn):
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXS-26",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS,
    )
    _basket(conn)
    assert ledger.tickers_awaiting_settlement(conn) == [
        "KXA-26", "KXB-26", "KXS-26"
    ]


def test_tickers_awaiting_settlement_drops_what_has_settled(conn):
    _basket(conn)
    _settle(conn, [("KXA-26", "yes")])
    assert ledger.tickers_awaiting_settlement(conn) == ["KXB-26"]
    _settle(conn, [("KXB-26", "yes")])
    assert ledger.tickers_awaiting_settlement(conn) == []


def test_tickers_awaiting_settlement_never_returns_a_synthetic_ticker(conn):
    _basket(conn)
    tickers = ledger.tickers_awaiting_settlement(conn)
    assert tickers
    assert not any(t.startswith(ledger.BASKET_PREFIX) for t in tickers)


def test_tickers_awaiting_settlement_honours_the_segment_filters(conn):
    theories.register(conn, "t2", "Theory Two", "theories/t2", now=TS)
    _basket(conn)
    _basket(conn, theory_id="t2", legs=[
        {"kalshi_ticker": "KXZ-26", "outcome": "yes", "entry_price": 0.40},
        {"kalshi_ticker": "KXY-26", "outcome": "no", "entry_price": 0.55},
    ])
    assert ledger.tickers_awaiting_settlement(conn, theory_id="t1") == [
        "KXA-26", "KXB-26"
    ]
    assert ledger.tickers_awaiting_settlement(conn, theory_id="t2") == [
        "KXY-26", "KXZ-26"
    ]
