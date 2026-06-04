# Prediction Engine Feeder Blank Cell Audit

Generated: 2026-06-04

## Scope
- Read-only audit of feeder files used by the current predictive chain: `engine.utah_bonus_predictive.materialize`, `engine.utah_draw_predictive` family/classifier modules, and `engine.utah_predictive_mixed.materialize`.
- No feeder values, truth files, runtime JSON, or prediction math were changed.
- Blank cells were classified by whether they affect identity/routing/quota/prior-year/probability/harvest/lineage behavior.

## Feeder Files Audited

| File | Rows | Columns | Empty Columns | Key Blank Rows | Review/Repair Fields |
| --- | ---: | ---: | ---: | ---: | ---: |
| `data_truth\draw_results_truth\normalized\draw_results_long.csv` | 176753 | 43 | 0 | 0 | 7 |
| `pipeline\RAW\hunt_unit_database\2026\csv\DATABASE.csv` | 1471 | 41 | 0 | 0 | 8 |
| `data_model\runtime_drafts\draw_reality_engine_v2.csv` | 176753 | 24 | 0 | 0 | 7 |
| `processed_data\draw_system_coverage_report.csv` | 204693 | 36 | 0 | 0 | 11 |
| `processed_data\hunt_master_enriched.csv` | 53225 | 81 | 7 | 0 | 17 |
| `processed_data\hunt_unit_reference_linked.csv` | 2997 | 89 | 9 | 0 | 16 |
| `processed_data\ml_draw_predictions_v1.csv` | 27940 | 180 | 12 | 593 | 51 |
| `processed_data\draw_reality_engine_predictive_v2.csv` | 26507 | 131 | 9 | 672 | 34 |
| `processed_data\point_ladder_view.csv` | 91712 | 159 | 15 | 124 | 74 |
| `processed_data\draw_reality_engine.csv` | 36892 | 68 | 7 | 0 | 17 |
| `data_model\harvest_quality\harvest_feature_model_by_hunt_code_2026.csv` | 1411 | 30 | 4 | 0 | 0 |

## Recommendation Summary

- `KEEP_BLANK_FOR_NON_APPLICABLE_FAMILIES`: 6 fields
- `KEEP_BLANK_OR_REMOVE_FROM_FUTURE_SCHEMA`: 25 fields
- `KEEP_BLANK_OR_TARGET_SPECIES_BACKFILL`: 17 fields
- `KEEP_BLANK_UNLESS_SOURCE_ADDED`: 28 fields
- `NO_ACTION`: 145 fields
- `NO_IMMEDIATE_ACTION`: 411 fields
- `REPAIR_REQUIRED`: 11 fields
- `REVIEW_IF_AFFECTS_ACTIVE_ROWS`: 4 fields
- `REVIEW_IF_IMPORTANT`: 8 fields
- `REVIEW_MODEL_KEY_STRATEGY`: 2 fields
- `REVIEW_SOURCE_EXPANSION`: 1 fields
- `REVIEW_TARGETED_BACKFILL`: 202 fields
- `SOURCE_EXPANSION_NEEDED`: 20 fields
- `SPECIES_SOURCE_EXPANSION_NEEDED`: 2 fields

## Most Important Findings

- There are true blank cells in prediction feeders, but many are structural or family-specific. Do not bulk fill blanks.
- The most important actionable category is `REVIEW_TARGETED_BACKFILL`: these are mostly routing, quota, prior-year display, and lineage fields that may be recoverable from existing canonical sources.
- Blank point keys appear mostly on non-point rows such as sportsman, availability, allocation, and pending strategy rows. These need a model-key decision, not loose numeric filling.
- Public-data limitation fields such as applicant retention and new entrants need new source support; they should stay blank until a defensible source exists.
- Harvest/age blanks remain source-limited and should not be inferred.

## High-Signal Field Findings

