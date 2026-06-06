# Hunt Builder Engine / Database / Rendering Audit
Generated: 2026-06-06T08:02:42
## Executive Summary
- Total files inventoried: 11793
- Engine/transform files detected: 677
- Data/feeder files detected: 9917
- Dependency references detected: 644
- Website/rendering files detected: 41
- Large files over 10 MB: 114
- Duplicate feeder-name conflicts: 2359

## Engines Inventoried
|engine_path|status|keyword_hits|expected_inputs_detected|outputs_detected|notes|
|---|---|---|---|---|---|
|app.js|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;bear;cougar;draw;engine;etl;harvest;hunt_research;odds;preference;sportsman;transform;turkey;validate||||
|apply-2026-supplements.js|INVENTORIED_NEEDS_RUNTIME_CHECK|database||||
|audit-normalized-staging.js|INVENTORIED_NEEDS_RUNTIME_CHECK|audit||||
|audit_2026_completeness.js|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw;engine||||
|boundary-resolver.js|INVENTORIED_NEEDS_RUNTIME_CHECK|draw||||
|build-coverage-matrix.js|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;draw;engine;harvest;hunt_research;point_ladder||||
|catalog-raw-backups.js|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;draw;harvest;odds||||
|config.js|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;bear;cougar;draw;engine;harvest;hunt_research;point_ladder;predict;turkey|GET|||
|coverage.js|INVENTORIED_NEEDS_RUNTIME_CHECK|engine;harvest||||
|data.js|INVENTORIED_NEEDS_RUNTIME_CHECK|bear;draw;harvest||||
|embed-mode.js|INVENTORIED_NEEDS_RUNTIME_CHECK|engine;hunt_research;predict||||
|event-handlers.js|INVENTORIED_NEEDS_RUNTIME_CHECK|etl||||
|export-data.js|INVENTORIED_NEEDS_RUNTIME_CHECK|draw;engine;harvest;point_ladder||||
|extract-harvest-metrics.js|INVENTORIED_NEEDS_RUNTIME_CHECK|harvest||||
|google-basemap.js|INVENTORIED_NEEDS_RUNTIME_CHECK|preference||||
|header-layout.js|INVENTORIED_NEEDS_RUNTIME_CHECK|engine;odds;transform||||
|hunt-research.js|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;bear;bonus;draw;engine;etl;harvest;hunt_research;lion;odds;point_ladder;predict;prediction;preferenc...||||
|map-engine.js|INVENTORIED_NEEDS_RUNTIME_CHECK|engine;transform||||
|rebuild-engine-from-projection.js|INVENTORIED_NEEDS_RUNTIME_CHECK|bonus;draw;engine;odds;point_ladder||||
|scrub-pdf.js|INVENTORIED_NEEDS_RUNTIME_CHECK|harvest||||
|scrub-workbook.js|INVENTORIED_NEEDS_RUNTIME_CHECK|harvest||||
|sentry-browser-init.js|INVENTORIED_NEEDS_RUNTIME_CHECK|ingest||||
|sleeper-report.js|INVENTORIED_NEEDS_RUNTIME_CHECK|harvest||||
|staging-audit.js|INVENTORIED_NEEDS_RUNTIME_CHECK|audit||||
|sync-upstream.js|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;harvest||||
|ui.js|INVENTORIED_NEEDS_RUNTIME_CHECK|draw;hunt_research;odds;transform||||
|engine/__init__.py|INVENTORIED_NEEDS_RUNTIME_CHECK|draw;engine||||
|huntplanner_web_crawler_package/audit-huntplanner-network-age-data.mjs|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;bear;draw;harvest;odds|node:fs;node:path;playwright|||
|pages-dist/app.js|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;bear;cougar;draw;engine;etl;harvest;hunt_research;odds;preference;sportsman;transform;turkey;validate||||
|pages-dist/boundary-resolver.js|INVENTORIED_NEEDS_RUNTIME_CHECK|draw||||
|pages-dist/config.js|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;bear;cougar;draw;engine;harvest;hunt_research;point_ladder;predict;turkey|GET|||
|pages-dist/coverage.js|INVENTORIED_NEEDS_RUNTIME_CHECK|engine;harvest||||
|pages-dist/data.js|INVENTORIED_NEEDS_RUNTIME_CHECK|bear;draw;harvest||||
|pages-dist/embed-mode.js|INVENTORIED_NEEDS_RUNTIME_CHECK|engine;hunt_research;predict||||
|pages-dist/event-handlers.js|INVENTORIED_NEEDS_RUNTIME_CHECK|etl||||
|pages-dist/google-basemap.js|INVENTORIED_NEEDS_RUNTIME_CHECK|preference||||
|pages-dist/header-layout.js|INVENTORIED_NEEDS_RUNTIME_CHECK|engine;odds;transform||||
|pages-dist/hunt-research.js|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;bear;bonus;draw;engine;etl;harvest;hunt_research;lion;odds;point_ladder;predict;prediction;preferenc...||||
|pages-dist/map-engine.js|INVENTORIED_NEEDS_RUNTIME_CHECK|engine;transform||||
|pages-dist/sentry-browser-init.js|INVENTORIED_NEEDS_RUNTIME_CHECK|ingest||||
|pages-dist/ui.js|INVENTORIED_NEEDS_RUNTIME_CHECK|draw;hunt_research;odds;transform||||
|scripts/append_elk_general_season_otc_to_2024_permits_fixed.py|INVENTORIED_NEEDS_RUNTIME_CHECK|database;draw;harvest;odds|r;w|||
|scripts/apply-boundary-columns-to-bible-year-documents.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database|r;w|||
|scripts/apply-confirmed-moose-permit-values-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;reconcile|r;w|||
|scripts/apply-confirmed-remaining-permit-values-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;reconcile|r;w|\n||
|scripts/apply-current-year-permit-allotments.py|INVENTORIED_NEEDS_RUNTIME_CHECK|database;draw;engine;point_ladder;predict;prediction|w|||
|scripts/apply-database-allotment-reconciliation-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw;reconcile|r;w|\n||
|scripts/apply-deer-buck-drawclass-rules.py|INVENTORIED_NEEDS_RUNTIME_CHECK|draw;sportsman|r;w|||
|scripts/apply-elk-antlerless-recommended-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;database;reconcile|r;w|\n||
|scripts/apply-final-reviewed-permit-overrides-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database|r;w|||
|scripts/apply-reviewed-live-permit-corrections-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database|w|\n||
|scripts/assemble-spin-off-fragments.js|INVENTORIED_NEEDS_RUNTIME_CHECK|validate||||
|scripts/assign-composite-synthetic-boundary-ids-2026.js|INVENTORIED_NEEDS_RUNTIME_CHECK|database||||
|scripts/audit-2023-harvest-supplements.py|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;database;draw;harvest;odds;turkey|w|\n||
|scripts/audit-2024-draw-odds-against-database-2025-permits.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw;odds|rb;w|\n||
|scripts/audit-2026-additional-crosswalk-sources.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;bear;database;draw;harvest|C:/Users/tyler/Desktop/GitHub/HUNTS/data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv;...|||
|scripts/audit-2026-dwr-draw-results-vs-database-allotments.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;bear;database;draw;odds;turkey|w|\n||
|scripts/audit-2026-live-vs-bible-hunt-code-universe.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw;sportsman|w|\n||
|scripts/audit-2026-permits-vs-2025-carryover.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw|r;w|\n||
|scripts/audit-2026-regulation-pdfs-against-unresolved-permits.py|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;bear;cougar;database;draw|C:/Users/tyler/Desktop/GitHub/HUNTS/pipeline/RAW/hunt_unit_database/2026/pdf/regulations/2026 Bear Cougar Furbearer G...|||
|scripts/audit-2026-species-truth-permit-sources.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw|C:/Users/tyler/Desktop/species truth data;w|\n||
|scripts/audit-active-data-feeds.js|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;bonus;database;draw;engine;harvest;hunt_research;odds;point_ladder;predict;prediction;preference;reconcile||||
|scripts/audit-and-clean-database-permit-model-fields.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw|w|\n||
|scripts/audit-bear-cougar-furbearer-guidebook-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;bear;bonus;cougar;database;draw;engine;harvest;odds;point_ladder;predict;prediction;sportsman|rb;w|||
|scripts/audit-big-game-application-guidebook-2023.py|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;bonus;database;draw;engine;harvest;odds;predict;prediction;preference;sportsman|w|\n||
|scripts/audit-big-game-application-guidebook-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;bear;database;draw;harvest;odds;sportsman;turkey|w|\n||
|scripts/audit-big-game-field-regulations-2023.py|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;database;draw;engine;harvest;odds;predict;prediction;sportsman|w|\n||
|scripts/audit-big-game-field-regulations-2025.py|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;database;draw;harvest;odds;predict;prediction;sportsman|w|\n||
|scripts/audit-buck-deer-pasted-permits-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw|w|||
|scripts/audit-canonical-data-drop.js|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database||||
|scripts/audit-comprehensive-2026-2025-history-integrity.py|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;bear;database;draw;harvest;materialize;odds|w|||
|scripts/audit-current-active-ea-hunts-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;database;reconcile|w|\n||
|scripts/audit-current-online-hunt-codes-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;database|w|\n||
|scripts/audit-database-fragment-manifest.js|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw;engine;harvest;odds;point_ladder;predict;prediction|pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv|||
|scripts/audit-database-historical-permit-lineage-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;bear;bonus;database;draw;odds|w|\n||
|scripts/audit-database-universe-counts-2026.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw|r;w|\n||
|scripts/audit-draw-2020-for-2021-source-parity.py|INVENTORIED_NEEDS_RUNTIME_CHECK|antlerless;audit;bonus;cougar;database;draw;odds;sportsman;turkey|w|||
|scripts/audit-draw-2020-hashed-for-2021-source-parity.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw;odds|w|||
|scripts/audit-draw-2022-for-2023-source-parity.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw;odds|w|||
|scripts/audit-draw-2023-bg-page-map.py|INVENTORIED_NEEDS_RUNTIME_CHECK|audit;database;draw;harvest;odds;validate|w|||

