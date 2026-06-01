# LFS Runtime Canonicalization Report

Generated: 2026-06-01T12:26:57.991754

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
- LIVE_RUNTIME_REQUIRED: **2**
- PUBLIC_DOWNLOAD_REQUIRED: **0**
- INTERNAL_REFERENCE_ONLY: **8**
- GENERATED_REFERENCE_ONLY: **4**
- OBSOLETE_OR_LEGACY: **4**
- REVIEW_REQUIRED: **2**

## Canonical Source Distribution
- CLOUDFLARE_R2_PUBLIC: **4**
- LEGACY_TO_REMOVE: **4**
- LOCAL_REFERENCE_ONLY: **12**

## Recommended Actions
- KEEP_REFERENCE_ONLY: **16**
- REVIEW_REQUIRED: **2**
- SERVE_FROM_R2: **2**

## Live Runtime Universe (LFS-tracked only)
- `processed_data/draw_reality_engine.csv` -> `CLOUDFLARE_R2_PUBLIC` / `SERVE_FROM_R2`
- `processed_data/draw_reality_engine_predictive_v2.csv` -> `CLOUDFLARE_R2_PUBLIC` / `REVIEW_REQUIRED`
- `processed_data/hunt_master_enriched.csv` -> `CLOUDFLARE_R2_PUBLIC` / `REVIEW_REQUIRED`
- `processed_data/statewide_composite_boundaries_2026.geojson` -> `CLOUDFLARE_R2_PUBLIC` / `SERVE_FROM_R2`

## Remote Upload + URL Verification
- Uploaded to remote R2 bucket (`uoga-data`) and verified `200`:
  - `https://json.uoga.workers.dev/processed_data/draw_reality_engine.csv`
  - `https://json.uoga.workers.dev/processed_data/statewide_composite_boundaries_2026.geojson`
- Also published and verified `200` for additional active runtime paths:
  - `https://json.uoga.workers.dev/processed_data/display-boundary-index-2026.json`
  - `https://json.uoga.workers.dev/processed_data/composite_hunt_unit_mapping_2026.geojson`
  - `https://json.uoga.workers.dev/processed_data/hunt_research_2026.json`
  - `https://json.uoga.workers.dev/processed_data/draw_reality_engine_v2.csv`
  - `https://json.uoga.workers.dev/processed_data/point_ladder_view.csv` (decompressed upload for browser CSV-read compatibility)
  - `https://json.uoga.workers.dev/processed_data/hunt_unit_reference_linked.csv`
  - `https://json.uoga.workers.dev/processed_data/public_contracts/outfitters-public.json`

## REVIEW_REQUIRED Runtime Items
- `processed_data/draw_reality_engine_predictive_v2.csv`
  - local file is an LFS pointer payload (no real local content to promote)
  - canonical URL exists in manifest but requires verified non-pointer source promotion
- `processed_data/hunt_master_enriched.csv`
  - local file is an LFS pointer payload (no real local content to promote)
  - canonical URL exists in manifest but requires verified non-pointer source promotion

## Runtime Redirect Result
- `public/data/runtime-manifest.json` and `data/runtime-manifest.json` are updated and kept canonicalized to Cloudflare object URLs for active runtime assets.
- Production runtime behavior remains canonical-first:
  - `config.js` runtime source selection uses manifest canonical URL chain for production hosts.
  - Hunt Research fallback mode remains disabled by default, preventing silent dependency on local LFS-backed legacy sources.

## Domain Canonicalization Check (Active Runtime Files)
- Canonical domain expected: `huntbuilder.uoga.org`
- Alternate domain reference found in active runtime files: NO
