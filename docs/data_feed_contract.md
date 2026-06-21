# Data Feed Contract

This project uses a public-data MVP contract now, with an upgrade path to true application-level feeds later.

## Required raw tables

- `applications_raw.csv`
- `applicants_raw.csv`
- `groups_raw.csv`
- `points_raw.csv`
- `quotas_raw.csv`
- `draw_results_raw.csv`
- `hunt_metadata_raw.csv`
- `harvest_quality_raw.csv`

## Privacy

- Do not store names, addresses, phone numbers, email addresses, birthdates, SSNs, or raw customer IDs.
- Use hashed IDs only.

## Source levels

- `fixture`: synthetic test data only.
- `public_historical_proxy`: public DWR reports and metadata.
- `application_level_feed`: true predictive feed with choice, group, residency, youth, and eligibility fields.

## Compatibility rule

The existing UI still consumes processed CSVs keyed by `(hunt_code, residency, points)`. New modeled fields must be additive.

## 2026 RAC Truth-Source Promotion

- When a normalized 2026 RAC truth-source table exists for permit counts, that table is authoritative for the 2026 permit overlay.
- Current-year RAC allotment values are the canonical available-permit counts for draw-odds modeling when a direct `hunt_code` row exists. These values are active quota inputs, not display-only reference fields.
- Runtime files carry these additive current-year allotment fields:
  - `permit_allotment_2026_res`
  - `permit_allotment_2026_nr`
  - `permit_allotment_2026_total`
  - `permit_allotment_2026_source`
  - `permit_allotment_2026_source_file`
  - `permit_allotment_2026_status`
- If RAC provides resident/nonresident values, all three allotment fields are populated. If RAC provides only a total, only `permit_allotment_2026_total` is populated and the resident/nonresident allotment fields remain blank.
- If no direct RAC allotment row exists, the allotment fields may fall back to existing `permits_2026_res`, `permits_2026_nr`, and `permits_2026_total` values, marked with `permit_allotment_2026_source = FALLBACK_EXISTING_2026_PERMITS`.
- Truth-source promotion is a separate data step from probability math changes. When current-year RAC allotments exist, they feed the existing quota allocation and draw-odds machinery; the formulas stay the same, but the current-year quota input changes to the RAC value.
- The promotion flow is:
  - normalized RAC truth table
  - audit against runtime surfaces
  - promote corrected values into the runtime CSVs
  - rerun audits until required families show zero mismatches
- Runtime promotion currently updates:
  - `processed_data/draw_reality_engine.csv`
  - `processed_data/point_ladder_view.csv`
  - `processed_data/hunt_master_enriched.csv`
  - `processed_data/hunt_unit_reference_linked.csv`

## Mixed Predictive Engine Contract

- `mixed_predictive_v1.0.0` is an additive prediction layer over the existing runtime files.
- The mixed engine uses prior-year DWR draw behavior as the anchor, then applies official current-year quota, applicant rollover / point-bank movement, and a small harvest-quality demand adjustment.
- The runtime should treat each draw design as a separate engine family, not as one blended probability model with a different label.
- `draw_model_class` and `probability_model` should point to the family-specific engine path:
  - `MODELED_PREFERENCE` -> preference engine
  - `MODELED_BONUS` -> max/weighted split engine
  - `MODELED_SPORTSMAN_DRAW` -> random sportsman engine
  - `MODELED_AVAILABILITY` -> O.T.C. / allotment engine
  - `MODELED_ALLOCATION` -> permit-allotment / O.T.C. engine
- Default component weights are:
  - `prior_year_behavior_weight = 0.60`
  - `quota_change_weight = 0.20`
  - `applicant_rollover_weight = 0.15`
  - `harvest_quality_demand_weight = 0.05`
- The harvest quality component must not exceed `0.10` without an explicit model version bump and regression coverage.
- Official 2026 RAC/DATABASE allotment fields drive `quota_2026_total`, `quota_2026_max_pool`, and `quota_2026_random_pool` when available.
- Those quota fields are derived from the official permit allotment for the lane, then split into max and random pools inside the max/weighted split engine.
- `quota_source_status = official` means the row is using the current-year official allotment source.
- Prior-year random-pool successes are historical draw results only; they must not be copied into 2026 point-specific odds.
- MAX POOL status text is descriptive only and must not create a guaranteed probability unless the modeled 2026 applicant/permit state supports it.
- Materialized mixed-model outputs remain keyed by `hunt_code`, `residency`, and `points`.

## Harvest Features In Prediction

- Harvest data may contribute quality and demand-pressure features only.
- Harvest data may not directly create or overwrite `p_draw`, `p_draw_mean`, `p_random_mean`, `p_max_pool_mean`, `p_preference_draw`, `p_bonus_pool`, 2026 quota fields, or 2026 public draw permit allotments.
- Harvest report permit counts are not 2026 public draw quota.
- Harvest feature rows may populate:
  - `harvest_quality_index`
  - `demand_pressure_signal`
  - `demand_pressure_category`
  - `point_creep_quality_adjustment`
  - `harvest_feature_match_method`
  - `harvest_feature_source_years`
  - `harvest_feature_reason_codes`
