# Antlerless phase workflow: measured repair and release decision

Date: 2026-09-21. Status: **LOCAL ENGINE REPAIR / NOT CERTIFIED / DO NOT PROMOTE**.

## Follow-up: direct PDF cells and explicit-zero normalizer

Latest evidence superseding the paths below:
`audit_output_phase1_candidate/pdf_cells_zero_regular_20260921_v1/`.
All new forecasts, extracts, scoring outputs and isolated rerun test outputs are
inside that directory. Earlier reviews are retained.

The hash-verified PDF is the 2024 adult antlerless report despite its legacy 2025
folder placement. Independent pdfplumber line extraction (not the canonical's
PyMuPDF table parser) matched all 198 hunt pages / 3,960 point-and-total rows,
31,680 applicant/bonus/regular/total cells and 7,920 printed ratios. All page
references match. Five species-summary pages are explicitly excluded from
hunt-level truth. Zero numeric/ratio mismatches, duplicate keys, missing rows or
unparsed numeric hunt lines. Representative pages 2, 101 and 203 were rendered
and visually checked. This verifies this report, not the other years or youth.

Five new regression failures exposed remaining numeric-zero loss in collapsed
residency normalization and conflicting legacy drawn values in explicit lanes.
The shared normalizer now retains zero and prioritizes explicit regular permits.
There is no new probability model, quota rule, cap or changed acceptance threshold.
The fresh nine-fold replay retains all 8,772 scores and reproduces the earlier
metrics exactly. Current CWMU saved rows still have no numeric forecast. The
unchanged frozen scorer, using its actual supported arguments on 364 saved
DEER/DOE/CWMU/ELK records, scores zero because their prediction-family field is
absent; this is a diagnostic failure to score, not acceptance. Fresh preference
metrics come from the retained exact-year/adult-pool scorer, not that zero-row run.

The first broad test invocation exposed an unsafe existing integration test that
ran the resolver on normal local output paths. It refreshed resolver audit and
reference outputs before isolation was fixed. The final fixture writes copies
under the candidate test directory and verifies original output hashes afterward.
Final isolated result: 93 passed. Protected input/prediction and previous audit
hashes are unchanged; no live deployment or certification registry was changed.

The two existing project-memory DATABASE hash/stale-build failures remain unwaived.

## Scope and preserved evidence

Executed the attached phase workflow using the actual repository owners and
supported tools. Existing candidate and real-final evidence was preserved;
final evidence is under `audit_output_phase1_candidate/engine_verification_20260921_v3/`.
The saved-publication diagnostic and first repair review remain in the sibling
`engine_verification_20260921_v2/` folder; neither was overwritten.
No truth extraction was rerun: `draw_results_long.csv` has every physical draw
year 2017-2026. Year presence is not a new claim of complete source-scope audit.
The retained 2024 antlerless PDF matches the expected SHA-256 beginning `2b1b`,
774,859 bytes and 203 measured pages. That hash belongs to the PDF, not Python.
The resolver remains unchanged at
`1457998b25ed1ee639dda281bd98326f3fe4c327697a367a9d4f916608b252cb`.

## Corrections to the supplied procedure

- The owner is `engine/utah_draw_predictive/preference_antlerless.py`, not
  `antlerless.py`. No replacement engine was created.
- The frozen scorer has no `--families` option. An audit-only filtered copy of
  the unchanged saved predictions was passed with its supported arguments.
  It returned zero scored rows for the 364 selected records. Exit zero is not
  a certification pass. Its broad actual-year/pool join is retained as a saved
  publication diagnostic, not used to override the corrected exact-adult census.
- `gallery/assess_cert.py` and the proposed split-JSON generator do not exist.
  The review reports measured ADR-0006 gates plus the requested stricter >20 pp
  tail check; it does not replace the production certification registry.
- The supplied row counts, five-private-code list, expected MAEs, code-number
  season ranges and Bear PASS label were not treated as measured truth.
  The retained official private-lands feeder has 27 codes; reference-only and
  private-land classification are not interchangeable.
- CWMU is not this preference engine. Saved CWMU rows contain no numeric
  probability, and the special-bonus current builder explicitly disables public
  CWMU materialization. Historical CWMU scores cannot certify those blank current
  records. Public versus private/operator scope must remain independently proven.
- Known 2024/2025 results cannot become untouched holdouts again. The nine folds
  are source-only chronological replays of known years, not newly blind evidence.

## Engine changes

Version `utah_preference_antlerless_v1.4.1` changes only demonstrated contracts:

1. Explicit regular-award values, including zero, take precedence over legacy
   drawn/total fallback fields. The pre-repair canonical audit found zero numeric
   discrepancies for this signature; this is preventive input-contract protection,
   not a claimed repair of thousands of bad official rows.
2. Explicit PRIVATE/LANDOWNER/VOUCHER allocation metadata excludes a row. The
   lane normalizer preserves that metadata. No hunt-code blacklist was invented.
