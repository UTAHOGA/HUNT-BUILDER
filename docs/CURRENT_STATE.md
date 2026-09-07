# Hunt Builder Current State

Memory contract: `1.2.0`
Last verified: `2026-09-06`
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

The code-only 2026 permit-allocation gate audits the five tracked hunt-level canonical/planner row surfaces plus the tracked Research metadata contract. It does not treat ignored optional hydration files as code-contract authority: the legacy observed draw engine is a historical point-row surface and does not carry hunt-level 2026 allocation columns, while ignored processed master/reference copies may be stale relative to R2. `npm run verify:permits-2026:optional-hydration` remains an explicit diagnostic for those local files and is expected to block when stale hydration is present.

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

- Current hunt identity and published permit reference: `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`. It is never historical draw-result truth or a scoring substitute.
- Official historical draw actuals and scoring truth: yearly canonicals in `data_truth/draw_results_truth/normalized/canonical_yearly/`, frozen into `data_truth/draw_results_truth/normalized/draw_results_long.csv`.
- Normalized harvest history: `data_truth/harvest_results_truth/normalized/`.
- Official source reports are stored under `pipeline/RAW/hunt_unit_database/<report-year>/pdf/`. The raw folder year is always the DWR report-generation year, never the following model year.
- The DWR landowner association list is stored as `pipeline/RAW/hunt_unit_database/2026/csv/official_landowner_associations_2026.csv` and is reference-only; it cannot enter public draw probability or quota calculations.
- Only official scorable draw-result rows with retained lineage may determine prediction accuracy.
- Permit totals, quota/reference rows, guidebooks, CWMU contact-operator rows, allocation-only rows, and overlays are not probability truth.

## Hunt Research Management And Quality Display

The visitor-facing management and harvest-quality layer is display-only and follows `docs/HUNT_RESEARCH_MANAGEMENT_AND_QUALITY_DISPLAY_SCHEMA.md`.

- Exact management context: `processed_data/management_context/hunt_management_objective_context.json`, rebuilt from the verified DWR plan inventory and the 227-row Hunt Planner management snapshot. Hunt identity is the DWR source hunt code plus compatible species/name; `boundary_id` and synthetic statewide unit targets are prohibited.
- Species-specific measures retain their DWR units: harvested-age targets for applicable male elk/moose/pronghorn hunts, buck-to-doe ratios for buck deer hunts, and population objectives for bison/sheep/goat and other population-applicable rows. Black bear and turkey retain statewide framework context only; cougar retains current open-season program authority only.
- Annual harvested age, DWR-reported three-year harvested age, computed three-year harvested age, and Hunt Planner current three-year age remain separate fields. A comparison is valid only when target and current measures use the same unit.
- The `U.O.G.A. Hunt Quality Profile V1` is not a DWR score and cannot change draw probability, permits, quotas, or canonical truth. Its four fixed components are biological measure (40%), three-year success (25%), three-year satisfaction (20%), and three-year inverse effort (15%). Missing components are never reweighted.
- A composite score is published only for exact-code, current-through-2025 grade A/B history with all three-year components, a numeric matching-unit DWR target/current comparison, no relevant value conflict, and at least 10 average hunters afield. Raw verified measures and explicit withholding reasons remain publishable when the composite gate is not met.

## Current Build Evidence

The locally promoted prediction runtime was rebuilt on `2026-08-27` from the then-current frozen, unified 2018-2025 forecast candidate. The promotion copied 31 forecast artifacts to `processed_data/`, verified every copied SHA-256, and backed up each prior local target. It did not upload or alter R2. That local runtime is now deliberately treated as stale because the official current database has changed; it remains untouched until the newer blind candidate is accepted and explicitly promoted.

