# Complete 2023 Harvest vs Draw Comparison

## Summary
- harvest_files_checked: 50
- draw_files_checked: 2
- active_database_hunt_codes: 1411
- complete_harvest_hunt_codes: 1085
- draw_odds_hunt_codes: 984
- both_harvest_and_draw: 971
- harvest_only: 114
- draw_only: 13
- harvest_codes_in_active_database: 967
- draw_codes_in_active_database: 890
- both_codes_in_active_database: 879
- harvest_only_in_active_database: 88
- draw_only_in_active_database: 11
- bucket_counts: {'harvest_only': 114, 'both': 971, 'draw_only': 13}
- harvest_family_hunt_code_counts: {'antlerless': 247, 'bighorn_sheep': 46, 'bison': 18, 'black_bear': 87, 'deer': 328, 'elk': 211, 'general_deer': 136, 'moose': 36, 'mountain_goat': 17, 'other': 1030, 'pronghorn': 99, 'turkey': 7}
- harvest_only_codes: 114 codes
- draw_only_codes: 13 codes
- outputs: {'csv': 'processed_data\\complete_2023_harvest_vs_draw_comparison.csv', 'json': 'processed_data/complete_2023_harvest_vs_draw_comparison.json', 'md': 'processed_data/complete_2023_harvest_vs_draw_comparison.md'}
- source_notes: Harvest fields are quality/demand features and must not be used as permit quotas or direct p_draw.; Draw-result fields are point-level odds/history and are the source for permits_2023_draw_res/nr/total.; The malformed 2024_antlerless_hr.csv file is parsed by locating column B as Hunt #.

## Interpretation
- `both` rows can support both draw-history features and harvest-quality features.
- `harvest_only` rows can support quality/demand features but should not receive draw odds from harvest data.
- `draw_only` rows can support point-ladder/draw-history features but have no harvest-quality row in this harvest database.
