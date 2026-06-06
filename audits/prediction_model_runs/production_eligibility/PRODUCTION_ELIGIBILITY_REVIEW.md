# Prediction Source Eligibility And Controlled Engine Runs

This is an audit-only gate. It validates the source draw-result years, runs controlled materializations into ignored audit folders, and does not promote production files.

## Summary
- Generated at: `2026-06-06T20:15:29.694157+00:00`
- Target years requested: `2025, 2026`
- Runs attempted: `2`
- Runs completed: `2`
- Direct production promotions applied: `0`
- Overall readiness: `PASS_WITH_PROMOTION_BLOCKERS`

## Run Results

### Target 2025
- Source year: `2024`
- Source status: `PASS`
- Source rows: `37128`
- Source scorable rows: `13394`
- Engine run status: `PASS`
- ML prediction rows: `45562`
- Predictive successor rows: `45562`
- Direct promotion status: `AUDIT_BACKTEST_ELIGIBLE_NOT_LIVE_PRODUCTION_TARGET`
- Notes: target_2025_is_historical_replay_not_current_live_surface

### Target 2026
- Source year: `2025`
- Source status: `PASS`
- Source rows: `75194`
- Source scorable rows: `75194`
- Engine run status: `PASS`
- ML prediction rows: `22807`
- Predictive successor rows: `22807`
- Direct promotion status: `RUN_COMPLETE_NOT_DIRECT_PROMOTION_ELIGIBLE`
- Notes: ml=NOT_DIRECT_PROMOTION_ELIGIBLE:missing_columns=49|missing_families=PREFERENCE_ANTLERLESS_DEER,PREFERENCE_ANTLERLESS_ELK,PREFERENCE_DEDICATED_HUNTER_DEER,PREFERENCE_DOE_PRONGHORN,YOUTH_GENERAL_ANY_BULL_ELK|candidate_has_fewer_rows=5133; predictive_successor=NOT_DIRECT_PROMOTION_ELIGIBLE:missing_columns=50|missing_families=PREFERENCE_DEDICATED_HUNTER_DEER|candidate_has_fewer_rows=3582

## Important Interpretation
- Target 2025 uses the existing no-leakage retrospective 2025 materialized input, so it is valid for audit/backtest review but is not a live production replacement.
- Target 2026 uses a copy of the current 2026 runtime draft materialized input and a copy of runtime draw reality v2, so the controlled run does not mutate production draft files.
- Production promotion remains blocked unless generated outputs match the active production schema and family coverage.

## Outputs
- `audits/prediction_model_runs/production_eligibility/production_eligibility_runs.csv`
- `audits/prediction_model_runs/production_eligibility/production_eligibility_output_profiles.csv`
- `audits/prediction_model_runs/production_eligibility/production_eligibility_summary.json`
- Large row-level outputs: `audits/prediction_model_runs/production_eligibility/engine_outputs/` (ignored/local only)
