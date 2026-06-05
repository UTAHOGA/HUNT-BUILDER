# 2025 Harvest/Draw Ingestion Audit

Read-only alignment proof for 2025 harvest results used by the 2026 Hunt Research model.

## Summary

- Result: `PASS`.
- Reported hunt year: `2025`.
- Model target year: `2026`.
- Raw harvest CSVs checked: `13`.
- Non-harvest reference CSVs checked: `1`.
- `2025.zip` exists: `True`.
- Harvest truth rows for 2025: `10122`.
- Harvest truth hunt codes for 2025: `1127`.
- Engine harvest long rows for 2025: `10122`.
- Engine harvest feature rows for 2025: `1127`.
- Missing engine feature rows sourced from normalized truth: `0`.
- 2026 feature model rows using 2025 harvest history: `1306`.
- 2026 feature model rows using 2026 harvest source year: `0`.
- Draw truth rows for 2025: `75194`.
- Draw truth hunt codes for 2025: `1053`.
- Draw reality engine v2 rows for 2025: `75194`.
- Draw reality engine v2 matches draw truth row count: `True`.
- Legacy draw_reality_engine.csv has 2025 rows: `False`.

## Missing Engine Feature Rows

| Hunt Code | Species | Hunt Name | Source | Action |
| --- | --- | --- | --- | --- |
|  |  |  |  | No source-backed gaps found |

## Raw CSV Inventory

| CSV | Class | Rows | Hunt Codes | Reported Years | Target Years | Source Dates | Status |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| harvest_results_2025_for_2026_BISON_hunt_success.csv | HARVEST_SOURCE | 18 | 18 | 2025 | 2026 | 2026-03-06 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2025_for_2026_DEER_hunt_success.csv | HARVEST_SOURCE | 418 | 418 | 2025 | 2026 | 2026-03-06 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2025_for_2026_DESERT_BIGHORN_SHEEP_hunt_success.csv | HARVEST_SOURCE | 25 | 25 | 2025 | 2026 | 2026-03-06 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2025_for_2026_ELK_hunt_success.csv | HARVEST_SOURCE | 455 | 455 | 2025 | 2026 | 2026-03-06 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2025_for_2026_hunt_code_keyed.csv | HARVEST_SOURCE | 1120 | 1120 | 2025 | 2026 | 2026-03-06 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2025_for_2026_MOOSE_hunt_success.csv | HARVEST_SOURCE | 44 | 44 | 2025 | 2026 | 2026-03-06 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2025_for_2026_MOUNTAIN_GOAT_hunt_success.csv | HARVEST_SOURCE | 18 | 18 | 2025 | 2026 | 2026-03-06 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2025_for_2026_PRONGHORN_hunt_success.csv | HARVEST_SOURCE | 121 | 121 | 2025 | 2026 | 2026-03-06 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2025_for_2026_ROCKY_MOUNTAIN_BIGHORN_SHEEP_hunt_success.csv | HARVEST_SOURCE | 21 | 21 | 2025 | 2026 | 2026-03-06 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2025_for_2026_source_inventory.csv | HARVEST_SOURCE | 1 | 0 | 2025 | 2026 | 2026-03-06 | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2025_for_2026_summary.csv | HARVEST_SOURCE | 29 | 0 | 2025 | 2026 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_quality_features_by_hunt_code_2025_for_2026.csv | HARVEST_SOURCE | 1120 | 1120 | 2025 | 2026 |  | RAW_GENERATED_CSV_PRESENT |
| harvest_results_2025_for_2026_all_long.csv | HARVEST_SOURCE | 1120 | 1120 | 2025 | 2026 | 2026-03-06 | RAW_GENERATED_CSV_PRESENT |
| limited entry elk private lands draw odds 2025.csv | NON_HARVEST_DRAW_REFERENCE | 131 | 131 |  |  |  | RAW_GENERATED_CSV_PRESENT |

## Guardrail

The 2026-03-06 source date is the publication/report date for 2025 harvest results. These rows are valid 2025 observed harvest history for the 2026 model, not observed 2026 harvest-year data.
