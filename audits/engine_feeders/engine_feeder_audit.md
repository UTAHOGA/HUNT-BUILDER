# Engine Feeder Audit

Forecast year: 2026
Total contracts: 53
Production blockers: 25

## Status Counts

- `BLOCKER`: 25
- `PASS`: 28

## Blockers

- `utah_rebuild_fixtures` `data/utah/fixtures/applications_raw.csv`: missing_file
- `utah_rebuild_fixtures` `data/utah/fixtures/applicants_raw.csv`: missing_file
- `utah_rebuild_fixtures` `data/utah/fixtures/groups_raw.csv`: missing_file
- `utah_rebuild_fixtures` `data/utah/fixtures/points_raw.csv`: missing_file
- `utah_rebuild_fixtures` `data/utah/fixtures/quotas_raw.csv`: missing_file
- `utah_rebuild_fixtures` `data/utah/fixtures/draw_results_raw.csv`: missing_file
- `utah_rebuild_fixtures` `data/utah/fixtures/hunt_metadata_raw.csv`: missing_file
- `utah_rebuild_fixtures` `data/utah/fixtures/harvest_quality_raw.csv`: missing_file
- `utah_materialize_engine` `processed_data/draw_reality_view.csv`: missing_required_columns
- `utah_materialize_engine` `processed_data/point_ladder_view.csv`: missing_required_columns, duplicate_primary_keys, missing_lineage_columns
- `utah_materialize_engine` `processed_data/historical_trend_2025.csv`: duplicate_primary_keys
- `utah_materialize_engine` `processed_data/projected_bonus_draw_2026_simulated.csv`: missing_required_columns
- `utah_materialize_engine` `processed_data/harvest-metrics-2024-bg-report.csv`: missing_required_columns
- `utah_materialize_engine` `processed_data/harvest-metrics-2025-prelim.csv`: missing_required_columns
- `utah_draw_predictive` `processed_data/ml_draw_predictions_v1.csv`: null_lineage_fields
- `utah_draw_predictive` `processed_data/draw_system_coverage_report.csv`: duplicate_primary_keys
- `utah_draw_predictive` `processed_data/hunt_unit_reference_linked.csv`: null_lineage_fields
- `harvest_quality` `data_model/quality/promoted_quality_sources.csv`: missing_required_columns
- `harvest_quality` `data_model/quality/promoted_draw_sources.csv`: missing_required_columns
- `harvest_quality` `data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv`: null_lineage_fields
- `harvest_quality` `data_model/harvest_quality/harvest_results_all_years_long.csv`: duplicate_primary_keys, invalid_percent_values, null_lineage_fields
- `harvest_quality` `data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv`: null_lineage_fields
- `utah_predictive_mixed` `processed_data/ml_draw_predictions_v1.csv`: null_lineage_fields
- `utah_predictive_mixed` `processed_data/point_ladder_view.csv`: duplicate_primary_keys, missing_lineage_columns
- `utah_predictive_mixed` `data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv`: null_lineage_fields

## Feeder Results

