# 2024 Black Bear Harvest/Mortality/Pursuit Supplement for 2025 Modeling

This package normalizes the uploaded 2024 black bear report excerpts into model-ready harvest quality/history tables.

## Scope

- `reported_hunt_year = 2024`
- `model_target_year = 2025`
- species = `Black Bear`

## Outputs

| Table | Rows | Unique hunt codes | Unique units | Year range |
|---|---:|---:|---:|---|
| black_bear_statewide_history_1967_2000 | 34 | 0 | 0 | 1967-2000 |
| black_bear_statewide_harvest_mortality_2001_2024 | 24 | 0 | 0 | 2001-2024 |
| black_bear_unit_harvest_2024 | 24 | 0 | 24 | 2024-2024 |
| black_bear_hunt_code_harvest_2024 | 87 | 87 | 25 | 2024-2024 |
| black_bear_harvest_objective_2024 | 21 | 0 | 17 | 2024-2024 |
| black_bear_statewide_pursuit_2002_2024 | 23 | 0 | 0 | 2002-2024 |
| black_bear_restricted_pursuit_annual | 20 | 0 | 0 | 2010-2024 |
| black_bear_pursuit_by_unit_2024 | 46 | 0 | 25 | 2024-2024 |
| black_bear_restricted_pursuit_by_unit_season_2024 | 9 | 0 | 9 | 2024-2024 |
| black_bear_unit_mortality_history_1990_2024 | 665 | 0 | 27 | 1990-2024 |


## Package totals

- Quality feature rows: 24
- Supplement long rows added: 953
- Enhanced all-long v3 rows: 4542

## Safeguards

Every row is marked:

```text
do_not_use_for_permit_quota = true
do_not_use_directly_for_p_draw = true
trend_feature_eligible = true
```

These rows are harvest quality, sex ratio, mean age, depredation, mortality, pursuit, and unit trend signals. They are not permit quota or direct draw probability inputs.
