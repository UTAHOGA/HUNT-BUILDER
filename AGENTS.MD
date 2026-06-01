# AGENTS.md — HUNT-BUILDER Repo Execution Orders

**Updated:** 2026-05-31T00:00:00+00:00

## Purpose Of This File

This file controls how Codex must work inside this repository.

Codex must read this file before making changes.

This repo has lost time to:
- half-finished rebuilds
- context drift
- placeholder files
- unvalidated outputs
- duplicated fragments
- runtime path mismatches
- broken deploy assumptions
- local-only files not available in production
- confusion between source-of-truth data and visitor-facing website files
- task switching before the assigned step was actually completed

The rule is simple:

## **Finish the assigned step completely before moving to another step.**

No guessing.  
No drifting.  
No abstract scaffolding.  
No starting over unless explicitly instructed.  
No publishing broken outputs.  
No silently changing source-of-truth data.  
No treating management-plan context as harvest, draw, permit, or prediction truth.  
No leaving production URLs or runtime JSON paths in a broken state.

---

## 1. Non-Negotiable Mission

This repo is built around verified truth-source databases first.

The mission is:

1. Build verified source inventories.
2. Promote only trusted sources.
3. Extract only promoted sources.
4. Normalize draw and harvest truth databases.
5. Validate every truth database.
6. Build comparison engines.
7. Build deterministic draw rules.
8. Build reviewed feature layers only after source truth is validated.
9. Build website/public outputs only from validated or explicitly approved data contracts.
10. Keep live runtime paths, public assets, and deployed pages working.

The project must produce defensible, traceable data. Every final number must be explainable back to its original source.

---

## 2. Current Live Architecture

Codex must treat the following as the active architecture unless explicitly reassigned:

```text
GitHub = source control only
Vercel = live Hunt Builder app host
huntbuilder.uoga.org = deployed Hunt Builder domain
uoga.org = parent website / marketing shell / button entry point
Cloudflare = public/runtime file delivery where configured and verified
```

Rules:

- GitHub is not a public hosting target.
- Vercel is the live application host.
- The parent U.O.G.A. website may link to Hunt Builder by buttons, navigation, or other entry points.
- Heavy public visitor files may be served from Cloudflare only if the URLs are verified and currently returning 200 in production.
- If Cloudflare runtime/public URLs are not verified and working, Codex must not assume they exist.
- If a visitor-facing file must work in production and no working Cloudflare source exists, the file must be repo-served through the proper public path contract.

---

## 3. Repo Location

Local active repo path:

```text
C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER
```

Related older/source repo path:

```text
C:\Users\tyler\Desktop\GitHub\HUNTS
```

If Codex imports or compares from `HUNTS`, the task must explicitly record:
- source path
- promotion reason
- row count and/or hash
- target path inside active `HUNT-BUILDER`

Do not silently pull files from `HUNTS` into `HUNT-BUILDER`.

---

## 4. Required Codex Behavior

Codex is in coding mode.

When assigned a task, Codex must:

1. implement the task
2. run the task
3. validate the result
4. fix failures
5. write required outputs
6. update `WORK_LOG.md`
7. commit changes when repository modification was requested
8. stop

Codex must not merely draft plans.

Codex must not leave TODO-only files.

Codex must not create empty modules.

Codex must not create abstract scaffolding without executable code.

Codex must not create placeholder-only files, placeholder-only logic, or placeholder-only reports that merely make a phase look started.

Codex must carry the assigned step through implementation, validation, artifact generation, and closeout before moving on.

Codex must not start over halfway through a task.

Codex must not switch tasks unless blocked.

Codex must not hide failures.

Codex must not mark a task complete unless the requested outputs exist and validation has run.

Codex must not claim success if validation was skipped.

Codex must not say a task is “ready” when it only created scaffolding.

Codex must not create multiple competing versions of the same pipeline.

If a task cannot be completed, Codex must stop and report:
- exact blocker
- exact file, line, or error
- what was completed
- what remains
- safest next step

---

## 5. Required Start Of Every Codex Session