_Showing first 80 of 677 rows._

## Feeder Files / Truth Source Status
|feeder_file|extension|size_bytes|size_mb|truth_source_guess|status|rows|columns|null_cells|blank_rows|duplicate_full_rows|notes|
|---|---|---|---|---|---|---|---|---|---|---|---|
|processed_data/audits/hunt_research_2026_before_numeric_fix_snapshot.json|.json|319882511|305.064|master_hunt_research_feed|FAIL_JSON_PARSE|None|||||Expecting property name enclosed in double quotes: line 567923 column 3 (char 20000000)|
|processed_data/hunt_research_2026.json|.json|305924170|291.752|master_hunt_research_feed|FAIL_JSON_PARSE|None|||||Unterminated string starting at: line 1 column 19999997 (char 19999996)|
|processed_data/hunt_research_2026_ladder.json|.json|305924170|291.752|master_hunt_research_feed|FAIL_JSON_PARSE|None|||||Unterminated string starting at: line 1 column 19999997 (char 19999996)|
|processed_data/hunt_research_2026_ladder_bonus_max_random.json|.json|146739010|139.941|master_hunt_research_feed|FAIL_JSON_PARSE|None|||||Unterminated string starting at: line 1 column 19999996 (char 19999995)|
|data/utah/official_downloads_2026/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson|.geojson|87146863|83.11|official_or_extracted_official|INVENTORIED|||||||
|processed_data/hunt_research_2026_ladder_preference.json|.json|82187730|78.38|master_hunt_research_feed|FAIL_JSON_PARSE|None|||||Expecting value: line 1 column 20000001 (char 20000000)|
|data_truth/draw_results_truth/normalized/draw_results_long.csv|.csv|77791622|74.188|official_or_extracted_official|PASS|176753|43|1887199|0|0||
|data_truth/draw_results_truth/normalized/draw_results_2025_for_2026_candidate_promotion_file_records.csv|.csv|68028388|64.877|official_or_extracted_official|PASS|75587|84|1980694|0|0||
|pipeline/RAW/hunt_unit_database/2026/csv/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED.csv|.csv|59371320|56.621|official_or_extracted_official|PASS|112056|43|593259|0|0||
|pipeline/RAW/hunt_unit_database/2026/csv/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED_V3.csv|.csv|59371320|56.621|official_or_extracted_official|PASS|112056|43|593259|0|0||
|pipeline/RAW/hunt_unit_database/2026/csv/Draw Odds/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED_V3.csv|.csv|59371320|56.621|official_or_extracted_official|PASS|112056|43|593259|0|0||
|pipeline/RAW/hunt_unit_database/2026/csv/draw_results_database_alignment_outputs_V3/draw_results_long_cumulative_2025...|.csv|59371320|56.621|official_or_extracted_official|PASS|112056|43|593259|0|0||
|pipeline/RAW/hunt_unit_database/2026/csv/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED_V2.csv|.csv|57999970|55.313|official_or_extracted_official|PASS|112056|43|593265|0|0||
|processed_data/draw_reality_engine_backup_before_2024_import.csv|.csv|52620090|50.182|reconciled_database_or_view|PASS|141516|34|1463738|0|0||
|processed_data/ml_draw_predictions_v1.csv|.csv|48351537|46.112|generated_engine_output|PASS|27940|180|2056684|0|0||
|data_model/runtime_drafts/mixed_predictive_engine_2026.predictions.csv|.csv|47860018|45.643|generated_engine_output|PASS|27822|181|2026425|0|0||
|processed_data/audits/hunt_research_2026_ladder_unclassified.csv|.csv|46064532|43.931|master_hunt_research_feed|PASS|46898|91|2106997|0|0||
|processed_data/draw_reality_engine_v2.csv|.csv|44863034|42.785|reconciled_database_or_view|PASS|176753|24|509165|0|0||
|data_model/runtime_drafts/draw_reality_engine_v2.csv|.csv|44792285|42.717|reconciled_database_or_view|PASS|176753|24|502766|0|0||
|processed_data/audits/hunt_research_2026_ladder_unclassified_classifier_exact.csv|.csv|43967059|41.93|master_hunt_research_feed|PASS|45116|92|2066445|0|0||
|processed_data/draw_reality_engine_predictive_v2.csv|.csv|42944164|40.955|reconciled_database_or_view|PASS|26389|173|1958740|0|0||
|data_model/runtime_drafts/mixed_predictive_engine_2026.materialized.csv|.csv|42943037|40.954|generated_engine_output|PASS|26389|173|1958748|0|0||
|data_truth/draw_results_truth/normalized/draw_results_2023_for_2024_candidate_promotion_file_records.csv|.csv|35406132|33.766|official_or_extracted_official|PASS|41201|105|2336033|0|0||
|processed_data/dwr_huntplanner_hanumber_2026_raw_payloads.json|.json|34755647|33.146|official_or_extracted_official|FAIL_JSON_PARSE|None|||||Unterminated string starting at: line 452322 column 19 (char 19994715)|
|data_model/runtime_drafts/draw_reality_engine_v2_rows_added.csv|.csv|34418796|32.824|reconciled_database_or_view|PASS|139891|24|425114|0|0||
|processed_data/hunt_research_2026_split/hunt_research_2026.details.json|.json|33963444|32.39|master_hunt_research_feed|FAIL_JSON_PARSE|None|||||Unterminated string starting at: line 1 column 19999997 (char 19999996)|
|processed_data/harvest_results_all_years_long.csv|.csv|30078733|28.685|harvest_source_or_output|PASS|75303|35|1060848|0|269||
|data/hunt_predictions.json|.json|30054306|28.662|generated_engine_output|FAIL_JSON_PARSE|None|||||Expecting ':' delimiter: line 374615 column 29 (char 19999470)|
|pages-dist/processed_data/public_contracts/hunt_predictions.json|.json|28443195|27.126|generated_engine_output|FAIL_JSON_PARSE|None|||||Unterminated string starting at: line 371780 column 27 (char 19999772)|
|processed_data/public_contracts/hunt_predictions.json|.json|28443195|27.126|generated_engine_output|FAIL_JSON_PARSE|None|||||Unterminated string starting at: line 371780 column 27 (char 19999772)|
|pipeline/RAW/hunt_unit_database/2026/csv/Draw Odds/rebuilt_2025_draw_results_for_2026_modeling.csv|.csv|27232226|25.971|official_or_extracted_official|PASS|75194|35|328624|0|0||
|processed_data/backups/current_year_allotment_overlay_20260523_075802/ml_draw_predictions_v1.csv|.csv|26051044|24.844|generated_engine_output|PASS|27940|131|1965395|0|0||
|processed_data/backups/current_year_allotment_overlay_20260523_080750/ml_draw_predictions_v1.csv|.csv|26051044|24.844|generated_engine_output|PASS|27940|131|1965395|0|0||
|processed_data/backups/current_year_allotment_overlay_20260523_072611/ml_draw_predictions_v1.csv|.csv|25843730|24.647|generated_engine_output|PASS|27815|131|1959804|0|0||
|processed_data/backups/current_year_allotment_overlay_20260523_075802/draw_reality_engine_predictive_v2.csv|.csv|25455643|24.276|reconciled_database_or_view|PASS|27940|131|2071311|0|0||
|processed_data/backups/current_year_allotment_overlay_20260523_080750/draw_reality_engine_predictive_v2.csv|.csv|25455643|24.276|reconciled_database_or_view|PASS|27940|131|2071311|0|0||
|processed_data/backups/current_year_allotment_overlay_20260523_072611/draw_reality_engine_predictive_v2.csv|.csv|25254426|24.084|reconciled_database_or_view|PASS|27815|131|2064659|0|0||
|data_model/harvest_quality/harvest_results_all_years_long.csv|.csv|24881298|23.729|harvest_source_or_output|PASS|68657|35|1006455|0|269||
|data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv|.csv|24881298|23.729|harvest_source_or_output|PASS|68657|35|1006455|0|269||
|data_truth/draw_results_truth/normalized/draw_results_2024_for_2025_candidate_promotion_file_records.csv|.csv|24674284|23.531|official_or_extracted_official|PASS|37224|78|1218476|0|0||
|processed_data/backups/current_year_allotment_overlay_20260523_071315/ml_draw_predictions_v1.csv|.csv|21458440|20.464|generated_engine_output|PASS|27815|125|1918806|0|0||
|processed_data/harvest_supplemental_metrics_2024_for_2025_long.csv|.csv|21382728|20.392|harvest_source_or_output|PASS|46838|23|259231|0|0||
|data_truth/harvest_results_truth/normalized/harvest_supplemental_metrics_2024_for_2025_long.csv|.csv|21382728|20.392|harvest_source_or_output|PASS|46838|23|259231|0|0||
|processed_data/backups/current_year_allotment_overlay_20260523_071315/draw_reality_engine_predictive_v2.csv|.csv|20869142|19.902|reconciled_database_or_view|PASS|27815|125|2023661|0|0||
|processed_data/backups/research_feeder_sync_20260604T064259Z/processed_data/draw_reality_engine.csv|.csv|20594722|19.641|reconciled_database_or_view|PASS|36892|64|1016352|0|0||
|data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv|.csv|18989572|18.11|generated_engine_output|PASS|23835|59|44252|0|0||
|data_model/runtime_drafts/predictive_bonus_engine_2026.predictions.csv|.csv|18585491|17.725|generated_engine_output|PASS|23835|53|14456|0|0||
|pipeline/RAW/hunt_unit_database/2026/csv/draw_results_long_cumulative_2025_draw_folder_CONTINUED.csv|.csv|18487610|17.631|official_or_extracted_official|PASS|112056|28|1270441|0|0||
|processed_data/backups/permit_allocations_2026_20260523_083028/processed_data/draw_reality_engine.csv|.csv|17727621|16.906|reconciled_database_or_view|PASS|36892|56|918933|0|0||
|processed_data/backups/permit_allocations_2026_20260523_082859/processed_data/draw_reality_engine.csv|.csv|17700713|16.881|reconciled_database_or_view|PASS|36892|56|918995|0|0||
|data_truth/draw_results_truth/normalized/draw_results_2021_for_2022_candidate_promotion_file_records.csv|.csv|16729020|15.954|official_or_extracted_official|PASS|27519|84|1189964|0|0||
|data_truth/draw_results_truth/normalized/draw_results_2022_for_2023_candidate_promotion_file_records.csv|.csv|16184931|15.435|official_or_extracted_official|PASS|18688|84|552360|0|0||
|processed_data/dwr_huntplanner_hanumber_2026.json|.json|15409432|14.696|official_or_extracted_official|PASS|1449|list|||||
|processed_data/draw_reality_view.csv|.csv|14072342|13.42|reconciled_database_or_view|PASS|53176|27|106259|0|0||
|hard-copy/pdf files/24_bg_HARVEST_report.pdf|.pdf|14037480|13.387|harvest_source_or_output|INVENTORIED|||||||
|pipeline/RAW/hunt_unit_database/2025/pdf/harvest_report/24_bg_HARVEST_report.pdf|.pdf|14037480|13.387|harvest_source_or_output|INVENTORIED|||||||
|data_model/runtime_drafts/mixed_predictive_engine_2026.audit.csv|.csv|13731420|13.095|generated_engine_output|PASS|27822|7|2011|0|0||
|processed_data/mixed_predictive_engine_2026_audit.csv|.csv|13370946|12.752|generated_engine_output|PASS|27940|7|2247|0|0||
|processed_data/backups/current_year_allotment_overlay_20260523_071315/draw_reality_engine.csv|.csv|13334737|12.717|reconciled_database_or_view|PASS|36892|50|878355|0|0||
|processed_data/audits/hunt_research_numeric_defect_audit.csv|.csv|12940279|12.341|master_hunt_research_feed|PASS|61387|9|0|0|0||
|pages-dist/processed_data/hard_data_exports/source_pdfs/draw_odds/2025/2025-big-game-draw-results.pdf|.pdf|12732089|12.142|official_or_extracted_official|INVENTORIED|||||||
|pipeline/RAW/hunt_unit_database/2026/pdf/draw_odds/2025 Big Game Draw Results.pdf|.pdf|12732089|12.142|official_or_extracted_official|INVENTORIED|||||||
|pipeline/RAW/hunt_unit_database/_quarantine/duplicates/exact_hash/25_bg-draw-results.pdf|.pdf|12732089|12.142|official_or_extracted_official|INVENTORIED|||||||
|processed_data/hard_data_exports/source_pdfs/draw_odds/2025/2025-big-game-draw-results.pdf|.pdf|12732089|12.142|official_or_extracted_official|INVENTORIED|||||||
|processed_data/hunt_research_2026_summary.json|.json|12253957|11.686|master_hunt_research_feed|PASS|3011|list|||||
|pipeline/RAW/hunt_unit_database/2024/csv/draw_results_2023_for_2024_UPLOADED_COMBINED_long.csv|.csv|12063058|11.504|official_or_extracted_official|PASS|38682|28|155740|0|0||
|pipeline/RAW/hunt_unit_database/2024/csv/Draw Odds/draw_results_2023_for_2024_UPLOADED_COMBINED_long.csv|.csv|12063058|11.504|official_or_extracted_official|PASS|38682|28|155740|0|0||
|pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/615cbcd5__Big game limited-entry &amp; once-in-a-lifetime draw res...|.pdf|10570345|10.081|official_or_extracted_official|INVENTORIED|||||||
|pipeline/RAW/hunt_unit_database/2022/pdf/draw_odds/21_bg-odds.pdf|.pdf|10570345|10.081|official_or_extracted_official|INVENTORIED|||||||
|pipeline/RAW/hunt_unit_database/2021/pdf/harvest_report/22_bg_harvest_report.pdf|.pdf|10336886|9.858|harvest_source_or_output|INVENTORIED|||||||
|pipeline/RAW/hunt_unit_database/2024/pdf/harvest_report/23_bg_report.pdf|.pdf|10336886|9.858|harvest_source_or_output|INVENTORIED|||||||
|pipeline/RAW/hunt_unit_database/2026/formatted_xlsx/draw_results_long_cumulative_2025_draw_folder_CONTINUED.xlsx|.xlsx|10243268|9.769|official_or_extracted_official|INVENTORIED|||||||
|pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/f4467d08__Big game limited-entry &amp; once-in-a-lifetime draw res...|.pdf|10158873|9.688|official_or_extracted_official|INVENTORIED|||||||
|pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/20_bg-odds.pdf|.pdf|10158873|9.688|official_or_extracted_official|INVENTORIED|||||||
|pipeline/RAW/hunt_unit_database/2024/csv/draw_results_2023_for_2024_long.csv|.csv|10155773|9.685|official_or_extracted_official|PASS|35960|27|116312|0|0||
|pipeline/RAW/hunt_unit_database/2024/csv/Draw Odds/draw_results_2023_for_2024_long.csv|.csv|10155773|9.685|official_or_extracted_official|PASS|35960|27|116312|0|0||
|data_truth/draw_results_truth/normalized/draw_results_2023_for_2024_top_missing_families_long.csv|.csv|9772695|9.32|official_or_extracted_official|PASS|23286|31|87167|0|0||
|pipeline/RAW/hunt_unit_database/2023/pdf/harvest_report/22_bg_report.pdf|.pdf|8749206|8.344|harvest_source_or_output|INVENTORIED|||||||
|processed_data/audits/hunt_research_full_final_reconciliation.csv|.csv|8143843|7.767|master_hunt_research_feed|PASS|40572|7|23303|0|0||
|processed_data/audits/hunt_research_feeder_to_contract_reconciliation.csv|.csv|7823691|7.461|master_hunt_research_feed|PASS|40572|7|31576|0|0||

