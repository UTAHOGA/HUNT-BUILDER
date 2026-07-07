# Draw-Line-Aware Prediction Scoring Design

This is the operating reference for full-engine year-to-year prediction scoring.
It defines how official draw-result truth, prediction outputs, hunt-code
crosswalks, draw-line logic, scoreability decisions, and metrics fit together.

Use this document when restarting the scoring work from scratch.

Primary scorer:

`tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.py`

Canonical workflow:

1. Generate frozen predictions from the engine for one source/target year pair.
2. Load official scorable truth rows for the following draw year.
3. Build the actual PDF-derived ladder.
4. Identify draw-line position inside that ladder.
5. Join predictions to actual ladder rows using structural keys plus points.
6. Score only real, possible, official ladder rows.
7. Treat extra generated prediction rows as diagnostics, not accuracy misses.

## Current Locked Audit

The corrected 2018 to 2019 full-engine-equivalent audit output was regenerated
after fixing youth draw-design normalization.

Prediction file:

`audits/prediction_blind_year_to_year/full_engine_equivalent_2018_to_2019/run_2018_to_2019/family_predictions.csv`

Scoring output:

`audits/prediction_blind_year_to_year/full_engine_equivalent_2018_to_2019/draw_line_aware_unblinded_diagnostics_2018_for_2019`

Actual-ladder result:

| Metric | Value |
|---|---:|
| `actual_ladder_rows` | 3,392 |
| `actual_ladder_possible_rows` | 3,381 |
| `actual_ladder_scored_rows` | 3,381 |
| `actual_ladder_possible_missing_prediction_rows` | 0 |
| `actual_ladder_possible_missing_prediction_probability_rows` | 0 |
| `actual_ladder_possible_score_coverage_rate` | 1.0000000000 |
| `all_possible_rows_scored` | true |
| `actual_ladder_mae` | 0.1311056371 |
| `actual_ladder_rmse` | 0.2528597640 |
| `actual_ladder_bias` | 0.0364752406 |
| `actual_ladder_applicant_weighted_mae` | 0.1009002915 |

Important: the top-level prediction-centric `scored_rows` value is not the
primary accuracy denominator for this audit. Use `actual_ladder_*` metrics for
official accuracy.

## Run Commands

Generate one full-engine prediction year:

```powershell
python -m engine.utah_draw_predictive.run_all_families `
  --source-year 2018 `
  --target-year 2019 `
  --audit-dir audits\prediction_blind_year_to_year\full_engine_equivalent_2018_to_2019\run_2018_to_2019
```

Score one year pair with row-level diagnostics:

```powershell
python tools\prediction_accuracy_backtest\score_full_engine_draw_line_aware.py `
  --prediction-file audits\prediction_blind_year_to_year\full_engine_equivalent_2018_to_2019\run_2018_to_2019\family_predictions.csv `
  --truth-file C:\Users\tyler\HUNT-BUILDER-BLIND\draw_results_truth\scoring_truth\2018_for_2019\truth_scorable_safe.csv `
  --output-dir audits\prediction_blind_year_to_year\full_engine_equivalent_2018_to_2019\draw_line_aware_unblinded_diagnostics_2018_for_2019 `
  --source-year 2018 `
  --target-year 2019
```

Score one year pair in blind-safe aggregate mode:

```powershell
python tools\prediction_accuracy_backtest\score_full_engine_draw_line_aware.py `
  --prediction-file audits\prediction_blind_year_to_year\full_engine_equivalent_2018_to_2019\run_2018_to_2019\family_predictions.csv `
  --truth-file C:\Users\tyler\HUNT-BUILDER-BLIND\draw_results_truth\scoring_truth\2018_for_2019\truth_scorable_safe.csv `
  --output-dir audits\prediction_blind_year_to_year\full_engine_equivalent_2018_to_2019\draw_line_aware_blind_summary_2018_for_2019 `
  --source-year 2018 `
  --target-year 2019 `
  --summary-only `
  --require-all-possible-scored
