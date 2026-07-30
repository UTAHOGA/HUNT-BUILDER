# 2026 Permit Allocation Integrity Report

Generated: 2026-07-30T11:19:29.911Z
Source file used: pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv
Source label: DATABASE_2026_DWR_APPROVED_PUBLISHED_PERMIT_ALLOCATIONS
Promotion blockers: 0

These fields represent DWR-approved/published 2026 permit allocations. They are intentionally separate from historical draw-result fields and harvest/performance fields.

## Status Counts

- FULL_SPLIT: 937
- TOTAL_ONLY: 227
- NO_QUOTA_PUBLISHED: 685
- PARTIAL_SPLIT: 0

## Files Audited

| File | Rows checked | Codes checked | Fields added | Fields updated | Mismatches before | Mismatches after | Blank values preserved | Target-only codes | Database-only codes |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| processed_data/hunt_unit_reference_linked.csv | 4762 | 1495 | none | none | 0 | 0 | 40148 | 36 | 354 |
| data/hunt-master-canonical-2026-database-candidate.json | 1471 | 1471 | none | none | 0 | 0 | 12788 | 0 | 378 |
| data/hunt-master-canonical-2026-foundation.json | 1471 | 1471 | none | none | 0 | 0 | 12788 | 0 | 378 |
| data/hunt-master-canonical-2026-source-of-truth.json | 1471 | 1471 | none | none | 0 | 0 | 12788 | 0 | 378 |
| processed_data/hunt-master-canonical-2026-source-of-truth.json | 1471 | 1471 | none | none | 0 | 0 | 12788 | 0 | 378 |
| canonical/hunt-planner-2026.json | 1471 | 1471 | none | data_status, permit_allocation_type, permit_note, permit_overlay_source, permit_source_authority, permit_status, permits_2026_nr, permits_2026_res, permits_2026_source, permits_2026_total | 9392 | 0 | 12788 | 0 | 378 |
| generated/pages/hunt-planner.json | 1471 | 1471 | none | data_status, permit_allocation_type, permit_note, permit_overlay_source, permit_source_authority, permit_status, permits_2026_nr, permits_2026_res, permits_2026_source, permits_2026_total | 9392 | 0 | 12788 | 0 | 378 |
| generated/pages/hunt-research.json | 0 | 0 | data_status, permit_allocation_type, permit_note, permit_overlay_source, permit_source_authority, permit_status, permits_2026_conservation, permits_2026_expo, permits_2026_nr, permits_2026_res, permits_2026_source, permits_2026_sportsman, permits_2026_total, special_permit_area_id, special_permit_category, special_permit_note, special_permit_overlay_source | none | 51 | 0 | 0 | 0 | 0 |

## Changed Files

- canonical/hunt-planner-2026.json
- generated/pages/hunt-planner.json
- generated/pages/hunt-research.json

