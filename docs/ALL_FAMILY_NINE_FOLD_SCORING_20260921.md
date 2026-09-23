# All-family nine-fold scoring — 2026-09-21

Status: **COMPLETE LOCAL RETROSPECTIVE REVIEW — NOT A RELEASE OR NEW CERTIFICATION**.

**Subsequent audit hold:** the 2026 outcome-normalization audit found omitted
positive-applicant / zero-award observations. The metrics below remain the
original measured results, not corrected acceptance results. See
`docs/2026_PDF_PROBABILITY_SEMANTICS_AUDIT_20260921.md`. Do not promote from the
2026 diagnostic or nine-fold aggregate before a corrected-projection rescore.

The scoring-only v2 rescore is now recorded in
`docs/2026_OFFICIAL_SOURCE_RESCORE_20260921.md`. The original values below are
preserved. Repeated structural scoring keys remain a separate acceptance hold.

All nine physical adjacent-year runs completed successfully using the existing
family engines and final `mixed_row` calculation. Historical inputs are isolated
copies of yearly canonicals through each source year; following-year actuals are
projected and scored after the forecast is saved. Engine settings remained fixed
throughout: deterministic bonus, one iteration; simulation-mean Bear, 200 iterations,
returning-cohort mode off. No applicant-demand repair was selected from these results.

Evidence root: `audit_output_real_final/all_family_nine_fold_20260921_v1/`.
Completed 2017–2019 source folds are directly below that root; completed 2020–2025
source folds are under `parallel/`. The interrupted original `source_2020/` folder
is preserved but excluded from every result.

## Year-by-year results

Errors are percentage points. Tail is the fraction of scored rows with absolute
error greater than 25 points. These are per-row, not applicant-weighted metrics.

| Physical fold | Scored rows | MAE | P90 | Tail >25 pp | Blocking gaps |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2017→2018 | 12,647 | 7.64 | 20.00 | 8.40% | 464 |
| 2018→2019 | 15,172 | 7.63 | 21.45 | 8.73% | 45 |
| 2019→2020 | 16,013 | 8.30 | 25.00 | 9.65% | 0 |
| 2020→2021 | 16,416 | 8.05 | 24.14 | 9.26% | 0 |
| 2021→2022 | 17,497 | 7.67 | 21.13 | 8.72% | 0 |
| 2022→2023 | 17,943 | 7.90 | 23.14 | 9.08% | 0 |
| 2023→2024 | 19,673 | 7.99 | 22.62 | 9.05% | 1 |
| 2024→2025 | 19,432 | 7.75 | 21.53 | 8.81% | 1 |
| 2025→2026 | 6,285 | 16.52 | 50.00 | 20.92% | 36 |
| Combined nine folds | **141,078** | **8.26** | **25.00** | **9.51%** | **547** |

All folds report zero false guarantees at ADR-0006's threshold. This does not
prove uncapped certainty behavior is repaired: the existing Bear probability
ceiling remains, with separate uncapped diagnostics in the controlled v3 review.
There are 13,414 >25-point errors and 5,930 zero-forecast/positive-actual rows;
all remain in the score and have separate diagnostic exports.

## Combined family gates

PASS means the existing numerical and coverage gate calculation passes for this
replay population. It is not a registry change or authority to release.

| Design | Scored rows | MAE (pp) | P90 (pp) | Tail >25 pp | Blocking gaps | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Limited-entry big game | 51,497 | 7.55 | 18.66 | 8.05% | 0 | PASS |
| Once-in-a-lifetime big game | 35,214 | 3.88 | 5.55 | 4.13% | 0 | PASS |
| Premium LE big game | 2,743 | 2.07 | 2.45 | 1.97% | 0 | PASS |
| General-season buck deer | 8,936 | 6.78 | 22.04 | 7.24% | 0 | PASS |
| CWMU big game | 21,437 | 13.03 | 50.00 | 16.11% | 0 | FAIL accuracy |
| Bear hunting | 9,593 | 12.30 | 36.89 | 13.95% | 0 | FAIL accuracy |
| Restricted Bear pursuit | 355 | 15.70 | 41.25 | 22.25% | 0 | FAIL accuracy/sample size |
| Turkey | 515 | 24.38 | 100.00 | 26.60% | 0 | FAIL accuracy |
| Antlerless deer | 1,316 | 13.16 | 58.21 | 16.87% | 70 | FAIL accuracy/coverage |
| Antlerless elk | 6,368 | 11.78 | 49.50 | 16.93% | 289 | FAIL accuracy/coverage |
| Dedicated Hunter | 1,825 | 25.02 | 99.50 | 29.70% | 88 | FAIL accuracy/coverage |
| Doe pronghorn | 1,261 | 15.61 | 69.73 | 21.17% | 71 | FAIL accuracy/coverage |
| Youth general any-bull elk | 18 | 1.75 | 4.26 | 0.00% | 0 | Insufficient sample |
| Unclassified Bear actual subtype | 0 | — | — | — | 29 | Coverage blocker |

The generation inventory contains 16 family labels. Sportsman, antlerless moose,
cougar and youth-turkey emissions are retained there even when no separate
eligible joined population appears in the scoring table. Emission is not
evidence of scorable coverage or acceptance; no sample count is manufactured.

## Important 2026 diagnostic

2025→2026 is retained separately from the adopted eight-fold ADR acceptance
window, while also included in the requested descriptive nine-fold total.
That year's LE score is 2,464 rows / 16.32 pp MAE; OIL is 622 / 19.08 pp;
CWMU is 330 / 57.69 pp. General deer is 1,146 / 6.94 pp. Its blocking gaps
are 29 unclassified Bear subtypes and seven Dedicated Hunter rows.

The lower matched population and worse LE/OIL/CWMU error require source-scope,
key and forecast-coverage review before drawing an applicant-behavior conclusion.
No assertion that the underlying PDF/canonical numbers are wrong follows from
these scores alone. No numerical misses were reclassified out of the score.

## Contracts and limitations

- Every family calls the existing final calculation. Unavailable historical
  runtime prior/harvest blend inputs are explicitly `None`; current DATABASE or
  harvest values are not substituted. This is not proof of complete historical
  website-input parity, especially for non-core blended families.
- The four core designs preserve family probability through the final calculation.
- Physical primary truth inputs exclude future years. No OS-level access audit
  is claimed for this general runner; the separate controlled Bear runner has one.
- These are known retrospective years, not newly unseen holdouts.
- All 20 protected canonical/long/DATABASE/runtime/registry files match the
  pre-run hash inventory. No staging, commit, push, R2 write or deployment.
- Focused final/reporter/availability checks: 29 passed. Broader family suite:
  476 passed / nine existing artifact/expectation failures. `npm test` stops at
  the two pre-existing DATABASE project-memory checks. Public-manifest guard passes.

## Review files

Under the evidence root's `review/` directory:

- `summary.json`: all windows, metrics, caveats and hash-verified final gates.
- `all_years_by_family.csv` and `year_by_year_by_family.csv`.
- `eight_fold_by_family.csv`: adopted historical window, excluding 2026 actuals.
- `family_emission_inventory.csv`: every emitted family, including unscored output.
- `all_scored_rows.csv`, `high_error_rows.csv`, `zero_forecast_positive_actual.csv`.
- `all_actual_gaps.csv` and `all_actual_gap_evidence.csv`: complete gap decisions.
- `false_guarantees.csv`: empty with its schema preserved.
- `protected_file_verification.json`: before/after hashes and zero changes.
