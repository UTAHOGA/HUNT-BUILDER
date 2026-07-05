# Locked 2026 Hunt-Code Universe

Status: `LOCKED_2026_UNTIL_NEXT_YEAR_DATA_ADDED`

No runtime, engine, website, or prediction-output files are changed by this lock.

## Counts

- Official active hunt-code count: `1097`
- Active prediction-scorable codes: `834`
- Active reference-only codes: `263`
- Full ledger rows, including support/appendix rows: `1646`
- Active-year truth codes: `1097`
- Canonical yearly codes: `1097`
- Long-file codes: `1097`
- Canonical/long aligned codes: `1097`
- Regulation reference-review codes: `0`
- Draw-result review codes: `0`
- DATABASE next-year support codes: `0`
- DATABASE non-scorable reference appendix codes: `546`
- Codes with boundary_id: `1640`
- Active-year truth codes with boundary_id: `1097`
- Excluded prefix rows: `12`
- Duplicate PDFs skipped: `1`

## Policy

- Official year truth is `active_year_truth_codes`; support and appendix rows do not count as official current hunt codes.
- DATABASE next-year support rows are retained only when confirmed by next-year canonical truth and excluded from active-year prediction accuracy.
- DATABASE non-scorable reference appendix rows are retained for lookup/review only and must not feed scoring, public odds, or official count totals.
- Regulation-only rows are reference-review active truth unless canonicalized as scorable draw-result rows.
- Waterfowl/swan TS codes are excluded from this big-game hunt-code universe lock.

## Outputs

- `LOCKED_2026_HUNT_CODE_UNIVERSE_WITH_BOUNDARY_ID.csv`
- `LOCKED_2026_ACTIVE_YEAR_TRUTH_WITH_BOUNDARY_ID.csv`
- `LOCKED_2026_DATABASE_NEXT_YEAR_PERMIT_SUPPORT.csv`
- `LOCKED_2026_DATABASE_NONSCORABLE_REFERENCE_APPENDIX.csv`
- `LOCKED_2026_SOURCE_YEAR_ARTIFACT_ROWS.csv`
- `LOCKED_2026_EXCLUDED_WATERFOWL_UPLAND_PREFIX_ROWS.csv`
- `LOCKED_2026_CANONICAL_LONG_RECONCILIATION.csv`
- `LOCKED_2026_HUNT_CODE_UNIVERSE_SUMMARY.json`
- `README_LOCKED_2026.md`

Do not change these locked counts until another year of source data is intentionally added and a new lock folder is created.
