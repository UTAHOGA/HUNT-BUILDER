# AGENTS.md

## Project Memory Contract

The repository is the durable memory for this project. Before inspecting or changing Hunt Research, prediction-engine, truth, runtime, build, or deployment behavior:

1. Read `docs/CURRENT_STATE.md`.
2. Read `governance/engine-authority.json`.
3. Read `docs/UTAH_DRAW_DESIGN_BASELINE.md` for prediction, routing, quota, residency, bear, or applicant-behavior work.
4. Read the applicable accepted records in `docs/decisions/`.
5. Run `npm run validate:project-memory` before editing and again before finishing.

`governance/engine-authority.json` is the machine-readable statement of the active architecture and current promotion state. `docs/CURRENT_STATE.md` is its human-readable briefing. Accepted decision records explain why the architecture exists. `WORK_LOG.md` is historical evidence only and must not override the current-state or authority contracts.

Do not create a new prediction-engine stack, parallel Research runtime, alternate truth authority, or replacement probability contract unless Tyler explicitly approves that architectural change. Improve the declared owning module instead. If implementation and the memory contract disagree, report the conflict and update the contract in the same approved change; do not silently select a different architecture. A requested architecture change must add or supersede an ADR and update `governance/engine-authority.json`.

## General Project Rules

Read this file before every task. Tyler's explicit instruction controls the task scope: if Tyler tells you to edit website, deploy, UI, production, engine, data, or truth files, then that file class is in scope for that task. Do not add extra restrictions that block the requested work.

Before starting, check `git status --short` and `git diff --cached --name-status`; if anything is unexpectedly staged, stop and ask.

Do not stage or commit large generated data files: files over 100 MB are prohibited from Git, files over 50 MB require review, and large generated JSON/CSV/GeoJSON/SQLite/runtime outputs belong in Cloudflare R2, not Git. Do not use Git LFS unless Tyler explicitly requests it. Never upload or commit `.git`, `.wrangler/state`, `node_modules`, cache blobs, or local generated audit junk.

Vercel deploys from `pages-dist` because `vercel.json` uses `buildCommand: npm run build` and `outputDirectory: pages-dist`; do not delete `pages-dist`. `pages-dist` may be edited or rebuilt when Tyler asks for website/deploy/build/live work. For data-engine/audit/model work, avoid unrelated website/deploy changes unless Tyler asks for them. For website/deploy/build/live work, edit the necessary website files directly and rebuild `pages-dist` as required. `scripts/build-pages-dist.js` should avoid duplicating huge runtime data into `pages-dist`; files over 100 MB should be R2-backed or skipped with a small manifest when possible.

Prediction-engine work should follow the simple loop: feed official scorable truth rows, generate predictions, compare against following-year official actual truth, identify error patterns, edit engine logic, and rerun. Ignore unscorable rows for accuracy work and never fabricate probability from permit totals, quota rows, CWMU contact-operator rows, guidebook rows, allocation-only rows, or reference rows. Sportsman permits are `SPORTSMAN_RANDOM_ONLY`; youth rows must be source-classified and not guessed; guaranteed/lifetime/general guaranteed-tag rows are not prediction rows; CWMU Contact Operator rows with blank permit numbers are `CWMU_CONTACT_OPERATOR_REFERENCE_ONLY`; allocation/reference-only rows are not probability rows.

Before finishing any task, run `git diff --cached --name-status` and `git status --short`, report whether anything is staged, and do not leave large generated files staged.
U.O.G.A. HUNT-BUILDER — Instructional Regime for ChatGPT / Codex Agent
MISSION
You are working on https://github.com/UTAHOGA/HUNT-BUILDER — HUNT-BUILDER is a Utah hunting research website at huntbuilder.pages.dev / huntbuilder.uoga.org / huntbuilder.uoga.org/research

