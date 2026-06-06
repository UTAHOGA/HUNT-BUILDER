# Clean Production Audit Targets

This pass excludes audit files, pages-dist duplicates, raw pipeline files, backup directories, tests, and false file references like r/w/rb.

## Production Engine Targets

|path|score|keyword_hits|public_delivery_hits|clean_refs|
|---|---|---|---|---|
|scripts/build-database-publish-readiness-report.py|150|antlerless;audit;bonus;database;draw;engine;harvest;point_ladder;predict;prediction;preference;turkey|draw_reality;ml_draw_predictions;point_ladder;processed_data/|canonical/permit-allocation-2026-integrity-report.json;data_truth/crosswalk_truth/normalized/retired_current_hunt_cod...|
|scripts/build-library-page-data.js|110|audit;database;draw;engine;harvest;odds;point_ladder;predict;prediction;sportsman|/public/;cloudflare;draw_reality;hard-copy/;json.uoga.workers.dev;ml_draw_predictions;point_ladder;processed_data/;pu...||
|scripts/publish-runtime-assets-r2.js|110|audit;bonus;database;draw;engine;hunt_research;odds;point_ladder;predict;prediction;preference|cloudflare;draw_reality;hunt_research;json.uoga.workers.dev;ml_draw_predictions;point_ladder;processed_data/;public/;r2||
|tools/verify_prediction_engine_targeted_backfill.py|110|audit;bonus;database;draw;engine;harvest;odds;point_ladder;predict;prediction;preference|cloudflare;draw_reality;json.uoga.workers.dev;ml_draw_predictions;point_ladder;processed_data/;public/;r2||
|scripts/audit-active-data-feeds.js|95|audit;bonus;database;draw;engine;harvest;hunt_research;odds;point_ladder;predict;prediction;preference;reconcile|cloudflare;draw_reality;hard-copy/;hunt_research;ml_draw_predictions;point_ladder;processed_data/;r2||
|hunt-research.js|90|antlerless;audit;bear;bonus;draw;engine;etl;harvest;hunt_research;lion;odds;point_ladder;predict;prediction;preferenc...|cloudflare;draw_reality;hunt_research;json.uoga.workers.dev;point_ladder;processed_data/;r2||
|scripts/audit-database-fragment-manifest.js|90|audit;database;draw;engine;harvest;odds;point_ladder;predict;prediction|draw_reality;ml_draw_predictions;point_ladder;processed_data/|pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv|
|scripts/audit-repo-file-retention.py|90|audit;database;draw;engine;harvest;hunt_research;point_ladder;predict;prediction|cloudflare;data_model/;draw_reality;hunt_research;ml_draw_predictions;point_ladder;processed_data/;r2||
|scripts/audit-repo-storage-placement.py|90|audit;bonus;database;draw;engine;hunt_research;odds;point_ladder;predict;prediction;preference|cloudflare;data_model/;draw_reality;hunt_research;ml_draw_predictions;point_ladder;processed_data/;public/;r2||
|scripts/audit-site-performance-library-outfitters.js|90|antlerless;audit;database;draw;engine;harvest;hunt_research;point_ladder;predict;prediction|cloudflare;draw_reality;hunt_research;ml_draw_predictions;point_ladder;processed_data/;public/;r2||
|scripts/rebuild-runtime-hunt-master-and-split.py|90|audit;bonus;database;draw;engine;harvest;hunt_research;point_ladder;predict;prediction;preference|cloudflare;draw_reality;hunt_research;ml_draw_predictions;point_ladder;processed_data/;r2||
|config.js|80|antlerless;bear;cougar;draw;engine;harvest;hunt_research;point_ladder;predict;turkey|/public/;cloudflare;draw_reality;hunt_research;json.uoga.workers.dev;point_ladder;processed_data/;public/;r2||
|scripts/build-pages-dist.js|70|antlerless;audit;bear;cougar;database;draw;engine;harvest;odds;point_ladder;predict;prediction;turkey|cloudflare;draw_reality;ml_draw_predictions;point_ladder;processed_data/;public/||
|tools/apply_boundary_crossmap_to_runtime_files.py|70|audit;database;hunt_research|hunt_research;processed_data/|data/hunt-master-canonical-2026-foundation.json;data/hunt-master-canonical-2026-source-of-truth.json;pipeline/RAW/hun...|
|tools/hunt_research_engine/audit_harvest_engine_ingestion.py|70|audit;database;draw;engine;harvest;hunt_research;ingest;point_ladder;predict;prediction|data_model/;draw_reality;hunt_research;ml_draw_predictions;point_ladder;processed_data/;r2||
|scripts/build-canonical-data-chain-report-step3.js|65|audit;database;draw;engine;harvest;point_ladder;predict;prediction;validate|cloudflare;draw_reality;ml_draw_predictions;point_ladder;processed_data/||
|tools/hunt_research_engine/audit_runtime_feeder_parity.py|65|audit;bonus;draw;engine;harvest;hunt_research;materialize;point_ladder;predict;prediction|data_model/;draw_reality;hunt_research;ml_draw_predictions;point_ladder;processed_data/;public/;r2||
|scripts/audit-lfs-runtime-canonicalization.py|60|audit|cloudflare;data_model/;documents.json;processed_data/;r2||
|engine/utah_predictive_mixed/materialize.py|55|audit;bonus;database;draw;engine;harvest;materialize;odds;point_ladder;predict;prediction;preference;sportsman;validate|draw_reality;ml_draw_predictions;point_ladder||
|scripts/clear-elk-private-lands-el-lo-2026-permit-fields.py|50|audit;bonus;database;draw;engine;harvest;materialize;odds;point_ladder;predict;prediction|data_model/;draw_reality;ml_draw_predictions;point_ladder;processed_data/;public/||
|scripts/lock-black-bear-conservation-br7307-2026.py|50|audit;bear;cougar;database;draw;engine;harvest;materialize;odds;point_ladder;predict;prediction;validate|data_model/;draw_reality;ml_draw_predictions;point_ladder;processed_data/||
|scripts/repair-prediction-feeder-targeted-backfill.py|50|audit;database;draw;engine;harvest;odds;point_ladder;predict;prediction|draw_reality;ml_draw_predictions;point_ladder;processed_data/||
|tools/engine_feeder_contract.py|50|antlerless;audit;bear;bonus;classifier;cougar;database;draw;engine;harvest;lion;materialize;odds;point_ladder;predict...|data_model/;draw_reality;ml_draw_predictions;point_ladder;processed_data/||
|engine/utah_bonus_predictive/materialize.py|50|antlerless;audit;bear;bonus;classifier;database;draw;engine;harvest;lion;materialize;odds;predict;prediction;preferen...|draw_reality;ml_draw_predictions||
|scripts/build-database-candidate-review-package.js|45|antlerless;audit;bear;database;draw;engine;harvest;point_ladder;predict;prediction;sportsman|draw_reality;ml_draw_predictions;point_ladder;processed_data/||
|scripts/build-database-fragment-manifest-step2.js|45|audit;database;draw;engine;harvest;ingest;point_ladder;predict;prediction|/public/;draw_reality;hard-copy/;ml_draw_predictions;point_ladder;processed_data/;public/||
|scripts/promote-ea-private-lands-canonical-2026.py|45|antlerless;audit;database;draw;engine;harvest;materialize;point_ladder;predict;prediction;validate|data_model/;draw_reality;ml_draw_predictions;point_ladder;processed_data/||
|tools/git_size_guard.py|45|harvest;ingest|cloudflare;data_model/;processed_data/;public/;r2||
|engine/utah_draw_predictive/database_hunt_code_model_gap.py|45|audit;bonus;classifier;database;draw;engine;odds;predict;prediction;preference;sportsman|draw_reality;ml_draw_predictions;processed_data/||
|app.js|40|antlerless;bear;cougar;draw;engine;etl;harvest;hunt_research;odds;preference;sportsman;transform;turkey;validate|cloudflare;hunt_research;processed_data/||
|scripts/apply-current-year-permit-allotments.py|40|database;draw;engine;point_ladder;predict;prediction|draw_reality;ml_draw_predictions;point_ladder;processed_data/||
|scripts/build-hunt-research-classification-layer.js|40|antlerless;audit;database;draw;engine;harvest;odds;point_ladder;predict;prediction;sportsman|data_model/;draw_reality;point_ladder;processed_data/|age;database;harvest;ladder;management;master;predictive;readiness;syncMatrix;yearChange|
|scripts/cloudflare-r2-runtime-worker.js|40||cloudflare;r2||
|scripts/finalize-canonical-coverage.js|40||cloudflare;r2||
|scripts/promote-2025-draw-permits-to-runtime.py|40|database;draw;engine;point_ladder;predict;prediction|draw_reality;ml_draw_predictions;point_ladder||
|scripts/promote-2026-draw-permit-subset.py|40|database;draw;engine;lion;point_ladder;predict;prediction|draw_reality;ml_draw_predictions;point_ladder||
|scripts/promote-hunt-class-selection-matrix-2026.py|40|database;draw;engine;point_ladder;predict;prediction|draw_reality;ml_draw_predictions;point_ladder||
|scripts/remove-retired-and-extra-cougar-active-runtime-codes-2026.py|40|cougar;database;draw;engine;point_ladder;predict;prediction|draw_reality;ml_draw_predictions;point_ladder||
|engine/utah_draw_predictive/availability_review.py|40|bear;bonus;classifier;cougar;draw;engine;harvest;lion;materialize;predict;prediction;preference;sportsman|draw_reality;ml_draw_predictions;processed_data/||
|engine/utah/quality/materialize_harvest_feature_model.py|40|audit;bonus;database;draw;engine;harvest;materialize;predict;prediction;preference|draw_reality;ml_draw_predictions||