- Build pipeline: `hybrid_ml_v2.1.0`.
- Forecast year: `2026`.
- Prediction rows: `40,642`.
- Backtest rows: `15,166`.
- Historical years used by the declared rebuild: `2018-2025`.
- Duplicate prediction keys: `0`.
- Frozen unified prediction SHA-256: `9e4c0f1a66678cd63df88512e45ba71d63746a6b21d7e4038fecb142f40e9d5e`.
- `DATABASE.csv` SHA-256 at prediction build: `dd87461a76555c73b74fb0df069b47d66ac979b096ab25d9395a2c78f860a24b`.
- Current reviewed `DATABASE.csv` SHA-256: `0678f9382ef3b17cbf08197113f56bdddc865755b66ea7f8983d8575c5fa3996`. The standalone current-identity/current-quota feeder audit is `processed_data/audits/database_current_identity_quota_2026_feeder_audit_summary.json`: it verifies all 1,433 retained DWR Planner records and all 1,848 database rows with zero unexplained current-field deltas. It retains the reviewed turkey and private-lands source differences as non-draw allocation context, retains the BR7004 official 18/2/20 draw-result split, preserves the PD1056 corrected 36/4/40 official value, and moves BR7324's 2025-27 conservation-cycle count out of current public-quota fields while preserving it in `conservation_permits_2026_total`. The database remains current identity/permit-reference context only; the compact prediction-build evidence intentionally retains its earlier build hash until prediction artifacts are rebuilt and accepted.

The full generated prediction manifest is a repo-external build artifact at `processed_data/utah_bonus_predictive_manifest.json`. Its compact integrity evidence—including pipeline and rule versions, forecast year, row counts, source hashes, and the promoted manifest SHA-256—is Git-tracked in `governance/engine-authority.json`. Code-only validation uses that compact record and performs the full manifest hash and field cross-check whenever the generated manifest is locally hydrated.

The normalized official draw truth is locally hydrated with `341,842` rows for draw years `2017-2026`; SHA-256 `8b0053a8be9366671a2c80d5d4e2bb0c290a32e3ce476d41154e5ecc113d0a18`. The 2017 legacy scope is frozen from retained official source reports, and the 2018 legacy-layout reports are canonically parsed; source-identity normalization retains distinct official scopes rather than merging coarse duplicate keys. On 2026-08-29, the yearly canonicals were corrected by official hunt-code prefix only: 2,723 historical `species` metadata cells are now normalized (for example, Deer at Bear River and Elk at Bear Mountain), with no official applicant, permit, probability, point, source-file, or PDF-page value changed. On 2026-09-02, `857` 2018 point-lane derived probabilities were corrected from rounded DWR `Success Ratio` display values to their exact retained applicant/permit counts; the source `1 in X` text, counts, point rows, and PDF lineage were preserved. The prior prediction-build manifest deliberately retains its earlier truth hash until a fresh source-only forecast is built and accepted. The September 2 live UtahDraws refresh added `2,144` actual 2026 antlerless point/residency/adult-youth rows across `153` public drawn hunt codes to the 2026 canonical. Of these rows, `1,911` have positive applicants and `233` preserve official zero-applicant evidence with blank probabilities. All `262` current Hunt Planner permit-reference rows remain non-scorable identity/quota references. The live source backs `153` of the `162` public drawn references; all nine unmatched references are zero-permit conservation, Expo, or control references. `EA1281` (Mt Dutton, Deep Creek) was removed from the active 2026 database and canonical reference set: its current DWR detail record identifies it as `HUNT_YEAR=2025` and `STATUS=OFF`, the current antlerless-elk list omits it, and the 2026 antlerless guidebook contains neither the code nor Deep Creek. Its `67` resident plus `8` nonresident permits (`75` total) are archived 2025 Hunt Planner values for the Dec. 20, 2025-Jan. 11, 2026 season, not 2026 draw permits. All `36` canonical 2025 EA1281 result rows remain preserved. The official online results are also formatted into one combined and five species-specific 2025-style PDFs under `pipeline/RAW/hunt_unit_database/2026/pdf/draw_odds/official_dwr_online_results/`, with resident and nonresident ladders matched by hunt code. Across all current live endpoint packages, `18,519` canonical rows have direct value parity and one `DB1630` row has multiple equal endpoint candidates; `17,165` rows are certifiable source-value parity and `1,355` are explicitly unscorable because the official source has no applicant or successful-applicant count.

