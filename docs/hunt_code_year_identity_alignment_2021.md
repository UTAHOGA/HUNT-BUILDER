# 2021 Hunt-Code Year Identity Alignment Audit

## Purpose
Create the 2021 year-specific identity ledger so a historical hunt code can be tied to a specific hunt, source page, report family, permit totals, current DATABASE exact-code status, and lifecycle interpretation.

## Inputs
- Source package: `C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021.zip`
- Report year: `2021`
- Model year: `2022`
- Current comparison database: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\pipeline\RAW\hunt_unit_database\2026\csv\DATABASE.csv`

## Outputs
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_ledger_2021.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_crosscheck_2021.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_issues_2021.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_scan_errors_2021.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_2021_summary.json`

## Key Counts
- Source PDFs: `22`
- Ledger rows: `1990`
- Unique hunt codes: `1023`
- Sportsman rows added from table parser: `12`
- Scan errors: `0`
- Coverage against lifecycle presence matrix: `1023/1023`
- Missing from identity ledger: `0`
- Extra in identity ledger: `0`

## Source Model-Year Labels
- `2022`: `1440`
- `2021`: `550`

## Crosscheck Status Counts
- `REVIEW_CURRENT_DATABASE_NAME_DIFFERENCE`: `498`
- `REVIEW_CONFLICTING_TOTAL_PERMITS`: `318`
- `REVIEW_TOTALS_PARSE`: `136`
- `HISTORICAL_CODE_NOT_IN_CURRENT_DATABASE`: `70`
- `OK`: `1`

## DATABASE Exact-Code Match Counts
- `EXACT_CODE_IN_DATABASE`: `1672`
- `NOT_IN_CURRENT_DATABASE`: `318`

## Totals Parse Counts
- `OK`: `1816`
- `REVIEW_TOTALS_PARSE`: `162`
- `OK_SPORTSMAN_TABLE`: `12`

## Lifecycle Class Counts
- `ACTIVE_IN_2026`: `1267`
- `TERMINAL_DROPOFF_CANDIDATE`: `670`
- `HISTORICAL_REAPPEARANCE_GAP_CODE`: `53`

## Interpretation
- The ledger is source evidence, not a truth-source promotion.
- Sportsman codes are included via a dedicated table parser.
- Rows with `REVIEW_*` statuses should be checked before using them as crosswalk truth.
- `DATABASE.csv` was not changed.