3. Exact-hunt point-band calibration requires two **distinct adjacent year pairs**.
   Previously two rungs in a single year pair could satisfy the two-transition
   test. When that evidence is insufficient, the existing same-program/residency
   rate remains the fallback. No retention formula, point-purchase allocation,
   quota split or Utah draw mechanic was replaced.

Hunt-total exclusion, fractional preference cutoff and same-family/residency
zero-point calibration already existed and remain tested. Existing tail floors
and ceilings were not adjusted to make the metrics pass. Their continued presence
means zero formal false guarantees alone is not evidence of a sound demand model;
near-certainty misses and uncapped full-allocation diagnostics are reported too.

After the initial replay, a numeric-zero (not only CSV string-zero) regression
case was added and repaired. All nine folds were then regenerated with the final
code already loaded. All 81 engine/replay implementation hashes remained unchanged
throughout this final run. It reproduces the initial repaired metrics exactly;
`replay_implementation_verification.json` records the final frozen implementation.

## Full exact-year adult comparison

Forecasts: `audits/prediction_release_candidates/antlerless_distinct_transitions_20260921_v2/`.
Full census: its `full_adult_census/` folder. Forecast generation uses only
canonical history through each source year and final `mixed_row` probability;
target actuals are used only in the subsequent score/diagnosis.

| Design | Scored | Prior MAE pp | Repaired MAE pp | P90 pp | Tail >25 pp |
| --- | ---: | ---: | ---: | ---: | ---: |
| Antlerless deer | 1,181 | 11.637 | 11.620 | 45.555 | 17.528% |
| Antlerless elk | 6,335 | 16.558 | 16.559 | 60.402 | 25.762% |
| Doe pronghorn | 1,256 | 12.410 | 12.408 | 49.900 | 16.640% |

All 8,772 scored rows are retained. The changes do not produce a material overall
accuracy improvement; elk MAE is very slightly worse. The repair enforces evidence
semantics, not a successful new demand model. All designs still fail the frozen
10 pp MAE / 30 pp P90 / 10% over-25-pp tail limits and the requested over-20-pp
tail limit. Formal false guarantees remain zero; near-certainty misses remain
35 deer, 215 elk and 54 doe. No elk subgroup was selected after seeing errors to
obtain an isolated PASS.

The full census retains 2,249 missing forecasts, 576 positive-applicant rows
without official probability and 30,360 zero-applicant rows. The separate gap
report traces missing predictions to source lanes and prior-point counts:
905 have no earlier program/residency transition, 170 have zero prior regular
awards, and 1,174 have no exact prior adult/residency lane. Independent official
source projection confirms those absent lanes; no predecessor or discontinuation
was invented. Numeric misses stay in all accuracy metrics.

Large errors persist even where the source quota proxy equals following-year
awards: 54 deer, 96 doe-pronghorn and 673 elk scored rows exceed 25 pp in that
unchanged-quota subset. These are direct targets for the next demand/cutoff
review, not an excuse to exclude rows or loosen gates. The independent intake
audit compares 44,816 matched engine source rows against the official source
projector and reports zero applicant/regular-award discrepancies.

## Verification and handoff

- New evidence-contract tests demonstrated three failures before the repair;
  all seven now pass, including string and numeric zero.
- Antlerless, historical target-year and CWMU-focused group: 27 passed.
- Shared preference, allocation, classification, Research and mixed-row group:
  43 passed.
- Resolver real-source and failure-path group: 9 passed. Resolver not edited.
- Final combined run: **79 passed**, with retained command, test-file hashes and
  output in `test_results.json` / `test_results.log`.
- The two formerly failing historical-adapter assertions now explicitly require
  blank probabilities, invalid modeled status, one source year and the exact
  NO_TRANSITION_EVIDENCE reason when no adjacent transition exists. Numeric
  modeled rows must still satisfy the original probability contract. No synthetic
  probability was added merely to satisfy a test.
- `check_bear.py` passes 99/90/9 inventory assertions. Its printed PASS and saved
  status note are not statistical certification; Bear remains non-certified.
- The separate project-memory DATABASE raw-hash/stale-build failures remain
  unwaived. Nothing in this review approves a new DATABASE hash.

Required outputs are `cert_report.json`, `species_hunt_breakdown.json`,
`online_hunt_codes.json`, row-level scores, per-hunt/fold metrics, input hashes,
and protected-file comparisons in the candidate review folder. No newly approved
online hunt codes exist because promotion conditions failed. No R2 upload,
website regeneration, deployment, staging, commit or push was performed.

Additional raw-PDF inventory and download-log changes appeared in the working
tree during this task. They were not part of this repair and were left untouched;
the protected input/actual/prediction/resolver/registry/prior-audit hash comparison
still has zero differences. This is not a claim that every file in the dirty
working tree remained unchanged.
