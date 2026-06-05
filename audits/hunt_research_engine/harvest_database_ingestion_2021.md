# 2021 Harvest Database Ingestion Audit

Read-only alignment proof for the 2021-for-2022 harvest package.

## Summary

- Result: `PASS`.
- Reported hunt year: `2021`.
- Model target year: `2022`.
- Raw package CSVs checked: `15`.
- Support files checked: `3`.
- `2021.zip` exists: `True`.
- Harvest truth rows for 2021: `7944`.
- Harvest truth hunt codes for 2021: `974`.
- Engine harvest long rows for 2021: `7944`.
- Engine harvest feature rows for 2021: `974`.
- Missing engine feature rows sourced from normalized truth: `0`.
- Engine supplemental feature rows not in normalized truth feature table: `0`.
- 2026 feature model rows using 2021 harvest history: `56`.
- Draw truth rows for 2021: `27519`.
- Draw truth hunt codes for 2021: `550`.
- Draw reality engine v2 rows for 2021: `27519`.
- Draw reality engine v2 matches draw truth row count: `True`.
- Legacy draw_reality_engine.csv has 2021 rows: `False`.

## Missing Engine Feature Rows

| Hunt Code | Species | Hunt Name | Source | Action |
| --- | --- | --- | --- | --- |
|  |  |  |  | No source-backed gaps found |

## Supplemental Engine Feature Rows

`0` engine 2021 feature rows are present beyond the normalized truth feature table.

## Raw CSV Inventory

| CSV | Rows | Hunt Codes | Reported Years | Target Years | Status |
| --- | ---: | ---: | --- | --- | --- |
| harvest_results_2021_for_2022_mountain_goat.csv | 17 | 17 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_pronghorn.csv | 85 | 85 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_rocky_mountain_bighorn_sheep.csv | 18 | 18 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_summary.csv | 11 | 0 |  |  | RAW_GENERATED_CSV_PRESENT |
| harvest_quality_features_by_hunt_code_2021_for_2022.csv | 974 | 974 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_all_long.csv | 1047 | 974 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_antlerless_deer.csv | 27 | 27 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_antlerless_elk.csv | 186 | 186 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_bison.csv | 13 | 13 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_black_bear.csv | 126 | 91 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_deer.csv | 344 | 306 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_desert_bighorn_sheep.csv | 21 | 21 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_elk.csv | 172 | 172 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_hunt_code_keyed.csv | 974 | 974 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2021_for_2022_moose.csv | 38 | 38 | 2021 | 2022 | RAW_GENERATED_CSV_PRESENT |

## Support Files

| File | Size Bytes | Status |
| --- | ---: | --- |
| utah_harvest_results_2021_for_2022.sqlite | 819200 | SUPPORT_FILE_PRESENT |
| harvest_results_2021_for_2022_database_report.json | 2005 | SUPPORT_FILE_PRESENT |
| harvest_results_2021_for_2022_database_report.md | 538 | SUPPORT_FILE_PRESENT |

## Guardrail

2021 harvest rows are quality/history inputs only. They are not permit quota truth and are not direct p_draw truth.
