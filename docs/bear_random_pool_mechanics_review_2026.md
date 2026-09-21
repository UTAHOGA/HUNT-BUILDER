# Bear Random-Pool Mechanics Review — 2026

Status: **CORRECTNESS REPAIR VALIDATED LOCALLY; ACCURACY FAILED; DO NOT PROMOTE**

## Rule resolved

Utah assigns one random number to an application and one additional random
number for every bonus point. The application retains its lowest number. When
more than one random-pool permit is available, the winning applications are the
applications with the lowest retained numbers; the same application cannot win
twice.

For Bear, this is an application-ranking problem without replacement. It is not
repeated sampling of total ticket share with replacement. Black Bear group
applications are not accepted, so party-size or group-ticket logic does not
belong in the Bear probability calculation.

The Bear owner now models each application's retained minimum directly. After a
monotone transform, the retained minimum is an exponential clock with rate
`points + 1`. The probability for a focal application is the probability that
no more than `random_permits - 1` other application clocks finish first. The
multi-permit mixed-weight case is evaluated deterministically with 16-node
Gauss-Legendre quadrature; the one-permit and equal-weight cases use exact
closed forms.

Sanity checks:

- Three applications with weights 3, 2 and 1 and two permits give the
  three-weight application probability `17/20 = 0.85`. The removed shortcut
  returned `0.75`.
- Three equal-weight applications and two permits give each application
  probability `2/3`.
- Max-pool winners are removed before the random-pool calculation.

## Source-only final-calculation result

The exact final website probability calculation was evaluated across the same
eight adjacent source-only folds and the same score keys used by the retained
Bear demand review. The candidate was frozen before scoring. It read official
2017–2025 history, source-classified every gap and did not read `DATABASE.csv`
as historical truth.

| Design / residency | Rows | MAE | P90 error | Error over 25 pp |
|---|---:|---:|---:|---:|
| Hunting — pooled | 9,078 | 12.062 pp | 35.464 pp | 13.384% |
| Hunting — resident | 7,970 | 10.744 pp | 30.966 pp | 11.631% |
| Hunting — nonresident | 1,108 | 21.541 pp | 70.000 pp | 25.993% |
| Pursuit — pooled | 308 | 15.458 pp | 37.581 pp | 22.078% |
| Pursuit — resident | 197 | 11.218 pp | 28.063 pp | 14.721% |
| Pursuit — nonresident | 111 | 22.981 pp | 47.189 pp | 35.135% |

The preceding retained shortcut scored hunting at 12.038 pp MAE and pursuit at
15.245 pp MAE. Correcting the mechanics therefore slightly worsened the
forecast scores. The old shortcut was accidentally compensating for an
over-optimistic forecast in thin lanes; it was not the official draw rule and
must not be retained as an accuracy adjustment.

The nonresident error is not confined to one anomalous year. Limited-entry
nonresident MAE ranges from 17–28 pp in every held-out year; restricted-pursuit
nonresident MAE ranges from 18–28 pp. The clearest calibration failure is the
upper forecast range: nonresident hunting rows predicted between 50% and 75%
average 59% predicted versus 22% realized, while rows predicted above 75%
average 96% predicted versus 54% realized. Recurring high-error hunting codes
include `BR7110`, `BR7201`, `BR7101`, `BR7114`, `BR7203` and `BR7104`; pursuit
includes `BR1008`, `BR1010`, `BR1011` and `BR1012`. This is evidence for a
thin-lane high-probability calibration/quota-state review, not a reason to
change the official weighted-random mechanic.

The hindsight-only mechanics diagnostic, which supplies actual next-year
demand and actual pool awards and is never used to forecast, improved under the
correct rule:

| Design / residency | Removed shortcut MAE | Correct mechanic MAE |
|---|---:|---:|
| Hunting — pooled | 7.078 pp | 7.027 pp |
| Hunting — nonresident | 14.127 pp | 14.031 pp |
| Pursuit — pooled | 8.465 pp | 8.065 pp |
| Pursuit — nonresident | 14.366 pp | 14.064 pp |

That diagnostic verifies the direction of the mechanics correction while also
showing that substantial nonresident error remains even with perfect demand
and award-count hindsight.

## Coverage and safeguards

- `22,057` family/final rows agree on the final probability calculation.
- `9,386` official rows are scored; `666` missing forecasts have one retained
  source classification each; unresolved gaps are zero.
- The 0.99 display ceiling is unchanged. The uncapped audit still finds 313
  hunting and 10 pursuit false-certainty cases; the ceiling is not counted as a
  model repair.
- All 20 protected truth, current-catalog, registry and saved-production files
  are byte-identical before and after the candidate.
- No production output, certification registry, R2 object or website was
  changed.

## Decision

Bear remains **NOT CERTIFIED** and the candidate remains **DO NOT PROMOTE**.
The corrected mechanics are retained in the local owner because they implement
the official rule, but they do not pass the frozen accuracy gates. Hunting
fails MAE, P90 and tail gates. Pursuit fails MAE and tail gates and remains below
the ordinary 400-row evidence minimum. Neither design qualifies for the
limited-evidence label because the unchanged accuracy thresholds still fail.

The next repair must focus on the nonresident thin-lane probability contract:
current quota/pool allocation uncertainty, the difference between expected
weighted-random probability and one realized annual outcome, and recurring
hunt/year/residency failure groups. It must not restore the inaccurate
with-replacement shortcut, invent Bear group applications, or tune applicant
demand again without a newly demonstrated demand defect.

## Official source anchors

- Utah DWR bonus points and draw procedure:
  <https://wildlife.utah.gov/?Itemid=446&catid=125&id=519&option=com_content&view=article>
- Utah DWR group-application eligibility:
  <https://wildlife.utah.gov/licenses/groups>
- 2026 Utah Black Bear, Cougar and Furbearer Guidebook:
  <https://wildlife.utah.gov/guidebooks/black-bear-cougar-furbearer-guidebook.pdf>
- Utah Administrative Rule R657-62:
  <https://wildlife.utah.gov/?catid=0&id=85>

## Retained evidence

- Passing operational candidate:
  `audits/prediction_release_candidates/bear_random_pool_mechanics_20260920_v2/`
- High-precision hindsight comparison:
  `audits/prediction_release_candidates/bear_random_pool_mechanics_20260920/hindsight_exact/`
- Operational 16-node hindsight comparison:
  `audits/prediction_release_candidates/bear_random_pool_mechanics_20260920/hindsight_exact_q16/`
- Superseded performance attempt:
  `audits/prediction_release_candidates/bear_random_pool_mechanics_20260920_v1/`
