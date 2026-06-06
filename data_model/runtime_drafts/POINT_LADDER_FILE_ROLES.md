# Point Ladder File Roles

This folder contains multiple point-ladder products. They are not simple chronological versions.

## Production Runtime Path

`processed_data/point_ladder_view.csv`

This path must remain the public/runtime path because `config.js`, `hunt-research.js`, library manifests, and the Cloudflare R2 object contract already point to it. The website should continue loading this path until a verified unified replacement is promoted.

Current production role:
- runtime/display point ladder for the Hunt Research page
- currently matches `data_model/runtime_drafts/point_ladder_view_v3.csv`
- live R2 URL: `https://json.uoga.workers.dev/processed_data/point_ladder_view.csv`

## Allocation / Completeness Ladder

`data_model/runtime_drafts/point_ladder_view_v2.csv`

Semantic copy:

`data_model/runtime_drafts/point_ladder_allocation_complete_v2026.csv`

Role:
- allocation/completeness point ladder
- broader hunt-code coverage
- includes public permit, max-point permit, random permit, guaranteed threshold, applicant stack, draw outlook, and special permit overlay fields

Do not delete `point_ladder_view_v2.csv` yet. It remains the original versioned evidence file for the semantic copy.

## Actual-Draw Runtime / Display Ladder

`data_model/runtime_drafts/point_ladder_view_v3.csv`

Semantic copy:

`data_model/runtime_drafts/point_ladder_runtime_actual_draw_v2026.csv`

Role:
- clean runtime/display ladder
- includes `draw_pool`, actual 2025 applicant/permit fields, projected 2026 point movement, `ladder_status`, source hash, and validation fields
- currently promoted to `processed_data/point_ladder_view.csv`

Do not delete `point_ladder_view_v3.csv` yet. It remains the original versioned evidence file for the semantic copy.

## Recommended Unified Candidate

Future output:

`data_model/runtime_drafts/point_ladder_unified_runtime_v2026.csv`

Purpose:
- preserve V3 runtime/display fields
- restore V2 allocation/completeness fields
- avoid shrinking the public ladder universe during bonus/preference lane validation

Promotion rule:
- do not overwrite `processed_data/point_ladder_view.csv` until the unified candidate has valid row counts, website-required columns, allocation columns, local Hunt Research rendering, Cloudflare upload verification, and live URL header/line validation.
