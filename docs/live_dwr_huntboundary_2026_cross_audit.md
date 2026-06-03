# Live DWR HuntBoundary 2026 Cross Audit

Snapshot UTC: `2026-06-03T16:43:30+00:00`

## Purpose

This audit refreshes the live Utah DWR HuntBoundary / Hunt Planner permit-number pull and compares it against the current local 2026 `DATABASE.csv` hunt-code universe.

This is a cross-audit only. It does not promote values and does not modify `DATABASE.csv`.

## Sources Checked

- Live DWR page: `https://dwrapps.utah.gov/huntboundary/`
- Live DWR JSON endpoint pattern: `https://dwrapps.utah.gov/huntboundary/HuntTableData?species=<species>&gender=<gender>`
- Hunt Builder DWR entry surface: `https://huntbuilder.uoga.org/#dwr`
- Local database compared: `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`

Reachability validation returned HTTP `200` for:

- `https://dwrapps.utah.gov/huntboundary/`
- `https://dwrapps.utah.gov/huntboundary/HuntTableData?species=Elk&gender=Antlerless`
- `https://huntbuilder.uoga.org/`
- `https://huntbuilder.uoga.org/#dwr`

## Important Local Database Note

The current local `DATABASE.csv` no longer contains these old duplicate headers:

- `permits_2026_res`
- `permits_2026_nr`
- `permits_2026_total`

Therefore this audit compared live DWR values against:

- `permit_allotment_2026_res`
- `permit_allotment_2026_nr`
- `permit_allotment_2026_total`

## Pull Coverage

- DWR endpoints queried: `19`
- Live rows extracted: `1414`
- Live unique hunt codes: `1412`
- Current database rows: `1449`
- Union comparison rows: `1470`

## Comparison Results

- `MATCH`: `754`
- `TOTAL_MATCH_SPLIT_DIFFERS`: `277`
- `NUMERIC_MISMATCH`: `40`
- `LIVE_ONLY`: `21`
- `DATABASE_ONLY`: `58`
- `LIVE_NO_QUOTA_DATABASE_PRESERVED`: `61`
- `BOTH_BLANK`: `259`

`TOTAL_MATCH_SPLIT_DIFFERS` means the total permit count aligns but the residency split shape differs, or the database has a split where DWR exposes only a total.

## Parser Repair Made During Audit

The live DWR endpoint sometimes publishes resident and nonresident quota values while leaving raw `QUOTA` as `0`. The audit script previously compared that zero literally, creating false mismatches. The script now calculates live total as `resident + nonresident` when DWR publishes a split but a zero or blank total.

After this repair, numeric mismatches dropped from `128` to `40`.

## Remaining Numeric Mismatch Families

- `EA`: `25`
- `PD`: `9`
- `DA`: `3`
- `MA`: `3`

These rows are in `processed_data/audits/live_dwr_huntboundary_2026_cross_audit.csv` with bucket `REVIEW_NUMERIC_MISMATCH`.

## Live-Only DWR Codes

Live DWR exposes `21` codes not present in the current local database:

`EA1007`, `EA1053`, `EA1107`, `EA1288`, `EA1289`, `EA1290`, `EA1291`, `EA1292`, `EA1293`, `EA1294`, `EA1295`, `EA1296`, `EA1297`, `EA1298`, `EA1299`, `EA1300`, `EA1301`, `MA1011`, `PD1011`, `PD1039`, `PD1041`

These should be reviewed before any database promotion because they may represent newly exposed HuntBoundary rows, split/duplicate hunt rows, or source timing differences.

## Database-Only Codes

The audit found `58` current database hunt codes not exposed by the queried live DWR endpoints.

These are not automatically wrong. Some are CWMU, retired, archived, no-quota, or source-scope exceptions. They are listed in the clean audit CSV with bucket `REVIEW_DATABASE_ONLY_NOT_IN_LIVE_PULL`.

## Outputs

- Raw live pull: `data_truth/crosswalk_truth/raw_inventory/live_dwr_hunt_planner_permit_numbers_comprehensive_2026.csv`
- Full validation comparison: `data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.csv`
- Summary JSON: `data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026_summary.json`
- Clean review CSV: `processed_data/audits/live_dwr_huntboundary_2026_cross_audit.csv`
- Script/report surface: `processed_data/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.md`

## Recommendation

Use the live DWR pull as strong confirmation evidence for current 2026 allotment values, but do not blanket-promote it. The next safe step is a focused review of:

- the `40` numeric mismatches,
- the `21` live-only DWR codes,
- the `58` database-only codes.

`DATABASE.csv` should remain unchanged until that focused review classifies each remaining row.
