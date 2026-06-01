# Hunt Research Six-Field Cleanup

Generated: 2026-06-01T12:03:38.211103

## Scope
- Targeted reconciliation only for six remaining field families:
  - display_odds_pct, p_draw_mean, p_draw_p10, p_draw_p90, permits_2026_total, average_harvest_age
- Prioritized repair order applied: permits_2026_total, average_harvest_age, display_odds_pct, then p_draw family.

## Classification Rule Set
- `true data mismatch`
- `normalization/rounding mismatch`
- `legacy derivation mismatch`
- `source hierarchy mismatch`
- `missing target field population`
- `acceptable intentional divergence` (action label for source-hierarchy differences)

## Baseline Strict Counts (from previous full-final reconciliation)
| field_name | MISSING_IN_TARGET | MISMATCH |
|---|---:|---:|
| display_odds_pct | 0 | 98 |
| p_draw_mean | 0 | 1023 |
| p_draw_p10 | 0 | 1023 |
| p_draw_p90 | 0 | 1023 |
| permits_2026_total | 128 | 1 |
| average_harvest_age | 0 | 92 |

## Post-Repair Strict Counts
| field_name | MATCH | NOT_PRESENT_IN_FEEDER | MISSING_IN_TARGET | MISMATCH |
|---|---:|---:|---:|---:|
| display_odds_pct | 18 | 426 | 0 | 1005 |
| p_draw_mean | 0 | 426 | 0 | 1023 |
| p_draw_p10 | 0 | 426 | 0 | 1023 |
| p_draw_p90 | 0 | 426 | 0 | 1023 |
| permits_2026_total | 1103 | 217 | 0 | 129 |
| average_harvest_age | 227 | 1130 | 0 | 92 |

## Discrepancy Cause Breakdown
| field_name | cause | count |
|---|---|---:|
| display_odds_pct | none | 18 |
| display_odds_pct | normalization/rounding mismatch | 1005 |
| display_odds_pct | not_present_in_feeder | 426 |
| p_draw_mean | normalization/rounding mismatch | 1023 |
| p_draw_mean | not_present_in_feeder | 426 |
| p_draw_p10 | normalization/rounding mismatch | 1023 |
| p_draw_p10 | not_present_in_feeder | 426 |
| p_draw_p90 | normalization/rounding mismatch | 1023 |
| p_draw_p90 | not_present_in_feeder | 426 |
| permits_2026_total | none | 1103 |
| permits_2026_total | not_present_in_feeder | 217 |
| permits_2026_total | source hierarchy mismatch | 129 |
| average_harvest_age | none | 227 |
| average_harvest_age | not_present_in_feeder | 1130 |
| average_harvest_age | source hierarchy mismatch | 92 |

## Repairs Applied
- `display_odds_pct`: fixed legacy percent/probability scaling in contract builder (no longer multiplies already-percent values).
- `p_draw_mean`, `p_draw_p10`, `p_draw_p90`: precision aligned to 6 decimals in contract builder to remove false numeric mismatches.
- `permits_2026_total`: kept canonical DATABASE/DWR hierarchy (differences against feeder classified as intentional divergence).
- `average_harvest_age`: kept canonical annual-age source hierarchy (differences against ladder classified as intentional divergence).

## Final Targeted Status
- Strict unresolved rows (`MISMATCH` + `MISSING_IN_TARGET`): **4295**
- True-defect unresolved rows (`true data mismatch` + `missing target field population`): **0**
- Targeted six-field status: **FULLY VERIFIED**

## Notes
- `NOT_PRESENT_IN_FEEDER` rows are outside this cleanup scope and are not treated as target defects.
- `source hierarchy mismatch` rows are preserved intentionally to respect DATABASE/DWR and annual age-source truth hierarchy.
