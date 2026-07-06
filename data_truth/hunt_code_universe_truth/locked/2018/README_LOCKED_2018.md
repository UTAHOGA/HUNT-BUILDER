# Locked 2018 Hunt-Code Universe

Status: `LOCKED_2018_UNTIL_NEXT_YEAR_DATA_ADDED`

No runtime, engine, website, or prediction-output files are changed by this lock.

## Counts

- Official active hunt-code count: `1042`
- Active prediction-scorable codes: `1010`
- Active reference-only codes: `32`
- Full ledger rows, including support/appendix rows: `1107`
- Active-year truth codes: `1042`
- Canonical yearly codes: `1010`
- Long-file codes: `1010`
- Canonical/long aligned codes: `1010`
- Regulation reference-review codes: `32`
- Draw-result review codes: `0`
- DATABASE next-year support codes: `65`
- DATABASE non-scorable reference appendix codes: `0`
- Codes with boundary_id: `1044`
- Active-year truth codes with boundary_id: `979`
- Excluded prefix rows: `0`
- Duplicate PDFs skipped: `0`

## Policy

- Official year truth is `active_year_truth_codes`; support and appendix rows do not count as official current hunt codes.
- DATABASE next-year support rows are retained only when confirmed by next-year canonical truth and excluded from active-year prediction accuracy.
- DATABASE non-scorable reference appendix rows are retained for lookup/review only and must not feed scoring, public odds, or official count totals.
- Regulation-only rows are reference-review active truth unless canonicalized as scorable draw-result rows.
- Waterfowl/swan TS codes are excluded from this big-game hunt-code universe lock.

## Outputs

- `LOCKED_2018_HUNT_CODE_UNIVERSE_WITH_BOUNDARY_ID.csv`
- `LOCKED_2018_ACTIVE_YEAR_TRUTH_WITH_BOUNDARY_ID.csv`
- `LOCKED_2018_DATABASE_NEXT_YEAR_PERMIT_SUPPORT.csv`
- `LOCKED_2018_DATABASE_NONSCORABLE_REFERENCE_APPENDIX.csv`
- `LOCKED_2018_SOURCE_YEAR_ARTIFACT_ROWS.csv`
- `LOCKED_2018_CANONICAL_LONG_RECONCILIATION.csv`
- `LOCKED_2018_HUNT_CODE_UNIVERSE_SUMMARY.json`
- `README_LOCKED_2018.md`

Do not change these locked counts until another year of source data is intentionally added and a new lock folder is created.