Five complete UOGA-styled 2026 result PDFs are retained under `pipeline/RAW/hunt_unit_database/2026/pdf/draw_odds/official_dwr_online_results/uoga_styled_20260902/`: corrected Antlerless, Big Game, Black Bear, Turkey, and Sportsman. They cover all `29` retained official UtahDraws packages and all `22,018` result rows. Each page uses the supplied UOGA circle logo, the current UOGA black/brown/cream/forest palette, and the 2025 DWR-style resident/nonresident point tables while clearly identifying DWR/UtahDraws as the data source. The generation guard requires every row to have `IsHistoricalData=False`, every populated season to have `LicenseYear=2026`, zero calendar-2025 season starts, and zero `EA1281` source matches; 2027 calendar starts remain valid only when DWR assigns them to the 2026 license year.

The accepted acceptance standard is `docs/decisions/ADR-0006-historical-blind-acceptance-thresholds.md`. Its source-only, physically adjacent review runs `2017→2018` through `2024→2025`; the final pair scores the 2025 drawing even though the corresponding canonical key is named for model year 2026. It explicitly excludes the 2025→2026 comparison. The current deterministic baseline is retained at `audits/prediction_blind_year_to_year/frozen_canonical_long_2017_2025_deterministic_20260906_current_identity_audited_bg/acceptance_review/`. It keeps all `90,145` joined rows and is `NOT_ACCEPTED`: MAE `0.115985`, RMSE `0.280574`, 90th-percentile error `0.400000`, and `11,830` rows (`13.123%`) over 25 probability points. It has `190` false guarantees: `182` limited-entry Bear hunting, `5` restricted Bear pursuit, and `3` Turkey. The source-typed reporting review is retained at `audits/prediction_blind_year_to_year/frozen_canonical_long_2017_2025_deterministic_20260906_current_identity_audited_bg_bear_subtype_reporting/`; no general/unlimited Bear pursuit availability rows are included in this probability population.

The existing, source-backed Bear returning-cohort uncertainty layer was then tested—not promoted—at 400 deterministic samples in `audits/prediction_blind_year_to_year/frozen_canonical_long_2017_2025_bear_source_calibrated_tail_mixture_20260906/acceptance_review/`. It preserves the exact same `90,145` scored keys and reduces false guarantees from `190` to `78` (`75` Bear plus the same `3` Turkey), with MAE `0.115837` and RMSE `0.280042`. It remains `NOT_ACCEPTED`: the P90 remains `0.400000`, and its tail grows slightly to `11,837` rows (`13.131%`). The active/default estimate remains deterministic; no candidate is certified or promoted.

The remaining `75` Bear false guarantees are evidence about unmet, lane-specific high-point demand—not missing official records or a permit-split problem. They occur in 2018→2019 through 2022→2023, are `72` resident and `3` nonresident cases, and all land at a following-year mixed cutoff (`54`) or below the following-year draw line (`21`). Seventy-four retain an explicit exact-code crosswalk and the remaining legacy case is also the identical `BR7209` code, so a code-transition explanation is not supported. Every remaining row still has a candidate P10 of `1.0`, so a generic probability cap would merely conceal the error. No PDF was re-ingested, no database or canonical truth was replaced, and no active runtime, prediction manifest, R2 object, or deployment was changed.

The durable source boundary for a future Bear entry/switch model is now `data_truth/point_purchase_truth/BLACK_BEAR_HUNT_LANE_TRANSITION_CONTRACT.md`. Public DWR reports and the UtahDraws endpoint remain aggregate-only evidence; they do not connect a person’s prior Bear outcome or point purchase to a following-year hunt selection. R657-62-8 confirms that DWR retains the electronic application record needed to make that connection, while the guidebook keeps individual results private. The only acceptable extension is a DWR-produced, de-identified, aggregate prior-activity-to-next-first-choice transition matrix that meets the contract’s lineage, adjacency, residency, suppression, and held-out validation gates. Until such an extract exists, no additional hunt-level entrant allocation is permitted.