_Showing first 40 of 388._

## Production Page / Rendering Targets

|path|score|keyword_hits|public_delivery_hits|clean_refs|
|---|---|---|---|---|
|hunt-research.js|90|antlerless;audit;bear;bonus;draw;engine;etl;harvest;hunt_research;lion;odds;point_ladder;predict;prediction;preferenc...|cloudflare;draw_reality;hunt_research;json.uoga.workers.dev;point_ladder;processed_data/;r2||
|config.js|80|antlerless;bear;cougar;draw;engine;harvest;hunt_research;point_ladder;predict;turkey|/public/;cloudflare;draw_reality;hunt_research;json.uoga.workers.dev;point_ladder;processed_data/;public/;r2||
|assets/js/hard-copy-public-library.js|70|audit;bear;bonus;cougar;database;draw;engine;harvest;odds;point_ladder;predict;prediction;turkey|/public/;documents.json;draw_reality;hard-copy/;ml_draw_predictions;point_ladder;processed_data/;public/||
|assets/js/research-outlook-dashboard.js|65|draw;engine;harvest;hunt_research;odds;predict;prediction;transform|cloudflare;hunt_research;json.uoga.workers.dev;processed_data/||
|research.html|45|draw;engine;harvest;odds;predict;prediction;transform;turkey|cloudflare||
|app.js|40|antlerless;bear;cougar;draw;engine;etl;harvest;hunt_research;odds;preference;sportsman;transform;turkey;validate|cloudflare;hunt_research;processed_data/||
|ui.js|15|draw;hunt_research;odds;transform|hunt_research||
|coverage.html|10|draw;engine;harvest;transform|||
|hard-copy.html|10|draw;harvest|||
|hard-data.html|10|audit;database;draw;transform|/public/;hard-copy/;processed_data/;public/||
|index.html|10|draw;odds;transform|||
|header-layout.js|5|engine;odds;transform|||
|hunt-research.html|5||||

