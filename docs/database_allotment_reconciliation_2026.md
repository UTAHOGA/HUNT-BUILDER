# DATABASE Allotment Reconciliation 2026

## Scope

This pass closes rows where recommended 2026 permit values already match `DATABASE.csv` `permit_allotment_2026_*` fields and splits out rows where DATABASE disagrees with the recommendation.

This split/reporting script did not change `DATABASE.csv`; it reflects the current DATABASE state at run time.

## Key Counts

- Reconciled allotment matches: `1158`
- Exact resident/nonresident/total matches: `1151`
- Total-only matches: `7`
- Reconciled rows that were previously in unresolved subset: `384`
- DATABASE disagreement rows: `0`
- Not reconciled / no recommendation / not compared rows: `312`

## Disagreement Counts


## Outputs

- Reconciled: `processed_data/audits/database_allotment_reconciled_2026.csv`
- Reconciled unresolved subset: `processed_data/audits/database_allotment_reconciled_2026_unresolved_subset.csv`
- DATABASE disagreements: `processed_data/audits/database_allotment_disagreements_2026.csv`
- Review/not reconciled: `processed_data/audits/database_allotment_no_recommendation_or_not_compared_2026.csv`
- Summary: `processed_data/audits/database_allotment_reconciliation_2026_summary.json`
