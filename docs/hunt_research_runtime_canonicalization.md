# Hunt Research Runtime Canonicalization

## Objective
Make Hunt Research runtime use a single canonical contract as primary:

- `processed_data/hunt_research_2026.json`

while preserving stable behavior with controlled fallback paths.

## What Changed

Primary runtime migration was implemented in:

- `hunt-research.js`

Key runtime behavior now:

1. `hunt-research.js` loads `HUNT_RESEARCH_DATA_SOURCES` first.
2. Canonical JSON rows are parsed from `processed_data/hunt_research_2026.json` (or configured canonical equivalent).
3. Engine/ladder/master/reference in-memory tables are derived from the canonical contract.
4. Legacy parallel CSV feeds are only used if canonical loading fails.

This preserves existing page render logic while changing source priority to the canonical contract.

## Dependency Classification

See:

- `processed_data/audits/hunt_research_runtime_dependency_reduction.csv`

Summary:

- Reduced to fallback-only for core legacy feeds:
  - `draw_reality_engine*`
  - `point_ladder_view`
  - `hunt_master_enriched`
  - `hunt_unit_reference_linked`
- Kept as separate secondary layers (intentionally not merged into core loader):
  - outlook contract feeds used by `assets/js/research-outlook-dashboard.js`
  - management context feed used by the same dashboard

## Remaining Temporary Dependencies

Temporary fallback dependencies retained for runtime safety:

- `processed_data/draw_reality_engine.csv`
- `processed_data/draw_reality_engine_predictive_v2.csv`
- `processed_data/point_ladder_view.csv`
- `processed_data/hunt_master_enriched.csv`
- `processed_data/hunt_unit_reference_linked.csv`

These are no longer primary in `hunt-research.js` and are used only if canonical contract loading fails.

## Validation Notes

Validated in-repo:

- syntax check of updated runtime script
- dependency-path audit artifacts generated
- `git diff --check`

Manual browser verification remains required per deployment environment to confirm live route behavior after publish.
