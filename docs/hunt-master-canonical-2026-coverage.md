# Hunt Master Canonical 2026 Coverage

This report documents the coverage receipt for `hunt-master-canonical-2026.json`.

## Summary

- Source files inspected: `24`
- Fields discovered: `820`
- Fields mapped: `85`
- Fields intentionally unmapped: `735`
- Owner-input markers: `2928`
- Source-needed regulatory/legal markers: `14`
- Hunt catalog rows: `1394`

## 1. Source Files Inspected

| path | exists | bytes | inspection_method |
| --- | --- | --- | --- |
| Canonical JSON rules.md | True | 504 | targeted canonical build source |
| config.js | True | 21281 | targeted canonical build source |
| app.js | True | 221425 | targeted canonical build source |
| data.js | True | 20854 | targeted canonical build source |
| boundary-resolver.js | True | 13300 | targeted canonical build source |
| hunt-research.js | True | 48484 | targeted canonical build source |
| docs/data_feed_contract.md | True | 1737 | targeted canonical build source |
| docs/predictive_engine_design.md | True | 1573 | targeted canonical build source |
| HARVEST_AND_REPORT_YEAR_RULES.md | True | 1528 | targeted canonical build source |
| data/hunt-master-canonical-2026-database-candidate.json | True | 2591773 | targeted canonical build source |
| data/hunt-master-canonical-2026-database-candidate.csv | True | 739463 | targeted canonical build source |
| pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv | True | 172848 | targeted canonical build source |
| data/outfitters-master.json | True | 25968 | targeted canonical build source |
| data/outfitters.json | True | 8293 | targeted canonical build source |
| processed_data/display-boundary-index-2026.json | True | 600616 | targeted canonical build source |
| processed_data/boundary-manifest-2026.json | True | 26122 | targeted canonical build source |
| processed_data/draw_reality_engine.csv | True | 12028512 | targeted canonical build source |
| processed_data/point_ladder_view.csv | True | 4222873 | targeted canonical build source |
| processed_data/hunt_master_enriched.csv | True | 8297771 | targeted canonical build source |
| processed_data/hunt_unit_reference_linked.csv | True | 754497 | targeted canonical build source |
| schemas/hunt-master-canonical-2026.schema.json | True | 6908 | targeted canonical build source |
| scripts/validate-canonical-json.js | True | 6436 | targeted canonical build source |
| tests/validate-canonical-json.test.js | True | 1954 | targeted canonical build source |
| package.json | True | 1060 | targeted canonical build source |

## 2. App-Facing Fields Found

The broad scan found app/runtime, CSV, and JSON fields. Mapped app-facing fields are listed below; implementation-only tokens are listed as intentionally unmapped in the coverage JSON.