Before coding, Codex must read:
- `AGENTS.md`
- `WORK_LOG.md`

Codex must also read relevant project documents when present and relevant to the task:
- `Canonical JSON rules.md`
- `HARVEST_AND_REPORT_YEAR_RULES.md`
- `HYBRID_ML_V1.md`
- `HYBRID_ML_V1_ROLLOUT.md`
- `LOCKED_CANONICAL_2026.md`
- `docs/utah_draw_routing_and_algorithm_v1.md`
- `docs/utah_draw_system_scope.md`
- `docs/utah_rules_sources.md`
- elk and mule deer foundational reference files when the task touches plan-context logic

Before coding, Codex must state:
- current completed step
- assigned step
- files Codex will modify
- files Codex will not modify
- validation Codex will run
- stop condition

If the user explicitly assigns a task, the assigned task controls.

If no task is assigned, Codex must read `WORK_LOG.md`, identify the last completed step, recommend the next step, and wait for confirmation unless continuation was already clearly assigned.

---

## 6. Current Known Progress Baseline

The historical baseline below is retained so Codex understands the original rebuild order. The current chronological truth is `WORK_LOG.md`.

### Step 1 — Raw Source Inventory

Complete.

Tool created:

```text
engine/utah/quality/inventory_raw_pdfs.py
```

Outputs created:

```text
data_model/quality/raw_pdf_inventory.csv
data_model/quality/raw_pdf_inventory.json
data_model/quality/raw_pdf_inventory_report.json
```

Known result:

```text
Total inventoried files: 1286
```

Inventory included:
- PDF page counts when readable
- duplicate sha256 checks
- same filename with different sha256 checks
- missing inferred year checks
- unknown report type checks
- no value parsing

No values were parsed during Step 1.

### Step 1B — Raw Inventory Audit

Complete.

Outputs created:

```text
data_model/quality/raw_pdf_inventory_audit.csv
data_model/quality/raw_pdf_inventory_audit_report.json
```

Known result:

```text
Total files audited: 1286
Promoted quality sources: 253
Promoted draw sources: 204
Held/review sources: 829
Duplicate pressure: 296 files held as duplicates
Unreadable PDFs: 13
Review required: 489
Missing year inference: 27
```

No values were extracted during Step 1B.

### Later Work

`WORK_LOG.md` contains the current chronology after these baseline steps, including:
- source parity audits
- draw truth hardening
- harvest truth hardening
- canonical data chain lock reports
- public library work
- youth reserve and preference ladder modeling
- average-harvest-age extraction and review work
- elk and mule deer plan guardrails
- runtime/public deployment repairs

Codex must treat `WORK_LOG.md` as the current chronology and must not revert the project to an obsolete phase.

---

## 7. Default Next-Step Rule

The user’s explicit instruction always controls the assigned step.

If the user gives no explicit task, Codex must:

1. read `WORK_LOG.md`
2. identify the last completed step
3. report a recommended next step
4. wait for confirmation unless the next step was already clearly assigned

Codex must not automatically perform obsolete earlier steps when later work has superseded them.

---

## 8. Current Operating Priority

Truth-source validation still governs data changes.

However, deployed website/runtime repairs are now authorized when explicitly assigned.

This means:

- Codex may repair live runtime 404s, broken public pages, missing public assets, public document routing, broken path contracts, and Vercel/static serving problems when assigned.
- Codex must not use website work as an excuse to bypass truth-source rules.
- Codex must not redesign UI unless explicitly asked.
- Codex must prioritize path correctness, production stability, and verified runtime sources before aesthetic changes.

---

## 9. Source Classification Rules

Required source classes:

- `harvest_results`
- `draw_results`
- `permit_data`
- `biology_population`
- `age_results`
- `management_plan`
- `regulations`
- `map_or_boundary`
- `website_runtime`
- `public_export`
- `model_output`
- `audit_validation_report`
- `unknown`

Required promotion statuses:

