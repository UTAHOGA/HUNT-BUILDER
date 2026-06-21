# Sync Yearly Normalized 2023-2024 From Canonical Master

Generated UTC: 2026-06-19T23:00:52.526985+00:00
Revalidated UTC: 2026-06-19T23:01:53.025587+00:00
Source canonical master: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\data_truth\draw_results_truth\normalized\draw_results_long.csv`
Status: `PASS_SYNCED_FROM_CANONICAL_MASTER`

Validation key uses row-level `source_file` / `source_pdf` before broad namespace because yearly namespace alone is too coarse for multi-file truth.

| Year | Before Rows | After Rows | Columns After | Size MB After | Duplicate Strict-Key Groups | Exact Duplicate Row Groups |
|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 41201 | 71658 | 55 | 61.036 | 0 | 0 |
| 2024 | 37224 | 86659 | 55 | 57.344 | 0 | 0 |

## Backups
- 2023: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\sync_yearly_normalized_2023_2024_from_canonical\backups\draw_results_2023_for_2024_candidate_promotion_file_records.backup_before_canonical_sync_20260619T230039Z.csv`
- 2024: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\sync_yearly_normalized_2023_2024_from_canonical\backups\draw_results_2024_for_2025_candidate_promotion_file_records.backup_before_canonical_sync_20260619T230039Z.csv`

## Git/Data Policy
These yearly CSVs are generated truth artifacts. Both synced files are over 50 MB, so they require review before Git staging. `draw_results_long.csv` is over 100 MB and belongs in R2, not Git.

All validation gates passed.
