# 2026 Core Hunt-Code Universe Reconciliation

## Purpose

This pass reconciles what can be safely classified now from the 2025 BIBLE draw-results universe, the fresh 2026 DWR Hunt Planner table, the popup/HaNumber pull, and the user-supplied 2026 species truth permit files.

It does not treat the raw DWR Hunt Planner table count as the core BIBLE/draw-results universe.

## Key Counts

- Total audit rows: `1718`
- Closed/classified rows: `1591`
- Review rows: `127`
- Closed core comparable 2026 rows: `1024`
- Maybe-core rows requiring review: `95`
- Separate/excluded rows: `599`

## Bucket Counts

- `CONFIRMED_2026_NEW_OR_OMITTED_DIRECT_SOURCE`: `2`
- `CORE_DRAW_RESULTS_CONTINUING`: `1024`
- `COUGAR_CURRENT_STATEWIDE_UNLIMITED_LAYER`: `1`
- `COUGAR_HISTORICAL_SPORTSMAN_ENDED`: `1`
- `CURRENT_PLANNER_EXTRA_REVIEW`: `35`
- `CURRENT_PLANNER_EXTRA_WITH_MULTI_SOURCE_PERMIT_SUPPORT`: `10`
- `DATABASE_REFERENCE_NOT_LIVE_TABLE`: `30`
- `HISTORICAL_LIBRARY_ONLY`: `245`
- `POSSIBLE_DROPPED_OR_NOT_EXPOSED_FROM_2025`: `29`
- `SEPARATE_CONSERVATION_LAYER`: `28`
- `SEPARATE_CWMU_CURRENT_PLANNER_LAYER`: `9`
- `SEPARATE_EXTENDED_ARCHERY_NO_QUOTA_LAYER`: `1`
- `SEPARATE_PRIVATE_LAND_LANDOWNER_LAYER`: `282`
- `SEPARATE_STATEWIDE_UNLIMITED_LAYER`: `1`
- `SEPARATE_TRIBAL_LAYER`: `10`
- `SPORTSMAN_CONTINUITY_LAYER_REVIEW`: `10`

## Review Bucket Counts

- `CONFIRMED_2026_NEW_OR_OMITTED_DIRECT_SOURCE`: `2`
- `CURRENT_PLANNER_EXTRA_REVIEW`: `35`
- `CURRENT_PLANNER_EXTRA_WITH_MULTI_SOURCE_PERMIT_SUPPORT`: `10`
- `DATABASE_REFERENCE_NOT_LIVE_TABLE`: `30`
- `POSSIBLE_DROPPED_OR_NOT_EXPOSED_FROM_2025`: `29`
- `SEPARATE_CONSERVATION_LAYER`: `2`
- `SEPARATE_CWMU_CURRENT_PLANNER_LAYER`: `9`
- `SPORTSMAN_CONTINUITY_LAYER_REVIEW`: `10`

## Interpretation

- `CORE_DRAW_RESULTS_CONTINUING` is the only closed core count in this pass.
- Private-land/landowner, conservation, statewide/unlimited, tribal, and historical-only rows were separated from the core comparable universe where deterministic.
- Rows marked `REVIEW` are the remaining place to spend human review time: possible drops, new additions, CWMU changes, sportsman continuity extraction gaps, or current-planner extras with source support.

## Outputs

- All rows: `processed_data/audits/current_2026_core_universe_reconciliation.csv`
- Closed rows: `processed_data/audits/current_2026_core_universe_reconciliation_closed.csv`
- Review rows: `processed_data/audits/current_2026_core_universe_reconciliation_review.csv`
- Summary: `processed_data/audits/current_2026_core_universe_reconciliation_summary.json`
