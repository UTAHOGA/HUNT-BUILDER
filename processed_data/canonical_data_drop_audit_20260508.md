# Canonical Data Drop Audit

Generated: 2026-05-08T15:45:59.628Z

## Summary

| Source | Target | Source codes | Target codes | Shared | Missing in target | Source-only fields | Significant drop |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| DATABASE.csv | canonical/hunt-planner-2026.json hunt_catalog | 1394 | 1394 | 1394 | 0 | 0 | no |
| DATABASE.csv | generated/pages/hunt-planner.json hunt_catalog | 1394 | 1394 | 1394 | 0 | 0 | no |
| DATABASE.csv | hunt-master-canonical-2026.json hunt_catalog | 1394 | 1394 | 1394 | 0 | 5 | YES |
| hunt_master_canonical_2026_built.csv | canonical/hunt-planner-2026.json hunt_catalog | 1289 | 1394 | 1288 | 1 | 2 | YES |
| hunt_master_canonical_2026_built.csv | generated/pages/hunt-planner.json hunt_catalog | 1289 | 1394 | 1288 | 1 | 2 | YES |
| hunt_master_canonical_2026_built.csv | hunt-master-canonical-2026.json hunt_catalog | 1289 | 1394 | 1288 | 1 | 2 | YES |
| processed_data/hunt_master_enriched.csv | canonical/hunt-planner-2026.json hunt_catalog | 1394 | 1394 | 1394 | 0 | 18 | YES |
| processed_data/hunt_master_enriched.csv | generated/pages/hunt-planner.json hunt_catalog | 1394 | 1394 | 1394 | 0 | 18 | YES |
| processed_data/hunt_master_enriched.csv | hunt-master-canonical-2026.json hunt_catalog | 1394 | 1394 | 1394 | 0 | 24 | YES |
| hunt-master-canonical-2026-foundation.json | canonical/hunt-planner-2026.json hunt_catalog | 1394 | 1394 | 1394 | 0 | 0 | no |
| hunt-master-canonical-2026-foundation.json | generated/pages/hunt-planner.json hunt_catalog | 1394 | 1394 | 1394 | 0 | 0 | no |
| hunt-master-canonical-2026-foundation.json | hunt-master-canonical-2026.json hunt_catalog | 1394 | 1394 | 1394 | 0 | 6 | YES |

## DATABASE.csv -> canonical/hunt-planner-2026.json hunt_catalog

- Source rows: 1395
- Target rows: 1394
- Source unique hunt codes: 1394
- Target unique hunt codes: 1394
- Missing in target: 0
- Extra in target: 0
- Source duplicate codes: 0
- Target duplicate codes: 0

### Shared-field mismatches, top fields

- NOTES: 5/5 checked differ

## DATABASE.csv -> generated/pages/hunt-planner.json hunt_catalog

- Source rows: 1395
- Target rows: 1394
- Source unique hunt codes: 1394
- Target unique hunt codes: 1394
- Missing in target: 0
- Extra in target: 0
- Source duplicate codes: 0
- Target duplicate codes: 0

### Shared-field mismatches, top fields

- NOTES: 5/5 checked differ

## DATABASE.csv -> hunt-master-canonical-2026.json hunt_catalog

- Source rows: 1395
- Target rows: 1394
- Source unique hunt codes: 1394
- Target unique hunt codes: 1394
- Missing in target: 0
- Extra in target: 0
- Source duplicate codes: 0
- Target duplicate codes: 0

### Meaningful source-only fields

- permits_2026_conservation: 1 | 2 | 8 | 4
- special_permit_area_id: CONSERVATION_ROCKY_MOUNTAIN_BIGHORN_SHEEP_BOOK_CLIFFS_SOUTH_2026 | CONSERVATION_ROCKY_MOUNTAIN_BIGHORN_SHEEP_BOX_ELDER_NEWFOUNDLAND_MTNS_2026 | CONSERVATION_ROCKY_MOUNTAIN_BIGHORN_SHEEP_NINE_MILE_GRAY_CANYON_2026 | CONSERVATION_TURKEY_CENTRAL_AREA_2026
- special_permit_category: CONSERVATION
- special_permit_note: 2026 conservation permit count from 2025-2027 conservation workbook source area: Book Cliffs, South (Any Legal Weapon). Kept outside normal public draw quota. | 2026 conservation permit count from 2025-2027 conservation workbook source area: Box Elder, Newfoundland Mtns (early) (Any Legal Weapon); Box Elder, Newfoundland Mtns (late) (Any Legal Weapon). Kept outside normal public draw quota. | 2026 conservation permit count from 2025-2027 conservation workbook source area: Nine Mile, Gray Canyon (Any Legal Weapon). Kept outside normal public draw quota. | 2026 conservation permit count from 2025-2027 conservation workbook source area: Central Area (Multiseason). Kept outside normal public draw quota.
- special_permit_overlay_source: pipeline/RAW/hunt_unit_database/2026/reports/conservation_raw_workbook_grouped_2026.csv | pipeline/RAW/hunt_unit_database/2026/reports/conservation_area_crosswalk_2026.csv

