# 2025 Permit Prior-Generation Reconciliation

Generated UTC: 2026-05-23T12:05:59.766361+00:00
Prior generation file: `data/hunt-master-canonical-2026-foundation.json`
Prior generation hunt codes: `1394`
Active database hunt codes: `1411`
Active-not-prior hunt codes: `17`
New 2026 gap codes match active-not-prior: `True`
Prior-overlap comparison rows: `1395` across `523` hunt codes

## Active Not In Prior

`EA1007`, `EA1053`, `EA1287`, `EA1288`, `EA1289`, `EA1290`, `EA1291`, `EA1292`, `EA1293`, `EA1294`, `EA1295`, `EA1296`, `EA1297`, `EA1298`, `EA1299`, `EA1300`, `PD1039`

## Status Counts

- `ACTIVE_ONLY`: `951`
- `DIFFERS_FROM_PRIOR_GENERATION`: `412`
- `PRIOR_ONLY`: `32`

## Surface Checks

| File | Codes | Missing fields | Missing JSON keys | New 2026 nonblank 2025 rows |
| --- | ---: | --- | ---: | ---: |
| pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv | 1411 | None | 0 | 0 |
| data/hunt-master-canonical-2026-source-of-truth.csv | 1411 | None | 0 | 0 |
| processed_data/hunt-master-canonical-2026-source-of-truth.csv | 1411 | None | 0 | 0 |
| data/hunt-master-canonical-2026-database-candidate.csv | 1411 | None | 0 | 0 |
| hunt-master-canonical-2026.json | 1411 | None | 0 | 0 |
| canonical/hunt-planner-2026.json | 1411 | None | 0 | 0 |
| generated/pages/hunt-planner.json | 1411 | None | 0 | 0 |
| data/hunt-master-canonical-2026-source-of-truth.json | 1411 | None | 0 | 0 |
| processed_data/hunt-master-canonical-2026-source-of-truth.json | 1411 | None | 0 | 0 |

## Note

Differences from the 1394-code foundation are retained in the CSV report. Active values use `2025_DRAW_RESULTS_TABLES` when sourced from the official draw-results extraction.
