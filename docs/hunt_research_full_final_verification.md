# Hunt Research Full Final Verification

Generated: 2026-06-01T11:56:53.085518

## Scope
- Full-field feeder-to-contract reconciliation rerun across all mapped Hunt Research fields.
- Runtime publication check rerun across all mapped fields.

## Universe Validation
- DATABASE hunt-code universe: **1449**
- Contract hunt-code universe: **1449**
- Universe aligned: **YES**

## Full-Field Reconciliation Summary
- Mapped fields: **28**
- Total comparison rows: **40572**

| Status | Count |
|---|---:|
| MATCH | 22151 |
| IMPROVED_FROM_CANONICAL_SOURCE | 1738 |
| MISSING_IN_TARGET | 128 |
| MISMATCH | 3260 |
| NOT_PRESENT_IN_FEEDER | 13295 |
| INTENTIONALLY_RETIRED | 0 |
| REVIEW_REQUIRED | 0 |

## Runtime Publication Summary (Mapped Fields)
| Publication status | Count |
|---|---:|
| PUBLISHED | 28 |
| LEGACY_ONLY | 0 |
| MISSING_IN_TARGET | 0 |
| REVIEW_REQUIRED | 0 |

## Unresolved Field Checks
- Reconciliation unresolved (`MISSING_IN_TARGET` + `MISMATCH` + `REVIEW_REQUIRED`): **3388**
- Runtime unresolved (`LEGACY_ONLY` + `MISSING_IN_TARGET` + `REVIEW_REQUIRED`): **0**
- Prior blocker-set mismatches introduced: **0**
- Prior blocker-set missing-in-target introduced: **0**

## Final Status
**PARTIALLY VERIFIED**

## Remaining Unresolved Fields
| field_name | MISSING_IN_TARGET | MISMATCH | REVIEW_REQUIRED |
|---|---:|---:|---:|
| display_odds_pct | 0 | 98 | 0 |
| p_draw_mean | 0 | 1023 | 0 |
| p_draw_p10 | 0 | 1023 | 0 |
| p_draw_p90 | 0 | 1023 | 0 |
| permits_2026_total | 128 | 1 | 0 |
| average_harvest_age | 0 | 92 | 0 |

## Source Notes
- Master source used for verification: `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/pipeline/RAW/hunt_unit_database/2026/csv/hunt_master_canonical_2026_built.csv`
- Local `processed_data/hunt_master_enriched.csv` LFS pointer detected: **YES**
- Management fields verified against canonical management-context source.
