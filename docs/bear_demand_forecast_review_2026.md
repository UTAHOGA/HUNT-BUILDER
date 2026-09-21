# Bear applicant-demand evaluation — 2026-09-20

## Result

**Demand candidates were implemented and scored through the final website
calculation. None passes the unchanged accuracy gates. No production model,
certification label, display filter, saved prediction or registry was changed.**

Cumulative stack improves restricted-pursuit mean absolute probability error
from 15.245 to 14.543 percentage points, and mean absolute error in applicants
above a scored point from 4.763 to 3.662 applicants (about 23%). Its P90 error
is worse. The new joint-transition and adaptive candidates do not beat the
baseline's overall accuracy. They remain opt-in development candidates.

## Frozen final-calculation comparisons

Every candidate uses the same 9,078 hunting and 308 pursuit scored rows across
eight adjacent comparisons, 2017→2018 through 2024→2025. Inputs are reviewed
2017–2019 yearly canonical lanes and independently extracted, canonical-reconciled
2020–2025 PDF lanes. Historical forecasts never read DATABASE.csv. Same-code,
program, residency, pre-draw identity and post-boundary restrictions are unchanged.
All previously viewed results remain development evidence, not unseen holdouts.

| Candidate | Hunting MAE (pp) | Hunting P90 (pp) | Hunting >25pp errors | Pursuit MAE (pp) | Pursuit P90 (pp) | Pursuit >25pp errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Existing source-only baseline | 12.038 | 35.294 | 13.329% | 15.245 | 36.655 | 22.078% |
| Cumulative stack | 12.412 | 37.194 | 13.340% | 14.543 | 40.188 | 18.831% |
| Joint transition scenarios | 12.822 | 38.444 | 16.590% | 16.805 | 39.442 | 26.948% |
| Adaptive cumulative stack | 12.101 | 34.491 | 12.987% | 15.464 | 41.721 | 19.805% |
| Unchanged maximum | 10.000 | 30.000 | 10.000% | 10.000 | 30.000 | 10.000% |

The baseline was replayed twice with identical metrics. These figures do not
replace the earlier five-fold 12.259/13.943 results: that experiment started
source history in 2020. Recent-five-fold subsets of this new experiment retain
earlier comparable evidence and are separately reported in `candidate_metrics.csv`.

Each candidate verifies 22,057 owner-to-final rows, including honest blanks,
through `engine.utah_predictive_mixed.materialize.mixed_row`. No realized-winner
or harvest reblend changes its Bear probability. Every candidate has the same
scored keys and 666 source-classified gaps: 643 hunting and 23 pursuit. Reasons:
120 zero source-year award proxies, 242 absent point/predecessor transitions,
139 absent source lanes, 109 pre-draw boundary changes and 56 one-to-many splits.
Unclassified gaps: zero. No numerical errors were reclassified as gaps.

Formal false guarantees are zero under the unchanged 0.99 ceiling. That is
not an accuracy fix: uncapped false-certainty counts remain 321 for baseline,
392 for cumulative stack and 349 for adaptive cumulative. All errors are retained.

## Changes in the existing owner

- `cumulative_transition_ensemble` forecasts whole cumulative vectors from up
  to three contiguous exact-hunt/program/residency transitions plus two explicit
  persistence scenarios. Both bonus and regular winners leave before unsuccessful
  applicants advance. It averages complete scenario probabilities, not products
  of separately averaged bonus/random components. Measured accuracy is worse.
- `adaptive_cumulative_stack` learns a bounded persistence-versus-advancement
  coefficient from that lane's earlier transitions, with a fixed ridge prior
  and shrunk innovations. Some large hunting errors improve; mean accuracy does not.
- Cumulative modes reject a second arrival model/independent cell noise. Single-year
  history does not fabricate transitions. Both new modes keep all seven 2026
  split codes blank. Existing production/default demand behavior is unchanged.
- The audit driver freezes policy, source, code, identity census, parameters and
  seeds before scoring, seals forecasts before target reads, and retains exact
  implementation snapshots. It can bind a hash-pinned scorer independently of
  a concurrently edited working file.

## Restricted-pursuit limited evidence

Frozen policy/ADR hashes and limits are unchanged. Group integrity, deterministic
resampling, empty-residency and non-independent-rung tests ran before revised
scores. Each uncertainty analysis uses 10,000 PCG64 resamples with seed 20260920,
keeping all point rows and both residencies in a hunt/year together.

The pursuit census has 331 eligible actual rows: 308 scored and 23 classified
gaps. Scored groups comprise 63 hunt/year blocks, nine hunt/regime histories and
eight years, not 308 independent samples. Cumulative-stack pooled MAE 95% intervals:

- Whole hunt/year: 12.81–16.34 pp.
- Whole hunt/regime: 12.65–16.70 pp.
- Whole year: 12.77–16.66 pp.

Resident/nonresident intervals, year/hunt/lane breakdowns and leave-one-year/hunt
sensitivity reports are retained. Cumulative stack has 33 recurring
hunt/regime/residency/metric failures across multiple years. It does not qualify
for the provisional label, independently of the ordinary 400-row requirement.

## Remaining error is not only demand

