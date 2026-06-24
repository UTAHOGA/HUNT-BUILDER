# 2025 Harvest Results Database for 2026 Modeling

- Input file: `2026-03-06-2025-preliminary-bg-harvest.xlsx`
- Reported hunt year: `2025`
- Model target year: `2026`
- Source status: `preliminary`
- Source date: `2026-03-06`

## Build totals

- Total rows processed: **1,120**
- Unique hunt codes: **1,120**
- Species represented: **8**
- Total permits in source: **156,537**
- Total hunters afield in source: **137,497**
- Total harvest in source: **45,764**

## Species counts

| Species | Rows |
|---|---:|
| Bison | 18 |
| Deer | 418 |
| Desert Bighorn Sheep | 25 |
| Elk | 455 |
| Moose | 44 |
| Mountain Goat | 18 |
| Pronghorn | 121 |
| Rocky Mountain Bighorn Sheep | 21 |

## Safeguards

- `do_not_use_for_permit_quota = true`
- `do_not_use_directly_for_p_draw = true`
- `trend_feature_eligible = true`

This dataset is suitable for quality/history/demand-signal features. It must not overwrite official 2026 permit quotas or direct draw probability outputs.
