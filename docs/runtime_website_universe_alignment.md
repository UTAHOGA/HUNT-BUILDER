# Runtime Website Universe Alignment

Generated: 2026-06-04

## Purpose

This pass aligned the active website/runtime hunt-code universe after the Research contract rebuild reached the `DATABASE.csv` universe.

## Required-now files updated

These files are active or public/runtime-facing and were updated or republished:

- `data/hunt-master-canonical-2026-foundation.json`
- `data/hunt-master-canonical-2026-foundation.csv`
- `data/hunt-master-canonical-2026-source-of-truth.json`
- `data/hunt-master-canonical-2026-source-of-truth.csv`
- `data/hunt-master-canonical-2026-database-candidate.json`
- `data/hunt-master-canonical-2026-database-candidate.csv`
- `processed_data/hunt-master-canonical-2026-source-of-truth.json`
- `processed_data/hunt-master-canonical-2026-source-of-truth.csv`
- `processed_data/hunt_research_2026_split/hunt_research_2026.index.json`
- `processed_data/hunt_research_2026_split/hunts/*.json`
- `processed_data/hunt_research_2026_split/manifest.json`
- `processed_data/hunt_research_2026_split/split-summary.json`
- `processed_data/hunt_research_2026.json`
- `processed_data/hunt_research_2026_ladder.json`
- `processed_data/hunt_research_2026_ladder_preference.json`
- `processed_data/hunt_research_2026_ladder_bonus_max_random.json`
- `public/data/runtime-manifest.json`
- `data/runtime-manifest.json`
- `config.js`
- `scripts/publish-runtime-assets-r2.js`

## Files confirmed as still needing runtime awareness

The following files are part of the active or public/download website universe and should be kept aligned/published when rebuilt:

- `processed_data/hunt_master_enriched.csv`
- `processed_data/ml_draw_predictions_v1.csv`
- `processed_data/draw_reality_engine.csv`
- `processed_data/draw_reality_engine_v2.csv`
- `processed_data/draw_reality_engine_predictive_v2.csv`
- `processed_data/draw_reality_view.csv`
- `processed_data/hunt_unit_reference_linked.csv`
- `processed_data/point_ladder_view.csv`

## Files not promoted as active runtime

- `processed_data/hunt_master_enriched_2026_draw_subset.csv` remains missing/review-required and is not an active runtime source.
- `data_truth/draw_results_truth/normalized/draw_results_long.csv` remains truth/reference only.
- `processed_data/hunt_truth_from_json.sqlite` remains internal only.
- `processed_data/draw_system_coverage_report.csv` remains internal QA only.
- `processed_data/draw_reality_engine_backup_before_2024_import.csv` remains historical backup/reference only.

## Key results

- Builder first-load hunt master changed from `1394` codes to `1471` codes.
- Builder fallback/source-of-truth master changed from `1411` codes to `1471` codes.
- Processed hunt-master mirror now has `1471` codes.
- Research split index changed from `1607` codes to `1471` codes.
- `179` stale split detail files outside `DATABASE.csv` were removed.
- Large runtime JSON files were minified without changing values so Wrangler could publish them under the 300 MiB object-upload limit.
- `config.js` cache versions were bumped to `20260604-runtime-canonical-1`.
- Stale hardcoded LFS-pointer assumptions were removed from `config.js`.

## Cloudflare R2 publication

Published to bucket `uoga-data` under each file's repo-relative key. Public base:

`https://json.uoga.workers.dev`

All published R2 public URLs returned `200` with matching byte lengths during validation.

## Remaining deployment step

The Cloudflare objects are live. The rebuilt `data/*.json`, `config.js`, and manifest files still need the normal Vercel/GitHub deployment path before `https://huntbuilder.uoga.org` can use the rebuilt Builder first-load master.
