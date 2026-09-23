# Hunt Builder Current State

Memory contract: `1.3.0`
Last verified: `2026-09-20`
Machine authority: `governance/engine-authority.json`

This is the required short briefing for Hunt Builder, Hunt Research, prediction-engine, truth, runtime, build, and deployment work. It supersedes older files whose names contain "current" when their generated date is earlier than this document. `WORK_LOG.md` is historical evidence, not current architecture authority.

## Current Classification

### Reviewed corrective shell release live (2026-09-21)

See `docs/CORRECTIVE_RELEASE_20260921.md`. This isolated release preserves the
existing certified runtime and all seven R2 object hashes; it does not certify
new families. It repairs imports, reference-catalog metadata and clean-build
asset retention. Website packaging no longer regenerates data from fixture
fallbacks. The original pending main-checkout work is not included. Both public
hosts are promoted and hash-verified: Pages `094c2549`, Vercel
`dpl_F3Zwa8DGDx19CP7HLdr73jRCo7PM`. Vercel live and Pages preview each pass 1,255
browser scenarios; Pages production passes the 19-case smoke check. All 4,249
Pages and 4,250 Vercel uploaded assets match the release inventory. The exact
old/new hashes and rollback references are in
`governance/releases/20260921-corrective-release.json`.

### Residency-separated acceptance and antlerless calibration review (2026-09-22)

Resident and nonresident prediction identities are now explicitly gated and
reported separately from engine input through historical scoring and Research
display. The eight-fold reviewer writes per-family/per-residency tables; a
passing combined family score may not conceal a failing residency slice. The
Research runtime continues to select exact
`hunt_code + residency + points + draw_pool` rows and regression coverage proves
that resident and nonresident rows cannot borrow one another's probability.

The retained adjacent-year canonicals support Tyler's behavioral concern:
pooled bounded same-lane returns are lower for nonresidents than residents
(deer 0.5491 vs 0.6663, elk 0.5468 vs 0.7019, doe pronghorn 0.5554 vs
0.7388). That observation did **not** justify a hard discount. Matched
development candidates lowering only the nonresident return quantile from Q80
to Q70 or Q50 worsened the exact final probability result: baseline MAE
0.1181081, Q70 0.1193634, Q50 0.1207050, with worse tail behavior. Both
candidates are rejected and the current engine behavior is retained. The next
antlerless repair must measure nonresident switch-in/arrival placement from
prior adjacent-year nonresident lanes; it may not pool resident behavior or
invent hunt choices from statewide point-purchase totals. No forecast,
certification registry, runtime artifact, R2 object or live site was promoted.

Evidence:
`audit_output_real_final/current_code_exact_website_eightfold_20260922_v1/review_residency_slices/`,
`audit_output_real_final/antlerless_residency_return_q80_matched_baseline_20260922_v1/`,
`audit_output_real_final/antlerless_residency_return_q70_dev_20260922_v1/`, and
`audit_output_real_final/antlerless_residency_return_calibration_dev_20260922_v1/`.

The compact supplemental certification evidence is now retained under
`audits/prediction_release_candidates/residency_lane_acceptance_20260922/`.
All eight Resident/Nonresident slices for the four already-certified core
designs pass the unchanged ADR-0006 thresholds with zero false guarantees and
zero unclassified gaps. This tightens the existing certification gate without
changing a probability, certifying another design, or treating 2025→2026 as an
acceptance fold. The public evidence contract is
`public/data/prediction-residency-certification.json`.

A fresh current-code, source-isolated 2017→2018 through 2024→2025 replay
under `audit_output_real_final/residency_current_main_eightfold_20260922_v1/`
reproduced all four combined design results and all eight Resident/Nonresident
slice metrics exactly, with zero false guarantees and zero unclassified gaps
in those designs. The local registry builder now withholds a combined passing
design when its required residency evidence is absent; a resident-only scope
must be declared in the frozen review manifest and match an approved
single-lane program, and the four core designs
cannot narrow their two-lane scope. This is a local gate repair and review,
not a new forecast, registry promotion, R2 upload, or website deployment.

### Canonical lineage repair and long-truth freeze complete (2026-09-22)

The yearly canonical source repair is complete and the long truth has been
rebuilt solely from the ten approved yearly canonicals. The frozen long file
contains 326,523 rows / 103 columns at SHA-256
`e2ec4a7ad80cabab64921f22067b6ab49e6f897ccfa2e7601f3a7f33047e82f2`.
Strict ordered parity with the yearly canonicals passes. Six historical source
groups / 1,929 rows changed only their retained repository `source_path`; their
parent PDFs are byte-identical to the former audit copies and no historical
applicant, permit, probability, ratio, point, residency, or draw-year value
changed.

The 2026 canonical no longer treats generated UOGA PDF presentation rows as an
independent truth source. Before removal, all 1,276 scorable reproduction rows
matched retained UtahDraws endpoint rows across 11,484 numeric cells with zero
mismatches. The cleanup removed 12,051 reproduction rows: 1,276 scorable
duplicates, 181 duplicate zero rows, 13 stale zero rows, and 10,581 empty
presentation rungs without endpoint records. All retained endpoint rows stayed
numerically unchanged. The 2025 adult/youth antlerless canonicals were already
correct: 7,940 rows, 63,520 count cells and 15,880 printed ratios independently
match the retained official PDFs with zero differences.

The official 2024/2025 static-report counts are legitimately different: 2024
has 14 links and 2025 has 13 because the 2025 DWR list has no separate static
Sportsman report. Both years retain their proper antlerless reports. Repair and
rollback evidence is under
`audit_output_real_final/canonical_source_lineage_repair_20260922_v1/`.
Existing prediction certification is not silently rebound to the new truth
hash: current-code eight-fold ADR-0006 replay is required before another
promotion.

### PDF-year feed check and partial DB0008 routing repair (2026-09-22)

Tyler removed the misplaced legacy 2024 antlerless copy from the 2025 folder;
do not restore it. The original 2024 source remains in its correct archive.
Actual 2025 adult/youth antlerless PDFs are
present under `2025/pdf/draw_odds/official_dwr_archive/big_game_antlerless/`;
their 7,940 canonical references also occur in the long file with draw year 2025.
The folder/title cougar difference reflects an earlier drawing year, not proof
of a wrong canonical year. See `docs/PDF_YEAR_AND_FEED_REVIEW_20260922.md`.

Follow-up: the 2024 resolver DOES write 159 ANTLERLESS_REFERENCE rows into the
local predictive successor CSV (source_years_used=2024;2026). Their probability
and applicant/award fields are blank and probability_model=NONE prevents final
odds, but this is an active legacy artifact writer, not only a stored duplicate.
Correct canonical references do not prove past engine builds avoided it.
Separate that reference-writing path and verify exact downstream consumption.

Fresh annual audit checked 132 currently listed official PDF URLs: 131 have
exact local byte matches; 2019 LE/OIL has identical text on all 551 pages but
different PDF bytes. Complete independent 2025 adult/youth comparisons pass:
7,940 hunt-table rows, 63,520 count cells and 15,880 printed ratios, no differences.
The selected canonical/long row-and-cell multisets also match. This does not
certify forecast delivery. Seven Python files still reference the removed
2024-in-2025 path. A separate top-level 2020 antlerless PDF differs from the
official archive on three pages, including EA1089's printed top-row anomaly;
the canonical cites the exact official archive and preserves its carryover note.
Tyler subsequently authorized replacing ONLY that alternate top-level 2020
PDF. Replacement is complete, matches official SHA256 2efb7b6d...564dc7d04,
and its original bytes are hash-verified in a separate rollback folder.
All canonicals and long truth remained unchanged. The engine's default long
input has exactly the same 7,480 adult/youth 2020 source-scope rows and cells
as the canonical; no new forecasts were generated. Receipt:
`audit_output_real_final/antlerless_2020_official_pdf_replacement_20260922_v1/`.
Do not restore the alternate over official bytes. Full annual
counts, legitimate publication differences and remaining boundaries:
`docs/PIPELINE_ANNUAL_SOURCE_AUDIT_20260922.md`.

The classifier no longer labels extended archery as random-only. DB0008's
legacy canonical metadata/redundant-copy accounting remains pending; do not
call the full repair or a fresh acceptance run complete. All original frozen
forecasts remain unchanged. Current classifier code needs a new hash-linked
review before promotion. Failing-family triage identifies CWMU and youth
fallback paths and higher nonresident antlerless errors for the next repair.

### DB1592 / DB1630 Planner discrepancy is non-blocking (2026-09-22)

Tyler explicitly accepted the Planner-versus-regular-draw total discrepancy as
non-blocking. Retained UtahDraws regular-round allocations are DB1592 97 resident
+ 10 nonresident = 107, and DB1630 349 + 39 = 388. Preserve Planner values 200
and 720 as reference evidence; neither a typo nor a particular explanation for
the difference has been proven. This discrepancy alone must not block scoring
or certification, override draw-round supply, or exclude verified hunt lanes.
The allocation verifier reports `REFERENCE_TOTAL_DIFFERENCE_NON_BLOCKING` while
still enforcing exact source cells, hashes, unique residency lanes and R + NR =
regular total. Source-year-only forecasting and all statistical gates remain.
This does not resolve or admit the two unlabeled legacy adult/youth copies;
use their separately verified typed endpoint counterparts without double counting.

### Concurrent-change integrity verified; promotion remains held (2026-09-21)

`processed_data/concurrent_change_audit_20260921.txt` records
`VERIFIED_BUT_NOT_PROMOTION_READY` for the scoped import/helper/frozen-evidence
checks. The crosswalk import-order repair is retained; the requested helper
contract is present. All nine saved coverage candidates and original forecasts
still match their freeze hashes. Fresh outcome-integrity verification confirms
the earlier eight score CSVs remain byte-identical and all 11,781 verified zero
outcomes remain in the 2026 projection. No Bear forecasts were regenerated.

The user identified the Bear change as intentional, but its claimed 400+ scored
rows / below-10-pp MAE improvement is unverified. The source-row counter is not
the joined scoring population. The concurrent diff review found weakened identity
validation; those safeguards are restored while preserving the concurrent priors,
split-code tables and counter. Changed behavior is now labeled
`bear_bonus_phase9_candidate`; it has NOT been statistically accepted. The
classifier preserves intentional blanks for both saved phase8 and new candidate
labels. No frozen forecast regeneration or acceptance registry change.

The source crosswalk now keeps exact row verification separate from legacy
whole-group status. Mixed verified/pending groups are explicitly `PARTIAL`;
unresolved totals are not promoted to verified rows. The 1,333 legacy unverified
groups are not forecast gaps. Follow-up verification resolved 95 of the 97
potentially scorable unverified rows: 87 Sportsman rows (1,068 cell checks) and
eight DB0008 rows (40 applicant/award fields). Two legacy general-deer rows
remain pool-ambiguous; their separately labeled adult and youth endpoint rows
are already retained and independently verified in the canonical. Do not
assign the legacy copies a pool or count them again. Source review remains
BLOCKED, separately from empty displays, aggregate totals and Planner references.
Fresh output: `audit_output_real_final/source97_verified_row_review_20260921/`;
targeted receipt: `audit_output_real_final/source97_resolution_20260921/`.

**Newly verified routing discrepancy:** DB0008 is an extended-archery-only
general-season deer DRAW permit, not availability-only. The retained 2026 Big
Game Application guidebook pages 9/44 and typed UtahDraws endpoint confirm it.
The existing canonical availability labels and the classifier's generic
extended-archery random-target fallback require a scoped metadata/routing repair.
This verification did not change canonical values, routing engines or frozen
forecasts. Do not discard DB0008 outcomes as reference-only to clear a gate.

### Original 1,398 coverage gaps repaired; candidate not promoted (2026-09-21)

Latest scoped candidate review:
`audit_output_real_final/youth_coverage_feed_repair_20260921_v1/review/summary.json`.
All nine folds have zero unresolved coverage gaps. Independent integrity audit
verifies all 1,398 original blocking keys are now scored, with no duplicate
scored keys and every unrelated retained forecast field unchanged. Repaired
youth general-deer score aliases and explicit unmodeled youth placeholder handoff
to the pre-existing exact-source fallback; no adult odds borrowed and copied
prior-year guarantees remain blank.

