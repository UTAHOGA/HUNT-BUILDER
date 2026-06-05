# 2023 Harvest/Draw Ingestion Audit

Read-only proof that 2023 harvest data is present in the harvest truth/feature path and available to the Hunt Research engine.

## Summary

- Result: `PASS`.
- Reported hunt year: `2023`.
- Model target year: `2024`.
- Harvest truth rows for 2023: `7492`.
- Harvest truth hunt codes for 2023: `1078`.
- Engine feature rows for 2023: `1179`.
- Engine feature hunt codes for 2023: `1179`.
- Draw truth rows for 2023: `17128`.
- Draw truth hunt codes for 2023: `1010`.
- Feature model rows using 2023 history: `1111`.
- Feature model hunt codes using 2023 history: `1111`.

## Source Status

| Source | Truth long rows | Truth feature rows | Engine feature rows | Status |
| --- | ---: | ---: | ---: | --- |
| 2023 desert bighorn harvest report unit not number.pdf | 411 | 16 | 16 | INGESTED_TRUTH_AND_ENGINE_FEATURE |
| 2023 Hunt Success.pdf | 5448 | 592 | 592 | INGESTED_TRUTH_AND_ENGINE_FEATURE |
| 2023_le_oial_all.pdf | 0 | 0 | 0 | REFERENCE_OR_DUPLICATE_NOT_PROMOTED |
| 2023-24 turkey.pdf | 0 | 0 | 7 | ENGINE_FEATURE_ONLY |
| A96251BE__2023_antlerless_hr.pdf | 597 | 199 | 199 | INGESTED_TRUTH_AND_ENGINE_FEATURE |
| dbd8a659__cougar_2023.pdf | 0 | 0 | 0 | REFERENCE_OR_DUPLICATE_NOT_PROMOTED |
| dc965eb4__General-season buck deer.pdf | 534 | 136 | 136 | INGESTED_TRUTH_AND_ENGINE_FEATURE |
| 23_bg_report.pdf | 0 | 0 | 94 | ENGINE_FEATURE_ONLY |
| 23_black_bear_report.pdf | 261 | 87 | 87 | INGESTED_TRUTH_AND_ENGINE_FEATURE |
| BIGHORN SHEEP 2023-harvest-data.pdf | 8 | 0 | 0 | TRUTH_ONLY_NOT_ENGINE_FEATURE |
| 61FC0758__BIGHORN SHEEP 2023-harvest-data.pdf | 8 | 0 | 0 | TRUTH_ONLY_NOT_ENGINE_FEATURE |

## Notes

- `2023 Hunt Success.pdf` is the broad all-species hunt-code keyed harvest package and covers 592 hunt codes.
- `23_bg_report.pdf` and `2023-24 turkey.pdf` are present in the engine-facing feature table but not fully represented as normalized long truth rows in this pass.
- `2023_le_oial_all.pdf` and `dbd8a659__cougar_2023.pdf` are treated as reference/duplicate/not-promoted for the current harvest engine path unless later review promotes them.
- Harvest rows remain quality/history inputs. They must not overwrite draw quota, draw odds, or `DATABASE.csv` permit truth.

## Conclusion

2023 harvest data is already ingested into the engine-facing harvest feature path. The broad all-species harvest source and listed supplemental sources are present where expected; a few listed PDFs are duplicate/reference coverage or unsupported for current promotion.
