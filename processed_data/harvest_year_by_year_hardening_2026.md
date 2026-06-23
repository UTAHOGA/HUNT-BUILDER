# Harvest Year-By-Year Hardening Audit 2026

Read-only audit of normalized harvest truth against the current 2026 canonical hunt-code universe.

## Topline

- Current DATABASE hunt codes: 1471
- Harvest best rows: 5151
- Harvest long rows: 68657
- Current codes covered in at least one harvest year: 1244
- Current codes missing from all harvest years: 227
- Historical harvest codes not in current DATABASE: 180
- 2021 unique harvest hunt-code baseline: 974
- Expected trend: unique harvest hunt-code count should generally increase slightly year over year, or any drop should be explained by source coverage, discontinued codes, or true season structure changes.

## Year Coverage

| Reported hunt year | Native unique harvest codes | Best rows | Metric warnings |
|---|---:|---:|---:|
| 2021 | 974 | 974 | 1008 |
| 2022 | 924 | 924 | 1320 |
| 2023 | 1078 | 1078 | 1250 |
| 2024 | 1048 | 1048 | 11931 |
| 2025 | 1127 | 1127 | 12 |

## Current Reference Alignment

The 2026 `DATABASE.csv` comparison is only for crosswalk/alignment work. It is not a completeness score for older harvest years.

| Reported hunt year | Current 2026 codes cross-referenced | Current 2026 codes not cross-referenced |
|---|---:|---:|
| 2021 | 837 | 634 |
| 2022 | 826 | 645 |
| 2023 | 1010 | 461 |
| 2024 | 1003 | 468 |
| 2025 | 1123 | 348 |

## Harvest Metric Publication Status

| Metric | Captured in harvest truth | Published in hunt reference | Published in hunt master |
|---|---:|---:|---:|
| permits | yes | no | no |
| hunters_afield | yes | yes | yes |
| harvest_total | yes | yes | yes |
| harvest_male | yes | no | no |
| harvest_female | yes | no | no |
| harvest_young | yes | no | no |
| percent_success | yes | yes | yes |
| average_days | yes | yes | no |
| hunter_satisfaction | yes | yes | no |
| average_age | yes | no | no |
| harvest_objective | yes | no | no |

Note: current hunt-reference publication is mostly 2025-facing. The all-year harvest truth file is richer than the current website-facing/reference fields.

## Guardrails

- This audit does not change harvest truth rows, `DATABASE.csv`, website feeds, or draw predictions.
- Missing rows are repair targets, not proof that a hunt lacked harvest.
- Harvest `permits` fields remain report-context values and are not draw allotments.