### Shared-field mismatches, top fields

- permits_2026_total: 1/1074 checked differ
- NOTES: 5/5 checked differ

## hunt_master_canonical_2026_built.csv -> canonical/hunt-planner-2026.json hunt_catalog

- Source rows: 1289
- Target rows: 1394
- Source unique hunt codes: 1289
- Target unique hunt codes: 1394
- Missing in target: 1 (DB1276)
- Extra in target: 106 (BR1001, BR1008, BR1009, BR1010, BR1011, BR1012, BR1013, BR1015, BR1016, BR1017, BR1018, BR7000, BR7001, BR7003, BR7004, BR7005, BR7007, BR7009, BR7010, BR7011, BR7012, BR7013, BR7014, BR7015, BR7016, BR7017, BR7018, BR7020, BR7021, BR7022, BR7100, BR7101, BR7102, BR7104, BR7105, BR7106, BR7109, BR7110, BR7111, BR7112, BR7113, BR7114, BR7115, BR7116, BR7117, BR7118, BR7119, BR7120, BR7121, BR7122, BR7123, BR7124, BR7125, BR7126, BR7127, BR7200, BR7201, BR7203, BR7204, BR7205, BR7207, BR7210, BR7211, BR7212, BR7213, BR7214, BR7215, BR7216, BR7217, BR7218, BR7219, BR7220, BR7221, BR7224, BR7225, BR7228, BR7229, BR7237, BR7238, BR7239, ...)
- Source duplicate codes: 0
- Target duplicate codes: 0

### Meaningful source-only fields

- avg_days_2026: 9.0 | 4.0 | 5.5 | 1.8
- satisfaction_2026: 3.6 | 4.0 | 4.3 | 4.8

### Shared-field mismatches, top fields

- sex_type: 134/1288 checked differ
- hunt_type: 85/1288 checked differ
- weapon: 108/1288 checked differ
- hunt_name: 128/1288 checked differ
- season: 12/1288 checked differ
- permits_2026_res: 792/792 checked differ
- permits_2026_nr: 788/788 checked differ
- permits_2026_total: 986/986 checked differ
- permit_status: 316/1288 checked differ
- permit_overlay_source: 1288/1288 checked differ
- source_authority: 175/1288 checked differ
- data_status: 502/1288 checked differ
- boundary_id: 1288/1288 checked differ

## hunt_master_canonical_2026_built.csv -> generated/pages/hunt-planner.json hunt_catalog

- Source rows: 1289
- Target rows: 1394
- Source unique hunt codes: 1289
- Target unique hunt codes: 1394
- Missing in target: 1 (DB1276)
- Extra in target: 106 (BR1001, BR1008, BR1009, BR1010, BR1011, BR1012, BR1013, BR1015, BR1016, BR1017, BR1018, BR7000, BR7001, BR7003, BR7004, BR7005, BR7007, BR7009, BR7010, BR7011, BR7012, BR7013, BR7014, BR7015, BR7016, BR7017, BR7018, BR7020, BR7021, BR7022, BR7100, BR7101, BR7102, BR7104, BR7105, BR7106, BR7109, BR7110, BR7111, BR7112, BR7113, BR7114, BR7115, BR7116, BR7117, BR7118, BR7119, BR7120, BR7121, BR7122, BR7123, BR7124, BR7125, BR7126, BR7127, BR7200, BR7201, BR7203, BR7204, BR7205, BR7207, BR7210, BR7211, BR7212, BR7213, BR7214, BR7215, BR7216, BR7217, BR7218, BR7219, BR7220, BR7221, BR7224, BR7225, BR7228, BR7229, BR7237, BR7238, BR7239, ...)
- Source duplicate codes: 0
- Target duplicate codes: 0

### Meaningful source-only fields

