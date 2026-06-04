# Current 2026 Hunt-Code Permit Reconciliation

## Purpose

This is an audit-only reconciliation for current 2026 hunt codes and permit/allotment numbers. It compares current external evidence and produces recommended permit candidates, but it does not write to `DATABASE.csv`.

## Source Precedence

1. DWR Hunt Planner `HaNumber` pull when it has a current permit value.
1. Reviewed override rows for explicitly user-confirmed extraction/crosswalk corrections.
2. DWR Hunt Planner `HaNumber` pull when it has a current permit value.
3. Live DWR HuntBoundary `HuntTableData` table values.
4. Repaired Buck Deer workbook/pasted source rows for Buck Deer-specific support.
5. UtahDraws/BIBLE 2026 draw-results evidence where DWR current sources are blank or where it supports the same value.
6. `DATABASE.csv` is comparison/reference only in this pass, not a winner source.

## Key Counts

- Candidate hunt codes in union: `1470`
- Rows with recommended external permit values: `1158`
- Unresolved/review rows: `556`
- Rows where only `DATABASE.csv` has a permit reference value: `56`

## Winner Source Counts

- `HANUMBER`: `1125`
- `HUNTTABLE`: `22`
- `NONE`: `256`
- `NONE_EXTERNAL_DATABASE_REFERENCE_ONLY`: `56`
- `REVIEWED_OVERRIDE`: `1`
- `UTAHDRAWS`: `10`

## Confidence Counts

- `HIGH_CONFIRMED_2PLUS`: `760`
- `MEDIUM_SINGLE_SOURCE`: `81`
- `MEDIUM_TOTAL_CONFIRMED`: `72`
- `NO_PERMIT_VALUE`: `256`
- `REVIEWED_OVERRIDE_CONFIRMED`: `1`
- `REVIEW_REQUIRED`: `56`
- `REVIEW_SOURCE_CONFLICT`: `244`

## Recommended Action Counts

- `FIND_EXTERNAL_SOURCE_BEFORE_PROMOTION`: `56`
- `NO_CURRENT_PERMIT_VALUE_FOUND`: `256`
- `PROMOTE_CANDIDATE_AFTER_REVIEW`: `841`
- `PROMOTE_REVIEWED_OVERRIDE`: `1`
- `PROMOTE_TOTAL_AFTER_SPLIT_REVIEW`: `72`
- `REVIEW_BEFORE_PROMOTION`: `244`

## Source Coverage Counts

- `buck_deer`: `458` present codes, `328` value codes
- `database`: `1471` present codes, `1214` value codes
- `hanumber`: `1449` present codes, `1127` value codes
- `hunttable`: `1413` present codes, `1093` value codes
- `reviewed_override`: `1` present codes, `1` value codes
- `utahdraws`: `834` present codes, `834` value codes

## Main Unresolved Prefix Families

- `DB`: `174`
- `EL`: `126`
- `LO`: `113`
- `EB`: `65`
- `PB`: `19`
- `EA`: `9`
- `DS`: `8`
- `BI`: `6`
- `BR`: `6`
- `LD`: `6`
- `LP`: `6`
- `RS`: `6`
- `TK`: `6`
- `GO`: `2`
- `MB`: `2`
- `CG`: `1`
- `EX`: `1`

## Main Unresolved Species Families

- `Deer`: `288`
- `Elk`: `206`
- `Pronghorn`: `25`
- `Desert Bighorn Sheep`: `8`
- `Bison`: `6`
- `Black Bear`: `6`
- `Rocky Mountain Bighorn Sheep`: `6`
- `Turkey`: `6`
- `Moose`: `2`
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
