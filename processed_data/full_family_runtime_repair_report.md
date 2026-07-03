# Full Engine All-Year Repair Report

Repo: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER`
Audit dir: `audits\full_family_runtime_prediction_wired_20260703`

## Scope

- Repaired preference-family engines to use forecast-year-aware permit accessors.
- Normalized historical split-residency ladder columns without fake eligibility defaults.
- Added an actual source-year/target-year runner for historical preference-family validation.
- Runs Sportsman as its own resident-only random draw stream from yearly Sportsman draw-result sources.
- Runs bear, youth turkey, and youth draw through deduped historical target adapters.

## Result

- Count rows written: 81
- Leakage failures: 0
- Zero-row modeled failures: 0
- Classified clean-run blockers: 0
- Intentional unreleased-results holdouts: 3

## Files

- `changed_files.txt`
- `source_column_mapping.csv`
- `per_family_year_prediction_counts.csv`
- `all_year_family_prediction_counts.csv`
- `leakage_check.csv`
- `classified_reconciliation.csv`
