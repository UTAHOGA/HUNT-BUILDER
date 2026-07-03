# Full Family Runtime Prediction Outcome

Created: 2026-07-03T02:59:59

Full family audit: `audits\full_family_runtime_prediction_20260703_024059`
Materialized outputs: `audits\full_family_runtime_materialized_20260703_025641\outputs`

## Result
- Family/year statuses: {'PASS': 51, 'CLASSIFIED': 30}
- Total full-family runner prediction rows: 94888
- Leakage statuses: {'PASS': 54, 'CLASSIFIED': 27}
- Materialized runtime rows: 38647
- Materialized hunt codes: 878
- Hunt-code reconciliation required rows: 0

## Classified Rows
- bonus_bear: 9 - DEFERRED_WITH_REASON: bear target-year source selection is still under repair
- preference_antlerless_deer: 1 - HELD_OUT_UNRELEASED_2027_ANTLERLESS_DOE_RESULTS
- preference_antlerless_elk: 1 - HELD_OUT_UNRELEASED_2027_ANTLERLESS_DOE_RESULTS
- preference_doe_pronghorn: 1 - HELD_OUT_UNRELEASED_2027_ANTLERLESS_DOE_RESULTS
- youth_draw: 9 - DEFERRED_WITH_REASON: youth draw historical target-year runner wiring is not promoted
- youth_turkey: 9 - DEFERRED_WITH_REASON: youth turkey historical target-year runner wiring is not promoted

## Truth Surface
- `data_truth/draw_results_truth/normalized/draw_results_long.csv`
- Run filtered progressive source/target years from draw_results_long.csv, which is aligned to the canonical_yearly union; it did not open each yearly canonical CSV directly.

## Promotion
- Processed files copied: 37
- Public content files copied: 23
- 150 MB runtime truth copy was not promoted to Git.
