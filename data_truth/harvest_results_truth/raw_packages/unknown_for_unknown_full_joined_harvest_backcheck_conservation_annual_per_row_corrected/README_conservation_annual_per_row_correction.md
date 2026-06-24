# Full Joined Harvest Backcheck — Conservation Annual-Per-Row Correction

This package corrects conservation handling based on the working rule supplied by Tyler:

> Each row in the 2025-2027 Conservation Permits file is **one permit per year** for 2025, 2026, and 2027.

Therefore the conservation permit count is **not divided by 3**.

## Correct conservation totals

- Conservation source rows: 336
- 2025 conservation permits: 336
- 2026 conservation permits: 336
- 2027 conservation permits: 336
- 2025-2027 permit-year instances: 1,008

## Correct 2026 known all-class total

- Public RAC permits: 17,231
- CWMU permits: 1,645
- Sportsman permits: 10
- Conservation permits: 336

Known 2026 all-class total: **19,222**

## Remaining limitation

The conservation file provides species + area + condition, but not always a single active hunt code. Therefore:

- High-confidence selected conservation rows: 171
- Conservation rows requiring manual review: 165

Aggregate conservation total reconciles. Final hunt-code-level distribution requires manual review of ambiguous conservation rows.
