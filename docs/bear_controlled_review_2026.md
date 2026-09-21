# Bear controlled review — 2026-09-20

Later demand experiments and eight-fold final-calculation results are in
`docs/bear_demand_forecast_review_2026.md`. None passes; the five-fold evidence
below is retained unchanged and does not authorize a release.

**Result: source-boundary and final-calculation repairs implemented; five
historical comparisons completed; Bear is NOT certified. DO NOT PROMOTE.**

This review supersedes the earlier statement that no new PDF-first folds had
been executed. It does not supersede the frozen four-core production release.

## Implemented repairs

- All seven La Sal/Dolores Triangle hunting codes start prediction history at
  the effective 2026 split. No parent-stack transfer, no duplication across
  children, and no pre-split pooled retention/arrival calibration. A 2027 test
  proves adding or changing pre-split demand cannot change the forecast.
- The original La Sal codes remain available to their historical, pre-split
  folds. Restricted pursuit remains separate and does not inherit the hunting
  boundary reset. Other reviewed pre-draw identity changes reset history too.
- Program/residency calibration stays separate. Conditional probability for
  an applicant is no longer incorrectly zero solely because the model rounded
  that point cell's demand to zero. Unsupported point/predecessor histories
  instead remain `NO_TRANSITION_EVIDENCE` with blank probability.
- The owner recognizes fresh canonical program evidence without consulting a
  later report. R/NR expansion requires exact reconciliation of all eight
  published lane values. Aggregate `All` reuse, hunt-total addition,
  conflicting duplicates and unreconciled award components are prohibited.
  Identical point duplicates count once. Both max/bonus and regular/random
  winners leave their own program's ladder; pursuit does not use hunting
  point purchases or infer entrants from OTC products.
- Drawing quotas use exact immediately prior canonical program/code/residency
  awards, explicitly `SOURCE_YEAR_CANONICAL_AWARDS_PROXY`, not target DATABASE
  permits or an older missing-lane fallback. For 2026 split codes,
  `forecast_quota_proxy` is blank. Their requested `public_permits_target`
  values remain separately marked whole-hunt references, not R/NR allocations.
- Final classification preserves `NO_TRANSITION_EVIDENCE` and clears stale
  probability and projected-line aliases. A split row cannot turn back into a
  generic modeled or availability row during final materialization.
- The final website calculation preserves the Bear family result and cannot
  restore a withheld probability or raise it by re-blending prior winners or
  harvest features. Historical quota metadata identifies the actual source
  year and official report, never the current DATABASE as its origin.
- No yearly canonical, unified truth, production prediction, current DATABASE,
  protected permit/quota field, production certification registry or website
  artifact was overwritten.

## Historical evaluation

Official 2020–2025 PDF extractions were already independently checked against
all printed totals and canonical numeric values. The forecast worker opens
only per-year frozen source extracts, not an all-years file followed by a
filter. Its read guard is installed before model imports. Target actuals are
opened by a separate scoring process only after both family and final files
are hashed. Current DATABASE and harvest-feature reads are prohibited.

Development used 2020→2021, 2021→2022 and 2022→2023. The final two comparisons
were not used to choose or tune the candidate. Candidate experiments retained:

| Development candidate | Hunting MAE | Hunting >25-point error rate | Result |
| --- | ---: | ---: | --- |
| Corrected deterministic cohort, before no-transition gate | 11.745% | 12.466% | Failed |
| Same-lane cumulative stack, before no-transition gate | 11.805% | 12.819% | Failed; not selected |
| Cohort/source-transition uncertainty, 200 iterations | 11.532% | 12.085% | Best tested hunting candidate; still failed |
| Hierarchical cohort/arrival uncertainty, 200 iterations | 12.130% | 13.069% | Failed; not selected |

The no-transition gate changes the scored population, so these percentages are
not a like-for-like proof of improvement. Every intentional blank remains in
the actual-side coverage inventory. No numerical error was relabeled out of
the score because its later quota or applicant count changed.

Final candidate: existing cohort roll-forward, source-transition simulation
mean, 200 iterations, seed 20260701, returning-cohort mode off. The cumulative
option remains experimental and is not the default. All five comparisons use
the same implementation hashes. Import-guard replay v7 reproduces the v6
family and final forecast bytes; it is reproducibility, not a second set of
independent folds or a new untouched holdout.

| Comparison | Hunting scored rows | Hunting MAE (points) | Pursuit scored rows | Pursuit MAE (points) |
| --- | ---: | ---: | ---: | ---: |
| 2020→2021 | 1,217 | 12.110 | 41 | 11.057 |
| 2021→2022 | 1,151 | 10.073 | 48 | 13.672 |
| 2022→2023 | 1,190 | 12.351 | 52 | 16.351 |
| 2023→2024 | 1,193 | 13.278 | 56 | 12.829 |
| 2024→2025 | 1,207 | 13.394 | 56 | 15.165 |

