# Four-Page Canonical Coverage (Scoped)

Generated: 2026-07-30T11:12:00.203Z

## Scope Lock

This canonical system is scoped to four UOGA support tools only:

- Hunt Planner
- Hunt Research
- Hard Copies
- Outfitter Verification

It does not model or manage the full UOGA nonprofit website/CMS.

## Source Files Scanned

| File | Kind | Rows/Bytes | Fields |
| --- | --- | --- | --- |
| index.html | html | 30920 |  |
| research.html | html | 56600 |  |
| hard-copy.html | html | 4663 |  |
| verify.html | html | 32405 |  |
| config.js | js | 26174 |  |
| app.js | js | 290875 |  |
| data.js | js | 23353 |  |
| boundary-resolver.js | js | 13756 |  |
| hunt-research.js | js | 128608 |  |
| ui.js | js | 38233 |  |
| header-layout.js | js | 56607 |  |
| google-basemap.js | js | 7131 |  |
| map-engine.js | js | 10290 |  |
| style.css | css | 56739 |  |
| data/hunt-master-canonical-2026-foundation.json | json | 1471 | BoundaryID, Weapon, access_type, average_harvest_age, average_harvest_age_review_status, average_harvest_age_source_file, boundaryID, boundaryId, boundaryLink, boundary_id, boundary_id_numeric, category, code, conservation_permits_2026_source, conservation_permits_2026_total, current_age_3yr_average, data_status, dates, draw_2025_bg_pdf_page, draw_2025_bg_report_page, draw_2025_type, draw_2026_system_type, draw_family, dwr_huntplanner_age_objective |
| data/hunt-master-canonical-2026-database-candidate.json | json | 1471 | BoundaryID, Weapon, access_type, average_harvest_age, average_harvest_age_review_status, average_harvest_age_source_file, boundaryID, boundaryId, boundaryLink, boundary_id, boundary_id_numeric, category, code, conservation_permits_2026_source, conservation_permits_2026_total, current_age_3yr_average, data_status, dates, draw_2025_bg_pdf_page, draw_2025_bg_report_page, draw_2025_type, draw_2026_system_type, draw_family, dwr_huntplanner_age_objective |
| data/hunt-master-canonical-2026-source-of-truth.json | json | 1471 | BoundaryID, Weapon, access_type, average_harvest_age, average_harvest_age_review_status, average_harvest_age_source_file, boundaryID, boundaryId, boundaryLink, boundary_id, boundary_id_numeric, category, code, conservation_permits_2026_source, conservation_permits_2026_total, current_age_3yr_average, data_status, dates, draw_2025_bg_pdf_page, draw_2025_bg_report_page, draw_2025_type, draw_2026_system_type, draw_family, dwr_huntplanner_age_objective |
| processed_data/hunt_unit_reference_linked.csv | csv | 4762 | hunt_code, residency, hunt_name, species, weapon, hunt_type, access_type, public_permits_2025, public_permits_2026, permits_2025_res, permits_2025_nr, permits_2025_total, permits_2026_res, permits_2026_nr, permits_2026_total, applicants_2025, projected_applicants_2026, max_point_permits_2026, random_permits_2026, guaranteed_at_2026, delta_gap, trend, coverage_status, coverage_reason |
| processed_data/display-boundary-index-2026.json | json | 1471 | boundary_geojson_path, boundary_geometry_type, boundary_id, boundary_kml_path, boundary_kmz_path, boundary_source_authority, boundary_source_file, dwr_boundary_link, geometry_status, hunt_code, member_boundary_count, member_boundary_ids, merged_boundary_id, source_boundary_ids |
| processed_data/boundary-manifest-2026.json | json | 27 | boundary_geojson_path, boundary_geometry_type, boundary_id, boundary_kml_path, boundary_kmz_path, geometry_status, hunt_code, member_boundary_count, member_boundary_ids, merged_boundary_id, notes, placemark_count, sha256, source_filename |
| processed_data/hard_data_exports/hard_copy_pdf_manifest.web.json | json | 458 | companion_href, companion_type, group, href, model_year_folder, parent_title, source_authority, source_role, source_year, subtitle, title, type, year |
| data/outfitters-public.json | json | 11 | blmDistricts, certLevel, city, email, listingName, listingType, logoUrl, notes, ownerName, phone, region, speciesServed, unitsServed, usfsForests, verificationStatus, website |
| data/outfitters.json | json | 11 | blmDistricts, certLevel, city, email, listingName, listingType, logoUrl, notes, ownerName, phone, region, speciesServed, unitsServed, usfsForests, verificationStatus, website |
| processed_data/outfitter-federal-unit-coverage-review.json | json | 761 | BlmAuthoritySource, BlmPermitMatchedOutfitterCount, BlmPermitMatchedOutfitters, ExampleHuntCodes, ExclusionReason, FederalCoverageEligible, FederalPermitMatchedOutfitterCount, FederalPermitMatchedOutfitters, HuntCount, Notes, PrimaryBlmDistrictId, PrimaryBlmDistrictName, PrimaryUsfsForestId, PrimaryUsfsForestName, Species, UnitCode, UnitName, UsfsAuthoritySource, UsfsPermitMatchedOutfitterCount, UsfsPermitMatchedOutfitters |

## Field Mapping Summary

- Total discovered field entries: 532
- Mapped: 532
- Intentionally unmapped: 0
- Deprecated: 0

## Owner Questions

| ID | Question | Status |
| --- | --- | --- |
| owner-hard-copy-categories | Confirm whether Hard Copies should remain PDF-only or include CSV/XLSX downloads later. | needs_owner_input |
| owner-outfitter-cpo-threshold | Confirm the owner-approved threshold for C.P.O. designation before automating verification labels. | needs_owner_input |

## Source-Needed Legal/Regulatory Items

| ID | Item | URL | Status |
| --- | --- | --- | --- |
| source-utah-dwr-outfitter-registration | Utah DWR outfitter registration floor and public-resource language. | https://wildlife.utah.gov/guide/outfitter.html | source_needed |
| source-regulatory-disclaimer | Verification disclaimer: not a license, permit grant, land-access guarantee, agency authorization, or legal determination. |  | source_needed |

## Generated Page Data (Derived Only)

- generated/pages/hunt-planner.json
- generated/pages/hunt-research.json
- generated/pages/hard-copies.json
- generated/pages/outfitter-verification.json

## Validation Commands

- npm run generate:page-data
- npm run validate:canonical
- npm run compare:runtime-contracts
- npm run promotion:safety
- npm run test
- npm run build
