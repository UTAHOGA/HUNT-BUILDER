# Phase 5 Targeted Production Breakpoint Check

## Git Status

```text
?? audits/prediction_engine_full_audit/

```
## Primary Findings To Review

- Compare `processed_data/point_ladder_view.csv` against runtime draft versions. If production has only 2 rows while runtime draft has tens of thousands, production point ladder rendering is likely broken or starved.
- `processed_data/public_contracts/hunt_odds_history.json` failed Phase 4 parsing. Confirm whether it is used. If not used, do not repair it unnecessarily. If used, regenerate from CSV or remove from runtime manifest.
- `hard-copy/data/documents.json` is missing, but public hard-copy library data exists. Confirm whether the JS fallback prefers `public/hard-copy/data/library_page_data.json` or still expects `documents.json`.

## Point Ladder Profiles

|file|exists|size_mb|rows|columns|hunt_code_like_columns|status|
|---|---|---|---|---|---|---|
|processed_data/point_ladder_view.csv|True|0.001|2|23|hunt_code|PASS|
|data_model/runtime_drafts/point_ladder_view_v2.csv|True|42.725|91588|51|hunt_code;hunt_name;hunt_type;hunt_class|PASS|
|data_model/runtime_drafts/point_ladder_view_v3.csv|True|20.116|78162|28|hunt_code;hunt_name;hunt_type;hunt_class|PASS|
|processed_data/backups/current_year_allotment_overlay_20260523_071315/point_ladder_view.csv|True|45.708|92844|88|hunt_code;reason_codes;hunt_category|PASS|

## JSON Breakpoint Profiles