- `PROMOTE`
- `HOLD_DUPLICATE`
- `HOLD_UNKNOWN_YEAR`
- `HOLD_UNKNOWN_TYPE`
- `HOLD_UNREADABLE_PDF`
- `HOLD_NON_HARVEST`
- `REVIEW_REQUIRED`
- `SOURCE_LABEL_LINEAGE_REVIEW`
- `PROMOTED_HISTORICAL_TRUTH`
- `REVIEW_EVIDENCE_ONLY`

Required engine-use flags:

```text
quality_engine_use: YES | NO | MAYBE
draw_engine_use: YES | NO | MAYBE
prediction_engine_use: YES | NO | MAYBE
website_public_use: YES | NO | MAYBE
```

Promotion rules remain in force:
- harvest reports, age reports, winter population reports, and similar may be quality-engine inputs
- draw results, draw odds, applicant reports, bonus point reports, and point ladder reports may be draw-engine inputs
- regulations, maps, guidebooks, proclamations, and descriptive files are not raw truth unless the task is explicitly public library curation
- duplicate files must not all promote
- unknown type or unknown year must not auto-promote without evidence
- management plans are context sources, not raw truth rows

---

## 10. Year Rules

For draw odds, draw results, and harvest report files:

```text
reported_hunt_year = the year the hunt, draw, or harvest actually occurred
model_target_year = reported_hunt_year + 1
```

Folder year is storage/provenance only.

Codex must store:
- `publish_year`
- `reported_hunt_year_inferred`
- `model_target_year`
- `source_file`
- `source_page` where applicable
- `source_table_title` where applicable

Codex must not confuse legacy historical input files with predictive outputs merely because they contain labels like `draw_odds`.

---

## 11. Truth Database Architecture

The final truth-source architecture is:

```text
data_truth/
  draw_results_truth/
    raw_inventory/
    extracted/
    normalized/
    validation/
  harvest_results_truth/
    raw_inventory/
    extracted/
    normalized/
    validation/
  crosswalk_truth/
    normalized/
    validation/
  comparison_outputs/
    validation/
```

Codex must preserve the separation between:
- harvest truth
- draw truth
- permit truth
- crosswalk truth
- management-plan context
- website/public display files
- predictive outputs

Codex must not combine truth layers unless the assigned step explicitly requires a reviewed merge layer.

---

## 12. Runtime / Reference CSV Roles

### `DATABASE.csv`

Use as:
- current canonical hunt-code universe
- current canonical boundary-id universe
- current direct DWR Hunt Planner permit/allotment truth where populated
- reviewed historical permit truth where source-lineage fields exist

### DATABASE is the truth source for current canonical hunt rows.

Do not overwrite populated numeric permit/allotment cells in `DATABASE.csv` from comparison files, inferred values, RAC files, generated audits, or rebuilt public documents.

### `MASTER.xlsx`

Use as:
- derived export workbook
- public/inspection-friendly formatted workbook
- recipient of validated values from `DATABASE.csv` and approved derived logic

Rules:
- `MASTER.xlsx` is not a peer truth source
- `MASTER.xlsx` must be regenerated or reconciled from `DATABASE.csv`
- if `DATABASE.csv` and `MASTER.xlsx` disagree on authoritative fields, `DATABASE.csv` controls unless an explicit documented fallback/export normalization rule says otherwise
- do not manually invent values in `MASTER.xlsx`

### `hunt_master_enriched.csv`

Use as:
- enriched hunt reference
- species/hunt name/weapon/hunt type/access reference
- CWMU vs public reference
- permit overlay reference
- harvest enrichment support

Do not use as raw harvest truth.

### `point_ladder_view.csv`

Use as:
- point ladder reference
- hunt_code + residency + points structure
- permit/ladder validation support

Do not use as raw draw truth.

### `draw_reality_engine.csv`

Use as:
- historical draw-results reference
- draw truth/backtesting candidate
- source file/page traceability support

Must be keyed by:
- `hunt_code`
- `year`
- `residency`
- `points`

Do not use as current hunt-code universe without filtering.

### `draw_reality_view.csv`

Use as:
- frontend/display only
- sanity comparison only

Do not treat as source truth.

### `harvest_master.csv`

Use as:
- harvest reference surface
- summary evidence
- feature support where validated

