# Full Family Classified Reconciliation

Source ledger: `processed_data/full_family_runtime_all_year_family_prediction_counts.csv`

## Summary

- Classified rows reconciled: 3
- True full-cert blocker rows: 0
- Intentional unreleased-results holdout rows: 3
- Bucket counts: `{'INTENTIONAL_UNRELEASED_ACTUALS_HOLDOUT': 3}`

## Family Buckets

- `preference_antlerless_deer`: `1` intentional holdout row(s)
- `preference_antlerless_elk`: `1` intentional holdout row(s)
- `preference_doe_pronghorn`: `1` intentional holdout row(s)

## Decision

- The previous 27 bear/youth full-cert blockers are now wired into the year-by-year runner.
- The only remaining classified rows are unreleased 2027 antlerless/doe actual-result holdouts and are not accuracy failures.
