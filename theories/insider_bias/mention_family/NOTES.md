# mention_family — notes

Lab notebook: raw, dated, append-only. The format and the distillation rule
are in `theories/_TEMPLATE/NOTES.md`. Nothing here is private — any session
may read any theory's notes.

## 2026-08-25 — Notebook opened; where this theory's history lives

This file starts empty by design; nothing was migrated into it.

- **`THEORY.md` Status** — `under_review` as of 2026-08-25, with a
  standing retirement proposal filed the same day and still awaiting
  the user's ruling. The tier A full-coverage backtest
  (`backtest-2026-08-25-mention-fullcov`: every mention-family
  survivor in the API-reachable window, n=3,441 settled, vs the n=116
  sample the bins were fit on) found no edge —
  `calibration_edge=-0.49` gross, `calibration_edge_net=-1.53`,
  `roi_all=-1.9%` — superseding the audit below.
- **`THEORY.md` Learnings** — the distilled record, in chronological
  order: (1) the 2026-08-25 skeptical audit of the original backtest
  edge — mechanics came back clean (no lookahead, fees included,
  negligible event clustering, stable pre-event favorites) but the
  statistical case was already much weaker than the headline read —
  pooled p=0.0395 gross, p=0.070 after fees, before any correction for
  this family having been *selected* as the standout slice of a
  200-row backtest; (2) the full-coverage rerun that followed and
  killed the edge outright, driving the status change above; (3) a
  same-day pattern-mining pass over the full-coverage rows that found
  timing and price-level effects dead, but a side asymmetry (NO
  favorites at ask ≥0.90) that survived every stress test — recorded
  as backlog idea `no-side-premium`, not a revival of this theory.
- **`RESEARCH_LOG.md`** — the session narratives, in order: the
  2026-08-24 split from `insider_judgment` into a separate theory; the
  2026-08-25 audit in full; "Full-coverage rerun: mention_family has
  no edge; under_review, retirement proposed"; and the same day's
  "Pattern-mining the fullcov rows" follow-up.

From here on, raw findings about this theory land in this file, and
`THEORY.md` changes only when the claim, the procedure, or the status
changes.

## 2026-08-29 — a shared-module correction changed this theory's arithmetic (retired; no version bump)

`tools/buckets.edge_for` was corrected on 2026-08-29: a confidence bucket
now contributes its own realized **edge** (`win_rate − mean entry price of
the rows that measured it`) instead of being repriced against each
candidate's own ask. See `theories/insider_bias/insider_judgment/
THEORY.md` "Version 4" for the full argument.

**This theory used that function, so its arithmetic moved under it.** On
the characterization fixture the ranking changes materially:

| | top pick | ask | net edge |
|---|---|---|---|
| before | `KXEARNINGSMENTIONURBN` (a cheaper strike) | 0.85 | +14.11 |
| after | `KXEARNINGSMENTIONURBN-26AUG26-TARI` | 0.97 | +8.21 |

The old formula was sorting this theory **by cheapness**: every candidate
in a price bin was repriced against that bin's win rate, so the cheapest
member of the bin always looked best. Price binning was the workaround
that kept this survivable — inside a narrow bin the flat rate is nearly
right — which is why the defect was never visible here as it was on
`insider_judgment`'s single 0.65–0.97 band. It was still a defect.

**No version bump.** This theory is `retired` (user ruling, 2026-08-27)
and records no further rows, so there is no track record for a version
number to keep separable; the fact is recorded here and in `THEORY.md`
instead. Anyone reviving it must read the v1 rows as priced by the old
formula, and re-derive, not reuse, any ranking from that era. The
pre-correction output is preserved unmodified in
`tests/characterization/goldens/mention_rank_wide.json`.
