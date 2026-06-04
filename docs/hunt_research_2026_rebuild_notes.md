# hunt_research_2026 Rebuild Notes

Generated: 2026-06-04T02:25:17.158938

## Contract rebuild goal
- Rebuilt canonical Hunt Research contracts from canonical sources with full 2026 hunt-code coverage and runtime-aligned field set:
  - `processed_data/hunt_research_2026.json` (full/backward-compatible)
  - `processed_data/hunt_research_2026_summary.json` (group-level summary)
  - `processed_data/hunt_research_2026_ladder.json` (point-level ladder)
  - `processed_data/hunt_research_2026_ladder_preference.json` (preference ladder rows)
  - `processed_data/hunt_research_2026_ladder_bonus_max_random.json` (bonus/max-random ladder rows)

## Sources used
- DATABASE truth: `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Master reference resolved: `processed_data/hunt_master_enriched.csv`
- Point ladder: `processed_data/point_ladder_view.csv`
- Draw history: `pipeline/RAW/hunt_unit_database/2026/csv/Draw Odds/rebuilt_2025_draw_results_for_2026_modeling.csv`
- Harvest features: `data_truth/harvest_results_truth/normalized/harvest_results_2025_for_2026_long.csv`
- Age features: `data_model/harvest_quality/harvest_average_age_global_merge_database.csv`
- Management context: `processed_data/management_context/hunt_management_objective_context.json`

## Coverage summary
- Contract rows: 91734
- Summary rows: 3009
- Preference ladder rows: 17820
- Bonus/max-random ladder rows: 43164
- Unclassified ladder rows (kept in full ladder): 30750
- Unique contract hunt codes: 1471
- DATABASE hunt codes: 1471
- Missing hunt codes vs DATABASE: 0
- Missing runtime fields with zero population: 0

## Runtime field status
- Expected runtime field set size: 65
- Fields with no populated values: None

## Notes
- `DATABASE.csv` was treated as truth and not modified.
- Missing values are explicit via `missing_value_classification` (not silently dropped).
- Completeness status: **COMPLETE**