```

`--summary-only` writes only aggregate summary JSON. Use it when row-level truth
diagnostics should remain opaque.

`--require-all-possible-scored` exits nonzero unless every possible actual
ladder row has a usable prediction probability.

## Output Files

The scorer writes:

| File | Purpose |
|---|---|
| `draw_line_aware_prediction_vs_actual_summary.json` | Aggregate run metadata, coverage, and metrics. |
| `draw_line_aware_actual_ladder_scoring_rows.csv` | Actual-ladder-centric scoring rows. This is the official accuracy surface. |
| `draw_line_aware_prediction_vs_actual_rowlevel.csv` | Prediction-centric join diagnostics. Useful for generated-row cleanup. |
| `draw_line_aware_prediction_vs_actual_by_family.csv` | Prediction-centric family summary. |
| `draw_line_aware_extra_prediction_diagnostics.csv` | Predictions that do not correspond to real PDF ladder rows. |

If `--summary-only` is used, only the summary JSON is written.

## Core Principle

The official PDF truth creates the actual ladder. The supplemental mixed-line
logic identifies where the draw line falls inside that official ladder. The
scorer evaluates real PDF ladder rows only.

Do not count generated prediction points outside the PDF ladder as official
accuracy misses. They are cleanup diagnostics.

## Structural Join Keys

The structural ladder key is:

`draw_design + draw_pool + hunt_code + residency`

Point-level scoring adds:

`points`

The exact point-level key is:

`draw_design + draw_pool + hunt_code + residency + points`

The preferred conceptual alignment key is:

`draw_design + hunt_code + residency + points`

But the implemented scorer also includes `draw_pool`, because youth reserves,
sportsman rows, black bear rows, dedicated hunter rows, and adult/general pools
can share similar design/hunt-code shapes while meaning different applicant
pools.

## Draw Pool Rules

`draw_pool` must be a real source-classified pool. It cannot be `standard`.

The scorer normalizes placeholder `STANDARD` to empty, then derives or preserves
real pools from prediction family, draw system, and source fields.

Examples of valid pools:

| Pool | Meaning |
|---|---|
| `adult_general_deer` | Adult general-season buck deer preference pool. |
| `dedicated_hunter` | Dedicated hunter deer preference pool. |
| `general_season_antlerless_deer` | Adult/general antlerless deer preference pool. |
| `general_season_antlerless_elk` | Adult/general antlerless elk preference pool. |
| `general_season_doe_pronghorn` | Adult/general doe pronghorn preference pool. |
| `youth_general_deer` | Youth general deer reserve pool. |
| `youth_antlerless_deer` | Youth antlerless deer reserve pool. |
| `youth_antlerless_elk` | Youth antlerless elk reserve pool. |
| `youth_doe_pronghorn` | Youth doe pronghorn reserve pool. |
| `youth_general_any_bull_elk` | Youth general any-bull elk set-aside pool. |
| `max_weighted_split` | Bonus/max-weighted split applicant pool. |
| `sportsman_random_only` | Sportsman random-only pool. |
| `reference_only` | Non-probability reference rows. |
| `preference_point` | Point-purchase/reference rows, not draw probability. |

Important normalization:

`black_bear`, `BLACK_BEAR`, and bear draw labels normalize to
`max_weighted_split` for scoring because the PDF ladder for bear bonus rows is
classified as `MAX_WEIGHTED_SPLIT` / `max_weighted_split`.

## Draw Design Rules

`draw_design` describes the draw algorithm or official draw system, not just the
species.

Common scoring designs:

| Draw Design | Meaning |
|---|---|
| `PREFERENCE_GENERAL_SEASON_BUCK_DEER` | General-season buck deer preference draw. |
| `PREFERENCE_DEDICATED_HUNTER_DEER` | Dedicated hunter deer preference draw. |
| `PREFERENCE_ANTLERLESS_DEER` | Antlerless deer preference draw. |
| `PREFERENCE_ANTLERLESS_ELK` | Antlerless elk preference draw. |
| `PREFERENCE_DOE_PRONGHORN` | Doe pronghorn preference draw. |
| `MAX_WEIGHTED_SPLIT` | Bonus/max point plus weighted/random split draw. |
| `SPORTSMAN_RANDOM_ONLY` | Sportsman random-only draw. |
| `YOUTH_GENERAL_ANY_BULL_ELK` | Youth any-bull elk set-aside/random draw. |
| `BONUS_TURKEY` | Turkey bonus or point-reference surface, often non-scorable depending source row. |
| `REFERENCE_ONLY` | Reference/allocation rows, not accuracy rows. |

Prediction family-to-design mapping:

| Prediction Family | Draw Design |
|---|---|
| `preference_general_deer` | `PREFERENCE_GENERAL_SEASON_BUCK_DEER` |
| `dedicated_hunter` | `PREFERENCE_DEDICATED_HUNTER_DEER` |
| `preference_antlerless_deer` | `PREFERENCE_ANTLERLESS_DEER` |
| `preference_antlerless_elk` | `PREFERENCE_ANTLERLESS_ELK` |
| `preference_doe_pronghorn` | `PREFERENCE_DOE_PRONGHORN` |
| `bonus_le_big_game` | `MAX_WEIGHTED_SPLIT` |
| `bonus_ple_big_game` | `MAX_WEIGHTED_SPLIT` |
| `bonus_oil_big_game` | `MAX_WEIGHTED_SPLIT` |
| `bonus_bear` | `MAX_WEIGHTED_SPLIT` |
| `sportsman` | `SPORTSMAN_RANDOM_ONLY` |

Special youth rule:

`family = youth_draw` does not automatically mean
`YOUTH_GENERAL_ANY_BULL_ELK`.

Youth prediction rows must preserve their explicit `draw_system_type` when it is
present. This is required so youth reserve rows join correctly:

| Youth Pool | Correct Design |
|---|---|
| `youth_general_deer` | `PREFERENCE_GENERAL_SEASON_BUCK_DEER` |
| `youth_antlerless_elk` | `PREFERENCE_ANTLERLESS_ELK` |
| `youth_antlerless_deer` | `PREFERENCE_ANTLERLESS_DEER` |
| `youth_doe_pronghorn` | `PREFERENCE_DOE_PRONGHORN` |
| `youth_general_any_bull_elk` | `YOUTH_GENERAL_ANY_BULL_ELK` |

The 2018 to 2019 audit initially missed 477 possible rows because all
`family=youth_draw` predictions were being forced to
`YOUTH_GENERAL_ANY_BULL_ELK`. The fix was to preserve `draw_system_type` for
youth reserve rows.

## Historical Hunt-Code Crosswalks

Historical draw-result rows may use hunt codes that later recode to current
codes. Those are not draw-pool or draw-design mismatches.

The scorer loads normalized crosswalk authority from:

| File | Use |
|---|---|
| `data_truth/crosswalk_truth/normalized/current_to_historical_hunt_code_crosswalk_2026.csv` | All-species current-to-historical mappings. |
| `data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv` | Bear-specific BR recodes. |
| `data_truth/crosswalk_truth/normalized/hunt_code_crosswalk_authority_2020_2026.csv` | Broad authority file for all-species code continuity and source-backed actions. |

The scorer also loads all CSV files from:

`data_truth/crosswalk_truth/normalized`

Additional files can be supplied with:

`--hunt-code-crosswalk-file`

Additional directories can be supplied with:

`--hunt-code-crosswalk-dir`

Accepted high-confidence statuses include:

- `HISTORICAL_CODE_RECODED_TO_CURRENT`
- `HISTORICAL_CODE_RECODED_BECAUSE_CODE_REUSED`
- `EXACT_CODE_CURRENT`
- exact or promoted exact history records from the all-species crosswalk
- source-backed authority actions that are not exclusion/reference-only actions

Bear examples:

- `BR7008 -> BR7022`
- `BR7108 -> BR7127`
- `BR7208 -> BR7239`

The scorer records original and resolved codes in output columns:

- `actual_original_hunt_code`
- `actual_hunt_code_crosswalk_status`
- `prediction_original_hunt_code`
- `prediction_hunt_code_crosswalk_status`
- `original_hunt_code_predicted`
- `hunt_code_crosswalk_status_predicted`

## Residency And Metric Scope

Truth rows can be scoped as:

| Residency | Meaning |
|---|---|
| `Resident` | Resident-specific actual ladder row. |
| `Nonresident` | Nonresident-specific actual ladder row. |
| `All` | Combined residency scope where the source publishes one real applicant ladder instead of separate resident and nonresident scoring lanes. |

Do not use the word `total` by itself as a draw classifier. In Utah DWR source
material it can mean several different things:

- a Hunt Planner Total Lane
- a bottom-of-table PDF total
- a permit-level summary row
- a permit allotment field such as `permits_2026_total`
- an extraction artifact

The scorer uses explicit context instead: draw design, draw pool, hunt code,
residency scope, record type, and whether the source row is a real point ladder.

Permit allotment columns are not residency-scoring lanes. For example, in
`pipeline/RAW/hunt_unit_database/2026/xlsx/2026_bull_elk_all.xlsx`:

| Pattern | Meaning |
|---|---|
| `permits_2026_res` + `permits_2026_nr` + `permits_2026_total` | Resident and nonresident quota allocation exists; total is the sum/check value. |
| `permits_2026_total` only | One total permit/cap number exists; resident/nonresident allocation does not apply in that workbook row. |
| all three permit fields blank | This workbook row does not provide a permit allotment number. |

Do not convert `permits_2026_total` into `residency = All`. `All` is reserved
for actual draw-result probability rows where the source publishes one combined
applicant ladder. A quota total is not an applicant ladder and cannot produce
accuracy by itself.

Identification rule for total-only permit allotments:

`permits_res blank + permits_nr blank + permits_total populated`

That rule must be applied only inside permit inventory/allotment sources such as
guidebook, Hunt Planner, RAC, or database workbook rows. It should not be applied
to actual draw-result odds tables without checking the row type, because draw
results also contain bottom-of-table totals and other summary values.

Draw family is supporting context, not the identifier. Total-only allotments are
often found on preference-point or draw-only hunts, but the scorer should not
classify them from `Preference` alone. The source fields define the allotment
shape; the actual draw-result PDF defines whether a probability row exists.

PDF draw-result rows often report permit totals in two different ways:

1. Total permits are the sum of resident and nonresident permit rows.
2. Total permits are a single total-pool allotment where resident/nonresident
   does not have a scoring role.

When a draw-result probability row is explicitly scoped as combined-residency,
the scorer treats the actual row as `All`. It does not create fake
resident/nonresident actual rows.

Prediction rows may be:

- explicit `Resident`
- explicit `Nonresident`
- explicit `All`
- blank residency but `metric_scope = total`
- blank residency on max-weighted rows, which are treated as `All`

If actual is `All` and predictions are split into Resident and Nonresident lanes,
the scorer builds an audit-only composite prediction from the existing predicted
probabilities. It does not invent actual probability.

Composite formula:

`combined_prediction = sum(predicted_probability_lane * actual_applicants_lane) / sum(actual_applicants_lane)`

If both lane applicant weights are zero, the scorer uses a simple average of
available prediction lanes.

If only one lane exists, the scorer may use that single lane and labels the
probability field as:

`single_resident_lane_for_total_scope`

or:

`single_nonresident_lane_for_total_scope`

## Actual Ladder Construction

The actual ladder is built only from official, scorable truth rows.

Allowed point record types:

- `point_level_draw_result`
- `point_row`
- `sportsman_total`
- `sportsman_total_draw_result`

Non-probability rows are excluded from the actual scoring ladder.

Excluded draw designs:

- `REFERENCE_ONLY`

Excluded draw pools:

- `reference_only`
- `lifetime_general_deer`
- `preference_point`

Rows with `scoring_allowed = false` are excluded.

`TOTAL` as a point value is only a literal source label. It is not a draw pool,
not a draw design, and not a sportsman point bucket. The scorer must not use
`TOTAL` as sportsman scoring semantics.

Sportsman is strictly random and has no bonus/preference point key. When an
official sportsman source row uses a blank, `TOTAL`, or similar summary label,
the scorer drops that label for sportsman joining and scoring.

Sportsman permits are resident-only for scoring. Nonresidents cannot apply or
draw for those permits, so nonresident sportsman rows with `N/A`, blank values,
or zero applicants are irrelevant to coverage and accuracy.

## Draw-Line Algorithm

For each actual structural ladder:

`draw_design + draw_pool + hunt_code + residency`

the scorer sorts numeric point rows high to low.

Definitions:

| Field | Algorithm |
|---|---|
| `top_applicant_point` | Highest point level with actual eligible applicants > 0. |
| `lowest_guaranteed_stack_point` | Lowest point in the top contiguous stack where all applicants at each point level drew. |
| `mixed_cutoff_point` | First point level, scanning high to low, where actual unsuccessful applicants > 0. |

A row is treated as guaranteed when:

`actual_eligible_applicants > 0`

and:

`actual_unsuccessful <= 0`

or:

`actual_probability >= 1.0`

Mixed row meaning:

The mixed cutoff is the row where some applicants drew and some did not. It is
not a full applicant rollover. Only unsuccessful applicants at the mixed row roll
forward to the next year, subject to retention/reapply behavior. This is a
strong predictive indicator, not an across-the-board certainty.

Preference draw note:

The max/weighted split draw uses the mixed cutoff to separate max/guaranteed
behavior from weighted/random behavior. General preference draws do not always
use that same max/weighted line concept. For preference rows, zero-applicant
rows above the active ladder are structural empty rungs, not successful applicant
rows.

## Point Relation Labels

`point_relation_to_draw_line` classifies each point row relative to the actual
PDF ladder.

| Relation | Meaning |
|---|---|
| `above_draw_line_guaranteed_stack` | Point is in the guaranteed stack above the mixed cutoff. |
| `at_mixed_draw_line` | Point is the mixed-success cutoff row. |
| `below_draw_line_random_pool` | Point is below the cutoff or in the non-guaranteed pool. |
| `all_applicant_points_guaranteed_or_no_mixed_draw_line` | No mixed-success row exists for the ladder. |
| `sportsman_random_permit_row` | Sportsman random-only row; no bonus/preference points apply. |
| `non_point_permit_summary_row` | Valid non-sportsman permit-level row with no point ladder. |
| `zero_applicant_structural_row` | Real PDF ladder row with zero actual applicants. |
| `outside_pdf_ladder_above_top_applicant_point` | Generated prediction row above the official applicant ladder. |
| `outside_pdf_ladder_below_min_point` | Generated prediction row below the official ladder. |
| `point_level_not_in_pdf_ladder_gap` | Generated prediction row inside a point gap not shown in the official PDF ladder. |
| `point_not_numeric` | Prediction point value cannot be interpreted as numeric and is not a recognized total row. |
| `no_structural_ladder` | Prediction row has no matching actual structural ladder. |

## Scoreability Status

`scoreability_status` explains whether an actual ladder row can enter accuracy.

| Status | Meaning |
|---|---|
| `scoreable` | Real actual probability, nonzero actual applicants, and matching prediction probability. |
| `possible_missing_prediction` | Real actual probability and nonzero applicants, but no matching prediction row. |
| `possible_missing_prediction_probability` | Matching prediction row exists but probability is blank/unusable. |
| `impossible_zero_actual_applicants` | Actual applicants are zero, so there is no applicant outcome to score. |
| `impossible_missing_actual_probability` | Actual probability is missing. |
| `diagnostic_extra_prediction_not_actual_ladder_row` | Prediction row is not an official actual ladder row. |

The goal for a complete engine coverage run is:

`actual_ladder_possible_missing_prediction_rows = 0`

and:

`actual_ladder_possible_missing_prediction_probability_rows = 0`

## Scoring Decisions

`scoring_decision` is the row-level denominator decision.

| Decision | Accuracy Effect |
|---|---|
| `score_probability` | Included in MAE, RMSE, bias, and coverage metrics. |
| `missing_prediction_for_scoreable_actual_ladder_row` | Not scored; counted as possible coverage gap. |
| `do_not_score_missing_prediction_probability` | Not scored; counted as possible prediction probability gap. |
| `do_not_score_zero_actual_applicants` | Excluded as impossible to score. |
| `do_not_score_missing_actual_probability` | Excluded as impossible to score. |
| `do_not_score_outside_pdf_ladder` | Prediction-centric diagnostic only. |
| `do_not_score_no_structural_ladder` | Prediction-centric diagnostic only. |

## Prediction Probability Fields

Prediction probabilities are read in priority order:

1. `p_draw_mean`
2. `p_draw`
3. `p_preference_draw`
4. `p_sportsman_draw`
5. `p_availability`

Values are bounded to `[0, 1]`.

If the value appears to be a percentage, it is divided by 100. This happens when
the raw value contains `%`, the field name includes `pct`/`percent`, or the
numeric value is greater than `1.0`.

## Actual Probability Fields

Actual probability is selected from residency/scope-aware fields first.

For `Resident`:

- `resident_p_draw`
- `resident_p_draw_percent`

For `Nonresident`:

- `nonresident_p_draw`
- `nonresident_p_draw_percent`

For `All`:

- `total_p_draw`
- `total_p_draw_percent`

Fallback fields:

- `actual_p`
- `p_draw`
- `p_draw_percent`
- `total_p_draw`
- `total_p_draw_percent`

The scorer does not fabricate actual probability from permit totals.

## Error Formulas

For each scored row:

`error = predicted_probability - actual_probability`

`absolute_error = abs(error)`

Metrics:

| Metric | Formula |
|---|---|
| `mae` | `mean(abs(error))` |
| `rmse` | `sqrt(mean(error^2))` |
| `bias` | `mean(error)` |
| `median_absolute_error` | median of `abs(error)` |
| `within_1pp_rate` | share of scored rows where `abs(error) <= 0.01` |
| `within_5pp_rate` | share of scored rows where `abs(error) <= 0.05` |
| `within_10pp_rate` | share of scored rows where `abs(error) <= 0.10` |
| `applicant_weighted_mae` | `sum(abs(error) * actual_eligible_applicants) / sum(actual_eligible_applicants)` |

Coverage:

`actual_ladder_possible_score_coverage_rate = actual_ladder_scored_rows / actual_ladder_possible_rows`

Completeness flag:

`all_possible_rows_scored = actual_ladder_possible_missing_prediction_rows == 0 and actual_ladder_possible_missing_prediction_probability_rows == 0`

## Actual-Ladder Metrics Vs Prediction-Centric Metrics

The scorer has two useful views.

Actual-ladder view:

- starts from official PDF/scorable truth rows
- decides which rows are possible
- determines whether each possible row has prediction coverage
- is the official accuracy denominator

Use these fields:

- `actual_ladder_rows`
- `actual_ladder_possible_rows`
- `actual_ladder_scored_rows`
- `actual_ladder_possible_score_coverage_rate`
- `actual_ladder_mae`
- `actual_ladder_rmse`
- `actual_ladder_bias`
- `actual_ladder_applicant_weighted_mae`

Prediction-centric view:

- starts from every generated prediction row
- classifies whether each prediction row lands on a PDF ladder point
- identifies extra generated rows and structural cleanup issues
- is not the official accuracy denominator

Top-level `scored_rows`, `not_scored_rows`, `structural_join_counts`, and
`point_relation_counts` are prediction-centric. They can look strange when a
large engine file emits many generated rows outside the official PDF ladder.

## Non-Scorable Rows

Never fabricate accuracy from:

- permit totals without official actual probability
- quota-only rows
- allocation-only rows
- reference-only rows
- guidebook rows
- CWMU contact-operator rows
- CWMU contact-operator rows with blank permit numbers
- guaranteed/lifetime/general guaranteed-tag rows
- point-purchase rows
- preference-point reference rows
- sportsman/admin rows that are not random-only draw probability rows
- OTC or availability-only rows unless they are explicitly modeled as
  availability rather than draw probability

These rows can still appear as diagnostics when they explain coverage or source
classification, but they do not enter MAE/RMSE.

## Youth Reserve Rules

Youth rows are separate source-classified draw pools, not adult preference rows
with a youth label.

Youth reserve pools:

- `youth_general_deer`
- `youth_antlerless_elk`
- `youth_antlerless_deer`
- `youth_doe_pronghorn`

Youth set-aside/random pool:

- `youth_general_any_bull_elk`

Youth reserve preference behavior:

- youth reserve rows can have their own PDF ladder rows
- up to 20 percent of permits may be reserved for youth, depending source rules
- unsuccessful youth-reserve applicants can roll into the main draw probability
- adult/general rows and youth reserve rows must remain separate scoring pools

Scoring implication:

A youth actual ladder row must join to a youth prediction row with the same
design/pool/code/scope/point. It must not be silently satisfied by an adult
general pool prediction row.

## Max/Weighted Split Rules

For max/weighted split designs:

- PDF ladder defines actual point rows
- mixed-line logic identifies the mixed success cutoff
- applicants above the cutoff can be treated as guaranteed stack when all drew
- applicants at the mixed row are partially successful
- unsuccessful applicants at the mixed row are the rollover signal
- below-cutoff rows are weighted/random pool behavior

The draw line is not invented by the prediction engine. The prediction engine
may help further define and forecast the line, but scoring anchors to the
official PDF ladder.

## Preference Draw Rules

For preference draws:

- high points generally draw before lower points
- actual ladder rows come from official PDF point rows
- zero-applicant rows are structural empty rungs
- zero-applicant rows do not consume permits
- zero-applicant rows do not roll forward
- zero-applicant rows are not scored for accuracy

Preference rows can still have a mixed-success line when the official ladder
shows partial success at a point level, but that does not make every preference
draw a max/weighted split model.

## Sportsman Rules

Sportsman rows are `SPORTSMAN_RANDOM_ONLY`.

They are valid as sportsman draw-result rows only when the source row is an
official random-only probability row. Sportsman rows have no point ladder, so
the scoring join does not use `points`, `TOTAL`, or any synthetic point marker.

Sportsman rows should not be joined to preference or max/weighted ladders.

Sportsman Buck Deer codes must be year-scoped. The 2017 Sportsman Odds Report
prints the deer row as `DB1045`, while later canonical sportsman truth uses
`DB0007`. `DB1045` is also a real limited-entry Fillmore/Oak Creek deer code in
other contexts, so `DB0007 -> DB1045` must never be a global alias. It is valid
only for the reviewed 2017 sportsman scoring context.

## Extra Prediction Diagnostics

The engine may generate more prediction rows than the PDF contains. These rows
are useful for cleanup, but they are not official misses.

Common examples:

- generated point levels above the top actual applicant point
- generated point levels below the lowest PDF ladder row
- generated point levels inside a gap that the PDF did not publish
- unsupported/reference/admin rows
- adult pool rows when scoring youth rows, or vice versa

Those rows go to:

`draw_line_aware_extra_prediction_diagnostics.csv`

with:

`scoreability_status = diagnostic_extra_prediction_not_actual_ladder_row`

## Required Output Columns

Per prediction row, the scorer writes:

- `structural_join_status`
- `point_relation_to_draw_line`
- `mixed_cutoff_point`
- `lowest_guaranteed_stack_point`
- `top_applicant_point`
- `scoring_decision`

The actual-ladder output also includes:

- `scoreability_status`
- `family_actual`
- `family_predicted`
- `actual_probability`
- `predicted_probability`
- `prediction_probability_field`
- `error`
- `absolute_error`
- hunt-code crosswalk status columns

## Debugging Checklist

If not all possible rows are scored:

1. Check `actual_ladder_possible_missing_prediction_rows`.
2. Check `actual_ladder_possible_missing_prediction_probability_rows`.
3. Open `draw_line_aware_actual_ladder_scoring_rows.csv`.
4. Filter `scoreability_status = possible_missing_prediction`.
5. Group by `draw_design_key + draw_pool_key`.
6. Group by `hunt_code + actual_original_hunt_code`.
7. Check whether prediction rows exist for the same hunt code under another
   pool/design.
8. If prediction rows exist under adult/general pools but actual rows are youth,
   fix engine youth emission or scorer youth design/pool normalization.
9. If prediction rows exist under historical/current code aliases, fix crosswalk
   resolution.
10. If prediction rows exist but probability is blank, fix prediction probability
    field emission.

Known solved issue:

The 2018 to 2019 audit had 477 missing rows after initial normalization. They
were:

- 327 `PREFERENCE_ANTLERLESS_ELK` / `youth_antlerless_elk`
- 78 `PREFERENCE_ANTLERLESS_DEER` / `youth_antlerless_deer`
- 72 `PREFERENCE_DOE_PRONGHORN` / `youth_doe_pronghorn`

The predictions existed, but the scorer forced all `family=youth_draw` rows to
`YOUTH_GENERAL_ANY_BULL_ELK`. Preserving explicit youth `draw_system_type`
fixed coverage to 100 percent.

## File Hygiene

Generated audit CSV/JSON outputs can be large. Do not stage or commit large
generated audit files.

Commit candidates are source/docs only:

- `tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.py`
- `docs/draw_line_aware_scoring_metrics.md`

Keep large runtime outputs under `audits/` for local review or move them to the
appropriate external storage path if they need to be preserved.
