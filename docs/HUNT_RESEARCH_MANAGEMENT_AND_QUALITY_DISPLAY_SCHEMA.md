# Hunt Research Management and Quality Display Schema

Status: active display contract for the 2026 Hunt Research management and hunt-quality release.

## Purpose

This contract defines how official Utah DWR management objectives, current management statistics, annual harvest evidence, reported three-year harvest evidence, and the U.O.G.A. Hunt Quality Profile may be displayed together without changing draw odds, permits, quotas, or prediction truth.

The DWR management measure controls the unit of comparison. A value may be compared with an objective only when the current value and objective use the same species, management unit, measure, time basis, and unit.

## Source authority

1. Exact hunt identity comes from `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`.
2. Current management objectives and current comparison values come from the retained 227-row DWR Hunt Planner management-unit snapshot.
3. Management-plan PDFs provide the governing framework, definition, period, and supporting unit-plan reference.
4. Annual harvest and hunter-experience values come from normalized official DWR harvest reports.
5. Annual harvested age and DWR-reported three-year harvested age remain separate fields with their own source lineage.
6. A statewide framework is not promoted into a hunt-unit target unless DWR identifies the selected unit strategy or exact unit objective.

`boundary_id` is never an identity key for management, harvest, age, or profile data.

## Species-specific management display

| Species | Primary management measure | Current comparison | Composite applicability |
|---|---|---|---|
| Elk | Harvested bull age objective for bull hunts; population objective for other associated hunts | DWR Hunt Planner current three-year age or current population estimate | Only when the selected measure applies to the hunt and both values are parseable |
| Moose | Harvested bull age objective | DWR Hunt Planner current three-year age | Yes when the exact code, measure, and harvest evidence pass the gate |
| Pronghorn | Harvested buck age objective for buck hunts; population objective for doe hunts | DWR Hunt Planner current three-year age or current population estimate | Only when the selected measure applies to the hunt |
| Mule deer | Bucks-per-100-does objective for buck hunts; population objective for antlerless hunts | DWR Hunt Planner current three-year bucks-per-100-does or population estimate | Only with the same-unit, same-unit-of-measure comparison |
| Bison | Population objective | Current population estimate | Yes when the exact values are unambiguous and the evidence gate passes |
| Bighorn sheep | Population objective | Current population estimate | Yes when the exact values are unambiguous and the evidence gate passes |
| Mountain goat | Population objective | Current population estimate | Yes when the exact values are unambiguous and the evidence gate passes |
| Black bear | Three-year strategy framework: adult male age-5 share, female harvest share, and DNA population growth | Requires the unit's selected Light, Moderate, or Liberal strategy plus matching observed values | No score until the selected unit strategy and current matching measures are verified |
| Wild turkey | Statewide habitat, hunter-participation, and event-participation objectives | Statewide program progress, when published | No unit composite from statewide program objectives |
| Cougar | Current open-season program authority and qualitative management goal | No current quantified management-plan target | No management-objective composite |

## Raw fields shown to visitors

The Research page should show these fields when evidence exists:

- DWR management measure name, target, current value, unit, status, scope, source, retrieval date, and plan reference.
- Most recent verified annual harvested age and its reported hunt year.
- DWR-reported three-year harvested age and its reported hunt year.
- DWR Hunt Planner current three-year age when available; this is not substituted for harvested-age history.
- Most recent harvest success, hunter satisfaction, average days hunted, harvest total, and hunters afield.
- Exact-code match status, source file/page or web locator, and evidence confidence.

## Objective status

`BELOW_OBJECTIVE`, `MEETING_OBJECTIVE`, and `ABOVE_OBJECTIVE` are assigned only when target and current values are parseable and comparable. Complex multi-area text, conflicting DWR records, missing current values, or non-unit statewide frameworks remain explicit context-only statuses.

Above-objective does not automatically mean better management. It means only that the current value is numerically above the published target range.

## U.O.G.A. Hunt Quality Profile

The profile is a display-only synthesis, not a DWR score and not a draw-probability input. It is comparable only within the same species, sex/permit type, and hunt class.

For rows that meet the evidence gate, the candidate composite uses fixed weights with no missing-component reweighting:

- 40% biological quality signal: current DWR management measure divided by the lower objective threshold, capped at 100.
- 25% three-year average harvest success.
- 20% three-year average hunter satisfaction, normalized from 0-5 to 0-100.
- 15% three-year average effort efficiency, where zero days is 100 and 12 or more days is 0.

The biological component is a hunter-quality signal. The separately displayed DWR objective status remains the authoritative description of whether the current value is below, within, or above the target.

## Composite publication gate

A composite score is published only when all conditions are true:

1. The management source is an exact DWR Hunt Planner hunt-code reference with compatible species identity.
2. The selected measure applies to the hunt's species and sex/type.
3. Target and current values are parseable and use the same unit.
4. No relevant DWR value-conflict flag is present.
5. Harvest history is an exact hunt-code match with data-quality grade A or B.
6. The retained history includes hunt year 2025.
7. Three-year success, satisfaction, effort, and hunters-afield values are all present.
8. Three-year average hunters afield is at least 10.

Rows that fail any condition retain the verified raw fields and a reason-coded unavailable score. They are never reweighted from a partial component set.

## Guardrails

- Management and harvest evidence may not create or overwrite `p_draw`, draw probabilities, permits, quotas, or applicant counts.
- Harvest-report permit counts are not current permit truth.
- Statewide plan statements may be displayed as statewide context but not as exact unit objectives.
- Black bear strategy bands require the selected unit strategy before comparison.
- Wild turkey statewide program objectives do not create hunt-unit scores.
- Cougar is labeled as a current open-season program, not as a current management plan.
- The composite is labeled `U.O.G.A. Hunt Quality Score`, carries its version/confidence, and is withheld when the publication gate fails.
