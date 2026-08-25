from datetime import datetime, timezone

import pytest

from tests.characterization import conftest as cz
from theories.insider_bias.mention_family import mention_bucket
from tools import db, ledger, theories
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


def test_price_reproduces_the_golden_rank(frozen_rates):
    ctx = TheoryContext(conn=None, board=cz.board_input(),
                        now=cz.frozen_now())
    result = _theory().start(ctx).finish(dry_run=True)
    assert result.judged is False
    assert cz.proj(list(result.scored)) == cz.load_golden("mention_rank")
    assert all(s.confidence for s in result.scored)


def _seed(conn):
    theories.register(conn, "mention_family", "Mention Family",
                      "theories/insider_bias/mention_family", now=TS)
    with db.write(conn):
        conn.execute("UPDATE theories SET status='testing'"
                     " WHERE id='mention_family'")


def test_finish_writes_the_same_rows_record_would(tmp_path, frozen_rates):
    board = cz.board_input()
    ranked = mention_bucket.rank(
        mention_bucket.find_candidates(board, now=cz.frozen_now()),
        cz.frozen_rates())
    if not ranked:
        pytest.skip("fixture holds no live mention-family candidates")

    via_record = db.connect(tmp_path / "a.db"); db.init_db(via_record)
    _seed(via_record)
    mention_bucket.record(via_record, ranked, run_id="live")

    via_finish = db.connect(tmp_path / "b.db"); db.init_db(via_finish)
    _seed(via_finish)
    ctx = TheoryContext.build(conn=via_finish, board=board,
                              now=cz.frozen_now())
    _theory().start(ctx).finish()

    fields = ("kalshi_ticker, outcome, entry_price, edge_pts_net, "
              "edge_basis, confidence, rationale, spread_at_call, "
              "volume_at_call")
    sql = f"SELECT {fields} FROM opportunities ORDER BY kalshi_ticker"
    a = [tuple(r) for r in via_record.execute(sql).fetchall()]
    b = [tuple(r) for r in via_finish.execute(sql).fetchall()]
    assert a == b
    via_record.close(); via_finish.close()
