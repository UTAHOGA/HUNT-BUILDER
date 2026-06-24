# Utah Wild Turkey Harvest Database — 2024-25 for 2026 Modeling

Source: `2024-25 turkey.pdf`

## Scope

- `reported_hunt_year = 2024` for fall management harvest rows.
- `reported_hunt_year = 2025` for spring limited-entry/CWMU, youth general-season, and spring general-season rows.
- `model_target_year = 2026`.
- Species: Wild Turkey.

## Row counts

| Table | Rows |
|---|---:|
| all_long | 157 |
| hunt_code_keyed | 7 |
| fall_management_2024_by_region_area | 16 |
| fall_management_statewide_history_2014_2024 | 11 |
| spring_limited_entry_cwmu_2025_by_hunt | 7 |
| limited_entry_cwmu_statewide_history_1991_2025 | 35 |
| youth_general_season_2025_by_region_county | 36 |
| spring_general_season_2025_by_region_county | 36 |
| general_season_statewide_history_2010_2025 | 16 |
| quality_features | 98 |

## Key statewide totals

| Metric | Value |
|---|---:|
| Fall management 2024 total harvest | 1123 |
| Spring limited-entry/CWMU 2025 total harvest | 966 |
| 3-day youth general-season 2025 total harvest | 376 |
| Spring general-season 2025 total harvest by county table | 2920 |
| Statewide general-season 2025 total harvest | 3296 |

## Safeguards

Every row is marked:

```text
do_not_use_for_permit_quota = true
do_not_use_directly_for_p_draw = true
trend_feature_eligible = true
```

These turkey rows should feed harvest quality, hunter effort, success-rate, and demand-signal features only.