| field | canonical_path | sources |
| --- | --- | --- |
| $schema | $schema | schemas/hunt-master-canonical-2026.schema.json |
| NOTES | hunt_catalog[].NOTES | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv |
| access_type | hunt_catalog[].access_type | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv |
| avg_days_2025 | hunt_catalog[].avg_days_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| avg_points_2025 | hunt_catalog[].avg_points_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| boundaryId | hunt_catalog[].boundaryId | app.js, boundary-resolver.js, data.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| boundary_geojson_path | hunt_catalog[].geometry.boundary_geojson_path | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| boundary_id | hunt_catalog[].boundary_id | app.js, boundary-resolver.js, data.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| boundary_id_numeric | hunt_catalog[].boundary_id_numeric | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| boundary_kmz_path | hunt_catalog[].geometry.boundary_kmz_path | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| boundary_token | hunt_catalog[].boundary_token | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| branding | outfitters[].branding | app.js, data/outfitters-master.json |
| businessName | outfitters[].businessName | app.js, data/outfitters-master.json |
| certLevel | outfitters[].certLevel | app.js, data/outfitters-master.json, data/outfitters.json |
| code | hunt_catalog[].code | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, scripts/validate-canonical-json.js |
| compliance | outfitters[].compliance | data/outfitters-master.json |
| contact | outfitters[].contact | app.js, data/outfitters-master.json |
| data_status | hunt_catalog[].data_status | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| displayName | outfitters[].displayName | app.js, data/outfitters-master.json |
| display_boundary_id | hunt_catalog[].geometry.display_boundary_id | app.js, processed_data/display-boundary-index-2026.json |
| draw_2025_bg_pdf_page | hunt_catalog[].draw_2025_bg_pdf_page | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| draw_2025_bg_report_page | hunt_catalog[].draw_2025_bg_report_page | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| draw_2025_species_section | hunt_catalog[].draw_2025_species_section | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| draw_2025_type | hunt_catalog[].draw_2025_type | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| draw_family | hunt_catalog[].draw_family | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| dwr_boundary_id | hunt_catalog[].geometry.dwr_boundary_id | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| dwr_member_boundary_ids | hunt_catalog[].geometry.dwr_member_boundary_ids | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| eligibility_class | hunt_catalog[].eligibility_class | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| geometry | hunt_catalog[].geometry | config.js, scripts/validate-canonical-json.js |
| geometry_status | hunt_catalog[].geometry.geometry_status | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| harvest_2025 | hunt_catalog[].harvest_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, processed_data/hunt_unit_reference_linked.csv |
| has_antlerless_draw | hunt_catalog[].has_antlerless_draw | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| has_bonus_draw | hunt_catalog[].has_bonus_draw | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| has_harvest | hunt_catalog[].has_harvest | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| headquarters | outfitters[].headquarters | app.js, data/outfitters-master.json |
| huntCode | hunt_catalog[].huntCode | app.js, boundary-resolver.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, scripts/validate-canonical-json.js |
| huntFit | outfitters[].huntFit | data/outfitters-master.json |
| hunt_class | hunt_catalog[].hunt_class | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| hunt_code | hunt_catalog[].hunt_code | app.js, boundary-resolver.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, hunt-research.js, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/display-boundary-index-2026.json, processed_data/draw_reality_engine.csv, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv, processed_data/point_ladder_view.csv, scripts/validate-canonical-json.js |
| hunt_name | hunt_catalog[].hunt_name | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| hunt_type | hunt_catalog[].hunt_type | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| hunters_2025 | hunt_catalog[].hunters_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| id | hunt_catalog[].id | app.js, data/outfitters-master.json, scripts/validate-canonical-json.js |
| internal | outfitters[].internal | data/outfitters-master.json |
| legalBusinessName | outfitters[].legalBusinessName | app.js, data/outfitters-master.json |
| listingName | outfitters[].displayName or outfitters[].businessName via existing outfitter master normalization | app.js, data/outfitters.json |
| listingType | outfitters[].listingType | app.js, data/outfitters-master.json, data/outfitters.json |
| memberStatus | outfitters[].memberStatus | data/outfitters-master.json |
| permit_allocation_type | hunt_catalog[].permit_allocation_type | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permit_note | hunt_catalog[].permit_note | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permit_overlay_source | hunt_catalog[].permit_overlay_source | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permit_source_authority | hunt_catalog[].permit_source_authority | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permit_status | hunt_catalog[].permit_status | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permits_2025_draw_nr | hunt_catalog[].permits_2025_draw_nr | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permits_2025_draw_res | hunt_catalog[].permits_2025_draw_res | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permits_2025_draw_total | hunt_catalog[].permits_2025_draw_total | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permits_2025_nr | hunt_catalog[].permits_2025_nr | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, processed_data/hunt_unit_reference_linked.csv |
| permits_2025_res | hunt_catalog[].permits_2025_res | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, processed_data/hunt_unit_reference_linked.csv |
| permits_2025_total | hunt_catalog[].permits_2025_total | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, processed_data/hunt_unit_reference_linked.csv |
| permits_2026_nr | hunt_catalog[].permits_2026_nr | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, hunt-research.js, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| permits_2026_res | hunt_catalog[].permits_2026_res | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, hunt-research.js, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| permits_2026_total | hunt_catalog[].permits_2026_total | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| provenance | hunt_catalog[].provenance | scripts/validate-canonical-json.js |
| publicStatus | outfitters[].publicStatus | data/outfitters-master.json |
| publication | outfitters[].publication | data/outfitters-master.json |
| referralPriority | outfitters[].referralPriority | data/outfitters-master.json |
| referralRotationGroup | outfitters[].referralRotationGroup | data/outfitters-master.json |
| referralStatus | outfitters[].referralStatus | data/outfitters-master.json |
| resolvedBoundaryIds | hunt_catalog[].resolvedBoundaryIds | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| satisfaction_2025 | hunt_catalog[].satisfaction_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| season | hunt_catalog[].season | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, scripts/validate-canonical-json.js |
| serviceArea | outfitters[].serviceArea | app.js, data/outfitters-master.json |
| services | outfitters[].services | app.js, data/outfitters-master.json |
| sex_type | hunt_catalog[].sex_type | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, scripts/validate-canonical-json.js |
| slug | outfitters[].slug | app.js, data/outfitters-master.json |
| source_authority | hunt_catalog[].source_authority | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| source_file | hunt_catalog[].source_file | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| species | hunt_catalog[].species | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| success_percent_2025 | hunt_catalog[].success_percent_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| title | hunt_catalog[].title | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, schemas/hunt-master-canonical-2026.schema.json, scripts/validate-canonical-json.js |
| unitCode | hunt_catalog[].unitCode | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| unitName | hunt_catalog[].unitName | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, scripts/validate-canonical-json.js |
| verificationStatus | outfitters[].verificationStatus | app.js, data/outfitters-master.json, data/outfitters.json |
| weapon | hunt_catalog[].weapon | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| youth_flag | hunt_catalog[].youth_flag | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |

## 3. Field Mapping Into `hunt-master-canonical-2026.json`

