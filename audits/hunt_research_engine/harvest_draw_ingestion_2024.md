# 2024 Harvest/Draw Ingestion Audit

Read-only alignment proof for the 2024 draw and harvest data feeding Hunt Research.

## Summary

- Result: `PASS`.
- Reported hunt year: `2024`.
- Model target year: `2025`.
- Raw generated harvest CSVs checked: `15`.
- Harvest truth rows for 2024: `35707`.
- Harvest truth hunt codes for 2024: `1048`.
- Engine harvest long rows for 2024: `35707`.
- Engine harvest feature rows for 2024 before repair: `1048`.
- Missing engine feature rows sourced from normalized truth: `0`.
- Draw truth rows for 2024: `37128`.
- Draw truth hunt codes for 2024: `580`.
- Draw reality engine v2 rows for 2024: `37128`.
- Draw reality engine v2 matches draw truth row count: `True`.
- Legacy draw_reality_engine.csv has 2024 rows: `False`.

## Missing Engine Feature Rows

| Hunt Code | Species | Hunt Name | Source | Action |
| --- | --- | --- | --- | --- |
|  |  |  |  | No source-backed gaps found |

## Raw Generated CSV Inventory

| CSV | Rows | Hunt Codes | Status |
| --- | ---: | ---: | --- |
| big_game_oil_hunt_number_harvest_supplement_2024.csv | 385 | 385 | RAW_GENERATED_CSV_PRESENT |
| bison_oial_hunt_harvest_2024.csv | 17 | 17 | RAW_GENERATED_CSV_PRESENT |
| desert_bighorn_hunt_harvest_2024.csv | 22 | 22 | RAW_GENERATED_CSV_PRESENT |
| elk_general_season_harvest_additional_2024.csv | 120 | 0 | RAW_GENERATED_CSV_PRESENT |
| harvest_quality_features_by_hunt_code_2024_for_2025.csv | 1039 | 1039 | RAW_GENERATED_CSV_PRESENT |
| harvest_quality_features_elk_age_2024_for_2025.csv | 26 | 0 | RAW_GENERATED_CSV_PRESENT |
| harvest_quality_features_extra_oil_2024_for_2025.csv | 32 | 0 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2024_for_2025_all_long.csv | 2767 | 1039 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2024_for_2025_ANTLERLESS_DEER.csv | 42 | 21 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2024_for_2025_ANTLERLESS_ELK.csv | 825 | 184 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2024_for_2025_BISON.csv | 16 | 16 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2024_for_2025_BLACK_BEAR.csv | 87 | 87 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2024_for_2025_DESERT_BIGHORN_SHEEP.csv | 21 | 21 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2024_for_2025_ELK.csv | 860 | 215 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2024_for_2025_extra_goat_bison_desert_sheep_long.csv | 676 | 56 | RAW_GENERATED_CSV_PRESENT |

## Guardrail

2024 harvest rows are quality/history inputs only. They are not permit quota truth and are not direct p_draw truth.
