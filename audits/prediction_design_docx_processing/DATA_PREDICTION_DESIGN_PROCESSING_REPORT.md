# Data Prediction Design Processing Report

Generated UTC: 2026-06-19T09:37:45.645095+00:00
Source DOCX: `C:\Users\tyler\Desktop\data prediction design.docx`
Paragraphs extracted: 331

## Controlling Decision
`draw_results_long.csv` remains the canonical engine-facing truth feeder for now. The `finalized_*` split files are useful reconciliation/supporting surfaces, but they are narrower and should not replace the master feeder until a feeder-contract change is explicitly made.

## What The Document Gets Right
- The repo already has the proposed `engine_rebuild_from_truth/` style separation: raw/extracted/normalized/engine/audit/output.
- The architecture direction toward R2-backed large files is correct; the canonical master is too large for Git.
- The prediction loop should stay truth-first: official scorable rows, generate predictions, compare to next-year actual draw truth, tune, rerun.

## What Must Be Held Back
- Do not apply global draw-type modifiers. Prior validation showed broad modifiers worsened results; tuning needs to be lane-specific.
- Do not treat fee elasticity, point creep, or application-growth assumptions as truth. Those can become experiments after the baseline engine is stable.
- Do not fabricate actual probability from hunt-level totals or zero-applicant rows. Accuracy validation must use scorable actual probability rows only.
- Do not square or otherwise alter point weights without official Utah rule support.

## Current File Inventory
| File | Exists | Rows | Columns | Size MB |
|---|---:|---:|---:|---:|
| `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\engine_rebuild_from_truth\extracted\draw_truth_raw.csv` | True | 30298 | 12 | 3.26 |
| `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\engine_rebuild_from_truth\normalized\finalized_draw_truth_2026.csv` | True | 30298 | 13 | 3.338 |
| `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\engine_rebuild_from_truth\engine\classified_draw_truth_2026.csv` | True | 30298 | 16 | 3.549 |
| `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\engine_rebuild_from_truth\engine\draw_engine_input_hunt_totals.csv` | True | 21246 | 15 | 6.78 |
| `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\engine_rebuild_from_truth\engine\draw_engine_input_point_rows.csv` | True | 460097 | 14 | 135.073 |
| `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\engine_rebuild_from_truth\engine\draw_reality_engine.csv` | True | 21246 | 16 | 5.034 |
| `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\engine_rebuild_from_truth\engine\prediction_outputs.csv` | True | 460097 | 16 | 115.879 |
| `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\engine_rebuild_from_truth\outputs\validation_report.json` | True |  |  | 0.003 |
| `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\data_truth\finalized_point_distribution.csv` | True | 460097 | 17 | 153.995 |
| `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\data_truth\finalized_hunt_truth.csv` | True | 21246 | 18 | 7.652 |
| `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\data_truth\draw_results_truth\normalized\draw_results_long.csv` | True | 535179 | 55 | 352.301 |

## Recommended Processing Order
1. R2 handoff/pointer manifest for large canonical truth and engine output artifacts.
2. Sync `engine_rebuild_from_truth` inputs from canonical `draw_results_long.csv`, not stale intermediate files.
3. Rerun fixed-key validation with `hunt_program` + `draw_family` in the key.
4. Tune bad lanes only: Dedicated Hunter, Youth DH, Youth Antlerless, Bear, Turkey.
5. Only after validation stabilizes, consider optional feature experiments like point creep and demand forecasting.

## Output Files
- extracted_text: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\prediction_design_docx_processing\data_prediction_design_extracted_text.txt`
- action_matrix: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\prediction_design_docx_processing\data_prediction_design_action_matrix.csv`
- file_inventory: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\prediction_design_docx_processing\engine_rebuild_file_inventory.csv`
- report: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\prediction_design_docx_processing\DATA_PREDICTION_DESIGN_PROCESSING_REPORT.md`
- status: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\prediction_design_docx_processing\DATA_PREDICTION_DESIGN_PROCESSING_STATUS.json`

## Canonical Master vs Current Engine-Rebuild Inputs

The current engine-rebuild files are internally clean, but they are narrower than the canonical `draw_results_long.csv` master. A normalized-key audit found:

- Canonical master rows: 535,179
- Covered by current finalized engine-input keys: 519,656
- Not covered by current finalized engine-input keys: 15,523

The uncovered rows are not automatically prediction failures. They are concentrated in hunt-total/reference/supplemental lanes and a smaller number of 2026 candidate/status rows. They must be explicitly classified before any engine run consumes them.

Audit outputs:

- `audits/prediction_design_docx_processing/canonical_master_vs_finalized_engine_input_gap_status.json`
- `audits/prediction_design_docx_processing/canonical_master_rows_not_in_finalized_engine_inputs_summary.csv`
- `audits/prediction_design_docx_processing/canonical_master_rows_not_in_finalized_engine_inputs_sample.csv`

Decision: do not feed the 15,523 gap rows silently into prediction accuracy. First classify them as scorable point rows, hunt totals, Sportsman/random-only, availability/reference-only, supplemental totals, or review-only.

