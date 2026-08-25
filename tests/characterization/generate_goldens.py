"""Generate every golden from the committed fixture. Run ONCE, at Phase 0:

    python -m tests.characterization.generate_goldens

Refuses to overwrite an existing golden (see conftest.dump_golden): after
Phase 0 these files are the migration's only proof that behavior did not
move, so regenerating one would destroy the evidence it exists to carry.

No network, no database -- everything comes from board_sample.json and the
frozen rates in meta.json.
"""

from __future__ import annotations

from theories.insider_bias import screen
from theories.insider_bias.insider_judgment import gate, pipeline
from theories.insider_bias.mention_family import mention_bucket
from tools.kalshi import markets

from tests.characterization import conftest as cz


def main() -> None:
    board = cz.board_input()
    now = cz.frozen_now()
    rates = cz.frozen_rates()

    candidates = screen.screen(board, now=now)
    cz.dump_golden("screen", candidates)

    events = pipeline.dedupe_by_event(candidates)
    cz.dump_golden("dedupe_by_event", events)

    survivors, counts = gate.partition(events)
    cz.dump_golden("gate_partition", {"survivors": survivors,
                                      "counts": counts})

    survivor_keys = {cz.event_key(s) for s in survivors}
    kept = [c for c in candidates if cz.event_key(c) in survivor_keys]
    cz.dump_golden("blind_payload",
                   pipeline.build_blind_payload(survivors, kept))

    cz.dump_golden("run_mechanical_stages",
                   pipeline.run_mechanical_stages(board, now))

    family = mention_bucket.find_candidates(board, now=now)
    cz.dump_golden("mention_find_candidates", family)
    cz.dump_golden("mention_rank", mention_bucket.rank(family, rates))

    # The validated 14-day window is routinely empty for this theory (see
    # build_fixture's docstring), so the goldens that actually lock its
    # arithmetic come from the wide horizon. `rank` and `rank_preview` are
    # locked separately and deliberately: they attach different edge_basis
    # values, and collapsing them is the exact regression the OOP spec's
    # non-regression list forbids.
    wide = mention_bucket.find_candidates(
        board, now=now, max_days_ahead=cz.preview_days()
    )
    cz.dump_golden("mention_find_candidates_wide", wide)
    cz.dump_golden("mention_rank_wide",
                   mention_bucket.rank(wide, rates, top_n=len(wide)))
    cz.dump_golden("mention_rank_preview_wide",
                   mention_bucket.rank_preview(wide, rates, top_n=len(wide)))

    cz.dump_golden(
        "normalize",
        {m["ticker"]: markets.normalize(m["raw"]) for m in cz.load_fixture()},
    )

    print("goldens written:", sorted(p.name for p in cz.GOLDENS.iterdir()))


if __name__ == "__main__":
    main()
