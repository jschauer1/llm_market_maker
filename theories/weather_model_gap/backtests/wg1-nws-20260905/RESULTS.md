# WG-1-NWS legacy diagnostic results

This experiment measures only the archived NWS settlement regime. It cannot validate current TWC contracts.

| Population | Known / selected | Net pts | One-contract net pts | Supported |
|---|---:|---:|---:|---|
| Pooled | 297 / 297 | -5.61 | -5.99 | False |
| KXHIGHNY | 96 / 96 | 1.57 | 1.19 | False |
| KXHIGHLAX | 102 / 102 | -8.91 | -9.26 | False |
| KXHIGHCHI | 99 / 99 | -9.18 | -9.58 | False |

Coverage: {"events": 498, "events_by_series": {"KXHIGHCHI": 166, "KXHIGHLAX": 166, "KXHIGHNY": 166}, "label_reasons": {"KXHIGHCHI:valid": 166, "KXHIGHLAX:valid": 166, "KXHIGHNY:missing_or_invalid_expiration_value": 1, "KXHIGHNY:valid": 165}, "source_end_inclusive": "2026-08-13", "source_start": "2026-03-01", "valid_labels_by_series": {"KXHIGHCHI": 166, "KXHIGHLAX": 166, "KXHIGHNY": 165}}

Frozen gate removals: {"ask_band": 1054, "edge_below_floor": 1541, "entry_candle_missing": 13, "invalid_model_input": 16, "lower_ranked": 384, "no_entry_activity": 178, "open_interest": 13, "spread": 32}

Interpretation: The frozen legacy population is unconfirmed and its pooled cluster intervals rule out a +3 point net effect. Stop without retuning.
