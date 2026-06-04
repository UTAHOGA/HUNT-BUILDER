# MODELED_AVAILABILITY Review Report

## Summary

- Forecast year: `2026`
- Source years: `2021, 2022, 2023, 2024, 2025`
- Total MODELED_AVAILABILITY rows: `124`
- Mountain lion / cougar rows: `120`
- Bear availability rows: `4`
- Other availability rows: `0`

## Field Guardrails

- `p_draw` non-null count: `0`
- `p_draw_pct` non-null count: `0`
- `p_preference_draw` non-null count: `0`
- `p_bonus_pool` non-null count: `0`
- `p_random_pool` non-null count: `0`
- `p_availability` non-null count: `122`
- `availability_pct` non-null count: `122`
- Duplicate key count: `0`

## Breakdown

| Group | Count |
|---|---:|
| BEAR_DRAW | 4 |
| MOUNTAIN_LION_DRAW | 120 |

## Conclusion

- Current live predictive artifacts contain 124 MODELED_AVAILABILITY rows: 120 mountain lion/cougar rows, 4 bear availability rows, and 0 other availability rows. A prior review artifact referenced 139 availability rows; that older count is stale relative to the current live predictive artifacts and does not represent an unexplained hidden family.
