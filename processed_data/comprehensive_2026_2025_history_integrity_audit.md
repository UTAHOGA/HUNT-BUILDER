# Comprehensive 2026/2025 History Integrity Audit

- Generated UTC: `2026-05-26T17:26:29+00:00`
- DATABASE active rows: `1394`
- DATABASE unique hunt codes: `1394`
- Retired current-code ledger rows: `17`
- Fatal blockers: `0`
- Review warnings: `3`

## Clean Core Checks

- Active DATABASE has no duplicate hunt codes and no blank boundary IDs.
- Retired 2026 current codes are absent from active DATABASE and preserved in the ledger.
- Live-online DATABASE missing-code count is zero in the latest committed DWR snapshot audit.
- Active EA reconciliation is clean: 204 live/current active EA rows and 204 DATABASE EA rows.
- Permit overlay validations show zero numeric mismatches against protected DATABASE cells.

## Remaining Review Classes

- `le_deer_2025_draw_to_database`: `6` issue rows. missing_database_rows=6 expected=6; numeric_diffs=0. Next: Treat missing rows as historical/CWMU review evidence unless user confirms they need active 2026 rows.
- `oil_2025_draw_to_database`: `12` issue rows. missing_database_rows=12 expected=12; numeric_diffs=0. Next: Treat missing rows as historical/CWMU review evidence unless user confirms they need active 2026 rows.
- `harvest_2025_for_2026_database_code_presence`: `29` issue rows. active_database_matches=1089; unmatched_active_database=29; retired_matches=0. Next: Resolve remaining unmatched harvest codes as historical-only, CWMU-retired, or current-code crosswalk candidates.

## Output Files

- Dashboard CSV: `data_truth/comparison_outputs/validation/comprehensive_2026_2025_history_integrity_audit.csv`
- Open issues CSV: `data_truth/comparison_outputs/validation/comprehensive_2026_2025_history_integrity_open_issues.csv`
- Summary JSON: `data_truth/comparison_outputs/validation/comprehensive_2026_2025_history_integrity_summary.json`

Guardrail: this audit does not alter website feeds, materializer outputs, or protected numeric DATABASE cells.
