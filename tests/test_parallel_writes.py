"""Verifies -- not assumes -- the spec section 4.9 concurrency claim: WAL
plus the 30s busy timeout let N connections, each recording a DIFFERENT
theory's rows, all commit. Each thread opens its own connection; a
sqlite3.Connection is never shared across the boundary."""

import threading

from tools import db, ledger, theories

TS = "2026-08-24T12:00:00Z"


def test_concurrent_connections_each_writing_their_own_theory_all_commit(tmp_path):
    path = tmp_path / "t.db"
    setup = db.connect(path)
    db.init_db(setup)
    for i in range(4):
        theories.register(setup, f"t{i}", f"T{i}", "x", now=TS)
    setup.close()

    errors: list[Exception] = []

    def work(i: int) -> None:
        try:
            conn = db.connect(path)
            for j in range(5):
                ledger.record_opportunity(
                    conn, theory_id=f"t{i}", theory_version=1,
                    kalshi_ticker=f"KX{i}-{j}", outcome="yes",
                    entry_price=0.5, edge_pts_net=3.0, now=TS)
            conn.close()
        except Exception as exc:          # surfaced below, never swallowed
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    check = db.connect(path)
    n = check.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
    assert n == 20
    check.close()