Combined diagnostic: 137,940 scored keys, 9.0876 pp MAE, 27.6077 pp P90,
10.4031% tail over 25 pp. Youth designs still fail accuracy/sample gates.
Coverage completion is not certification. The 2025→2026 diagnostic remains
separate; two populated unresolved source-youth dimensions are not settled here.

The final protected-file gate correctly fails: source-crosswalk and Bear code
changed concurrently during the run. Corrected only the crosswalk import-order
syntax error, preserving the external addition. Did not revert/adopt the Bear
change. Original frozen forecasts and official canonical/long/DATABASE bytes
are unchanged. 120 focused tests pass, but no current-tree promotion is approved.
See `docs/YOUTH_COVERAGE_FEED_REPAIR_20260921.md` for hashes and per-design results.
No staging, registry change, runtime rebuild, push, R2 upload or deployment.

### Scoring identities repaired; youth source routing corrected locally (2026-09-21)

The preceding identity-only nine-fold review was
`audit_output_real_final/identity_reconciled_rescore_20260921_v4/review/`.
Its 2026 CWMU youth-pool correction is superseded separately by
`audit_output_real_final/identity_reconciled_2026_cwmu_fix_20260921_v5/`.
The latter has exact scored-key/probability parity with V4, but retains distinct
adult/youth source evidence. Across these latest projections there are zero
repeated scored keys and zero conflicting populated actual-key groups. Empty
display records remain separate; all 11,781 verified zero outcomes are retained.

Combined nine-fold diagnostic: 135,963 independent scored keys, 8.6316 pp MAE,
25 pp P90, 9.8939% tail over 25 pp; 1,398 blocking coverage gaps remain, mostly
newly separated youth pools. The adopted eight-fold adult LE, OIL, Premium LE
and general-deer populations meet the numeric/classified-coverage checks; other
families still fail accuracy/coverage/sample gates. No new certification is
granted. Two populated 2026 deer rows still lack verified youth dimensions;
raw 2026 diagnostic matches are not acceptance evidence for those identities.

The current DATABASE hash delta was proved exclusively CRLF/LF, and the fresh
existing feeder audit reports zero unexplained current-field deltas. Authority
records the actual raw hash while retaining the old build digest and explicit
byte-level manifest drift. Project-memory now passes 151 checks.

After frozen-run verification, corrected the owning family runner so explicit
Deer species cannot become pronghorn from the shared label "Antlerless/Doe".
This metadata-only owner change passes regression tests but has not generated
new forecasts or runtime artifacts. Next: verify the remaining youth source-feed
and pending-output path using this corrected owner; do not fill youth odds with
adult probabilities. See `docs/SCORING_IDENTITY_AND_MEMORY_REPAIR_20260921.md`.
No staging, registry change, push, R2 upload or deployment.

### 2026 diagnostic outcome-normalization hold (2026-09-21)

**Update:** the scoring-only repair and frozen nine-fold replay are complete in
`audit_output_real_final/verified_outcome_rescore_20260921_v2/`. All 11,781 verified
zero outcomes are restored only in the scoring projection. Earlier eight score
CSVs and all nine forecast projections are unchanged. A fresh 2026-only official
pull independently matches all 29 retained shared endpoint responses. The
single-actual-row 2026 audit now scores 17,149 rows at 7.7002 pp MAE. Certification
is still held: repeated OIL/Dedicated Hunter structural forecast keys and coverage
gaps remain. See `docs/2026_OFFICIAL_SOURCE_RESCORE_20260921.md`; original reports
and the incomplete preference-guard v1 replay are retained, not promoted.

The closer PDF/endpoint audit found 11,781 exact-source positive-applicant,
zero-award canonical point records with blank observed probability. The saved
2026 actual-ladder scorer excludes 11,655 missing-probability keys, including
5,524 LE and 2,311 OIL. Three visually checked PDF pages match 388 canonical
count cells; no column shift was found in that sample. Already-split 2026 rows
bypass the older adapter's count-derived probability fallback. The original
nine-fold numbers remain evidence, not corrected acceptance results. Next:
repair the existing scoring projection under source/count guards and rescore
the same frozen forecasts; do not tune engine behavior to this biased subset.
See `docs/2026_PDF_PROBABILITY_SEMANTICS_AUDIT_20260921.md`. No protected truth,
forecast, runtime or certification registry changed in this diagnosis.

### All-family nine-fold scoring complete (2026-09-21)

The current task is all nine adjacent years, 2017→2018 through 2025→2026,
not further Bear tuning. New isolated evidence is under
`audit_output_real_final/all_family_nine_fold_20260921_v1/`. Each forecast uses
only canonical files through its source year. Every family is sent through
`mixed_row`; unavailable historical runtime prior/harvest blend inputs are
explicitly `None`. This is a retrospective calculation audit, not proof of
complete historical website-input parity or permission to promote.

Completed: 141,078 scored rows, MAE 8.259 pp, P90 25 pp, tail >25 pp 9.508%,
zero reported false guarantees and 547 blocking gaps. The four core designs
(LE, OIL, premium LE, general deer) pass the combined numerical/coverage gates
in this replay. Other families fail or lack sufficient evidence. The 2025→2026
diagnostic is materially worse (6,285 rows / 16.523 pp MAE); do not hide it in
the pooled average. All 20 protected files are unchanged. No registry or
production change. Full report: `docs/ALL_FAMILY_NINE_FOLD_SCORING_20260921.md`.

### Bear foundation recovery: corrected mechanics replay supersedes first attempt (2026-09-21)

See `docs/BEAR_FOUNDATION_RESTORE_REVIEW_20260921.md`. The working Bear owner had
lost the reviewed source-boundary implementation despite its retained tests and
ADR-0008. Restored dated programs, exact residency/source-year quota proxies,
split-history isolation, component/duplicate checks and source-only blanks from
the hash-verified reviewed baseline; preserved the newer strict availability
guard. The scorer's exact-code option is restored. Broader checks then exposed
the old with-replacement shortcut and missing opt-in adaptive function. Both
were recovered from the later hash-verified random-pool mechanics snapshot.
The corrected v3 run supersedes the initial v2 metrics below. Focused checks:
128 passed; broader family suite: 476 passed, nine recorded artifact/expectation
failures. Do not describe the adaptive function as still missing.

Initial v2 (superseded shortcut) eight-fold final-calculation replay: hunting 9,078 rows,
MAE 12.038 pp / P90 35.294 pp / tail 13.329%; restricted pursuit 308 rows,
MAE 15.245 pp / P90 36.655 pp / tail 22.078%. Zero unclassified gaps, but both
designs FAIL. The separate 2025→2026 diagnostic is not acceptance evidence.
The descriptive nine-fold review exposes 362 pre-ceiling false-certainty cases;
zero reported false guarantees under the old 0.99 ceiling is NOT a repair.
The corrected v3 replay is retained separately; no replacement model or forced
row count was added. No statistical certification is asserted by the recovery.

Corrected v3 is now complete: eight-fold hunting MAE 12.062 pp / P90 35.464 pp /
tail 13.384%; pursuit MAE 15.458 pp / P90 37.581 pp / tail 22.078%, with the same
9,078 and 308 row populations and no unclassified gaps. Both fail. The v3 review
records 364 pre-ceiling false-certainty cases across all nine runs; these remain
visible despite the existing ceiling. Twenty protected data/runtime/registry
files are unchanged. This is separate from the all-family run above.

All 105 deer residency splits / 210 rows balance. Existing DATABASE feeder audit
passes against its retained inputs, but raw-hash approval and release remain
blocked. Truth, DATABASE, normal runtime and certification registry unchanged.
Nothing staged or deployed. This entry supersedes stale counts below, not the
frozen certification thresholds or prior retained experiment evidence.

### BR1000 / Sportsman combined-artifact coverage repair (2026-09-21)

BR1000 remains the resident-only Sportsman Black Bear draw, not Bear bonus or
non-draw availability. Its official 2026 result and Planner identity are present.
The local combined ml_draw_predictions_v1.csv contains only 708 rows/19 codes,
while its companion report claims 40,642/978; only BI1000 remains of ten Sportsman
codes. The normal family builder emits all ten correctly. The prior writer of
the partial combined file has not been identified; no upstream routing defect
has been demonstrated.

The existing materializer now validates Sportsman key coverage before exporting
either combined surface. A separate candidate at
audit_output_phase1_candidate/sportsman_coverage_restore_20260921_v2 restores all
ten Sportsman rows using the existing owner and 2025 input, preserves other-family
cells, retains Planner season wording and withholds certified probability.
Its measured 717-row/28-code report explicitly marks the partial base unsuitable
for promotion. Original local runtime files remain unchanged with verified
rollback copies. This is NOT a complete runtime rebuild or deployment.

The broader Sportsman test also exposed an existing 2017 Cougar parent-filename
expectation mismatch (retained source says 2018_sportsman_odds.pdf). It is not
resolved or relabeled by this 2026 identity repair.

### Bear availability identity safeguard restored locally (2026-09-21)

