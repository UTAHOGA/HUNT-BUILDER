# LFS Runtime Canonicalization Report

Generated: 2026-06-01T11:44:03.649981

## Scope
- Audit of all currently LFS-tracked files in repo.
- Classification of live website universe dependencies.
- Canonical source assignment and runtime action recommendations.

## LFS Pattern Inventory (.gitattributes)
- `processed_data/ml_draw_predictions_v1.csv`
- `processed_data/draw_reality_engine_predictive_v2.csv`
- `processed_data/draw_reality_engine.csv`
- `processed_data/hunt_master_enriched_2026_draw_subset.csv`
- `processed_data/statewide_composite_boundaries_2026.geojson`
- `processed_data/composite_hunt_unit_mapping_2026.geojson`
- `data_truth/draw_results_truth/normalized/draw_results_long.csv`
- `data_model/runtime_drafts/mixed_predictive_engine_2026.predictions.csv`
- `data_model/runtime_drafts/mixed_predictive_engine_2026.materialized.csv`
- `data_model/runtime_drafts/mixed_predictive_engine_2026.audit.csv`
- `processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson`
- `processed_data/public_contracts/hunt_odds_history.json`
- `processed_data/hunt_truth_from_json.sqlite`
- `processed_data/draw_system_coverage_report.csv`
- `processed_data/draw_reality_engine_backup_before_2024_import.csv`
- `processed_data/backups/**/point_ladder_view.csv`

## Counts
- LFS-tracked files audited: **20**
- LIVE_RUNTIME_REQUIRED: **4**
- PUBLIC_DOWNLOAD_REQUIRED: **0**
- INTERNAL_REFERENCE_ONLY: **8**
- GENERATED_REFERENCE_ONLY: **4**
- OBSOLETE_OR_LEGACY: **4**
- REVIEW_REQUIRED: **0**

## Canonical Source Distribution
- CLOUDFLARE_R2_PUBLIC: **4**
- LEGACY_TO_REMOVE: **4**
- LOCAL_REFERENCE_ONLY: **12**

## Recommended Actions
- KEEP_REFERENCE_ONLY: **16**
- SERVE_FROM_R2: **4**

## Live Runtime Universe (LFS-tracked only)
- `processed_data/draw_reality_engine.csv` -> `CLOUDFLARE_R2_PUBLIC` / `SERVE_FROM_R2`
- `processed_data/draw_reality_engine_predictive_v2.csv` -> `CLOUDFLARE_R2_PUBLIC` / `SERVE_FROM_R2`
- `processed_data/hunt_master_enriched.csv` -> `CLOUDFLARE_R2_PUBLIC` / `SERVE_FROM_R2`
- `processed_data/statewide_composite_boundaries_2026.geojson` -> `CLOUDFLARE_R2_PUBLIC` / `SERVE_FROM_R2`

## Domain Canonicalization Check (Active Runtime Files)
- Canonical domain expected: `huntbuilder.uoga.org`
- Alternate domain reference found in active runtime files: NO
