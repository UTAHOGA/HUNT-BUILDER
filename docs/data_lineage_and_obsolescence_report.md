# Data Lineage And Obsolescence Report

Generated: 2026-06-01 (America/Denver)  
Scope: repo-local data layers + live runtime dependencies

## Lineage Contract (Current)
1. `DATABASE.csv` is canonical truth for current hunt-code universe, boundary ID alignment, and reviewed permit/allotment fields.
2. Regeneration/sync scripts materialize runtime and research surfaces from truth/reference layers.
3. Browser pages consume a mix of:
   - Vercel-served static JSON/GeoJSON from repo build artifact (`pages-dist`)
   - Cloudflare-hosted large CSV runtime feeds for Research.

## Truth Source (Authoritative)
- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
  - Role: canonical row truth for 2026 hunt universe and permit/allotment values where populated.
  - Policy: should not be overwritten by derived runtime outputs.

## Derived (Regenerated/Recipient Layers)
- `processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/MASTER.xlsx`
  - Recipient/export workbook derived from `DATABASE.csv`.
- `generated/audits/master_reconciliation_2026/master_database_2026_reconciliation_report.json`
- `generated/audits/master_reconciliation_2026/master_database_2026_reconciliation_changes.csv`
  - Evidence outputs proving DATABASE->MASTER reconciliation.
- `processed_data/public_contracts/hunt_application_outlook.json`
- `processed_data/public_contracts/hunt_predictions.json`
- `processed_data/public_contracts/hunt_units.geojson`
- `processed_data/public_contracts/source_snapshots.json`
- `data/public_contract_summary.json`
  - Public contract outputs generated from runtime/derived sources.

## Runtime-Active (Website Facing)
### Builder / Verify / hard-copy local-static runtime
- `data/hunt-master-canonical-2026-foundation.json`
- `data/hunt-master-canonical-2026-source-of-truth.json`
- `data/hunt_boundaries.geojson`
- `data/hunt-boundaries-lite.geojson`
- `processed_data/display-boundary-index-2026.json`
- `processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson`
- `data/conservation-permit-areas.json`
- `data/conservation-permit-hunt-table-2025-27.json`
- `processed_data/public_contracts/outfitters-public.json`
- `public/hard-copy/data/documents.json`
- `public/hard-copy/DISPLAY DATA/*`

### Research Cloudflare-first runtime
- `https://json.uoga.workers.dev/processed_data/draw_reality_engine_v2.csv`
- `https://json.uoga.workers.dev/processed_data/point_ladder_view.csv`
- `https://json.uoga.workers.dev/processed_data/hunt_master_enriched.csv`
- `https://json.uoga.workers.dev/processed_data/hunt_unit_reference_linked.csv`

## Display-Only / Reference Layers
- `processed_data/draw_reality_view.csv` (legacy display/reference surface)
- `processed_data/harvest_master.csv`
- `processed_data/harvest_quality_features_all_years_by_hunt_code.csv`
- `processed_data/harvest_age_features_by_hunt_code_all_years.csv`
- `processed_data/harvest_age_features_by_hunt_code_latest.csv`
- `data_model/runtime_drafts/draw_reality_engine_v2.csv`
- `data_model/harvest_quality/draw_reality_engine_predictive_with_harvest_features.csv`

These are useful for analysis and regeneration pipelines, but not currently the primary live page contract.

## Obsolete / Likely Retirement Candidates
- `verify.htmlm` route behavior (legacy typo alias; browser treats as download-like path).
- Duplicate alias pages where primary routes exist:
  - `hunt-research.html` (primary is `research.html`)
  - `vetting.html` (primary is `verify.html`)
- Bytecode/runtime artifacts:
  - `scripts/__pycache__/`
  - `engine/**/__pycache__/`

## Review / Risk Flags (Not Retire-Ready Yet)
1. `processed_data/composite_hunt_unit_mapping_2026.geojson`
   - Live 200 but parse failure indicates LFS-pointer-like payload in production response path.
2. Local missing-but-referenced fallback files:
   - `processed_data/hunt_master_enriched.csv`
   - `processed_data/hunt_unit_reference_linked.csv`
   - `processed_data/draw_reality_engine.csv`
   - Research is still operational because Cloudflare-first sources are healthy.
3. hard-copy fallback URL noise:
   - page works from `public/hard-copy/data/documents.json` but still requests missing fallback document manifests.

## Candidate Retirement Queue (Planned, Not Executed)
1. Remove/redirect `verify.htmlm`.
2. Reduce duplicate fallback chains on hard-copy page to only verified sources.
3. Prune dead fallback entries in Research config once local mirror strategy is finalized.
4. Purge committed `__pycache__` artifacts.

## Summary
- **Truth:** `DATABASE.csv`
- **Recipient/derived export:** `MASTER.xlsx`
- **Live runtime:** Vercel static + Cloudflare research CSVs
- **Display/reference:** draw/harvest auxiliary layers
- **Obsolete/dead-path pressure:** alias pages, typo route, stale fallback references, cache artifacts
