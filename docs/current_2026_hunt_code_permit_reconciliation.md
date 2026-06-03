# Current 2026 Hunt-Code Permit Reconciliation

## Purpose

This is an audit-only reconciliation for current 2026 hunt codes and permit/allotment numbers. It compares current external evidence and produces recommended permit candidates, but it does not write to `DATABASE.csv`.

## Source Precedence

1. DWR Hunt Planner `HaNumber` pull when it has a current permit value.
2. Live DWR HuntBoundary `HuntTableData` table values.
3. Repaired Buck Deer workbook/pasted source rows for Buck Deer-specific support.
4. UtahDraws/BIBLE 2026 draw-results evidence where DWR current sources are blank or where it supports the same value.
5. `DATABASE.csv` is comparison/reference only in this pass, not a winner source.

## Key Counts

- Candidate hunt codes in union: `1470`
- Rows with recommended external permit values: `1157`
- Unresolved/review rows: `596`
- Rows where only `DATABASE.csv` has a permit reference value: `56`

## Winner Source Counts

- `HANUMBER`: `1125`
- `HUNTTABLE`: `22`
- `NONE`: `257`
- `NONE_EXTERNAL_DATABASE_REFERENCE_ONLY`: `56`
- `UTAHDRAWS`: `10`

## Confidence Counts

- `HIGH_CONFIRMED_2PLUS`: `722`
- `MEDIUM_SINGLE_SOURCE`: `82`
- `MEDIUM_TOTAL_CONFIRMED`: `70`
- `NO_PERMIT_VALUE`: `257`
- `REVIEW_REQUIRED`: `56`
- `REVIEW_SOURCE_CONFLICT`: `283`

## Recommended Action Counts

- `FIND_EXTERNAL_SOURCE_BEFORE_PROMOTION`: `56`
- `NO_CURRENT_PERMIT_VALUE_FOUND`: `257`
- `PROMOTE_CANDIDATE_AFTER_REVIEW`: `804`
- `PROMOTE_TOTAL_AFTER_SPLIT_REVIEW`: `70`
- `REVIEW_BEFORE_PROMOTION`: `283`

## Source Coverage Counts

- `buck_deer`: `458` present codes, `328` value codes
- `database`: `1449` present codes, `1187` value codes
- `hanumber`: `1449` present codes, `1125` value codes
- `hunttable`: `1412` present codes, `1092` value codes
- `utahdraws`: `834` present codes, `834` value codes

## Main Unresolved Prefix Families

- `DB`: `174`
- `EL`: `126`
- `LO`: `113`
- `EB`: `65`
- `EA`: `33`
- `PB`: `19`
- `PD`: `9`
- `DS`: `8`
- `BI`: `6`
- `BR`: `6`
- `LD`: `6`
- `LP`: `6`
- `RS`: `6`
- `TK`: `6`
- `DA`: `3`
- `MA`: `3`
- `MB`: `3`
- `GO`: `2`
- `CG`: `1`
- `EX`: `1`

## Main Unresolved Species Families

- `Deer`: `291`
- `Elk`: `230`
- `Pronghorn`: `34`
- `Desert Bighorn Sheep`: `8`
- `Bison`: `6`
- `Black Bear`: `6`
- `Moose`: `6`
- `Rocky Mountain Bighorn Sheep`: `6`
- `Turkey`: `6`
- `Mountain Goat`: `2`
- `Cougar`: `1`

## Interpretation

Rows marked `HIGH_CONFIRMED_2PLUS` are the strongest candidates for promotion after review because at least two non-database sources agree exactly.

Rows marked `REVIEW_SOURCE_CONFLICT` have a selected winner by precedence but still conflict with another non-database source. These should be inspected before promotion, especially where UtahDraws/BIBLE values represent a different permit concept than current DWR allotment values.

Rows marked `REVIEW_REQUIRED` are the most important cleanup set because no external current source in this pass has permit values even though `DATABASE.csv` may contain a reference value.

## Outputs

- `processed_data/audits/current_2026_hunt_code_permit_reconciliation.csv`
- `processed_data/audits/current_2026_hunt_code_permit_unresolved.csv`
- `processed_data/audits/current_2026_hunt_code_permit_reconciliation_summary.json`
