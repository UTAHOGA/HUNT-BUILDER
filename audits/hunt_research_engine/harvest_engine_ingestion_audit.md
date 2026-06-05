# Harvest Engine Ingestion Audit

Read-only proof that harvest data is entering the correct downstream engine surfaces.

## Result

- Result: `PASS`.
- Current `DATABASE.csv` hunt codes: `1471`.
- Harvest truth rows: `68657`.
- Harvest feature model rows: `1411`.
- Current codes with feature row: `1410`.
- Mixed engine consumes harvest features: `True`.
- Mixed engine harvest probability component present: `True`.
- Website summary harvest display present: `True`.
- Website split detail harvest present: `True`.

## Correct Engine Path

1. `data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv` stores normalized harvest truth.
2. `data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv` stores year-by-year feature evidence.
3. `data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv` rolls that evidence into 2026 hunt-code feature rows.
4. `processed_data/ml_draw_predictions_v1.csv`, `processed_data/draw_reality_engine_predictive_v2.csv`, and `processed_data/point_ladder_view.csv` carry `harvest_quality_index`, `demand_pressure_signal`, and `p_harvest_adjusted`.
5. Hunt Research runtime files carry harvest display values such as `harvest_success_pct`, `average_harvest_age`, `current_age_3yr_average`, and split-detail `has_harvest` fields.

## Surface Counts

| Surface | Rows | Hunt codes | Duplicate key count | Required fields present | Key nonblank counts |
| --- | ---: | ---: | ---: | --- | --- |
| harvest_truth_normalized | 68657 | 1424 | 58254 | True | reported_hunt_year=68657, model_target_year=68657, hunt_code=68657, percent_success=58007, source_file=68657 |
| harvest_all_years_features | 5563 | 1561 | 0 | True | reported_hunt_year=5563, model_target_year=5563, hunt_code=5563, percent_success=4146, recommended_use=6 |
| harvest_feature_model_by_hunt_code_2026 | 1411 | 1411 | 0 | True | harvest_quality_index=1384, demand_pressure_signal=1404, demand_pressure_category=1411, point_creep_quality_adjustment=1411, harvest_success_recent=1404, harvest_success_3yr_avg=1404, hunter_satisfaction_recent=1277, hunter_effort_days_recent=1280 |
| ml_draw_predictions_v1 | 27940 | 1065 | 0 | True | harvest_quality_index=27590, demand_pressure_signal=27818, demand_pressure_category=27820, point_creep_quality_adjustment=27820, harvest_feature_match_method=27820, harvest_feature_source_years=27820, harvest_feature_reason_codes=27820, p_harvest_adjusted=22719 |
| draw_reality_engine_predictive_v2 | 26389 | 864 | 0 | True | harvest_quality_index=26075, demand_pressure_signal=26303, demand_pressure_category=26307, point_creep_quality_adjustment=26307, harvest_feature_match_method=26307, harvest_feature_source_years=26305, harvest_feature_reason_codes=26307, p_harvest_adjusted=21375 |
| point_ladder_view | 91712 | 1449 | 0 | True | harvest_quality_index=89820, demand_pressure_signal=91140, demand_pressure_category=91602, point_creep_quality_adjustment=91602, harvest_feature_match_method=91602, harvest_feature_source_years=91536, harvest_feature_reason_codes=91602, p_harvest_adjusted=25719 |
| hunt_unit_reference_linked | 2997 | 1471 | 0 | True | harvest_success_percent_2025=2218, harvest_2025=2220, harvest_hunters_2025=2228, harvest_average_days_2025=2218, harvest_satisfaction_2025=2218 |
| hunt_research_2026_summary | 3011 | 1471 | 0 | True | harvest_success_pct=2294, average_days_hunted=2294, average_harvest_age=1114, current_age_3yr_average=440 |
| hunt_research_2026_split_index | 1471 | 1471 | 0 | True | average_harvest_age=557, current_age_3yr_average=220 |
| hunt_research_2026_split_details | 1471 | 1471 | 0 | True | has_harvest=1428, percent_success=1111, harvest=1084, average_harvest_age=319, current_age_3yr_average=220 |

## Blockers And Warnings

| Severity | ID | Message |
| --- | --- | --- |
| WARNING | FEATURE_CODES_MISSING_FROM_SUMMARY | Feature codes absent from Hunt Research summary: ['EA1287'] |
| WARNING | FEATURE_CODES_MISSING_FROM_DETAILS | Feature codes absent from split details: ['EA1287'] |
| WARNING | CURRENT_CODES_WITHOUT_FEATURE_ROW | Current DATABASE codes without a 2026 harvest feature row: ['BI6530', 'BR7008', 'BR7019', 'BR7108', 'BR7208', 'DA1044', 'DA1051', 'DB1036', 'DB1059', 'DB1082', 'DB1088', 'DB1089', 'DB1094', 'DB1276', 'DB1320', 'DB1324', 'DB1338', 'DB1343', 'DB1344', 'DB1345'] |

## Guardrails

- Harvest data is quality/demand/display context.
- Harvest data is not a source for directly overwriting draw truth, probability truth, current-year quota, or `DATABASE.csv` permit/allotment truth.
- This audit did not run engines, edit source files, edit runtime manifests, or publish to R2.

## Conclusion

Harvest data is ingested into the correct engine path: quality feature model, mixed predictive engine harvest adjustment fields, and Hunt Research display/runtime harvest fields. Remaining gaps are coverage warnings, not evidence that harvest is being used as quota or draw truth.
