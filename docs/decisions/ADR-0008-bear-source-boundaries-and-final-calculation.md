# ADR-0008: Bear source boundaries and final calculation

- Status: Accepted for local implementation; not a certification or release
- Date: 2026-09-20
- Authority: Tyler's request to enforce post-split history, rerun five adjacent
  comparisons through the final website calculation, and enforce existing gates.
- Extends ADR-0002, ADR-0003 and ADR-0007. Does not supersede ADR-0006 thresholds.

## Decision

The existing Bear family owner remains `engine/utah_draw_predictive/bear.py`.
The seven 2026 La Sal Mtns/Dolores Triangle hunting codes BR7021, BR7022,
BR7126, BR7127, BR7238, BR7239 and BR7326 may use applicant history only
from the 2026 split forward. The four older-code mappings remain lineage
reference, never forecast inheritance. Earlier historical folds retain their
original unsplit hunting codes. Restricted pursuit is not part of this split.
Pre-draw reviewed program/boundary changes likewise reset usable history.

Retention and arrival calibration are separated by Bear program and residency;
split targets cannot indirectly consume pre-effective pooled demand. Missing
same-lane point/predecessor applicant evidence remains an explained blank.
An otherwise supported applicant's conditional probability is not zero merely
because a rounded demand cell is empty. Neither treatment invents observed
applicants, redistributes a parent stack or overwrites official source rows.

`engine/utah_predictive_mixed.materialize.mixed_row` preserves the Bear family
probability under `BEAR_FAMILY_MECHANICS_PRESERVED_V1`. It may not revive a
missing/withheld Bear forecast or re-blend historical realized winners or
harvest context into it. The four certified core designs are unchanged.

Historical forecasts read only frozen, independently PDF-extracted lanes
numerically reconciled to the yearly canonicals, through the source year.
Forecasts are frozen in a separate process before target actuals are opened.
Only hash-verified pre-draw identity exceptions may influence those forecasts.
The scorer's opt-in exact-code mode disables implicit present-day crosswalks.
Historical source-year award proxies keep their original year/file metadata;
they are neither current quotas nor DATABASE-derived demand.

### Foundation and publication-boundary implementation clarification

The owner, not just a test projection, enforces exact source-dated Bear
program identity. Published resident/nonresident columns expand only after
all eight lane counts reconcile to the combined official record. Aggregate
`All` records cannot supply either separate residency; hunt totals do not
enter point ladders. Identical point duplicates count once, conflicting
duplicates fail, and bonus plus regular awards must equal total awards.
Both kinds of winners leave the applicable program's ladder. Pursuit does
not inherit hunting point-purchase arrivals or OTC-product counts.

Drawing quota assumptions use only the immediately preceding source-year
canonical program/code/residency awards. Missing lanes are not backfilled
from an older year. The explicit contract is
`quota_source_type=SOURCE_YEAR_CANONICAL_AWARDS_PROXY`,
`quota_is_current_allocation=FALSE`, and a separate `forecast_quota_proxy`.
For the seven 2026 split codes, that proxy is blank. Their
`public_permits_target` holds the requested whole-hunt current reference
total, marked `WHOLE_HUNT_REFERENCE_NOT_MODEL_QUOTA`, with separate current
catalog/crosswalk provenance. No calculation may reinterpret those totals
as resident or nonresident quota. Final quota resolution preserves the blank.

Final classification must preserve the owner's `NO_TRANSITION_EVIDENCE`
disposition and clear stale raw/certified probability and projected-line
aliases. In 2027 only 2026 source history is eligible; in 2028 only 2026-2027,
and thereafter only post-split history. The number of source years is not
the number of completed independent accuracy comparisons.

Write-producing crosswalk tests must run against exact-byte inputs in an
isolated mirror. Source classification of missing forecasts is additive
audit evidence; it neither rewrites frozen forecasts nor removes numerical
errors. DATABASE line-ending diagnosis may prepare an isolated byte candidate
but may not silently replace production data or redefine its frozen hash.

## Consequences

The isolated five-fold review fails Bear acceptance. Hunting remains
experimental; restricted pursuit has insufficient evidence as well as accuracy
failures. The existing 0.99 ceiling is not an accuracy repair: uncapped
false-certainty diagnostics must remain visible. No certified field is
published, no production registry changes, and no upload or deployment follows
from these local repairs. Any later candidate must pass the unchanged gates.
