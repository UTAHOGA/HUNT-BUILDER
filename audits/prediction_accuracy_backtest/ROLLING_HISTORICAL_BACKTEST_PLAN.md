# Rolling Historical Prediction Backtest Plan

## Purpose

Because the feeder files have now been aligned across years, old archived prediction files are not required. The cleaner test is to regenerate historical predictions using only data available before each target year, then compare to the official raw draw results for that target year.

## No-Leakage Rule

For target year N, the model may use draw-result and harvest information only through year N-1. It may not use target-year actual draw results or any file derived from target-year results.

## Backtest Year Plan

### Target 2022
- Training cutoff: 2021
- Allowed draw result years: 2021
- Forbidden leakage years: 2022;2023;2024;2025;2026;2027;2028;2029
- Best actual candidate: `data_truth/draw_results_truth/normalized/draw_results_2022_for_2023_candidate_promotion_file_records.csv`
- Status: READY_TO_RUN_RETROSPECTIVE

### Target 2023
- Training cutoff: 2022
- Allowed draw result years: 2021;2022
- Forbidden leakage years: 2023;2024;2025;2026;2027;2028;2029
- Best actual candidate: `data_truth/draw_results_truth/normalized/draw_results_2023_for_2024_candidate_promotion_file_records.csv`
- Status: READY_TO_RUN_RETROSPECTIVE

### Target 2024
- Training cutoff: 2023
- Allowed draw result years: 2021;2022;2023
- Forbidden leakage years: 2024;2025;2026;2027;2028;2029
- Best actual candidate: `data_truth/draw_results_truth/normalized/draw_results_2024_for_2025_candidate_promotion_file_records.csv`
- Status: READY_TO_RUN_RETROSPECTIVE

### Target 2025
- Training cutoff: 2024
- Allowed draw result years: 2021;2022;2023;2024
- Forbidden leakage years: 2025;2026;2027;2028;2029
- Best actual candidate: `data_truth/draw_results_truth/normalized/draw_results_2025_for_2026_candidate_promotion_file_records.csv`
- Status: READY_TO_RUN_RETROSPECTIVE

### Target 2026
- Training cutoff: 2025
- Allowed draw result years: 2021;2022;2023;2024;2025
- Forbidden leakage years: 2026;2027;2028;2029
- Best actual candidate: `data_truth/draw_results_truth/normalized/draw_results_long.csv`
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
- `data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv` rows=68657 years=2021;2022;2023;2024;2025
- `processed_data/draw_reality_engine_v2.csv` rows=176753 years=2021;2022;2023;2024;2025;2026
- `processed_data/draw_reality_engine_predictive_v2.csv` rows=26389 years=2021;2022;2023;2024;2025;2026
- `processed_data/ml_draw_predictions_v1.csv` rows=27940 years=2021;2022;2023;2024;2025;2026;2076
- `processed_data/point_ladder_view.csv` rows=78162 years=

## Next Step

Create a retrospective runner that calls the engine for target years 2022-2025 using training cutoffs, writes predictions to audits/prediction_accuracy_backtest/retrospective_outputs/, and compares each target year against actual raw draw results for that same target year.

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

For each target year, it writes:

- `predictive_bonus_engine_<target_year>.materialized.csv`
- `ml_draw_predictions_v1.csv`
- `materialization_audit.json`
- `materialization_audit.csv`

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
| 2022 | 2021 | 27,519 | 0 | 0 | 0 |
| 2023 | 2021;2022 | 33,554 | 0 | 0 | 0 |
| 2024 | 2021;2022;2023 | 34,512 | 0 | 0 | 0 |
| 2025 | 2021;2022;2023;2024 | 46,142 | 0 | 0 | 0 |

## Updated Next Step

Run the rolling backtest comparison against these newly materialized retrospective folders. The comparison should label the model family as `BASELINE_RETROSPECTIVE_NOT_FULL_ENGINE_EQUIVALENT` so the result is not confused with a full reproduction of the 2026 predictive engine.
