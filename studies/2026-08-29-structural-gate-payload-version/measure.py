"""Reproduce the corrected measurement. Orders versions by captured_at.

The first version of this study extracted before/after quotes from
`sorted(set_of_values)` -- alphabetical order presented as chronological
-- which reversed three of its four examples. This script exists so the
ordering is explicit and checkable.

Run: python studies/2026-08-29-structural-gate-payload-version/measure.py
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import db, snapshot                         # noqa: E402


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def main() -> None:
    conn = db.connect()
    hist_r, hist_t, caps = defaultdict(list), defaultdict(list), defaultdict(int)
    nonopen_rows = 0
    for r in conn.execute("SELECT market_id, captured_at, raw_json, status "
                          "FROM market_snapshots ORDER BY market_id, captured_at"):
        d = json.loads(snapshot.payload_text(r["raw_json"]))
        mid = r["market_id"]
        caps[mid] += 1
        if r["status"] not in ("active", "open"):
            nonopen_rows += 1
        for field, store in (("rules_primary", hist_r), ("title", hist_t)):
            v = d.get(field)
            if v is not None and (not store[mid] or store[mid][-1][1] != v):
                store[mid].append((r["captured_at"], v, r["status"]))

    multi = sum(1 for v in caps.values() if v > 1)
    subst_r = {m: h for m, h in hist_r.items() if len({norm(x[1]) for x in h}) > 1}
    subst_t = {m: h for m, h in hist_t.items() if len({norm(x[1]) for x in h}) > 1}
    print(f"distinct markets           : {len(caps)}")
    print(f"multi-capture (denominator): {multi}")
    print(f"substantive rules changes  : {len(subst_r)} "
          f"({100*len(subst_r)/multi:.2f}%)")
    print(f"substantive title changes  : {len(subst_t)} "
          f"({100*len(subst_t)/multi:.2f}%)")
    tot = sum(caps.values())
    print(f"non-open snapshot rows     : {nonopen_rows} of {tot} "
          f"({100*nonopen_rows/tot:.1f}%) -- post-settlement channel "
          f"is near-unobservable")

    # Edit patterns: one shared across many markets is a template migration.
    groups = defaultdict(list)
    for m, h in subst_r.items():
        first, last = h[0][1], h[-1][1]
        sm = difflib.SequenceMatcher(None, first.split(), last.split())
        sig = tuple(sorted(
            (" ".join(first.split()[i1:i2])[:40],
             " ".join(last.split()[j1:j2])[:40])
            for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"))
        groups[sig].append(m)
    singles = [ms[0] for sig, ms in groups.items() if len(ms) == 1]
    print(f"\n{len(subst_r)} substantive rules changes -> "
          f"{len(groups)} edit patterns, {len(singles)} unique to one market")
    print("\nthe one genuine change of resolution criteria:")
    for m in singles:
        h = subst_r[m]
        if "become law" in h[0][1] or "enacted" in h[-1][1]:
            for ts, v, _ in h:
                print(f"  {ts}  {v[:100]}")


if __name__ == "__main__":
    main()
