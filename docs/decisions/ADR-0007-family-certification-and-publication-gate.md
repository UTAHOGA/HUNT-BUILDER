# ADR-0007: Family Certification And Publication Gate

- Status: Accepted
- Date: 2026-09-07

## Decision

Statistical certification is independent of runtime implementation status.
`PROMOTED_TO_RUNTIME` means that a family is routed and materialized; it does
not mean its probability forecast passed the blind acceptance standard.

Every forecastable draw design receives one of three evidence statuses from a
machine-generated registry:

- `CERTIFIED`: every ADR-0006 threshold passes, including source-classified
  coverage of every non-joined scoreable official actual.
- `EXPERIMENTAL_NOT_CERTIFIED`: enough evidence exists to judge the family, but
  at least one accuracy, tail, false-guarantee, or coverage gate fails.
- `INSUFFICIENT_EVIDENCE`: the family lacks the required independent folds,
  joined rows, or complete gate evidence.

Raw `p_draw` fields remain available for development and blind scoring. A
certification-aware public contract may expose future probability only through
`certified_p_draw`, `certified_p_draw_mean`, or `certified_p_draw_pct`. Those
fields must be blank for every non-certified row. Local or hosted promotion is
blocked when that contract is absent or violated.

Bear limited-entry hunting and restricted pursuit remain separate
certification populations. An untyped or combined `BEAR_DRAW` population
cannot certify either program.

The prior `guaranteed_at_*` fields remain temporary compatibility aliases.
New materializations also emit `projected_draw_line_2025` and
`projected_draw_line_2026`. A projected line estimates future draw structure;
it never converts a row to 100% probability and never promises that an
applicant will draw.

## Current Result

The gate was applied to the source-only 2017→2018 through 2024→2025 review.
The earlier report did not enforce its declared design-level non-joined-actual
gate. The rebuilt review now counts every scoreable official actual lacking a
forecast and requires an explicit source classification before certification.

No design is currently certified. `BONUS_OIL_BIG_GAME` passes the joined-row
probability thresholds but remains experimental because its missing scoreable
official actuals are not classified by the historical review. This corrects an
overstatement in the prior metric-only report; it does not change official
truth or any forecast value.

## Consequences

- The existing hosted Research release remains unchanged and explicitly
  uncertified.
- A new certification-aware build will show historical evidence and projected
  lines for non-certified families but withhold their future probability.
- Certification is granted per draw design, never by aggregate score.
- Closing a coverage gap requires a source-backed classification or a real
  forecast; deleting or silently dropping the official actual is prohibited.
- Upload, deployment, and production promotion still require Tyler's separate
  explicit authorization.
