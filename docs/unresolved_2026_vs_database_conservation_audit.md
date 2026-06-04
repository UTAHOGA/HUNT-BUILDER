# Unresolved 2026 Hunt Codes Vs DATABASE / Conservation Table Audit

## Scope

This audit joins the current unresolved 2026 hunt-code lists to `DATABASE.csv` and the normalized 2026 conservation permit table evidence.

Inputs:
- `processed_data/audits/current_2026_core_universe_reconciliation_review.csv`
- `processed_data/audits/current_2026_hunt_code_permit_unresolved.csv`
- `processed_data/audits/current_2026_permit_unresolved_split/remaining_unresolved_after_3_source_rule.csv`
- `processed_data/audits/permit_2026_species_truth_sources_vs_current_reconciliation.csv`
- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`

## Key Counts

- Unique unresolved codes audited: `698`
- Present in DATABASE: `675`
- Missing from DATABASE: `23`
- Present in conservation table evidence: `63`
- Synthetic conservation display-code policy rows: `10`

## Classification Counts

- `CLOSED_CURRENT_STATEWIDE_UNLIMITED`: `1`
- `CONSERVATION_SYNTHETIC_DISPLAY_CODE_REQUIRED`: `7`
- `CONSERVATION_TABLE_DB_MATCH`: `56`
- `DATABASE_HAS_VALUE_NO_RECOMMENDED_VALUE`: `136`
- `DATABASE_MATCHES_RECOMMENDED`: `218`
- `DATABASE_MISSING`: `23`
- `DATABASE_REFERENCE_NOT_LIVE`: `3`
- `REMAINING_UNRESOLVED_REVIEW`: `252`
- `UNRESOLVED_DATABASE_PRESENT_REVIEW`: `2`

## Locked Synthetic Conservation Display Codes

These codes are UOGA synthetic display/map codes only. They are not official DWR hunt codes and must not overwrite sportsman permit codes.

- `CBB1000`: Conservation Black Bear
- `CBI1000`: Conservation Bison
- `CD1000`: Conservation Deer
- `CDS1000`: Conservation Desert Bighorn Sheep
- `CE1000`: Conservation Elk
- `CM1000`: Conservation Moose
- `CMG1000`: Conservation Mountain Goat
- `CP1000`: Conservation Pronghorn
- `CRS1000`: Conservation Rocky Mountain Bighorn Sheep
- `CTK1000`: Conservation Turkey

## Conservation/Sportsman Finding

Conservation permit rows are direct conservation-table evidence and are not counted as sportsman support. Any conservation-table row currently using a sportsman hunt code for website/map identity is flagged as `CONSERVATION_SYNTHETIC_DISPLAY_CODE_REQUIRED`, with the sportsman code preserved only as `conservation_geometry_source_hunt_code`.

## Outputs

- Detail CSV: `processed_data/audits/unresolved_2026_vs_database_conservation_audit_synthetic_policy_update.csv`
- Summary JSON: `processed_data/audits/unresolved_2026_vs_database_conservation_audit_summary.json`
- Policy CSV: `processed_data/audits/conservation_synthetic_display_code_policy.csv`

## Guardrail

`DATABASE.csv` was not modified.
