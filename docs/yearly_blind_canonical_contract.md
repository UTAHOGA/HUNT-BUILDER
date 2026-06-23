# Yearly Canonical And Blind Scoring Contract

This repository uses a year-by-year workflow so each year can be frozen, reviewed, and scored without leaking future-year truth back into the model.

## Core Rules

1. Build one frozen canonical file per actual draw year.
2. Keep review workbooks separate from the canonical truth file.
3. Score predictions only against the next year's official scorable actuals.
4. Do not rebuild a year's score surface from the same year's answer key.
5. Keep large generated data outside Git when possible; commit only small manifests, scripts, and audit summaries.

## Canonical Layers

- `data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_<YEAR>_for_<YEAR+1>_canonical_yearly_draw_results.csv`
- This is the frozen yearly truth slice.
- It should be stable once validated.
- It should not be replaced by later candidate-promotion artifacts for the same target year.

## Review Workbooks

- `outputs/<YEAR> PERMITS.xlsx`
- `outputs/<YEAR> standardized long.xlsx`
- These are human-review and comparison workbooks.
- They may contain extra display fields, but they should stay aligned with the frozen canonical source.

## Scorable Outputs

- `outputs/<YEAR> scorable draw results.csv`
- This is the public scoring surface for blind comparison.
- It should be built from the frozen canonical layer, not from future-year truth files.

## Blind Backtest Rule

For a blind comparison from history year `H` to target year `T = H + 1`:

1. Freeze canonical truth for `H`.
2. Materialize predictions using only rows with source year `<= H`.
3. Freeze the prediction output.
4. Compare only against the official scorable truth file for `T`.
5. Do not use candidate-promotion or cleanup artifacts that already contain `T` truth values as the scoring answer key.

## Recommended Year Sequence

1. Clean and freeze `2019`.
2. Run blind `2019 -> 2020`.
3. Clean and freeze `2020`.
4. Run blind `2020 -> 2021`.
5. Continue one year at a time.

## Practical Notes

- `hunt_name`, `hunt_type`, `draw_design`, `species`, `sex_type`, `weapon`, and permit totals are the main fields that must stay normalized.
- `boundary_id` is useful for map alignment, but it should not be allowed to contaminate hunt-name normalization.
- Point-purchase, reference-only, allocation-only, and other non-scorable rows should stay out of blind accuracy scoring.
- If a row cannot be joined without a future-year source or a manual guess, it should remain blank or be excluded from scoring rather than invented.

## Existing Helpers

The repository already has scripts that support this workflow:

- `scripts/final_yearly_canonical_audit_and_sync_long.py`
- `scripts/export_yearly_canonical_workbook.py`
- `scripts/export_yearly_scorable_and_reference_csvs.py`
- `tools/prediction_accuracy_backtest/build_retrospective_materialized_predictions.py`
- `tools/prediction_accuracy_backtest/verify_prediction_vs_actual_accuracy.py`

Use those helpers in sequence so the canonical layer, the workbooks, and the blind score all come from the same frozen year slice.
