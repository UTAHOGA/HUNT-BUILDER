# 2024 Harvest Candidate Package Audit

Read-only review of the richer 2024 harvest packages supplied for possible Hunt Research use.

## Summary

- Result: `PASS_REVIEW_ONLY`.
- Candidate CSV files checked: `34`.
- Candidate report files loaded: `3`.
- Current normalized 2024 feature rows: `1048`.
- Current model 2024 feature rows: `1048`.
- Current model rows with observed `average_age`: `328`.
- Current truth rows with observed `average_age`: `0`.
- 2026 feature model rows using 2024 harvest history: `1147`.

## Recommendation

Do not wholesale replace current 2024 harvest feeders. Keep the full database package as stronger source evidence, and treat elk-age/OIL supplements as reviewed context-feature candidates because several rows are unit-level rather than direct hunt_code rows.

## Package Coverage

| Package | Candidate Hunt Codes | New Codes vs Current Truth | Current Truth Codes Missing From Candidate | Sample Missing From Candidate |
| --- | ---: | ---: | ---: | --- |
| database_package | 1039 | 0 | 9 | DS6623|STATEWIDE_SPORTSMAN_CONSERVATION|TK1003|TK1004|TK1005|TK1006|TK1007|TK1018|TK1021 |
| elk_age_supplement | 1040 | 0 | 8 | STATEWIDE_SPORTSMAN_CONSERVATION|TK1003|TK1004|TK1005|TK1006|TK1007|TK1018|TK1021 |
| extra_oil_supplement | 1041 | 0 | 7 | TK1003|TK1004|TK1005|TK1006|TK1007|TK1018|TK1021 |

## Candidate File Classifications

| Package | File | Rows 2024 | Hunt Codes | Classification | Recommendation |
| --- | --- | ---: | ---: | --- | --- |
| database_package | harvest_quality_features_by_hunt_code_2024_for_2025.csv | 1039 | 1039 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_all_long.csv | 2767 | 1039 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_hunt_code_keyed.csv | 1039 | 1039 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_source_inventory.csv | 25 | 0 | CONTEXT_PROMOTE_UNIT_LEVEL_REVIEW | Observed age/context rows exist but lack hunt_code; use only through reviewed unit-to-hunt mapping. |
| database_package | harvest_results_2024_for_2025_summary.csv | 11 | 0 | CONTEXT_HOLD_NO_HUNT_CODE | Rows have no direct hunt_code key, so they cannot replace hunt-code feeder rows. |
| database_package | harvest_unit_trend_rows_2024_for_2025.csv | 1523 | 0 | CONTEXT_HOLD_NO_HUNT_CODE | Rows have no direct hunt_code key, so they cannot replace hunt-code feeder rows. |
| database_package | harvest_results_2024_for_2025_ANTLERLESS_DEER.csv | 42 | 21 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_ANTLERLESS_ELK.csv | 825 | 184 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_BISON.csv | 16 | 16 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_BLACK_BEAR.csv | 87 | 87 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_DESERT_BIGHORN_SHEEP.csv | 21 | 21 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_ELK.csv | 860 | 215 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_MOOSE.csv | 37 | 37 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_MOUNTAIN_GOAT.csv | 17 | 17 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_MULE_DEER.csv | 668 | 334 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_PRONGHORN.csv | 174 | 87 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| database_package | harvest_results_2024_for_2025_ROCKY_MOUNTAIN_BIGHORN_SHEEP.csv | 20 | 20 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| elk_age_supplement | big_game_oil_hunt_number_harvest_supplement_2024.csv | 385 | 385 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| elk_age_supplement | elk_average_age_limited_entry_units_2015_2024.csv | 26 | 0 | CONTEXT_PROMOTE_UNIT_LEVEL_REVIEW | Observed age/context rows exist but lack hunt_code; use only through reviewed unit-to-hunt mapping. |
| elk_age_supplement | elk_general_season_harvest_additional_2024.csv | 120 | 0 | CONTEXT_PROMOTE_UNIT_LEVEL_REVIEW | Unit-level quality/context metrics exist but lack hunt_code; use only through reviewed unit-to-hunt mapping. |
| elk_age_supplement | harvest_quality_features_elk_age_2024_for_2025.csv | 26 | 0 | CONTEXT_PROMOTE_UNIT_LEVEL_REVIEW | Observed age/context rows exist but lack hunt_code; use only through reviewed unit-to-hunt mapping. |
| elk_age_supplement | harvest_results_2024_for_2025_all_long_enhanced.csv | 2913 | 1039 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| extra_oil_supplement | bison_oial_hunt_harvest_2024.csv | 17 | 17 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| extra_oil_supplement | bison_statewide_1950_2024.csv | 1 | 0 | CONTEXT_PROMOTE_UNIT_LEVEL_REVIEW | Unit-level quality/context metrics exist but lack hunt_code; use only through reviewed unit-to-hunt mapping. |
| extra_oil_supplement | desert_bighorn_hunt_harvest_2024.csv | 22 | 22 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| extra_oil_supplement | desert_bighorn_ram_harvest_by_unit_2015_2024.csv | 17 | 0 | CONTEXT_HOLD_NO_HUNT_CODE | Rows have no direct hunt_code key, so they cannot replace hunt-code feeder rows. |
| extra_oil_supplement | desert_bighorn_statewide_1967_2024.csv | 1 | 0 | CONTEXT_PROMOTE_UNIT_LEVEL_REVIEW | Unit-level quality/context metrics exist but lack hunt_code; use only through reviewed unit-to-hunt mapping. |
| extra_oil_supplement | desert_bighorn_trend_count_by_unit_2015_2024.csv | 15 | 0 | CONTEXT_HOLD_NO_HUNT_CODE | Rows have no direct hunt_code key, so they cannot replace hunt-code feeder rows. |
| extra_oil_supplement | harvest_quality_features_extra_oil_2024_for_2025.csv | 32 | 0 | CONTEXT_PROMOTE_UNIT_LEVEL_REVIEW | Unit-level quality/context metrics exist but lack hunt_code; use only through reviewed unit-to-hunt mapping. |
| extra_oil_supplement | harvest_results_2024_for_2025_all_long_enhanced_v2.csv | 3031 | 1041 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| extra_oil_supplement | harvest_results_2024_for_2025_extra_goat_bison_desert_sheep_long.csv | 118 | 56 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| extra_oil_supplement | mountain_goat_billy_harvest_by_unit_2015_2024.csv | 15 | 0 | CONTEXT_HOLD_NO_HUNT_CODE | Rows have no direct hunt_code key, so they cannot replace hunt-code feeder rows. |
| extra_oil_supplement | mountain_goat_hunt_harvest_2024.csv | 17 | 17 | REFERENCE_ALREADY_COVERED | Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement. |
| extra_oil_supplement | mountain_goat_nanny_harvest_by_unit_2015_2024.csv | 15 | 0 | CONTEXT_HOLD_NO_HUNT_CODE | Rows have no direct hunt_code key, so they cannot replace hunt-code feeder rows. |

## Guardrail

Candidate 2024 harvest packages may support harvest quality/history and unit-level context only. They must not overwrite permit quota, draw odds, p_draw, or DATABASE.csv.
