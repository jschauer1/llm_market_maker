"""Pass 4: pass 3's bar, restricted to observations with a tradeable book.

**This module adds exactly one thing to pass 3 and must never add a
second.** The statistic, the inclusion floors, the four flag gates, the
Holm family, the "measured" criterion, the secondary MDE view and the
carried candidates all come from `mine.py` and `pass3.py` unchanged. The
only new code is an observation-level WHERE clause and the accounting of
what it removes.

The bar this implements is STUDY.md "Pass 4, pre-registered now" as
amended by "Correction to pass 4's filter, made before pass 4 runs", both
committed before any pass-4 number existed:

  * an observation is admitted only if it carried a tradeable book AT THE
    DECISION POINT -- `open_interest >= 100` and `spread <= 0.07`;
  * the threshold is the one derived from this population's own
    distribution by the sibling study and *offered* to pass 4 in
    STUDY.md's 2026-09-01 cross-reference, adopted here verbatim rather
    than re-derived, because re-deriving it now -- after pass 3's numbers
    are known -- would be a threshold chosen with the answer in view;
  * everything downstream of the filter is pass 3's, by import.

**The acceptance test is the thing that decides this pass, not the flag
count.** STUDY.md fixes it twice: *if `mention_family` still trips the
gates under the filter, the population is still wrong and pass 4 is not
measured, whatever else it flags.* That is implemented here as a real
term in `measured`, not printed as advice -- pass 3 flagged nine series
and was not measured, and the control is why.

**How to read the filter's effect, per ticket
`2026-09-01-pass4-filter-roles-are-reversed`.** The correction that set
this filter argued `open_interest` was load-bearing and `spread` was not.
At 99.95% backfill coverage the sibling study measured the opposite: in
the 0.90-0.97 band, `spread<=0.07 AND oi==0` is -1.46 against
`spread<=0.07 AND oi>=100` at -1.14, a 0.3-point gap, while the
unfiltered-to-filtered improvement in that band is 6.5 points. Almost all
of the filter's effect is the SPREAD condition. The filter is still run
exactly as pre-registered -- the ticket is explicit that nothing should
be retuned -- but no result from it may be attributed to open interest.

Run: python tickets/study/investigation/2026-08-29-series-bias-mining/pass4.py
"""

from __future__ import annotations

import sqlite3
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


#: Located by MARKER rather than by depth -- see the same note in
#: `mine.py`. This study has moved three times and each move silently
#: broke a hardcoded `parents[N]`.
def _repo_root(start: Path) -> Path:
    for p in start.parents:
        if (p / "tools").is_dir() and (p / "theories").is_dir():
            return p
    raise RuntimeError("repo root not found above %s" % start)


sys.path.insert(0, str(_repo_root(Path(__file__).resolve())))
sys.path.insert(0, str(HERE))

import mine as M                                       # noqa: E402
import pass3 as P3                                     # noqa: E402

DB = HERE / "data" / "collect.db"

#: STUDY.md "Correction to pass 4's filter" + the 2026-09-01
#: cross-reference that fixed the level from the population's own
#: open-interest distribution (p50=0, p75=110, p90=1201 in the 0.90-0.97
#: cell; 100 is the first round level separating "somebody holds this"
#: from "nobody does"). Adopted verbatim, NOT re-derived -- see module
#: docstring.
TRADEABLE_MAX_SPREAD = 0.07
TRADEABLE_MIN_OI = 100.0

VIEWS = P3.VIEWS


def _view_clause(view: str) -> tuple[str, str, str]:
    """(ask_col, won_col, where) for a declared view -- pass 3's, plus
    the tradeable-book filter.

    **The 24h view's filter is mixed-timestamp, and that is disclosed
    rather than hidden.** `collect.py` captured `spread_24h` but no
    `open_interest_24h`, so the 24h view applies its own spread at its
    own timestamp and borrows the open-interest level from the 25%
    decision point. That point is EARLIER than 24h-before-close for any
    market living longer than four days, so the borrowed level is a
    staler mark, never a peek forward. It is still a different filter
    from the primary's and no 24h number may be read as though it were
    the same one.
    """
    if view not in VIEWS:
        raise ValueError("unknown view %r; declared views are %s"
                         % (view, ", ".join(VIEWS)))
    ask_col, won_col = "ask", "won"
    where = "ask IS NOT NULL AND won IS NOT NULL"
    spread_col = "spread"
    if view == "at_24h":
        ask_col, won_col = "ask_24h", "won_24h"
        where = "ask_24h IS NOT NULL AND won_24h IS NOT NULL"
        spread_col = "spread_24h"
    elif view == "early":
        where += " AND early_settled = 1"
    elif view == "ontime":
        where += " AND (early_settled = 0 OR early_settled IS NULL)"
    where += (" AND %s IS NOT NULL AND %s <= %r"
              " AND open_interest IS NOT NULL AND open_interest >= %r"
              % (spread_col, spread_col, TRADEABLE_MAX_SPREAD,
                 TRADEABLE_MIN_OI))
    return ask_col, won_col, where


