# 2026 Species Truth Permit Source Audit

## Scope

Normalized the user-supplied 2026 species truth permit files and compared direct hunt-code rows against the current reconciliation and DATABASE allotment reference fields.

Expo files were kept as name-only evidence because they do not carry hunt codes. They are not promotion-ready until mapped by an approved hunt-code crosswalk.

## Key Counts

- Normalized source rows: `844`
- Direct hunt-code rows: `598`
- Name-only rows: `246`
- Rows with permit values: `715`

## Source Family Counts

- `CONSERVATION_PERMITS_DIRECT`: `120` rows, `120` with permit values
- `DEER_BUCK_DB_DIRECT`: `458` rows, `329` with permit values
- `DEER_DOE_DIRECT`: `20` rows, `20` with permit values
- `EXPO_DRAW_RESULTS_NAME_ONLY`: `123` rows, `123` with permit values
- `EXPO_PERMIT_DRAW_NAME_ONLY`: `123` rows, `123` with permit values

## Comparison Status Counts

- `SOURCE_DIFFERS_FROM_CURRENT_RECONCILIATION`: `87`
- `SOURCE_HAS_VALUE_NO_CURRENT_COMPARISON_VALUE`: `1`
- `SOURCE_MATCHES_DATABASE`: `21`
- `SOURCE_MATCHES_RECOMMENDED`: `226`
- `SOURCE_NO_PERMIT_VALUE`: `129`
- `SOURCE_TOTAL_MATCHES_DATABASE`: `7`
- `SOURCE_TOTAL_MATCHES_RECOMMENDED`: `127`
- `UNMAPPED_NAME_ONLY_SOURCE`: `246`

## Outputs

- Normalized CSV: `processed_data/audits/permit_2026_species_truth_sources_normalized.csv`
- Comparison CSV: `processed_data/audits/permit_2026_species_truth_sources_vs_current_reconciliation.csv`
- Summary JSON: `processed_data/audits/permit_2026_species_truth_sources_summary.json`

## Guardrail

`DATABASE.csv` was not modified.
