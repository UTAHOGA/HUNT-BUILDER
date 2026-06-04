# Repo Storage Placement Decision Report

Generated: 2026-06-04T07:27:57Z

## Decision Rule

- GitHub: source code, small docs/manifests/config, small truth anchors, and reproducible scripts.
- Vercel: the frontend app and small static/runtime files required for first load.
- Cloudflare R2: large public/runtime files and public downloads.
- Local/LFS reference: raw source PDFs/XLSX, backups, SQLite, model working files, and internal truth exports not read by visitors.

## Counts

- `CLOUDFLARE_R2_PUBLIC`: `44`
- `GITHUB_AND_VERCEL_APP`: `80`
- `GITHUB_AND_VERCEL_PUBLIC`: `73`
- `GITHUB_AND_VERCEL_RUNTIME`: `482`
- `GITHUB_CODE`: `606`
- `GITHUB_DOCS`: `108`
- `GITHUB_REFERENCE_IF_PROMOTED`: `1243`
- `GITHUB_REVIEW`: `190`
- `GITHUB_SMALL_PROCESSED`: `4401`
- `GITHUB_TRUTH_SOURCE`: `514`
- `GIT_LFS_OR_LOCAL_REFERENCE`: `10`
- `LOCAL_ONLY_IGNORE`: `10772`
- `LOCAL_OR_R2_REFERENCE`: `1678`

## Must Stay In GitHub And Vercel

- Root app files: `index.html`, `research.html`, `verify.html`, `hard-copy.html`, `app.js`, `config.js`, `data.js`, `hunt-research.js`, CSS, map modules, and small supporting JS.
- Small runtime data under `data/`, especially Builder first-load hunt-master JSON files.
- Small public assets under `public/` and `assets/`.
- `public/data/runtime-manifest.json` and `data/runtime-manifest.json` as small manifests pointing to R2.

## Must Stay In GitHub But Not Vercel Runtime

