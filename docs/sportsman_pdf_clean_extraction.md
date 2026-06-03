# Sportsman PDF Clean Extraction

## Purpose

This pass creates a cleaner extraction layer for Sportsman draw-result PDFs so downstream scripts do not have to parse fragile PDF text directly.

The key defect being guarded against is PDF text where the prior `N/A` cell joins to the hunt code, producing false raw values such as `ABI1000`. In the clean extract, the raw artifact is preserved for audit, while the normalized script-facing code is corrected to the real hunt code, such as `BI1000`.

## Outputs

- `processed_data/audits/sportsman_pdf_clean_extract.csv`
- `processed_data/audits/sportsman_pdf_clean_script_feed.csv`
- `processed_data/audits/sportsman_pdf_clean_extract.xlsx`
- `processed_data/audits/sportsman_pdf_clean_extract_audit.csv`
- `processed_data/audits/sportsman_pdf_clean_extract_summary.json`

## Which File Scripts Should Use

Use:

```text
processed_data/audits/sportsman_pdf_clean_script_feed.csv
```

This file keeps one preferred row per `draw_results_year + normalized_hunt_code`.

Preference order:

1. `BIBLE_HUNT_CODES` source rows
2. official one-hunt-per-page totals
3. UtahDraws summary ladder rows
4. normal inline Sportsman table rows
5. stacked-column Sportsman table rows
6. normalized `N/A`-glued code rows

The full `sportsman_pdf_clean_extract.csv` remains the audit/evidence table and intentionally includes duplicate source copies where both BIBLE and repo pipeline copies exist.

## Current Counts

- Source PDFs scanned: `16`
- Full extracted rows: `172`
- Preferred script-feed rows: `96`
- Unique normalized hunt codes: `12`
- Source-audit failures: `0`
- `N/A`-glued artifact rows normalized: `52`

Preferred script-feed rows by draw-results year:

| draw_results_year | rows |
|---|---:|
| 2018 | 11 |
| 2019 | 11 |
| 2020 | 11 |
| 2021 | 12 |
| 2022 | 11 |
| 2023 | 10 |
| 2024 | 10 |
| 2025 | 10 |
| 2026 | 10 |

## Supported PDF Layouts

- normal one-line Sportsman table rows
- stacked-column Sportsman table rows
- `N/A`-glued code rows, for example `ABI1000 -> BI1000`
- generated one-hunt-per-page Sportsman result PDFs
- UtahDraws summary export PDFs

## Guardrails

- Do not treat raw `ABI1000`, `ABR1000`, `ADB0007`, etc. as real hunt codes.
- Do not rewrite `DATABASE.csv` from this extraction layer without a separate reviewed promotion step.
- Keep Sportsman permits separate from bonus/preference ladder mechanics.
- Preserve `raw_extracted_code`, `normalized_hunt_code`, and `artifact_status` for audit traceability.