The current Bear module again defines the validator imported by the existing
materializer. It checks source-target identity, program, residency, duplicates,
and blank draw-probability/point fields for documented non-draw availability.
Unverified pursuit labels cannot qualify as modeled availability. Current
generation confirms BR1001 in both lanes, BR1007 Resident and BR1018 Nonresident.
This restores build import and validation, not Bear statistical certification.
The latest retained nine-fold review has zero false guarantees but still fails
accuracy/tail gates (and restricted pursuit's minimum population).
No probability formula, historical truth, DATABASE or live artifact was changed.
The deer residency staging quality gate now reports Bear import PASS; DATABASE
hash approval and release authorization remain blocked. One saved-runtime test
still fails because local ml_draw_predictions_v1.csv lacks BR1000. No deployment.

### Antlerless phase workflow: narrow repairs, no certification (2026-09-21)

The latest review is `docs/ANTLERLESS_PHASE_WORKFLOW_20260921.md` and
`audit_output_phase1_candidate/pdf_cells_zero_regular_20260921_v1/`.
The follow-up independently extracted every hunt-table row in the retained 2024
adult antlerless PDF: 3,960 canonical rows, 31,680 numeric cells and 7,920 printed
ratios match, including page lineage. This is not an all-year PDF audit. A further
shared-normalizer repair preserves numeric zero in collapsed lanes and gives
explicit regular awards precedence over conflicting legacy drawn totals.
All nine folds were regenerated inside this candidate folder; scores are unchanged.
The isolated suite passes 93 tests. An initial legacy integration test refreshed
local resolver audit/reference outputs; that test now uses isolated copies and
asserts retained output hashes stay unchanged. Canonicals, long truth, DATABASE,
saved prediction bytes and previous candidate evidence match their start hashes.
The existing antlerless owner now preserves explicit zero regular awards,
excludes explicit private-allocation metadata and requires two distinct adjacent
year pairs before using an exact-hunt point-band transition rate. No engine was
replaced and no permit mechanics or acceptance limits changed.

All nine known-year folds were regenerated: 8,772 full-adult-census scores remain.
MAE is 11.620 pp deer / 16.559 pp elk / 12.408 pp doe; all still fail certification.
This is an evidence-contract repair, not a passing demand model. CWMU's saved
current records have no numeric forecasts; neither it nor Bear gains promotion
from source/reference/inventory tests. The prior two stale nonblank test
assertions now validate explicit NO_TRANSITION_EVIDENCE instead; focused and
shared tests pass. DATABASE raw-hash/stale-build gate failures persist.
No production artifact, source truth, DATABASE or certification registry changed.

### Current-hunt filter and selected-point parity repaired locally (2026-09-21)

See `docs/CURRENT_HUNT_ELIGIBILITY_AND_RESEARCH_PARITY_20260921.md`.
The retained 1,848-code catalog is preserved; its new derived selection manifest
admits 1,424 evidence-backed current choices and separately retains 424
historical/noncurrent/unverified reference codes. This is not a fresh DWR census
or 1,424 certified public-draw predictions. No historical truth or DATABASE row
was rewritten.

Local Research now shares the exact selected point row between summary, ladder
and Outlook, prevents ambiguous pool fallback and separates harvest percentages
from draw success. Six local browser checks pass. This candidate is NOT DEPLOYED.

Fresh nine-fold antlerless full-adult-census verification scores 8,772 rows:
deer 11.637 pp MAE, elk 16.558 pp, doe pronghorn 12.410 pp. All three still fail
the frozen accuracy limits; 2,249 missing forecasts remain in the coverage audit.
This known-year replay does not certify or promote antlerless. Two existing
historical-adapter test failures and two existing project-memory DATABASE hash /
stale-build failures remain unwaived. No registry or production artifact changed.

### Bear quota/outcome diagnosis corrected (2026-09-20)

The source-only quota-state and random-outcome review is complete; see
`docs/bear_quota_outcome_calibration_review_2026.md`. The earlier statement
that this was the remaining repair was incomplete. Across 1,412 adjacent lane
transitions, the existing latest same-lane award proxy has lower quota MAE than
two/three-year means or medians, trend projection and a program/residency
Markov mode. Replacing it would reduce accuracy.

A frozen Nonresident probability-cell calibration failed 2022 validation and
worsened the 2023→2024 / 2024→2025 large-error tails. A same-hunt/program/
residency exact-rung transition-median applicant candidate then failed the first
six development folds and was removed before late-fold evaluation. These are
not production modes.

The correct status is not “one known calibration remains.” Current evidence
has exhausted the reviewed source-only quota smoothing, general demand,
cumulative demand, transition ensemble, adaptive demand, thin-lane arrival,
probability calibration and exact-lane median candidates. Bear remains **NOT
CERTIFIED / DO NOT PROMOTE**.

The retained official 2026 Bear result canonical supplied a genuinely unseen
2025→2026 fold after those candidate decisions were frozen. It contains 2,814
public point-level rows across 90 limited-entry and nine restricted-pursuit
codes. The exact final calculation fails again: limited-entry 1,098 scored rows
at 13.045 pp MAE / 38.596 pp P90 / 14.845% tail; pursuit 60 rows at 19.726 pp /
57.591 pp / 25.000% tail. All 129 missing forecasts are source-classified,
unresolved gaps and false guarantees are zero. The combined nine-fold result
is limited-entry 10,176 rows at 11.673 pp / 32.879 pp / 13.001% and pursuit 368
rows at 16.434 pp / 44.444 pp / 21.739%; pursuit also remains below 400 rows.
The next honest new evidence is the next official draw year or newly discovered
official pre-draw residency allocation evidence. Known historical outcomes
must not be repeatedly tuned until they pass.

### Bear nonresident thin-lane review completed (2026-09-20)

The proposed thin-lane repair was evaluated and rejected. The review used the
same eight 2017→2018 through 2024→2025 source-only folds and the exact final
`mixed_row` probability calculation. The 400-simulation hierarchical baseline
still fails: hunting 9,078 rows / 11.507 pp MAE / 32.000 pp P90 / 12.778% tail;
pursuit 308 rows / 15.792 pp / 42.125 pp / 21.104% tail.

An isolated source-calibrated empty-upper-rung arrival candidate changed 991
hunting probabilities across 33 codes, reduced hunting MAE by only 0.016 pp
against its matching 100-simulation baseline, and changed no pursuit row. Its
final results still fail every accuracy gate: hunting 11.502 pp MAE / 32.000 pp
P90 / 12.734% tail; pursuit 15.818 pp / 42.055 pp / 21.429% tail, with only 308
rows. It was removed from the owning engine after evaluation. Defaults,
production probabilities and the certification registry remain unchanged.

No future-year input, resident/nonresident ladder reuse, split-code history
inheritance or unexplained coverage gap was found. The remaining blocker is
recurring thin nonresident quota-state and realized-random-outcome calibration,
not a universal bonus-pool cap or another broad arrival prior. Evidence is under
`audits/prediction_release_candidates/bear_lane_cohort_current_mechanics_20260920_v1`
and `bear_thin_nr_source_arrivals_20260920_v1_100`. Bear remains **NOT CERTIFIED /
DO NOT PROMOTE**.

### Bear demand candidates evaluated through final calculation (2026-09-20)

The controlled comparison is complete; see `docs/bear_demand_forecast_review_2026.md`.
Four demand approaches were evaluated on the same eight 2017→2018 through
2024→2025 comparisons: 9,078 hunting and 308 pursuit scored rows, unchanged
limits, source-only inputs and the final `mixed_row` calculation. Cumulative
stack improves pursuit MAE from 15.245 to 14.543 pp but worsens P90. The new
joint/adaptive candidates do not improve overall accuracy. No candidate passes;
defaults and production probabilities remain unchanged.

The frozen limited-evidence uncertainty evaluator is now implemented and run
using 10,000 whole-group resamples per analysis plus year/hunt/residency and
leave-one-group-out checks. Accuracy and recurring failures block any provisional
label. Known results are not unseen holdouts. All 666 gaps are source-classified;
numerical misses remain scored. Twenty protected files are unchanged.

Evidence roots are `bear_demand_forecast_20260920_v1` and `v3` under
`audits/prediction_release_candidates/`. V2 was invalidated by a concurrent
scorer edit; V3 pins the original scorer. Bear remains **NOT CERTIFIED / DO NOT
PROMOTE**. Four-core registry, two project-memory and 19 broader V3 failures
are unchanged. The seven split codes are three new Dolores seasonal hunts and
four La Sal recodes, not two plus five. BR7237/BR7325 are separately new in 2025
and already have 2025 draw history. ADR-0008's boundary restrictions remain.

Full predictive verification completed at 425 passes / nine prior failures;
afterward a concurrent writer again removed the shared scorer's
`--exact-codes-only` option. Its fresh readback test fails. V3's frozen-scorer
results are unaffected, but current working-scorer integration needs single-writer
coordination. Do not describe the current checkout as fully passing.

### Research evidence display repair (2026-09-20; local, not deployed)

ADR-0010 extends the selected-point certification gate to projected lines,
traffic lights, point-creep and catch-up advice. Unsupported rows display
`Prediction withheld`, without raw/summary probability fallback. The four
certified designs retain their existing probabilities; Bear remains NOT CERTIFIED.
Candidate composite provenance separates current catalog identity/permit
references, historical row lineage, future certification and harvest context.

Historical records remain in the audit archive, not automatically on a current
hunt page. All seven La Sal/Dolores split codes suppress pre-2026 historical
results. Generic applicant/permit counts can no longer generate a historical
result in the browser. Explicit applicable historical-result fields remain
displayable, independently of future model certification. This scoped repair
does not claim a fresh, complete all-hunt identity/crosswalk audit.

No production artifacts or certification registry were changed. The two
pre-existing project-memory failures and 19 broader V3 failures are unwaived.

### Restricted-pursuit limited-evidence policy frozen (2026-09-20)

ADR-0009 and `governance/bear-restricted-pursuit-limited-evidence.v1.json`
record Tyler's approved prospective policy. Their exact SHA-256 hashes are
pinned in `governance/engine-authority.json`. This is a separate local
provisional-review pathway for restricted pursuit only, NOT a relaxation of
ADR-0006 certification or a probability-release authorization.

Before the next revised candidate is scored, freeze its policy/source/code
manifest, complete eligible history census and reviewed hunt/year groups.
Keep all accuracy limits unchanged; require resident/nonresident and recurring
hunt-error checks. Quantify uncertainty with whole hunt/year blocks, whole
hunt histories and whole draw years, not independent point-row resampling.
Only a complete passing review may use **“Provisionally validated—limited
evidence”**, pending a later genuinely unseen draw. Known historical results
cannot become unseen again. No candidate has received that label and the
uncertainty evaluator was not implemented by that policy-only change; the later
demand review above implements and runs it without granting a label.

Bear remains **NOT CERTIFIED / DO NOT PROMOTE**. The 400-row ordinary
certification requirement, four-core `adr-0006-2200616ce0b9` registry and
`certified_p_draw*`-only public contract remain unchanged. Existing failed
scores, two project-memory failures and 19 broader V3 failures are unwaived.

### Bear foundation and split follow-up verified locally (2026-09-20)

**DO NOT PROMOTE.** The current Bear owner now enforces the foundation rules
directly, not only in an audit adapter: source-dated program classification,
reconciled R/NR expansion, no `All` reuse, identical-point deduplication with
conflict rejection, component-award reconciliation, and program/residency-only
calibration. Both bonus and random winners leave their own program's ladder;
restricted pursuit does not borrow hunting point purchases or OTC entrants.
Target-year/future history is rejected and 2026 identity decisions are not
applied to earlier forecasts.

For all seven split codes, the 2026 owner output AND final classification
preserve `NO_TRANSITION_EVIDENCE` with every probability blank. The official
whole-hunt reference totals (2/43/6/27/2/6/14) are expressly NOT residency
allocations or model quotas. `forecast_quota_proxy` remains blank on these
rows. Other drawing lanes use exact immediately prior canonical awards,
`SOURCE_YEAR_CANONICAL_AWARDS_PROXY`, with `quota_is_current_allocation=FALSE`.
No old parent history or pre-2026 pooled calibration may feed the split codes.
One source year in 2027 is not a completed, independent historical test fold.

Final evidence is under
`audits/prediction_release_candidates/bear_program_source_repair_20260919/independent_replay/`:
`five_folds_final_v6`, `release_review_final_v3`, `current_inventory_final`,
`retained_reconciliation_final`, and `crosswalk_test_mirror_final`.
The unchanged five-fold accuracy failures below reproduce through the final
calculation with all implementation hashes verified. All 374 gaps in the
older eight-fold diagnostic are separately source-classified (254 absent
comparable source lanes; 120 zero-award proxies). Its eight forecast files
and 2,124 large numerical errors remain intact; this is not recertification.

Verification: 67 focused tests pass; the full predictive suite has 383 passes
and the same nine pre-existing failure identities. The isolated crosswalk
suite has four passes and reproduces 96/97/105 rows, 994/1110 permit totals,
four recodes, three split children and 91 exact matches without writing the
retained crosswalk. Its stale BR7324 assertion now reflects the actual blank
conservation reference, not an invented positive quota. All 20 protected
files are unchanged against this work's captured baseline. A separate check
of the older 19-file foundation snapshot finds 18 matching hashes and one
pre-existing saved `ml_draw_predictions_v1.csv` difference: old `17c3ea08...`,
current/start-of-work `90cb4f00...`. This difference also exists in the retained
availability-audit baseline and is not caused or repaired by this work. Do
not claim the older 19-file snapshot and current saved artifacts are identical.
The two project-memory raw-hash/stale-build failures and 19 broader V3
failures remain unwaived. An isolated LF-byte candidate matches the recorded
DATABASE hash exactly; no production bytes or frozen provenance were changed.

### Bear post-split boundary and five-fold final-calculation review (2026-09-20)

The controlled review is complete; **Bear remains NOT certified and must not
be promoted**. See `docs/bear_controlled_review_2026.md` and ADR-0008. The seven
La Sal/Dolores Triangle hunting codes use only 2026-forward history, with no
parent inheritance or pre-split pooled calibration. Original unsplit hunts
remain in earlier historical tests; restricted pursuit is separate.

The five PDF-first 2020→2021 through 2024→2025 comparisons now have been run
through the exact final `mixed_row` calculation with import-time source guards,
no historical DATABASE reads, frozen forecasts before actuals and only reviewed
pre-draw crosswalks. Hunting: 5,958 scored, MAE 12.259 points, P90 35.414 points,
13.209% above 25-point error. Pursuit: 253 scored, MAE 13.943 points, P90 34.767
points, 18.972% above 25-point error. Both fail; all 291 coverage gaps are
source-classified. Pursuit has only 267 possible scorable official rows in the
window, below the frozen 400 minimum. The unchanged 0.99 ceiling masks 217
uncapped false-certainty cases and is not treated as a repaired demand model.

Candidate-only registry `adr-0006-731a13966798` keeps every certified probability
blank; the suppression gate passes, not the certification/promotion gates.
Evidence: `audits/prediction_release_candidates/bear_controlled_review_20260920/`
(`five_folds_import_guard_v7`, `release_review_v2`). Current inventory still
represents 99 draw codes / 198 residency combinations plus four availability
products. All 14 split lanes remain blank. The name-only 2023 canonical repair
is prepared, not promoted. All 20 protected data files, the four certified core
designs and production registry remain unchanged. No staging or publication.

The preceding source-build sections below are retained history, not a claim
that the new five-fold review is still pending. The nine pre-existing predictive
test failures, two project-memory failures and 19 broader V3 failures persist.

### Bear PDF-first 2020-2025 history rebuild (2026-09-20, isolated)

Fresh official PDFs, not DATABASE or saved predictions, now independently
produce 24,942 point/residency records and 1,170 lane-year totals. All printed
totals and all 195,840 compared canonical numeric cells reconcile. Six 2023
canonical hunt names are corrupt across 138 rows; the independent candidate
uses the correct PDF names, while protected canonical files remain unchanged.
See `docs/bear_availability_validation_2026.md`, section `2020-2025 PDF Validation`.
Final evidence: `audits/prediction_release_candidates/bear_pdf_history_2020_2025_20260920/assembled_v4/`.

The owning Bear classifier now recognizes verified source-dated PDF identity
before consulting the latest Bear report and no longer loads Sportsman count
data to identify explicit Bear programs. No formula, quota accessor, code
alias or availability allowlist changed. A write-blocked fresh diagnostic
covers all 99 current guidebook codes / 198 residency combinations plus four
correct non-draw records. Its raw probabilities are not certified output.
The prospective evidence gate keeps probabilities blank; seven current codes
have no exact-code 2020-2025 history: the existing Bear crosswalk links four
La Sal recodes to predecessors present in all six PDFs and identifies three
new Dolores Triangle split-child hunts. DWR's 2026 guidebook p. 4 confirms the
boundary split; code lineage is not automatic full applicant-stack transfer.
Dated catalog
evidence for the 24 historical availability product/year combinations was not
located; do not claim they were all 100% available. Current harvest-objective
status also remains unknown, not a guaranteed permit.

Six source years provide five adjacent comparisons, not six executed folds.
This pass builds the baseline and transition audit; it does not execute or
certify historical accuracy folds. Full predictive tests: 333 passed, same
nine pre-existing failures. Focused tests: 58 passed. All 20 original protected
data artifacts remain byte-identical. Both pre-existing project-memory failures
and the separate 19 broader V3 failures remain unresolved. Nothing staged or
published. Four certified core designs and Bear's non-certified status remain
unchanged.

### Bear availability validation and saved-artifact block (2026-09-19)

Current result: local syntax/control-flow and availability-identity safety are
repaired, but saved Bear artifacts are **not valid release evidence**. See
`docs/bear_availability_validation_2026.md` for exact source hashes, page images,
code tables, tests and discrepancies. No production data was regenerated.

Direct inspection of the 2024–2026 official guidebooks confirms 90 hunting-draw
codes and nine separate restricted-pursuit draw codes in 2026. Four is only the
current non-draw product/residency inventory: BR1001 Resident/Nonresident harvest
objective, BR1007 Resident general pursuit, BR1018 Nonresident general pursuit.
The guidebook establishes these program categories but does not print those
three catalog IDs. The availability allowlist has not been expanded.

The saved 708-row ML file contains four BR availability records cloned from
Sportsman Bison, all Bison/Resident, with duplicate BR1001 Resident identity.
The two saved Bear CSVs still contain 19 availability rows; the saved reports
disagree about counts and restricted-pursuit modeling. Fresh availability-only
generation from current catalog identities produces four correct Bear lanes.
Builder and final family-output gates reject cross-species identity, wrong
residency/program, duplicates and draw probability on availability records.

The current checkout also differs from the earlier Bear foundation description
below: its quota accessor still reads target permit context, not exclusively
source-year canonical awards. The earlier fold results remain retained candidate
evidence, **not verified behavior of this checkout**. Restoring/verifying that
foundation is outside this narrow availability repair; the required historical
canonical-truth authority is unchanged. Bear remains uncertified/unpromoted.

Compilation and AST parsing pass. Focused tests: 22 passed; two additional Bear
unit checks pass. Full predictive directory: 327 passed, nine failed, versus
316 passed/nine failed after syntax repair alone. The nine failing test identities
are unchanged; 135/135 is not this checkout's suite. The separate broader V3
19-failure record remains unresolved. Project-memory validation retains the two
pre-existing DATABASE byte-hash failures; no hash or data was rewritten to pass.
Nothing staged, committed, uploaded or deployed.

### CWMU operator-reference exclusion (2026-09-19, local and unpromoted)

Tyler next authorized CWMU exclusion safety in the existing family engine.
Explicit CWMU operator/contact reference records now route to
`NO_ORIGINAL_DRAW_PROBABILITY` with `EXCLUDED_NOT_PREDICTIVE_DRAW`, no raw or
certified forecast fields, and no stale modeled/guaranteed display claims.
Family inference, source-probability fallback, final family materialization
and the certification gate cannot revive these records as public draw odds.
No CWMU forecast has been enabled or certified.

Do not classify a public drawing as non-draw from a season note alone: DWR
requires public CWMU winners to contact the operator for hunting dates
(`https://wildlife.utah.gov/cwmu`). The read-only inventory found 338 CWMU-linked
current identity rows (290 with season-contact notes), 83,240 CWMU-linked
unified-truth records, and zero explicitly labeled operator-reference records
in those populations. This is a preventive boundary repair, not 2,528 repaired
or deleted operator rows. The retained 2025-to-2026 diagnostic still contains
exactly 2,528 `SOURCE_VERIFIED_NO_PUBLIC_ODDS_CWMU_EXCLUDED` dispositions.

Public quota accessors and allotment helpers are unchanged. Removing overlay
allotments from each CWMU identity row produces identical public quota results.
All 25 protected file hashes match, including ten yearly canonicals, unified
truth, DATABASE, production registry/manifest/prediction artifacts, the frozen
core release, Research page, earlier Bear changes and quota helpers. Evidence:
`audits/prediction_release_candidates/cwmu_reference_boundary_20260919/`.

Focused/boundary regressions pass; the expanded run retains the stale registry
count assertion (OIL expected 18,087 versus the frozen certified 34,944).
The broader V3 19-failure record and both pre-existing DATABASE line-ending hash
validation failures remain unchanged. No stage, commit, upload or deployment.

### Bear-only source/program foundation repair (2026-09-19, local and unpromoted)

Tyler authorized Bear as the only next family. The owning `bear.py` now admits
the fresh official yearly-canonical schema, retains source-dated hunting versus
restricted-pursuit identity, and reconciles the published resident/nonresident
columns. Before this repair, direct Bear intake from the current long truth
admitted only 77 ladders per residency in 2017 and none in 2018-2025. It now
admits 90/91/97/100/100/96/96/96/97 exact hunt-program ladders per residency for
2017-2025. No canonical or unified-truth row was changed.

Bear's local quota input is now the exact source-year canonical lane's awarded
permits, explicitly `SOURCE_YEAR_CANONICAL_AWARDS_PROXY`, **not a current-year
allocation**. DATABASE.csv cannot override it. Missing/stale/combined-only
residency evidence cannot supply a probability. Hunt totals are excluded,
identical point duplicates are counted once, conflicting counts fail, and the
2026 code aliases cannot erase historical codes in earlier folds. Retention
and arrival evidence are isolated by Bear program and residency; the hunting
point-purchase table cannot corroborate pursuit arrivals.

DWR R657-62-8 and -19 identify two separate bonus-point programs: limited-entry
hunting and restricted pursuit. A drawn restricted-pursuit winner forfeits that
program's points; keeping that winner at the old pursuit rung would be wrong.
Hunting winners leave only the hunting ladder. Harvest-objective permits and
general pursuit are non-draw availability, and harvest-objective permits do
not forfeit bonus points. No individual cross-program applicant movement is
inferred from aggregate reports. Official rule checked:
https://wildlife.utah.gov/rules/r657-62.

The isolated evidence is
`audits/prediction_release_candidates/bear_program_source_repair_20260919/`.
Its `folds_v2/` replay freezes forecasts before opening following-year actuals,
uses no DATABASE.csv or later-PDF lookup, and reuses the existing projection
and scorer. All eight 2017-to-2025 adjacent folds completed. This is **not** a
certification or final post-family website-calculation test. Hunting has 9,367
scored rows, MAE 20.594 pp and over-25-pp tail 21.672%; pursuit has 311 rows,
MAE 24.375 pp and tail 30.225%. Both P90 errors are 100 pp. There are 374
missing/blank scoreable-actual keys requiring source classification. Numeric
errors remain in the score. The old 75-false-guarantee count belongs to a
rejected candidate. The existing 0.99 ceiling is unchanged; zero formal
false-guarantee flags is not proof that structural certainty errors were fixed.

The four-core published registry `adr-0006-2200616ce0b9`, runtime artifacts,
Research page, all yearly canonicals and unified truth remain byte-identical.
Bear is still uncertified and probability-suppressed. The existing V3 broader
19 failures remain documented. Project-memory validation has a pre-existing
two-check DATABASE byte-hash failure: the working file is CRLF, and its LF
content hash equals the recorded version. Neither that file nor the frozen
hash was rewritten or waived. No staging, commit, upload or deployment occurs
in this Bear repair.

### Completion repair: all four core designs published and verified (2026-09-19)

The separately frozen repair is under
`audits/prediction_release_candidates/core_le_deer_repair_20260919/`.
Registry `adr-0006-2200616ce0b9` certifies all four core designs using nine
source-only adjacent folds and the exact final `mixed_row` calculation. No
threshold or deer probability formula changed. The historical deer quota
adapter now sums point awards once, excluding duplicated hunt-total rows.
Deer has 8,936 scored rows: MAE 6.777 pp, P90 22.038 pp, tail 7.240%, zero
false-certainty errors and zero unresolved actual gaps. LE's 32 blanks were
independently replayed against source-only cohort history and the existing
no-certainty safeguard; they remain blank, with all official actuals retained.

| Certified design | Scored rows | MAE (pp) | P90 (pp) | Error over 25 pp |
|---|---:|---:|---:|---:|
| Limited-entry big game | 51,270 | 7.555 | 18.669 | 8.040% |
| Once-in-a-lifetime big game | 34,944 | 3.875 | 5.527 | 4.115% |
| Premium limited-entry big game | 2,743 | 2.066 | 2.453 | 1.969% |
| General-season buck deer | 8,936 | 6.777 | 22.038 | 7.240% |

All four have zero unresolved scoreable gaps and zero false-certainty failures.
Frozen limits remain MAE <=10 pp, P90 <=30 pp and over-25-pp tail <=10%.
The 32 LE `NO_TRANSITION_EVIDENCE` records are independently documented
abstentions, not invented predictions. Zero carried-forward cohort does not
mean zero applicants at that same point in the prior official report.

The residual LE audit records 125 zero-versus-positive errors over the first
eight folds and 129 over all nine, all retained in numeric metrics. The old
3,886 claim is not reproduced by the current frozen results. The supplied
six-way diagnostic catch-all must not be mistaken for proof of zero demand:
74 residual rows have positive cohorts and no random-pool permit. Do not
exclude numeric errors because of a later quota change or claim perfect
predictions. The exact code/threshold freeze and previous candidates remain
unchanged. The current four-core registry is statistical certification, not
universal hunt coverage or a guarantee.

Independent accounting covers 796 codes / 1,592 lanes: 847 modeled, 100
zero-quota, 356 historical, 7 without comparable history, 6 without transition
evidence, and 276 without a current published allocation. Thus 745 retained
lanes have an explicit nonforecast disposition, including 356 historical lanes;
389 are current nonforecast lanes. All 105 current deer hunts / 210 residency
combinations are accounted for. Only supported certified values may display.

The verified published contract is `research_candidate_harvest_preserved/`.
An additional isolation check caught four derived harvest-context fields in
the first contract. The initial R2 attempt was stopped and all six original
objects restored and hash-verified (`r2_publication/rollback_result.json`). No
Pages deployment occurred in that attempt. The corrected builder preserves
harvest context as well as draw-result/permit/quota values; the release gate
requires explicit zero-change evidence. Broader regression is 356 passed / 19
failed, separately documented in `REGRESSION_FAILURE_REVIEW.md`; it is not an
all-green repository claim. The 51 focused release tests pass.

Deployment `3c71b92f` and `https://huntbuilder.pages.dev/research` both pass
1,255/1,255 scenarios, with zero failed requests or console errors. The actual
summary/index fetch response bytes match the reviewed SHA-256 hashes; all
4,249 deployed file hashes match the isolated release manifest. Exact report:
`audits/prediction_release_candidates/core_le_deer_repair_20260919/production_promotion_report.json`.
The requested `coverage_final_audited.json`, `classifications_final_audited.json`
and `research_final_audited/browser_qa.json` are hash-identical final evidence
aliases within that candidate. Earlier candidates and rollback records remain.

### Superseded diagnostic baseline: core_final_coverage_20260919

The published four-design registry is not proof of complete runtime coverage.
The isolated correction is under
`audits/prediction_release_candidates/core_final_coverage_20260919/`.
It repairs explicit deer residency, source-classifies the ten historical-only
antlerless identities, scores the final `mixed_row` calculation, and inventories
all 796 retained core target codes / 1,592 residency lanes independently of
the prediction output. Missing evidence is a withheld forecast, never a zero
probability or a default Resident lane.

The current official UtahDraws general-deer payload supplies separate regular
round quotas for 105 current hunts. These match exact code, compatible name,
weapon and season dates and are attached as `target_permits_*` only. They do
not replace Board/Planner permit references in DATABASE.csv or public fields.
The fresh source is hash-retained in the candidate's `source_evidence/`; its
quota/identity/season values equal the retained official snapshot. It is
current-target context only and must never be read by a historical fold.
All candidate outputs remain isolated. Nine adjacent historical folds now score
the exact final public calculation, including a coverage gate for present rows
whose probability is blank. This stricter review certifies only OIL and premium
limited-entry. Limited-entry meets the numerical accuracy limits but has 32
unresolved scoreable-actual coverage gaps. General deer has no unclassified gaps,
but fails mean error (10.494 percentage points), 90th-percentile error (39.5 pp),
and over-25-pp tail rate (12.970%). Limits remain 10 pp, 30 pp, and 10%.

The final local candidate is `mixed_final_audited/` with the matching
`research_final_audited/` contract; it withholds LE and general-deer probability.
This retained baseline was not a production release. Do not describe all four designs as universally complete
or use the earlier family-only registry to bypass the stricter release gate.
This baseline remains audit-only; the production record below is the later
verified `core_le_deer_repair_20260919` release, not this rejected candidate.
See `audits/prediction_release_candidates/core_final_coverage_20260919/COMPLETION_REPORT.md`.

### Current production release

- Product phase: `HOSTED_CERTIFIED_CORE_PUBLISHED_NONCERTIFIED_SUPPRESSED`.
- Hunt Research: hosted and materially functional.
- Prediction mechanics: implemented across the declared engine roles below.
- Active forecast year: `2026`.
- Prediction accuracy certified: `PARTIAL_BY_DRAW_DESIGN`; the four core designs below are certified.
- Promotion status: `PARTIAL_FAMILY_PROMOTION_COMPLETE`.
- New engine designs: prohibited without Tyler's explicit approval.

The family-certification gate is implemented and deployed. Runtime
implementation status and statistical certification are now separate. Raw
probabilities remain available only for development and blind scoring; the
certification-aware public contract displays only `certified_p_draw*`
fields. Non-certified rows retain their historical evidence and projected draw
line, but their future probability is withheld. The line is a structural
forecast, never a guaranteed draw.

The current production materialization is frozen under
`audits/prediction_release_candidates/core_le_deer_repair_20260919/`.
Its primary prediction file contains `31,905` rows at SHA-256
`849d9da58fb409232bef8cac9474499b06cfae74b3a4809179bf9be8ff56c6da`.
The successor CSV used by the public contract has SHA-256
`bf647645b9c12be9b4377ec3ac79ffc29f752757b6acc6ce60a125de8a7fc00b`;
its keyed final probability projection is identical to the primary file.
The public contract certifies only `BONUS_LE_BIG_GAME`, `BONUS_OIL_BIG_GAME`,
`BONUS_PLE_BIG_GAME`, and `PREFERENCE_GENERAL_SEASON_BUCK_DEER`; every other
family has blank `certified_p_draw*` fields. Six sanitized R2 objects were
hash-verified after upload with rollback copies under
`rollback/20260919T211214Z/`. The oversized legacy ladder archive was not
replaced and is not consumed by the normal page. Cloudflare Pages deployment
`3c71b92f` and the public alias both pass the same 1,255-scenario browser matrix
with zero failed requests and zero console errors. The prior `d6f6feeb`
deployment and its original rollback evidence remain retained.

The 2026-09-09 post-family carry-forward audit found a separate probability
defect in `engine/utah_predictive_mixed`: although the family engine removed a
random/weighted winner from the returning applicant cohort, the final blend
reintroduced the same outcome through a 60% prior-year success-rate component
and a 20% quota proxy. The isolated correction withholds both components only
for `MODELED_BONUS` rows with an official prior random/weighted winner and
lets the winner-removed cohort forecast own the current probability. It does
not alter preference draws. Against the frozen 33,875-row candidate and the
official 2025 residency lanes, 2,166 bonus rows were affected, including 1,841
certified rows; the legacy blend was higher on 1,809 rows, with median
inflation 5.404 percentage points among those rows and a maximum of 80 points.
The evidence is under
`audits/prediction_release_candidates/random_winner_baseline_suppression_20260909/`.
The correction was rebuilt from the promoted official year canonicals,
re-certified across nine source-only adjacent folds, and promoted on
2026-09-19. Post-mix certification annotates the corrected probability, so the
public `certified_p_draw*` values cannot retain the pre-correction blend.

The separately named year-by-year official-source rebuild is active under
`audits/prediction_rebuilds/fresh_official_draw_truth_rebuild_2017_forward_20260909/`.
Draw years 2017 and 2018 are frozen there as isolated source-truth candidates.
The current 2017 V3 freeze contains 26,310 rows and 981 hunt codes at SHA-256
`5f3942d077c32fe9c73a888c57ab762f740b467d986028d126ca399436538c99`.
All 1,392 pages in its 19-PDF official source set were scanned with zero
unknown roles. Eighteen files match `C:\Users\tyler\Downloads\2017`; that
folder has the November 2016 Sportsman report instead of the correct November
2017 `2018_sportsman_odds.pdf`. The V3 correction also retains the previously
verified cougar boundary: `2018_cougar_*` was drawn October 31, 2017, while
`2017_cougar_*` was drawn November 2, 2016. Relative to the retained canonical,
259 matched cougar rows and 11 Sportsman rows change official values, and 20
obsolete `CG7620` rows are absent.

The repaired 2018 freeze contains 31,031 rows and 1,010 hunt codes at SHA-256
`29f26cd0493e61a082961d0a728356859de6956722f4bc0ddfcaf9be20574f9a`.
Its 13 fresh official PDFs contain 1,436 pages with zero unknown roles. The
candidate matches every retained canonical key and adds 693 official rows: 546
historical cougar and 147 turkey. It corrects an absorbed-report-header name
defect and a second-`Totals` cell shift in the retained hunt-total lanes. Four
public management-buck hunts (`DB1009`, `DB1010`, `DB1051`, and `DB1052`)
retain distinct `MANAGEMENT_DEER` identity but the official
`BONUS_LE_BIG_GAME` design; they are not general-season preference rows. These
2017 and 2018 freezes were promoted on 2026-09-19 with hash-verified rollback
copies.

The repaired 2019 freeze contains 33,478 rows and 1,054 hunt codes at SHA-256
`3a3592de82c6a1168fed18cf3e60f23c00a6fbea40a2874f238fc1eb700163fa`.
Its 14 fresh official PDFs contain 1,531 pages with zero unknown roles. After
normalizing the retained canonical's split-output source names, all 33,478
identities reconcile with zero missing or added rows. Count fields agree except
that the retained canonical labels each of the 11 random-only Sportsman permits
as a bonus permit. The fresh candidate also preserves six antlerless-moose
ratios whose retained text lost the leading `1`, four official Bear half-up
ratio values, and the correct Sportsman elk result of `1 in 10,750.0` rather
than the adjacent mountain-goat value. Six public management-buck codes retain
distinct `MANAGEMENT_DEER` identity and the official `BONUS_LE_BIG_GAME`
design. The 2019 freeze was promoted on 2026-09-19.
Thirteen fresh PDFs are byte-identical to a repository copy; the fresh main
big-game PDF differs only in modification metadata, with identical normalized
text and word geometry on all 551 pages.

Draw year 2020 is now promoted from a complete fresh official-source replay.
The durable inventory contains 16 DWR PDFs and 1,527 pages: 14 model-relevant
sources or supporting reports and two reference-only swan/crane/grouse reports
outside the current model scope. The promoted canonical has 33,363 rows and
1,028 hunt codes, retains all 33,069 prior row identities, and adds 294 rows
from the correct 2020-21 cougar draw. Seven DWR pages repeat point-14 total and
ratio display cells on an empty point-15 row. The canonical uses the zero bonus
and regular component columns for point 15, retains the displayed carryover in
lineage notes, and leaves the actual awards at point 14. The rebuilt
338,574-row long truth at SHA-256
`aed03f2def7809428e9ffe8f557614a3b4836d01f320c5edbee1d1514e178a5c`
has strict ordered parity with the promoted yearly canonicals. The 2026
database remains current target identity and permit-reference context only.

The promoted year-by-year rebuild extends through draw year 2025, with
frozen source-truth hashes `1992af0a73a5fb35e9fe1361d7b971a9cf71e05ac9736d7ee35ad7b8a2542956`
(2021), `0af89ac480c918ae2fca847acbf06d57b0248255cd7ccad5a17967b4cf361ce7`
(2022), `9c0e30adaf45bae0fa4775077d0383f056d590e5ea98a83a4dfc822475fb6792`
(2023), `778299eb8a197a30c269631e762535da794c4ff20c5f2b8e911d72e2ef99397c`
(2024), and `1538e65bfb8ecdf0a0c526e6e0424c1ed6263a3a9cdd8164d6d724e8a3c3fcc1`
(2025). The 2026 UtahDraws endpoint replay returned all 33 requested endpoint
payloads, 1,094 hunts, and 22,304 flat odds rows. Its canonical comparison has
20,520 direct source-value parity rows, one equal-value adult/youth turkey
identity ambiguity on a zero-applicant rung, and no official value mismatch.

The strict source-only certification review now covers nine adjacent folds
from 2017-to-2018 through 2025-to-2026. Every identity exception is frozen
from the applicable target application guide before the target draw; unchanged
codes pass through, while boundary/program changes, splits, eliminations, and
unresolved transitions are blocked. The gap classifier now honors those
pre-draw blocks instead of mislabeling intentionally excluded stacks as engine
omissions, and recognizes DWR's compact `*_dh_odds.pdf` filenames as Dedicated
Hunter sources. Premium limited-entry deer is evaluated separately from
ordinary limited-entry using the official printed `Premium LE` hunt identity.
The final audit has zero unclassified actual gaps and zero false guarantees.
Four designs independently pass every ADR-0006 threshold across nine folds:
`BONUS_LE_BIG_GAME`, `BONUS_OIL_BIG_GAME`, `BONUS_PLE_BIG_GAME`, and
`PREFERENCE_GENERAL_SEASON_BUCK_DEER`. The active registry names the same four
certified designs; Bear, CWMU,
turkey, antlerless, Dedicated Hunter, and under-evidenced youth designs remain
withheld. Overall multi-family certification remains `NOT_CERTIFIED`, but the
four certified designs were rebuilt and re-promoted on 2026-09-19 through the constrained
`certified_p_draw*` public contract. That partial promotion does not certify or
publish probability for any other family.

The fresh rebuild now includes reviewed audit-only hunt-identity crosswalks for
2017-to-2018 and 2018-to-2019. The first contains 1,047 transition rows and
covers all 981 source and 1,010 target hunt codes; 924 rows permit applicant
carry-forward. The second contains 1,078 transition rows and covers all 1,010
source and 1,054 target hunt codes; 963 rows permit carry-forward. Permission
is limited to `SAME_IDENTITY` or `NAME_ALIAS` rows with a common forecastable
draw design and applies only within the same draw-design and residency lane.
Every boundary/program change, split, new hunt, eliminated hunt, and unresolved
candidate is blocked. Six unresolved source candidates remain explicit rather
than guessed. These tables are not integrated into the engine, canonical truth,
runtime, or certification evidence. They remain target-informed identity
diagnostics and are not source-only certification inputs.

## Active Research Runtime

The normal Research page is `research.html`, loaded by `hunt-research.js` and configured by `config.js`.

The canonical split contract loads:

1. `processed_data/hunt_research_2026_summary.json` at startup.
2. `processed_data/hunt_research_2026_split/hunt_research_2026.index.json` at startup.
3. `processed_data/hunt_research_2026_split/hunts/<hunt_code>.json` for only the selected hunt.

The full details bundle remains an R2 fallback. The oversized
`hunt_research_2026_ladder.json` archive and `point_ladder_view.csv` are not
fetched by the normal startup path. This avoids downloading nearly 200 MiB
before the page becomes interactive while preserving the same evidence-backed
selected-hunt rows.

The older engine/ladder/master/reference CSV path is a legacy fallback and is disabled unless explicitly configured. Do not create a parallel Research loader.

The summary, index, full fallback bundle, and legacy data surfaces are R2-backed;
the lazy per-hunt details are included in the Cloudflare Pages bundle.
`governance/engine-authority.json` retains the role and canonical URL for each
active artifact. Local absence of an optional R2 hydration is a warning, not a
code-contract failure.

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

## Harvest Report Library

The public Library registers only the three most recent assembled harvest years—2023, 2024, and 2025—under `HARVEST REPORTS`. The three annual PDFs contain 3,375 normalized official hunt-code rows. Each report displays permit utilization, harvest success, days hunted, hunter satisfaction, annual harvested age, DWR-reported three-year harvested age, the compatible species-specific DWR management objective/current/status measure, and the evidence-gated U.O.G.A. Hunt Unit Quality profile. A U.O.G.A.-styled clickable table of contents navigates by Species / Sex, and the alphabetical hunting-unit index links exact unit names and hunt codes to their result rows. Blank measures remain blank; the reports do not infer missing values, current quota, or draw probability. The separate 2025 permit-utilization and conservation supplement remains registered as a fourth Library file.

The 2025 report contains 1,148 rows: 1,141 current big-game dashboard rows and seven official turkey rows. It includes the official 2025 elk, pronghorn, and moose annual ages plus their DWR-reported 2023-2025 averages. The report is explicitly labeled as the current dashboard/preliminary package reconciled through September 2, 2026, rather than as a replaced final annual package.

An earlier 2017–2025 nine-report assembly and its release remain documented in `WORK_LOG.md` as historical evidence. The current public registry intentionally supersedes that set with the enhanced 2023–2025 reports described above.

## Internal Outfitter Directory

The public GitHub repository does not hold the promoted internal rows. The
Git-ignored local artifact
`local_data/outfitters/outfitters-master.internal.json` is the working directory
of 138 named hunting businesses promoted from the reconciled spreadsheet. It
preserves 7 `Confirmed`, 59 `Needs Verification`, and 72 `Spreadsheet Only`
records without converting those values into the separate legacy
`Vetted/Unreviewed` field. Fishing-only and unclassified businesses are
excluded. `data/outfitter-internal-master-manifest.json` records the promotion
counts and source hash without exposing private rows.

The updated working master now supplies 80 hunting-outfitter USFS/BLM evidence
records. The supplied official USDA Forest Service rosters confirm 70 unique
hunting businesses independently of their contact-record review status. The
Manti-La Sal list, last updated May 19, 2026, contributes 19 matched businesses
with North Zone or South Zone scope. The 2025 Fishlake image contributes 41
matched businesses with whole-Fishlake scope. The prior Region 4 FOIA rosters
remain integrated. Permit confirmation changes neither contact verification nor
spreadsheet review status; among the 70 permit-confirmed businesses, 6 contact
records are `Confirmed`, 33 are `Needs Verification`, and 31 are `Spreadsheet
Only`. Ten remaining federal-area records stay internal leads.

The 761-row local federal coverage review now uses the September 8, 2026 full
Utah DWR ArcGIS boundary snapshot: 685 unique polygons, including two additions
and two name corrections relative to the 683-feature browser-light map layer.
Of 477 eligible unit/species rows, 464 resolve to exact DWR geometry and 13 do
not. Every business tied by exact or clearly close business name to a supplied
official issued-authorization roster participates in the authorization
crosswalk even when its independent contact record is `Needs Verification` or
`Spreadsheet Only`. Ambiguous Cisco and Sunrise Manti-La Sal identities and the
unmatched Chunky Trout Fishlake name remain unresolved rather than being
assigned by guesswork.

A confirmed USFS SUP or BLM SRP area intersecting a DWR unit establishes guide
authorization on the permitted federal land inside that unit. The same mapped
species/unit coverage applies to every sex-specific or hunt-specific selection
that uses that DWR species/unit geometry. A 0.1-acre minimum overlap excludes
boundary-touch artifacts; whole-unit coverage percentage is descriptive and is
not an authorization gate. The current build records 7,639
outfitter/unit/species associations across 70 permit-confirmed outfitters in
354 public coverage rows, including six separately operator-confirmed Wild Eyez
elk-service claims. The legacy 75% comparison would retain only 26 rows across
32 outfitters and therefore does not control eligibility.

The public contract contains the existing 11 vetted contact rows plus 63
permit-confirmed, name-only profiles. Those 63 profiles expose only the business
name and confirmed coverage; their phone, email, website, owner, city, personal
address, and other unverified contact fields remain withheld. The public
coverage contract is `processed_data/outfitter-federal-unit-coverage-review.json`.
Private internal source and evidence artifacts remain outside the public build.

The tracked `data/outfitters-master.json` and root canonical outfitter array are
narrowed to nine unique vetted hunting businesses. Six fishing-only legacy rows
and their tracked logo-source entries were removed from the current tree. Those
11 vetted contact rows remain unchanged; the public feed supplements them with
the 63 permit-confirmed name-only profiles described above.
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
- Current reviewed `DATABASE.csv` SHA-256: `a2b5d1049e3286f43b388dc273dacbd0c27453d42e7d90493a34b1af62a501e7`. The standalone current-identity/current-quota feeder audit is `processed_data/audits/database_current_identity_quota_2026_feeder_audit_summary.json`: it verifies all 1,433 retained DWR Planner records and all 1,848 database rows with zero unexplained current-field deltas. On 2026-09-22, the final three legacy RAC-labeled current rows (`BI6506`, `BI6529`, `BI6539`) were relabeled to the retained DWR Hunt Planner `HaNumber` source only after exact code, 2026 hunt year, species, resident, nonresident and total equality; no permit value changed. Zero current DATABASE rows remain RAC-labeled. It retains the reviewed turkey and private-lands source differences as non-draw allocation context, retains the BR7004 official 18/2/20 draw-result split, preserves the PD1056 corrected 36/4/40 official value, and moves BR7324's 2025-27 conservation-cycle count out of current public-quota fields while preserving it in `conservation_permits_2026_total`. The five antlerless-elk conservation reference codes `EA1180`, `EA1270`, `EA1271`, `EA2041`, and `EA2045` retain their separate four-permit conservation counts while their public-draw quota status remains `NO_QUOTA_PUBLISHED`. The database remains current identity/permit-reference context only; the compact prediction-build evidence intentionally retains its earlier build hash until prediction artifacts are rebuilt and accepted.

The full generated prediction manifest is a repo-external build artifact at `processed_data/utah_bonus_predictive_manifest.json`. Its compact integrity evidence—including pipeline and rule versions, forecast year, row counts, source hashes, and the promoted manifest SHA-256—is Git-tracked in `governance/engine-authority.json`. Code-only validation uses that compact record and performs the full manifest hash and field cross-check whenever the generated manifest is locally hydrated.

The normalized official draw truth is locally hydrated with `339,096` rows for draw years `2017-2026`; SHA-256 `5f617a3f27659787987cbe3c3e6ecd0ea92548abf597c62a543ac5287ff649ed`. The 2017 legacy scope is frozen from retained official source reports, and the 2018 legacy-layout reports are canonically parsed; source-identity normalization retains distinct official scopes rather than merging coarse duplicate keys. On 2026-08-29, the yearly canonicals were corrected by official hunt-code prefix only: 2,723 historical `species` metadata cells are now normalized (for example, Deer at Bear River and Elk at Bear Mountain), with no official applicant, permit, probability, point, source-file, or PDF-page value changed. On 2026-09-02, `857` 2018 point-lane derived probabilities were corrected from rounded DWR `Success Ratio` display values to their exact retained applicant/permit counts; the source `1 in X` text, counts, point rows, and PDF lineage were preserved. The 2026-09-09 source audit proved that the supplied 2021 general-season buck-deer PDF is byte-identical to the retained DWR archive and exactly matches all 2,208 canonical hunt/point rows, applicant and permit counts, success ratios, PDF pages, and recomputed probabilities. It completed the earlier 483-row repair across 21 hunts by normalizing `draw_design` and `hunt_class` in addition to `draw_system_type` and `draw_pool`; no official numeric or lineage value changed. The proven `3,040`-row 2023 false youth-general-deer source lane remains removed after exact multiset reconciliation to the retained youth-antlerless deer, elk, and pronghorn lanes. The frozen long file has strict ordered value parity with all ten yearly canonicals. The prior promoted prediction-build manifest deliberately retains its earlier truth hash until a candidate is separately authorized for promotion. The September 2 live UtahDraws refresh added `2,144` actual 2026 antlerless point/residency/adult-youth rows across `153` public drawn hunt codes to the 2026 canonical. Of these rows, `1,911` have positive applicants and `233` preserve official zero-applicant evidence with blank probabilities. All `262` current Hunt Planner permit-reference rows remain non-scorable identity/quota references. The live source backs `153` of the `162` public drawn references; all nine unmatched references are zero-permit conservation, Expo, or control references. `EA1281` (Mt Dutton, Deep Creek) was removed from the active 2026 database and canonical reference set: its current DWR detail record identifies it as `HUNT_YEAR=2025` and `STATUS=OFF`, the current antlerless-elk list omits it, and the 2026 antlerless guidebook contains neither the code nor Deep Creek. Its `67` resident plus `8` nonresident permits (`75` total) are archived 2025 Hunt Planner values for the Dec. 20, 2025-Jan. 11, 2026 season, not 2026 draw permits. All `36` canonical 2025 EA1281 result rows remain preserved. The official online results are also formatted into one combined and five species-specific 2025-style PDFs under `pipeline/RAW/hunt_unit_database/2026/pdf/draw_odds/official_dwr_online_results/`, with resident and nonresident ladders matched by hunt code. Across all current live endpoint packages, `18,519` canonical rows have direct value parity and one `DB1630` row has multiple equal endpoint candidates; `17,165` rows are certifiable source-value parity and `1,355` are explicitly unscorable because the official source has no applicant or successful-applicant count.

Five complete UOGA-styled 2026 result PDFs are retained under `pipeline/RAW/hunt_unit_database/2026/pdf/draw_odds/official_dwr_online_results/uoga_styled_20260902/`: corrected Antlerless, Big Game, Black Bear, Turkey, and Sportsman. They cover all `29` retained official UtahDraws packages and all `22,018` result rows. Each page uses the supplied UOGA circle logo, the current UOGA black/brown/cream/forest palette, and the 2025 DWR-style resident/nonresident point tables while clearly identifying DWR/UtahDraws as the data source. The generation guard requires every row to have `IsHistoricalData=False`, every populated season to have `LicenseYear=2026`, zero calendar-2025 season starts, and zero `EA1281` source matches; 2027 calendar starts remain valid only when DWR assigns them to the 2026 license year.

The accepted acceptance standard is `docs/decisions/ADR-0006-historical-blind-acceptance-thresholds.md`, with the publication enforcement contract in `docs/decisions/ADR-0007-family-certification-and-publication-gate.md`. Its source-only, physically adjacent review runs `2017→2018` through `2024→2025`; the final pair scores the 2025 drawing even though the corresponding canonical key is named for model year 2026. It explicitly excludes the 2025→2026 comparison. The current deterministic baseline is retained at `audits/prediction_blind_year_to_year/frozen_canonical_long_2017_2025_deterministic_20260906_current_identity_audited_bg/acceptance_review/`. It keeps all `90,145` joined rows and is `NOT_ACCEPTED`: MAE `0.115985`, RMSE `0.280574`, 90th-percentile error `0.400000`, and `11,830` rows (`13.123%`) over 25 probability points. It has `190` false guarantees: `182` limited-entry Bear hunting, `5` restricted Bear pursuit, and `3` Turkey. The source-typed reporting review is retained at `audits/prediction_blind_year_to_year/frozen_canonical_long_2017_2025_deterministic_20260906_current_identity_audited_bg_bear_subtype_reporting/`; no general/unlimited Bear pursuit availability rows are included in this probability population.

The separate fresh official source rebuild has now advanced through physical draw year 2022 without replacing the current certification registry. Its isolated 2021 candidate has `33,789` rows and zero duplicate source identities; it repairs the retained adult/youth turkey scope collision, restores the black-bear parent scope, includes DWR's footnoted one-time Sportsman Cougar row `CG9999`, and assigns the 2021-22 Cougar report by physical draw year. Its isolated 2022 candidate has `34,876` rows and zero duplicate source identities; it keeps adult/youth antlerless and turkey programs separate and assigns the 2022-23 Cougar report to physical draw year 2022. The pre-draw exceptions-only identity evidence now covers through 2021→2022; that final table blocks seven changed bison identities, thirteen eliminated hunts, and ten Bear program changes rather than carrying their applicant stacks. The five early source-only folds through 2021→2022 retain zero formal false guarantees and score `75,559` rows at MAE `0.089087`, P90 error `0.260322`, and tail error `10.114%`. That isolated review remains `NOT_ACCEPTED` because the tail rate is still above the 10% limit and `5,145` scoreable official-actual gaps remain unclassified. The 2021 and 2022 candidates, crosswalks, and fold outputs remain audit-only and unpromoted.

The current machine-enforced review is `audits/prediction_blind_year_to_year/certification_repair_clean_2017_2025_20260909/acceptance_review/`. It reruns all eight physically adjacent folds against the repaired canonical truth and source-classifies each missing scoreable actual against its exact prior-year source. The compact registry is `governance/prediction-family-certification.json`. Four core big-game designs are now locally `CERTIFIED`, all with zero false guarantees and zero unclassified official-actual gaps: `BONUS_LE_BIG_GAME` (49,916 joined rows, MAE `0.070690`, P90 `0.161155`, tail `7.290%`), `BONUS_OIL_BIG_GAME` (34,330 rows, MAE `0.043740`, P90 `0.045455`, tail `4.532%`), `BONUS_PLE_BIG_GAME` (1,912 rows across five folds, MAE `0.020256`, P90 `0.022884`, tail `1.987%`), and `PREFERENCE_GENERAL_SEASON_BUCK_DEER` (7,783 rows, MAE `0.088697`, P90 `0.250000`, tail `9.457%`). Bear, CWMU, turkey, antlerless, dedicated-hunter, and under-evidenced youth designs remain experimental or insufficient and cannot publish certified probability. The overall multi-design registry therefore remains `NOT_CERTIFIED`. This certification is local only: no runtime artifact, R2 object, or live page was promoted.

The certification-aware local materialization now separates raw development probability from publishable probability. It retains raw `p_draw*` fields for scoring, emits `certified_p_draw*` only for a design whose registry status is `CERTIFIED`, and otherwise marks the probability `EXPERIMENTAL_NOT_CERTIFIED`, `INSUFFICIENT_EVIDENCE`, or `NOT_EVALUATED`. The 2026-09-09 isolated materialization from the rebuilt truth produced `33,875` rows: `26,486` certified, `6,319` experimental, `416` insufficient-evidence, and `654` not-evaluated. Its publication audit found zero unauthorized certified-probability rows. All `28,613` rows labeled `MODELED_BONUS` carry `p_draw`; two recovered legacy Bear point rows explain the increase from the preceding materialization. Probability-less bonus rows are now explicitly pending instead of modeled, and the primary CSV surface has 212 unique columns with no duplicate header names. The Research source treats a future line as a `Projected Draw Line`; it does not convert a selected point level above that line into 100% odds. These changes are local and have not been built into or deployed over the hosted release.

The requested direct same-hunt, same-residency cumulative-applicant-stack candidate was developed on `2019→2020` through `2022→2023`, frozen, and then tested on the previously unopened `2023→2024` and `2024→2025` folds. It failed the Bear limited-entry gates in both phases. Development had `4,755` rows, MAE `0.120384`, P90 `0.361654`, tail `13.165%`, and zero forecasted-certainty failures. Holdout had `3,216` rows, MAE `0.127443`, P90 `0.375429`, tail `14.583%`, and one forecasted-certainty failure. The matching hierarchical baseline was better on every holdout accuracy measure and had the same one certainty failure, so the cumulative candidate was rejected and removed from the selectable engine modes. Its immutable audit evidence remains under `audits/prediction_blind_year_to_year/bear_lane_cumulative_sparse_gamma_development_2019_2023_20260907/` and `audits/prediction_blind_year_to_year/bear_lane_cumulative_sparse_gamma_holdout_2023_2025_20260907/`.

The retained audit-only `lane_cohort_hierarchical` Bear candidate was then run through all eight adjacent folds at 400 deterministic samples. Limited-entry Bear improves materially over the deterministic baseline—from MAE `0.157690` to `0.113279`, P90 `0.565000` to `0.333333`, tail `16.811%` to `12.634%`, and `182` to `34` forecasted-certainty failures—but still fails every ADR-0006 accuracy gate. Restricted pursuit improves from MAE `0.174980` to `0.145782`, P90 `0.429231` to `0.375000`, tail `21.887%` to `18.006%`, and five to one certainty failure, but has only `311` joined rows and is also insufficiently evidenced. The full candidate remains off by default, unpromoted, and uncertified at `audits/prediction_blind_year_to_year/bear_lane_cohort_hierarchical_2017_2025_20260907/`. The 35 remaining exact-100 errors are not caused by applicants over 25 points or a missing unit crosswalk: 31 occur in the thin-history `2018→2019` fold, three in the next two early folds, and one in `2024→2025`. They arise when the aggregate public history has no source-supported rival arrival above the focal rung; changing that assumption after opening the holdout would require new prospective evidence before certification.

The existing, source-backed Bear returning-cohort uncertainty layer was then tested—not promoted—at 400 deterministic samples in `audits/prediction_blind_year_to_year/frozen_canonical_long_2017_2025_bear_source_calibrated_tail_mixture_20260906/acceptance_review/`. It preserves the exact same `90,145` scored keys and reduces false guarantees from `190` to `78` (`75` Bear plus the same `3` Turkey), with MAE `0.115837` and RMSE `0.280042`. It remains `NOT_ACCEPTED`: the P90 remains `0.400000`, and its tail grows slightly to `11,837` rows (`13.131%`). The active/default estimate remains deterministic; no candidate is certified or promoted.

The remaining `75` Bear false guarantees are evidence about unmet, lane-specific high-point demand—not missing official records or a permit-split problem. They occur in 2018→2019 through 2022→2023, are `72` resident and `3` nonresident cases, and all land at a following-year mixed cutoff (`54`) or below the following-year draw line (`21`). Seventy-four retain an explicit exact-code crosswalk and the remaining legacy case is also the identical `BR7209` code, so a code-transition explanation is not supported. Every remaining row still has a candidate P10 of `1.0`, so a generic probability cap would merely conceal the error. No PDF was re-ingested, no database or canonical truth was replaced, and no active runtime, prediction manifest, R2 object, or deployment was changed.

The durable source boundary for a future Bear entry/switch model is now `data_truth/point_purchase_truth/BLACK_BEAR_HUNT_LANE_TRANSITION_CONTRACT.md`. Public DWR reports and the UtahDraws endpoint remain aggregate-only evidence; they do not connect a person’s prior Bear outcome or point purchase to a following-year hunt selection. R657-62-8 confirms that DWR retains the electronic application record needed to make that connection, while the guidebook keeps individual results private. The only acceptable extension is a DWR-produced, de-identified, aggregate prior-activity-to-next-first-choice transition matrix that meets the contract’s lineage, adjacency, residency, suppression, and held-out validation gates. Until such an extract exists, no additional hunt-level entrant allocation is permitted.

The retained official 2018–2022 black-bear PDFs contain separate resident and nonresident point ladders, while the canonical source rows retain their combined values. The hash-linked extraction at `data_truth/draw_results_truth/validation/black_bear_2018_2022_pdf_residency_ladders.csv` recombines exactly to all five canonical years, with no missing point keys or value disagreements. The prior 2018 canonical omitted the retained Black Bear report; it was rebuilt from the ten retained official report parents, compared so that every non-Bear row and the existing `BR1000` Sportsman row remained identical, then promoted with a hash-verified rollback copy. `draw_results_long.csv` is rebuilt solely from the canonical yearly truth and now has `338,802` rows, including the later frozen 2017 canonical promotion, the `2,144` newly promoted official 2026 antlerless result rows, the exclusion of the misclassified EA1281 permit reference, and the removal of the proven 3,040-row 2023 duplicate lane. The extraction remains validation truth: the engine must not use a combined-residency row as a resident or nonresident odds ladder. The 2021→2022 paired source-and-held-out lane fold found a narrowly scoped defect in the audit-only historical permit proxy: it summed broad resident/nonresident columns from both normalized lane rows and doubled the max-point/random permit allocation. The repair now uses each lane's scoped `total_permits` once. The source-only rerun has zero duplicate forecast keys and reduces Bear from `68` to `53` false guarantees and MAE from `0.402231` to `0.323858`; it remains **NOT_ACCEPTED** because every remaining false guarantee is a max-pool demand miss, not a combined-lane or repeated permit-allocation defect. The attempted generic demand-scenario adjustment is explicitly not retained.

The paired Bear lane-fold replication is complete for `2018→2019`, `2019→2020`, `2020→2021`, and `2021→2022`. Every source file physically excludes later official truth and every Bear leakage check passes. The archived classifier repair now carries the retained PDF page's explicit `TRUE_BEAR_BONUS_DRAW` or `BEAR_PURSUIT_BONUS_DRAW` identity only on the audit's official residency-lane projections; it does not alter canonical truth or classify rows from a code prefix, permit total, or generic legacy label. The reruns now produce deterministic Bear rows in every earlier fold: `3,600` rows across `75` hunt codes for `2018→2019`, `4,464` across `93` for `2019→2020`, and `4,176` across `87` for `2020→2021`.

On 2026-09-10, the fresh 2018 and 2019 official-source replays repaired the underlying rotated-page classification for `BR1008`-`BR1013`. Each replay retained every prior fresh-candidate row key and every applicant, permit, and probability measure; only 126 metadata rows per year changed from a numeric pseudo-name/limited-entry routing to the published Book Cliffs, La Sal, or San Juan pursuit name and `RESTRICTED_BEAR_PURSUIT` routing. The repaired frozen hashes are `29f26cd0493e61a082961d0a728356859de6956722f4bc0ddfcaf9be20574f9a` for 2018 and `3a3592de82c6a1168fed18cf3e60f23c00a6fbea40a2874f238fc1eb700163fa` for 2019. The reviewed crosswalks now allow all six same-code pursuit identities to carry only inside that design and residency lane. Crosswalk-aware isolated diagnostics at `audits/prediction_rebuilds/fresh_official_draw_truth_rebuild_2017_forward_20260909/isolated_crosswalk_aware_full_engine_folds_bear_pursuit_repaired/` score 13,244 rows at MAE 0.092796 for 2017-to-2018 and 14,619 rows at MAE 0.088596 for 2018-to-2019. Coverage remains 88.34% and 90.10%, respectively. Because these diagnostics use a reviewed target-transition table, they are explicitly non-certifying; no canonical, unified truth, runtime, registry, R2 object, or live page was changed.

The certification-eligible replacement is the strict source-only replay under `audits/prediction_rebuilds/fresh_official_draw_truth_rebuild_2017_forward_20260909/strict_source_only_pre_draw_crosswalk_folds_2017_2019/`. Its exceptions-only crosswalks use source-year truth plus hash-frozen target application guidebooks that state deadlines and result dates; target draw-result identity is not read when the crosswalk is built. Unlisted source codes pass through unchanged, the single verified Chimney Rock CWMU recode `MB6204` to `MB6240` may carry within its existing design/residency lane, and every documented split or boundary change is blocked. The 2017-to-2018 fold scores 13,248 rows at MAE `0.092919`, RMSE `0.239462`, applicant-weighted MAE `0.037899`, and 88.40% possible-row coverage. The 2018-to-2019 fold scores 14,616 rows at MAE `0.088541`, RMSE `0.232632`, applicant-weighted MAE `0.060453`, and 90.06% coverage. Both have zero formal false guarantees. This closes the 2018/2019 source and identity repair, but does not by itself change the full ADR-0006 registry or authorize production promotion.

This repaired coverage replaces—not validates—the earlier fallback score. On held-out official lanes, `2018→2019` has `31` scoreable Bear rows, MAE `0.404796`, and zero false guarantees; `2019→2020` has `1,168`, MAE `0.324195`, and `61` false guarantees; `2020→2021` has `1,248`, MAE `0.356603`, and `98` false guarantees. The `2021→2022` repaired permit-proxy fold remains `1,205` scoreable rows, MAE `0.323858`, and `53` false guarantees. The classifier repair therefore resolves archive coverage but shows that the deterministic model is not accepted and that high-point demand behavior must not yet be changed. Combined history must never be treated as a resident or nonresident ladder.

The latest unpromoted diagnostic candidate at `audits/prediction_blind_backtests/2025_to_2026_truth_2018_2026_20260828_bear_source_repair/` froze its forecast before reading 2026 actuals. It uses the current database SHA above and has frozen prediction SHA-256 `5d0becac14bbeb84b96725acd917c4e7bc8a4a799d23b0a740b736874be8d90a`. The retained, hash-verified 2025 DWR black-bear report corrects a stale source path that had caused the engine to treat every current `Pursuit Only`/`O.T.C.` Planner label as non-draw. The repaired audit joins `14,040` official actual keys with zero duplicate prediction-key groups, zero duplicate actual-key groups, and zero unexpected engine/key gaps; all `72` formerly excluded bear actual rows now have a forecast. The remaining `2,585` non-joined keys are fully source-classified: `2,528` intentionally excluded CWMU public-odds rows and `57` current additions with no comparable official historical ladder. Probability MAE is `0.122557`, RMSE is `0.290447`, `1,976` rows exceed 25 percentage points absolute error, and there are `229` false guarantees (`63` bear rows). This diagnostic is explicitly **not accepted** and is excluded from ADR-0006 acceptance; its purpose is source-coverage and targeted-rule repair, not certification.

On `2026-09-10`, the certified-core contract replaced six production R2 objects: summary `42b46d8c...0c87`, index `711e4bea...1fc`, details `2811bcb5...7399`, point ladder `cb8a33fa...5dd5`, predictive runtime `9143d741...836`, and public ML predictions `a4f2ddf6...7df`. Each live object was downloaded after upload and matched the candidate SHA-256 exactly. Exact pre-release copies are retained under `rollback/20260910T154642Z/`. The 512 MiB legacy ladder archive remains at `1a45732c...44a5d`; Wrangler could not upload the 434 MiB candidate replacement, and the current page does not consume that archive.

The released contract contains `3,419` summary rows, `102,229` point-ladder rows, a current selection index of `1,471` hunt codes, and selected-hunt direct details. All `33,875` prediction identities are preserved, and non-certified rows have no public probability. The initial all-hunts point-ladder download was replaced by lazy per-hunt details after production QA exposed a startup delay. Final deployment `17d45b08` and `https://huntbuilder.pages.dev/research.html` both pass the 13-scenario certified/suppressed matrix with zero failed requests and zero console errors.

## Remaining Certification Boundary

1. The formally adopted overall historical acceptance review remains `NOT_ACCEPTED`, but certification is enforced per design. Limited-entry, once-in-a-lifetime, premium limited-entry, and general-season buck deer pass the complete machine-enforced contract and are promoted. Bear, CWMU, turkey, antlerless, Dedicated Hunter, and under-evidenced youth designs still fail an error, coverage, or evidence-volume threshold and remain probability-suppressed.
2. The `57` 2026 actual rows reduce to six current hunt codes (`BI6539`, `BR7021`, `BR7126`, `BR7238`, `DB1109`, `DB1121`). Their retained crosswalk verifies no exact 2018-2025 canonical draw predecessor, documents the dated application-guidebook listing, and keeps them deliberately unscored. They must not receive a borrowed same-unit probability unless an official DWR predecessor mapping is retained.
3. The full all-family system must still be described as partially certified. No aggregate label may imply that suppressed families have passed.

These boundaries prohibit extending publication beyond the four certified designs. They do not undo the completed core promotion or authorize another redesign.

## Approved Continuation Path

1. Review only the remaining `75` Bear false guarantees by subtype, residency, point rung, permit split, and source-backed applicant-cohort behavior. Repair only another demonstrated simulator or cohort defect; do not use combined-residency rows, future truth, or a generic probability cap.
2. Retain `EB3100` resident point 12 as an explicit unresolved first-fold mixed-cutoff case unless an official source-backed mechanic explains its held-out result. Do not force it below 100 percent merely to satisfy the acceptance gate.
3. Keep the six no-exact-history codes source-classified as intentionally unscored rather than unresolved engine gaps.
4. Preserve `engine/utah_predictive_mixed` as the final probability blend and `engine/utah_draw_predictive` as family authority.
5. For any future release, repeat the isolated materialization, publication gate, rollback backup, hash verification, and representative Research UI matrix. Never widen the certified allowlist without new ADR-0006 evidence.

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
python -m engine.utah_bonus_predictive.materialize --output-dir audits/prediction_release_candidates/<new-candidate>/materialization --forecast-year 2026 --history-years 2017,2018,2019,2020,2021,2022,2023,2024,2025
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

## 2026-09-20 Full-engine current-target certification check

The full 2025-source/2026-model-target audit is retained in two separately named candidates. The original 10,367-row scorer result (MAE `0.0792699873`) is preserved at `audits/prediction_release_candidates/full_engine_2025_to_2026_unfiltered_10367_replay_20260920/` with the exact original scorer hash `075d9580c5f2214da3e12aa33a57f5577b32d8ee67f1afc58e9364b9fba583d6`. It remains a superseded mis-year-join diagnostic.

The corrected year-filter result is preserved at `audits/prediction_release_candidates/full_engine_2025_to_2026_year_filtered_7909_20260920/`. It scores `7,909` rows at MAE `0.0684251859` and removes the demonstrated Antelope Island 2021 join. Its scorer hash is `85bb42b60aa179486e9ac069adebf83473bb171b0d11bb172d089229e74e1b9a`. The retained output is not rewritten to fit a claim: its emitted `actual_draw_years_indexed` keys are `2025` and `2026`, while `actual_model_target_years_indexed` contains `2026` and `2027`, because the implemented filter accepts either year field equal to the requested target. This discrepancy is release-blocking evidence, not a reason to discard the corrected audit.

No new family is promoted. Limited-entry remains blocked by the retained strict 10.145% over-25-point tail finding; once-in-a-lifetime retains recurring hunt/regime/residency failures; premium limited-entry has only 76 scored rows in the corrected target audit; and general-season buck deer has zero scored rows. Bear remains not certified and excluded from promotion. Existing historical-fold registry decisions are not silently revoked or widened by this current-target diagnostic.

The full predictive suite completed with `424 passed, 10 failed`: the same nine known failures plus the anticipated concurrent-writer `--exact-codes-only` integration failure. The shared scorer was not overwritten to conceal it.

## 2026-09-20 Bear random-pool mechanics correction

The documented Bear random-pool question has now been resolved in the owning module and reviewed in `docs/bear_random_pool_mechanics_review_2026.md`. Bear does not accept group applications. The former multi-permit shortcut repeatedly sampled ticket share with replacement; the corrected calculation ranks each application's retained minimum random number without replacement, after removing max-pool winners. Focused sanity checks reproduce `17/20` for a 3/2/1-weight, two-permit pool and `2/3` for three equal-weight applications competing for two permits.

The full eight-fold exact-final-calculation candidate is retained under `audits/prediction_release_candidates/bear_random_pool_mechanics_20260920_v2/`. All `9,078` hunting and `308` pursuit score keys are preserved; `666` forecast gaps are source-classified and unresolved gaps remain zero. All 20 protected files are byte-identical.

Correct mechanics do not certify Bear. Hunting scores 12.062 pp MAE, 35.464 pp P90 and 13.384% over-25-point error. Pursuit scores 15.458 pp MAE, 37.581 pp P90 and 22.078% over-25-point error. Nonresident hunting/pursuit MAE is 21.541/22.981 pp. The prior shortcut's slightly better scores were accidental compensation for over-optimistic thin-lane forecasts, not evidence that it represented Utah's rule.

Release decision remains **DO NOT PROMOTE**. No registry, saved prediction, R2 object or website changed. The next repair is the nonresident thin-lane probability contract and recurring hunt/year/residency failures—not Bear party logic, another display filter, or another applicant-demand adjustment without new evidence of a demand defect.

## 2026-09-21 current canonical and source crosswalk audit (local only)

The named current master at `data/utah/official_downloads_2026/hunt_master_canonical_2026.csv`
is under official current-code review, not an approved complete replacement release
inventory. Fresh Planner matrix/detail evidence has 1,426 explicitly 2026 codes
versus the master's 1,288: 171 current codes missing from master and 33 master
codes without matrix confirmation. Direct follow-up confirms PB5329 as current,
leaving 32 for noncurrent/program review. Absence is not retirement. No current or
historical canonical was rewritten and no promotion filter was applied.

`docs/CURRENT_CANONICAL_PLANNER_REVIEW_20260921.md` and
`docs/SOURCE_MAPPING_CROSSWALK_REVIEW_20260921.md` record the evidence. Requested
current-code review exports are in `processed_data`; final evidence-enriched
source mapping is in `audit_output_phase1_candidate/source_mapping_crosswalk_20260921_v3`.
PDF/code/page presence and guidebook listings are not numeric parity or automatic
predecessor approval. The source closure gate remains BLOCKED, including missing
adult/youth source dimensions and unresolved total/Sportsman/reference scopes.
Existing DATABASE raw-hash/stale-build project-memory failures are not waived.

## 2026-09-21 source-pool metadata applied; no engine rebuild

`docs/SOURCE_POOL_LABEL_RECOVERY_20260921.md` supersedes the broad blank-youth
blocking counts above. Recovered 27,751 missing endpoint-pool labels in the local
2026 yearly canonical and synchronized exactly those cells into long truth, with
hash-verified rollback copies. No numbers, other metadata, engine, forecast or
live artifacts changed. Post-application: 21,806 rows / 109,030 populated numeric
cells match retained raw endpoints; full long/canonical ordered-value parity
passes 338,574 rows. Youth-only hunt eligibility remains separate from IsYouth.

Two positive rows still have identical adult/youth source vectors: DB1592 NR at
3 points and DB1630 NR at 2 points. Another 518 unresolved records have no
applicants/awards; 10,236 absent endpoint rungs are explicitly structural, and 272
reference records are not draw truth. General-deer Planner totals do not remove
the official endpoint residency lanes. Historical freeze reports are retained;
new hashes and the local-only application are recorded in engine-authority.json.
No certification or release approval was changed; DATABASE blockers remain.
