# Official 2026 refresh and frozen-forecast rescore

Status: **SCORING PREPARATION REPAIRED; LOCAL DIAGNOSTIC, NOT CERTIFICATION**.

## Fresh official source comparison

Used the existing `scripts/pull-utahdraws-draw-odds-2026.py`, redirecting only
its output directories to a new review folder. No historic snapshot overwritten.
Downloaded only license year 2026: 33 advertised groups, zero failed downloads,
1,094 hunt records and 22,304 flattened rows. These are source-record counts,
not current eligible-hunt counts.

All 29 groups shared with the retained September 2 snapshot have identical
parsed JSON responses, including their values and array order. The four extra
Crane/Grouse/Swan groups are retained as raw download evidence only, not added
to canonicals or this model's scoring scope.

The new official files were compared directly with the canonical, without
opening a UOGA-generated PDF: 21,806 exact source-row matches, 109,030 count
cells, zero count mismatches in matched records, and zero disagreements between
populated observed probabilities and their count ratios. The same 11,781
positive-applicant, zero-award records have blank probability in the original
canonical. Unmatched display rows, unresolved source pools and references are
not declared verified. Their underlying counts were not changed.

Fresh evidence:

- `audit_output_phase1_candidate/official_utahdraws_fresh_20260921_v1/json/`
- `audit_output_phase1_candidate/fresh_2026_canonical_comparison_20260921_v1/`

DWR's [current draw-system explanation](https://wildlife.utah.gov/draw) says
static draw-odds PDFs are no longer posted; the official platform offers
printable PDFs of filtered results. The [Big Game PDF archive](https://wildlife.utah.gov/biggame/odds)
currently lists originals through 2025. Checked during this task. A platform
print/export can be retained as a source-view copy; our generated UOGA PDF is
not the authority for this repair.

## Narrow scoring repair

The existing adapter now accepts `--verified-outcome-audit`. It verifies the
frozen canonical hash, raw endpoint hashes, exact residency/point/youth identity
and numeric equality again before deriving a missing observed frequency.
Positive, finite whole applicant counts and complete, consistent award counts
are required. Existing probabilities and printed ratios are preserved. Zero
applicants, incomplete counts, inconsistent components, reference/allocation
records and unverified identities do not acquire an outcome.

Exactly 11,781 records gained observed zero outcomes **in the separate scoring
projection only**. No count/ratio/identity field changed. No row added or removed.
Observed zero is not a prediction about any future applicant.

The first local replay v1 exposed an overly broad REFERENCE substring guard
that also rejected PREFERENCE. Corrected it to complete design tokens and added
a regression. That v1 remains retained, superseded by v2; its scores must not
be used as the completed correction.

## Completed v2 rescore

`audit_output_real_final/verified_outcome_rescore_20260921_v2/`

All nine existing physical folds were rescored with the original frozen
forecasts. The eight earlier score CSVs are byte-identical to their originals.
All nine forecast projections are byte-identical; only the 2026 observed-outcome
projection changed. No engine rebuilt or retuned.

Single-actual-row audit for 2025-to-2026:

| Measure | Original | Corrected |
| --- | ---: | ---: |
| Scored actual rows | 5,893 | 17,149 |
| Mean absolute error | 16.2344 pp | 7.7002 pp |
| Positive-applicant rows missing a forecast value/record | 555 | 914 |
| Zero-applicant rows kept unscored | 12,101 | 12,101 |

Newly observed zero outcomes expose more forecast gaps; those gaps were not
deleted to improve accuracy. This remains the existing scorer's single-row
selection policy, not an approval of conflicting forecast identities.

For continuity, the original prediction-row report is also retained: 19,831
scored prediction rows, MAE 7.2269 pp, P90 19.9 pp, 8.3859% tail above 25 pp,
and zero reported false guarantees. **Do not treat 19,831 as independent actual
samples:** it includes 2,682 repeated structural scoring keys (2,547 OIL and
135 Dedicated Hunter). The old 2026 report already had 392 such groups; restoring
zero outcomes exposes additional existing forecasts. Repeated structural keys
also occur in earlier folds. No duplicate forecast was selected, discarded or
edited to improve this result. Exact final key/pool provenance must be reconciled
before accepting design sample counts or certification.

Projection integrity and all repeated keys are retained in
`projection_integrity_and_duplicate_review.json` and
`repeated_structural_scoring_keys.csv`. The nine-fold combined reports and
separate adopted eight-fold window remain under `review/`, diagnostic only.

## Verification and boundaries

- 46 focused tests passed, including source/hash rejection, finite/complete
  counts, zero versus missing, preference versus reference, residency isolation,
  and unchanged historical adapter/report behavior.
- Projection integrity: PASS; original row counts and non-probability cells
  preserved; eight earlier scoring CSVs identical; all forecast projections identical.
- Protected engine, canonical, long-truth, DATABASE and original forecast/report
  hashes are checked in the review's protected-file verification.
- The two existing project-memory DATABASE/stale-build failures remain unwaived.
- No canonical/long truth, DATABASE, engine, normal runtime, certification
  registry or production artifact changed. Nothing staged, pushed or deployed.
