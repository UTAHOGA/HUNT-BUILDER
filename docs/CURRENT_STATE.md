# Hunt Builder Current State

Memory contract: `1.2.0`
Last verified: `2026-08-28`
Machine authority: `governance/engine-authority.json`

This is the required short briefing for Hunt Builder, Hunt Research, prediction-engine, truth, runtime, build, and deployment work. It supersedes older files whose names contain "current" when their generated date is earlier than this document. `WORK_LOG.md` is historical evidence, not current architecture authority.

## Current Classification

- Product phase: `HOSTED_NORMAL_SPLIT_CONTRACT_RELEASED_CERTIFICATION_PENDING`.
- Hunt Research: hosted and materially functional.
- Prediction mechanics: implemented across the declared engine roles below.
- Active forecast year: `2026`.
- Prediction accuracy certified: `NO`.
- Promotion status: `BLOCKED`.
- New engine designs: prohibited without Tyler's explicit approval.

## Active Research Runtime

The normal Research page is `research.html`, loaded by `hunt-research.js` and configured by `config.js`.

The canonical split contract loads first:

1. `processed_data/hunt_research_2026_summary.json`
2. `processed_data/hunt_research_2026_split/hunt_research_2026.index.json`
3. `processed_data/hunt_research_2026_ladder.json`
4. `processed_data/hunt_research_2026_split/hunt_research_2026.details.json`

The older engine/ladder/master/reference CSV path is a legacy fallback and is disabled unless explicitly configured. Do not create a parallel Research loader.

All six declared Research/runtime payloads, including the split index, are Cloudflare R2-backed and may be absent from a code-only checkout. `governance/engine-authority.json` retains each logical path and canonical HTTPS URL. Local absence is a hydration warning, not a code-contract failure.

## Engine Ownership

The four engine directories are cooperating layers, not competing designs:

| Role | Authority | Version / purpose |
|---|---|---|
| Post-family probability calibration | `engine/utah_predictive_mixed` | `mixed_predictive_v1.0.0`; calibrates eligible family outputs and passes random-only designs through unchanged |
| Family routing and exclusions | `engine/utah_draw_predictive` | Classifies draw families and owns family-specific rules, availability, allocation, and exclusions |
| Forecast and artifact materialization | `engine/utah_bonus_predictive` | `hybrid_ml_v2.1.0` build pipeline; cohort forecast, uncertainty, backtest rows, orchestration, and packaging |
| Deterministic Utah foundation | `engine/utah` | Utah draw mechanics, base demand/quota logic, simulation, validation, and materialization |

Future work must improve the owning layer. Do not create another top-level engine stack to solve a family-specific defect.

## Official Draw-Design Baseline

`docs/UTAH_DRAW_DESIGN_BASELINE.md` is the current source-backed routing matrix. The parent design is classified before any probability is calculated:

- Bonus: limited-entry and once-in-a-lifetime big game, public bonus-eligible CWMU lanes, antlerless moose, ewe sheep, limited-entry turkey, limited-entry bear hunting, and restricted bear pursuit.
- Preference: general-season buck deer, Dedicated Hunter, antlerless deer, antlerless elk, and doe pronghorn.
- Random-only: Sportsman and youth draw-only general any-bull or hunter's-choice elk.
- No original draw probability: bear harvest-objective hunting, general bear pursuit, current cougar opportunity, private-lands-only antlerless elk, remaining permits, and other purchase/allocation/reference rows.

Youth is an overlay, not one universal engine. General deer and most antlerless youth use up-to-20% reserves and then continue into the main preference draw. Youth turkey uses an up-to-15% set-aside within the turkey bonus design.

Black bear has four distinct public behaviors. Limited-entry hunting and restricted pursuit are bonus drawings. Harvest-objective hunting and general pursuit are availability programs. Never convert a pursuit purchase row into hunting odds or a restricted-pursuit draw row into availability merely because both say `pursuit`.

## Residency and Applicant Behavior

