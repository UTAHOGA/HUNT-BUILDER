# Rolling Historical Prediction Backtest Plan

## Purpose

Because the feeder files have now been aligned across years, old archived prediction files are not required. The cleaner test is to regenerate historical predictions using only data available before each target year, then compare to the official raw draw results for that target year.

## No-Leakage Rule

For target year N, the model may use draw-result and harvest information only through year N-1. It may not use target-year actual draw results or any file derived from target-year results.

## Backtest Year Plan

### Target 2020
- Training cutoff: 2019
- Allowed draw result years: 2019
- Forbidden leakage years: 2020;2021;2022;2023;2024;2025;2026;2027;2028;2029
- Best actual candidate: `data_truth/draw_results_truth/normalized/draw_results_2019_for_2020_candidate_promotion_file_records.csv`
- Status: READY_TO_RUN_RETROSPECTIVE_WITH_EXTRA_SOURCE
- Note: This year is not in `draw_results_long.csv`; it is runnable through the materializer's `--extra-source-draw-results` option without merging the file into production truth.

### Target 2021
- Training cutoff: 2020
- Allowed draw result years: 2020
- Forbidden leakage years: 2021;2022;2023;2024;2025;2026;2027;2028;2029
- Best actual candidate: `data_truth/draw_results_truth/normalized/draw_results_2020_for_2021_candidate_promotion_file_records_STRICT_USABLE_PLUS_SPORTSMAN.csv`
- Status: READY_TO_RUN_RETROSPECTIVE_WITH_EXTRA_SOURCE
- Note: This year is not in `draw_results_long.csv`; it is runnable through the materializer's `--extra-source-draw-results` option without merging the strict usable 2020-for-2021 source into production truth.
- Validation evidence: `data_truth/draw_results_truth/validation/draw_results_2020_for_2021_materializer_schema_validation_summary.json`

### Target 2022
- Training cutoff: 2021
- Allowed draw result years: 2021
- Forbidden leakage years: 2022;2023;2024;2025;2026;2027;2028;2029
- Best actual candidate: `data_truth/draw_results_truth/normalized/draw_results_2021_for_2022_candidate_promotion_file_records.csv`
- Status: READY_TO_RUN_RETROSPECTIVE

### Target 2023
- Training cutoff: 2022
- Allowed draw result years: 2021;2022
- Forbidden leakage years: 2023;2024;2025;2026;2027;2028;2029
- Best actual candidate: `data_truth/draw_results_truth/normalized/draw_results_2022_for_2023_candidate_promotion_file_records.csv`
- Status: READY_TO_RUN_RETROSPECTIVE

### Target 2024
- Training cutoff: 2023
- Allowed draw result years: 2021;2022;2023
- Forbidden leakage years: 2024;2025;2026;2027;2028;2029
- Best actual candidate: `data_truth/draw_results_truth/normalized/draw_results_2023_for_2024_candidate_promotion_file_records.csv`
- Status: READY_TO_RUN_RETROSPECTIVE

### Target 2025
- Training cutoff: 2024
- Allowed draw result years: 2021;2022;2023;2024
- Forbidden leakage years: 2025;2026;2027;2028;2029
- Best actual candidate: `data_truth/draw_results_truth/normalized/draw_results_2024_for_2025_candidate_promotion_file_records.csv`
- Status: READY_TO_RUN_RETROSPECTIVE

### Target 2026
- Training cutoff: 2025
- Allowed draw result years: 2021;2022;2023;2024;2025
- Forbidden leakage years: 2026;2027;2028;2029
- Best actual candidate: HOLD until actual 2026 draw results are published and validated
- Status: HOLD_UNTIL_ACTUAL_RESULTS_PUBLISHED

## Engine Capability Check

- `engine/utah_bonus_predictive/materialize.py` exists=True rolling_support=True forecast_year=True history_years=True
- `engine/utah_predictive_mixed/materialize.py` exists=True rolling_support=False forecast_year=False history_years=False
- `engine/utah_draw_predictive/availability_review.py` exists=True rolling_support=True forecast_year=True history_years=True
- `scripts/rebuild-runtime-hunt-master-and-split.py` exists=True rolling_support=False forecast_year=False history_years=False
- `tools/verify_prediction_engine_targeted_backfill.py` exists=True rolling_support=True forecast_year=True history_years=False
- `rebuild-engine-from-projection.js` exists=True rolling_support=False forecast_year=False history_years=False

## Feeder Year Coverage

- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` rows=1471 years=2026
- `data_truth/draw_results_truth/normalized/draw_results_long.csv` rows=176753 years=2021;2022;2023;2024;2025;2026
- `data_truth/draw_results_truth/normalized/draw_results_2019_for_2020_candidate_promotion_file_records.csv` rows=58155 years=2019 extra retrospective source for target 2020
- `data_truth/draw_results_truth/normalized/draw_results_2020_for_2021_candidate_promotion_file_records_STRICT_USABLE_PLUS_SPORTSMAN.csv` rows=6659 years=2020 extra retrospective source for target 2021
- `audits/draw_truth_rebuild/draw_results_long_REBUILT_CANDIDATE.csv` rows=257632 years=2019;2021;2022;2023;2024;2025;2026 and does not currently unlock target 2021 because year 2020 rows are absent
- `data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv` rows=68657 years=2021;2022;2023;2024;2025
- `processed_data/draw_reality_engine_v2.csv` rows=176753 years=2021;2022;2023;2024;2025;2026
- `processed_data/draw_reality_engine_predictive_v2.csv` rows=26389 years=2021;2022;2023;2024;2025;2026
- `processed_data/ml_draw_predictions_v1.csv` rows=27940 years=2021;2022;2023;2024;2025;2026;2076
- `processed_data/point_ladder_view.csv` rows=78162 years=

## Next Step

Run the prediction-vs-actual verifier after retrospective materialization. It compares each target year against the corrected same-target actual source:

- 2020 prediction vs 2019-for-2020 actual truth.
- 2021 prediction vs validated strict 2020-for-2021 actual truth.
- 2022 prediction vs 2021-for-2022 actual truth.
- 2023 prediction vs 2022-for-2023 actual truth.
- 2024 prediction vs 2023-for-2024 actual truth.
- 2025 prediction vs 2024-for-2025 actual truth.
- 2026 remains HOLD until actual 2026 draw results are published and validated.

## Phase 7 Failure Diagnosis

Phase 7 failed because the existing prediction modules are post-processors, not full retrospective materializers.

The failing post-processors expected year-specific input files that did not exist for historical target years:

- `data_model/runtime_drafts/predictive_bonus_engine_<year>.materialized.csv`
- `ml_draw_predictions_v1.csv` inside each retrospective output folder

The current 2026 production files cannot be reused directly for 2022-2025 rolling backtests because they contain post-2022, post-2023, post-2024, and post-2025 information. Using them would leak future information into the historical test.

## Retrospective Materializer Added

Created:

`tools/prediction_accuracy_backtest/build_retrospective_materialized_predictions.py`

The script builds no-leakage retrospective prediction inputs under:

`audits/prediction_accuracy_backtest/retrospective_outputs/<target_year>/materialized/`

The materializer also supports repeatable extra normalized draw-result inputs:

`--extra-source-draw-results <path>`

This is used for early years such as target 2020, where the normalized 2019-for-2020 extract exists but is not merged into the production `draw_results_long.csv` file.

For each target year, it writes:

- `predictive_bonus_engine_<target_year>.materialized.csv`
- `ml_draw_predictions_v1.csv`
- `materialization_audit.json`
- `materialization_audit.csv`

## Prediction Vs Actual Verification Added

Created:

`tools/prediction_accuracy_backtest/verify_prediction_vs_actual_accuracy.py`

The verifier writes small committed summary reports to:

- `audits/prediction_accuracy_backtest/20_actual_truth_pairing_plan.csv`
- `audits/prediction_accuracy_backtest/21_prediction_vs_actual_accuracy_summary.csv`
- `audits/prediction_accuracy_backtest/22_prediction_vs_actual_accuracy_by_family.csv`
- `audits/prediction_accuracy_backtest/23_prediction_vs_actual_accuracy_by_species.csv`
- `audits/prediction_accuracy_backtest/24_prediction_vs_actual_accuracy_by_residency.csv`
- `audits/prediction_accuracy_backtest/25_prediction_vs_actual_accuracy_by_point_bucket.csv`
- `audits/prediction_accuracy_backtest/PREDICTION_ENGINE_VERIFICATION_REPORT.md`

Ignored row-level joins are written to:

`audits/prediction_accuracy_backtest/rowlevel_verification_outputs/`

Verification result from the latest run:

- Evaluated pairs: 12.
- Held pairs: 2 target-year 2026 prediction files.
- Leakage failures: 0.
- Joined rows: 299,404 across evaluated pairs.
- Target-year 2020: evaluated with medium confidence because the older extraction includes sparse summary rows.
- Target-year 2021: evaluated with high confidence using the validated strict usable plus Sportsman source.
- Target-years 2022-2025: evaluated against corrected same-target normalized candidate files.
- Target-year 2026: held until actual 2026 draw results are published and validated.

## No-Leakage Behavior

For target year `N`, the materializer:

- excludes every draw-result row with `year >= N`
- uses only the requested `--history-years` that are less than `N`
- records `target_year`
- records `training_cutoff_year`
- records `history_years_used`
- records `source_row_years`
- records `no_leakage_rule=exclude_source_draw_results_where_draw_year_gte_target_year`
- sets `model_version=retrospective_<target_year>`

## Model Equivalence Status

These outputs are `BASELINE_RETROSPECTIVE`, not full engine-equivalent outputs.

The baseline model uses:

1. historical average `p_draw` by `hunt_code + residency + points + draw_pool`
2. fallback average by `hunt_code + residency + draw_pool`
3. fallback average by `species + residency + draw_pool`
4. fallback global average

Every row records the selected fallback tier in `prediction_method`.

## Generated Retrospective Output Summary

| Target year | History years used | Output rows | Duplicate safe keys | Rows without probability | Leakage rows |
| --- | --- | ---: | ---: | ---: | ---: |
| 2020 | 2019 | 57,313 | 0 | 0 | 0 |
| 2021 | 2020 | 6,659 | 0 | 0 | 0 |
| 2022 | 2021 | 27,519 | 0 | 0 | 0 |
| 2023 | 2021;2022 | 33,554 | 0 | 0 | 0 |
| 2024 | 2021;2022;2023 | 34,512 | 0 | 0 | 0 |
| 2025 | 2021;2022;2023;2024 | 46,142 | 0 | 0 | 0 |

## Early Year Availability Audit

Created:

`audits/prediction_accuracy_backtest/historical_draw_year_availability_audit.md`

Key result:

- Target 2020: runnable with the 2019-for-2020 normalized candidate extract.
- Target 2021: runnable with the strict usable plus Sportsman 2020-for-2021 normalized candidate extract.
- Target 2022: already covered by `draw_results_long.csv` year 2021 rows.

## Updated Next Step

Run the rolling backtest comparison against these newly materialized retrospective folders. The comparison should label the model family as `BASELINE_RETROSPECTIVE_NOT_FULL_ENGINE_EQUIVALENT` so the result is not confused with a full reproduction of the 2026 predictive engine.
