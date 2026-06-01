# Hunt Research Feeder-to-Contract Reconciliation

## Step 1 ? Locked legacy feeder set

- `processed_data/draw_reality_engine.csv`: Engine odds/permit-status feeder (legacy core engine rows).
- `processed_data/point_ladder_view.csv`: Point ladder + modeled probability feeder (legacy ladder rows).
- `processed_data/hunt_master_enriched.csv`: Hunt metadata feeder (legacy master rows; local file currently LFS pointer).
- `processed_data/hunt_unit_reference_linked.csv`: Reference + harvest summary + permit overlay feeder (legacy reference rows).

## Step 2 ? Field ownership map

| Hunter-facing field | Feeder source of record | Target field in `hunt_research_2026.json` | Expected exact match | Canonical improvement allowed |
|---|---|---|---|---|
| hunt_name | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_master_enriched.csv` (hunt_name) | `hunt_name` | NO | YES |
| species | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_master_enriched.csv` (species) | `species` | YES | NO |
| weapon | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_master_enriched.csv` (weapon) | `weapon` | YES | NO |
| hunt_type | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_master_enriched.csv` (hunt_type) | `hunt_type` | NO | YES |
| residency | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (residency) | `residency` | YES | NO |
| draw_pool | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (draw_pool) | `draw_pool` | YES | NO |
| points | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (points) | `points` | YES | NO |
| draw_outlook | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (draw_outlook) | `draw_outlook` | YES | NO |
| status | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (status) | `status` | NO | YES |
| trend | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (trend) | `trend` | YES | NO |
| display_odds_pct | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (display_odds_pct) | `display_odds_pct` | NO | YES |
| p_draw_mean | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (p_draw_mean) | `p_draw_mean` | NO | YES |
| p_draw_p10 | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (p_draw_p10) | `p_draw_p10` | NO | YES |
| p_draw_p90 | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (p_draw_p90) | `p_draw_p90` | NO | YES |
| point_pool_zone | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (point_pool_zone) | `point_pool_zone` | YES | NO |
| guaranteed_at_2026 | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (guaranteed_at_2026) | `guaranteed_at_2026` | NO | YES |
| permits_2026_res | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_unit_reference_linked.csv` (permits_2026_res) | `permits_2026_res` | NO | YES |
| permits_2026_nr | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_unit_reference_linked.csv` (permits_2026_nr) | `permits_2026_nr` | NO | YES |
| permits_2026_total | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_unit_reference_linked.csv` (permits_2026_total) | `permits_2026_total` | NO | YES |
| harvest_success_pct | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_unit_reference_linked.csv` (harvest_success_percent_2025) | `harvest_success_pct` | NO | YES |
| average_days_hunted | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_unit_reference_linked.csv` (harvest_average_days_2025) | `average_days_hunted` | NO | YES |
| average_harvest_age | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (average_harvest_age) | `average_harvest_age` | NO | YES |
| current_age_3yr_average | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (current_age_3yr_average) | `current_age_3yr_average` | NO | YES |
| management_objective_type | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_master_enriched.csv` (management_objective_type) | `management_objective_type` | NO | YES |
| management_objective_range | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_master_enriched.csv` (management_objective_range) | `management_objective_range` | NO | YES |
| management_direction | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/hunt_master_enriched.csv` (management_direction) | `management_direction` | NO | YES |
| availability_status | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/draw_reality_engine.csv` (availability_status) | `availability_status` | NO | YES |
| dwr_result_display | `C:/Users/tyler/Desktop/GitHub/HUNT-BUILDER/processed_data/point_ladder_view.csv` (dwr_result_display) | `dwr_result_display` | NO | YES |

## Step 3/4 ? 1,449-code reconciliation results

- Universe size (DATABASE.csv): **1449** hunt codes
- Mapped fields audited: **28**
- Total comparison rows: **40572**

| Status | Count |
|---|---:|
| MATCH | 16120 |
| IMPROVED_FROM_CANONICAL_SOURCE | 4147 |
| MISSING_IN_TARGET | 590 |
| MISMATCH | 0 |
| NOT_PRESENT_IN_FEEDER | 9572 |
| INTENTIONALLY_RETIRED | 0 |
| REVIEW_REQUIRED | 10143 |

## Step 5 ? Runtime publication check

| Publication status | Count |
|---|---:|
| MISSING_IN_CONTRACT | 2 |
| PRIMARY_FROM_CONTRACT_WITH_LEGACY_FALLBACK | 21 |
| REVIEW_REQUIRED | 5 |

- Fields not fully published from canonical contract path: availability_status, current_age_3yr_average, dwr_result_display, guaranteed_at_2026, management_direction, management_objective_range, management_objective_type

## Replacement verdict

**PARTIALLY VERIFIED** as a strict four-feeder replacement under current evidence set.

Notes:
- Local `hunt_master_enriched.csv` is an LFS pointer, so feeder-value reconciliation for master-owned fields is marked `REVIEW_REQUIRED` rather than guessed.
- Runtime is contract-primary after canonicalization, with legacy feeder chains retained as fallback safety paths.