- `scripts/`, `tests/`, `docs/`, `schemas/`, and small validation/audit outputs.
- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` as the current truth anchor.
- Small `data_truth/` validation/source-control files.

## Must Live In Cloudflare R2 For Public Runtime

- `processed_data/composite_hunt_unit_mapping_2026.geojson` (52.37 MB)
- `processed_data/display-boundary-index-2026.json` (0.83 MB)
- `processed_data/draw_reality_engine.csv` (23.355 MB)
- `processed_data/draw_reality_engine_predictive_v2.csv` (23.372 MB)
- `processed_data/draw_reality_engine_v2.csv` (42.785 MB)
- `processed_data/draw_reality_view.csv` (13.42 MB)
- `processed_data/hunt_master_enriched.csv` (49.372 MB)
- `processed_data/hunt_research_2026.json` (249.155 MB)
- `processed_data/hunt_research_2026_ladder.json` (249.155 MB)
- `processed_data/hunt_research_2026_ladder_bonus_max_random.json` (118.755 MB)
- `processed_data/hunt_research_2026_ladder_preference.json` (51.528 MB)
- `processed_data/hunt_research_2026_split/hunt_research_2026.index.json` (0.952 MB)
- `processed_data/hunt_research_2026_summary.json` (10.039 MB)
- `processed_data/hunt_unit_reference_linked.csv` (2.354 MB)
- `processed_data/ml_draw_predictions_v1.csv` (44.891 MB)
- `processed_data/point_ladder_view.csv` (133.881 MB)
- `processed_data/public_contracts/hunt_odds_history.json` (108.673 MB)
- `processed_data/statewide_composite_boundaries_2026.geojson` (83.11 MB)

## Should Stay Local Or LFS Reference Only

- Raw `pipeline/RAW/` PDFs/XLSX/ZIPs unless curated for public library downloads.
- `processed_data/*.sqlite`, backup folders, and model draft CSVs.
- Large truth/reference files such as `data_truth/draw_results_truth/normalized/draw_results_long.csv` unless a reviewed public contract is produced.
- Root backup/junk files such as `.tmp_r2_test.csv`, `point_ladder_view1.csv`, old `.bak` files, and stale one-off exports.

## Immediate Cleanup Recommendations

- Remove broad `.gitignore` rule `*.md`; it accidentally hides project docs from GitHub.
- Keep `DATABASE.csv` explicitly tracked even though `pipeline/RAW/` is generally ignored.
- Keep large runtime outputs ignored locally and published through `public/data/runtime-manifest.json` to R2.
- Delete or move root junk/legacy files to a local archive before any commit sweep.
- Do not put R2-public files back into normal GitHub blobs; GitHub should carry manifests and source scripts, not 50-300 MB runtime payloads.

## Largest Files Reviewed

| Path | MB | Recommended home |
| --- | ---: | --- |
| `processed_data/audits/hunt_research_2026_before_numeric_fix_snapshot.json` | 305.064 | `LOCAL_OR_R2_REFERENCE` |
| `processed_data/hunt_research_2026.json` | 249.155 | `CLOUDFLARE_R2_PUBLIC` |
| `processed_data/hunt_research_2026_ladder.json` | 249.155 | `CLOUDFLARE_R2_PUBLIC` |
| `processed_data/audits/research_feeder_database_permit_sync_audit.csv` | 218.428 | `LOCAL_OR_R2_REFERENCE` |
| `processed_data/point_ladder_view.csv` | 133.881 | `CLOUDFLARE_R2_PUBLIC` |
| `HUNT-BUILDER/point_ladder_view1.csv` | 126.32 | `LOCAL_ONLY_IGNORE` |
| `point_ladder_view1.csv` | 126.32 | `LOCAL_ONLY_IGNORE` |
| `processed_data/backups/research_feeder_sync_20260604T064259Z/processed_data/point_ladder_view.csv` | 126.32 | `LOCAL_ONLY_IGNORE` |
| `processed_data/hunt_research_2026_ladder_bonus_max_random.json` | 118.755 | `CLOUDFLARE_R2_PUBLIC` |
| `data/hunt_odds_history.json` | 108.691 | `CLOUDFLARE_R2_PUBLIC` |
| `HUNT-BUILDER/data/hunt_odds_history.json` | 108.691 | `LOCAL_ONLY_IGNORE` |
| `HUNT-BUILDER/pages-dist/data/hunt_odds_history.json` | 108.691 | `LOCAL_ONLY_IGNORE` |
| `HUNT-BUILDER/pages-dist/processed_data/public_contracts/hunt_odds_history.json` | 108.691 | `LOCAL_ONLY_IGNORE` |
| `HUNT-BUILDER/processed_data/public_contracts/hunt_odds_history.json` | 108.691 | `LOCAL_ONLY_IGNORE` |
| `pages-dist/data/hunt_odds_history.json` | 108.691 | `LOCAL_OR_R2_REFERENCE` |
| `processed_data/public_contracts/hunt_odds_history.json` | 108.673 | `CLOUDFLARE_R2_PUBLIC` |
| `pages-dist/processed_data/public_contracts/hunt_odds_history.json` | 108.673 | `LOCAL_OR_R2_REFERENCE` |
| `data/hunt_boundaries_arcgis.json` | 84.029 | `CLOUDFLARE_R2_PUBLIC` |
| `HUNT-BUILDER/data/hunt_boundaries_arcgis.json` | 84.029 | `LOCAL_ONLY_IGNORE` |
| `data/utah/foundation_bundle_2026/utah_boundaries_canonical_2026.geojson` | 83.11 | `CLOUDFLARE_R2_PUBLIC` |
| `data/utah/official_downloads_2026/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson` | 83.11 | `CLOUDFLARE_R2_PUBLIC` |
| `processed_data/statewide_composite_boundaries_2026.geojson` | 83.11 | `CLOUDFLARE_R2_PUBLIC` |
| `processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson` | 83.11 | `CLOUDFLARE_R2_PUBLIC` |
| `HUNT-BUILDER/data/utah/foundation_bundle_2026/utah_boundaries_canonical_2026.geojson` | 83.11 | `LOCAL_ONLY_IGNORE` |
| `HUNT-BUILDER/data/utah/official_downloads_2026/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson` | 83.11 | `LOCAL_ONLY_IGNORE` |
| `HUNT-BUILDER/pages-dist/processed_data/statewide_composite_boundaries_2026.geojson` | 83.11 | `LOCAL_ONLY_IGNORE` |
| `HUNT-BUILDER/pages-dist/processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson` | 83.11 | `LOCAL_ONLY_IGNORE` |
| `HUNT-BUILDER/processed_data/statewide_composite_boundaries_2026.geojson` | 83.11 | `LOCAL_ONLY_IGNORE` |
| `HUNT-BUILDER/processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson` | 83.11 | `LOCAL_ONLY_IGNORE` |
| `pages-dist/processed_data/statewide_composite_boundaries_2026.geojson` | 83.11 | `LOCAL_OR_R2_REFERENCE` |
| `pages-dist/processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson` | 83.11 | `LOCAL_OR_R2_REFERENCE` |
| `processed_data/hunt_truth_from_json.sqlite` | 81.516 | `LOCAL_ONLY_IGNORE` |
| `processed_data/draw_system_coverage_report.csv` | 74.917 | `LOCAL_OR_R2_REFERENCE` |
| `data_truth/draw_results_truth/normalized/draw_results_long.csv` | 74.188 | `GIT_LFS_OR_LOCAL_REFERENCE` |
| `HUNT-BUILDER/data_truth/draw_results_truth/normalized/draw_results_long.csv` | 74.188 | `LOCAL_ONLY_IGNORE` |
| `data/utah/foundation_bundle_2026/utah_hunt_foundation_2026.sqlite` | 69.984 | `CLOUDFLARE_R2_PUBLIC` |
| `HUNT-BUILDER/data/utah/foundation_bundle_2026/utah_hunt_foundation_2026.sqlite` | 69.984 | `LOCAL_ONLY_IGNORE` |
| `data_truth/draw_results_truth/normalized/draw_results_2025_for_2026_candidate_promotion_file_records.csv` | 64.877 | `GIT_LFS_OR_LOCAL_REFERENCE` |
| `HUNT-BUILDER/data_truth/draw_results_truth/normalized/draw_results_2025_for_2026_candidate_promotion_file_records.csv` | 64.877 | `LOCAL_ONLY_IGNORE` |
| `processed_data/backups/permit_allocations_2026_20260523_082859/processed_data/point_ladder_view.csv` | 58.084 | `LOCAL_ONLY_IGNORE` |

## Review Required Examples

- `.gitattributes` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `.gitignore` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `.nojekyll` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `CODEX_TASK_elk_plan_context_integration.txt` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `Git LFS/git-lfs.exe` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `Git LFS/unins000.dat` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `Git LFS/unins000.exe` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `README.txt` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `UPLOAD_README.txt` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/boundary-id-alignment-reconcile-2026-20260508_143652.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/boundary-id-alignment-reconcile-2026-20260508_143854.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/canonical-field-usage-map.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/canonical-rebuild-coverage.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/composite-synthetic-boundary-id-assign-2026-20260508_144635.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/data-drop-audit-report.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/eb3038-ladder-debug-report.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/four-page-canonical-coverage.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/hard-copies-2026.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/hunt-planner-2026.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/hunt-research-2026.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/outfitter-verification-2026.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/permit-allocation-2026-integrity-report.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/runtime-preservation-matrix.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `canonical/shared-2026.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `certs/localhost.crt` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `certs/localhost.key` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `codex-process-report.txt` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `deer_2025_bonus_random_audit.csv` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `deer_2025_bonus_random_summary.csv` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `elk_hunts_clean.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `elk_hunts_grouped.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `elk_plan_codex_expanded_outputs/CODEX_TASK_elk_plan_context_integration.txt` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `engine_payload_manifest.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `generated/audits/master_reconciliation_2026/master_database_2026_reconciliation_changes.csv` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `generated/audits/master_reconciliation_2026/master_database_2026_reconciliation_report.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `generated/pages/hard-copies.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `generated/pages/hunt-planner.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `generated/pages/hunt-research.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `generated/pages/outfitter-verification.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
- `hard-copy/documents.json` -> `GITHUB_REVIEW`: Small miscellaneous file; review before tracking/deploying.
