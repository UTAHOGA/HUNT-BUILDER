# Final Live Push Verification Report

- Timestamp UTC: `2026-05-23T16:05:43.5376915Z`
- Branch: `main`
- Commit SHA: `a06b552ea2783bcfa7be3af6e57a071dec2924ce`
- Push result: `origin/main` matches local `main`
- Git LFS used: `yes`
- LFS tracked file count: `8`
- Cloudflare Worker deployed: `json`
- R2 bucket: `uoga-data`

## Publish Readiness

- Database publish-ready: `true`
- DATABASE unique hunt codes: `1411`
- Harvest audit blocker count: `0`
- Mixed predictive engine publish-ready: `true`
- Prediction row count: `27940`
- Duplicate key count: `0`
- Probability guardrail result: `PASS`
- Quota guardrail result: `PASS`
- Special permit guardrail result: `PASS`

## Validation Results

- `python scripts/build-database-publish-readiness-report.py`: `PASS`
- `python scripts/compare-canonical-hunt-database.py`: `PASS`
- `python scripts/build-all-rac-permit-database-compare.py`: `PASS`
- `python scripts/audit-harvest-results-database-final.py`: `PASS`
- `python scripts/build_mixed_predictive_engine_2026.py`: `PASS`
- `python scripts/audit-repo-file-retention.py`: `PASS`
- `python -m pytest tests/utah_quality -q`: `18 passed`
- `python -m pytest tests/utah_predictive_mixed -q`: `20 passed`
- Permit/truth/ladder focused tests: `43 passed`
- Draw predictive + frontend probability tests: `132 passed`
- Bonus predictive tests: `36 passed`
- `python -m compileall engine scripts tests`: `PASS`
- `node --check hunt-research.js`: `PASS`
- `node --check scripts/verify-permit-allocations-2026.js`: `PASS`
- `npm.cmd run verify:permits-2026`: `PASS`
- `npm.cmd test`: `PASS`
- Final JSON validation: `PASS`
- Required runtime files present: `PASS`
- LFS large-file staging check: `PASS`

## Runtime Verification

- Local `research.html` returned HTTP `200`.
- Production `research.html`, `config.js`, and `hunt-research.js` matched local SHA-256 hashes.
- Runtime sample verification passed for:
  - `DB1004`: public draw `80` + Expo `3` = all-class `83`; conservation not used.
  - `EB3024 Resident`: `30` max-pool guaranteed, `29` mixed cutoff, `28` random pool.
  - `EB3022 Resident`: official quota source, total `130`, max pool `65`, random pool `65`.
  - `EA1267`: 2026 allotment `180 / 20 / 200`.
  - `BR1001`: `MODELED_AVAILABILITY`, no `p_draw`.
  - `BR1000`: Sportsman model only.
- Browser automation modules were unavailable, so local verification used HTTP and runtime source-selection checks.

## Cloudflare / LFS Notes

GitHub Pages serves LFS-backed CSV files as pointer text. The hunt research loader already rejects Git LFS pointer text and falls through to the next configured source. The `json.uoga.workers.dev` Worker was deployed with the `uoga-data` R2 bucket and now returns real CSV/GeoJSON content for required runtime files.

Verified Cloudflare runtime content:

- `point_ladder_view.csv`
- `processed_data/point_ladder_view.csv`
- `processed_data/ml_draw_predictions_v1.csv`
- `processed_data/draw_reality_engine_predictive_v2.csv`
- `processed_data/draw_reality_engine_v2.csv`
- `draw_reality_engine.csv`
- `processed_data/draw_reality_engine.csv`
- `hunt_master_enriched.csv`
- `hunt_unit_reference_linked.csv`
- `processed_data/statewide_composite_boundaries_2026.geojson`
- `processed_data/composite_hunt_unit_mapping_2026.geojson`

## Retention Follow-Up

- Cloudflare R2 runtime recommendations: `2989`
- Cloudflare R2 archive recommendations: `306`
- Tracked files over 25 MB: `29`
- No files were deleted in this release.
- Remaining cleanup is storage hygiene only, not a prediction-engine blocker.
