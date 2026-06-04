# DATABASE Allotment Database Patch 2026

## Source Meaning

- `DATABASE.csv` allotment numbers are the `permit_allotment_2026_*` fields. In the current project lineage, populated allotment rows primarily came from live DWR Hunt Planner / HuntTable current-year pulls.
- Recommended numbers are the selected current-source winner from the permit reconciliation file. Source precedence is HaNumber, HuntTable, Buck Deer repaired source, then UtahDraws. DATABASE is comparison/reference only in that winner selection.

## Applied Scope

- Exact DATABASE/recommended matches were reconciled in the audit with no numeric DATABASE edit needed.
- Total-only matches were reconciled by total. Blank resident/nonresident split cells were filled only when the recommended split was present.
- Blank DATABASE allotment rows with recommended values were populated.
- True nonblank DATABASE disagreements were left unchanged.

## Key Counts

- `ADDED_DATABASE_ROW_FROM_BLANK_RECOMMENDATION`: `22`
- `LEFT_UNCHANGED_TRUE_DISAGREEMENT`: `43`
- `RECONCILED_DATABASE_BLANK_FILLED`: `6`
- `RECONCILED_EXACT_MATCH_NO_NUMERIC_CHANGE`: `1075`
- `RECONCILED_TOTAL_MATCH`: `13`
- Numeric rows changed: `34`
- True disagreements left unchanged: `43`

## Outputs

- Patch audit: `processed_data/audits/database_allotment_database_patch_2026.csv`
- True disagreements: `processed_data/audits/database_allotment_true_disagreements_after_patch_2026.csv`
- Summary: `processed_data/audits/database_allotment_database_patch_2026_summary.json`
- Backup: `processed_data/backups/DATABASE_before_allotment_reconciliation_20260604T052630Z.csv`
