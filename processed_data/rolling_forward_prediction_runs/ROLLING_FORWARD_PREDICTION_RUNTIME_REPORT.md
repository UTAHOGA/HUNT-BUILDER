# Rolling Forward Prediction Runtime Report

Promoted at: 2026-07-01T05:11:05
Source audit: `D:\DESKTOP\GitHub\HUNT-BUILDER\audits\rolling_forward_prediction_run_20260701_050705`
Runtime directory: `D:\DESKTOP\GitHub\HUNT-BUILDER\processed_data\rolling_forward_prediction_runs`

| Source -> Target | Rows | Size MB | Runtime file |
|---|---:|---:|---|
| 2018 -> 2019 | 12007 | 8.942 | `processed_data/rolling_forward_prediction_runs/rolling_forward_2018_to_2019_family_predictions.csv` |
| 2019 -> 2020 | 9151 | 6.863 | `processed_data/rolling_forward_prediction_runs/rolling_forward_2019_to_2020_family_predictions.csv` |
| 2020 -> 2021 | 7367 | 5.525 | `processed_data/rolling_forward_prediction_runs/rolling_forward_2020_to_2021_family_predictions.csv` |
| 2021 -> 2022 | 6336 | 4.781 | `processed_data/rolling_forward_prediction_runs/rolling_forward_2021_to_2022_family_predictions.csv` |
| 2022 -> 2023 | 11985 | 8.946 | `processed_data/rolling_forward_prediction_runs/rolling_forward_2022_to_2023_family_predictions.csv` |
| 2023 -> 2024 | 12332 | 9.238 | `processed_data/rolling_forward_prediction_runs/rolling_forward_2023_to_2024_family_predictions.csv` |
| 2024 -> 2025 | 12603 | 9.387 | `processed_data/rolling_forward_prediction_runs/rolling_forward_2024_to_2025_family_predictions.csv` |
| 2025 -> 2026 | 13618 | 10.155 | `processed_data/rolling_forward_prediction_runs/rolling_forward_2025_to_2026_family_predictions.csv` |
| 2026 -> 2027 | 5973 | 4.431 | `processed_data/rolling_forward_prediction_runs/rolling_forward_2026_to_2027_family_predictions.csv` |

## Family Totals

| Family | Prediction rows |
|---|---:|
| preference_general_deer | 40570 |
| preference_antlerless_elk | 21496 |
| dedicated_hunter | 16657 |
| preference_antlerless_deer | 8478 |
| preference_doe_pronghorn | 4076 |
| SPORTSMAN_RANDOM_ONLY | 95 |

## Runtime Safety

- These files are production runtime artifacts for rolling-forward prediction output.
- They do not replace `ml_draw_predictions_v1.csv`.
- They do not replace `draw_reality_engine_predictive_v2.csv`.
- They do not replace `draw_reality_engine_v2.csv`.
