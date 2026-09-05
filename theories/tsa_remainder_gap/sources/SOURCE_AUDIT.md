# TSA source-contract audit

**Date:** 2026-09-05 · **Scope:** source and settlement arithmetic only; no
quotes, forecasts, model probabilities, trades, or returns were read or
computed.

## Result

The named Monday-through-Sunday window is the correct interpretation, but the
current TSA archive is not an exact reconstruction of every settlement-time
input. It crosses one recorded strike in 16 of
219 explicit-TSA-source events (7.3%). Moving the
seven-day window one day earlier or later produces 69 and
67 disagreement events, respectively, versus 16 for the
named Sunday. Every disagreement uses the same strict-above, named-week-ending
primary-rule form. The observed pattern therefore does not support a changed
weekly definition or a one-day parser error.

Kalshi's normalized `expiration_value` predicts every recorded market payout in
214 of 215 events where it is numeric and consistent within the event. The one
exception is `KXTSAW-25APR20`: its value is 2,188,786, while its monotone payout
ladder places the outcome above 2,450,000 and at or below 2,500,000. Four other
events have no single parseable numeric value. Settlement results remain the
contract outcome; `expiration_value` is a strong cross-check, not an infallible
source field.

Across the 215 parseable events, the current TSA mean exceeds Kalshi's normalized
settlement value by more than one traveler in 179 events, is lower by more than
one in six, and is within one in 30. The median difference is +3,448 and the
median absolute difference is 4,108. This directional pattern is consistent
with later TSA revisions to provisional counts. It does not prove revisions:
the retained receipts cannot distinguish later TSA edits from a different
Kalshi settlement snapshot or processing rule.

Integer rounding or truncation cannot explain the 16 crossed strikes. The
current mean is 156 to 28,937 travelers from the affected strike, while an
integer conversion can move it by less than one. The crossings occur from
2022-10-23 through 2025-06-01: 1/28 eligible events in 2022, 5/53 in 2023,
7/52 in 2024, 3/51 in 2025, and 0/35 in 2026 through August 30. The absence of
recent crossings is encouraging but is not evidence that historical receipt
versions are equivalent.

## Exact disagreements

`Result / archive` gives Kalshi's recorded payout followed by the payout implied
by today's official TSA Monday-Sunday mean. Exact primary and secondary rules,
seven daily values, full event ladders, and raw expiration-value strings are in
`comparison.json`; the exact affected market objects are in
`selected_market_receipts.json`.

| Week ending | Market | Strike | Current TSA mean | Kalshi expiration value | Current - expiration | Result / archive | Distance to strike |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2022-10-23 | `TSAW-22OCT23-A2.25` | 2,250,000 | 2,233,567.9 | 2,256,506 | -22,938.1 | YES / NO | 16,432.1 |
| 2023-03-12 | `TSAW-23MAR12-A2.30` | 2,300,000 | 2,300,277.7 | 2,285,256 | +15,021.7 | NO / YES | 277.7 |
| 2023-04-30 | `TSAW-23APR30-A2.30` | 2,300,000 | 2,313,146.4 | 2,298,129 | +15,017.4 | NO / YES | 13,146.4 |
| 2023-07-16 | `TSAW-23JUL16-A2.60` | 2,600,000 | 2,603,060.1 | 2,594,678 | +8,382.1 | NO / YES | 3,060.1 |
| 2023-07-30 | `TSAW-23JUL30-A2.60` | 2,600,000 | 2,621,361.1 | 2,592,360 | +29,001.1 | NO / YES | 21,361.1 |
| 2023-09-10 | `TSAW-23SEP10-A2.30` | 2,300,000 | 2,302,251.0 | 2,293,025 | +9,226.0 | NO / YES | 2,251.0 |
| 2024-01-28 | `TSAW-24JAN28-A2.00` | 2,000,000 | 2,003,489.1 | 1,999,976 | +3,513.1 | NO / YES | 3,489.1 |
| 2024-03-03 | `TSAW-24MAR03-A2.35` | 2,350,000 | 2,333,486.4 | 2,360,710 | -27,223.6 | YES / NO | 16,513.6 |
| 2024-04-07 | `TSAW-24APR07-A2.50` | 2,500,000 | 2,504,253.1 | 2,492,101 | +12,152.1 | NO / YES | 4,253.1 |
| 2024-04-28 | `TSAW-24APR28-A2.45` | 2,450,000 | 2,454,126.6 | 2,446,181 | +7,945.6 | NO / YES | 4,126.6 |
| 2024-06-30 | `TSAW-24JUN30-A2.80` | 2,800,000 | 2,803,154.0 | 2,798,814 | +4,340.0 | NO / YES | 3,154.0 |
| 2024-09-08 | `TSAW-24SEP08-A2.35` | 2,350,000 | 2,321,063.3 | 2,368,354 | -47,290.7 | YES / NO | 28,936.7 |
| 2024-09-29 | `TSAW-24SEP29-A2.40` | 2,400,000 | 2,415,059.7 | 2,396,504 | +18,555.7 | NO / YES | 15,059.7 |
| 2025-01-05 | `KXTSAW-25JAN05-A2.50` | 2,500,000 | 2,507,847.4 | 2,495,850 | +11,997.4 | NO / YES | 7,847.4 |
| 2025-05-11 | `KXTSAW-25MAY11-A2.45` | 2,450,000 | 2,456,879.3 | 2,446,455 | +10,424.3 | NO / YES | 6,879.3 |
| 2025-06-01 | `KXTSAW-25JUN01-A2.60` | 2,600,000 | 2,600,156.1 | 2,589,306 | +10,850.1 | NO / YES | 156.1 |

## Consequence for replay

A deterministic replay remains **tier A for model contamination** because no LLM
judgment enters its decision path. Tier does not certify source fidelity. A
replay using today's mutable TSA archive must be marked experimental and
source-diagnostic unless the implementation either reconstructs the historical
information set or measures and bounds the decision impact of the source
version. Timestamped Friday captures are the clean prospective path; they are
not a universal prerequisite for using independently validated historical
source data.

## Retained evidence

- `receipts.json`: URLs, retrieval times, byte counts, and SHA-256 hashes.
- `tsa_2022.html` through `tsa_2026.html`: exact TSA responses used.
- `selected_market_receipts.json`: exact Kalshi records for all 16 crossed
  strikes plus the two records exposing the 2025-04-20 expiration-value anomaly.
- `comparison.json`: method, census summary, all 16 rules/daily inputs/ladders,
  date concentration, adjacent-window check, and the expiration-value anomaly.

The full Kalshi pagination responses were compacted after comparison; their
receipt metadata and hashes remain in `receipts.json`.

The bounded four-repository recovery check is in `PUBLIC_REPO_AUDIT.md`. None
of the repositories covers the disputed 2022-10-23 through 2025-06-01 interval
with contemporaneous snapshots. It also documents the old TSA table's
same-weekday comparison-column trap.
