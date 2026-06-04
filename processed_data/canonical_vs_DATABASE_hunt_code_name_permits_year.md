# Canonical Vs DATABASE Hunt Code / Name / Permit-Year Cross-Check

Generated UTC: 2026-05-23T15:32:58.580589+00:00
Database rows: 1411
Database unique hunt codes: 1411

| Canonical file | Codes | In both | DB only | Canonical only | Active 2026/name mismatches |
| --- | ---: | ---: | ---: | ---: | ---: |
| hunt-master-canonical-2026.json | 1411 | 1411 | 0 | 0 | 0 |
| canonical/hunt-planner-2026.json | 1411 | 1411 | 0 | 0 | 0 |
| generated/pages/hunt-planner.json | 1411 | 1411 | 0 | 0 | 0 |
| data/hunt-master-canonical-2026-database-candidate.csv | 1411 | 1411 | 0 | 0 | 0 |
| data/hunt-master-canonical-2026-source-of-truth.csv | 1411 | 1411 | 0 | 0 | 0 |
| processed_data/hunt-master-canonical-2026-source-of-truth.csv | 1411 | 1411 | 0 | 0 | 0 |

## Active 2026 Alignment

- Aligned with `DATABASE.csv` for hunt code, normalized hunt name, and active 2026 permit fields: `hunt-master-canonical-2026.json`, `canonical/hunt-planner-2026.json`, `generated/pages/hunt-planner.json`, `data/hunt-master-canonical-2026-database-candidate.csv`, `data/hunt-master-canonical-2026-source-of-truth.csv`, `processed_data/hunt-master-canonical-2026-source-of-truth.csv`.

## 1,411 To 1,394 Gap Explanation

- The former 17-code gap in stale 1,394-code catalog files is explained by new 2026 RAC rows.
- New 2026 antlerless elk rows: 16 hunt codes from `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_antlerless_elk_permits.csv`.
- New 2026 doe pronghorn rows: 1 hunt code, `PD1039`, from `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_doe_pronghorn_permits.csv`.
- Combined permits represented by those rows: 1150 total permits (`1034` resident / `116` nonresident).
- Detailed pullout: `processed_data/new_2026_rac_hunts_explain_1394_gap.md`.

## Notes

- Active 2026/name mismatches compare shared `hunt_name`, `permits_2026_*`, and `permit_allotment_2026_*` columns.
- Ambiguous `permits_year_*` columns are intentionally excluded; explicit `permits_2025_draw_*` and active 2026 allotment fields carry year-specific permit meaning.
- Hunt names are compared case-insensitively with whitespace normalized.
