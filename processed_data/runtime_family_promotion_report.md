# Runtime Family Promotion Report

- promotion_decision: APPROVED_RUNTIME_PROMOTION_2026_06_29
- promotion_ready: True
- promoted_family_count: 6
- promoted_row_count: 3546
- permit_source_field_contract: NOT_REQUIRED_FOR_RUNTIME_PROMOTION; permit authority is carried by permits_2026_* fields, public_permits_2026 where applicable, and reason_codes.

| Family | Status | Rows | Hunt codes | Duplicate keys | Source report |
| --- | --- | ---: | ---: | ---: | --- |
| SPORTSMAN_RANDOM_ONLY | PROMOTED_TO_RUNTIME | 10 | 10 | 0 | processed_data\sportsman_permit_report.json |
| YOUTH_GENERAL_ANY_BULL_ELK | PROMOTED_TO_RUNTIME | 2 | 1 | 0 | processed_data\youth_draw_report.json |
| PREFERENCE_DEDICATED_HUNTER_DEER | PROMOTED_TO_RUNTIME | 503 | 31 | 0 | processed_data\dedicated_hunter_report.json |
| BEAR_DRAW | PROMOTED_TO_RUNTIME | 2615 | 100 | 0 | processed_data\bear_report.json |
| BONUS_TURKEY | PROMOTED_TO_RUNTIME | 184 | 9 | 0 | processed_data\turkey_bonus_report.json |
| YOUTH_TURKEY_SET_ASIDE | PROMOTED_TO_RUNTIME | 232 | 5 | 0 | processed_data\youth_turkey_report.json |

## Excluded From This Promotion

- MAX_WEIGHTED_SPLIT_PENDING_CHALLENGE_TEST
- CWMU_CONSERVATION_PRIVATE_LAND_REFERENCE_ONLY

Promoted to active runtime: 2026-07-02T19:36:04+00:00
Promotion source audit: audits/scorable_engine_rows/20260702_bear_pending_reconciled_2027
Promotion gate audit: audits/runtime_production_gate/20260702_133421_bear_reconciled_candidate_gate
