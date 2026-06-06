# Production Equivalence Diagnosis

## Result
- Production promotion attempted: `no`
- Production files modified: `no`
- Direct production equivalence: `FAIL`
- Diagnosis: controlled outputs are useful engine artifacts, but they are not production-equivalent runtime feeds.

## Main Cause
The controlled folders are not only a pure bonus-engine run, but they are still mostly bonus-engine materializer outputs plus a few special-case appenders. Production files are wider runtime surfaces: they include preference lanes, Sportsman/random-only lanes, youth review lanes, allocation/reference rows, point ladder rows, Hunt Research JSON display fields, and source/lineage decorations.

## Blocker Counts
- Missing production column rows classified: `776`
- Missing family rows classified: `224`
- Runtime merge checks: `12`
- Promotion-blocking checks: `12`

## Runtime Merge Classification Counts
- `ALLOCATION_OR_REFERENCE_ONLY`: `2`
- `BONUS_ENGINE_OUTPUT`: `4`
- `PREFERENCE_ENGINE_OUTPUT`: `2`
- `PUBLIC_RUNTIME_DISPLAY_METADATA`: `4`

## Missing Family Classification Counts
- `BONUS_ENGINE_OUTPUT`: `100`
- `PREFERENCE_ENGINE_OUTPUT`: `52`
- `PUBLIC_RUNTIME_DISPLAY_METADATA`: `2`
- `SPORTSMAN_RANDOM_ONLY`: `4`
- `TRUE_MISSING_MODEL_OUTPUT`: `60`
- `YOUTH_REVIEW_REQUIRED`: `6`

## What Is Missing
- `PREFERENCE_ENGINE_OUTPUT`: preference-point and dedicated-hunter rows require the preference engine/output merge path.
- `SPORTSMAN_RANDOM_ONLY`: Sportsman rows are random-only and special-case, not produced by the basic bonus ladder.
- `YOUTH_REVIEW_REQUIRED`: youth rows need separate youth routing/review before production replacement.
- `ALLOCATION_OR_REFERENCE_ONLY`: point ladder, allocation, permit, boundary, and reference rows come from runtime/reference merge layers.
- `PUBLIC_RUNTIME_DISPLAY_METADATA`: Hunt Research JSON files are website-ready merged display surfaces, not direct model outputs.
- `PRODUCTION_COLUMN_DECORATION`: production CSVs carry lineage, source, page, and display decoration columns beyond the controlled model core.
- `TRUE_MISSING_MODEL_OUTPUT`: any remaining probability/model gaps need model-output investigation before promotion.

## Promotion Blockers By File
- `2026_from_2025_truth_pdf_draw_results` vs `processed_data/ml_draw_predictions_v1.csv`: `PREFERENCE_ENGINE_OUTPUT`, missing columns `49`, missing families `9`, missing rows `5622`.
- `2026_from_2025_truth_pdf_draw_results` vs `processed_data/draw_reality_engine_predictive_v2.csv`: `BONUS_ENGINE_OUTPUT`, missing columns `50`, missing families `5`, missing rows `4183`.
- `2026_from_2025_truth_pdf_draw_results` vs `processed_data/point_ladder_view.csv`: `ALLOCATION_OR_REFERENCE_ONLY`, missing columns `28`, missing families `19`, missing rows `78162`.
- `2026_from_2025_truth_pdf_draw_results` vs `processed_data/hunt_research_2026.json`: `PUBLIC_RUNTIME_DISPLAY_METADATA`, missing columns `101`, missing families `36`, missing rows `91759`.
- `2026_from_2025_truth_pdf_draw_results` vs `processed_data/hunt_research_2026_ladder.json`: `PUBLIC_RUNTIME_DISPLAY_METADATA`, missing columns `101`, missing families `36`, missing rows `91759`.
- `2026_from_2025_truth_pdf_draw_results` vs `data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv`: `BONUS_ENGINE_OUTPUT`, missing columns `59`, missing families `7`, missing rows `24465`.
- `2027_from_2026_dwr_released_candidate` vs `processed_data/ml_draw_predictions_v1.csv`: `PREFERENCE_ENGINE_OUTPUT`, missing columns `49`, missing families `9`, missing rows `5622`.
- `2027_from_2026_dwr_released_candidate` vs `processed_data/draw_reality_engine_predictive_v2.csv`: `BONUS_ENGINE_OUTPUT`, missing columns `50`, missing families `5`, missing rows `4183`.
- `2027_from_2026_dwr_released_candidate` vs `processed_data/point_ladder_view.csv`: `ALLOCATION_OR_REFERENCE_ONLY`, missing columns `28`, missing families `19`, missing rows `78162`.
- `2027_from_2026_dwr_released_candidate` vs `processed_data/hunt_research_2026.json`: `PUBLIC_RUNTIME_DISPLAY_METADATA`, missing columns `101`, missing families `36`, missing rows `91759`.
- `2027_from_2026_dwr_released_candidate` vs `processed_data/hunt_research_2026_ladder.json`: `PUBLIC_RUNTIME_DISPLAY_METADATA`, missing columns `101`, missing families `36`, missing rows `91759`.
- `2027_from_2026_dwr_released_candidate` vs `data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv`: `BONUS_ENGINE_OUTPUT`, missing columns `59`, missing families `7`, missing rows `24465`.

## Required Reports
- `audits/prediction_model_runs/production_eligibility/diagnose_missing_production_columns.csv`
- `audits/prediction_model_runs/production_eligibility/diagnose_missing_families.csv`
- `audits/prediction_model_runs/production_eligibility/diagnose_runtime_merge_requirements.csv`