| Status | Group | Path | Rows | Duplicate Keys | Issues |
| --- | --- | --- | ---: | ---: | --- |
| BLOCKER | utah_rebuild_fixtures | `data/utah/fixtures/applications_raw.csv` |  | 0 | missing_file |
| BLOCKER | utah_rebuild_fixtures | `data/utah/fixtures/applicants_raw.csv` |  | 0 | missing_file |
| BLOCKER | utah_rebuild_fixtures | `data/utah/fixtures/groups_raw.csv` |  | 0 | missing_file |
| BLOCKER | utah_rebuild_fixtures | `data/utah/fixtures/points_raw.csv` |  | 0 | missing_file |
| BLOCKER | utah_rebuild_fixtures | `data/utah/fixtures/quotas_raw.csv` |  | 0 | missing_file |
| BLOCKER | utah_rebuild_fixtures | `data/utah/fixtures/draw_results_raw.csv` |  | 0 | missing_file |
| BLOCKER | utah_rebuild_fixtures | `data/utah/fixtures/hunt_metadata_raw.csv` |  | 0 | missing_file |
| BLOCKER | utah_rebuild_fixtures | `data/utah/fixtures/harvest_quality_raw.csv` |  | 0 | missing_file |
| PASS | utah_materialize_engine | `processed_data/draw_reality_engine.csv` | 176753 | 0 | - |
| BLOCKER | utah_materialize_engine | `processed_data/draw_reality_view.csv` | 53176 | 0 | missing_required_columns |
| BLOCKER | utah_materialize_engine | `processed_data/point_ladder_view.csv` | 78162 | 17186 | missing_required_columns, duplicate_primary_keys, missing_lineage_columns |
| BLOCKER | utah_materialize_engine | `processed_data/historical_trend_2025.csv` | 47950 | 47138 | duplicate_primary_keys |
| BLOCKER | utah_materialize_engine | `processed_data/projected_bonus_draw_2026_simulated.csv` | 46992 | 0 | missing_required_columns |
| PASS | utah_materialize_engine | `processed_data/recommended_permits_2026.csv` | 928 | 0 | - |
| PASS | utah_materialize_engine | `processed_data/hunt_master_enriched.csv` | 51857 | 0 | - |
| BLOCKER | utah_materialize_engine | `processed_data/harvest-metrics-2024-bg-report.csv` | 647 | 0 | missing_required_columns |
| BLOCKER | utah_materialize_engine | `processed_data/harvest-metrics-2025-prelim.csv` | 1092 | 0 | missing_required_columns |
| PASS | utah_materialize_engine | `processed_data/hunt-master-canonical.json` |  | 0 | - |
| PASS | utah_bonus_predictive | `data_truth/draw_results_truth/normalized/draw_results_long.csv` | 197362 | 0 | - |
| PASS | utah_bonus_predictive | `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` | 1471 | 0 | - |
| PASS | utah_bonus_predictive | `scripts/build_runtime_draw_feed_v2.py` |  | 0 | - |
| PASS | utah_bonus_predictive | `scripts/build_predictive_bonus_engine_v1.py` |  | 0 | - |
| PASS | utah_bonus_predictive | `hunt-research.js` |  | 0 | - |
| PASS | utah_bonus_predictive | `config.js` |  | 0 | - |
| PASS | utah_bonus_predictive_skip_upstream | `data_model/runtime_drafts/predictive_bonus_engine_2026.predictions.csv` | 23835 | 0 | - |
| PASS | utah_bonus_predictive_skip_upstream | `data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv` | 23835 | 0 | - |
| PASS | utah_bonus_predictive_skip_upstream | `data_model/runtime_drafts/predictive_bonus_engine_2026.audit.csv` | 756 | 0 | - |
| PASS | utah_draw_predictive | `processed_data/draw_reality_engine_v2.csv` | 176753 | 0 | - |
| PASS | utah_draw_predictive | `processed_data/draw_reality_engine_predictive_v2.csv` | 26389 | 0 | - |
| BLOCKER | utah_draw_predictive | `processed_data/ml_draw_predictions_v1.csv` | 27940 | 0 | null_lineage_fields |
| BLOCKER | utah_draw_predictive | `processed_data/draw_system_coverage_report.csv` | 204693 | 193486 | duplicate_primary_keys |
| PASS | utah_draw_predictive | `processed_data/draw_system_coverage_report.json` |  | 0 | - |
| PASS | utah_draw_predictive | `processed_data/hunt_master_enriched.csv` | 51857 | 0 | - |
| BLOCKER | utah_draw_predictive | `processed_data/hunt_unit_reference_linked.csv` | 2997 | 0 | null_lineage_fields |
| PASS | utah_draw_predictive | `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` | 1471 | 0 | - |
| PASS | utah_draw_predictive | `data/utah/sportsman/sportsman_odds_2025.csv` | 10 | 0 | - |
| PASS | utah_draw_predictive | `data/cougar_hunt_table_official.json` |  | 0 | - |
| PASS | utah_draw_predictive | `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/black bear.csv` | 106 | 0 | - |
| PASS | utah_draw_predictive | `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/elk antlerless private lands.csv` | 27 | 0 | - |
| PASS | utah_draw_predictive | `pipeline/RAW/hunt_unit_database/2026/csv/2026_elk_general_anybull_youth.csv` | 1 | 0 | - |
| PASS | harvest_quality | `data_model/quality/raw_pdf_inventory_audit.csv` | 1286 | 0 | - |
| BLOCKER | harvest_quality | `data_model/quality/promoted_quality_sources.csv` | 253 | 0 | missing_required_columns |
| BLOCKER | harvest_quality | `data_model/quality/promoted_draw_sources.csv` | 204 | 0 | missing_required_columns |
| BLOCKER | harvest_quality | `data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv` | 5570 | 0 | null_lineage_fields |
| BLOCKER | harvest_quality | `data_model/harvest_quality/harvest_results_all_years_long.csv` | 68657 | 58254 | duplicate_primary_keys, invalid_percent_values, null_lineage_fields |
| BLOCKER | harvest_quality | `data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv` | 1471 | 0 | null_lineage_fields |
| PASS | harvest_quality | `processed_data/harvest_results_database_final_audit.json` |  | 0 | - |
| BLOCKER | utah_predictive_mixed | `processed_data/ml_draw_predictions_v1.csv` | 27940 | 0 | null_lineage_fields |
| PASS | utah_predictive_mixed | `processed_data/draw_reality_engine_predictive_v2.csv` | 26389 | 0 | - |
| BLOCKER | utah_predictive_mixed | `processed_data/point_ladder_view.csv` | 78162 | 17186 | duplicate_primary_keys, missing_lineage_columns |
| PASS | utah_predictive_mixed | `processed_data/draw_reality_engine.csv` | 176753 | 0 | - |
| BLOCKER | utah_predictive_mixed | `data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv` | 1471 | 0 | null_lineage_fields |
| PASS | utah_predictive_mixed | `processed_data/harvest_results_database_final_audit.json` |  | 0 | - |