The prediction engine estimates future draw odds by hunt code, residency lane, and point level using official Utah DWR draw-result ladders. Goal is NOT to invent odds from permit totals. Goal is to use official historical applicant counts and awarded permits to model official Utah draw mechanics, forecast next year's applicant ladder, calculate probability for one applicant at each point level, and compare forecast to next year's official DWR actuals.

This is a transparency-first, source-backed, conservative system. A probability may be useful for research before it is statistically certified, but must not be represented as guaranteed or live-certified unless it passes defined historical validation.

0. READ-ONLY FIRST
Before any edit, run read-only checks. Do not stage, push, or deploy until all gates pass. Nothing in data_truth/ canonicals, DATABASE.csv permit/quota protected fields may be mutated to improve metrics.

1. TRUTH AND DATA AUTHORITY - TWO SEPARATE CONTRACTS
Historical draw-results truth (prediction and scoring truth)
Yearly canonical official draw-result files: data_truth/draw_results_truth/normalized/canonical_yearly/
Frozen long-form historical truth built ONLY from those canonicals: data_truth/draw_results_truth/normalized/draw_results_long.csv
These retain point-level official applicant counts, bonus/max permits, regular/random permits, total permits, residency, source file, PDF page/source lineage, and draw-family classification.
Historical accuracy must be measured ONLY against following-year official draw-result truth.
Current hunt identity and current permit reference
pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv is NOT historical draw truth. It is used ONLY for current hunt identity, current hunt-code metadata, current Planner permit-reference context, current residency quota context where officially published. It must never replace canonicals or be treated as source of historical applicant demand or historical probability.

2. DRAW-FAMILY ROUTING COMES BEFORE PROBABILITY MATH
Utah does not have one universal draw formula. Every row must first be classified into its parent draw design.

Parent Design	Examples	Owner
Bonus / max-weighted split	Limited-entry deer, elk, pronghorn; once-in-a-lifetime species; eligible public CWMU; antlerless moose; ewe sheep; limited-entry turkey; limited-entry Bear hunting	engine/utah + utah_bonus_predictive
Preference	General-season buck deer; Dedicated Hunter; antlerless deer and elk; doe pronghorn	Preference-family engines
Random only	Sportsman; youth draw-only general elk	Random/youth engines
No original draw probability	OTC, availability-only, private-land allocation, remaining permits, general Bear pursuit, harvest-objective Bear, current cougar opportunity, reference rows	Availability/reference routing only
Important exclusions:

Permit totals alone are not odds
CWMU operator/contact rows are not draw rows
Expo, conservation, private-land, mitigation, allocation-only, reference rows are not public-draw probability truth
Bear pursuit availability must never be mixed with Bear hunting-draw odds
Youth is an overlay, not one generic engine
3. UTAH RULES THE ENGINE MUST PRESERVE
Residency
Resident and nonresident lanes are separate rules, not display labels. Each lane may have different quota, point ladder, max-point pool, random pool, predicted demand, cutoff. Engine may NEVER merge resident and nonresident applicant counts simply because they share hunt code.

Bonus Draw Mechanics (ordinary Utah bonus designs)
Portion of permits issued through max-point process
Remaining permits issued through weighted random: each applicant has one random number plus one additional for each bonus point. Odd pools give extra to max-point side.
Residency crossover may happen only after separate resident/nonresident rounds, and only for family/program where Utah officially permits it.
Engine must not use historical winner share as substitute for official resident/nonresident quota split.
Demand Forecasting Core Assumption
Prior-year winners leave applicant ladder
Prior-year unsuccessful advance one point
Just-missed high-point cohort is strongest demand anchor
Lower-point additions, switching, new entrants, attrition are secondary and require historical evidence
No model may fabricate hunt-specific cohort from statewide point-purchase totals.
4. EXISTING ENGINE LAYERS - DO NOT REPLACE WITH GENERIC ML
Layer	Responsibility
engine/utah	Deterministic Utah mechanics, quota handling, max/random logic, validation
engine/utah_draw_predictive	Draw-family classification, routing, exclusions, residency and family-specific rules
engine/utah_bonus_predictive	Cohort forecasting, uncertainty, historical backtesting, artifact packaging
engine/utah_predictive_mixed	Post-family calibration ONLY; must not replace family mechanics
Bear work is intentionally deprioritized.

