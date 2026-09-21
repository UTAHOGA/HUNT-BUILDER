# Bear Quota-State and Random-Outcome Calibration Review

Status: **EVALUATED — NOT CERTIFIED — DO NOT PROMOTE**  
Date: 2026-09-20

## Result

The prior diagnosis was incomplete. A replacement nonresident quota-state
forecast and a post-mechanics random-outcome calibration do not repair Bear.
The latest same-hunt, same-residency official award count is already the best
source-only quota proxy among the reviewed transparent methods. The reviewed
outcome calibration fails validation and worsens the late limited-entry tail.

No default engine behavior, production prediction, registry entry or website
field changed.

## Quota-state comparison

Across 1,412 adjacent lane transitions, and separately across 574 transitions
ending in 2023–2025, the latest same-lane award count outperforms two- and
three-year means/medians, a last-delta trend and a program/residency Markov mode.

| Source-only method | All-transition quota MAE | 2023–2025 quota MAE |
| --- | ---: | ---: |
| Latest same lane | **0.523** | **0.324** |
| Median, last 2 | 0.666 | 0.436 |
| Median, last 3 | 0.763 | 0.537 |
| Mean, last 2 | 0.666 | 0.436 |
| Mean, last 3 | 0.775 | 0.538 |
| Last-delta trend | 0.801 | 0.537 |
| Program/residency Markov mode | 0.644 | 0.357 |

The existing `SOURCE_YEAR_CANONICAL_AWARDS_PROXY` therefore remains the least
error-prone reviewed source-only quota state. This does not make it a current
allocation claim.

## Frozen nonresident calibration candidate

The candidate was selected using source years 2017–2021, then evaluated on
2022. It grouped prior official results by design, residency and five-point
mechanical-probability cells, retained five mechanical-prior observations and
adjusted Nonresident rows only. Target actuals were used only after forecast
construction for scoring.

It did not pass validation. On the later 2023→2024 and 2024→2025 comparisons:

| Design | Baseline MAE / P90 / tail | Candidate MAE / P90 / tail |
| --- | --- | --- |
| Limited-entry hunting | 12.113 / 32.333 / 13.358% | **12.290 / 31.817 / 14.107%** |
| Restricted pursuit | 16.260 / 41.869 / 23.214% | **16.143 / 44.192 / 25.893%** |

Small mean changes do not offset the worse large-error tails. The candidate is
rejected and is not an engine mode.

## Exact-lane transition-median development candidate

A subsequent same-hunt/program/residency-only applicant candidate used the
median of up to three earlier exact-rung adjacent transitions. It used no
statewide purchases, other hunt, other residency, current database or target
actual. It was stopped before the late folds because the first six development
folds failed:

| Design | Rows | MAE | P90 | Tail >25 pp |
| --- | ---: | ---: | ---: | ---: |
| Limited-entry hunting | 6,675 | 11.606% | 32.333% | 12.330% |
| Restricted pursuit | 196 | 16.408% | 49.000% | 22.959% |

The opt-in implementation was removed from the owner after the development
failure. Its exact failed forecasts remain retained for audit.

## Correct next conclusion

The current source-only hierarchical applicant model remains the least-bad
reviewed Bear candidate, but it still fails certification. Quota smoothing,
probability-cell calibration and robust exact-lane medians cannot honestly
bridge the remaining error.

## Genuinely unseen 2025 to 2026 official fold

The official 2026 Bear results were subsequently found in the retained yearly
canonical. The 2,814 public Bear point-level rows are confirmed canonical
scorable records: 1,407 Resident and 1,407 Nonresident rows, covering 90
limited-entry codes and the nine reviewed restricted-pursuit codes. The 2025
source-only forecast was frozen before those target actuals were opened.

| Design | Rows | MAE | P90 | Tail >25 pp | Classified gaps | Unresolved gaps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Limited-entry hunting | 1,098 | 13.045% | 38.596% | 14.845% | 126 | 0 |
| Restricted pursuit | 60 | 19.726% | 57.591% | 25.000% | 3 | 0 |

Both designs fail the unchanged accuracy gates on the genuinely unseen year.
There are no false guarantees. Combining this fold with the prior eight
source-only adjacent folds produces:

| Design | Folds | Rows | MAE | P90 | Tail >25 pp |
| --- | ---: | ---: | ---: | ---: | ---: |
| Limited-entry hunting | 9 | 10,176 | 11.673% | 32.879% | 13.001% |
| Restricted pursuit | 9 | 368 | 16.434% | 44.444% | 21.739% |

Restricted pursuit also remains below the 400-row minimum. The unseen fold
therefore confirms that Bear must remain not certified; it does not support a
calibration or labeling exception. The next defensible new evidence is the
next official draw year or a newly discovered official pre-draw
resident/nonresident allocation source. Existing historical outcomes must not
be repeatedly tuned until they pass.

## Evidence and preservation

- Quota/outcome review:
  `audits/prediction_release_candidates/bear_quota_outcome_calibration_20260920_v1/`
- Transition-median development failure:
  `audits/prediction_release_candidates/bear_lane_transition_median_20260920_dev/`
- Genuinely unseen 2025 to 2026 fold:
  `audits/prediction_release_candidates/bear_2025_to_2026_new_official_fold_20260920_v1/`
- All 20 protected files are byte-identical.
- No truth, canonical, `DATABASE.csv`, saved prediction, registry, R2 object or
  website artifact changed.
- Nothing was staged, committed, pushed, uploaded or deployed.
