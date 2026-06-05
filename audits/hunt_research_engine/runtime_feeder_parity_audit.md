# Runtime Feeder Parity Audit

Read-only classification of local feeder CSVs against runtime manifests and R2 URLs.

## Summary

- Result: `PASS_WITH_RESTORE_AND_MANIFEST_RECOMMENDATIONS`.
- Files checked: `32`.
- Restore/demote recommendations: `4`.
- R2 remote failures: `0`.
- Manifest size drift files: `5`.
- Worktree dirty during audit: `True` (`40` entries).

## Classification Counts

| Classification | Count |
| --- | ---: |
| LOCAL_ENGINE_FEEDER_AUTHORITATIVE | 9 |
| LOCAL_MODEL_FEEDER_AUTHORITATIVE | 3 |
| LOCAL_REFERENCE_UNCLASSIFIED | 1 |
| LOCAL_RUNTIME_DRAFT_AUTHORITATIVE | 6 |
| LOCAL_TRUTH_AUTHORITATIVE | 3 |
| R2_CANONICAL_LOCAL_CACHE_OK | 3 |
| R2_CANONICAL_MANIFEST_SIZE_DRIFT | 1 |
| REFERENCE_ONLY_RETIRE_FROM_RUNTIME | 1 |
| RESTORE_LOCAL_STUB_FROM_R2_AND_UPDATE_MANIFEST | 4 |
| REVIEW_OR_RETIRE_CANDIDATE | 1 |

## Files

