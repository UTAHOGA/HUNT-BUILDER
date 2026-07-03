# Locked 2026 Hunt-Code Universe With Boundary IDs

Status: `LOCKED_2026_UNTIL_NEXT_YEAR_DATA_ADDED`

This folder freezes the reconciled 2026 hunt-code universe counts across the model workbook, 2026 DWR hunt matrix, DATABASE, long file, boundary index/GeoJSON assets, and BIBLE year documents.

No runtime or website files are changed by this lock.

## Locked Count Policy

- `1097` = 2026 permits => 2027 model workbook universe.
- `1394` = 2026 structured mapped/searchable hunt matrix universe.
- `1645` = DATABASE superset, including support/historical/reference rows.
- `1289` = demoted legacy/derived built master, not a current count authority.

## Files

- `LOCKED_2026_HUNT_CODE_UNIVERSE_WITH_BOUNDARY_ID.csv` - full union ledger with explicit `boundary_id` column.
- `LOCKED_2026_MATRIX_MAPPED_SEARCHABLE_WITH_BOUNDARY_ID.csv` - the 1394 matrix/search/map universe.
- `LOCKED_2026_MODEL_WORKBOOK_WITH_BOUNDARY_ID.csv` - the 1097 model workbook universe.
- `LOCKED_2026_BIBLE_RECONCILIATION_COMPARISONS.csv` - workbook/matrix vs BIBLE year-document comparison counts.
- `LOCKED_2026_BIBLE_RECONCILIATION_DELTAS_WITH_BOUNDARY_ID.csv` - row-level BIBLE deltas with `boundary_id`.
- `LOCKED_2026_HUNT_CODE_UNIVERSE_SUMMARY.json` - machine-readable count summary.

## BIBLE Reconciliation

- 2025 BIBLE year document: `1053`
- 2025 permits => 2026 model workbook: `1064`
- Difference: `11` workbook-only Sportsman/statewide-family codes:
  `BI1000 BR1000 CG9999 DB0007 DS1000 EB1000 GO1000 MB1000 PB1000 RS0001 TK0001`
- 2026 BIBLE year document currently structured: `31`
- 2026 permits => 2027 model workbook: `1097`

BIBLE year documents are retained as source-library truth/reference, not the sole current active universe authority.

## Rule

Do not change these locked 2026 counts until another year of source data is intentionally added and a new lock folder is created.
