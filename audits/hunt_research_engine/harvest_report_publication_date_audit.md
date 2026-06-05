# Harvest Report Publication-Date Audit

Checks that source filename/report dates are not being mistaken for observed harvest years.

## Summary

- Result: `PASS`.
- Observed rows with `reported_hunt_year=2026`: `0`.
- 2026 harvest feature model rows using source year 2026: `0`.
- Publication-date-after-hunt-year source groups: `17`.
- Key finding: No observed 2026 harvest-year rows are present. Filename dates such as 2026-03-06 are publication/report dates for reported_hunt_year=2025 sources.

## Publication-Date Source Groups

| Table | Reported Hunt Year | Source File | Filename Years | Rows | Status |
| --- | ---: | --- | --- | ---: | --- |
| harvest_truth_long | 2021 | harvest_quality_features_by_hunt_code_2021_for_2022.csv | 2021|2022 | 1948 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_truth_long | 2021 | harvest_results_2021_for_2022_hunt_code_keyed.csv | 2021|2022 | 1948 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_truth_long | 2022 | harvest_quality_features_by_hunt_code_2022_for_2023.csv | 2022|2023 | 1848 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_truth_long | 2023 | 2024_antlerless_hr.csv | 2024 | 225 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_truth_long | 2025 | 2026-03-06-2025-preliminary-bg-harvest.xlsx | 2025|2026 | 10080 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_truth_features | 2021 | harvest_results_2021_for_2022_hunt_code_keyed.csv | 2021|2022 | 974 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_truth_features | 2023 | 2024_antlerless_hr.csv | 2024 | 48 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_truth_features | 2025 | 2026-03-06-2025-preliminary-bg-harvest.xlsx | 2025|2026 | 1120 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_model_long | 2021 | harvest_quality_features_by_hunt_code_2021_for_2022.csv | 2021|2022 | 1948 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_model_long | 2021 | harvest_results_2021_for_2022_hunt_code_keyed.csv | 2021|2022 | 1948 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_model_long | 2022 | harvest_quality_features_by_hunt_code_2022_for_2023.csv | 2022|2023 | 1848 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_model_long | 2023 | 2024_antlerless_hr.csv | 2024 | 225 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_model_long | 2025 | 2026-03-06-2025-preliminary-bg-harvest.xlsx | 2025|2026 | 10080 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_model_features | 2021 | harvest_results_2021_for_2022_hunt_code_keyed.csv | 2021|2022 | 974 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_model_features | 2023 | 2024_antlerless_hr.csv | 2024 | 48 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_model_features | 2025 | 2026-03-06-2025-preliminary-bg-harvest.pdf | 2025|2026 | 1114 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
| harvest_model_features | 2025 | 2026-03-06-2025-preliminary-bg-harvest.xlsx | 2025|2026 | 6 | EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR |
