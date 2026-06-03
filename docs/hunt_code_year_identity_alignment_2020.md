# 2020 Hunt-Code Year Identity Alignment Audit

## Purpose
Create the first year-specific identity ledger so a historical hunt code can be tied to a specific hunt, source page, report family, permit totals, current DATABASE exact-code status, and lifecycle interpretation.

## Inputs
- Source package: `C:\Users\tyler\Desktop\BIBLE HUNT CODES\COMPREHENSIVE 2020-2025.zip`
- Report year: `2020`
- Model year: `2021`
- Current comparison database: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\pipeline\RAW\hunt_unit_database\2026\csv\DATABASE.csv`

## Outputs
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_ledger_2020.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_crosscheck_2020.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_issues_2020.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_scan_errors_2020.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_2020_summary.json`

## Key Counts
- 2020 source PDFs: `23`
- Ledger rows: `2032`
- Unique hunt codes: `1028`
- Sportsman rows added from table parser: `11`
- Scan errors: `0`

## Crosscheck Status Counts
- `REVIEW_CURRENT_DATABASE_NAME_DIFFERENCE`: `457`
- `REVIEW_CONFLICTING_TOTAL_PERMITS`: `327`
- `REVIEW_TOTALS_PARSE`: `138`
- `HISTORICAL_CODE_NOT_IN_CURRENT_DATABASE`: `106`

## DATABASE Exact-Code Match Counts
- `EXACT_CODE_IN_DATABASE`: `1587`
- `NOT_IN_CURRENT_DATABASE`: `445`

## Totals Parse Counts
- `OK`: `1854`
- `REVIEW_TOTALS_PARSE`: `167`
- `OK_SPORTSMAN_TABLE`: `11`

## Lifecycle Class Counts
- `ACTIVE_IN_2026`: `1216`
- `TERMINAL_DROPOFF_CANDIDATE`: `767`
- `HISTORICAL_REAPPEARANCE_GAP_CODE`: `49`

## Interpretation
- `hunt_code_year_identity_ledger_2020.csv` is the source-evidence ledger.
- `hunt_code_year_identity_crosscheck_2020.csv` is the one-row-per-code review surface.
- Rows with `REVIEW_*` statuses should be checked before using them as crosswalk truth.
- `DATABASE.csv` was not changed.