5. CERTIFICATION STANDARD (FROZEN - DO NOT RELAX)
Each draw design certified independently. Good statewide average cannot certify failing design. For each design, source-only physically adjacent-year folds must meet ALL:

Gate	Required
Independent adjacent-year folds	>=2
Joined official scorable rows	>=400
MAE	<=10 pp
P90 absolute error	<=30 pp
Absolute-error tail above 25 pp	<=10%
Forecasted-certainty failures (forecast ~100% while actual <100%)	0
Official actuals without forecasts	Every one must be source-classified
6. CURRENT STATUS FROM COMPLETION_REPORT.md 2026-09-19
Design	Scored Rows	Mean Error	P90	Tail>25pp	Unresolved Gaps	Result
Limited-entry big game	51,270	7.555	18.669	8.04%	32	Blocked by coverage
Once-in-a-lifetime big game	34,944	3.875	5.527	4.115%	0	Certified
Premium LE big game	2,743	2.066	2.453	1.969%	0	Certified
General-season buck deer	8,936	10.494	39.500	12.97%	0	Fails accuracy
Inventory: 796 retained core hunt codes / 1,592 residency combinations. Final local browser run passed 1,249/1,249 scenarios.

Live site at huntbuilder.pages.dev/research currently withholds LE and general deer (displays only OIL and Premium LE as certified). Local candidate that withholds failing designs has NOT been deployed.

7. IMMEDIATE PROBLEMS TO FIX
A. BONUS_LE_BIG_GAME zero-forecast / positive-actual tail
Signature: forecast p=0, public_permits_target=0, algorithm_status=MODELED_SOURCE_BACKED_ROLL_FORWARD yet following-year official point row has positive actual probability. Observed: ~2,573 resident + ~1,313 nonresident.

Fallback bonus_le_big_game_source_backed_roll_forward carries prior probability forward only when primary cohort model does not emit matching structural key. Zero appears when primary does not emit.

B. 32 Limited-Entry Gaps
All 32 carry deliberate "no transition evidence" status. They correctly remain blank; audit must record why rather than treating as unexplained omission.

C. General-Season Buck Deer - Preference Point
Deer is PREFERENCE, not bonus. There are tons of applicants. The model is too optimistic near cutoff. Root cause found: historical test adapter counted BOTH hunt-total row and point-level rows, doubling permit supply. Example: Box Elder official PDF = 225 resident + 20 nonresident awards, not 450 and 40. After fixing counting, six development folds improved from 10.44 to 6.29 pp MAE and large-error from 13.06% to 6.47% with NO probability formula change.

Residency note: Hunt Planner shows combined total, but official draw results DO separate resident/nonresident regular-round allocations. You must preserve DWR separate allocations even where Planner shows combined. General deer was incomplete: Research artifacts had 105 resident selections and zero nonresident. Now repaired locally to 210 combinations using DWR regular-draw allocations, not assumed split.

8. DIAGNOSTIC REQUIRED FOR ALL BONUS_LE ZERO ROWS
Build audit table for every row where forecast p=0 and target_official_p>0 in 8-fold join. One row = source_year, hunt_code, residency, point_level, draw_pool.

Required columns:

