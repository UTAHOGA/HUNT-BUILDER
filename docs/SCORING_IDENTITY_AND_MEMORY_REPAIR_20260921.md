# Scoring identity and project-memory repair

Scope: local evaluator/authority repair, not an engine rebuild or release.

## Completed measured result

All nine frozen folds are scored. The final 2026-only CWMU pool fix has exact
scored-key and probability parity with the completed V4 nine-fold review:
135,963 independent joined keys, MAE 8.631590 pp, P90 25 pp, tail 9.893868%.
There are no repeated scored keys in any fold; the latest eight historical
projections plus 2026 V5 have zero conflicting populated actual-key groups.
27,182 repeated/superseded forecast records have a retained resolution ledger;
the original frozen forecasts are unchanged. All 204 protected inputs/reports
were unchanged at the completed frozen-review checkpoint.

The adopted 2017-2018 through 2024-2025 review, separately from 2026:

| Adult design | Scored keys | MAE pp | P90 pp | Tail >25 pp | Blocking gaps |
| --- | ---: | ---: | ---: | ---: | ---: |
| Limited entry | 49,033 | 7.113 | 16.407 | 7.375% | 0 |
| Once-in-a-lifetime | 17,544 | 2.788 | 3.243 | 2.890% | 0 |
| Premium limited entry | 2,667 | 1.983 | 2.229 | 1.875% | 0 |
| General-season buck deer | 7,779 | 6.749 | 21.767 | 7.147% | 0 |

These meet the recorded numerical/classified-coverage checks. They are not a
new certification decision or permission to ignore runtime/source gates.
Bear, CWMU, Turkey, antlerless, Dedicated Hunter and youth populations still
have accuracy, sample or coverage failures. Nine-fold blocking coverage gaps
total 1,398; 1,292 are in the adopted eight-fold window, 106 in the separately
labeled 2026 diagnostic. The latter has 17,244 scored keys, 8.036415 pp MAE,
1,512 missing/blank forecast actual keys of which 1,406 are source-classified.
Separating CWMU youth exposes additional source-classified lanes, not fabricated
forecast samples. Existing probability ceilings require their separate risk
review; zero reported false guarantees is not proof of zero uncapped risk.

The two ambiguous 2026 deer rows are still matched in the raw diagnostic and
explicitly blocked from certification by the source gate. They are not in the
adopted eight-fold acceptance window. No adult/youth labels were guessed.

## Database hash resolution

The current raw DATABASE digest is
`656ace9ba714e2ab3c2d9cf136e6ee99f67a9ed0382b4c80f1b9b9912fe66f4d`.
Replacing CRLF with LF in memory reproduces the previously approved digest
`bb3c821b7de85735c9d49baddf695abb1744ee5ba6f398488ad6060802339106`
exactly. This proves the entire difference is line endings, not CSV values.
The fresh existing feeder audit verifies 1,848 database rows against 1,433
retained Planner records and the approved narrower feeders, with zero unexplained
current-field deltas. Evidence: `processed_data/audits/database_byte_identity_20260921/`.

Authority now records the actual raw digest and preserves the older build digest.
The explicit stale-manifest blocker describes byte-level drift; it does not
pretend a rebuild occurred. DATABASE, canonicals, long truth and runtime were
not changed. Historical truth remains canonical/long, never DATABASE.

## Repeated samples and pool identity

The scorer previously collapsed distinct source pools and counted multiple
forecasts against the same official outcome. Repairs are in the existing
projection, scorer and acceptance reporter:

- Preserve source-labeled youth/adult pools for Dedicated Hunter, general deer,
  antlerless and turkey. Youth preference overlays are not random-only youth elk.
- Retain the main OIL or Sportsman owner when its same-lane fallback also exists.
  This follows the fallback-only-when-primary-is-absent contract. Even a blank
  main forecast remains blank; probability magnitude and target results never
  select the winner. Exact repeated final records count once.
- Retain a per-row resolution ledger with original frozen row numbers, complete
  score keys and algorithm status. No frozen forecast is deleted or edited.
- Reject unresolved forecast collisions and repeated acceptance keys instead of
  choosing whichever result makes the error smaller. Report youth pools separately.
- Recheck actual-record collisions too; equal keys alone are not numeric parity.

