# 2023-24 Turkey Harvest Database for 2025 Modeling

Generated: 2026-05-23T08:52:41.342219+00:00

Source: `2023-24 turkey.pdf`

## Year treatment

- `reported_hunt_year = 2023` for fall management harvest rows.
- `reported_hunt_year = 2024` for spring limited-entry/CWMU, youth general-season, and spring general-season rows.
- `model_target_year = 2025`.

## Totals

| Output | Rows |
|---|---:|
| All-long normalized rows | 155 |
| Hunt-code keyed rows | 7 |
| Quality-feature rows | 155 |

## Table summary

| table_name                                            | harvest_family                                     |   rows |   hunt_code_rows |   total_harvest_sum |   unique_hunt_codes |
|:------------------------------------------------------|:---------------------------------------------------|-------:|-----------------:|--------------------:|--------------------:|
| fall_management_by_region_area_2023                   | Turkey Fall Management                             |     17 |                0 |                1764 |                   0 |
| fall_management_statewide_history_2014_2023           | Turkey Fall Management Statewide History           |     10 |                0 |               13222 |                   0 |
| general_season_statewide_history_2010_2024            | Turkey General Season Statewide History            |     15 |                0 |               27795 |                   0 |
| spring_general_season_by_region_county_2024           | Turkey Spring General Season                       |     36 |                0 |                6295 |                   0 |
| spring_limited_entry_cwmu_by_hunt_2024                | Turkey Spring Limited Entry/CWMU                   |      7 |                7 |                 635 |                   7 |
| spring_limited_entry_cwmu_statewide_history_1991_2024 | Turkey Spring Limited Entry/CWMU Statewide History |     34 |                0 |               29430 |                   0 |
| spring_youth_general_season_by_region_county_2024     | Turkey Spring Youth General Season                 |     36 |                0 |                1444 |                   0 |

## Safeguards

Every row is marked:

```text
do_not_use_for_permit_quota = true
do_not_use_directly_for_p_draw = true
trend_feature_eligible = true
```

Use these rows as turkey harvest-quality, hunter-effort, success-rate, and demand-signal features only.
