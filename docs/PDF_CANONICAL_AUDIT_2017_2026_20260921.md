# Official-source verification, 2017-2026

Local audit completed September 21, 2026. **Full verification remains BLOCKED;
this is not a prediction-accuracy test or a certification/promotion decision.**

## Evidence and measured results

- Verifier: `engine/utah/quality/verify_all_failing_engines_pdfs.py`.
- Full report: `processed_data/2026_all_species_all_years_2017_2026_audit.json`.
- Requested run log: `processed_data/2026_audit.log`.
- Separate CSVs with the same report prefix retain files, canonical sources,
  cell differences, year/scope coverage, and manifest references.
- Download checks: `processed_data/2026_official_pdf_fetch_audit.json`.
- Tests/backups: `audit_output_phase1_candidate/all_pdf_verification_20260921_v1/`.

The scan inspected 675 PDF paths, representing 458 unique measured hashes. No
unreadable or inventory-integrity failures were found. The refreshed raw inventory
contains 876 entries, not 876 PDFs: 572 PDFs, 166 CSVs, 137 JSON files and one TXT.
The broader scan also includes retained raw-PDF and canonical parent paths.

It matched 309,644 canonical rows and compared 3,075,715 cells. These comparisons
include printed success ratios as well as counts. Every year from 2017 through
2026 is represented. There are 97 fully matched source groups out of 171; a
source group is a year/scope/source-label combination, not a unique report.

**No unexplained applicant or permit-count difference was found in matched rows.**
This does not assert parity for unmatched rows or prove complete historical scope.

## Interpretation of the strict audit flags

| Measured flag | Review of the retained differences | Consequence |
| --- | --- | --- |
| 705 `VALUE_MISMATCH` entries | All are success-ratio whitespace differences; removing whitespace makes every pair equal, e.g. `1in1.0` / `1 in 1.0`. | They are raw transcription-format differences, not changed odds or applicant counts. The strict report preserves them unchanged. |
| 14 `DOCUMENTED_SOURCE_DISPLAY_CARRYOVER` entries | Seven printed total cells and seven ratios match the documented zero-applicant/zero-component 2020 anomaly signature. | Raw differences and canonical normalization remain visible; no new source correction was made. |
| 1,243 `PDF_ROW_NOT_IN_CANONICAL` entries | All are 2017 `hunt_total_draw_result` rows. None is a missing point-rung row. | Reconcile summary-row scope deliberately; never add totals to point-row awards and double-count supply. |
| 241 historical `UNVERIFIED_LAYOUT_OR_KEY` entries | 154 Big Game hunt totals and 87 Sportsman records. | Complete the specific total/Sportsman layout checks; do not describe ordinary historical point ladders as missing. |
| Remaining 2026 unresolved groups | Legacy PDF labels, endpoint groups without direct current row linkage, and explicitly non-PDF Planner reference rows. | Review exact archived parents and raw endpoint parity. Missing legacy PDF paths do not mean all equivalent official data is absent. |

The existing `canonical_parent_source_mapping_2018_2026.csv` contains prior
endpoint lineage work. That prior mapping was not silently treated as a fresh
numeric pass. It remains relevant evidence for the next exact-key reconciliation.
The 18 absent matrix scopes are **publication/program review items**, not proof
that 18 required reports are missing. Source layouts and program publication
changed across years; a universal filename or report-count expectation is invalid.

## 2026 official sources

DWR's [Big Game page](https://wildlife.utah.gov/biggame), under "Hunt drawing
results and drawing odds," explicitly routes 2026 onward to UtahDraws and earlier
years to the historical archive. Both official odds indexes were read successfully.
They exposed no 2026 PDF links during this run. Each of the four PDF URLs supplied
in the template returned HTTP 404. No HTML error response was saved as a PDF.
The requests, response codes, final URLs and check timestamps are retained.

The directly linked 2026 canonical rows were compared to raw retained JSON, not
merely to flattened CSVs or locally designed PDFs:

| Raw endpoint | Matched rows, including adult/youth where present |
| --- | ---: |
| Antlerless deer | 244 |
| Antlerless elk | 1,493 |
| Antlerless moose | 80 |
| Doe pronghorn | 313 |
| Ewe Rocky Mountain bighorn sheep | 14 |
| Dedicated Hunter deer | 279 |
| General-season buck deer | 1,722 |
| **Total** | **4,145** |

All 20,725 numeric-field comparisons in these directly linked rows match, including
explicit zero regular awards. Exact hunt/residency/point/youth keys are preserved.
Of 32,834 total 2026 canonical rows, the remaining 28,689 were not freshly
numerically certified by this direct-link check. Some are non-draw references;
others need the retained lineage crosswalk applied and validated. Do not interpret
the unmatched population as missing official results or failed predictions.

## Current identity and safety boundary

`DATABASE.csv` contains 1,848 distinct codes. The named official hunt-master file
selected by the verifier contains 1,288. These are different catalogs/scopes; code
overlap is contextual, not historical numeric truth or current-site eligibility.
The figure 418 belongs to the earlier antlerless subset, not the full database.
Historical canonicals and the canonical-derived long file remain prediction truth.

All frozen protected inputs were unchanged during the run. No canonical,
DATABASE, probability engine, certification registry or runtime was edited.
Nothing was staged, committed, pushed, uploaded or deployed. The pre-existing
DATABASE raw-hash/stale-build project-memory failures remain unwaived.

The source-download scripts found 59 Big Game and 18 Bear/Turkey download targets
already present; zero were overwritten or newly downloaded. Their prior logs and
the pre-refresh inventory were retained before the requested refresh.

## Verification and next work

The final isolated suite passed 24 tests, including real-source resolver checks,
missing/unreadable source handling, dynamic counts, explicit zero awards,
rotated PDF columns, endpoint youth separation, HTML rejection, and a complete
report-generation regression test. An initial audit crashed in difference-report
serialization after reading the PDFs; the collision between document identity and
source cell value was repaired, tested, and the full run was repeated successfully.
The completed verifier returned exit 1 for its documented BLOCKED result, not an
exception. Its counts come from actual inputs, never fixed row/species fallbacks.

Next: resolve the outstanding total/Sportsman layouts and exact 2026 parent links;
then distinguish documented formatting/scope differences from genuine missing
numeric evidence in the gate. Do not rewrite truth or tune engines to satisfy
format-only flags. Prediction acceptance and release remain separate workflows.

To preserve this completed audit, use a fresh output directory on the next run:

```powershell
python engine/utah/quality/verify_all_failing_engines_pdfs.py --out-dir audit_output_phase1_candidate/all_pdf_verification_next
```
