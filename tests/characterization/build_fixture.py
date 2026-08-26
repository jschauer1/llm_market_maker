"""Build the characterization fixture from a real Kalshi board. Run ONCE,
at Phase 0 of the theory-layer OOP migration, from the repo root:

    python -m tests.characterization.build_fixture

Contents: every market that survives screen.screen() (so the goldens cover
every candidate the current code produces), every mention_family market
that survives the screen at a wide horizon, and a systematic sample of
2,000 non-survivors (reject paths and every gate.classify category),
deduped, sorted by ticker, written with sort_keys=True.

**Why the wide-horizon mention_family pass exists.** On a typical board
that theory has *zero* candidates inside its validated 14-day window --
its own module docstring predicts this ("most candidates only become
eligible in the final days before close"), and it was true when this
fixture was first built. Without this second pass its goldens are `[]`,
which locks nothing: `rank([]) == []` passes even if `rank` is broken, and
the OOP migration ports exactly that code. The wide pass is fixture
coverage only -- it never changes what the 14-day goldens record.

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
from theories.insider_bias.mention_family import mention_bucket
from tools import board as board_tool, db

FIXTURES = Path(__file__).parent / "fixtures"

#: Non-survivors kept, evenly spaced across close_time. Covers the reject
#: paths and every gate category without carrying a 100k-market board.
SAMPLE_SIZE = 2000

#: Horizon for the mention_family coverage pass -- see the module
#: docstring. Wide enough to catch the whole family that clears the price,
#: spread and volume screen, so `rank`'s bins and sort are all exercised.
PREVIEW_DAYS = 365.0

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
    family = mention_bucket.find_candidates(
        board, now=now_dt, max_days_ahead=PREVIEW_DAYS
    )
    family_tickers = {c["ticker"] for c in family}
    if not family_tickers:
        raise RuntimeError(
            "no mention_family candidates at any horizon on this board -- "
            "the fixture would lock vacuous goldens for that theory. "
            "Investigate before committing (see the module docstring)."
        )

    wanted = survivor_tickers | family_tickers
    keep = [m for m in board if m["ticker"] in wanted]
    rest = [m for m in board if m["ticker"] not in wanted]
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
                "family_survivors": len(family_tickers),
                "preview_days": PREVIEW_DAYS,
                "rates": mention_bucket.measured_rate(conn),
            },
            sort_keys=True,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(
        f"fixture: {len(fixture)} markets ({len(survivor_tickers)} survivors "
        f"+ {len(family_tickers)} mention_family + sample) from a "
        f"{len(board)}-market board, frozen_now={frozen_now}"
    )


if __name__ == "__main__":
    main()
