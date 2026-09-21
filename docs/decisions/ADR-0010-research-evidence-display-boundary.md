# ADR-0010: Research evidence display boundary

- Status: Accepted display contract; implementation local, not deployed
- Date: 2026-09-20
- Authority: Tyler's instruction to fix source/display confusion and clarification that history must apply to the current hunt
- Extends ADR-0007's certified-only probability contract to its supporting future guidance. Does not change certification, model logic, source truth or release authority.

## Decision

A selected hunt/residency/point row without a usable `certified_p_draw*` value
and `CERTIFIED` status must not display a future projected line, favorable or
unfavorable forecast traffic light, point-creep advice or catch-up claim.
Show the evidence status and `Prediction withheld`. No summary, catalog,
harvest contract, raw probability or line-position fallback may revive odds.
Certified core values remain unchanged. Provisional policy is not certification.

Keep archived original history, but display historical results on a current
hunt page only when applicable to that hunt/program/residency and boundary.
The seven ADR-0008 La Sal/Dolores split codes cannot display pre-2026 results
as their own history. Show the reason; never copy parent results into either
child. This is separate from whether an otherwise comparable hunt's future
forecast has passed certification. Generic applicant/permit fields may be
projected demand or current allocations: the browser must not divide them
to invent a historical result. It may display explicit historical-result fields.

Research details are composite data, not one `DATABASE.csv` truth source.
The candidate builder labels current catalog identity/permit references,
recorded historical row lineage, certified future fields and harvest context
separately. Missing row provenance is explicitly missing, not reconstructed
from catalog or harvest fields. Existing row/source bytes are not rewritten.

## Implementation and limits

Owners remain `hunt-research.js`, `assets/js/research-outlook-dashboard.js`
and `scripts/build_certified_research_contract_candidate.py`. No parallel
runtime or prediction stack is introduced. Display regression tests exercise
unsupported and certified rows, stale guidance, source separation and all
seven split exclusions. This is not a new all-hunt crosswalk validation.

Bear remains NOT CERTIFIED. Four-core registry `adr-0006-2200616ce0b9`, frozen
accuracy limits, two known project-memory failures and 19 broader V3 failures
are unchanged. No production data regeneration or deployment is authorized
by this record.
