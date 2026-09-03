"""Build the characterization fixture from a real Kalshi board. Run ONCE,
at Phase 0 of the theory-layer OOP migration, from the repo root:

    python -m tests.characterization.build_fixture

Contents: every market that survives screen.screen() (so the goldens cover
every candidate the current code produces) and a systematic sample of
2,000 non-survivors (reject paths and every gate.classify category),
deduped, sorted by ticker, written with sort_keys=True.

**THIS SCRIPT NO LONGER REPRODUCES THE COMMITTED FIXTURE, and the reason
is recorded here rather than left to be rediscovered.** Until 2026-09-02
it ran a second pass -- every `mention_family` market surviving the screen
at a 365-day horizon -- and unioned those tickers into the fixture. That
pass contributed **163 markets** (`meta.json`'s `family_survivors`) which
are in `fixtures/board_sample.json` today and are covered by the
`normalize` golden, one entry per fixture row. The pass existed because
that theory had *zero* candidates inside its validated 14-day window on a
typical board, so without it `mention_rank`'s goldens were `[]`, which
locks nothing.

`mention_family` was retired (user, 2026-08-27) and its code deleted on
2026-09-02, so the pass is gone and its six goldens went with it. The 163
markets stay in the committed fixture: **goldens are immutable, and the
seven that survive -- screen, dedupe_by_event, gate_partition,
gate_partition_v3, blind_payload_v3, run_mechanical_stages_v3, normalize
-- were all recorded against a fixture containing them.** Rebuilding the
fixture without those rows would change `normalize` and every funnel count
downstream of it. That was already true of any re-run (a different board
and a different clock produce a different fixture), which is why this
script says "run ONCE"; what changed is that the fixture's *shape* can no
longer be reproduced even in principle. Retrieve the pass that built it
with

    git show 450db428ec0e7542852fae6484ab8370aaeddfad:tests/characterization/build_fixture.py

`meta.json` keeps `family_survivors`, `preview_days` and `rates` for the
same reason it keeps `full_board_size`: it is the record of how the
committed fixture was made, not a live input. Nothing reads them now.

**The frozen clock is the board's own capture moment**, not wall-clock now.
A board and a clock that disagree would screen out everything that closed
in between, and the whole point of the fixture is a realistic candidate
set. Using the freshest stored snapshot rather than forcing a fresh pull is
deliberate: board.get_board guarantees a rebuilt board is identical to a
fetched one, `raw` included, so the fixture is no different -- and it costs
no network call and no ~200MB of new snapshot rows.

generate_goldens.py then works from the committed fixture alone: no
network, no database, reproducible forever.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from theories.insider_bias import screen
from theories.insider_bias.replay import systematic_sample
from tools import board as board_tool, db

FIXTURES = Path(__file__).parent / "fixtures"

#: Non-survivors kept, evenly spaced across close_time. Covers the reject
#: paths and every gate category without carrying a 100k-market board.
SAMPLE_SIZE = 2000

#: Large enough that any stored board is reused rather than refetched --
#: see the module docstring on why the cache is the right source here.
MAX_AGE_MINUTES = 60 * 24 * 30


def main() -> None:
    conn = db.connect()
    db.init_db(conn)

    info = board_tool.board_info(conn)
    board = board_tool.get_board(conn, max_age_minutes=MAX_AGE_MINUTES)
    frozen_now = info["captured_at"] if info else db.utcnow()
    now_dt = datetime.fromisoformat(frozen_now.replace("Z", "+00:00"))

    survivor_tickers = {c["ticker"] for c in screen.screen(board, now=now_dt)}

    keep = [m for m in board if m["ticker"] in survivor_tickers]
    rest = [m for m in board if m["ticker"] not in survivor_tickers]
    keep += systematic_sample(rest, SAMPLE_SIZE)

    by_ticker = {m["ticker"]: m for m in keep}
    fixture = [by_ticker[t] for t in sorted(by_ticker)]

    FIXTURES.mkdir(exist_ok=True)
    (FIXTURES / "board_sample.json").write_text(
        json.dumps(fixture, sort_keys=True, indent=1), encoding="utf-8"
    )
    (FIXTURES / "meta.json").write_text(
        json.dumps(
            {
                "frozen_now": frozen_now,
                "full_board_size": len(board),
                "survivors": len(survivor_tickers),
            },
            sort_keys=True,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(
        f"fixture: {len(fixture)} markets ({len(survivor_tickers)} survivors "
        f"+ sample) from a {len(board)}-market board, "
        f"frozen_now={frozen_now}"
    )


if __name__ == "__main__":
    main()