| field | canonical_path | sources |
| --- | --- | --- |
| $schema | $schema | schemas/hunt-master-canonical-2026.schema.json |
| NOTES | hunt_catalog[].NOTES | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv |
| access_type | hunt_catalog[].access_type | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv |
| avg_days_2025 | hunt_catalog[].avg_days_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| avg_points_2025 | hunt_catalog[].avg_points_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| boundaryId | hunt_catalog[].boundaryId | app.js, boundary-resolver.js, data.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| boundary_geojson_path | hunt_catalog[].geometry.boundary_geojson_path | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| boundary_id | hunt_catalog[].boundary_id | app.js, boundary-resolver.js, data.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| boundary_id_numeric | hunt_catalog[].boundary_id_numeric | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| boundary_kmz_path | hunt_catalog[].geometry.boundary_kmz_path | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| boundary_token | hunt_catalog[].boundary_token | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| branding | outfitters[].branding | app.js, data/outfitters-master.json |
| businessName | outfitters[].businessName | app.js, data/outfitters-master.json |
| certLevel | outfitters[].certLevel | app.js, data/outfitters-master.json, data/outfitters.json |
| code | hunt_catalog[].code | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, scripts/validate-canonical-json.js |
| compliance | outfitters[].compliance | data/outfitters-master.json |
| contact | outfitters[].contact | app.js, data/outfitters-master.json |
| data_status | hunt_catalog[].data_status | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| displayName | outfitters[].displayName | app.js, data/outfitters-master.json |
| display_boundary_id | hunt_catalog[].geometry.display_boundary_id | app.js, processed_data/display-boundary-index-2026.json |
| draw_2025_bg_pdf_page | hunt_catalog[].draw_2025_bg_pdf_page | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| draw_2025_bg_report_page | hunt_catalog[].draw_2025_bg_report_page | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| draw_2025_species_section | hunt_catalog[].draw_2025_species_section | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| draw_2025_type | hunt_catalog[].draw_2025_type | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| draw_family | hunt_catalog[].draw_family | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| dwr_boundary_id | hunt_catalog[].geometry.dwr_boundary_id | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| dwr_member_boundary_ids | hunt_catalog[].geometry.dwr_member_boundary_ids | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| eligibility_class | hunt_catalog[].eligibility_class | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| geometry | hunt_catalog[].geometry | config.js, scripts/validate-canonical-json.js |
| geometry_status | hunt_catalog[].geometry.geometry_status | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| harvest_2025 | hunt_catalog[].harvest_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, processed_data/hunt_unit_reference_linked.csv |
| has_antlerless_draw | hunt_catalog[].has_antlerless_draw | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| has_bonus_draw | hunt_catalog[].has_bonus_draw | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| has_harvest | hunt_catalog[].has_harvest | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| headquarters | outfitters[].headquarters | app.js, data/outfitters-master.json |
| huntCode | hunt_catalog[].huntCode | app.js, boundary-resolver.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, scripts/validate-canonical-json.js |
| huntFit | outfitters[].huntFit | data/outfitters-master.json |
| hunt_class | hunt_catalog[].hunt_class | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| hunt_code | hunt_catalog[].hunt_code | app.js, boundary-resolver.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, hunt-research.js, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/display-boundary-index-2026.json, processed_data/draw_reality_engine.csv, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv, processed_data/point_ladder_view.csv, scripts/validate-canonical-json.js |
| hunt_name | hunt_catalog[].hunt_name | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| hunt_type | hunt_catalog[].hunt_type | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| hunters_2025 | hunt_catalog[].hunters_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| id | hunt_catalog[].id | app.js, data/outfitters-master.json, scripts/validate-canonical-json.js |
| internal | outfitters[].internal | data/outfitters-master.json |
| legalBusinessName | outfitters[].legalBusinessName | app.js, data/outfitters-master.json |
| listingName | outfitters[].displayName or outfitters[].businessName via existing outfitter master normalization | app.js, data/outfitters.json |
| listingType | outfitters[].listingType | app.js, data/outfitters-master.json, data/outfitters.json |
| memberStatus | outfitters[].memberStatus | data/outfitters-master.json |
| permit_allocation_type | hunt_catalog[].permit_allocation_type | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permit_note | hunt_catalog[].permit_note | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permit_overlay_source | hunt_catalog[].permit_overlay_source | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permit_source_authority | hunt_catalog[].permit_source_authority | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permit_status | hunt_catalog[].permit_status | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permits_2025_draw_nr | hunt_catalog[].permits_2025_draw_nr | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permits_2025_draw_res | hunt_catalog[].permits_2025_draw_res | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permits_2025_draw_total | hunt_catalog[].permits_2025_draw_total | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| permits_2025_nr | hunt_catalog[].permits_2025_nr | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, processed_data/hunt_unit_reference_linked.csv |
| permits_2025_res | hunt_catalog[].permits_2025_res | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, processed_data/hunt_unit_reference_linked.csv |
| permits_2025_total | hunt_catalog[].permits_2025_total | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, processed_data/hunt_unit_reference_linked.csv |
| permits_2026_nr | hunt_catalog[].permits_2026_nr | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, hunt-research.js, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| permits_2026_res | hunt_catalog[].permits_2026_res | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, hunt-research.js, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| permits_2026_total | hunt_catalog[].permits_2026_total | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| provenance | hunt_catalog[].provenance | scripts/validate-canonical-json.js |
| publicStatus | outfitters[].publicStatus | data/outfitters-master.json |
| publication | outfitters[].publication | data/outfitters-master.json |
| referralPriority | outfitters[].referralPriority | data/outfitters-master.json |
| referralRotationGroup | outfitters[].referralRotationGroup | data/outfitters-master.json |
| referralStatus | outfitters[].referralStatus | data/outfitters-master.json |
| resolvedBoundaryIds | hunt_catalog[].resolvedBoundaryIds | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| satisfaction_2025 | hunt_catalog[].satisfaction_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| season | hunt_catalog[].season | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, scripts/validate-canonical-json.js |
| serviceArea | outfitters[].serviceArea | app.js, data/outfitters-master.json |
| services | outfitters[].services | app.js, data/outfitters-master.json |
| sex_type | hunt_catalog[].sex_type | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, scripts/validate-canonical-json.js |
| slug | outfitters[].slug | app.js, data/outfitters-master.json |
| source_authority | hunt_catalog[].source_authority | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| source_file | hunt_catalog[].source_file | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| species | hunt_catalog[].species | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| success_percent_2025 | hunt_catalog[].success_percent_2025 | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| title | hunt_catalog[].title | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, schemas/hunt-master-canonical-2026.schema.json, scripts/validate-canonical-json.js |
| unitCode | hunt_catalog[].unitCode | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |
| unitName | hunt_catalog[].unitName | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, scripts/validate-canonical-json.js |
| verificationStatus | outfitters[].verificationStatus | app.js, data/outfitters-master.json, data/outfitters.json |
| weapon | hunt_catalog[].weapon | app.js, data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json, pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv, processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv, scripts/validate-canonical-json.js |
| youth_flag | hunt_catalog[].youth_flag | data/hunt-master-canonical-2026-database-candidate.csv, data/hunt-master-canonical-2026-database-candidate.json |

## 4. Fields Not Represented And Why

Every unmapped discovered field is intentionally marked with a reason in `hunt-master-canonical-2026.coverage.json`. The most common reasons are runtime/UI implementation tokens, research CSV outputs that remain materialized outside the canonical, and documentation/control vocabulary.

