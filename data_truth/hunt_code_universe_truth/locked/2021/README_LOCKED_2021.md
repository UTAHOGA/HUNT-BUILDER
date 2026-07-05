# Locked 2021 Hunt-Code Universe

Status: `LOCKED_2021_UNTIL_NEXT_YEAR_DATA_ADDED`

No runtime, engine, website, or prediction-output files are changed by this lock.

## Counts

- Official active hunt-code count: `1070`
- Active prediction-scorable codes: `1022`
- Active reference-only codes: `48`
- Full ledger rows, including support/appendix rows: `1117`
- Active-year truth codes: `1070`
- Canonical yearly codes: `1022`
- Long-file codes: `1022`
- Canonical/long aligned codes: `1022`
- Regulation reference-review codes: `47`
- Draw-result review codes: `1`
- DATABASE next-year support codes: `47`
- DATABASE non-scorable reference appendix codes: `0`
- Codes with boundary_id: `1074`
- Active-year truth codes with boundary_id: `1027`
- Excluded prefix rows: `13`
- Duplicate PDFs skipped: `0`

## Policy

- Official year truth is `active_year_truth_codes`; support and appendix rows do not count as official current hunt codes.
- DATABASE next-year support rows are retained only when confirmed by next-year canonical truth and excluded from active-year prediction accuracy.
- DATABASE non-scorable reference appendix rows are retained for lookup/review only and must not feed scoring, public odds, or official count totals.
- Regulation-only rows are reference-review active truth unless canonicalized as scorable draw-result rows.
- Waterfowl/swan TS codes are excluded from this big-game hunt-code universe lock.

## Outputs

- `LOCKED_2021_HUNT_CODE_UNIVERSE_WITH_BOUNDARY_ID.csv`
- `LOCKED_2021_ACTIVE_YEAR_TRUTH_WITH_BOUNDARY_ID.csv`
- `LOCKED_2021_DATABASE_NEXT_YEAR_PERMIT_SUPPORT.csv`
- `LOCKED_2021_DATABASE_NONSCORABLE_REFERENCE_APPENDIX.csv`
- `LOCKED_2021_SOURCE_YEAR_ARTIFACT_ROWS.csv`
- `LOCKED_2021_EXCLUDED_WATERFOWL_UPLAND_PREFIX_ROWS.csv`
- `LOCKED_2021_CANONICAL_LONG_RECONCILIATION.csv`
- `LOCKED_2021_HUNT_CODE_UNIVERSE_SUMMARY.json`
- `README_LOCKED_2021.md`

Do not change these locked counts until another year of source data is intentionally added and a new lock folder is created.
