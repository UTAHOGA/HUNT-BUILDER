# hunt_research_2026 Rebuild Notes

Generated: 2026-06-01T12:03:38.198104

## Contract rebuild goal
- Rebuilt `processed_data/hunt_research_2026.json` from canonical sources with full 2026 hunt-code coverage and runtime-aligned field set.

## Sources used
- DATABASE truth: `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Master reference resolved: `pipeline/RAW/hunt_unit_database/2026/csv/hunt_master_canonical_2026_built.csv`
- Point ladder: `processed_data/point_ladder_view.csv`
- Draw history: `processed_data/draw_reality_engine.csv`
- Harvest features: `processed_data/harvest_quality_features_all_years_by_hunt_code.csv`
- Age features: `data_model/harvest_quality/harvest_average_age_global_merge_database.csv`
- Management context: `processed_data/management_context/hunt_management_objective_context.json`

## Coverage summary
- Contract rows: 91712
- Unique contract hunt codes: 1449
- DATABASE hunt codes: 1449
- Missing hunt codes vs DATABASE: 0
- Missing runtime fields with zero population: 4

## Runtime field status
- Expected runtime field set size: 65
- Fields with no populated values: length, p_bonus_pool_pct, push, some

## Notes
- `DATABASE.csv` was treated as truth and not modified.
- Missing values are explicit via `missing_value_classification` (not silently dropped).
- Completeness status: **PARTIAL**
