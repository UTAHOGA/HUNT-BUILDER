# 2026 Permits vs Same-Code 2025 Carryover Audit

## Question

Could the `DATABASE.csv` 2026 allotment fields or the current recommended fields simply match same-code 2025 permit numbers?

## Short Answer

Yes, some rows numerically match same-code 2025 permit values. A numeric match alone does not prove carryover, because many rows also have current 2026 source support from HaNumber, HuntTable, UtahDraws, or the repaired Buck Deer current source.

## Counts

- DATABASE rows audited: `1471`
- Rows where allotment or recommendation matched same-code 2025 numbers: `164`

## Risk Classification

- `MATCHES_2025_WITH_CURRENT_SOURCE_SUPPORT`: `164`
- `NO_2025_NUMERIC_MATCH`: `1307`

## Allotment vs 2025

- `BOTH_BLANK`: `157`
- `DIFFERS`: `795`
- `EXACT_MATCH`: `156`
- `LEFT_BLANK`: `99`
- `RIGHT_BLANK`: `258`
- `TOTAL_MATCH_ONLY`: `6`

## Recommended vs 2025

- `BOTH_BLANK`: `212`
- `DIFFERS`: `792`
- `EXACT_MATCH`: `158`
- `LEFT_BLANK`: `100`
- `RIGHT_BLANK`: `203`
- `TOTAL_MATCH_ONLY`: `6`

## Outputs

- Full audit: `processed_data/audits/permit_2026_vs_2025_same_code_carryover_audit.csv`
- Review subset: `processed_data/audits/permit_2026_vs_2025_same_code_carryover_review.csv`
- Summary: `processed_data/audits/permit_2026_vs_2025_same_code_carryover_summary.json`
