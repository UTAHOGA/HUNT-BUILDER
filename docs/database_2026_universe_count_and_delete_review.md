# DATABASE 2026 Universe Count And Delete Review

## Short Answer

Do not bulk-delete rows from `DATABASE.csv` right now. The current file has `1471` rows / `1471` unique hunt codes, but the active current reconciliation universe has `1470` rows because `PD1025` is now retained only as a retired reference row.

The earlier `1600+` number did not come from the active `DATABASE.csv`; it came from historical draw/alignment working files with `1600` or `1615` unique source/alignment codes.

## Current Counts

- Current DATABASE rows: `1471`
- Current DATABASE unique hunt codes: `1471`
- Active reconciliation rows: `1470`
- Retired reference rows: `1`

## Row Classification

- `ACTIVE_RECONCILIATION_ROW`: `1470`
- `RETIRED_REFERENCE_ROW`: `1`

## Delete Recommendation

- `KEEP`: `1470`
- `KEEP_REFERENCE_DO_NOT_DELETE`: `1`

## Reference Counts

- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.pre_2025_permit_backfill_backup.csv`: `1449` rows / `1449` unique hunt codes
- `processed_data/backups/DATABASE_before_allotment_reconciliation_20260604T052630Z.csv`: `1449` rows / `1449` unique hunt codes
- `pipeline/RAW/hunt_unit_database/2026/csv/draw_database_alignment_changes_by_hunt_code_V2.csv`: `1615` rows / `1615` unique hunt codes
- `pipeline/RAW/hunt_unit_database/2026/csv/draw_results_database_alignment_outputs_V3/draw_database_alignment_changes_by_hunt_code_V3.csv`: `1615` rows / `1615` unique hunt codes
- `pipeline/RAW/hunt_unit_database/2026/csv/draw_results_database_alignment_outputs_V3/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED_V3.csv`: `112056` rows / `1615` unique hunt codes

## Recommendation

Keep `DATABASE.csv` as truth/reference with retired rows clearly marked. For website/current permit outputs, use the active reconciliation universe instead of physically deleting historical/crosswalk rows.

If you later want a current-only file, generate a derived export that excludes `RETIRED_REFERENCE_ROW` rows rather than deleting them from the truth database.

## Outputs

- `processed_data/audits/database_2026_universe_count_and_delete_review.csv`
- `processed_data/audits/database_2026_universe_count_and_delete_review_summary.json`
