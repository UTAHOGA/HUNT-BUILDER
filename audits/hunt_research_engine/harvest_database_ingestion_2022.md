# 2022 Harvest Database Ingestion Audit

Read-only alignment proof for the 2022-for-2023 harvest database package.

## Summary

- Result: `PASS`.
- Reported hunt year: `2022`.
- Model target year: `2023`.
- Raw package CSVs checked: `8`.
- Support files checked: `3`.
- `2022.zip` exists: `True`.
- Harvest truth rows for 2022: `7392`.
- Harvest truth hunt codes for 2022: `924`.
- Engine harvest long rows for 2022: `7392`.
- Engine harvest feature rows for 2022: `1050`.
- Missing engine feature rows sourced from normalized truth: `0`.
- Engine supplemental feature rows not in normalized truth feature table: `126`.
- 2026 feature model rows using 2022 harvest history: `175`.
- Draw truth rows for 2022: `18688`.
- Draw truth hunt codes for 2022: `1024`.
- Draw reality engine v2 rows for 2022: `18688`.
- Draw reality engine v2 matches draw truth row count: `True`.
- Legacy draw_reality_engine.csv rows for 2022: `18638`.
- Legacy draw_reality_engine.csv row delta vs draw truth: `-50`.

## Missing Engine Feature Rows

| Hunt Code | Species | Hunt Name | Source | Action |
| --- | --- | --- | --- | --- |
|  |  |  |  | No source-backed gaps found |

## Supplemental Engine Feature Rows

`126` engine 2022 feature rows are present beyond the normalized truth feature table. These are review-visible supplemental context rows, not missing truth rows.

## Raw CSV Inventory

| CSV | Rows | Hunt Codes | Reported Years | Target Years | Source Classes | Status |
| --- | ---: | ---: | --- | --- | --- | --- |
| harvest_quality_features_by_hunt_code_2022_for_2023.csv | 924 | 924 | 2022 | 2023 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2022_for_2023_all_long.csv | 1023 | 924 | 2022 | 2023 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2022_for_2023_antlerless.csv | 238 | 238 | 2022 | 2023 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2022_for_2023_black_bear.csv | 133 | 87 | 2022 | 2023 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2022_for_2023_cougar.csv | 53 | 0 | 2022 | 2023 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2022_for_2023_hunt_code_keyed.csv | 924 | 924 | 2022 | 2023 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2022_for_2023_le_oial_all.csv | 599 | 599 | 2022 | 2023 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2022_for_2023_summary.csv | 19 | 0 |  |  |  | RAW_GENERATED_CSV_PRESENT |

## Support Files

| File | Size Bytes | Status |
| --- | ---: | --- |
| utah_harvest_results_2022_for_2023.sqlite | 856064 | SUPPORT_FILE_PRESENT |
| harvest_results_2022_for_2023_database_report.json | 2927 | SUPPORT_FILE_PRESENT |
| harvest_results_2022_for_2023_database_report.md | 1255 | SUPPORT_FILE_PRESENT |

## Guardrail

2022 harvest rows are quality/history inputs only. They are not permit quota truth and are not direct p_draw truth.