- avg_days_2026: 9.0 | 4.0 | 5.5 | 1.8
- satisfaction_2026: 3.6 | 4.0 | 4.3 | 4.8

### Shared-field mismatches, top fields

- sex_type: 134/1288 checked differ
- hunt_type: 85/1288 checked differ
- weapon: 108/1288 checked differ
- hunt_name: 128/1288 checked differ
- season: 12/1288 checked differ
- permits_2026_res: 792/792 checked differ
- permits_2026_nr: 788/788 checked differ
- permits_2026_total: 986/986 checked differ
- permit_status: 316/1288 checked differ
- permit_overlay_source: 1288/1288 checked differ
- source_authority: 175/1288 checked differ
- data_status: 502/1288 checked differ
- boundary_id: 1288/1288 checked differ

## hunt_master_canonical_2026_built.csv -> hunt-master-canonical-2026.json hunt_catalog

- Source rows: 1289
- Target rows: 1394
- Source unique hunt codes: 1289
- Target unique hunt codes: 1394
- Missing in target: 1 (DB1276)
- Extra in target: 106 (BR1001, BR1008, BR1009, BR1010, BR1011, BR1012, BR1013, BR1015, BR1016, BR1017, BR1018, BR7000, BR7001, BR7003, BR7004, BR7005, BR7007, BR7009, BR7010, BR7011, BR7012, BR7013, BR7014, BR7015, BR7016, BR7017, BR7018, BR7020, BR7021, BR7022, BR7100, BR7101, BR7102, BR7104, BR7105, BR7106, BR7109, BR7110, BR7111, BR7112, BR7113, BR7114, BR7115, BR7116, BR7117, BR7118, BR7119, BR7120, BR7121, BR7122, BR7123, BR7124, BR7125, BR7126, BR7127, BR7200, BR7201, BR7203, BR7204, BR7205, BR7207, BR7210, BR7211, BR7212, BR7213, BR7214, BR7215, BR7216, BR7217, BR7218, BR7219, BR7220, BR7221, BR7224, BR7225, BR7228, BR7229, BR7237, BR7238, BR7239, ...)
- Source duplicate codes: 0
- Target duplicate codes: 0

### Meaningful source-only fields

- avg_days_2026: 9.0 | 4.0 | 5.5 | 1.8
- satisfaction_2026: 3.6 | 4.0 | 4.3 | 4.8

### Shared-field mismatches, top fields

- sex_type: 134/1288 checked differ
- hunt_type: 85/1288 checked differ
- weapon: 108/1288 checked differ
- hunt_name: 128/1288 checked differ
- season: 12/1288 checked differ
- permits_2026_res: 792/792 checked differ
- permits_2026_nr: 788/788 checked differ
- permits_2026_total: 985/985 checked differ
- permit_status: 510/1288 checked differ
- permit_overlay_source: 896/1174 checked differ
- source_authority: 175/1288 checked differ
- data_status: 510/1288 checked differ
- boundary_id: 1288/1288 checked differ

## processed_data/hunt_master_enriched.csv -> canonical/hunt-planner-2026.json hunt_catalog

- Source rows: 53060
- Target rows: 1394
- Source unique hunt codes: 1394
- Target unique hunt codes: 1394
- Missing in target: 0
- Extra in target: 0
- Source duplicate codes: 1394
- Target duplicate codes: 0

### Meaningful source-only fields

- applicants_2025: 0 | 2 | 3 | 12
- max_point_permits_2026: 1 | 0 | 2 | 4
- missing_draw_data: TRUE | FALSE
- missing_permits: TRUE | FALSE
- missing_projection: TRUE | FALSE
- odds_2025: N/A | 1 in 2.0 | 1 in 342.0 | 1 in 6.5
- odds_2026_projected: 100.000 | 50.075 | 0.102 | 0.110
- points: 32 | 31 | 30 | 29
- projected_applicants_2026: 0 | 1 | 3 | 12
- projected_applicants_2026_source: projected_2026 | fallback_2025 | missing_projection_fill_v1
- public_permits_2025: 2 | 4 | 5 | 25
- public_permits_2026: 2 | 0 | 4 | 5
- public_permits_2026_source: DATABASE_2026_DWR_APPROVED_PUBLISHED_PERMIT_ALLOCATIONS
- random_permits_2026: 1 | 0 | 2 | 3
- residency: Resident | Nonresident
- success_harvest: 2 | 14 | 13 | 22
- success_hunters: 2 | 15 | 13 | 28
- success_percent: 100 | 93.3 | 78.6 | 93.1

