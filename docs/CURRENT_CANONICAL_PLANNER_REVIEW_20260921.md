# Current hunt-master canonical versus fresh DWR Planner

Local, read-only review. No current master, historical canonical, DATABASE,
prediction, eligibility projection, or website artifact was changed.

The requested master is
`data/utah/official_downloads_2026/hunt_master_canonical_2026.csv`.
Its retained download manifest is dated May 6, 2026. It has 1,288 distinct codes
and no explicit retired/status fields. It is not yet a verified complete current
inventory. A missing code must not be classified as retired just because it is
absent from this master.

## Fresh official checks

All 30 HuntTableData matrix requests and all 1,443 HaNumber detail requests
succeeded. The matrix/detail scan found 1,426 records explicitly labeled 2026
and 17 with older years. Current year means publication-year presence here,
not public-draw eligibility or permission to emit a probability.

| Comparison | Codes |
| --- | ---: |
| Named current canonical | 1,288 |
| Canonical confirmed 2026 in matrix/detail scan | 1,255 |
| Current matrix codes missing from canonical | 171 |
| Canonical without 2026 matrix confirmation | 33 |

Direct HaNumber follow-up on the 21 canonical codes absent from the matrix
found PB5329 explicitly in 2026. The other 20 returned no 2026 hunt-year record.
The remaining 12 canonical codes were present in the matrix with older years.
All direct requests succeeded with matching hunt identities.

Thus the combined check supports **1,256 current canonical codes**, **32 canonical
codes without a published 2026 record in these responses**, and **171 current
matrix codes missing from canonical**. It does not prove those 32 permanently
retired. PB5329 demonstrates why table absence alone is insufficient.

Of the 171 missing current codes, **146 belong to species already represented in
the canonical** and **25 belong to additional bird categories**. Those additional
species remain outside any proposed automatic inclusion; this review does not
undo the user's earlier crane/grouse/swan scope exclusions. The combined
same-species current presence census is 1,402, not a forced 1,471. This is still
an identity census, not a public-draw or prediction count.

Examples: EA1007 and many current Bear codes are absent from the named master;
EA1281 instead returns a 2025 record. DATABASE's 561 codes absent from the master
are therefore **catalog differences, not a retired list**. The earlier proposed
canonical-only promotion filtering was withdrawn; the resolver was restored to
its pre-task SHA-256 `1457998b25ed1ee639dda281bd98326f3fe4c327697a367a9d4f916608b252cb`.

## Retained evidence

Under `audit_output_phase1_candidate/current_canonical_identity_20260921/`:

- `planner_matrix/`: complete fresh official matrix responses and request log.
- `planner_popup/`: 1,443 official detail responses, normalized CSV and summary.
- `review/current_code_reconciliation.csv`: full code-level comparison.
- `review/summary.json`: measured counts and SHA-256 hashes.
- `direct_followup/`: raw responses and hashes for all 21 direct checks;
  `summary.json` also lists all 146 same-species and 25 additional-species codes.

Official endpoints: https://dwrapps.utah.gov/huntboundary/HuntTableData and
https://dwrapps.utah.gov/huntboundary/HaNumber. Captured on September 21, 2026
(UTC timestamps retained per response). These are current identity/permit
references; applicant and awarded-permit outcome truth remains the physical-year
draw canonicals and their official draw-result parents.

Next identity repair requires reviewing the missing current codes and the 32
noncurrent/unconfirmed records by program, preserving old records separately,
then publishing a source-backed current canonical candidate. No historical
draw rows should be removed merely because their codes are no longer current.
