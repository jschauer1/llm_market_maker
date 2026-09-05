# TRG-1: negative archive diagnostic

The fixed remainder model did not show an edge. Its chronological holdout lost
**8.07 net points per position**, or **8.64 points with one-contract rounded
fees**. The theory is under review; no bet is recommended from this result.

| Partition | Entries / calendar weeks | Net points | Weekly 95% interval |
|---|---:|---:|---:|
| Development | 94 / 167 | -1.84 | [-8.78, +5.10] |
| Holdout | 44 / 53 | -8.07 | [-15.29, -0.85] |

All 138 entries settled. Holdout has 43 settlement-day clusters, whose interval
is [-15.33, -0.81]. Its YES positions averaged -4.82 points (n=30), NO -15.02
(n=14). Model probabilities averaged 52.1%; only 4/44 positions won.

This is a **tier-A experimental current-archive reconstruction**, not validated
historical source evidence. TSA revisions remain unresolved. All rows use
`exp/trg1-20260905/` identities and are excluded from production scores. No
threshold, side or date was selected after seeing returns.

[Frozen protocol](PROTOCOL.md), [input identity](identity.json),
[outcome-free decisions](decisions.json), [calendar/exclusion manifest](evaluation_manifest.json),
and [full statistics and ledger scores](results.json) preserve the audit trail.