- Resident and nonresident quota lanes are part of the draw rule, not labels added after the probability calculation.
- Odd bonus pools round toward the max-point side. A one-permit nonresident lane is the documented random-after-bonus-round exception.
- Do not infer an official current residency quota from historical winner share. The shared quota resolver now uses an explicit official resident/nonresident split first and permits a total-derived split only for an allowlisted draw family with a source-backed allocation rule. Unsupported total-only families block instead of guessing.
- The latest unsuccessful applicant ladder advanced one point is the primary demand forecast. High-point just-missed applicants receive the strongest evidence-based retention because they are normally the most stable cohort.
- Switching, new entrants, and attrition are secondary components. Their weights and all retention rates must be selected by following-year blind results, not intuition alone.

## Truth Authority

- Current hunt identity and published permit reference: `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`.
- Official normalized draw actuals: `data_truth/draw_results_truth/normalized/draw_results_long.csv`.
- Normalized harvest history: `data_truth/harvest_results_truth/normalized/`.
- Official source reports are stored under `pipeline/RAW/hunt_unit_database/<report-year>/pdf/`. The raw folder year is always the DWR report-generation year, never the following model year.
- The DWR landowner association list is stored as `pipeline/RAW/hunt_unit_database/2026/csv/official_landowner_associations_2026.csv` and is reference-only; it cannot enter public draw probability or quota calculations.
- Only official scorable draw-result rows with retained lineage may determine prediction accuracy.
- Permit totals, quota/reference rows, guidebooks, CWMU contact-operator rows, allocation-only rows, and overlays are not probability truth.

## Current Build Evidence

The certified local prediction runtime was rebuilt on `2026-08-27` from the frozen, unified 2018-2025 forecast candidate and the current official 2026 database. The promotion copied 31 forecast artifacts to `processed_data/`, verified every copied SHA-256, and backed up each prior local target. It does not upload or alter R2.

- Build pipeline: `hybrid_ml_v2.1.0`.
- Forecast year: `2026`.
- Prediction rows: `40,642`.
- Backtest rows: `15,166`.
- Historical years used by the declared rebuild: `2018-2025`.
- Duplicate prediction keys: `0`.
- Frozen unified prediction SHA-256: `9e4c0f1a66678cd63df88512e45ba71d63746a6b21d7e4038fecb142f40e9d5e`.
- `DATABASE.csv` SHA-256 at prediction build: `dd87461a76555c73b74fb0df069b47d66ac979b096ab25d9395a2c78f860a24b`.
- Current reviewed `DATABASE.csv` SHA-256: `3df7803b00c95176b106a01d5a86dc61a21b3ddb481107fa1310e1cf0dd56b1f`. The database now includes the complete reviewed conservation-permit crosswalk on all 405 covered current hunt codes, plus the reviewed EA2045 and PD1056 corrections; the compact prediction-build evidence intentionally retains the earlier build hash until the prediction artifacts are rebuilt.

The full generated prediction manifest is a repo-external build artifact at `processed_data/utah_bonus_predictive_manifest.json`. Its compact integrity evidence—including pipeline and rule versions, forecast year, row counts, source hashes, and the promoted manifest SHA-256—is Git-tracked in `governance/engine-authority.json`. Code-only validation uses that compact record and performs the full manifest hash and field cross-check whenever the generated manifest is locally hydrated.

The normalized official draw truth is locally hydrated with `309,562` rows for draw years `2018-2026`; SHA-256 `94189f6c0bbb90ad597a8f0cd3f3d96b2be1983b0d927665d18d3673da920474`. Every canonical annual source has retained lineage. The 2018 legacy-layout reports are now canonically parsed; source-identity normalization retains distinct official scopes rather than merging coarse duplicate keys.