_Showing first 80 of 9917 rows._

## Duplicate/Conflict Candidates
|file_name|copies|paths|truth_source_guesses|statuses|recommended_action|
|---|---|---|---|---|---|
|deer_2025_bonus_random_audit.csv|2|deer_2025_bonus_random_audit.csv;pipeline/RAW/hunt_unit_database/2025/csv/deer_2025_bonus_random_audit.csv|unknown|PASS|review_duplicate_feeder_names|
|hunt_history_2025_2026_dwr_aligned.csv|2|hunt_history_2025_2026_dwr_aligned.csv;pipeline/RAW/hunt_unit_database/2025/csv/hunt_history_2025_2026_dwr_aligned.csv|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|hunt_master_canonical_2026_built.csv|2|hunt_master_canonical_2026_built.csv;pipeline/RAW/hunt_unit_database/2026/csv/hunt_master_canonical_2026_built.csv|unknown|PASS|review_duplicate_feeder_names|
|manifest.json|4|manifest.json;pages-dist/manifest.json;data/utah/foundation_bundle_2026/manifest.json;processed_data/hunt_research_20...|master_hunt_research_feed;unknown|PASS|review_duplicate_feeder_names|
|package.json|2|package.json;huntplanner_web_crawler_package/package.json|unknown|PASS|review_duplicate_feeder_names|
|point_ladder_view.csv|8|point_ladder_view.csv;processed_data/point_ladder_view.csv;pages-dist/processed_data/point_ladder_view.csv;processed_...|unknown|PASS|review_duplicate_feeder_names|
|hunt-planner-2026.json|4|canonical/hunt-planner-2026.json;processed_data/backups/permit_allocations_2026_20260510_160357/canonical/hunt-planne...|unknown|PASS|review_duplicate_feeder_names|
|bighorn_sheep_hunt_table_official.json|2|data/bighorn_sheep_hunt_table_official.json;pages-dist/data/bighorn_sheep_hunt_table_official.json|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|bison_hunt_table_official.json|2|data/bison_hunt_table_official.json;pages-dist/data/bison_hunt_table_official.json|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|black_bear_hunt_table_official.json|2|data/black_bear_hunt_table_official.json;pages-dist/data/black_bear_hunt_table_official.json|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|conservation-permit-areas.json|2|data/conservation-permit-areas.json;pages-dist/data/conservation-permit-areas.json|unknown|PASS|review_duplicate_feeder_names|
|conservation-permit-hunt-table-2025-27-audit.json|2|data/conservation-permit-hunt-table-2025-27-audit.json;pipeline/RAW/hunt_unit_database/2025/json/conservation-permit-...|unknown|PASS|review_duplicate_feeder_names|
|conservation-permit-hunt-table-2025-27-summary.json|2|data/conservation-permit-hunt-table-2025-27-summary.json;pipeline/RAW/hunt_unit_database/2025/json/conservation-permi...|unknown|PASS|review_duplicate_feeder_names|
|conservation-permit-hunt-table-2025-27.csv|2|data/conservation-permit-hunt-table-2025-27.csv;pipeline/RAW/hunt_unit_database/2025/csv/conservation-permit-hunt-tab...|unknown|PASS|review_duplicate_feeder_names|
|conservation-permit-hunt-table-2025-27.json|3|data/conservation-permit-hunt-table-2025-27.json;pages-dist/data/conservation-permit-hunt-table-2025-27.json;pipeline...|unknown|PASS|review_duplicate_feeder_names|
|conservation-permit-workbook-2025-27-raw.csv|2|data/conservation-permit-workbook-2025-27-raw.csv;pipeline/RAW/hunt_unit_database/2025/csv/conservation-permit-workbo...|unknown|PASS|review_duplicate_feeder_names|
|conservation-permit-workbook-2025-27-raw.json|2|data/conservation-permit-workbook-2025-27-raw.json;pipeline/RAW/hunt_unit_database/2025/json/conservation-permit-work...|unknown|PASS|review_duplicate_feeder_names|
|conservation-permit-workbook-2025-27-summary.json|2|data/conservation-permit-workbook-2025-27-summary.json;pipeline/RAW/hunt_unit_database/2025/json/conservation-permit-...|unknown|PASS|review_duplicate_feeder_names|
|cougar_hunt_table_official.json|2|data/cougar_hunt_table_official.json;pages-dist/data/cougar_hunt_table_official.json|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|cwmu-boundaries.geojson|2|data/cwmu-boundaries.geojson;pages-dist/data/cwmu-boundaries.geojson|unknown|INVENTORIED|review_duplicate_feeder_names|
|dwr-getcwmuboundaries.json|2|data/dwr-GetCWMUBoundaries.json;pages-dist/data/dwr-GetCWMUBoundaries.json|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|elk_antlerless_hunt_table_official.json|2|data/elk_antlerless_hunt_table_official.json;pages-dist/data/elk_antlerless_hunt_table_official.json|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|elk_hunt_table_official.json|2|data/elk_hunt_table_official.json;pages-dist/data/elk_hunt_table_official.json|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|hunt-boundaries-lite.geojson|2|data/hunt-boundaries-lite.geojson;pages-dist/data/hunt-boundaries-lite.geojson|unknown|INVENTORIED|review_duplicate_feeder_names|
|hunt-master-canonical-2026-database-candidate.csv|2|data/hunt-master-canonical-2026-database-candidate.csv;processed_data/backups/rac_current_year_database_promotion_202...|unknown|PASS|review_duplicate_feeder_names|
|hunt-master-canonical-2026-database-candidate.json|4|data/hunt-master-canonical-2026-database-candidate.json;processed_data/backups/permit_allocations_2026_20260510_16035...|unknown|PASS|review_duplicate_feeder_names|
|hunt-master-canonical-2026-foundation.json|4|data/hunt-master-canonical-2026-foundation.json;pages-dist/data/hunt-master-canonical-2026-foundation.json;processed_...|unknown|PASS|review_duplicate_feeder_names|
|hunt-master-canonical-2026-source-of-truth.csv|6|data/hunt-master-canonical-2026-source-of-truth.csv;processed_data/hunt-master-canonical-2026-source-of-truth.csv;pag...|unknown|PASS|review_duplicate_feeder_names|
|hunt-master-canonical-2026-source-of-truth.json|10|data/hunt-master-canonical-2026-source-of-truth.json;processed_data/hunt-master-canonical-2026-source-of-truth.json;p...|unknown|PASS|review_duplicate_feeder_names|
|hunt_application_outlook.json|6|data/hunt_application_outlook.json;pages-dist/data/hunt_application_outlook.json;pages-dist/processed_data/public_con...|unknown|PASS|review_duplicate_feeder_names|
|hunt_boundaries.geojson|2|data/hunt_boundaries.geojson;pages-dist/data/hunt_boundaries.geojson|unknown|INVENTORIED|review_duplicate_feeder_names|
|hunt_odds_history.csv|3|data/hunt_odds_history.csv;pages-dist/processed_data/public_contracts/hunt_odds_history.csv;processed_data/public_con...|unknown|PASS|review_duplicate_feeder_names|
|hunt_odds_history.json|3|data/hunt_odds_history.json;pages-dist/processed_data/public_contracts/hunt_odds_history.json;processed_data/public_c...|unknown|FAIL_JSON_PARSE|review_duplicate_feeder_names|
|hunt_predictions.json|3|data/hunt_predictions.json;pages-dist/processed_data/public_contracts/hunt_predictions.json;processed_data/public_con...|generated_engine_output|FAIL_JSON_PARSE|review_duplicate_feeder_names|
|hunt_units.geojson|4|data/hunt_units.geojson;pages-dist/data/hunt_units.geojson;pages-dist/processed_data/public_contracts/hunt_units.geoj...|unknown|INVENTORIED|review_duplicate_feeder_names|
|loa_2024_gdb_-2965368397397759606.geojson|2|data/LOA_2024_gdb_-2965368397397759606.geojson;pipeline/RAW/hunt_unit_database/2024/geojson/LOA_2024_gdb_-29653683973...|unknown|INVENTORIED|review_duplicate_feeder_names|
|moose_hunt_table_official.json|2|data/moose_hunt_table_official.json;pages-dist/data/moose_hunt_table_official.json|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|mountain_goat_hunt_table_official.json|2|data/mountain_goat_hunt_table_official.json;pages-dist/data/mountain_goat_hunt_table_official.json|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|outfitters-public.json|4|data/outfitters-public.json;pages-dist/data/outfitters-public.json;pages-dist/processed_data/public_contracts/outfitt...|unknown|PASS|review_duplicate_feeder_names|
|outfitters.json|2|data/outfitters.json;pages-dist/data/outfitters.json|unknown|PASS|review_duplicate_feeder_names|
|pronghorn_hunt_table_official.json|2|data/pronghorn_hunt_table_official.json;pages-dist/data/pronghorn_hunt_table_official.json|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|public_contract_summary.json|4|data/public_contract_summary.json;pages-dist/data/public_contract_summary.json;pages-dist/processed_data/public_contr...|unknown|PASS|review_duplicate_feeder_names|
|runtime-manifest.json|4|data/runtime-manifest.json;pages-dist/data/runtime-manifest.json;pages-dist/public/data/runtime-manifest.json;public/...|unknown|PASS|review_duplicate_feeder_names|
|source_snapshots.json|4|data/source_snapshots.json;pages-dist/data/source_snapshots.json;pages-dist/processed_data/public_contracts/source_sn...|unknown|PASS|review_duplicate_feeder_names|
|statewide-composite-members-2026-lite.geojson|2|data/statewide-composite-members-2026-lite.geojson;pages-dist/data/statewide-composite-members-2026-lite.geojson|unknown|INVENTORIED|review_duplicate_feeder_names|
|turkey_hunt_table_official.json|2|data/turkey_hunt_table_official.json;pages-dist/data/turkey_hunt_table_official.json|official_or_extracted_official|PASS|review_duplicate_feeder_names|
|utah_big_game_hunt_boundaries_2025_elk.csv|2|data/Utah_Big_Game_Hunt_Boundaries_2025_elk.csv;pipeline/RAW/hunt_unit_database/2025/csv/Utah_Big_Game_Hunt_Boundarie...|unknown|PASS|review_duplicate_feeder_names|
|documents.json|3|hard-copy/documents.json;pages-dist/public/hard-copy/data/documents.json;public/hard-copy/data/documents.json|unknown|FAIL_JSON_PARSE;PASS|review_duplicate_feeder_names|
|boundary-id-overrides-2026.json|2|processed_data/boundary-id-overrides-2026.json;pages-dist/processed_data/boundary-id-overrides-2026.json|unknown|PASS|review_duplicate_feeder_names|
|boundary-manifest-2026.csv|2|processed_data/boundary-manifest-2026.csv;pages-dist/processed_data/boundary-manifest-2026.csv|unknown|PASS|review_duplicate_feeder_names|
|boundary-manifest-2026.json|2|processed_data/boundary-manifest-2026.json;pages-dist/processed_data/boundary-manifest-2026.json|unknown|PASS|review_duplicate_feeder_names|
|boundary_id_render_map_verification_2026.json|2|processed_data/boundary_id_render_map_verification_2026.json;pages-dist/processed_data/boundary_id_render_map_verific...|unknown|PASS|review_duplicate_feeder_names|
|boundary_registry_2026.csv|2|processed_data/boundary_registry_2026.csv;pages-dist/processed_data/boundary_registry_2026.csv|unknown|PASS|review_duplicate_feeder_names|
|conservation_area_crosswalk_2026.csv|2|processed_data/conservation_area_crosswalk_2026.csv;pipeline/RAW/hunt_unit_database/2026/reports/conservation_area_cr...|manual_or_generated_crosswalk|PASS|review_duplicate_feeder_names|
|conservation_area_crosswalk_2026.json|2|processed_data/conservation_area_crosswalk_2026.json;pipeline/RAW/hunt_unit_database/2026/reports/conservation_area_c...|manual_or_generated_crosswalk|PASS|review_duplicate_feeder_names|
|coverage-matrix.json|2|processed_data/coverage-matrix.json;pages-dist/processed_data/coverage-matrix.json|unknown|PASS|review_duplicate_feeder_names|
|current_to_historical_hunt_code_crosswalk_2026.csv|3|processed_data/current_to_historical_hunt_code_crosswalk_2026.csv;data_truth/crosswalk_truth/normalized/current_to_hi...|manual_or_generated_crosswalk|PASS|review_duplicate_feeder_names|
|display-boundary-index-2026.csv|2|processed_data/display-boundary-index-2026.csv;pages-dist/processed_data/display-boundary-index-2026.csv|unknown|PASS|review_duplicate_feeder_names|
|display-boundary-index-2026.json|2|processed_data/display-boundary-index-2026.json;pages-dist/processed_data/display-boundary-index-2026.json|unknown|PASS|review_duplicate_feeder_names|
|display-boundary-synthetic-id-map-2026.csv|2|processed_data/display-boundary-synthetic-id-map-2026.csv;pages-dist/processed_data/display-boundary-synthetic-id-map...|unknown|PASS|review_duplicate_feeder_names|
|display-boundary-synthetic-id-map-2026.json|2|processed_data/display-boundary-synthetic-id-map-2026.json;pages-dist/processed_data/display-boundary-synthetic-id-ma...|unknown|PASS|review_duplicate_feeder_names|
|draw_breakdown_2025.csv|3|processed_data/draw_breakdown_2025.csv;pipeline/RAW/hunt_unit_database/2026/csv/Draw Odds/draw_breakdown_2025.csv;pip...|unknown|PASS|review_duplicate_feeder_names|
|draw_reality_engine.csv|9|processed_data/draw_reality_engine.csv;data/utah/fixtures/draw_reality_engine.csv;pages-dist/processed_data/draw_real...|reconciled_database_or_view|PASS|review_duplicate_feeder_names|
|draw_reality_engine_predictive_v2.csv|5|processed_data/draw_reality_engine_predictive_v2.csv;processed_data/backups/current_year_allotment_overlay_20260523_0...|reconciled_database_or_view|PASS|review_duplicate_feeder_names|
|draw_reality_engine_v2.csv|2|processed_data/draw_reality_engine_v2.csv;data_model/runtime_drafts/draw_reality_engine_v2.csv|reconciled_database_or_view|PASS|review_duplicate_feeder_names|
|harvest_feature_model_audit.csv|2|processed_data/harvest_feature_model_audit.csv;audits/hunt_research_engine/harvest_feature_model_audit.csv|harvest_source_or_output;master_hunt_research_feed|PASS|review_duplicate_feeder_names|
|harvest_feature_model_audit.json|2|processed_data/harvest_feature_model_audit.json;audits/hunt_research_engine/harvest_feature_model_audit.json|harvest_source_or_output;master_hunt_research_feed|PASS|review_duplicate_feeder_names|
|harvest_master.csv|2|processed_data/harvest_master.csv;pages-dist/processed_data/harvest_master.csv|harvest_source_or_output|PASS|review_duplicate_feeder_names|
|harvest_quality_features_all_years_by_hunt_code.csv|4|processed_data/harvest_quality_features_all_years_by_hunt_code.csv;data_model/harvest_quality/harvest_quality_feature...|harvest_source_or_output|PASS|review_duplicate_feeder_names|
|harvest_results_all_years_long.csv|3|processed_data/harvest_results_all_years_long.csv;data_model/harvest_quality/harvest_results_all_years_long.csv;data_...|harvest_source_or_output|PASS|review_duplicate_feeder_names|
|harvest_supplemental_metrics_2024_for_2025_long.csv|2|processed_data/harvest_supplemental_metrics_2024_for_2025_long.csv;data_truth/harvest_results_truth/normalized/harves...|harvest_source_or_output|PASS|review_duplicate_feeder_names|
|hunt_code_boundary_map_2026.csv|2|processed_data/hunt_code_boundary_map_2026.csv;pages-dist/processed_data/hunt_code_boundary_map_2026.csv|unknown|PASS|review_duplicate_feeder_names|
|hunt_database_complete.csv|2|processed_data/hunt_database_complete.csv;pages-dist/processed_data/hunt_database_complete.csv|unknown|PASS|review_duplicate_feeder_names|
|hunt_master_enriched.csv|8|processed_data/hunt_master_enriched.csv;pages-dist/processed_data/hunt_master_enriched.csv;processed_data/_fixture_re...|unknown|PASS|review_duplicate_feeder_names|
|hunt_unit_reference_linked.csv|8|processed_data/hunt_unit_reference_linked.csv;pages-dist/processed_data/hunt_unit_reference_linked.csv;processed_data...|unknown|PASS|review_duplicate_feeder_names|
|ml_draw_predictions_v1.csv|5|processed_data/ml_draw_predictions_v1.csv;processed_data/backups/current_year_allotment_overlay_20260523_071315/ml_dr...|generated_engine_output|PASS|review_duplicate_feeder_names|
|normalized-staging-audit.csv|2|processed_data/normalized-staging-audit.csv;pages-dist/processed_data/normalized-staging-audit.csv|unknown|PASS|review_duplicate_feeder_names|
|normalized-staging-audit.json|2|processed_data/normalized-staging-audit.json;pages-dist/processed_data/normalized-staging-audit.json|unknown|PASS|review_duplicate_feeder_names|
|online_runtime_crosscheck.json|2|processed_data/online_runtime_crosscheck.json;pages-dist/processed_data/online_runtime_crosscheck.json|unknown|PASS|review_duplicate_feeder_names|
|outfitter-federal-unit-coverage-review.json|2|processed_data/outfitter-federal-unit-coverage-review.json;pages-dist/processed_data/outfitter-federal-unit-coverage-...|unknown|PASS|review_duplicate_feeder_names|