| field | status | reason | sources |
| --- | --- | --- | --- |
| $id | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | schemas/hunt-master-canonical-2026.schema.json |
| ACRES | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| ADMIN | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| AIzaSyC49dXQ4FOyXqaUey4ASKlnDXWiwBHDlRM | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | config.js |
| Acreage | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Agency | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| All | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Antlerless | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| ApiProjectMapError | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Archery | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| BLM | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| BOUNDARYID | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Bearded | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| BillingNotEnabledMapError | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Bison | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| BlmAuthoritySource | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| BlmPermitMatchedOutfitters | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Both | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | data.js |
| BoundaryID | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js, data.js |
| Boundary_Id | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Boundary_Name | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Buck | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| Bull | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js, data.js |
| CITY | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| COUNTY | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| CO_NAME | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| CWMU | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| Cache | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | config.js |
| City | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Conservation | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| Copied | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Cougar | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| County | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| DESIG | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| DOMContentLoaded | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| DS | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Deer | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| District | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| DwrUnitName | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| EB1003 | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | config.js |
| EB1004 | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | config.js |
| EB1009 | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | config.js |
| Elk | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, data.js |
| Enter | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Escape | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, hunt-research.js |
| Ewe | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| FORESTNAME | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| FS | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| FeatureCollection | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js, data.js |
| FederalCoverageEligible | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| FederalPermitMatchedOutfitters | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Field | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| Fillmore | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | config.js |
| Fishlake | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | config.js |
| GIS_ACRES | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| GREEN | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| Google | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Guaranteed | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| HAMSS | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| HUNT_CODE | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | boundary-resolver.js |
| Hunt | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| HuntCategory | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| HuntCode | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| HuntType | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Hunter | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| InvalidKey | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| InvalidKeyMapError | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| LABEL_STATE | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Lodging | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Management | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| Monroe | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | config.js |
| Moose | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| MultiPolygon | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Multiseason | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| Muzzleloader | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| NAME | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Name | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Nebo | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | config.js |
| No | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| NoApiKeys | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Nonresident | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, data.js, hunt-research.js |
| Notes | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| OK | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| OWNER | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Outfitter | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| ParkName | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Polygon | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| PrimaryBlmDistrictName | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| PrimaryUsfsForestName | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Private | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Pronghorn | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Pursuit | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | data.js |
| RE | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| RS | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Ram | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| RefererNotAllowedMapError | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Resident | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, data.js, hunt-research.js |
| SITLA | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Select | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Sources | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| Species | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Statewide | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | data.js |
| Title | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Trophy | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Turkey | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| UNIT_NAME | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| UOGA_DISPLAY_BOUNDARY_ID | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| UOGA_HUNT_CODES | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| URL | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| US | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| UT | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| UTAH | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| UT_LGD | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Unavailable | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| UnitCode | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| UnitName | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Unknown | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| UsfsAuthoritySource | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| UsfsPermitMatchedOutfitters | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Utah | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Verified | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| WEBLINK1 | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Weapon | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| Weblink1 | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| YELLOW | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| You | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| Youth | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, config.js |
| _blank | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| absolute | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| acres | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| active | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| addToBasketButton | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| additionalProperties | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | schemas/hunt-master-canonical-2026.schema.json |
| address | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| admin | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| administrative_area_level_1 | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| and | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| antlerless | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, hunt-research.js |
| antlerless_odds_row_start | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/hunt_unit_reference_linked.csv |
| antlerless_odds_sheet | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/hunt_unit_reference_linked.csv |
| antlerless_odds_title | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/hunt_unit_reference_linked.csv |
| applicants_2025 | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/hunt_master_enriched.csv, processed_data/hunt_unit_reference_linked.csv |
| applicants_above | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/draw_reality_engine.csv |
| applicants_at_level | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/draw_reality_engine.csv |
| applyFiltersBtn | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| archery | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| array | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | scripts/validate-canonical-json.js |
| aside | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| assert | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | tests/validate-canonical-json.test.js |
| auto | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| basemapPopover | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| basketCount | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| basketList | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| bearded | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| beaver | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| beta | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| bg_odds_hunt_title | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/hunt_unit_reference_linked.csv |
| bg_odds_pdf_page_index | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/hunt_unit_reference_linked.csv |
| bg_odds_printed_page | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/hunt_unit_reference_linked.csv |
| bighorn | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| blm | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| blmAuthoritySource | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| blmDetail | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| blmDistricts | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | data/outfitters.json |
| blmPermitMatchedOutfitters | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| boolean | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| boundaryGeojsonPath | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js |
| boundaryGeometryType | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js |
| boundaryID | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, data.js |
| boundaryIdNumeric | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| boundaryIds | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| boundaryKmlPath | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js |
| boundaryKmzPath | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js |
| boundaryLink | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js |
| boundaryNames | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| boundaryURL | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| boundary_geometry_type | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| boundary_kml_path | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| boundary_link | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | boundary-resolver.js |
| bounds_changed | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| buck | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| builder | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| bull | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| category | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| center | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| choice | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| city | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, data/outfitters.json |
| clearBasketButton | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| clearFiltersBtn | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| clearFiltersButton | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| closeHuntDetailsBtn | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| closeMapChooserBtn | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| co_name | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| compass | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| conservation | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| controls | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| count | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/boundary-manifest-2026.json |
| county | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| coverage_reason | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/hunt_unit_reference_linked.csv |
| coverage_status | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/hunt_unit_reference_linked.csv |
| cow | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| cwmu | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| dates | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| deer | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, hunt-research.js |
| defaultUiDisabled | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| defaultUiHidden | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| delta_gap | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/draw_reality_engine.csv, processed_data/hunt_unit_reference_linked.csv |
| description | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | package.json |
| desert | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| desig | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| detailContent | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| detailEmpty | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| detailSubtitle | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| detailTitle | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| devDependencies | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | package.json |
| devDependencies.pdf-parse | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | package.json |
| devDependencies.pdfkit | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | package.json |
| devDependencies.wrangler | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | package.json |
| devDependencies.xlsx | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | package.json |
| development | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| displayBoundaryId | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| display_odds_pct | intentionally_unmapped | intentionally_unmapped: research/model output field remains in processed CSV materializations and is referenced through modeling/data_sources, not stored as static hunt catalog truth. | hunt-research.js |
| doe | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| dolores | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| draw_outlook | intentionally_unmapped | intentionally_unmapped: research/model output field remains in processed CSV materializations and is referenced through modeling/data_sources, not stored as static hunt catalog truth. | hunt-research.js, processed_data/draw_reality_engine.csv |
| duplicate_kmz_sha256_groups | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/boundary-manifest-2026.json |
| duplicate_kmz_sha256_groups[].hunt_codes | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/boundary-manifest-2026.json |
| duplicate_kmz_sha256_groups[].sha256 | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | processed_data/boundary-manifest-2026.json |
| dwr | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| dwrBoundaryId | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js |
| dwrBoundaryLink | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | boundary-resolver.js |
| dwrMapFrame | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| dwrMemberBoundaryIds | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js |
| dwr_boundary_link | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js, processed_data/display-boundary-index-2026.json |
| dwr_unit_name | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| earth | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| either | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| elevationScale | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| elk | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, hunt-research.js |
| email | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, data/outfitters.json |
| emailPrimary | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| error | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| ewe | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| exaggeration | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| externalBoundaryNames | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| fallback_member_features | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js |
| federalCoverageEligible | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| federalLayersSummary | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| federalPermitMatchedOutfitters | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| ferron | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| fillmore | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| filterReadout | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js |
| filters_applied | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| fishlake | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| fixed | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| forestMatch | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| fs | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | scripts/validate-canonical-json.js |
| function | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js, boundary-resolver.js |
| gap | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | hunt-research.js, processed_data/draw_reality_engine.csv |
| general | intentionally_unmapped | intentionally_unmapped: discovered during broad scan but not an app-facing canonical data field; retain in source file or future module if needed. | app.js |
| ... | 475 additional rows omitted from Markdown; see coverage JSON. | |