def load_tradeable(path: Path = DB, view: str = "primary"
                   ) -> dict[str, list[tuple]]:
    """pass 3's loader with the pre-registered tradeable-book filter."""
    ask_col, won_col, where = _view_clause(view)
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    conn.row_factory = sqlite3.Row
    out: dict[str, list[tuple]] = {}
    for r in conn.execute(
            "SELECT series_ticker, DATE(close_time) AS day, "
            "%s AS won, %s AS ask FROM obs "
            "WHERE %s AND close_time IS NOT NULL"
            % (won_col, ask_col, where)):
        out.setdefault(r["series_ticker"], []).append(
            (r["day"], float(r["won"]), float(r["ask"])))
    conn.close()
    return out


def filter_accounting(path: Path = DB) -> dict:
    """What the filter removes, by reason. STUDY.md's correction requires
    the chosen threshold be recorded "with the count of observations it
    removes", and rows failing an inclusion rule are counted and reported
    rather than silently dropped."""
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    q = lambda w: conn.execute(                        # noqa: E731
        "SELECT COUNT(*) FROM obs WHERE ask IS NOT NULL "
        "AND won IS NOT NULL AND close_time IS NOT NULL AND " + w
    ).fetchone()[0]
    total = q("1=1")
    out = {
        "priced_obs": total,
        "no_book_fields": q("spread IS NULL OR open_interest IS NULL"),
        "fails_spread": q("spread IS NOT NULL AND spread > %r"
                          % TRADEABLE_MAX_SPREAD),
        "fails_oi": q("open_interest IS NOT NULL AND open_interest < %r"
                      % TRADEABLE_MIN_OI),
        "fails_spread_only": q(
            "spread IS NOT NULL AND open_interest IS NOT NULL "
            "AND spread > %r AND open_interest >= %r"
            % (TRADEABLE_MAX_SPREAD, TRADEABLE_MIN_OI)),
        "fails_oi_only": q(
            "spread IS NOT NULL AND open_interest IS NOT NULL "
            "AND spread <= %r AND open_interest < %r"
            % (TRADEABLE_MAX_SPREAD, TRADEABLE_MIN_OI)),
        "fails_both": q(
            "spread IS NOT NULL AND open_interest IS NOT NULL "
            "AND spread > %r AND open_interest < %r"
            % (TRADEABLE_MAX_SPREAD, TRADEABLE_MIN_OI)),
        "admitted": q("spread IS NOT NULL AND open_interest IS NOT NULL "
                      "AND spread <= %r AND open_interest >= %r"
                      % (TRADEABLE_MAX_SPREAD, TRADEABLE_MIN_OI)),
    }
    conn.close()
    out["removed"] = total - out["admitted"]
    out["removed_pct"] = 100.0 * out["removed"] / total if total else 0.0
    return out


def robustness(flagged, path: Path = DB) -> dict:
    """pass 3's robustness views, on the filtered population."""
    want = {st.series for st in flagged}
    if not want:
        return {}
    out: dict[str, dict] = {s: {} for s in want}
    for view in ("at_24h", "early", "ontime"):
        by_series = load_tradeable(path, view=view)
        for s in want:
            rows = by_series.get(s)
            out[s][view] = M.stat_for(s, rows) if rows else None
    return out


