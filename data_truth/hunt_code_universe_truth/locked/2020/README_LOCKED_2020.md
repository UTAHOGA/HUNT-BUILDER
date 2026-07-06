# Locked 2020 Hunt-Code Universe

Status: `LOCKED_2020_UNTIL_NEXT_YEAR_DATA_ADDED`

No runtime, engine, website, or prediction-output files are changed by this lock.

## Counts

- Official active hunt-code count: `1067`
- Active prediction-scorable codes: `1028`
- Active reference-only codes: `39`
- Full ledger rows, including support/appendix rows: `1145`
- Active-year truth codes: `1067`
- Canonical yearly codes: `1028`
- Long-file codes: `1028`
- Canonical/long aligned codes: `1028`
- Regulation reference-review codes: `39`
- Draw-result review codes: `0`
- DATABASE next-year support codes: `78`
- DATABASE non-scorable reference appendix codes: `0`
- Codes with boundary_id: `1106`
- Active-year truth codes with boundary_id: `1028`
- Excluded prefix rows: `0`
- Duplicate PDFs skipped: `1`

## Policy

- Official year truth is `active_year_truth_codes`; support and appendix rows do not count as official current hunt codes.
- DATABASE next-year support rows are retained only when confirmed by next-year canonical truth and excluded from active-year prediction accuracy.
- DATABASE non-scorable reference appendix rows are retained for lookup/review only and must not feed scoring, public odds, or official count totals.
- Regulation-only rows are reference-review active truth unless canonicalized as scorable draw-result rows.
- Waterfowl/swan TS codes are excluded from this big-game hunt-code universe lock.

## Outputs

- `LOCKED_2020_HUNT_CODE_UNIVERSE_WITH_BOUNDARY_ID.csv`
- `LOCKED_2020_ACTIVE_YEAR_TRUTH_WITH_BOUNDARY_ID.csv`
- `LOCKED_2020_DATABASE_NEXT_YEAR_PERMIT_SUPPORT.csv`
- `LOCKED_2020_DATABASE_NONSCORABLE_REFERENCE_APPENDIX.csv`
- `LOCKED_2020_SOURCE_YEAR_ARTIFACT_ROWS.csv`
- `LOCKED_2020_CANONICAL_LONG_RECONCILIATION.csv`
- `LOCKED_2020_HUNT_CODE_UNIVERSE_SUMMARY.json`
- `README_LOCKED_2020.md`

Do not change these locked counts until another year of source data is intentionally added and a new lock folder is created.