## Production Delivery Dependencies

|source_ref|consumed_by|consumer_type|output_ref|page_area|score|status|
|---|---|---|---|---|---|---|
|processed_data/draw_reality_engine_predictive_v2.csv|scripts/build-database-publish-readiness-report.py|engine_or_transform|||55|TRACE_DETECTED|
|pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv|scripts/audit-database-fragment-manifest.js|engine_or_transform|||45|TRACE_DETECTED|
|pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv|scripts/build-database-publish-readiness-report.py|engine_or_transform|||45|TRACE_DETECTED|
|pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv|tools/apply_boundary_crossmap_to_runtime_files.py|engine_or_transform|||45|TRACE_DETECTED|
|processed_data/ml_draw_predictions_v1.csv|scripts/build-database-publish-readiness-report.py|engine_or_transform|||35|TRACE_DETECTED|
|processed_data/point_ladder_view.csv|scripts/build-database-publish-readiness-report.py|engine_or_transform|||30|TRACE_DETECTED|
|processed_data/hunt_research_2026_split/hunts|tools/apply_boundary_crossmap_to_runtime_files.py|engine_or_transform||research|25|TRACE_DETECTED|
|processed_data/hunt_research_2026_summary.json|tools/apply_boundary_crossmap_to_runtime_files.py|engine_or_transform||research|25|TRACE_DETECTED|
|C:/Users/tyler/Desktop/BIBLE HUNT CODES/2021.zip|tools/hunt_research_engine/audit_2021_harvest_database_ingestion.py|engine_or_transform||research|15|TRACE_DETECTED|
|C:/Users/tyler/Desktop/BIBLE HUNT CODES/2022.zip|tools/hunt_research_engine/audit_2022_harvest_database_ingestion.py|engine_or_transform||research|15|TRACE_DETECTED|
|C:/Users/tyler/Desktop/BIBLE HUNT CODES/2023.zip|tools/hunt_research_engine/audit_2023_harvest_database_ingestion.py|engine_or_transform||research|15|TRACE_DETECTED|
|C:/Users/tyler/Desktop/BIBLE HUNT CODES/2025.zip|tools/hunt_research_engine/audit_2025_harvest_draw_ingestion.py|engine_or_transform||research|15|TRACE_DETECTED|
|D:/DOCUMENTS/GitHub/HUNTS/HUNTS/data_truth/harvest_results_truth/raw_packages/2023_for_2024_harvest_results_2023_all_...|scripts/audit-2026-additional-crosswalk-sources.py|engine_or_transform|||10|TRACE_DETECTED|
|D:/DOCUMENTS/GitHub/HUNTS/HUNTS/data_truth/harvest_results_truth/raw_packages/2023_for_2024_harvest_results_2023_all_...|scripts/audit-2026-additional-crosswalk-sources.py|engine_or_transform|||10|TRACE_DETECTED|
|processed_data/draw_system_coverage_report.json|scripts/build-database-publish-readiness-report.py|engine_or_transform|||10|TRACE_DETECTED|
|database|scripts/build-hunt-research-classification-layer.js|engine_or_transform||research|10|TRACE_DETECTED|
|harvest|scripts/build-hunt-research-classification-layer.js|engine_or_transform||research|10|TRACE_DETECTED|
|predictive|scripts/build-hunt-research-classification-layer.js|engine_or_transform||research|10|TRACE_DETECTED|
|C:/Users/tyler/Desktop/GitHub/HUNTS/pipeline/RAW/hunt_unit_database/2026/pdf/regulations/2026 Bear Cougar Furbearer G...|scripts/audit-2026-regulation-pdfs-against-unresolved-permits.py|engine_or_transform|||5|TRACE_DETECTED|
|C:/Users/tyler/Desktop/GitHub/HUNTS/pipeline/RAW/hunt_unit_database/2026/pdf/regulations/2026 Big Game Application.pdf|scripts/audit-2026-regulation-pdfs-against-unresolved-permits.py|engine_or_transform|||5|TRACE_DETECTED|
|C:/Users/tyler/Desktop/GitHub/HUNTS/pipeline/RAW/hunt_unit_database/2026/pdf/regulations/antlerless_guidebook.pdf|scripts/audit-2026-regulation-pdfs-against-unresolved-permits.py|engine_or_transform|||5|TRACE_DETECTED|
|canonical/permit-allocation-2026-integrity-report.json|scripts/build-database-publish-readiness-report.py|engine_or_transform|||5|TRACE_DETECTED|
|data_truth/crosswalk_truth/normalized/retired_current_hunt_codes_2026.csv|scripts/build-database-publish-readiness-report.py|engine_or_transform|||5|TRACE_DETECTED|
|processed_data/all_rac_2026_permits_vs_DATABASE.json|scripts/build-database-publish-readiness-report.py|engine_or_transform|||5|TRACE_DETECTED|
|processed_data/antlerless_elk_current_rac_allotment_vs_database_runtime.json|scripts/build-database-publish-readiness-report.py|engine_or_transform|||5|TRACE_DETECTED|
|processed_data/gpt_work_review_report.json|scripts/build-database-publish-readiness-report.py|engine_or_transform|||5|TRACE_DETECTED|
|processed_data/hunt_unit_reference_linked.csv|scripts/build-database-publish-readiness-report.py|engine_or_transform|||5|TRACE_DETECTED|
|processed_data/modeled_availability_review_report.json|scripts/build-database-publish-readiness-report.py|engine_or_transform|||5|TRACE_DETECTED|
|processed_data/truth_source_promotion_summary.json|scripts/build-database-publish-readiness-report.py|engine_or_transform|||5|TRACE_DETECTED|
|age|scripts/build-hunt-research-classification-layer.js|engine_or_transform||research|5|TRACE_DETECTED|
|ladder|scripts/build-hunt-research-classification-layer.js|engine_or_transform||research|5|TRACE_DETECTED|
|management|scripts/build-hunt-research-classification-layer.js|engine_or_transform||research|5|TRACE_DETECTED|
|master|scripts/build-hunt-research-classification-layer.js|engine_or_transform||research|5|TRACE_DETECTED|
|readiness|scripts/build-hunt-research-classification-layer.js|engine_or_transform||research|5|TRACE_DETECTED|
|syncMatrix|scripts/build-hunt-research-classification-layer.js|engine_or_transform||research|5|TRACE_DETECTED|
|yearChange|scripts/build-hunt-research-classification-layer.js|engine_or_transform||research|5|TRACE_DETECTED|

