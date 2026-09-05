# Public TSA capture repository audit

**Date:** 2026-09-05 · **Scope:** the four named GitHub repositories only.
Repository code was inspected as text and was never executed. No market prices,
model outputs, or trading returns were read or computed.

## Conclusion

None of the four repositories contains contemporaneous TSA snapshots for the
16 disputed weeks, which run from 2022-10-23 through 2025-06-01. They therefore
cannot recover or validate the source versions behind those settlements, and
they do not change the proposal's historical evidence status. A lean archive
replay remains a tier-A experimental source diagnostic; prospective runs should
seal the Friday TSA response.

## Repository findings

- [`hunj/tsa-passenger-throughput`](https://github.com/hunj/tsa-passenger-throughput)
  has 313 commits from 2020-12-26 through 2021-12-27. It made daily captures
  around 18:38 UTC in July 2021, so immutable snapshots exist for some legacy
  2021 markets, after the proposed 15:00 UTC entry. It has no 2022+ data despite
  being archived in May 2023. The sampled July 16–18 snapshots added one row per
  day and changed no common row.
- [`bbgatch/tsa`](https://github.com/bbgatch/tsa) has 28 commits from
  2020-07-09 through 2020-12-30 and daily CSVs for part of July–August 2020.
  `revision-check.py` merely subtracts the two latest row-aligned `2020`
  columns and computes an unsaved sum. It does not retain revision dates or
  magnitudes. The sampled August 27/28 files changed no common row.
- [`chengxdadp/tsa-passenger-volume`](https://github.com/chengxdadp/tsa-passenger-volume)
  has 28 weekly commits from 2026-03-10 through 2026-08-31. Four sampled SQLite
  versions changed no common row and only added new dates; all 239 dates common
  to its latest snapshot and this audit's TSA receipt match exactly. Its older
  years were backfilled when the repository began. The Monday 02:00 UTC cron
  snapshots ended on the preceding Thursday, so they are not Friday 15:00 UTC
  receipts.
- [`zach-wendland/TSA-volume`](https://github.com/zach-wendland/TSA-volume)
  has four commits on 2025-11-09 and 2025-11-10. It commits no TSA data or raw
  HTML; rows are upserted to an external Supabase database that is not present
  in the repository.

The samples directly show no revisions. The `bbgatch` README says TSA may
periodically update old data, but its repository does not retain a measured
revision result. These sources cannot establish the cause, size, or timing of
the 2022–2025 differences.

## Comparison-column date trap

The old TSA table aligned comparison years by weekday, not by identical
month/day. In the raw `hunj` snapshot from 2021-07-16, the first row is:

```text
7/15/2021,2152053,706164,2716828
```

The same file repeats `706164,2716828` on a row dated `7/16/2020`. Thus the
comparison value beside Thursday 2021-07-15 belongs to Thursday 2020-07-16,
not 2020-07-15. The repository's later parser subtracts one or two from the
year while preserving month and day; `bbgatch` likewise stores its `2019`
comparison under the `2020` row date. Those derived dates are unsafe. Only the
current-year value or an explicitly dated, year-specific TSA page should enter
a daily historical series. The modern `chengxdadp` parser avoids this trap by
fetching each annual page separately.

## Retained receipts

[`public_repo_audit/receipts.json`](public_repo_audit/receipts.json) records
pinned URLs, retrieval times, byte counts, and SHA-256 hashes.
[`summary.json`](public_repo_audit/summary.json) contains the machine-readable
conclusion. The retained samples include repository metadata, trees, commit
lists, parser text, selected daily CSVs, and four read-only 2026 SQLite
snapshots.
Captured Python source receipts use a `.py.txt` suffix so repository tooling
treats them as passive evidence rather than local implementation.
