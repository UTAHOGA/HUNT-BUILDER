# Prediction Validation Classification Audit

Generated UTC: 2026-06-19T04:49:58.863101+00:00

## Scope

- Actual probability is sourced only from published truth `success_rate / 100`.
- Permit/applicant division is not used as actual probability.
- Metrics include only `SCORABLE_ACTUAL` rows.
- Zero-applicant rows remain ladder structure and are excluded from accuracy scoring.

## Results

- Joined scorable actual rows: `64745`
- MAE: `0.0007398933734372983`
- RMSE: `0.004280262510824513`
- Bias: `-0.00014353294528998467`
- Failure rows over 0.25 absolute error: `0`
- Source anomaly review rows excluded from metrics: `1`

## Truth Row Classification

- `SCORABLE_ACTUAL`: `64745`
- `SOURCE_ANOMALY_REVIEW`: `1`
- `UNSCORABLE_NONZERO_APPLICANTS_NO_PUBLISHED_SUCCESS_RATE`: `77158`
- `ZERO_APPLICANT_GUARANTEED_ZONE`: `147169`
- `ZERO_APPLICANT_STRUCTURAL`: `171024`

## DS6608 Finding

- Failing row: `DS6608`, model year `2026`, `Nonresident`, point level `32`.
- Published PDF text says `1 in 2.0`, but the same row has `1` applicant and `1` permit.
- Tyler reviewed and confirmed this should be `1 in 1.0` / `100%`.
- The raw PDF-derived value remains preserved in `source_anomaly_review_rows.csv`.
- The row is excluded from accuracy metrics as `SOURCE_ANOMALY_REVIEW` so it does not falsely count as an engine miss.

## 2021/2022 Success-Rate Coverage

- 2021 has nonzero-applicant rows but zero published `success_rate` values in the current truth surface.
- 2022 has 18,056 nonzero-applicant rows but only 2 rows with `success_rate`.
- This is a truth-field normalization gap, not evidence that the PDFs lack outcomes.

## Output Files

- `prediction_vs_actual_full`: `audits\prediction_validation\prediction_vs_actual_full.csv`
- `prediction_vs_actual_summary`: `audits\prediction_validation\prediction_vs_actual_summary.csv`
- `prediction_vs_actual_by_year`: `audits\prediction_validation\prediction_vs_actual_by_year.csv`
- `prediction_vs_actual_by_point_bucket`: `audits\prediction_validation\prediction_vs_actual_by_point_bucket.csv`
- `truth_row_validation_classification_counts`: `audits\prediction_validation\truth_row_validation_classification_counts.csv`
- `success_rate_coverage_by_year`: `audits\prediction_validation\success_rate_coverage_by_year.csv`
- `DS6608_failure_inspection`: `audits\prediction_validation\DS6608_failure_inspection.csv`
- `classification_report`: `audits/prediction_validation/PREDICTION_VALIDATION_CLASSIFICATION_REPORT.md`
