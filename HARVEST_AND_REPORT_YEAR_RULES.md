# Harvest And Report Year Rules (Utah Hunt Model)

## Core rule
For `draw_odds` and `harvest_report` files:
- `reported_hunt_year` = the year the hunt/harvest actually occurred (from file title/content)
- `model_target_year` = `reported_hunt_year + 1`

This matches predictive use: prior completed season informs the following draw year.

## Your examples
- `2023-harvest-data` -> reported year `2023` -> model target year `2024`
- `22_bg_report` -> reported year `2022` -> model target year `2023`
- `2023_le_oial_all` -> reported year `2023` -> model target year `2024`

## Important distinction
- Folder year (`publish_year`) is storage/provenance context.
- Reported hunt year drives modeling alignment.
- They can differ without being wrong.
- Naming note: many legacy files/folders say `draw_odds`, but semantically these are `draw_results` inputs for the next prediction year.

## Recommended practice
1. Keep raw files for provenance (do not blindly bulk-move).
2. Always compute and store:
   - `publish_year`
   - `reported_hunt_year_inferred`
   - `model_target_year`
3. Flag only true anomalies for manual review:
   - reported year cannot be inferred
   - reported year appears in the future relative to storage year

## Current implementation in repo
Script:
- `pipeline/scripts/ingest/rebuild_model_year_manifest.py`

Manifest output:
- `pipeline/manifests/pdf_model_ready_manifest_with_target_year_v3.csv`

Manual review list:
- `processed_data/pdf_year_manual_review.csv`

## 2024 harvest database integration rule

The 2024 harvest-results database is historical quality data for the 2026 prediction engine. It is not a 2026 permit-allocation source.

Canonical command:

```bash
python -m engine.utah.quality.build_harvest_quality_history --model-target-year 2026 --years 2024,2025 --update-predictive
```

Expected outputs:

- `data_truth/harvest_results_truth/harvest_2024_source_inventory.csv`
- `data_truth/harvest_results_truth/harvest_2024_source_inventory.json`
- `data_truth/harvest_results_truth/harvest_2024_source_inventory.md`
- `data_truth/harvest_results_truth/normalized/harvest_results_2024_for_2026_long.csv`
- `data_truth/harvest_results_truth/normalized/harvest_results_2024_for_2026_rejects.csv`
- `data_truth/harvest_results_truth/normalized/harvest_results_2024_for_2026_report.json`
- `data_model/quality/harvest_quality_2024_for_2026.csv`
- `data_model/quality/harvest_quality_2024_for_2026_vs_database.csv`
- `data_model/quality/harvest_quality_history_for_2026.csv`
- `data_model/quality/harvest_quality_2024_2025_features_for_2026.csv`
- `data_model/quality/harvest_quality_history_for_2026_report.json`
- `processed_data/harvest_2024_integration_audit.json`
- `processed_data/harvest_2024_integration_audit.md`

Safeguards:

- 2024 harvest results must not populate 2026 permit quotas.
- 2024 harvest results must not become official 2026 allotments.
- 2024 harvest results must not create or modify `p_draw`, `p_draw_pct`, `p_bonus_pool`, `p_random_pool`, or `p_preference_draw`.
- 2024 + 2025 harvest history may populate additive quality/history fields such as harvest success, harvest count, hunters, average days, satisfaction, and year-over-year deltas.
- If probability fields change during harvest-quality integration, the builder must fail rather than silently write bad artifacts.
