# Reconcile Finalized Truth With Draw Results Long

Generated UTC: 2026-06-19T09:28:25.673433+00:00

Status: PASS_RECONCILED_SYNCED_2021_2022_AND_APPENDED_2026

## Canonical Decision

DRAW_RESULTS_LONG_REMAINS_ENGINE_FEEDER_CANONICAL: draw_results_long.csv carries the 55-column engine-facing schema and richer identity/source metadata; finalized_point_distribution.csv and finalized_hunt_truth.csv remain narrower reconciliation/source-truth surfaces.

## Actions

- Synced 2021 normalized yearly file from draw_results_long canonical slice.
- Synced 2022 normalized yearly file from draw_results_long canonical slice.
- Appended accepted 2026 dense live+PDF candidate into draw_results_long.csv.
- Synced 2026 normalized yearly file to the same long-schema 2026 slice because the previous target was stale.

## Final Counts

- draw_results_long rows before: 535179
- draw_results_long rows after: 535179
- 2026 rows added: 30298
- duplicate strict-key groups after: 0
- blank hunt_code rows after: 0
- blank year rows after: 0

## Outputs

- Status JSON: C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\reconcile_finalized_vs_long_and_sync_2026\RECONCILE_FINALIZED_VS_LONG_AND_SYNC_2026_STATUS.json
- Reconciliation CSV: C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\reconcile_finalized_vs_long_and_sync_2026\finalized_vs_draw_results_long_by_year.csv
- Row counts: C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\reconcile_finalized_vs_long_and_sync_2026\draw_results_long_row_counts_before_after.csv
- Duplicate keys: C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\reconcile_finalized_vs_long_and_sync_2026\draw_results_long_duplicate_strict_keys_after.csv
- Backups: C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\reconcile_finalized_vs_long_and_sync_2026\backups
