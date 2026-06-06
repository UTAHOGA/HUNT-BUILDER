# Production Prediction Assembly Plan

## Scope
This is a no-promotion assembly plan. It explains how the current production prediction/runtime files are assembled from separate model lanes and runtime merge layers.

## Production Files Not Modified
- `processed_data/ml_draw_predictions_v1.csv`
- `processed_data/draw_reality_engine_predictive_v2.csv`
- `processed_data/point_ladder_view.csv`
- `processed_data/hunt_research_2026.json`
- `processed_data/hunt_research_2026_ladder.json`
- `data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv`
- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- `data_truth/draw_results_truth/normalized/draw_results_long.csv`

## Main Finding
Current production is not a single model output. It is an assembled runtime product: bonus engine rows plus preference rows, Sportsman/random-only rows, youth-reviewed rows, allocation/reference overlays, compact point-ladder display, and Hunt Research JSON display metadata.

## Lanes Already Present In Current Production
- `BONUS_ENGINE_OUTPUT`
- `PREFERENCE_ENGINE_OUTPUT`
- `SPORTSMAN_RANDOM_ONLY`
- `ALLOCATION_OR_REFERENCE_ONLY`
- `PUBLIC_RUNTIME_DISPLAY_METADATA`
- `POINT_LADDER_DISPLAY`
- `HUNT_RESEARCH_JSON_MERGE`

## Lanes Missing Or Incomplete In Controlled Rebuilds
- `PREFERENCE_ENGINE_OUTPUT`
- `YOUTH_REVIEW_REQUIRED / YOUTH_CONFIRMED_LANE`
- `ALLOCATION_OR_REFERENCE_ONLY`
- `PUBLIC_RUNTIME_DISPLAY_METADATA`
- `POINT_LADDER_DISPLAY`
- `HUNT_RESEARCH_JSON_MERGE`

## Runtime Decoration / Merge Required
The following production files require runtime decoration or merge after model math:
- `processed_data/ml_draw_predictions_v1.csv`: model lanes plus lineage, display, source, and demand/quality decorations.
- `processed_data/draw_reality_engine_predictive_v2.csv`: modeled predictive rows plus runtime/reference decoration.
- `processed_data/point_ladder_view.csv`: compact point ladder generated from draw truth/reference grain; not a direct model output.
- `processed_data/hunt_research_2026.json`: website/research merge output.
- `processed_data/hunt_research_2026_ladder.json`: website ladder/research merge output.

## Active Builder Contributions
These are the active production assembly builders to understand before touching runtime files. This plan documents them only; it does not execute the rebuild sequence.
- `engine.utah_bonus_predictive.materialize`
  - Sequence role: prediction math.
  - Contributes: model outputs.
  - Primary outputs: ml_draw_predictions_v1.csv; draw_reality_engine_predictive_v2.csv; lane-specific prediction CSVs.
  - Lane ownership: BONUS_ENGINE_OUTPUT plus wired special-case model appenders; does not by itself create the full website/runtime contract.
  - Required inputs: validated historical draw truth; current hunt/permit/allotment reference; runtime draft materialized feeder inputs.
  - Blocker if missing: No production-equivalent model rows can be staged.
- `scripts/sync_online_runtime_from_predictive.py`
  - Sequence role: runtime sync.
  - Contributes: runtime display fields; allocation/reference rows; Hunt Research JSON decoration inputs.
  - Primary outputs: decorated runtime CSV surfaces consumed by downstream builders.
  - Lane ownership: PUBLIC_RUNTIME_DISPLAY_METADATA and ALLOCATION_OR_REFERENCE_ONLY merge layer.
  - Required inputs: model outputs plus reference, source-lineage, and current hunt metadata.
  - Blocker if missing: Model math remains too narrow for production display and website handoff.
