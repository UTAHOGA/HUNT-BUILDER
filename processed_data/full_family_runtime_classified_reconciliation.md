# Full Family Classified Reconciliation

Source ledger: `processed_data\full_family_runtime_all_year_family_prediction_counts.csv`

## Summary

- Classified rows reconciled: 30
- True full-cert blocker rows: 27
- Intentional unreleased-results holdout rows: 3
- Bucket counts: `{'FULL_CERT_WIRING_BLOCKER': 27, 'INTENTIONAL_UNRELEASED_ACTUALS_HOLDOUT': 3}`

## Family Buckets

- `bonus_bear`: `{'FULL_CERT_WIRING_BLOCKER': 9}`
- `preference_antlerless_deer`: `{'INTENTIONAL_UNRELEASED_ACTUALS_HOLDOUT': 1}`
- `preference_antlerless_elk`: `{'INTENTIONAL_UNRELEASED_ACTUALS_HOLDOUT': 1}`
- `preference_doe_pronghorn`: `{'INTENTIONAL_UNRELEASED_ACTUALS_HOLDOUT': 1}`
- `youth_draw`: `{'FULL_CERT_WIRING_BLOCKER': 9}`
- `youth_turkey`: `{'FULL_CERT_WIRING_BLOCKER': 9}`

## Decision

- The three 2026->2027 antlerless/doe rows are not accuracy failures and should remain held out until official 2027 actual draw results are released.
- The 27 bear/youth rows are real full-family certification blockers, but not because runtime output is missing today. They are blocked because the all-year validator still uses placeholder classified rows instead of promoted historical adapters.
- Do not replace these with raw long-file builder calls. The direct probe showed row inflation and/or pending rows when the current builders are fed undeduped historical long rows.

## Recommended Fix Order

1. Add a deduped historical feeder adapter for `bonus_bear` and prove bounded probabilities/no future-year use on 2024->2025, 2025->2026, and 2026->2027.
2. Add the same style adapter for `youth_turkey`, with duplicate-key checks before writing family outputs.
3. Add explicit progressive-source handling for `youth_draw`; verify youth rows do not claim future source years beyond the allowed source history window.
4. Keep `preference_antlerless_deer`, `preference_antlerless_elk`, and `preference_doe_pronghorn` as held-out/not-penalized for 2026->2027 until the public actuals exist.

## Files Written

- `processed_data\full_family_runtime_classified_reconciliation.csv`
- `processed_data\full_family_runtime_classified_reconciliation.json`
- `processed_data\full_family_runtime_classified_reconciliation.md`