## Truth Source Targets

|feeder_file|size_mb|truth_source_guess|status|rows|columns|null_cells|duplicate_full_rows|score|
|---|---|---|---|---|---|---|---|---|
|processed_data/draw_reality_engine_predictive_v2.csv|40.955|reconciled_database_or_view|PASS|26389|173|1958740|0|55|
|data_truth/draw_results_truth/validation/black_bear_2024_draw_odds_model_target_2025_vs_DATABASE.csv|0.044|official_or_extracted_official|PASS|96|29|36|0|55|
|data_model/harvest_quality/harvest_results_2024_complete_database.csv|1.014|canonical_database|PASS|2767|44|40266|0|50|
|data_model/harvest_quality/harvest_results_2023_for_2024_complete_database.csv|0.573|canonical_database|PASS|1193|57|33268|4|50|
|data_model/harvest_quality/harvest_results_2022_for_2023_complete_database.csv|0.401|canonical_database|PASS|1023|43|17858|0|50|
|data_model/harvest_quality/harvest_average_age_global_merge_database.csv|0.318|canonical_database|PASS|1303|15|1480|0|50|
|data_model/harvest_quality/harvest_results_2021_for_2022_complete_database.csv|0.2|canonical_database|PASS|974|20|2532|0|50|
|data_model/quality/harvest_quality_2025_for_2026_vs_database.csv|0.156|canonical_database|PASS|1118|20|1274|0|50|
|data_truth/draw_results_truth/validation/le_deer_2025_draw_results_model_target_2026_vs_DATABASE.csv|0.11|official_or_extracted_official|PASS|195|40|8|0|50|
|data_truth/draw_results_truth/validation/oil_2025_draw_results_model_target_2026_vs_DATABASE.csv|0.06|official_or_extracted_official|PASS|101|40|0|0|50|
|data_truth/draw_results_truth/validation/oil_2025_draw_pdf_values_promoted_to_DATABASE.csv|0.001|official_or_extracted_official|PASS|2|21|0|0|50|
|processed_data/hunt_research_2026_ladder.json|291.752|master_hunt_research_feed|FAIL_JSON_PARSE|||||45|
|processed_data/hunt_research_2026_ladder_bonus_max_random.json|139.941|master_hunt_research_feed|FAIL_JSON_PARSE|||||45|
|processed_data/public_contracts/hunt_odds_history.json|108.673|unknown|FAIL_JSON_PARSE|||||45|
|processed_data/hunt_research_2026_ladder_preference.json|78.38|master_hunt_research_feed|FAIL_JSON_PARSE|||||45|
|processed_data/audits/hunt_research_2026_ladder_unclassified.csv|43.931|master_hunt_research_feed|PASS|46898|91|2106997|0|45|
|processed_data/audits/hunt_research_2026_ladder_unclassified_classifier_exact.csv|41.93|master_hunt_research_feed|PASS|45116|92|2066445|0|45|
|processed_data/public_contracts/hunt_odds_history.csv|29.253|unknown|PASS|176753|21|366045|0|45|
|processed_data/public_contracts/hunt_predictions.json|27.126|generated_engine_output|FAIL_JSON_PARSE|||||45|
|processed_data/all_rac_2026_permits_vs_DATABASE.csv|0.271|canonical_database|PASS|562|37|3852|0|45|
|processed_data/2026_big_game_application_guidebook_vs_DATABASE.csv|0.157|official_or_extracted_official|PASS|728|19|2033|0|45|
|processed_data/audits/legacy_vs_dwr_permit_mismatch_recommendations_with_database.csv|0.027|official_or_extracted_official|PASS|74|26|450|0|45|
|data_truth/permit_overlay_truth/validation/elk_private_lands_EL_LO_2026_vs_DATABASE.csv|0.022|canonical_database|PASS|131|13|655|0|45|
|processed_data/audits/hunt_codes_only_in_2024_not_in_2026_database.csv|0.013|canonical_database|PASS|61|7|0|60|45|
|data_truth/permit_overlay_truth/validation/black_bear_permits_2026_vs_DATABASE.csv|0.01|canonical_database|PASS|106|12|34|0|45|
|data_truth/permit_overlay_truth/validation/buck_deer_permits_2026_vs_DATABASE.csv|0.008|canonical_database|PASS|76|14|157|0|45|
|data_truth/permit_overlay_truth/validation/rocky_bighorn_permits_2026_vs_DATABASE.csv|0.003|canonical_database|PASS|21|14|25|0|45|
|data_truth/permit_overlay_truth/validation/desert_bighorn_permits_2026_vs_DATABASE.csv|0.002|canonical_database|PASS|18|13|0|0|45|
|data_truth/permit_overlay_truth/validation/elk_antlerless_private_lands_EA_2026_vs_DATABASE.csv|0.002|canonical_database|PASS|27|7|0|0|45|
|processed_data/audits/hunt_research_2026_ladder_unclassified_classifier_exact_summary.csv|0.0|master_hunt_research_feed|PASS|4|3|1|0|45|
|processed_data/audits/hunt_research_2026_ladder_unclassified_summary.csv|0.0|master_hunt_research_feed|PASS|5|3|1|0|45|
|processed_data/draw_reality_engine_backup_before_2024_import.csv|50.182|reconciled_database_or_view|PASS|141516|34|1463738|0|30|
|processed_data/ml_draw_predictions_v1.csv|46.112|generated_engine_output|PASS|27940|180|2056684|0|30|
|processed_data/draw_reality_engine_v2.csv|42.785|reconciled_database_or_view|PASS|176753|24|509165|0|30|
|data_model/runtime_drafts/draw_reality_engine_v2.csv|42.717|reconciled_database_or_view|PASS|176753|24|502766|0|30|
|data_model/runtime_drafts/draw_reality_engine_v2_rows_added.csv|32.824|reconciled_database_or_view|PASS|139891|24|425114|0|30|
|processed_data/draw_reality_view.csv|13.42|reconciled_database_or_view|PASS|53176|27|106259|0|30|
|processed_data/draw_reality_engine_clean.csv|4.464|reconciled_database_or_view|PASS|32608|15|55038|0|30|
|processed_data/audits/hunt_research_2026_max_point_above_line_display_audit.csv|1.975|master_hunt_research_feed|PASS|33418|8|24255|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192826Z/raw_packages/2021_for_2022_harvest_results_2021_for_2022_da...|0.43|harvest_source_or_output|PASS|1047|28|2799|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192845Z/raw_packages/2021_for_2022_harvest_results_2021_for_2022_da...|0.43|harvest_source_or_output|PASS|1047|28|2799|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192826Z/raw_packages/2022_for_2023_harvest_results_2022_for_2023_da...|0.336|harvest_source_or_output|PASS|1023|34|11860|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192845Z/raw_packages/2022_for_2023_harvest_results_2022_for_2023_da...|0.336|harvest_source_or_output|PASS|1023|34|11860|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192826Z/raw_packages/2022_for_2023_harvest_results_2022_for_2023_da...|0.306|harvest_source_or_output|PASS|924|34|10751|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192845Z/raw_packages/2022_for_2023_harvest_results_2022_for_2023_da...|0.306|harvest_source_or_output|PASS|924|34|10751|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192826Z/raw_packages/2023_for_2024_harvest_results_2023_all_species...|0.303|harvest_source_or_output|PASS|592|29|14|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192845Z/raw_packages/2023_for_2024_harvest_results_2023_all_species...|0.303|harvest_source_or_output|PASS|592|29|14|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192826Z/raw_packages/2022_for_2023_harvest_results_2022_for_2023_da...|0.205|harvest_source_or_output|PASS|599|34|6607|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192845Z/raw_packages/2022_for_2023_harvest_results_2022_for_2023_da...|0.205|harvest_source_or_output|PASS|599|34|6607|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192826Z/raw_packages/2021_for_2022_harvest_results_2021_for_2022_da...|0.176|harvest_source_or_output|PASS|974|13|17|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192845Z/raw_packages/2021_for_2022_harvest_results_2021_for_2022_da...|0.176|harvest_source_or_output|PASS|974|13|17|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192826Z/raw_packages/2021_for_2022_harvest_results_2021_for_2022_da...|0.162|harvest_source_or_output|PASS|974|15|8|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192845Z/raw_packages/2021_for_2022_harvest_results_2021_for_2022_da...|0.162|harvest_source_or_output|PASS|974|15|8|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192826Z/raw_packages/2021_for_2022_harvest_results_2021_for_2022_da...|0.136|harvest_source_or_output|PASS|344|28|1033|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192826Z/raw_packages/2023_for_2024_harvest_results_2023_all_species...|0.136|harvest_source_or_output|PASS|592|18|14|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192845Z/raw_packages/2021_for_2022_harvest_results_2021_for_2022_da...|0.136|harvest_source_or_output|PASS|344|28|1033|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192845Z/raw_packages/2023_for_2024_harvest_results_2023_all_species...|0.136|harvest_source_or_output|PASS|592|18|14|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192826Z/raw_packages/2023_for_2024_harvest_results_2023_all_species...|0.108|harvest_source_or_output|PASS|211|29|0|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192845Z/raw_packages/2023_for_2024_harvest_results_2023_all_species...|0.108|harvest_source_or_output|PASS|211|29|0|0|30|
|pipeline/R2_OFFLOAD/incoming/hq_unzipped_20260605T192826Z/raw_packages/2022_for_2023_harvest_results_2022_for_2023_da...|0.104|harvest_source_or_output|PASS|924|18|2197|0|30|