A separate hindsight diagnostic deliberately substitutes target-year actual
applicants and bonus/random award totals. It is **not a forecast, a theoretical
lower bound, or certification evidence**. With that advantage, pooled MAE is
7.078 pp hunting and 8.465 pp pursuit; nonresident MAE is still 14.127 and
14.366 pp. With actual demand but legitimate source-year quota proxies, pooled
errors are 7.852 and 9.087 pp. “Group” here originally referred to grouped
audit strata, not party applications; Utah does not accept Black Bear group
applications. The application-minimum, without-replacement random-pool rule has
since been implemented and evaluated in
`docs/bear_random_pool_mechanics_review_2026.md`. It does not pass the frozen
accuracy gates. Thin nonresident lanes retain quota/pool and realized-random-
outcome error as well as the genuine forecasting problem. This does not
justify weakening gates or claiming certification is impossible.

## Crosswalk: three new seasonal codes and four recodes

DWR 2026 guidebook page 4 confirms Dolores Triangle was separated from La Sal
Mtns. Pages 73–75 show its three seasonal hunts. Those pages were rendered and
visually inspected; the retained crosswalk gives these exact mappings:

| Current code | Prior code | Meaning |
| --- | --- | --- |
| BR7021 | None | New Dolores spring |
| BR7126 | None | New Dolores summer |
| BR7238 | None | New Dolores fall |
| BR7022 | BR7008 | La Sal spring recode; changed boundary |
| BR7127 | BR7108 | La Sal summer recode; changed boundary |
| BR7239 | BR7208 | La Sal fall recode; changed boundary |
| BR7326 | BR7307 | La Sal multiseason recode; changed boundary |

Seven hunt codes are not seven geographical units. Four have genuine predecessor
history, retained as lineage but not automatically comparable after the boundary
change under ADR-0008. Separately, **two hunts were new in 2025**, BR7237 and
BR7325; they already have 2025 draw records and are not the seven split codes.

Official source: https://wildlife.utah.gov/guidebooks/black-bear-cougar-furbearer-guidebook.pdf

## Evidence and preservation

All paths below are under `audits/prediction_release_candidates/`:

- `bear_demand_forecast_20260920_v1`: baseline, cumulative, joint, grouped
  uncertainty, exact final checks and hindsight diagnostics. Manifest SHA-256
  `fe791e2fa9bbbdb450cf662cb9180a9bb828b8d243e0857f9393aa58da37a1f8`.
- `bear_demand_forecast_20260920_v2`: retained **invalidated attempt**. A concurrent
  scorer edit broke the freeze. Its baseline scores are not accepted evidence.
- `bear_demand_forecast_20260920_v3`: baseline replay and adaptive candidate,
  pinned to the original scorer snapshot. Manifest SHA-256
  `3884c3c3be2c020de1e8f826ca71674b1de8e6221650d0229f11ef73aa3d457a`.

The first uncertainty report encountered a NumPy-integer JSON serialization
error after scoring. The reporter-only fix is regression-tested; frozen models
and numerical forecasts were unchanged. A subsequent concurrent scorer reset
removed `--exact-codes-only`; that narrow source-boundary option was restored,
then a fresh readback found it removed again by a concurrent writer. The final
working-file guard test fails. V3 already used its pinned scorer independently;
do not rewrite the frozen evaluation or repeatedly overwrite another writer.
Stable integration requires single-writer coordination on the shared scorer.

Verification: 31 pre-score candidate/policy tests pass; compilation passes.
The full predictive run completed with 425 passes and the same nine existing
failures. Subsequent isolated readback confirms one additional current-working-
scorer regression (`test_exact_code_scoring_never_loads_current_crosswalks`).
The larger focused run had 86 passes and that one scorer failure. Public-manifest
guard passes. Project-memory still reports its two prior failures (151 checks).
Retained XML files record test-time results rather than implying concurrent
working files stayed unchanged afterward.

Twenty protected truth/registry/saved prediction/report files match the captured
baseline. No staging, commit, push, R2 upload, deployment, saved-probability
overwrite, certification relabeling or UI-filter change occurred in this work.
Four-core `adr-0006-2200616ce0b9`, two existing project-memory failures and 19
broader V3 failures remain unwaived. Bear remains **NOT CERTIFIED / DO NOT PROMOTE**.

## Nonresident thin-lane follow-up

The requested bonus/random thin-lane review found that one-permit nonresident
lanes already assign zero max-point permits and one random permit. The bonus
pool therefore cannot be the dominating term in those lanes. No future-year
read, resident/nonresident key collision or seven-code split-history inheritance
was found.

A full eight-fold, 400-simulation replay of the corrected hierarchical model
scored hunting at 11.507 pp MAE / 32.000 pp P90 / 12.778% tail and pursuit at
15.792 pp / 42.125 pp / 21.104% tail. An isolated candidate allowed a measured
program/residency arrival prior to populate otherwise empty upper rungs only for
nonresident lanes with one or two source-year awards and fewer than 20 forecast
applicants. In a paired 100-simulation comparison it changed 991 hunting rows
across 33 codes, reduced hunting MAE by only 0.016 pp, changed no pursuit row,
and still failed all three accuracy gates. It was removed from the default owner.

The paired evidence and exact row diff are retained under
`audits/prediction_release_candidates/bear_thin_nr_source_arrivals_20260920_v1_100/`.
Twenty protected files are unchanged, all 666 gaps remain classified, and the
seven split codes remain blank. The next defensible investigation is recurring
thin-nonresident quota-state calibration by hunt/year/residency, not a universal
bonus-pool cap, a broad arrival prior or a certification-label exception.