- `processed_data\draw_reality_engine.csv` / `boundary_id`: 36860/36892 blank (99.913%) - `IDENTITY_GAP` - `REPAIR_REQUIRED`. Identity/year blanks can break row matching.
- `processed_data\point_ladder_view.csv` / `boundary_id`: 90598/91712 blank (98.785%) - `IDENTITY_GAP` - `REPAIR_REQUIRED`. Identity/year blanks can break row matching.
- `processed_data\hunt_unit_reference_linked.csv` / `boundary_id`: 2358/2997 blank (78.679%) - `IDENTITY_GAP` - `REPAIR_REQUIRED`. Identity/year blanks can break row matching.
- `data_truth\draw_results_truth\normalized\draw_results_long.csv` / `boundary_id`: 71864/176753 blank (40.658%) - `IDENTITY_GAP` - `REPAIR_REQUIRED`. Identity/year blanks can break row matching.
- `data_model\runtime_drafts\draw_reality_engine_v2.csv` / `boundary_id`: 7205/176753 blank (4.076%) - `IDENTITY_GAP` - `REPAIR_REQUIRED`. Identity/year blanks can break row matching.
- `processed_data\hunt_master_enriched.csv` / `points`: 1328/53225 blank (2.495%) - `IDENTITY_GAP` - `REPAIR_REQUIRED`. Identity/year blanks can break row matching.
- `pipeline\RAW\hunt_unit_database\2026\csv\DATABASE.csv` / `boundary_id`: 22/1471 blank (1.496%) - `IDENTITY_GAP` - `REPAIR_REQUIRED`. Identity/year blanks can break row matching.
- `processed_data\point_ladder_view.csv` / `point`: 124/91712 blank (0.135%) - `IDENTITY_GAP` - `REPAIR_REQUIRED`. Identity/year blanks can break row matching.
- `processed_data\point_ladder_view.csv` / `points`: 124/91712 blank (0.135%) - `CRITICAL_KEY_BLANK` - `REPAIR_REQUIRED`. Key field has blanks; rows cannot safely join.
- `processed_data\point_ladder_view.csv` / `prediction_year`: 110/91712 blank (0.120%) - `IDENTITY_GAP` - `REPAIR_REQUIRED`. Identity/year blanks can break row matching.
- `processed_data\point_ladder_view.csv` / `source_year`: 110/91712 blank (0.120%) - `IDENTITY_GAP` - `REPAIR_REQUIRED`. Identity/year blanks can break row matching.
- `processed_data\draw_reality_engine_predictive_v2.csv` / `points`: 672/26507 blank (2.535%) - `NON_POINT_ROW_KEY_BLANK` - `REVIEW_MODEL_KEY_STRATEGY`. Mostly non-point/sportsman/availability rows. Do not blindly fill; decide sentinel points or separate non-point contract.
- `processed_data\ml_draw_predictions_v1.csv` / `points`: 593/27940 blank (2.122%) - `NON_POINT_ROW_KEY_BLANK` - `REVIEW_MODEL_KEY_STRATEGY`. Mostly non-point/sportsman/availability rows. Do not blindly fill; decide sentinel points or separate non-point contract.
- `processed_data\point_ladder_view.csv` / `algorithm_status`: 91712/91712 blank (100.000%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\point_ladder_view.csv` / `draw_system_type`: 91712/91712 blank (100.000%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\draw_system_coverage_report.csv` / `probability_model`: 204569/204693 blank (99.939%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\draw_system_coverage_report.csv` / `availability_status`: 204515/204693 blank (99.913%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\hunt_master_enriched.csv` / `draw_model_class`: 53173/53225 blank (99.902%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\hunt_master_enriched.csv` / `probability_model`: 53171/53225 blank (99.899%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\draw_reality_engine.csv` / `draw_model_class`: 36840/36892 blank (99.859%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\draw_reality_engine.csv` / `probability_model`: 36840/36892 blank (99.859%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\hunt_master_enriched.csv` / `availability_status`: 53105/53225 blank (99.775%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\ml_draw_predictions_v1.csv` / `probability_model`: 27816/27940 blank (99.556%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\draw_reality_engine.csv` / `availability_status`: 36722/36892 blank (99.539%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\draw_reality_engine_predictive_v2.csv` / `probability_model`: 26383/26507 blank (99.532%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\ml_draw_predictions_v1.csv` / `availability_status`: 27762/27940 blank (99.363%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\draw_reality_engine_predictive_v2.csv` / `availability_status`: 26329/26507 blank (99.328%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\draw_system_coverage_report.csv` / `data_quality_flags`: 201190/204693 blank (98.289%) - `LINEAGE_GAP` - `REVIEW_TARGETED_BACKFILL`. Lineage blanks weaken explainability even if math can run.
- `processed_data\hunt_unit_reference_linked.csv` / `availability_status`: 2945/2997 blank (98.265%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\hunt_unit_reference_linked.csv` / `draw_model_class`: 2945/2997 blank (98.265%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\hunt_unit_reference_linked.csv` / `probability_model`: 2945/2997 blank (98.265%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\point_ladder_view.csv` / `draw_model_class`: 89996/91712 blank (98.129%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\point_ladder_view.csv` / `probability_model`: 89996/91712 blank (98.129%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\point_ladder_view.csv` / `hunt_name`: 89422/91712 blank (97.503%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\point_ladder_view.csv` / `species`: 89422/91712 blank (97.503%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\point_ladder_view.csv` / `availability_status`: 87816/91712 blank (95.752%) - `ROUTING_GAP` - `REVIEW_TARGETED_BACKFILL`. Routing blanks can push rows into wrong draw family or fallback behavior.
- `processed_data\draw_reality_engine.csv` / `data_quality_grade`: 34764/36892 blank (94.232%) - `LINEAGE_GAP` - `REVIEW_TARGETED_BACKFILL`. Lineage blanks weaken explainability even if math can run.
- `processed_data\draw_reality_engine.csv` / `reason_codes`: 34764/36892 blank (94.232%) - `LINEAGE_GAP` - `REVIEW_TARGETED_BACKFILL`. Lineage blanks weaken explainability even if math can run.
- `processed_data\draw_reality_engine.csv` / `truth_source_file`: 34646/36892 blank (93.912%) - `LINEAGE_GAP` - `REVIEW_TARGETED_BACKFILL`. Lineage blanks weaken explainability even if math can run.
- `processed_data\draw_reality_engine.csv` / `truth_source_status`: 34646/36892 blank (93.912%) - `LINEAGE_GAP` - `REVIEW_TARGETED_BACKFILL`. Lineage blanks weaken explainability even if math can run.
- `processed_data\point_ladder_view.csv` / `display_2025_draw_results`: 85617/91712 blank (93.354%) - `PRIOR_YEAR_PARTIAL_BLANKS` - `REVIEW_TARGETED_BACKFILL`. Could improve ladder fidelity and prior-year baseline where source rows exist.
- `processed_data\point_ladder_view.csv` / `dwr_result_display`: 85617/91712 blank (93.354%) - `PRIOR_YEAR_PARTIAL_BLANKS` - `REVIEW_TARGETED_BACKFILL`. Could improve ladder fidelity and prior-year baseline where source rows exist.
- `processed_data\point_ladder_view.csv` / `success_ratio`: 85617/91712 blank (93.354%) - `PRIOR_YEAR_PARTIAL_BLANKS` - `REVIEW_TARGETED_BACKFILL`. Could improve ladder fidelity and prior-year baseline where source rows exist.
- `processed_data\draw_system_coverage_report.csv` / `reason_codes`: 183333/204693 blank (89.565%) - `LINEAGE_GAP` - `REVIEW_TARGETED_BACKFILL`. Lineage blanks weaken explainability even if math can run.
- `processed_data\hunt_unit_reference_linked.csv` / `data_quality_grade`: 2641/2997 blank (88.121%) - `LINEAGE_GAP` - `REVIEW_TARGETED_BACKFILL`. Lineage blanks weaken explainability even if math can run.
- `processed_data\hunt_unit_reference_linked.csv` / `reason_codes`: 2641/2997 blank (88.121%) - `LINEAGE_GAP` - `REVIEW_TARGETED_BACKFILL`. Lineage blanks weaken explainability even if math can run.
- `processed_data\hunt_unit_reference_linked.csv` / `truth_source_file`: 2641/2997 blank (88.121%) - `LINEAGE_GAP` - `REVIEW_TARGETED_BACKFILL`. Lineage blanks weaken explainability even if math can run.
- `processed_data\hunt_unit_reference_linked.csv` / `truth_source_status`: 2641/2997 blank (88.121%) - `LINEAGE_GAP` - `REVIEW_TARGETED_BACKFILL`. Lineage blanks weaken explainability even if math can run.
- `processed_data\ml_draw_predictions_v1.csv` / `data_quality_flags`: 24437/27940 blank (87.462%) - `LINEAGE_GAP` - `REVIEW_TARGETED_BACKFILL`. Lineage blanks weaken explainability even if math can run.
- `processed_data\draw_system_coverage_report.csv` / `p_draw`: 177468/204693 blank (86.700%) - `PROBABILITY_PARTIAL_BLANKS` - `REVIEW_TARGETED_BACKFILL`. Blank probabilities may be expected for non-modeled rows; verify active modeled rows.

## What Could Be Populated

- Candidate backfills: routing labels (`species`, `hunt_name`, `hunt_class`, `draw_system_type`, `draw_model_class`, `probability_model`), quota/source fields, prior-year display/result fields, and lineage fields where the same hunt-code rows exist in `DATABASE.csv`, reviewed permit tables, `draw_results_long.csv`, or the current canonical Research contract.
- Candidate model-key cleanup: blank `points` rows on non-point draw families should be intentionally represented, for example via a separate non-point contract or a documented sentinel, rather than silently writing `0`.
- Keep blank: special permit overlay columns unless conservation/expo/sportsman overlays are explicitly loaded; true applicant-rollover fields unless a real applicant feed or reviewed proxy exists; harvest-age fields unless annual harvest report evidence exists.

## Suggested Next Repair Pass

1. Filter the CSV to `recommended_action = REVIEW_TARGETED_BACKFILL`.
2. Prioritize routing and quota fields on `processed_data/ml_draw_predictions_v1.csv`, `processed_data/draw_reality_engine_predictive_v2.csv`, and `processed_data/point_ladder_view.csv`.
3. Separately decide how to represent non-point families with blank `points` before writing any value.
4. Leave `SOURCE_EXPANSION_NEEDED` fields blank until a real source exists.

## Output
- Field-level CSV: `processed_data/audits/prediction_engine_feeder_blank_cell_audit.csv`
