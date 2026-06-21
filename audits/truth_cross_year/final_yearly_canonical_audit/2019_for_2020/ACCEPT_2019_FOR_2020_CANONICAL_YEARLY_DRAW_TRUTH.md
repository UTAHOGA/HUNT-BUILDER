# Accept 2019=2020 Canonical Yearly Draw Truth

Generated UTC: 2026-06-20T00:01:32.296733+00:00

Decision: `ACCEPTED_FOR_CANONICAL_YEARLY_DRAW_TRUTH_PROMOTION`

Target file: `data_truth\draw_results_truth\normalized\canonical_yearly\draw_results_2019_for_2020_canonical_yearly_draw_results.csv`

## Validation

- Rows: 66945
- Columns: 55
- 55-column schema match: True
- Source year counts: {'2019': 66945}
- Model year counts: {'2020': 66945}
- Unique hunt codes: 1054
- Duplicate strict-key groups: 0
- CG9999 rows: 0
- Critical draw-truth blanks: {'hunt_code': 0, 'hunt_name': 0, 'species': 0, 'sex': 0, 'sex_type': 0, 'weapon': 0, 'draw_design': 0, 'residency': 0, 'points': 0, 'row_type': 0, 'record_type': 0, 'source_file': 0, 'source_pdf': 0, 'permits_year_res': 0, 'permits_year_nr': 0, 'permits_year_total': 0}

## Boundary Enrichment

Boundary enrichment status: `PARTIAL_ACCEPTED_FOR_2019_OLD_CODE_FILE`

Remaining blank boundary_id rows: 5811

Remaining blank boundary_id unique hunt codes: 98

Remaining boundary_id blanks are accepted for 2019 promotion because exact future yearly CSV boundary matching produced no safe fills; do not guess old-code boundaries.

## Acceptance

2019=2020 canonical yearly draw truth is accepted for canonical promotion. Boundary enrichment is explicitly partial and is not a draw-truth blocker for this old source year.

ACCEPT_2019_FOR_2020_CANONICAL_YEARLY_DRAW_TRUTH: true
