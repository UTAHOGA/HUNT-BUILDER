# Key Alignment Crosswalk Audit - 2026 Runtime/Truth Sync

Created: 2026-07-03T02:32:57

## Controlling Key Structure
- `display_reference_key`: `hunt_code`
- `database_boundary_reference_key`: `hunt_code`, `boundary_id`
- `crosswalk_authority_lookup_key`: `hunt_year|target_year|permit_draw_year|source_year`, `hunt_code`
- `current_to_historical_crosswalk_key`: `current_hunt_code`, `historical_hunt_code`, `historical_year`
- `wide_canonical_truth_key`: `actual_draw_year`, `model_target_year`, `hunt_code`, `draw_system_type`, `points`, `record_type`
- `long_truth_probability_key`: `actual_draw_year`, `model_target_year`, `hunt_code`, `draw_system_type`, `residency`, `points`, `draw_pool(default=standard)`
- `predictive_runtime_key`: `forecast_year|year`, `hunt_code`, `draw_system_type`, `residency`, `points`, `draw_pool(default=standard)`
- `research_runtime_selection_key`: `hunt_code`, `forecast_year`, `runtime_promotion_family`, `residency`, `points`, `draw_pool(default=standard)`

Important: `hunt_code` is the display/reference handle. It is not enough for prediction equality once residency, points, draw pool, draw system, and year are involved.

Operational defaults: blank `draw_pool` is treated as `standard`; blank `points` is valid for availability/random/direct-allocation families and is not by itself a broken key.

## Crosswalk Authority Files
- `data_truth\crosswalk_truth\normalized\hunt_code_crosswalk_authority_2020_2026.csv`: rows `15747`, hunt codes `1723`, fields `69`
  - operational keys `9259`; duplicate lookup rows `6488`; missing required lookup rows `0`
  - first fields: authority_id, authority_status, source_year, target_year, hunt_year, permit_draw_year, source_document, source_document_year, source_page, source_table, source_row_number, source_label
- `data_truth\crosswalk_truth\normalized\current_to_historical_hunt_code_crosswalk_2026.csv`: rows `169`, hunt codes `169`, fields `31`
  - operational keys `169`; duplicate lookup rows `0`; missing required lookup rows `0`
  - first fields: current_hunt_code, current_prefix, current_hunt_name, species, sex_type, weapon, hunt_type, season, in_database_2026, database_permits_2026_res, database_permits_2026_nonres, database_permits_2026_total

Note: duplicate lookup rows in `hunt_code_crosswalk_authority_2020_2026.csv` are source-evidence multiplicity. The engine resolver compresses by `(year, hunt_code)` with authority precedence; it is not a prediction duplicate-key failure.

## File Counts
- `pipeline\RAW\hunt_unit_database\2026\csv\DATABASE.csv`: rows `1645`, hunt codes `1645`, years ``
  - operational keys `1645`; duplicate operational key rows `0`; missing required key rows `0`
- `data_truth\draw_results_truth\normalized\draw_results_long.csv`: rows `313506`, hunt codes `1508`, years `2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027`
  - operational keys `295744`; duplicate operational key rows `17762`; missing required key rows `0`
- `processed_data\draw_reality_engine_predictive_v2.csv`: rows `38653`, hunt codes `884`, years `2026, 2027`
  - operational keys `38653`; duplicate operational key rows `0`; missing required key rows `0`
- `processed_data\ml_draw_predictions_v1.csv`: rows `38647`, hunt codes `878`, years `2027`
  - operational keys `38647`; duplicate operational key rows `0`; missing required key rows `0`

## Canonical Yearly Counts
- `draw_results_2018_for_2019_canonical_yearly_draw_results.csv`: rows `31031`, hunt codes `1010`, years `2018, 2019`, operational wide keys `31031`, duplicate operational key rows `0`
- `draw_results_2019_for_2020_canonical_yearly_draw_results.csv`: rows `33478`, hunt codes `1054`, years `2019, 2020`, operational wide keys `32805`, duplicate operational key rows `673`
- `draw_results_2020_for_2021_canonical_yearly_draw_results.csv`: rows `33370`, hunt codes `1028`, years `2020, 2021`, operational wide keys `32690`, duplicate operational key rows `680`
- `draw_results_2021_for_2022_canonical_yearly_draw_results.csv`: rows `33788`, hunt codes `1022`, years `2021, 2022`, operational wide keys `29554`, duplicate operational key rows `4234`
- `draw_results_2022_for_2023_canonical_yearly_draw_results.csv`: rows `34876`, hunt codes `1020`, years `2022, 2023`, operational wide keys `34678`, duplicate operational key rows `198`
- `draw_results_2023_for_2024_canonical_yearly_draw_results.csv`: rows `35834`, hunt codes `1034`, years `2023, 2024`, operational wide keys `33534`, duplicate operational key rows `2300`
- `draw_results_2024_for_2025_canonical_yearly_draw_results.csv`: rows `43175`, hunt codes `1028`, years `2024, 2025`, operational wide keys `34539`, duplicate operational key rows `8636`
- `draw_results_2025_for_2026_canonical_yearly_draw_results.csv`: rows `38120`, hunt codes `1064`, years `2025, 2026`, operational wide keys `37868`, duplicate operational key rows `252`
- `draw_results_2026_for_2027_canonical_yearly_draw_results.csv`: rows `29812`, hunt codes `1097`, years `2026, 2027`, operational wide keys `14654`, duplicate operational key rows `15158`

## Hunt Code Overlap Snapshot
- `database_codes`: `1645`
- `canonical_yearly_union_codes`: `1508`
- `long_codes`: `1508`
- `predictive_v2_codes`: `884`
- `ml_prediction_codes`: `878`
- `database_and_canonical_union`: `1337`
- `database_not_in_canonical_union`: `308`
- `canonical_union_not_in_database`: `171`
- `long_not_in_canonical_union`: `0`
- `canonical_union_not_in_long`: `0`
- `predictive_v2_not_in_database`: `52`
- `ml_not_in_database`: `52`

## Promotion Note
- `draw_results_long.csv` was included in this audit. It is currently not modified in git, so there is no changed long-file payload to push in this bundle unless it is regenerated or touched intentionally.
- The live staged dependency bundle includes `DATABASE.csv`, canonical yearly CSVs, engine/contract validation tools, and locked 2026 hunt-code universe CSVs.
- No website split, boundary GeoJSON/KML, or `hunt_research.json` rebuild is part of this audit.