_Showing first 80 of 2359 rows._

## Website Delivery / Rendering Inventory
|page_or_component|page_area|data_refs|public_delivery_hits|status|notes|
|---|---|---|---|---|---|
|builder.html|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|coverage.html|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|hard-copy.html|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|hard-data.html|research||/public/;hard-copy/;processed_data/;public/|INVENTORIED_NEEDS_BROWSER_CHECK||
|hunt-builder-google-earth.html|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|hunt-research.html|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|index.html|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|ownership-dock.js|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|research.html|research||cloudflare|INVENTORIED_NEEDS_BROWSER_CHECK||
|staging-audit.html|research||processed_data/|INVENTORIED_NEEDS_BROWSER_CHECK||
|style.css|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|uoga-analytics.js|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|verify.html|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|vetting.html|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|data/conservation-permit-hunt-table-2025-27.html|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|data/hunt-unit-authority-review-register-2026-03-28.html|outfitter|||INVENTORIED_NEEDS_BROWSER_CHECK||
|data/hunt-unit-permit-checklist-2026-03-28.html|outfitter|||INVENTORIED_NEEDS_BROWSER_CHECK||
|data/uoga-outfitter-review-checklist-template-2026-03-28.html|outfitter|||INVENTORIED_NEEDS_BROWSER_CHECK||
|hard-copy/hard-copy.css|library_or_hard_copy||hard-copy/|INVENTORIED_NEEDS_BROWSER_CHECK||
|hard-copy/hard-copy.js|library_or_hard_copy||hard-copy/|INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/builder.html|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/coverage.html|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/hard-copy.html|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/hard-data.html|research||/public/;hard-copy/;processed_data/;public/|INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/hunt-research.html|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/index.html|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/ownership-dock.js|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/research.html|research||cloudflare|INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/style.css|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/uoga-analytics.js|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/verify.html|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pages-dist/vetting.html|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|scripts/build-canonical-rebuild.js|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|scripts/build-guidebook-viewer-pdfs.js|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|scripts/cloudflare-r2-runtime-worker.js|other||cloudflare;r2|INVENTORIED_NEEDS_BROWSER_CHECK||
|scripts/deploy-pages-dist.js|other||cloudflare|INVENTORIED_NEEDS_BROWSER_CHECK||
|tests/selection-matrix-progressive.test.js|research|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pipeline/RAW/hunt_unit_database/2025/other/conservation-permit-hunt-table-2025-27.html|other|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pipeline/RAW/hunt_unit_database/2026/other/hunt-unit-authority-review-register-2026-03-28.html|outfitter|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pipeline/RAW/hunt_unit_database/2026/other/hunt-unit-permit-checklist-2026-03-28.html|outfitter|||INVENTORIED_NEEDS_BROWSER_CHECK||
|pipeline/RAW/hunt_unit_database/2026/other/uoga-outfitter-review-checklist-template-2026-03-28.html|outfitter|||INVENTORIED_NEEDS_BROWSER_CHECK||

