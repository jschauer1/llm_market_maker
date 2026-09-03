"""Generate every golden from the committed fixture. Run ONCE, at Phase 0:

    python -m tests.characterization.generate_goldens

Refuses to overwrite an existing golden (see conftest.dump_golden): after
Phase 0 these files are the migration's only proof that behavior did not
move, so regenerating one would destroy the evidence it exists to carry.

No network, no database -- everything comes from board_sample.json and
meta.json.

**Six of the thirteen goldens this once wrote no longer exist.** The
`mention_*` files (`mention_find_candidates`, `..._wide`, `mention_rank`,
`mention_rank_wide`, `mention_rank_preview_wide`,
`mention_rank_wide_edge_corrected`) locked `mention_family`, which the
user retired on 2026-08-27; its code was deleted on 2026-09-02 and the
goldens went with it, along with the `rates`/`preview_days` accessors this
script used to read out of meta.json. The generator that wrote them is at

    git show 450db428ec0e7542852fae6484ab8370aaeddfad:tests/characterization/generate_goldens.py

The seven that remain -- screen, dedupe_by_event, gate_partition,
gate_partition_v3, blind_payload_v3, run_mechanical_stages_v3, normalize
-- cover live code and are untouched by that deletion.
"""

from __future__ import annotations

from theories.insider_bias import screen
from theories.insider_bias.insider_judgment import gate, pipeline
from tools.kalshi import markets

from tests.characterization import conftest as cz


def main() -> None:
    board = cz.board_input()
    now = cz.frozen_now()

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

    cz.dump_golden(
        "normalize",
        {m["ticker"]: markets.normalize(m["raw"]) for m in cz.load_fixture()},
    )

    print("goldens written:", sorted(p.name for p in cz.GOLDENS.iterdir()))


if __name__ == "__main__":
    main()