source_official_applicants, source_official_bonus_permits, source_official_regular_permits, source_official_total_permits_lane
target_official_applicants, target_official_bonus_permits, target_official_regular_permits, target_official_total_permits_lane
hunt_code_exists_source_canonical, hunt_code_exists_target_canonical
residency_lane_exists_source_canonical, residency_lane_exists_target_canonical
hunt_code_continuity [CONTINUOUS, SPLIT, MERGED, DISCONTINUED, NEW]
quota_source_type_for_forecast [OFFICIAL_CANONICAL, DATABASE_PROXY, ZERO_FALLBACK]
cohort_engine_emitted_bool, cohort_engine_p_draw, cohort_engine_applicant_forecast, cohort_engine_score_key
fallback_score_key, fallback_algorithm_status
official_score_key_source, official_score_key_target
source_pdf_page_lineage_present, target_pdf_page_lineage_present
Classification - Exactly One Status, Precedence Order
Check in this order, assign once, stop:

INSUFFICIENT_OFFICIAL_LINEAGE - source or target lineage missing
NEW_OR_UNCOMPARABLE_OFFICIAL_LANE - hunt_code or residency lane exists in target canonical but not source canonical
TARGET_YEAR_OFFICIAL_PROGRAM_OR_QUOTA_CHANGE - source total permits 0/null and target >0, or target >=2x source AND DATABASE metadata changed
SOURCE_PROXY_QUOTA_FAILURE - source_official_total>0 but public_permits_target==0 and quota_source_type != OFFICIAL_CANONICAL (source_year proxy incorrectly zeroed quota despite active lane)
SOURCE_TO_ENGINE_IDENTITY_OR_KEY_MISMATCH - cohort_emitted true but cohort_score_key != fallback_score_key, or cohort exists same hunt_code but different draw_pool label / residency case
COHORT_ENGINE_ZERO_DEMAND_FAILURE - remaining, stable identity, quota official, cohort emitted zero demand yet target shows positive
python
def classify_le_zero_row(r):
    if not r.source_lineage_ok or not r.target_lineage_ok:
        return "INSUFFICIENT_OFFICIAL_LINEAGE"
    if (not r.hunt_code_exists_source and r.hunt_code_exists_target) or \
       (not r.res_lane_exists_source and r.res_lane_exists_target):
        return "NEW_OR_UNCOMPARABLE_OFFICIAL_LANE"
    if r.source_official_total_permits in (0,None) and r.target_official_total_permits>0:
        return "TARGET_YEAR_OFFICIAL_PROGRAM_OR_QUOTA_CHANGE"
    if r.source_official_total_permits>0 and r.public_permits_target==0 and r.quota_source_type!="OFFICIAL_CANONICAL":
        return "SOURCE_PROXY_QUOTA_FAILURE"
    if r.cohort_emitted and r.cohort_score_key != r.fallback_score_key:
        return "SOURCE_TO_ENGINE_IDENTITY_OR_KEY_MISMATCH"
    if r.cohort_emitted_alt_pool and r.cohort_p_draw_alt>0:
        return "SOURCE_TO_ENGINE_IDENTITY_OR_KEY_MISMATCH"
    return "COHORT_ENGINE_ZERO_DEMAND_FAILURE"
9. REPAIR ORDER - SMALLEST SAFE, DO NOT CHANGE BEHAVIOR ASSUMPTIONS FIRST
Repair 1 - Lineage: Enforce draw_results_long.csv build fails if any row loses source_file + pdf_page. Fix INSUFFICIENT_OFFICIAL_LINEAGE.

Repair 2 - Quota Source: In engine/utah for BONUS_LE, force public_permits_target from source-year canonical official permits for exact residency lane, never DATABASE.csv. This likely fixes majority of 2,573 resident zeros.

Repair 3 - Score-Key Unification: Create one canonical build_score_key() used by utah_draw_predictive, utah_bonus_predictive, and fallback. Normalize family=BONUS_LE_BIG_GAME, draw_pool=BONUS/REGULAR, species, hunt_class, residency uppercased, point_level int. Log any cohort emission not matching canonical official key.