- `scripts/build-unified-point-ladder-runtime.py`
  - Sequence role: point ladder merge.
  - Contributes: POINT_LADDER_DISPLAY.
  - Primary outputs: processed_data/point_ladder_view.csv.
  - Lane ownership: compact public/runtime ladder; not the broader 91k Hunt Research surface.
  - Required inputs: draw truth, point rows, residency/points grain, and runtime reference fields.
  - Blocker if missing: Hunt Research ladder display cannot prove compact grain/row parity.
- `scripts/build-hunt-research-2026-contract.py`
  - Sequence role: Hunt Research JSON contract.
  - Contributes: HUNT_RESEARCH_JSON_MERGE; PUBLIC_RUNTIME_DISPLAY_METADATA; Hunt Research JSON decoration.
  - Primary outputs: processed_data/hunt_research_2026.json; processed_data/hunt_research_2026_ladder.json.
  - Lane ownership: website-facing research contract merge, including model outputs, ladder/reference rows, lineage, and display metadata.
  - Required inputs: decorated model/runtime CSVs, compact ladder, reference overlays, and source-lineage fields.
  - Blocker if missing: Large Hunt Research JSON cannot be rebuilt from validated staged runtime inputs.
- `scripts/rebuild-runtime-hunt-master-and-split.py`
  - Sequence role: final runtime master/split.
  - Contributes: final runtime master/split; R2-ready split/index packaging.
  - Primary outputs: processed_data/hunt_research_2026_summary.json; processed_data/hunt_research_2026_split/.
  - Lane ownership: final public/runtime packaging after contract validation; upload/publish remains a separate gated action.
  - Required inputs: validated Hunt Research contract JSON and runtime master files.
  - Blocker if missing: Website/runtime split files cannot be regenerated or prepared for R2 validation.

## Safe Candidates For Later Promotion
- No full controlled folder is safe for direct promotion today.
- Individual lane outputs may become promotion candidates only after a staging assembly proves row, family, schema, and runtime-display parity.
- The 2027-from-2026 released candidate remains audit-only for production odds because it lacks scorable probability/applicant/drawn fields.

## Must Remain Audit-Only
- `audits/prediction_model_runs/2026_from_2025_truth_pdf_draw_results/` until full assembly parity passes.
- `audits/prediction_model_runs/2027_from_2026_dwr_released_candidate/` for production odds.
- Any broader 91k Hunt Research surface as a replacement for compact `point_ladder_view.csv`; it may belong in Hunt Research display metadata, not compact ladder replacement.

## Exact Rebuild Sequence If Blockers Are Cleared
Do not execute this sequence until blockers are cleared, staging paths are explicit, and production/runtime files are protected by a reviewed promotion gate.
1. `python -m engine.utah_bonus_predictive.materialize --output-dir <staging_dir> --forecast-year 2026 --history-years 2025`
2. `python scripts/sync_online_runtime_from_predictive.py`
3. `python scripts/build-unified-point-ladder-runtime.py`
4. `python scripts/build-hunt-research-2026-contract.py`
5. `python scripts/rebuild-runtime-hunt-master-and-split.py`
6. `python tools/prediction_accuracy_backtest/validate_and_run_prediction_models.py --root .`
7. `python tools/prediction_accuracy_backtest/diagnose_production_equivalence.py --root .`
8. `python tools/prediction_accuracy_backtest/build_production_assembly_plan.py --root .`
9. `git diff --check`
10. `python tools/git_size_guard.py --warn-only`

## Stop Conditions
- Stop if any lane remains unclassified.
- Stop if youth source mechanics are not proven.
- Stop if staging output is missing production columns, families, or row coverage.
- Stop if compact `point_ladder_view.csv` would be replaced by a broader research surface without grain proof.
- Stop if any production file, `DATABASE.csv`, `draw_results_long.csv`, website/R2/manifest file, or large row-level output would be modified during planning.

## Output Files
- `production_assembly_lane_plan.csv`
- `production_assembly_required_inputs.csv`
- `production_assembly_blockers.csv`
- `PRODUCTION_ASSEMBLY_PLAN.md`
