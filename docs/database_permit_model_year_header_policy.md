# DATABASE Permit Model-Year Header Policy

Generated: `2026-06-04T06:38:34+00:00`

## Decision

The exact model-year labels are now defined, but `DATABASE.csv` keeps machine-safe canonical headers for now. This avoids breaking active Python and website code that still reads `permits_2025_total` and `permit_allotment_2026_total`.

Human-facing exports should use the display headers in the map below.

## Header Map

| Canonical machine header | Display/model-year header |
|---|---|
| `permits_2024_res` | `RES_PERMITS_2024=2025_MODEL` |
| `permits_2024_nr` | `N.R_PERMITS_2024=2025_MODEL` |
| `permits_2024_total` | `TOTAL_PERMITS_2024=2025_MODEL` |
| `permits_2025_res` | `RES_PERMITS_2025=2026_MODEL` |
| `permits_2025_nr` | `N.R_PERMITS_2025=2026_MODEL` |
| `permits_2025_total` | `TOTAL_PERMITS_2025=2026_MODEL` |
| `permit_allotment_2026_res` | `RES_PERMITS_2026=2027_MODEL` |
| `permit_allotment_2026_nr` | `N.R_PERMITS_2026=2027_MODEL` |
| `permit_allotment_2026_total` | `TOTAL_PERMITS_2026=2027_MODEL` |

## Database Cleanliness Results

- Rows: `1471`
- Unique hunt codes: `1471`
- Duplicate hunt codes: `0`
- Numeric permit cells normalized from decimal-looking values: `4961`

## Field Population

| Field | Populated | Blank | Zero |
|---|---:|---:|---:|
| `permits_2024_res` | 973 | 498 | 3 |
| `permits_2024_nr` | 973 | 498 | 444 |
| `permits_2024_total` | 973 | 498 | 0 |
| `permits_2025_res` | 1056 | 415 | 3 |
| `permits_2025_nr` | 1056 | 415 | 450 |
| `permits_2025_total` | 1056 | 415 | 0 |
| `permit_allotment_2026_res` | 957 | 514 | 3 |
| `permit_allotment_2026_nr` | 957 | 514 | 482 |
| `permit_allotment_2026_total` | 1215 | 256 | 0 |

## Outputs

- Header map: `processed_data\audits\database_permit_model_year_header_map.csv`
- Cleanliness audit: `processed_data\audits\database_permit_field_cleanliness_audit.csv`
- Display-header export: `processed_data\audits\DATABASE_permit_model_year_display_headers.csv`
- Summary: `processed_data\audits\database_permit_model_field_cleanliness_summary.json`
