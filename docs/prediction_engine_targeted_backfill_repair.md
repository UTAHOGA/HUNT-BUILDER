# Prediction Engine Targeted Backfill Repair

Generated: 2026-06-04T09:17:32Z

## Scope

This pass started with `REVIEW_TARGETED_BACKFILL` rows from `processed_data/audits/prediction_engine_feeder_blank_cell_audit.csv`.

The repair was intentionally limited to exact `hunt_code` backfills from `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` into derived/runtime feeder files. It did not modify `DATABASE.csv`, normalized draw truth, or model probability fields.

## Files Repaired

The following full feeder files were repaired locally and republished to their canonical Cloudflare R2 URLs:

| File | Applied cells |
| --- | ---: |
| `processed_data/point_ladder_view.csv` | 376,260 |
| `processed_data/draw_reality_engine_predictive_v2.csv` | 119,319 |
| `processed_data/ml_draw_predictions_v1.csv` | 114,452 |
| `processed_data/hunt_master_enriched.csv` | 88,700 |
| `processed_data/draw_reality_engine.csv` | 60,566 |
| `processed_data/hunt_unit_reference_linked.csv` | 4,524 |

Total source-backed cells applied: 763,821.

## Fields Repaired

Approved backfill families:

- `hunt_name`, `species`, `sex_type`, `weapon`, `hunt_class`
- `draw_system_type` from `draw_2026_system_type`
- `permit_allotment_2026_res`, `permit_allotment_2026_nr`, `permit_allotment_2026_total`
- `permits_2026_res`, `permits_2026_nr`, `permits_2026_total`
- `public_permits_2026`, `quota_2026_total`
- `quota_source_status`, `quota_source_year`, `quota_source_file`
- `truth_source_file`, `truth_source_status`

All fills required:

- blank target cell
- exact `hunt_code` match in `DATABASE.csv`
- nonblank source value
- a permitted source-backed field rule in `scripts/repair-prediction-feeder-targeted-backfill.py`

## Deferred Fields

The pass intentionally did not fill probability, prior-year draw-result, pool-flag, or model-status blanks. Those need model/draw-truth logic rather than simple current-database backfill.

Deferred families include:

- `p_draw*`, `p_max_pool_mean`, `p_random_mean`
- `random_draw_odds_2026`, `display_odds*`
- `applicants*`, `prior_year_*`, `success_ratio`
- `quota_2026_max_pool`, `quota_2026_random_pool`
- `projected_2026_*`, `is_2026_*`
- `probability_model`, `draw_model_class`, `availability_status`, `algorithm_status`

## Explicitly Not Modified

- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`: truth source, not modified.
- `data_truth/draw_results_truth/normalized/draw_results_long.csv`: normalized draw truth, not modified.
- `data_model/runtime_drafts/draw_reality_engine_v2.csv`: historical runtime draft, not modified from current-year `DATABASE.csv`.
- `processed_data/draw_system_coverage_report.csv`: generated coverage report, not modified.

## R2 Publication

Uploaded and verified:

- `https://json.uoga.workers.dev/processed_data/draw_reality_engine.csv`
- `https://json.uoga.workers.dev/processed_data/draw_reality_engine_predictive_v2.csv`
- `https://json.uoga.workers.dev/processed_data/point_ladder_view.csv`
- `https://json.uoga.workers.dev/processed_data/hunt_master_enriched.csv`
- `https://json.uoga.workers.dev/processed_data/hunt_unit_reference_linked.csv`
- `https://json.uoga.workers.dev/processed_data/ml_draw_predictions_v1.csv`

Both runtime manifests were updated with refreshed size and timestamp metadata:

- `public/data/runtime-manifest.json`
- `data/runtime-manifest.json`

## Audit Output

The comprehensive count audit is:

- `processed_data/audits/prediction_engine_targeted_backfill_summary.csv`

No row-sample audit file is retained. This was a comprehensive engine repair, not a sample export.