## 5. Every `needs_owner_input` Item

| path | status | question | source_hint |
| --- | --- | --- | --- |
| $.business_profile.legal_business_name | needs_owner_input | Provide legal business name for contracts, invoices, and waivers. |  |
| $.business_profile.mailing_address | needs_owner_input | Provide official mailing address if it belongs in canonical operations data. |  |
| $.business_profile.primary_contact | needs_owner_input | Provide owner-approved public business contact for booking workflow. |  |
| $.seasons[0].start_date | needs_owner_input | Parse start date for BI6527 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[0].end_date | needs_owner_input | Parse end date for BI6527 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[1].start_date | needs_owner_input | Parse start date for BI6538 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[1].end_date | needs_owner_input | Parse end date for BI6538 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[2].start_date | needs_owner_input | Parse start date for BI6505 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[2].end_date | needs_owner_input | Parse end date for BI6505 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[3].start_date | needs_owner_input | Parse start date for BI6506 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[3].end_date | needs_owner_input | Parse end date for BI6506 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[4].start_date | needs_owner_input | Parse start date for BI6529 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[4].end_date | needs_owner_input | Parse end date for BI6529 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[5].start_date | needs_owner_input | Parse start date for BI6536 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[5].end_date | needs_owner_input | Parse end date for BI6536 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[6].start_date | needs_owner_input | Parse start date for BI6539 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[6].end_date | needs_owner_input | Parse end date for BI6539 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[7].start_date | needs_owner_input | Parse start date for BI6500 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[7].end_date | needs_owner_input | Parse end date for BI6500 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[8].start_date | needs_owner_input | Parse start date for BI6503 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[8].end_date | needs_owner_input | Parse end date for BI6503 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[9].start_date | needs_owner_input | Parse start date for BI6504 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[9].end_date | needs_owner_input | Parse end date for BI6504 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[10].start_date | needs_owner_input | Parse start date for BI6516 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[10].end_date | needs_owner_input | Parse end date for BI6516 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[11].start_date | needs_owner_input | Parse start date for BI6531 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[11].end_date | needs_owner_input | Parse end date for BI6531 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[12].start_date | needs_owner_input | Parse start date for BI6534 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[12].end_date | needs_owner_input | Parse end date for BI6534 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[13].start_date | needs_owner_input | Parse start date for BI6535 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[13].end_date | needs_owner_input | Parse end date for BI6535 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[14].start_date | needs_owner_input | Parse start date for BI6537 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[14].end_date | needs_owner_input | Parse end date for BI6537 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[15].start_date | needs_owner_input | Parse start date for BI6509 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[15].end_date | needs_owner_input | Parse end date for BI6509 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[16].start_date | needs_owner_input | Parse start date for BI6528 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[16].end_date | needs_owner_input | Parse end date for BI6528 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[17].start_date | needs_owner_input | Parse start date for BI6532 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[17].end_date | needs_owner_input | Parse end date for BI6532 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[18].start_date | needs_owner_input | Parse start date for BI1000 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[18].end_date | needs_owner_input | Parse end date for BI1000 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[19].start_date | needs_owner_input | Parse start date for BR1007 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[19].end_date | needs_owner_input | Parse end date for BR1007 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[20].start_date | needs_owner_input | Parse start date for BR1000 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[20].end_date | needs_owner_input | Parse end date for BR1000 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[21].start_date | needs_owner_input | Parse start date for CG9999 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[21].end_date | needs_owner_input | Parse end date for CG9999 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[22].start_date | needs_owner_input | Parse start date for DA1011 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[22].end_date | needs_owner_input | Parse end date for DA1011 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[23].start_date | needs_owner_input | Parse start date for DA1012 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[23].end_date | needs_owner_input | Parse end date for DA1012 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[24].start_date | needs_owner_input | Parse start date for DA1013 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[24].end_date | needs_owner_input | Parse end date for DA1013 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[25].start_date | needs_owner_input | Parse start date for DA1050 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[25].end_date | needs_owner_input | Parse end date for DA1050 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[26].start_date | needs_owner_input | Parse start date for DB1200 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[26].end_date | needs_owner_input | Parse end date for DB1200 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[27].start_date | needs_owner_input | Parse start date for DB1201 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[27].end_date | needs_owner_input | Parse end date for DB1201 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[28].start_date | needs_owner_input | Parse start date for DB1202 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[28].end_date | needs_owner_input | Parse end date for DB1202 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[29].start_date | needs_owner_input | Parse start date for DB1203 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[29].end_date | needs_owner_input | Parse end date for DB1203 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[30].start_date | needs_owner_input | Parse start date for DB1204 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[30].end_date | needs_owner_input | Parse end date for DB1204 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[31].start_date | needs_owner_input | Parse start date for DB1205 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[31].end_date | needs_owner_input | Parse end date for DB1205 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[32].start_date | needs_owner_input | Parse start date for DB1206 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[32].end_date | needs_owner_input | Parse end date for DB1206 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[33].start_date | needs_owner_input | Parse start date for DB1207 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[33].end_date | needs_owner_input | Parse end date for DB1207 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[34].start_date | needs_owner_input | Parse start date for DB1208 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[34].end_date | needs_owner_input | Parse end date for DB1208 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[35].start_date | needs_owner_input | Parse start date for DB1209 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[35].end_date | needs_owner_input | Parse end date for DB1209 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[36].start_date | needs_owner_input | Parse start date for DB1211 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[36].end_date | needs_owner_input | Parse end date for DB1211 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[37].start_date | needs_owner_input | Parse start date for DB1212 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[37].end_date | needs_owner_input | Parse end date for DB1212 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[38].start_date | needs_owner_input | Parse start date for DB1213 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[38].end_date | needs_owner_input | Parse end date for DB1213 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[39].start_date | needs_owner_input | Parse start date for DB1215 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[39].end_date | needs_owner_input | Parse end date for DB1215 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[40].start_date | needs_owner_input | Parse start date for DB1216 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[40].end_date | needs_owner_input | Parse end date for DB1216 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[41].start_date | needs_owner_input | Parse start date for DB1217 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[41].end_date | needs_owner_input | Parse end date for DB1217 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[42].start_date | needs_owner_input | Parse start date for DB1219 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[42].end_date | needs_owner_input | Parse end date for DB1219 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[43].start_date | needs_owner_input | Parse start date for DB1222 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[43].end_date | needs_owner_input | Parse end date for DB1222 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[44].start_date | needs_owner_input | Parse start date for DB1224 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[44].end_date | needs_owner_input | Parse end date for DB1224 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[45].start_date | needs_owner_input | Parse start date for DB1227 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[45].end_date | needs_owner_input | Parse end date for DB1227 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[46].start_date | needs_owner_input | Parse start date for DB1228 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[46].end_date | needs_owner_input | Parse end date for DB1228 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[47].start_date | needs_owner_input | Parse start date for DB1229 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[47].end_date | needs_owner_input | Parse end date for DB1229 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[48].start_date | needs_owner_input | Parse start date for DB1230 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[48].end_date | needs_owner_input | Parse end date for DB1230 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[49].start_date | needs_owner_input | Parse start date for DB1231 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[49].end_date | needs_owner_input | Parse end date for DB1231 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[50].start_date | needs_owner_input | Parse start date for DB1232 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[50].end_date | needs_owner_input | Parse end date for DB1232 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[51].start_date | needs_owner_input | Parse start date for DB1233 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[51].end_date | needs_owner_input | Parse end date for DB1233 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[52].start_date | needs_owner_input | Parse start date for DB1234 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[52].end_date | needs_owner_input | Parse end date for DB1234 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[53].start_date | needs_owner_input | Parse start date for DB1236 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[53].end_date | needs_owner_input | Parse end date for DB1236 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[54].start_date | needs_owner_input | Parse start date for DB1237 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[54].end_date | needs_owner_input | Parse end date for DB1237 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[55].start_date | needs_owner_input | Parse start date for DB1238 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[55].end_date | needs_owner_input | Parse end date for DB1238 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[56].start_date | needs_owner_input | Parse start date for DB1239 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[56].end_date | needs_owner_input | Parse end date for DB1239 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[57].start_date | needs_owner_input | Parse start date for DB1240 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[57].end_date | needs_owner_input | Parse end date for DB1240 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[58].start_date | needs_owner_input | Parse start date for DB1241 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[58].end_date | needs_owner_input | Parse end date for DB1241 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[59].start_date | needs_owner_input | Parse start date for DB1242 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[59].end_date | needs_owner_input | Parse end date for DB1242 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[60].start_date | needs_owner_input | Parse start date for DB1243 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[60].end_date | needs_owner_input | Parse end date for DB1243 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[61].start_date | needs_owner_input | Parse start date for DB1244 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[61].end_date | needs_owner_input | Parse end date for DB1244 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[62].start_date | needs_owner_input | Parse start date for DB1245 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[62].end_date | needs_owner_input | Parse end date for DB1245 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[63].start_date | needs_owner_input | Parse start date for DB1246 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[63].end_date | needs_owner_input | Parse end date for DB1246 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[64].start_date | needs_owner_input | Parse start date for DB1248 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[64].end_date | needs_owner_input | Parse end date for DB1248 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[65].start_date | needs_owner_input | Parse start date for DB1249 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[65].end_date | needs_owner_input | Parse end date for DB1249 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[66].start_date | needs_owner_input | Parse start date for DB1250 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[66].end_date | needs_owner_input | Parse end date for DB1250 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[67].start_date | needs_owner_input | Parse start date for DB1251 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[67].end_date | needs_owner_input | Parse end date for DB1251 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[68].start_date | needs_owner_input | Parse start date for DB1252 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[68].end_date | needs_owner_input | Parse end date for DB1252 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[69].start_date | needs_owner_input | Parse start date for DB1253 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[69].end_date | needs_owner_input | Parse end date for DB1253 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[70].start_date | needs_owner_input | Parse start date for DB1255 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[70].end_date | needs_owner_input | Parse end date for DB1255 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[71].start_date | needs_owner_input | Parse start date for DB1256 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[71].end_date | needs_owner_input | Parse end date for DB1256 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[72].start_date | needs_owner_input | Parse start date for DB1258 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[72].end_date | needs_owner_input | Parse end date for DB1258 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[73].start_date | needs_owner_input | Parse start date for DB1259 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[73].end_date | needs_owner_input | Parse end date for DB1259 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[74].start_date | needs_owner_input | Parse start date for DB1260 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[74].end_date | needs_owner_input | Parse end date for DB1260 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[75].start_date | needs_owner_input | Parse start date for DB1261 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[75].end_date | needs_owner_input | Parse end date for DB1261 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[76].start_date | needs_owner_input | Parse start date for DB1263 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[76].end_date | needs_owner_input | Parse end date for DB1263 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[77].start_date | needs_owner_input | Parse start date for DB1264 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[77].end_date | needs_owner_input | Parse end date for DB1264 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[78].start_date | needs_owner_input | Parse start date for DB1265 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[78].end_date | needs_owner_input | Parse end date for DB1265 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[79].start_date | needs_owner_input | Parse start date for DB1266 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[79].end_date | needs_owner_input | Parse end date for DB1266 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[80].start_date | needs_owner_input | Parse start date for DB1269 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[80].end_date | needs_owner_input | Parse end date for DB1269 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[81].start_date | needs_owner_input | Parse start date for DB1270 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[81].end_date | needs_owner_input | Parse end date for DB1270 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[82].start_date | needs_owner_input | Parse start date for DB1271 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[82].end_date | needs_owner_input | Parse end date for DB1271 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[83].start_date | needs_owner_input | Parse start date for DB1272 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[83].end_date | needs_owner_input | Parse end date for DB1272 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[84].start_date | needs_owner_input | Parse start date for DB1273 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[84].end_date | needs_owner_input | Parse end date for DB1273 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[85].start_date | needs_owner_input | Parse start date for DB1274 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[85].end_date | needs_owner_input | Parse end date for DB1274 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[86].start_date | needs_owner_input | Parse start date for DB1275 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[86].end_date | needs_owner_input | Parse end date for DB1275 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[87].start_date | needs_owner_input | Parse start date for DB1277 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[87].end_date | needs_owner_input | Parse end date for DB1277 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[88].start_date | needs_owner_input | Parse start date for DB1279 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[88].end_date | needs_owner_input | Parse end date for DB1279 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[89].start_date | needs_owner_input | Parse start date for DB1280 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[89].end_date | needs_owner_input | Parse end date for DB1280 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[90].start_date | needs_owner_input | Parse start date for DB1281 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[90].end_date | needs_owner_input | Parse end date for DB1281 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[91].start_date | needs_owner_input | Parse start date for DB1282 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[91].end_date | needs_owner_input | Parse end date for DB1282 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[92].start_date | needs_owner_input | Parse start date for DB1283 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[92].end_date | needs_owner_input | Parse end date for DB1283 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[93].start_date | needs_owner_input | Parse start date for DB1285 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[93].end_date | needs_owner_input | Parse end date for DB1285 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[94].start_date | needs_owner_input | Parse start date for DB1286 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[94].end_date | needs_owner_input | Parse end date for DB1286 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[95].start_date | needs_owner_input | Parse start date for DB1287 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[95].end_date | needs_owner_input | Parse end date for DB1287 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[96].start_date | needs_owner_input | Parse start date for DB1288 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[96].end_date | needs_owner_input | Parse end date for DB1288 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[97].start_date | needs_owner_input | Parse start date for DB1289 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[97].end_date | needs_owner_input | Parse end date for DB1289 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[98].start_date | needs_owner_input | Parse start date for DB1290 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[98].end_date | needs_owner_input | Parse end date for DB1290 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[99].start_date | needs_owner_input | Parse start date for DB1291 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[99].end_date | needs_owner_input | Parse end date for DB1291 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[100].start_date | needs_owner_input | Parse start date for DB1292 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[100].end_date | needs_owner_input | Parse end date for DB1292 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[101].start_date | needs_owner_input | Parse start date for DB1293 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[101].end_date | needs_owner_input | Parse end date for DB1293 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[102].start_date | needs_owner_input | Parse start date for DB1294 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[102].end_date | needs_owner_input | Parse end date for DB1294 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[103].start_date | needs_owner_input | Parse start date for DB1295 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[103].end_date | needs_owner_input | Parse end date for DB1295 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[104].start_date | needs_owner_input | Parse start date for DB1298 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[104].end_date | needs_owner_input | Parse end date for DB1298 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[105].start_date | needs_owner_input | Parse start date for DB1299 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[105].end_date | needs_owner_input | Parse end date for DB1299 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[106].start_date | needs_owner_input | Parse start date for DB1300 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[106].end_date | needs_owner_input | Parse end date for DB1300 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[107].start_date | needs_owner_input | Parse start date for DB1301 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[107].end_date | needs_owner_input | Parse end date for DB1301 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[108].start_date | needs_owner_input | Parse start date for DB1303 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[108].end_date | needs_owner_input | Parse end date for DB1303 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[109].start_date | needs_owner_input | Parse start date for DB1304 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[109].end_date | needs_owner_input | Parse end date for DB1304 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[110].start_date | needs_owner_input | Parse start date for DB1305 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[110].end_date | needs_owner_input | Parse end date for DB1305 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[111].start_date | needs_owner_input | Parse start date for DB1306 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[111].end_date | needs_owner_input | Parse end date for DB1306 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[112].start_date | needs_owner_input | Parse start date for DB1308 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[112].end_date | needs_owner_input | Parse end date for DB1308 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[113].start_date | needs_owner_input | Parse start date for DB1309 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[113].end_date | needs_owner_input | Parse end date for DB1309 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[114].start_date | needs_owner_input | Parse start date for DB1310 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[114].end_date | needs_owner_input | Parse end date for DB1310 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[115].start_date | needs_owner_input | Parse start date for DB1312 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[115].end_date | needs_owner_input | Parse end date for DB1312 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[116].start_date | needs_owner_input | Parse start date for DB1317 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[116].end_date | needs_owner_input | Parse end date for DB1317 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[117].start_date | needs_owner_input | Parse start date for DB1322 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[117].end_date | needs_owner_input | Parse end date for DB1322 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[118].start_date | needs_owner_input | Parse start date for DB1323 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[118].end_date | needs_owner_input | Parse end date for DB1323 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[119].start_date | needs_owner_input | Parse start date for DB1325 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[119].end_date | needs_owner_input | Parse end date for DB1325 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[120].start_date | needs_owner_input | Parse start date for DB1326 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[120].end_date | needs_owner_input | Parse end date for DB1326 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[121].start_date | needs_owner_input | Parse start date for DB1327 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[121].end_date | needs_owner_input | Parse end date for DB1327 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[122].start_date | needs_owner_input | Parse start date for DB1328 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[122].end_date | needs_owner_input | Parse end date for DB1328 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[123].start_date | needs_owner_input | Parse start date for DB1330 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[123].end_date | needs_owner_input | Parse end date for DB1330 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[124].start_date | needs_owner_input | Parse start date for DB1331 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[124].end_date | needs_owner_input | Parse end date for DB1331 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[125].start_date | needs_owner_input | Parse start date for DB1332 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[125].end_date | needs_owner_input | Parse end date for DB1332 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[126].start_date | needs_owner_input | Parse start date for DB1333 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[126].end_date | needs_owner_input | Parse end date for DB1333 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[127].start_date | needs_owner_input | Parse start date for DB1334 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[127].end_date | needs_owner_input | Parse end date for DB1334 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[128].start_date | needs_owner_input | Parse start date for DB1335 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[128].end_date | needs_owner_input | Parse end date for DB1335 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[129].start_date | needs_owner_input | Parse start date for DB1336 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[129].end_date | needs_owner_input | Parse end date for DB1336 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[130].start_date | needs_owner_input | Parse start date for DB1337 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[130].end_date | needs_owner_input | Parse end date for DB1337 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[131].start_date | needs_owner_input | Parse start date for DB1341 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[131].end_date | needs_owner_input | Parse end date for DB1341 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[132].start_date | needs_owner_input | Parse start date for DB1342 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[132].end_date | needs_owner_input | Parse end date for DB1342 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[133].start_date | needs_owner_input | Parse start date for DB1347 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[133].end_date | needs_owner_input | Parse end date for DB1347 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[134].start_date | needs_owner_input | Parse start date for DB1349 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[134].end_date | needs_owner_input | Parse end date for DB1349 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[135].start_date | needs_owner_input | Parse start date for DB1351 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[135].end_date | needs_owner_input | Parse end date for DB1351 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[136].start_date | needs_owner_input | Parse start date for DB1058 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[136].end_date | needs_owner_input | Parse end date for DB1058 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[137].start_date | needs_owner_input | Parse start date for DB1056 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[137].end_date | needs_owner_input | Parse end date for DB1056 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[138].start_date | needs_owner_input | Parse start date for DB1075 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[138].end_date | needs_owner_input | Parse end date for DB1075 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[139].start_date | needs_owner_input | Parse start date for DB1118 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[139].end_date | needs_owner_input | Parse end date for DB1118 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[140].start_date | needs_owner_input | Parse start date for DB1076 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[140].end_date | needs_owner_input | Parse end date for DB1076 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[141].start_date | needs_owner_input | Parse start date for DB0008 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[141].end_date | needs_owner_input | Parse end date for DB0008 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[142].start_date | needs_owner_input | Parse start date for DA1009 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[142].end_date | needs_owner_input | Parse end date for DA1009 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[143].start_date | needs_owner_input | Parse start date for DA1027 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[143].end_date | needs_owner_input | Parse end date for DA1027 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[144].start_date | needs_owner_input | Parse start date for DA1041 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[144].end_date | needs_owner_input | Parse end date for DA1041 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[145].start_date | needs_owner_input | Parse start date for DA1047 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[145].end_date | needs_owner_input | Parse end date for DA1047 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[146].start_date | needs_owner_input | Parse start date for DB1531 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[146].end_date | needs_owner_input | Parse end date for DB1531 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[147].start_date | needs_owner_input | Parse start date for DB1533 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[147].end_date | needs_owner_input | Parse end date for DB1533 from raw_season_text; confirm exact date before automation. |  |
| $.seasons[148].start_date | needs_owner_input | Parse start date for DB1534 from raw_season_text; confirm exact date before automation. |  |
| ... | 2628 additional rows omitted from Markdown; see coverage JSON. | |