`audit_output_real_final/identity_reconciled_rescore_20260921_v4/` is the full
nine-fold source-pool repair candidate. V1 stopped at an additional Sportsman
fallback collision. V2 resolved OIL/Dedicated Hunter but exposed broader youth
pool collapsing; it remains superseded diagnostic evidence.

V3 separated the broader youth pools. Its final actual-key audit found 23
apparent conflicts, all in the 2026 diagnostic. Twelve were explicitly adult
versus youth CWMU Turkey rows. V4's first fix matched an explicit CWMU design,
but these endpoint records use the generic MAX_WEIGHTED_SPLIT design and are
identified by the resolved CWMU family. The final fix uses that existing family
identity as well; its 2026-only rescore is retained separately in
`audit_output_real_final/identity_reconciled_2026_cwmu_fix_20260921_v5/`.
The other eleven
pair a zero-applicant, zero-award, no-probability display row with a populated
Turkey observation. They remain in the source ledger as empty displays, not
conflicting observed outcomes. Missing counts, awards without applicants and
conflicting populated values still fail the numeric conflict check.

The two unresolved populated source dimensions are DB1592 Nonresident point 3
and DB1630 Nonresident point 2. Neither is assigned an adult/youth label by this
repair. The remaining 528 unresolved rows consist of 518 empty draw displays
and 10 extended-archery reference records; they are not additional probability
samples. The source gate remains explicit, not inferred from statewide totals.

## Next confirmed owning-feed defect

`_youth_draw_pool_for_row` in the existing family runner uses the word `doe` in
a generic shared label to select pronghorn, even when `species` says Deer.
Regression tests reproduce this with `Youth Antlerless/Doe Reserve` and with
`Youth antlerless doe deer`. Exact source species must outrank this shared
label. The owner fix was applied after the frozen review completed; the four
new regression cases now pass, along with the existing youth/classifier checks
(37 focused tests). This is an output routing correction, not permission to substitute adult
odds for youth odds or to fill pending youth probabilities. Frozen scoring
evidence must remain separate from any subsequent owner repair/rebuild.

## Broader verification limitation

Final combined focused regression suite: 114 passed. Changed-file diff checks
and Python compilation pass. The project-memory check now passes all 151 checks and the public-manifest guard
passes. The broad npm test reaches an existing catalog/foundation mismatch:
generated catalog 1,471 versus broad foundation 1,848. The broad foundation
includes historical/reference records, so this needs an exact eligibility/code
comparison rather than a replacement hardcoded count. No catalog/test threshold
was changed during this scoring repair. A separate older Bear source-lineage
test expects a retained-PDF provenance label while the scorer now resolves the
same subtype from canonical truth; that assertion was not weakened.

## Coverage is evidence, not a target count

The gap classifier now uses the same exact-code boundary as the frozen scorer.
It does not inject current Bear aliases into historical lane matching.
Existing antlerless no-transition blanks are independently checked against
source-only program/residency transitions. Dedicated Hunter blanks are also
checked against the existing three-year expiring-enrollment requirement.
Status text alone cannot excuse a gap. Unsupported or missing model outputs
remain blocking; newly separated youth records may expose additional gaps.

## Source gate and Bear boundary

The retained v3 source-mapping audit is historical evidence, not today's label
count. Later exact-parent recovery and the fresh 2026 endpoint audit supersede
its unresolved count without forcing unknown youth dimensions. The 1,243
historical aggregate totals and 705 ratio-whitespace differences remain
separate from missing point rungs. DB0008 reference records and Sportsman
BR1000 are not public Bear hunting quotas.

All 11,781 source-verified zero-success observations remain in scoring-only
projections. Empty-applicant rows remain unscored. A past zero-success observation
does not make future probability zero. Future blanks must be decided from
source-year evidence, never by inspecting whether next year's applicants appear.

The corrected Bear foundation replay is retained, not restarted or overwritten.
Its owner is `engine/utah_draw_predictive/bear.py`; there is no second
`engine/utah_bonus_predictive/bear.py` to invent. No pursuit rows are manufactured
to reach 400. Both bonus and regular winners leave the returning cohort; the
regular component is not a substitute for total public awards in a bonus design.
Existing same-program/residency modeling is preserved. The old 0.99 ceiling
still requires the retained pre-ceiling certainty audit and cannot certify Bear.

No registry update, staging, commit, push, R2 upload or deployment is authorized
by this diagnostic. The four-core `adr-0006-2200616ce0b9` production registry is
unchanged. Candidate metrics do not override unresolved source/pool gates.
