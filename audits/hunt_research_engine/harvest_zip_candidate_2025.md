# 2025 Harvest ZIP Candidate Audit

Read-only audit of the external `HUNTS` 2025-for-2026 harvest ZIP against the active HUNT-BUILDER package.

## Summary

- Result: `PASS_ARCHIVE_MATCHES_ACTIVE_PACKAGE`.
- External source path: `C:\Users\tyler\Desktop\GitHub\HUNTS\pipeline\RAW\hunt_unit_database\2026\csv\HARVEST REPORT\2025 HARVEST DATA.zip`.
- External source SHA256: `4ee4ccc904c56fb62159314743d9f5e034c2ea757d81f1924317bf2cf7ee1fc1`.
- ZIP members checked: `18`.
- Members matching active local raw package: `16`.
- Extra helper members not promoted: `2`.
- Members requiring review: `0`.
- Harvest truth rows for 2025: `10122`.
- Harvest truth hunt codes for 2025: `1127`.
- Engine harvest feature rows for 2025: `1127`.
- 2026 feature model rows using 2025 harvest history: `1306`.
- 2026 feature model rows using 2026 source year: `0`.

## Promotion Decision

- Decision: `NO_COPY_NEEDED`.
- Reason: The ZIP's core harvest CSV/report/SQLite members match the active HUNT-BUILDER raw package byte-for-byte. Extra workbook/rejected-row helper files are archive evidence only and are not needed by the engine feeder contract.

## ZIP Member Inventory

| Member | Class | Rows | Hunt Codes | Local Match Status | Recommendation |
| --- | --- | ---: | ---: | --- | --- |
| harvest_quality_features_by_hunt_code_2025_for_2026.csv | HARVEST_CSV | 1120 | 1120 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_BISON_hunt_success.csv | HARVEST_CSV | 18 | 18 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_DEER_hunt_success.csv | HARVEST_CSV | 418 | 418 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_DESERT_BIGHORN_SHEEP_hunt_success.csv | HARVEST_CSV | 25 | 25 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_ELK_hunt_success.csv | HARVEST_CSV | 455 | 455 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_MOOSE_hunt_success.csv | HARVEST_CSV | 44 | 44 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_MOUNTAIN_GOAT_hunt_success.csv | HARVEST_CSV | 18 | 18 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_PRONGHORN_hunt_success.csv | HARVEST_CSV | 121 | 121 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_ROCKY_MOUNTAIN_BIGHORN_SHEEP_hunt_success.csv | HARVEST_CSV | 21 | 21 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_all_long.csv | HARVEST_CSV | 1120 | 1120 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_database.xlsx | WORKBOOK_HELPER | 0 | 0 | ZIP_EXTRA_HELPER_NOT_PROMOTED | Helper artifact is not required for engine/runtime ingestion; keep as external archive evidence unless explicitly requested. |
| harvest_results_2025_for_2026_database_report.json | PACKAGE_REPORT | 0 | 0 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_database_report.md | PACKAGE_REPORT | 0 | 0 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_hunt_code_keyed.csv | HARVEST_CSV | 1120 | 1120 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_rejected_rows_for_review.csv | REVIEW_HELPER | 6 | 0 | ZIP_EXTRA_HELPER_NOT_PROMOTED | Helper artifact is not required for engine/runtime ingestion; keep as external archive evidence unless explicitly requested. |
| harvest_results_2025_for_2026_source_inventory.csv | HARVEST_CSV | 1 | 0 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| harvest_results_2025_for_2026_summary.csv | HARVEST_CSV | 29 | 0 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |
| utah_harvest_results_2025_for_2026.sqlite | SQLITE_SUPPORT | 0 | 0 | ZIP_MATCHES_ACTIVE_LOCAL_RAW | Core active package already has this exact file. |

## Guardrail

This 2025-for-2026 harvest package is observed 2025 harvest history for the 2026 model. It must not overwrite DATABASE.csv, permit quota, draw odds, or p_draw.