- The mixed engine may apply only a capped demand-pressure adjustment derived from those fields.

## Special Permit Overlay Guardrails

- Expo, Conservation, Sportsman, CWMU, landowner, mitigation, private, and boundary overlay permits are not public draw odds quota.
- Special permit overlays may be used for total-permit reconciliation, source metadata, explanatory display, and audit traceability.
- Special permit overlays must not increase `p_draw_mean`.
- Special permit overlays must not enter max-point-pool or random-pool quota.
- Sportsman rows use their own sportsman strategy and are not folded into max/weighted split or preference public draw pools.

## Promotion Metadata

- The runtime overlay may add or populate these metadata fields:
  - `permit_source`
  - `quota_source`
  - `truth_source_file`
  - `truth_source_status`
  - `data_quality_grade`
  - `reason_codes`
  - `hunt_category`
  - `draw_model_class`
  - `probability_model`
  - `availability_status`
  - `new_this_year`
- The canonical permit-overlay source label for this pass is `2026_RAC_TRUTH_SOURCE`.
- `reason_codes` append with pipe delimiters rather than replacing useful existing values.

## Total-Only And Dash Rules

- Dashes or blanks in prior-year permit columns are treated as zero for audit delta calculations only.
- Dash normalization must not be used to fabricate a prior-year runtime row.
- If a truth source provides only total permits, do not invent a resident/nonresident split.
- Private-lands-only antlerless elk is availability-only unless a source explicitly provides split-by-residency draw mechanics.

## O.T.C. / Allotment Runtime Handling

- O.T.C. / allotment rows must not be forced into normal draw-probability semantics.
- Private-lands-only antlerless elk rows should use:
  - `hunt_category = PRIVATE_LANDS_ONLY_ANTLERLESS_ELK`
  - `draw_model_class = AVAILABILITY_ONLY`
  - `probability_model = NONE`
- O.T.C. / allotment rows may still appear in runtime surfaces for lookup continuity, but they must not receive invented draw probabilities.
- `MODELED_AVAILABILITY` rows are O.T.C. / allotment rows, not draw odds. They must keep `p_draw`, `p_draw_pct`, `p_bonus_pool`, `p_random_pool`, and `p_preference_draw` null.
- O.T.C. / allotment rows may use:
  - `p_availability`
  - `availability_pct`
  - `availability_status`
  - `permit_availability_type`
  - `unit_status`
  - `rule_status`
  - `reason_codes`
- Mountain lion / cougar uses O.T.C. / allotment semantics rather than draw odds.
- Bear harvest-objective and pursuit-only rows use O.T.C. / allotment semantics rather than draw odds.

## Out-Of-Scope Non-Target Handling

- `OUT_OF_SCOPE_NON_TARGET` rows are preserved in coverage and audit artifacts for traceability.
- `OUT_OF_SCOPE_NON_TARGET` rows must keep `p_draw`, `p_draw_pct`, `p_preference_draw`, `p_bonus_pool`, and `p_random_pool` null.
- Normal user-facing Hunt Research prediction output should hide `OUT_OF_SCOPE_NON_TARGET` rows unless audit/debug mode is explicitly enabled.
- When shown in audit/debug mode, the UI should label them as `Out of scope / not a target prediction category`.
- Target big-game, turkey, bear, and mountain lion / cougar rows must not be pushed into `OUT_OF_SCOPE_NON_TARGET` merely because they are pending, non-draw, or missing a modeled probability.

## Control-Unit Overlays

- Control-unit overlays are tracked separately from permit truth rows.
- An unresolved control-unit overlay must not be auto-converted into a fabricated permit row.
- The current unresolved overlay item is `Henry Mtns` for the 2026 antlerless elk control-unit list; it remains unresolved until a matching 2026 permit truth row is surfaced.

## Fixture rebuild pipeline

- The canonical rebuild entrypoint is `engine.utah.materialize`.
- Exact command shape:

  ```bash
  python -m engine.utah.materialize --input-dir data/utah/fixtures --output-dir processed_data --draw-year 2026 --iterations 10000 --seed 2026 --model-version hybrid_ml_v1.0.0 --rule-version utah_draw_model_v1.0.0 --quota-source fixture --applicant-pool-source fixture
  ```

- It reads the synthetic tables in `data/utah/fixtures/`.
- It writes the compatibility CSVs directly into the chosen output directory as:
  - `draw_reality_engine.csv`
  - `point_ladder_view.csv`
  - `hunt_master_enriched.csv`
  - `hunt_unit_reference_linked.csv`
- Rebuild outputs should be labeled by source level. For the fixture pipeline, use `fixture` or `fixture_rebuild` rather than implying a true predictive feed.
