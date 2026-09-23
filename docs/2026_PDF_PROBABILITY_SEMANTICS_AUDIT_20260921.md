# 2026 PDF/count/probability audit

Status: **LOCAL DIAGNOSIS; NO TRUTH OR FORECAST REWRITE; NO CERTIFICATION**.

The 2026 diagnostic has a demonstrated outcome-normalization omission. Do not
use the existing 2025-to-2026 scores or descriptive nine-fold total as a final
acceptance result until this is repaired and rescored. Earlier eight-fold
artifacts are preserved; this finding alone does not recalculate those scores.

## Measured evidence

Fresh audit: `audit_output_phase1_candidate/2026_pdf_probability_semantics_20260921_v1/`.
The summary records measured SHA-256 hashes for the canonical, source endpoints,
PDF and audit implementation. All inspected inputs remained unchanged.

- 32,834 canonical records inspected.
- 21,806 exact endpoint rows match across 109,030 populated count cells.
- No differences between populated observed probabilities and awards/applicants
  in those matched records (tolerance 0.0000001).
- **11,781 source-verified positive-applicant, zero-award point records have no
  probability recognized by the current scorer.** This is a canonical-record
  count, not a claim that all records are separate eligible scoring keys.
- 10,236 records lack an exact endpoint identity match; the earlier source-pool
  audit identifies these as empty display rungs. This audit does not verify
  their zeros or turn them into observations. Other unresolved pool/reference
  records remain unresolved, rather than being forced into a match.

Missing zero-outcome records include 5,524 LE, 2,311 OIL, 2,139 CWMU and
362 Premium LE records. Other families are itemized in the audit summary.

## Actual PDF inspection

Inspected the complete Big Game PDF pages 237, 761 and 762 visually and extracted
each resident/nonresident table independently, checking its six column headers.
The file is the 932-page September 2 topo/youth-residency-fixed UOGA reproduction,
not an original DWR-authored PDF. It shares its upstream UtahDraws data with the
endpoint records, so PDF agreement is presentation validation, not independent
authentication of the official source capture.

All **97 populated point rows / 388 count cells** on these pages agree with the
canonical. Three blank display rows remain explicitly distinct from zero counts.
This is a three-page layout/cell check, not a complete visual audit of 932 pages.

| Hunt / residency / points | Printed applicants | Max/bonus | Regular | Total awards | Printed ratio | Current scoring treatment |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| DB1016 / Nonresident / 0 | 12 | 0 | 0 | 0 | N/A | Missing actual probability; omitted |
| DB1016 / Nonresident / 10 | 1 | 0 | 1 | 1 | 1 in 1.0 | Included |
| MB6011 / Resident / 28 | 80 | 0 | 0 | 0 | N/A | Missing actual probability; omitted |
| MB6011 / Resident / 29 | 12 | 9 | 0 | 9 | 1 in 1.3 | Included |

The displayed ratio may remain N/A to mirror DWR formatting. An observed
zero-success result is still established by positive applicants and explicit
zero awards. This does **not** mean that a future applicant's chance is zero.

## Located failure

`project_legacy_canonical_for_blind_scoring.expand_actual` calculates an outcome
from counts when expanding older combined-residency rows. Already separated
2026 rows are appended unchanged. `actual_probability_and_counts` in the final
scorer reads probability fields but does not derive a missing probability from
otherwise complete official applicant/award counts.

The saved 2025-to-2026 actual-ladder audit consequently marks **11,655 positive
applicant rows** `do_not_score_missing_actual_probability`, including all
5,524 LE and 2,311 OIL cases above. Of these omitted rows, 11,256 already have
forecast values. This normalized scoring population is not the same counting
unit as the 11,781 raw canonical records. The omission favors retaining rows
with winners; its precise effect on error metrics requires a fresh rescore.

This explains a substantial coverage defect without demonstrating a numeric
column shift or applicant-behavior failure. It does not explain every forecast
error, repair existing forecast gaps, or establish that every 2026 source scope
is complete.

## Narrow next repair

In the existing scoring projection/normalizer, derive an observed outcome only
from a verified public-draw point row with positive applicant count and explicit,
consistent award counts. Preserve 0 awards as an observed zero; keep missing
counts, zero-applicant display rows, ambiguous identities and reference rows
unscorable. Preserve raw printed ratios and counts. Do not edit prediction
probabilities, permit mechanics or protected truth to improve a metric.

Then rescore the frozen forecasts against a separately retained corrected
actual projection. No engine rebuild is needed to isolate this evaluator
effect. Preserve old reports and identify superseding reports explicitly.

Four audit regressions pass: explicit zero outcome; unresolved source rejection;
empty/missing count rejection; existing zero/reference exclusion. No truth,
DATABASE, forecast, runtime, registry or production files were changed. The
project-memory gate still has the two pre-existing DATABASE/stale-build failures.