### Shared-field mismatches, top fields

- species: 5/1394 checked differ
- hunt_name: 389/1394 checked differ
- weapon: 207/1394 checked differ
- hunt_type: 450/1394 checked differ
- access_type: 238/1394 checked differ

## processed_data/hunt_master_enriched.csv -> generated/pages/hunt-planner.json hunt_catalog

- Source rows: 53060
- Target rows: 1394
- Source unique hunt codes: 1394
- Target unique hunt codes: 1394
- Missing in target: 0
- Extra in target: 0
- Source duplicate codes: 1394
- Target duplicate codes: 0

### Meaningful source-only fields

- applicants_2025: 0 | 2 | 3 | 12
- max_point_permits_2026: 1 | 0 | 2 | 4
- missing_draw_data: TRUE | FALSE
- missing_permits: TRUE | FALSE
- missing_projection: TRUE | FALSE
- odds_2025: N/A | 1 in 2.0 | 1 in 342.0 | 1 in 6.5
- odds_2026_projected: 100.000 | 50.075 | 0.102 | 0.110
- points: 32 | 31 | 30 | 29
- projected_applicants_2026: 0 | 1 | 3 | 12
- projected_applicants_2026_source: projected_2026 | fallback_2025 | missing_projection_fill_v1
- public_permits_2025: 2 | 4 | 5 | 25
- public_permits_2026: 2 | 0 | 4 | 5
- public_permits_2026_source: DATABASE_2026_DWR_APPROVED_PUBLISHED_PERMIT_ALLOCATIONS
- random_permits_2026: 1 | 0 | 2 | 3
- residency: Resident | Nonresident
- success_harvest: 2 | 14 | 13 | 22
- success_hunters: 2 | 15 | 13 | 28
- success_percent: 100 | 93.3 | 78.6 | 93.1

### Shared-field mismatches, top fields

- species: 5/1394 checked differ
- hunt_name: 389/1394 checked differ
- weapon: 207/1394 checked differ
- hunt_type: 450/1394 checked differ
- access_type: 238/1394 checked differ

## processed_data/hunt_master_enriched.csv -> hunt-master-canonical-2026.json hunt_catalog

- Source rows: 53060
- Target rows: 1394
- Source unique hunt codes: 1394
- Target unique hunt codes: 1394
- Missing in target: 0
- Extra in target: 0
- Source duplicate codes: 1394
- Target duplicate codes: 0

### Meaningful source-only fields

