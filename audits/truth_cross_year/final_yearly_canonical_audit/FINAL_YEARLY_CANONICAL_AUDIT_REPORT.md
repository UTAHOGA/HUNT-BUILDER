# Final Yearly Canonical Audit

Generated UTC: 2026-06-20T23:37:03.482830+00:00
Status: `PASS_CANONICAL_YEARLY_READY_LONG_CONFIRMED`

## Canonical Yearly Files

| Year | Model Year | Rows | Hunt Codes | Size MB | Duplicate Keys | CG9999 Rows | File |
|---:|---:|---:|---:|---:|---:|---:|---|
| 2019 | 2020 | 66945 | 1054 | 42.9 | 0 | 0 | `data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2019_for_2020_canonical_yearly_draw_results.csv` |
| 2020 | 2021 | 66715 | 1028 | 43.269 | 0 | 0 | `data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2020_for_2021_canonical_yearly_draw_results.csv` |
| 2021 | 2022 | 67565 | 1022 | 29.589 | 0 | 0 | `data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2021_for_2022_canonical_yearly_draw_results.csv` |
| 2022 | 2023 | 69741 | 1020 | 32.017 | 0 | 0 | `data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2022_for_2023_canonical_yearly_draw_results.csv` |
| 2023 | 2024 | 71658 | 1035 | 61.036 | 0 | 1 | `data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2023_for_2024_canonical_yearly_draw_results.csv` |
| 2024 | 2025 | 86659 | 1028 | 57.344 | 0 | 1 | `data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2024_for_2025_canonical_yearly_draw_results.csv` |
| 2025 | 2026 | 75598 | 1064 | 55.808 | 0 | 1 | `data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2025_for_2026_canonical_yearly_draw_results.csv` |
| 2026 | 2027 | 30298 | 847 | 28.903 | 0 | 0 | `data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2026_for_2027_canonical_yearly_draw_results.csv` |

## Long File Confirmation

`draw_results_long.csv` byte-matches the dry-run rebuild from canonical yearly files: `True`

## Git / R2 Policy

The canonical yearly CSVs for 2023, 2024, and 2025 are over 50 MB, so they need review before Git staging. The master long file and dry-run rebuilt long file are over 100 MB and should be R2-backed, not committed to Git.

All validation gates passed.