Do not treat as the only raw harvest truth if normalized truth packages exist.

### `harvest_quality_features_all_years_by_hunt_code.csv`

Use as:
- historical harvest-quality feature evidence
- cross-year support
- reviewed average-age support where validated

Do not assume blank age means unavailable in source PDFs.

### `harvest_age_features_by_hunt_code_all_years.csv`

Use as:
- canonical reviewed age feature history once built and validated

Do not overwrite raw harvest truth.

### `harvest_age_features_by_hunt_code_latest.csv`

Use as:
- latest reviewed age feature layer for quality scoring

Do not use to modify draw odds or quotas.

---

## 13. Runtime / Public Asset Contract

This section governs what must live in the repo `public/` tree versus what may be served elsewhere.

### Core rule:
If a file is visitor-facing and must render/view/download in production, it should live under `public/` unless there is a verified working Cloudflare delivery path already in use.

### Public visitor files belong under `public/`.

Examples:
- PDFs intended for public view/download
- public document manifests
- public JSON feeds
- public logos/images/icons
- static visitor-facing downloads
- curated public exports
- public-facing hard-copy assets

Preferred structure:

```text
public/
  hard-copy/
    data/
      documents.json
    pdfs/
      ...
    DISPLAY DATA/
      ...
  assets/
    logos/
    images/
  data/
    public visitor/runtime JSON only
```

Rules:
- Root-level visitor paths should map cleanly to `public/` assets in deployment.
- Codex must not keep required visitor-facing files only in local folders outside deploy-visible paths.
- If a page expects `/hard-copy/data/documents.json`, the canonical deploy-visible source must exist under `public/hard-copy/data/documents.json` or an explicit verified rewrite must map it there.
- Do not rely on local-only files for production behavior.
- Do not expose internal/raw files to visitors unless explicitly curated.

### Repo-served public assets
Use repo-served public assets when:
- the file is required for current production behavior
- Cloudflare source is absent, broken, or unverified
- the file size is acceptable for repo/deploy use
- the file is curated and intended for public access

### Cloudflare-served assets
Cloudflare may be used for:
- very large public documents
- heavy JSON/GeoJSON feeds
- large visitor downloads
- static public runtime files where repo size or deploy limits are a concern

But:
- Codex must not assume Cloudflare exists just because code references it
- a Cloudflare URL is valid only when it returns 200 and matches the current live contract
- if Cloudflare fallback is broken, repo-served public files must be used for production repair when appropriate

### No mixed broken fallbacks
Codex must not leave a page in a state where:
- local path 404s
- repo path 404s
- Cloudflare fallback 404s
- and the page crashes

A runtime/public contract is not complete until at least one valid source path works in production.

---

## 14. Research Library Mapping Law

Every research-library document or row created from this point forward must carry explicit hunt-code mapping fields.

Required columns:
- `hunt_code`
- `boundary_id`
- `hunt_code_mapping_status`
- `boundary_id_mapping_status`
- `candidate_hunt_code`
- `candidate_boundary_id`

Rules:
- reviewed fields are truth; candidate fields are evidence only
- blank reviewed fields are allowed only when mapping status explains why
- `DATABASE.csv` is the canonical current hunt-code and boundary-id source unless explicitly replaced by a later reviewed source
- direct DWR permit/allotment values in `DATABASE.csv` must not be overwritten by library/master rebuilds, comparison files, or inference
- populated numeric 2026 permit/allotment cells in `DATABASE.csv` are direct Utah DWR Hunt Planner truth and must not be changed or overwritten by comparison files, inferred values, draw reports, RAC files, audit outputs, or rebuilt library/master documents
- populated 2025 or older permit fields in `DATABASE.csv` are canonical historical source truth when they carry reviewed source-lineage fields such as `permits_2025_source` or `permits_2025_draw_source`
- populated 2025 or older permit fields without source lineage must be flagged for lineage repair before being treated as canonical truth
- `permits_2025` is the full populated 2025 historical permit universe
- `permits_2025_draw` is a narrower bonus-point draw-results subset and must not be described as the full 2025 draw/permit universe
- feeder/reference files such as `hunt_master_enriched.csv`, `point_ladder_view.csv`, canonical JSON, and boundary GeoJSON must be registered as source rows with hashes before they can support alignment work
- direct Utah DWR Hunt Planner CSV-folder files are source evidence only until a reviewed promotion step identifies source dates/year context
- do not promote 2025 permit values into 2026 available allotment fields unless every imported source used in that promotion has reviewed source-date context
- old-prefix, private-land, conservation, and document-level matches must flow through the current-to-historical crosswalk before promotion
- fuzzy reconciliation output is review evidence, not a promoted mapping
- document-level source rows must be extracted into per-hunt-code rows before promotion

