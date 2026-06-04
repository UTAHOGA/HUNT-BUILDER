# Ambiguous Permit-Year Column Removal

Generated UTC: 2026-05-23T11:14:33.481558+00:00
Removed fields: `permits_year_res, permits_year_nr, permits_year_total`
Files written: `6`
Total columns/list references removed: `27`

## DB1002 Explicit Field Check

- 2025 draw-result permits: `1 / 0 / 1`
- 2026 allotment permits: `1 / 0 / 1`

## Files

| File | Status | Removed | Written |
| --- | --- | ---: | --- |
| pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv | columns_removed | 3 | True |
| processed_data/hunt_master_enriched.csv | columns_removed | 3 | True |
| processed_data/hunt_unit_reference_linked.csv | columns_removed | 3 | True |
| processed_data/point_ladder_view.csv | columns_removed | 3 | True |
| processed_data/draw_reality_engine.csv | columns_removed | 3 | True |
| data/hunt-master-canonical-2026-database-candidate.csv | no_ambiguous_columns | 0 | False |
| data/hunt-master-canonical-2026-source-of-truth.csv | no_ambiguous_columns | 0 | False |
| processed_data/hunt-master-canonical-2026-source-of-truth.csv | no_ambiguous_columns | 0 | False |
| generated/pages/hunt-research.json | list_references_removed | 12 | True |