## Large Files Not To Stage
|path|size_bytes|size_mb|extension|type|truth_source_guess|modified|
|---|---|---|---|---|---|---|
|.tmp_r2_test.csv|46220759|44.08|.csv|data_or_feeder|unknown|2026-06-05T12:29:22|
|point_ladder_view1.csv|132456166|126.32|.csv|data_or_feeder|unknown|2026-05-26T22:04:55|
|data/hunt_boundaries_arcgis.json|88110587|84.029|.json|data_or_feeder|unknown|2026-05-23T22:11:41|
|data/hunt_odds_history.csv|30693029|29.271|.csv|data_or_feeder|unknown|2026-06-05T12:29:22|
|data/hunt_odds_history.json|113970739|108.691|.json|data_or_feeder|unknown|2026-05-30T05:30:08|
|data/hunt_predictions.json|30054306|28.662|.json|data_or_feeder|generated_engine_output|2026-06-05T12:29:22|
|processed_data/composite_hunt_unit_mapping_2026.geojson|54914353|52.37|.geojson|data_or_feeder|unknown|2026-05-26T09:20:10|
|processed_data/draw_reality_engine_backup_before_2024_import.csv|52620090|50.182|.csv|data_or_feeder|reconciled_database_or_view|2026-05-23T09:22:19|
|processed_data/draw_reality_engine_predictive_v2.csv|42944164|40.955|.csv|data_or_feeder|reconciled_database_or_view|2026-06-04T16:40:44|
|processed_data/draw_reality_engine_v2.csv|44863034|42.785|.csv|data_or_feeder|reconciled_database_or_view|2026-06-05T12:29:24|
|processed_data/draw_reality_view.csv|14072342|13.42|.csv|data_or_feeder|reconciled_database_or_view|2026-06-05T12:29:24|
|processed_data/draw_system_coverage_report.csv|78555708|74.917|.csv|data_or_feeder|unknown|2026-05-23T02:07:28|
|processed_data/dwr_huntplanner_hanumber_2026.json|15409432|14.696|.json|data_or_feeder|official_or_extracted_official|2026-06-03T21:36:06|
|processed_data/dwr_huntplanner_hanumber_2026_raw_payloads.json|34755647|33.146|.json|data_or_feeder|official_or_extracted_official|2026-06-03T21:36:06|
|processed_data/harvest_results_all_years_long.csv|30078733|28.685|.csv|data_or_feeder|harvest_source_or_output|2026-05-28T16:29:01|
|processed_data/harvest_supplemental_metrics_2024_for_2025_long.csv|21382728|20.392|.csv|data_or_feeder|harvest_source_or_output|2026-05-27T02:27:49|
|processed_data/hunt_decision_output.csv|11415874|10.887|.csv|data_or_feeder|unknown|2026-05-06T09:16:23|
|processed_data/hunt_research_2026.json|305924170|291.752|.json|data_or_feeder|master_hunt_research_feed|2026-06-04T22:40:54|
|processed_data/hunt_research_2026_ladder.json|305924170|291.752|.json|data_or_feeder|master_hunt_research_feed|2026-06-04T22:40:58|
|processed_data/hunt_research_2026_ladder_bonus_max_random.json|146739010|139.941|.json|data_or_feeder|master_hunt_research_feed|2026-06-04T22:41:00|
|processed_data/hunt_research_2026_ladder_preference.json|82187730|78.38|.json|data_or_feeder|master_hunt_research_feed|2026-06-04T22:40:59|
|processed_data/hunt_research_2026_summary.json|12253957|11.686|.json|data_or_feeder|master_hunt_research_feed|2026-06-05T02:10:02|
|processed_data/hunt_truth_from_json.sqlite|85475328|81.516|.sqlite|other|unknown|2026-05-06T09:16:24|
|processed_data/mixed_predictive_engine_2026_audit.csv|13370946|12.752|.csv|data_or_feeder|generated_engine_output|2026-06-04T23:50:11|
|processed_data/ml_draw_predictions_v1.csv|48351537|46.112|.csv|data_or_feeder|generated_engine_output|2026-06-05T12:29:25|
|processed_data/projected_bonus_draw_2026_simulated.csv|18106562|17.268|.csv|data_or_feeder|unknown|2026-05-05T20:33:37|
|processed_data/statewide_composite_boundaries_2026.geojson|87146863|83.11|.geojson|data_or_feeder|unknown|2026-05-26T09:20:13|
|processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson|87146863|83.11|.geojson|data_or_feeder|unknown|2026-06-01T01:26:30|
|processed_data/truth_downloads_comprehensive.sqlite|10813440|10.312|.sqlite|other|unknown|2026-06-05T12:29:25|
|data/utah/foundation_bundle_2026/utah_boundaries_canonical_2026.geojson|87146863|83.11|.geojson|data_or_feeder|unknown|2026-05-23T22:11:42|
|data/utah/foundation_bundle_2026/utah_boundaries_canonical_2026.kml|22520888|21.478|.kml|data_or_feeder|unknown|2026-06-05T12:29:22|
|data/utah/foundation_bundle_2026/utah_hunt_foundation_2026.sqlite|73383936|69.984|.sqlite|other|unknown|2026-05-23T22:11:42|
|data/utah/official_downloads_2026/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson|87146863|83.11|.geojson|data_or_feeder|official_or_extracted_official|2026-05-23T22:11:42|
|data_model/harvest_quality/harvest_results_all_years_long.csv|24881298|23.729|.csv|data_or_feeder|harvest_source_or_output|2026-06-05T12:29:22|
|data_model/runtime_drafts/draw_reality_engine_v2.csv|44792285|42.717|.csv|data_or_feeder|reconciled_database_or_view|2026-06-05T12:29:22|
|data_model/runtime_drafts/draw_reality_engine_v2_rows_added.csv|34418796|32.824|.csv|data_or_feeder|reconciled_database_or_view|2026-06-05T12:29:22|
|data_model/runtime_drafts/hunt_master_enriched_v2.csv|23621424|22.527|.csv|data_or_feeder|unknown|2026-06-05T12:29:23|
|data_model/runtime_drafts/mixed_predictive_engine_2026.audit.csv|13731420|13.095|.csv|data_or_feeder|generated_engine_output|2026-06-04T15:16:30|
|data_model/runtime_drafts/mixed_predictive_engine_2026.materialized.csv|42943037|40.954|.csv|data_or_feeder|generated_engine_output|2026-06-04T15:33:30|
|data_model/runtime_drafts/mixed_predictive_engine_2026.predictions.csv|47860018|45.643|.csv|data_or_feeder|generated_engine_output|2026-06-04T15:33:26|
|data_model/runtime_drafts/point_ladder_missing_columns_audit.csv|14100188|13.447|.csv|data_or_feeder|unknown|2026-06-05T12:29:23|
|data_model/runtime_drafts/point_ladder_view_v2.csv|44800057|42.725|.csv|data_or_feeder|unknown|2026-06-05T12:29:23|
|data_model/runtime_drafts/point_ladder_view_v3.csv|21093626|20.116|.csv|data_or_feeder|unknown|2026-06-05T12:29:23|
|data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv|18989572|18.11|.csv|data_or_feeder|generated_engine_output|2026-06-05T12:29:23|
|data_model/runtime_drafts/predictive_bonus_engine_2026.predictions.csv|18585491|17.725|.csv|data_or_feeder|generated_engine_output|2026-06-05T12:29:23|
|data_model/validation/hunt_type_hunt_class_matrix_audit.csv|24457807|23.325|.csv|data_or_feeder|unknown|2026-05-23T22:11:44|
|data_truth/comparison_outputs/database_candidate_review/database_candidate_review_records.csv|21773104|20.764|.csv|data_or_feeder|unknown|2026-06-05T12:29:23|
|data_truth/draw_results_truth/normalized/draw_results_2021_for_2022_candidate_promotion_file_records.csv|16729020|15.954|.csv|data_or_feeder|official_or_extracted_official|2026-06-05T12:29:23|
|data_truth/draw_results_truth/normalized/draw_results_2022_for_2023_candidate_promotion_file_records.csv|16184931|15.435|.csv|data_or_feeder|official_or_extracted_official|2026-06-05T12:29:23|
|data_truth/draw_results_truth/normalized/draw_results_2023_for_2024_candidate_promotion_file_records.csv|35406132|33.766|.csv|data_or_feeder|official_or_extracted_official|2026-06-05T12:29:23|
|data_truth/draw_results_truth/normalized/draw_results_2024_for_2025_candidate_promotion_file_records.csv|24674284|23.531|.csv|data_or_feeder|official_or_extracted_official|2026-06-05T12:29:23|
|data_truth/draw_results_truth/normalized/draw_results_2025_for_2026_candidate_promotion_file_records.csv|68028388|64.877|.csv|data_or_feeder|official_or_extracted_official|2026-05-27T03:09:16|
|data_truth/draw_results_truth/normalized/draw_results_long.csv|77791622|74.188|.csv|data_or_feeder|official_or_extracted_official|2026-05-23T22:11:59|
|data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv|24881298|23.729|.csv|data_or_feeder|harvest_source_or_output|2026-05-26T12:43:13|
|data_truth/harvest_results_truth/normalized/harvest_supplemental_metrics_2024_for_2025_long.csv|21382728|20.392|.csv|data_or_feeder|harvest_source_or_output|2026-05-27T02:27:49|
|hard-copy/pdf files/24_bg_HARVEST_report.pdf|14037480|13.387|.pdf|data_or_feeder|harvest_source_or_output|2026-06-05T12:29:23|
|pages-dist/processed_data/public_contracts/hunt_odds_history.csv|30497310|29.085|.csv|data_or_feeder|unknown|2026-06-06T07:11:42|
|pages-dist/processed_data/public_contracts/hunt_odds_history.json|113951774|108.673|.json|data_or_feeder|unknown|2026-06-06T07:11:42|
|pages-dist/processed_data/public_contracts/hunt_predictions.json|28443195|27.126|.json|data_or_feeder|generated_engine_output|2026-06-06T07:11:41|
|pages-dist/processed_data/hard_data_exports/source_pdfs/draw_odds/2025/2025-big-game-draw-results.pdf|12732089|12.142|.pdf|data_or_feeder|official_or_extracted_official|2026-06-05T12:29:24|
|pipeline/R2_OFFLOAD/incoming/harvest_quality_20260605.zip|12103659|11.543|.zip|other|harvest_source_or_output|2026-06-05T12:16:18|
|pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds.zip|38180256|36.412|.zip|other|official_or_extracted_official|2026-06-03T06:54:34|
|pipeline/RAW/hunt_unit_database/2021/bible_truth/pdf/2021_PERMITS=2022_MODEL__L.E. BIG GAME DRAW RESULTS.pdf|10570345|10.081|.pdf|data_or_feeder|unknown|2026-06-03T06:39:31|
|pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/615cbcd5__Big game limited-entry &amp; once-in-a-lifetime draw res...|10570345|10.081|.pdf|data_or_feeder|official_or_extracted_official|2026-05-01T05:44:53|
|pipeline/RAW/hunt_unit_database/2022/pdf/draw_odds.zip|25435779|24.257|.zip|other|official_or_extracted_official|2026-06-03T06:54:59|
|pipeline/RAW/hunt_unit_database/2022/pdf/draw_odds/21_bg-odds.pdf|10570345|10.081|.pdf|data_or_feeder|official_or_extracted_official|2026-05-03T02:58:27|
|pipeline/RAW/hunt_unit_database/2024/csv/draw_results_2023_for_2024_UPLOADED_COMBINED_long.csv|12063058|11.504|.csv|data_or_feeder|official_or_extracted_official|2026-05-10T14:06:16|
|pipeline/RAW/hunt_unit_database/2024/csv/Draw Odds/draw_results_2023_for_2024_UPLOADED_COMBINED_long.csv|12063058|11.504|.csv|data_or_feeder|official_or_extracted_official|2026-05-10T14:06:17|
|pipeline/RAW/hunt_unit_database/2025/bible_truth/pdf/2025_PERMITS=2026_MODEL__L.E. BIG GAME DRAW RESULTS.pdf|12732089|12.142|.pdf|data_or_feeder|unknown|2026-06-03T10:23:48|
|pipeline/RAW/hunt_unit_database/2025/pdf/harvest_report/24_bg_HARVEST_report.pdf|14037480|13.387|.pdf|data_or_feeder|harvest_source_or_output|2026-05-01T03:07:17|
|pipeline/RAW/hunt_unit_database/2026/csv/draw_results_long_cumulative_2025_draw_folder_CONTINUED.csv|18487610|17.631|.csv|data_or_feeder|official_or_extracted_official|2026-05-10T10:17:58|
|pipeline/RAW/hunt_unit_database/2026/csv/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED.csv|59371320|56.621|.csv|data_or_feeder|official_or_extracted_official|2026-05-10T11:19:04|
|pipeline/RAW/hunt_unit_database/2026/csv/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED_V2.csv|57999970|55.313|.csv|data_or_feeder|official_or_extracted_official|2026-05-10T10:38:42|
|pipeline/RAW/hunt_unit_database/2026/csv/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED_V3.csv|59371320|56.621|.csv|data_or_feeder|official_or_extracted_official|2026-05-10T11:36:47|
|pipeline/RAW/hunt_unit_database/2026/csv/Draw Odds/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED_V3.csv|59371320|56.621|.csv|data_or_feeder|official_or_extracted_official|2026-05-10T11:36:47|
|pipeline/RAW/hunt_unit_database/2026/csv/Draw Odds/rebuilt_2025_draw_results_for_2026_modeling.csv|27232226|25.971|.csv|data_or_feeder|official_or_extracted_official|2026-06-01T16:19:32|
|pipeline/RAW/hunt_unit_database/2026/csv/draw_results_database_alignment_outputs_V3/draw_results_long_cumulative_2025...|59371320|56.621|.csv|data_or_feeder|official_or_extracted_official|2026-05-10T11:36:47|
|pipeline/RAW/hunt_unit_database/2026/pdf/draw_odds/2025 Big Game Draw Results.pdf|12732089|12.142|.pdf|data_or_feeder|official_or_extracted_official|2026-03-31T00:14:10|
|pipeline/RAW/hunt_unit_database/_quarantine/duplicates/exact_hash/1ACA3B7A__24_bg_report.pdf|14037480|13.387|.pdf|data_or_feeder|unknown|2026-04-22T17:24:45|
|pipeline/RAW/hunt_unit_database/_quarantine/duplicates/exact_hash/25_bg-draw-results.pdf|12732089|12.142|.pdf|data_or_feeder|official_or_extracted_official|2026-03-31T00:14:10|

_Showing first 80 of 114 rows._

## Initial Findings
- This audit is inventory/read-only. It does not repair data, stage Git files, or push.
- Any file listed in `00_large_files_over_10mb.csv` should be reviewed before staging. Most large raw/generated files belong in R2 or ignored local storage, not Git.
- Engine files marked `INVENTORIED_NEEDS_RUNTIME_CHECK` need direct CLI/test execution after their feeder dependencies are confirmed.
- Website files marked `INVENTORIED_NEEDS_BROWSER_CHECK` need local preview validation after data paths are confirmed.

## Next Required Terminal Checks
```powershell
git status --short
Get-ChildItem audits\prediction_engine_full_audit -File | Select-Object Name,Length,LastWriteTime
```