The final `mixed_row` probabilities exactly match the frozen family values.

## Frozen acceptance results

| Gate | Required | Limited-entry hunting | Restricted pursuit |
| --- | ---: | ---: | ---: |
| Independent comparisons | ≥2 | 5 | 5 |
| Scored rows | ≥400 | 5,958 | 253 — fails |
| MAE | ≤10 points | 12.259 — fails | 13.943 — fails |
| P90 absolute error | ≤30 points | 35.414 — fails | 34.767 — fails |
| Errors above 25 points | ≤10% | 13.209% — fails | 18.972% — fails |
| Formal false-certainty flags | 0 | 0* | 0* |
| Unclassified actual gaps | 0 | 0 | 0 |

*The unchanged pre-existing 0.99 ceiling prevents formal 100% forecasts. Before
that ceiling, 214 hunting rows and three pursuit rows are false-certainty
cases. Zero formal flags are NOT proof that demand uncertainty was repaired.

Of 20,942 official target point/residency records, 14,440 have zero actual
applicants, 6,211 are scored and 291 are source-classified gaps: 185 without
point/predecessor applicant evidence, 38 without a positive source-year award
proxy, and 68 new hunt/residency rows without a source ladder. These are retained
in the audit. Restricted pursuit has only **267 scorable official rows total**
in the five-fold window; even perfect forecast coverage cannot satisfy 400.

The 835 over-25-point errors include 156 with a later quota change and 449 with
two or fewer actual applicants at the point. Those categories overlap and
remain scored. The row-level diagnostic preserves source awards, applicant
counts, forecast stack, target awards, source PDF/page and error; it does not
claim quota changes or small samples explain every failure.

## Current inventory and name repairs

The separate current-target diagnostic represents all 99 drawing codes / 198
resident–nonresident combinations plus four non-draw availability records.
All 14 split-code/residency rows are probability-blank. Identity coverage is
not forecast accuracy or certification. The current-target inventory reads
DATABASE only after historical PDF history is frozen and is not a historical
fold input. Its default deterministic diagnostic is not the selected simulated
candidate and is not released.

The isolated 2023 canonical candidate repairs 138 hunt-name cells across six
codes. All other fields compare identically; unaffected records retain their
exact bytes. Candidate SHA-256:
`de4f72acdd04e0df474119b2dc5c3f120edc0f21f8f4fbba1d20ea78a984fbb2`.
The production canonical remains unchanged.

## Evidence and publication decision

All paths below are under
`audits/prediction_release_candidates/bear_program_source_repair_20260919/independent_replay/`:

- `five_folds_final_v6/`: final five source-only folds and hash manifests.
- `release_review_final_v3/`: machine-generated Bear-only registry, frozen acceptance
  review, 835-row error diagnostic, publication gate and release blockers.
- `current_inventory_final/`: write-blocked fresh current identity inventory.
- `retained_reconciliation_final/`: old eight-fold gap classification, preserved
  numeric-error inventory, canonical intake, forward-only split crosswalk and
  isolated LF-byte DATABASE candidate.
- `crosswalk_test_mirror_final/`: isolated four-test run and original-file hash
  preservation, never a rewrite of retained normalized crosswalk evidence.
- `focused_final.xml`, `predictive_final_v3.xml`: regression evidence.

The earlier name-only canonical candidate remains at
`audits/prediction_release_candidates/bear_controlled_review_20260920/preparation_v2/`.
Earlier runs are retained, not overwritten. The new five-fold replay reproduces
the same numeric result with the current owner/classifier/adapter hashes frozen;
it is not five additional independent folds or a new untouched holdout.

Candidate registry: `adr-0006-731a13966798`. Hunting is
`EXPERIMENTAL_NOT_CERTIFIED`; pursuit is `INSUFFICIENT_EVIDENCE`. The public
field gate passes by keeping all 14,603 candidate rows' `certified_p_draw*`
fields blank, with zero unauthorized public probabilities. That is successful
suppression, NOT successful Bear certification or permission to deploy.

The original 20 protected files remain byte-identical. The live four-core
registry `adr-0006-2200616ce0b9` is unchanged. No production files are approved
to change; no R2 upload, website build, deployment, staging or commit occurred.
The corrupt saved Bear/Bison rows were not released or overwritten.

Remaining work is substantive: improve demand prediction against development
evidence and obtain sufficient additional independent pursuit evidence. The
two evaluated holdouts must not be reused as untouched tests after tuning.
Do not raise the sample count by duplicating lanes/folds, merge pursuit with
hunting, relax thresholds, or treat the 0.99 ceiling as the solution.

## Reproduce without touching production

Use a new output directory on every run; existing candidates are not overwritten.

