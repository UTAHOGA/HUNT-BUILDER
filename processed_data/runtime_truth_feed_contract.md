# Runtime Truth Feed Contract

Generated runtime draw-result feeds should preserve the source truth before any
prediction engine reshapes it.

## Canonical Row Shape

- Canonical truth may be stored wide, with resident and nonresident fields on
  the same row.
- Runtime adapters may expand wide truth into one `Resident` row and one
  `Nonresident` row.
- Expanded runtime keys must include:
  `hunt_code + year + source_draw_class + draw_subpool + draw_pool + residency + points`.

## Required Semantics

- `source_draw_class` separates adult, youth, lifetime, dedicated hunter, turkey,
  Sportsman, bear, and other source/report families before any row collapse.
- `draw_subpool` separates distinct official same-point reported pools. These
  rows must not be summed into one fake applicant stack.
- Exact duplicate mirrors may be deduped only when applicant, permit, and
  success fields are identical.
- Summary-only rows with applicants/permits but no point ladder use
  `points=ALL`; point-stack engines must skip those rows.
- Non-scorable reference, quota-only, allocation-only, conservation, CWMU
  contact-operator, and no-public-odds rows must not enter public probability
  surfaces.

## Current Builder

`scripts/build_runtime_draw_feed_v2.py` implements this contract and writes the
draft runtime feed plus validation artifacts under `data_model/runtime_drafts/`.