The retained official 2018–2022 black-bear PDFs contain separate resident and nonresident point ladders, while the canonical source rows retain their combined values. The hash-linked extraction at `data_truth/draw_results_truth/validation/black_bear_2018_2022_pdf_residency_ladders.csv` recombines exactly to all five canonical years, with no missing point keys or value disagreements. The prior 2018 canonical omitted the retained Black Bear report; it was rebuilt from the ten retained official report parents, compared so that every non-Bear row and the existing `BR1000` Sportsman row remained identical, then promoted with a hash-verified rollback copy. `draw_results_long.csv` is rebuilt solely from the canonical yearly truth and now has `341,842` rows, including the later frozen 2017 canonical promotion, the `2,144` newly promoted official 2026 antlerless result rows, and the exclusion of the misclassified EA1281 permit reference. The extraction remains validation truth: the engine must not use a combined-residency row as a resident or nonresident odds ladder. The 2021→2022 paired source-and-held-out lane fold found a narrowly scoped defect in the audit-only historical permit proxy: it summed broad resident/nonresident columns from both normalized lane rows and doubled the max-point/random permit allocation. The repair now uses each lane's scoped `total_permits` once. The source-only rerun has zero duplicate forecast keys and reduces Bear from `68` to `53` false guarantees and MAE from `0.402231` to `0.323858`; it remains **NOT_ACCEPTED** because every remaining false guarantee is a max-pool demand miss, not a combined-lane or repeated permit-allocation defect. The attempted generic demand-scenario adjustment is explicitly not retained.

The paired Bear lane-fold replication is complete for `2018→2019`, `2019→2020`, `2020→2021`, and `2021→2022`. Every source file physically excludes later official truth and every Bear leakage check passes. The archived classifier repair now carries the retained PDF page's explicit `TRUE_BEAR_BONUS_DRAW` or `BEAR_PURSUIT_BONUS_DRAW` identity only on the audit's official residency-lane projections; it does not alter canonical truth or classify rows from a code prefix, permit total, or generic legacy label. The reruns now produce deterministic Bear rows in every earlier fold: `3,600` rows across `75` hunt codes for `2018→2019`, `4,464` across `93` for `2019→2020`, and `4,176` across `87` for `2020→2021`.

This repaired coverage replaces—not validates—the earlier fallback score. On held-out official lanes, `2018→2019` has `31` scoreable Bear rows, MAE `0.404796`, and zero false guarantees; `2019→2020` has `1,168`, MAE `0.324195`, and `61` false guarantees; `2020→2021` has `1,248`, MAE `0.356603`, and `98` false guarantees. The `2021→2022` repaired permit-proxy fold remains `1,205` scoreable rows, MAE `0.323858`, and `53` false guarantees. The classifier repair therefore resolves archive coverage but shows that the deterministic model is not accepted and that high-point demand behavior must not yet be changed. Combined history must never be treated as a resident or nonresident ladder.

The latest unpromoted diagnostic candidate at `audits/prediction_blind_backtests/2025_to_2026_truth_2018_2026_20260828_bear_source_repair/` froze its forecast before reading 2026 actuals. It uses the current database SHA above and has frozen prediction SHA-256 `5d0becac14bbeb84b96725acd917c4e7bc8a4a799d23b0a740b736874be8d90a`. The retained, hash-verified 2025 DWR black-bear report corrects a stale source path that had caused the engine to treat every current `Pursuit Only`/`O.T.C.` Planner label as non-draw. The repaired audit joins `14,040` official actual keys with zero duplicate prediction-key groups, zero duplicate actual-key groups, and zero unexpected engine/key gaps; all `72` formerly excluded bear actual rows now have a forecast. The remaining `2,585` non-joined keys are fully source-classified: `2,528` intentionally excluded CWMU public-odds rows and `57` current additions with no comparable official historical ladder. Probability MAE is `0.122557`, RMSE is `0.290447`, `1,976` rows exceed 25 percentage points absolute error, and there are `229` false guarantees (`63` bear rows). This diagnostic is explicitly **not accepted** and is excluded from ADR-0006 acceptance; its purpose is source-coverage and targeted-rule repair, not certification.