The blind 2025-to-2026 run froze the unified forecast before reading 2026 actuals. It joins `13,968` official actual keys with zero duplicate prediction-key groups, zero duplicate actual-key groups, and zero unexpected engine/key gaps. Probability MAE is `0.122938` and RMSE is `0.291489`. The just-missed applicant model MAE is `4.5771`: `30.41%` better than the paired same-point baseline and `2.47%` better than pure unsuccessful-rollforward. The `2,657` non-joined keys are source-classified as `2,528` CWMU public-odds exclusions, `72` current-Planner non-draw bear transitions awaiting dated-snapshot reconciliation, and `57` official no-exact-history additions.

On `2026-08-28`, the normal four-file split Research contract was released to R2 and the Pages frontend was deployed with `HUNT_RESEARCH_DATA_VERSION = 20260828-certified-split-contract-1`. The public worker returned an exact SHA-256 match for all four objects: summary `766fb913...30de7`, index `fac60c2a...90e83`, ladder `1a45732c...44a5d`, and details `67ab489b...2812a`. Fresh rollback copies are retained under `audits/prediction_blind_backtests/2025_to_2026_truth_2018_2026_20260827_certification_candidate/r2_authorized_release_20260828T010028Z/`.

The released split contract contains a rebuilt summary (`5,477` rows), ladder (`136,882` rows), current 2026 selection index (`1,471` hunt codes), details bundle, and point-ladder support (`136,726` rows). All `40,642` frozen prediction keys are represented in the candidate ladders. The index intentionally excludes `320` historical summary/reference-only codes, while summary and details retain them as non-selectable reference context. The live smoke test at `https://huntbuilder.pages.dev/research.html` resolved `BR7004` for a nonresident at zero points as Black Bear with `18` resident / `2` nonresident permits, and the status label cleared after rendering.

The pipeline and runtime model versions describe different layers. The legacy hosted predictive CSV remains content/schema-different from the rebuilt local forecast (`35,016` hosted rows and `220` fields versus `40,642` local rows and `192` fields), but it is legacy-fallback-only and is not part of the normal Research load path.

## Why Promotion Is Blocked

1. Aggregate blind acceptance thresholds, including tail-error and false-guarantee tolerances, are not yet formally certified despite the completed comparison.
2. The `72` current-Planner non-draw bear transitions require a dated Planner snapshot to distinguish valid program transition from data drift.
3. The `57` official no-exact-history 2026 additions require their source crosswalk before they can become historical forecasting lanes.
4. The generic deterministic simulator residency sequence remains uncertified.
5. Five explicit family/design contract-drift items remain under review in the machine authority.
6. The current `DATABASE.csv` is newer than the checked-in compact prediction-build evidence after the reviewed conservation-permit crosswalk and EA2045/PD1056 corrections. Rebuild and revalidate prediction artifacts before any later prediction promotion.

These blockers mean "do not publish this as newly certified." They do not authorize another redesign.

## Approved Continuation Path

1. Establish formal aggregate blind acceptance thresholds and review the remaining tail-error and false-guarantee evidence.
2. Resolve the dated Planner/bear and no-exact-history source transitions.
3. Preserve `engine/utah_predictive_mixed` as the final probability blend and `engine/utah_draw_predictive` as family authority.
4. Do not replace the legacy predictive fallback or publish a newly accuracy-certified claim without Tyler's explicit authorization and a fresh rollback plan.

## Required Commands

Before and after related work:

```powershell
npm run validate:project-memory
```

Normal repository validation:

```powershell
npm test
```

Current declared prediction materialization command:

```powershell
python scripts/promote_certified_prediction_candidate.py --candidate audits/prediction_blind_backtests/2025_to_2026_truth_2018_2026_20260827_certification_candidate --apply
```

## Stop-And-Reconcile Conditions

Stop and reconcile the memory contract instead of improvising when:

- an undeclared engine directory appears;
- a runtime artifact identifies a different final model owner;
- truth paths or forecast year change;
- implementation contradicts an accepted ADR;
- a generated manifest no longer matches its declared inputs;
- a task would turn a reference/allocation/availability row into probability truth;
- a proposed change would publish or deploy without explicit authorization.
