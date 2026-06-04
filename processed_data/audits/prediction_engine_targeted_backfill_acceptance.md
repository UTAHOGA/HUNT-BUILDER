# Prediction Engine Targeted Backfill Acceptance

Generated: 2026-06-04T09:49:15.152434+00:00
Production readiness: **FAIL**

## Scope

This audit is read-only. It verifies the previous targeted feeder backfill against DATABASE.csv, the repair summary, git history where available, manifests, and Cloudflare R2.

## Blockers

- before_after_unavailable_for_large_ignored_files
- blank_cell_audit_rerun_script_not_found
- processed_data/draw_reality_engine.csv:before_snapshot_unavailable
- processed_data/draw_reality_engine_predictive_v2.csv:before_snapshot_unavailable
- processed_data/hunt_master_enriched.csv:before_snapshot_unavailable
- processed_data/point_ladder_view.csv:before_snapshot_unavailable
- quota_arithmetic_failed
- source_backing_failed

## File Results

### processed_data/point_ladder_view.csv

- Rows: 91712
- Columns: 159
- Summary changed cells: 376260
- Before snapshot available: NO
- Duplicate primary-key rows: 0
- Changed columns: draw_system_type, hunt_name, quota_2026_total, quota_source_file, quota_source_status, quota_source_year, species, truth_source_file, truth_source_status
- Probability range check: PASS
- Permit-allotment arithmetic: PASS
- Permits-2026 arithmetic: PASS

### processed_data/draw_reality_engine_predictive_v2.csv

- Rows: 26507
- Columns: 131
- Summary changed cells: 119319
- Before snapshot available: NO
- Duplicate primary-key rows: 0
- Changed columns: hunt_class, permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, public_permits_2026, quota_2026_total, quota_source_file, quota_source_status, quota_source_year, sex_type, species, weapon
- Probability range check: PASS
- Permit-allotment arithmetic: PASS
- Permits-2026 arithmetic: NOT_APPLICABLE

### processed_data/ml_draw_predictions_v1.csv

- Rows: 27940
- Columns: 180
- Summary changed cells: 114452
- Before snapshot available: YES
- Duplicate primary-key rows: 0
- Changed columns: hunt_class, permit_allotment_2026_nr, permit_allotment_2026_res, permit_allotment_2026_total, public_permits_2026, quota_2026_total, quota_source_file, sex_type, species, weapon
- Probability range check: PASS
- Permit-allotment arithmetic: FAIL
- Permits-2026 arithmetic: NOT_APPLICABLE

### processed_data/hunt_master_enriched.csv

- Rows: 53225
- Columns: 81
- Summary changed cells: 88700
- Before snapshot available: NO
- Duplicate primary-key rows: 14
- Changed columns: truth_source_file, truth_source_status
- Probability range check: PASS
- Permit-allotment arithmetic: PASS
- Permits-2026 arithmetic: PASS

### processed_data/draw_reality_engine.csv

- Rows: 36892
- Columns: 68
- Summary changed cells: 60566
- Before snapshot available: NO
- Duplicate primary-key rows: 0
- Changed columns: truth_source_file, truth_source_status
- Probability range check: PASS
- Permit-allotment arithmetic: PASS
- Permits-2026 arithmetic: PASS

### processed_data/hunt_unit_reference_linked.csv

- Rows: 2997
- Columns: 89
- Summary changed cells: 4524
- Before snapshot available: YES
- Duplicate primary-key rows: 55
- Changed columns: truth_source_file, truth_source_status
- Probability range check: PASS
- Permit-allotment arithmetic: PASS
- Permits-2026 arithmetic: PASS

## R2 Verification

- processed_data/point_ladder_view.csv: PASS (local and R2 match)
- processed_data/draw_reality_engine_predictive_v2.csv: PASS (local and R2 match)
- processed_data/ml_draw_predictions_v1.csv: PASS (local and R2 match)
- processed_data/hunt_master_enriched.csv: PASS (local and R2 match)
- processed_data/draw_reality_engine.csv: PASS (local and R2 match)
- processed_data/hunt_unit_reference_linked.csv: PASS (local and R2 match)

## Validation Commands

- `python -m compileall -q engine scripts tools tests`: PASS (0)
- `python tools/audit_engine_feeders.py --root . --forecast-year 2026 --warn-only`: PASS (0)
- `python -m pytest -q tests/test_engine_feeder_audit_tools.py`: PASS (0)
- `git diff --check`: PASS (0)
- `blank-cell audit rerun`: BLOCKED (None)

## Interpretation

Tracked feeder diffs can be proven at cell level from the backfill parent commit. Large ignored/R2-served feeder files do not have Git before snapshots available, so their safety is reconstructed from the repair summary, current DATABASE.csv equality checks, manifests, and R2/local hashes.
