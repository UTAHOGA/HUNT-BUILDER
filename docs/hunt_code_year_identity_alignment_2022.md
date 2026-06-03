# 2022 Hunt-Code Year Identity Alignment Audit

## Year Semantics
- `draw_results_year = 2022`.
- `permit_draw_year = 2022`.
- `model_year = 2023`.
- Source filename model labels are preserved as source evidence only.

## Key Counts
- Ledger rows: `1998`
- Unique hunt codes: `1020`
- Sportsman rows added: `11`
- Lifecycle source-hit rows added: `11`
- Scan errors: `0`
- Missing from identity ledger after correction: `0`
- Extra in identity ledger after correction: `0`

## Sportsman Normalization
The 2022 Sportsman PDF text extraction joins `N/A` text onto hunt codes, producing artifacts such as `ABI1000`. The ledger normalizes those rows to the user-confirmed copied-text codes.

## Outputs
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_ledger_2022.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_crosscheck_2022.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_issues_2022.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_scan_errors_2022.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_sportsman_normalization_2022.csv`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\processed_data\audits\hunt_code_year_identity_2022_summary.json`
- `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\docs\hunt_code_year_identity_alignment_2022.md`