```powershell
py -m py_compile engine/utah_draw_predictive/bear.py
py -X utf8 scripts/audit_bear_controlled_candidates.py --phase folds --central-estimate simulation_mean --iterations 200 --out-dir audits/prediction_release_candidates/bear_recheck_NEW
py -X utf8 scripts/review_bear_controlled_folds.py --folds audits/prediction_release_candidates/bear_recheck_NEW --out-dir audits/prediction_release_candidates/bear_review_NEW
py -m pytest tests/utah_draw_predictive -q
npm run validate:project-memory
npm run guard:public-manifests
```

Known repository limitations remain separate from model accuracy: the nine
pre-existing predictive test failures, an existing mixed saved-data test with
a missing EB3022 row, the two project-memory hash/stale-build failures and the
19 broader V3 failures. These are not waived or silently repaired by replacing
production artifacts.

Final verification: 383 predictive tests passed with the same nine existing
failure identities; 67 focused source/boundary/availability tests passed,
including an active returning-tail regression proving hunting point purchases
cannot alter pursuit. The isolated crosswalk suite passes all four tests.
The requested
11 saved-file coverage tests passed; 11 certification/public-contract tests
passed (the known stale current-registry fixture was deselected only in this
earlier focused run and remains a failure in the complete suite). The mixed subset
has 36 passes and the existing missing-EB3022 saved-data failure. Compilation,
diff checks and the public-manifest guard pass. Project-memory validation still
fails the same two checks; no frozen hash or protected data was changed to
make them pass.

## Retained eight-fold diagnostics and byte-level preflight

All **374** older missing/blank prediction keys now have a source-supported
classification: 254 have no comparable source-year program/residency ladder,
and 120 have zero source-year awards. All eight frozen forecast hashes remain
identical. This classification is a sidecar, not a rewrite or rescoring that
erases errors. The 2,124 over-25-point numerical misses remain in the retained
diagnostic, including 1,072 with zero forecast demand and zero probability.
The older MAEs of 20.594 and 24.375 points remain failed supporting evidence.

Canonical intake is verified at 90/91/97/100/100/96/96/96/97 drawing ladders
per residency for 2017-2025. These are program-separated combined inventory
counts, not proof of individual applicant return or universal lane continuity.

The mirror verifies 96/97/105 source/current rows, 994/1110 permits, four
lineage recodes, three split children and 91 exact matches. It copies exact
inputs and checks original sources AND generated outputs for unchanged hashes.
The test's old BR7324 positive-permit expectation was inconsistent with the
actual blank conservation-reference quota; the assertion now verifies that
blank and its exclusion from the positive-permit inventory. No permit value
or retained crosswalk was changed to make the test pass.

DATABASE current bytes hash to
`656ace9ba714e2ab3c2d9cf136e6ee99f67a9ed0382b4c80f1b9b9912fe66f4d`.
An isolated candidate replacing only the 1,849 CRLF line endings with LF hashes
to the existing verified
`bb3c821b7de85735c9d49baddf695abb1744ee5ba6f398488ad6060802339106`.
All parsed rows and fields are identical. That candidate is **not installed**;
the two project-memory failures remain visible. No validator, verified hash,
production CSV, canonical or four-core registry was changed.

Preservation qualification: the 20-file current-work baseline remains exactly
unchanged, including saved ML predictions at SHA-256
`90cb4f004a5b37349bae3ca264b269d40fe8a5420b6236225fe5a927c5415056`.
The **older** 19-file foundation snapshot instead records that one file at
`17c3ea0861b792378ec6c6943a3461946455b3578862e7c46c402ef3e3311b3f`;
its other 18 files still match. The retained availability-audit baseline
already records the current `90cb4f00...` bytes. LF/CRLF projection does not
explain the older saved-prediction difference. This is a pre-existing snapshot
discrepancy, not a write in this work; no rollback, overwrite or promotion
was performed. See `independent_replay/preservation_snapshot_comparison.json`.

The foundation repair and boundary verification are complete locally. Accuracy
and independent pursuit evidence remain the substantive blockers, not another
availability-filter change. No site build or browser promotion matrix was run
because no website/runtime artifact changed and promotion is expressly barred.

Additional isolated reproduction (choose NEW directories):

```powershell
py -X utf8 scripts/run_bear_crosswalk_isolated_tests.py --out-dir audits/prediction_release_candidates/bear_program_source_repair_20260919/independent_replay/crosswalk_NEW
py -X utf8 scripts/audit_bear_foundation_followup.py --out-dir audits/prediction_release_candidates/bear_program_source_repair_20260919/independent_replay/reconciliation_NEW
py -m pytest tests/utah_draw_predictive/test_bear_foundation_boundary_2026.py tests/utah_draw_predictive/test_bear_pdf_controlled_replay.py tests/utah_draw_predictive/test_bear_pdf_source_boundary.py tests/utah_draw_predictive/test_bear_availability_live_generation.py -q --basetemp=audits/prediction_release_candidates/bear_program_source_repair_20260919/independent_replay/pytest_NEW
```