---

## 15. Hunt Planner / ArcGIS Data Boundary

Standing project knowledge:

```text
Public Hunt Planner / ArcGIS did not expose true average harvest age fields.
```

Use Hunt Planner / ArcGIS for:
- hunt code
- hunt number
- hunt name
- boundary id
- boundary name
- geometry
- public map metadata

Do not use Hunt Planner / ArcGIS for:
- average harvest age
- mean age
- percent 5+
- tooth/cementum age data
- observed harvested-age metrics

Average harvest age must come from annual reports, age tables, and validated extracted evidence.

---

## 16. Average Harvest Age / Age-Quality Feature Rules

Age data is a quality-score feature, not a draw-odds or permit-quota feature.

Valid observed animal-age fields include:
- `average_harvest_age`
- `average_age`
- `mean_age`
- `avg_age`
- tooth-age / cementum-annuli tables
- percent 5+ only as an explicitly separate proxy
- percent adult male/female only when clearly labeled as age-structure context

Never use these as animal age:
- `average_days`
- `average_days_hunted`
- `mean_days`
- `mean_days_hunted`
- `hunter_days`
- `pursuit_days`
- `days_afield`
- `success_rate`
- `hunter_satisfaction`
- `buck_to_doe_ratio`
- `bull_to_cow_ratio`
- management objective age bands

Zero Rule:
- do not fill missing age with `0`
- if a zero age is found, blank it, flag it, and record why

Age scope labels:
- `hunt_code_direct`
- `unit_level_repeated_to_hunt_code`
- `unit_level_needs_hunt_code_crosswalk`
- `management_unit_level`
- `statewide_only`
- `source_context_review`

Age review rules remain in force:
- direct hunt-code scope preferred
- unit-level repeated-to-hunt scope must be labeled
- fuzzy or crosswalk-weak mappings must be REVIEW or BLOCK

---

## 17. Elk Statewide Plan Reference And Age-Quality Guardrails

The elk statewide plan is management/policy context only.

It may support:
- research explanation
- management labels
- quality-context benchmarks
- validation checks
- unit objective comparisons

It must not directly modify:
- `DATABASE.csv`
- permit/allotment truth
- draw odds
- probability fields
- public runtime truth

Management age objectives are not observed `average_harvest_age`.

Observed annual-report age fields must stay separate from plan objectives.

Allowed derived context fields may include:
- `elk_age_objective_min`
- `elk_age_objective_max`
- `elk_age_objective_category`
- `elk_age_objective_source = ELK_STATEWIDE_PLAN`
- `elk_age_objective_context_only = true`

---

## 18. Mule Deer Statewide Plan Reference And Harvest-Context Guardrails

The mule deer statewide plan is management/policy context only.

It may support:
- research explanation
- management labels
- quality-context benchmarks
- demand-pressure explanation
- validation checks
- objective comparisons
- CWD context explanation

It must not directly modify:
- `DATABASE.csv`
- permit/allotment truth
- draw odds
- probability fields
- public runtime truth

Plan thresholds are not observed `average_harvest_age`.

Observed annual-report age fields must stay separate from plan thresholds.

