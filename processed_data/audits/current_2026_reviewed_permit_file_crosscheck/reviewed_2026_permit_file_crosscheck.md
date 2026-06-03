# Reviewed 2026 Permit File Crosscheck

## Purpose

This audit normalizes the local reviewed 2026 permit CSV files and compares them against the current remaining unresolved 2026 permit review set. It is audit-only and does not modify `DATABASE.csv`.

## Key Counts

- Normalized source rows: `3294`
- Normalized source rows with permit values: `2646`
- Unique hunt codes in normalized table: `1393`
- Remaining unresolved input rows: `354`
- Rows strictly resolved by reviewed files: `0`
- Rows supported by reviewed files but still requiring precedence review: `39`
- Rows still unresolved after reviewed file crosscheck: `354`

## Source Role Counts

- `REVIEWED_FAMILY`: `1393`
- `REVIEWED_MASTER`: `1393`
- `SUPERSEDED_FRAGMENT_DO_NOT_USE_FOR_CANONICAL`: `508`

## Resolution Status Counts

- `NO_REVIEWED_PERMIT_VALUE`: `315`
- `SUPPORTS_REVIEWED_VALUE_WITH_REMAINING_CONFLICT`: `39`

## Outputs

- `processed_data/audits/current_2026_reviewed_permit_file_crosscheck/reviewed_2026_permit_sources_normalized.csv`
- `processed_data/audits/current_2026_reviewed_permit_file_crosscheck/reviewed_2026_permit_sources_by_hunt_code.csv`
- `processed_data/audits/current_2026_reviewed_permit_file_crosscheck/reviewed_2026_permit_remaining_unresolved_crosscheck.csv`
- `processed_data/audits/current_2026_reviewed_permit_file_crosscheck/supported_by_reviewed_2026_permit_files.csv`
- `processed_data/audits/current_2026_reviewed_permit_file_crosscheck/strictly_resolved_by_reviewed_2026_permit_files.csv`
- `processed_data/audits/current_2026_reviewed_permit_file_crosscheck/still_unresolved_after_reviewed_2026_permit_files.csv`
- `processed_data/audits/current_2026_reviewed_permit_file_crosscheck/reviewed_2026_permit_file_crosscheck_summary.json`
- `processed_data/audits/current_2026_reviewed_permit_file_crosscheck/reviewed_2026_permit_file_crosscheck.md`