_Showing first 60 of 2638._

## Tracked Large Files Still In Production Scope

|path|size_mb|type|truth_source_guess|tracked|
|---|---|---|---|---|
|.tmp_r2_test.csv|44.08|data_or_feeder|unknown|yes|
|data/hunt_odds_history.csv|29.271|data_or_feeder|unknown|yes|
|data/hunt_predictions.json|28.662|data_or_feeder|generated_engine_output|yes|
|processed_data/draw_reality_engine_v2.csv|42.785|data_or_feeder|reconciled_database_or_view|yes|
|processed_data/draw_reality_view.csv|13.42|data_or_feeder|reconciled_database_or_view|yes|
|processed_data/dwr_huntplanner_hanumber_2026.json|14.696|data_or_feeder|official_or_extracted_official|yes|
|processed_data/dwr_huntplanner_hanumber_2026_raw_payloads.json|33.146|data_or_feeder|official_or_extracted_official|yes|
|processed_data/harvest_results_all_years_long.csv|28.685|data_or_feeder|harvest_source_or_output|yes|
|processed_data/harvest_supplemental_metrics_2024_for_2025_long.csv|20.392|data_or_feeder|harvest_source_or_output|yes|
|processed_data/hunt_decision_output.csv|10.887|data_or_feeder|unknown|yes|
|processed_data/mixed_predictive_engine_2026_audit.csv|12.752|data_or_feeder|generated_engine_output|yes|
|processed_data/ml_draw_predictions_v1.csv|46.112|data_or_feeder|generated_engine_output|yes|
|processed_data/projected_bonus_draw_2026_simulated.csv|17.268|data_or_feeder|unknown|yes|
|processed_data/truth_downloads_comprehensive.sqlite|10.312|other|unknown|yes|
|data/utah/foundation_bundle_2026/utah_boundaries_canonical_2026.kml|21.478|data_or_feeder|unknown|yes|
|data_model/harvest_quality/harvest_results_all_years_long.csv|23.729|data_or_feeder|harvest_source_or_output|yes|
|data_model/runtime_drafts/draw_reality_engine_v2.csv|42.717|data_or_feeder|reconciled_database_or_view|yes|
|data_model/runtime_drafts/draw_reality_engine_v2_rows_added.csv|32.824|data_or_feeder|reconciled_database_or_view|yes|
|data_model/runtime_drafts/hunt_master_enriched_v2.csv|22.527|data_or_feeder|unknown|yes|
|data_model/runtime_drafts/point_ladder_missing_columns_audit.csv|13.447|data_or_feeder|unknown|yes|
|data_model/runtime_drafts/point_ladder_view_v2.csv|42.725|data_or_feeder|unknown|yes|
|data_model/runtime_drafts/point_ladder_view_v3.csv|20.116|data_or_feeder|unknown|yes|
|data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv|18.11|data_or_feeder|generated_engine_output|yes|
|data_model/runtime_drafts/predictive_bonus_engine_2026.predictions.csv|17.725|data_or_feeder|generated_engine_output|yes|
|data_model/validation/hunt_type_hunt_class_matrix_audit.csv|23.325|data_or_feeder|unknown|yes|
|data_truth/comparison_outputs/database_candidate_review/database_candidate_review_records.csv|20.764|data_or_feeder|unknown|yes|
|data_truth/draw_results_truth/normalized/draw_results_2021_for_2022_candidate_promotion_file_records.csv|15.954|data_or_feeder|official_or_extracted_official|yes|
|data_truth/draw_results_truth/normalized/draw_results_2022_for_2023_candidate_promotion_file_records.csv|15.435|data_or_feeder|official_or_extracted_official|yes|
|data_truth/draw_results_truth/normalized/draw_results_2023_for_2024_candidate_promotion_file_records.csv|33.766|data_or_feeder|official_or_extracted_official|yes|
|data_truth/draw_results_truth/normalized/draw_results_2024_for_2025_candidate_promotion_file_records.csv|23.531|data_or_feeder|official_or_extracted_official|yes|
|data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv|23.729|data_or_feeder|harvest_source_or_output|yes|
|data_truth/harvest_results_truth/normalized/harvest_supplemental_metrics_2024_for_2025_long.csv|20.392|data_or_feeder|harvest_source_or_output|yes|
|hard-copy/pdf files/24_bg_HARVEST_report.pdf|13.387|data_or_feeder|harvest_source_or_output|yes|
|processed_data/audits/hunt_research_2026_ladder_unclassified.csv|43.931|data_or_feeder|master_hunt_research_feed|yes|
|processed_data/audits/hunt_research_2026_ladder_unclassified_classifier_exact.csv|41.93|data_or_feeder|master_hunt_research_feed|yes|
|processed_data/audits/hunt_research_numeric_defect_audit.csv|12.341|data_or_feeder|master_hunt_research_feed|yes|
|processed_data/audits/prediction_engine_targeted_backfill_verification.csv|22.757|data_or_feeder|unknown|yes|
|processed_data/public_contracts/hunt_odds_history.csv|29.253|data_or_feeder|unknown|yes|
|processed_data/public_contracts/hunt_predictions.json|27.126|data_or_feeder|generated_engine_output|yes|
|processed_data/hard_data_exports/source_pdfs/draw_odds/2025/2025-big-game-draw-results.pdf|12.142|data_or_feeder|official_or_extracted_official|yes|

## Next Repair Order

1. Confirm production page data paths: research, hunt-research, hard-data, hard-copy/library.
2. Confirm production engine feeders: hunt_research_2026, draw_reality, ml_draw_predictions, point_ladder, harvest long files, DATABASE.csv.
3. Run only the engine CLIs/tests tied to those files.
4. Patch rendering only where data fails to load, parses incorrectly, or creates duplicate text.
5. Do not stage large data files; only stage audit reports and safe source fixes.