| Path | Local Rows | Local Size | R2 Status | Classification | Recommendation |
| --- | ---: | ---: | --- | --- | --- |
| `data_model/quality/promoted_draw_sources.csv` | 204 | 76852 |  | LOCAL_ENGINE_FEEDER_AUTHORITATIVE | Engine contract references this generated local feeder. |
| `data_model/quality/promoted_quality_sources.csv` | 253 | 100536 |  | LOCAL_ENGINE_FEEDER_AUTHORITATIVE | Engine contract references this generated local feeder. |
| `data_model/quality/raw_pdf_inventory_audit.csv` | 1286 | 544937 |  | LOCAL_ENGINE_FEEDER_AUTHORITATIVE | Engine contract references this generated local feeder. |
| `processed_data/draw_system_coverage_report.csv` | 204693 | 78555708 |  | LOCAL_ENGINE_FEEDER_AUTHORITATIVE | Engine contract references this generated local feeder. |
| `processed_data/harvest-metrics-2024-bg-report.csv` | 647 | 17212 |  | LOCAL_ENGINE_FEEDER_AUTHORITATIVE | Engine contract references this generated local feeder. |
| `processed_data/harvest-metrics-2025-prelim.csv` | 1092 | 30015 |  | LOCAL_ENGINE_FEEDER_AUTHORITATIVE | Engine contract references this generated local feeder. |
| `processed_data/historical_trend_2025.csv` | 47950 | 5599579 |  | LOCAL_ENGINE_FEEDER_AUTHORITATIVE | Engine contract references this generated local feeder. |
| `processed_data/projected_bonus_draw_2026_simulated.csv` | 46992 | 18106562 |  | LOCAL_ENGINE_FEEDER_AUTHORITATIVE | Engine contract references this generated local feeder. |
| `processed_data/recommended_permits_2026.csv` | 928 | 215471 |  | LOCAL_ENGINE_FEEDER_AUTHORITATIVE | Engine contract references this generated local feeder. |
| `data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv` | 1471 | 462884 |  | LOCAL_MODEL_FEEDER_AUTHORITATIVE | Harvest model feeder is a local generated model input/output, not R2 runtime canonical. |
| `data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv` | 5570 | 2087901 |  | LOCAL_MODEL_FEEDER_AUTHORITATIVE | Harvest model feeder is a local generated model input/output, not R2 runtime canonical. |
| `data_model/harvest_quality/harvest_results_all_years_long.csv` | 68657 | 24881298 |  | LOCAL_MODEL_FEEDER_AUTHORITATIVE | Harvest model feeder is a local generated model input/output, not R2 runtime canonical. |
| `processed_data/hunt-master-canonical-2026-source-of-truth.csv` | 1471 | 1315638 | LOCAL_PATH | LOCAL_REFERENCE_UNCLASSIFIED | Local file exists but is not clearly runtime-canonical from manifest or contract. |
| `data_model/runtime_drafts/mixed_predictive_engine_2026.audit.csv` | 27822 | 13731420 |  | LOCAL_RUNTIME_DRAFT_AUTHORITATIVE | Runtime draft output is local authoritative until promoted/published. |
| `data_model/runtime_drafts/mixed_predictive_engine_2026.materialized.csv` | 26389 | 42943037 |  | LOCAL_RUNTIME_DRAFT_AUTHORITATIVE | Runtime draft output is local authoritative until promoted/published. |
| `data_model/runtime_drafts/mixed_predictive_engine_2026.predictions.csv` | 27822 | 47860018 |  | LOCAL_RUNTIME_DRAFT_AUTHORITATIVE | Runtime draft output is local authoritative until promoted/published. |
| `data_model/runtime_drafts/predictive_bonus_engine_2026.audit.csv` | 756 | 169464 |  | LOCAL_RUNTIME_DRAFT_AUTHORITATIVE | Runtime draft output is local authoritative until promoted/published. |
| `data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv` | 23835 | 18989572 |  | LOCAL_RUNTIME_DRAFT_AUTHORITATIVE | Runtime draft output is local authoritative until promoted/published. |
| `data_model/runtime_drafts/predictive_bonus_engine_2026.predictions.csv` | 23835 | 18585491 |  | LOCAL_RUNTIME_DRAFT_AUTHORITATIVE | Runtime draft output is local authoritative until promoted/published. |
| `data_truth/draw_results_truth/normalized/draw_results_long.csv` | 176753 | 77791622 |  | LOCAL_TRUTH_AUTHORITATIVE | Normalized truth table is local/repo authoritative and should not be replaced from R2. |
| `data_truth/harvest_results_truth/normalized/harvest_quality_features_all_years_by_hunt_code.csv` | 5151 | 1926517 |  | LOCAL_TRUTH_AUTHORITATIVE | Normalized truth table is local/repo authoritative and should not be replaced from R2. |
| `data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv` | 68657 | 24881298 |  | LOCAL_TRUTH_AUTHORITATIVE | Normalized truth table is local/repo authoritative and should not be replaced from R2. |
| `processed_data/draw_reality_engine_v2.csv` | 176753 | 44863034 | 200 | R2_CANONICAL_LOCAL_CACHE_OK | Manifest marks R2 as live canonical runtime source; local file is a cache/reference copy. |
| `processed_data/draw_reality_view.csv` | 53176 | 14072342 | 200 | R2_CANONICAL_LOCAL_CACHE_OK | Manifest marks R2 as live canonical runtime source; local file is a cache/reference copy. |
| `processed_data/ml_draw_predictions_v1.csv` | 27940 | 48351537 | 200 | R2_CANONICAL_LOCAL_CACHE_OK | Manifest marks R2 as live canonical runtime source; local file is a cache/reference copy. |
| `processed_data/draw_reality_engine_predictive_v2.csv` | 26389 | 42944164 | 200 | R2_CANONICAL_MANIFEST_SIZE_DRIFT | R2 is live, but manifest size differs from the served object. Update manifest sizes before publish closeout. |
| `processed_data/draw_reality_engine_backup_before_2024_import.csv` | 141516 | 52620090 |  | REFERENCE_ONLY_RETIRE_FROM_RUNTIME | Reference/backup file only; should not feed runtime. |
| `processed_data/draw_reality_engine.csv` | 2 | 1712 | 200 | RESTORE_LOCAL_STUB_FROM_R2_AND_UPDATE_MANIFEST | R2 is live and local CSV is a tiny/stub copy; manifest size differs from R2. Restore local if local tools consume it and update runtime manifest sizes. |
| `processed_data/hunt_master_enriched.csv` | 2 | 635 | 200 | RESTORE_LOCAL_STUB_FROM_R2_AND_UPDATE_MANIFEST | R2 is live and local CSV is a tiny/stub copy; manifest size differs from R2. Restore local if local tools consume it and update runtime manifest sizes. |
| `processed_data/hunt_unit_reference_linked.csv` | 2 | 1128 | 200 | RESTORE_LOCAL_STUB_FROM_R2_AND_UPDATE_MANIFEST | R2 is live and local CSV is a tiny/stub copy; manifest size differs from R2. Restore local if local tools consume it and update runtime manifest sizes. |
| `processed_data/point_ladder_view.csv` | 2 | 612 | 200 | RESTORE_LOCAL_STUB_FROM_R2_AND_UPDATE_MANIFEST | R2 is live and local CSV is a tiny/stub copy; manifest size differs from R2. Restore local if local tools consume it and update runtime manifest sizes. |
| `processed_data/hunt_master_enriched_2026_draw_subset.csv` |  | 0 |  | REVIEW_OR_RETIRE_CANDIDATE | Manifest says this file is review-required and not currently served live. |

