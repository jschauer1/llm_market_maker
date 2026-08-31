from datetime import datetime, timezone

import pytest

from tests.characterization import conftest as cz
from theories.insider_bias.mention_family import mention_bucket
from tools import db, theories
from tools.domain import Market
from tools.theory import TheoryContext

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
TS = "2026-08-24T12:00:00Z"


def _theory():
    from theories.insider_bias.mention_family import THEORY
    return THEORY


@pytest.fixture
def frozen_rates(monkeypatch):
    monkeypatch.setattr(mention_bucket, "measured_rate",
                        lambda conn: cz.frozen_rates())
    return cz.frozen_rates()


def _synthetic_board() -> list[Market]:
    """Three mention-family markets, one per PRICE_BINS bucket, built to
    clear screen.screen() inside the validated 14-day window against NOW.

    The committed fixture board (cz.board_input()) legitimately produces
    ZERO live mention_family candidates on the validated horizon --
    confirmed by tests/characterization/goldens/mention_rank.json and
    mention_find_candidates.json both being `[]`. A test built only from
    that fixture cannot fail if _to_candidate, _rationale, or Edge
    construction breaks: an empty list trivially equals an empty golden,
    and record()/finish() have nothing to write. This hand-built board
    exists so the adapter's per-candidate conversion is actually exercised
    (see tests/characterization/build_fixture.py's docstring on why an
    empty candidate set locks nothing).

    Built as domain.Market objects, not raw dicts: screen.screen() and
    find_candidates() read a market by attribute (`market.mid`,
    `market.ticker`, `market.spread`, ...), the same access pattern
    tools.board.get_board() hands back in production. A plain dict would
    not satisfy that access pattern at all, so a real Market instance --
    built with every field screen.screen() and the price-bin bucketing
    touch -- is the only fixture shape this path accepts.
    """
    def m(ticker: str, yes_ask: float) -> Market:
        return Market(
            platform="kalshi", ticker=ticker, title=f"title for {ticker}",
            yes_bid=round(yes_ask - 0.02, 2), yes_ask=yes_ask,
            no_bid=round(1 - yes_ask - 0.02, 2), no_ask=round(1 - yes_ask, 2),
            mid=round(yes_ask - 0.01, 2), spread=0.02, volume=5000.0,
            is_open=True, close_time="2026-08-30T00:00:00Z",
            status="active", event_ticker=f"KXTRUMPMENTION-{ticker[-1]}",
            series_ticker="KXTRUMPMENTION", rules_primary="rules text",
            raw={"ticker": ticker},
        )

    return [
        m("KXTRUMPMENTION-1", 0.70),   # -> mention_family_lt75
        m("KXTRUMPMENTION-2", 0.80),   # -> mention_family_75_85
        m("KXTRUMPMENTION-3", 0.90),   # -> mention_family_85plus
    ]


def test_price_matches_the_dict_path_rank_on_a_synthetic_board(frozen_rates):
    """Not a golden comparison: the golden fixture board has zero live
    mention_family candidates on the validated horizon (see
    _synthetic_board's docstring), which would make this assertion pass
    vacuously against an empty list regardless of whether the adapter is
    correct. This board is built to have real hits in all three price
    bins instead, and is cross-checked against mention_bucket.rank called
    directly on the same board -- a genuine equivalence, not an empty-list
    coincidence.
    """
    board = _synthetic_board()
    ctx = TheoryContext(conn=None, board=board, now=NOW)
    result = _theory().start(ctx).finish(dry_run=True)
    assert result.judged is False
    assert len(result.scored) == 3
    assert {s.confidence for s in result.scored} == {
        "mention_family_lt75", "mention_family_75_85",
        "mention_family_85plus",
    }
    assert all(s.confidence for s in result.scored)
    assert all(s.edge.basis == "measured" for s in result.scored)

    want = mention_bucket.rank(
        mention_bucket.find_candidates(board, now=NOW), frozen_rates)
    assert len(want) == 3
    assert cz.proj(list(result.scored)) == cz.proj(want)


def _seed(conn):
    theories.register(conn, "mention_family", "Mention Family",
                      "theories/insider_bias/mention_family", now=TS)
    with db.write(conn):
        conn.execute("UPDATE theories SET status='testing'"
                     " WHERE id='mention_family'")


def test_finish_writes_the_same_rows_record_would(tmp_path, frozen_rates):
    board = _synthetic_board()
    ranked = mention_bucket.rank(
        mention_bucket.find_candidates(board, now=NOW), frozen_rates)
    # Locks the test itself, not just the adapter: if the board stops
    # clearing screen.screen() the rows-compared-below assertion would
    # pass vacuously on two empty tables, exactly the failure mode this
    # rewrite exists to close off.
    assert len(ranked) == 3

    via_record = db.connect(tmp_path / "a.db"); db.init_db(via_record)
    _seed(via_record)
    mention_bucket.record(via_record, ranked, run_id="live")

    via_finish = db.connect(tmp_path / "b.db"); db.init_db(via_finish)
    _seed(via_finish)
    ctx = TheoryContext.build(conn=via_finish, board=board, now=NOW)
    _theory().start(ctx).finish()

    fields = ("kalshi_ticker, outcome, entry_price, edge_pts_net, "
              "edge_basis, confidence, rationale, spread_at_call, "
              "volume_at_call")
    sql = f"SELECT {fields} FROM opportunities ORDER BY kalshi_ticker"
    a = [tuple(r) for r in via_record.execute(sql).fetchall()]
    b = [tuple(r) for r in via_finish.execute(sql).fetchall()]
    assert len(a) == 3
    assert a == b
    via_record.close(); via_finish.close()