- applicants_2025: 0 | 2 | 3 | 12
- max_point_permits_2026: 1 | 0 | 2 | 4
- missing_draw_data: TRUE | FALSE
- missing_permits: TRUE | FALSE
- missing_projection: TRUE | FALSE
- odds_2025: N/A | 1 in 2.0 | 1 in 342.0 | 1 in 6.5
- odds_2026_projected: 100.000 | 50.075 | 0.102 | 0.110
- permits_2026_conservation: 2 | 1 | 4 | 8
- permits_2026_source: DATABASE_2026_DWR_APPROVED_PUBLISHED_PERMIT_ALLOCATIONS
- points: 32 | 31 | 30 | 29
- projected_applicants_2026: 0 | 1 | 3 | 12
- projected_applicants_2026_source: projected_2026 | fallback_2025 | missing_projection_fill_v1
- public_permits_2025: 2 | 4 | 5 | 25
- public_permits_2026: 2 | 0 | 4 | 5
- public_permits_2026_source: DATABASE_2026_DWR_APPROVED_PUBLISHED_PERMIT_ALLOCATIONS
- random_permits_2026: 1 | 0 | 2 | 3
- residency: Resident | Nonresident
- special_permit_area_id: CONSERVATION_DEER_BOOK_CLIFFS_2026 | CONSERVATION_DESERT_BIGHORN_SHEEP_KAIPAROWITS_EAST_2026 | CONSERVATION_DESERT_BIGHORN_SHEEP_KAIPAROWITS_ESCALANTE_2026 | CONSERVATION_DESERT_BIGHORN_SHEEP_SAN_RAFAEL_DIRTY_DEVIL_2026
- special_permit_category: CONSERVATION
- special_permit_note: 2026 conservation permit count from 2025-2027 conservation workbook source area: Book Cliffs (Hunter's Choice - winning bidder chooses one eligible season for that unit/species; not a multiseason permit). Kept outside normal public draw quota. | 2026 conservation permit count from 2025-2027 conservation workbook source area: Kaiparowits, East (Any Legal Weapon). Kept outside normal public draw quota. | 2026 conservation permit count from 2025-2027 conservation workbook source area: Kaiparowits, Escalante (Any Legal Weapon). Kept outside normal public draw quota. | 2026 conservation permit count from 2025-2027 conservation workbook source area: San Rafael, Dirty Devil (Any Legal Weapon). Kept outside normal public draw quota.
- special_permit_overlay_source: pipeline/RAW/hunt_unit_database/2026/reports/conservation_raw_workbook_grouped_2026.csv | pipeline/RAW/hunt_unit_database/2026/reports/conservation_area_crosswalk_2026.csv
- success_harvest: 2 | 14 | 13 | 22
- success_hunters: 2 | 15 | 13 | 28
- success_percent: 100 | 93.3 | 78.6 | 93.1

### Shared-field mismatches, top fields

- species: 5/1394 checked differ
- hunt_name: 389/1394 checked differ
- weapon: 207/1394 checked differ
- hunt_type: 450/1394 checked differ
- access_type: 238/1394 checked differ
- permits_2026_total: 1/1074 checked differ
- permit_status: 335/1394 checked differ
- permit_allocation_type: 1114/1394 checked differ
- permit_source_authority: 1394/1394 checked differ
- permit_note: 1003/1003 checked differ
- permit_overlay_source: 1394/1394 checked differ
- data_status: 516/1394 checked differ

## hunt-master-canonical-2026-foundation.json -> canonical/hunt-planner-2026.json hunt_catalog

- Source rows: 1394
- Target rows: 1394
- Source unique hunt codes: 1394
- Target unique hunt codes: 1394
- Missing in target: 0
- Extra in target: 0
- Source duplicate codes: 0
- Target duplicate codes: 0

## hunt-master-canonical-2026-foundation.json -> generated/pages/hunt-planner.json hunt_catalog

- Source rows: 1394
- Target rows: 1394
- Source unique hunt codes: 1394
- Target unique hunt codes: 1394
- Missing in target: 0
- Extra in target: 0
- Source duplicate codes: 0
- Target duplicate codes: 0

## hunt-master-canonical-2026-foundation.json -> hunt-master-canonical-2026.json hunt_catalog

- Source rows: 1394
- Target rows: 1394
- Source unique hunt codes: 1394
- Target unique hunt codes: 1394
- Missing in target: 0
- Extra in target: 0
- Source duplicate codes: 0
- Target duplicate codes: 0

### Meaningful source-only fields

- permits_2026_conservation: 2 | 1 | 4 | 8
- permits_2026_source: DATABASE_2026_DWR_APPROVED_PUBLISHED_PERMIT_ALLOCATIONS
- special_permit_area_id: CONSERVATION_DEER_BOOK_CLIFFS_2026 | CONSERVATION_DEER_LA_SAL_DOLORES_TRIANGLE_2026 | CONSERVATION_DESERT_BIGHORN_SHEEP_KAIPAROWITS_EAST_2026 | CONSERVATION_DESERT_BIGHORN_SHEEP_KAIPAROWITS_ESCALANTE_2026
- special_permit_category: CONSERVATION
- special_permit_note: 2026 conservation permit count from 2025-2027 conservation workbook source area: Book Cliffs (Hunter's Choice - winning bidder chooses one eligible season for that unit/species; not a multiseason permit). Kept outside normal public draw quota. | 2026 conservation permit count from 2025-2027 conservation workbook source area: Book Cliffs (Archery). Kept outside normal public draw quota. | 2026 conservation permit count from 2025-2027 conservation workbook source area: La Sal, Dolores Triangle (Multiseason). Kept outside normal public draw quota. | 2026 conservation permit count from 2025-2027 conservation workbook source area: Book Cliffs (Muzzleloader). Kept outside normal public draw quota.
- special_permit_overlay_source: pipeline/RAW/hunt_unit_database/2026/reports/conservation_raw_workbook_grouped_2026.csv | pipeline/RAW/hunt_unit_database/2026/reports/conservation_area_crosswalk_2026.csv

### Shared-field mismatches, top fields

- boundary_id: 143/1394 checked differ
- permits_2026_total: 1/1074 checked differ
- permit_status: 335/1394 checked differ
- permit_allocation_type: 1114/1394 checked differ
- permit_source_authority: 1394/1394 checked differ
- permit_note: 1003/1003 checked differ
- permit_overlay_source: 1394/1394 checked differ
- data_status: 516/1394 checked differ

