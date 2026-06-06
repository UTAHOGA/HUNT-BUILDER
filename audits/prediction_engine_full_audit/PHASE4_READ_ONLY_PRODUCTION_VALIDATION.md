# Phase 4 Read-Only Production Validation

## Git Status

```text
?? audits/prediction_engine_full_audit/

```
## Diff Stat

```text

```
## Key Feeder Validation

|file|kind|size_mb|status|rows_scanned|columns|null_cells_scanned|duplicate_full_rows_scanned|sample_columns|notes|
|---|---|---|---|---|---|---|---|---|---|
|pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv|csv|0.714|PASS|1471|41|22963|0|hunt_code;boundary_id;hunt_name;sex_type;species;weapon;hunt_type;hunt_class;season;NOTES;draw_2025_bg_pdf_page;draw_...||
|processed_data/draw_reality_engine_predictive_v2.csv|csv|40.955|PASS|26389|173|1958740|0|year;forecast_year;hunt_code;boundary_id;hunt_name;species;sportsman_species;sex_type;hunt_type;hunt_class;residency;...||
|processed_data/draw_reality_engine_v2.csv|csv|42.785|PASS|100000|24|248878|0|hunt_code;boundary_id;hunt_name;species;sex_type;hunt_type;weapon;hunt_class;season;year;draw_pool;residency;points;e...|scanned_first_100000_rows|
|processed_data/draw_reality_view.csv|csv|13.42|PASS|53176|27|106259|0|hunt_code;residency;user_points;species;unit;weapon;public_permits_2025;public_permits_2026;max_point_permits;random_...||
|processed_data/ml_draw_predictions_v1.csv|csv|46.112|PASS|27940|180|2056684|0|model_version;rule_version;year;forecast_year;hunt_code;hunt_name;species;sex_type;hunt_type;permits_2025_draw_res;pe...||
|processed_data/point_ladder_view.csv|csv|0.001|PASS|2|23|12|0|hunt_code;residency;points;public_permits_2025;public_permits_2026;public_permits_2026_source;max_point_permits_2025;...||
|processed_data/hunt_research_2026.json|json|291.752|PASS_JSONL_SAMPLE|1||||first_char=[; head=[{"hunt_code":"BI1000","hunt_name":"Bison - Statewide Permit","species":"Bison","sex_type":"Hunter...|large_file_sampled_as_jsonl|
|processed_data/hunt_research_2026_ladder.json|json|291.752|PASS_JSONL_SAMPLE|1||||first_char=[; head=[{"hunt_code":"BI1000","hunt_name":"Bison - Statewide Permit","species":"Bison","sex_type":"Hunter...|large_file_sampled_as_jsonl|
|processed_data/hunt_research_2026_ladder_bonus_max_random.json|json|139.941|PASS_JSONL_SAMPLE|1||||first_char=[; head=[{"hunt_code":"BI6500","hunt_name":"Antelope Island","species":"Bison","sex_type":"Hunters Choice"...|large_file_sampled_as_jsonl|
|processed_data/hunt_research_2026_ladder_preference.json|json|78.38|PASS_JSON|24477|101|||hunt_code;hunt_name;species;sex_type;weapon;hunt_type;hunt_class;boundary_id;unit_name;residency;points;year;draw_poo...||
|processed_data/public_contracts/hunt_odds_history.csv|csv|29.253|PASS|100000|21|179535|0|hunt_code;boundary_id;hunt_name;species;sex_type;weapon;hunt_type;hunt_class;reported_hunt_year;model_target_year;dra...|scanned_first_100000_rows|
|processed_data/public_contracts/hunt_odds_history.json|json|108.673|FAIL_JSON_PARSE_OR_GIANT_NON_JSONL|0||||first_char=[; head=[   {     "hunt_code": "BI1000",     "boundary_id": "5000",     "hunt_name": "Bison - Statewide Pe...|sample_jsonl_ok=0; sample_jsonl_bad=100; full_parse_skipped_due_size|
|processed_data/public_contracts/hunt_predictions.json|json|27.126|PASS_JSON|26389|18|||hunt_code;hunt_name;species;sex_type;weapon;hunt_type;hunt_class;residency;points;draw_pool;modeled_draw_probability;...||
|public/hard-copy/data/library_page_data.json|json|1.415|PASS_JSON|1471|22|||hunt_code;species;hunt_name;unit;weapon;permits_2026;classification;modeled;has_prediction;has_point_ladder;has_cross...||
|public/hard-copy/data/library_page_hunts.csv|csv|0.606|PASS|1471|22|5120|0|hunt_code;species;hunt_name;unit;weapon;permits_2026;classification;modeled;has_prediction;has_point_ladder;has_cross...||
|public/hard-copy/data/library_page_summary.json|json|0.015|PASS_JSON|12|dict|||generated_at;current_source_used;cloudflare_fallback_base;pages_file_limit_mb;counts;species_counts;classification_co...||
|public/hard-copy/manifests/hard_data_manifest.json|json|0.015|PASS_JSON|12|dict|||generated_at;current_source_used;cloudflare_fallback_base;pages_file_limit_mb;counts;species_counts;classification_co...||
|hard-copy/data/documents.json|json||MISSING|||||||

## Page / Code Data References

|path|size_mb|status|data_refs|r2_refs|notes|
|---|---|---|---|---|---|
|scripts/build-database-publish-readiness-report.py|0.02|PASS_READ|- `draw_reality_engine_predictive_v2` duplicate keys: {report[;- `ml_draw_predictions_v1` duplicate keys: {report[;dr...|||
|scripts/build-library-page-data.js|0.023|PASS_READ|,       has_point_ladder: point.map.has(code) ? ;./processed_data/hard_data_exports/library/;./public/hard-copy/;draw...|https://json.uoga.workers.dev||
|scripts/publish-runtime-assets-r2.js|0.02|PASS_READ|https://json.uoga.workers.dev;internal_backups_point_ladder_view_glob;processed_data;processed_data/backups;processed...|https://git-lfs.github.com/spec/v1;https://json.uoga.workers.dev||
|tools/verify_prediction_engine_targeted_backfill.py|0.041|PASS_READ|https://json.uoga.workers.dev/;processed_data/audits;processed_data/audits/prediction_engine_feeder_blank_cell_audit....|https://json.uoga.workers.dev/||
|scripts/audit-active-data-feeds.js|0.039|PASS_READ|draw_reality;draw_reality_engine_predictive;draw_reality_engine_predictive_v2.csv;hunt_research;ml_draw_predictions;p...|https://git-lfs.github.com/spec/v1||
|hunt-research.js|0.112|PASS_READ|https://json.uoga.workers.dev;hunt_research_recent_hunts;ml_draw_prob_2026;ml_draw_probability_2026;ml_draw_probabili...|https://git-lfs.github.com/spec/v1;https://json.uoga.workers.dev||
|scripts/rebuild-runtime-hunt-master-and-split.py|0.02|PASS_READ|DATABASE.csv + processed_data/hunt_research_2026_summary.json;hunt_research_2026.index.json;hunt_research_2026_split;...|https://dwrapps.utah.gov/huntboundary/hbstart?HN={code};https://git-lfs.github.com/spec/v1||
|config.js|0.025|PASS_READ|./processed_data/hunt_research_2026_split;https://json.uoga.workers.dev;processed_data/display-boundary-index-2026.js...|https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0/query?where=;https://dwrmap...||
|scripts/build-pages-dist.js|0.013|PASS_READ|processed_data/boundaries;processed_data/boundary-id-overrides-2026.json;processed_data/boundary-manifest-2026.csv;pr...|||
|tools/hunt_research_engine/audit_harvest_engine_ingestion.py|0.02|PASS_READ|4. `processed_data/ml_draw_predictions_v1.csv`, `processed_data/draw_reality_engine_predictive_v2.csv`, and `processe...|||
|assets/js/hard-copy-public-library.js|0.025|PASS_READ|)) {       candidates.add(`./public/hard-copy/${trimmed.slice(;)) {       candidates.add(`/public/hard-copy/${trimmed...|||
|assets/js/research-outlook-dashboard.js|0.045|PASS_READ|https://json.uoga.workers.dev;selected_hunt_research_draw_pool;selected_hunt_research_points;selected_hunt_research_r...|https://git-lfs.github.com/spec/v1;https://json.uoga.workers.dev||
|research.html|0.051|PASS_READ||https://js.sentry-cdn.com/26137c5576f01423efc85f47076f9548.min.js||
|hard-copy.html|0.004|PASS_READ||https://js.sentry-cdn.com/26137c5576f01423efc85f47076f9548.min.js||
|hard-data.html|0.018|PASS_READ|./processed_data/hard_data_exports/hard_data_manifest.web.json;./processed_data/hard_data_exports/library/;./public/h...|https://js.sentry-cdn.com/26137c5576f01423efc85f47076f9548.min.js||
|app.js|0.27|PASS_READ|);   // Production runtime should prefer Cloudflare/object-hosted boundary files over   // repo-served processed_data...|https://dwrapps.utah.gov/huntboundary/hbstart;https://dwrapps.utah.gov/huntboundary/hbstart?HN=${encodeURIComponent(h...||
|ui.js|0.035|PASS_READ|hunt_research_recent_hunts;selected_hunt_research_draw_pool;selected_hunt_research_points;selected_hunt_research_resi...|||
|header-layout.js|0.053|PASS_READ||https://dwrapps.utah.gov/huntboundary/hbstart;https://www.uoga.org;https://www.uoga.org/membership-sign-up;https://ww...||

## Syntax Checks

|file|kind|status|notes|
|---|---|---|---|
|scripts/build-database-publish-readiness-report.py|python|PASS_SYNTAX||
|scripts/build-library-page-data.js|javascript|PASS_SYNTAX||
|scripts/publish-runtime-assets-r2.js|javascript|PASS_SYNTAX||
|tools/verify_prediction_engine_targeted_backfill.py|python|PASS_SYNTAX||
|scripts/audit-active-data-feeds.js|javascript|PASS_SYNTAX||
|hunt-research.js|javascript|PASS_SYNTAX||
|scripts/rebuild-runtime-hunt-master-and-split.py|python|PASS_SYNTAX||
|config.js|javascript|PASS_SYNTAX||
|scripts/build-pages-dist.js|javascript|PASS_SYNTAX||
|tools/hunt_research_engine/audit_harvest_engine_ingestion.py|python|PASS_SYNTAX||
|assets/js/hard-copy-public-library.js|javascript|PASS_SYNTAX||
|assets/js/research-outlook-dashboard.js|javascript|PASS_SYNTAX||
|research.html|text/html/css|NOT_SYNTAX_CHECKED||
|hard-copy.html|text/html/css|NOT_SYNTAX_CHECKED||
|hard-data.html|text/html/css|NOT_SYNTAX_CHECKED||
|app.js|javascript|PASS_SYNTAX||
|ui.js|javascript|PASS_SYNTAX||
|header-layout.js|javascript|PASS_SYNTAX||

## Modified File Risk

_No rows._

## Phase 4 Interpretation

- PASS_JSONL_SAMPLE means the file is likely newline-delimited JSON or chunked records, not ordinary JSON. Do not call it corrupt until the consuming script is checked.
- FAIL_JSON_PARSE_OR_GIANT_NON_JSONL means the first sample did not parse as ordinary JSON or JSONL. Verify whether the file is intentionally streamed, compressed, partial, or malformed.
- HIGH_LARGE_TRACKED_FILE should not be committed without confirming it is required and intentionally regenerated.
- GENERATED_PUBLIC_DATA should be committed only if it is the intended website delivery output.
