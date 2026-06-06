# Prediction Engine Verification Report

This audit compares retrospective prediction outputs to paired actual draw-truth sources.

## Pairing Result

| Target | Prediction kind | Status | Confidence | Joined rows | MAE | RMSE | Bias |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| 2020 | predictive_bonus_engine_materialized | EVALUATED | MEDIUM_EXTRA_NORMALIZED_SOURCE | 44642 | 0.031203 | 0.085675 | 0.004499 |
| 2020 | ml_draw_predictions_v1 | EVALUATED | MEDIUM_EXTRA_NORMALIZED_SOURCE | 44642 | 0.031203 | 0.085675 | 0.004499 |
| 2021 | predictive_bonus_engine_materialized | EVALUATED | HIGH_VALIDATED_STRICT_USABLE_PLUS_SPORTSMAN | 6659 | 0.000000 | 0.000000 | 0.000000 |
| 2021 | ml_draw_predictions_v1 | EVALUATED | HIGH_VALIDATED_STRICT_USABLE_PLUS_SPORTSMAN | 6659 | 0.000000 | 0.000000 | 0.000000 |
| 2022 | predictive_bonus_engine_materialized | EVALUATED | HIGH_NORMALIZED_CANDIDATE | 20590 | 0.000216 | 0.001704 | 0.000054 |
| 2022 | ml_draw_predictions_v1 | EVALUATED | HIGH_NORMALIZED_CANDIDATE | 20590 | 0.000216 | 0.001704 | 0.000054 |
| 2023 | predictive_bonus_engine_materialized | EVALUATED | HIGH_NORMALIZED_CANDIDATE | 25399 | 0.030129 | 0.103580 | 0.005194 |
| 2023 | ml_draw_predictions_v1 | EVALUATED | HIGH_NORMALIZED_CANDIDATE | 25399 | 0.030129 | 0.103580 | 0.005194 |
| 2024 | predictive_bonus_engine_materialized | EVALUATED | HIGH_NORMALIZED_CANDIDATE | 25004 | 0.068271 | 0.164636 | 0.015292 |
| 2024 | ml_draw_predictions_v1 | EVALUATED | HIGH_NORMALIZED_CANDIDATE | 25004 | 0.068271 | 0.164636 | 0.015292 |
| 2025 | predictive_bonus_engine_materialized | EVALUATED | HIGH_NORMALIZED_CANDIDATE | 27408 | 0.070644 | 0.167379 | 0.017351 |
| 2025 | ml_draw_predictions_v1 | EVALUATED | HIGH_NORMALIZED_CANDIDATE | 27408 | 0.070644 | 0.167379 | 0.017351 |
| 2026 | predictive_bonus_engine_materialized | EVALUATED_NO_SCORABLE_ACTUAL_PROBABILITY | HIGH_VALIDATED_LIMITED_2026_CANDIDATE | 0 |  |  |  |
| 2026 | ml_draw_predictions_v1 | EVALUATED_NO_SCORABLE_ACTUAL_PROBABILITY | HIGH_VALIDATED_LIMITED_2026_CANDIDATE | 0 |  |  |  |

## Forecast Vs Reconstruction Warning Labels

| Warning status | Pair count |
| --- | ---: |
| BASELINE_RETROSPECTIVE_NOT_FULL_ENGINE_EQUIVALENT | 12 |
| INSUFFICIENT_METADATA | 2 |

Zero-error or near-zero-error rows are retained in the metrics, but they are not presented as standalone proof of live forecast accuracy when the generation method indicates a baseline retrospective reconstruction or when probabilities exactly match actual truth.

## No-Leakage Status

- Evaluated pairs: 14
- Held pairs: 0
- Leakage failures: 0
- Rule: actual rows with draw-result `year >= target_year` or `model_target_year > target_year` are excluded; prediction rows with source years at or after the target year are not scored.

## Biggest Weaknesses By Family

- family `LIMITED_ENTRY_DEER` target 2024 ml_draw_predictions_v1: MAE=0.4748, rows=178
- family `LIMITED_ENTRY_DEER` target 2024 predictive_bonus_engine_materialized: MAE=0.4748, rows=178
- family `BLACK_BEAR` target 2024 ml_draw_predictions_v1: MAE=0.3505, rows=42
- family `BLACK_BEAR` target 2024 predictive_bonus_engine_materialized: MAE=0.3505, rows=42
- family `ANTLERLESS_BIG_GAME` target 2024 ml_draw_predictions_v1: MAE=0.1300, rows=61
- family `ANTLERLESS_BIG_GAME` target 2024 predictive_bonus_engine_materialized: MAE=0.1300, rows=61
- family `youth_antlerless` target 2020 ml_draw_predictions_v1: MAE=0.0878, rows=2228
- family `youth_antlerless` target 2020 predictive_bonus_engine_materialized: MAE=0.0878, rows=2228

## Biggest Weaknesses By Species

- species `Bear` target 2024 ml_draw_predictions_v1: MAE=0.3505, rows=42
- species `Bear` target 2024 predictive_bonus_engine_materialized: MAE=0.3505, rows=42
- species `Unknown` target 2025 ml_draw_predictions_v1: MAE=0.1160, rows=1312
- species `Unknown` target 2025 predictive_bonus_engine_materialized: MAE=0.1160, rows=1312
- species `Black Bear` target 2024 ml_draw_predictions_v1: MAE=0.0930, rows=1404
- species `Black Bear` target 2024 predictive_bonus_engine_materialized: MAE=0.0930, rows=1404
- species `Pronghorn` target 2025 ml_draw_predictions_v1: MAE=0.0882, rows=4512
- species `Pronghorn` target 2025 predictive_bonus_engine_materialized: MAE=0.0882, rows=4512

## Biggest Weaknesses By Residency

- residency `Resident` target 2025 ml_draw_predictions_v1: MAE=0.0780, rows=18575
- residency `Resident` target 2025 predictive_bonus_engine_materialized: MAE=0.0780, rows=18575
- residency `Nonresident` target 2024 ml_draw_predictions_v1: MAE=0.0762, rows=8637
- residency `Nonresident` target 2024 predictive_bonus_engine_materialized: MAE=0.0762, rows=8637
- residency `Resident` target 2024 ml_draw_predictions_v1: MAE=0.0641, rows=16367
- residency `Resident` target 2024 predictive_bonus_engine_materialized: MAE=0.0641, rows=16367
- residency `Nonresident` target 2023 ml_draw_predictions_v1: MAE=0.0562, rows=8938
- residency `Nonresident` target 2023 predictive_bonus_engine_materialized: MAE=0.0562, rows=8938

## Notes

- Target 2026 is evaluated when production 2026 prediction outputs are present, using the validated limited 2026 actual truth file for evaluation only.
- The 2026 actual truth file has `model_target_year=2027`; that is not treated as leakage because the verification target uses `actual_draw_year/source_year=2026`.
- Row-level joins are written under an ignored folder and are not intended for GitHub commits.
- Retrospective baseline rows are separated from true forecast comparisons by `27_prediction_actual_circularity_audit.csv`.