On `2026-08-28`, the normal four-file split Research contract was released to R2 and the Pages frontend was deployed with `HUNT_RESEARCH_DATA_VERSION = 20260828-certified-split-contract-1`. The public worker returned an exact SHA-256 match for all four objects: summary `766fb913...30de7`, index `fac60c2a...90e83`, ladder `1a45732c...44a5d`, and details `67ab489b...2812a`. Fresh rollback copies are retained under `audits/prediction_blind_backtests/2025_to_2026_truth_2018_2026_20260827_certification_candidate/r2_authorized_release_20260828T010028Z/`.

The released split contract contains a rebuilt summary (`5,477` rows), ladder (`136,882` rows), current 2026 selection index (`1,471` hunt codes), details bundle, and point-ladder support (`136,726` rows). All `40,642` frozen prediction keys are represented in the candidate ladders. The index intentionally excludes `320` historical summary/reference-only codes, while summary and details retain them as non-selectable reference context. The live smoke test at `https://huntbuilder.pages.dev/research.html` resolved `BR7004` for a nonresident at zero points as Black Bear with `18` resident / `2` nonresident permits, and the status label cleared after rendering.

The pipeline and runtime model versions describe different layers. The legacy hosted predictive CSV remains content/schema-different from the rebuilt local forecast (`35,016` hosted rows and `220` fields versus `40,642` local rows and `192` fields), but it is legacy-fallback-only and is not part of the normal Research load path.

## Why Promotion Is Blocked

1. The formally adopted historical acceptance review is `NOT_ACCEPTED`: `BONUS_OIL_BIG_GAME` meets the per-design threshold, but the other reviewed designs either fail an error/false-guarantee threshold or have insufficient independent evidence. The highest recurring false-guarantee patterns are recorded by hunt code and draw design in the historical acceptance review.
2. The `57` 2026 actual rows reduce to six current hunt codes (`BI6539`, `BR7021`, `BR7126`, `BR7238`, `DB1109`, `DB1121`). Their retained crosswalk verifies no exact 2018-2025 canonical draw predecessor, documents the dated application-guidebook listing, and keeps them deliberately unscored. They must not receive a borrowed same-unit probability unless an official DWR predecessor mapping is retained.
3. The checked-in local prediction manifest and runtime artifacts still reflect the prior database/candidate. The current reviewed `DATABASE.csv` is newer after the conservation-permit crosswalk and EA2045/PD1056 corrections; the newer candidate has not been accepted or promoted.
4. The four source/family contract mismatches recorded on 2026-08-28 are resolved. The only remaining contract-drift review is local-versus-R2 equivalence for the legacy predictive CSV fallback, which is not part of the normal Research load path.

These blockers mean "do not publish this as newly certified." They do not authorize another redesign.

## Approved Continuation Path

1. Review only the remaining `75` Bear false guarantees by subtype, residency, point rung, permit split, and source-backed applicant-cohort behavior. Repair only another demonstrated simulator or cohort defect; do not use combined-residency rows, future truth, or a generic probability cap.
2. Retain `EB3100` resident point 12 as an explicit unresolved first-fold mixed-cutoff case unless an official source-backed mechanic explains its held-out result. Do not force it below 100 percent merely to satisfy the acceptance gate.
3. Keep the six no-exact-history codes source-classified as intentionally unscored rather than unresolved engine gaps.
4. Preserve `engine/utah_predictive_mixed` as the final probability blend and `engine/utah_draw_predictive` as family authority.
5. If accepted, rebuild the local runtime artifacts and manifests from the 2026-08-28 candidate, then separately obtain authorization and a rollback plan before any hosted release.

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