Allowed derived context fields may include:
- `mule_deer_general_buck_doe_objective_min`
- `mule_deer_general_buck_doe_objective_max`
- `mule_deer_limited_entry_buck_doe_objective_min`
- `mule_deer_limited_entry_buck_doe_objective_max`
- `mule_deer_premium_limited_entry_buck_doe_objective_min`
- `mule_deer_premium_limited_entry_buck_doe_objective_max`
- `mule_deer_ple_percent_5plus_threshold`
- `mule_deer_ple_percent_5plus_context_only = true`
- `mule_deer_permit_auto_change_threshold_pct`
- `mule_deer_plan_context_only = true`

---

## 19. Prediction / Modeling Boundaries

Prediction outputs must be downstream of validated truth data.

Codex must distinguish:
- deterministic rule simulation
- modeled probability
- historical observed probability
- display odds
- policy context
- age-quality context
- harvest quality context
- current permit truth
- historical draw truth

Do not use policy-plan values to directly change probability.

Do not use age or quality metrics to alter permits or quotas.

---

## 20. Website / Public Output Rules

Website-facing files are downstream outputs.

Codex may modify website/public output files when explicitly assigned, but must follow these rules:

- do not modify website/public output files on guessed data
- do not expose raw runtime or internal truth fragments unless specifically curated
- public library files must remain curated
- denylist protections must remain active for raw/internal files
- if a public artifact is created or repaired, Codex must validate:
  - no raw file exposure
  - public manifest integrity
  - correct build/deploy path
  - correct `public/` routing
  - preview status when requested
  - file-size/runtime constraints when Cloudflare is involved

### Live deployment repair rule
When assigned a deployed-site/runtime repair task:
- fix production pathing first
- do not redesign UI unless explicitly requested
- do not break existing root URL contracts
- do not move public assets without documenting the new path contract
- prefer `public/` for visitor-facing files unless Cloudflare is verified and intentionally authoritative

---

## 21. Required Validation Commands

Codex must run validation appropriate to the task.

Common validations include:

```powershell
python -m py_compile <changed_python_files>
node --check <changed_js_files>
npm.cmd run build
python -m pytest <targeted_tests> -q
git diff --check
```

For CSV/data tasks, Codex must also validate:
- output files exist
- row counts are nonzero unless expected
- required columns exist
- no duplicate promoted rows unless allowed
- no invalid zero age values
- no days-hunted fields used as age
- no permit/allotment truth changed unless explicitly assigned
- no `DATABASE.csv` changes unless explicitly assigned
- no website files changed unless explicitly assigned

For website/runtime/public tasks, Codex must also validate:
- runtime URLs return 200
- required JSON/GeoJSON files resolve
- required logos/images resolve
- page loads without fatal console crashes
- at least one verified production data source works
- if a page expects `/hard-copy/...`, production serves it correctly

---

## 22. Work Log Requirements

Every completed repository task must update `WORK_LOG.md`.

Each entry must include:
- timestamp UTC
- scope
- files changed
- outputs created
- key results
- validation commands run
- whether commit was made
- commit hash if available

Codex must not treat a task as closed if `WORK_LOG.md` is not updated.

---

## 23. Commit Rules

If the task modifies repository files and the user asked Codex to make the change, Codex must commit after validation passes unless explicitly told not to commit.

Commit messages must be specific.

Do not commit broken outputs.

Do not commit junk.

Do not commit local-only large artifacts unless they are intentionally project artifacts and approved for tracking.

Do not commit raw temporary downloads unless the task explicitly requires source anchoring.

---

## 24. Mandatory Mobile QA Final Pass

Every website, UI, public-output, or page-build task must finish with a mobile-first QA pass before closeout.

Validate where relevant:
- no horizontal overflow
- primary navigation remains usable
- sticky headers do not cover controls
- text remains readable
- buttons/icons have usable tap targets
- tables, ladders, maps, overlays, and PDF viewers remain accessible
- desktop layout is not broken by mobile fixes

For website tasks, Codex must include the mobile QA result in `WORK_LOG.md` and the final report.

---

## 25. Final Report Format

When Codex finishes, it must report:
- exact files changed
- exact outputs created
- validation commands run
- key counts
- blockers if any
- commit hash if committed
- stop condition satisfied

Codex must not continue to another task after reporting completion.
