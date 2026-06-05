# 2023 Harvest Database Ingestion Audit

Read-only alignment proof for the 2023 all-species harvest database package.

## Summary

- Result: `PASS`.
- Reported hunt year: `2023`.
- Model target year: `2024`.
- Raw package CSVs checked: `15`.
- Support files checked: `3`.
- `2023.zip` exists: `True`.
- Harvest truth rows for 2023: `7492`.
- Harvest truth hunt codes for 2023: `1078`.
- Engine harvest long rows for 2023: `7492`.
- Engine harvest feature rows for 2023: `1179`.
- Missing engine feature rows sourced from normalized truth: `0`.
- Engine supplemental feature rows not in normalized truth feature table: `101`.
- 2026 feature model rows using 2023 harvest history: `1181`.
- Draw truth rows for 2023: `17128`.
- Draw truth hunt codes for 2023: `1010`.
- Draw reality engine v2 rows for 2023: `17128`.
- Draw reality engine v2 matches draw truth row count: `True`.
- Legacy draw_reality_engine.csv matches draw truth row count: `True`.

## Missing Engine Feature Rows

| Hunt Code | Species | Hunt Name | Source | Action |
| --- | --- | --- | --- | --- |
|  |  |  |  | No source-backed gaps found |

## Supplemental Engine Feature Rows

`101` engine 2023 feature rows are present beyond the normalized truth feature table. These are review-visible supplemental context rows, not missing truth rows.

## Raw CSV Inventory

| CSV | Rows | Hunt Codes | Reported Years | Target Years | Source Classes | Status |
| --- | ---: | ---: | --- | --- | --- | --- |
| harvest_results_2023_ROCKY_MOUNTAIN_BIGHORN_SHEEP_hunt_success.csv | 14 | 14 | 2023 | 2024 | harvest_results | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2023_species_summary.csv | 8 | 0 | 2023 | 2024 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_location_hunt_code_crosswalk_2023_bighorn_sheep.csv | 138 | 3 | 2023 |  |  | RAW_GENERATED_CSV_PRESENT |
| harvest_quality_features_bighorn_by_hunt_code_2023.csv | 30 | 30 | 2023 | 2024 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_quality_features_by_hunt_code_all_species_2023.csv | 592 | 592 | 2023 | 2024 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2023_all_species_hunt_success_long.csv | 592 | 592 | 2023 | 2024 | harvest_results | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2023_bighorn_sheep_hunt_success_aggregate.csv | 30 | 30 | 2023 | 2024 | harvest_results | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2023_bighorn_sheep_measurements_crosswalked.csv | 138 | 3 | 2023 | 2024 | harvest_measurements | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2023_BISON_hunt_success.csv | 18 | 18 | 2023 | 2024 | harvest_results | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2023_DEER_hunt_success.csv | 192 | 192 | 2023 | 2024 | harvest_results | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2023_DESERT_BIGHORN_SHEEP_hunt_success.csv | 16 | 16 | 2023 | 2024 | harvest_results | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2023_ELK_hunt_success.csv | 211 | 211 | 2023 | 2024 | harvest_results | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2023_MOOSE_hunt_success.csv | 36 | 36 | 2023 | 2024 | harvest_results | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2023_MOUNTAIN_GOAT_hunt_success.csv | 17 | 17 | 2023 | 2024 | harvest_results | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2023_PRONGHORN_hunt_success.csv | 88 | 88 | 2023 | 2024 | harvest_results | RAW_GENERATED_CSV_PRESENT |

## Support Files

| File | Size Bytes | Status |
| --- | ---: | --- |
| utah_harvest_results_2023_all_species.sqlite | 1089536 | SUPPORT_FILE_PRESENT |
| harvest_results_2023_all_species_database_report.json | 8274 | SUPPORT_FILE_PRESENT |
| harvest_results_2023_all_species_database_report.md | 2015 | SUPPORT_FILE_PRESENT |

## Guardrail

2023 harvest rows are quality/history inputs only. They are not permit quota truth and are not direct p_draw truth.
