# 2026 Permit Allocation Integrity Report

Generated: 2026-07-30T11:11:39.005Z
Source file used: pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv
Source label: DATABASE_2026_DWR_APPROVED_PUBLISHED_PERMIT_ALLOCATIONS
Promotion blockers: 7

## Status Counts

- FULL_SPLIT: 937
- TOTAL_ONLY: 227
- SPECIAL_PERMIT_ONLY: 0
- NO_QUOTA_PUBLISHED: 685
- PARTIAL_SPLIT: 0

## Files Audited

| File | Rows checked | Codes checked | Mismatches before | Mismatches after | Blank values preserved | Target-only codes | Database-only codes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| processed_data/hunt_unit_reference_linked.csv | 4762 | 1495 | 156 | 7703 | 39998 | 36 | 354 |
| data/hunt-master-canonical-2026-database-candidate.json | 1471 | 1471 | 0 | 12583 | 12643 | 0 | 378 |
| data/hunt-master-canonical-2026-foundation.json | 1471 | 1471 | 0 | 12583 | 12643 | 0 | 378 |
| data/hunt-master-canonical-2026-source-of-truth.json | 1471 | 1471 | 0 | 12583 | 12643 | 0 | 378 |
| processed_data/hunt-master-canonical-2026-source-of-truth.json | 1471 | 1471 | 0 | 12583 | 12643 | 0 | 378 |
| canonical/hunt-planner-2026.json | 1411 | 1410 | 0 | 1511 | 12068 | 1 | 439 |
| generated/pages/hunt-planner.json | 1411 | 1410 | 0 | 1511 | 12068 | 1 | 439 |
| generated/pages/hunt-research.json | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Guardrails

- Allocation fields match DATABASE.csv: FAIL
- Historical draw-result and harvest/performance fields are not accepted as allocation sources.
- TOTAL_ONLY rows may not contain inferred resident/nonresident splits.
- NO_QUOTA_PUBLISHED rows may not contain invented permit totals.
- SPECIAL_PERMIT_ONLY rows may contain special permit counts while remaining excluded from normal public draw permit totals.
- Source/provenance markers are required.

## Skipped Missing Targets

- processed_data/hunt_master_enriched.csv
- processed_data/draw_reality_engine.csv
- processed_data/point_ladder_view.csv

