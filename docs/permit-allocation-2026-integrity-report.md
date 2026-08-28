# 2026 Permit Allocation Integrity Report

Generated: 2026-08-28T10:53:45.301Z
Source file used: pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv
Source label: DATABASE_2026_DWR_APPROVED_PUBLISHED_PERMIT_ALLOCATIONS
Promotion blockers: 0

These fields represent DWR-approved/published 2026 permit allocations. They are intentionally separate from historical draw-result fields and harvest/performance fields.

## Status Counts

- FULL_SPLIT: 932
- TOTAL_ONLY: 227
- NO_QUOTA_PUBLISHED: 665
- PARTIAL_SPLIT: 0

## Files Audited

| File | Rows checked | Codes checked | Fields added | Fields updated | Mismatches before | Mismatches after | Blank values preserved | Target-only codes | Database-only codes |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| data/hunt-master-canonical-2026-database-candidate.csv | 1471 | 1471 | none | conservation_permits_2026_total, data_status, permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, permits_2026_nr, permits_2026_res, permits_2026_source, permits_2026_total | 3138 | 0 | 1390 | 0 | 378 |
| data/hunt-master-canonical-2026-foundation.csv | 1471 | 1471 | none | conservation_permits_2026_total, data_status, permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, permits_2026_nr, permits_2026_res, permits_2026_source, permits_2026_total | 3138 | 0 | 1390 | 0 | 378 |
| data/hunt-master-canonical-2026-source-of-truth.csv | 1471 | 1471 | none | conservation_permits_2026_total, data_status, permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, permits_2026_nr, permits_2026_res, permits_2026_source, permits_2026_total | 3138 | 0 | 1390 | 0 | 378 |
| public/hunt-docs/latest/availability_only.csv | 49539 | 269 | none | permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, permits_2026_nr, permits_2026_res, permits_2026_total | 124744 | 0 | 7024 | 0 | 1580 |
| public/hunt-docs/latest/public_all_hunts.csv | 116813 | 607 | none | permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, permits_2026_nr, permits_2026_res, permits_2026_total | 206179 | 0 | 126931 | 0 | 1242 |
| data/hunt-master-canonical-2026-database-candidate.json | 1471 | 1471 | none | conservation_permits_2026_total, data_status, permit_allocation_type, permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, permit_status, permits_2026_conservation, permits_2026_nr, permits_2026_res, permits_2026_total | 437 | 0 | 12409 | 0 | 378 |
| data/hunt-master-canonical-2026-foundation.json | 1471 | 1471 | none | conservation_permits_2026_total, data_status, permit_allocation_type, permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, permit_status, permits_2026_conservation, permits_2026_nr, permits_2026_res, permits_2026_total | 437 | 0 | 12409 | 0 | 378 |
| data/hunt-master-canonical-2026-source-of-truth.json | 1471 | 1471 | none | conservation_permits_2026_total, data_status, permit_allocation_type, permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, permit_status, permits_2026_conservation, permits_2026_nr, permits_2026_res, permits_2026_total | 437 | 0 | 12409 | 0 | 378 |
| canonical/hunt-planner-2026.json | 1471 | 1471 | none | conservation_permits_2026_total, data_status, permit_allocation_type, permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, permit_status, permits_2026_conservation, permits_2026_nr, permits_2026_res, permits_2026_total | 437 | 0 | 12409 | 0 | 378 |
| generated/pages/hunt-planner.json | 1471 | 1471 | none | conservation_permits_2026_total, data_status, permit_allocation_type, permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, permit_status, permits_2026_conservation, permits_2026_nr, permits_2026_res, permits_2026_total | 437 | 0 | 12409 | 0 | 378 |
| data/hunt_application_outlook.json | 2898 | 1449 | none | permits_2026_res, permits_2026_total | 364 | 0 | 1700 | 0 | 400 |
| processed_data/public_contracts/hunt_application_outlook.json | 2898 | 1449 | none | permits_2026_res, permits_2026_total | 364 | 0 | 1700 | 0 | 400 |
| generated/pages/hunt-research.json | 0 | 0 | none | none | 0 | 0 | 0 | 0 | 0 |

## Changed Files

- data/hunt-master-canonical-2026-database-candidate.csv
- data/hunt-master-canonical-2026-foundation.csv
- data/hunt-master-canonical-2026-source-of-truth.csv
- public/hunt-docs/latest/availability_only.csv
- public/hunt-docs/latest/public_all_hunts.csv
- data/hunt-master-canonical-2026-database-candidate.json
- data/hunt-master-canonical-2026-foundation.json
- data/hunt-master-canonical-2026-source-of-truth.json
- canonical/hunt-planner-2026.json
- generated/pages/hunt-planner.json
- data/hunt_application_outlook.json
- processed_data/public_contracts/hunt_application_outlook.json

