# hunt_research_2026.json Numeric Defect Audit

## Scope
- Audited priority numeric fields at row level against canonical feeder hierarchy.
- Compared pre-fix snapshot to rebuilt contract and traced changed values to source row keys.

## Priority Fields Audited
- `odds_2025_actual`
- `display_odds_pct`
- `p_draw_mean`
- `p_draw_p10`
- `p_draw_p90`
- `guaranteed_at_2026`
- `permits_2026_total`
- `average_harvest_age`
- `current_age_3yr_average`

## Repair Summary
- Fields repaired: `odds_2025_actual`
- Total changed or unresolved audit rows: 61387
- Remaining review-required rows: 0

## Root Causes Observed
- Wrong feeder path selection risk for 2025 history fallback (legacy draw file lacked 2025 rows).
- Success-ratio parsing risk (`1 in X` text) could produce bad percent if parsed as generic numeric text.
- Source hierarchy precedence required explicit planner-first behavior for `current_age_3yr_average`.

## Actions Applied
- Switched draw-history feeder selection to canonical candidates including normalized draw truth with 2025 coverage.
- Added dedicated `1 in X` success-ratio-to-percent parser to avoid scaling/parse defects.
- Set planner source precedence for `current_age_3yr_average` before non-planner fallbacks.
- Rebuilt `processed_data/hunt_research_2026.json` and reran row-level verification.

## Trust Status
- Priority numeric fields are now numerically trustworthy against the defined source hierarchy.