def run(path: Path = DB) -> dict:
    """Pass 3's analysis on the filtered population, plus the acceptance
    test as a real term in `measured`.

    `P3.run` is called rather than reimplemented: the floors, gates, Holm
    family, MDE view and carried candidates must be pass 3's exactly, or
    the two passes are not comparable and the filter is not the only
    thing that changed.
    """
    r = P3.run(by_series=load_tradeable(path), path=path)
    control_tripping = [s for s in r["control"]
                        if s.passes_split and s.passes_t]
    r["control_tripping"] = control_tripping
    r["control_clean"] = not control_tripping
    #: STUDY.md, twice: "if mention_family still trips the gates under
    #: that filter, the population is still wrong and pass 4 is not
    #: measured either, whatever else it flags."
    r["measured_pass3_criterion"] = r["measured"]
    r["measured"] = bool(r["measured"] and r["control_clean"])
    r["filter"] = filter_accounting(path)
    return r


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DB
    print("population: %s" % path.name)
    r = run(path)
    f = r["filter"]
    print("=" * 72)
    print("PASS 4 -- broad sweep under a TRADEABLE-BOOK filter")
    print("bar: STUDY.md 'Pass 4, pre-registered now' + its correction")
    print("filter: spread <= %.2f AND open_interest >= %.0f, at the "
          "decision point" % (TRADEABLE_MAX_SPREAD, TRADEABLE_MIN_OI))
    print("=" * 72)
    print("-- what the filter removes (recorded, never silent) --")
    print("  priced observations      : %d" % f["priced_obs"])
    print("  admitted                 : %d" % f["admitted"])
    print("  removed                  : %d  (%.1f%%)"
          % (f["removed"], f["removed_pct"]))
    print("    no book fields (NULL)  : %d" % f["no_book_fields"])
    print("    fails spread only      : %d" % f["fails_spread_only"])
    print("    fails open interest only: %d" % f["fails_oi_only"])
    print("    fails both             : %d" % f["fails_both"])
    print("  (fails spread, any OI    : %d)" % f["fails_spread"])
    print("  (fails OI, any spread    : %d)" % f["fails_oi"])
    print()
    print("series with priced obs      : %d" % r["series_seen"])
    print("series clearing floors      : %d" % r["series_admitted"])
    print("  of which mention control  : %d" % len(r["control"]))
    print("series TESTED (Holm family) : %d" % len(r["stats"]))
    print("expected false positives    : %.1f" % r["expected_false_positives"])
    print("median MDE over tested      : %.2f pts" % r["median_mde"])
    print()
    print("-- ACCEPTANCE TEST: the negative control decides this pass --")
    print("  control series admitted  : %d" % len(r["control"]))
    print("  control tripping split+t : %d  %s"
          % (len(r["control_tripping"]),
             [s.series for s in r["control_tripping"]]))
    for st in sorted(r["control_tripping"], key=lambda x: -abs(x.t)):
        print("      %-24s n=%5d days=%4d gross=%+7.2f t=%+6.2f"
              % (st.series, st.n, st.n_days, st.edge, st.t))
    print("  CONTROL CLEAN?           : %s"
          % ("YES" if r["control_clean"] else "NO -- population still wrong"))
    print()
    print("pass-3 criterion (>=%d tested, median MDE <=%s) : %s"
          % (P3.MIN_TESTED_FOR_MEASURED, P3.MAX_MEDIAN_MDE_FOR_MEASURED,
             "met" if r["measured_pass3_criterion"] else "NOT met"))
    print("PRE-REGISTERED 'MEASURED'?  : %s"
          % ("YES" if r["measured"] else "NO -- not measured"))
    print("FLAGGED (all four gates)    : %d" % len(r["flagged"]))
    for st in sorted(r["flagged"], key=lambda x: -abs(x.t)):
        print("    %-24s n=%5d days=%4d gross=%+7.2f net=%+7.2f "
              "t=%+6.2f p=%.2e halves %+6.2f/%+6.2f"
              % (st.series, st.n, st.n_days, st.edge, st.edge_net,
                 st.t, st.p, st.first_edge, st.second_edge))

    print()
    print("-- selection channel (reported, never filtered) --")
    if r["winrate_low_mde"] is not None and r["winrate_high_mde"] is not None:
        print("  mean win rate, MDE<=8 : %.4f" % r["winrate_low_mde"])
        print("  mean win rate, MDE >8 : %.4f" % r["winrate_high_mde"])

    print()
    print("-- SECONDARY view: pass 2's MDE<=5 floor, OUTCOME-CORRELATED --")
    print("  tested  : %d" % r["powered_tested"])
    print("  flagged : %d  %s"
          % (len(r["powered_flagged"]),
             [s.series for s in r["powered_flagged"]]))

    print()
    print("-- carried candidates, signs fixed before looking --")
    for series, want in P3.PREREGISTERED_SIGNS.items():
        st = r["carried"].get(series)
        if st is None:
            print("  %-12s not in the admitted family this pass" % series)
            continue
        got = 1 if st.edge > 0 else -1
        ok = (got == want and st.passes_t
              and st.series in r["holm_survivors"])
        note = "" if got == want else "  [SIGN OPPOSITE -- failed test]"
        print("  %-12s predicted %s | gross %+7.2f t %+6.2f p %.2e "
              "n=%d days=%d -> %s%s"
              % (series, "+" if want > 0 else "-", st.edge, st.t, st.p,
                 st.n, st.n_days,
                 "CONFIRMED" if ok else "not confirmed", note))

    if r["flagged"]:
        print()
        print("-- robustness (declared before results; never promotes) --")
        print("   NOTE: the at_24h view filters on spread_24h but borrows")
        print("   open interest from the 25% decision point -- no")
        print("   open_interest_24h was captured. A staler mark, never a")
        print("   peek forward, but not the same filter.")
        rb = robustness(r["flagged"], path)
        for st in sorted(r["flagged"], key=lambda x: -abs(x.t)):
            print("  %s   primary %+.2f (t %+.2f, n=%d)"
                  % (st.series, st.edge, st.t, st.n))
            for view in ("at_24h", "early", "ontime"):
                v = rb[st.series][view]
                if v is None:
                    print("      %-8s -- below the floors in this view"
                          % view)
                else:
                    same = ("same sign" if (v.edge > 0) == (st.edge > 0)
                            else "SIGN FLIPS")
                    print("      %-8s %+7.2f  t %+6.2f  n=%-5d days=%-4d %s"
                          % (view, v.edge, v.t, v.n, v.n_days, same))


if __name__ == "__main__":
    main()