|file|exists|size_mb|status|first_200|parse_note|
|---|---|---|---|---|---|
|processed_data/public_contracts/hunt_odds_history.json|True|108.673|SKIPPED_FULL_PARSE_LARGE|[\n  {\n    "hunt_code": "BI1000",\n    "boundary_id": "5000",\n    "hunt_name": "Bison - Statewide Permit",\n    "species": "Bison",\n  ...||
|processed_data/public_contracts/hunt_predictions.json|True|27.126|PASS_JSON|[\n  {\n    "hunt_code": "BI1000",\n    "hunt_name": "Bison - Statewide Permit",\n    "species": "Bison",\n    "sex_type": "Hunters Choic...|type=list; count=26389|
|data/hunt_predictions.json|True|28.662|PASS_JSON|[\n  {\n    "hunt_code": "BI1000",\n    "hunt_name": "Sportsman Bison",\n    "species": "Bison",\n    "sex_type": "Hunters Choice",...|type=list; count=27940|
|data/hunt_odds_history.json|True|108.691|SKIPPED_FULL_PARSE_LARGE|[\n  {\n    "hunt_code": "BI1000",\n    "boundary_id": "5000",\n    "hunt_name": "Bison - Statewide Permit",\n    "species": "Bison",\n  ...||
|processed_data/hunt_research_2026.json|True|291.752|SKIPPED_FULL_PARSE_LARGE|[{"hunt_code":"BI1000","hunt_name":"Bison - Statewide Permit","species":"Bison","sex_type":"Hunters Choice","weapon":"Any Legal Weapon","...||
|processed_data/hunt_research_2026_ladder.json|True|291.752|SKIPPED_FULL_PARSE_LARGE|[{"hunt_code":"BI1000","hunt_name":"Bison - Statewide Permit","species":"Bison","sex_type":"Hunters Choice","weapon":"Any Legal Weapon","...||

## Hard-Copy Library Profiles

|file|exists|size_mb|status|first_200|parse_note|
|---|---|---|---|---|---|
|hard-copy/data/documents.json|False||MISSING|||
|public/hard-copy/data/documents.json|True|0.003|PASS_JSON|[\n  {\n    "folderId": "rules",\n    "title": "2026 Big Game Application Guidebook",\n    "subtitle": "Current-cycle big game applicatio...|type=list; count=10|
|public/hard-copy/data/library_page_data.json|True|1.415|PASS_JSON|[\n  {\n    "hunt_code": "BI6500",\n    "species": "Bison",\n    "hunt_name": "Antelope Island",\n    "unit": "",\n    "weapon": "A...|type=list; count=1471|
|public/hard-copy/data/library_page_hunts.csv|True|0.606|PASS|||
|public/hard-copy/data/library_page_summary.json|True|0.015|PASS_JSON|{\n  "generated_at": "2026-06-05T10:20:58.197Z",\n  "current_source_used": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",\n ...|type=dict; count=12|
|public/hard-copy/manifests/hard_data_manifest.json|True|0.015|PASS_JSON|{\n  "generated_at": "2026-06-05T10:20:58.197Z",\n  "current_source_used": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",\n ...|type=dict; count=12|

## Code Reference Hits

|file|pattern|hit_count|sample_hits|
|---|---|---|---|
|config.js|point_ladder_view.csv|1|L353: relativePath: 'processed_data/point_ladder_view.csv',|
|config.js|json.uoga.workers.dev|1|L43: const CLOUDFLARE_BASE = 'https://json.uoga.workers.dev';|
|config.js|hunt_research_2026_split|6|L297: key: 'research_hunt_research_2026_split_index_json', // L298: relativePath: 'processed_data/hunt_research_2026_split/hunt_research_...|
|config.js|draw_reality_engine_predictive_v2|2|L338: key: 'research_draw_reality_engine_predictive_v2_csv', // L339: relativePath: 'processed_data/draw_reality_engine_predictive_v2.csv',|
|hunt-research.js|point_ladder_view.csv|1|L34: : [fallbackR2('processed_data/point_ladder_view.csv')];|
|hunt-research.js|json.uoga.workers.dev|1|L2: const FALLBACK_R2_BASE = String(window.UOGA_CONFIG?.CLOUDFLARE_BASE // 'https://json.uoga.workers.dev').replace(/\/+$/, '');|
|hunt-research.js|hunt_research_2026_split|4|L15: : [fallbackR2('processed_data/hunt_research_2026_split/hunt_research_2026.index.json')]; // L18: : [fallbackR2('processed_data/hunt_...|
|hunt-research.js|hunt_research_2026_ladder|1|L26: : [fallbackR2('processed_data/hunt_research_2026_ladder.json')];|
|hunt-research.js|ml_draw|1|L905: return num(firstAvailable(row, ['ml_draw_probability_2026', 'ml_draw_prob_2026', 'ml_draw_probability_pct']));|
|assets/js/hard-copy-public-library.js|documents.json|2|L4: "./hard-copy/data/documents.json", // L5: "./public/hard-copy/data/documents.json",|
|assets/js/hard-copy-public-library.js|library_page_data.json|1|L31: "library_page_data.json",|
|assets/js/hard-copy-public-library.js|library_page_hunts.csv|2|L37: "processed_data/hard_data_exports/library/library_page_hunts.csv", // L38: "processed_data/library/library_page_hunts.csv",|
|assets/js/hard-copy-public-library.js|processed_data|11|L20: "processed_data/hunt_master_enriched.csv", // L21: "processed_data/point_ladder_view.csv", // L22: "processed_data/draw_reality_engi...|
|assets/js/hard-copy-public-library.js|public/hard-copy|17|L5: "./public/hard-copy/data/documents.json", // L42: { folderId: "rules", title: "2026 Big Game Application Guidebook", subtitle: "Curre...|
|scripts/build-library-page-data.js|library_page_data.json|4|L33: libraryJson: 'processed_data/library/library_page_data.json', // L38: productionJson: 'processed_data/production/library_page_data.j...|
|scripts/build-library-page-data.js|point_ladder_view.csv|1|L20: pointLadderView: 'processed_data/point_ladder_view.csv',|
|scripts/build-library-page-data.js|ml_draw_predictions_v1.csv|1|L19: mlDrawPredictions: 'processed_data/ml_draw_predictions_v1.csv',|
|scripts/build-library-page-data.js|draw_reality_engine_predictive_v2.csv|1|L18: drawRealityEnginePredictive: 'processed_data/draw_reality_engine_predictive_v2.csv',|