## 6. Every `source_needed` Regulation/Legal Item

| path | status | question | source_hint |
| --- | --- | --- | --- |
| $.species[0].legal_classification | source_needed | Verify current Utah DWR legal/regulatory classification for Bison. | Current-year Utah DWR guidebook |
| $.species[1].legal_classification | source_needed | Verify current Utah DWR legal/regulatory classification for Black Bear. | Current-year Utah DWR guidebook |
| $.species[2].legal_classification | source_needed | Verify current Utah DWR legal/regulatory classification for Cougar. | Current-year Utah DWR guidebook |
| $.species[3].legal_classification | source_needed | Verify current Utah DWR legal/regulatory classification for Deer. | Current-year Utah DWR guidebook |
| $.species[4].legal_classification | source_needed | Verify current Utah DWR legal/regulatory classification for Desert Bighorn Sheep. | Current-year Utah DWR guidebook |
| $.species[5].legal_classification | source_needed | Verify current Utah DWR legal/regulatory classification for Elk. | Current-year Utah DWR guidebook |
| $.species[6].legal_classification | source_needed | Verify current Utah DWR legal/regulatory classification for Moose. | Current-year Utah DWR guidebook |
| $.species[7].legal_classification | source_needed | Verify current Utah DWR legal/regulatory classification for Mountain Goat. | Current-year Utah DWR guidebook |
| $.species[8].legal_classification | source_needed | Verify current Utah DWR legal/regulatory classification for Pronghorn. | Current-year Utah DWR guidebook |
| $.species[9].legal_classification | source_needed | Verify current Utah DWR legal/regulatory classification for Rocky Mountain Bighorn Sheep. | Current-year Utah DWR guidebook |
| $.species[10].legal_classification | source_needed | Verify current Utah DWR legal/regulatory classification for Turkey. | Current-year Utah DWR guidebook |
| $.refund_policy.policy_text | source_needed | Provide current refund/cancellation policy and legal review source. | Owner-approved contract/refund document |
| $.licenses_and_tags.regulatory_warning | source_needed | Verify all license/tag legal requirements against current Utah DWR guidebooks before public legal display. | Current Utah DWR guidebooks |
| $.regulations_references[2].url | source_needed | Add current official guidebook URLs for every species before using this as legal/regulatory advice. |  |

## 7. Validation Commands Run

```powershell
npm.cmd run validate:canonical
npm.cmd run test:canonical
```

## 8. Test Results

- `npm.cmd run validate:canonical`: passed
- `npm.cmd run test:canonical`: passed
- Counts: `{"hunt_catalog_count": 1394, "hunt_units_count": 568, "outfitter_count": 70, "packages_count": 123, "seasons_count": 1394, "species_count": 11}`

## Completion Gate

- Coverage JSON exists: yes
- Coverage Markdown exists: yes
- All discovered fields mapped or intentionally unmapped: yes
- Validation/tests pass: yes
