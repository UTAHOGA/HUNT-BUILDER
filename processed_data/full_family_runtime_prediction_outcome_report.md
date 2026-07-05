# Full Family Runtime Prediction Outcome

Created: 2026-07-03T03:58:35

Full family audit: `audits\full_family_runtime_prediction_wired_20260703`
Materialized outputs: `audits\full_family_runtime_materialized_20260703_025641\outputs`

## Result
- Family/year statuses: {'PASS': 78, 'CLASSIFIED': 3}
- Total full-family runner prediction rows: 118511
- Leakage statuses: {'PASS': 81}
- Prediction files checked: 81
- Duplicate runtime-key files: 0
- Bad probability files: 0
- Materialized runtime rows: 38647
- Materialized hunt codes: None
- Hunt-code reconciliation required rows: 0

## Wired Families
- bonus_bear rows: 21525
- youth_turkey rows: 2080
- youth_draw rows: 18

## Classified Rows
- preference_antlerless_deer: 1 - HELD_OUT_UNRELEASED_2027_ANTLERLESS_DOE_RESULTS
- preference_antlerless_elk: 1 - HELD_OUT_UNRELEASED_2027_ANTLERLESS_DOE_RESULTS
- preference_doe_pronghorn: 1 - HELD_OUT_UNRELEASED_2027_ANTLERLESS_DOE_RESULTS

## Truth Surface
- `data_truth/draw_results_truth/normalized/draw_results_long.csv`
- Bear/youth historical adapters use all source years through the prediction source year.
- The 2026->2027 antlerless/doe rows remain held out until official actual results are released.

## Artifacts
- Year-by-year run folders: `audits\full_family_runtime_prediction_wired_20260703\runs\2019` through `audits\full_family_runtime_prediction_wired_20260703\runs\2027`
- Each target-year folder now has 9 prediction CSV files.
