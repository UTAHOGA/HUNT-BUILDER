# Canonical Research Page Engine Contract

This is the controlling contract for the Hunt Research page, its raw/source data feed, and the prediction-engine outputs displayed on that page.

It does not control the Hunt Builder / Hunt Planner entry page, boundary split delivery scaffolding, GeoJSON, KML, or page-flow rebuilds. Those surfaces may support display, but they are not allowed to redefine prediction truth.

## Controlling Principle

The Hunt Research page must answer this question:

Are we feeding the Research Page and prediction engines the maximum truth-backed scorable data available, and are we generating the maximum accurate runtime prediction output without leakage, invalid assumptions, silent drops, or unsafe website display?

The answer must be one of:

- `YES - PROMOTION_READY`
- `YES, BUT MORE REPAIRS ARE AVAILABLE - PASS_WITH_REPAIR_CANDIDATES`
- `NO - FAIL_BLOCKED`

## Identity Contract

`hunt_code` is the primary display handle, but it is not the full prediction-engine primary key.

The canonical Research Page prediction key is:

- `hunt_code`
- `target_year` or `actual_draw_year`
- `engine_family`
- `residency` when applicable
- `point_level` when applicable
- `draw_pool` when applicable

This prevents collision with Hunt Builder / Hunt Planner delivery surfaces that are keyed first by hunt code and boundary/display metadata.

## Truth Contract

Actual draw truth may come only from official source data or normalized canonical truth with retained lineage.

The current controlling actual-truth universe is:

- `data_truth/draw_results_truth/normalized/canonical_yearly/*.csv`

The current controlling reference universe is:

- `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`

Reference data can define hunt existence, metadata, permit/allocation context, and display eligibility. Reference data is not actual draw-result truth.

## Research Page Runtime Contract

The page-facing Research contract currently loads:

- `processed_data/hunt_research_2026_summary.json`
- `processed_data/hunt_research_2026_split/hunt_research_2026.index.json`
- `processed_data/hunt_research_2026_split/hunt_research_2026.details.json`
- `processed_data/hunt_research_2026_ladder.json` when present
- `processed_data/hunt_research_2026_ladder_preference.json` as the current existing ladder JSON surface

These files are runtime/public delivery surfaces. They are not allowed to become actual truth unless their fields trace back to the canonical truth universe.

## Engine Feeder Contract

The Research Page engine feed currently includes:

- `processed_data/draw_reality_engine.csv`
- `processed_data/draw_reality_engine_v2.csv`
- `processed_data/draw_reality_engine_predictive_v2.csv`
- `processed_data/point_ladder_view.csv`
- `processed_data/hunt_master_enriched.csv`
- `processed_data/hunt_unit_reference_linked.csv`

The validator also cross-checks the declared feeder contracts in `tools/engine_feeder_contract.py` where applicable.

## Engine Families

Every row must resolve to one of:

- `PREFERENCE_DRAW`
- `BONUS_SPLIT_DRAW`
- `YOUTH_RANDOM`
- `AVAILABILITY_ONLY`
- `OTC_CAPPED`
- `OTC_UNLIMITED`
- `DIRECT_ALLOCATION`
- `HARVEST_FEATURE`
- `POINT_LADDER`
- `MIXED_DRAW`
- `UNKNOWN`

Availability-only and OTC-unlimited rows must not receive fake draw odds.

## 2027 Holdout Rule

Unreleased 2027 actual results for these families must be held out from scoring until official public results exist:

- `preference_antlerless_deer`
- `preference_antlerless_elk`
- `preference_doe_pronghorn`

Held-out rows are not prediction failures and must not penalize calibration or accuracy reporting.

## Special Code Policy

The following 2026 codes are valid bonus-point-only purchase codes, not hunt codes:

- `BER`
- `BIS`
- `BPU`
- `DBS`
- `DEE`
- `DHL`
- `ELK`
- `GDR`
- `GOA`
- `MOO`
- `PRO`
- `RMB`

They may appear in feeder files for purchase/point accounting, but they must not be scored as hunts and must not be required as Hunt Research runtime hunt rows.

All individual cougar `CG*` reporting/unit codes collapse forward to the one current open-season code:

- `CG9999`

The Research Page should carry `CG9999` forward for cougar open season and terminate the individual `CG*` reporting codes from current hunt-code runtime.

`EA1287` is terminated for 2026 Research runtime unless a source-backed prior-year crosswalk is added. Historical/RAC traces may remain in audit/reference files, but `EA1287` should not be treated as a current runtime hunt code.

## Coverage Rules

If canonical truth contains more eligible scorable hunt codes than the engine feeder, every missing code must be classified as a legitimate exclusion, repair candidate, or blocker.

If the feeder contains more hunt codes than canonical truth, the extra codes must be classified as one of:

- `reference_only`
- `availability_only`
- `otc`
- `non_scorable`
- `future_hunt_code`
- `stale_or_unsafe`
- `blocker`

If runtime output contains fewer hunt codes than feeder input, every missing code must be explained.

If runtime output contains more hunt codes than feeder input, that is a blocker unless an approved reference-expansion rule explains it.

## Count Block

The count block is populated by:

```text
python tools/validate_research_page_canonical_contract.py --repo . --write-audits --strict --no-promote
```

The validator writes the audited values to:

- `audits/research_page_canonical_contract/<timestamp>/CANONICAL_COUNT_BLOCK.csv`

No count in this contract should be hand-maintained. If the generated count block is missing, promotion is blocked.

## Required Audit Package

Every complete validation run must write:

- `ENGINE_RESEARCH_PAGE_CANONICAL_CONTRACT_AUDIT.md`
- `CANONICAL_COUNT_BLOCK.csv`
- `FEEDER_TRUTH_SOURCE_AUDIT.csv`
- `CANONICAL_TRUTH_UNIVERSE_SUMMARY.csv`
- `SCORABLE_TRUTH_ROWS.csv`
- `UNSCORABLE_TRUTH_ROWS.csv`
- `ENGINE_INPUT_COVERAGE_AUDIT.csv`
- `ENGINE_DROPPED_HUNT_CODES_DETAIL.csv`
- `RUNTIME_OUTPUT_VALIDATION.csv`
- `WEBSITE_METRIC_DISPLAY_MAP.csv`
- `PROMOTION_READINESS.md`
- `TEST_RESULTS.txt`

## Promotion Status

`PROMOTION_READY` requires no blockers, no target-year leakage, no unsafe truth source, no schema failure, no invalid probability/percent, no quota arithmetic blocker, explained drops, current runtime output, complete website display mapping, and passing tests.

`PASS_WITH_REPAIR_CANDIDATES` means no safety blocker was found, but more truth-backed rows or hunt codes can still be added through documented repairs.

`FAIL_BLOCKED` means promotion is blocked by leakage, unsafe truth, schema failure, invalid probabilities, quota failure, major unexplained coverage loss, stale runtime contamination, missing display mapping, or test failure.