Repair 4 - Program-Change Classification: Emit official_change_classification column. Rows classified as TARGET_YEAR_OFFICIAL_PROGRAM_OR_QUOTA_CHANGE or NEW_OR_UNCOMPARABLE_OFFICIAL_LANE get excluded from MAE/P90/tail per standard "must be source-classified". Re-run 8-fold. LE should go from blocked to certified.

Repair 5 - LE 32 Gaps: For 32 rows with NO_TRANSITION_EVIDENCE, emit blank p_draw with algorithm_status=NO_TRANSITION_EVIDENCE, reason="No prior cohort at point X for hunt_code Y: source year had 0 applicants and 0 permits at this point, target introduced new cohort - no historical transition preserved", preserve source lineage. Update release checks to treat NO_TRANSITION_EVIDENCE with lineage as documented intentional blank, not unresolved gap. Intentional empty upper-point rows should remain blank unless supported.

Repair 6 - General Deer Preference Fix:

In historical test adapter, do NOT count hunt_total_row + point_level_rows. Use ONLY sum(point_level_rows.regular_permits) per hunt_code+residency. This fixes double-count (Box Elder 225+20 not 450+40).
Preserve separate resident/nonresident regular-round allocations from canonicals, even where Planner shows combined.
Preference probability: p=1 above cutoff, p=0 below, p=remaining_tags_at_cutoff / applicants_at_cutoff at cutoff. Do not forecast 100% at cutoff when official is fractional.
Do not model new entrants from statewide point-purchase totals. Model new entrants from historical 0-point lane transitions in same hunt family only.
Repair 7 - Historical Accuracy on Exact Final Calculation: Run 9 adjacent-year tests including final probability calculation used by website. Count blank predictions as coverage gaps unless source-classified as NO_TRANSITION_EVIDENCE.

Repair 8 - Expand Release Checks: Beyond 13 examples, inventory all 1,592 hunt/residency combinations including historical, zero-quota, insufficient-evidence. Must pass 1,249/1,249 scenarios, no failed requests or console errors.

10. CONSTRAINTS - NON-NEGOTIABLE
Do not use following-year actual values to build forecast. Use only to label/score.
Do not fabricate hunt-specific entrants from statewide point-purchase data
Do not change Utah resident/nonresident allocation rules
Do not convert projected draw lines into guarantees
Do not suppress difficult rows merely to improve metrics
Do not merge different draw designs
Preserve all official source rows and lineage
Prefer fixing source/key/quota routing before changing applicant-behavior assumptions
Do not loosen frozen accuracy limits to get passing result
Do not mutate protected fields: historical draw truth, DATABASE.csv, protected draw-result, permit and quota fields remain unchanged unless explicitly authorized
11. VERIFICATION REQUIRED
39 focused tests must pass (engine, classification, residency, website-contract)
Broader suite: document production-report/source-expectation mismatches, do not hide
Run full 9-fold for all 4 designs on exact final website probability calculation
Verify 7 retained R2 data objects against recorded hashes before publish
Preserve all 4,249 live site files and verify rollback copy
12. PUBLISHING SAFEGUARDS
Local candidate withholds predictions for failing designs. Do not deploy until gates pass.
Release from exact current live site files hash-checked first
Final local public candidate displays certified probability only for certified families (OIL, Premium LE, and after fixes LE and General Deer if they pass)
Bear, CWMU, turkey, antlerless, Dedicated Hunter, youth families remain non-certified and withheld
Nothing staged, pushed, or deployed until verification complete
13. OUTPUT EXPECTED FROM YOU
Diagnostic CSV breaking down 3,886 zero-forecast rows into 6 statuses
Patched build_score_key() and quota source fix
Patched deer adapter (no double count) + preference cutoff logic
Updated COMPLETION_REPORT.md with 0 unresolved gaps and deer MAE under 10 pp if evidence supports
Test logs showing 9-fold results on final website calculation
Continue working until fixed and published online, but do not publish until all frozen gates pass.