## Dirty Worktree Sample

- ` M WORK_LOG.md`
- ` M data_truth/comparison_outputs/validation/harvest_draw_same_year_alignment_2026_summary.json`
- ` M data_truth/harvest_results_truth/validation/harvest_year_by_year_hardening_2026.csv`
- ` M data_truth/harvest_results_truth/validation/harvest_year_by_year_hardening_2026_historical_only_codes.csv`
- ` M data_truth/harvest_results_truth/validation/harvest_year_by_year_hardening_2026_missing_codes.csv`
- ` M data_truth/harvest_results_truth/validation/harvest_year_by_year_hardening_2026_summary.json`
- ` M engine/utah_draw_predictive/__init__.py`
- ` D pipeline/scripts/ingest/extraction/24_bg-draw-results.pdf`
- ` D "pipeline/scripts/ingest/extraction/python extract_elk.py"`
- ` M processed_data/hunt_unit_reference_linked.csv`
- ` M tests/utah_quality/test_harvest_year_by_year_hardening_2026.py`
- `?? "INGEST FOLDER/"`
- `?? audits/hunt_research_engine/runtime_feeder_parity_audit.csv`
- `?? audits/hunt_research_engine/runtime_feeder_parity_audit.json`
- `?? audits/hunt_research_engine/runtime_feeder_parity_audit.md`
- `?? "engine/CLEAN INPUTS/"`
- `?? engine/utah_draw_predictive/materialize.py`
- `?? ingest-pdf-to-hunt-engine.js`
- `?? pipeline/INGEST/`
- `?? pipeline/scripts/extraction/`
- `?? pipeline/scripts/pdf_extract.py`
- `?? pipeline/scripts/preference_engine.py`
- `?? pipeline/scripts/preference_engine_v3.py`
- `?? processed_data/harvest_draw_same_year_alignment_2026.md`
- `?? processed_data/harvest_report_2026.before_20260605_105251.csv`
- `?? processed_data/harvest_report_2026.before_20260605_105302.csv`
- `?? processed_data/harvest_report_2026.csv`
- `?? processed_data/harvest_year_by_year_hardening_2026.md`
- `?? scripts/2021/`
- `?? scripts/2022/`
- `?? scripts/2023/`
- `?? scripts/2024/`
- `?? scripts/2025/`
- `?? scripts/2026/`
- `?? "scripts/INGEST FOLDER/"`
- `?? scripts/preference_engine.py`
- `?? scripts/run_preference_ingest_batch.py`
- `?? tests/utah_draw_predictive/test_materialize_module_exists.py`
- `?? tools/hunt_research_engine/audit_runtime_feeder_parity.py`
- `?? tools/ingest_dropzone_all_engines.ps1`
