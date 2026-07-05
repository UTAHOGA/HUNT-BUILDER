# 2026 Big Game Hunt Code Reconciliation

This checks hunt-code presence from the corrected 2026 Big Game Application Guidebook against the core source/database/runtime reference surfaces.

## Result

- Guidebook hunt codes checked: `728`
- Required-surface blocker count: `2`
- Codes present in every required surface: `726`
- Optional predictive rows missing: `0`
- Extra DATABASE codes not in guidebook: `917`

Required surfaces: `DATABASE.csv`, `hunt_master_enriched.csv`, `hunt_unit_reference_linked.csv`, `point_ladder_view.csv`, `draw_reality_engine.csv`.

Optional predictive surface: `draw_reality_engine_predictive_v2.csv`. Missing optional rows are coverage notes, not source-code reconciliation blockers.

## Required Blockers

| hunt_code | missing required surfaces |
|---|---|
| BI6539 | hunt_master_enriched |
| DB1121 | hunt_master_enriched |

Full row-level output: `processed_data/2026_big_game_hunt_code_reconciliation.csv`
