## 2026-06-01T12:00:00-06:00 - Hunt Research Full Final Verification Rerun (All Mapped Fields)

- Assigned action:
  - Run one final strict full-field reconciliation across all mapped Hunt Research fields.
  - Re-run runtime publication check across all mapped fields.
  - Determine final status: FULLY VERIFIED vs PARTIALLY VERIFIED.

- Implementation:
  - Added:
    - `scripts/hunt-research-full-final-verification.py`
  - Generated outputs:
    - `docs/hunt_research_full_final_verification.md`
    - `processed_data/audits/hunt_research_full_final_reconciliation.csv`
    - `processed_data/audits/hunt_research_full_final_runtime_publication_check.csv`

- Reconciliation scope:
  - full DATABASE universe: `1449` hunt codes
  - mapped fields audited: `28`
  - total comparison rows: `40572`

- Full-field reconciliation status counts:
  - `MATCH`: `22151`
  - `IMPROVED_FROM_CANONICAL_SOURCE`: `1738`
  - `NOT_PRESENT_IN_FEEDER`: `13295`
  - `MISSING_IN_TARGET`: `128`
  - `MISMATCH`: `3260`
  - `REVIEW_REQUIRED`: `0`

- Runtime publication check (all mapped fields):
  - `PUBLISHED`: `28`
  - `LEGACY_ONLY`: `0`
  - `MISSING_IN_TARGET`: `0`
  - `REVIEW_REQUIRED`: `0`

- Prior blocker-set integrity check:
  - blocker-set `MISMATCH` introduced: `0`
  - blocker-set `MISSING_IN_TARGET` introduced: `0`

- Remaining unresolved fields from strict full-field reconciliation:
  - `display_odds_pct` (`MISMATCH`: 98)
  - `p_draw_mean` (`MISMATCH`: 1023)
  - `p_draw_p10` (`MISMATCH`: 1023)
  - `p_draw_p90` (`MISMATCH`: 1023)
  - `permits_2026_total` (`MISSING_IN_TARGET`: 128, `MISMATCH`: 1)
  - `average_harvest_age` (`MISMATCH`: 92)

- Final status:
  - **PARTIALLY VERIFIED**

- Validation:
  - `python -m py_compile scripts/hunt-research-full-final-verification.py` -> PASS
  - `python scripts/hunt-research-full-final-verification.py` -> PASS
  - universe alignment check in output -> `1449/1449`
  - blocker-set mismatch regression check -> PASS (`0` introduced)

## 2026-06-01T11:55:00-06:00 - LFS Runtime Canonicalization Pass (Website Universe Redirect)

- Assigned action:
  - Audit all LFS-tracked files.
  - Determine which are in the live website/runtime universe.
  - Redirect active runtime/page dependencies to canonical sources (R2 for large runtime assets).

- Runtime canonicalization changes:
  - Updated:
    - `config.js`
      - production runtime source selection now canonical-only for large `processed_data` assets:
        - uses runtime manifest canonical URL (preferred)
        - falls back to object-hosted URL only if manifest entry is missing
      - local `./processed_data/*` runtime fallbacks are now dev-only.
      - boundary source arrays are production-canonicalized:
        - `HUNT_BOUNDARY_SOURCES`
        - `DISPLAY_BOUNDARY_INDEX_SOURCES`
        - `COMPOSITE_BOUNDARY_SOURCES`
      - outfitter directory source chain now canonicalized through config:
        - `OUTFITTERS_DATA_SOURCES` now targets canonical contract path first.
    - `verify.html`
      - removed hardcoded multi-path source list.
      - now consumes `window.UOGA_CONFIG.OUTFITTERS_DATA_SOURCES` and iterates available sources.
      - preserves fallback behavior only when canonical source is unavailable.

- Manifest + audit refresh:
  - Ran:
    - `node scripts/publish-runtime-assets-r2.js --dry-run`
  - Regenerated:
    - `public/data/runtime-manifest.json`
    - `data/runtime-manifest.json`
    - `processed_data/audits/large_file_classification_audit.csv`

- New LFS runtime audit tooling + outputs:
  - Added:
    - `scripts/audit-lfs-runtime-canonicalization.py`
  - Generated:
    - `processed_data/audits/lfs_runtime_canonicalization_audit.csv`
    - `docs/lfs_runtime_canonicalization_report.md`

- LFS universe result summary:
  - LFS-tracked files audited: `20`
  - LIVE_RUNTIME_REQUIRED: `4`
    - `processed_data/draw_reality_engine.csv`
    - `processed_data/draw_reality_engine_predictive_v2.csv`
    - `processed_data/hunt_master_enriched.csv`
    - `processed_data/statewide_composite_boundaries_2026.geojson`
  - Canonical source for all 4 live LFS runtime assets: `CLOUDFLARE_R2_PUBLIC`
  - Recommended action for all 4 live LFS runtime assets: `SERVE_FROM_R2`

- Validation:
  - Production source selection smoke-test:
    - evaluated `config.js` in production host context (`huntbuilder.uoga.org`)
    - verified live runtime arrays do not include local `./processed_data/*` paths in production mode.
  - Live pages:
    - `https://huntbuilder.uoga.org/` -> `200`
    - `https://huntbuilder.uoga.org/research.html` -> `200`
    - `https://huntbuilder.uoga.org/verify.html` -> `200`
    - `https://huntbuilder.uoga.org/hard-copy.html` -> `200`
  - Runtime manifest:
    - `https://huntbuilder.uoga.org/public/data/runtime-manifest.json` -> `200`
  - Canonical runtime asset URLs (`json.uoga.workers.dev`):
    - live frontend-used canonical URLs checked -> `200` (HEAD)
  - LFS-pointer risk spot-check:
    - canonical R2 URLs for:
      - `draw_reality_engine_predictive_v2.csv`
      - `hunt_master_enriched.csv`
    - prefix check confirms not serving Git LFS pointer payload text.

## 2026-06-01T11:40:00-06:00 - Hunt Research Remaining Gap Closure (Contract Verification)

- Assigned action:
  - Close remaining Hunt Research contract verification blockers:
    - `availability_status`
    - `current_age_3yr_average`
    - `dwr_result_display`
    - `guaranteed_at_2026`
    - `management_direction`
    - `management_objective_range`
    - `management_objective_type`
  - Resolve `hunt_master_enriched.csv` LFS verification blocker with a runtime-readable canonical substitute.

- Contract rebuild update:
  - Updated:
    - `scripts/build-hunt-research-2026-contract.py`
  - Added contract fields:
    - `availability_status`
    - `current_age_3yr_average`
  - Source order used:
    - `availability_status`: ladder/draw status families (`availability_status`, `allocation_status`, `status`, `draw_outlook`)
    - `current_age_3yr_average`: ladder -> `DATABASE.csv` -> DWR HaNumber pull (`processed_data/dwr_huntplanner_hanumber_2026.csv`)
  - Regenerated:
    - `processed_data/hunt_research_2026.json`
    - `processed_data/audits/hunt_research_2026_rebuild_coverage.csv`
    - `docs/hunt_research_2026_rebuild_notes.md`

- Gap-closure verification run:
  - Added:
    - `scripts/close-hunt-research-remaining-gaps.py`
  - Outputs:
    - `docs/hunt_research_remaining_gap_closure.md`
    - `processed_data/audits/hunt_research_remaining_gap_closure.csv`
    - `processed_data/audits/hunt_research_runtime_publication_check.csv` (updated)
    - `processed_data/audits/hunt_research_remaining_gap_closure_detail.csv` (row-level trace)
  - Master feeder blocker resolution:
    - `processed_data/hunt_master_enriched.csv` detected as local LFS pointer
    - substitute verification source used:
      - `pipeline/RAW/hunt_unit_database/2026/csv/hunt_master_canonical_2026_built.csv`
    - management-objective verification moved to canonical:
      - `processed_data/management_context/hunt_management_objective_context.json`

- Validation:
  - `python -m py_compile scripts/build-hunt-research-2026-contract.py` -> PASS
  - `python scripts/build-hunt-research-2026-contract.py` -> PASS
  - `python -m py_compile scripts/close-hunt-research-remaining-gaps.py` -> PASS
  - `python scripts/close-hunt-research-remaining-gaps.py` -> PASS
  - Contract coverage checks:
    - unique hunt codes: `1449` in contract vs `1449` in `DATABASE.csv`
    - unresolved fields present in contract: `7/7`
    - unresolved fields runtime-published from contract: `7/7`
    - unresolved-field mismatches: `0`
    - unresolved-field missing-in-target: `0`

## 2026-06-01T13:05:00-06:00 - Comprehensive DWR Hunt Planner HaNumber Pull (2026 Universe)

- Assigned action:
  - Perform a more comprehensive live data pull from DWR Hunt Planner popup source:
    - `https://dwrapps.utah.gov/huntboundary/HaNumber?roles=&hn={hunt_code}`
  - Keep this as source evidence only (no `DATABASE.csv` overwrite).

- Script updated:
  - `scripts/fetch-dwr-huntplanner-hanumber-2026.js`
  - Expanded extracted fields to include additional popup metadata and text blocks:
    - `dwr_waiting_period_years`
    - `dwr_special_provisions_text`
    - `dwr_notes_text`
    - `dwr_harvest_reporting_text`
    - `duplicate_until_date`
    - `otc_sales_begin_date`
    - `otc_sales_end_date`
    - sold draw/OTC quota fields
    - security/display flags
    - management label-value pair JSON
  - Added raw payload export:
    - `processed_data/dwr_huntplanner_hanumber_2026_raw_payloads.json`

- Pull run:
  - command:
    - `node scripts/fetch-dwr-huntplanner-hanumber-2026.js`
  - scope:
    - 2026 hunt codes sourced from `DATABASE.csv` canonical universe
  - result:
    - rows written: `1449`
    - fetch OK: `1449`
    - fetch errors: `0`
    - rows with management stats: `970`
    - rows with percent harvest success: `960`
    - rows with current age 3yr average: `220`
    - rows with waiting period years: `1272`
    - rows with special provisions: `668`
    - rows with notes: `937`
    - rows with harvest reporting text: `698`
    - rows with surrender info: `814`

- EB3038 verification against user-provided example:
  - `hunt_code`: `EB3038`
  - `dwr_hunt_name`: `Manti`
  - `dwr_weapon`: `Any Legal Weapon`
  - `season_date_text`: `Sept 16 2026 - Sept 20 2026`
  - permits: `61 res / 7 nr / 68 total`
  - `dwr_harvest_reporting_text`: populated
  - `harvest_survey_due`: `Oct 20, 2026`
  - `harvest_penalty_date`: `Oct 21, 2026`
  - `surrender_info_text`: populated
  - `dwr_notes_text`: populated
  - `dwr_special_provisions_text`: `Permit holders may NOT hunt on CWMUs`
  - `dwr_waiting_period_years`: `5`
  - `percent_harvest_success_previous_hunting_season`: `72.4`
  - `population_objective`: `12000`
  - `current_population_estimate`: `12200`
  - `age_objective`: `5.5-6.0`
  - `current_age_3yr_average`: `6.3`

- Outputs created:
  - `processed_data/dwr_huntplanner_hanumber_2026.csv`
  - `processed_data/dwr_huntplanner_hanumber_2026.json`
  - `processed_data/dwr_huntplanner_hanumber_2026_raw_payloads.json`
  - `processed_data/audits/dwr_huntplanner_hanumber_2026_audit.json`
  - `processed_data/audits/dwr_huntplanner_hanumber_2026_audit.csv`

- Validation:
  - `node --check scripts/fetch-dwr-huntplanner-hanumber-2026.js` -> PASS
  - live run completed with `0` fetch failures
  - manual EB3038 row inspection confirms expected field population

## 2026-06-01T12:20:00-06:00 - Full Promotion of Two-Column Age Structure to Public Hunt-Table Export Set

- Assigned action:
  - Promote validated two-column age export structure from samples into the full public hunt-table workbook set:
    - `Average Harvest Age`
    - `Current Age (3-Yr Avg)`
  - Preserve existing safeguards.
  - Regenerate public-facing hunt-table outputs.

- Implementation:
  - Extended:
    - `scripts/repair-two-column-public-age-exports-2026.py`
  - Added full-promotion mode:
    - `--promote-full`
    - applies in-place updates to:
      - `processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/*.xlsx`
  - Added full-promotion audit artifacts:
    - `processed_data/audits/average_harvest_age_two_column_full_promotion_audit.json`
    - `processed_data/audits/average_harvest_age_two_column_full_promotion_audit.csv`
  - Regenerated validated sample outputs from updated full set:
    - `processed_data/hard_data_exports/hunt_tables/2026/SAMPLES_TWO_COLUMN_AGE/*.xlsx`

- Full-promotion run result:
  - Command:
    - `python scripts/repair-two-column-public-age-exports-2026.py --promote-full`
  - Summary:
    - files scanned: `168`
    - files updated: `165`
    - hunt-table files with hunt rows: `165`
    - columns added total: `169`
    - files where old age header was replaced: `161`
    - total rows filled with `Average Harvest Age`: `2030`
    - total rows filled with `Current Age (3-Yr Avg)`: `716`
  - Header coverage:
    - hunt-header files: `165`
    - files with `Average Harvest Age`: `165/165`
    - files with `Current Age (3-Yr Avg)`: `165/165`
    - old header string hits after promotion: `0`
    - non-hunt workbooks unchanged by design: `3`

- Safeguard validation:
  - `python -m py_compile scripts/repair-two-column-public-age-exports-2026.py scripts/augment_hunt_tables_prior_year_harvest.py scripts/redraft-hunt-tables-2026-clean-display.py` -> PASS
  - No zero values written:
    - `Average Harvest Age`: `0` zero cells
    - `Current Age (3-Yr Avg)`: `0` zero cells
  - `Current Age (3-Yr Avg)` source guard:
    - rows with current-age value but no canonical `DATABASE.csv` current-age value: `0`
    - current-age mismatches against canonical `DATABASE.csv`: `0`
  - `Age Objective` remains excluded by rule:
    - two-column script sources are limited to approved annual-age families + canonical DWR current-age field.

## 2026-06-01T10:45:00-06:00 - Two-Column Public Age Repair (Average Harvest Age + Current Age 3-Yr Avg)

- Assigned action:
  - Repair and split public age columns into:
    - `Average Harvest Age`
    - `Current Age (3-Yr Avg)`
  - Keep strict source-family separation and regenerate sample public outputs.

- Pipeline/template updates:
  - Updated hunt-table redraft pipeline template:
    - `scripts/redraft-hunt-tables-2026-clean-display.py`
    - replaced old age header with `Average Harvest Age`
    - added `Current Age (3-Yr Avg)` as a separate output column
    - wired current 3-year age from canonical `DATABASE.csv`
  - Updated workbook augmentation pipeline:
    - `scripts/augment_hunt_tables_prior_year_harvest.py`
    - added `Current Age (3-Yr Avg)` output column
    - normalized age header aliases to new two-column scheme
    - added canonical current-age lookup from `DATABASE.csv`

- New task script and outputs:
  - Added:
    - `scripts/repair-two-column-public-age-exports-2026.py`
  - Generated:
    - `docs/average_harvest_age_two_column_policy.md`
    - `processed_data/audits/average_harvest_age_two_column_audit.csv`
    - sample repaired public outputs in:
      - `processed_data/hard_data_exports/hunt_tables/2026/SAMPLES_TWO_COLUMN_AGE/`

- Sample output regeneration results:
  - `2026_BLACK_BEAR.xlsx` -> `UPDATED` (rows=106, average age filled=96, current 3-yr filled=0)
  - `2026_ELK_BULL_ALL.xlsx` -> `UPDATED` (rows=353, average age filled=274, current 3-yr filled=143)
  - `2026_DEER_BUCK_LIMITED_ENTRY.xlsx` -> `UPDATED` (rows=67, average age filled=0, current 3-yr filled=0)

- Two-column audit summary:
  - rows audited: `2898`
  - unique hunt codes: `1449`
  - public `Average Harvest Age` populated rows: `1268`
  - public `Current Age (3-Yr Avg)` populated rows: `440`
  - canonical average-age populated codes: `634`
  - canonical current-age populated codes: `219`
  - average-age blank causes:
    - `SOURCE_MISSING`: `1624`
    - `MAPPING_FAILURE`: `6`
  - current-age blank causes:
    - `NOT_SUPPORTED_FOR_SPECIES`: `1260`
    - `SOURCE_MISSING`: `878`
    - `MAPPING_FAILURE`: `320`

- Validation:
  - `python -m py_compile scripts/redraft-hunt-tables-2026-clean-display.py scripts/augment_hunt_tables_prior_year_harvest.py scripts/repair-two-column-public-age-exports-2026.py` -> PASS
  - `python scripts/repair-two-column-public-age-exports-2026.py` -> PASS
  - zero-value guardrail check on both age columns in audit output -> PASS (`0` zero values written)
  - sample workbook header validation confirms:
    - `Average Harvest Age`
    - `Current Age (3-Yr Avg)`

## 2026-06-01T09:44:00-06:00 - Domain Canonicalization (Single Production Domain Policy)

- Assigned action:
  - Consolidate domain references to one canonical production domain:
    - `https://huntbuilder.uoga.org`
  - Eliminate active usage assumptions for:
    - `https://hunt-builder.uoga.org`

- Outputs created:
  - `docs/domain_canonicalization_report.md`
  - `processed_data/audits/domain_reference_audit.csv`

- Files updated:
  - `AGENTS.MD`
  - `hunt-master-canonical-2026.json`
  - `schemas/hunt-master-canonical-2026.schema (2).json`
  - `scripts/audit-active-data-feeds.js`
  - `scripts/audit-site-performance-library-outfitters.js`
  - `processed_data/final_live_push_verification_report.json`

- Domain handling decisions:
  - Canonical domain remains `huntbuilder.uoga.org`.
  - `hunt-builder.uoga.org` references are retained only where needed for redirect enforcement:
    - `vercel.json` host redirect rule
    - `embed-mode.js` runtime redirect detection
  - Historical audit artifact reference retained as legacy evidence:
    - `processed_data/audits/promote_now_live_alignment.csv`

- Validation:
  - `rg -l "hunt-builder\\.uoga\\.org"` returns only:
    - `embed-mode.js`
    - `vercel.json`
    - `processed_data/audits/promote_now_live_alignment.csv`
  - `rg -l "huntbuilder\\.uoga\\.org"` confirms canonical references across active runtime/config/docs.
  - `git diff --check` clean.

## 2026-06-01T09:02:00-06:00 - Canonical R2 Promotion Completed (hunt_research_2026.json)

- Assigned follow-up:
  - Re-run canonical R2 promotion once Wrangler auth was restored.

- Cloudflare access validation:
  - `wrangler whoami` -> PASS
  - Account: `cd6d0adbdac9690cdae5f1c6d52aaa9b`

- Promotion action:
  - `wrangler r2 object put uoga-data/processed_data/hunt_research_2026.json --file processed_data/hunt_research_2026.json --config wrangler.r2-runtime.jsonc --remote`
  - Result: upload complete.

- Runtime verification:
  - `https://json.uoga.workers.dev/processed_data/hunt_research_2026.json` -> `200` (28,329,606 bytes)
  - `https://huntbuilder.uoga.org/data/runtime-manifest.json` -> `200`
  - `https://huntbuilder.uoga.org/` -> `200`
  - `https://huntbuilder.uoga.org/research.html` -> `200`
  - `https://huntbuilder.uoga.org/verify.html` -> `200`
  - `https://huntbuilder.uoga.org/hard-copy.html` -> `200`

- Note:
  - `https://huntbuilder.uoga.org/processed_data/hunt_research_2026.json` remains `404`, which is expected for Cloudflare-canonical runtime delivery and not required when pages consume canonical manifest/runtime URLs.

## 2026-06-01T08:55:00-06:00 - Promote-Now Alignment Release Execution

- Assigned action:
  - Execute strict promote-now alignment release (no scope expansion).

- Release actions completed:
  - Pushed release trigger commit to `main`:
    - `4fec81e8` (`docs: add promote-now live alignment checklist and audit`)
  - Re-verified live production routes:
    - `https://huntbuilder.uoga.org/` -> `200`
    - `https://huntbuilder.uoga.org/research.html` -> `200`
    - `https://huntbuilder.uoga.org/verify.html` -> `200`
    - `https://huntbuilder.uoga.org/hard-copy.html` -> `200`
  - Re-verified route-loaded JS/CSS assets for those pages:
    - all resolved with `200`
  - Re-verified runtime manifest endpoints:
    - `https://huntbuilder.uoga.org/data/runtime-manifest.json` -> `200`
    - `https://huntbuilder.uoga.org/public/data/runtime-manifest.json` -> `200`
  - Re-verified canonical runtime sources used by Builder:
    - `https://json.uoga.workers.dev/processed_data/display-boundary-index-2026.json` -> `200`
    - `https://json.uoga.workers.dev/processed_data/statewide_composite_boundaries_2026.geojson` -> `200`
    - `https://json.uoga.workers.dev/processed_data/composite_hunt_unit_mapping_2026.geojson` -> `200`

- Payload parity check (repo head vs live):
  - Checked:
    - `embed-mode.js`
    - `config.js`
    - `data.js`
    - `app.js`
    - `hunt-research.js`
    - `assets/js/research-outlook-dashboard.js`
    - `assets/css/hard-copy-public-library.css`
  - Result:
    - live content matches repo head after normalizing line endings (`CRLF` local vs `LF` live).

- Blocker on required step 1 (R2 publish):
  - Attempted remote upload:
    - `wrangler r2 object put uoga-data/processed_data/hunt_research_2026.json --file processed_data/hunt_research_2026.json --config wrangler.r2-runtime.jsonc --remote`
  - Cloudflare response:
    - `403 Forbidden` / `code 10000 Authentication error`
  - Current status:
    - `https://json.uoga.workers.dev/processed_data/hunt_research_2026.json` -> `404`
    - canonical R2 publish for `hunt_research_2026.json` remains blocked pending valid Cloudflare auth token/account binding in this environment.

## 2026-06-01T09:05:00-06:00 - Strict Promote-Now Live Alignment List (Live Canonical vs Repo Canonical)

- Assigned action:
  - Produce strict promote-now list to align live canonical with repo canonical.

- Outputs created:
  - `docs/promote_now_live_alignment_checklist.md`
  - `processed_data/audits/promote_now_live_alignment.csv`

- Method:
  - Pulled live HTML shells for:
    - `/`
    - `/research.html`
    - `/verify.html`
    - `/hard-copy.html`
  - Enumerated live script/style payload URLs from those pages.
  - Compared live payload hashes to local repo head for the loaded runtime files.
  - Probed required runtime endpoints (primary domain + Cloudflare runtime paths).

- Key findings used for categorization:
  - Out-of-sync live payloads:
    - `embed-mode.js`
    - `config.js`
    - `data.js`
    - `app.js`
    - `hunt-research.js`
    - `assets/js/research-outlook-dashboard.js`
    - `assets/css/hard-copy-public-library.css`
  - In-sync payload:
    - `assets/js/hard-copy-public-library.js`
  - Missing canonical manifest endpoints:
    - `/public/data/runtime-manifest.json` -> 404
    - `/data/runtime-manifest.json` -> 404
  - Missing research summary contract:
    - `https://json.uoga.workers.dev/processed_data/hunt_research_2026.json` -> 404
    - `https://huntbuilder.uoga.org/processed_data/hunt_research_2026.json` -> 404
  - Alternate domain remains DNS unresolved:
    - `https://hunt-builder.uoga.org`

- Validation:
  - `curl -I` endpoint checks for all listed items (200/404/DNS states recorded in checklist/audit outputs).
  - Hash comparison script run for live-vs-local payload byte equality.

## 2026-06-01T08:40:00-06:00 - Focused Runtime Promotion Pass (LFS Pointer Runtime Prune + Alternate Domain Canonical Enforcement)

- Assigned action:
  - Run focused promotion pass to replace remaining LFS-pointer runtime source usage with verified canonical R2 objects.
  - Resolve alternate domain parity/redirect policy gap.

- Files changed:
  - `config.js`
  - `embed-mode.js`
  - `docs/large_file_delivery_architecture.md`

- Work completed:
  - Added hard pointer-key guardrail in runtime config for known pointer feeds:
    - `research_draw_reality_engine_predictive_v2_csv`
    - `research_hunt_master_enriched_csv`
  - Pruned local processed_data fallback paths for those pointer feeds even if manifest is unavailable early.
  - Confirmed source arrays now resolve to canonical R2/Cloudflare URLs only for those two feeds.
  - Added client-side canonical host safety redirect:
    - if host is `hunt-builder.uoga.org`, redirect to `https://huntbuilder.uoga.org` preserving path/query/hash.
  - Documented canonical-domain enforcement as dual layer:
    - host redirect in `vercel.json`
    - client safety redirect in `embed-mode.js`.

- Validation:
  - `node --check config.js` PASS
  - `node --check embed-mode.js` PASS
  - `node scripts/publish-runtime-assets-r2.js --dry-run --verbose` PASS
  - config runtime evaluation check (Node VM):
    - predictive feed local fallback removed
    - hunt_master_enriched local fallback removed
  - `curl -I https://huntbuilder.uoga.org/` -> `200`
  - `curl -I https://hunt-builder.uoga.org/` -> DNS unresolved (`curl: (6) Could not resolve host`)
  - `npm run build` PASS

## 2026-06-01T08:12:00-06:00 - Large-File Delivery Architecture Pass (R2 + Runtime Manifest)

- Assigned action:
  - Implement safest large-file delivery architecture with Cloudflare R2 + tracked runtime manifest.

- Files changed:
  - `.gitattributes`
  - `config.js`
  - `package.json`
  - `scripts/build-pages-dist.js`
  - `scripts/publish-runtime-assets-r2.js` (new)
  - `docs/large_file_delivery_architecture.md` (new)
  - `public/data/runtime-manifest.json` (generated)
  - `data/runtime-manifest.json` (generated mirror)
  - `processed_data/audits/large_file_classification_audit.csv` (generated)

- Outputs created:
  - `processed_data/audits/large_file_classification_audit.csv`
  - `public/data/runtime-manifest.json`
  - `data/runtime-manifest.json`
  - `docs/large_file_delivery_architecture.md`

- Work completed:
  - Added a single audited publish script that:
    - classifies runtime/large-file targets
    - writes audit CSV
    - writes canonical runtime manifest
    - supports optional R2 upload via S3-compatible endpoint (AWS CLI).
  - Implemented manifest-driven runtime URL preference in `config.js` for Builder and Research large runtime feeds while preserving existing fallback chains.
  - Added build-path support for runtime manifest files in `pages-dist`.
  - Fixed suspicious `.gitattributes` pattern:
    - `Git[[:space:]]LFS/*.exe` -> `Git\ LFS/*.exe`.

- Validation:
  - `node scripts/publish-runtime-assets-r2.js --dry-run --verbose` PASS
  - `node --check config.js` PASS
  - `node --check scripts/publish-runtime-assets-r2.js` PASS
  - `node --check scripts/build-pages-dist.js` PASS
  - `git diff --check` PASS

- Classification counts (audit run):
  - `REPO_SMALL`: 1
  - `LFS_REFERENCE_ONLY`: 3
  - `R2_PUBLIC`: 12
  - `INTERNAL_ONLY`: 3
  - `REVIEW_REQUIRED`: 1

## 2026-06-01T07:48:00-06:00 - Google Earth 3D Chrome Runtime Reliability Patch (Dual-Mode Retry + Structured Diagnostics)

- Assigned action:
  - Investigate continued Chrome-only Earth mode failures where Edge still renders.
  - Keep Earth mode active (no forced fallback), improve resilience and diagnostics.

- Files changed:
  - `app.js`

- Work completed:
  - Replaced single-attempt Earth mode logic with controlled retry cycle:
    - tries configured default mode first
    - retries alternate mode (`SATELLITE` <-> `HYBRID`) once via tracked mode cycle
  - Added normalized Earth mode setters to keep element property/attribute values consistent.
  - Added structured `gmp-error` capture:
    - serializable payload snapshot
    - attempted mode list
    - timestamp and normalized current mode
  - Enhanced unavailable diagnostics/status context with:
    - gmp error code/message fields where available
    - tried mode list and mode cycle in console diagnostics
  - Corrected WebGL diagnostics capture:
    - separate WebGL2/WebGL contexts
    - renderer/vendor extraction via `WEBGL_debug_renderer_info` where available

- Validation:
  - `node --check app.js` PASS
  - `git diff --check` PASS

## 2026-06-01T09:24:00-06:00 - Verify Directory Card Upgrade + Trust/Label Pass

- Assigned action:
  - Continue ordered completion sequence:
    - step 4: actionable verified outfitter directory cards
    - step 5: trust/label/dead-path pass.

- Files changed:
  - `verify.html`

- Work completed:
  - Upgraded public outfitter cards to be more actionable:
    - added primary `Contact` CTA routing (phone, then email, then website)
    - retained dedicated `Website`, `Call`, and `Email` actions where published
    - converted `Species served` and `Units served` from plain text lines to badge groups
    - formatted reviewed timestamps to readable date labels
    - expanded service-badge derivation with additional service categories and dedupe handling
  - Added card styling support for service/species/unit badge groups and primary action emphasis.
  - Trust/cleanup checks:
    - verified `verify.htmlm` remains a live redirect shim to `verify.html`
    - scanned known misspelling set from prior QA notes; no active matches found in current repo text search scope.

- Validation:
  - `node --check app.js` PASS (existing modified runtime file still valid)
  - `node --check config.js` PASS (existing modified runtime file still valid)
  - `node --check assets/js/research-outlook-dashboard.js` PASS
  - `node --check hunt-research.js` PASS

## 2026-06-01T09:05:00-06:00 - Research Flagship Dashboard Polish (Decision Grid + Collapsed Secondary Sections + Ladder Header Cleanup)

- Assigned action:
  - Continue step 3 of build completion:
    - keep Hunt Research as flagship decision page
    - preserve model math
    - polish dashboard structure and ladder clarity.

- Files changed:
  - `assets/js/research-outlook-dashboard.js`
  - `hunt-research.js`

- Work completed:
  - Kept `Hunt Application Outlook` hero + 3-column decision grid as primary research surface.
  - Added explicit field-class separation labels in dashboard panels:
    - Official DWR source fields
    - Model-generated fields
    - U.O.G.A. curated context
  - Kept source/freshness/model details in collapsed `<details>` section.
  - Collapsed non-core secondary blocks (Hunter-Fit Signals, Comparable Hunts) so the ladder remains the main decision surface below the dashboard.
  - Standardized ladder header language:
    - `2025 Result` -> `2025 Draw Results` (status-only mode)

- Validation:
  - `node --check assets/js/research-outlook-dashboard.js` PASS
  - `node --check hunt-research.js` PASS

## 2026-06-01T08:42:00-06:00 - Runtime Contract Cleanup Pass (Canonical Domain Rule + Cloudflare-First Processed Data)

- Assigned action:
  - Execute next-priority runtime cleanup:
    1) lock canonical domain behavior
    2) reduce runtime dependence on repo-served `processed_data/*` for production.

- Files changed:
  - `vercel.json`
  - `config.js`
  - `app.js`

- Work completed:
  - Added host-conditional redirect rule in `vercel.json`:
    - `hunt-builder.uoga.org` -> `https://huntbuilder.uoga.org/:path*` (permanent).
  - Added Cloudflare/object-first candidate helper in `config.js` for processed runtime assets.
  - Switched these source groups to Cloudflare-first ordering in production:
    - `HUNT_BOUNDARY_SOURCES` (composite boundary runtime file)
    - `DISPLAY_BOUNDARY_INDEX_SOURCES` (JSON)
    - `COMPOSITE_BOUNDARY_SOURCES` (composite boundaries file)
  - Removed `./processed_data/hunt-master-canonical-2026-source-of-truth.json` from canonical hunt master candidates (local `data/*` canonical files remain).
  - Fixed research contract URL from non-existent Cloudflare root path to:
    - `${CLOUDFLARE_BASE}/processed_data/hunt_research_2026.json`
  - Added production path remap in `app.js` `normalizeRelativeGeoPath()`:
    - relative `processed_data/*` boundary paths now resolve to Cloudflare base outside local dev.

- Runtime checks performed:
  - `hunt-builder.uoga.org` DNS currently unresolved (still retired at DNS level).
  - `huntbuilder.uoga.org` reachable (200).
  - Verified Cloudflare availability:
    - `processed_data/display-boundary-index-2026.json` -> 200
    - `processed_data/statewide_composite_boundaries_2026.geojson` -> 200
    - `processed_data/draw_reality_engine.csv` -> 200
    - `processed_data/point_ladder_view.csv` -> 200
    - `processed_data/hunt_master_enriched.csv` -> 200
    - `processed_data/hunt_unit_reference_linked.csv` -> 200
  - Observed `processed_data/hunt_research_2026.json` on Cloudflare currently 404, so local fallback remains in source list.

## 2026-06-01T08:05:00-06:00 - Builder Map UX Pass (DWR Panel Hide + Earth Intro Flight + Top Direction Controls)

- Assigned action:
  - Remove the ownership panel from DWR iframe mode.
  - Make Earth mode start from globe-scale view and animate into a low-angle hunt-unit view.
  - Add top directional controls (N/E/S/W) in Earth mode.
  - Keep Earth bottom controls auto-open behavior active.

- Files changed:
  - `index.html`
  - `app.js`

- Work completed:
  - Added hard hide CSS so `#ownershipDock` cannot remain visible when `hidden`/`aria-hidden=true` in DWR mode.
  - Added Earth-only top direction control bar with N/E/S/W buttons.
  - Wired direction buttons to rotate Earth heading while preserving center/range/tilt.
  - Added Earth intro-flight state to run globe-to-unit animation when Earth mode is selected.
  - Increased navigation-control open passes to improve auto-expanded bottom controls behavior.
  - Added Earth intro timer cleanup when leaving Earth mode or on 3D-unavailable states.

- Validation:
  - `node --check app.js` PASS
  - `npm run build` PASS
  - Build regenerated existing derived manifests/exports as part of project build pipeline.

## 2026-06-01T02:52:34-06:00 - Reconciled Missing Split Hunt Codes (+319 Detail JSON Files)

- Assigned action:
  - Create missing split JSON hunt records to close the audit gap:
    - `Geo hunt codes missing from split: 319`.

- Work completed:
  - Added `319` new hunt detail JSON files under:
    - `processed_data/hunt_research_2026_split/hunts/*.json`
  - Appended corresponding `319` index rows in:
    - `processed_data/hunt_research_2026_split/hunt_research_2026.index.json`
  - Updated split metadata counts:
    - `processed_data/hunt_research_2026_split/manifest.json`
    - `processed_data/hunt_research_2026_split/split-summary.json`
  - Re-ran boundary vs split audit outputs.

- Post-change validation:
  - `geojson_hunt_codes_detected`: `1607`
  - `split_hunt_codes_detected`: `1607`
  - `matched_hunt_codes`: `1607`
  - `geo_hunt_codes_without_split`: `0`
  - `split_hunt_codes_without_geo`: `0`
  - invalid/broken files detected: `0`
  - equivalence verdict: `EQUIVALENT` (by hunt-code mapping set)

## 2026-06-01T02:47:14-06:00 - Boundary vs Hunt Research Split Audit

- Assigned action:
  - Audit `processed_data/boundaries` vs `processed_data/hunt_research_2026_split` for 1:1 mapping and file health.

- Outputs created:
  - `processed_data/audits/boundary_vs_hunt_research_2026_split_audit.json`
  - `processed_data/audits/boundary_vs_hunt_research_2026_split_missing.csv`

- Key results:
  - `.geojson` in boundaries: `1654`
  - `.json` in hunt_research_2026_split: `3`
  - filename-stem matches: `0` (not 1:1)
  - hunt-code overlaps: `1288` matched split codes
  - geo hunt codes missing from split: `319`
  - split hunt codes missing from geo: `0`
  - invalid/malformed/LFS-pointer files found in these local directories: `0`
  - overall equivalence verdict: `NOT_EQUIVALENT`

- Validation performed:
  - file counts by extension
  - filename-stem set comparison
  - hunt-code extraction from GeoJSON metadata and split JSON arrays
  - invalid JSON / empty file / Git LFS pointer detection
  - ambiguity checks for duplicate code mappings

## 2026-06-01T02:31:14-06:00 - Entry Page 3D Runtime Contract Verification (Live Script Pin Audit + Cache-Bust Tokens)

- Assigned action:
  - Verify why live site still exhibits old 3D behavior after local fixes.

- Findings:
  - Live entry page currently serves older pinned bundles:
    - `./data.js?v=20260404-selection-matrix-fix-1`
    - `app.js?v=20260506-card-select-flyin-popup-6`
  - Live `app.js` still contains deprecated `defaultUIDisabled/defaultUiDisabled` paths and does not include new LFS-pointer-aware JSON fallback logic.
  - Live `processed_data/boundaries/EB3024.geojson` still returns Git LFS pointer text, while Cloudflare path serves real GeoJSON.

- Fix applied:
  - `index.html`
    - bumped runtime script tokens to force fresh bundle retrieval after deploy:
      - `data.js?v=20260601-3d-runtime-lfs-fallback-1`
      - `app.js?v=20260601-earth3d-runtime-repair-1`

- Validation:
  - `npm run build` PASS.
  - Confirms runtime path changes are production-ready once deployed.

- Note:
  - Until deployment, `huntbuilder.uoga.org` will continue executing old pinned scripts and old 3D behavior.

## 2026-06-01T02:21:15-06:00 - Builder Runtime Error Fixes (LFS Boundary Pointer Fallback + Google Earth 3D Deprecation Cleanup)

- Assigned action:
  - Address runtime console errors:
    - `Direct boundary GeoJSON load failed ... Unexpected token 'v', "version ht"...`
    - repeated `defaultUIDisabled` deprecation warnings from Maps 3D runtime.

- Root causes confirmed:
  - Live `https://huntbuilder.uoga.org/processed_data/boundaries/EB3024.geojson` returns a Git LFS pointer payload (not GeoJSON JSON).
  - Cloudflare mirror path returns valid GeoJSON JSON.
  - Google Maps 3D runtime logs deprecation warning when legacy `defaultUIDisabled`-related usage is touched.

- Fixes applied:
  - `data.js`
    - Reworked `fetchJson` to parse response text first.
    - Added Git LFS pointer detection (`version https://git-lfs.github.com/spec/v1`).
    - Added automatic Cloudflare retry for `processed_data/*` URLs when an LFS pointer is returned.
    - Added runtime warning message identifying pointer retry path.
  - `app.js`
    - Removed deprecated `defaultUiDisabled/defaultUIDisabled` property usage in Earth control setup.
    - Removed legacy `default-ui-disabled` attribute removal touchpoint so 3D runtime no longer emits that deprecation warning path from app code.

- Validation:
  - JS parse check PASS for modified files (`app.js`, `data.js`).
  - `npm run build` PASS.
  - Code scan confirms no remaining `defaultUIDisabled/defaultUiDisabled/default-ui-disabled` references in `app.js`.

- Note:
  - These fixes require deployment before live console errors clear on `huntbuilder.uoga.org`.

## 2026-06-01T02:11:06-06:00 - Builder Google Earth 3D Failure Handling (Blank Map Prevention + Automatic Fallback)

- Assigned action:
  - Fix Builder map behavior where Google Earth / Google Maps 3D can fail to initialize and leave a blank map surface.

- Root cause confirmed:
  - In live verification, Google 3D runtime emitted:
    - `Attempted to load a 3D Map, but failed...`
  - Current code path could still report Earth as active while both `#map` and `#googleEarth3dMap` were hidden.

- Fix implemented:
  - `app.js`
    - Added Earth failure handler:
      - `handleGoogleEarth3dUnavailable(reason)`
    - Wired `gmp-error` event on `gmp-map-3d` to invoke failure handler.
    - Added safety check in Earth setup:
      - if `maps3d.Map3DElement` is unavailable, fail fast and fallback.
    - Prevented overlay/status path from running when Earth element is hidden.
    - Updated Earth mode branch to fallback to Google Maps on init failure, with accurate status messaging.
  - Behavior change:
    - If Earth 3D cannot render, app now auto-switches to Google Maps and shows:
      - `Google Earth 3D could not render... Switched to Google Maps.`
    - No more blank dual-hidden map state on Earth failure.

- Validation:
  - `npm run build` PASS.
  - Local runtime fallback test (forced `gmp-error` dispatch) PASS:
    - `mapTypeSelect` changed from `earth` to `google`.
    - `#map.hidden` = `false`.
    - `#googleEarth3dMap.hidden` = `true`.
    - status text confirms Earth failure + Google fallback.

- Note:
  - This fix is in local code and requires deployment before it affects `huntbuilder.uoga.org`.
  - If Earth fails in production after deploy, it indicates key/runtime support limits for 3D; app now degrades cleanly to Google Maps instead of blanking.

## 2026-06-01T02:03:53-06:00 - Research Page Runtime Render Speed Pass (No-Store Removal + Faster Source Order + Dashboard Parallelism)

- Assigned action:
  - Improve Research page render speed without changing prediction math or UI layout.

- Changes applied:
  - `config.js`
    - Updated observed engine source order to prefer smaller valid runtime engine first:
      - added `draw_reality_engine.csv` (Cloudflare/local) ahead of `draw_reality_engine_v2.csv`.
      - retained v2 as fallback.
  - `hunt-research.js`
    - Removed forced no-cache fetch for research datasets (`cache: no-store`).
    - Removed duplicate `masterRows` indexing pass in `indexData` to avoid redundant per-load CPU work.
  - `assets/js/research-outlook-dashboard.js`
    - Removed forced no-cache fetch for dashboard feeds.
    - Increased fetch timeout from `2200ms` to `6000ms` to reduce unnecessary fallback churn.
    - Reordered outlook contract lookup to try local repo-served contract first.
    - Parallelized management + outlook supplemental loading with `Promise.allSettled`.

- Validation:
  - `npm run build` PASS.
  - Code scan confirms no remaining `no-store` usage in:
    - `hunt-research.js`
    - `assets/js/research-outlook-dashboard.js`
  - Data compatibility check:
    - `draw_reality_engine.csv` header contains required core research keys (`hunt_code`, `year`, `residency`, `points`, `draw_pool`, permits/allotment fields).

- Notes:
  - Largest first-load cost is still full browser parse/index of the engine CSV.
  - This pass improves repeat-load behavior and reduces first-hit overhead, but a next pass should move to a pre-indexed per-hunt contract to remove full-file client parse cost.

## 2026-06-01T01:24:00-06:00 - Focused Runtime-Contract Cleanup Pass (Fallback Prune + Composite Source Fix + Alternate Domain Retirement)

- Assigned action:
  - Remove dead runtime fallbacks.
  - Fix/replace broken composite GeoJSON source path.
  - Configure or formally retire alternate domain.

- Runtime-contract changes:
  - `config.js`
    - Removed broken composite source from active Builder composite list:
      - removed `./processed_data/composite_hunt_unit_mapping_2026.geojson?...`
    - Pruned dead/legacy research fallback candidates to a tighter contract:
      - removed legacy `draw_reality_engine.csv` URL variants from observed/predictive source arrays
      - removed runtime draft/model draft fallback files (`data_model/runtime_drafts/*`, harvest-quality draft CSV fallback entries)
      - removed ladder-as-master/reference fallbacks (`point_ladder_view.csv` from master/reference source groups)
      - retained Cloudflare primary + local processed fallback entries only.
  - `assets/js/hard-copy-public-library.js`
    - Removed dead manifest URLs causing known 404 noise:
      - removed `public_library_allowlist.json` fallback
      - removed `./hard-copy/documents.json` fallback
      - removed `./public/hard-copy/DISPLAY DATA/data/documents.json` fallback
    - Kept canonical runtime document feed contract:
      - `./hard-copy/data/documents.json`
      - `./public/hard-copy/data/documents.json`

- Alternate-domain decision:
  - `AGENTS.md` domain policy updated:
    - `https://hunt-builder.uoga.org/` is formally retired until DNS is explicitly restored.
    - parity auditing should resume only after DNS restoration.
  - `docs/site_map_and_runtime_audit.md` updated to record retirement decision.

- Validation:
  - `npm run guard:public-manifests` PASS
  - DNS check:
    - `huntbuilder.uoga.org` resolves.
    - `hunt-builder.uoga.org` remains NXDOMAIN.
  - Source-contract verification by code scan:
    - broken composite file no longer present in `COMPOSITE_BOUNDARY_SOURCES`
    - hard-copy dead fallback manifest URLs removed from `MANIFEST_URLS`
    - research source arrays now use reduced Cloudflare-first + local fallback contract.

- Notes:
  - Live production error logs will continue to show old fallback/composite behavior until a new deployment is triggered from this commit.

## 2026-06-01T00:58:00-06:00 - Public Surface Hardening: Internal Instruction/Planning File Exposure Guardrails

- Assigned action:
  - Remove/deny internal instruction, AGENTS/task/audit-planning markdown/text exposure from public website surfaces.
  - Enforce public rendering allowlists for extension + path.
  - Add automated guardrail check.

- Exposure audit completed:
  - Reviewed live/public manifests and runtime feeds with focus on:
    - `public/hard-copy/data/documents.json`
    - `processed_data/hard_data_exports/hard_data_manifest.web.json`
    - hard-copy and hard-data runtime rendering logic
  - Verified `public/hard-copy/data/documents.json` remained visitor-safe (PDF/XLSX only).
  - Identified public-surface risks:
    - `hard-data.html` static catalog referenced internal/audit-oriented files (including `.md`).
    - `scripts/build-pages-dist.js` explicitly included internal `.md` audit files and copied directory trees without internal-file filtering.

- Fixes applied:
  - `assets/js/hard-copy-public-library.js`
    - Added strict rendering allowlist:
      - approved path prefixes: `./public/hard-copy/`, `/public/hard-copy/`, `./hard-copy/`, `/hard-copy/`
      - approved extensions: `.pdf`, `.xlsx`
    - Added hard block patterns for internal names/tokens:
      - `AGENTS*`, `CODEX*`, `audit*`, `implementation*`, `internal*`, `planning*`, `task*`, `.md`, `.txt`
    - Enforced these checks before any manifest item can render.
  - `hard-data.html`
    - Removed internal static catalog entries.
    - Added runtime render allowlist:
      - approved prefixes: `./processed_data/hard_data_exports/library/`, `./public/hard-copy/`, `./hard-copy/`
      - approved extensions: `.csv`, `.json`, `.pdf`, `.xlsx`
    - Added same internal-token blocklist (`AGENTS/CODEX/audit/implementation/internal/planning/task/.md/.txt`).
  - `scripts/build-library-page-data.js`
    - Added public web-manifest safety filter before writing `hard_data_manifest.web.json`.
    - Removed audit-manifest rows from web manifest seed.
    - Enforced safe item filtering (prefix + extension + internal-token block).
  - `scripts/build-pages-dist.js`
    - Removed `staging-audit.html` from root publish list.
    - Removed explicit `.md` processed-data audit file entries from publish list.
    - Added path-level publish deny rules:
      - deny `.md`, `.txt`
      - deny `AGENTS*`, `CODEX*`, `audit*`, `implementation*`, `internal*`, `planning*`, `task*`
      - deny `/audit(s)/` and `/internal/` path segments
    - Applied deny filtering for both direct file copies and recursive directory copies.
  - `package.json`
    - Added `guard:public-manifests` script.
    - Integrated guard into `build:pages` pipeline before `build-pages-dist`.
  - Added new guard script:
    - `scripts/guard-public-manifest-exposure.js`
    - Fails build if blocked tokens/extensions/paths appear in target public manifests or public-serving directories.

- Validation:
  - `node scripts/build-library-page-data.js` PASS (manifest regenerated with safe entries)
  - `npm run guard:public-manifests` PASS
  - `npm run build` PASS (includes guard during build pipeline)
  - Post-checks:
    - `public/hard-copy/data/documents.json` -> rows `10`, blocked rows `0`
    - `processed_data/hard_data_exports/hard_data_manifest.web.json` -> rows `3`, blocked rows `0`
    - No `.md` or `.txt` files found under `public/` or `processed_data/hard_data_exports/`

## 2026-06-01T00:22:00-06:00 - Full Repo / Live Site / Data / Prediction Engine Audit + Domain Parity Rule Update

- Assigned action:
  - Execute full audit of live site, repo active vs obsolete files, data lineage, and prediction-engine architecture.
  - Add explicit primary/secondary domain parity policy to `AGENTS.md`.

- Policy update completed:
  - `AGENTS.md` updated with required rule:
    - Primary domain: `https://huntbuilder.uoga.org/`
    - Secondary parity domain: `https://hunt-builder.uoga.org/`
    - Required mismatch reporting categories: redirects, page content, runtime paths, JSON/GeoJSON feeds, hard-copy, Builder/map, stale deployment indicators.

- Audit outputs created:
  - `docs/site_map_and_runtime_audit.md`
  - `docs/repo_active_vs_obsolete_audit.csv`
  - `docs/data_lineage_and_obsolescence_report.md`
  - `docs/prediction_engine_architecture_report.md`

- Live verification executed:
  - Route HTTP checks for:
    - `/`, `/index.html`, `/builder.html`, `/research.html`, `/hunt-research.html`, `/verify.html`, `/vetting.html`, `/hard-copy.html`, `/hard-data.html`, `/coverage.html`, `/verify.htmlm`
  - Playwright runtime checks:
    - Builder: loads, no 404s, one parse error from `processed_data/composite_hunt_unit_mapping_2026.geojson` payload.
    - Research: loads clean with selected hunt params.
    - Verify: loads clean.
    - Hard-copy: loads folder wall (8 folders), but still logs fallback 404 noise.
  - Domain parity checks:
    - `huntbuilder.uoga.org` resolves and serves pages.
    - `hunt-builder.uoga.org` does not resolve (NXDOMAIN), parity not testable.

- Additional evidence generation run:
  - `node scripts/audit-active-data-feeds.js` PASS
  - Generated/updated `processed_data/audits/*` readiness and runtime source audit artifacts used as supporting evidence.

- Scope control:
  - No prediction math changes.
  - No UI redesign.
  - No broad refactor.
  - Task completed as audit/documentation + verification.

## 2026-05-31T16:05:00-06:00 - MASTER Reconciliation Audit Artifact Durability

- Follow-up action:
  - Preserve MASTER reconciliation evidence in a tracked location (repo ignores `processed_data/*`).
- File updated:
  - `scripts/reconcile-master-xlsx-from-database-2026.py`
- Change:
  - Script now writes duplicate reconciliation audit outputs to:
    - `generated/audits/master_reconciliation_2026/master_database_2026_reconciliation_report.json`
    - `generated/audits/master_reconciliation_2026/master_database_2026_reconciliation_changes.csv`
  - Existing `processed_data/audits/*` outputs remain for local pipeline compatibility.
- Validation:
  - `python scripts/reconcile-master-xlsx-from-database-2026.py` PASS
  - Re-run after prior sync showed idempotent state:
    - `Changes: 0`
    - `Changed hunt codes: 0`

## 2026-05-31T15:10:00-06:00 - Builder Runtime 404 Repair + MASTER.xlsx Reconciliation From DATABASE Truth

- Assigned action:
  - Repair Builder/map runtime 404s with minimal path/config changes.
  - Reconcile `MASTER.xlsx` from authoritative `DATABASE.csv` values.

- Part 1 (Builder runtime) findings:
  - Live Builder load audit (Playwright network capture on `https://huntbuilder.uoga.org/`) showed 2 runtime 404s:
    - `./processed_data/outfitter-federal-unit-coverage-review.json`
    - `./data/hunt_boundaries_finalized_2026.geojson`
  - Remaining core Builder runtime files and map assets were returning `200`.

- Part 1 fix:
  - `config.js` updated to use a single repo-served static strategy for Builder runtime-critical sources.
  - Removed broken/missing local-first candidates and removed Builder Cloudflare fallback candidates for:
    - boundary sources
    - boundary manifest fallback list
    - canonical hunt master candidates
    - elk boundary table candidates
    - outfitter directory sources
    - conservation permit sources
  - Set `OUTFITTER_FEDERAL_COVERAGE_SOURCES` to empty list (optional dataset absent; runtime now fail-safe without 404).
  - Removed missing `hunt_boundaries_finalized_2026.geojson` from finalized boundary source order; retained existing local boundary files.

- Part 1 validation:
  - Local Builder runtime network capture (`https://localhost:4173/index.html`) after change:
    - `MISS_COUNT=0` (no 4xx/5xx requests during page load)
  - `npm run build` PASS.

- Part 2 (MASTER reconciliation) implementation:
  - Added repeatable reconciliation script:
    - `scripts/reconcile-master-xlsx-from-database-2026.py`
  - Script behavior:
    - Loads authoritative `DATABASE.csv`.
    - Reconciles `MASTER.xlsx` by `HUNT CODE`.
    - Syncs truth fields:
      - `HUNT NAME`, `SPECIES`, `SEX TYPE`, `SEASON`
      - `2026 PERMITS RES`, `2026 PERMITS NR`, `2026 PERMITS TOTAL`
    - Permit truth selection rule:
      - `permit_allotment_2026_*` primary
      - fallback to `permits_2026_*`
    - Preserves normalized export columns (`HUNT TYPE`, `WEAPON`, `HUNT CLASS`) and writes normalization audit stats (no overwrite).
    - Emits audit outputs:
      - `processed_data/audits/master_database_2026_reconciliation_report.json`
      - `processed_data/audits/master_database_2026_reconciliation_changes.csv`

- Part 2 run result:
  - `python scripts/reconcile-master-xlsx-from-database-2026.py` PASS.
  - Reconciliation summary:
    - Total cell changes: `17`
    - Fields changed:
      - `SEASON`: `2`
      - `2026 PERMITS TOTAL`: `15`
    - Corrected missing `2026 PERMITS TOTAL` hunt codes:
      - `BR7324`, `DB1056`, `DB1075`, `DB1076`, `DB1118`,
      - `EA1180`, `EA1270`, `EA1271`, `EA2041`, `EA2045`,
      - `TK1012`, `TK1013`, `TK1014`, `TK1015`, `TK1016`
    - `MASTER` and `DATABASE` hunt-code universes aligned (`1449` rows each; no missing code on either side).

## 2026-05-31T13:35:00-06:00 - Hard-Copy Deployment Path Repair (Path Mapping + Deploy-Critical Library Assets)

- Assigned action:
  - Verify and repair hard-copy deployment-path mismatches only.
- Root findings:
  - `hard-copy.html` and `assets/js/hard-copy-public-library.js` load correctly in production.
  - Runtime data path `/public/hard-copy/data/documents.json` resolves, but `/hard-copy/data/documents.json` does not.
  - Library document files referenced by `public/hard-copy/data/documents.json` were present locally but not tracked, so production returned 404 for linked PDFs/XLSX.
- Fixes applied:
  - `vercel.json`: added rewrite rule mapping `/hard-copy/:path*` -> `/public/hard-copy/:path*`.
  - Added deploy-critical hard-copy assets referenced by `documents.json` into source control:
    - `public/hard-copy/DISPLAY DATA/regulations/2026.biggame.app.pdf`
    - `public/hard-copy/DISPLAY DATA/regulations/2026.regs.cougar.bear.pdf`
    - `public/hard-copy/DISPLAY DATA/regulations/2026.regs.turkey.pdf`
    - `public/hard-copy/DISPLAY DATA/regulations/2026.regs.fishing.pdf`
    - `public/hard-copy/DISPLAY DATA/expo permits/2026 EXPO DRAW RESULTS.pdf`
    - `public/hard-copy/DISPLAY DATA/data/2025_harvest_summary_public.xlsx`
    - `public/hard-copy/DISPLAY DATA/data/2025_draw_results_summary_public.xlsx`
    - `public/hard-copy/DISPLAY DATA/data/2026_hunt_units_permit_numbers.xlsx`
    - `public/hard-copy/DISPLAY DATA/data/utah_outfitters_by_hunt_code_hunt_name.xlsx`
    - `public/hard-copy/DISPLAY DATA/harvest results/unit_specific_conservation_expo_bundles.xlsx`
- Validation:
  - `npm run build` PASS.
  - Verified local pages-dist now contains all 10 referenced document assets and hard-copy runtime files.
- Scope control:
  - No Hunt Builder map logic changed.
  - No hard-copy styling redesign performed.

## 2026-05-30T11:47:24-06:00 - Runtime 404 Restore From Desktop Public Contracts + Boundary Fallback Paths

- Assigned action:
  - Restore files currently requested by browser runtime/F12 from `C:\Users\tyler\Desktop\public_contracts`.
- Source files restored from desktop package:
  - `hunt_odds_history.csv`
  - `hunt_odds_history.json`
  - `hunt_predictions.json`
  - `hunt_application_outlook.json`
  - `hunt_units.geojson`
  - `outfitters-public.json`
  - `public_contract_summary.json`
  - `source_snapshots.json`
- Restored target paths:
  - `data/*` copies for runtime fallbacks
  - `processed_data/public_contracts/*` copies for contract feed paths
  - `processed_data/composite_hunt_unit_mapping_2026.geojson`
  - `processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson`
  - `processed_data/statewide_composite_boundaries_2026.geojson`
  - `processed_data/display-boundary-index-2026.json`
  - `processed_data/display-boundary-index-2026.csv`
  - `processed_data/hunt-master-canonical-2026-source-of-truth.json`
- Build packaging fix:
  - `scripts/build-pages-dist.js`
  - Added missing `/data` public-contract files to `dataFiles` copy list.
  - Added missing processed boundary files to `processedFiles` copy list.
  - Updated size-limit behavior so Vercel builds (`VERCEL=1`) include oversized restored files that were previously skipped.
- Validation:
  - `npm run build` PASS
  - `VERCEL=1 npm run build` PASS
  - Verified generated `pages-dist` now includes previously missing runtime files:
    - contract data JSON/CSV in `pages-dist/data`
    - processed boundary/index files in `pages-dist/processed_data`

## 2026-05-30T17:23:31Z - Production 404 Root-Cause (Vercel Config) + Deploy Output Fix

- Assigned action:
  - Diagnose production domain-wide 404s and restore correct static asset/data serving.
- Root cause identified:
  - `huntbuilder.uoga.org` DNS currently points to Vercel (`cname.vercel-dns.com`), not Cloudflare Pages.
  - Existing `vercel.json` only published root `*.html`, `*.js`, `*.css`, excluding directories such as:
    - `assets/*`
    - `data/*`
    - `processed_data/*`
  - This matched live 404s for logos, hard-copy JS/CSS, contract JSON, and canonical data files.
- Files modified:
  - `vercel.json`
- Changes:
  - Replaced restrictive static-glob config with build/output config:
    - `buildCommand: npm run build`
    - `outputDirectory: pages-dist`
  - This aligns Vercel production deploy with the same curated artifact package used by local validation.
- Validation:
  - `npm.cmd run build` PASS
  - Confirmed required production files exist in `pages-dist`:
    - hard-copy assets
    - research dashboard JS
    - outfitter/public contract feeds
    - conservation permit feeds
    - canonical hunt master foundation JSON

## 2026-05-30T16:49:03Z - Cloudflare Pages Dist Deploy Command Hardening

- Assigned action:
  - Resolve deployment drift where Pages was not publishing from `pages-dist`.
- Files modified:
  - `scripts/deploy-pages-dist.js` (new)
  - `package.json`
- Changes:
  - Added deterministic deploy script that:
    - runs full build (`npm run build`) unless `--skip-build`
    - verifies `pages-dist/index.html` and `pages-dist/hard-copy.html` exist
    - deploys with explicit command: `wrangler pages deploy pages-dist --project-name <name>`
    - supports `--project-name`, `--branch`, `--commit-hash`, and `--dry-run`
    - supports env fallbacks: `CLOUDFLARE_PAGES_PROJECT`, `CLOUDFLARE_PAGES_BRANCH`, `CLOUDFLARE_PAGES_COMMIT_HASH`
  - Added npm script:
    - `deploy:pages-dist`
- Validation:
  - `node --check scripts/deploy-pages-dist.js` PASS
  - `node scripts/deploy-pages-dist.js --project-name uoga-hunt-builder --dry-run --skip-build` PASS
  - `npm.cmd run deploy:pages-dist -- --project-name uoga-hunt-builder --dry-run` PASS
  - Local account check: `wrangler whoami` PASS; `wrangler pages project list --json` returned `[]` in current logged-in account.

## 2026-05-30T16:43:17Z - Hard-Copy Render Hardening + Google Map Auth Fallback

- Assigned action:
  - Fix reported hard-copy non-render state and Google Earth/Google Maps non-render in local runtime.
- Files modified:
  - `app.js`
- Hard-copy verification:
  - Confirmed current `hard-copy.html` + library script path renders with folders/results visible on both root and pages-dist routes in local runtime.
- Map fixes:
  - Added local-dev redirect from `127.0.0.1` to `localhost` to reduce referrer mismatch risk.
  - Added Google auth failure fallback behavior: when Google map authentication/referrer check fails, app now auto-switches to DWR map mode instead of leaving a broken Google map overlay.
- Validation:
  - `node --check assets/js/hard-copy-public-library.js` PASS
  - `node --check app.js` PASS
  - Runtime check (root): `https://localhost:4173/hard-copy.html` => `folders=8`, `cards=3`, `results visible`
  - Runtime check (pages-dist): `https://localhost:4173/pages-dist/hard-copy.html` => `folders=8`, `cards=3`, `results visible`
  - Runtime check (root/pages-dist map): Google auth blocked in local runtime now falls back to DWR mode (`mapTypeSelect=dwr`, `dwrMapFrame visible`).

## 2026-05-30T16:34:02Z - Hard-Copy Render Recovery (Pages-Dist Refresh)

- Assigned action:
  - Restore hard-copy page rendering in active built output.
- Root cause found:
  - Source fix existed in root files, but `pages-dist` was stale and still serving older output.
- Actions performed:
  - Ran full build pipeline to refresh pages-dist assets:
    - `npm.cmd run build`
  - Verified deployed-path render target directly:
    - `https://127.0.0.1:4173/pages-dist/hard-copy.html`
  - Confirmed runtime state:
    - `folders = 8`
    - `results panel hidden = false`
    - `result cards visible on load = 3`
    - `title = UTAH DWR RULES & REGULATIONS`
- Files refreshed by build:
  - `pages-dist/processed_data/hard_data_exports/library/hard_data_manifest.json`
  - `pages-dist/processed_data/hard_data_exports/library/library_page_summary.json`
  - `pages-dist/processed_data/library/hard_data_library_manifest.json`
  - `pages-dist/processed_data/library/library_page_summary.json`
  - `pages-dist/processed_data/production/library_page_summary.json`
  - `pages-dist/public/hard-copy/data/library_page_summary.json`
  - `pages-dist/public/hard-copy/manifests/hard_data_manifest.json`
  - `public/hard-copy/data/library_page_summary.json`
  - `public/hard-copy/manifests/hard_data_manifest.json`

## 2026-05-30T15:23:32Z - Hard-Copy Library Default Visible Results

- Assigned action:
  - Resolve "library not rendering" perception by showing file cards immediately on page load.
- Files modified:
  - `assets/js/hard-copy-public-library.js`
  - `hard-copy.html`
- Changes:
  - Library now auto-selects the first folder that has available items and opens the results panel by default.
  - Initial render now shows document cards without requiring the first folder click.
  - Bumped hard-copy script cache token.
- Validation:
  - `node --check assets/js/hard-copy-public-library.js` PASS
  - Playwright runtime check PASS:
    - `resultsPanel hidden = false`
    - `title = UTAH DWR RULES & REGULATIONS`
    - `cards = 3`

## 2026-05-30T15:08:24Z - Hard-Copy Library Render Resilience Fix

- Assigned action:
  - Repair public Research/Hard-Copy library rendering regression.
- Files modified:
  - `assets/js/hard-copy-public-library.js`
  - `hard-copy.html`
- Fixes applied:
  - Added manifest fallbacks for both public and root-served hard-copy document paths.
  - Added href candidate resolution so links work whether files are served from `/public/hard-copy/*` or `/hard-copy/*`.
  - Made local availability checks fail-open on network/HEAD uncertainty so optional checks do not blank the library wall/cards.
  - Normalized fixed fallback entries through `toPublicItem(...)` before dedupe to prevent single-item collapse when manifest files are unavailable.
  - Bumped hard-copy library script cache token in `hard-copy.html`.
- Validation:
  - `node --check assets/js/hard-copy-public-library.js` PASS
  - `npm.cmd run build` PASS

## 2026-05-30T14:00:33Z - Compare Hunts Action Opens Backpack Tray

- Assigned action:
  - Continue Builder workflow polish so compare flow is immediate.
- File modified:
  - `app.js`
- Change:
  - Updated `openCompareHunts(...)` to auto-open the Hunt Backpack tray when it is closed, then scroll/focus compare surfaces.
  - This removes an extra manual step after clicking `Compare Hunts`.
- Validation:
  - `node --check app.js` PASS
  - `npm.cmd run build` PASS

## 2026-05-30T13:59:40Z - Hunt Builder Action Unification (View Research / Compare / Save / Find Outfitters)

- Assigned action:
  - Next step on Builder UX continuity: make hunt cards behave like a single hunt-planning workflow.
- File modified:
  - `app.js`
- Changes:
  - Matching hunt cards now expose clear action buttons:
    - `View Research`
    - `Compare Hunts`
    - `Save Hunt`
    - `Find Outfitters`
  - Selected Hunt Details card now exposes the same four actions.
  - Selected floating hunt placard now exposes the same four actions (plus existing `View Map`).
  - Added supporting action handlers:
    - `openCompareHunts(...)` saves to backpack and jumps to compare surface.
    - `openOutfitterMatches(...)` selects hunt (if needed), loads outfitter matches, and scrolls to outfitter panel.
    - Save action confirms via status line.
  - Updated matching-card click handling for new action buttons.
- Validation:
  - `node --check app.js` PASS
  - `npm.cmd run build` PASS

## 2026-05-30T12:28:13Z - Hunt Research Input Debounce For Live Typing

- Assigned action:
  - Continue speed polish and reduce unnecessary rerenders during hunt-code typing.
- File modified:
  - `hunt-research.js`
- Change:
  - Added a small `180ms` debounce on input-triggered `runResearch()` calls for `huntCodeInput` and `pointsInput`.
  - Keeps immediate feedback while preventing one render cycle per keystroke.
- Validation:
  - `node --check hunt-research.js` PASS
  - `npm.cmd run build` PASS

## 2026-05-30T12:27:25Z - Hunt Research Speed Pass (Lazy Runtime Load On Demand)

- Assigned action:
  - Keep moving with speed optimization and reduce first-load cost on Hunt Research.
- Files modified:
  - `hunt-research.js`
  - `research.html`
- Speed optimization changes:
  - Converted Hunt Research runtime load flow to lazy/on-demand:
    - no heavyweight engine/ladder/master/reference CSV load on initial page paint when no hunt is selected
    - runtime data now loads when a hunt code is present and report execution is requested
  - Added load-promise guard in `loadData()` so repeated rapid UI events reuse one in-flight load instead of stacking duplicate fetch/parse work.
  - Preserved builder-handoff behavior:
    - if a hunt is already selected from handoff/storage, report still auto-runs.
  - Updated `research.html` cache-bust token for `hunt-research.js`.
- Validation:
  - `node --check hunt-research.js` PASS
  - `npm.cmd run build` PASS

## 2026-05-30T12:08:22Z - Research Runtime Source Fallback Expansion In Config

- Assigned action:
  - Keep moving and improve Hunt Research runtime resilience when primary `processed_data/*` sources are absent.
- File modified:
  - `config.js`
- Change:
  - Expanded `HUNT_RESEARCH_*_SOURCES` fallback lists to include reviewed local runtime files that exist in this repo snapshot:
    - `data_model/runtime_drafts/draw_reality_engine_v2.csv`
    - `data_model/harvest_quality/draw_reality_engine_predictive_with_harvest_features.csv`
    - `processed_data/point_ladder_view.csv` fallback for master/reference surfaces
  - No prediction math changes; source-order resilience only.
- Validation:
  - `node --check config.js` PASS
  - `npm.cmd run build` PASS

## 2026-05-30T12:06:50Z - Verify Page Outfitter Feed Priority Aligned To Public Contracts

- Assigned action:
  - Keep moving and align Outfitter Verification runtime reads with the public contract output.
- File modified:
  - `verify.html`
- Change:
  - Updated the verified-directory source order to:
    1. `processed_data/public_contracts/outfitters-public.json`
    2. `data/outfitters-public.json`
    3. `data/outfitters.json` vetted fallback filter
  - Added status messaging so page explicitly identifies when records come from contract feed vs fallback.
- Validation:
  - `npm.cmd run build` PASS

## 2026-05-30T12:05:32Z - Research Dashboard Contract Source Priority Alignment

- Assigned action:
  - Continue forward and align Hunt Research dashboard runtime reads with the merged public contract layer.
- File modified:
  - `assets/js/research-outlook-dashboard.js`
- Change:
  - Updated `getOutlookSources()` to prefer `processed_data/public_contracts/hunt_application_outlook.json` (local + Cloudflare paths) before legacy `processed_data/research_page` fallback paths.
  - This keeps dashboard reads aligned with the contract pipeline while preserving fallback safety.
- Validation:
  - `node --check assets/js/research-outlook-dashboard.js` PASS
  - `npm.cmd run build` PASS

## 2026-05-30T12:04:38Z - Hunt Research Ladder Polish (Blank Non-Applicable Cells + High-Signal Notes)

- Assigned action:
  - Continue forward with Hunt Research decision-table polish.
- File modified:
  - `hunt-research.js`
- Ladder polish changes:
  - Kept existing point-ladder header structure and premium R/Y/G wording.
  - Removed ladder-cell fallback clutter so non-applicable values render as blank cells instead of repeated `Not available`.
  - Tightened Notes content to only high-signal labels:
    - `Your Rung`
    - `Draw Line`
    - `Above Line` / `Below Line`
    - `Permits: X R / Y NR / Z Total`
    - `Harvest: ...`
    - `Point Creep Risk`
    - `Random Pool` / `Max Pool`
  - Removed verbose ladder-note narratives so Notes reads as a compact hunter-facing marker column.
- Validation:
  - `node --check hunt-research.js` PASS
  - `npm.cmd run build` PASS

## 2026-05-30T11:30:22Z - Merge/Upgrade Public Contracts Using Stronger Runtime Sources

- Assigned action:
  - Continue to next step and merge the previously attached public contract package with the current repo contract workflow.
- Files modified:
  - `scripts/build-public-data-contracts.js`
- Merge/upgrade behavior implemented:
  - Promoted stronger runtime candidates for contract generation:
    - predictive: `data_model/harvest_quality/draw_reality_engine_predictive_with_harvest_features.csv`
    - odds history: `data_model/runtime_drafts/draw_reality_engine_v2.csv`
    - hunt units: prefer `data/hunt_boundaries.geojson`
  - Kept fallback safety chain for missing runtime files.
  - Added selected-column CSV parsing to reduce memory footprint on large runtime CSVs and prevent heap failures.
  - Preserved non-overwrite rule: this step only builds website-facing contract outputs; no permit truth/prediction source truth files were modified.
- Generated/merged contract results:
  - `hunt_predictions_rows`: `27940`
  - `hunt_odds_history_rows`: `176753`
  - `hunt_application_outlook_rows`: `2898`
  - `outfitters_public_rows`: `11`
  - `hunt_units_features`: `683`
  - `prediction_source_mode`: `runtime_csv`
  - `odds_history_source_mode`: `runtime_csv`
  - `outfitters_source_mode`: `outfitters_json_fallback`
- External sync performed:
  - Synced updated outputs from `processed_data/public_contracts/*` to `C:/Users/tyler/Desktop/public_contracts/*` so the attached package is now merged-upgraded in place.
- Validation:
  - `node --check scripts/build-public-data-contracts.js` PASS
  - `node scripts/build-public-data-contracts.js` PASS
  - `npm.cmd run build` PASS

## 2026-05-30T10:50:08Z - Public Data Contract Layer Build + Runtime Fallback Hardening

- Assigned action:
  - Continue step sequence with the public data contract layer and complete generation of website-facing contract artifacts.
- Files modified:
  - `scripts/build-public-data-contracts.js`
  - `package.json`
- Files generated:
  - `processed_data/public_contracts/hunt_units.geojson`
  - `processed_data/public_contracts/hunt_odds_history.csv`
  - `processed_data/public_contracts/hunt_odds_history.json`
  - `processed_data/public_contracts/hunt_predictions.json`
  - `processed_data/public_contracts/hunt_application_outlook.json`
  - `processed_data/public_contracts/outfitters-public.json`
  - `processed_data/public_contracts/source_snapshots.json`
  - `processed_data/public_contracts/public_contract_summary.json`
- Contract builder hardening:
  - Added input resolution and fallback candidates so missing runtime CSVs no longer crash contract generation.
  - Added safe fallback synthesis from `processed_data/research_page/hunt_application_outlook.json` when runtime prediction/odds CSVs are unavailable or too sparse.
  - Added outfitter fallback behavior: if `data/outfitters-public.json` is empty, contract output uses reviewed records from `data/outfitters.json`.
  - Preserved guardrail: contract builder creates website-facing outputs only and does not modify `DATABASE.csv` or draw math.
  - Added build-chain integration: `npm run build` now executes `build:public-contracts` before `build-pages-dist`.
- Output summary:
  - `hunt_predictions_rows`: `2898`
  - `hunt_odds_history_rows`: `2898`
  - `hunt_application_outlook_rows`: `2898`
  - `outfitters_public_rows`: `11`
  - `hunt_units_features`: `683`
  - `unique_prediction_hunts`: `1449`
  - `prediction_source_mode`: `outlook_fallback`
  - `odds_history_source_mode`: `outlook_fallback`
  - `outfitters_source_mode`: `outfitters_json_fallback`
- Validation:
  - `node --check scripts/build-public-data-contracts.js` PASS
  - `node scripts/build-public-data-contracts.js` PASS
  - `npm.cmd run build` PASS

## 2026-05-30T07:40:36Z - Ingest 2026 Conservation Permit PDF Into DATABASE.csv

- Assigned action:
  - Ingest conservation permit data from desktop PDF:
    - `C:/Users/tyler/Desktop/species truth data/2026 CONSERVATION  PERMITS.pdf`
  - Permit rule used: one permit row = one permit count.
- File modified:
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Backup created:
  - `processed_data/backups/DATABASE_before_conservation_pdf_ingest_20260530_074022.csv`
- New columns added to `DATABASE.csv`:
  - `conservation_permits_2026_total`
  - `conservation_permits_2026_source`
- Ingest logic:
  - Extracted PDF rows by regex `No. + HUNT CODE` and aggregated counts by `hunt_code`.
  - Wrote aggregated counts into the new conservation columns for matched hunt codes.
  - Conservative backfill guardrail: only filled `permit_allotment_2026_total` when a row is conservation-context and that allotment total was blank.
  - Existing nonblank allotment totals were not overwritten by this pass.
- Audit output:
  - `processed_data/audits/conservation_pdf_ingest_2026_20260530_074022.json`
- Key results:
  - PDF unique row/code pairs extracted: `332`
  - Unique hunt codes extracted: `120`
  - Source codes missing from database: `0`
  - Database rows matched and updated with conservation columns: `120`
  - Conservation-row blank allotment backfills applied: `15`
  - Matched non-conservation rows touched in conservation-only columns: `93`
- Validation:
  - `DATABASE.csv` rows after ingest: `1449`
  - `DATABASE.csv` columns after ingest: `37`
  - New column nonblank counts:
    - `conservation_permits_2026_total`: `120`
    - `conservation_permits_2026_source`: `120`

## 2026-05-30T07:37:13Z - Drop permits_2025_draw_* Family From DATABASE 2026

- Assigned action:
  - Delete 2025 draw-subset permit columns from `DATABASE.csv`:
    - `permits_2025_draw_res`
    - `permits_2025_draw_nr`
    - `permits_2025_draw_total`
    - `permits_2025_draw_source`
- File modified:
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Backup created:
  - `processed_data/backups/DATABASE_before_drop_permits_2025_draw_family_20260530_073655.csv`
- Validation:
  - Row count after change: `1449`
  - Column count after change: `35`
  - Removed columns are absent
  - Canonical 2025 permit truth columns remain present:
    - `permits_2025_res`
    - `permits_2025_nr`
    - `permits_2025_total`
    - `permits_2025_source`
  - Draw page/type metadata columns remain present:
    - `draw_2025_bg_pdf_page`
    - `draw_2025_bg_report_page`
    - `draw_2025_type`

## 2026-05-30T07:31:48Z - Drop permits_2026_draw_* Family From DATABASE 2026

- Assigned action:
  - Delete the 2026 draw-subset permit family:
    - `permits_2026_draw_res`
    - `permits_2026_draw_nr`
    - `permits_2026_draw_total`
- File modified:
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Backup created:
  - `processed_data/backups/DATABASE_before_drop_permits_2026_draw_res_20260530_073056.csv`
- Validation:
  - Row count after change: `1449`
  - Column count after change: `39`
  - Presence check:
    - `permits_2026_draw_res`: removed
    - `permits_2026_draw_nr`: removed
    - `permits_2026_draw_total`: removed
    - `permit_allotment_2026_res`: present
    - `permit_allotment_2026_nr`: present
    - `permit_allotment_2026_total`: present

## 2026-05-30T07:25:58Z - DWR Copy/Paste Script Location Note

- Added instruction note file:
  - `scripts/DWR_COPY_PASTE_WORKFLOW.md`
- Scope:
  - documents the generated copy/paste reconciliation scripts and exact run commands
  - includes workflow order for permit normalization and Expo/Conservation reconciliation
- Scripts referenced:
  - `scripts/reconcile-all-species-permits-2026.py`
  - `scripts/reconcile-expo-conservation-rows.py`
  - `scripts/reconcile-deer-conservation-rows.py`
  - `scripts/apply-deer-buck-drawclass-rules.py`
- Validation:
  - file exists and is readable
  - no data/runtime/prediction files changed by this documentation-only note

## 2026-05-30T07:24:06Z - Drop Duplicate permits_2026 Triplet, Keep permit_allotment_2026 Triplet

- Assigned action:
  - Keep `permit_allotment_2026_res`, `permit_allotment_2026_nr`, `permit_allotment_2026_total`.
  - Delete duplicate columns `permits_2026_res`, `permits_2026_nr`, `permits_2026_total`.
- File modified:
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Backup created:
  - `processed_data/backups/DATABASE_before_drop_permits_2026_columns_20260530_072345.csv`
- Validation:
  - Row count after change: `1449`
  - Column count after change: `42` (from `45`)
  - Presence check:
    - `permits_2026_res`: removed
    - `permits_2026_nr`: removed
    - `permits_2026_total`: removed
    - `permit_allotment_2026_res`: present
    - `permit_allotment_2026_nr`: present
    - `permit_allotment_2026_total`: present
  - Nonblank coverage retained for kept columns:
    - `permit_allotment_2026_res`: `938`
    - `permit_allotment_2026_nr`: `932`
    - `permit_allotment_2026_total`: `1173`

## 2026-05-30T05:28:43Z - Expo/Conservation Reconcile Script + All-Species Permit Reconcile Script

- Added reusable Expo/Conservation reconciliation script:
  - `scripts/reconcile-expo-conservation-rows.py`
- Script behavior:
  - confirms conservation/expo rows using `DATABASE.csv`, conservation-match table, and row text cues
  - fills missing `hunt_code` by normalized `hunt_name + weapon` match to DATABASE when confident
  - applies draw-class outputs:
    - conservation -> `hunt_type=conservation` and organization list in `hunt_class` when available
    - expo -> `hunt_type=L.E.` and `hunt_class=expo`
  - conservation precedence over expo when both are present
- Added reusable all-species permit reconciliation script:
  - `scripts/reconcile-all-species-permits-2026.py`
- Script behavior:
  - normalizes permit text labels (`Res:`, `NonRes:`, `Total:`) into numeric permit columns
  - moves/deletes blank non-res continuation rows when detected
  - computes total when resident + nonresident are present and total is blank
  - reconciles permit columns against DATABASE 2026 truth (`permits_2026_*`, fallback `permit_allotment_2026_*`)
  - default excludes Expo/Conservation rows for “all other species permits”
  - uses similarity gate (default 0.80): overwrite mismatches only when target-vs-truth similarity is high, otherwise fill blanks only
- Validation:
  - `python -m py_compile scripts/reconcile-expo-conservation-rows.py` PASS
  - `python -m py_compile scripts/reconcile-all-species-permits-2026.py` PASS
  - `python scripts/reconcile-expo-conservation-rows.py --target-csv "C:/Users/tyler/Desktop/species truth data/2026 deer buck db.csv"` PASS
    - rows checked: `458`
    - changes: `0`
    - conservation rows touched (already aligned): `5`
  - `python scripts/reconcile-all-species-permits-2026.py --target-csv "C:/Users/tyler/Desktop/species truth data/2026 deer doe.csv"` PASS
    - rows checked after continuation-row cleanup: `20`
    - moved non-res rows: `4`
    - deleted continuation rows: `4`
    - normalized cells: `24`
    - permit-database changes: `0`
  - `python scripts/reconcile-all-species-permits-2026.py --target-csv "C:/Users/tyler/Desktop/species truth data/2026 deer buck db.csv"` PASS
    - rows checked: `458`
    - blank permit cells eligible to fill from truth: `20`
    - special rows excluded (expo/conservation): `5`
- Data protection:
  - no changes to `DATABASE.csv`
  - no runtime/prediction/public-page files changed

## 2026-05-30T03:17:26Z - Research Outlook Contract Fallback + Dashboard Contract Validation

- Implemented a fallback seed path in `scripts/build-hunt-research-classification-layer.js` so `hunt_application_outlook` can still be generated when `processed_data/hunt_master_enriched.csv` is unavailable by seeding from `processed_data/point_ladder_view.csv`.
- Kept prediction math untouched and preserved guardrails that protect `DATABASE.csv`, predictive runtime rows, and ladder source rows from modification.
- Regenerated research contract outputs:
  - `processed_data/research_page/hunt_application_outlook.json`
  - `processed_data/research_page/hunt_application_outlook.csv`
  - `processed_data/audits/hunt_classification_layer_audit.json`
- Regeneration result:
  - outlook rows: `2898`
  - tag rows: `13446`
  - sleeper rows: `184`
  - blocked rows: `0`
  - protected file hash checks: `database=true`, `predictive=true`, `ladder=true`
- Validation:
  - `node --check scripts/build-hunt-research-classification-layer.js` PASS
  - `node --check hunt-research.js` PASS
  - `node --check assets/js/research-outlook-dashboard.js` PASS
  - `node scripts/build-hunt-research-classification-layer.js` PASS
  - `npm.cmd run build` PASS
- Mobile QA final pass:
  - Confirmed mobile breakpoints and overflow protections remain active for Research + dashboard components via CSS contract checks (`@media (max-width: 1220px/768px)`, `overflow-x: auto`, one-column collapse, and min-width safeguards on ladder/dashboard containers).
  - No mobile-only style regressions were introduced by this change set.

## 2026-05-29T17:36:34Z - Research Readability And Library Overlay Polish

- Removed the visible Hunt Research runtime source URL paragraph from the dashboard source/freshness details while keeping compact source metadata fields available.
- Made the shared page navigation/header stay at the top by fixing the static nav strip and making the rebuilt `header-layout.js` topbar sticky; refreshed cache-bust tokens in the pages that load those assets.
- Improved Hunt Research readability: darker labels, stronger summary values, clearer hunt subtitle/readout text, unclipped signal legend, larger signal text, and a taller point-ladder viewing area.
- Converted Hunting Bible folder results into a centered overlay panel with a close button; file cards and actions now use higher-contrast parchment styling.
- Changed embedded library resources to open in a fixed primary-screen overlay instead of scrolling the visitor down-page; PDF flipbook remains modal and opens over the primary screen.
- Validation: `node --check header-layout.js`, `node --check assets/js/research-outlook-dashboard.js`, `node --check assets/js/hard-copy-public-library.js`, `node --check hunt-research.js`, `node --check app.js`, and `npm.cmd run build` all passed.
- Local browser smoke test: Research source URL text count `0`, rebuilt header computed `position: sticky`, point-ladder viewport height approximately `890px`, Hunting Bible results panel computed `position: fixed`, and folder overlay opened visibly.
- Build note: the build regenerated library data/manifests as a side effect; those generated data changes were restored because this pass was UI-only.
- Commit: recorded in final closeout report for this UI pass.

## 2026-05-29T08:35:12Z - Backfill Blank 2026 Permit Cells From DWR Popup Nonzero Values

- Backfilled 369 blank `permits_2026_*` cells and matching `permit_allotment_2026_*` cells from nonzero DWR Hunt Planner popup values where both DATABASE permit and allotment cells were blank.
- Added `database_dwr_huntplanner_2026_backfilled_permits_vs_2025.csv` to compare every DWR backfilled 2026 cell against the matching 2025 permit field.
- Backfill breakdown: 327 resident cells, 15 nonresident cells, and 27 total cells.
- 2025 comparison: 324 backfilled cells were within 20% of 2025, 42 were flagged as 20%+ big changes, and 3 had no 2025 value.
- Remaining nonmatches after backfill: 1,635 blank-vs-DWR-zero cells, 342 numeric conflicts, and 1 other difference; these were not overwritten.
- Ran `npm.cmd run build`: PASS. Total current hunts 1,449; modeled 1,448; manual review 0; Gate PASS 1,449; Gate BLOCK 0; crosswalk matched current codes 169.

## 2026-05-29T08:10:05Z - Confirm 2026 Permit Allotment Columns Against DWR Popup

- Updated the DWR Hunt Planner database merge script to check and fill `permit_allotment_2026_res`, `permit_allotment_2026_nr`, and `permit_allotment_2026_total` only when the canonical `permits_2026_*` value exactly matches the DWR Hunt Planner popup value.
- Added an allotment-fill audit showing whether each permit/allotment cell was already matched, filled, or not filled because DATABASE and DWR did not match.
- Result: 2,000 allotment cells already matched DATABASE and DWR; 0 new allotment cells were filled; 343 cells were not filled because DATABASE and DWR permit values did not match; 2,004 cells had no DATABASE permit value to promote.
- Existing `permit_allotment_2026_*` columns remain the display/allocation columns; no duplicate DWR permit columns were added.
- Ran `npm.cmd run build`: PASS. Total current hunts 1,449; modeled 1,448; manual review 0; Gate PASS 1,449; Gate BLOCK 0; crosswalk matched current codes 169.

## 2026-05-29T07:59:06Z - Clean DATABASE DWR Management Objective Fields

- Removed duplicate DWR-prefixed permit/source overlay fields from `DATABASE.csv`; existing `permits_2026_res`, `permits_2026_nr`, and `permits_2026_total` remain the permit columns.
- Kept `percent_harvest_success_previous_hunting_season` and `current_age_3yr_average` as clean source fields from the DWR Hunt Planner popup.
- Added back only the non-duplicate DWR management-context fields: `dwr_huntplanner_age_objective`, `dwr_huntplanner_population_objective`, and `dwr_huntplanner_current_population_estimate`.
- Added a permit comparison audit plus nonmatch-only CSV so matching values are visible and nonmatching values are reported instead of silently overwritten.
- Added a management-plan comparison audit against the elk and mule deer foundational reference extracts. DWR Hunt Planner boundary-deduped sums do not exactly match statewide plan totals, so these fields remain unit/hunt context rather than direct plan rollups.
- Validation: 1,449 DATABASE rows; 960 previous-season harvest-success values; 220 current age 3-year average values; 220 age objective values; 618 population objective values; 611 current population estimate values.
- Ran `npm.cmd run build`: PASS. Total current hunts 1,449; modeled 1,448; manual review 0; Gate PASS 1,449; Gate BLOCK 0; crosswalk matched current codes 169.

## 2026-05-29T07:46:30Z - DATABASE DWR Hunt Planner Source Overlay

- Appended reviewed DWR Hunt Planner source-evidence columns to canonical 2026 `DATABASE.csv` without overwriting existing permit truth columns.
- Added source columns for DWR popup URL/retrieval metadata, season text, DWR permit evidence, previous-season percent harvest success, current age 3-year average, age objective, population objective, and current population estimate.
- Created a repeatable merge script and permit comparison audit for DATABASE vs DWR Hunt Planner popup values.
- Validation: 1,449 DATABASE rows, 1,449 matched DWR popup hunt codes, 0 missing popup rows, 960 previous-season harvest-success values populated, 220 current age 3-year average values populated.
- Permit comparison audit classified 2,347 difference cells: 1,635 DATABASE blank vs DWR zero, 369 DATABASE blank vs DWR value, 342 numeric conflicts, and 1 other difference. Existing canonical permit columns were not overwritten.
- Ran `npm.cmd run build`: PASS. Total current hunts 1,449; modeled 1,448; manual review 0; Gate PASS 1,449; Gate BLOCK 0; crosswalk matched current codes 169.

## 2026-05-29T07:36:06Z - DWR Hunt Planner Popup Data Extract

- Created a DWR Hunt Planner HaNumber JSON extractor for the 2026 current hunt-code universe.
- Extracted popup-backed source evidence for 1,449 current hunt codes from the public DWR Hunt Planner endpoint.
- Captured permit counts, season text, surrender/survey dates, percent harvest success, population fields, age objective, current age 3-year average, boundaries, and biologist notes where DWR exposes them.
- Wrote normalized CSV/JSON outputs plus audit CSV/JSON under processed_data.
- Validation: 1,449 rows fetched, 1,449 OK, 0 fetch errors, 970 rows with management stats, 960 with percent harvest success, 220 with current age 3-year average, 1,449 PASS review rows.
- Important guardrail: current_age_3yr_average is DWR Hunt Planner current-age context, not prior-year average harvest age; this extract does not modify DATABASE.csv or prediction outputs.

## 2026-05-29T06:58:53Z - BR1000 Black Bear Statewide Season Display Correction

- Updated the 2026 hunt-table generator with a deterministic BR1000 season display override.
- Regenerated and published the BR1000 2026 hunt table XLSX/PDF display files through the hunt-table pipeline.
- Verified BR1000 in the live XLSX and pages-dist XLSX contains the corrected season text.
- Verified the generated BR1000 PDF text contains the corrected season text.
- Ran npm.cmd run build: PASS. Library gate remains Gate BLOCK 0 and Manual review 0; crosswalk matched current codes remains 169.

# WORK LOG

## Regenerate 2026 Hunt Table XLSX/PDF Display Files With Season Enrichment
- Timestamp (UTC): 2026-05-29T05:54:27Z
- Scope:
  - Regenerated the full 2026 hunt-table display set from `processed_data/hunt_research_2026_split/hunts`.
  - Patched the XLSX generator to enrich display rows from canonical `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` by normalized `hunt_code`, with conservative `species + hunt_name` fallback available.
  - Fixed the season-column issue by loading `season` from `DATABASE.csv`; for the one statewide black bear row where `DATABASE.csv` and the source workbook had a blank season, used the reviewed note sentence that explicitly describes the season.
  - Preserved public display formatting: row-1 headers, dark brown/white header row, parchment banded rows, table filters, wrapped text, legal landscape print setup, narrow margins, fit-to-width, and centered print layout.
  - Updated PDF conversion to clear stale PDFs before rendering, use legal landscape page size, and rewrite the hard-copy PDF manifest from the regenerated PDF/XLSX pairs.
- Files updated:
  - `.gitattributes`
  - `scripts/regenerate-hunt-tables-2026-clean-xlsx.py`
  - `scripts/convert-hunt-tables-2026-xlxs-to-pdfs.py`
  - `processed_data/hard_data_exports/hard_copy_pdf_manifest.web.json`
  - `processed_data/audits/hunt_tables_2026_clean_xlsx_regeneration_audit.csv`
  - `processed_data/hard_data_exports/hunt_tables/2026/XLXS/*`
  - `processed_data/hard_data_exports/hunt_tables/2026/PDF'S/*`
  - `pages-dist/processed_data/hard_data_exports/hunt_tables/2026/XLXS/*`
  - `pages-dist/processed_data/hard_data_exports/hunt_tables/2026/PDF'S/*`
- Outputs created / regenerated:
  - 119 clean XLSX files
  - 119 matching PDF files
  - 119 staged clean XLSX files
  - 119 hard-copy PDF manifest entries with valid XLSX companions
- Key results:
  - Live XLSX files: 119
  - Live PDF files: 119
  - `pages-dist` XLSX files: 119
  - `pages-dist` PDF files: 119
  - Total hunt rows rendered: 1288
  - Bad workbook header/table/merge issues: 0
  - Blank season rows: 0
  - Database code join rows: 1288
  - Database name fallback rows: 0
  - Missing database join rows: 0
  - Manifest hunt-table entries: 119
  - Manifest missing links: 0
- Validation commands run:
  - `python -m py_compile scripts/regenerate-hunt-tables-2026-clean-xlsx.py scripts/convert-hunt-tables-2026-xlxs-to-pdfs.py`
  - `npm.cmd run hunt-tables:2026:clean-all`
  - workbook validation for headers, merged cells, table count, row count, and blank seasons
  - manifest link validation for regenerated PDF/XLSX hrefs
  - `npm.cmd run build`
- Build result:
  - Total current hunts: 1449
  - Modeled: 1448
  - Manual review: 0
  - Gate PASS: 1449
  - Gate BLOCK: 0
  - Crosswalk matched current codes: 169
- Commit:
  - This entry is included in the hunt-table regeneration commit.

## Elk Plan Codex Instruction Integration
- Timestamp (UTC): 2026-05-29T00:56:00Z
- Scope:
  - Added elk statewide management-plan instructions to `AGENTS.MD` so Codex treats the elk plan as policy / quality-context reference, not raw harvest truth, permit truth, or draw-odds truth.
  - Added guardrails requiring Codex to distinguish observed annual-report `average_harvest_age` from elk management-plan age objectives such as `6.5-7.0`, `6.0-6.5`, and `5.5-6.0`.
  - Added explicit prohibition against using `average_days_hunted`, `mean_days_hunted`, hunter days, or pursuit days as animal age.
  - Added rules preventing elk plan values from directly modifying `DATABASE.csv`, permit/allotment values, `p_draw`, point-ladder probabilities, or website-facing runtime files.
  - Added allowed elk-plan context outputs such as `elk_plan_quality_rules.json`, `elk_plan_context_features.csv`, and `elk_age_objective_context_by_unit.csv`.
- Files updated:
  - `AGENTS.MD`
  - `WORK_LOG.md`
- Supporting files to copy into repo if not already present:
  - `elk_statewide_plan_foundational_reference_codex_expanded.md`
  - `CODEX_TASK_elk_plan_context_integration.txt`
- Validation target:
  - Confirm `AGENTS.MD` contains `Elk Statewide Plan Reference And Age-Quality Guardrails`.
  - Confirm `WORK_LOG.md` contains this closeout entry.
  - Confirm no runtime engine files, `DATABASE.csv`, prediction outputs, or website feeds were changed by this documentation-only integration.


## Hunt Research DB1533 Permit + Guaranteed-Line Fallback Fix
- Timestamp (UTC): 2026-05-28T11:40:00Z
- Scope:
  - Updated `hunt-research.js` permit display fallbacks so permit numbers render when only total permit fields are populated (for example `permits_2026_total`, `permit_allotment_2026_total`, `public_permits_2026`).
  - Added derived guaranteed-line fallback logic:
    - if explicit guaranteed/cutoff fields are missing, infer guaranteed point from ladder rows where modeled odds are effectively `>= 99.9%`.
  - Wired guaranteed-line fallback into:
    - summary top card (`Guaranteed To Draw Line`)
    - summary status card
    - ladder guaranteed marker detection.
- Validation:
  - `node --check hunt-research.js` passed.
  - `npm.cmd run build` passed.
  - Data confirmation for `DB1533`:
    - 2026 total permits present (`5400`) in canonical/runtime files.
    - modeled ladder rows exist in `point_ladder_view.csv` for resident/nonresident.
    - derived guaranteed-point fallback resolves to `2` points for both resident and nonresident ladders based on `>=99.9%` rows.

## Adaptive Ladder Headers + Preference/Bonus Mode Split
- Timestamp (UTC): 2026-05-28T11:05:00Z
- Scope:
  - Updated `research.html` ladder header row to use dynamic header IDs for a single adaptive ladder component.
  - Updated `hunt-research.js` to detect ladder display mode by draw family and status:
    - `PREFERENCE`
    - `BONUS`
    - `YOUTH_RESERVE`
    - `ALLOCATION_AVAILABILITY`
    - `STATUS_ONLY`
  - Added conditional header rendering with fixed five-column layouts per mode.
  - Added preference-specific odds precedence for ladder rendering:
    - `display_odds_pct`
    - `p_draw_mean * 100`
    - `odds_2026_projected`
    - `preference_draw_odds_2026`
    - `preference_projection_2026`
    - `modeled_preference_probability`
    - `draw_probability`
    - `p50`
  - Reworked ladder row rendering so preference families no longer use bonus-style max/random labels.
  - Preserved one ladder component; no per-hunt-type page split was introduced.
- Validation:
  - `node --check hunt-research.js` passed.
  - `npm.cmd run build` passed.
  - Verified `pages-dist/hunt-research.js` includes adaptive header/mode logic and preference odds mapping tokens.
  - Verified current runtime data examples:
    - `PREFERENCE_GENERAL_SEASON_BUCK_DEER` modeled rows present (`132`) in predictive runtime.
    - Youth rows present as `YOUTH_DRAW_ONLY_ELK` pending (`2`) and not force-modeled.

## Predictive Pending Resolution + Youth Reserve Modeling + Age Quality Scoring
- Timestamp (UTC): 2026-05-28T09:55:00Z
- Scope:
  - Updated `engine/utah_draw_predictive/preference_general_deer.py` modeled-status gate so rows with valid modeled preference probability outputs are promoted to `MODELED_PREFERENCE` instead of remaining `IN_SCOPE_MODEL_PENDING`.
  - Implemented explicit youth reserve mechanics in `engine/utah_draw_predictive/youth.py`:
    - `YOUTH_GENERAL_DEER_RESERVE` and `YOUTH_ANTLERLESS_OR_DOE_RESERVE` now use a reserve model contract with:
      - up to 20% youth reserve permit split (`quota_2026_youth_reserve`)
      - rollover-to-main-draw probability composition
      - modeled/pending gating via `youth_reserve_model_valid`.
    - Kept `YOUTH_DRAW_ONLY_ELK` separate from adult preference and pending when source mechanics remain unresolved.
    - Kept `YOUTH_OTC_OR_AVAILABILITY` excluded/non-draw.
  - Added age-quality scoring support in `engine/utah/quality_score.py` and integrated it via `engine/utah/materialize_engine.py`:
    - Added `age_quality_score`
    - Added `average_age_harvested`
    - Added `age_data_available`
    - Added `age_quality_source_field`
    - Implemented neutral fallback (`50.0`) when age data is missing.
    - Applied class-aware weighting:
      - stronger age weighting for LE/PLE/OIL/CWMU/trophy-oriented categories
      - standard weighting for general/opportunity hunts.
  - Exposed quality component fields in `processed_data/model_outputs/hunt_decision_scores_v1.csv`.
- Validation:
  - `python -m py_compile engine/utah_draw_predictive/preference_general_deer.py engine/utah_draw_predictive/youth.py engine/utah/quality_score.py engine/utah/materialize_engine.py` passed.
  - `python scripts/materialize_predictive_outputs.py` passed.
  - `python -m engine.utah.materialize_engine --input processed_data --output processed_data/model_outputs` passed.
  - `npm.cmd run build` passed.
  - Predictive status delta after rematerialization:
    - `PREFERENCE_GENERAL_SEASON_BUCK_DEER` pending rows: `132 -> 0`
    - total `IN_SCOPE_MODEL_PENDING`: `612 -> 480`
    - remaining pending families:
      - `BONUS_CWMU_BIG_GAME: 383`
      - `BEAR_DRAW: 83`
      - `BONUS_ANTLERLESS_MOOSE: 10`
      - `YOUTH_DRAW_ONLY_ELK: 2`
      - `BONUS_TURKEY: 2`
  - Age-data audit across required files:
    - `processed_data/harvest_master.csv`: no average-age columns
    - `processed_data/harvest_quality_features_all_years_by_hunt_code.csv`: `average_age` exists but populated rows `0`
    - `pipeline/RAW/hunt_unit_database/2026/csv/harvest_quality_features_by_hunt_code_2025_for_2026.csv`: no average-age columns
    - `processed_data/hunt_master_enriched.csv`: no average-age columns
    - Current codes with populated age: `0 / 1449` (age fallback neutral currently active for all rows)

## Step 4C Public Library PDF Flipbook + Download Actions
- Timestamp (UTC): 2026-05-28T08:46:50Z
- Scope:
  - Added in-page PDF flipbook viewer shell to `hard-copy.html` with:
    - title
    - download link
    - previous/next controls
    - close button
  - Upgraded `assets/js/hard-copy-public-library.js` card behavior:
    - PDF cards: `View Flipbook` + `Download PDF`
    - Calendar embedded item: `View Calendar` in-page iframe
    - Other files: `Open File` action
  - Implemented lazy-load library strategy for PDF rendering:
    - PDF.js (CDN module)
    - page-flip / StPageFlip (CDN script)
    - no pre-render on initial page load
  - Added in-page flipbook open/close lifecycle and prev/next handlers.
  - Preserved runtime denylist protections and curated folder behavior.
  - Maintained Step 4B regulations public-copy path and manual manifest usage.
- Validation:
  - `npm.cmd run build` passed.
  - Gate remained clean: `Gate BLOCK: 0`, `Manual review: 0`, crosswalk matched `169`.
  - `pages-dist` artifacts verified:
    - `hard-copy.html`
    - `assets/css/hard-copy-public-library.css`
    - `assets/js/hard-copy-public-library.js`
    - `assets/backgrounds/library-wallpaper.jpg`
  - Public regulations copy path verified:
    - `pages-dist/public/hard-copy/regulations/2026/` contains 6 PDFs.
  - Preview probe URL returned `200` and includes both:
    - `uogaPdfFlipPanel`
    - `uogaEmbedPanel`
  - Manifest-level curation check remained:
    - Rules `6`
    - Calendar `1`
    - `raw_runtime_exposed = 0`

## Step 4B Public Library Calendar + Regulations Population
- Timestamp (UTC): 2026-05-28T08:40:08Z
- Scope:
  - Populated public Rules/Regulations and Calendar folders for `hard-copy.html` curation layer only.
  - Added manual public manifest file:
    - `processed_data/hard_data_exports/library/public_library_manual_items.json`
  - Added 6 regulation PDF public items sourced from:
    - `pipeline/RAW/hunt_unit_database/2026/pdf/regulations`
  - Added Utah DWR calendar as embedded item (`type=iframe`, `delivery=embedded`) for in-page calendar viewing.
  - Updated `assets/js/hard-copy-public-library.js` to:
    - load manual public items manifest
    - map regulation/rules/guidebook/proclamation/application signals to Rules folder
    - map calendar signals to Calendar folder
    - open embedded items in-page via iframe panel (no navigation away)
    - keep runtime denylist protection active for raw engine/internal files
  - Updated `assets/css/hard-copy-public-library.css` with embedded panel styling and responsive iframe behavior.
  - Updated `scripts/build-pages-dist.js` with narrow public copy rule:
    - copy only `pipeline/RAW/hunt_unit_database/2026/pdf/regulations/*.pdf`
    - to `pages-dist/public/hard-copy/regulations/2026/`
    - no broad `pipeline/RAW` exposure.
- Validation:
  - `npm.cmd run build` passed.
  - Build gate remained clean: `Gate BLOCK: 0`, `Manual review: 0`, crosswalk matched `169`.
  - Verified output files in `pages-dist`:
    - `hard-copy.html`
    - `assets/css/hard-copy-public-library.css`
    - `assets/js/hard-copy-public-library.js`
    - `assets/backgrounds/library-wallpaper.jpg`
  - Verified regulations PDF publish path exists and contains 6 PDFs:
    - `pages-dist/public/hard-copy/regulations/2026/`
  - Verified preview URL returned `200` and includes embedded panel markup.
  - Manifest-level curation check:
    - Rules folder count: `6`
    - Calendar folder count: `1`
    - `raw_runtime_exposed: 0`

## Step 4 Public Hunt Library Curation (hard-copy.html)
- Timestamp (UTC): 2026-05-28T08:23:36Z
- Scope:
  - Reworked `hard-copy.html` into a clean public-library shell with external CSS/JS only (removed large inline force-hide baseline).
  - Replaced `assets/css/hard-copy-public-library.css` with a wallpaper-first interactive layout:
    - full-screen wallpaper
    - centered top public nav
    - compact search bar
    - parchment-style 8-folder selector grid
    - compact results drawer/panel
  - Replaced `assets/js/hard-copy-public-library.js` with curated public behavior:
    - hides results on initial load
    - opens filtered results only after folder click or non-empty search
    - clear button resets search + folder and hides results panel
    - blocks raw runtime/internal files from public rendering via denylist
    - keeps curated public manifest/pdf sources and explicit 2026 hunt-units public CSV link
  - Kept hard-data/research runtime chain intact; no canonical database cleanup/deletion/move/rename/archive performed.
- Validation:
  - `npm.cmd run build` passed.
  - Build gate remained clean:
    - `Gate BLOCK: 0`
    - `Manual review: 0`
    - Crosswalk scan matched `169` current codes.
  - `pages-dist` output checks passed:
    - `pages-dist/hard-copy.html`
    - `pages-dist/assets/css/hard-copy-public-library.css`
    - `pages-dist/assets/js/hard-copy-public-library.js`
    - `pages-dist/assets/backgrounds/library-wallpaper.jpg`
  - Local preview probe returned HTTP `200` for `http://localhost:8091/hard-copy.html?v=step4-public-library`.

## Step 3 Canonical Data Chain Lock Report
- Timestamp (UTC): 2026-05-28T08:10:33Z
- Scope:
  - Implemented canonical-chain validator script: `scripts/build-canonical-data-chain-report-step3.js`.
  - Generated required outputs:
    - `processed_data/audits/canonical_data_chain_report.csv`
    - `processed_data/audits/canonical_data_chain_report.json`
  - Validated canonical chain roles for:
    - official source (`DATABASE.csv`)
    - runtime masters
    - current-to-historical crosswalk
    - draw/prediction runtime files
    - harvest evidence files
    - model outputs + model run report
    - public Hunt Library exports
  - Enforced file-size publishing rule:
    - files over `25 MiB` marked `cloudflare_fallback_required=true` and `pages_dist_publishable=false`.
  - Confirmed crosswalk uses `current_hunt_code` for current join and preserves `historical_hunt_code` as historical metadata.
  - Kept task read/validate/report only for chain locking; no moves/deletes/renames/archives performed.
- Validation:
  - `node scripts\\build-canonical-data-chain-report-step3.js` passed.
  - `npm.cmd run build` passed.
  - Build gate remained clean:
    - `Gate BLOCK: 0`
    - `Manual review: 0`
    - Crosswalk scan: `169` rows matched to current codes.
  - Block query returned no rows:
    - `Import-Csv processed_data\\library\\library_page_hunts.csv | Where-Object { manual_review_required=true or gate_status=BLOCK }`

## Step 2 Database Fragment Manifest (Inventory + Classification Only)
- Timestamp (UTC): 2026-05-28T07:58:59Z
- Scope:
  - Implemented a Step 2-specific inventory/classification generator: `scripts/build-database-fragment-manifest-step2.js`.
  - Scanned the requested roots without moving or deleting files:
    - `processed_data/`
    - `pipeline/`
    - `data/`
    - `_exports/`
    - `C:\\Users\\tyler\\Desktop\\GitHub\\HUNTS\\data_truth` (read-only inventory)
  - Produced required outputs:
    - `processed_data/audits/database_fragment_manifest.csv`
    - `processed_data/audits/database_fragment_manifest.json`
  - Applied explicit known-file classification rules for official source, runtime master, prediction runtime, model outputs, harvest evidence, historical crosswalk, and public export files.
  - Added duplicate/stale family detection and external HUNTS truth candidate gap detection for review.
- Validation:
  - `node scripts\\build-database-fragment-manifest-step2.js` passed.
  - Output files exist and are populated.
  - Manifest summary:
    - total rows: `5763`
    - unknown_needs_review: `4101`
    - obsolete_fragment: `92`
    - public_export: `78`
    - prediction_runtime: `8`
    - likely needed from `HUNTS/data_truth` but not imported by filename match: `126`

## Step 1B Gate-Block Resolution Audit (PD1006 / PD1045 / PD1046)
- Timestamp (UTC): 2026-05-28T07:44:58Z
- Scope:
  - Re-ran the Step 1B blocker investigation for `PD1006`, `PD1045`, and `PD1046` across the required current source, runtime, coverage, crosswalk, and harvest files.
  - Confirmed all three hunt codes are present in `DATABASE.csv`, `hunt_master_enriched.csv`, `hunt_unit_reference_linked.csv`, `draw_reality_engine.csv`, and `point_ladder_view.csv`.
  - Confirmed `PD1045` and `PD1046` are also present in `draw_reality_engine_predictive_v2.csv` and `ml_draw_predictions_v1.csv`.
  - Confirmed `PD1006` is absent from predictive output files but present in `predictive_coverage_report.csv` with `in_current_database=True`, `in_forecast=False`, and `exclusion_reason=not_OIL_LE_PLE`, while still carried in runtime as `DATABASE_REFERENCE_ONLY_NO_DRAW_DETAIL`.
  - Confirmed all three are not present in the current-to-historical crosswalk, which remains expected because this bridge only includes selected current-code families (`169` total matched current codes) and does not govern general current-code inclusion.
  - Confirmed harvest evidence exists for all three via `harvest_master.csv` and/or `harvest_quality_features_all_years_by_hunt_code.csv`.
  - Updated `scripts/build-library-page-data.js` so `exclusion_reason` is considered classification evidence and `DATABASE_REFERENCE_ONLY_NO_DRAW_DETAIL` rows no longer count as modeled predictions.
  - Rebuilt the library package and confirmed gate closure with zero manual-review and zero block rows.
- Validation:
  - `npm.cmd run build` passed.
  - Build report summary:
    - `total_current_hunts: 1449`
    - `modeled_count: 1448`
    - `manual_review_count: 0`
    - `promotion_gate_pass_count: 1449`
    - `promotion_gate_block_count: 0`
    - Crosswalk scan: `processed_data/current_to_historical_hunt_code_crosswalk_2026.csv: 169 rows, matched 169 current codes total`.
  - `Import-Csv .\processed_data\library\library_page_hunts.csv | Where-Object { $_.manual_review_required -eq "true" -or $_.gate_status -eq "BLOCK" }` returned no rows.

## 2020 Hashed Draw PDF Source Parity For 2021 Modeling
- Timestamp (UTC): 2026-05-27T05:48:00Z
- Scope:
  - Added a dedicated source-anchor audit for the user-supplied hashed-name 2020 draw-odds PDF set used for 2021 modeling.
  - Compared the `13` supplied PDFs from the older `HUNTS` repo against active `HUNT-BUILDER` copies by size and SHA-256 hash.
  - Confirmed all `13 / 13` supplied PDFs are byte-identical in the active repo.
  - Confirmed there are no active-only PDFs and no duplicate hash groups in the active 2020 hashed draw-odds PDF folder.
  - Compared the hashed-name source lineage to the existing named `20_*` 2020-for-2021 source package.
  - Recorded `10` same-hash matches to the existing named `20_*` source folder.
  - Recorded `3` hashed PDFs without a named `20_*` same-hash match: cougar, turkey bonus, and youth turkey.
  - Anchored current normalized 2021 draw truth at `27,519` rows and `550` native unique hunt codes, with `21_bg-odds.pdf` as the current source label.
  - Flagged source labels as `SOURCE_LABEL_LINEAGE_REVIEW` because this hashed lineage is source evidence and does not currently appear as normalized row labels.
  - Kept the audit source-only/read-only: no PDF extraction, normalized draw rewrite, `DATABASE.csv` edit, website feed edit, or prediction output edit was performed.
- Outputs:
  - `scripts/audit-draw-2020-hashed-for-2021-source-parity.py`
  - `tests/utah/test_draw_2020_hashed_for_2021_source_parity.py`
  - `data_truth/draw_results_truth/validation/draw_2020_hashed_for_2021_source_parity.csv`
  - `data_truth/draw_results_truth/validation/draw_2020_hashed_for_2021_source_parity_summary.json`
  - `processed_data/draw_2020_hashed_for_2021_source_parity.md`
- Validation:
  - `python scripts\audit-draw-2020-hashed-for-2021-source-parity.py` passed.
  - `python -m py_compile scripts\audit-draw-2020-hashed-for-2021-source-parity.py tests\utah\test_draw_2020_hashed_for_2021_source_parity.py` passed.
  - `python -m pytest tests\utah\test_draw_2020_hashed_for_2021_source_parity.py tests\utah\test_draw_2020_for_2021_source_parity.py -q` passed: `7`.

## 2023 Draw PDF Source Parity For 2024 Modeling
- Timestamp (UTC): 2026-05-27T05:40:00Z
- Scope:
  - Added a dedicated source-anchor audit for the user-supplied 2023 draw-odds PDF set used for 2024 modeling.
  - Compared the `17` supplied PDFs from the older `HUNTS` repo against active `HUNT-BUILDER` copies by size and SHA-256 hash.
  - Confirmed all `17 / 17` supplied PDFs are byte-identical in the active repo.
  - Confirmed there are no active-only PDFs and no duplicate hash groups in the active 2024 draw-odds PDF folder.
  - Linked the PDF source set to the previously anchored 2023-for-2024 CSV exports.
  - Recorded that the two CSV exports directly represent `7 / 17` expected PDF labels and leave `10` expected PDF labels unrepresented as direct CSV `source_file` labels.
  - Recorded current normalized draw-year/model-year 2024 truth at `37,128` rows and `580` unique hunt codes.
  - Flagged normalized 2024 draw truth source labels as `SOURCE_LABEL_LINEAGE_REVIEW` because they use `24_*` source labels rather than this anchored 2023 PDF source set.
  - Kept the audit source-only/read-only: no PDF extraction, normalized draw rewrite, `DATABASE.csv` edit, website feed edit, or prediction output edit was performed.
- Outputs:
  - `scripts/audit-draw-2023-for-2024-pdf-source-parity.py`
  - `tests/utah/test_draw_2023_for_2024_pdf_source_parity.py`
  - `data_truth/draw_results_truth/validation/draw_2023_for_2024_pdf_source_parity.csv`
  - `data_truth/draw_results_truth/validation/draw_2023_for_2024_pdf_source_parity_summary.json`
  - `processed_data/draw_2023_for_2024_pdf_source_parity.md`
- Validation:
  - `python scripts\audit-draw-2023-for-2024-pdf-source-parity.py` passed.
  - `python -m py_compile scripts\audit-draw-2023-for-2024-pdf-source-parity.py tests\utah\test_draw_2023_for_2024_pdf_source_parity.py` passed.
  - `python -m pytest tests\utah\test_draw_2023_for_2024_pdf_source_parity.py tests\utah\test_draw_2023_for_2024_csv_source_parity.py -q` passed: `9`.

## 2023 Draw CSV Source Parity For 2024 Modeling
- Timestamp (UTC): 2026-05-27T05:26:00Z
- Scope:
  - Added a dedicated source-anchor audit for the two large user-supplied 2023-for-2024 draw-result CSV exports.
  - Verified both files from the older `HUNTS` repo are present in active `HUNT-BUILDER` as exact byte and row-content matches.
  - Anchored `draw_results_2023_for_2024_long.csv` at `35,960` rows and `580` unique hunt codes, with one represented source file and all rows classified as bonus draw method.
  - Anchored `draw_results_2023_for_2024_UPLOADED_COMBINED_long.csv` at `38,682` rows and `593` unique hunt codes, with six represented source files and both bonus and preference draw methods.
  - Recorded the row-key relationship between the two CSVs: `11,718` overlapping row keys, `24,242` standard-only row keys, and `26,964` uploaded-combined-only row keys.
  - Compared both source exports to current normalized model-year/draw-year 2024 draw truth without promoting either CSV.
  - Recorded current normalized 2024 draw truth at `37,128` rows and `580` unique hunt codes.
  - Recorded standard-vs-normalized 2024 overlap: `558` hunt codes and `21,416` row keys.
  - Recorded uploaded-combined-vs-normalized 2024 overlap: `181` hunt codes and `8,011` row keys.
  - Confirmed these source files must go through an explicit reconciliation/promotion step before changing normalized draw truth.
  - Kept the audit source-only/read-only: no normalized draw rewrite, `DATABASE.csv` edit, website feed edit, or prediction output edit was performed.
- Outputs:
  - `scripts/audit-draw-2023-for-2024-csv-source-parity.py`
  - `tests/utah/test_draw_2023_for_2024_csv_source_parity.py`
  - `data_truth/draw_results_truth/validation/draw_2023_for_2024_csv_source_parity.csv`
  - `data_truth/draw_results_truth/validation/draw_2023_for_2024_csv_source_parity_summary.json`
  - `processed_data/draw_2023_for_2024_csv_source_parity.md`
- Validation:
  - `python scripts\audit-draw-2023-for-2024-csv-source-parity.py` passed.
  - `python -m py_compile scripts\audit-draw-2023-for-2024-csv-source-parity.py tests\utah\test_draw_2023_for_2024_csv_source_parity.py` passed.
  - `python -m pytest tests\utah\test_draw_2023_for_2024_csv_source_parity.py tests\utah\test_draw_year_by_year_hardening_2026.py -q` passed: `8`.

## 2022 Draw Odds Source Parity For 2023 Modeling
- Timestamp (UTC): 2026-05-27T05:16:00Z
- Scope:
  - Added a dedicated source-anchor audit for the user-supplied 2022 draw-odds PDF set used for 2023 modeling.
  - Compared the `15` supplied PDFs from the older `HUNTS` repo against active `HUNT-BUILDER` copies by size and SHA-256 hash.
  - Confirmed all `15 / 15` supplied PDFs are byte-identical in the active repo.
  - Recorded the active repo's `2` extra same-hash aliases as duplicate aliases, not additional source coverage:
    - `2022 _Youth antlerless big game draw results.pdf` duplicates `22_youth_antlerless_drawing_odds_report.pdf`.
    - `2022 Dedicated Hunter deer draw results.pdf` duplicates `22_dh_odds.pdf`.
  - Recorded the expected same-hash pair in the supplied source set: `2022 Youth draw-only elk bonus point draw results.pdf` and `22_youth_bull_elk.pdf`.
  - Anchored normalized 2022 draw truth at `18,688` rows and `1,024` native unique hunt codes.
  - Flagged current normalized 2022 draw source labels as `SOURCE_LABEL_LINEAGE_REVIEW` because they still reference 2021 PDF labels, even though the 2022 source package is now anchored.
  - Kept the audit source-only/read-only: no PDF extraction, draw truth rewrite, `DATABASE.csv` edit, website feed edit, or prediction output edit was performed.
- Outputs:
  - `scripts/audit-draw-2022-for-2023-source-parity.py`
  - `tests/utah/test_draw_2022_for_2023_source_parity.py`
  - `data_truth/draw_results_truth/validation/draw_2022_for_2023_source_parity.csv`
  - `data_truth/draw_results_truth/validation/draw_2022_for_2023_source_parity_summary.json`
  - `processed_data/draw_2022_for_2023_source_parity.md`
- Validation:
  - `python scripts\audit-draw-2022-for-2023-source-parity.py` passed.
  - `python -m py_compile scripts\audit-draw-2022-for-2023-source-parity.py tests\utah\test_draw_2022_for_2023_source_parity.py` passed.
  - `python -m pytest tests\utah\test_draw_2022_for_2023_source_parity.py tests\utah\test_draw_year_by_year_hardening_2026.py -q` passed: `7`.

## 2023 Harvest Source Parity For 2024 Modeling
- Timestamp (UTC): 2026-05-27T05:12:00Z
- Scope:
  - Added a dedicated parity audit for the user-supplied `2024/csv/Harvest Results` folder from the older `HUNTS` repo.
  - Compared all `50` supplied 2023 harvest CSVs against active `HUNT-BUILDER` harvest truth raw packages by filename, headers, rows, and hashes.
  - Verified the promoted 2023 all-species baseline package matches active truth packages by row/header content: `15 / 15` files.
  - Verified the separate 2023-24 turkey package files match active truth packages by row/header content: `4 / 4` files.
  - Inventoried `31` uploaded/all-sources/antlerless/supplemental CSVs as review evidence because matching active truth-package copies are not currently promoted.
  - Anchored the normalized 2023 harvest truth count at `1078` rows and `1078` unique native hunt codes.
  - Registered the existing 2023 harvest-vs-draw comparison artifact without promoting harvest values into draw/permit truth.
  - Reconfirmed same-year 2023 harvest/draw alignment: `1078` harvest native codes, `1010` draw native codes, `921` same-code overlap, `157` harvest-only, and `89` draw-only.
  - Kept the audit read-only for truth data: no `DATABASE.csv`, website feeds, draw predictions, permit/allotment cells, or normalized harvest rows were modified.
- Outputs:
  - `scripts/audit-harvest-2023-for-2024-source-parity.py`
  - `tests/utah_quality/test_harvest_2023_for_2024_source_parity.py`
  - `data_truth/harvest_results_truth/validation/harvest_2023_for_2024_source_parity.csv`
  - `data_truth/harvest_results_truth/validation/harvest_2023_for_2024_source_parity_summary.json`
  - `processed_data/harvest_2023_for_2024_source_parity.md`
- Validation:
  - `python scripts\audit-harvest-2023-for-2024-source-parity.py` passed.
  - `python -m py_compile scripts\audit-harvest-2023-for-2024-source-parity.py tests\utah_quality\test_harvest_2023_for_2024_source_parity.py` passed.
  - `python -m pytest tests\utah_quality\test_harvest_2023_for_2024_source_parity.py tests\utah_quality\test_harvest_draw_same_year_alignment_2026.py -q` passed: `7`.

## Harvest Year-By-Year Hardening Audit Against Current 2026 Universe
- Timestamp (UTC): 2026-05-27T04:36:00Z
- Scope:
  - Re-ran the year-by-year harvest truth hardening audit against the current canonical `DATABASE.csv` hunt-code universe.
  - Added a dedicated parity audit for the user-supplied `2021_for_2022` harvest CSV source set from the older `HUNTS` repo.
  - Added a dedicated parity audit for the user-supplied 2023-folder harvest handoff, split into `2022_FOR_2023_MODEL` and `2023_ALL_SPECIES_FOR_2024_MODEL` groups.
  - Verified the external 2021 source files match the active `HUNT-BUILDER` harvest truth package at row/header level before treating the 2021 harvest year as anchored.
  - Verified the external 2022-for-2023 model files and the 2023 all-species files match active `HUNT-BUILDER` harvest truth packages at row/header level.
  - Added the 2021 unique harvest-code baseline note to the generated hardening audit: `974` unique hunt codes in reported hunt year 2021, with an expectation that later years should generally increase slightly or explain any drop.
  - Added harvest metric publication status to the generated audit so captured truth fields are not confused with website/reference-published fields.
  - Added a draw-side year-by-year hardening audit with the same native-count rule: draw years are counted in draw-land first, and 2026 active-code comparison is only cross-reference evidence.
  - Added a dedicated source-anchor audit for the user-supplied 2020 draw-odds PDF set used for 2021 modeling.
  - Added a same-year harvest-vs-draw alignment audit so `2021 harvest` compares to `2021 draw odds/results`, `2022 harvest` to `2022 draw odds/results`, and so on.
  - Recorded the data-land rule that harvest truth and draw truth remain separate until a later feature-combine step for prediction modeling.
  - Kept the pass read-only for truth data: no harvest rows, `DATABASE.csv` values, website feeds, draw predictions, or permit/allotment cells were modified.
  - Confirmed reported harvest years remain `2021` through `2025`, with model target years `2022` through `2026`.
  - Refreshed the existing final harvest audit outputs so their active-code feature-readiness counts align to the current `1449`-code active universe instead of the stale `1394`-code universe.
- Outputs:
  - `scripts/audit-harvest-2021-for-2022-source-parity.py`
  - `scripts/audit-harvest-2022-for-2023-source-parity.py`
  - `tests/utah_quality/test_harvest_2021_for_2022_source_parity.py`
  - `tests/utah_quality/test_harvest_2022_for_2023_source_parity.py`
  - `data_truth/harvest_results_truth/validation/harvest_2021_for_2022_source_parity.csv`
  - `data_truth/harvest_results_truth/validation/harvest_2021_for_2022_source_parity_summary.json`
  - `data_truth/harvest_results_truth/validation/harvest_2022_for_2023_source_parity.csv`
  - `data_truth/harvest_results_truth/validation/harvest_2022_for_2023_source_parity_summary.json`
  - `processed_data/harvest_2021_for_2022_source_parity.md`
  - `processed_data/harvest_2022_for_2023_source_parity.md`
  - `data_truth/harvest_results_truth/validation/harvest_year_by_year_hardening_2026.csv`
  - `data_truth/harvest_results_truth/validation/harvest_year_by_year_hardening_2026_missing_codes.csv`
  - `data_truth/harvest_results_truth/validation/harvest_year_by_year_hardening_2026_historical_only_codes.csv`
  - `data_truth/harvest_results_truth/validation/harvest_year_by_year_hardening_2026_summary.json`
  - `processed_data/harvest_year_by_year_hardening_2026.md`
  - `scripts/audit-draw-year-by-year-hardening-2026.py`
  - `scripts/audit-draw-2020-for-2021-source-parity.py`
  - `tests/utah/test_draw_year_by_year_hardening_2026.py`
  - `tests/utah/test_draw_2020_for_2021_source_parity.py`
  - `data_truth/draw_results_truth/validation/draw_2020_for_2021_source_parity.csv`
  - `data_truth/draw_results_truth/validation/draw_2020_for_2021_source_parity_summary.json`
  - `processed_data/draw_2020_for_2021_source_parity.md`
  - `data_truth/draw_results_truth/validation/draw_year_by_year_hardening_2026.csv`
  - `data_truth/draw_results_truth/validation/draw_year_by_year_hardening_2026_missing_codes.csv`
  - `data_truth/draw_results_truth/validation/draw_year_by_year_hardening_2026_summary.json`
  - `processed_data/draw_year_by_year_hardening_2026.md`
  - `scripts/audit-harvest-draw-same-year-alignment-2026.py`
  - `tests/utah_quality/test_harvest_draw_same_year_alignment_2026.py`
  - `data_truth/comparison_outputs/validation/harvest_draw_same_year_alignment_2026.csv`
  - `data_truth/comparison_outputs/validation/harvest_draw_same_year_alignment_2026_code_detail.csv`
  - `data_truth/comparison_outputs/validation/harvest_draw_same_year_alignment_2026_summary.json`
  - `processed_data/harvest_draw_same_year_alignment_2026.md`
  - refreshed `processed_data/harvest_results_database_final_audit.*`
  - refreshed `processed_data/harvest_results_database_feature_readiness_audit.csv`
  - refreshed `processed_data/harvest_results_database_hunt_code_alignment_audit.csv`
- Key results:
  - Current canonical hunt-code universe: `1449` rows / `1449` unique hunt codes.
  - Harvest best rows: `5151`.
  - Harvest long rows: `68657`.
  - Current codes covered by at least one harvest year: `1242`.
  - Current codes missing from all harvest years: `207`.
  - Historical harvest codes not present in current `DATABASE.csv`: `182`.
  - 2021-for-2022 source parity: `15 / 15` expected CSV files match row-level content between `HUNTS` and `HUNT-BUILDER`.
  - 2021 normalized harvest rows: `974` rows / `974` unique hunt codes.
  - 2022-for-2023 and 2023 all-species handoff parity: `23 / 23` expected CSV files match row-level content between `HUNTS` and `HUNT-BUILDER`.
  - 2022 normalized harvest rows: `924` rows / `924` unique hunt codes.
  - 2023 normalized harvest rows: `1078` rows / `1078` unique hunt codes.
  - Historical harvest years are now shown by native unique hunt-code count first; 2026 active-code matching is labeled `CROSS_REFERENCE_ONLY_NOT_YEAR_COMPLETENESS`.
  - Draw native unique hunt-code counts:
    - 2021: `550`
    - 2022: `1024`
    - 2023: `1010`
    - 2024: `580`
    - 2025: `1053`
    - 2026: `548`
  - Draw truth captures fields useful for later prediction features, including applicants, drawn counts, permits, success ratio, residency, points, draw pool/method where available, source file, and page number.
  - 2020 draw-odds PDF parity for 2021 modeling: `17 / 17` expected PDFs are byte-identical between `HUNTS` and `HUNT-BUILDER`.
  - Current 2021 normalized draw truth rows: `27519`.
  - Current 2021 normalized draw truth source label is `21_bg-odds.pdf`; this is flagged as `SOURCE_LABEL_LINEAGE_REVIEW` because the anchored PDF set is the 2020 draw-odds source set for 2021 modeling.
  - Draw and harvest truth are not combined in this step.
  - Same-year 2021 comparison:
    - Harvest native unique hunt codes: `974`
    - Draw native unique hunt codes: `550`
    - Same-code overlap: `527`
    - Harvest-only same-year codes: `447`
    - Draw-only same-year codes: `23`
  - Same-year 2022 comparison:
    - Harvest native unique hunt codes: `924`
    - Draw native unique hunt codes: `1024`
    - Same-code overlap: `846`
    - Harvest-only same-year codes: `78`
    - Draw-only same-year codes: `178`
  - Harvest truth captures: `average_age`, `hunter_satisfaction`, `average_days`, `percent_success`, `harvest_total`, `harvest_male`, `harvest_female`, `hunters_afield`, and report-context `permits`.
  - Current `hunt_unit_reference_linked.csv` publishes 2025-facing harvest/hunters/success/average-days/satisfaction fields, but not `average_age`.
  - Current `hunt_master_enriched.csv` publishes only the thinner hunters/harvest/success surface for harvest metrics.
  - 2025 reported harvest year coverage: `1122 / 1449` current codes (`77.43%`).
  - Year-by-year current-code coverage:
    - 2021: `836 / 1449`
    - 2022: `824 / 1449`
    - 2023: `1009 / 1449`
    - 2024: `1003 / 1449`
    - 2025: `1122 / 1449`
- Validation:
  - `python scripts\audit-harvest-2021-for-2022-source-parity.py` passed.
  - `python scripts\audit-harvest-2022-for-2023-source-parity.py` passed.
  - `python scripts\audit-draw-2020-for-2021-source-parity.py` passed.
  - `python scripts\audit-harvest-year-by-year-hardening-2026.py` passed.
  - `python scripts\audit-draw-year-by-year-hardening-2026.py` passed.
  - `python scripts\audit-harvest-draw-same-year-alignment-2026.py` passed.
  - `python -m py_compile scripts\audit-harvest-2021-for-2022-source-parity.py scripts\audit-harvest-year-by-year-hardening-2026.py` passed.
  - `python -m pytest tests\utah_quality\test_harvest_2021_for_2022_source_parity.py tests\utah_quality\test_harvest_year_by_year_hardening_2026.py tests\utah_quality\test_harvest_database_final_audit.py tests\utah\test_all_years_harvest_database.py -q` passed: `27`.
  - `python -m pytest tests\utah_quality\test_harvest_year_by_year_hardening_2026.py tests\utah_quality\test_harvest_2021_for_2022_source_parity.py -q` passed after publication-status additions: `9`.
  - `python -m pytest tests\utah_quality\test_harvest_year_by_year_hardening_2026.py tests\utah\test_draw_year_by_year_hardening_2026.py -q` passed after native-count/cross-reference rule corrections: `9`.
  - `python -m pytest tests\utah_quality\test_harvest_draw_same_year_alignment_2026.py tests\utah_quality\test_harvest_year_by_year_hardening_2026.py tests\utah\test_draw_year_by_year_hardening_2026.py -q` passed: `12`.
  - `python -m pytest tests\utah_quality\test_harvest_2022_for_2023_source_parity.py tests\utah_quality\test_harvest_draw_same_year_alignment_2026.py tests\utah_quality\test_harvest_year_by_year_hardening_2026.py tests\utah\test_draw_year_by_year_hardening_2026.py -q` passed: `15`.
  - `python -m pytest tests\utah\test_draw_2020_for_2021_source_parity.py tests\utah\test_draw_year_by_year_hardening_2026.py tests\utah_quality\test_harvest_draw_same_year_alignment_2026.py -q` passed: `9`.

## Main Hunt Master Enriched Hunt-Class And Routing Promotion
- Timestamp (UTC): 2026-05-27T03:53:00Z
- Scope:
  - Promoted the user-facing selection fields and internal draw-routing fields into the main `processed_data/hunt_master_enriched.csv`.
  - Preserved the main enriched file as the full all-hunts reference; it was not replaced by the draw subset and no rows were dropped.
  - Added `species`, `sex_type`, `hunt_class`, `draw_2026_system_type`, `draw_system_type`, `algorithm_status`, and `draw_routing_reason`.
  - Populated selector fields from canonical `DATABASE.csv` by `hunt_code`.
  - Populated routing fields using the active `engine.utah_draw_predictive.classifier` so youth draw-only elk and youth availability/OTC elk route separately.
  - Protected all existing permit/projection numeric fields from overwrite.
- Outputs:
  - `scripts/promote-hunt-class-routing-to-main-enriched-2026.py`
  - `data_truth/comparison_outputs/validation/hunt_master_enriched_hunt_class_routing_2026.csv`
  - `data_truth/comparison_outputs/validation/hunt_master_enriched_hunt_class_routing_2026_summary.json`
  - `processed_data/hunt_master_enriched_hunt_class_routing_2026.md`
  - `tests/utah/test_hunt_master_enriched_hunt_class_routing_2026.py`
  - updated `processed_data/hunt_master_enriched.csv`
- Key results:
  - Row count before/after: `54467` -> `54467`.
  - Unique hunt codes before/after: `1526` -> `1526`.
  - Protected numeric permit/projection cells changed: `0`.
  - Added fields: `species`, `sex_type`, `hunt_class`, `draw_2026_system_type`, `draw_system_type`, `algorithm_status`, `draw_routing_reason`.
  - `EB1007` now carries `hunt_class=Youth`, `draw_system_type=YOUTH_DRAW_ONLY_ELK`, and `algorithm_status=IN_SCOPE_MODEL_PENDING`.
  - `EB1011` now carries `hunt_class=General Bull`, `draw_system_type=YOUTH_OTC_OR_AVAILABILITY`, and `algorithm_status=EXCLUDED_NOT_PREDICTIVE_DRAW`.
- Validation:
  - `python scripts\promote-hunt-class-routing-to-main-enriched-2026.py` passed.
  - `python -m pytest tests\utah\test_hunt_master_enriched_hunt_class_routing_2026.py tests\utah\test_2026_draw_permit_subset.py tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah_draw_predictive\test_youth_general_any_bull_elk_strategy.py tests\utah_draw_predictive\test_youth_coverage.py -q` passed: `15`.
  - `python -m pytest tests\utah\test_hunt_master_enriched_hunt_class_routing_2026.py tests\utah\test_2026_draw_permit_subset.py tests\utah_draw_predictive\test_youth_general_any_bull_elk_strategy.py tests\utah_draw_predictive\test_youth_coverage.py -q` passed after diff cleanup: `13`.
  - `python -m py_compile scripts\promote-hunt-class-routing-to-main-enriched-2026.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed with `0` duplicate hunt codes, `0` blank boundary IDs, and `0` permit/allotment mismatches.

## 2026 Draw Subset Regeneration And Runtime Surface Coverage
- Timestamp (UTC): 2026-05-27T03:45:00Z
- Scope:
  - Regenerated the 2026 draw-routing/classification artifacts after splitting youth draw behavior into explicit families.
  - Preserved the main `processed_data/hunt_master_enriched.csv` as the full all-hunts enriched surface; it was not replaced by the draw subset.
  - Rebuilt the 2026 draw subset from refreshed prediction rows and canonical `DATABASE.csv` permit values.
  - Added an idempotent runtime reference-surface coverage repair script that appends missing `DATABASE.csv` hunt-code reference rows without overwriting existing permit cells or inventing draw odds.
  - Refreshed final permit crosschecks, comprehensive history integrity, and hunt-code family gap scan outputs.
- Outputs:
  - `scripts/repair-runtime-reference-surface-coverage-2026.py`
  - `data_truth/comparison_outputs/validation/runtime_reference_surface_coverage_repair_2026.csv`
  - `data_truth/comparison_outputs/validation/runtime_reference_surface_coverage_repair_2026_summary.json`
  - `processed_data/runtime_reference_surface_coverage_repair_2026.md`
  - refreshed `processed_data/ml_draw_predictions_v1.csv`
  - refreshed `data_truth/comparison_outputs/validation/permits_2026_draw_subset_summary.json`
  - refreshed `processed_data/2026_hunt_code_family_gap_scan*`
  - refreshed final permit and comprehensive integrity reports
- Key results:
  - `DATABASE.csv` remains `1449` rows with `1449` unique hunt codes.
  - Main `hunt_master_enriched.csv` remains a full enriched surface: `54467` rows and `1526` unique hunt codes.
  - Current `DATABASE.csv` codes missing from `hunt_master_enriched.csv`: `0`.
  - Current `DATABASE.csv` codes missing from `point_ladder_view.csv`: `0`.
  - Current `DATABASE.csv` codes missing from `draw_reality_engine.csv`: `0`.
  - 2026 draw subset now contains `863` draw-engine hunt codes and `813` numeric 2026 draw-permit rows.
  - Youth draw-only elk is routed separately as `YOUTH_DRAW_ONLY_ELK` with `1` hunt code.
  - `permits_2026_total` remains `1120` populated rows.
  - `permit_allotment_2026_total` remains `1091` populated rows.
  - `permits_2026_draw_total` is now `813` populated rows after excluding non-draw/availability-only routes from the draw subset.
  - 2026 permit/allotment total mismatches remain `0`.
  - Comprehensive history-integrity fatal blockers remain `0`; open issues remain `0`.
- Validation:
  - `python -m engine.utah_bonus_predictive.materialize --output-dir processed_data --forecast-year 2026 --history-years 2021,2022,2023,2024,2025` passed.
  - `python -m engine.utah_draw_predictive.classifier --output-dir processed_data --forecast-year 2026 --history-years 2021,2022,2023,2024,2025` passed.
  - `python scripts\promote-2026-draw-permit-subset.py` passed.
  - `python scripts\repair-runtime-reference-surface-coverage-2026.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python scripts\scan-2026-hunt-code-family-gaps.py` passed.
  - `python -m pytest tests\utah\test_2026_draw_permit_subset.py tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py tests\utah\test_hunt_code_family_gap_scan_2026.py tests\utah_draw_predictive\test_youth_general_deer_strategy.py tests\utah_draw_predictive\test_youth_general_any_bull_elk_strategy.py tests\utah_draw_predictive\test_youth_not_bonus_or_adult_preference.py tests\utah_draw_predictive\test_youth_coverage.py -q` passed: `23`.
  - `python -m py_compile scripts\repair-runtime-reference-surface-coverage-2026.py scripts\promote-2026-draw-permit-subset.py scripts\final-permit-database-crosscheck-2026.py scripts\scan-2026-hunt-code-family-gaps.py` passed.
  - `git diff --check` passed.

## Utah Draw Routing And Algorithm V1
- Timestamp (UTC): 2026-05-27T03:08:00Z
- Scope:
  - Added the active `HUNT-BUILDER` draw-routing and formula contract that ties the user-facing selection matrix to the internal draw model family.
  - Documented why `hunt_class` exists and when it should be visible: only when it further separates the selected `species -> sex_type -> hunt_type -> weapon` result into a different draw route.
  - Grounded the formulas in current Utah DWR source anchors for bonus points, preference points, group applications, youth reserves, draw-only youth elk, sportsman permits, and expo random drawings.
  - Documented bonus, preference, youth, sportsman, expo, total-only quota, and availability-only guardrails without changing runtime data, permit values, website feeds, or prediction outputs.
- Outputs:
  - `docs/utah_draw_routing_and_algorithm_v1.md`
  - `docs/utah_draw_system_scope.md`
  - `docs/utah_rules_sources.md`
- Key results:
  - The algorithm routes after final hunt selection instead of making `hunt_class` a duplicate visible selector.
  - `EB1007` is called out as draw-only youth elk, while `EB1011` is called out as availability/OTC-style youth general elk.
  - Sportsman and Expo rows are documented as random-only families that do not use bonus or preference points.
  - Total-only CWMU/private/overlay rows are protected from invented resident/nonresident splits.
- Validation:
  - Markdown files were read back successfully.
  - `git diff --check` passed.

## 2024 PDF To 2025 PDF Hunt-Code Crosswalk
- Timestamp (UTC): 2026-05-26T23:50:00Z
- Scope:
  - Built a read-only crosswalk from 2024 PDF draw evidence for model year 2025 to available 2025 PDF draw evidence for model year 2026 and the current active `DATABASE.csv` universe.
  - Compared all `874` source rows from `draw_odds_2024_model_target_2025_permit_totals.csv`.
  - Used the currently extracted next-year PDF evidence from `2025 LE Deer Draw Results.pdf` and `2025 O.I.L. Draw Results.pdf` (`296` combined rows).
  - Separated same-code carry-forward rows, replacement candidates, next-year PDF same-code/current-database-status review rows, and likely dropped rows.
  - Kept the output read-only: no `DATABASE.csv` values, website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Outputs:
  - `scripts/build-2024-to-2025-pdf-hunt-code-crosswalk.py`
  - `data_truth/crosswalk_truth/validation/hunt_code_crosswalk_2024_pdf_to_2025_pdf_model_years.csv`
  - `data_truth/crosswalk_truth/validation/hunt_code_crosswalk_2024_pdf_to_2025_pdf_dropped_review.csv`
  - `data_truth/crosswalk_truth/validation/hunt_code_crosswalk_2024_pdf_to_2025_pdf_model_years_summary.json`
  - `processed_data/hunt_code_crosswalk_2024_pdf_to_2025_pdf_model_years.md`
  - `tests/utah/test_hunt_code_crosswalk_2024_pdf_to_2025_pdf.py`
- Key results:
  - Crosswalk rows: `874`.
  - Current active database rows used for active-code comparison: `1394`.
  - Same code in 2025 PDF and current active database: `257`.
  - Same code current active but no next-year PDF match/source family: `564`.
  - Replacement candidates: `24`.
  - Same code exists in 2025 PDF but database row is currently marked historical-only: `16`.
  - Likely dropped/no current active match rows: `13`.
  - Dropped/review rows total: `29`.
  - Guardrail: output is review evidence and does not modify `DATABASE.csv`.
- Validation:
  - `python scripts\build-2024-to-2025-pdf-hunt-code-crosswalk.py` passed.
  - `python -m py_compile scripts\build-2024-to-2025-pdf-hunt-code-crosswalk.py` passed.
  - `python -m pytest tests\utah\test_hunt_code_crosswalk_2024_pdf_to_2025_pdf.py tests\utah\test_2024_draw_odds_database_2025_permit_audit.py tests\utah\test_final_permit_database_crosscheck_2026.py -q` passed: `8`.

## Remaining Source-Only 2024 Draw PDF Rows Promoted As 2025 Historical Truth
- Timestamp (UTC): 2026-05-26T23:40:00Z
- Scope:
  - Promoted the remaining `49` source-only 2024 draw PDF rows into canonical `DATABASE.csv` as historical 2025 draw-result rows.
  - Populated only reviewed historical 2025 fields: `permits_2025_*`, `permits_2025_draw_*`, draw page/source lineage, and historical-only notes/status.
  - Left all 2026 live permit and 2026 allotment fields blank for the inserted historical rows.
  - Mapped all inserted rows to reviewed boundary IDs from official hunt-number/boundary evidence and current canonical reference rows.
  - Updated the historical-lineage audit to recognize reviewed PDF promotion source labels as canonical 2025 source lineage.
  - Refreshed the 2024 draw audit, comprehensive live DWR comparison, final permit crosscheck, publish-readiness report, and comprehensive history-integrity audit.
  - No website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Outputs:
  - `scripts/promote-source-only-2024-draw-pdf-values-2025.py`
  - `data_truth/draw_results_truth/validation/source_only_2024_draw_pdf_values_promoted_to_DATABASE_2025.csv`
  - `data_truth/draw_results_truth/validation/source_only_2024_draw_pdf_values_promoted_to_DATABASE_2025_summary.json`
  - `processed_data/source_only_2024_draw_pdf_values_promoted_to_DATABASE_2025.md`
  - refreshed 2024 draw audit, live DWR comparison, final permit crosscheck, historical lineage, publish-readiness, and history-integrity artifacts.
- Key results:
  - Inserted historical 2025 rows: `49`.
  - 2024 draw PDF source-code rows missing from `DATABASE.csv`: `0`, down from `49`.
  - `DATABASE.csv` row count: `1447`.
  - Duplicate hunt codes: `0`.
  - Blank boundary IDs: `0`.
  - Populated `permits_2025_total` rows: `1083`.
  - Populated `permits_2025_draw_total` rows: `680`.
  - Populated `permits_2026_total` rows remain `1120`.
  - 2026 permit/allotment total mismatches remain `0`.
  - Live DWR numeric mismatches remain `0`.
  - Historical lineage blockers: `0`.
  - Comprehensive history-integrity fatal blockers: `0`; open issues dropped to `24`.
  - Publish-ready remains `true`.
- Validation:
  - `python scripts\promote-source-only-2024-draw-pdf-values-2025.py` passed.
  - `python scripts\audit-2024-draw-odds-against-database-2025-permits.py` passed.
  - `python scripts\report-br-rs-2024-draw-permit-differences.py` passed.
  - `python scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python scripts\audit-database-historical-permit-lineage-2026.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python -m py_compile scripts\promote-source-only-2024-draw-pdf-values-2025.py scripts\audit-database-historical-permit-lineage-2026.py scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python -m pytest tests\utah\test_2024_draw_odds_database_2025_permit_audit.py tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_database_historical_permit_lineage_2026.py tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py -q` passed: `18`.

## Source-Only Bear 2024 Draw Rows Promoted As 2025 Historical Truth
- Timestamp (UTC): 2026-05-26T23:25:00Z
- Scope:
  - Promoted the four user-confirmed source-only bear rows from `2024 Bear Draw Results.pdf` into canonical `DATABASE.csv` as historical 2025 draw-result rows.
  - Confirmed these values are for 2025 historical draw truth only; no 2026 permit/allotment values were populated for the inserted rows.
  - Added explicit historical-only notes/status to the inserted rows.
  - Mapped boundary IDs from official black-bear hunt table evidence: `BR7008`, `BR7108`, and `BR7208` to `La Sal` boundary `684`; `BR7019` to `Chalk Creek/East Canyon/Morgan-South Rich` boundary `610`.
  - Refreshed the 2024 draw audit, focused BR/RS difference report, final permit crosscheck, publish-readiness report, and comprehensive history-integrity audit after promotion.
  - No website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Outputs:
  - `scripts/promote-source-only-br-2024-draw-pdf-values-2025.py`
  - `data_truth/draw_results_truth/validation/source_only_br_2024_draw_pdf_values_promoted_to_DATABASE_2025.csv`
  - `data_truth/draw_results_truth/validation/source_only_br_2024_draw_pdf_values_promoted_to_DATABASE_2025_summary.json`
  - `processed_data/source_only_br_2024_draw_pdf_values_promoted_to_DATABASE_2025.md`
  - refreshed 2024 draw audit, BR/RS difference report, final permit crosscheck, publish-readiness, and history-integrity artifacts.
- Key results:
  - Inserted historical 2025 rows: `4`.
  - Inserted codes and permit totals: `BR7008=40/3/43`, `BR7019=5/0/5`, `BR7108=25/2/27`, `BR7208=6/0/6`.
  - Source PDF SHA256: `518b6b257c35e326c1d8a9900067ebde2569c0f8231c29b5c1b502a1dd10447b`.
  - Active database row count increased from `1394` to `1398`.
  - Final populated `permits_2025_total` rows increased from `1030` to `1034`.
  - Final populated `permits_2025_draw_total` rows increased from `627` to `631`.
  - BR/RS focused difference report now has `0` rows.
  - Final 2026 permit/allotment total mismatches remain `0`; publish-ready remains `true`.
- Validation:
  - `python scripts\promote-source-only-br-2024-draw-pdf-values-2025.py` passed.
  - `python scripts\audit-2024-draw-odds-against-database-2025-permits.py` passed.
  - `python scripts\report-br-rs-2024-draw-permit-differences.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m py_compile scripts\promote-source-only-br-2024-draw-pdf-values-2025.py scripts\promote-br-rs-2024-draw-pdf-values-2025.py scripts\report-br-rs-2024-draw-permit-differences.py scripts\audit-2024-draw-odds-against-database-2025-permits.py` passed.
  - `python -m pytest tests\utah\test_br_rs_2024_draw_permit_differences.py tests\utah\test_2024_draw_odds_database_2025_permit_audit.py tests\utah\test_final_permit_database_crosscheck_2026.py -q` passed: `9`.

## BR/RS 2024 Draw PDF Values Promoted To 2025 Draw Results
- Timestamp (UTC): 2026-05-26T23:10:00Z
- Scope:
  - Treated the 2024 draw PDF values as authoritative for active BR/RS model-target-2025 draw-result permit numbers.
  - Promoted PDF-derived values into both broad `permits_2025_*` fields and `permits_2025_draw_*` fields for active BR/RS rows where numeric differences existed.
  - Skipped source-only rows that do not exist in the current active database; those remain review evidence only.
  - Refreshed the 2024 draw audit, focused BR/RS difference report, final permit crosscheck, publish-readiness report, and comprehensive history-integrity audit after promotion.
  - No 2026 permit/allotment values, website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Outputs:
  - `scripts/promote-br-rs-2024-draw-pdf-values-2025.py`
  - `data_truth/draw_results_truth/validation/br_rs_2024_draw_pdf_values_promoted_to_DATABASE_2025.csv`
  - `data_truth/draw_results_truth/validation/br_rs_2024_draw_pdf_values_promoted_to_DATABASE_2025_summary.json`
  - `processed_data/br_rs_2024_draw_pdf_values_promoted_to_DATABASE_2025.md`
  - refreshed `data_truth/draw_results_truth/validation/draw_odds_2024_model_target_2025_vs_DATABASE_2025_permits_summary.json`
  - refreshed `data_truth/draw_results_truth/validation/br_rs_2024_model_target_2025_permit_differences_summary.json`
  - refreshed final permit crosscheck, publish-readiness, and history-integrity artifacts.
- Key results:
  - Promoted active rows: `63`.
  - Prefix counts promoted: `55` BR and `8` RS.
  - Changed cells: `572`.
  - Skipped current-absent source codes: `BR7008`, `BR7019`, `BR7108`, `BR7208`.
  - Active BR/RS numeric differences remaining after refresh: `0`.
  - Focused BR/RS difference report now contains only the four current-absent BR review rows.
  - Final populated `permits_2025_draw_total` rows increased from `572` to `627`.
  - Final populated `permits_2025_total` rows remain `1030`.
  - Final 2026 permit/allotment total mismatches remain `0`; publish-ready remains `true`.
- Validation:
  - `python scripts\promote-br-rs-2024-draw-pdf-values-2025.py` passed.
  - `python scripts\audit-2024-draw-odds-against-database-2025-permits.py` passed.
  - `python scripts\report-br-rs-2024-draw-permit-differences.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m py_compile scripts\promote-br-rs-2024-draw-pdf-values-2025.py scripts\report-br-rs-2024-draw-permit-differences.py scripts\audit-2024-draw-odds-against-database-2025-permits.py` passed.
  - `python -m pytest tests\utah\test_br_rs_2024_draw_permit_differences.py tests\utah\test_2024_draw_odds_database_2025_permit_audit.py tests\utah\test_final_permit_database_crosscheck_2026.py -q` passed: `9`.

## Bear And Rocky Mountain Sheep 2024 Draw Difference Audit
- Timestamp (UTC): 2026-05-26T22:45:00Z
- Scope:
  - Imported the missing 2024 Rocky Mountain bighorn sheep harvest-by-unit PDF from the `HUNTS` raw library into the active `HUNT-BUILDER` raw library.
  - Registered the imported harvest PDF as source inventory evidence only; no harvest values were parsed in this step.
  - Generated a focused BR/RS permit-number difference report from the 2024 draw-odds model-target-2025 audit against canonical `DATABASE.csv`.
  - Kept the report read-only. No populated `DATABASE.csv` permit fields were changed or overwritten.
  - No website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Outputs:
  - `pipeline/RAW/hunt_unit_database/2025/pdf/harvest_report/rocky mountain sheep/r.m. sheep 2024 harvest by unit.pdf`
  - `scripts/report-br-rs-2024-draw-permit-differences.py`
  - `data_truth/harvest_results_truth/raw_inventory/imported_rm_sheep_2024_harvest_source.csv`
  - `data_truth/harvest_results_truth/raw_inventory/imported_rm_sheep_2024_harvest_source_summary.json`
  - `data_truth/draw_results_truth/validation/br_rs_2024_model_target_2025_permit_differences.csv`
  - `data_truth/draw_results_truth/validation/br_rs_2024_model_target_2025_permit_differences_summary.json`
  - `processed_data/br_rs_2024_model_target_2025_permit_differences.md`
  - `tests/utah/test_br_rs_2024_draw_permit_differences.py`
- Key results:
  - Imported RM sheep harvest PDF SHA256: `ed380919970757e585d867146e3e44c5ec720a03dcce291157c3dcc11c11b4a7`.
  - BR/RS differing-or-missing rows: `67`.
  - Numeric permit differences: `63` total, with `55` BR rows and `8` RS rows.
  - Source-code-not-in-current-database rows: `4`, all BR (`BR7008`, `BR7019`, `BR7108`, `BR7208`).
  - Largest total delta: `BR7004`, source total `8` vs database 2025 total `20`, delta `-12`.
- Validation:
  - `python scripts\report-br-rs-2024-draw-permit-differences.py` passed.
  - `python -m py_compile scripts\report-br-rs-2024-draw-permit-differences.py` passed.
  - `python -m pytest tests\utah\test_br_rs_2024_draw_permit_differences.py -q` passed: `3`.

## 2024 Draw Odds 2025 Permit Audit And Safe Blank Fill
- Timestamp (UTC): 2026-05-26T22:35:00Z
- Scope:
  - Reprocessed the 2024 draw odds PDF package stored under the 2025 draw-odds folder as model-target-year 2025 permit evidence.
  - Fixed the 2024 draw-odds parser so odds-ratio text such as `1 in 2464.0` is not misread as nonresident permit count data.
  - Built a comprehensive 2024 draw-results package and audited it against canonical `DATABASE.csv` 2025 permit fields.
  - Treated the 2024 draw-odds package as reference evidence, not a bulk overwrite source, because many populated `permits_2025` values already carry reviewed historical lineage and differ from the draw-odds package.
  - Promoted only blank broad 2025 permit cells where the audit identified safe review candidates.
  - No populated 2025 historical permit values were overwritten.
  - `permits_2025_draw_total` remains the narrower bonus-point draw subset and was not expanded into the full 2025 permit universe.
  - No website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Outputs:
  - `scripts/audit-2024-draw-odds-against-database-2025-permits.py`
  - `scripts/promote-2024-draw-odds-blank-2025-permits.py`
  - `data_truth/draw_results_truth/normalized/draw_odds_2024_model_target_2025_permit_totals.csv`
  - `data_truth/draw_results_truth/validation/draw_odds_2024_model_target_2025_vs_DATABASE_2025_permits.csv`
  - `data_truth/draw_results_truth/validation/draw_odds_2024_model_target_2025_vs_DATABASE_2025_permits_summary.json`
  - `data_truth/draw_results_truth/validation/draw_odds_2024_blank_2025_permits_promoted.csv`
  - `data_truth/draw_results_truth/validation/draw_odds_2024_blank_2025_permits_promoted_summary.json`
  - `processed_data/draw_odds_2024_model_target_2025_vs_DATABASE_2025_permits.md`
  - `processed_data/draw_odds_2024_blank_2025_permits_promoted.md`
  - refreshed final permit crosscheck, publish-readiness, and history-integrity artifacts.
- Key results:
  - Comprehensive 2024 source rows/codes: `874`.
  - Source prefix counts included `EB=209`, `DB=187`, `EA=158`, `BR=96`, `PB=85`, plus OIL and smaller categories.
  - Source codes missing from active 2026-era `DATABASE.csv`: `53`, consistent with retired/history-only rows.
  - Broad `permits_2025` comparison: `308` matches, `511` differs, `2` blank, `53` source-code-not-in-database.
  - Narrow `permits_2025_draw` comparison: `259` matches, `285` differs, `277` blank, `53` source-code-not-in-database.
  - Safe blank promotions: `2` rows, `EB3168` and `MB6265`.
  - Final populated `permits_2025_total` rows: `1030`, up from `1028`.
  - Final populated `permits_2025_draw_total` rows: `572`, unchanged by design.
  - Final 2026 permit/allotment total mismatches remain `0`.
- Validation:
  - `python scripts\process_draw_odds_folder_2024.py` passed.
  - `python scripts\extract_2024_antlerless_draw_odds_and_compare.py` passed.
  - `python scripts\build_comprehensive_draw_results_2024.py` passed.
  - `python scripts\audit-2024-draw-odds-against-database-2025-permits.py` passed.
  - `python scripts\promote-2024-draw-odds-blank-2025-permits.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m py_compile scripts\process_draw_odds_folder_2024.py scripts\extract_2024_antlerless_draw_odds_and_compare.py scripts\build_comprehensive_draw_results_2024.py scripts\audit-2024-draw-odds-against-database-2025-permits.py scripts\promote-2024-draw-odds-blank-2025-permits.py` passed.
  - `python -m pytest tests\utah\test_2024_draw_odds_database_2025_permit_audit.py tests\utah\test_2025_draw_permit_field_promotion.py tests\utah\test_final_permit_database_crosscheck_2026.py -q` passed: `18`.

## Correct Live DWR Total-Only Shape After Permit Promotion
- Timestamp (UTC): 2026-05-26T22:13:00Z
- Scope:
  - Corrected the comprehensive live DWR shape rule so rows where DWR publishes only a total (`resident=0`, `nonresident=0`, `total>0`) remain total-only instead of being interpreted as nonresident-only.
  - Kept true resident/nonresident split rows intact; rows with nonzero resident plus total can still derive nonresident as `total - resident` when DWR omits the explicit nonresident value.
  - Re-ran the comprehensive live DWR promotion, live comparison, final crosscheck, publish-readiness report, and comprehensive history audit.
  - Verified that 2025 permit and 2025 draw-permit fields had `0` changed rows and `0` changed cells from the pre-promotion database state.
  - No website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Key results:
  - Live numeric rows represented in current 2026 permit fields: `1068`.
  - Shape counts: `594` true resident/nonresident split rows, `191` live total-only rows, `283` CWMU total-only rows, and `321` DWR no-quota preserved rows.
  - Current `DATABASE.csv` 2026 permit shape: `611` split rows and `510` total-only rows.
  - Split-row math mismatches: `0`.
  - Example correction: `DA1001` is now blank resident / blank nonresident / total `30` with status `LIVE_DWR_TOTAL_ONLY`.
  - Example true split retained: `BR7004` remains `18 / 2 / 20` with status `LIVE_DWR_RES_NR_SPLIT`.
  - Final 2026 permit/allotment total mismatches remain `0`.
- Validation:
  - `python scripts\promote-comprehensive-live-dwr-permit-totals-2026.py` passed.
  - `python scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m py_compile scripts\promote-comprehensive-live-dwr-permit-totals-2026.py scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python -m pytest tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py -q` passed: `11`.

## Comprehensive Live DWR 2026 Permit Totals Promoted Over Allotment
- Timestamp (UTC): 2026-05-26T22:07:00Z
- Scope:
  - Promoted all numeric 2026 Utah DWR Hunt Planner live permit totals from the comprehensive live snapshot into canonical `DATABASE.csv`.
  - Wrote the same live-shaped numbers into the 2026 allotment fields wherever live DWR numeric values exist, so `permit_allotment_2026_*` now mirrors current live permit truth instead of older allotment-derived values.
  - Preserved reviewed database-entered values for DWR no-quota rows, including conservation, expo, statewide, control, and other rows where the live website does not publish a quota.
  - Kept CWMU rows as total-only values, using the DWR-published public permit count as `permits_2026_total` / `permit_allotment_2026_total`.
  - Did not change 2025 permit fields; `permits_2025_draw_total` remains low at `572` and needs a separate historical repair pass.
  - No website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Outputs:
  - `scripts/promote-comprehensive-live-dwr-permit-totals-2026.py`
  - `data_truth/crosswalk_truth/validation/comprehensive_live_dwr_permit_totals_promoted_to_DATABASE_2026.csv`
  - `data_truth/crosswalk_truth/validation/comprehensive_live_dwr_permit_totals_promoted_to_DATABASE_2026_summary.json`
  - `processed_data/comprehensive_live_dwr_permit_totals_promoted_to_DATABASE_2026.md`
  - refreshed comprehensive live DWR comparison, final permit crosscheck, publish-readiness, and history-integrity artifacts.
- Key results:
  - Live DWR rows: `1389`.
  - Live/DATABASE matched rows: `1389`.
  - Numeric live rows promoted over allotment: `1068`.
  - DWR no-quota rows preserved from reviewed database values: `321`.
  - Missing DATABASE rows from live DWR snapshot: `0`.
  - Final populated `permit_allotment_2026_total` rows: `1091`, up from `912`.
  - Final populated `permits_2026_total` rows: `1120`.
  - 2026 permit/allotment total mismatches: `0`.
  - Comprehensive live comparison exact matches: `1068`; split-difference bucket eliminated.
  - Publish readiness remains `true`; comprehensive history fatal blockers remain `0`.
- Validation:
  - `python scripts\promote-comprehensive-live-dwr-permit-totals-2026.py` passed.
  - `python scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python -m py_compile scripts\promote-comprehensive-live-dwr-permit-totals-2026.py scripts\final-permit-database-crosscheck-2026.py scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python -m pytest tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py -q` passed: `11`.

## Comprehensive Live DWR Permit Number Extraction
- Timestamp (UTC): 2026-05-26T21:38:00Z
- Scope:
  - Added a comprehensive DWR Hunt Planner extraction across all reviewed `HuntTableData` species/gender endpoints that currently return rows.
  - Queried 19 live DWR website endpoints and compared results by `hunt_code` to canonical `DATABASE.csv`.
  - Kept the extraction as confirmation evidence only; this step did not modify `DATABASE.csv`.
  - Fixed CWMU shaping so total-only CWMU rows use live `QUOTA_RES` when populated, otherwise live `QUOTA`, preventing zero `QUOTA_RES` from masking a valid total.
- Outputs:
  - `scripts/pull-live-dwr-permit-numbers-comprehensive-2026.py`
  - `data_truth/crosswalk_truth/raw_inventory/live_dwr_hunt_planner_permit_numbers_comprehensive_2026.csv`
  - `data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.csv`
  - `data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026_summary.json`
  - `processed_data/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.md`
- Key results:
  - DWR endpoints queried: `19`.
  - Live DWR rows extracted: `1389`.
  - Live unique hunt codes: `1389`.
  - DATABASE rows compared: `1394`.
  - Exact matches: `682`.
  - Total-confirmed split-difference rows: `378`.
  - DWR no-quota rows with database values preserved: `47`.
  - Blank on both sides: `274`.
  - Live-only rows: `0`.
  - Live numeric / database blank rows: `0`.
  - Database-only rows not exposed by queried endpoints: `5` (`BI6505`, `BI6506`, `BI6529`, `BI6536`, `BI6539`).
  - Numeric mismatch rows needing review: `8` (`BI6528`, `BI6532`, `BR7004`, `EB3010`, `EB3047`, `EB3088`, `EB3112`, `EB3185`).
- Validation:
  - `python scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python scripts\pull-live-dwr-permit-numbers-2026.py` passed.
  - `python -m py_compile scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py scripts\pull-live-dwr-permit-numbers-2026.py scripts\promote-live-dwr-permit-numbers-2026.py` passed.
  - `python -m pytest tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py -q` passed.

## Live DWR Permit Numbers Promoted With No-Quota Preservation
- Timestamp (UTC): 2026-05-26T21:05:00Z
- Scope:
  - Promoted reviewed live Utah DWR Hunt Planner permit numbers for antlerless elk and doe pronghorn into canonical `DATABASE.csv`.
  - Shaped CWMU live rows as `permits_2026_total` only because DWR publishes CWMU public permit counts in the live `QUOTA_RES` field while `QUOTA` is zero.
  - Preserved database-entered values whenever the live DWR endpoint published blank/zero quota rows, including conservation, expo, control, and hard-copy/RAC-sourced values.
  - Verified Expo hard-copy permit totals from `pipeline/RAW/hunt_unit_database/2026/xlsx/expo permits 2026.xlsx` and promoted the three antlerless elk Expo rows as total-only values.
- Outputs:
  - `scripts/promote-live-dwr-permit-numbers-2026.py`
  - `scripts/promote-expo-hard-copy-permits-2026.py`
  - `data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_promoted_to_DATABASE_2026.csv`
  - `data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_promoted_to_DATABASE_2026_summary.json`
  - `data_truth/crosswalk_truth/validation/expo_hard_copy_promoted_to_DATABASE_2026.csv`
  - `data_truth/crosswalk_truth/validation/expo_hard_copy_promoted_to_DATABASE_2026_summary.json`
  - `processed_data/live_dwr_permit_numbers_promoted_to_DATABASE_2026.md`
  - `processed_data/expo_hard_copy_promoted_to_DATABASE_2026.md`
  - `tests/utah/test_live_dwr_and_expo_permit_promotion_2026.py`
- Key results:
  - Live rows reviewed: `227`.
  - Live/DATABASE matches after shaping: `217`.
  - DWR blank/no-quota rows preserved from database: `4`.
  - Blank on both sides: `6`.
  - Numeric mismatches: `0`.
  - CWMU total-only rows shaped from live `QUOTA_RES`: `67`.
  - Expo hard-copy rows promoted: `3` (`EA1220=3`, `EA1258=1`, `EA1221=1`).
  - `EA1286` Monroe preserved as `36/4/40` from entered RAC data despite live DWR publishing no quota in the selected endpoint.
- Validation:
  - `python scripts\promote-expo-hard-copy-permits-2026.py` passed.
  - `python scripts\pull-live-dwr-permit-numbers-2026.py` passed.
  - `python scripts\promote-live-dwr-permit-numbers-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed with `publish_ready=true`.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed with `fatal_blocker_count=0`.
  - `python scripts\audit-current-active-ea-hunts-2026.py` passed with `204` active EA rows reconciled.
  - `python scripts\audit-current-online-hunt-codes-2026.py` passed with `0` database codes missing from live.
  - `python -m pytest tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py tests\utah\test_database_historical_permit_lineage_2026.py tests\utah\test_database_authoritative_permit_overlay_plan_2026.py tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py tests\utah\test_retired_current_hunt_codes_2026.py -q` passed: `15`.

## Live DWR Permit Number Pull
- Timestamp (UTC): 2026-05-26T18:58:00Z
- Scope:
  - Added a repeatable sidecar pull for live Utah DWR Hunt Planner permit numbers from the reviewed `HuntTableData` endpoints.
  - Captured live `QUOTA_RES`, `QUOTA_NRES`, and `QUOTA` fields for antlerless elk and doe pronghorn.
  - Compared live values to canonical `DATABASE.csv` permit/allotment fields without modifying `DATABASE.csv`.
- Outputs:
  - `scripts/pull-live-dwr-permit-numbers-2026.py`
  - `data_truth/crosswalk_truth/raw_inventory/live_dwr_hunt_planner_permit_numbers_2026.csv`
  - `data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_vs_DATABASE_2026.csv`
  - `data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_vs_DATABASE_2026_summary.json`
  - `processed_data/live_dwr_permit_numbers_vs_DATABASE_2026.md`
- Key results:
  - Live rows pulled: `227`.
  - Elk antlerless rows: `204`.
  - Doe pronghorn rows: `23`.
  - Presence comparison: `227` live rows all present in `DATABASE.csv`.
  - Exact numeric matches: `97`.
  - Total-match split-difference rows: `27`.
  - Numeric mismatch rows: `94`.
  - Live numeric / database blank rows: `9`.
- Validation:
  - `python scripts\pull-live-dwr-permit-numbers-2026.py` passed.
  - `python -m py_compile scripts\pull-live-dwr-permit-numbers-2026.py` passed.

## Database Audit Resumed After Sync
- Timestamp (UTC): 2026-05-26T18:44:00Z
- Scope:
  - Resumed canonical database audit after local `main` was synced with `origin/main`.
  - Corrected database audit scripts that still referenced the old `HUNTS` repo path so they now read active `HUNT-BUILDER` `DATABASE.csv`.
  - Updated stale audit/test assumptions from the pre-retirement `1411` active-code universe to the current `1394` active-code universe.
  - Updated publish-readiness sensitive checks so `PD1039` is expected in the retired current-code ledger, not active `DATABASE.csv`, and `EA2012` uses the canonical `400` total.
  - Rebuilt draw and harvest cumulative summaries so embedded active DATABASE coverage now reflects `1394` active hunt codes.
  - Did not modify protected numeric `DATABASE.csv` cells or website feeds.
- Key results:
  - Active DATABASE rows: `1394`.
  - Active DATABASE duplicate hunt codes: `0`.
  - Active DATABASE blank boundary IDs: `0`.
  - Current active EA reconciliation: `204` live/current rows and `204` DATABASE rows.
  - Current online missing DATABASE rows: `0`.
  - Historical 2025 permit lineage blockers: `0`.
  - Comprehensive audit fatal blockers: `0`.
  - Database publish-ready status: `true`, with retained Henry Mtns control-unit warning only.
- Validation:
  - `python scripts\audit-database-historical-permit-lineage-2026.py` passed.
  - `python scripts\build-database-authoritative-permit-overlay-plan-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\fill-database-boundary-ids-from-json-2026.py` passed.
  - `python scripts\audit-current-active-ea-hunts-2026.py` passed.
  - `python scripts\audit-current-online-hunt-codes-2026.py` passed.
  - `python scripts\build-all-years-harvest-database.py` passed.
  - `python scripts\finalize-draw-results-cumulative-database.py` passed.
  - `python scripts\audit-harvest-results-database-final.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m py_compile ...` passed for the modified audit scripts and tests.
  - Focused database-audit pytest bundle passed: `59`.

## Merge Conflict Resolution For Diverged Main
- Timestamp (UTC): 2026-05-26T18:35:00Z
- Scope:
  - Resolved the in-progress merge conflicts between local `main` and `origin/main`.
  - Kept the newer validated generated truth artifacts where both sides only differed by generation timestamp.
  - Preserved both local and remote-only `WORK_LOG.md` sections so audit/history context was not lost.
  - Did not overwrite protected numeric `DATABASE.csv` cells as part of conflict resolution.
- Validation:
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed with `0` fatal blockers and `0` protected permit-overlay numeric mismatches.
  - `python scripts\validate-ea-private-lands-canonical-2026.py` passed with `0` blockers and `0` DATABASE mismatches.
  - `python scripts\lock-black-bear-conservation-br7307-2026.py` passed with `BR7307` selected total `4` and `0` validation errors.
  - Split focused pytest validation passed: `31` tests total.

## HUNT-BUILDER-CLEAN Missing Artifact Import
- Timestamp (UTC): 2026-05-26T18:03:00Z
- Scope:
  - Imported files that existed in `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER-CLEAN` but did not exist at the same paths in active `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER`.
  - Used a missing-path-only/no-overwrite policy so active `DATABASE.csv`, canonical runtime files, and same-path active data were not replaced by CLEAN versions.
  - Wrote a hash manifest for the CLEAN-only import and a separate dependency manifest for the user-supplied EA private-lands raw source needed by the imported validation package.
  - Confirmed `BR7307` is an active 2026 black bear conservation hunt, not merely an example row, and retained it as total-only conservation source truth.
- Outputs:
  - `processed_data/audits/hunt_builder_clean_only_file_import_2026_05_26.csv`
  - `processed_data/audits/hunt_builder_clean_import_dependency_manifest_2026_05_26.csv`
  - `data_truth/permit_overlay_truth/normalized/black_bear_conservation_BR7307_lock_2026.csv`
  - `data_truth/permit_overlay_truth/normalized/elk_antlerless_private_lands_EA_2026_canonical.csv`
  - `data_truth/permit_overlay_truth/normalized/elk_private_lands_EL_LO_2026_source_audit.csv`
  - `processed_data/hard_data_exports/library/`
  - `processed_data/library/`
  - `processed_data/production/`
  - `public/hard-copy/`
- Validation:
  - Hash verification passed for all `65` CLEAN-only copied files.
  - `python -m py_compile scripts\audit-elk-private-lands-el-lo-2026.py scripts\lock-black-bear-conservation-br7307-2026.py scripts\promote-ea-private-lands-canonical-2026.py scripts\validate-ea-private-lands-canonical-2026.py` passed.
  - `python scripts\validate-ea-private-lands-canonical-2026.py` passed with `0` blockers and `0` DATABASE mismatches.
  - `python -m pytest tests\utah\test_ea_private_lands_canonical_2026.py tests\utah\test_ea_private_lands_canonical_promotion_2026.py -q` passed.
  - `python scripts\lock-black-bear-conservation-br7307-2026.py` passed with `BR7307` selected total `4`, total-only status, and `0` validation errors.
- Guardrail:
  - No existing same-path active files were overwritten during the import copy.
  - `DATABASE.csv` was not overwritten by CLEAN and remains the canonical active truth source.

## HUNT-BUILDER Active Repo Correction And HUNTS Change Transfer
- Timestamp (UTC): 2026-05-26T17:37:01Z
- Scope:
  - Corrected the local repo instruction file so Codex operates from `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER` as the active repository.
  - Copied the recent truth-source, crosswalk, permit-overlay, draw-results, harvest-integrity, and comprehensive audit artifacts that were mistakenly built in `C:\Users\tyler\Desktop\GitHub\HUNTS` into this active repository.
  - Merged the missing HUNTS work-log sections into this active repo without overwriting HUNT-BUILDER's existing website, library, and research-library history.
  - Preserved guardrails: no website feed promotion was performed as part of the transfer, and protected numeric DATABASE cells were copied only as the current HUNTS truth-state requested by the user.
- Validation plan:
  - Run the transferred comprehensive integrity audit.
  - Run the focused transferred pytest bundle for retirement, boundary IDs, crosswalk, black bear, LE deer, O.I.L., and comprehensive audit integrity.
  - Commit the HUNT-BUILDER transfer when validation is complete.
- Validation completed:
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed in `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER`.
  - `python -m py_compile scripts\audit-comprehensive-2026-2025-history-integrity.py tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py` passed.
  - `python -m pytest tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py tests\utah\test_retired_current_hunt_codes_2026.py tests\utah\test_database_boundary_id_fill_2026.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py tests\utah\test_black_bear_br_crosscompare_2024_2025_2026.py tests\utah\test_le_deer_2025_draw_results_extraction.py tests\utah\test_oil_2025_draw_results_extraction.py -q` passed: `22`.

## Comprehensive 2026/2025 History Integrity Audit
- Timestamp (UTC): 2026-05-26T17:26:29Z
- Scope:
  - Built a consolidated audit over active 2026 `DATABASE.csv`, retired current-code ledger, live/current DWR snapshot summaries, active EA reconciliation, current-to-historical crosswalk summary, 2026 permit-overlay validation files, 2025 draw-results validation files, and 2025 harvest-results truth rows.
  - Did not modify protected numeric `DATABASE.csv` cells, website feeds, generated pages, or materializer outputs.
  - Wrote a dashboard and open-issue queue that separates fatal blockers from historical-review warnings.
- Outputs:
  - `scripts/audit-comprehensive-2026-2025-history-integrity.py`
  - `tests/utah/test_comprehensive_2026_2025_history_integrity_audit.py`
  - `data_truth/comparison_outputs/validation/comprehensive_2026_2025_history_integrity_audit.csv`
  - `data_truth/comparison_outputs/validation/comprehensive_2026_2025_history_integrity_open_issues.csv`
  - `data_truth/comparison_outputs/validation/comprehensive_2026_2025_history_integrity_summary.json`
  - `processed_data/comprehensive_2026_2025_history_integrity_audit.md`
- Key results:
  - Active `DATABASE.csv` rows: `1394`.
  - Unique active hunt codes: `1394`.
  - Duplicate active hunt codes: `0`.
  - Blank active boundary IDs: `0`.
  - Retired current-code ledger rows: `17`.
  - Retired codes still active in `DATABASE.csv`: `0`.
  - Permit-overlay numeric mismatches against protected `DATABASE.csv` cells: `0`.
  - Fatal blockers: `0`.
  - Review-warning classes: `3`.
  - Open review issue rows: `47`.
  - Open issue breakdown: `6` 2025 LE deer draw source rows missing from active 2026 DATABASE, `12` 2025 O.I.L. draw source rows missing from active 2026 DATABASE, and `29` 2025 harvest source codes not present in active 2026 DATABASE.
- Validation:
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m py_compile scripts\audit-comprehensive-2026-2025-history-integrity.py tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py` passed.
  - `python -m pytest tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py -q` passed: `3`.
  - `python -m pytest tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py tests\utah\test_retired_current_hunt_codes_2026.py tests\utah\test_database_boundary_id_fill_2026.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py tests\utah\test_black_bear_br_crosscompare_2024_2025_2026.py tests\utah\test_le_deer_2025_draw_results_extraction.py tests\utah\test_oil_2025_draw_results_extraction.py -q` passed: `22`.

## Archive Defunct EA1287-EA1300 Effective 2026
- Timestamp (UTC): 2026-05-26T17:12:46Z
- Scope:
  - Archived `EA1287` through `EA1300` from active 2026 `DATABASE.csv` after user rechecked and confirmed those codes no longer exist online effective 2026.
  - Preserved all `14` newly archived rows in the retired current-code ledger alongside the previously retired `EA1007`, `EA1053`, and `PD1039`.
  - Reran boundary, live-online, and active-EA reconciliation audits after the archive.
  - Did not modify website feeds, generated pages, materializer files, or historical draw/harvest rows.
- Outputs:
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
  - `data_truth/crosswalk_truth/normalized/retired_current_hunt_codes_2026.csv`
  - `data_truth/crosswalk_truth/validation/retired_current_hunt_codes_2026_summary.json`
  - `processed_data/retired_current_hunt_codes_2026.md`
  - `data_truth/crosswalk_truth/validation/current_online_missing_hunt_codes_2026_review.csv`
  - `data_truth/crosswalk_truth/validation/current_online_missing_hunt_codes_2026_review_summary.json`
  - `data_truth/crosswalk_truth/validation/current_active_ea_hunts_2026_reconciliation.csv`
  - `data_truth/crosswalk_truth/validation/current_active_ea_hunts_2026_reconciliation_summary.json`
  - `data_truth/crosswalk_truth/validation/database_boundary_id_fill_2026_audit.csv`
  - `data_truth/crosswalk_truth/validation/database_boundary_id_fill_2026_summary.json`
- Key results:
  - DATABASE rows before this archive: `1408`.
  - DATABASE rows after this archive: `1394`.
  - Newly archived rows: `14`.
  - Total retired current-code ledger rows: `17`.
  - DATABASE duplicate hunt codes: `0`.
  - DATABASE blank boundary IDs: `0`.
  - Live-online missing DATABASE rows: `0`.
  - Active `EA` reconciliation: `204` live active `EA` rows, `204` DATABASE `EA` rows, `0` missing, `0` extras.
- Validation:
  - `python scripts\retire-current-hunt-codes-2026.py` passed.
  - `python scripts\fill-database-boundary-ids-from-json-2026.py` passed.
  - `python scripts\audit-current-online-hunt-codes-2026.py` passed.
  - `python scripts\audit-current-active-ea-hunts-2026.py` passed.
  - `python -m py_compile scripts\retire-current-hunt-codes-2026.py scripts\audit-current-online-hunt-codes-2026.py scripts\audit-current-active-ea-hunts-2026.py scripts\fill-database-boundary-ids-from-json-2026.py tests\utah\test_retired_current_hunt_codes_2026.py tests\utah\test_database_boundary_id_fill_2026.py` passed.
  - `python -m pytest tests\utah\test_retired_current_hunt_codes_2026.py tests\utah\test_database_boundary_id_fill_2026.py -q` passed: `4`.
  - Targeted inline validation confirmed `DATABASE.csv` has `1394` rows, none of the `17` retired codes remain active, the retired ledger has exactly those `17` codes, and live-online/active-EA audit blockers are `0`.

## Current Active EA Hunts Reconciliation
- Timestamp (UTC): 2026-05-26T17:09:52Z
- Scope:
  - Reconciled canonical `DATABASE.csv` `EA` rows against the current active Utah DWR Hunt Planner antlerless elk `EA` list provided by the user and available through the live Hunt Planner table endpoint.
  - Did not delete or modify any additional active `EA` rows after user clarified the remaining active `EA` list should be protected.
  - Wrote a reviewed audit identifying active coverage and extra DATABASE rows that require separate review as possible RAC-only, future-season, or code-remap rows.
  - Preserved prior retirement state: only `EA1007`, `EA1053`, and `PD1039` remain retired from active 2026 DATABASE.
- Outputs:
  - `scripts/audit-current-active-ea-hunts-2026.py`
  - `data_truth/crosswalk_truth/validation/current_active_ea_hunts_2026_reconciliation.csv`
  - `data_truth/crosswalk_truth/validation/current_active_ea_hunts_2026_reconciliation_summary.json`
  - `processed_data/current_active_ea_hunts_2026_reconciliation.md`
- Key results:
  - Live/current active `EA` count: `204`.
  - DATABASE active `EA` count: `218`.
  - Active `EA` codes missing from DATABASE: `0`.
  - DATABASE extra `EA` rows not in current active list: `14`.
  - Extra rows are `EA1287`, `EA1288`, `EA1289`, `EA1290`, `EA1291`, `EA1292`, `EA1293`, `EA1294`, `EA1295`, `EA1296`, `EA1297`, `EA1298`, `EA1299`, and `EA1300`.
- Validation:
  - `python scripts\audit-current-active-ea-hunts-2026.py` passed.
  - `python -m py_compile scripts\audit-current-active-ea-hunts-2026.py` passed.

## Retire Invalid 2026 Current Hunt Codes
- Timestamp (UTC): 2026-05-26T17:01:51Z
- Scope:
  - Retired `EA1007`, `EA1053`, and `PD1039` from canonical 2026 `DATABASE.csv` after user confirmed those hunt codes and their 2026 data cease to exist online effective 2026.
  - Preserved the removed rows in a reviewed retirement ledger before deleting them from the current DATABASE universe.
  - Reran the boundary-ID fill audit after retirement; reviewed target count dropped from `17` to `14`, with `0` blockers, `0` blank boundary IDs, and `0` duplicate hunt codes.
  - Reran the live DWR Hunt Planner online-missing audit after retirement; the user-reported codes no longer appear in current DATABASE and are listed as retired from DATABASE.
  - Removed the superseded pre-retirement online-missing audit files so current validation artifacts no longer list `EA1007`, `EA1053`, or `PD1039` as current DATABASE rows.
  - Did not modify website feeds, generated pages, materializer files, or historical draw/harvest rows.
- Outputs:
  - `scripts/retire-current-hunt-codes-2026.py`
  - `tests/utah/test_retired_current_hunt_codes_2026.py`
  - `data_truth/crosswalk_truth/normalized/retired_current_hunt_codes_2026.csv`
  - `data_truth/crosswalk_truth/validation/retired_current_hunt_codes_2026_summary.json`
  - `processed_data/retired_current_hunt_codes_2026.md`
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
  - `data_truth/crosswalk_truth/validation/current_online_missing_hunt_codes_2026_review.csv`
  - `data_truth/crosswalk_truth/validation/current_online_missing_hunt_codes_2026_review_summary.json`
  - `data_truth/crosswalk_truth/validation/database_boundary_id_fill_2026_audit.csv`
  - `data_truth/crosswalk_truth/validation/database_boundary_id_fill_2026_summary.json`
- Key results:
  - DATABASE rows before retirement: `1411`.
  - DATABASE rows after retirement: `1408`.
  - Retired current codes: `EA1007`, `EA1053`, `PD1039`.
  - Retired rows preserved: `3`.
  - Remaining DATABASE duplicate hunt codes: `0`.
  - Remaining DATABASE blank boundary IDs: `0`.
  - Live-online missing DATABASE rows after retirement: `14`, all `EA` rows; no user-reported retired code remains in DATABASE.
- Validation:
  - `python scripts\retire-current-hunt-codes-2026.py` passed.
  - `python scripts\fill-database-boundary-ids-from-json-2026.py` passed.
  - `python scripts\audit-current-online-hunt-codes-2026.py` passed.
  - `python -m py_compile scripts\retire-current-hunt-codes-2026.py scripts\audit-current-online-hunt-codes-2026.py scripts\fill-database-boundary-ids-from-json-2026.py tests\utah\test_retired_current_hunt_codes_2026.py tests\utah\test_database_boundary_id_fill_2026.py` passed.
  - `python -m pytest tests\utah\test_retired_current_hunt_codes_2026.py tests\utah\test_database_boundary_id_fill_2026.py -q` passed: `4`.
  - Targeted inline validation confirmed `DATABASE.csv` has `1408` rows, no `EA1007`/`EA1053`/`PD1039` rows, `0` duplicates, and `0` blank boundary IDs.
  - Broader `tests\utah\test_current_year_permit_allotments.py` was checked and still has unrelated pre-existing runtime failures: `hunt_master_enriched.csv` is a Git LFS pointer and `EA2012` runtime expectations differ from current source values.

## Current Online Missing Hunt Code Audit 2026
- Timestamp (UTC): 2026-05-26T16:46:26Z
- Scope:
  - Audited canonical `DATABASE.csv` hunt codes against the live Utah DWR Hunt Planner `HaSetup` hunt-number list.
  - Confirmed user-reported codes `EA1007`, `EA1053`, and `PD1039` are not present in the live online Hunt Planner hunt-number list at audit time.
  - Identified `17` canonical DATABASE rows not present in the live online hunt-number list: `16` antlerless elk `EA` rows and `1` doe pronghorn `PD` row.
  - Preserved protected numeric DATABASE cells; this audit is sidecar quarantine evidence only and does not delete or overwrite RAC/current-year allotment values.
  - Marked missing-online rows with recommendation `QUARANTINE_CURRENT_ONLINE_MAPPING; do not promote as live-online-current without a new DWR export`.
- Outputs:
  - `scripts/audit-current-online-hunt-codes-2026.py`
  - `data_truth/crosswalk_truth/raw_inventory/live_dwr_hunt_planner_hunt_codes_snapshot_2026.csv`
  - `data_truth/crosswalk_truth/validation/current_online_missing_hunt_codes_2026.csv`
  - `data_truth/crosswalk_truth/validation/current_online_missing_hunt_codes_2026_summary.json`
  - `processed_data/current_online_missing_hunt_codes_2026.md`
- Key results:
  - Live DWR Hunt Planner hunt-number count: `1422`.
  - DATABASE hunt-code row count: `1411`.
  - DATABASE codes missing from live online list: `17`.
  - User-reported missing codes confirmed absent: `EA1007`, `EA1053`, `PD1039`.
  - Same-name live candidates found: `EA1053 -> EA1054` for `Nine Mile, West Anthro` on the current live table, and `EA1007 -> EA2013` for `Wasatch Mtns, Currant Creek` private-lands-only; no same-name live candidate found for `PD1039`.
- Validation:
  - `python scripts\audit-current-online-hunt-codes-2026.py` passed.
  - `python -m py_compile scripts\audit-current-online-hunt-codes-2026.py` passed.
  - Inline validation confirmed `17` audit rows and high-priority absent status for `EA1007`, `EA1053`, and `PD1039`.

## Current Online Missing Hunt Code Audit Review 2026
- Timestamp (UTC): 2026-05-26T16:57:06Z
- Scope:
  - Refined the live-online audit after user clarification that `EA1007`, `EA1053`, and `PD1039` are hunt codes that no longer exist online.
  - Added a selected live DWR Hunt Planner table snapshot for the current online `Elk|Antlerless` and `Pronghorn|Doe` rows.
  - Added explicit audit fields distinguishing the issue as `HUNT_CODE_MISSING_ONLINE_BOUNDARY_ID_PRESENT`.
  - Confirmed this is not a boundary-ID gap: all `17` missing-online rows have populated DATABASE boundary IDs.
  - Preserved protected `DATABASE.csv` numeric cells and did not modify website-facing outputs.
- Outputs:
  - `data_truth/crosswalk_truth/raw_inventory/live_dwr_hunt_planner_selected_tables_snapshot_2026.csv`
  - `data_truth/crosswalk_truth/validation/current_online_missing_hunt_codes_2026_review.csv`
  - `data_truth/crosswalk_truth/validation/current_online_missing_hunt_codes_2026_review_summary.json`
  - `processed_data/current_online_missing_hunt_codes_2026_review.md`
- Key results:
  - Live selected table rows: `227` (`204` `Elk|Antlerless`, `23` `Pronghorn|Doe`).
  - User-reported codes confirmed absent from live online hunt-code list: `EA1007`, `EA1053`, `PD1039`.
  - Live same-name candidates: `EA1053 -> EA1054` for `Nine Mile, West Anthro`; `EA1007 -> EA2013` for `Wasatch Mtns, Currant Creek` private-lands-only; no live same-name candidate for `PD1039`.
- Validation:
  - `python scripts\audit-current-online-hunt-codes-2026.py` passed.
  - `python -m py_compile scripts\audit-current-online-hunt-codes-2026.py` passed.

## 2026 DATABASE Boundary ID Fill From JSON/GeoJSON
- Timestamp (UTC): 2026-05-26T16:36:35Z
- Scope:
  - Filled the `17` remaining blank `boundary_id` cells in canonical `DATABASE.csv` using reviewed JSON/GeoJSON evidence.
  - Used direct official hunt-table JSON matches only when `HUNT_NUMBER` and boundary name agreed with the current DATABASE row.
  - Used exact official boundary-name matches from `data/elk_antlerless_hunt_table_official.json` and `data/pronghorn_hunt_table_official.json` where current RAC split codes did not appear as direct `HUNT_NUMBER` rows.
  - Used exact unique DWR boundary-layer name matches from `data/hunt_boundaries.geojson` for new current RAC split units not present by code in the official hunt-table JSON.
  - Caught and corrected a code-reuse trap: current `EA1007` is `Wasatch Mtns, Currant Creek`, so it maps by current boundary name to `227`; the stale direct `EA1007` JSON row for `Box Elder, Grouse Creek` was not promoted.
  - Final DATABASE health check: `1411` rows, `1411` unique hunt codes, `0` duplicate hunt codes, and `0` blank boundary IDs.
- Outputs:
  - `scripts/fill-database-boundary-ids-from-json-2026.py`
  - `tests/utah/test_database_boundary_id_fill_2026.py`
  - `data_truth/crosswalk_truth/validation/database_boundary_id_fill_2026_audit.csv`
  - `data_truth/crosswalk_truth/validation/database_boundary_id_fill_2026_summary.json`
  - `processed_data/database_boundary_id_fill_2026.md`
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Validation:
  - `python scripts\fill-database-boundary-ids-from-json-2026.py` passed.
  - `python -m py_compile scripts\fill-database-boundary-ids-from-json-2026.py tests\utah\test_database_boundary_id_fill_2026.py` passed.
  - `python -m pytest tests\utah\test_database_boundary_id_fill_2026.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py -q` passed: `6`.

## Current Reference-Only Hunt Code Review 2026
- Timestamp (UTC): 2026-05-26T16:26:44Z
- Scope:
  - Resolved the four remaining current-reference-only rows identified for manual review: `CG9999`, `EX1000`, `LO0008`, and `LO0011`.
  - Promoted `CG9999` as the reviewed statewide cougar current reference row with `season=open`, `permits_2026_total=unlimited`, and `permit_allotment_2026_status=UNLIMITED_PERMITS` from the DWR Hunt Planner cougar CSV.
  - Preserved `EX1000`, `LO0008`, and `LO0011` as reviewed no-quota-published reference rows and did not invent numeric resident, nonresident, or total permit counts.
  - Updated the current-to-historical crosswalk builder so reviewed current-reference rows are no longer counted as unresolved manual-review gaps.
  - Rebuilt the current-to-historical crosswalk: `169` rows, `0` missing from `DATABASE.csv`, `0` duplicate current-code rows, and `4` `REVIEWED_CURRENT_REFERENCE` rows.
- Outputs:
  - `scripts/resolve-current-reference-codes-2026.py`
  - `tests/utah/test_current_reference_codes_2026.py`
  - `data_truth/crosswalk_truth/validation/current_reference_codes_2026_review.csv`
  - `data_truth/crosswalk_truth/validation/current_reference_codes_2026_summary.json`
  - `processed_data/current_reference_codes_2026_review.md`
  - `data_truth/crosswalk_truth/normalized/current_to_historical_hunt_code_crosswalk_2026.csv`
  - `data_truth/crosswalk_truth/validation/current_to_historical_hunt_code_crosswalk_2026_summary.json`
  - `processed_data/current_to_historical_hunt_code_crosswalk_2026.csv`
  - `processed_data/current_to_historical_hunt_code_crosswalk_2026.md`
- Validation:
  - `python scripts\resolve-current-reference-codes-2026.py` passed.
  - `python scripts\build-current-historical-hunt-code-crosswalk-2026.py` passed.
  - `python -m py_compile scripts\resolve-current-reference-codes-2026.py scripts\build-current-historical-hunt-code-crosswalk-2026.py tests\utah\test_current_reference_codes_2026.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py` passed.
  - `python -m pytest tests\utah\test_current_reference_codes_2026.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py -q` passed: `6`.

## 2026 EL/LO Private-Lands Elk Source Audit
- Timestamp (UTC): 2026-05-26T14:01:30Z
- Scope:
  - Audited the attached DWR Hunt Planner private-lands bull elk file `2026 l.e. elk.private lands  EL-2025 and LO-2026.csv`.
  - Confirmed the source has `131` rows: `126` `EL` rows and `5` elk `LO` Diamond Mtn Landowner Association rows.
  - Confirmed the attached source publishes `0` permit-number values; therefore no numeric permit values were promoted from this source.
  - Confirmed date context: `125` `EL` rows have 2025-only season dates, `1` `EL` row crosses 2025-2026, and all `5` elk `LO` rows have 2026 dates.
  - Compared against `DATABASE.csv`: `0` missing rows, `128` rows where DATABASE already has protected numeric values not present in the attached source, and `3` rows blank in both source and DATABASE (`LO0012`, `LO0013`, `LO0014`).
  - Checked RAC/private permit evidence: `0` exact `EL`/elk `LO` RAC code matches and `126` `EL -> EB` prefix-swap RAC candidate matches, all marked review evidence only because public `EB` RAC recommendations must not be promoted into private-land `EL/LO` rows without reviewed access-class confirmation.
- Files:
  - `scripts/audit-elk-private-lands-el-lo-2026.py`
  - `tests/utah/test_elk_private_lands_el_lo_audit_2026.py`
  - `data_truth/permit_overlay_truth/normalized/elk_private_lands_EL_LO_2026_source_audit.csv`
  - `data_truth/permit_overlay_truth/validation/elk_private_lands_EL_LO_2026_vs_DATABASE.csv`
  - `data_truth/permit_overlay_truth/validation/elk_private_lands_EL_LO_2026_rac_candidate_matches.csv`
  - `data_truth/permit_overlay_truth/validation/elk_private_lands_EL_LO_2026_summary.json`
  - `processed_data/elk_private_lands_EL_LO_2026_audit.md`
- Validation:
  - `python scripts\audit-elk-private-lands-el-lo-2026.py`
  - `python -m compileall scripts\audit-elk-private-lands-el-lo-2026.py tests\utah\test_elk_private_lands_el_lo_audit_2026.py`
  - `python -m pytest tests\utah\test_elk_private_lands_el_lo_audit_2026.py -q` passed: `3`

## 2026 Black Bear Permit Split Normalization
- Timestamp (UTC): 2026-05-26T13:56:00Z
- Scope:
  - Normalized the DWR Hunt Planner `2026 black bear permits.csv` source where resident and nonresident permit counts were stored in the same physical column with `NonRes:` continuation rows.
  - Collapsed `207` physical source rows into `106` one-row-per-`BR` hunt-code records with explicit `permits_2026_res`, `permits_2026_nr`, and `permits_2026_total` fields.
  - Preserved `BR7307` as the reviewed La Sal black bear conservation lock with `Total=4` and blank resident/nonresident split fields because no split is published for that conservation package.
  - Compared normalized 2026 `BR` rows against canonical `DATABASE.csv`; there were `0` numeric mismatches and `0` missing DATABASE rows after promotion.
  - Promoted reviewed 2026 black bear permit/allotment source lineage into `DATABASE.csv` without changing historical 2025 or older permit fields.
  - Wrote a 2026-to-2025 black bear hunt-code comparison: `12` current 2026 BR codes were not present in the 2025 draw-results BR universe, and `3` 2025 draw-result BR codes were not present in the 2026 source.
- Files:
  - `scripts/normalize-black-bear-permits-2026.py`
  - `tests/utah/test_black_bear_permit_normalization_2026.py`
  - `data_truth/permit_overlay_truth/normalized/black_bear_permits_2026_canonical.csv`
  - `data_truth/permit_overlay_truth/validation/black_bear_permits_2026_vs_DATABASE.csv`
  - `data_truth/permit_overlay_truth/validation/black_bear_2026_vs_2025_code_comparison.csv`
  - `data_truth/permit_overlay_truth/validation/black_bear_permits_2026_summary.json`
  - `processed_data/black_bear_permits_2026_summary.md`
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Validation:
  - `python scripts\normalize-black-bear-permits-2026.py`
  - `python -m compileall scripts\normalize-black-bear-permits-2026.py tests\utah\test_black_bear_permit_normalization_2026.py`
  - `python -m pytest tests\utah\test_black_bear_permit_normalization_2026.py -q` passed: `5`
  - Focused `black_bear_permits_2026_vs_DATABASE.csv` scan returned `0` numeric mismatches and `0` missing DATABASE rows.

## BR7307 Black Bear Conservation Permit Lock 2026
- Timestamp (UTC): 2026-05-26T13:46:57Z
- Scope:
  - Confirmed `BR7307` exists as the current La Sal black bear `Multiseason - Conservation` hunt-code row in the 2026 black bear permit source and `DATABASE.csv`.
  - Locked `BR7307` as a total-only conservation reference with `Total=4`, preserving blank resident/nonresident split fields because no split is published for this conservation package.
  - Recorded the four PDF evidence rows supplied for the 2025-2027 conservation permit table: UHA row `36`, SFW row `37`, MDF row `38`, and SFW row `39`, one tag each.
  - Cross-checked the normalized conservation table, where the two SFW rows are compressed as `permit_count=2`; normalized source total also sums to `4`.
  - Synchronized the active current 2026 DATABASE/runtime/reference surfaces for `BR7307` without changing historical 2025 draw/harvest permit fields.
- Files:
  - `scripts/lock-black-bear-conservation-br7307-2026.py`
  - `tests/utah/test_black_bear_conservation_br7307_lock_2026.py`
  - `data_truth/permit_overlay_truth/normalized/black_bear_conservation_BR7307_lock_2026.csv`
  - `data_truth/permit_overlay_truth/validation/black_bear_conservation_BR7307_lock_2026_audit.csv`
  - `processed_data/black_bear_conservation_BR7307_lock_2026_summary.json`
  - `processed_data/black_bear_conservation_BR7307_lock_2026.md`
  - Current 2026 DATABASE/runtime/reference CSV surfaces carrying `BR7307`.
- Validation:
  - `python scripts\lock-black-bear-conservation-br7307-2026.py`
  - `python -m compileall scripts\lock-black-bear-conservation-br7307-2026.py tests\utah\test_black_bear_conservation_br7307_lock_2026.py`
  - `python -m pytest tests\utah\test_black_bear_conservation_br7307_lock_2026.py -q` passed: `3`
  - Focused `BR7307` stale/blank/zero current-total scan across active surfaces returned `0` bad current total cells.

## EA Private-Lands Canonical Permit Promotion 2026
- Timestamp (UTC): 2026-05-26T13:33:39Z
- Scope:
  - Promoted the reviewed DWR Hunt Planner `EA` antlerless elk private-lands source into current 2026 permit/allotment surfaces.
  - Corrected the five DATABASE mismatches identified by the canonical EA validation: `EA2012` `500 -> 400`, `EA2015` `75 -> 100`, `EA2016` `325 -> 275`, `EA2027` `250 -> 300`, and `EA2046` `50 -> 25`.
  - Preserved historical 2025 and older fields; only current 2026 permit/allotment/quota fields and source traceability fields were synchronized.
  - Re-ran the canonical EA validation; DATABASE now has zero missing rows and zero mismatches against the reviewed source.
- Files:
  - `scripts/promote-ea-private-lands-canonical-2026.py`
  - `tests/utah/test_ea_private_lands_canonical_promotion_2026.py`
  - `tests/utah/test_ea_private_lands_canonical_2026.py`
  - `data_truth/permit_overlay_truth/validation/elk_antlerless_private_lands_EA_2026_promotion_audit.csv`
  - `data_truth/permit_overlay_truth/validation/elk_antlerless_private_lands_EA_2026_promotion_summary.json`
  - `data_truth/permit_overlay_truth/validation/elk_antlerless_private_lands_EA_2026_vs_DATABASE.csv`
  - `data_truth/permit_overlay_truth/validation/elk_antlerless_private_lands_EA_2026_summary.json`
  - `processed_data/elk_antlerless_private_lands_EA_2026_promotion.md`
  - Current 2026 DATABASE/runtime/reference CSV surfaces carrying the affected `EA` rows.
- Validation:
  - `python scripts\promote-ea-private-lands-canonical-2026.py`
  - `python scripts\validate-ea-private-lands-canonical-2026.py`
  - `python -m compileall scripts\promote-ea-private-lands-canonical-2026.py tests\utah\test_ea_private_lands_canonical_promotion_2026.py tests\utah\test_ea_private_lands_canonical_2026.py`
  - `python -m pytest tests\utah\test_ea_private_lands_canonical_2026.py tests\utah\test_ea_private_lands_canonical_promotion_2026.py -q` passed: `6`
  - Focused stale-value scan across active current surfaces returned `0` stale current cells.

## Desert Bighorn Conservation Permit Code Lock 2026
- Timestamp (UTC): 2026-05-25T01:55:00Z
- Scope:
  - Resolved the current `DS` predictive gap by treating the unmapped desert bighorn rows as conservation/statewide permit reference rows.
  - Pulled permit counts from `data_truth/permit_overlay_truth/normalized/conservation_permit_cycle_rows_2022_2027.csv`, using the 2025-2027 conservation permit cycle.
  - Locked `DS1000`, `DS1002`, `DS1003`, `DS1004`, `DS1006`, `DS1007`, and `DS6605` with `Res=1`, `Non Res=0`, and `Total=1`.
  - Added non-modeled predictive-v2 reference rows for `DS1002`, `DS1003`, `DS1004`, `DS1006`, `DS1007`, and `DS6605`; preserved `DS1000` as the existing sportsman/statewide row.
  - Regenerated the current hunt-code family gap scan; `DS` is now resolved and total missing current DATABASE codes dropped from `20` to `14`.
- Files:
  - `scripts/lock-desert-bighorn-conservation-permit-codes-2026.py`
  - `data_truth/permit_overlay_truth/normalized/desert_bighorn_conservation_permit_code_lock_2026.csv`
  - `processed_data/desert_bighorn_conservation_permit_code_lock_2026_summary.json`
  - `processed_data/desert_bighorn_conservation_permit_code_lock_2026.md`
  - `processed_data/desert_bighorn_conservation_permit_code_lock_2026_runtime_updates.csv`
  - `tests/utah/test_desert_bighorn_conservation_code_lock_2026.py`
- Validation:
  - `python scripts\lock-desert-bighorn-conservation-permit-codes-2026.py`
  - `python scripts\scan-2026-hunt-code-family-gaps.py`
  - `python -m compileall scripts\lock-desert-bighorn-conservation-permit-codes-2026.py tests\utah\test_desert_bighorn_conservation_code_lock_2026.py`
  - `python -m pytest tests\utah\test_desert_bighorn_conservation_code_lock_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py tests\utah\test_elk_bull_reference_resolution_2026.py tests\utah\test_elk_private_land_resolution_2026.py tests\utah\test_conservation_permit_code_lock_2026.py -q` passed: `19`
  - `python -m pytest tests\utah_bonus_predictive\test_phase11_sportsman_materialization.py tests\utah_draw_predictive\test_sportsman_permit_classification.py -q` passed: `2`

## Conservation Permit Hunt Code Lock 2026
- Timestamp (UTC): 2026-05-25T01:40:00Z
- Scope:
  - Locked the supplied conservation permit hunt codes into the current 2026 permit/reference surfaces so they do not drift or disappear from downstream coverage.
  - Added a traceable conservation permit code lock table with `Non Res`, `Res`, and `Total` headers.
  - Cleared the stale `EA1180` public/total quota value of `17` and preserved all five antlerless elk conservation codes as source-confirmed `NO_QUOTA_PUBLISHED` reference rows.
  - Pushed `EB3128` and `EB3209` through the reference surfaces as conservation `TOTAL_ONLY` bull elk records with total `1`, without inventing resident/nonresident splits or draw odds.
  - Regenerated the current hunt-code family gap scan after the lock; `EA` and `EB` remain resolved with zero missing predictive-v2 codes.
- Files:
  - `scripts/lock-conservation-permit-hunt-codes-2026.py`
  - `data_truth/permit_overlay_truth/normalized/conservation_permit_hunt_code_lock_2026.csv`
  - `processed_data/conservation_permit_hunt_code_lock_2026_summary.json`
  - `processed_data/conservation_permit_hunt_code_lock_2026.md`
  - `processed_data/conservation_permit_hunt_code_lock_2026_runtime_updates.csv`
  - `tests/utah/test_conservation_permit_code_lock_2026.py`
- Validation:
  - `python scripts\lock-conservation-permit-hunt-codes-2026.py`
  - `python scripts\scan-2026-hunt-code-family-gaps.py`
  - `python -m compileall scripts\lock-conservation-permit-hunt-codes-2026.py tests\utah\test_conservation_permit_code_lock_2026.py`
  - `python -m pytest tests\utah\test_conservation_permit_code_lock_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py tests\utah\test_elk_bull_reference_resolution_2026.py -q` passed: `12`

## Shared Double-Pillow Header Navigation
- Timestamp (UTC): 2026-05-23T17:35:00Z
- Scope:
  - Added a shared primary header navigation bar generated by `header-layout.js`.
  - Matched the Hunt Backpack visual language with a cream outer pillow, dark brown inner pillow, rounded beveled ends, orange lettering, and raised hover expansion for each navigation item.
  - Added `U.O.G.A. HOME` to the primary header flow and renamed `HARD COPIES` presentation to `HUNT LIBRARY`.
  - Reordered builder header controls so Instructions sits before the map selector, matching the requested visual flow.
  - Bumped page header script cache keys so browsers load the updated shared header.
- Files:
  - `header-layout.js`
  - `index.html`
  - `research.html`
  - `verify.html`
  - `hard-copy.html`
  - `tests/utah/test_header_layout.py`
- Validation:
  - `node --check header-layout.js`
  - `python -m pytest tests/utah/test_header_layout.py tests/utah/test_frontend_probability_selection.py -q`

### Header Navigation Refinement
- Timestamp (UTC): 2026-05-23T17:55:00Z
- Scope:
  - Pointed `U.O.G.A. HOME` in the shared header navigation to `https://www.uoga.org`.
  - Gave each navigation page item its own brown rounded inner pillow instead of relying on text-only interaction.
  - Changed the selected/active page item font color to white.
  - Kept hover motion on the entire page pillow so it raises and expands toward the viewer.
- Validation:
  - `node --check header-layout.js`
  - `python -m pytest tests/utah/test_header_layout.py tests/utah/test_frontend_probability_selection.py -q`

### Header Navigation Visual Polish
- Timestamp (UTC): 2026-05-23T18:10:00Z
- Scope:
  - Changed the center navigation tray between page pillows back to a light cream/white inset so the individual brown page pillows stand apart.
  - Reduced page-pillow hover expansion to a subtle lift/scale and made the hover outline orange.
  - Rounded the Hunt Backpack outer shell into the same long oval language as the Google Maps header pillow.
  - Bumped `ui.js` cache keys on the visible pages so the updated backpack shell styling loads immediately.
- Validation:
  - `node --check header-layout.js`
  - `node --check ui.js`
  - `python -m pytest tests/utah/test_header_layout.py tests/utah/test_frontend_probability_selection.py -q`

### Unified Header Navigation Placement
- Timestamp (UTC): 2026-05-23T18:25:00Z
- Scope:
  - Made the shared header navigation use one canonical five-link set on every page.
  - Fixed the desktop navigation into the same centered header slot across Builder, Hunt Research, Outfitters, and Hunt Library.
  - Preserved the same color, size, active-page treatment, page-pillow styling, and mobile wrap behavior across pages.
  - Bumped `header-layout.js` cache keys so all pages load the unified placement rules.
- Validation:
  - `node --check header-layout.js`
  - `node --check ui.js`
  - `python -m pytest tests/utah/test_header_layout.py tests/utah/test_frontend_probability_selection.py -q`

### Hunt Research Header Centering Fix
- Timestamp (UTC): 2026-05-23T18:40:00Z
- Scope:
  - Kept Hunt Research using the fixed centered desktop nav position even when narrower viewport rules are active.
  - Scoped the wrapped nav fallback to headers that actually have left-side controls, so Builder can protect Instructions/Google Maps while Research remains centered.
  - Preserved deep orange hover text, orange border highlight, subtle page-pillow lift, and white selected-page text.
- Validation:
  - `node --check header-layout.js`
  - `node --check ui.js`
  - `python -m pytest tests/utah/test_header_layout.py tests/utah/test_frontend_probability_selection.py -q`

## Hunt Research Point Ladder Guaranteed-Line Highlight
- Timestamp (UTC): 2026-05-23T18:55:00Z
- Scope:
  - Updated the point ladder guaranteed-to-draw line to use `rgb(250, 120, 0)`.
  - Added a dark brown inset box around the guaranteed line using the existing `rgb(55, 34, 22)` outline token.
  - Preserved the hunter-points blue highlight while making the combined hunter/guaranteed row keep the same brown outline.
- Files:
  - `research.html`
  - `tests/utah/test_point_ladder_pool_display.py`
- Validation:
  - `node --check hunt-research.js`
  - `python -m pytest tests/utah/test_point_ladder_pool_display.py tests/utah/test_frontend_probability_selection.py -q`

## Mixed Predictive Draw-Odds Engine 2026
- Timestamp (UTC): 2026-05-23T14:20:00Z
- Scope:
  - Built the additive Utah mixed predictive draw-odds engine under `engine/utah_predictive_mixed/`.
  - Combined prior-year DWR draw behavior, official 2026 RAC/DATABASE quota inputs, applicant rollover / point-bank movement, harvest-quality demand pressure, and calibrated mixed probability.
  - Kept prior-year draw behavior as the highest-weighted signal with default weights:
    - prior-year behavior `0.60`
    - quota change `0.20`
    - applicant rollover `0.15`
    - harvest quality / demand `0.05`
  - Preserved the rule that harvest features are quality/demand signals only and do not overwrite probability or quota/allotment fields.
  - Preserved the rule that Expo, Conservation, Sportsman, CWMU, landowner, mitigation, private, and boundary overlays are not public draw quota.
  - Preserved the rule that MAX POOL status text does not force `100%`.
  - Preserved the rule that 2025 historical random-pool success is not copied into 2026 point-specific odds.
- Scripts/modules:
  - `scripts/build_mixed_predictive_engine_2026.py`
  - `engine/utah_predictive_mixed/__init__.py`
  - `engine/utah_predictive_mixed/models.py`
  - `engine/utah_predictive_mixed/prior_year.py`
  - `engine/utah_predictive_mixed/quota.py`
  - `engine/utah_predictive_mixed/rollover.py`
  - `engine/utah_predictive_mixed/harvest_features.py`
  - `engine/utah_predictive_mixed/mixed_probability.py`
  - `engine/utah_predictive_mixed/backtest.py`
  - `engine/utah_predictive_mixed/materialize.py`
- Outputs:
  - `data_model/runtime_drafts/mixed_predictive_engine_2026.predictions.csv`
  - `data_model/runtime_drafts/mixed_predictive_engine_2026.materialized.csv`
  - `data_model/runtime_drafts/mixed_predictive_engine_2026.audit.csv`
  - `data_model/runtime_drafts/mixed_predictive_engine_2026.summary.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/point_ladder_view.csv`
  - `processed_data/mixed_predictive_engine_2026_summary.json`
  - `processed_data/mixed_predictive_engine_2026_audit.csv`
  - `processed_data/mixed_predictive_engine_2026_audit.md`
- Key results:
  - Prediction rows: `27940`.
  - MODELED_BONUS rows: `25610`.
  - MODELED_PREFERENCE rows: `1605`.
  - MODELED_SPORTSMAN_DRAW rows: `10`.
  - Availability/allocation rows: `178`.
  - Prior-year exact matches: `27940`.
  - Quota-adjusted rows: `16145`.
  - Rollover-adjusted rows: `22719`.
  - Harvest-adjusted rows: `22719`.
  - Rows using fallback harvest features: `120`.
  - Rows with no harvest history: `0`.
  - Duplicate key count: `0`.
  - Probability field guardrail: `PASS`.
  - Quota guardrail: `PASS`.
  - Special permit guardrail: `PASS`.
  - Harvest audit blocker count: `0`.
  - Harvest audit warning count: `15529` and preserved as source-review metadata, not a blocker.
  - Publish ready for mixed predictive engine: `true`.
- Spot checks:
  - `DB1004` reconciles public draw `80` plus Expo `3` to all-class total `83`; Conservation was not used to explain the gap.
  - `EB3024` Resident point `30` is `max_pool_guaranteed`.
  - `EB3024` Resident point `29` is `max_pool_cutoff_mixed` with `p_max_pool_mean = 0.142857`, `p_random_mean = 0.006257`, and `projected_applicants = 21`.
  - `EB3024` Resident point `28` is `random_pool`.
  - `EB3022` uses `quota_source_status = official`, `quota_2026_total = 130`, and source file `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_limited_entry_bull_elk_permits.csv`.
- Docs/tests:
  - Updated `HYBRID_ML_V1.md`, `docs/predictive_engine_design.md`, `docs/data_feed_contract.md`, and `ENGINE_RULES_SPEC.md`.
  - Added focused mixed-engine tests under `tests/utah_predictive_mixed/`.
- Validation:
  - `python scripts/build_mixed_predictive_engine_2026.py` passed.
  - `python -m pytest tests/utah_predictive_mixed -q` passed: `20`.
  - `python -m pytest tests/utah_quality -q` passed: `18`.
  - `python -m pytest tests/utah_bonus_predictive tests/utah_draw_predictive tests/utah/test_frontend_probability_selection.py -q` passed: `168`.
  - `python -m compileall engine scripts tests` passed.
  - `node --check hunt-research.js` passed.
  - `npm.cmd run verify:permits-2026` passed with files audited `11`, rows updated `156`, mismatches after sync `0`, and promotion blockers `0`.

## All RAC 2026 Permit Cumulative Vs DATABASE Comparison
- Timestamp (UTC): 2026-05-23T06:14:00Z
- Scope:
  - Built a fresh cumulative 2026 RAC permit table from normalized `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_*.csv` family files.
  - Excluded metadata, prior comparison outputs, supplemental parsing intermediates, control-unit overlays, and raw PDF permit-row extraction files from the cumulative permit table.
  - Compared the cumulative RAC rows against `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` by `hunt_code`.
  - Kept unit-level general-season deer rows and category-level general bull elk rows in the cumulative output, but marked them as not directly comparable one-to-one where appropriate.
- Files written:
  - `scripts/build-all-rac-permit-database-compare.py`
  - `processed_data/all_rac_2026_permits_cumulative.csv`
  - `processed_data/all_rac_2026_permits_cumulative.json`
  - `processed_data/all_rac_2026_permits_vs_DATABASE.csv`
  - `processed_data/all_rac_2026_permits_vs_DATABASE.json`
  - `processed_data/all_rac_2026_permits_vs_DATABASE.md`
- Result:
  - Corrected follow-up (UTC): 2026-05-23T06:39:00Z.
  - Removed invalid `DA1051` / Beaver City antlerless deer row after user supplied the corrected official antlerless deer availability list.
  - Corrected `DA1009`, `DA1018`, and `DA1033` antlerless deer permit totals back to the supplied truth source and current `DATABASE.csv` values.
  - Cumulative RAC rows: `562`.
  - RAC rows with hunt codes: `528`.
  - Unique RAC hunt codes: `528`.
  - DATABASE unique hunt codes: `1394`.
  - RAC hunt codes missing in DATABASE: `17`.
  - Numeric mismatch rows: `39`.
  - Significant numeric differences with absolute total delta greater than `5`: `28`.
  - Missing DATABASE hunt codes: `EA1007`, `EA1053`, `EA1287`, `EA1288`, `EA1289`, `EA1290`, `EA1291`, `EA1292`, `EA1293`, `EA1294`, `EA1295`, `EA1296`, `EA1297`, `EA1298`, `EA1299`, `EA1300`, `PD1039`.
  - Corrected antlerless deer truth rows: `16`.
  - Corrected antlerless deer 2026 total: `340`.
- Validation:
  - Ran `python scripts/build-all-rac-permit-database-compare.py`.
  - Ran `python -m compileall scripts/build-all-rac-permit-database-compare.py`.
  - Ran `python -m engine.utah.truth_source_promotion --truth-root pipeline/RAW/hunt_unit_database/2026/csv --processed-root processed_data --families doe_pronghorn antlerless_deer standard_antlerless_elk private_lands_antlerless_elk antlerless_elk_control_units antlerless_moose ewe_rocky_sheep --promote --write-audits`.
  - Ran `python -m pytest tests/utah/test_truth_source_promotion.py -q` and passed `20`.
  - Ran `python -m compileall engine tests scripts/build-all-rac-permit-database-compare.py`.
  - Confirmed all five processed output artifacts exist and the comparison CSV has `562` rows.
  - Confirmed `DA1051` count is `0` in the corrected antlerless deer truth file, audit CSV, runtime reference, enriched master, draw reality, point ladder, RAC cumulative, and RAC-vs-DATABASE comparison.

## Antlerless Elk Allotment Vs Current Runtime Comparison
- Timestamp (UTC): 2026-05-23T06:44:00Z
- Scope:
  - Initial pass incorrectly used `DATABASE.csv` as the allotment baseline.
  - Corrected pass (UTC): 2026-05-23T06:50:00Z.
  - Compared the current RAC allotment values from `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_antlerless_elk_permits.csv` against `DATABASE.csv` and the promoted runtime reference.
  - Did not change model math or active permit values in this pass.
- Files written:
  - `scripts/compare-antlerless-elk-allotments.py`
  - `processed_data/antlerless_elk_current_rac_allotment_vs_database_runtime.csv`
  - `processed_data/antlerless_elk_current_rac_allotment_vs_database_runtime.json`
  - `processed_data/antlerless_elk_current_rac_allotment_vs_database_runtime.md`
- Result:
  - Current RAC rows compared: `116`.
  - Runtime matches current RAC: `116`.
  - Runtime difference rows: `0`.
  - DATABASE difference rows: `37`.
  - DATABASE stale/different rows: `20`.
  - DATABASE missing current RAC hunt codes: `17`.
  - Significant DATABASE differences with absolute total delta greater than `5`: `19`.
  - Largest DATABASE differences: `EA1267` Cache RAC `200` vs DATABASE `90`, `EA1269` Ogden excludes Hyrum RAC `300` vs DATABASE `200`, `EA2033` Kamas archery RAC `200` vs DATABASE `250`.
- Validation:
  - Ran `python scripts/compare-antlerless-elk-allotments.py`.
  - Ran `python -m compileall scripts/compare-antlerless-elk-allotments.py`.

## Out-Of-Scope Non-Target Cleanup
- Timestamp (UTC): 2026-05-22T18:30:00Z
- Scope:
  - Tightened `OUT_OF_SCOPE_NON_TARGET` handling without deleting audit data.
  - Fixed a false-positive classifier rule where the generic token `grouse` incorrectly pushed `Box Elder, Grouse Creek` limited-entry elk rows into the out-of-scope bucket.
  - Rebuilt predictive artifacts so `EB3147`, `EB3150`, and `EB3153` now classify as `BONUS_LE_BIG_GAME` / `MODELED_BONUS`.
  - Added Hunt Research gating so true out-of-scope rows remain hidden from the standard prediction view and only surface in audit/debug mode with an explicit out-of-scope label.
  - Preserved out-of-scope categories in coverage/audit reporting with null probability fields.
- Files updated:
  - `engine/utah_draw_predictive/classifier.py`
  - `hunt-research.js`
  - `docs/utah_draw_system_scope.md`
  - `docs/data_feed_contract.md`
  - `tests/utah_draw_predictive/test_out_of_scope_non_target.py`
  - `tests/utah_draw_predictive/test_out_of_scope_runtime_policy.py`
  - `tests/utah/test_frontend_probability_selection.py`
  - `tests/utah_bonus_predictive/test_final_artifact_guardrails.py`
- Validation notes:
  - Live `OUT_OF_SCOPE_NON_TARGET` predictive row count after rebuild: `0`
  - `EB3147`, `EB3150`, and `EB3153` are no longer misclassified as out-of-scope
  - Out-of-scope rows, if present, keep probability fields null and remain countable in coverage artifacts
  - Standard Hunt Research view now hides out-of-scope rows unless audit/debug mode is enabled

## Draw Odds Combined Display Format
- Timestamp (UTC): 2026-05-22T10:30:00Z
- Scope:
  - Updated Hunt Research so every user-facing draw-odds display uses combined `~1 in X or Y%` text instead of percent-only odds.
  - Added a shared draw-odds formatter and centralized numeric odds selection order in `hunt-research.js`.
  - Removed any remaining status-driven MAX POOL odds shortcut behavior from the display path.
  - Updated the Hunt Research signal legend so green is tied to effective numeric guarantee rather than MAX POOL status text.
  - Added and refreshed regression tests for combined odds examples, MAX POOL fixture behavior, ladder formatting, source snapshot formatting, and no-percent-only primary odds.
- Files updated:
  - `hunt-research.js`
  - `research.html`
  - `ENGINE_RULES_SPEC.md`
  - `HYBRID_ML_V1.md`
  - `docs/predictive_engine_design.md`
  - `docs/utah_bonus_predictive_engine.md`
  - `docs/utah_draw_system_scope.md`
  - `tests/utah/test_frontend_probability_selection.py`
- Rules locked in:
  - User-facing draw odds now select numeric values in this order:
    - `display_odds_pct`
    - `p_draw_mean * 100`
    - `odds_2026_projected`
    - `max_pool_projection_2026`
    - `random_draw_odds_2026`
    - `random_draw_projection_2026`
    - otherwise `Not available`
  - `MAX POOL` remains descriptive only and does not imply `~1 in 1 or 100%`, a Guaranteed badge, or a green light by itself.
  - Internal numeric probability fields remain unchanged.
- Validation target:
  - `py -3 -m pytest tests/utah -q`
  - `node --check hunt-research.js`
  - `py -3 -m compileall engine tests`

## Premium Limited Entry Deer Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Reviewed user-supplied 2025 to 2026 premium limited-entry / management / cactus deer permit counts and treated them as the truth-source reference.
  - Normalized `DB1121` Antelope Island Management 2025 values from blank to explicit zeroes in the RAC supplemental source table.
  - Added missing `DB1058` Paunsaugunt Cactus to the same source table so the repo carries the full user-confirmed permit set.
  - Built a compact audit artifact showing which changes are unchanged, minor, or significant.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_buck_deer_premium_management_permits.csv`
- Outputs created:
  - `processed_data/ple_deer_truth_source_audit.csv`
  - `processed_data/ple_deer_truth_source_audit.json`
- Validation summary:
  - All current 2026 repo-side permit values for the audited rows match the truth-source table: `true`
  - Smoke tests run: `6`
  - Smoke tests failed: `0`
  - Significant row-level changes greater than 5 permits:
    - `DB1010` Paunsaugunt Management Any Legal Weapon resident: `24 -> 30` (`+6`)
    - `DB1058` Paunsaugunt Cactus Any Legal Weapon resident: `27 -> 18` (`-9`)
  - Major group-level changes:
    - `Paunsaugunt Management`: `45 -> 55` (`+10`)
    - `Paunsaugunt Cactus`: `30 -> 20` (`-10`)
  - Minor notable changes:
    - `Henry Mtns Premium`: `44 -> 46` (`+2`)
    - `Antelope Island Management`: `0 -> 2` (`+2`, new 2026 row)

## Limited Entry Deer Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Added the user-provided 2025 to 2026 limited-entry buck deer permit table as a supplemental truth-source reference.
  - Built a focused audit comparing the truth-source table against current repo-side 2026 permit values.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_buck_deer_limited_entry_permits.csv`
- Outputs created:
  - `processed_data/le_deer_truth_source_audit.csv`
  - `processed_data/le_deer_truth_source_audit.json`
- Validation summary:
  - All current 2026 repo-side permit values for the audited rows match the truth-source table: `true`
  - Smoke tests run: `6`
  - Smoke tests failed: `0`
  - Major group-level changes:
    - `Book Cliffs, North`: `127 -> 152` (`+25`)
    - `Book Cliffs`: `107 -> 131` (`+24`)
    - `West Desert, Vernon`: `230 -> 254` (`+24`)
    - `Diamond Mtn`: `110 -> 120` (`+10`)
  - Significant group-level change:
    - `Book Cliffs, South`: `32 -> 38` (`+6`)
  - Significant row-level changes greater than 5 permits:
    - `DB1017` Book Cliffs, North resident: `114 -> 137` (`+23`)
    - `DB1024` West Desert, Vernon resident: `118 -> 130` (`+12`)
    - `DB1011` Book Cliffs archery resident: `45 -> 55` (`+10`)
    - `DB1025` Book Cliffs muzzleloader resident: `45 -> 55` (`+10`)

## O.I.L. Bull Moose Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Added the user-provided 2025 to 2026 O.I.L. bull moose permit table as a supplemental truth-source reference.
  - Built a focused audit comparing the truth-source table against current repo-side 2026 permit values.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_oial_bull_moose_permits.csv`
- Outputs created:
  - `processed_data/oial_moose_truth_source_audit.csv`
  - `processed_data/oial_moose_truth_source_audit.json`
- Validation summary:
  - All current 2026 repo-side permit values for the audited rows match the truth-source table: `true`
  - Smoke tests run: `6`
  - Smoke tests failed: `0`
  - Grand total changed from `106` to `113` (`+7`)
  - Largest unit-level change:
    - `MB6000` Cache resident: `12 -> 14` (`+2`)
  - Minor unit-level increases:
    - `Chalk Creek`: `3 -> 4`
    - `East Canyon, Morgan-Summit`: `4 -> 5`
    - `Kamas`: `5 -> 6`
    - `North Slope, Summit`: `22 -> 23`
    - `Yellowstone`: `5 -> 6`
  - Nonresident total remained flat at `11`; resident total increased from `95` to `102`

## O.I.L. Mountain Goat Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Added the user-provided 2025 to 2026 O.I.L. mountain goat permit table as a supplemental truth-source reference.
  - Built a focused audit comparing the truth-source table against current repo-side 2026 permit values.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_oial_mountain_goat_permits.csv`
- Outputs created:
  - `processed_data/oial_goat_truth_source_audit.csv`
  - `processed_data/oial_goat_truth_source_audit.json`
- Validation summary:
  - All current 2026 repo-side permit values for the audited rows match the truth-source table: `true`
  - Smoke tests run: `6`
  - Smoke tests failed: `0`
  - Grand total changed from `103` to `112` (`+9`)
  - Largest unit-level change:
    - `GO6803` Nebo any legal weapon: `18 -> 24` (`+6`)
  - Minor unit-level increases:
    - `High Uintas East`: `2 -> 3`
    - `High Uintas Leidy Peak`: `1 -> 2`
    - `La Sal Mtns`: `11 -> 12`
  - Nonresident total increased from `10` to `11`; resident total increased from `93` to `101`

## O.I.L. Bison Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Added the user-provided 2025 to 2026 O.I.L. bison permit table as a supplemental truth-source reference.
  - Built a focused audit comparing the truth-source table against current repo-side 2026 permit values.
  - Treated `BI6527` Nine Mile OTC as a non-quota context row and kept it out of the numeric quota audit.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_oial_bison_permits.csv`
- Outputs created:
  - `processed_data/oial_bison_truth_source_audit.csv`
  - `processed_data/oial_bison_truth_source_audit.json`
- Validation summary:
  - All current 2026 repo-side permit values for the audited quota rows match the truth-source table: `true`
  - Smoke tests run: `6`
  - Smoke tests failed: `0`
  - Grand total changed from `133` to `135` (`+2`)
  - Largest positive changes:
    - `BI6536` Book Cliffs, Bitter Creek female only: `3 -> 15` (`+12`)
    - `BI6534` Book Cliffs, Bitter Creek hunter's choice: `5 -> 10` (`+5`)
    - `BI6537` Book Cliffs, Little Creek/South hunter's choice: `10 -> 15` (`+5`)
  - Largest negative changes:
    - `BI6506` Henry Mtns female only: `30 -> 11` (`-19`)
    - `BI6505` Henry Mtns female only: `29 -> 11` (`-18`)
  - `BI6539` Henry Mtns female only is a new 2026 quota row normalized from 2025 dashes to zero for comparison.

## O.I.L. Desert Bighorn Sheep Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Added the user-provided 2025 to 2026 O.I.L. desert bighorn sheep permit table as a supplemental truth-source reference.
  - Built a focused audit comparing the truth-source table against current repo-side 2026 permit values.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_oial_desert_bighorn_sheep_permits.csv`
- Outputs created:
  - `processed_data/oial_desert_sheep_truth_source_audit.csv`
  - `processed_data/oial_desert_sheep_truth_source_audit.json`
- Validation summary:
  - All current 2026 repo-side permit values for the audited rows match the truth-source table: `true`
  - Smoke tests run: `6`
  - Smoke tests failed: `0`
  - Grand total changed from `88` to `85` (`-3`)
  - Largest decreases:
    - `DS6621` Pine Valley, Beaver Dam: `5 -> 2` (`-3`)
    - `DS6608` San Rafael, Dirty Devil: `7 -> 4` (`-3`)
  - Largest increase:
    - `DS6604` La Sal, Potash/South Cisco: `6 -> 8` (`+2`)
  - Minor increases:
    - `DS6601` Kaiparowits, East: `12 -> 13`
    - `DS6625` Mineral Mtns: `3 -> 4`

## O.I.L. Rocky Mountain Bighorn Sheep Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Added the user-provided 2025 to 2026 O.I.L. Rocky Mountain bighorn sheep permit table as a supplemental truth-source reference.
  - Built a focused audit comparing the truth-source table against current repo-side 2026 permit values.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_oial_rocky_mountain_bighorn_sheep_permits.csv`
- Outputs created:
  - `processed_data/oial_rocky_sheep_truth_source_audit.csv`
  - `processed_data/oial_rocky_sheep_truth_source_audit.json`
- Validation summary:
  - All current 2026 repo-side permit values for the audited rows match the truth-source table: `true`
  - Smoke tests run: `6`
  - Smoke tests failed: `0`
  - Grand total changed from `52` to `51` (`-1`)
  - Largest decreases:
    - `RS6726` Fillmore, Oak Creek: `5 -> 4` (`-1`)
    - `RS6709` North Slope, Summit/West Daggett: `4 -> 3` (`-1`)
    - `RS6708` North Slope, Three Corners: `3 -> 2` (`-1`)
  - Largest increases:
    - `RS6700` Antelope Island: `1 -> 2` (`+1`)
    - `RS6724` Wasatch Mtns, West: `2 -> 3` (`+1`)

## General Season Bull Elk Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Added the user-provided 2025 to 2026 general season bull elk category table as a supplemental truth-source reference.
  - Built a focused audit comparing the truth-source category totals against current repo-side 2026 category or code-level support.
  - Kept the audit explicit about category-level gaps where the repo currently stores code-level context rows instead of a clean category total.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_general_season_bull_elk_permits.csv`
- Outputs created:
  - `processed_data/general_bull_elk_truth_source_audit.csv`
  - `processed_data/general_bull_elk_truth_source_audit.json`
- Validation summary:
  - Smoke tests run: `6`
  - Smoke tests failed: `0`
  - Clear 2026 match:
    - `EB1007` draw-only youth any bull stayed `750 -> 750`
  - Clear 2026 mismatch:
    - `EB1012` Uinta Basin private lands only any bull is `500` in current repo-side source rows but `750` in the user-provided truth table
  - Category-level verification gaps remain for:
    - `Spike Bull` `15000 -> 15000`
    - `Any Bull Elk (includes muzzleloader)` `15000 -> 15000`
    - `Any Bull Late` `Unlimited -> Unlimited`
    - `Youth General Season` `Unlimited -> Unlimited`

## Limited Entry Bull Elk Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Added the user-provided 2025 to 2026 limited-entry bull elk permit table as a supplemental truth-source reference.
  - Built a focused audit comparing the truth-source table against current repo-side 2026 permit values.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_limited_entry_bull_elk_permits.csv`
- Outputs created:
  - `processed_data/le_bull_elk_truth_source_audit.csv`
  - `processed_data/le_bull_elk_truth_source_audit.json`
- Validation summary:
  - Smoke tests run: `6`
  - Smoke tests failed: `0`
  - Current repo-side mismatches are limited to a Monroe cluster:
    - `EB3010`
    - `EB3047`
    - `EB3088`
    - `EB3112`
    - `EB3185`
  - Large increases:
    - `Nebo/San Pitch Mtns`: `95 -> 128` (`+33`)
    - `Boulder`: `125 -> 139` (`+14`)
    - `San Juan Bull Elk`: `115 -> 127` (`+12`)
    - `Diamond Mtn`: `100 -> 111` (`+11`)
  - Large decreases:
    - `Wasatch Mtns`: `726 -> 580` (`-146`)
    - `Manti`: `700 -> 660` (`-40`)
  - `EB3024` Beaver, East early any legal weapon remained unchanged at `10`.

## Limited Entry Bull Elk Late Archery Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Added the user-provided 2025 to 2026 limited-entry late archery bull elk permit table as a supplemental truth-source reference.
  - Built a focused audit comparing the truth-source table against current repo-side 2026 permit values.
  - Preserved the row-level truth values as canonical because the printed 2025 resident subtotal in the user block does not reconcile with the listed rows.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_limited_entry_bull_elk_late_archery_permits.csv`
- Outputs created:
  - `processed_data/le_bull_elk_late_archery_truth_source_audit.csv`
  - `processed_data/le_bull_elk_late_archery_truth_source_audit.json`
- Validation summary:
  - Smoke tests run: `6`
  - Smoke tests failed: `0`
  - Row-summed totals:
    - `2025`: `158`
    - `2026`: `193`
  - The printed `2025` line `95 / 11 / 158` is partially inconsistent with the listed rows:
    - row-summed resident subtotal = `138`
    - row-summed nonresident subtotal = `20`
    - row-summed grand total = `158`
  - The grand total `158` reconciles, but the displayed resident/nonresident subtotals do not.
  - Largest increases:
    - `Beaver, East`: `15 -> 20` (`+5`)
    - `Fillmore, Pahvant`: `15 -> 20` (`+5`)
    - `Southwest Desert, South`: `10 -> 20` (`+10`)
  - Other notable increases:
    - `Mt Dutton`: `10 -> 15` (`+5`)
    - `Nebo/San Pitch Mtns`: `10 -> 15` (`+5`)
    - `Panguitch Lake`: `10 -> 15` (`+5`)

## Limited Entry Bull Elk HAMSS And September Archery Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Added the user-provided 2025 to 2026 limited-entry HAMSS and September archery bull elk permit tables as a supplemental truth-source reference.
  - Built a focused audit comparing the truth-source table against current repo-side 2026 permit values.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_limited_entry_bull_elk_hamss_and_september_archery_permits.csv`
- Outputs created:
  - `processed_data/le_bull_elk_hamss_september_archery_truth_source_audit.csv`
  - `processed_data/le_bull_elk_hamss_september_archery_truth_source_audit.json`
- Validation summary:
  - Smoke tests run: `6`
  - Smoke tests failed: `0`
  - All current repo-side 2026 rows for these hunt codes match the truth-source table: `true`
  - HAMSS totals remained flat at `80 -> 80`
  - September archery totals increased from `70 -> 72` (`+2`)
  - Largest decreases:
    - `Cache, North`: `28 -> 24` (`-4`) for both HAMSS and September archery
    - `East Canyon`: `10 -> 8` (`-2`) for HAMSS
  - Largest increases:
    - `Southwest Desert, North`: `18 -> 23` (`+5`) for both HAMSS and September archery
    - `West Desert, Deep Creek`: `14 -> 15` (`+1`) for both HAMSS and September archery

## Bear Strategy Correction - Official 2025 Draw Odds Re-Audit
- Timestamp (UTC): 2026-05-21T00:00:00Z
- Scope:
  - Re-audited Utah black bear rows against the official `2025 Black Bear Draw odds.pdf` and the 2026 black bear permit sheet.
  - Corrected the blanket treatment of unit-specific pursuit rows so official point-table pursuit hunt codes are modeled as bear bonus draw rows.
  - Preserved `BR1000` as `SPORTSMAN_PERMIT`, `BR1001` as harvest-objective availability, and `BR1007` / `BR1018` as unlimited-pursuit availability.
- Files updated:
  - `engine/utah_draw_predictive/bear.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - Focused bear audit / subtype / materialization tests
- Outputs refreshed:
  - `processed_data/bear_predictions_v1.csv`
  - `processed_data/bear_report.json`
  - `processed_data/bear_draw_odds_source_audit.csv`
  - `processed_data/bear_draw_odds_source_audit.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/predictive_coverage_report.csv`
  - `processed_data/predictive_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
- Validation summary:
  - Focused Python tests run: `21`
  - Focused Python tests failed: `0`
  - Official bear hunt codes found in 2025 draw-odds PDF: `97`
  - Official bear pursuit hunt codes found in 2025 draw-odds PDF: `9`
  - Pursuit hunt codes corrected from availability to modeled bonus: `9`
  - `BR1008`, `BR1009`, and `BR1011` now classify as `RESTRICTED_BEAR_PURSUIT` and materialize with bear bonus probability fields.
  - `BR1000` remains Sportsman-only.
  - `BR1001` remains harvest-objective availability-only with no `p_draw`.
  - `BR1007` / `BR1018` remain unlimited-pursuit availability-only with no `p_draw`.
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Correction results:
  - Official point-table pursuit rows are now treated as real point-based bear draw rows for matching 2026 quota hunt families.
  - Availability-only bear rows still do not receive fake draw odds.
  - Bear rows still never use `p_preference_draw`.
  - Existing EB3024, one-permit random-only, MAX POOL, and UI precedence guardrails remained passing.

## Step 1B - Raw Inventory Audit
- Timestamp (UTC): 2026-05-10T12:43:23.701298Z
- Total files audited: 1286
- Promoted quality sources: 253
- Promoted draw sources: 204
- Held/review sources: 829
- Biggest risks found:
  - High duplicate pressure: 296 files held as duplicates.
  - Unreadable PDFs: 13 files require source replacement or repair.
  - Review required: 489 files have unknown/conflicting metadata.
  - Missing year inference: 27 files need year assignment.
- Outputs:
  - data_model/quality/raw_pdf_inventory_audit.csv
  - data_model/quality/raw_pdf_inventory_audit_report.json

## Step 1C - Promoted Source Manifests
- Timestamp (UTC): 2026-05-10T13:16:50.588074+00:00
- Input: data_model/quality/raw_pdf_inventory_audit.csv
- Promoted quality sources: 253
- Promoted draw sources: 204
- Validation passed: True
- Promotion blockers: 0
- Outputs:
  - data_model/quality/promoted_quality_sources.csv
  - data_model/quality/promoted_draw_sources.csv
  - data_model/quality/promoted_source_summary.json

## Step 1D - Promoted Source Year Map
- Timestamp (UTC): 2026-05-10T13:34:21.393303+00:00
- Inputs:
  - data_model/quality/promoted_quality_sources.csv
  - data_model/quality/promoted_draw_sources.csv
  - data_model/quality/raw_pdf_inventory_audit.csv
- Promoted quality rows mapped: 253
- Promoted draw rows mapped: 204
- Total promoted rows in year map: 457
- Year conflicts (folder year vs reported hunt year): 222
- Year unknown rows: 0
- Validation passed: True
- Outputs:
  - data_model/quality/promoted_source_year_map.csv
  - data_model/quality/promoted_source_year_map_report.json

## Reference Baseline Audit - DATABASE.csv
- Timestamp (UTC): 2026-05-10T14:06:52.319022+00:00
- Source:
  - pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv
- Classification:
  - reference_role: canonical_2026_database_reference
  - derived_or_source: source_reference
  - usable_for_hunt_code_validation: YES
  - usable_for_2026_permit_reference: YES
  - usable_for_harvest_truth: NO
  - usable_for_draw_truth: NO
- Validation counts:
  - rows: 1395
  - unique hunt codes: 1394
  - duplicate hunt codes: 0
  - malformed/missing hunt_code rows: 1 (flagged/rejected for reference joins)
  - missing permits_2026_total rows (allowed): 321
  - total present with split missing (allowed): 194
  - res+nr vs total conflicts (blockers): 0
- Outputs:
  - data_model/quality/reference_baseline_audit.csv
  - data_model/quality/reference_baseline_audit_report.json

## Runtime Draft Build - V3 Draw Feed (Draft Only)
- Timestamp (UTC): 2026-05-10T17:44:04Z
- Task scope:
  - Build validated draft runtime draw feed from DATABASE-aligned V3 draw truth.
  - Do not modify website files.
  - Do not overwrite production `processed_data` runtime feeds.
- Inputs:
  - data_truth/draw_results_truth/normalized/draw_results_long.csv
  - processed_data/draw_reality_engine.csv (comparison baseline only)
  - pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv
- Outputs:
  - data_model/runtime_drafts/draw_reality_engine_v2.csv
  - data_model/runtime_drafts/draw_reality_engine_v2_manifest.json
  - data_model/runtime_drafts/draw_reality_engine_v2_validation_report.json
  - data_model/runtime_drafts/draw_reality_engine_v2_vs_current_report.json
  - data_model/runtime_drafts/draw_reality_engine_v2_rows_added.csv
  - data_model/runtime_drafts/draw_reality_engine_v2_schema_changes.csv
- Validation results:
  - V3 rows: 112056
  - Draft rows: 112056
  - Corrected-key duplicates: 0
  - Required key blanks (`hunt_code`, `year`, `draw_pool`, `residency`, `points`): 0
  - DATABASE-matched rows missing boundary_id: 0
  - `HUNT_CODE_NOT_IN_2026_DATABASE` rows: 7167
  - `HUNT_CODE_NOT_IN_2026_DATABASE` unique hunt codes: 221
  - Current runtime rows: 36862
  - Rows added vs current runtime: 75194
  - Current runtime missing `draw_pool`: true
  - Core draw-value mismatches on overlapping rows: 0
- Promotion blockers:
  - Production `processed_data` not updated in this step.
  - Website runtime not updated in this step.
  - Downstream runtime consumers may need schema updates for `draw_pool`.

## Runtime Draft Sync - 2026 DATABASE-Backed Support Feeds (Draft Only)
- Timestamp (UTC): 2026-05-10T17:51:04Z
- Scope:
  - Built remaining 2026 DATABASE-backed runtime draft files under `data_model/runtime_drafts`.
  - Did not overwrite production `processed_data`.
  - Did not update website files/loaders.
- Inputs:
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
  - `data_model/runtime_drafts/draw_reality_engine_v2.csv`
  - `processed_data/point_ladder_view.csv`
  - `processed_data/hunt_master_enriched.csv`
  - `processed_data/hunt_unit_reference_linked.csv`
- Outputs:
  - `data_model/runtime_drafts/permits_2026_online.csv`
  - `data_model/runtime_drafts/point_ladder_view_v2.csv`
  - `data_model/runtime_drafts/hunt_master_enriched_v2.csv`
  - `data_model/runtime_drafts/hunt_boundary_crosswalk_v2.csv`

## Runtime Draft Pre-Promotion Audit - Duplicate/Matrix Integrity (Draft Only)
- Timestamp (UTC): 2026-05-10T18:12:04Z
- Scope:
  - Audited runtime draft integrity before any promotion.
  - Focused on removed rows from `hunt_master_enriched` during draft sync.
  - Audited separation and usage of `hunt_type`, `hunt_class`, `draw_pool`, and status fields.
  - No production files modified.
- Inputs:
  - `processed_data/hunt_master_enriched.csv`
  - `data_model/runtime_drafts/hunt_master_enriched_v2.csv`
  - `data_model/runtime_drafts/draw_reality_engine_v2.csv`
  - `data_model/runtime_drafts/point_ladder_view_v2.csv`
  - `data_model/runtime_drafts/permits_2026_online.csv`
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Outputs:
  - `data_model/validation/runtime_draft_pre_promotion_audit.csv`
  - `data_model/validation/runtime_draft_pre_promotion_audit_report.json`
  - `data_model/validation/hunt_master_enriched_duplicate_audit.csv`
  - `data_model/validation/hunt_type_hunt_class_matrix_audit.csv`
- Key results:
  - Rows in source `hunt_master_enriched` missing from draft v2 by key (`hunt_code+residency+points`): 1203
  - `SAFE_DUPLICATE_COLLAPSE`: 0
  - `REVIEW_REQUIRED`: 0
  - `PROMOTION_BLOCKER`: 1203
  - Corrected-key duplicates in `draw_reality_engine_v2` (`hunt_code+year+draw_pool+residency+points`): 0
  - Distinct draw pools present in `draw_reality_engine_v2`: `standard`, `youth`, `lifetime`, `dedicated_hunter`, `youth_dedicated_hunter`, `youth_turkey`, `youth_mature_bull`
  - Status misuse findings: 0
  - Draw pool misused as `hunt_class`: 14169 rows (promotion blocker)
  - `data_model/runtime_drafts/runtime_feed_sync_report.json`
  - `data_model/runtime_drafts/runtime_feed_sync_summary.csv`
- Validation summary:
  - DATABASE valid hunt codes: 1394
  - permits_2026_online rows: 1394
  - permits blank hunt_code: 0
  - permits duplicate hunt_code: 0
  - permits boundary_id missing: 0
  - permit math conflicts: 0
  - permit status counts:
    - OK: 880
    - TOTAL_ONLY_SPLIT_MISSING: 351
    - NO_QUOTA_PUBLISHED: 163
    - CALCULATED_TOTAL_FROM_SPLIT: 0
    - PERMIT_MATH_CONFLICT: 0
  - point_ladder_view_v2 rows: 91588
  - point_ladder_view_v2 boundary_id missing: 0
  - point_ladder_view_v2 duplicate hunt_code+residency+points: 0
  - hunt_master_enriched_v2 rows: 51857
  - hunt_master_enriched_v2 duplicate keys removed from source during draft sync: 1203
  - hunt_master_enriched_v2 boundary_id missing: 0
  - hunt_boundary_crosswalk_v2 rows: 1394
  - hunt_boundary_crosswalk_v2 duplicate hunt_code: 0
  - hunt_boundary_crosswalk_v2 boundary_id missing: 0
- Promotion blockers:
  - DRAFT_ONLY_NOT_PUBLISHED
  - PROCESSED_DATA_NOT_UPDATED
  - WEBSITE_LOADER_MUST_SUPPORT_DRAW_POOL
  - DO_NOT_MERGE_HISTORICAL_DATABASE_YEARS_INTO_2026

## Validation Audit - hunt_type vs hunt_class Matrix
- Timestamp (UTC): 2026-05-10T18:10:44Z
- Scope:
  - Audited runtime draft files for correct usage separation of `hunt_type`, `hunt_class`, `draw_pool`, and status fields.
  - No production/runtime/website files were modified.
- Inputs:
  - `data_model/runtime_drafts/draw_reality_engine_v2.csv`
  - `data_model/runtime_drafts/point_ladder_view_v2.csv`
  - `data_model/runtime_drafts/hunt_master_enriched_v2.csv`
  - `data_model/runtime_drafts/permits_2026_online.csv`
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Outputs:
  - `data_model/validation/hunt_type_hunt_class_matrix_audit.csv`
  - `data_model/validation/hunt_type_hunt_class_matrix_audit_report.json`
- Validation summary:
  - Distinct `hunt_type` values: 34
  - Distinct `hunt_class` values: 6
  - Rows with blank `hunt_class`: 0
  - Rows where `hunt_class == hunt_type`: 63963
  - Suspicious broad `hunt_class` rows: 236012
  - Status/data_status classification misuse findings: 0
  - Total issue rows written: 313189
- Key finding:
  - `hunt_class` is largely populated with broad bucket values (especially non-selective classes), so classification selectivity is not aligned with required matrix semantics.
  - `DATABASE.csv` currently has `hunt_type` but no `hunt_class`; `proposed_hunt_class` was generated in the audit output only.

## Harvest Truth Normalization - 2025 Preliminary Harvest for 2026 Model (Draft Truth Layer)
- Timestamp (UTC): 2026-05-10T19:10:38Z
- Scope:
  - Parsed and normalized `2026-03-06-2025-preliminary-bg-harvest.pdf` for harvest truth only.
  - Explicitly kept this source out of 2026 permit allocation fields.
  - No updates to `processed_data`, website files, `public_client_engine.csv`, or prediction builds.
- Inputs:
  - `pipeline/RAW/hunt_unit_database/2026/pdf/harvest_report/2026-03-06-2025-preliminary-bg-harvest.pdf`
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Outputs:
  - `data_truth/harvest_results_truth/normalized/harvest_results_2025_for_2026_long.csv`
  - `data_truth/harvest_results_truth/normalized/harvest_results_2025_for_2026_rejects.csv`
  - `data_truth/harvest_results_truth/normalized/harvest_results_2025_for_2026_report.json`
  - `data_model/quality/harvest_quality_2025_for_2026.csv`
  - `data_model/quality/harvest_quality_2025_for_2026_vs_database.csv`

## Draft Rebuild - point_ladder_view_v3 from 2025 Actual Draw Truth + 2026 Pool Projection
- Timestamp (UTC): 2026-05-10T20:19:58Z
- Scope:
  - Rebuilt draft ladder feed under `data_model/runtime_drafts` only.
  - Did not modify `processed_data`, website files, `public_client_engine.csv`, or prediction models.
- Inputs:
  - `data_model/runtime_drafts/draw_reality_engine_v2.csv`
  - `data_model/runtime_drafts/permits_2026_online.csv`
  - `data_model/runtime_drafts/point_ladder_view_v2.csv`
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Outputs:
  - `data_model/runtime_drafts/applicant_pool_2026_from_2025_actual.csv`
  - `data_model/runtime_drafts/point_ladder_view_v3.csv`
  - `data_model/runtime_drafts/point_ladder_view_v3_validation_report.json`
  - `data_model/runtime_drafts/point_ladder_view_v3_vs_current.csv`
  - `data_model/runtime_drafts/point_ladder_missing_columns_audit.csv`
- Validation summary:
  - `point_ladder_view_v3` rows: `78162`
  - Blank key fields (`hunt_code`, `draw_pool`, `residency`, `points`): `0`
  - Duplicate corrected keys (`hunt_code+draw_pool+residency+points`): `0`
  - Rows missing `odds_2025_actual`: `70836`
  - Rows missing `max_pool_projection_2026`: `19462`
  - Rows missing `odds_2025_actual` despite 2025 actual odds existing: `0`
  - Rows with projected applicants but blank `max_pool_projection_2026`: `0`
  - Negative projected nonwinner rows: `0`
  - Promotion blockers: `0`
- Notes:
  - `draw_pool` is preserved in the corrected key and row output.
  - `odds_2025_actual` is sourced only from 2025 actual draw rows and not from projected values.
  - 2026 permit fields remain sourced from DATABASE-backed permit drafts only.
- Validation summary:
  - Total pages scanned: 19
  - Parsed rows: 1118
  - Rejected rows: 2
  - Unique hunt codes: 1118
  - DATABASE matched rows: 1089
  - DATABASE unmatched rows: 29
  - Blank hunt_code rows: 0
  - Blank harvest metric rows: 4
  - Percent-success conflicts beyond tolerance: 0
  - Impossible metrics (`harvest > hunters`): 0
  - Duplicate hunt-code counts: none
- Classification notes:
  - The same-named PDF found under `pipeline/RAW/hunt_unit_database/2026/pdf/current_year_permit_numbers/...` was flagged as `MISFILED_HARVEST_REPORT` in the report.
  - Raw file was not moved.
  - `reported_hunt_year` was fixed to 2025 and `model_target_year` to 2026.
  - `source_permits` remains a harvest-report metric and is not used as 2026 allocation quota.

## Step 1C - Promoted Source Manifests Sync
- Timestamp (UTC): 2026-06-21T00:09:12.634264+00:00
- Scope:
  - Re-ran the canonical Step 1C manifest builder against `data_model/quality/raw_pdf_inventory_audit.csv`.
  - Confirmed no alternate Step 1C pipeline was introduced.
  - Did not modify website files, `public_client_engine.csv`, or `engine/utah/materialize_engine.py`.
- Outputs refreshed:
  - `data_model/quality/promoted_source_summary.json`
- Outputs verified unchanged and present:
  - `data_model/quality/promoted_quality_sources.csv`
  - `data_model/quality/promoted_draw_sources.csv`
- Validation summary:
  - Expected promoted quality rows from audit: 253
  - Actual promoted quality rows: 253
  - Expected promoted draw rows from audit: 204
  - Actual promoted draw rows: 204
  - Duplicate quality source rows: 0
  - Duplicate draw source rows: 0
  - Non-promoted quality rows leaked into manifest: 0
  - Non-promoted draw rows leaked into manifest: 0
  - Summary `all_checks_passed`: true

## Utah Predictive Draw Engine Review Audit
- Timestamp (UTC): 2026-05-20T00:00:00Z
- Scope:
  - Review-only audit of the Utah predictive draw-engine work under `C:\Users\tyler\Desktop\GitHub\HUNTS`.
  - Confirmed the review used the active repo only and did not use `C:\Projects\HUNTS-main`.
  - Did not start Phase 8 or implement any new family strategy during this pass.
- Outputs created:
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
- Validation summary:
  - Python tests run: `63`
  - Python tests failed: `0`
  - Current predictive rows: `28860`
  - `MODELED_BONUS` rows: `23407`
  - `MODELED_PREFERENCE` rows: `1634`
  - `IN_SCOPE_MODEL_PENDING` rows: `2911`
  - `OUT_OF_SCOPE_NON_TARGET` rows: `908`
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Review findings:
  - Phase 7 turkey report semantics are now explicit in the generated turkey artifacts.
  - Coverage family-vs-history semantics are present, but one pending-family boolean still uses row presence instead of registry status for mountain lion/cougar.
  - Utah draw-system docs still describe several modeled Phase 3-7 families as pending and need refresh before the next implementation phase.

## Final Cleanup Before Phase 8
- Timestamp (UTC): 2026-05-21T00:00:00Z
- Scope:
  - Completed the final pre-Phase-8 cleanup in `C:\Users\tyler\Desktop\GitHub\HUNTS`.
  - Did not use `C:\Projects\HUNTS-main`.
  - Did not start Phase 8 or implement bear, mountain lion/cougar, or private-lands-only antlerless elk strategies.
- Outputs refreshed:
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
- Validation summary:
  - Python tests run: `66`
  - Python tests failed: `0`
  - Predictive rows: `28860`
  - `MODELED_BONUS` rows: `23407`
  - `MODELED_PREFERENCE` rows: `1634`
  - `IN_SCOPE_MODEL_PENDING` rows: `2911`
  - `OUT_OF_SCOPE_NON_TARGET` rows: `908`
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Cleanup results:
  - `docs/utah_draw_system_scope.md` now reflects Phases 1-7 completed and the correct pending families.
  - Mountain lion/cougar is now reported as in scope, not modeled, and still pending even with `0` active predictive rows.
  - All `MODELED_PREFERENCE` rows now populate `p_preference_draw` consistently with `p_draw`.

## Phase 8 Bear Strategy
- Timestamp (UTC): 2026-05-21T00:00:00Z
- Scope:
  - Implemented Phase 8 for `BEAR_DRAW` only in `C:\Users\tyler\Desktop\GitHub\HUNTS`.
  - Did not use `C:\Projects\HUNTS-main`.
  - Did not begin Phase 9 or implement mountain lion/cougar or private-lands-only antlerless elk strategies.
- Files updated:
  - `engine/utah_draw_predictive/bear.py`
  - `engine/utah_draw_predictive/classifier.py`
  - `engine/utah_draw_predictive/random_only.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - `docs/utah_draw_system_scope.md`
  - Focused Phase 8 tests and artifact-validation tests
- Outputs refreshed:
  - `processed_data/bear_draw_predictions_v1.csv`
  - `processed_data/bear_draw_report.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
- Validation summary:
  - Python tests run: `75`
  - Python tests failed: `0`
  - Predictive rows: `27621`
  - `MODELED_BONUS` rows: `25282`
  - `MODELED_PREFERENCE` rows: `1731`
  - `IN_SCOPE_MODEL_PENDING` rows: `402`
  - `OUT_OF_SCOPE_NON_TARGET` rows: `198`
  - `BEAR_DRAW` active predictive rows: `1347`
  - `BEAR_DRAW` modeled rows: `1258`
  - `BEAR_DRAW` pending rows: `81`
  - `BEAR_DRAW` excluded rows: `8`
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Phase 8 results:
  - Public limited-entry bear and restricted bear pursuit rows now model as `MODELED_BONUS` with Utah bonus pool / random pool probabilities.
  - Harvest-objective, non-public, and ambiguous bear rows do not receive fake `p_draw`.
  - Restricted bear pursuit no longer falls into the generic random-only bucket.
  - False-positive `BEAR_DRAW` classification from hunt names like `Bear Mountain` / `Fishlake` was removed from unrelated non-bear rows.
  - Mountain lion/cougar remains in scope, not modeled, and pending.
  - Private-lands-only antlerless elk remains allocation-pending.

## Phase 8 Sportsman Correction
- Timestamp (UTC): 2026-05-21T00:00:00Z
- Scope:
  - Corrected Sportsman permit handling inside Phase 8 without beginning Phase 9.
  - Separated `SPORTSMAN_PERMIT` from `BEAR_DRAW` and other bonus/preference families.
  - Reclassified `BR1000` as `SPORTSMAN_PERMIT`, `BR1001` as harvest-objective availability, and `BR1007` / `BR1018` as unlimited-pursuit availability.
- Outputs refreshed:
  - `processed_data/sportsman_permit_predictions_v1.csv`
  - `processed_data/sportsman_permit_report.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
- Validation summary:
  - Python tests run: `82`
  - Python tests failed: `0`
  - Predictive rows: `27649`
  - `MODELED_BONUS` rows: `25291`
  - `MODELED_PREFERENCE` rows: `1731`
  - `IN_SCOPE_MODEL_PENDING` rows: `419`
  - `EXCLUDED_NOT_PREDICTIVE_DRAW` rows: `10`
  - `OUT_OF_SCOPE_NON_TARGET` rows: `198`
  - `SPORTSMAN_PERMIT` rows: `22`
  - `SPORTSMAN_PERMIT` modeled rows: `0`
  - `SPORTSMAN_PERMIT` pending rows: `22`
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Correction results:
  - Sportsman permits are now classified as their own strategy family and are not detected by a simple `1000` suffix rule.
  - `BR1000` now classifies as `SPORTSMAN_PERMIT` with `draw_outlook = SPORTSMAN ODDS SOURCE MISSING`.
  - `BR1001` remains `HARVEST_OBJECTIVE_AVAILABILITY` and does not receive draw-odds fields.
  - `BR1007` and `BR1018` remain `UNLIMITED_PURSUIT_PERMIT` availability rows and do not receive draw-odds fields.
  - All current Sportsman rows stay pending because the active repo only exposes `SPORTSMAN_PERMIT_NO_DRAW_ODDS` source rows without usable applicant-denominator odds data.

## Phase 9 Private-Lands-Only Antlerless Elk Allocation Strategy
- Timestamp (UTC): 2026-05-21T00:00:00Z
- Scope:
  - Implemented Phase 9 for `PRIVATE_LANDS_ONLY_ANTLERLESS_ELK` only in `C:\Users\tyler\Desktop\GitHub\HUNTS`.
  - Did not use `C:\Projects\HUNTS-main`.
  - Did not begin Phase 10 or implement mountain lion/cougar strategy work.
- Files updated:
  - `engine/utah_draw_predictive/private_lands_antlerless_elk.py`
  - `engine/utah_draw_predictive/classifier.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - `docs/utah_draw_system_scope.md`
  - Focused Phase 9 tests and artifact-validation tests
- Outputs refreshed:
  - `processed_data/private_lands_antlerless_elk_predictions_v1.csv`
  - `processed_data/private_lands_antlerless_elk_report.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
- Validation summary:
  - Python tests run: `87`
  - Python tests failed: `0`
  - Predictive rows: `27703`
  - `MODELED_BONUS` rows: `25291`
  - `MODELED_PREFERENCE` rows: `1731`
  - `MODELED_ALLOCATION` rows: `54`
  - `IN_SCOPE_MODEL_PENDING` rows: `419`
  - `OUT_OF_SCOPE_NON_TARGET` rows: `198`
  - `PRIVATE_LANDS_ONLY_ANTLERLESS_ELK` modeled allocation rows: `54`
  - `PRIVATE_LANDS_ONLY_ANTLERLESS_ELK` hunt codes: `27`
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Phase 9 results:
  - Private-lands-only antlerless elk is now modeled as allocation / availability, not as preference or bonus draw odds.
  - No private-lands-only antlerless elk row receives `p_draw`, `p_draw_pct`, `p_bonus_pool`, `p_random_pool`, or `p_preference_draw`.
  - Allocation totals from the 2026 permit source are preserved in `permits_allotted`, while missing remaining inventory is called out with `allocation_status = ALLOCATION KNOWN / REMAINING UNKNOWN`.
  - Normal public antlerless elk preference rows remain modeled and separate.
  - Mountain lion/cougar remains in scope, not modeled, and pending.

## Phase 10 Mountain Lion / Cougar Availability Strategy
- Timestamp (UTC): 2026-05-21T00:00:00Z
- Scope:
  - Implemented Phase 10 for `MOUNTAIN_LION_DRAW` only in `C:\Users\tyler\Desktop\GitHub\HUNTS`.
  - Did not use `C:\Projects\HUNTS-main`.
  - Did not begin any new bear, sportsman, or private-lands-only antlerless elk work.
- Files updated:
  - `engine/utah_draw_predictive/mountain_lion.py`
  - `engine/utah_draw_predictive/__init__.py`
  - `engine/utah_draw_predictive/classifier.py`
  - `engine/utah_draw_predictive/random_only.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - `docs/utah_draw_system_scope.md`
  - Focused Phase 10 tests and artifact-validation tests
- Outputs refreshed:
  - `processed_data/mountain_lion_availability_predictions_v1.csv`
  - `processed_data/mountain_lion_availability_report.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
- Validation summary:
  - Python tests run: `91`
  - Python tests failed: `0`
  - Predictive rows: `27823`
  - `MODELED_BONUS` rows: `25291`
  - `MODELED_PREFERENCE` rows: `1731`
  - `MODELED_ALLOCATION` rows: `54`
  - `MODELED_AVAILABILITY` rows: `120`
  - `IN_SCOPE_MODEL_PENDING` rows: `419`
  - `OUT_OF_SCOPE_NON_TARGET` rows: `198`
  - `MOUNTAIN_LION_DRAW` rows: `120`
  - `MOUNTAIN_LION_DRAW` hunt codes: `60`
  - `MOUNTAIN_LION_DRAW` units: `60`
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Phase 10 results:
  - Mountain lion / cougar is now modeled as statewide OTC rule-status and availability, not draw odds.
  - No mountain lion row receives `p_draw`, `p_draw_pct`, `p_bonus_pool`, `p_random_pool`, or `p_preference_draw`.
  - The local 2026 cougar guidebook provides year-round availability support, and the local cougar geometry file provides the management/reporting unit surface.
  - Coverage now distinguishes in-scope availability modeling from pending families without showing `0 rows` plus `still pending` confusion for cougar.

## Phase 11 Sportsman Permit Odds Strategy
- Timestamp (UTC): 2026-05-21T00:00:00Z
- Scope:
  - Implemented Phase 11 for `SPORTSMAN_PERMIT` only in `C:\Users\tyler\Desktop\GitHub\HUNTS`.
  - Normalized the official 2025 Sportsman odds source into `data/utah/sportsman/sportsman_odds_2025.csv`.
  - Replaced the old pending/source-missing Sportsman path with a resident-only modeled Sportsman odds family.
- Files updated:
  - `engine/utah_draw_predictive/sportsman.py`
  - `engine/utah_draw_predictive/classifier.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - `docs/utah_draw_system_scope.md`
  - Focused Phase 11 Sportsman tests and artifact-validation tests
- Outputs refreshed:
  - `processed_data/sportsman_permit_predictions_v1.csv`
  - `processed_data/sportsman_permit_report.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
- Validation summary:
  - Python tests run: `93`
  - Python tests failed: `0`
  - Predictive rows: `27811`
  - `MODELED_BONUS` rows: `25291`
  - `MODELED_PREFERENCE` rows: `1731`
  - `MODELED_ALLOCATION` rows: `54`
  - `MODELED_AVAILABILITY` rows: `120`
  - `MODELED_SPORTSMAN_DRAW` rows: `10`
  - `IN_SCOPE_MODEL_PENDING` rows: `397`
  - `OUT_OF_SCOPE_NON_TARGET` rows: `198`
  - `SPORTSMAN_PERMIT` hunt codes: `10`
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Phase 11 results:
  - Sportsman permits now use the official Sportsman odds source and no longer depend on suffix-only detection or missing-source placeholders.
  - `BR1000`, `DB0007`, `RS0001`, and `TK0001` all classify correctly as `SPORTSMAN_PERMIT`.
  - Sportsman rows are resident-only and modeled with `p_sportsman_draw`, `p_draw`, and `p_draw_pct`.
  - Sportsman rows do not use `p_bonus_pool`, `p_random_pool`, or `p_preference_draw`.
  - `BR1000` is handled entirely through `SPORTSMAN_PERMIT`, not `BEAR_DRAW`.

## Phase 12 Bear Subtype Strategy
- Timestamp (UTC): 2026-05-21T00:00:00Z
- Scope:
  - Implemented Phase 12 for subtype-aware bear handling only in `C:\Users\tyler\Desktop\GitHub\HUNTS`.
  - Used `pipeline/RAW/hunt_unit_database/2026/pdf/draw_odds/2025 Black Bear Draw odds.pdf` and `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/black bear.csv` to lock subtype behavior.
  - Preserved Phase 11 Sportsman handling so `BR1000` stays outside `BEAR_DRAW`.
- Files updated:
  - `engine/utah_draw_predictive/bear.py`
  - `engine/utah_draw_predictive/classifier.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - `docs/utah_draw_system_scope.md`
  - Focused Phase 12 bear tests and artifact-validation tests
- Outputs refreshed:
  - `processed_data/bear_predictions_v1.csv`
  - `processed_data/bear_report.json`
  - `processed_data/bear_draw_predictions_v1.csv`
  - `processed_data/bear_draw_report.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
- Validation summary:
  - Python tests run: `97`
  - Python tests failed: `0`
  - Predictive rows: `27763`
  - `MODELED_BONUS` rows: `25233`
  - `MODELED_PREFERENCE` rows: `1731`
  - `MODELED_ALLOCATION` rows: `54`
  - `MODELED_AVAILABILITY` rows: `139`
  - `MODELED_SPORTSMAN_DRAW` rows: `10`
  - `IN_SCOPE_MODEL_PENDING` rows: `394`
  - `EXCLUDED_NOT_PREDICTIVE_DRAW` rows: `4`
  - `OUT_OF_SCOPE_NON_TARGET` rows: `198`
  - Bear predictive rows: `1305`
  - Bear modeled bonus rows: `1209`
  - Bear modeled availability rows: `19`
  - Bear pending rows: `73`
  - Bear excluded rows: `4`
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Phase 12 results:
  - `BR1000` remains Sportsman-only and is not overridden by bear logic.
  - `BR1001` is harvest-objective availability only and never receives draw-odds fields.
  - `BR1007` and `BR1018` are unlimited-pursuit availability only and never receive draw-odds fields.
  - Unit-specific pursuit rows are also surfaced as availability, not bonus draw odds.
  - Only true limited-entry bear rows remain in the bear bonus path, and bear rows never use preference fields.

## Phase 13 Mountain Lion / Cougar Rule-Status Strategy
- Timestamp (UTC): 2026-05-21T00:00:00Z
- Scope:
  - Completed Phase 13 for `MOUNTAIN_LION_DRAW` only in `C:\Users\tyler\Desktop\GitHub\HUNTS`.
  - Preserved Phase 12 bear behavior unchanged while tightening cougar report and coverage semantics.
  - Kept cougar in scope as a rule-status / availability family, not a draw-odds family.
- Files updated:
  - `engine/utah_draw_predictive/mountain_lion.py`
  - `engine/utah_draw_predictive/classifier.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - `docs/utah_draw_system_scope.md`
  - Focused Phase 13 mountain lion tests and artifact-validation tests
- Outputs refreshed:
  - `processed_data/mountain_lion_availability_predictions_v1.csv`
  - `processed_data/mountain_lion_availability_report.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
- Validation summary:
  - Python tests run: `101`
  - Python tests failed: `0`
  - Predictive rows: `27763`
  - `MODELED_BONUS` rows: `25233`
  - `MODELED_PREFERENCE` rows: `1731`
  - `MODELED_ALLOCATION` rows: `54`
  - `MODELED_AVAILABILITY` rows: `139`
  - `MODELED_SPORTSMAN_DRAW` rows: `10`
  - `IN_SCOPE_MODEL_PENDING` rows: `394`
  - `EXCLUDED_NOT_PREDICTIVE_DRAW` rows: `4`
  - `OUT_OF_SCOPE_NON_TARGET` rows: `198`
  - Mountain lion / cougar predictive rows: `120`
  - Mountain lion / cougar hunt codes: `60`
  - Mountain lion / cougar units: `60`
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Phase 13 results:
  - Cougar remains modeled as statewide OTC rule-status and availability, not draw odds.
  - No cougar row receives `p_draw`, `p_draw_pct`, `p_bonus_pool`, `p_random_pool`, or `p_preference_draw`.
  - Availability/status fields now explicitly carry permit/rule/season status semantics for the family report and coverage outputs.
  - Bear Phase 12 guardrails remained unchanged and passing.

## Phase 14 Private-Lands-Only Antlerless Elk Allocation / Availability Closeout
- Timestamp (UTC): 2026-05-21T00:00:00Z
- Scope:
  - Closed out `PRIVATE_LANDS_ONLY_ANTLERLESS_ELK` as an allocation / availability family in `C:\Users\tyler\Desktop\GitHub\HUNTS`.
  - Preserved all accepted bonus, preference, sportsman, bear-subtype, and mountain-lion behaviors.
  - Promoted the direct 2026 private-lands permit sheet as the allocation source for permit totals and season windows.
- Files updated:
  - `engine/utah_draw_predictive/private_lands_antlerless_elk.py`
  - `engine/utah_draw_predictive/classifier.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - `docs/utah_draw_system_scope.md`
  - Focused private-lands allocation tests and artifact-validation tests
- Outputs refreshed:
  - `processed_data/private_lands_antlerless_elk_predictions_v1.csv`
  - `processed_data/private_lands_antlerless_elk_allocations_v1.csv`
  - `processed_data/private_lands_antlerless_elk_report.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
- Validation summary:
  - Python tests run: `104`
  - Python tests failed: `0`
  - Predictive rows: `27763`
  - `MODELED_BONUS` rows: `25233`
  - `MODELED_PREFERENCE` rows: `1731`
  - `MODELED_ALLOCATION` rows: `54`
  - `MODELED_AVAILABILITY` rows: `139`
  - `MODELED_SPORTSMAN_DRAW` rows: `10`
  - `IN_SCOPE_MODEL_PENDING` rows: `394`
  - `EXCLUDED_NOT_PREDICTIVE_DRAW` rows: `4`
  - `OUT_OF_SCOPE_NON_TARGET` rows: `198`
  - Private-lands-only antlerless elk reviewed rows: `27`
  - Private-lands-only antlerless elk predictive rows: `54`
  - Private-lands-only antlerless elk hunt codes: `27`
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Phase 14 results:
  - Private-lands-only antlerless elk is now closed out as `MODELED_ALLOCATION`, not preference or bonus draw odds.
  - No private-lands-only row receives `p_draw`, `p_draw_pct`, `p_preference_draw`, `p_bonus_pool`, or `p_random_pool`.
  - `permits_allotted` and season dates come from the direct 2026 private-lands permit source, while remaining/availability probability fields stay blank when the source cannot defensibly support them.
  - Coverage now reports private-lands-only rows as modeled allocation rather than pending, and normal antlerless elk preference remains separate and passing.

## Phase 15 Youth General Deer + Youth Any-Bull Elk Separation / Pending Strategy
- Timestamp (UTC): 2026-05-20T23:59:00Z
- Scope:
  - Implemented the youth-family classifier and reporting pass in `C:\Users\tyler\Desktop\GitHub\HUNTS`.
  - Kept youth general deer and youth any-bull elk in scope without forcing them into adult general deer, antlerless elk, or OIL / LE / PLE bonus logic.
  - Surfaced current-year youth elk rows as explicit pending predictive rows with no fake draw odds.
  - Preserved all accepted bonus, preference, sportsman, bear-subtype, private-lands-only, and mountain-lion behaviors.
- Files updated:
  - `engine/utah_draw_predictive/youth.py`
  - `engine/utah_draw_predictive/classifier.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - `docs/utah_draw_system_scope.md`
  - Focused youth strategy / coverage / materialization tests
- Outputs refreshed:
  - `processed_data/youth_draw_predictions_v1.csv`
  - `processed_data/youth_draw_report.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
- Validation summary:
  - Python tests run: `111`
  - Python tests failed: `0`
  - Predictive rows: `27767`
  - `MODELED_BONUS` rows: `25233`
  - `MODELED_PREFERENCE` rows: `1731`
  - `MODELED_ALLOCATION` rows: `54`
  - `MODELED_AVAILABILITY` rows: `139`
  - `MODELED_SPORTSMAN_DRAW` rows: `10`
  - `IN_SCOPE_MODEL_PENDING` rows: `398`
  - `EXCLUDED_NOT_PREDICTIVE_DRAW` rows: `4`
  - `OUT_OF_SCOPE_NON_TARGET` rows: `198`
  - Youth general deer reviewed rows: `4853`
  - Youth general deer active predictive rows: `0`
  - Youth any-bull elk reviewed rows: `74`
  - Youth any-bull elk active predictive rows: `4`
  - Duplicate key count on `hunt_code,residency,points`: `0`
- Phase 15 results:
  - Youth general deer and youth any-bull elk now classify as their own in-scope families.
  - No youth row receives `p_draw`, `p_draw_pct`, `p_preference_draw`, `p_bonus_pool`, or `p_random_pool`.
  - Youth elk is surfaced from the current-year youth source as pending because quota/mechanics are not yet defensible.
  - Youth deer remains separate from adult general deer, but no active 2026 predictive youth-deer rows are created because the current-year source surface does not cleanly separate a youth pool from shared general-season permit rows.

## Online Runtime Sync + Final Cross-Checks
- Timestamp (UTC): 2026-05-21T07:00:00Z
- Scope:
  - Synced the Hunt Research support files in `C:\Users\tyler\Desktop\GitHub\HUNTS` so predictive-only groups are now present in the online runtime layer.
  - Preserved all accepted predictive family math while fixing the website-facing ladder/master/reference mismatch around Sportsman, mountain lion availability, dedicated hunter draw pools, and youth elk pending rows.
  - Added a frontend fallback so non-point families still render summary cards even when no exact point row exists.
- Files updated:
  - `scripts/sync_online_runtime_from_predictive.py`
  - `hunt-research.js`
  - `config.js`
  - `scripts/build-pages-dist.js`
  - `processed_data/hunt_master_enriched.csv`
  - `processed_data/hunt_unit_reference_linked.csv`
  - `processed_data/point_ladder_view.csv`
  - `processed_data/online_runtime_crosscheck.json`
  - `processed_data/online_runtime_crosscheck.md`
  - Focused runtime sync / frontend fallback tests
- Outputs refreshed:
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/hunt_master_enriched.csv`
  - `processed_data/hunt_unit_reference_linked.csv`
  - `processed_data/point_ladder_view.csv`
  - `processed_data/online_runtime_crosscheck.json`
  - `processed_data/online_runtime_crosscheck.md`
- Validation summary:
  - Python tests run: `118`
  - Python tests failed: `0`
  - Online runtime cross-check status: `PASS`
  - Engine groups: `2007`
  - Missing engine groups after sync:
    - ladder: `0`
    - master: `0`
    - reference: `0`
  - Duplicate key count in synced runtime files:
    - ladder `(hunt_code,residency,points,draw_pool)`: `0`
    - master `(hunt_code,residency,points,draw_pool)`: `0`
    - reference `(hunt_code,residency,draw_pool)`: `0`
  - Pages build:
    - `pages-dist` build completed successfully
    - large runtime files still exceed the 25 MiB Pages cap and rely on the existing Cloudflare object fallback
- Results:
  - Sportsman groups now exist in ladder/master/reference with `draw_pool=sportsman`.
  - Mountain lion availability groups now exist in ladder/master/reference and remain availability-only.
  - Dedicated Hunter draw-pool groups now exist in the master/reference layer instead of collapsing back to standard deer rows.
  - Youth elk pending groups now exist in ladder/master/reference and remain in-scope without fake draw odds.
  - Hunt Research now falls back to the first engine group row for non-point families before dropping to ladder-only summary behavior.

## Limited Entry Buck Pronghorn Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:00:00Z
- Scope:
  - Added the user-verified 2025-to-2026 limited-entry buck pronghorn permit table as a normalized truth-source CSV.
  - Generated a row-by-row and group-level audit against the current 2026 linked hunt reference.
  - Kept the work isolated to truth-source normalization and audit outputs only.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_limited_entry_buck_pronghorn_permits.csv`
  - `processed_data/le_buck_pronghorn_truth_source_audit.csv`
  - `processed_data/le_buck_pronghorn_truth_source_audit.json`
  - `WORK_LOG.md`
- Validation summary:
  - Python smoke tests run: `6`
  - Python smoke tests failed: `0`
  - Truth rows normalized: `66`
  - Unique hunt codes audited: `66`
  - Repo-side 2026 row mismatches: `0`
- Results:
  - All current repo-side 2026 limited-entry buck pronghorn values matched the supplied truth table.
  - The largest group increase was `Parker Mtn`, moving from `200` total permits in 2025 to `250` in 2026.
  - Other major shifts were `West Desert, Snake Valley` from `120` to `132`, `Fillmore, Oak Creek South` from `75` to `85`, `North Slope, Three Corners/West Daggett` from `64` to `54`, and `Vernal` from `110` to `100`.
  - The normalized audit cleanly separates unchanged groups from minor, significant, and major permit changes for downstream review.

## Doe Pronghorn Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T00:30:00Z
- Scope:
  - Added the user-verified 2025-to-2026 doe pronghorn permit table as a normalized truth-source CSV, including 2026 season dates.
  - Generated a row-by-row and group-level audit against the current 2026 linked hunt reference.
  - Kept the work isolated to truth-source normalization and audit outputs only.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_doe_pronghorn_permits.csv`
  - `processed_data/doe_pronghorn_truth_source_audit.csv`
  - `processed_data/doe_pronghorn_truth_source_audit.json`
  - `WORK_LOG.md`
- Validation summary:
  - Python smoke tests run: `6`
  - Python smoke tests failed: `0`
  - Truth rows normalized: `16`
  - Unique hunt codes audited: `16`
  - Repo-side 2026 row mismatches: `13`
- Results:
  - The current linked reference does not yet match the supplied doe-pronghorn truth table.
  - The affected hunt codes are `PD1000`, `PD1012`, `PD1017`, `PD1039`, `PD1044`, `PD1057`, and `PD1059`.
  - The largest group decrease was `Box Elder, Snowville`, moving from `80` total permits in 2025 to `40` in 2026.
  - `Panguitch Lake/Zion, North` appears as a new 2026 quota row at `40` total permits and is absent from the current linked reference.
  - Other notable changes were `Box Elder, West` from `55` to `35`, `Vernal-Ouray Valley` from `10` to `5`, `Parker Mtn, Highlands` from `75` to `70`, and `Parker Mtn, Plains` from `70` to `75`.

## Antlerless Deer Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T01:00:00Z
- Scope:
  - Added the user-verified 2025-to-2026 antlerless deer permit table as a normalized truth-source CSV, including 2026 season dates.
  - Generated a hunt-code-level total-permit audit against the current 2026 linked hunt reference.
  - Kept the work isolated to truth-source normalization and audit outputs only.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_antlerless_deer_permits.csv`
  - `processed_data/antlerless_deer_truth_source_audit.csv`
  - `processed_data/antlerless_deer_truth_source_audit.json`
  - `WORK_LOG.md`
- Validation summary:
  - Python smoke tests run: `6`
  - Python smoke tests failed: `0`
  - Truth rows normalized: `17`
  - Unique hunt codes audited: `17`
  - Repo-side 2026 row mismatches: `4`
- Results:
  - The current linked reference matches most of the supplied antlerless-deer truth table, but it still disagrees on `DA1009`, `DA1018`, and `DA1033`, and it is missing `DA1051`.
  - `Beaver City` appears as a new 2026 row at `10` total permits after normalizing the 2025 dashes to zero for audit use.
  - `Pine Valley, Enterprise` dropped from `25` to `20`, and `Pine Valley, New Harmony` dropped from `20` to `15`.
  - `San Juan, Monticello` hunt `DA1033` increased from `5` to `10`.
  - Grand total moved from `340` permits in 2025 to `345` in 2026.

## Antlerless Elk Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T01:30:00Z
- Scope:
  - Added the user-verified 2025-to-2026 standard antlerless elk permit table as a normalized truth-source CSV with season dates and residency splits.
  - Added the user-verified 2025-to-2026 private-lands-only antlerless elk permit table as a separate normalized truth-source CSV.
  - Generated separate audits for the standard antlerless-elk surface and the private-lands-only surface against the current 2026 linked hunt reference.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_antlerless_elk_permits.csv`
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_private_lands_only_antlerless_elk_permits.csv`
  - `processed_data/antlerless_elk_truth_source_audit.csv`
  - `processed_data/antlerless_elk_truth_source_audit.json`
  - `processed_data/private_lands_antlerless_elk_truth_source_audit.csv`
  - `processed_data/private_lands_antlerless_elk_truth_source_audit.json`
  - `WORK_LOG.md`
- Validation summary:
  - Python smoke tests run: `6`
  - Python smoke tests failed: `0`
  - Standard antlerless elk truth rows normalized: `116`
  - Standard antlerless elk repo-side mismatch rows: `74`
  - Private-lands-only antlerless elk truth rows normalized: `26`
  - Private-lands-only antlerless elk repo-side mismatch rows: `5`
- Results:
  - The standard antlerless-elk linked reference is still stale for many of the largest 2026 changes and several new 2026 rows.
  - The affected standard antlerless-elk hunt codes include `EA1007`, `EA1010`, `EA1011`, `EA1021`, `EA1033`, `EA1035`, `EA1053`, `EA1054`, `EA1063`, `EA1069`, `EA1193`, `EA1208`, `EA1222`, `EA1223`, `EA1251`, `EA1266`, `EA1267`, `EA1269`, `EA1284`, `EA1285`, `EA1286`, `EA1287`, `EA1288`, `EA1289`, `EA1290`, `EA1291`, `EA1292`, `EA1293`, `EA1294`, `EA1295`, `EA1296`, `EA1297`, `EA1298`, `EA1299`, `EA1300`, `EA2033`, and `EA2036`.
  - The largest standard-antlerless increases were `EA1007` Wasatch Mtns, Currant Creek from `0` to `200`, `EA1267` Cache from `90` to `200`, `EA1269` Ogden (excludes Hyrum) from `200` to `300`, and multiple new Wasatch / Manti / Mt Dutton rows promoted from zero in 2025 to active 2026 quotas.
  - Major standard-antlerless decreases include `EA2033` Kamas archery from `250` to `200`, `EA1033` Kamas from `125` to `100`, `EA1035` Kamas, Oakley from `125` to `100`, and `EA1069` Panguitch Lake from `35` to `25`.
  - The private-lands-only mismatch cluster is narrower and limited to `EA2012`, `EA2015`, `EA2016`, `EA2027`, and `EA2046`.
  - The largest private-lands-only moves were `EA2012` Wasatch Mtns, West-Central from `400` to `500`, `EA2027` Cache from `300` to `250`, `EA2016` Nebo from `275` to `325`, `EA2046` Box Elder, Sawtooth from `25` to `50`, and `EA2015` Paunsaugunt from `100` to `75`.

## Antlerless Elk Control Unit Truth-Source Overlay
- Timestamp (UTC): 2026-05-22T02:00:00Z
- Scope:
  - Added the user-verified 2026 antlerless elk control-unit list as a normalized truth-source CSV.
  - Mapped each listed control unit against the normalized standard antlerless elk and private-lands-only antlerless elk truth-source tables.
  - Generated an audit showing which hunt codes currently fall under each control unit.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_antlerless_elk_control_units.csv`
  - `processed_data/antlerless_elk_control_unit_audit.csv`
  - `processed_data/antlerless_elk_control_unit_audit.json`
  - `WORK_LOG.md`
- Validation summary:
  - Python smoke tests run: `6`
  - Python smoke tests failed: `0`
  - Control units listed: `9`
  - Control units matched to normalized 2026 truth rows: `8`
  - Unmatched control units: `Henry Mtns`
- Results:
  - `Box Elder, Grouse Creek` is correctly captured as a new control unit and maps to antlerless elk hunt code `EA1287`.
  - `Chalk Creek`, `East Canyon`, `Kamas`, `Morgan-South Rich`, `Pine Valley`, and `Zion` all map into both the standard antlerless elk and private-lands-only antlerless elk truth surfaces.
  - `Ogden` maps into the standard antlerless elk surface through `EA1063`, `EA1064`, and `EA1269`.
  - `Henry Mtns` does not currently map to any normalized 2026 antlerless elk or private-lands-only antlerless elk truth rows and should be treated as an unmatched control-unit note until a corresponding permit row is surfaced.

## Antlerless Moose Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T02:15:00Z
- Scope:
  - Added the user-verified 2025-to-2026 antlerless moose permit table as a normalized truth-source CSV with season dates and residency splits.
  - Generated a row-by-row audit against the current 2026 linked hunt reference.
  - Kept the work isolated to truth-source normalization and audit outputs only.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_antlerless_moose_permits.csv`
  - `processed_data/antlerless_moose_truth_source_audit.csv`
  - `processed_data/antlerless_moose_truth_source_audit.json`
  - `WORK_LOG.md`
- Validation summary:
  - Python smoke tests run: `6`
  - Python smoke tests failed: `0`
  - Truth rows normalized: `3`
  - Unique hunt codes audited: `3`
  - Repo-side 2026 row mismatches: `0`
- Results:
  - All current linked-reference antlerless moose values match the supplied 2026 truth table.
  - `Morgan-South Rich` remains unchanged in both any-legal-weapon and archery surfaces.
  - `Wasatch Mtns, Salt Lake-Timpanogos` remains unchanged at `5` total permits.
  - Grand total remains unchanged from `15` in 2025 to `15` in 2026.

## Ewe Rocky Mountain Bighorn Sheep Truth-Source Normalization
- Timestamp (UTC): 2026-05-22T02:30:00Z
- Scope:
  - Added the user-verified 2025-to-2026 ewe Rocky Mountain bighorn sheep permit table as a normalized truth-source CSV with season dates and residency splits.
  - Generated a row-by-row audit against the current 2026 linked hunt reference.
  - Kept the work isolated to truth-source normalization and audit outputs only.
- Files updated:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026_rac_ewe_rocky_mountain_bighorn_sheep_permits.csv`
  - `processed_data/ewe_rocky_sheep_truth_source_audit.csv`
  - `processed_data/ewe_rocky_sheep_truth_source_audit.json`
  - `WORK_LOG.md`
- Validation summary:
  - Python smoke tests run: `6`
  - Python smoke tests failed: `0`
  - Truth rows normalized: `1`
  - Unique hunt codes audited: `1`
  - Repo-side 2026 row mismatches: `0`
- Results:
  - All current linked-reference ewe Rocky Mountain bighorn sheep values match the supplied 2026 truth table.
  - `Box Elder, Newfoundland Mtn` remains unchanged at `5` total permits.
  - Grand total remains unchanged from `5` in 2025 to `5` in 2026.

## 2026 Permit Truth-Source Promotion
- Timestamp (UTC): 2026-05-22T09:00:00Z
- Scope:
  - Added `engine/utah/truth_source_promotion.py` as the reusable promotion and re-audit module for 2026 RAC permit truth tables.
  - Promoted corrected 2026 permit counts into the live runtime CSV surfaces:
    - `processed_data/hunt_unit_reference_linked.csv`
    - `processed_data/hunt_master_enriched.csv`
    - `processed_data/point_ladder_view.csv`
    - `processed_data/draw_reality_engine.csv`
  - Regenerated audits for doe pronghorn, antlerless deer, standard antlerless elk, private-lands-only antlerless elk, antlerless moose, ewe Rocky Mountain bighorn sheep, and the antlerless elk control-unit overlay.
  - Added targeted tests for truth-source promotion, metadata propagation, private-lands-only structure, and control-unit overlay handling.
- Files updated:
  - `engine/utah/truth_source_promotion.py`
  - `tests/utah/test_truth_source_promotion.py`
  - `docs/data_feed_contract.md`
  - `docs/predictive_engine_design.md`
  - `processed_data/hunt_unit_reference_linked.csv`
  - `processed_data/hunt_master_enriched.csv`
  - `processed_data/point_ladder_view.csv`
  - `processed_data/draw_reality_engine.csv`
  - `processed_data/truth_source_promotion_summary.json`
  - `processed_data/doe_pronghorn_truth_source_audit.csv`
  - `processed_data/doe_pronghorn_truth_source_audit.json`
  - `processed_data/antlerless_deer_truth_source_audit.csv`
  - `processed_data/antlerless_deer_truth_source_audit.json`
  - `processed_data/antlerless_elk_truth_source_audit.csv`
  - `processed_data/antlerless_elk_truth_source_audit.json`
  - `processed_data/private_lands_antlerless_elk_truth_source_audit.csv`
  - `processed_data/private_lands_antlerless_elk_truth_source_audit.json`
  - `processed_data/antlerless_moose_truth_source_audit.csv`
  - `processed_data/antlerless_moose_truth_source_audit.json`
  - `processed_data/ewe_rocky_sheep_truth_source_audit.csv`
  - `processed_data/ewe_rocky_sheep_truth_source_audit.json`
  - `processed_data/antlerless_elk_control_unit_audit.csv`
  - `processed_data/antlerless_elk_control_unit_audit.json`
  - `WORK_LOG.md`
- Validation summary:
  - Targeted promotion tests passed: `20`
  - Corrected-family mismatches after promotion:
    - doe pronghorn: `0`
    - antlerless deer: `0`
    - standard antlerless elk: `0`
    - private-lands-only antlerless elk: `0`
    - antlerless moose: `0`
    - ewe Rocky Mountain bighorn sheep: `0`
  - Private-lands-only duplicated-by-residency structural errors after promotion: `0`
- Runtime promotion results:
  - Doe pronghorn rows corrected from stale overlay values and `PD1039` was added to all runtime surfaces.
  - Antlerless deer rows corrected and `DA1051` was added to all runtime surfaces.
  - Standard antlerless elk rows were corrected across large quota shifts and the missing 2026 rows such as `EA1287`, `EA1288`, `EA1289`, `EA1290`, `EA1291`, `EA1292`, `EA1293`, `EA1294`, `EA1295`, `EA1296`, `EA1297`, `EA1298`, `EA1299`, and `EA1300` were added where supported by the truth source.
  - Private-lands-only antlerless elk rows were converted to explicit availability-only runtime handling with:
    - `hunt_category = PRIVATE_LANDS_ONLY_ANTLERLESS_ELK`
    - `draw_model_class = AVAILABILITY_ONLY`
    - `probability_model = NONE`
    - no duplicated total values in `public_permits_2026` across resident and nonresident rows
  - Corrected and added rows now carry truth-source metadata including `permit_source`, `quota_source`, `truth_source_file`, `truth_source_status`, `data_quality_grade`, and `reason_codes`.
- Locked families preserved:
  - Limited-entry bull elk HAMSS / September archery remains clean.
  - Limited-entry buck pronghorn remains clean.
  - Antlerless moose remains zero mismatch.
  - Ewe Rocky Mountain bighorn sheep remains zero mismatch.
- Control-unit overlay handling:
  - `Box Elder, Grouse Creek` remains marked `new_this_year = YES` and maps to `EA1287`.
  - `Henry Mtns` remains an unresolved control-unit overlay item with no fabricated 2026 permit row.

## MODELED_AVAILABILITY Final Consistency Review
- Timestamp (UTC): 2026-05-23T02:40:00Z
- Scope:
  - Added a dedicated modeled-availability review CLI and report artifacts.
  - Preserved availability-only semantics while adding explicit availability metadata and reason codes to mountain lion/cougar and bear availability rows.
  - Extended the draw-system coverage report with a dedicated `modeled_availability` summary block.
  - Verified that availability rows do not receive draw-probability, bonus, or preference fields.
- Files updated:
  - `engine/utah_draw_predictive/__init__.py`
  - `engine/utah_draw_predictive/availability_review.py`
  - `engine/utah_draw_predictive/classifier.py`
  - `engine/utah_draw_predictive/mountain_lion.py`
  - `engine/utah_draw_predictive/bear.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - `docs/utah_draw_system_scope.md`
  - `docs/utah_bonus_predictive_engine.md`
  - `docs/data_feed_contract.md`
  - `docs/predictive_engine_design.md`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/draw_system_coverage_report.csv`
  - `processed_data/draw_system_coverage_report.json`
  - `processed_data/utah_bonus_predictive_manifest.json`
  - `processed_data/gpt_work_review_report.json`
  - `processed_data/gpt_work_review_report.md`
  - `processed_data/mountain_lion_availability_report.json`
  - `processed_data/mountain_lion_availability_predictions_v1.csv`
  - `processed_data/bear_report.json`
  - `processed_data/modeled_availability_review_report.json`
  - `processed_data/modeled_availability_review_report.md`
  - `tests/utah_draw_predictive/test_draw_system_coverage_report.py`
  - `tests/utah_draw_predictive/test_modeled_availability_semantics.py`
  - `tests/utah_draw_predictive/test_modeled_availability_report.py`
  - `tests/utah_bonus_predictive/test_final_artifact_guardrails.py`
- Validation summary:
  - Materialize command passed for `forecast_year=2026` and `history_years=2021,2022,2023,2024,2025`.
  - Classifier coverage rebuild passed.
  - Availability review CLI passed and wrote both JSON and Markdown reports.
  - `tests/utah_draw_predictive`: `95 passed`
  - `tests/utah_bonus_predictive`: `28 passed` across file-by-file execution
  - `tests/utah/test_frontend_probability_selection.py`: `22 passed`
  - Combined focused-suite total: `145 passed`, `0 failed`
  - `node --check hunt-research.js`: passed
  - `python -m compileall engine tests`: passed
- Results:
  - Live predictive artifacts currently contain `124` `MODELED_AVAILABILITY` rows, not `139`.
  - The full live availability breakdown is:
    - `120` mountain lion / cougar availability rows
    - `4` bear availability rows
    - `0` other availability rows
  - The earlier `139` count was confirmed to be a stale prior review reference, not an unexplained third availability family.
  - All live `MODELED_AVAILABILITY` rows now carry explicit `reason_codes`.
  - All live `MODELED_AVAILABILITY` rows now carry `probability_model = NONE`.
  - All live `MODELED_AVAILABILITY` rows keep `p_draw`, `p_draw_pct`, `p_preference_draw`, `p_bonus_pool`, and `p_random_pool` null.
  - Bear availability/status semantics remain:
    - `BR1001` harvest-objective availability
    - `BR1007` unlimited pursuit availability
    - `BR1018` unlimited pursuit availability
  - Mountain lion / cougar remains modeled as availability/status only with no draw-odds fields.

## Canonical Database Vs Modeled Hunt-Code Reconciliation
- Timestamp (UTC): 2026-05-23T03:45:00Z
- Scope:
  - Added a dedicated reconciliation audit that compares the canonical database hunt-code universe against modeled and coverage hunt-code universes.
  - Generated bucketed gap artifacts for:
    - `in_database_and_modeled`
    - `in_database_not_modeled`
    - `modeled_not_in_database`
    - `coverage_seen_not_in_database`
    - `historical_or_observed_only`
    - `pending_or_non_probability_status`
    - `out_of_scope_or_excluded`
  - Added focused tests to lock canonical-count discovery, gap math, and reason coverage for every database-not-modeled hunt code.
- Files updated:
  - `engine/utah_draw_predictive/database_hunt_code_model_gap.py`
  - `processed_data/database_hunt_code_model_gap.csv`
  - `processed_data/database_hunt_code_model_gap.json`
  - `processed_data/database_hunt_code_model_gap.md`
  - `tests/utah_draw_predictive/test_database_hunt_code_model_gap.py`
  - `WORK_LOG.md`
- Validation summary:
  - Reconciliation generator command completed and wrote all three artifacts.
  - Focused reconciliation tests: `6 passed`
  - Full focused suite:
    - `tests/utah_bonus_predictive`
    - `tests/utah_draw_predictive`
    - `tests/utah/test_frontend_probability_selection.py`
    - Result: `158 passed`, `0 failed`
- Results:
  - Canonical database file used: `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
  - Canonical database unique hunt-code count: `1394`
  - Modeled target hunt-code count: `1021`
  - Database-to-modeled gap: `373`
  - Coverage target-scope hunt-code count: `1668`
  - Coverage-to-database overage: `274`
  - The audit did not find a canonical database candidate with exactly `1294` unique hunt codes in this repo snapshot and recorded that discrepancy explicitly in the report.

## 2026 RAC Current-Year Allotment Overlay
- Timestamp (UTC): 2026-05-23T00:00:00Z
- Scope:
  - Added explicit current-year available-permit/allotment fields to the runtime CSV surfaces so 2026 RAC allotments are not confused with 2025 draw-result permit fields.
  - Wired RAC direct hunt-code allotments into the active bonus-draw quota path so max-point pool, random pool, cutoff, and draw probability calculations use RAC 2026 permit values when available.
  - Created `scripts/apply-current-year-permit-allotments.py` to read direct hunt-code rows from normalized `2026_rac_*.csv` tables.
  - Populated:
    - `permit_allotment_2026_res`
    - `permit_allotment_2026_nr`
    - `permit_allotment_2026_total`
    - `permit_allotment_2026_source`
    - `permit_allotment_2026_source_file`
    - `permit_allotment_2026_status`
  - RAC direct hunt-code rows use `permit_allotment_2026_source = 2026_RAC_CURRENT_YEAR_ALLOTMENT`.
  - Rows without direct RAC support fall back to existing `permits_2026_*` values and are marked `FALLBACK_EXISTING_2026_PERMITS`.
  - Total-only RAC rows keep resident/nonresident allotment fields blank rather than inventing a split.
- Key checks:
  - `EA1267` now carries RAC current-year allotment `180 / 20 / 200`.
  - `EA2012` private-lands-only antlerless elk carries total-only allotment `500` with blank resident/nonresident allotment fields.
  - `DA1009` antlerless deer carries total-only allotment `25`.
  - `EB3024` uses RAC current-year allotment `9 / 1 / 10`; Resident quota behavior uses `9`, resulting in `quota_2026_max_pool = 5` and `quota_2026_random_pool = 4`.
  - `EB3022` uses RAC current-year allotment `130 / 15 / 145`; Resident quota behavior uses `130`, resulting in `quota_2026_max_pool = 65` and `quota_2026_random_pool = 65`.
  - `BR1008` uses fallback existing 2026 permit fields because there is no direct RAC row.
- Outputs:
  - `processed_data/current_year_permit_allotment_overlay_dry_run.json`
  - `processed_data/current_year_permit_allotment_overlay_dry_run_summary.csv`
  - `processed_data/current_year_permit_allotment_overlay_write.json`
  - `processed_data/current_year_permit_allotment_overlay_write_summary.csv`
  - `processed_data/current_year_permit_allotment_rac_index.csv`
- Validation:
  - Focused current-year allotment tests were added in `tests/utah/test_current_year_permit_allotments.py`.
  - Probability formulas and frontend odds formatting were not changed; current-year RAC allotments now feed the existing quota-driven draw-odds behavior.

## Point Ladder Max-Point Vs Random-Pool Display Correction
- Timestamp (UTC): 2026-05-23T04:30:00Z
- Scope:
  - Corrected the point ladder presentation so DWR historical point-row successes remain historical draw results and do not become 2026 max-point guarantees.
  - Added a reusable enrichment step that joins `point_ladder_view.csv` to `draw_reality_engine_v2.csv` and `draw_reality_engine_predictive_v2.csv`.
  - Added DWR historical fields, max-point boundary fields, pool-zone classification, and display-only ladder columns.
  - Updated frontend ladder labels from `2025 Actual Odds` to `2025 Draw Results` and from `2026 Max Pool` to `2026 Max Point Pool`.
- Files updated:
  - `engine/utah/point_ladder_pool.py`
  - `hunt-research.js`
  - `research.html`
  - `processed_data/point_ladder_view.csv`
  - `tests/utah/test_frontend_probability_selection.py`
  - `tests/utah/test_point_ladder_pool_display.py`
  - `WORK_LOG.md`
- EB3024 resident verification:
  - `max_point_pool_boundary = 29`
  - `random_pool_start_point = 28`
  - 30 and 29 points show `2026 Max Point Pool = ~1 in 1 or 100%`.
  - 28 and below are random-pool rows for 2026 random-draw display.
  - 12 points preserves the 2025 DWR random-pool success as `~1 in 49.0 or 2.0%` while using predictive `p_random_pool` for 2026 Random Draw.
- Validation status:
  - Enrichment command completed for source year `2025`.
  - Focused regression tests were added; final command results are recorded in the assistant closeout for this task.

## Bonus-Point Rollover And Mixed Cutoff Prediction Correction
- Timestamp (UTC): 2026-05-23T05:20:00Z
- Scope:
  - Refined the Utah bonus-point predictive builder so 2026 forecasts use a rolled-forward applicant stack instead of hard-coding the 2025 cutoff.
  - Successful max-point and random-pool applicants are removed; unsuccessful applicants advance by one bonus point with inferred retention; lower-point additions are estimated from observed transitions.
  - Official 2026 quota splits are applied with `quota_source_status = official`.
  - Recomputed max-point zones now distinguish `max_pool_guaranteed`, `max_pool_cutoff_mixed`, and `random_pool`.
  - Added explicit `p_max_pool_mean`, `p_random_mean`, `p_draw_mean`, `point_pool_zone`, quota status, rollover source year, retention, and reason-code metadata to runtime outputs.
- Files updated:
  - `scripts/build_predictive_bonus_engine_v1.py`
  - `engine/utah_bonus_predictive/cohort_forecast.py`
  - `engine/utah_bonus_predictive/forecast.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - `engine/utah_bonus_predictive/rules.py`
  - `engine/utah/materialize.py`
  - `engine/utah/point_ladder_pool.py`
  - `HYBRID_ML_V1.md`
  - `ENGINE_RULES_SPEC.md`
  - `processed_data/ml_draw_predictions_v1.csv`
  - `processed_data/draw_reality_engine_predictive_v2.csv`
  - `processed_data/point_ladder_view.csv`
  - `data_model/runtime_drafts/predictive_bonus_engine_2026.predictions.csv`
  - `data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv`
  - `data_model/runtime_drafts/predictive_bonus_engine_2026.audit.csv`
  - `tests/utah_bonus_predictive/test_eb3024_fixture.py`
  - `tests/utah/test_point_ladder_pool_display.py`
- EB3024 resident verification after correction:
  - 2026 rolled-forward stack has 2 applicants at 30 points and 21 applicants at 29 points.
  - 30 points is `max_pool_guaranteed` with `p_max_pool_mean = 1.000000`.
  - 29 points is `max_pool_cutoff_mixed` with `p_max_pool_mean = 0.142857` and modeled random fallback.
  - 28 points and below are `random_pool` rows with modeled random-draw values.
  - 2025 historical random successes remain in `2025 Draw Results` only.

## 2025 Limited Entry Elk Permit Reconciliation Utility
- Timestamp (UTC): 2026-05-23T06:00:00Z
- Scope:
  - Added `scripts/reconcile-le-elk-2025-permits.js` to reconcile 2025 LE Elk patch values into the canonical database and runtime/catalog files.
  - Added dry-run and write commands in `package.json`.
  - The utility patches only EB-code/LE Elk rows, preserves 2026 official permit columns, adds missing runtime draw-result columns when needed, writes timestamp backups before write-mode changes, and emits reconciliation reports.
- Current blocker:
  - Required input `processed_data/le_elk_2025_database_patch.csv` was not present in this repo snapshot.
  - The utility now writes explicit dry-run/write reports and exits nonzero when that required patch source is missing rather than fabricating values.

## Official 2026 Quota Input Verification
- Timestamp (UTC): 2026-05-23T06:45:00Z
- Scope:
  - Verified the official 2026 permit allotment source as `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`.
  - Added explicit quota provenance and allocation fields to bonus predictive rows:
    - `quota_2026_total`
    - `quota_2026_max_pool`
    - `quota_2026_random_pool`
    - `quota_source_status`
    - `quota_source_year`
    - `quota_source_file`
    - projected 2026 cutoff / random-pool-start fields
    - max-point, mixed-cutoff, and random-pool boolean flags
  - Fixed formal materialization so processed outputs preserve the official 2026 quota values instead of relabeling 2025 historical totals as 2026 public permits.
  - Added a source snapshot/debug UI field that displays `2026 quota source: official`.
  - Added regression coverage using `EB3022 Resident`, where the 2025 draw-result quota was `160` and the official 2026 quota is `130`.
- Validation summary:
  - `processed_data/ml_draw_predictions_v1.csv`, `processed_data/draw_reality_engine_predictive_v2.csv`, and `processed_data/point_ladder_view.csv` now include the required quota fields.
  - `EB3022 Resident` now reports `public_permits_2025 = 160`, `public_permits_2026 = 130`, `quota_2026_max_pool = 65`, and `quota_2026_random_pool = 65`.
  - Official quota rows join back to `DATABASE.csv` by `hunt_code + residency` with zero quota mismatches.
  - Historical 2025 random-pool draw results are not copied into 2026 random-draw prediction cells.
  - Focused quota/frontend/ladder tests passed, and all `tests/utah_bonus_predictive` tests passed when run in split chunks.

## Compiled 2026 Allotment Vs 2025 Draw-Available Comparison
- Timestamp (UTC): 2026-05-23T07:10:00Z
- Scope:
  - Compared `pipeline/RAW/hunt_unit_database/2026/csv/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED_V3.csv` against current compiled 2026 quota outputs.
  - Aggregated 2025 draw-available permits by `hunt_code + residency` from the aligned point-level draw file.
  - Compared against `processed_data/ml_draw_predictions_v1.csv` compiled 2026 quota values, with `DATABASE.csv` as a fallback only when a key was absent from compiled predictions.
  - Wrote:
    - `processed_data/compiled_2026_allotment_vs_2025_draw_available_significant_differences.csv`
    - `processed_data/compiled_2026_allotment_vs_2025_draw_available_significant_differences.json`
- Result:
  - Significant threshold used: absolute permit delta greater than `5`.
  - Significant differences found: `250`.
  - Increases: `222`.
  - Decreases: `28`.
  - Species breakdown: Deer `175`, Elk `48`, Turkey `11`, Pronghorn `11`, Bison `3`, Black Bear `2`.
  - Largest increase: `DB1556 Resident` Wasatch Mtns, West late any-legal-weapon deer, `3207 -> 4590`, delta `+1383`.
  - Largest decrease: `DB1775 Resident` Fillmore dedicated hunter deer, `159 -> 38`, delta `-121`.

## 2026 RAC Current-Year Permit Allotment Promotion And Engine Reconciliation
- Timestamp (UTC): 2026-05-23T08:35:00Z
- Scope:
  - Treated normalized `2026_rac_*.csv` files as the canonical current-year allotment source for 2026 draw/hunt permit availability when a direct `hunt_code` row is present.
  - Promoted direct RAC current-year values into `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` and canonical/feed files.
  - Preserved total-only rows without inventing resident/nonresident splits.
  - Kept unit-level/category/shared RAC rows in cumulative audit outputs without blindly expanding them into hunt-code database rows.
  - Wired RAC current-year allotments into the bonus prediction quota path so max-point pool, random pool, cutoffs, and `p_draw_mean` use the current allotment when present.
- Key implementation files:
  - `engine/utah/current_year_allotments.py`
  - `scripts/promote-rac-current-year-allotments-to-database.py`
  - `scripts/apply-current-year-permit-allotments.py`
  - `scripts/build_predictive_bonus_engine_v1.py`
  - `engine/utah_bonus_predictive/materialize.py`
  - `engine/utah_bonus_predictive/forecast.py`
  - `scripts/verify-permit-allocations-2026.js`
- Canonical promotion results:
  - Direct RAC hunt-code allotments promoted: `519`.
  - `DATABASE.csv` rows after promotion: `1411`.
  - `DATABASE.csv` unique hunt codes after promotion: `1411`.
  - Direct RAC missing after promotion: `0`.
  - Direct RAC numeric mismatches after promotion: `0`.
  - Blank RAC descriptive fields no longer overwrite known database seasons; affected season values were repaired from timestamped backups and the promoter was hardened.
- Cumulative RAC audit:
  - Cumulative RAC rows: `562`.
  - RAC hunt-code rows: `528`.
  - RAC unique hunt codes: `528`.
  - RAC hunt codes missing in `DATABASE.csv`: `0`.
  - Numeric mismatch rows: `0`.
  - Significant difference rows with absolute delta greater than 5: `0`.
- Antlerless elk verification:
  - `2026_rac_antlerless_elk_permits.csv` rows checked: `116`.
  - Unique antlerless elk hunt codes checked: `116`.
  - Database match rows: `116`.
  - Runtime match rows: `116`.
  - Database/runtime difference rows: `0`.
  - Example corrected current-year allotments: `EA1267 = 180/20/200`, `EA2033 = 180/20/200`, `EA1021 = 252/28/280`, `EA1208 = 292/33/325`.
- Prediction engine checks:
  - `EB3024 Resident` uses RAC current-year allotment `9/1/10`, with Resident quota `9`, max-point permits `5`, and random permits `4`.
  - `EB3022 Resident` uses RAC current-year allotment `130/15/145`, with Resident quota `130`, max-point permits `65`, and random permits `65`.
  - Prediction rows carry `permit_allotment_2026_*`, `quota_2026_*`, `quota_source_file`, and `RAC_CURRENT_YEAR_ALLOTMENT_USED` reason-code provenance where applicable.
  - Model/probability formulas were not changed; the current-year quota input was corrected.
- Private-lands-only handling:
  - Total-only private-lands antlerless elk rows remain availability/allocation style, not normal resident/nonresident draw rows.
  - `EA2012` is total-only `500`; resident and nonresident allotment fields remain blank.
  - `public_permits_2026` remains blank for private-lands-only total-only rows after the final truth-source promotion.
- Reports regenerated:
  - `processed_data/rac_current_year_database_promotion_write.json`
  - `processed_data/all_rac_2026_permits_cumulative.csv`
  - `processed_data/all_rac_2026_permits_cumulative.json`
  - `processed_data/all_rac_2026_permits_vs_DATABASE.csv`
  - `processed_data/all_rac_2026_permits_vs_DATABASE.json`
  - `processed_data/all_rac_2026_permits_vs_DATABASE.md`
  - `processed_data/antlerless_elk_current_rac_allotment_vs_database_runtime.csv`
  - `processed_data/antlerless_elk_current_rac_allotment_vs_database_runtime.json`
  - `processed_data/antlerless_elk_current_rac_allotment_vs_database_runtime.md`
  - `canonical/permit-allocation-2026-integrity-report.json`
  - `docs/permit-allocation-2026-integrity-report.md`
- Validation:
  - `python -m pytest tests/utah/test_current_year_permit_allotments.py tests/utah/test_truth_source_promotion.py tests/utah_bonus_predictive/test_official_2026_quota_inputs.py tests/utah/test_point_ladder_pool_display.py -q` passed: `43`.
  - `python -m pytest -q tests/utah_draw_predictive tests/utah/test_frontend_probability_selection.py` passed: `132`.
  - `python -m pytest -q tests/utah_bonus_predictive` passed: `36`.
  - `python -m compileall engine scripts tests` passed.
  - `node --check hunt-research.js` passed.
  - `node --check scripts/verify-permit-allocations-2026.js` passed.
  - `npm.cmd test` passed, including canonical JSON validation, canonical rebuild guardrails, and permit verification.
- Notes:
  - Added `schemas/hunt-master-canonical-2026.schema.json` because the repo's Node canonical test expected it and it was missing.
  - Added existing `drawPoolSelect` to `canonical/shared-2026.json` so the shared UI contract matches `research.html`.
  - Command-line git was unavailable in this environment, so no commit was created here.

## Canonical Draw Family Label Normalization
- Timestamp (UTC): 2026-05-23T08:55:00Z
- Scope:
  - Replaced internal catalog `draw_family` buckets such as `BONUS`, `ANTLERLESS`, `TURKEY_DRAW`, `NONE`, `HARVEST_OBJECTIVE`, and `UNKNOWN` with user-facing family labels.
  - Preserved model mechanics fields separately; no `algorithm_status`, `draw_system_type`, model strategy, or probability math was changed.
  - Added `scripts/normalize-draw-family-labels.py` so future catalog surfaces can be normalized repeatably.
  - Updated `scripts/promote-rac-current-year-allotments-to-database.py` so newly added RAC rows receive descriptive draw-family labels instead of `NONE`.
- Current family labels:
  - `Limited Entry` for split bonus/random-style limited-entry, premium, once-in-a-lifetime, limited turkey, limited pronghorn/deer/elk, and quota-backed restricted bear rows.
  - `General` for preference-style public draw rows, including antlerless and doe pronghorn style rows.
  - `O.T.C.` for true statewide/unlimited/no-quota availability-style rows and extended archery style rows.
  - `CWMU`, `Allocation`, `Sportsman`, and `Availability` are retained as explicit non-standard/offering-specific families where forcing `General` would hide important context.
- Active catalog counts after normalization:
  - `data/hunt-master-canonical-2026-database-candidate.csv`: `Limited Entry=477`, `Allocation=323`, `General=302`, `CWMU=283`, `O.T.C.=14`, `Sportsman=11`, `Availability=1`.
  - `canonical/hunt-planner-2026.json`: `Limited Entry=477`, `Allocation=323`, `General=308`, `CWMU=283`, `Sportsman=11`, `O.T.C.=8`, `Availability=1`.
  - `generated/pages/hunt-planner.json`: `Limited Entry=480`, `Allocation=323`, `General=288`, `CWMU=283`, `Sportsman=11`, `O.T.C.=8`, `Availability=1`.
- Validation:
  - `python -m pytest tests/utah/test_draw_family_labels.py tests/utah/test_current_year_permit_allotments.py -q` passed: `15`.
  - `python -m compileall scripts tests` passed.
  - `npm.cmd test` passed, including canonical JSON validation, canonical rebuild guardrails, and permit verification.

## Database Publish Readiness Gate
- Timestamp (UTC): 2026-05-23T09:20:00Z
- Scope:
  - Added a final database publish-readiness audit that ties together promoted source checks, canonical `DATABASE.csv`, runtime feed surfaces, prediction guardrails, draw-family semantics, duplicate-key checks, and sensitive-row spot checks.
  - Wrote:
    - `scripts/build-database-publish-readiness-report.py`
    - `processed_data/database_publish_readiness_report.json`
    - `processed_data/database_publish_readiness_report.md`
- Final readiness result:
  - `publish_ready = true`.
  - Blockers: `0`.
  - Warning retained: Henry Mtns remains an unresolved antlerless elk control-unit overlay item and is not fabricated into a permit row.
- Source-to-database checks:
  - Database rows: `1411`.
  - Database unique hunt codes: `1411`.
  - RAC hunt codes missing in database: `0`.
  - RAC numeric mismatch rows: `0`.
  - RAC significant differences greater than 5: `0`.
  - Truth-source family mismatches after promotion: `0`.
- Database-to-runtime checks:
  - Permit allocation integrity promotion blockers: `0`.
  - Permit allocation mismatches after sync: `0`.
  - Antlerless elk database/runtime differences: `0 / 0`.
- Semantic guardrails:
  - Null-probability violations for availability/allocation/pending/excluded/out-of-scope rows: `0`.
  - `ml_draw_predictions_v1.csv` duplicate keys: `0`.
  - `draw_reality_engine_predictive_v2.csv` duplicate keys: `0`.
  - Old internal draw-family label hits: `0`.
  - Sensitive row failed checks: `0`.
- Validation:
  - `npm.cmd run verify:permits-2026` passed.
  - `python -m pytest tests/utah/test_draw_family_labels.py tests/utah/test_current_year_permit_allotments.py tests/utah/test_truth_source_promotion.py tests/utah_bonus_predictive/test_official_2026_quota_inputs.py tests/utah/test_point_ladder_pool_display.py -q` passed: `49`.
  - `python -m pytest -q tests/utah_draw_predictive tests/utah/test_frontend_probability_selection.py` passed: `132`.
  - `python -m pytest -q tests/utah_bonus_predictive` passed: `36`.
  - `python -m compileall engine scripts tests` passed.
  - `node --check hunt-research.js` passed.
  - `node --check scripts/verify-permit-allocations-2026.js` passed.
  - `npm.cmd test` passed.

## Canonical Vs DATABASE Hunt Code / Name / Permit-Year Cross-Check
- Timestamp (UTC): 2026-05-23T09:28:00Z
- Scope:
  - Added `scripts/compare-canonical-hunt-database.py`.
  - Compared `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` against active canonical/catalog surfaces by `hunt_code`, normalized `hunt_name`, active 2026 permit fields, and prior-year alias fields.
  - Wrote:
    - `processed_data/canonical_vs_DATABASE_hunt_code_name_permits_year.csv`
    - `processed_data/canonical_vs_DATABASE_hunt_code_name_permits_year.json`
    - `processed_data/canonical_vs_DATABASE_hunt_code_name_permits_year.md`
- Key findings:
  - `DATABASE.csv` has `1411` rows and `1411` unique hunt codes.
  - `canonical/hunt-planner-2026.json` has `1411` hunt codes, no database-only/canonical-only hunt codes, and `0` active 2026/name mismatches against `DATABASE.csv`.
  - `data/hunt-master-canonical-2026-source-of-truth.csv` has `1411` hunt codes, no database-only/canonical-only hunt codes, and `0` active 2026/name mismatches against `DATABASE.csv`.
  - Root `hunt-master-canonical-2026.json` is behind the current database by `17` hunt codes: `EA1007`, `EA1053`, `EA1287`, `EA1288`, `EA1289`, `EA1290`, `EA1291`, `EA1292`, `EA1293`, `EA1294`, `EA1295`, `EA1296`, `EA1297`, `EA1298`, `EA1299`, `EA1300`, and `PD1039`.
  - `generated/pages/hunt-planner.json` is also behind by the same `17` hunt codes and has `91` name-only active mismatches.
  - Prior-year `permits_year_*` to `permits_2025_*` alias mismatches remain reported separately because legacy/catalog files do not share one consistent prior-year permit semantics.
- Validation:
  - `python scripts/compare-canonical-hunt-database.py` passed.
  - `python -m compileall scripts` passed.

## 2025 Draw-Result Permit Field Promotion
- Timestamp (UTC): 2026-05-23T09:44:00Z
- Scope:
  - Added `scripts/promote-2025-draw-permits-to-runtime.py`.
  - Promoted canonical explicit 2025 draw-result permit fields into database, runtime, predictive, and catalog surfaces:
    - `permits_2025_draw_res`
    - `permits_2025_draw_nr`
    - `permits_2025_draw_total`
    - `draw_2025_bg_pdf_page`
    - `draw_2025_bg_report_page`
    - `draw_2025_type`
    - `draw_2025_species_section`
    - `permits_2025_draw_source`
  - Synced legacy `permits_year_*` to the explicit 2025 draw-result fields only on current hunt-level/reference surfaces where those columns were being used as current prior-year permit references:
    - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
    - `processed_data/hunt_master_enriched.csv`
    - `processed_data/hunt_unit_reference_linked.csv`
    - `processed_data/point_ladder_view.csv`
  - Did not overwrite historical row-year `permits_year_*` values in `processed_data/draw_reality_engine.csv` or predictive output files.
  - Added `tests/utah/test_2025_draw_permit_field_promotion.py`.
- Outputs:
  - `processed_data/permits_2025_draw_field_promotion_report.json`
  - `processed_data/permits_2025_draw_field_promotion_report.csv`
  - `processed_data/permits_2025_draw_field_promotion_report.md`
- Key findings:
  - Canonical source has `572` hunt codes with explicit 2025 draw-result permit values.
  - `DB1002` now resolves to `1 / 0 / 1` in `DATABASE.csv` for both explicit 2025 draw fields and legacy `permits_year_*`.
  - `DB1002` retains 2026 RAC allotment `1 / 0 / 1`.
  - `DB1002` draw-result provenance carries DWR report page `19`.
- Validation:
  - `python scripts/promote-2025-draw-permits-to-runtime.py` passed.
  - `python scripts/compare-canonical-hunt-database.py` passed after promotion.
  - `python -m compileall scripts tests` passed.
  - `python -m pytest tests/utah/test_2025_draw_permit_field_promotion.py tests/utah/test_current_year_permit_allotments.py tests/utah/test_draw_family_labels.py -q` passed: `20`.
  - `npm.cmd run verify:permits-2026` passed.
  - `npm.cmd test` passed.
  - `node --check hunt-research.js` passed.
  - `python scripts/build-database-publish-readiness-report.py` passed with `publish_ready = true`.
  - `python -m pytest -q tests/utah_draw_predictive tests/utah/test_frontend_probability_selection.py` passed: `132`.
  - `tests/utah_bonus_predictive` passed when run in split groups: `36` total. The all-at-once command timed out in this environment before completion, but the same test files passed in smaller batches.

## New 2026 RAC Rows Explaining 1,411 To 1,394 Gap
- Timestamp (UTC): 2026-05-23T10:20:00Z
- Scope:
  - Documented the 17 hunt-code gap between `DATABASE.csv` / current canonical source-of-truth (`1411`) and stale 1,394-code catalog files.
  - Wrote:
    - `processed_data/new_2026_rac_hunts_explain_1394_gap.csv`
    - `processed_data/new_2026_rac_hunts_explain_1394_gap.json`
    - `processed_data/new_2026_rac_hunts_explain_1394_gap.md`
  - Updated:
    - `processed_data/canonical_vs_DATABASE_hunt_code_name_permits_year.md`
    - `processed_data/canonical_vs_DATABASE_hunt_code_name_permits_year.json`
    - `processed_data/database_publish_readiness_report.md`
    - `processed_data/database_publish_readiness_report.json`
    - `docs/permit-allocation-2026-integrity-report.md`
    - `canonical/permit-allocation-2026-integrity-report.json`
- Findings:
  - 16 gap codes are new 2026 antlerless elk general-season hunts from `2026_rac_antlerless_elk_permits.csv`.
  - 1 gap code is new 2026 doe pronghorn `PD1039` from `2026_rac_doe_pronghorn_permits.csv`.
  - Together these 17 rows account for `1,150` current-year permits: `1,034` resident and `116` nonresident.

## Catalog Surface 1,411 Sync And 1,305 Gap Breakdown
- Timestamp (UTC): 2026-05-23T11:00:00Z
- Scope:
  - Added `scripts/sync-catalog-surfaces-to-1411.py`.
  - Synced stale catalog surfaces to the current `1411`-code `DATABASE.csv` universe.
  - Root `hunt-master-canonical-2026.json` now has `1411` hunt codes and `1411` matching season records.
  - `generated/pages/hunt-planner.json` now has `1411` hunt codes.
  - `processed_data/hunt-master-canonical-2026-source-of-truth.csv` now has `1411` hunt codes.
  - `data/hunt-master-canonical-2026-database-candidate.csv` active 2026 permit/name fields now match `DATABASE.csv`.
- Outputs:
  - `processed_data/catalog_surface_1411_sync_report.json`
  - `processed_data/catalog_surface_1411_sync_report.md`
  - `processed_data/stale_1305_to_1411_gap_breakdown.csv`
  - `processed_data/stale_1305_to_1411_gap_breakdown.json`
  - `processed_data/stale_1305_to_1411_gap_breakdown.md`
  - `processed_data/hunt_code_surface_counts_after_catalog_sync.csv`
  - `processed_data/hunt_code_surface_counts_after_catalog_sync.json`
  - `processed_data/hunt_code_surface_counts_after_catalog_sync.md`
- 1,305 to 1,411 gap:
  - The old `processed_data/hunt-master-canonical-2026-source-of-truth.csv` was missing `106` current database hunt codes.
  - Missing-code makeup: `104` black bear (`BR*`) rows, `1` desert bighorn sheep (`DS1000`) row, and `1` deer landowner/private-land row (`LO0010`).
  - This stale CSV gap is now resolved by copying the current 1,411-code source-of-truth CSV into `processed_data`.
- Current post-sync counts:
  - `DATABASE.csv`: `1411` unique hunt codes.
  - Root canonical JSON: `1411`.
  - Canonical planner JSON: `1411`.
  - Generated planner JSON: `1411`.
  - Data/processed source-of-truth JSON/CSV catalog surfaces: `1411`.
  - Enriched/reference/ladder runtime surfaces retain all database codes plus `60` cougar availability codes.
  - Predictive outputs remain `1065` hunt codes by model scope and still are not forced to include non-predictive database rows.
- Validation:
  - `python scripts/sync-catalog-surfaces-to-1411.py` passed.
  - `python scripts/compare-canonical-hunt-database.py` passed.
  - `python -m compileall scripts` passed.
  - `npm.cmd run verify:permits-2026` passed.
  - `npm.cmd test` passed with root canonical `hunt_catalog_count = 1411`.

## Ambiguous `permits_year_*` Column Removal
- Timestamp (UTC): 2026-05-23T11:14:00Z
- Scope:
  - Removed ambiguous generic permit-year columns from active current-year database/runtime/source-of-truth CSV surfaces:
    - `permits_year_res`
    - `permits_year_nr`
    - `permits_year_total`
  - Preserved explicit year-specific fields:
    - 2025 draw-result permits: `permits_2025_draw_res`, `permits_2025_draw_nr`, `permits_2025_draw_total`
    - 2026 current allotments: `permits_2026_res`, `permits_2026_nr`, `permits_2026_total`, `permit_allotment_2026_res`, `permit_allotment_2026_nr`, `permit_allotment_2026_total`
  - Added `scripts/remove-ambiguous-permits-year-columns.py` so the cleanup is repeatable.
  - Updated comparison/promotion/permit-change/reconciliation helpers so they no longer write ambiguous current-surface aliases.
- Outputs:
  - `processed_data/permits_year_column_removal_report.json`
  - `processed_data/permits_year_column_removal_report.csv`
  - `processed_data/permits_year_column_removal_report.md`
- Key checks:
  - `DATABASE.csv` remains `1411` rows / `1411` unique hunt codes.
  - Canonical/catalog surfaces remain aligned at `1411` hunt codes with `0` active 2026/name mismatches.
  - All RAC 2026 permit rows still match `DATABASE.csv`: missing in database `0`, numeric mismatches `0`, significant differences greater than 5 `0`.
  - `DB1002` now uses explicit 2025 draw-result permits `1 / 0 / 1` and explicit 2026 allotment permits `1 / 0 / 1`; no ambiguous `permits_year_*` columns are required.
- Validation:
  - `python scripts/remove-ambiguous-permits-year-columns.py` passed and wrote removal reports.
  - `python scripts/promote-2025-draw-permits-to-runtime.py` passed with `0` changed cells after explicit-field cleanup.
  - `python scripts/build-all-rac-permit-database-compare.py` passed with RAC missing in database `0`, numeric mismatches `0`, significant differences greater than 5 `0`.
  - `python scripts/compare-canonical-hunt-database.py` passed with all checked canonical/catalog surfaces at `1411` codes and `0` active 2026/name mismatches.
  - Header audit confirmed no active current CSV surface still carries `permits_year_res`, `permits_year_nr`, or `permits_year_total`.
  - `python -m pytest tests/utah/test_2025_draw_permit_field_promotion.py tests/utah/test_current_year_permit_allotments.py tests/utah/test_draw_family_labels.py -q` passed: `22`.
  - `python -m compileall scripts engine tests` passed.
  - `node --check scripts/permit-change-report-2026.js`, `node --check scripts/reconcile-le-elk-2025-permits.js`, and `node --check hunt-research.js` passed.
  - `npm.cmd run verify:permits-2026` passed with post-sync mismatches `0`.
  - `npm.cmd test` passed with canonical JSON count `1411` and permit verification post-sync mismatches `0`.

## 2025 Draw-Results Permit Promotion
- Timestamp (UTC): 2026-05-23T11:26:00Z
- Scope:
  - Promoted explicit `permits_2025_res`, `permits_2025_nr`, and `permits_2025_total` from the local official 2025 draw-results extraction:
    - `pipeline/RAW/hunt_unit_database/2026/csv/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED_V3.csv`
  - Kept this separate from:
    - `permit_allotment_2026_*`, which remains current 2026 RAC draw allotment.
    - `permits_2025_draw_*`, which remains detailed DWR draw-result permit extraction fields.
  - Added `scripts/promote-2025-draw-results-permits.py`.
- Outputs:
  - `processed_data/permits_2025_draw_results_promotion_report.json`
  - `processed_data/permits_2025_draw_results_promotion_report.csv`
  - `processed_data/permits_2025_draw_results_promotion_report.md`
- Key findings:
  - Source rows scanned: `112056`.
  - Source rows used for 2025 database-matched draw permits: `73604`.
  - Database hunt codes with promoted 2025 draw-results permit totals: `1028`.
  - Promoted hunt codes with nonzero 2025 draw-result permits: `1026`.
  - Existing `permits_2025_draw_total` cross-check mismatches: `0`.
  - Spot checks:
    - `DB1002`: `1 / 0 / 1` from `2025 LE Deer Draw Results.pdf`.
    - `EB3024`: `9 / 1 / 10` from `2025 LE Elk Draw Results(1).pdf`.
    - `EA1010`: `18 / 2 / 20` from `2025 Antlerless Draw Results(1).pdf` / `2025 Youth Antlerless Draw.pdf`.
    - `PB5025`: `39 / 4 / 43` from `2025 LE Pronghorn Draw Results.pdf`.
    - `BR1008`: `26 / 2 / 28` from `2025 Black Bear Draw odds.pdf`.
    - `PD1039`: no 2025 draw-results row, consistent with a new 2026 hunt row.
- Validation:
  - `python scripts/promote-2025-draw-results-permits.py` passed with draw-field mismatch count `0`.
  - `python scripts/compare-canonical-hunt-database.py` passed with all checked canonical/catalog surfaces at `1411` codes and `0` active 2026/name mismatches.
  - `python scripts/build-all-rac-permit-database-compare.py` passed with RAC missing in database `0`, numeric mismatches `0`, significant differences greater than 5 `0`.
  - `python -m pytest tests/utah/test_2025_draw_permit_field_promotion.py tests/utah/test_current_year_permit_allotments.py tests/utah/test_draw_family_labels.py -q` passed: `24`.
  - `python -m compileall scripts engine tests` passed.
  - `node --check scripts/permit-change-report-2026.js`, `node --check scripts/reconcile-le-elk-2025-permits.js`, and `node --check hunt-research.js` passed.
  - `npm.cmd run verify:permits-2026` passed with post-sync mismatches `0`.
  - `npm.cmd test` passed with canonical JSON count `1411` and permit verification post-sync mismatches `0`.

## 2025 Permit Prior-Generation Reconciliation
- Timestamp (UTC): 2026-05-23T11:33:00Z
- Scope:
  - Compared active 1411-code `DATABASE.csv` / canonical catalog surfaces against the prior 1394-code foundation:
    - `data/hunt-master-canonical-2026-foundation.json`
  - Added `scripts/reconcile-2025-permits-prior-generation.py`.
  - Ensured active CSV and JSON surfaces all carry:
    - `permits_2025_res`
    - `permits_2025_nr`
    - `permits_2025_total`
  - Ensured the 17 new 2026 RAC hunt codes carry blank 2025 permit values rather than missing fields.
- Outputs:
  - `processed_data/permits_2025_prior_generation_reconciliation.json`
  - `processed_data/permits_2025_prior_generation_reconciliation.csv`
  - `processed_data/permits_2025_prior_generation_reconciliation.md`
- Key findings:
  - Prior-generation hunt-code count: `1394`.
  - Active database hunt-code count: `1411`.
  - Active-not-prior count: `17`.
  - Active-not-prior hunt codes exactly match the new 2026 RAC gap list:
    - `EA1007`, `EA1053`, `EA1287`, `EA1288`, `EA1289`, `EA1290`, `EA1291`, `EA1292`, `EA1293`, `EA1294`, `EA1295`, `EA1296`, `EA1297`, `EA1298`, `EA1299`, `EA1300`, `PD1039`.
  - New 2026 hunt rows with nonblank 2025 permit values across checked active surfaces: `0`.
  - Prior-overlap differences were documented in the CSV report; active values remain sourced from official draw-results tables when `permits_2025_source = 2025_DRAW_RESULTS_TABLES`.
- Validation:
  - `python scripts/reconcile-2025-permits-prior-generation.py` passed.
  - `python scripts/compare-canonical-hunt-database.py` passed with all checked canonical/catalog surfaces at `1411` codes and `0` active 2026/name mismatches.
  - `python scripts/build-all-rac-permit-database-compare.py` passed with RAC missing in database `0`, numeric mismatches `0`, significant differences greater than 5 `0`.
  - `python -m pytest tests/utah/test_2025_draw_permit_field_promotion.py tests/utah/test_current_year_permit_allotments.py tests/utah/test_draw_family_labels.py -q` passed: `25`.
  - `python -m compileall scripts engine tests` passed.
  - `node --check scripts/permit-change-report-2026.js`, `node --check scripts/reconcile-le-elk-2025-permits.js`, and `node --check hunt-research.js` passed.
  - `npm.cmd run verify:permits-2026` passed with post-sync mismatches `0`.
  - `npm.cmd test` passed with canonical JSON count `1411` and permit verification post-sync mismatches `0`.

## Empty DATABASE Column Cleanup
- Timestamp (UTC): 2026-05-23T12:00:00Z
- Scope:
  - Audited Excel-style `DATABASE.csv` columns `M` and `T`.
  - Column `M` was an unnamed blank-header field with `0` populated values.
  - Column `T` was `draw_2025_species_section` with `0` populated values.
  - Removed both empty fields from active database, runtime, canonical, and catalog surfaces rather than keeping ambiguous unpopulated data.
  - Added `scripts/remove-empty-database-columns.py` so the cleanup is repeatable and guarded.
  - Updated `scripts/promote-2025-draw-permits-to-runtime.py` so `draw_2025_species_section` is not recreated by the 2025 draw permit promotion step.
- Outputs:
  - `processed_data/empty_database_column_removal_report.json`
  - `processed_data/empty_database_column_removal_report.csv`
  - `processed_data/empty_database_column_removal_report.md`
- Key checks:
  - `DATABASE.csv` remains `1411` rows / `1411` unique hunt codes.
  - Fully blank database rows found/removed: `0`.
  - Nonblank rows missing `hunt_code`: `0`.
  - Blank header columns remaining in `DATABASE.csv`: `0`.
  - `draw_2025_species_section` columns remaining in `DATABASE.csv`: `0`.
- Validation:
  - `python scripts/remove-empty-database-columns.py` passed; final post-verifier pass found `0` remaining empty fields to remove.
  - `python scripts/promote-2025-draw-permits-to-runtime.py` passed with `0` changed cells.
  - `python scripts/promote-2025-draw-results-permits.py` passed with draw-field mismatch count `0`.
  - `python scripts/reconcile-2025-permits-prior-generation.py` passed and confirmed the 17 new 2026 RAC rows remain blank for 2025 permits.
  - `python scripts/compare-canonical-hunt-database.py` passed with all checked canonical/catalog surfaces at `1411` codes and `0` active 2026/name mismatches.
  - `python scripts/build-all-rac-permit-database-compare.py` passed with RAC missing in database `0`, numeric mismatches `0`, significant differences greater than 5 `0`.
  - `python -m pytest tests/utah/test_2025_draw_permit_field_promotion.py tests/utah/test_current_year_permit_allotments.py tests/utah/test_draw_family_labels.py -q` passed: `28`.
  - `python -m compileall scripts engine tests` passed.
  - `node --check scripts/permit-change-report-2026.js`, `node --check scripts/reconcile-le-elk-2025-permits.js`, and `node --check hunt-research.js` passed.
  - `npm.cmd run verify:permits-2026` passed with post-sync mismatches `0`.
  - `npm.cmd test` passed with canonical JSON count `1411` and permit verification post-sync mismatches `0`.

## All-Years Harvest Package Import And Harvest Quality Database
- Timestamp (UTC): 2026-05-23T13:12:00Z
- Scope:
  - Imported existing harvest ZIP packages as source/truth inputs without re-extracting PDFs.
  - Extracted package contents into:
    - `data_truth/harvest_results_truth/raw_packages/`
    - `data_model/harvest_quality/raw_packages/`
  - Built cumulative normalized harvest outputs for reported hunt years `2021`, `2022`, `2023`, `2024`, and `2025`.
  - Mirrored feature-ready harvest tables into `data_model/harvest_quality/`.
  - Preserved harvest data as quality/history/demand-signal input only.
  - Added special permit overlay classification for `CONSERVATION`, `CWMU`, `EXPO`, and `SPORTSMAN` rows as total-permit reconciliation only.
  - Confirmed special permit overlays are not public draw-odds rows and are not p_draw math inputs.
- Scripts:
  - `scripts/import-harvest-packages-to-truth.py`
  - `scripts/build-all-years-harvest-database.py`
- Outputs:
  - `data_truth/harvest_results_truth/raw_packages_manifest.csv`
  - `data_truth/harvest_results_truth/raw_packages_manifest.json`
  - `data_truth/harvest_results_truth/raw_packages_manifest.md`
  - `data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv`
  - `data_truth/harvest_results_truth/normalized/harvest_quality_features_all_years_by_hunt_code.csv`
  - `data_truth/harvest_results_truth/normalized/harvest_results_all_years_source_audit.csv`
  - `data_truth/harvest_results_truth/normalized/harvest_results_all_years_summary.json`
  - `data_truth/harvest_results_truth/normalized/harvest_results_all_years_summary.md`
  - `data_model/harvest_quality/harvest_results_all_years_long.csv`
  - `data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv`
  - `data_model/permit_overlays/special_permit_overlay_classes_all_years.csv`
  - `processed_data/harvest_results_all_years_long.csv`
  - `processed_data/harvest_quality_features_all_years_by_hunt_code.csv`
  - `processed_data/special_permit_overlay_classes_all_years.csv`
- Key findings:
  - Unique harvest packages imported: `7`.
  - Duplicate package paths de-duplicated by SHA: `5`.
  - Extracted files: `104`.
  - Extracted CSV files: `83`.
  - Extracted SQLite files: `7`.
  - Extracted PDF files: `0`.
  - PDF re-extraction performed: `NO`.
  - Normalized long harvest rows: `28669`.
  - Best-by-year/hunt-code rows: `5149`.
  - Reported hunt year counts:
    - `2021`: `974`
    - `2022`: `924`
    - `2023`: `1078`
    - `2024`: `1046`
    - `2025`: `1127`
  - Model target year counts:
    - `2022`: `974`
    - `2023`: `924`
    - `2024`: `1078`
    - `2025`: `1046`
    - `2026`: `1127`
  - Active database coverage by reported hunt year:
    - `2021`: `803`
    - `2022`: `781`
    - `2023`: `960`
    - `2024`: `956`
    - `2025`: `1097`
  - Unique hunt codes across all harvest years: `1423`.
  - Special permit overlay rows: `1530`.
  - Special permit overlay class counts:
    - `CONSERVATION`: `76`
    - `CWMU`: `1429`
    - `EXPO`: `9`
    - `SPORTSMAN`: `16`
- Guardrails:
  - Harvest permit fields remain harvest-report context only.
  - Harvest rows have `do_not_use_for_permit_quota = True`.
  - Harvest rows have `do_not_use_directly_for_p_draw = True`.
  - Expo, Conservation, Sportsman, and CWMU rows are marked `TOTAL_PERMIT_RECONCILIATION_ONLY`, `public_draw_odds_use = NO`, and `p_draw_math_use = NO`.
- Validation:
  - `python scripts/import-harvest-packages-to-truth.py` passed.
  - `python scripts/build-all-years-harvest-database.py` passed.
  - `python -m pytest tests/utah/test_all_years_harvest_database.py -q` passed: `9`.
  - `python -m pytest tests/utah/test_all_years_harvest_database.py tests/utah/test_2025_draw_permit_field_promotion.py tests/utah/test_current_year_permit_allotments.py tests/utah/test_draw_family_labels.py -q` passed: `37`.
  - `python -m compileall scripts engine tests` passed.
  - `node --check hunt-research.js` passed.

## Max Point Pool Guaranteed Display Label
- Timestamp (UTC): 2026-05-23T16:20:00Z
- Scope:
  - Updated the point-ladder frontend display so rows in the guaranteed max-point-pool zone show `~1 in 1 or 99%`.
  - Kept mixed cutoff max-point-pool rows on their modeled fraction/display value.
  - Kept shared draw-odds formatting and underlying probability math unchanged.
- Files:
  - `hunt-research.js`
  - `tests/utah/test_frontend_probability_selection.py`
- Validation:
  - `python -m pytest tests/utah/test_frontend_probability_selection.py -q` passed: `28`.
  - `node --check hunt-research.js` passed.
  - `python -m compileall tests hunt-research.js` passed.

## Hunt Research Source Pill Button Fix
- Timestamp (UTC): 2026-05-23T17:45:00Z
- Scope:
  - Fixed the Hunt Research ladder `Sources` pill click handler so CSV string point values match numeric button point values.
  - Kept the fix display/interactivity-only; no prediction math or data outputs changed.
- Files:
  - `hunt-research.js`
  - `research.html`
  - `tests/utah/test_frontend_probability_selection.py`
- Validation:
  - `python -m pytest tests/utah/test_frontend_probability_selection.py -q` passed: `29`.
  - `node --check hunt-research.js` passed.
  - `python -m compileall tests hunt-research.js` passed.
  - Browser verification passed locally: `Sources` pill opened the DWR Source Snapshot modal after running `EB3024` resident at `30` points.

## Hunt Research Guaranteed Line Orange
- Timestamp (UTC): 2026-05-23T18:05:00Z
- Scope:
  - Updated the Hunt Research point-ladder guaranteed-to-draw line and `Guaranteed` marker to use the requested orange `rgb(255, 140, 20)`.
  - Kept this as a visual-only change; no draw odds, prediction math, or runtime data files changed.
- Files:
  - `research.html`
  - `tests/utah/test_frontend_probability_selection.py`
- Validation:
  - `python -m pytest tests/utah/test_frontend_probability_selection.py -q` passed: `30`.
  - `node --check hunt-research.js` passed.
  - `python -m compileall tests hunt-research.js` passed.
  - Browser visual pass was attempted, but the in-app browser text-entry path was blocked by its virtual clipboard limitation; static CSS regression covers the exact requested RGB value.

## Hunt Research Highlight Outline
- Timestamp (UTC): 2026-05-23T18:20:00Z
- Scope:
  - Added a dark-brown outline to highlighted Hunt Research point-ladder boxes, including selected-user rows, guaranteed rows, and `YOU` / `Guaranteed` marker pills.
  - Kept this visual-only; no draw odds, prediction math, or runtime data files changed.
- Files:
  - `research.html`
  - `tests/utah/test_frontend_probability_selection.py`
- Validation:
  - `python -m pytest tests/utah/test_frontend_probability_selection.py -q` passed: `31`.
  - `node --check hunt-research.js` passed.
  - `python -m compileall tests hunt-research.js` passed.

## Hunt Research Distinct Ladder Highlight Colors
- Timestamp (UTC): 2026-05-23T18:35:00Z
- Scope:
  - Changed the hunter-selected point row to a pale blue highlight with a stronger blue accent.
  - Kept the predicted guaranteed-to-draw line orange and preserved the dark-brown outline.
  - Added a combined-row treatment so rows that are both `YOU` and `Guaranteed` show both blue and orange cues.
  - Kept this visual-only; no draw odds, prediction math, or runtime data files changed.
- Files:
  - `research.html`
  - `tests/utah/test_frontend_probability_selection.py`
- Validation:
  - `python -m pytest tests/utah/test_frontend_probability_selection.py -q` passed: `32`.
  - `node --check hunt-research.js` passed.
  - `python -m compileall tests hunt-research.js` passed.

## Repo File Retention And LFS Audit
- Timestamp (UTC): 2026-05-23T14:55:00Z
- Scope:
  - Audited repository files for GitHub, Cloudflare R2 runtime/archive, local archive, delete-after-backup, and review-required storage actions.
  - Confirmed `pages-dist/` is a deploy bundle only; root/main repository files remain the source/runtime truth inputs.
  - Added Git LFS tracking patterns for large processed runtime data, including `processed_data/boundaries/**`, `processed_data/hunt_research_2026_split/**`, major prediction/runtime CSVs, large GeoJSON boundaries, and SQLite artifacts.
  - No files were deleted, and no prediction/model outputs were changed.
- Scripts/tests:
  - `scripts/audit-repo-file-retention.py`
  - `tests/utah/test_repo_file_retention_audit.py`
- Outputs:
  - `processed_data/repo_file_retention_audit.csv`
  - `processed_data/repo_file_retention_audit.json`
  - `processed_data/repo_file_retention_audit.md`
  - `processed_data/repo_file_retention_summary_by_directory.csv`
  - `processed_data/repo_file_retention_cloudflare_manifest.csv`
  - `processed_data/repo_file_retention_github_keep_manifest.csv`
  - `processed_data/repo_file_retention_delete_after_backup_manifest.csv`
  - `processed_data/repo_file_retention_review_required_manifest.csv`
- Key results:
  - Total repo file count: `8984`.
  - Total repo size: `4339.944 MB`.
  - Cloudflare R2 runtime-data recommendations: `2989`.
  - Cloudflare R2 archive-data recommendations: `306`.
  - GitHub keep recommendations: `1708` across source, docs, scripts/tests, and small canonical data classes.
  - Local archive recommendations: `914`.
  - Delete-after-backup recommendations: `393`.
  - Review-required recommendations: `732`.
  - Tracked files over 25 MB: `29`.
  - Tracked files over 100 MB: `1`.
- Validation:
  - `python scripts/audit-repo-file-retention.py` passed.
  - `python -m pytest tests\utah\test_repo_file_retention_audit.py -q` passed: `14`.
  - `python -m compileall scripts tests` passed.
  - `python scripts/compare-complete-2023-harvest-to-draw.py` passed and refreshed the complete 2023 harvest-vs-draw comparison.

## Harvest Package Split-Season Year Correction
- Timestamp (UTC): 2026-05-23T13:20:00Z
- Scope:
  - Corrected split-season package year inference so season spans such as `2023_24` and `23-24` use the ending season year as the reported hunt year.
  - Confirmed `turkey_harvest_results_2023_24_for_2025_database.zip` now resolves to reported hunt year `2024` and model target year `2025`.
  - Confirmed `turkey_harvest_results_2024_25_for_2026_database.zip` now resolves to reported hunt year `2025` and model target year `2026`.
  - Materialized the supplied master package bundle into truth/model source-bundle folders without PDF re-extraction.
  - Preferred master-bundle package filenames over older loose ZIP copies to avoid double-counting rebuilt packages with the same filename.
  - Kept overlay/backcheck packages available as source material while limiting harvest normalization to harvest/turkey database and harvest supplement ZIPs.
- Scripts:
  - `scripts/import-harvest-packages-to-truth.py`
  - `scripts/build-all-years-harvest-database.py`
- Key results:
  - Unique source packages imported from the master bundle: `14`.
  - Extracted files: `183`.
  - Extracted CSV files: `143`.
  - Extracted SQLite files: `11`.
  - Extracted PDF files: `0`.
  - PDF re-extraction performed: `NO`.
  - Normalized long harvest rows: `68657`.
  - Best-by-year/hunt-code rows: `5151`.
  - Reported hunt year counts:
    - `2021`: `974`
    - `2022`: `924`
    - `2023`: `1078`
    - `2024`: `1048`
    - `2025`: `1127`
  - Model target year counts:
    - `2022`: `974`
    - `2023`: `924`
    - `2024`: `1078`
    - `2025`: `1048`
    - `2026`: `1127`
  - Unique hunt codes across all harvest years: `1424`.
  - Special permit overlay rows: `1531`.
  - Special permit overlay class counts:
    - `CONSERVATION`: `77`
    - `CWMU`: `1429`
    - `EXPO`: `9`
    - `SPORTSMAN`: `16`
- Validation:
  - `python scripts/import-harvest-packages-to-truth.py` passed.
  - `python scripts/build-all-years-harvest-database.py` passed.
  - `python -m pytest tests/utah/test_all_years_harvest_database.py -q` passed: `10`.
  - `python -m pytest tests/utah/test_all_years_harvest_database.py tests/utah/test_2025_draw_permit_field_promotion.py tests/utah/test_current_year_permit_allotments.py tests/utah/test_draw_family_labels.py -q` passed: `38`.
  - `python -m compileall scripts engine tests` passed.

## Final Harvest Database Audit And Feature Contract
- Timestamp (UTC): 2026-05-23T13:40:00Z
- Scope:
  - Audited the completed all-years harvest-result database for source inventory, required-field missingness, key integrity, metric integrity, year coverage, hunt-code alignment, and active 2026 feature readiness.
  - Created a formal harvest modeling contract clarifying that harvest data is quality/demand-signal metadata only.
  - Implemented harvest quality feature helpers and a guarded materializer that joins harvest-derived features without changing probability or quota/allotment fields.
  - Confirmed harvest report permit counts are not used as 2026 public draw quota/allotment.
  - Confirmed Expo, Conservation, Sportsman, and CWMU overlays remain total-permit reconciliation only and are not p_draw inputs.
- Scripts/modules:
  - `scripts/audit-harvest-results-database-final.py`
  - `engine/utah/quality/harvest_feature_model.py`
  - `engine/utah/quality/materialize_harvest_feature_model.py`
- Outputs:
  - `processed_data/harvest_results_database_final_audit.csv`
  - `processed_data/harvest_results_database_final_audit.json`
  - `processed_data/harvest_results_database_final_audit.md`
  - `processed_data/harvest_results_database_key_integrity_audit.csv`
  - `processed_data/harvest_results_database_metric_integrity_audit.csv`
  - `processed_data/harvest_results_database_year_coverage_audit.csv`
  - `processed_data/harvest_results_database_hunt_code_alignment_audit.csv`
  - `processed_data/harvest_results_database_feature_readiness_audit.csv`
  - `processed_data/harvest_results_database_modeling_contract.md`
  - `data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv`
  - `data_model/harvest_quality/harvest_feature_model_by_species_year.csv`
  - `data_model/harvest_quality/ml_draw_predictions_with_harvest_features.csv`
  - `data_model/harvest_quality/draw_reality_engine_predictive_with_harvest_features.csv`
  - `processed_data/harvest_feature_model_audit.csv`
  - `processed_data/harvest_feature_model_audit.json`
  - `processed_data/harvest_feature_model_audit.md`
- Key results:
  - Harvest database row count: `68657`.
  - Best-by-year/hunt-code rows: `5151`.
  - Reported hunt-year coverage: `2021`, `2022`, `2023`, `2024`, `2025`.
  - Model target-year coverage: `2022`, `2023`, `2024`, `2025`, `2026`.
  - Active 2026 feature rows: `1411`.
  - Exact hunt-code feature matches: `1188`.
  - Fallback feature matches: `222`.
  - No-history rows: `1`.
  - Harvest quality index count: `1384`.
  - Demand pressure signal count: `1404`.
  - Audit blocker count: `0`.
  - Audit warning count: `15529`.
  - Metric issue count: `15521`.
  - Success-rate math conflict rows reported for review: `12923`.
  - Protected probability and quota/allotment fields unchanged: `true`.
- Validation:
  - `python scripts/audit-harvest-results-database-final.py` passed.
  - `python -m engine.utah.quality.materialize_harvest_feature_model --output-dir processed_data --forecast-year 2026` passed.
  - `python -m pytest tests/utah_quality -q` passed: `18`.
  - `python -m pytest tests/utah/test_current_year_permit_allotments.py tests/utah_bonus_predictive/test_official_2026_quota_inputs.py -q` passed: `15`.
  - `python -m compileall scripts engine tests` passed.
  - `node --check hunt-research.js` passed.

## Hunt Research Draw-Pool UX Simplification
- Timestamp (UTC): 2026-05-23T17:16:44Z
- Scope:
  - Removed the visible Hunt Research draw-pool selector from hunter-facing controls while preserving the internal `draw_pool` key used by the prediction lookup.
  - Replaced raw `standard` pool readouts with hidden/internal routing; non-standard handoffs can still display hunter-readable labels such as `Youth draw`.
  - Updated Builder and backpack handoffs to carry the internal draw-pool key into Hunt Research without asking hunters to choose engine categories.
  - Confirmed this is a frontend routing/display cleanup only; no prediction math, data artifacts, or quota fields were changed.
- Validation:
  - `node --check hunt-research.js` passed.
  - `node --check app.js` passed.
  - `node --check ui.js` passed.
  - `python -m pytest tests/utah/test_frontend_probability_selection.py -q` passed: `35`.

## Clean Builder Root Navigation Links
- Timestamp (UTC): 2026-05-24T00:20:00Z
- Scope:
  - Replaced internal `./index.html#google-maps` Builder navigation targets with clean `./` links across the shared header, static pages, generated page metadata, and canonical nav metadata.
  - Kept map-mode hash behavior out of visible navigation so Wix/GitHub/browser routing can resolve the Builder root cleanly.
  - No model, data, prediction, or permit outputs were changed.
- Validation:
  - `python -m pytest tests/utah/test_header_layout.py -q` passed: `7`.
  - `node --check header-layout.js` passed.
  - JSON validation passed for touched canonical/generated page metadata.
  - `python -m compileall tests/utah/test_header_layout.py` passed.

## GitHub Pages Custom Domain Mapping
- Timestamp (UTC): 2026-05-24T00:30:00Z
- Scope:
  - Added the root `CNAME` file required by GitHub Pages so the published `HUNTS` site maps to `hunt-builder.uoga.org`.
  - Confirmed the site build script already includes `CNAME` when present.
  - No website content, model output, or runtime data was changed.
- Validation:
  - Confirmed `CNAME` contains exactly `hunt-builder.uoga.org`.
  - `python -m compileall scripts tests` passed.

## Emergency Pages Fallback While DNS Is Missing
- Timestamp (UTC): 2026-05-24T03:26:00Z
- Scope:
  - Removed the root `CNAME` file temporarily because public DNS returned `NXDOMAIN` for `hunt-builder.uoga.org`.
  - This prevents GitHub Pages project URLs from redirecting to an unresolved custom domain while Wix DNS is repaired.
  - The correct Wix DNS record must be restored before re-adding `CNAME`: host/name `hunt-builder`, value/target `utahoga.github.io`.
- Validation:
  - Public DNS checks returned no CNAME/A record for `hunt-builder.uoga.org` before this fallback.
  - No website source, model output, or runtime data was changed.

## Pages Branch Custom Domain Restore
- Timestamp (UTC): 2026-05-24T03:38:00Z
- Scope:
  - Restored the GitHub Pages `CNAME` file on the published `gh-pages` branch with `hunt-builder.uoga.org`.
  - Kept source/runtime data and prediction outputs unchanged.
  - Used the Pages branch because the emergency static site is currently being served from `gh-pages`.
- Validation:
  - Pushed `gh-pages` commit `d5cefe1` with the custom-domain `CNAME`.
  - Public DNS still needs to resolve `hunt-builder.uoga.org` to GitHub Pages before the custom domain can render reliably.

## Pages Custom Domain Corrected To Utahoga
- Timestamp (UTC): 2026-05-24T03:43:00Z
- Scope:
  - Corrected the published Pages `CNAME` hostname from `hunt-builder.uoga.org` to `hunt-builder.utahoga.org` to match the Wix DNS record.
  - Confirmed Wix DNS resolves `hunt-builder.utahoga.org` as a CNAME to `utahoga.github.io`.
  - No website source, model output, or runtime data was changed.

## Pages Custom Domain Returned To UOGA
- Timestamp (UTC): 2026-05-24T03:47:00Z
- Scope:
  - Returned both source and published Pages `CNAME` files to `hunt-builder.uoga.org` because Wix DNS is being corrected to that hostname.
  - No website source, model output, or runtime data was changed.

## Cumulative Harvest And Draw Truth Databases Finalized
- Timestamp (UTC): 2026-05-25T03:49:12Z
- Scope:
  - Rebuilt and validated the cumulative harvest truth database from the existing all-year harvest builder.
  - Finalized the cumulative draw-results truth validation layer around `data_truth/draw_results_truth/normalized/draw_results_long.csv` without rewriting the runtime long table.
  - Added draw all-years summary and source-audit artifacts to match the harvest truth database validation pattern.
  - Confirmed the 2026 current-to-historical crosswalk is present in draw truth coverage: `169` of `169` crosswalk current codes appear in draw rows.
  - Did not modify `hard-copy`, Pages output branches, public website feeds, materializers, or probability math.
- Harvest results:
  - Normalized long rows: `68,657`.
  - Best by reported year and hunt code rows: `5,151`.
  - Reported hunt years: `2021`, `2022`, `2023`, `2024`, `2025`.
  - Model target years: `2022`, `2023`, `2024`, `2025`, `2026`.
  - Final harvest audit blocker count: `0`.
- Draw results:
  - Normalized long rows: `176,753`.
  - Draw years: `2021`, `2022`, `2023`, `2024`, `2025`, `2026`.
  - Model target years: `2022`, `2023`, `2024`, `2025`, `2026`, `2027`.
  - Duplicate `(hunt_code, year, draw_pool, residency, points)` keys: `0`.
  - Blank hunt-code rows: `0`.
  - Invalid year rows: `0`.
  - Draw validation blocker count: `0`.
- Outputs:
  - `scripts/finalize-draw-results-cumulative-database.py`
  - `tests/utah/test_draw_results_cumulative_database.py`
  - `data_truth/draw_results_truth/normalized/draw_results_all_years_summary.json`
  - `data_truth/draw_results_truth/normalized/draw_results_all_years_summary.md`
  - `data_truth/draw_results_truth/normalized/draw_results_all_years_source_audit.csv`
  - `processed_data/draw_results_all_years_summary.json`
  - `processed_data/draw_results_all_years_summary.md`
  - `processed_data/draw_results_all_years_source_audit.csv`
- Validation:
  - `python scripts\finalize-draw-results-cumulative-database.py` passed.
  - `python scripts\build-all-years-harvest-database.py` passed.
  - `python scripts\audit-harvest-results-database-final.py` passed with `audit_blocker_count = 0`.
  - `python -m pytest tests\utah\test_all_years_harvest_database.py tests\utah\test_draw_results_cumulative_database.py -q` passed: `13`.
  - `python -m pytest tests\utah_quality\test_harvest_database_final_audit.py tests\utah_quality\test_harvest_feature_model.py tests\utah\test_all_years_harvest_database.py tests\utah\test_draw_results_cumulative_database.py -q` passed: `27`.
  - `python -m py_compile scripts\finalize-draw-results-cumulative-database.py scripts\build-all-years-harvest-database.py tests\utah\test_draw_results_cumulative_database.py tests\utah\test_all_years_harvest_database.py` passed.

## Hard-Copy Library Publish Audit
- Timestamp (UTC): 2026-05-25T04:22:00Z
- Scope:
  - Added a focused hard-copy document library audit for the website/library package.
  - Audited existing library-master records, public document records, processed/public/pages-dist manifests, generated/canonical page libraries, duplicate keys, and href resolvability.
  - Did not modify `hard-copy`, `public/hard-copy`, generated page libraries, `pages-dist`, publish scripts, website feeds, or truth databases.
- Result:
  - Status: `NOT_PUBLISH_SAFE`.
  - Blockers: `478`.
  - Warnings: `2`.
  - Master library records: `328`.
  - Public document records: `9`.
  - Processed PDF manifest records: `405`.
  - Pages-dist PDF manifest records: `405`.
  - Generated page library records: `405`.
- Major blockers:
  - `hard-copy/documents.json` is still a stub source file.
  - `hard-copy.html` fetches `/hard-copy/data/documents.json`, but `pages-dist/hard-copy/data/documents.json` is missing.
  - Manifest hrefs are not publish-safe: `476` broken href findings across root and pages-dist checks.
  - Master library duplicate-key warning remains and needs cleanup before relying on the library as canonical.
- Outputs:
  - `scripts/audit-hard-copy-library.py`
  - `tests/utah/test_hard_copy_library_audit.py`
  - `processed_data/hard_copy_library_audit_report.json`
  - `processed_data/hard_copy_library_audit_report.md`
  - `processed_data/hard_copy_library_audit_issues.csv`
- Validation:
  - `python scripts\audit-hard-copy-library.py` passed and wrote the audit artifacts.
  - `python -m pytest tests\utah\test_hard_copy_library_audit.py -q` passed: `2`.
  - `python -m py_compile scripts\audit-hard-copy-library.py tests\utah\test_hard_copy_library_audit.py` passed.

## Library Master Database Reconciliation
- Timestamp (UTC): 2026-05-25T04:55:00Z
- Scope:
  - Reconciled `pipeline/RAW/hunt_unit_database/library-master.csv` against the current 2026 `DATABASE.csv` truth source at `C:\Users\tyler\Desktop\GitHub\HUNTS\pipeline\RAW\hunt_unit_database\2026\csv\DATABASE.csv`.
  - Treated `library-master` as a candidate catalog, not as a truth source.
  - Wrote database-enriched candidate outputs instead of overwriting the existing library master.
  - Crosschecked public document rows against `public/hard-copy/data/documents.json` and local hard-copy file paths.
  - Did not modify website runtime feeds, prediction math, `pages-dist`, or the original `library-master.csv`.
- Results:
  - Library master rows: `328`.
  - 2026 `DATABASE.csv` rows: `1,411`.
  - 2026 `DATABASE.csv` unique hunt codes: `1,411`.
  - Match status: `REVIEW_REQUIRED`.
  - High-confidence database matches: `104`.
  - Review database matches: `30`.
  - Ambiguous database matches: `184`.
  - Document rows not hunt-coded: `10`.
  - Public/source document files found: `9`.
  - Missing source path document rows: `1` (`2022-2024 Conservation Permits` source path still needs final public file placement).
- Outputs:
  - `scripts/reconcile-library-master-to-database-2026.py`
  - `tests/utah/test_library_master_database_reconciliation.py`
  - `processed_data/library_master_database_reconciliation.csv`
  - `processed_data/library_master_database_reconciliation.md`
  - `processed_data/library_master_database_reconciliation_summary.json`
  - `pipeline/RAW/hunt_unit_database/library-master.reconciled.csv`
  - `pipeline/RAW/hunt_unit_database/library-master.reconciled.json`
- Validation:
  - `python scripts\reconcile-library-master-to-database-2026.py` passed.
  - `python -m pytest tests\utah\test_library_master_database_reconciliation.py -q` passed: `2`.
  - `python -m py_compile scripts\reconcile-library-master-to-database-2026.py tests\utah\test_library_master_database_reconciliation.py` passed.

## Library Master vs Hunt Master Enriched Comparison
- Timestamp (UTC): 2026-05-25T05:12:00Z
- Scope:
  - Compared the reconciled library candidate against `processed_data/hunt_master_enriched.csv`.
  - Used `database_hunt_code` from `library-master.reconciled.csv` as the comparison key.
  - Accounted for `hunt_master_enriched.csv` being a runtime surface with repeated rows by residency, point bucket, and draw pool.
  - Did not modify `hunt_master_enriched.csv`, website feeds, prediction math, `pages-dist`, or the original `library-master.csv`.
- Results:
  - Library rows compared: `328`.
  - Library reconciled hunt codes: `147`.
  - Hunt master rows: `54,357`.
  - Hunt master unique hunt codes: `1,471`.
  - Library codes found in hunt master: `147`.
  - Library codes missing from hunt master: `0`.
  - Document-only rows not hunt-coded: `10`.
  - Fully aligned rows: `31`.
  - Found but prior library/database review still required: `96`.
  - Found with runtime field drift: `191`.
  - Largest field drift bucket: `database_permits_2026_source -> permits_2026_source` on `191` rows, mostly source-label normalization differences.
- Outputs:
  - `scripts/compare-library-master-to-hunt-master-enriched.py`
  - `tests/utah/test_library_master_hunt_master_enriched_comparison.py`
  - `processed_data/library_master_vs_hunt_master_enriched.csv`
  - `processed_data/library_master_vs_hunt_master_enriched.md`
  - `processed_data/library_master_vs_hunt_master_enriched_summary.json`
- Validation:
  - `python scripts\compare-library-master-to-hunt-master-enriched.py` passed.
  - `python -m pytest tests\utah\test_library_master_hunt_master_enriched_comparison.py -q` passed: `2`.
  - `python -m py_compile scripts\compare-library-master-to-hunt-master-enriched.py tests\utah\test_library_master_hunt_master_enriched_comparison.py` passed.

## Governed Research Library Master Mapping Contract
- Timestamp (UTC): 2026-05-25T06:05:00Z
- Scope:
  - Made hunt-code mapping a governed research-library contract instead of an implicit/fuzzy side effect.
  - Added the required reviewed mapping columns `hunt_code` and `boundary_id` plus candidate/status columns for every research-library row.
  - Kept the existing `library-master.csv` unchanged and built a normalized research-library truth candidate under `data_truth/research_library_truth`.
  - Used the HUNTS 2026 `DATABASE.csv` as the database authority, `hunt_master_enriched.csv` as the runtime/reference crosscheck, and the current-to-historical crosswalk as prefix-change evidence.
  - Preserved 2022-2024 conservation-permit rows as candidate evidence only because current/historical prefix changes require reviewed crosswalk promotion.
  - Added the same mapping law to `AGENTS.MD` and a standalone `RESEARCH_LIBRARY_MASTER_RULES.md`.
  - No website feeds, `pages-dist`, `public_client_engine.csv`, materializer code, prediction math, original `library-master.csv`, or source `DATABASE.csv` files were changed.
- Outputs:
  - `scripts/build-research-library-master.py`
  - `tests/utah/test_research_library_master.py`
  - `RESEARCH_LIBRARY_MASTER_RULES.md`
  - `data_truth/research_library_truth/normalized/research_library_master.csv`
  - `data_truth/research_library_truth/normalized/research_library_master.json`
  - `data_truth/research_library_truth/validation/research_library_master_summary.json`
  - `data_truth/research_library_truth/validation/research_library_master_mapping_gaps.csv`
  - `processed_data/research_library_master.csv`
  - `processed_data/research_library_master.md`
- Key results:
  - Research-library rows built: `328`.
  - Document-level rows: `10`.
  - Permit-allocation rows: `318`.
  - Candidate hunt-code rows: `318`.
  - Unique candidate hunt codes: `147`.
  - Candidate boundary-id rows: `318`.
  - Candidate codes missing HUNTS `DATABASE.csv`: `0`.
  - Candidate codes missing `hunt_master_enriched.csv`: `0`.
  - Reviewed/promoted hunt-code rows: `0`.
  - Reviewed/promoted boundary-id rows: `0`.
  - Rows requiring review before promotion: `328`.
  - Validation blockers: `0`.
- Validation:
  - `python scripts\build-research-library-master.py` passed.
  - `python -m py_compile scripts\build-research-library-master.py tests\utah\test_research_library_master.py` passed.
  - `python -m pytest tests\utah\test_research_library_master.py -q` passed: `2`.
  - `python -m pytest tests\utah\test_research_library_master.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py tests\utah\test_library_master_database_reconciliation.py tests\utah\test_library_master_hunt_master_enriched_comparison.py -q` passed: `9`.

## Research Library Feeder And Boundary Source Registry
- Timestamp (UTC): 2026-05-25T06:35:00Z
- Scope:
  - Expanded the governed research-library master to register canonical feeder/reference files as first-class `feeder_file` rows.
  - Registered the HUNTS 2026 `DATABASE.csv` as the canonical current hunt-code and boundary-id source.
  - Registered the local `DATABASE.csv` mirror, `hunt_master_enriched.csv`, `point_ladder_view.csv`, canonical build files, canonical JSON surfaces, research JSON surfaces, boundary alignment reports, and major boundary JSON/GeoJSON files.
  - Added file hashes, file sizes, row counts, unique hunt-code counts, and unique boundary-id counts where safe and applicable.
  - Updated the mapping law to require feeder/reference files to be registered before they support boundary alignment work.
  - No website feeds, `pages-dist`, `public_client_engine.csv`, materializer code, prediction math, original `library-master.csv`, or source database files were changed.
- Outputs refreshed:
  - `scripts/build-research-library-master.py`
  - `tests/utah/test_research_library_master.py`
  - `RESEARCH_LIBRARY_MASTER_RULES.md`
  - `data_truth/research_library_truth/normalized/research_library_master.csv`
  - `data_truth/research_library_truth/normalized/research_library_master.json`
  - `data_truth/research_library_truth/validation/research_library_master_summary.json`
  - `data_truth/research_library_truth/validation/research_library_master_mapping_gaps.csv`
  - `processed_data/research_library_master.csv`
  - `processed_data/research_library_master.md`
- Key results:
  - Research-library rows built: `356`.
  - Source catalog rows: `328`.
  - Feeder file rows: `28`.
  - Boundary-alignment feeder rows: `27`.
  - Canonical database feeder rows: `1`.
  - Missing feeder files: `0`.
  - Candidate hunt-code rows remain: `318`.
  - Unique candidate hunt codes remain: `147`.
  - Rows requiring mapping review remain: `328`.
  - Validation blockers: `0`.
- Validation:
  - `python scripts\build-research-library-master.py` passed.
  - `python -m py_compile scripts\build-research-library-master.py tests\utah\test_research_library_master.py` passed.
  - `python -m pytest tests\utah\test_research_library_master.py -q` passed: `3`.
  - `python -m pytest tests\utah\test_research_library_master.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py tests\utah\test_library_master_database_reconciliation.py tests\utah\test_library_master_hunt_master_enriched_comparison.py -q` passed: `10`.

## RAC Recommended Permits And Preliminary Harvest Source Registration
- Timestamp (UTC): 2026-05-25T07:05:00Z
- Scope:
  - Registered the user-supplied `2026 rac recommended permits.xlsx` workbook as a current-year permit recommendation feeder source.
  - Registered the companion `2026 rac recommended permits.pdf` as a current-year permit recommendation feeder source.
  - Registered `2026-03-06-2025-preliminary-bg-harvest.pdf` as a preliminary 2025 big game harvest feeder source.
  - Added PDF page-count and workbook sheet-count metadata to the governed research-library master schema.
  - Did not parse or promote permit/harvest values into truth tables in this step; these files are registered and hashed as source evidence first.
  - No website feeds, `pages-dist`, `public_client_engine.csv`, materializer code, prediction math, original `library-master.csv`, or source files were changed.
- Key results:
  - Research-library rows built: `359`.
  - Feeder file rows: `31`.
  - Boundary-alignment feeder rows: `30`.
  - Missing feeder files: `0`.
  - RAC workbook sheet count: `1`.
  - RAC PDF page count: `39`.
  - Preliminary harvest PDF page count: `23`.
  - Validation blockers: `0`.
- Validation:
  - `python scripts\build-research-library-master.py` passed.
  - `python -m py_compile scripts\build-research-library-master.py tests\utah\test_research_library_master.py` passed.
  - `python -m pytest tests\utah\test_research_library_master.py -q` passed: `3`.
  - `python -m pytest tests\utah\test_research_library_master.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py tests\utah\test_library_master_database_reconciliation.py tests\utah\test_library_master_hunt_master_enriched_comparison.py -q` passed: `10`.

## Direct DWR Hunt Planner CSV Folder Registration And 2025 Permit Guard
- Timestamp (UTC): 2026-05-25T07:35:00Z
- Scope:
  - Registered the direct Utah DWR Hunt Planner CSV folder `pipeline/RAW/hunt_unit_database/2026/csv` as source evidence.
  - Auto-discovered all `89` `.csv` files in the folder and added `88` direct-folder feeder rows after de-duping the already registered local `DATABASE.csv` mirror.
  - Added source filename year context, source path year context, and source file modified timestamp metadata to the research-library master.
  - Added explicit `permit_allotment_2026_promotion_status` fields so source rows cannot be mistaken for promoted 2026 available allotment values.
  - Guardrail added: 2025 permit values must not be promoted into 2026 available allotment unless every imported source used in that promotion has reviewed source-date context.
  - Kept `DATABASE.csv` as the canonical current hunt-code and boundary-id source; direct folder CSVs are source evidence only.
  - No website feeds, `pages-dist`, `public_client_engine.csv`, materializer code, prediction math, original `library-master.csv`, or source CSV files were changed.
- Key results:
  - Research-library rows built: `447`.
  - Source catalog rows: `328`.
  - Feeder file rows: `119`.
  - Direct DWR Hunt Planner CSV files discovered: `89`.
  - Direct DWR Hunt Planner CSV feeder rows: `88`.
  - Boundary-alignment feeder rows: `118`.
  - Promotion status counts: `NOT_PROMOTED_CATALOG_REVIEW_REQUIRED=328`, `NOT_PROMOTED_SOURCE_REGISTRY_ONLY=119`.
  - Source rows missing year context: `8`.
  - Missing feeder files: `0`.
  - Validation blockers: `0`.
- Validation:
  - `python scripts\build-research-library-master.py` passed.
  - `python -m py_compile scripts\build-research-library-master.py tests\utah\test_research_library_master.py` passed.
  - `python -m pytest tests\utah\test_research_library_master.py -q` passed: `4`.
  - `python -m pytest tests\utah\test_research_library_master.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py tests\utah\test_library_master_database_reconciliation.py tests\utah\test_library_master_hunt_master_enriched_comparison.py -q` passed: `11`.

## Hunt Master Canonical Permit Deep Dive
- Timestamp (UTC): 2026-05-25T08:15:00Z
- Scope:
  - Built a read-only permit consistency audit for `pipeline/RAW/hunt_unit_database/2026/csv/hunt_master_canonical_2026_built.csv`.
  - Compared the target file's duplicate permit triples positionally against canonical HUNTS `DATABASE.csv`, direct RAC/current-year CSV evidence, and high-confidence current-year total-scan evidence.
  - Treated the first duplicate permit triple as 2025 permit evidence and the second duplicate permit triple as 2026/current allotment evidence for audit purposes only.
  - Added the hard guardrail that populated numeric permit cells in canonical `DATABASE.csv` are direct Utah DWR Hunt Planner truth and must not be changed or overwritten by comparison files, inferred values, draw reports, RAC files, audit outputs, or rebuilt library/master documents.
  - No `DATABASE.csv`, website feeds, `pages-dist`, `public_client_engine.csv`, materializer code, source CSV files, or runtime prediction surfaces were changed.
- Outputs:
  - `scripts/audit-hunt-master-canonical-permit-consistency.py`
  - `tests/utah/test_hunt_master_canonical_permit_deep_dive.py`
  - `processed_data/hunt_master_canonical_2026_built_permit_deep_dive.csv`
  - `processed_data/hunt_master_canonical_2026_built_permit_deep_dive_summary.json`
  - `processed_data/hunt_master_canonical_2026_built_permit_deep_dive.md`
  - `data_truth/comparison_outputs/validation/hunt_master_canonical_2026_built_permit_deep_dive_summary.json`
- Key results:
  - Target rows: `1289`.
  - Target unique hunt codes: `1289`.
  - Canonical `DATABASE.csv` rows: `1411`.
  - Target duplicate hunt codes: `0`.
  - Target codes missing canonical `DATABASE.csv`: `1` (`DB1276`).
  - Canonical `DATABASE.csv` codes missing target: `123`.
  - Direct RAC hunt-code evidence rows: `519`.
  - Total-scan high-confidence hunt-code evidence rows: `855`.
  - High-confidence rows: `318`.
  - Medium 2026 database-match rows: `370`.
  - Low 2025-only match rows: `109`.
  - Review-required rows: `492`.
  - Large target 2025-to-2026 total-change review rows: `42`.
  - Spot checks confirmed `BI6505` and `BI6506` second triples match canonical 2026/allotment values; `DB1200` is correctly flagged as a zero-placeholder target case against populated canonical 2026 permit values.
- Validation:
  - `python scripts\audit-hunt-master-canonical-permit-consistency.py` passed.
  - `python -m py_compile scripts\audit-hunt-master-canonical-permit-consistency.py tests\utah\test_hunt_master_canonical_permit_deep_dive.py` passed.
  - `python -m pytest tests\utah\test_hunt_master_canonical_permit_deep_dive.py -q` passed: `3`.
  - `python -m pytest tests\utah\test_research_library_master.py -q` passed: `4`.

## Database-Authoritative Permit Overlay Plan
- Timestamp (UTC): 2026-05-25T08:35:00Z
- Scope:
  - Built a safe overlay action queue from the permit deep-dive audit.
  - Used canonical HUNTS `DATABASE.csv` as the authoritative source anywhere populated numeric 2026 permit or allotment cells exist.
  - Marked target/master disagreements as downstream overlay actions or review evidence; did not modify `DATABASE.csv`, source CSV files, website feeds, runtime files, materializer code, or prediction surfaces.
  - Added database-only hunt codes to the downstream action queue so derived universes can be expanded from canonical `DATABASE.csv` rather than from incomplete target/master rows.
- Outputs:
  - `scripts/build-database-authoritative-permit-overlay-plan-2026.py`
  - `tests/utah/test_database_authoritative_permit_overlay_plan_2026.py`
  - `processed_data/database_authoritative_permit_overlay_plan_2026.csv`
  - `processed_data/database_authoritative_permit_overlay_plan_2026_summary.json`
  - `processed_data/database_authoritative_permit_overlay_plan_2026.md`
  - `data_truth/comparison_outputs/validation/database_authoritative_permit_overlay_plan_2026_summary.json`
- Key results:
  - Overlay plan rows: `1412`.
  - Unique hunt codes: `1412`.
  - Database numeric protected rows: `1261`.
  - Target-and-database rows: `1288`.
  - Database-only rows to add to derived universe: `123`.
  - Target-only blocker codes: `1` (`DB1276`).
  - Rows already matching database: `688`.
  - Rows where derived outputs should use canonical `DATABASE.csv` 2026 permit values over target/master disagreement: `455`.
  - Rows with no numeric permit data: `140`.
  - Target-only 2026 values needing review: `5`.
- Validation:
  - `python scripts\build-database-authoritative-permit-overlay-plan-2026.py` passed.
  - `python -m py_compile scripts\build-database-authoritative-permit-overlay-plan-2026.py tests\utah\test_database_authoritative_permit_overlay_plan_2026.py` passed.
  - `python -m pytest tests\utah\test_database_authoritative_permit_overlay_plan_2026.py -q` passed: `3`.
  - `python -m pytest tests\utah\test_database_authoritative_permit_overlay_plan_2026.py tests\utah\test_hunt_master_canonical_permit_deep_dive.py -q` passed: `6`.

## DATABASE 2026 Authority Clarification
- Timestamp (UTC): 2026-05-25T08:50:00Z
- Scope:
  - Tightened the previously broad `DATABASE.csv` numeric-cell guardrail.
  - Clarified that populated numeric `2026` permit/allotment cells in canonical `DATABASE.csv` are the direct Utah DWR Hunt Planner truth source.
  - Clarified that populated `2025` or older permit fields in `DATABASE.csv` are historical evidence fields unless separately sourced as current Hunt Planner data; they likely originate from raw PDF/import pipelines and must retain lineage before being used as truth.
  - Regenerated the permit deep-dive and database-authoritative overlay summaries with the corrected authority language.
  - No source CSV values, `DATABASE.csv`, website feeds, runtime files, materializer code, or prediction surfaces were changed.
- Validation:
  - `python scripts\audit-hunt-master-canonical-permit-consistency.py` passed.
  - `python scripts\build-database-authoritative-permit-overlay-plan-2026.py` passed.
  - `python -m py_compile scripts\audit-hunt-master-canonical-permit-consistency.py scripts\build-database-authoritative-permit-overlay-plan-2026.py tests\utah\test_hunt_master_canonical_permit_deep_dive.py tests\utah\test_database_authoritative_permit_overlay_plan_2026.py` passed.
  - `python -m pytest tests\utah\test_hunt_master_canonical_permit_deep_dive.py tests\utah\test_database_authoritative_permit_overlay_plan_2026.py -q` passed: `6`.

## Historical Permit Source-Lineage Lock
- Timestamp (UTC): 2026-05-25T09:10:00Z
- Scope:
  - Corrected the canonical rule for passed hunt-year permit values.
  - Locked source-lined 2025 and older permit fields in `DATABASE.csv` as canonical historical source truth, not soft evidence.
  - Added a historical permit lineage audit for canonical `DATABASE.csv`.
  - Verified that populated 2025 historical permit fields carry source lineage and do not have paired-family strays.
  - Clarified that `permits_2025` is the full populated 2025 historical permit universe in `DATABASE.csv`, while `permits_2025_draw` is a narrower bonus-point draw-results subset, not the full 2025 draw/permit universe.
  - Regenerated the existing permit deep-dive and database-authoritative overlay summaries with the corrected historical-truth language.
  - No source CSV values, `DATABASE.csv`, website feeds, runtime files, materializer code, or prediction surfaces were changed.
- Outputs:
  - `scripts/audit-database-historical-permit-lineage-2026.py`
  - `tests/utah/test_database_historical_permit_lineage_2026.py`
  - `processed_data/database_historical_permit_lineage_2026.csv`
  - `processed_data/database_historical_permit_lineage_2026_summary.json`
  - `processed_data/database_historical_permit_lineage_2026.md`
  - `data_truth/comparison_outputs/validation/database_historical_permit_lineage_2026_summary.json`
- Key results:
  - Canonical `DATABASE.csv` rows audited: `1411`.
  - Historical audit rows: `2822`.
  - Historical years detected: `2025`.
  - Canonical historical source-truth rows: `1600`.
  - Full populated 2025 historical permit universe (`permits_2025`): `1028`, all sourced to `2025_DRAW_RESULTS_TABLES`.
  - 2025 bonus-point draw-results subset (`permits_2025_draw`): `572`, all sourced to `2025_DRAW_RESULTS_TABLES`.
  - 2025 non-bonus/general subset in the base historical permit universe: `456`.
  - Lineage blockers: `0`.
  - Paired-family comparison: `572` matches, `456` primary-only, `383` both blank, `0` mismatches.
- Validation:
  - `python scripts\audit-hunt-master-canonical-permit-consistency.py` passed.
  - `python scripts\build-database-authoritative-permit-overlay-plan-2026.py` passed.
  - `python scripts\audit-database-historical-permit-lineage-2026.py` passed.
  - `python -m py_compile scripts\audit-database-historical-permit-lineage-2026.py tests\utah\test_database_historical_permit_lineage_2026.py scripts\audit-hunt-master-canonical-permit-consistency.py scripts\build-database-authoritative-permit-overlay-plan-2026.py tests\utah\test_hunt_master_canonical_permit_deep_dive.py tests\utah\test_database_authoritative_permit_overlay_plan_2026.py` passed.
  - `python -m pytest tests\utah\test_database_historical_permit_lineage_2026.py tests\utah\test_hunt_master_canonical_permit_deep_dive.py tests\utah\test_database_authoritative_permit_overlay_plan_2026.py -q` passed: `9`.

## 2025 To 2026 Hunt-Code Comparison
- Timestamp (UTC): 2026-05-26T00:30:00Z
- Scope:
  - Built a read-only hunt-code comparison between source-lined 2025 historical permit codes and current 2026 DWR Hunt Planner `DATABASE.csv` codes.
  - Used `permits_2025` as the full populated 2025 historical permit-code universe.
  - Used populated `permits_2026` rows as the current 2026 permit-code universe and all `DATABASE.csv` rows as the 2026 reference universe.
  - Enriched exact-code gaps with the promoted `current_to_historical_hunt_code_crosswalk_2026.csv`.
  - Used only promoted `historical_hunt_code` mappings for continuity; candidate/name-match fields remain review evidence and were not used as truth.
  - No source CSV values, `DATABASE.csv`, website feeds, runtime files, materializer code, or prediction surfaces were changed.
- Outputs:
  - `scripts/compare-2025-2026-hunt-codes.py`
  - `tests/utah/test_hunt_code_comparison_2025_to_2026.py`
  - `processed_data/hunt_code_comparison_2025_to_2026.csv`
  - `processed_data/hunt_code_comparison_2025_to_2026_summary.json`
  - `processed_data/hunt_code_comparison_2025_to_2026.md`
  - `data_truth/comparison_outputs/validation/hunt_code_comparison_2025_to_2026_summary.json`
- Key results:
  - 2026 `DATABASE.csv` reference universe: `1411`.
  - Source-lined 2025 historical permit codes: `1028`.
  - Populated 2026 permit codes: `1261`.
  - Exact same-code continuity: `1027`.
  - 2025 historical codes absent from 2026 `DATABASE.csv`: `0`.
  - 2025 historical codes present but without populated 2026 permits: `1` (`BR7307`).
  - Populated 2026 permit codes without exact 2025 code: `234`.
  - Populated 2026 permit codes with promoted mapped 2025 history: `133`.
  - Populated 2026 permit codes with no mapped 2025 history: `101`.
  - 2026 reference-only rows without 2025 or 2026 permit values: `149`.
  - Spot checks: `EL3000 -> EB3000` via promoted prefix-swap mapping; `BI6539` remains no mapped 2025 history; `CG9999` remains reference-only.
- Validation:
  - `python scripts\compare-2025-2026-hunt-codes.py` passed.
  - `python -m py_compile scripts\compare-2025-2026-hunt-codes.py tests\utah\test_hunt_code_comparison_2025_to_2026.py` passed.
  - `python -m pytest tests\utah\test_hunt_code_comparison_2025_to_2026.py -q` passed: `4`.
  - `python -m pytest tests\utah\test_hunt_code_comparison_2025_to_2026.py tests\utah\test_database_historical_permit_lineage_2026.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py -q` passed: `10`.

## 2025 Guidebook Code Lookup For 2026 Gaps
- Timestamp (UTC): 2026-05-26T01:00:00Z
- Scope:
  - Extracted hunt-code lines from `HUNTS/pipeline/RAW/hunt_unit_database/2025/pdf/regulation/2025_biggameapp.pdf`.
  - Compared extracted 2025 guidebook codes to the 102 unresolved rows from the 2025-to-2026 hunt-code comparison (`101` current 2026 populated codes with no mapped 2025 history plus `1` 2025 historical code without populated 2026 permits).
  - Classified evidence as exact current-code hits, same-number prefix swaps, name/species candidates, or no guidebook code found.
  - Kept name-only candidates as review evidence only; no source CSV values, `DATABASE.csv`, website feeds, runtime files, materializer code, or prediction surfaces were changed.
- Outputs:
  - `scripts/find-2025-regulation-codes-for-2026-gaps.py`
  - `tests/utah/test_guidebook_2025_codes_for_2026_gaps.py`
  - `processed_data/guidebook_2025_extracted_hunt_codes.csv`
  - `processed_data/guidebook_2025_codes_for_2026_gaps.csv`
  - `processed_data/guidebook_2025_codes_for_2026_gaps_summary.json`
  - `processed_data/guidebook_2025_codes_for_2026_gaps.md`
  - `data_truth/comparison_outputs/validation/guidebook_2025_codes_for_2026_gaps_summary.json`
- Key results:
  - 2025 guidebook code-line rows extracted: `743`.
  - Unique 2025 guidebook codes extracted: `734`.
  - Gap rows checked: `102`.
  - Exact current-code hits in guidebook: `2` (`EB3168`, `DB1109`).
  - Same-number prefix-swap hits in guidebook: `21` (mostly `LO -> DB`, plus `EL3168 -> EB3168`).
  - Same-species/name-only candidates: `15`.
  - No guidebook code found: `64`.
  - Name-only examples kept as review evidence: `BI6539` has Henry Mtns bison candidates, `DS6605` has `DS6621`, `PD1039` has `PB5054|PB5061|PB5041`.
- Validation:
  - `python scripts\find-2025-regulation-codes-for-2026-gaps.py` passed.
  - `python -m py_compile scripts\find-2025-regulation-codes-for-2026-gaps.py tests\utah\test_guidebook_2025_codes_for_2026_gaps.py` passed.
  - `python -m pytest tests\utah\test_guidebook_2025_codes_for_2026_gaps.py -q` passed: `3`.
  - `python -m pytest tests\utah\test_guidebook_2025_codes_for_2026_gaps.py tests\utah\test_hunt_code_comparison_2025_to_2026.py -q` passed: `7`.

## 2025 Guidebook Evidence Text Sanitization
- Timestamp (UTC): 2026-05-26T13:14:54Z
- Scope:
  - Fixed PDF/Excel text encoding garbage in the 2025 guidebook candidate-line evidence columns.
  - Normalized extracted guidebook evidence text to ASCII so date ranges write as `Oct. 18-Oct. 26` instead of leaking smart dashes or mojibake such as `â€“`.
  - Wrote regenerated guidebook CSV outputs with UTF-8 BOM for Excel-friendly opening on Windows.
  - Added a regression guard that fails if extracted guidebook evidence outputs contain mojibake, smart dashes, daggers, bullets, or replacement characters.
  - No hunt-code matching logic, source CSV values, `DATABASE.csv`, website feeds, runtime files, materializer code, or prediction surfaces were changed.
- Outputs:
  - `scripts/find-2025-regulation-codes-for-2026-gaps.py`
  - `tests/utah/test_guidebook_2025_codes_for_2026_gaps.py`
  - `processed_data/guidebook_2025_extracted_hunt_codes.csv`
  - `processed_data/guidebook_2025_codes_for_2026_gaps.csv`
- Key results:
  - Preserved guidebook extraction counts: `743` code-line rows and `734` unique codes.
  - Preserved gap check count: `102`.
  - Preserved match status counts: `2` exact current-code hits, `21` prefix-swap hits, `15` name/species candidates, and `64` no-code rows.
  - Verified `LO1627` candidate line now reads `Cache (new) DB1627 Oct. 18-Oct. 26`.
- Validation:
  - `python scripts\find-2025-regulation-codes-for-2026-gaps.py` passed.
  - `python -m py_compile scripts\find-2025-regulation-codes-for-2026-gaps.py tests\utah\test_guidebook_2025_codes_for_2026_gaps.py` passed.
  - `python -m pytest tests\utah\test_guidebook_2025_codes_for_2026_gaps.py -q` passed: `4`.
  - Direct scan of `processed_data\guidebook_2025_codes_for_2026_gaps.csv` and `processed_data\guidebook_2025_extracted_hunt_codes.csv` found no `â`, `Â`, replacement characters, smart dashes, daggers, or bullets.

## 2026 EA Private-Lands Canonical Source Validation
- Timestamp (UTC): 2026-05-26T13:20:58Z
- Scope:
  - Registered the user-supplied DWR Hunt Planner file `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/elk antlerless private lands only EA.csv` as canonical source evidence for antlerless elk private-lands-only `EA` permit totals.
  - Normalized the source into a committed permit-overlay truth table with source path, source SHA-256, and numeric `permits_2026_total` values.
  - Compared every supplied `EA` hunt code against protected current `DATABASE.csv` values without modifying `DATABASE.csv`.
  - Preserved the rule that populated `DATABASE.csv` numeric cells are not overwritten by comparison output without explicit review and promotion approval.
- Outputs:
  - `scripts/validate-ea-private-lands-canonical-2026.py`
  - `tests/utah/test_ea_private_lands_canonical_2026.py`
  - `data_truth/permit_overlay_truth/normalized/elk_antlerless_private_lands_EA_2026_canonical.csv`
  - `data_truth/permit_overlay_truth/validation/elk_antlerless_private_lands_EA_2026_vs_DATABASE.csv`
  - `data_truth/permit_overlay_truth/validation/elk_antlerless_private_lands_EA_2026_summary.json`
  - `processed_data/elk_antlerless_private_lands_EA_2026_summary.md`
- Key results:
  - Source rows: `27`.
  - Unique `EA` hunt codes: `27`.
  - Source total 2026 permits: `9830`.
  - Structural blockers: `0`.
  - Missing DATABASE hunt codes: `0`.
  - DATABASE protected-value differences: `5`.
  - Difference codes: `EA2012`, `EA2015`, `EA2016`, `EA2027`, and `EA2046`.
- Validation:
  - `python scripts\validate-ea-private-lands-canonical-2026.py` passed.
  - `python -m py_compile scripts\validate-ea-private-lands-canonical-2026.py tests\utah\test_ea_private_lands_canonical_2026.py` passed.
  - `python -m pytest tests\utah\test_ea_private_lands_canonical_2026.py -q` passed: `3`.

## Private-Land Bull Elk 2026 Quota Cleanup And 2024 Bear Draw Extraction
- Timestamp (UTC): 2026-05-26T14:30:00Z
- Scope:
  - Enforced the user clarification that private-land bull elk `EL` and elk `LO` rows must not carry 2026 permit availability or allotment numbers.
  - Cleared leaked 2026 permit/quota/allotment fields from the 131 private-land elk `EL/LO` codes in `DATABASE.csv`, enriched/canonical CSV surfaces, predictive reference rows, and ladder/reference drafts while leaving public `EB` rows untouched.
  - Re-ran the EL/LO private-land elk audit after cleanup; all 131 rows are now `SOURCE_AND_DATABASE_BLANK` for numeric 2026 permit comparison, with zero database numeric values unsupported by the private-land source.
  - Extracted the attached `24 bear draw odds complete.pdf` into a normalized 2024 black bear draw-results permit-total artifact aligned to model target year 2025.
  - Stored bear resident/nonresident eligible applicants, bonus permits, regular permits, total permits, page numbers, source SHA-256, and DATABASE comparison status.
- Outputs:
  - `scripts/clear-elk-private-lands-el-lo-2026-permit-fields.py`
  - `scripts/extract-black-bear-2024-draw-odds-permits.py`
  - `tests/utah/test_elk_private_lands_el_lo_clear_2026.py`
  - `tests/utah/test_black_bear_2024_draw_odds_extraction.py`
  - `data_truth/permit_overlay_truth/validation/elk_private_lands_EL_LO_2026_cleared_permit_fields.csv`
  - `data_truth/permit_overlay_truth/validation/elk_private_lands_EL_LO_2026_cleared_permit_fields_summary.json`
  - `processed_data/elk_private_lands_EL_LO_2026_cleared_permit_fields.md`
  - `data_truth/draw_results_truth/normalized/black_bear_2024_draw_odds_model_target_2025_permit_totals.csv`
  - `data_truth/draw_results_truth/validation/black_bear_2024_draw_odds_model_target_2025_vs_DATABASE.csv`
  - `data_truth/draw_results_truth/validation/black_bear_2024_draw_odds_model_target_2025_summary.json`
  - `processed_data/black_bear_2024_draw_odds_model_target_2025_permit_totals.md`
- Key results:
  - EL/LO target codes: `131` (`EL=126`, `LO=5`).
  - Remaining EL/LO numeric 2026 permit/quota leak cells: `0`.
  - Public `EB3020` retained 2026 quota values, proving public limited-entry elk rows were not cleared.
  - Bear draw-odds extracted rows: `96` unique `BR` hunt codes.
  - Bear source public permits: `943` total (`887` resident, `56` nonresident).
  - Bear source classifications: `9` pursuit bonus-draw rows and `87` true bear bonus-draw rows.
  - Bear comparison to current `DATABASE.csv` 2025 fields: `37` matches, `55` differences requiring lineage review, `4` source codes missing from current DATABASE (`BR7008`, `BR7019`, `BR7108`, `BR7208`).
  - Bear draw source is historical draw-results evidence (`reported_draw_year=2024`, `model_target_year=2025`) and was not promoted into 2026 availability fields.
- Validation:
  - `python scripts\clear-elk-private-lands-el-lo-2026-permit-fields.py` passed and is idempotent.
  - `python scripts\audit-elk-private-lands-el-lo-2026.py` passed after cleanup.
  - `python scripts\extract-black-bear-2024-draw-odds-permits.py` passed.
  - `python -m py_compile scripts\clear-elk-private-lands-el-lo-2026-permit-fields.py scripts\extract-black-bear-2024-draw-odds-permits.py tests\utah\test_elk_private_lands_el_lo_clear_2026.py tests\utah\test_black_bear_2024_draw_odds_extraction.py tests\utah\test_elk_private_lands_el_lo_audit_2026.py` passed.
  - `python -m pytest tests\utah\test_elk_private_lands_el_lo_clear_2026.py tests\utah\test_elk_private_lands_el_lo_audit_2026.py tests\utah\test_elk_private_land_resolution_2026.py tests\utah\test_black_bear_2024_draw_odds_extraction.py tests\utah\test_black_bear_permit_normalization_2026.py -q` passed: `16`.

## Black Bear BR 2024-2025-2026 Draw/Permit Crosswalk
- Timestamp (UTC): 2026-05-26T14:50:00Z
- Scope:
  - Added an executable cross-comparison for black bear `BR` hunt codes across the 2024 draw-odds PDF, the user-supplied 2025 draw-odds PDF, and the current 2026 DWR Hunt Planner permit overlay.
  - Extracted the 2025 black bear draw-odds PDF as model-target-year 2026 historical draw evidence.
  - Built a reviewed BR crosswalk artifact that resolves high-confidence historical recodes without modifying protected `DATABASE.csv` current permit cells.
  - Preserved current-only Dolores Triangle split rows and conservation rows as source evidence instead of forcing them into public draw-result rows.
- Outputs:
  - `scripts/crosscompare-black-bear-draw-odds-2024-2025-2026.py`
  - `tests/utah/test_black_bear_br_crosscompare_2024_2025_2026.py`
  - `data_truth/draw_results_truth/normalized/black_bear_2025_draw_odds_model_target_2026_permit_totals.csv`
  - `data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv`
  - `data_truth/crosswalk_truth/validation/black_bear_BR_2024_2025_2026_crosswalk_summary.json`
  - `processed_data/black_bear_BR_2024_2025_2026_crosswalk.md`
- Key results:
  - 2024 draw rows: `96`; 2025 draw rows: `97`; current 2026 permit rows: `106`.
  - 2025 draw total public permits: `994`; current 2026 numeric permit total: `1020`.
  - 2024-only draw code: `BR7019`.
  - 2025-only versus 2024 draw codes: `BR7237` and `BR7325`.
  - High-confidence recodes: `BR7008 -> BR7022`, `BR7108 -> BR7127`, `BR7208 -> BR7239`, and `BR7307 -> BR7326`.
  - `BR7307` is explicitly flagged as code reuse: historical 2025 La Sal limited-entry multiseason mapped to current `BR7326`, while current `BR7307` is the 2026 La Sal conservation package with `4` total permits and no resident/nonresident split.
  - After applying reviewed recodes, all `97` 2025 draw rows map to current 2026 hunt codes.
  - Remaining mapped 2025-to-2026 numeric differences: `BR7004->BR7004`, `BR7210->BR7210`, `BR7211->BR7211`, and `BR7317->BR7317`.
- Validation:
  - `python scripts\crosscompare-black-bear-draw-odds-2024-2025-2026.py` passed.
  - `python -m py_compile scripts\crosscompare-black-bear-draw-odds-2024-2025-2026.py tests\utah\test_black_bear_br_crosscompare_2024_2025_2026.py` passed.
  - `python -m pytest tests\utah\test_black_bear_br_crosscompare_2024_2025_2026.py -q` passed: `4`.

## Black Bear 2026 Reviewed Res/NR/Total Export
- Timestamp (UTC): 2026-05-26T15:10:00Z
- Scope:
  - Preserved the raw DWR Hunt Planner CSV with its two-line `Res:` / `NonRes:` source layout.
  - Extended the black bear 2026 normalizer to also write a reviewed, one-row-per-code CSV export beside the source pull with numeric `permits_2026_res`, `permits_2026_nr`, and `permits_2026_total` columns.
  - Added test coverage for the reviewed export and the four checked rows: `BR7004`, `BR7210`, `BR7211`, and `BR7317`.
- Outputs:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 black bear permits reviewed res-nr-total.csv`
  - `data_truth/permit_overlay_truth/normalized/black_bear_permits_2026_canonical.csv`
  - `data_truth/permit_overlay_truth/validation/black_bear_permits_2026_summary.json`
  - `processed_data/black_bear_permits_2026_summary.md`
- Key results:
  - Reviewed export rows: `106`.
  - Unique `BR` hunt codes: `106`.
  - `FULL_SPLIT` rows: `100`.
  - `TOTAL_ONLY` rows: `1` (`BR7307` conservation package total `4`, no published resident/nonresident split).
  - `NO_PUBLISHED_NUMERIC_PERMIT` rows: `5`.
  - Confirmed 2026 values: `BR7004 = 18/0/18`, `BR7210 = 3/0/3`, `BR7211 = 26/3/29`, and `BR7317 = 9/1/10`.
- Validation:
  - `python scripts\normalize-black-bear-permits-2026.py` passed.
  - `python -m py_compile scripts\normalize-black-bear-permits-2026.py tests\utah\test_black_bear_permit_normalization_2026.py` passed.
  - `python -m pytest tests\utah\test_black_bear_permit_normalization_2026.py -q` passed: `6`.

## Black Bear 2026 Production Library PDF/XLSX
- Timestamp (UTC): 2026-05-26T15:17:19Z
- Scope:
  - Built the library-facing production PDF and companion XLSX from the reviewed 2026 black bear res/non-res/total export.
  - Replaced the older black bear library PDF that exposed internal notes paths with a clean 10-column table: hunt name, hunt code, sex, species, weapon, hunt type, season, resident permits, nonresident permits, and total permits.
  - Preserved the existing library manifest path by regenerating `2026_BLACK_BEAR.pdf` and `2026_BLACK_BEAR.xlsx` in place.
  - Added a validation JSON artifact for the production document build.
  - Added an explicit `BR7307` code-reuse warning: in 2026, `BR7307` is the La Sal multiseason conservation package with 4 total permits and no resident/nonresident split; older La Sal limited-entry multiseason history crosswalks to current `BR7326`.
- Outputs:
  - `scripts/build-black-bear-production-documents-2026.py`
  - `tests/utah/test_black_bear_production_documents_2026.py`
  - `processed_data/hard_data_exports/hunt_tables/2026/2026_BLACK_BEAR.pdf`
  - `processed_data/hard_data_exports/hunt_tables/2026/2026_BLACK_BEAR.xlsx`
  - `processed_data/hard_data_exports/hunt_tables/2026/2026_BLACK_BEAR.validation.json`
- Key results:
  - Production rows: `106`.
  - Unique `BR` hunt codes: `106`.
  - Permit status counts: `100` full resident/nonresident splits, `1` total-only conservation package, and `5` rows with no published numeric permit count.
  - Numeric 2026 total permits represented: `1020`.
  - Checked values: `BR7004 = 18/0/18`, `BR7210 = 3/0/3`, `BR7211 = 26/3/29`, `BR7307 = total-only 4`, `BR7317 = 9/1/10`, and `BR7326 = 13/1/14`.
  - PDF validation confirmed the title, checked codes, the `BR7307` code-reuse note, and no `../notes/DATABASE` internal path leakage.
- Validation:
  - `python scripts\build-black-bear-production-documents-2026.py` passed.
  - `python -m py_compile scripts\build-black-bear-production-documents-2026.py tests\utah\test_black_bear_production_documents_2026.py` passed.
  - `python -m pytest tests\utah\test_black_bear_production_documents_2026.py tests\utah\test_black_bear_permit_normalization_2026.py -q` passed: `10`.

## Desert Bighorn 2026 Public/OIAL Permit Audit And Parallel Conservation Crosswalk
- Timestamp (UTC): 2026-05-26T15:46:12Z
- Scope:
  - Normalized the reviewed 2026 public/once-in-a-lifetime desert bighorn permit rows from the DWR Hunt Planner source file.
  - Split source `Res:` and `NonRes:` values into reviewed numeric `permits_2026_res`, `permits_2026_nr`, and `permits_2026_total` fields.
  - Cross-checked those 18 public/OIAL rows against `DATABASE.csv` and the 2026 RAC/OIAL comparison CSV.
  - Added mapping-law columns to the reviewed DS export: `hunt_code`, `boundary_id`, `hunt_code_mapping_status`, `boundary_id_mapping_status`, `candidate_hunt_code`, and `candidate_boundary_id`.
  - Resolved the DS conservation mismatch class by marking conservation rows as parallel one-permit opportunities, not replacements for the public once-in-a-lifetime rows.
  - Updated the current-to-historical crosswalk builder so DS conservation rows use `PROMOTED_PARALLEL_PUBLIC_UNIT_REFERENCE`.
  - Did not change protected `DATABASE.csv` numeric cells.
- Outputs:
  - `scripts/normalize-desert-bighorn-permits-2026.py`
  - `tests/utah/test_desert_bighorn_permit_normalization_2026.py`
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 desert bighorn reviewed res-nr-total.csv`
  - `data_truth/permit_overlay_truth/normalized/desert_bighorn_permits_2026_canonical.csv`
  - `data_truth/permit_overlay_truth/validation/desert_bighorn_permits_2026_vs_DATABASE.csv`
  - `data_truth/permit_overlay_truth/validation/desert_bighorn_permits_2026_vs_RAC.csv`
  - `data_truth/permit_overlay_truth/validation/desert_bighorn_public_vs_conservation_parallel_2026.csv`
  - `data_truth/permit_overlay_truth/validation/desert_bighorn_permits_2026_summary.json`
  - `processed_data/desert_bighorn_permits_2026_summary.md`
  - `data_truth/crosswalk_truth/normalized/current_to_historical_hunt_code_crosswalk_2026.csv`
  - `data_truth/crosswalk_truth/validation/current_to_historical_hunt_code_crosswalk_2026_summary.json`
- Key results:
  - Public/OIAL DS source rows: `18`.
  - Unique public/OIAL DS hunt codes: `18`.
  - Public/OIAL 2026 total permits: `85`.
  - DATABASE comparison: `18` matches, `0` mismatches.
  - RAC comparison: `18` matches, `0` mismatches.
  - Resolved parallel conservation rows: `DS1002 -> DS6601`, `DS1003 -> DS6626|DS6627`, `DS1004 -> DS6608|DS6624`, `DS1006 -> DS6603`, `DS1007 -> DS6610`, and `DS6605 -> DS6621`.
  - Crosswalk status counts now include `6` `PROMOTED_PARALLEL_PUBLIC_UNIT_REFERENCE` rows.
- Validation:
  - `python scripts\normalize-desert-bighorn-permits-2026.py` passed.
  - `python scripts\build-current-historical-hunt-code-crosswalk-2026.py` passed.
  - `python -m py_compile scripts\normalize-desert-bighorn-permits-2026.py scripts\build-current-historical-hunt-code-crosswalk-2026.py tests\utah\test_desert_bighorn_permit_normalization_2026.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py` passed.
  - `python -m pytest tests\utah\test_desert_bighorn_permit_normalization_2026.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py -q` passed: `7`.

## 2025 All O.I.L. Draw Results Extraction
- Timestamp (UTC): 2026-05-26T15:57:29Z
- Scope:
  - Registered and extracted the user-supplied `2025 O.I.L. Draw Results.pdf` as historical draw-results evidence.
  - Applied project year rules: `reported_draw_year=2025`, `model_target_year=2026`.
  - Extracted one hunt-code row from every PDF page with resident/nonresident eligible applicants, bonus permits, regular permits, total draw permits, source PDF page, source report page, and SHA-256.
  - Added research-library mapping-law fields to the normalized draw-results rows.
  - Compared the extracted totals to `DATABASE.csv` 2025 draw-result fields only; no current 2026 permit/allotment cells were modified.
- Outputs:
  - `scripts/extract-oil-2025-draw-results-permits.py`
  - `tests/utah/test_oil_2025_draw_results_extraction.py`
  - `data_truth/draw_results_truth/normalized/oil_2025_draw_results_model_target_2026_permit_totals.csv`
  - `data_truth/draw_results_truth/validation/oil_2025_draw_results_model_target_2026_vs_DATABASE.csv`
  - `data_truth/draw_results_truth/validation/oil_2025_draw_results_model_target_2026_summary.json`
  - `processed_data/oil_2025_draw_results_model_target_2026_permit_totals.md`
- Key results:
  - PDF pages extracted: `101`.
  - Unique hunt codes: `101`.
  - Prefix counts: `BI=15`, `DS=18`, `GO=17`, `MB=36`, `RS=15`.
  - Source total public draw permits: `502` (`457` resident, `45` nonresident).
  - DATABASE comparison: `89` matches against `permits_2025_draw_*`, `0` numeric differences, `0` blank draw fields.
  - Historical source codes missing from current `DATABASE.csv`: `12`, all CWMU bull moose rows: `MB6200`, `MB6207`, `MB6209`, `MB6217`, `MB6220`, `MB6223`, `MB6224`, `MB6225`, `MB6240`, `MB6254`, `MB6257`, and `MB6259`.
- Validation:
  - `python scripts\extract-oil-2025-draw-results-permits.py` passed.
  - `python -m py_compile scripts\extract-oil-2025-draw-results-permits.py tests\utah\test_oil_2025_draw_results_extraction.py` passed.
  - `python -m pytest tests\utah\test_oil_2025_draw_results_extraction.py -q` passed: `4`.

## Rocky Mountain Bighorn 2026 Permit Audit And Parallel Conservation Crosswalk
- Timestamp (UTC): 2026-05-26T16:05:25Z
- Scope:
  - Registered the user-supplied current Utah DWR Hunt Planner Rocky Mountain bighorn `RS/RE` rows as source evidence.
  - Normalized the 2026 resident, nonresident, and total permit fields into a reviewed export with mapping-law columns.
  - Cross-checked reviewed rows against canonical `DATABASE.csv`, the RAC/OIAL Rocky Mountain bighorn comparison CSV, and the RAC ewe comparison CSV.
  - Filled blank conservation/statewide count cells from canonical `DATABASE.csv` only where `DATABASE.csv` already had populated 2026 values.
  - Resolved the `RS100x` conservation/current mismatch class by marking those rows as parallel permit opportunities, not replacements for the public once-in-a-lifetime rows.
  - Updated the current-to-historical crosswalk builder so `RS1000`, `RS1001`, `RS1003`, and `RS1006` use `PROMOTED_PARALLEL_PUBLIC_UNIT_REFERENCE`.
  - Did not change protected `DATABASE.csv` numeric cells.
- Outputs:
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 rocky mountain bighorn user verified.csv`
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 rocky mountain bighorn reviewed res-nr-total.csv`
  - `scripts/normalize-rocky-bighorn-permits-2026.py`
  - `tests/utah/test_rocky_bighorn_permit_normalization_2026.py`
  - `data_truth/permit_overlay_truth/normalized/rocky_bighorn_permits_2026_canonical.csv`
  - `data_truth/permit_overlay_truth/validation/rocky_bighorn_permits_2026_vs_DATABASE.csv`
  - `data_truth/permit_overlay_truth/validation/rocky_bighorn_permits_2026_vs_RAC.csv`
  - `data_truth/permit_overlay_truth/validation/rocky_bighorn_public_vs_conservation_parallel_2026.csv`
  - `data_truth/permit_overlay_truth/validation/rocky_bighorn_permits_2026_summary.json`
  - `processed_data/rocky_bighorn_permits_2026_summary.md`
  - `data_truth/crosswalk_truth/normalized/current_to_historical_hunt_code_crosswalk_2026.csv`
  - `data_truth/crosswalk_truth/validation/current_to_historical_hunt_code_crosswalk_2026_summary.json`
- Key results:
  - Source rows: `21`.
  - Unique `RS/RE` hunt codes: `21`.
  - Numeric 2026 total permits carried in reviewed output: `60`.
  - DATABASE numeric comparison: `0` mismatches.
  - RAC numeric comparison: `0` mismatches.
  - One row has no published numeric permit count: `RS1000`.
  - Semantic review flags: `16` rows where current source sex/season wording differs from `DATABASE.csv`; no numeric changes were made.
  - Resolved parallel conservation/current rows: `RS1000 -> RS6700`, `RS1001 -> RS6701`, `RS1003 -> RS6703|RS6704|RS6722`, and `RS1006 -> RS6712`.
- Validation:
  - `python scripts\normalize-rocky-bighorn-permits-2026.py` passed.
  - `python scripts\build-current-historical-hunt-code-crosswalk-2026.py` passed.
  - `python -m py_compile scripts\normalize-rocky-bighorn-permits-2026.py scripts\build-current-historical-hunt-code-crosswalk-2026.py` passed.
  - `python -m pytest tests\utah\test_rocky_bighorn_permit_normalization_2026.py tests\utah\test_current_historical_hunt_code_crosswalk_2026.py -q` passed: `7`.

## Buck Deer 2026 Permit Audit And 2025 LE Deer Draw Results Extraction
- Timestamp (UTC): 2026-05-26T16:14:20Z
- Scope:
  - Normalized the 2026 limited-entry buck deer `DB` source rows into reviewed resident, nonresident, and total permit fields.
  - Normalized the 2026 limited-entry private-land deer `LD/LO` rows into a reviewed no-quota-published export.
  - Repaired the reviewed private-land export for `LO0010`, which is present in canonical `DATABASE.csv` and the user-supplied DWR Hunt Planner row but omitted from the local private-land source CSV.
  - Compared 2026 `DB/LD/LO` rows against protected `DATABASE.csv` and RAC limited-entry buck deer comparison evidence.
  - Extracted the attached `2025 LE Deer Draw Results.pdf` into per-hunt-code draw-result permit totals using project year rules: `reported_draw_year=2025`, `model_target_year=2026`.
  - Compared extracted 2025 draw-result totals to `DATABASE.csv` 2025 draw-result fields only.
  - Did not change protected `DATABASE.csv` numeric cells.
- Outputs:
  - `scripts/normalize-buck-deer-permits-2026.py`
  - `scripts/extract-le-deer-2025-draw-results-permits.py`
  - `tests/utah/test_buck_deer_permit_normalization_2026.py`
  - `tests/utah/test_le_deer_2025_draw_results_extraction.py`
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 buck deer limited entry reviewed res-nr-total.csv`
  - `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 buck deer private land reviewed res-nr-total.csv`
  - `data_truth/permit_overlay_truth/normalized/buck_deer_permits_2026_canonical.csv`
  - `data_truth/permit_overlay_truth/validation/buck_deer_permits_2026_vs_DATABASE.csv`
  - `data_truth/permit_overlay_truth/validation/buck_deer_limited_entry_2026_vs_RAC.csv`
  - `data_truth/permit_overlay_truth/validation/buck_deer_private_land_2026_source_completeness.csv`
  - `data_truth/permit_overlay_truth/validation/buck_deer_permits_2026_summary.json`
  - `data_truth/draw_results_truth/normalized/le_deer_2025_draw_results_model_target_2026_permit_totals.csv`
  - `data_truth/draw_results_truth/validation/le_deer_2025_draw_results_model_target_2026_vs_DATABASE.csv`
  - `data_truth/draw_results_truth/validation/le_deer_2025_draw_results_model_target_2026_summary.json`
  - `processed_data/buck_deer_permits_2026_summary.md`
  - `processed_data/le_deer_2025_draw_results_model_target_2026_permit_totals.md`
- Key results:
  - 2026 limited-entry `DB` rows: `67`.
  - 2026 limited-entry private-land `LD/LO` rows: `9`.
  - 2026 numeric total permits represented: `1428`.
  - DATABASE numeric comparison for 2026 permit rows: `0` mismatches.
  - RAC numeric comparison for 2026 limited-entry `DB` subset: `0` mismatches.
  - Private-land source omission repaired in reviewed export: `LO0010`.
  - 2025 LE Deer PDF pages: `196`; extracted hunt-code rows: `195`.
  - 2025 LE Deer draw-result total public permits: `1714` (`1560` resident, `154` nonresident).
  - DATABASE comparison for 2025 LE Deer draw results: `189` matches, `0` numeric differences, and `6` historical CWMU source codes missing from current `DATABASE.csv`: `DB1320`, `DB1324`, `DB1343`, `DB1344`, `DB1345`, and `DB1348`.
  - Semantic review flags: `DB1090`, `DB1091`, `DB1105`, and `DB1116` have HAMSS label placement differences between source and `DATABASE.csv`; numeric fields match.
- Validation:
  - `python scripts\normalize-buck-deer-permits-2026.py` passed.
  - `python scripts\extract-le-deer-2025-draw-results-permits.py` passed.
  - `python -m py_compile scripts\normalize-buck-deer-permits-2026.py scripts\extract-le-deer-2025-draw-results-permits.py tests\utah\test_buck_deer_permit_normalization_2026.py tests\utah\test_le_deer_2025_draw_results_extraction.py` passed.
  - `python -m pytest tests\utah\test_buck_deer_permit_normalization_2026.py tests\utah\test_le_deer_2025_draw_results_extraction.py -q` passed: `7`.

## Rocky Mountain Bighorn Sex-Type Correction
- Timestamp (UTC): 2026-05-26T16:18:17Z
- Scope:
  - Corrected Rocky Mountain bighorn semantic labels so `RS` rows are `Ram` and `RE` rows are `Ewe`.
  - Updated canonical `DATABASE.csv` sex-type values for all current Rocky Mountain bighorn rows.
  - Updated the reviewed Rocky Mountain bighorn permit source/export and regenerated the normalized permit audit outputs.
  - Updated O.I.L. draw extraction logic so historical `RS` draw-result rows extract as `Ram` instead of `Male Only`.
  - Regenerated the 2025 O.I.L. draw-results normalized and validation outputs after the sex-type correction.
  - Rebuilt the current-to-historical crosswalk output after the corrected `DATABASE.csv` semantic values.
  - Did not change protected numeric permit/allotment fields.
- Key results:
  - Canonical `DATABASE.csv` Rocky Mountain bighorn sex-type counts now show `20` `Ram` rows and `1` `Ewe` row.
  - Checked primary Rocky artifacts show no `Either Sex` values for `RS/RE` Rocky Mountain bighorn rows.
  - Rocky permit numeric comparison remains clean: `0` DATABASE mismatches and `0` RAC mismatches.
  - Remaining Rocky permit semantic review flags are date-text only: `RS6700` and `RE1000`; there are no sex-type review flags.
- Validation:
  - `python scripts\normalize-rocky-bighorn-permits-2026.py` passed.
  - `python scripts\extract-oil-2025-draw-results-permits.py` passed.
  - `python scripts\build-current-historical-hunt-code-crosswalk-2026.py` passed.
  - `python -m py_compile scripts\normalize-rocky-bighorn-permits-2026.py scripts\extract-oil-2025-draw-results-permits.py tests\utah\test_rocky_bighorn_permit_normalization_2026.py tests\utah\test_oil_2025_draw_results_extraction.py` passed.
  - `python -m pytest tests\utah\test_rocky_bighorn_permit_normalization_2026.py tests\utah\test_oil_2025_draw_results_extraction.py -q` passed: `8`.


## Merge-Preserved Remote Work Log Sections
- Timestamp (UTC): 2026-05-26T18:30:00Z
- Scope:
  - Preserved work-log sections that existed only on `origin/main` during merge conflict resolution.
  - No source data, website feed, or DATABASE values are changed by this merge-log marker.

## Live Domain Handoff To HUNT-BUILDER Repo
- Timestamp (UTC): 2026-05-24T04:38:00Z
- Scope:
  - Began moving the live GitHub Pages custom-domain claim from `UTAHOGA/HUNT-FROM-THE-FRONT` to `UTAHOGA/HUNT-BUILDER`.
  - Removed the source-branch `CNAME` from the old `HUNT-FROM-THE-FRONT` repo so `HUNT-BUILDER` can be the sole repo for `hunt-builder.uoga.org`.
  - No prediction data, runtime feed, or website content was changed.

## HUNT-BUILDER Repo Rename Confirmed
- Timestamp (UTC): 2026-05-24T04:40:00Z
- Scope:
  - Confirmed GitHub redirects the old `UTAHOGA/HUNT-FROM-THE-FRONT` remote to `UTAHOGA/HUNT-BUILDER`.
  - Restored the `CNAME` on `main` because `HUNT-BUILDER` is the renamed live repo, not a separate duplicate target.
  - Updated local remote naming to point directly at `UTAHOGA/HUNT-BUILDER`.

## Header Navigation Hover Instructions
- Timestamp (UTC): 2026-05-24T04:53:00Z
- Scope:
  - Added small hover/focus instruction popups to the shared primary header navigation.
  - Hints now explain Builder, Research, Outfitters, Library, and U.O.G.A. Home without adding more permanent page clutter.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.
- Validation:
  - `node --check header-layout.js` passed.
  - `python -m pytest tests/utah/test_header_layout.py -q` passed: `8`.
  - `python -m compileall tests/utah/test_header_layout.py` passed.
  - Local static smoke check confirmed `header-layout.js` serves with the new hover help text.

## Header UOGA Logo Link
- Timestamp (UTC): 2026-05-24T04:59:00Z
- Scope:
  - Added a cropped U.O.G.A. Wildlife Elevated license-plate logo asset to the shared website header.
  - The logo sits inside the header at the upper-left side and links to `https://www.uoga.org`.
  - Bumped the `header-layout.js` cache-busting query on site pages so browsers pick up the new header behavior.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.
- Validation:
  - `node --check header-layout.js` passed.
  - `python -m pytest tests/utah/test_header_layout.py -q` passed: `9`.
  - `python -m compileall tests/utah/test_header_layout.py` passed.
  - Local static smoke check confirmed the logo asset and updated header script serve successfully.

## Header Logo Removed
- Timestamp (UTC): 2026-05-24T05:05:00Z
- Scope:
  - Removed the upper-left header logo after layout review showed it consumed too much header space.
  - Removed the temporary cropped logo asset and bumped the `header-layout.js` cache tag to force the no-logo header layout.
  - Preserved the shared navigation hover instructions and all domain/CNAME settings.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.

## Header Nav Inline Helper Text
- Timestamp (UTC): 2026-05-24T05:19:00Z
- Scope:
  - Replaced the floating nav helper popups with inline hover/focus helper text inside each navigation pill.
  - Shortened helper copy so it fits within each pill without expanding the header.
  - Removed the orange underline from the selected nav pill while preserving selected-page white text.
  - Bumped the `header-layout.js` cache tag again so browsers fetch the inline-helper script instead of the older floating-popup script.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.
- Validation:
  - `node --check header-layout.js` passed.
  - `python -m pytest tests/utah/test_header_layout.py -q` passed: `8`.
  - `python -m compileall tests/utah/test_header_layout.py` passed.
  - Local static smoke check confirmed the inline helper text is present and the selected underline CSS is absent.

## Header Nav Helper Copy Refinement
- Timestamp (UTC): 2026-05-24T05:28:00Z
- Scope:
  - Updated inline nav helper copy to the final visitor-facing wording:
    Builder `FIND YOUR DREAM HUNT`, Research `MATCH HUNT TO YOUR POINTS`, Outfitters `FIND YOUR OUTFITTER`, Library `CANONICAL DOCS`.
  - No layout, prediction data, runtime feeds, permit logic, or model outputs were changed.

## Header Nav Replacement Helper Final
- Timestamp (UTC): 2026-05-24T05:40:00Z
- Scope:
  - Kept the helper behavior as text replacement inside the same nav pill rather than a separate advice line.
  - Updated helper copy to: Builder `FIND YOUR DREAM HUNT`, Research `MATCH THE HUNT TO YOUR POINTS`, Outfitters `FIND YOUR OUTFITTER`, Library `YOUR BIBLE SOURCE DOCS`.
  - Active/selected nav pills do not show helper replacement text.
  - Pill dimensions remain unchanged and the selected underline remains removed.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.
- Validation:
  - `node --check header-layout.js` passed.
  - `python -m pytest tests/utah/test_header_layout.py -q` passed: `8`.
  - `python -m compileall tests/utah/test_header_layout.py` passed.

## Header Nav Two-Line Helper Text
- Timestamp (UTC): 2026-05-24T06:05:00Z
- Scope:
  - Updated the nav replacement helper text to two-line white text inside the same fixed-size pill.
  - Renamed the visible `HUNT LIBRARY` nav label to `HUNTING BIBLE`.
  - Helper copy now uses: Builder `FIND YOUR / DREAM HUNT`, Research `MATCH / HUNT = POINTS`, Outfitters `OPTIMIZE / YOUR ODDS`, Hunting Bible `YOUR BIBLE / SOURCE DOCS`.
  - Active/selected nav pills still do not show helper replacement text.
  - Bumped the `header-layout.js` cache tag to `20260524-bible-help-1`.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.

## Header Nav Cache Refresh
- Timestamp (UTC): 2026-05-24T06:18:00Z
- Scope:
  - Bumped the shared header script cache tag to `20260524-bible-help-2` on all static pages.
  - This is a deploy refresh only; the two-line helper text, `HUNTING BIBLE` label, and selected-page behavior are unchanged.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.

## Header Nav Helper Text Enlargement
- Timestamp (UTC): 2026-05-24T06:31:00Z
- Scope:
  - Enlarged the in-pill helper replacement text from `10px` to `12px` so it matches the normal nav title size more closely.
  - Tightened helper letter spacing and strengthened the white text shadow so the two-line copy reads as the button title instead of a small inset note.
  - Bumped the shared header script cache tag to `20260524-bible-help-3`.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.

## Hunt Research Guaranteed Line Highlight Fix
- Timestamp (UTC): 2026-05-24T07:11:00Z
- Scope:
  - Updated the point ladder row classification so the orange guaranteed-line highlight applies to the modeled 2026 cutoff row, falling back to `guaranteed_at_2026` when no cutoff is available.
  - Changed the ladder marker label to `Guaranteed Line` for that row and preserved the requested orange `rgb(250, 120, 0)` with the dark brown outline.
  - Applied the orange fill to the guaranteed-line row cells as well as the row container so the highlight cannot be washed out by table-cell backgrounds.
  - Bumped the `hunt-research.js` cache tag to `20260524-guaranteed-line-1`.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.

## Hunt Research Guaranteed Line Field Correction
- Timestamp (UTC): 2026-05-24T07:43:00Z
- Scope:
  - Corrected the orange guaranteed-line row to use `guaranteed_at_2026` before `projected_2026_max_cutoff_point`, matching the top summary value.
  - Confirmed the MB6011 Resident data pattern: `guaranteed_at_2026 = 29` while `projected_2026_max_cutoff_point = 28.0`, so 28 is the mixed cutoff boundary, not the guaranteed-to-draw line.
  - Bumped the `hunt-research.js` cache tag to `20260524-guaranteed-line-2`.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.

## Hunt Research Hunt Data Pill Cleanup
- Timestamp (UTC): 2026-05-24T08:05:00Z
- Scope:
  - Reduced point-ladder data pills so they appear only on the selected hunter-point row and the true guaranteed-line row.
  - Renamed the ladder marker button from `Sources` to `Hunt Data` to better describe the cumulative source snapshot.
  - Added a `Hunt Data` action to Hunt Backpack items that links to the Hunting Bible with the hunt code carried forward.
  - Bumped the `ui.js` cache tag on Hunt Research to `20260524-backpack-hunt-data-1`.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.

## 2026 Big Game Application Guidebook Ingest Verification
- Timestamp (UTC): 2026-05-24T08:37:00Z
- Scope:
  - Verified `pipeline/RAW/hunt_unit_database/2026/pdf/regulations/2026 Big Game Application.pdf` is already present in the raw PDF inventory.
  - Verified the Hunting Bible export copy exists at `processed_data/hard_data_exports/source_pdfs/regulations/2026/2026-big-game-application-guidebook.pdf`.
  - Verified the exported PDF SHA-256 matches the raw source PDF, so the library copy is byte-for-byte identical to the official source file.
  - Verified the hard-copy manifest exposes it as `2026 Big Game Application Guidebook` with `group = regulation` and `source_role = official_source`.
  - Kept the guidebook as regulation/reference material only; it is not promoted as draw-results truth, harvest truth, quota input, or prediction math input.
  - Hardened the hard-copy publish script so it can read JSON manifests with a UTF-8 byte-order marker and skip unnecessary manifest rewrites when entries are already correct.
  - Re-ran the hard-copy harvest/regulation publisher; it confirmed the guidebook entry was already present and refreshed the 2025 preliminary big-game harvest report export to match its raw source PDF.
  - No prediction data, runtime feeds, permit logic, or model outputs were changed.

## 2026 Big Game Application Guidebook Database Audit
- Timestamp (UTC): 2026-05-24T09:20:00Z
- Scope:
  - Added a repeatable guidebook audit that extracts 728 hunt codes from the 2026 Big Game Application Guidebook hunt-table pages and compares them to `DATABASE.csv`.
  - Materialized the regulation-reference hunt table at `data_truth/regulations_truth/normalized/2026_big_game_application_guidebook_hunt_tables.csv`.
  - Wrote comparison outputs at `processed_data/2026_big_game_application_guidebook_vs_DATABASE.csv`, `.json`, and `.md`.
  - Confirmed all 728 extracted guidebook hunt codes exist in `DATABASE.csv`.
  - Found one real season-date conflict from the pasted/official guidebook text: `RS6700` Antelope Island Rocky Mountain bighorn sheep is `Nov. 9-Nov. 16`, while the database/catalog had `Nov 11-Nov 18`.
  - Patched `RS6700` season to `Nov 09, 2026 - Nov 16, 2026` where the existing file format used comma-style dates, and `Nov 09 2026 - Nov 16 2026` where the existing file format used no-comma dates.
  - Left remaining guidebook warnings as label-only review notes for management/HAMSS display naming; no remaining season mismatches or missing guidebook hunt codes.
  - No permit counts, draw odds, harvest features, quota fields, or prediction math were changed.
- Validation:
  - `python scripts/audit-big-game-application-guidebook-2026.py` passed with `728` guidebook hunt codes, `728` database matches, `0` missing codes, `0` season review warnings and `0` blockers.
  - `python -m pytest tests/utah/test_big_game_application_guidebook_ingest.py tests/utah/test_big_game_application_guidebook_database_audit.py -q` passed: `5`.
  - `python -m compileall scripts\audit-big-game-application-guidebook-2026.py scripts\patch-big-game-application-guidebook-season-corrections-2026.py tests\utah\test_big_game_application_guidebook_ingest.py tests\utah\test_big_game_application_guidebook_database_audit.py` passed.
  - `npm.cmd run verify:permits-2026` passed with `promotion_blockers = 0`.
  - `python scripts/build-database-publish-readiness-report.py` passed with `publish_ready = true`.

## 2026 Big Game Application Guidebook Post-Publication Corrections
- Timestamp (UTC): 2026-05-24T10:10:00Z
- Scope:
  - Added the official post-publication correction notes to the repeatable guidebook audit as regulation/reference corrections.
  - Materialized the correction audit at `data_truth/regulations_truth/normalized/2026_big_game_application_guidebook_post_publication_corrections.csv`.
  - Confirmed `DB1276` Plymouth Peak is absent and superseded by `DB1306` Washakie CWMU.
  - Confirmed `MB6264` Sand Creek CWMU moose and `DB1350` Milburn CWMU buck deer are absent from the corrected guidebook reference and current DATABASE.
  - Confirmed `DB1115` is named `Little Rockies` in both the corrected guidebook reference and DATABASE.
  - Kept these notes as regulation/reference corrections only; no permit counts, draw odds, harvest features, quota fields, or prediction math were changed.
- Validation:
  - `python scripts/audit-big-game-application-guidebook-2026.py` passed with `4` post-publication corrections checked and `0` correction review items.
  - `python -m compileall scripts\audit-big-game-application-guidebook-2026.py tests\utah\test_big_game_application_guidebook_database_audit.py` passed.

## 2025 Big Game Field Regulations Source Label Audit
- Timestamp (UTC): 2026-05-24T10:45:00Z
- Scope:
  - Added a repeatable source-label audit for `pipeline/RAW/hunt_unit_database/2025/pdf/regulation/field_regs 2025.pdf`.
  - Confirmed the PDF is the `2025 Utah Big Game Field Regulations` source, with SHA-256 `05a87b5babd0a22af62c993bd3fe0ba106fb18f7029ed60fc75f6babe4dbdaa7`.
  - Confirmed no Hunting Bible/hard-copy manifest entry currently labels this PDF as `2026 Field Regulations`.
  - Confirmed the source is not exported to the Hunting Bible yet and is not present in the quality raw PDF inventory/promoted source manifests.
  - Captured the pasted post-publication corrections and updates in `data_truth/regulations_truth/normalized/2025_big_game_field_regulations_post_publication_corrections.csv`.
  - Kept the file as regulation/reference material only; no permit counts, draw odds, harvest features, quota fields, or prediction math were changed.
- Validation:
  - `python scripts/audit-big-game-field-regulations-2025.py` passed with `9` source-label checks and `0` blockers.
  - `python -m pytest tests/utah/test_big_game_field_regulations_2025_source_audit.py -q` passed: `2`.
  - `python -m compileall scripts\audit-big-game-field-regulations-2025.py tests\utah\test_big_game_field_regulations_2025_source_audit.py` passed.

## 2025 Big Game Field Regulations Comprehensive Text Audit
- Timestamp (UTC): 2026-05-24T09:35:00Z
- Scope:
  - Expanded the 2025 field-regulations audit into a page/line/token cross-check against `pipeline/RAW/hunt_unit_database/2025/pdf/regulation/field_regs 2025.pdf`.
  - Materialized every extracted PDF text line with source file, PDF page, printed page, line number, and text.
  - Materialized every extracted date, number/money, phone/code, and Utah Admin./Code citation token with page and line traceability.
  - Added 50 pasted-data anchor checks covering contents, season dates, license/application fees, over-the-counter dates, youth elk updates, CWD/reporting rules, weapon restrictions, special restrictions, donation/Red Butte removals, antlerless/CWMU sections, and definitions.
  - Confirmed the PDF is the 2025 field-regulations source only and remains regulation/reference material, not draw odds, harvest feature, quota, prediction, or 2026 field-regulations input.
  - No raw PDF, website feed, permit counts, draw odds, harvest features, quota fields, or prediction math were changed.
- Outputs:
  - `data_truth/regulations_truth/normalized/2025_big_game_field_regulations_text_lines.csv`
  - `data_truth/regulations_truth/normalized/2025_big_game_field_regulations_number_tokens.csv`
  - `data_truth/regulations_truth/normalized/2025_big_game_field_regulations_expected_text_checks.csv`
  - `processed_data/2025_big_game_field_regulations_source_label_audit.json`
  - `processed_data/2025_big_game_field_regulations_source_label_audit.md`
- Key results:
  - PDF pages: `68`.
  - Extracted text lines: `3723`.
  - Extracted number/date/citation tokens: `1483`.
  - Token type counts: `1217` number/money, `141` code citation, `125` date.
  - Pasted-data anchor checks: `50`.
  - Pasted-data anchor failures: `0`.
  - Audit blockers: `0`.
- Validation:
  - `python scripts\audit-big-game-field-regulations-2025.py` passed.
  - `python -m pytest tests\utah\test_big_game_field_regulations_2025_source_audit.py -q` passed: `3`.
  - `python -m compileall scripts\audit-big-game-field-regulations-2025.py tests\utah\test_big_game_field_regulations_2025_source_audit.py` passed.

## 2026 Big Game Hunt Code Reconciliation
- Timestamp (UTC): 2026-05-24T09:55:00Z
- Scope:
  - Added a repeatable hunt-code reconciliation that starts from the corrected 2026 Big Game Application Guidebook hunt table and checks every guidebook code against the core source/database/runtime reference surfaces.
  - Required surfaces checked: `DATABASE.csv`, `hunt_master_enriched.csv`, `hunt_unit_reference_linked.csv`, `point_ladder_view.csv`, and `draw_reality_engine.csv`.
  - Kept `draw_reality_engine_predictive_v2.csv` as an optional predictive coverage surface so source-code reconciliation is not confused with model-row coverage.
  - No raw PDF, website feed, permit count, draw odds, harvest feature, quota field, or prediction math was changed.
- Outputs:
  - `processed_data/2026_big_game_hunt_code_reconciliation.csv`
  - `processed_data/2026_big_game_hunt_code_reconciliation_summary.json`
  - `processed_data/2026_big_game_hunt_code_reconciliation.md`
- Key results:
  - Corrected guidebook hunt codes checked: `728`.
  - Codes present in all required surfaces: `728`.
  - Required-surface blockers: `0`.
  - Missing by required surface: `0` for every required surface.
  - Optional predictive coverage notes: `44` codes absent from `draw_reality_engine_predictive_v2.csv`.
  - Extra DATABASE codes not printed in the big-game application hunt tables: `683`, expected because DATABASE also carries antlerless and broader active reference rows.
- Validation:
  - `python scripts\reconcile-big-game-hunt-codes-2026.py` passed.
  - `python -m pytest tests\utah\test_big_game_application_guidebook_database_audit.py tests\utah\test_big_game_hunt_code_reconciliation.py -q` passed: `4`.
  - `python -m compileall scripts\reconcile-big-game-hunt-codes-2026.py tests\utah\test_big_game_hunt_code_reconciliation.py` passed.

## 2026 Big Game Predictive Guidebook Promotion And Bear/Cougar/Furbearer Audit
- Timestamp (UTC): 2026-05-24T09:57:00Z
- Scope:
  - Promoted the 44 corrected 2026 Big Game Application Guidebook hunt codes that were absent from `processed_data/draw_reality_engine_predictive_v2.csv`.
  - Added those rows as `GUIDEBOOK_TRUTH_REFERENCE` records only; hunt-code, permit-reference, season, weapon, and source lineage fields were populated, while draw odds remain explicitly unmodeled.
  - Materialized the promotion manifest and summary at `processed_data/2026_big_game_predictive_v2_guidebook_promotion.csv` and `.json`.
  - Refreshed the 2026 big-game hunt-code reconciliation; all 728 corrected guidebook codes now pass the optional predictive v2 surface check.
  - Added a full truth-source audit for `pipeline/RAW/hunt_unit_database/2026/pdf/regulations/2026 Bear Cougar Furbearer Guidebook.pdf`.
  - Materialized page/line text, number/date/code tokens, 55 pasted-data anchor checks, and 99 black-bear hunt-code rows from the Bear/Cougar/Furbearer guidebook.
  - Confirmed all 99 Bear guidebook `BR` hunt codes are present in both `DATABASE.csv` and `draw_reality_engine_predictive_v2.csv`.
  - No raw PDFs, website feeds, harvest features, or prediction probability math were changed.
- Outputs:
  - `processed_data/2026_big_game_predictive_v2_guidebook_promotion.csv`
  - `processed_data/2026_big_game_predictive_v2_guidebook_promotion_summary.json`
  - `data_truth/regulations_truth/normalized/2026_bear_cougar_furbearer_guidebook_text_lines.csv`
  - `data_truth/regulations_truth/normalized/2026_bear_cougar_furbearer_guidebook_number_tokens.csv`
  - `data_truth/regulations_truth/normalized/2026_bear_cougar_furbearer_guidebook_expected_text_checks.csv`
  - `data_truth/regulations_truth/normalized/2026_bear_cougar_furbearer_guidebook_bear_hunt_tables.csv`
  - `processed_data/2026_bear_cougar_furbearer_guidebook_audit.json`
  - `processed_data/2026_bear_cougar_furbearer_guidebook_audit.md`
- Key results:
  - Promoted guidebook truth-reference hunt codes into predictive v2: `44`.
  - Still-missing corrected 2026 big-game guidebook codes in predictive v2: `0`.
  - Bear/Cougar/Furbearer PDF pages: `88`.
  - Extracted Bear/Cougar/Furbearer text lines: `3501`.
  - Extracted Bear/Cougar/Furbearer number/date/code tokens: `2506`.
  - Bear/Cougar/Furbearer pasted-data anchor checks: `55`.
  - Bear/Cougar/Furbearer anchor failures: `0`.
  - Bear guidebook hunt codes checked: `99`.
  - Bear guidebook hunt codes missing DATABASE: `0`.
  - Bear guidebook hunt codes missing predictive v2: `0`.
- Validation:
  - `python scripts\promote-guidebook-codes-to-predictive-v2-2026.py` passed.
  - `python scripts\reconcile-big-game-hunt-codes-2026.py` passed with optional predictive missing count `0`.
  - `python scripts\audit-bear-cougar-furbearer-guidebook-2026.py` passed with `0` blockers.
  - `python -m pytest tests\utah\test_big_game_predictive_guidebook_promotion.py tests\utah\test_big_game_hunt_code_reconciliation.py tests\utah\test_bear_cougar_furbearer_guidebook_2026_audit.py -q` passed: `5`.
  - `python -m compileall scripts\promote-guidebook-codes-to-predictive-v2-2026.py scripts\audit-bear-cougar-furbearer-guidebook-2026.py tests\utah\test_big_game_predictive_guidebook_promotion.py tests\utah\test_big_game_hunt_code_reconciliation.py tests\utah\test_bear_cougar_furbearer_guidebook_2026_audit.py` passed.

## 2026 Turkey Guidebook Truth-Source Audit
- Timestamp (UTC): 2026-05-24T10:23:00Z
- Scope:
  - Added a repeatable truth-source audit for `pipeline/RAW/hunt_unit_database/2026/pdf/regulations/2026 Turkey.pdf`, titled `2025-26 Utah Upland Game and Turkey Guidebook`.
  - Materialized extracted PDF text lines, number/date/code tokens, expected pasted-data anchor checks, and turkey hunt-code/name reconciliation outputs.
  - Confirmed the guidebook's printed turkey hunt codes `TK1003`, `TK1004`, `TK1005`, `TK1006`, `TK1007`, `TK1018`, and `TK1021` all resolve to database hunt names.
  - Confirmed guidebook labels such as `Central (TK1003)` resolve to normalized database names such as `Central Area`.
  - Confirmed `TKY` is a bonus-point application code, not a `DATABASE.csv` hunt row, and should not be treated as a missing hunt name.
  - Confirmed all 7 printed turkey hunt codes are also present in `draw_reality_engine_predictive_v2.csv`.
  - No raw PDFs, website feeds, permit values, harvest features, or prediction probability math were changed.
- Outputs:
  - `data_truth/regulations_truth/normalized/2026_turkey_guidebook_text_lines.csv`
  - `data_truth/regulations_truth/normalized/2026_turkey_guidebook_number_tokens.csv`
  - `data_truth/regulations_truth/normalized/2026_turkey_guidebook_expected_text_checks.csv`
  - `data_truth/regulations_truth/normalized/2026_turkey_guidebook_hunt_code_name_reconciliation.csv`
  - `processed_data/2026_turkey_guidebook_audit.json`
  - `processed_data/2026_turkey_guidebook_audit.md`
- Key results:
  - PDF pages: `45`.
  - Extracted text lines: `2521`.
  - Extracted number/date/code tokens: `1968`.
  - Pasted-data anchor checks: `53`.
  - Anchor failures: `0`.
  - Printed turkey hunt codes checked: `7`.
  - Database name-resolved printed hunt codes: `7`.
  - Hunt-code reconciliation failures: `0`.
  - Bonus-point code handled separately: `TKY`.
  - Extra database turkey codes not printed in the guidebook code list: `11`.
- Validation:
  - `python scripts\audit-turkey-guidebook-2026.py` passed with `0` blockers.
  - `python -m pytest tests\utah\test_turkey_guidebook_2026_audit.py -q` passed: `3`.
  - `python -m compileall scripts\audit-turkey-guidebook-2026.py tests\utah\test_turkey_guidebook_2026_audit.py` passed.

## 2026 Bear Hunt-Code Resolution
- Timestamp (UTC): 2026-05-24T10:44:00Z
- Scope:
  - Expanded the 2026 Bear/Cougar/Furbearer guidebook audit to resolve the full black-bear `BR` code universe across current and historical surfaces.
  - Materialized `data_truth/regulations_truth/normalized/2026_bear_cougar_furbearer_guidebook_bear_hunt_code_reconciliation.csv`.
  - Classified all `BR` codes as guidebook-printed current hunt-table codes, current database reference codes not printed in the hunt tables, or historical-only draw-reality codes.
  - Confirmed current `DATABASE.csv`, `hunt_master_enriched.csv`, `point_ladder_view.csv`, and `draw_reality_engine_predictive_v2.csv` each carry `106` current bear codes.
  - Resolved the 7 current database reference codes not printed in the guidebook hunt tables: `BR1000`, `BR1001`, `BR1007`, `BR1018`, `BR7237`, `BR7307`, and `BR7324`.
  - Identified 14 historical-only bear codes present in `draw_reality_engine.csv` but not current 2026 `DATABASE.csv`: `BR7008`, `BR7019`, `BR7108`, `BR7208`, `BR7209`, `BR7226`, `BR7227`, `BR7230`, `BR7231`, `BR7232`, `BR7233`, `BR7234`, `BR7235`, and `BR7236`.
  - No raw PDFs, website feeds, permit values, harvest features, or prediction probability math were changed.
- Key results:
  - Guidebook-printed current bear hunt-table codes: `99`.
  - Current database bear codes: `106`.
  - Current predictive v2 bear codes: `106`.
  - Current hunt-master bear codes: `106`.
  - Current point-ladder bear codes: `106`.
  - Historical draw-reality bear codes: `120`.
  - Current database reference codes not printed in hunt tables: `7`.
  - Historical-only draw-reality bear codes: `14`.
  - Current bear-code reconciliation failures: `0`.
  - Audit blockers: `0`.
- Validation:
  - `python scripts\audit-bear-cougar-furbearer-guidebook-2026.py` passed with `0` blockers.
  - `python -m pytest tests\utah\test_bear_cougar_furbearer_guidebook_2026_audit.py -q` passed: `4`.
  - `python -m compileall scripts\audit-bear-cougar-furbearer-guidebook-2026.py tests\utah\test_bear_cougar_furbearer_guidebook_2026_audit.py` passed.

## 2026 Turkey Hunt-Code Resolution
- Timestamp (UTC): 2026-05-24T11:10:00Z
- Scope:
  - Added a repeatable full Turkey code resolver using the 2024-25 Upland Game and Turkey Guidebook as prior-year context and the already-audited 2025-26 guidebook as current guidebook context.
  - Materialized the 2024-25 guidebook text-line, token, expected-anchor, and hunt-code/name reconciliation truth-source outputs.
  - Confirmed the 2024-25 guidebook prints the same seven real Turkey hunt codes as the 2025-26 guidebook: `TK1003`, `TK1004`, `TK1005`, `TK1006`, `TK1007`, `TK1018`, and `TK1021`.
  - Confirmed `TKY` remains a bonus-point/application code and is not a missing `DATABASE.csv` hunt row.
  - Resolved all 18 current `DATABASE.csv` Turkey codes across `hunt_master_enriched.csv`, `point_ladder_view.csv`, `draw_reality_engine.csv`, and `draw_reality_engine_predictive_v2.csv`.
  - Promoted 10 current Turkey database-reference codes into predictive v2 as `TURKEY_GUIDEBOOK_REFERENCE` rows only: `TK1000`, `TK1001`, `TK1012`, `TK1013`, `TK1014`, `TK1015`, `TK1016`, `TK1019`, `TK1020`, and `TK1022`.
  - Kept those promoted rows non-modeled with no draw odds or probability fields invented.
  - No raw PDFs, website feeds, permit values, harvest features, or prediction probability math were changed.
- Outputs:
  - `data_truth/regulations_truth/normalized/2025_turkey_guidebook_text_lines.csv`
  - `data_truth/regulations_truth/normalized/2025_turkey_guidebook_number_tokens.csv`
  - `data_truth/regulations_truth/normalized/2025_turkey_guidebook_expected_text_checks.csv`
  - `data_truth/regulations_truth/normalized/2025_turkey_guidebook_hunt_code_name_reconciliation.csv`
  - `data_truth/regulations_truth/normalized/2026_turkey_full_hunt_code_reconciliation.csv`
  - `processed_data/2025_turkey_guidebook_audit.json`
  - `processed_data/2025_turkey_guidebook_audit.md`
  - `processed_data/2026_turkey_full_hunt_code_reconciliation_summary.json`
  - `processed_data/2026_turkey_full_hunt_code_reconciliation.md`
  - `processed_data/2026_turkey_predictive_v2_reference_promotion.csv`
  - `processed_data/2026_turkey_predictive_v2_reference_promotion_summary.json`
- Key results:
  - 2024-25 guidebook PDF pages: `63`.
  - 2024-25 extracted text lines: `3431`.
  - 2024-25 extracted number/date/code tokens: `2459`.
  - 2024-25 pasted-data anchor checks: `35`.
  - 2024-25 anchor failures: `0`.
  - Current `DATABASE.csv` Turkey codes: `18`.
  - 2025-26 guidebook-printed current Turkey hunt codes: `7`.
  - Current database Turkey codes not printed in the 2025-26 guidebook code list: `11`.
  - Current predictive v2 Turkey code coverage after reference promotion: `18`.
  - Full Turkey reconciliation blockers: `0`.
- Validation:
  - `python scripts\resolve-turkey-hunt-codes-2026.py` passed with `0` blockers.
  - `python -m pytest tests\utah\test_turkey_guidebook_2026_audit.py tests\utah\test_turkey_hunt_code_resolution_2026.py -q` passed: `7`.
  - `python -m compileall scripts\resolve-turkey-hunt-codes-2026.py tests\utah\test_turkey_hunt_code_resolution_2026.py` passed.

## 2026 Hunt-Code Family Gap Scan
- Timestamp (UTC): 2026-05-24T13:50:00Z
- Scope:
  - Added a read-only, repeatable family-level hunt-code gap scan across current 2026 `DATABASE.csv`, `hunt_master_enriched.csv`, `point_ladder_view.csv`, `draw_reality_engine.csv`, and `draw_reality_engine_predictive_v2.csv`.
  - Grouped current hunt-code coverage by code prefix/species family and ranked families by current database codes missing from predictive v2.
  - Confirmed no current `DATABASE.csv` codes are missing from the required reference surfaces `hunt_master_enriched.csv`, `point_ladder_view.csv`, or `draw_reality_engine.csv`.
  - Kept the scan audit-only; no reference rows were promoted and no prediction math was changed.
- Outputs:
  - `processed_data/2026_hunt_code_family_gap_scan.csv`
  - `processed_data/2026_hunt_code_family_gap_scan_summary.json`
  - `processed_data/2026_hunt_code_family_gap_scan.md`
- Key results:
  - Current `DATABASE.csv` hunt codes: `1411`.
  - Families scanned: `21`.
  - Fully resolved families: `6` (`BR`, `GO`, `MA`, `MB`, `PB`, `TK`).
  - Families with predictive v2 gaps: `15`.
  - Current database codes missing predictive v2: `352`.
  - Required-surface missing current database codes: `0`.
  - Largest predictive v2 gaps: `EL` limited-entry elk reference (`126`), `LO` limited-entry deer reference (`113`), and `EA` antlerless elk (`51`).
- Validation:
  - `python scripts\scan-2026-hunt-code-family-gaps.py` passed.
  - `python -m pytest tests\utah\test_hunt_code_family_gap_scan_2026.py -q` passed: `3`.
  - `python -m compileall scripts\scan-2026-hunt-code-family-gaps.py tests\utah\test_hunt_code_family_gap_scan_2026.py` passed.

## 2026 Antlerless Hunt-Code Resolution
- Timestamp (UTC): 2026-05-24T14:04:05Z
- Scope:
  - Added a repeatable antlerless hunt-code resolver using `pipeline/RAW/hunt_unit_database/2025/pdf/draw_odds/2024 antlerless draw results.pdf` as prior draw-results context.
  - Materialized 2024 antlerless draw-results text lines and parsed hunt rows under `data_truth/draw_results_truth/extracted/`.
  - Reconciled the current 2026 `DA`, `EA`, `PD`, and `RE` code families across `DATABASE.csv`, `hunt_master_enriched.csv`, `point_ladder_view.csv`, `draw_reality_engine.csv`, and `draw_reality_engine_predictive_v2.csv`.
  - Promoted 62 missing antlerless current database codes into predictive v2 as non-modeled reference rows only.
  - Kept promoted rows explicitly marked with `algorithm_status = ANTLERLESS_REFERENCE`, `modeled_by_engine = False`, `probability_model = NONE`, and `display_odds_text = Antlerless reference only; odds not modeled`.
  - Refreshed the 2026 family gap scan after antlerless resolution.
  - No raw PDFs, website feeds, permit values, harvest features, quota fields, or prediction probability math were changed.
- Outputs:
  - `scripts/resolve-antlerless-hunt-codes-2026.py`
  - `data_truth/draw_results_truth/extracted/2024_antlerless_draw_results_text_lines.csv`
  - `data_truth/draw_results_truth/extracted/2024_antlerless_draw_results_hunt_rows.csv`
  - `data_truth/draw_results_truth/validation/2026_antlerless_hunt_code_reconciliation.csv`
  - `processed_data/2024_antlerless_draw_results_audit.json`
  - `processed_data/2024_antlerless_draw_results_audit.md`
  - `processed_data/2026_antlerless_hunt_code_reconciliation_summary.json`
  - `processed_data/2026_antlerless_hunt_code_reconciliation.md`
  - `processed_data/2026_antlerless_predictive_v2_reference_promotion.csv`
  - `processed_data/2026_antlerless_predictive_v2_reference_promotion_summary.json`
- Key results:
  - Source PDF pages: `198`.
  - Source SHA-256: `21ea12abd24abb29b074520eccae1ab1b689d6e969d622803f220c0ca4664789`.
  - Extracted text lines: `5346`.
  - Parsed draw-result hunt rows: `198`.
  - Parsed draw-result prefix counts: `DA 21`, `EA 158`, `MA 2`, `PD 16`, `RE 1`.
  - Current target database codes checked: `265`.
  - Current target database codes present in 2024 draw results: `182`.
  - Promoted reference hunt-code count: `62` (`EA 51`, `PD 8`, `DA 2`, `RE 1`).
  - Antlerless reconciliation failures: `0`.
  - Audit blockers: `0`.
  - Updated gap scan current database codes missing predictive v2: `290`, down from `352`.
  - Updated resolved families: `10` (`BR`, `DA`, `EA`, `GO`, `MA`, `MB`, `PB`, `PD`, `RE`, `TK`).
  - Remaining largest predictive gaps: `EL` (`126`), `LO` (`113`), and `DB` (`15`).
- Validation:
  - `python scripts\resolve-antlerless-hunt-codes-2026.py` passed.
  - `python scripts\scan-2026-hunt-code-family-gaps.py` passed.
  - `python -m pytest tests\utah\test_antlerless_hunt_code_resolution_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py -q` passed: `6`.
  - `python -m compileall scripts\resolve-antlerless-hunt-codes-2026.py scripts\scan-2026-hunt-code-family-gaps.py tests\utah\test_antlerless_hunt_code_resolution_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py` passed.

## 2026 Deer Hunt-Code Resolution
- Timestamp (UTC): 2026-05-24T21:51:10Z
- Scope:
  - Added a repeatable deer hunt-code resolver using `pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023 DEER ODDS.pdf` as prior draw-results context.
  - Cross-checked the PDF hunt headers against `pipeline/RAW/hunt_unit_database/2024/csv/draw_results_2023_for_2024_long.csv`.
  - Materialized 2023 Deer Odds text lines and hunt-header rows under `data_truth/draw_results_truth/extracted/`.
  - Reconciled current 2026 `DB` and `LO` code families across `DATABASE.csv`, `hunt_master_enriched.csv`, `point_ladder_view.csv`, `draw_reality_engine.csv`, and `draw_reality_engine_predictive_v2.csv`.
  - Promoted 128 missing deer current database codes into predictive v2 as non-modeled reference rows only.
  - Kept promoted rows explicitly marked with `algorithm_status = DEER_REFERENCE`, `modeled_by_engine = False`, `probability_model = NONE`, and `display_odds_text = Deer reference only; odds not modeled`.
  - Classified the remaining DB gaps as tribal or special-permit reference-only rows and the LO family as private-land reference-only rows.
  - Refreshed the 2026 family gap scan after deer resolution.
  - No raw PDFs, website feeds, permit values, harvest features, quota fields, or prediction probability math were changed.
- Outputs:
  - `scripts/resolve-deer-hunt-codes-2026.py`
  - `data_truth/draw_results_truth/extracted/2023_deer_odds_text_lines.csv`
  - `data_truth/draw_results_truth/extracted/2023_deer_odds_hunt_headers.csv`
  - `data_truth/draw_results_truth/validation/2026_deer_hunt_code_reconciliation.csv`
  - `processed_data/2023_deer_odds_audit.json`
  - `processed_data/2023_deer_odds_audit.md`
  - `processed_data/2026_deer_hunt_code_reconciliation_summary.json`
  - `processed_data/2026_deer_hunt_code_reconciliation.md`
  - `processed_data/2026_deer_predictive_v2_reference_promotion.csv`
  - `processed_data/2026_deer_predictive_v2_reference_promotion_summary.json`
- Key results:
  - Source PDF pages: `190`.
  - Source SHA-256: `4188e4c1b712ec1c4973b735b6cb06e489680f15a1b2011857046b49707efabf`.
  - Extracted text lines: `7220`.
  - Parsed DB hunt headers: `189`.
  - Long CSV DB draw-result rows cross-checked: `11718`.
  - PDF header codes match long CSV DB codes: `true`.
  - Current target database codes checked: `458`.
  - Current database codes present in 2023 Deer Odds: `172`.
  - Promoted reference hunt-code count: `128` (`DB 15`, `LO 113`).
  - Deer reconciliation failures: `0`.
  - Audit blockers: `0`.
  - Updated gap scan current database codes missing predictive v2: `162`, down from `290`.
  - Updated resolved families: `12` (`BR`, `DA`, `DB`, `EA`, `GO`, `LO`, `MA`, `MB`, `PB`, `PD`, `RE`, `TK`).
  - Remaining largest predictive gaps: `EL` (`126`), `EB` (`10`), and `DS` (`6`).
- Validation:
  - `python scripts\resolve-deer-hunt-codes-2026.py` passed.
  - `python scripts\scan-2026-hunt-code-family-gaps.py` passed.
  - `python -m pytest tests\utah\test_deer_hunt_code_resolution_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py -q` passed: `6`.
  - `python -m compileall scripts\resolve-deer-hunt-codes-2026.py scripts\scan-2026-hunt-code-family-gaps.py tests\utah\test_deer_hunt_code_resolution_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py` passed.

## 2023 Big Game Field Regulations Source Audit
- Timestamp (UTC): 2026-05-24T21:59:22Z
- Scope:
  - Added a repeatable source audit for `pipeline/RAW/hunt_unit_database/2023/pdf/regulation/2023_field_regs.pdf`.
  - Locked the file identity as `2023 Utah Big Game Field Regulations` with SHA-256 `c68a0ef12e09e810449e2a5f569bcf445709249c9354036bc1ef17086477284f`.
  - Materialized 2023 field-regulations text lines, number/date/citation tokens, and pasted-text anchor checks under `data_truth/regulations_truth/normalized/`.
  - Classified the source as `REGULATION_REFERENCE_ONLY` with guardrail `DO_NOT_USE_AS_DRAW_ODDS_HARVEST_FEATURE_OR_2026_QUOTA_INPUT`.
  - Confirmed this source did not promote draw rows, prediction rows, harvest features, permit quotas, or website-facing files.
- Outputs:
  - `scripts/audit-big-game-field-regulations-2023.py`
  - `tests/utah/test_big_game_field_regulations_2023_source_audit.py`
  - `data_truth/regulations_truth/normalized/2023_big_game_field_regulations_text_lines.csv`
  - `data_truth/regulations_truth/normalized/2023_big_game_field_regulations_number_tokens.csv`
  - `data_truth/regulations_truth/normalized/2023_big_game_field_regulations_expected_text_checks.csv`
  - `processed_data/2023_big_game_field_regulations_source_audit.json`
  - `processed_data/2023_big_game_field_regulations_source_audit.md`
- Key results:
  - Source PDF pages: `72`.
  - Source file size: `5,784,679` bytes.
  - Extracted text lines: `4014`.
  - Extracted number/date/citation tokens: `1582` (`number_or_money 1286`, `code_citation 191`, `date 105`).
  - Pasted-text checks: `69`.
  - Pasted-text failures: `0`.
  - Audit blockers: `0`.
  - Database reconciliation effect: `NO_DRAW_OR_PREDICTION_ROWS_PROMOTED`.
- Validation:
  - `python scripts\audit-big-game-field-regulations-2023.py` passed.
  - `python -m pytest tests\utah\test_big_game_field_regulations_2023_source_audit.py -q` passed: `2`.
  - `python -m compileall scripts\audit-big-game-field-regulations-2023.py tests\utah\test_big_game_field_regulations_2023_source_audit.py` passed.

## 2023 Big Game Application Guidebook Source Audit
- Timestamp (UTC): 2026-05-24T22:06:00Z
- Scope:
  - Added a repeatable source audit for `pipeline/RAW/hunt_unit_database/2023/pdf/regulation/2023_biggameapp.pdf`.
  - Locked the file identity as the revised May `2023 Utah Big Game Application Guidebook` with SHA-256 `7357df71939b084d5e6807a1bc01670bb6f1c04369e550946b1363c57ed2082b`.
  - Materialized 2023 application-guidebook text lines, number/date/citation tokens, pasted-text anchor checks, and hunt-table reference rows under `data_truth/regulations_truth/normalized/`.
  - Classified the source as `APPLICATION_GUIDEBOOK_REFERENCE_ONLY` with guardrail `DO_NOT_USE_AS_DRAW_ODDS_HARVEST_FEATURE_OR_2026_QUOTA_INPUT`.
  - Confirmed this source did not promote draw rows, prediction rows, harvest features, permit quotas, or website-facing files.
- Outputs:
  - `scripts/audit-big-game-application-guidebook-2023.py`
  - `tests/utah/test_big_game_application_guidebook_2023_source_audit.py`
  - `data_truth/regulations_truth/normalized/2023_big_game_application_guidebook_text_lines.csv`
  - `data_truth/regulations_truth/normalized/2023_big_game_application_guidebook_number_tokens.csv`
  - `data_truth/regulations_truth/normalized/2023_big_game_application_guidebook_expected_text_checks.csv`
  - `data_truth/regulations_truth/normalized/2023_big_game_application_guidebook_hunt_tables.csv`
  - `processed_data/2023_big_game_application_guidebook_source_audit.json`
  - `processed_data/2023_big_game_application_guidebook_source_audit.md`
- Key results:
  - Source PDF pages: `80`.
  - Source file size: `2,880,571` bytes.
  - Extracted text lines: `3915`.
  - Extracted number/date/citation tokens: `3422` (`number_or_money 2841`, `date 508`, `code_citation 73`).
  - Hunt-table reference rows: `719`.
  - Unique hunt codes: `719`.
  - Hunt-code prefix counts: `DB 326`, `EB 212`, `PB 87`, `MB 30`, `BI 17`, `GO 17`, `DS 16`, `RS 14`.
  - Pasted-text checks: `66`.
  - Pasted-text failures: `0`.
  - Audit blockers: `0`.
  - Database reconciliation effect: `NO_DRAW_OR_PREDICTION_ROWS_PROMOTED`.
- Validation:
  - `python scripts\audit-big-game-application-guidebook-2023.py` passed.
  - `python -m pytest tests\utah\test_big_game_application_guidebook_2023_source_audit.py -q` passed: `2`.
  - `python -m compileall scripts\audit-big-game-application-guidebook-2023.py tests\utah\test_big_game_application_guidebook_2023_source_audit.py` passed.

## Elk Bull Private-Land Hunt Planner Spreadsheet Export
- Timestamp (UTC): 2026-05-25T00:22:44Z
- Scope:
  - Created a repeatable spreadsheet export for current Utah DWR Hunt Planner elk bull private-land-only reference rows.
  - Included `126` `EL` limited-entry private-land-only bull elk rows and `5` Diamond Mtn Landowner Association `LO` rows.
  - Preserved explicit `Non Res`, `Res`, and `Total` columns as blank because the source confirms no resident/nonresident/total permit allotment is published for these private-land-only hunts.
  - Preserved source authority as `Utah DWR Hunt Planner`.
  - Did not promote these rows as public draw odds, harvest features, prediction rows, or website-facing outputs.
- Outputs:
  - `scripts/export-elk-bull-private-lands-spreadsheet.mjs`
  - `tests/utah/test_elk_bull_private_lands_spreadsheet.py`
  - `processed_data/elk_bull_private_lands_hunt_planner_reference.csv`
  - `processed_data/elk_bull_private_lands_hunt_planner_reference.xlsx`
  - `processed_data/elk_bull_private_lands_hunt_planner_reference_report.json`
- Key results:
  - Output rows: `131`.
  - `EL` rows: `126`.
  - `LO` rows: `5`.
  - Duplicate hunt codes: `0`.
  - Required quota columns present: `Non Res`, `Res`, `Total`.
  - Blank quota columns confirmed: `true`.
  - Permit status: `NO_QUOTA_PUBLISHED`.
  - Data status: `SOURCE_CONFIRMED_NO_QUOTA_PUBLISHED`.
- Validation:
  - `node scripts\export-elk-bull-private-lands-spreadsheet.mjs` passed.
  - `python -m pytest tests\utah\test_elk_bull_private_lands_spreadsheet.py -q` passed: `3`.
  - `python -m compileall tests\utah\test_elk_bull_private_lands_spreadsheet.py` passed.
  - `node --check scripts\export-elk-bull-private-lands-spreadsheet.mjs` passed.

## 2022-2027 Conservation Permit Vault And Trend Model
- Timestamp (UTC): 2026-05-25T00:33:42Z
- Scope:
  - Vaulted the `2022-2024 Conservation Permits` source package under permit-overlay truth storage.
  - Preserved the canonical source PDF and one extracted workbook copy with SHA-256 validation.
  - Held the second extracted workbook copy as an exact SHA-256 duplicate instead of copying it twice.
  - Built a deterministic cycle-to-cycle conservation permit trend model comparing `2022-2024` to `2025-2027`.
  - Classified outputs as trend/reference only with guardrail `TREND_MODEL_ONLY_DO_NOT_USE_AS_DRAW_ODDS_OR_HARVEST_RESULTS`.
  - Did not modify website-facing files, prediction outputs, harvest-result truth, draw-result truth, or materializer code.
- Outputs:
  - `scripts/vault-conservation-permits-2022-2024.py`
  - `scripts/model-conservation-permit-trends-2022-2027.py`
  - `tests/utah/test_conservation_permits_2022_2024_vault.py`
  - `tests/utah/test_conservation_permit_trends_2022_2027.py`
  - `data_truth/permit_overlay_truth/raw_sources/2022_2024_conservation_permits/`
  - `data_truth/permit_overlay_truth/normalized/conservation_permit_cycle_rows_2022_2027.csv`
  - `data_truth/permit_overlay_truth/normalized/conservation_permit_trends_by_species_2022_2027.csv`
  - `data_truth/permit_overlay_truth/normalized/conservation_permit_trends_by_group_2022_2027.csv`
  - `data_truth/permit_overlay_truth/normalized/conservation_permit_trends_2022_2027_summary.json`
  - `processed_data/conservation_permit_trends_2022_2027.md`
- Key results:
  - 2022-2024 conservation permits: `318`.
  - 2025-2027 conservation permits: `336`.
  - Cycle change: `+18` permits.
  - Percent change: `+5.66%`.
  - Annual average changed from `106.0` to `112.0` permits/year.
  - Largest species-family increases: Elk `+11`, Pronghorn `+9`, Black Bear `+3`.
  - Largest species-family decreases: Bison `-2`, Rocky Mountain Bighorn Sheep `-2`, Cougar `-1`, Moose `-1`.
  - Largest group increase: SFW `+37`.
  - Largest group decreases: SCI `-16`, RMEF `-7`, UWSF `-7`.
  - Vault validation status: `PASS`.
  - Trend-model validation status: `PASS`.
- Validation:
  - `python scripts\vault-conservation-permits-2022-2024.py` passed.
  - `python scripts\model-conservation-permit-trends-2022-2027.py` passed.
  - `python -m pytest tests\utah\test_conservation_permits_2022_2024_vault.py tests\utah\test_conservation_permit_trends_2022_2027.py -q` passed: `8`.
  - `python -m compileall scripts\vault-conservation-permits-2022-2024.py scripts\model-conservation-permit-trends-2022-2027.py tests\utah\test_conservation_permits_2022_2024_vault.py tests\utah\test_conservation_permit_trends_2022_2027.py` passed.

## 2026 Pronghorn Buck Hunt-Code Resolution And Export
- Timestamp (UTC): 2026-05-25T00:51:44Z
- Scope:
  - Created a repeatable pronghorn buck reference export from the current 2026 Utah DWR Hunt Planner canonical surface.
  - Included `88` `PB` pronghorn buck rows and the six source-confirmed private-land-only `LP` rows supplied by the user: `LP5025`, `LP5031`, `LP5033`, `LP5046`, `LP5049`, and `LP5051`.
  - Preserved published `Non Res`, `Res`, and `Total` quota values on public `PB` rows.
  - Preserved blank `Non Res`, `Res`, and `Total` quota values on private-land-only `LP` rows because the source confirms no quota is published.
  - Promoted the six `LP` rows into `draw_reality_engine_predictive_v2.csv` as non-modeled reference rows only.
  - Kept promoted rows explicitly marked with `algorithm_status = PRONGHORN_PRIVATE_LAND_REFERENCE`, `modeled_by_engine = False`, `probability_model = NONE`, and `display_odds_text = Private-land pronghorn reference only; odds not modeled`.
  - Refreshed the 2026 family gap scan after pronghorn resolution.
  - No website feeds, harvest features, public draw quotas, or probability math were changed.
- Outputs:
  - `scripts/resolve-pronghorn-hunt-codes-2026.py`
  - `scripts/export-pronghorn-buck-reference-spreadsheet.mjs`
  - `tests/utah/test_pronghorn_private_land_resolution_2026.py`
  - `processed_data/pronghorn_buck_limited_entry_reference_export.csv`
  - `processed_data/pronghorn_buck_limited_entry_reference_export.xlsx`
  - `processed_data/pronghorn_buck_limited_entry_reference_export_report.json`
  - `processed_data/pronghorn_buck_limited_entry_reference_export_xlsx_report.json`
  - `data_truth/draw_results_truth/validation/2026_pronghorn_hunt_code_reconciliation.csv`
  - `processed_data/2026_pronghorn_hunt_code_reconciliation_summary.json`
  - `processed_data/2026_pronghorn_hunt_code_reconciliation.md`
  - `processed_data/2026_pronghorn_private_land_predictive_v2_reference_promotion.csv`
  - `processed_data/2026_pronghorn_private_land_predictive_v2_reference_promotion_summary.json`
- Key results:
  - Current pronghorn buck rows checked: `94`.
  - `PB` rows: `88`.
  - `LP` rows: `6`.
  - Newly promoted `LP` reference rows: `6`.
  - `LP` quota leak count: `0`.
  - Pronghorn reconciliation blockers: `0`.
  - Updated gap scan current database codes missing predictive v2: `156`, down from `162`.
  - Updated resolved families: `13` (`BR`, `DA`, `DB`, `EA`, `GO`, `LO`, `LP`, `MA`, `MB`, `PB`, `PD`, `RE`, `TK`).
  - Remaining largest predictive gaps: `EL` (`126`), `EB` (`10`), and `DS` (`6`).
- Validation:
  - `python scripts\resolve-pronghorn-hunt-codes-2026.py` passed.
  - `node scripts\export-pronghorn-buck-reference-spreadsheet.mjs` passed.
  - `python scripts\scan-2026-hunt-code-family-gaps.py` passed.
  - `python -m pytest tests\utah\test_pronghorn_private_land_resolution_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py -q` passed: `6`.
  - `python -m compileall scripts\resolve-pronghorn-hunt-codes-2026.py tests\utah\test_pronghorn_private_land_resolution_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py` passed.
  - `node --check scripts\export-pronghorn-buck-reference-spreadsheet.mjs` passed.

## 2026 Elk Private-Land Hunt-Code Resolution
- Timestamp (UTC): 2026-05-25T00:58:47Z
- Scope:
  - Added a repeatable resolver for current 2026 Utah DWR Hunt Planner `EL` private-land-only bull elk rows.
  - Promoted all `126` `EL` rows into `draw_reality_engine_predictive_v2.csv` as non-modeled reference rows only.
  - Kept promoted rows explicitly marked with `algorithm_status = ELK_PRIVATE_LAND_REFERENCE`, `modeled_by_engine = False`, `probability_model = NONE`, and `display_odds_text = Private-land elk reference only; odds not modeled`.
  - Preserved blank `Non Res`, `Res`, and `Total` quota/allotment fields because the source confirms no quota is published for these private-land-only hunts.
  - Recorded the five Diamond Mtn `LO0011`-`LO0015` elk rows as already exported elk private-land references but not part of the `EL` prefix gap.
  - Refreshed the 2026 family gap scan after elk private-land resolution.
  - No website feeds, harvest features, public `EB` quotas, or probability math were changed.
- Outputs:
  - `scripts/resolve-elk-private-land-hunt-codes-2026.py`
  - `tests/utah/test_elk_private_land_resolution_2026.py`
  - `data_truth/draw_results_truth/validation/2026_elk_private_land_hunt_code_reconciliation.csv`
  - `processed_data/2026_elk_private_land_hunt_code_reconciliation_summary.json`
  - `processed_data/2026_elk_private_land_hunt_code_reconciliation.md`
  - `processed_data/2026_elk_private_land_predictive_v2_reference_promotion.csv`
  - `processed_data/2026_elk_private_land_predictive_v2_reference_promotion_summary.json`
- Key results:
  - Current `EL` private-land bull elk rows checked: `126`.
  - Newly promoted `EL` reference rows: `126`.
  - `EL` quota leak count: `0`.
  - Elk private-land reconciliation blockers: `0`.
  - Updated gap scan current database codes missing predictive v2: `30`, down from `156`.
  - Updated resolved families: `14` (`BR`, `DA`, `DB`, `EA`, `EL`, `GO`, `LO`, `LP`, `MA`, `MB`, `PB`, `PD`, `RE`, `TK`).
  - Remaining largest predictive gaps: `EB` (`10`), `DS` (`6`), and `LD` (`6`).
- Validation:
  - `python scripts\resolve-elk-private-land-hunt-codes-2026.py` passed.
  - `python scripts\scan-2026-hunt-code-family-gaps.py` passed.
  - `python -m pytest tests\utah\test_elk_private_land_resolution_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py tests\utah\test_elk_bull_private_lands_spreadsheet.py -q` passed: `9`.
  - `python -m compileall scripts\resolve-elk-private-land-hunt-codes-2026.py tests\utah\test_elk_private_land_resolution_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py` passed.

## 2026 Elk Bull EB Reference Hunt-Code Resolution
- Timestamp (UTC): 2026-05-25T01:20:24Z
- Scope:
  - Added a repeatable resolver for current 2026 Utah DWR Hunt Planner `EB` elk bull reference rows supplied from the current Hunt Planner surface.
  - Reconciled `13` reference rows: `5` `TOTAL_ONLY` rows and `8` `NO_QUOTA_PUBLISHED` rows.
  - Promoted the `10` missing `EB` rows into `draw_reality_engine_predictive_v2.csv` as non-modeled reference rows only.
  - Kept promoted rows explicitly marked with `algorithm_status = ELK_BULL_REFERENCE`, `modeled_by_engine = False`, `probability_model = NONE`, and `display_odds_text = Elk bull reference only; odds not modeled`.
  - Preserved canonical total-only values for `EB1012 = 500`, `EB3128 = 1`, and `EB3209 = 1`.
  - Preserved blank quota/allotment fields on `NO_QUOTA_PUBLISHED` general-season rows, ignoring stale DATABASE season-length-looking totals.
  - Created an elk bull reference spreadsheet export with explicit `Non Res`, `Res`, and `Total` columns.
  - Refreshed the 2026 family gap scan after `EB` resolution.
  - No website feeds, harvest features, public-client files, materializer code, or probability math were changed.
- Outputs:
  - `scripts/resolve-elk-bull-reference-hunt-codes-2026.py`
  - `scripts/export-elk-bull-reference-spreadsheet.mjs`
  - `tests/utah/test_elk_bull_reference_resolution_2026.py`
  - `data_truth/draw_results_truth/validation/2026_elk_bull_reference_hunt_code_reconciliation.csv`
  - `processed_data/2026_elk_bull_reference_hunt_code_reconciliation_summary.json`
  - `processed_data/2026_elk_bull_reference_hunt_code_reconciliation.md`
  - `processed_data/2026_elk_bull_reference_predictive_v2_reference_promotion.csv`
  - `processed_data/2026_elk_bull_reference_predictive_v2_reference_promotion_summary.json`
  - `processed_data/elk_bull_reference_hunt_planner_reference.csv`
  - `processed_data/elk_bull_reference_hunt_planner_reference.xlsx`
  - `processed_data/elk_bull_reference_hunt_planner_reference_report.json`
- Key results:
  - Current `EB` reference rows checked: `13`.
  - Newly promoted `EB` reference rows: `10`.
  - `TOTAL_ONLY` rows: `5` (`EB1000`, `EB1007`, `EB1012`, `EB3128`, `EB3209`).
  - `NO_QUOTA_PUBLISHED` rows: `8`.
  - Stale quota leaks: `0`.
  - Reconciliation blockers: `0`.
  - Updated gap scan current database codes missing predictive v2: `20`, down from `30`.
  - Updated resolved families: `15` (`BR`, `DA`, `DB`, `EA`, `EB`, `EL`, `GO`, `LO`, `LP`, `MA`, `MB`, `PB`, `PD`, `RE`, `TK`).
  - Remaining largest predictive gaps: `DS` (`6`), `LD` (`6`), and `RS` (`4`).
- Validation:
  - `python scripts\resolve-elk-bull-reference-hunt-codes-2026.py` passed.
  - `node scripts\export-elk-bull-reference-spreadsheet.mjs` passed with bundled workspace Node runtime.
  - `python scripts\scan-2026-hunt-code-family-gaps.py` passed.
  - `python -m pytest tests\utah\test_elk_bull_reference_resolution_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py -q` passed: `7`.
  - `python -m compileall scripts\resolve-elk-bull-reference-hunt-codes-2026.py tests\utah\test_elk_bull_reference_resolution_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py` passed.
  - `node --check scripts\export-elk-bull-reference-spreadsheet.mjs` passed with bundled workspace Node runtime.

## 2026 Private-Land Deer And Final Reference Hunt-Code Locks
- Timestamp (UTC): 2026-05-25T02:23:00Z
- Scope:
  - Locked the current Utah DWR Hunt Planner private-land deer rows supplied by the user: `LD1001`, `LD1004`, `LD1006`, `LD1019`, `LD1023`, `LD1108`, `LO0008`, `LO0009`, and `LO0010`.
  - Promoted the six missing `LD` rows into `draw_reality_engine_predictive_v2.csv` as non-modeled private-land deer reference rows only.
  - Preserved the three existing Diamond Mtn `LO0008`-`LO0010` rows as non-modeled private-land deer references and fixed the deer resolver so reruns do not flatten those rows back into generic deer references.
  - Locked the remaining current-database predictive gaps supplied by the user: `RS0001`, `RS1000`, `RS1001`, `RS1003`, `RS1006`, `BI6527`, `BI6538`, `EX1000`, and `CG9999`.
  - Pulled Rocky Mountain bighorn conservation/statewide permit counts from `data_truth/permit_overlay_truth/normalized/conservation_permit_cycle_rows_2022_2027.csv` where available: `RS0001`, `RS1001`, `RS1003`, and `RS1006` each have `Res=1`, `Non Res=0`, `Total=1`.
  - Preserved blank quota/allotment fields for source-confirmed no-quota reference rows: `RS1000`, `BI6527`, `BI6538`, `EX1000`, and `CG9999`.
  - Verified that the six private-land pronghorn `LP` rows are already resolved in the current predictive surface and did not duplicate them.
  - Refreshed the 2026 family gap scan after the locks.
  - No website feeds, `public_client_engine.csv`, materializer code, harvest features, or probability math were changed.
- Outputs:
  - `scripts/lock-private-land-deer-hunt-codes-2026.py`
  - `scripts/lock-final-reference-hunt-codes-2026.py`
  - `tests/utah/test_private_land_deer_code_lock_2026.py`
  - `tests/utah/test_final_reference_hunt_code_lock_2026.py`
  - `data_truth/permit_overlay_truth/normalized/private_land_deer_hunt_code_lock_2026.csv`
  - `data_truth/permit_overlay_truth/normalized/final_reference_hunt_code_lock_2026.csv`
  - `processed_data/private_land_deer_hunt_code_lock_2026_summary.json`
  - `processed_data/final_reference_hunt_code_lock_2026_summary.json`
  - `processed_data/private_land_deer_hunt_code_lock_2026.md`
  - `processed_data/final_reference_hunt_code_lock_2026.md`
  - `processed_data/private_land_deer_hunt_code_lock_2026_runtime_updates.csv`
  - `processed_data/final_reference_hunt_code_lock_2026_runtime_updates.csv`
- Key results:
  - Private-land deer locked rows: `9`.
  - New `LD` predictive reference rows: `6`.
  - Final reference locked rows: `9`.
  - Final reference `FULL_SPLIT` rows: `4`.
  - Final reference `NO_QUOTA_PUBLISHED` rows: `5`.
  - Updated gap scan current database codes missing predictive v2: `0`, down from `8`.
  - Updated resolved families: `21`.
  - Predictive gap families remaining: `0`.
  - Required-surface blocker families remaining: `0`.
  - Follow-up needed: build an explicit current-code-to-historical-code crosswalk for changed code families instead of treating 2023 guidebook codes as identical to current Hunt Planner codes.
- Validation:
  - `python scripts\lock-private-land-deer-hunt-codes-2026.py` passed.
  - `python scripts\lock-final-reference-hunt-codes-2026.py` passed.
  - `python scripts\scan-2026-hunt-code-family-gaps.py` passed.
  - `python -m pytest tests\utah\test_private_land_deer_code_lock_2026.py tests\utah\test_final_reference_hunt_code_lock_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py tests\utah\test_deer_hunt_code_resolution_2026.py tests\utah\test_elk_bull_reference_resolution_2026.py tests\utah\test_elk_private_land_resolution_2026.py tests\utah\test_desert_bighorn_conservation_code_lock_2026.py tests\utah\test_conservation_permit_code_lock_2026.py -q` passed: `29`.
  - `python -m py_compile scripts\lock-private-land-deer-hunt-codes-2026.py scripts\lock-final-reference-hunt-codes-2026.py scripts\resolve-deer-hunt-codes-2026.py` passed.

## 2026 Current-To-Historical Hunt-Code Crosswalk Truth
- Timestamp (UTC): 2026-05-25T03:10:26Z
- Scope:
  - Promoted the older backcheck/crosswalk evidence into an explicit crosswalk truth artifact for changed/current reference hunt-code families.
  - Used `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` as the current-code authority and crosschecked every promoted current code against it.
  - Included all current `LD`, `LP`, and `EL` codes; the user-supplied `LO0008`-`LO0015` private-land/landowner association codes; and the locked conservation/reference codes for `DS`, `EA`, `EB`, `RS`, `BI`, `EX`, and `CG`.
  - Preserved current Hunt Planner codes as current truth and stored historical candidates separately so 2023 guidebook/public codes are not silently treated as identical to current private-land or conservation codes.
  - No website feeds, `public_client_engine.csv`, materializer code, harvest features, probability math, or runtime prediction surfaces were changed.
- Outputs:
  - `scripts/build-current-historical-hunt-code-crosswalk-2026.py`
  - `tests/utah/test_current_historical_hunt_code_crosswalk_2026.py`
  - `data_truth/crosswalk_truth/normalized/current_to_historical_hunt_code_crosswalk_2026.csv`
  - `data_truth/crosswalk_truth/validation/current_to_historical_hunt_code_crosswalk_2026_summary.json`
  - `processed_data/current_to_historical_hunt_code_crosswalk_2026.csv`
  - `processed_data/current_to_historical_hunt_code_crosswalk_2026.md`
- Key results:
  - Crosswalk target rows: `169`.
  - `DATABASE.csv` missing current-code rows: `0`.
  - Duplicate current-code rows: `0`.
  - Blockers: `0`.
  - Prefix counts: `EL=126`, `LD=6`, `LP=6`, `LO=8`, `DS=7`, `EA=5`, `RS=5`, `BI=2`, `EB=2`, `EX=1`, `CG=1`.
  - Status counts: `PROMOTED_PREFIX_SWAP_CANDIDATE=138`, `PROMOTED_EXACT_HISTORY=19`, `PROMOTED_PINNED_CANDIDATE=8`, `CURRENT_REFERENCE_ONLY_NEEDS_REVIEW=4`.
  - Spot checks: `LD1001 -> DB1001`, `LP5025 -> PB5025`, `EL3000 -> EB3000`, `EL3210 -> EB3210`, `RS1001 -> RS6701`, `DS1004 -> DS6608`, `BI6527 -> BI6527`, while `EX1000` and `CG9999` remain current-reference-only.
- Validation:
  - `python scripts\build-current-historical-hunt-code-crosswalk-2026.py` passed.
  - `python -m pytest tests\utah\test_current_historical_hunt_code_crosswalk_2026.py -q` passed: `3`.
  - `python -m pytest tests\utah\test_current_historical_hunt_code_crosswalk_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py tests\utah\test_private_land_deer_code_lock_2026.py tests\utah\test_pronghorn_private_land_resolution_2026.py tests\utah\test_elk_private_land_resolution_2026.py tests\utah\test_conservation_permit_code_lock_2026.py tests\utah\test_desert_bighorn_conservation_code_lock_2026.py tests\utah\test_final_reference_hunt_code_lock_2026.py -q` passed: `28`.
  - `python -m py_compile scripts\build-current-historical-hunt-code-crosswalk-2026.py` passed.

## Research Library Mapping Law
- Timestamp (UTC): 2026-05-25T06:05:00Z
- Scope:
  - Added an explicit mapping-law section to `AGENTS.MD` so future research-library documents and rows must carry reviewed `hunt_code` and `boundary_id` fields plus mapping-status and candidate fields.
  - Reinforced that candidate/fuzzy/current-to-historical evidence must not be treated as promoted truth until reviewed.
  - The executable research-library master build and validation artifacts were created in the sibling `HUNT-BUILDER` workspace where the library catalog currently lives.
- Validation:
  - Confirmed `AGENTS.MD` now contains the required research-library mapping contract.

## Research Library Feeder Source Law
- Timestamp (UTC): 2026-05-25T06:35:00Z
- Scope:
  - Extended `AGENTS.MD` so `DATABASE.csv` is explicitly treated as the canonical current hunt-code and boundary-id source unless replaced by a later reviewed canonical database.
  - Added the rule that feeder/reference files such as `hunt_master_enriched.csv`, `point_ladder_view.csv`, canonical JSON, and boundary GeoJSON must be registered as source rows with hashes before supporting alignment work.
  - The executable source registry update was completed in the sibling `HUNT-BUILDER` workspace where the research library master is built.
- Validation:
  - Confirmed `AGENTS.MD` now contains the feeder/source registration rule.

## 2025 Permit Promotion Guard
- Timestamp (UTC): 2026-05-25T07:35:00Z
- Scope:
  - Extended `AGENTS.MD` so direct Utah DWR Hunt Planner CSV-folder files are explicitly source evidence only until a reviewed promotion step identifies source dates/year context.
  - Added the guardrail that 2025 permit values must not be promoted into 2026 available allotment fields unless every imported source used in that promotion has reviewed source-date context.
  - The executable source registry update was completed in the sibling `HUNT-BUILDER` workspace where the research library master is built.
- Validation:
  - Confirmed `AGENTS.MD` now contains the direct CSV source-evidence and 2025-to-2026 promotion guardrails.

## Canonical DATABASE Numeric Cell Protection
- Timestamp (UTC): 2026-05-25T08:15:00Z
- Scope:
  - Extended `AGENTS.MD` so populated numeric permit cells in canonical `DATABASE.csv` are explicitly treated as direct Utah DWR Hunt Planner truth.
  - Added the rule that populated numeric permit cells in canonical `DATABASE.csv` must not be changed or overwritten by comparison files, inferred values, draw reports, RAC files, audit outputs, or rebuilt library/master documents.
  - The executable permit deep-dive audit was completed in the sibling `HUNT-BUILDER` workspace where `hunt_master_canonical_2026_built.csv` and the direct CSV folder live.
- Validation:
  - Confirmed `AGENTS.MD` now contains the canonical numeric-cell protection rule.

## Canonical DATABASE 2026 Authority Clarification
- Timestamp (UTC): 2026-05-25T08:50:00Z
- Scope:
  - Tightened the canonical `DATABASE.csv` numeric-cell protection rule.
  - Clarified that populated numeric `2026` permit/allotment cells are the direct Utah DWR Hunt Planner truth source.
  - Clarified that populated `2025` or older permit fields with reviewed source lineage are canonical historical source truth, not soft evidence.
  - Clarified that `permits_2025` is the full populated 2025 historical permit universe in `DATABASE.csv`, while `permits_2025_draw` is a narrower bonus-point draw-results subset and must not be described as the full 2025 draw/permit universe.
  - The executable audit and overlay-plan artifacts were regenerated in the sibling `HUNT-BUILDER` workspace.
- Validation:
  - Confirmed `AGENTS.MD` now contains the corrected 2026 authority and historical-field lineage rule.

## Expo Permit Draw Results Total-Only And Sheep Sex Labels
- Timestamp (UTC): 2026-05-26T21:50:00Z
- Scope:
  - Normalized `pipeline/RAW/hunt_unit_database/2026/xlsx/expo permits 2026.xlsx` into a per-hunt-unit/weapon/season draw-result artifact that publishes only `permits_2026_total`.
  - Verified the Expo workbook has `125` permit rows and the normalized output has the same `125` rows.
  - Preserved the no resident/nonresident split guardrail for Expo permits because the source publishes total permits only.
  - Normalized DWR sheep sex labels in canonical `DATABASE.csv`: all desert bighorn sheep rows are `Male Only`; `RE1000` is the single Rocky Mountain bighorn `Ewe` hunt; all other Rocky Mountain bighorn rows are `Ram`.
  - Re-ran comprehensive live DWR permit extraction, database publish readiness, and comprehensive 2026/2025 history-integrity audit after the sheep normalization.
  - No website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Outputs:
  - `scripts/normalize-expo-permit-draw-results-2026.py`
  - `scripts/normalize-sheep-sex-types-2026.py`
  - `data_truth/draw_results_truth/normalized/expo_permit_draw_results_2026_total_only.csv`
  - `data_truth/draw_results_truth/validation/expo_permit_draw_results_2026_total_only_summary.json`
  - `data_truth/crosswalk_truth/validation/sheep_sex_type_normalization_2026.csv`
  - `data_truth/crosswalk_truth/validation/sheep_sex_type_normalization_2026_summary.json`
  - `processed_data/expo_permit_draw_results_2026_total_only.md`
  - `processed_data/sheep_sex_type_normalization_2026.md`
- Key results:
  - Expo normalized rows: `125`.
  - Expo total permits: `200`.
  - Expo mapping statuses: `MATCH_HIGH=57`, `AMBIGUOUS_DATABASE_MATCH=47`, `NO_DATABASE_MATCH=21`.
  - Sheep sex counts: `Desert Bighorn Sheep|Male Only=25`, `Rocky Mountain Bighorn Sheep|Ewe=1`, `Rocky Mountain Bighorn Sheep|Ram=20`.
  - Comprehensive live DWR comparison remains clear of live-only rows and live-numeric/database-blank rows: both counts are `0`.
  - Publish readiness remains `true`.
  - Comprehensive history audit fatal blockers remain `0`.
- Validation:
  - `python scripts\normalize-expo-permit-draw-results-2026.py` passed.
  - `python scripts\normalize-sheep-sex-types-2026.py` passed.
  - `python scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m py_compile scripts\normalize-expo-permit-draw-results-2026.py scripts\normalize-sheep-sex-types-2026.py scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python -m pytest tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py -q` passed: `7`.

## Reviewed Live Permit Corrections And CWMU Total-Only Shape
- Timestamp (UTC): 2026-05-26T21:55:00Z
- Scope:
  - Applied reviewed Utah DWR Hunt Planner live permit blocks to the remaining numeric mismatch rows: `BI6528`, `BI6532`, `BR7004`, `EB3010`, `EB3047`, `EB3088`, `EB3112`, and `EB3185`.
  - Recorded `BR7004` as `18 / 2 / 20` because the DWR block shows resident `18` and total `20`, so nonresident is derived as total minus resident.
  - Normalized all `283` CWMU rows in `DATABASE.csv` to total-only permit shape: blank `permits_2026_res`, blank `permits_2026_nr`, populated `permits_2026_total`.
  - Updated the comprehensive live DWR comparison so split rows with resident and total values can derive nonresident as `total - resident` when DWR omits an explicit nonresident field.
  - Re-ran comprehensive live DWR permit extraction, database publish readiness, and comprehensive 2026/2025 history-integrity audit after the corrections.
  - No website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Outputs:
  - `scripts/apply-reviewed-live-permit-corrections-2026.py`
  - `data_truth/crosswalk_truth/validation/reviewed_live_permit_corrections_2026.csv`
  - `data_truth/crosswalk_truth/validation/reviewed_live_permit_corrections_2026_summary.json`
  - `processed_data/reviewed_live_permit_corrections_2026.md`
- Key results:
  - Reviewed numeric correction rows applied: `8`.
  - CWMU total-only rows normalized: `283`.
  - CWMU rows still carrying a resident/nonresident split: `0`.
  - Comprehensive live DWR numeric mismatches: `0`, down from `8`.
  - Comprehensive live DWR comparison remains clear of live-only rows and live-numeric/database-blank rows: both counts are `0`.
  - Publish readiness remains `true`.
  - Comprehensive history audit fatal blockers remain `0`.
- Validation:
  - `python scripts\apply-reviewed-live-permit-corrections-2026.py` passed.
  - `python scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m py_compile scripts\apply-reviewed-live-permit-corrections-2026.py scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python -m pytest tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py -q` passed: `8`.

## EB3135 Barney Top Label Check
- Timestamp (UTC): 2026-05-26T22:00:00Z
- Scope:
  - Confirmed `EB3135` is `Barney Top/Kaiparowits` archery with 2026 permits `9 / 1 / 10`.
  - Confirmed Monroe mid-season any-legal-weapon remains `EB3185` with 2026 permits `18 / 3 / 21`.
  - Corrected the canonical `EB3135` weapon label from `September Archery` to the DWR Hunt Planner label `Archery`.
  - Added `EB3135` to the reviewed live permit correction audit as a label-only correction.
  - Re-ran comprehensive live DWR permit extraction, database publish readiness, and comprehensive 2026/2025 history-integrity audit after the label correction.
  - No website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Key results:
  - `EB3135` comparison status remains `MATCH`.
  - `EB3185` comparison status remains `MATCH`.
  - Comprehensive live DWR numeric mismatches remain `0`.
  - Publish readiness remains `true`.
  - Comprehensive history audit fatal blockers remain `0`.
- Validation:
  - `python scripts\apply-reviewed-live-permit-corrections-2026.py` passed.
  - `python scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m pytest tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py -q` passed.

## EB3135 September Archery Preservation
- Timestamp (UTC): 2026-05-26T22:05:00Z
- Scope:
  - Reverted the prior `EB3135` weapon-label flattening.
  - Preserved canonical `EB3135` as `September Archery` because Barney Top/Kaiparowits has multiple archery-season contexts and the season-specific label is needed.
  - Kept `EB3135` permit values unchanged at `9 / 1 / 10`.
  - Confirmed `EB3185` remains Monroe `Mid Any Legal Weapon` at `18 / 3 / 21`.
  - Re-ran comprehensive live DWR permit extraction, database publish readiness, and comprehensive 2026/2025 history-integrity audit after restoring the label.
  - No website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Key results:
  - `EB3135` database weapon: `September Archery`.
  - `EB3135` live comparison remains numeric `MATCH`.
  - Comprehensive live DWR numeric mismatches remain `0`.
  - Publish readiness remains `true`.
  - Comprehensive history audit fatal blockers remain `0`.
- Validation:
  - `python scripts\apply-reviewed-live-permit-corrections-2026.py` passed.
  - `python scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m py_compile scripts\apply-reviewed-live-permit-corrections-2026.py` passed.
  - `python -m pytest tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py -q` passed: `8`.

## Final All-Species Permit Database Crosscheck
- Timestamp (UTC): 2026-05-26T22:10:00Z
- Scope:
  - Added a read-only all-species crosscheck for canonical `DATABASE.csv`.
  - Compared populated `permits_2026_total`, `permit_allotment_2026_total`, `permits_2025_total`, and `permits_2025_draw_total` across all hunt codes.
  - Generated detail, species-summary, prefix-summary, JSON summary, and Markdown report outputs.
  - Re-ran comprehensive live DWR extraction first so live comparison statuses were current.
  - Re-ran database publish readiness and comprehensive 2026/2025 history-integrity audit.
  - No database cells, website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed by the final crosscheck.
- Outputs:
  - `scripts/final-permit-database-crosscheck-2026.py`
  - `tests/utah/test_final_permit_database_crosscheck_2026.py`
  - `data_truth/comparison_outputs/validation/final_permit_database_crosscheck_2026.csv`
  - `data_truth/comparison_outputs/validation/final_permit_database_crosscheck_2026_by_species.csv`
  - `data_truth/comparison_outputs/validation/final_permit_database_crosscheck_2026_by_prefix.csv`
  - `data_truth/comparison_outputs/validation/final_permit_database_crosscheck_2026_summary.json`
  - `processed_data/final_permit_database_crosscheck_2026.md`
- Key results:
  - DATABASE rows: `1394`.
  - Unique hunt codes: `1394`.
  - Duplicate hunt codes: `0`.
  - Blank boundary IDs: `0`.
  - Populated `permits_2026_total` rows: `1120`.
  - Populated `permit_allotment_2026_total` rows: `912`.
  - Populated `permits_2025_total` rows: `1028`.
  - Populated `permits_2025_draw_total` rows: `572`.
  - Populated 2026 permit totals that differ from populated 2026 allotment totals: `0`.
  - Live DWR numeric mismatches remain `0`.
  - Publish readiness remains `true`.
  - Comprehensive history audit fatal blockers remain `0`.
- Validation:
  - `python scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python -m py_compile scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python -m pytest tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py -q` passed: `10`.

## Same-Code 2025 PDF Crosswalk And O.I.L. Draw Cleanup
- Timestamp (UTC): 2026-05-27T00:10:00Z
- Scope:
  - Reclassified the 16 same-code rows that appeared in the 2025 PDF but were still marked historical-only in `DATABASE.csv`.
  - Confirmed those 16 rows now crosswalk as `SAME_CODE_IN_2025_PDF_AND_CURRENT_ACTIVE`, not historical-only review rows.
  - Promoted reviewed 2025 O.I.L. PDF draw-results values for 8 Rocky Mountain bighorn sheep rows that had numeric differences against the PDF extraction.
  - Added reviewed CWMU bull moose rows `MB6225` and `MB6257` using existing CWMU boundary IDs, so the O.I.L. PDF and 2025 harvest sources no longer report those codes as missing from the database.
  - Registered `2025_OIL_DRAW_RESULTS_PDF_HUNT_YEAR_2025` as accepted historical lineage for the 2025 permit and 2025 draw-permit field families.
  - Updated crosswalk, O.I.L., LE deer, lineage, live-DWR, final crosscheck, publish-readiness, and comprehensive history-integrity outputs.
  - No website feeds, `public_client_engine.csv`, prediction math, materializer code, or populated 2026 live DWR permit/allotment numbers were changed.
- Outputs:
  - `scripts/promote-same-code-2025-pdf-crosswalk-active.py`
  - `scripts/promote-oil-2025-draw-pdf-values-to-database.py`
  - `data_truth/crosswalk_truth/validation/same_code_2025_pdf_crosswalk_active_promotions.csv`
  - `data_truth/crosswalk_truth/validation/same_code_2025_pdf_crosswalk_active_promotions_summary.json`
  - `data_truth/draw_results_truth/validation/oil_2025_draw_pdf_values_promoted_to_DATABASE.csv`
  - `data_truth/draw_results_truth/validation/oil_2025_draw_pdf_values_promoted_to_DATABASE_summary.json`
  - `processed_data/same_code_2025_pdf_crosswalk_active_promotions.md`
  - `processed_data/oil_2025_draw_pdf_values_promoted_to_DATABASE.md`
- Key results:
  - `DATABASE.csv` rows: `1449`.
  - Unique hunt codes: `1449`.
  - Duplicate hunt codes: `0`.
  - Blank boundary IDs: `0`.
  - Current-active database rows in the 2024-to-2025 PDF crosswalk: `1412`.
  - Same-code historical-only review rows remaining in the crosswalk: `0`.
  - O.I.L. 2025 PDF database matches: `101 / 101`.
  - LE deer 2025 PDF database matches: `195 / 195`.
  - 2026 permit/allotment total mismatches: `0`.
  - Historical lineage blockers: `0`.
  - Comprehensive history-integrity fatal blockers: `0`.
  - Remaining comprehensive open issues: `4`, all warning-only 2025 harvest codes not in the active database.
- Validation:
  - `python scripts\promote-oil-2025-draw-pdf-values-to-database.py` passed.
  - `python scripts\extract-oil-2025-draw-results-permits.py` passed.
  - `python scripts\extract-le-deer-2025-draw-results-permits.py` passed.
  - `python scripts\promote-same-code-2025-pdf-crosswalk-active.py` passed.
  - `python scripts\build-2024-to-2025-pdf-hunt-code-crosswalk.py` passed.
  - `python scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python scripts\audit-database-historical-permit-lineage-2026.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m py_compile scripts\promote-same-code-2025-pdf-crosswalk-active.py scripts\promote-oil-2025-draw-pdf-values-to-database.py scripts\audit-database-historical-permit-lineage-2026.py scripts\build-2024-to-2025-pdf-hunt-code-crosswalk.py scripts\extract-le-deer-2025-draw-results-permits.py scripts\extract-oil-2025-draw-results-permits.py scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python -m pytest tests\utah\test_hunt_code_crosswalk_2024_pdf_to_2025_pdf.py tests\utah\test_le_deer_2025_draw_results_extraction.py tests\utah\test_oil_2025_draw_results_extraction.py tests\utah\test_database_historical_permit_lineage_2026.py tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py -q` passed: `23`.

## Harvest-Only 2025 Code Resolution Ledger
- Timestamp (UTC): 2026-05-27T00:20:00Z
- Scope:
  - Reviewed the final 4 warning-only 2025 harvest codes: `BI0001`, `DB1774`, `PB5343`, and `PD1041`.
  - Created a reviewed harvest-only resolution ledger instead of inserting these as unverified current 2026 permit rows.
  - Wired the comprehensive 2026/2025 integrity audit to treat reviewed harvest-only resolutions as closed evidence.
  - No `DATABASE.csv` permit/allotment values, website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Resolution summary:
  - `BI0001` maps to active Antelope Island bison draw family `BI6500`; `BI0001` itself is official bison boundary/table evidence.
  - `DB1774` maps to historical draw-reality/draw-results evidence for Chalk Creek/East Canyon/Morgan-South Rich; no active 2026 DATABASE row exists.
  - `PB5343` maps to the official pronghorn table and point-ladder code for Prohibition Springs CWMU; no active 2026 DATABASE row exists.
  - `PD1041` maps historically to Heist CWMU doe pronghorn and recodes to current DATABASE row `PD1052`.
- Outputs:
  - `scripts/resolve-harvest-only-2025-codes.py`
  - `data_truth/crosswalk_truth/normalized/harvest_only_2025_code_resolutions.csv`
  - `data_truth/crosswalk_truth/validation/harvest_only_2025_code_resolutions_summary.json`
  - `processed_data/harvest_only_2025_code_resolutions.md`
- Key results:
  - Harvest-only resolution ledger rows: `4`.
  - Comprehensive history-integrity open issues: `0`.
  - Comprehensive history-integrity warning count: `0`.
  - Comprehensive history-integrity fatal blockers: `0`.
- Validation:
  - `python scripts\resolve-harvest-only-2025-codes.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python -m py_compile scripts\resolve-harvest-only-2025-codes.py scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python -m pytest tests\utah\test_hunt_code_crosswalk_2024_pdf_to_2025_pdf.py tests\utah\test_le_deer_2025_draw_results_extraction.py tests\utah\test_oil_2025_draw_results_extraction.py tests\utah\test_database_historical_permit_lineage_2026.py tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_live_dwr_and_expo_permit_promotion_2026.py tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py -q` passed: `26`.

## Harvest-Only Remap Rule Tightening
- Timestamp (UTC): 2026-05-27T00:36:00Z
- Scope:
  - Tightened the reviewed harvest-only code rule: if a 2025 code no longer exists in 2026 and does not have a definite hunt name, weapon, species, and sex-type match, classify it as discontinued.
  - Reclassified `PB5343` as `DISCONTINUED_2026_NO_DEFINITE_ONE_TO_ONE_MATCH`; no current Prohibition Springs CWMU buck pronghorn row exists in `DATABASE.csv`.
  - Reclassified `DB1774` as `DISCONTINUED_2026_NO_DEFINITE_ONE_TO_ONE_MATCH`; the old combined Dedicated Hunter deer harvest code has no one-to-one 2026 row and appears split across unit-specific current Dedicated Hunter rows.
  - Preserved `PD1041 -> PD1052` because it is a definite Heist CWMU doe pronghorn, any-legal-weapon match.
  - Preserved `BI0001 -> BI1000` as the sportsman/statewide bison equivalent from prior user review.
  - No `DATABASE.csv` permit/allotment values, website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Key results:
  - Harvest-only resolution ledger rows: `4`.
  - Discontinued/no-current-code rows: `2` (`DB1774`, `PB5343`).
  - Definite current recode rows: `1` (`PD1041 -> PD1052`).
  - Sportsman/statewide equivalent rows: `1` (`BI0001 -> BI1000`).
  - Comprehensive history-integrity open issues: `0`.
  - Comprehensive history-integrity warning count: `0`.
- Validation:
  - `python scripts\resolve-harvest-only-2025-codes.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.

## Remaining 2025 History, Crosswalk, Expo/Conservation, And Boundary Closeout
- Timestamp (UTC): 2026-05-27T00:52:00Z
- Scope:
  - Added a closeout audit for the remaining validation buckets: 2025 historical permit completeness from the 2024 draw-results PDFs, dropped/split historical hunt-code crosswalk rows, expo/conservation blank-live handling, and boundary ID proofing.
  - Confirmed the broad `permits_2025` universe is complete against the `874`-row 2024 draw-results source: `0` source codes missing from `DATABASE.csv` and `0` safe blank candidates remaining.
  - Preserved `permits_2025_draw` as the narrower draw subset: `222` source rows remain blank in that subset by design and are not treated as the full historical permit universe.
  - Reviewed the final `13` dropped/split historical crosswalk rows and classified all `13` as `REVIEWED_HISTORICAL_ONLY_NO_DEFINITE_2026_ONE_TO_ONE_MATCH`; no bad current-code remaps were forced.
  - Confirmed expo hard-copy rows promoted to `DATABASE.csv` are present: `3` checked, `0` missing database codes.
  - Confirmed conservation lock rows are present: `8` checked, `0` missing database codes.
  - Confirmed database boundary IDs against local official JSON/render evidence: `389` official-boundary code checks, `0` mismatches; render-map verification remains `promotion_safe=true`.
  - No `DATABASE.csv` permit/allotment values, website feeds, `public_client_engine.csv`, prediction math, or materializer code were changed.
- Outputs:
  - `scripts/validate-remaining-2025-history-crosswalk-boundaries.py`
  - `tests/utah/test_remaining_2025_history_crosswalk_boundary_closeout.py`
  - `data_truth/comparison_outputs/validation/remaining_2025_history_crosswalk_boundary_closeout.csv`
  - `data_truth/comparison_outputs/validation/remaining_2025_history_crosswalk_boundary_closeout_summary.json`
  - `processed_data/remaining_2025_history_crosswalk_boundary_closeout.md`
- Key results:
  - Closeout blockers: `0`.
  - DATABASE rows: `1449`.
  - Unique hunt codes: `1449`.
  - Broad 2025 draw-source rows checked: `874`.
  - Broad 2025 source codes missing database: `0`.
  - Broad 2025 safe blank candidates remaining: `0`.
  - Dropped/split crosswalk rows reviewed: `13`.
  - Dropped/split crosswalk blockers: `0`.
  - Official boundary mismatches: `0`.
  - Comprehensive history-integrity open issues: `0`.
  - Publish readiness: `true`.
- Validation:
  - `python scripts\audit-2024-draw-odds-against-database-2025-permits.py` passed.
  - `python scripts\report-br-rs-2024-draw-permit-differences.py` passed.
  - `python scripts\build-2024-to-2025-pdf-hunt-code-crosswalk.py` passed.
  - `python scripts\pull-live-dwr-permit-numbers-comprehensive-2026.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python scripts\audit-database-historical-permit-lineage-2026.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `node scripts\verify-boundary-id-render-map-2026.js` passed.
  - `python scripts\validate-remaining-2025-history-crosswalk-boundaries.py` passed.
  - `python -m py_compile scripts\validate-remaining-2025-history-crosswalk-boundaries.py scripts\audit-2024-draw-odds-against-database-2025-permits.py scripts\audit-comprehensive-2026-2025-history-integrity.py scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python -m pytest tests\utah\test_remaining_2025_history_crosswalk_boundary_closeout.py tests\utah\test_hunt_code_crosswalk_2024_pdf_to_2025_pdf.py tests\utah\test_database_historical_permit_lineage_2026.py tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py -q` passed: `13`.

## 2026 Draw-Permit Subset Alignment
- Timestamp (UTC): 2026-05-27T01:50:00Z
- Scope:
  - Created the explicit 2026 counterpart to the existing `permits_2025_draw_*` subset.
  - Added `permits_2026_draw_res`, `permits_2026_draw_nr`, `permits_2026_draw_total`, `permits_2026_draw_source`, and `draw_2026_system_type`.
  - Used `processed_data/ml_draw_predictions_v1.csv` only to identify which hunt codes feed the draw engine; permit numbers were copied from canonical `DATABASE.csv` 2026 permit/allotment truth fields.
  - Promoted the new fields into `DATABASE.csv`, draw/runtime reference surfaces, canonical CSV candidates, and a full duplicate of the LFS-backed hunt master file at `processed_data/hunt_master_enriched_2026_draw_subset.csv`.
  - Left the original `processed_data/hunt_master_enriched.csv` as an untouched Git LFS pointer so the replacement upload can remain clean.
  - No 2025 historical permit values, 2026 permit values, 2026 allotment values, website materializers, or public website feeds were recalculated or overwritten.
- Outputs:
  - `scripts/promote-2026-draw-permit-subset.py`
  - `data_truth/comparison_outputs/validation/permits_2026_draw_subset.csv`
  - `data_truth/comparison_outputs/validation/permits_2026_draw_subset_summary.json`
  - `processed_data/permits_2026_draw_subset.md`
  - `processed_data/permits_2026_draw_field_promotion_report.json`
  - `processed_data/permits_2026_draw_field_promotion_report.csv`
  - `processed_data/hunt_master_enriched_2026_draw_subset.csv`
  - `.gitattributes`
  - `tests/utah/test_2026_draw_permit_subset.py`
- Key results:
  - Draw-engine hunt codes considered: `1005`.
  - Explicit 2026 draw-permit subset rows promoted in `DATABASE.csv`: `995`.
  - Draw-engine codes missing from `DATABASE.csv`: `0`.
  - Non-numeric 2026 database totals in the subset: `0`.
  - Engine/reference codes skipped for no numeric 2026 total: `10`.
  - `hunt_master_enriched_2026_draw_subset.csv` rows checked: `54357`.
  - `hunt_master_enriched_2026_draw_subset.csv` rows populated with 2026 draw subset fields: `49930`.
- Validation:
  - `python scripts\promote-2026-draw-permit-subset.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python scripts\audit-database-historical-permit-lineage-2026.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python -m py_compile scripts\promote-2026-draw-permit-subset.py scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python -m pytest tests\utah\test_2026_draw_permit_subset.py tests\utah\test_2025_draw_permit_field_promotion.py tests\utah\test_database_historical_permit_lineage_2026.py tests\utah\test_remaining_2025_history_crosswalk_boundary_closeout.py tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py -q` passed: `30`.

## 2026 Hunt-Class Selection Matrix Repair
- Timestamp (UTC): 2026-05-27T02:10:00Z
- Scope:
  - Corrected the active selection matrix to `species -> sex_type -> hunt_type -> hunt_class -> weapon`.
  - Backfilled `hunt_class` into `DATABASE.csv`, active draw/runtime reference CSVs, canonical CSV candidates, and the edited duplicate `processed_data/hunt_master_enriched_2026_draw_subset.csv`.
  - Removed the duplicate `draw_2026_permit_family` field. `draw_2026_system_type` remains only as internal engine routing and is not a selection-matrix label.
  - Used `data/utah/official_downloads_2026/hunt_master_canonical_2026.csv` as the hunt-class source.
  - Preserved source permit numbers, historical 2025 fields, 2026 allotment totals, website feeds, and materializer logic.
- Outputs:
  - `scripts/promote-hunt-class-selection-matrix-2026.py`
  - `data_truth/comparison_outputs/validation/hunt_class_selection_matrix_2026.csv`
  - `data_truth/comparison_outputs/validation/hunt_class_selection_matrix_2026_summary.json`
  - `processed_data/hunt_class_selection_matrix_2026.md`
  - `tests/utah/test_hunt_class_selection_matrix_2026.py`
- Key results:
  - Source hunt-class codes: `1288`.
  - DATABASE rows with `hunt_class`: `1288`.
  - Duplicate selector field removed: `draw_2026_permit_family`.
  - Example: `EB1007` is `hunt_type=General Season - Any Bull`, `hunt_class=Youth`.
  - Example: `EB1003` is `hunt_type=General Season - Spike Bull`, `hunt_class=Spike Only`.
  - Example: `EB3022` is `hunt_type=Limited Entry`, `hunt_class=Mature Bull`.
  - Example: `EA2012` is `hunt_type=Private Lands Only`, `hunt_class=Antlerless`.
- Validation:
  - `python scripts\promote-2026-draw-permit-subset.py` passed.
  - `python scripts\promote-hunt-class-selection-matrix-2026.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python scripts\audit-database-historical-permit-lineage-2026.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python -m py_compile scripts\promote-2026-draw-permit-subset.py scripts\promote-hunt-class-selection-matrix-2026.py scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python -m pytest tests\utah\test_hunt_class_selection_matrix_2026.py tests\utah\test_2026_draw_permit_subset.py tests\utah\test_2025_draw_permit_field_promotion.py tests\utah\test_database_historical_permit_lineage_2026.py tests\utah\test_remaining_2025_history_crosswalk_boundary_closeout.py tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py -q` passed: `34`.

## Hunt-Class Duplicate Selection Suppression
- Timestamp (UTC): 2026-05-27T02:16:00Z
- Scope:
  - Updated the website picker logic so `hunt_class` is only shown when it further diversifies the selected `hunt_type`.
  - Preserved the matrix order as `species -> sex_type -> hunt_type -> hunt_class -> weapon`.
  - Suppressed exact duplicate class/type labels such as `Once-in-a-lifetime -> Once-in-a-lifetime`, `CWMU -> CWMU`, and singular/plural private-land duplicates.
  - Kept meaningful refinements like `Youth`, `Spike Only`, `Mature Bull`, and `Antlerless`.
- Validation:
  - `node --check app.js` passed.

## Hunt-Class Selector Moved After Weapon
- Timestamp (UTC): 2026-05-27T02:16:00Z
- Scope:
  - Reordered the user-facing picker to `species -> sex_type -> hunt_type -> weapon -> hunt_class`.
  - Moved the Hunt Class selector below Weapon Type in `index.html`.
  - Updated the matrix refresh order so weapon selection is applied before hunt-class options are recalculated.
  - Updated auto-advance order to move from Hunt Type to Weapon, then Hunt Class, then DWR Hunt Units.
  - Regenerated hunt-class selection-matrix validation outputs with the corrected order.
- Validation:
  - `python scripts\promote-hunt-class-selection-matrix-2026.py` passed.
  - `node --check app.js` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `python -m pytest tests\utah\test_hunt_class_selection_matrix_2026.py tests\utah\test_2026_draw_permit_subset.py tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py -q` passed: `16`.

## Progressive Hunt Selection Matrix
- Timestamp (UTC): 2026-05-27T02:21:51Z
- Scope:
  - Converted the Hunt Builder selection matrix into a progressive/regressive stack.
  - On page entry, only hunt-number search and Species remain open.
  - Sex, Hunt Type, Weapon, Hunt Class, and DWR Hunt Units now slide open only after the required upstream selection is made.
  - Upstream changes reset and collapse downstream choices to prevent stale selections.
  - Hunt Class remains skipped when it does not further diversify results after Weapon.
  - Added a direct `Research This Hunt` button from matching hunt cards, the selected-hunt panel, and the selected-hunt float.
  - The visible Hunt Research action carries the selected hunt through the existing Backpack/research workflow and routes to `research.html`.
- Validation:
  - `node --check app.js` passed.
  - `node tests\selection-matrix-progressive.test.js` passed.
  - `git diff --check` passed.

## 2025 Historical Source Label Repair
- Timestamp (UTC): 2026-05-27T01:18:00Z
- Scope:
  - Repaired misleading 2025 historical lineage labels that made passed-year values look like current/live 2026 data.
  - Replaced `canonical_2026_source_of_truth_draw_results` with `2025_DRAW_RESULTS_TABLES` in 2025 draw-source fields and dependent runtime/reference surfaces.
  - Replaced `2025_OIL_DRAW_RESULTS_PDF_MODEL_TARGET_2026` with `2025_OIL_DRAW_RESULTS_PDF_HUNT_YEAR_2025` in 2025 permit lineage fields.
  - Replaced the display type `2025 O.I.L. Draw Results PDF Model Target 2026` with `2025 O.I.L. Draw Results PDF Hunt Year 2025`.
  - Added `scripts/repair-2025-historical-source-labels.py` and a lineage test guard to prevent 2026/live/RAC-current labels from appearing in populated 2025 historical source fields.
  - No 2025 permit numbers, 2026 live DWR permit numbers, or 2026 allotment numbers were recalculated or overwritten.
- Key results:
  - `DATABASE.csv` rows: `1449`.
  - Unique hunt codes: `1449`.
  - Blank boundary IDs: `0`.
  - Duplicate hunt codes: `0`.
  - 2025 full historical permit rows: `1085`.
  - 2025 bonus-point draw subset rows: `682`.
  - 2026 permit/allotment mismatches: `0`.
  - Publish readiness: `true`.
- Validation:
  - `python scripts\repair-2025-historical-source-labels.py` passed.
  - `python scripts\extract-oil-2025-draw-results-permits.py` passed.
  - `python scripts\extract-le-deer-2025-draw-results-permits.py` passed.
  - `python scripts\audit-database-historical-permit-lineage-2026.py` passed.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed.
  - `python scripts\validate-remaining-2025-history-crosswalk-boundaries.py` passed.
  - `python scripts\build-database-publish-readiness-report.py` passed.
  - `node scripts\verify-boundary-id-render-map-2026.js` passed.
  - `python -m py_compile scripts\repair-2025-historical-source-labels.py scripts\audit-database-historical-permit-lineage-2026.py scripts\promote-2025-draw-permits-to-runtime.py scripts\promote-oil-2025-draw-pdf-values-to-database.py` passed.
  - `python -m pytest tests\utah\test_database_historical_permit_lineage_2026.py tests\utah\test_remaining_2025_history_crosswalk_boundary_closeout.py tests\utah\test_hunt_code_crosswalk_2024_pdf_to_2025_pdf.py tests\utah\test_le_deer_2025_draw_results_extraction.py tests\utah\test_oil_2025_draw_results_extraction.py tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py -q` passed: `20`.

## Youth Elk Draw-Only Classifier Repair
- Timestamp (UTC): 2026-05-27T16:58:00Z
- Scope:
  - Added the explicit `YOUTH_DRAW_ONLY_ELK` classifier family.
  - Routed `EB1007` to `YOUTH_DRAW_ONLY_ELK` for the draw-only youth any bull/hunter's choice elk row.
  - Routed `EB1011` to `OTC_OR_REMAINING_TARGET` so general-season youth elk availability/purchase behavior does not feed youth draw odds.
  - Updated youth strategy helpers, coverage summary labels, docs, and focused regression tests.
  - Left permit databases, website feeds, library/page-dist files, and broad generated artifacts unchanged.
- Validation:
  - Direct classifier check passed: `EB1007 -> YOUTH_DRAW_ONLY_ELK`; `EB1011 -> OTC_OR_REMAINING_TARGET`.
  - `python -m py_compile engine\utah_draw_predictive\youth.py engine\utah_draw_predictive\classifier.py tests\utah_draw_predictive\test_youth_general_any_bull_elk_strategy.py tests\utah_draw_predictive\test_youth_not_bonus_or_adult_preference.py tests\utah_draw_predictive\test_out_of_scope_runtime_policy.py tests\utah_draw_predictive\test_youth_coverage.py tests\utah_draw_predictive\test_docs_current_state.py` passed.
  - `python -m pytest tests\utah_draw_predictive\test_youth_general_any_bull_elk_strategy.py tests\utah_draw_predictive\test_youth_not_bonus_or_adult_preference.py tests\utah_draw_predictive\test_youth_coverage.py tests\utah_draw_predictive\test_out_of_scope_runtime_policy.py tests\utah_draw_predictive\test_docs_current_state.py -q` passed: `11`.
  - `git diff --check` passed.

## Youth Draw Family Split
- Timestamp (UTC): 2026-05-27T17:18:00Z
- Scope:
  - Split youth routing into four explicit draw-system families: `YOUTH_DRAW_ONLY_ELK`, `YOUTH_GENERAL_DEER_RESERVE`, `YOUTH_ANTLERLESS_OR_DOE_RESERVE`, and `YOUTH_OTC_OR_AVAILABILITY`.
  - Renamed the emitted youth general deer family from `YOUTH_GENERAL_DEER` to `YOUTH_GENERAL_DEER_RESERVE` while keeping a code alias for older imports.
  - Added youth antlerless/doe reserve detection for youth antlerless deer, youth antlerless elk, and youth doe pronghorn rows.
  - Routed `EB1011` to `YOUTH_OTC_OR_AVAILABILITY` instead of the generic `OTC_OR_REMAINING_TARGET` bucket.
  - Updated classifier coverage summaries, docs, and focused regression tests.
  - Left permit databases, website feeds, library/page-dist files, and broad generated artifacts unchanged.
- Validation:
  - Direct classifier check passed:
    - `EB1007 -> YOUTH_DRAW_ONLY_ELK`
    - `EB1011 -> YOUTH_OTC_OR_AVAILABILITY`
    - youth general deer rows -> `YOUTH_GENERAL_DEER_RESERVE`
    - youth antlerless elk and youth doe pronghorn rows -> `YOUTH_ANTLERLESS_OR_DOE_RESERVE`
  - `python -m py_compile engine\utah_draw_predictive\youth.py engine\utah_draw_predictive\classifier.py tests\utah_draw_predictive\test_youth_general_deer_strategy.py tests\utah_draw_predictive\test_youth_general_any_bull_elk_strategy.py tests\utah_draw_predictive\test_youth_not_bonus_or_adult_preference.py tests\utah_draw_predictive\test_youth_coverage.py tests\utah_draw_predictive\test_out_of_scope_runtime_policy.py tests\utah_draw_predictive\test_docs_current_state.py` passed.
  - `python -m pytest tests\utah_draw_predictive\test_youth_general_deer_strategy.py tests\utah_draw_predictive\test_youth_general_any_bull_elk_strategy.py tests\utah_draw_predictive\test_youth_not_bonus_or_adult_preference.py tests\utah_draw_predictive\test_youth_coverage.py tests\utah_draw_predictive\test_out_of_scope_runtime_policy.py tests\utah_draw_predictive\test_docs_current_state.py -q` passed: `13`.

## Active Runtime Cougar/Retired Code Cleanup
- Timestamp (UTC): 2026-05-27T04:07:00Z
- Scope:
  - Enforced the current DWR `DATABASE.csv` hunt-code universe across active runtime/reference surfaces.
  - Preserved `DATABASE.csv` unchanged as the canonical current truth source.
  - Removed the 17 user-confirmed retired 2026 codes from active runtime/reference surfaces: `EA1007`, `EA1053`, `EA1287` through `EA1300`, and `PD1039`.
  - Removed old/non-current cougar codes from active runtime/predictive surfaces, leaving only current statewide cougar code `CG9999` in the active enriched and point-ladder references.
  - Preserved removed-code evidence in `data_truth/crosswalk_truth/normalized/active_runtime_codes_removed_2026.csv`.
  - Left historical draw-reality evidence intact; it is not the current active hunt-code universe.
- Outputs:
  - `scripts/remove-retired-and-extra-cougar-active-runtime-codes-2026.py`
  - `data_truth/crosswalk_truth/normalized/active_runtime_codes_removed_2026.csv`
  - `data_truth/crosswalk_truth/validation/active_runtime_codes_removed_2026_summary.json`
  - `processed_data/active_runtime_codes_removed_2026.md`
  - `tests/utah/test_active_runtime_code_cleanup_2026.py`
- Key results:
  - `DATABASE.csv`: `1449` rows, `1449` unique hunt codes, one current cougar code: `CG9999`.
  - `hunt_master_enriched.csv`: unique hunt codes corrected from `1526` to `1449`.
  - `point_ladder_view.csv`: unique hunt codes corrected from `1526` to `1449`.
  - `hunt_master_enriched_2026_draw_subset.csv`: unique hunt codes corrected from `1471` to `1394`.
  - `ml_draw_predictions_v1.csv`: unique hunt codes corrected from `923` to `863` by removing old cougar prediction rows.
  - `draw_reality_engine_predictive_v2.csv`: unique hunt codes corrected from `923` to `863` by removing old cougar prediction rows.
  - Removed-code archive rows: `351`.
  - Active runtime cleanup blockers: `0`.
- Validation:
  - `python scripts\remove-retired-and-extra-cougar-active-runtime-codes-2026.py` passed idempotently.
  - `python scripts\final-permit-database-crosscheck-2026.py` passed: `1449` rows, `1449` unique hunt codes, `0` duplicate hunt codes, `0` blank boundary IDs, `0` 2026 permit/allotment mismatches.
  - `python scripts\scan-2026-hunt-code-family-gaps.py` passed: hunt master and point ladder both `1449` current codes; required-surface blocker families `0`.
  - `python scripts\audit-comprehensive-2026-2025-history-integrity.py` passed: fatal blockers `0`, open issues `0`.
  - `python -m py_compile scripts\remove-retired-and-extra-cougar-active-runtime-codes-2026.py scripts\scan-2026-hunt-code-family-gaps.py scripts\promote-hunt-class-routing-to-main-enriched-2026.py` passed.
  - `python -m pytest tests\utah\test_active_runtime_code_cleanup_2026.py tests\utah\test_hunt_master_enriched_hunt_class_routing_2026.py tests\utah\test_hunt_code_family_gap_scan_2026.py tests\utah\test_retired_current_hunt_codes_2026.py tests\utah\test_final_permit_database_crosscheck_2026.py tests\utah\test_2026_draw_permit_subset.py tests\utah\test_comprehensive_2026_2025_history_integrity_audit.py -q` passed: `22`.

## Hunt Research Ladder/Data Panel Repair
- Timestamp (UTC): 2026-05-27T04:31:00Z
- Scope:
  - Updated the Hunt Research point ladder so it opens automatically when scrolled into view and also opens on mouse/focus entry.
  - Reframed the row popup from a source-heavy snapshot into a decision-focused `Hunt Data Snapshot`.
  - Added plain-language pillow-box sections for current point odds, draw-pool position, catch-up/point-creep status, max-point vs random-pool interpretation, formula explanation, recommendation, permit context, and harvest snapshot.
  - Removed the need for official source/page references in the popup; source digging remains a library task.
  - Repaired `processed_data/hunt_unit_reference_linked.csv` so the research page reference layer matches the current 2026 `DATABASE.csv` hunt-code universe.
  - Removed retired/current-invalid reference rows and backfilled the 55 missing current reference codes from `hunt_master_enriched.csv` plus 2025-for-2026 harvest feature rows where available.
- Outputs:
  - `scripts/repair-hunt-research-reference-linked-2026.py`
  - `data_truth/comparison_outputs/validation/hunt_research_reference_linked_2026_summary.json`
  - `processed_data/hunt_research_reference_linked_2026.md`
  - `tests/hunt-research-ladder-data-panel.test.js`
  - `tests/utah/test_hunt_research_reference_linked_2026.py`
- Key results:
  - `hunt_unit_reference_linked.csv`: `1449` unique current hunt codes after repair.
  - Current cougar reference rows: only `CG9999`.
  - Retired EA/PD reference codes remaining: `0`.
  - Backfilled missing current reference rows: `110` rows across `55` hunt codes.
  - Harvest-populated current hunt codes in research reference: `1113`.
  - Repair blockers: `0`.
- Validation:
  - Local HTTP check for `research.html?hunt_code=EB3038` returned `200`.
  - `node --check hunt-research.js` passed.
  - `node tests\hunt-research-ladder-data-panel.test.js` passed.
  - `python -m py_compile scripts\repair-hunt-research-reference-linked-2026.py` passed.
  - `python -m pytest tests\utah\test_hunt_research_reference_linked_2026.py tests\utah\test_active_runtime_code_cleanup_2026.py tests\utah\test_final_permit_database_crosscheck_2026.py -q` passed: `5`.
  - Browser automation note: local page served, but Playwright was not installed in the available Node runtime, so screenshot/browser automation was not completed in this session.

## 2023 Big Game Draw Odds Page Map Anchor
- Timestamp (UTC): 2026-05-27T06:00:00Z
- Scope:
  - Anchored `23_bg-odds.pdf` as the 2023 big game draw-odds source for 2024 modeling and 2023 harvest-result comparison.
  - Preserved the user-supplied page map in validation output without forcing it to be the exclusive extraction boundary.
  - Added an observed physical PDF page map from the current point-level extraction.
  - Linked the 580 source hunt codes back to the existing complete 2023 harvest-vs-draw comparison.
  - Left `DATABASE.csv`, normalized draw truth, harvest truth, permit numbers, runtime files, and website feeds unchanged.
- Outputs:
  - `scripts/audit-draw-2023-bg-page-map.py`
  - `data_truth/draw_results_truth/validation/draw_2023_bg_page_map.csv`
  - `data_truth/draw_results_truth/validation/draw_2023_bg_page_map_summary.json`
  - `processed_data/draw_2023_bg_page_map.md`
  - `tests/utah/test_draw_2023_bg_page_map.py`
- Key results:
  - PDF page count: `588`.
  - Legacy/active PDF byte match: `true`.
  - Source extraction rows: `35960`.
  - Source extraction unique hunt codes: `580`.
  - Observed extraction page map coverage: `35960 / 35960` rows, `0` unassigned.
  - User-supplied page ranges assigned: `35774` rows, with `186` rows on the three seam pages not included by the supplied ranges.
  - Harvest/draw comparison linkage: `580 / 580` source codes matched.
  - Comparison buckets for this source: `579` both harvest and draw, `1` draw-only (`MB6252`).
  - Current 2026 active-database flags for this source: `541` yes, `39` no.
- Validation:
  - `python scripts\audit-draw-2023-bg-page-map.py` passed.
  - `python -m py_compile scripts\audit-draw-2023-bg-page-map.py tests\utah\test_draw_2023_bg_page_map.py` passed.
  - `python -m pytest tests\utah\test_draw_2023_bg_page_map.py -q` passed: `5`.
  - `git diff --check` passed.

## 2023 Moose Draw PDF Source Anchor
- Timestamp (UTC): 2026-05-27T06:26:00Z
- Scope:
  - Imported the legacy `bull moose.pdf` and `antlerless moose.pdf` 2023 draw-result sources into the active `HUNT-BUILDER` raw source folder.
  - Anchored both PDFs with sha256 byte-match checks against the legacy `HUNTS` copies.
  - Extracted hunt-code evidence only and compared those codes to existing 2023-for-2024 draw CSV rows.
  - Linked all moose PDF hunt codes to the existing complete 2023 harvest-vs-draw comparison.
  - Left `DATABASE.csv`, normalized draw truth, harvest truth, permit numbers, runtime files, and website feeds unchanged.
- Outputs:
  - `pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/bull moose.pdf`
  - `pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/antlerless moose.pdf`
  - `scripts/audit-draw-2023-moose-pdf-sources.py`
  - `data_truth/draw_results_truth/validation/draw_2023_moose_pdf_sources.csv`
  - `data_truth/draw_results_truth/validation/draw_2023_moose_pdf_hunt_codes.csv`
  - `data_truth/draw_results_truth/validation/draw_2023_moose_pdf_sources_summary.json`
  - `processed_data/draw_2023_moose_pdf_sources.md`
  - `tests/utah/test_draw_2023_moose_pdf_sources.py`
- Key results:
  - Source PDFs checked: `2`.
  - Byte-identical active copies: `2`.
  - Total PDF hunt codes: `33`.
  - Bull moose PDF: `41` pages, `30` MB hunt codes, `1860` expected draw CSV rows under `23_bg-odds.pdf`.
  - Antlerless moose PDF: `3` pages, `3` MA hunt codes, `108` expected draw CSV rows under `2023 Antlerless big game draw results.pdf`.
  - Codes matched to expected 2023-for-2024 draw CSV rows: `33 / 33`.
  - Codes matched to harvest/draw comparison: `33 / 33`.
  - Bull moose comparison buckets: `29` both, `1` draw-only (`MB6252`).
  - Antlerless moose comparison buckets: `3` both.
- Validation:
  - `python scripts\audit-draw-2023-moose-pdf-sources.py` passed.
  - `python -m py_compile scripts\audit-draw-2023-moose-pdf-sources.py tests\utah\test_draw_2023_moose_pdf_sources.py` passed.
  - `python -m pytest tests\utah\test_draw_2023_moose_pdf_sources.py -q` passed: `5`.
  - `git diff --check` passed.

## 2023 Moose Harvest Source Anchor
- Timestamp (UTC): 2026-05-27T06:31:00Z
- Scope:
  - Anchored the three active 2023 moose harvest CSV sources against their legacy `HUNTS` copies.
  - Compared bull and antlerless moose harvest hunt-code coverage against the 2023 moose draw PDF audit.
  - Recorded draw-only and harvest-only moose code gaps for 2024 modeling evidence.
  - Left `DATABASE.csv`, normalized harvest truth, normalized draw truth, permit numbers, runtime files, and website feeds unchanged.
- Outputs:
  - `scripts/audit-harvest-2023-moose-sources.py`
  - `data_truth/harvest_results_truth/validation/harvest_2023_moose_source_files.csv`
  - `data_truth/harvest_results_truth/validation/harvest_2023_moose_code_reconciliation.csv`
  - `data_truth/harvest_results_truth/validation/harvest_2023_moose_source_summary.json`
  - `processed_data/harvest_2023_moose_source_audit.md`
  - `tests/utah/test_harvest_2023_moose_sources.py`
- Key results:
  - Harvest CSV files checked: `3`.
  - Byte-identical active copies: `3`.
  - Bull moose harvest rows / codes: `36 / 36`.
  - Bull moose harvest totals: `171` permits, `170` hunters afield, `162` harvested.
  - Antlerless moose harvest rows / codes: `3 / 3`.
  - Antlerless moose harvest totals: `9` permits, `9` hunters afield, `8` harvested.
  - Bull moose draw-only code confirmed: `MB6252`.
  - Bull moose harvest-only codes: `MB6200`, `MB6209`, `MB6216`, `MB6217`, `MB6220`, `MB6254`, `MB6258`.
  - Antlerless moose draw/harvest mismatch count: `0`.
- Validation:
  - `python scripts\audit-harvest-2023-moose-sources.py` passed.
  - `python -m py_compile scripts\audit-harvest-2023-moose-sources.py tests\utah\test_harvest_2023_moose_sources.py` passed.
  - `python -m pytest tests\utah\test_harvest_2023_moose_sources.py -q` passed: `5`.
  - `git diff --check` passed.

## 2023 Moose Gap Fill Candidate Evidence
- Timestamp (UTC): 2026-05-27T06:44:00Z
- Scope:
  - Searched local source ledgers/permit overlays and official DWR online sources for obvious 2023 moose harvest/draw gaps.
  - Recorded review evidence only; no runtime, `DATABASE.csv`, normalized truth, permit totals, or website-facing feeds were changed.
  - Identified the Jacob's Creek CWMU code transition as the only high-confidence fill candidate.
- Outputs:
  - `scripts/audit-harvest-2023-moose-gap-fill-candidates.py`
  - `data_truth/harvest_results_truth/validation/harvest_2023_moose_gap_fill_candidates.csv`
  - `data_truth/harvest_results_truth/validation/harvest_2023_moose_gap_fill_summary.json`
  - `processed_data/harvest_2023_moose_gap_fill_audit.md`
  - `tests/utah/test_harvest_2023_moose_gap_fill_candidates.py`
- Key results:
  - Gap rows reviewed: `8`.
  - High-confidence fill candidate: `MB6252 -> MB6258` for Jacob's Creek CWMU.
  - Paired harvest target row: `MB6258`.
  - Retained harvest-only rows: `MB6200`, `MB6209`, `MB6216`, `MB6217`, `MB6220`, `MB6254`.
  - Runtime/database changes made: `NO`.
  - Official-source links recorded:
    - DWR 2022 Big Game Annual Report.
    - DWR 2023 Big Game Annual Report.
    - DWR drawing odds page.
- Validation:
  - `python scripts\audit-harvest-2023-moose-gap-fill-candidates.py` passed.
  - `python -m py_compile scripts\audit-harvest-2023-moose-gap-fill-candidates.py tests\utah\test_harvest_2023_moose_gap_fill_candidates.py` passed.
  - `python -m pytest tests\utah\test_harvest_2023_moose_gap_fill_candidates.py -q` passed: `4`.

## Short Modeled Year Source Gap Search
- Timestamp (UTC): 2026-05-27T06:52:00Z
- Scope:
  - Searched local raw source resources and official DWR online source pages for obvious gaps in the short modeled years `2021` and `2024`.
  - Built a read-only evidence audit that separates draw extraction gaps from harvest re-normalization/enrichment gaps.
  - Left `DATABASE.csv`, normalized draw truth, normalized harvest truth, materialized runtime CSVs, permit totals, and website/library outputs unchanged.
- Outputs:
  - `scripts/audit-short-modeled-year-source-gaps.py`
  - `data_truth/comparison_outputs/validation/short_modeled_year_source_gap_audit.csv`
  - `data_truth/comparison_outputs/validation/short_modeled_year_source_gap_audit_summary.json`
  - `processed_data/short_modeled_year_source_gap_audit.md`
  - `tests/utah/test_short_modeled_year_source_gap_audit.py`
- Key results:
  - Source evidence rows: `26`.
  - Local draw source families ready for extraction/reconciliation: `20`.
  - Local harvest re-normalization/enrichment opportunities: `3`.
  - 2021 draw gap pattern: normalized truth is one bonus-only source label (`21_bg-odds.pdf`), while local raw sources include general deer, lifetime deer, dedicated hunter, antlerless, youth, sportsman, black bear, cougar, and turkey source families.
  - 2021 harvest gap pattern: value-bearing `harvest_results_2021_for_2022_all_long.csv` exists locally, but current best-by-code 2021 normalized metrics are blank.
  - 2024 draw gap pattern: local 2023-for-2024 sources include preference/youth/dedicated/turkey/cougar/sportsman families that are not fully represented in normalized 2024 draw truth.
  - 2024 harvest gap pattern: local supplement files can enrich elk average age and black bear objective/mortality features.
  - Same-year gap counts recorded:
    - 2021: `447` harvest-only, `23` draw-only.
    - 2024: `471` harvest-only, `3` draw-only.
- Official source pages consulted:
  - DWR big game draw odds.
  - DWR other-species draw odds.
  - DWR big game harvest and survey reports.
  - DWR annual reports.
- Validation:
  - `python scripts\audit-short-modeled-year-source-gaps.py` passed.
  - `python -m py_compile scripts\audit-short-modeled-year-source-gaps.py tests\utah\test_short_modeled_year_source_gap_audit.py` passed.
  - `python -m pytest tests\utah\test_short_modeled_year_source_gap_audit.py -q` passed: `5`.

## Database Candidate Review Consolidation
- Timestamp (UTC): 2026-05-27T09:27:49Z
- Scope:
  - Consolidated fragmented draw, harvest, prediction, point-ladder, coverage, crosswalk, and permit-candidate evidence into a single database comparison package.
  - Compared all evidence rows against the current official `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`.
  - Preserved provenance through a source inventory and source-path/source-file fields instead of deleting raw fragments.
  - Did not modify `DATABASE.csv`, canonical permit cells, runtime engine files, website feed logic, or public library curation.
- Outputs:
  - `scripts/build-database-candidate-review-package.js`
  - `tests/database-candidate-review.test.js`
  - `data_truth/comparison_outputs/database_candidate_review/database_candidate_review_records.csv`
  - `data_truth/comparison_outputs/database_candidate_review/database_candidate_review_by_current_code.csv`
  - `data_truth/comparison_outputs/database_candidate_review/database_candidate_review_source_inventory.csv`
  - `data_truth/comparison_outputs/database_candidate_review/database_candidate_review_summary.json`
  - `processed_data/database_candidate_review.md`
- Key results:
  - Current `DATABASE.csv` hunt codes: `1,449`.
  - Source files registered/present: `25 / 25`.
  - Source rows scanned: `659,336`.
  - Normalized evidence records: `55,093`.
  - Current-code rollup rows: `1,775`.
  - Possible database-fill evidence records: `5,222`.
  - Missing-database/crosswalk-required evidence records: `3,319`.
  - Evidence domains included: draw results, harvest, harvest truth, prediction, point ladder, coverage, crosswalk, permit candidates, and comparisons.
- Validation:
  - `node scripts\build-database-candidate-review-package.js` passed.
  - `node tests\database-candidate-review.test.js` passed.

## Database Fragment Manifest And Crosswalk Join Repair
- Timestamp (UTC): 2026-05-27T09:50:00Z
- Scope:
  - Audited database-related draw, harvest, permit, crosswalk, runtime, public-export, and validation fragments in `processed_data`, `pipeline/RAW`, local `data_truth`, and external read-only `C:\Users\tyler\Desktop\GitHub\HUNTS\data_truth`.
  - Fixed the Hunt Library builder so `current_to_historical_hunt_code_crosswalk_2026.csv` joins on `current_hunt_code`, `current_code`, and `current_hunt_number` as current keys.
  - Kept `historical_hunt_code` as historical evidence metadata only; it is not treated as a current database key.
  - Did not modify `DATABASE.csv`, `hunt_master_enriched.csv`, runtime prediction CSVs, permit totals, or any copied fragment files.
- Outputs:
  - `scripts/audit-database-fragment-manifest.js`
  - `tests/database-fragment-manifest.test.js`
  - `data_truth/comparison_outputs/database_fragment_audit/database_fragment_manifest.csv`
  - `data_truth/comparison_outputs/database_fragment_audit/database_fragment_recommendations.csv`
  - `data_truth/comparison_outputs/database_fragment_audit/database_fragment_summary.json`
  - `processed_data/database_fragment_audit.md`
- Key results:
  - Fragment manifest rows: `3,186`.
  - Official current source files: `1`.
  - Runtime engine/output files: `11`.
  - Page public exports: `12`.
  - Candidate promotion files: `188`.
  - Normalized truth sources: `51`.
  - Audit/validation reports: `442`.
  - Obsolete/archive fragments: `681`, including `276` Windows copy-suffix ` (2)` files.
  - External `HUNTS` files needing import review: `61`.
  - Unknown/manual-review files: `1,800`.
- Build result after repair:
  - Current `DATABASE.csv` hunt rows: `1,449`.
  - `hunt_master_enriched.csv`: `53,225` rows, `1,449` current-code matches.
  - `draw_reality_engine.csv`: `36,912` rows, `1,449` current-code matches.
  - `draw_reality_engine_v2.csv`: `176,753` rows, `1,449` current-code matches.
  - `draw_reality_engine_predictive_v2.csv`: `26,387` rows, `863` current-code matches.
  - `ml_draw_predictions_v1.csv`: `26,387` rows, `863` current-code matches.
  - `point_ladder_view.csv`: `91,712` rows, `1,449` current-code matches.
  - `harvest_master.csv`: `1,764` rows, `1,133` current-code matches.
  - `harvest_quality_features_all_years_by_hunt_code.csv`: `5,151` rows, `1,242` current-code matches.
  - `current_to_historical_hunt_code_crosswalk_2026.csv`: `169` rows, `169` current-code matches.
  - Gate PASS: `1,449`.
  - Gate BLOCK: `0`.
- Validation:
  - `node scripts\audit-database-fragment-manifest.js` passed.
  - `node tests\database-fragment-manifest.test.js` passed.
  - `npm.cmd run build` passed.
  - `node tests\database-candidate-review.test.js` passed.
  - `git diff --check` passed with line-ending warnings only.

## Reformat 2026 Hunt Table XLSX Files For Online Display (Table Color Extension)
- Timestamp (UTC): 2026-05-29T01:54:41Z
- Scope:
  - Reformatted every workbook in:
    - processed_data/hard_data_exports/hunt_tables/2026/XLXS
  - Added bulk reformatter script:
    - scripts/reformat-hunt-tables-2026-xlsx-online.py
  - Rebuilt table ranges so styling extends across added harvest-quality columns.
  - Removed/recreated table objects per workbook to eliminate partial table-range coloring.
  - Applied consistent presentation settings:
    - styled table (TableStyleMedium2 with row striping)
    - standardized header formatting
    - freeze panes below header
    - full-range filters
    - tuned column widths
  - Added header sanitation (string/unique header names) to prevent Excel table-read warnings.
- Outputs:
  - Updated 48 XLSX files in processed_data/hard_data_exports/hunt_tables/2026/XLXS
  - Audit report:
    - processed_data/audits/hunt_tables_2026_xlsx_reformat_audit.csv
- Validation:
  - py scripts/reformat-hunt-tables-2026-xlsx-online.py passed.
  - Result: 	otal=48, ok=48, skip=0, error=0.
  - Verified table refs now span full header/data widths including added harvest columns.

## Regenerate 2026 Hunt Table PDFs From Reformatted XLXS Set
- Timestamp (UTC): 2026-05-29T02:37:40Z
- Scope:
  - Regenerated public display PDFs from:
    - processed_data/hard_data_exports/hunt_tables/2026/XLXS
  - Output folder:
    - processed_data/hard_data_exports/hunt_tables/2026/PDF'S
  - Added converter utility:
    - scripts/convert-hunt-tables-2026-xlxs-to-pdfs.py
- Validation:
  - Source workbooks counted: 48
  - Output PDFs counted: 48
  - Missing PDF count after pass:  
  - Confirmed naming coverage includes mixed-case and space-suffixed variants present in the XLXS set.

## Hunt Table Formatting Correction Follow-up (Black Bear Table Object)
- Timestamp (UTC): 2026-05-29T03:08:04Z
- Scope:
  - Investigated reported formatting miss in:
    - processed_data/hard_data_exports/hunt_tables/2026/XLXS/2026_BLACK_BEAR.xlsx
  - Found missing Excel table object on that workbook, which prevented reliable table-style propagation.
  - Reapplied full table object and style range:
    - A3:N109
  - Re-rendered corresponding PDF:
    - processed_data/hard_data_exports/hunt_tables/2026/PDF'S/2026_BLACK_BEAR.pdf
- Validation:
  - Verified all 48 XLXS files now contain table objects (
o_table=0).
  - Verified XLSX=48, PDF=48 parity.
## Regenerate 2026 Hunt Table XLSX/PDF Display Files From Clean Source Rows
- Timestamp (UTC): 2026-05-29T05:34:00Z
- Scope:
  - Rebuilt the public 2026 hunt table display workbooks from:
    - pipeline/RAW/hunt_unit_database/2026/formatted_xlsx
  - Replaced inherited/partially formatted workbook artifacts with clean files containing only the approved public columns:
    - hunt_name
    - hunt_code
    - sex_type
    - species
    - weapon
    - hunt_type
    - season
    - permits_2026_res
    - permits_2026_nr
    - permits_2026_total
    - NOTES
    - Harvest Prior Year
    - Percent Harvest Success (previous hunting season)
    - Average Age Harvested (previous hunting season)
    - Avg Days Hunted (previous hunting season)
  - Joined latest available harvest metrics from processed_data harvest feature files by hunt_code.
  - Regenerated matching public PDFs from the clean rows.
  - Standardized display filenames to uppercase visitor-facing names.
- Outputs:
  - Clean XLSX files: 46
  - Clean PDF files: 46
  - Audit:
    - processed_data/audits/hunt_tables_2026_clean_redraft_audit.csv
  - Script:
    - scripts/redraft-hunt-tables-2026-clean-display.py
- Validation:
  - Verified all 46 clean XLSX files have the exact 15-column header set.
  - Verified no merged cells remain in the clean XLSX outputs.
  - Verified each clean XLSX contains exactly one table object.
  - Verified XLSX/PDF stem parity: 46 XLSX, 46 PDF, missing pairs: 0.
  - Removed leftover Excel lock file from the display XLSX folder.
  - npm.cmd run build passed.

## DWR Hunt Planner CWMU Permit Split Correction
- Timestamp (UTC): 2026-05-29T08:55:00Z
- Scope:
  - Corrected DWR Hunt Planner permit merge behavior for CWMU rows where the source publishes resident/nonresident public-permit values but leaves the raw total field at 0.
  - Derived CWMU total as resident plus nonresident instead of treating the resident field as a total-only quota.
  - Backfilled explicit CWMU nonresident 0 values where DWR publishes `NonRes: 0`.
  - Replaced stale `LIVE_DWR_CWMU_TOTAL_ONLY_FROM_QUOTA_RES` status labels with `DWR_HUNTPLANNER_CWMU_RES_NR_TOTAL_DERIVED` for current CWMU split rows.
- Validation:
  - `node scripts/merge-dwr-huntplanner-fields-into-database-2026.js` passed.
  - DATABASE rows: 1449.
  - Matched DWR popup rows: 1449.
  - Permit exact-match/backfilled cells: 2981.
  - EB CWMU check: 67 active EB CWMU rows carry Res, NonRes 0, and Total = Res + NonRes; the remaining EB CWMU row is historical-only 2025 and not active 2026.

## Regenerate Public Hunt Table Display Files After Permit Split Corrections
- Timestamp (UTC): 2026-05-29T09:18:00Z
- Scope:
  - Regenerated public hunt-table XLSX and PDF files so the online display files reflect corrected resident/nonresident/total permit values.
  - Confirmed elk antlerless examples:
    - EA1010: Res 18, NonRes 2, Total 20.
    - EA1011: Res 9, NonRes 1, Total 10.
    - EA1118 CWMU: Res 6, NonRes 0, Total 6.
    - EA1147 CWMU: Res 15, NonRes 0, Total 15.
    - EA2002 private lands only: Total 600 with resident/nonresident blank.
  - Updated hard-copy PDF manifest links to the simplified public display filenames.
- Validation:
  - `py scripts/redraft-hunt-tables-2026-clean-display.py` passed.
  - Clean XLSX files: 46.
  - Clean PDF files: 46.
  - `npm.cmd run build` passed.
  - Gate PASS: 1449.
  - Gate BLOCK: 0.

## Public Hunt Table Permit Split Refresh - Moose And Pronghorn
- Timestamp (UTC): 2026-05-29T10:35:00Z
- Scope:
  - Updated public display hunt-table XLSX/PDF outputs for the pasted moose bull, pronghorn buck, and pronghorn doe source scopes.
  - Kept DATABASE.csv as the controlling truth source for current permit values and seasons.
  - Rebuilt the public moose bull O.I.L table to current-source scope only:
    - 2026 MOOSE BULL O.I.L: 27 rows.
  - Added public pronghorn buck display tables by hunt class:
    - 2026 PRONGHORN BUCK L.E: 66 rows.
    - 2026 PRONGHORN BUCK L.E PRIVATE LANDS ONLY: 6 rows.
    - 2026 PRONGHORN BUCK CWMU: 21 rows.
    - 2026 PRONGHORN BUCK STATEWIDE: 1 row.
  - Added public pronghorn doe display tables by hunt class:
    - 2026 PRONGHORN DOE GENERAL SEASON: 15 rows.
    - 2026 PRONGHORN DOE CWMU: 8 rows.
  - Held out historical-only/non-current rows from current public display tables, including PD1006, PD1016, PD1025, PD1026, PD1032, PD1045, PD1046, PB5313, and PB5341.
  - Updated hard-copy PDF manifest links for the new public pronghorn table PDFs/XLSX companions.
- Validation:
  - Verified all target XLSX files exist and row counts match the selected current-source scopes.
  - Verified matching PDFs exist locally and in pages-dist.
  - Verified hard_copy_pdf_manifest.web.json contains all new public pronghorn table entries.
  - `npm.cmd run build` passed.
  - Gate PASS: 1449.
  - Gate BLOCK: 0.

## Black Bear Permit Truth-Source Correction
- Timestamp (UTC): 2026-05-29T11:25:00Z
- Scope:
  - Treated the user-pasted Utah DWR Hunt Planner black bear rows as the controlling truth source for this correction pass.
  - Corrected `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 black bear permits reviewed res-nr-total.csv` so BR7307 no longer carries an unsupported numeric total.
  - Normalized local helper black bear CSVs so orphan `NonRes:` continuation rows were folded into the matching row and totals were recomputed from resident plus nonresident values.
  - Confirmed BR7004 remains DWR truth as Res 18, NonRes 0, Total 18.
- Validation:
  - Reviewed black bear rows: 106.
  - Full split rows: 100.
  - Blank/no published numeric permit rows: 6.
  - Partial permit rows: 0.
  - Duplicate hunt codes: 0.
  - Bad Res + NonRes totals: 0.
  - Orphan NonRes rows: 0.

## Antlerless Elk Permit Truth-Source Correction
- Timestamp (UTC): 2026-05-29T11:45:00Z
- Scope:
  - Treated the user-pasted Utah DWR Hunt Planner antlerless elk EA rows as the controlling truth source for this correction pass.
  - Created `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 elk antlerless all reviewed res-nr-total.csv` from the pasted-row-aligned 2026 elk antlerless draw table, with boundary-id metadata joined from DATABASE.csv only for mapping context.
  - Normalized `elk antlerless private lands only EA.csv` to use numeric total-only permit values instead of `Total: N` text.
  - Confirmed expo/conservation/control/pending rows remain blank when the DWR-pasted row did not publish a numeric permit value, including EA1220, EA1221, EA1258, and EA1286.
- Validation:
  - Reviewed EA rows: 204.
  - Full split rows: 167.
  - Total-only rows: 27.
  - Blank/no published numeric permit rows: 10.
  - Partial permit rows: 0.
  - Duplicate hunt codes: 0.
  - Bad Res + NonRes totals: 0.

## Reviewed 2026 Permit Truth Source Family Builder
- Timestamp (UTC): 2026-05-29T10:42:00Z
- Scope:
  - Created `scripts/build-reviewed-permit-truth-sources-2026.py` to rebuild reviewed permit truth-source CSVs from the pasted-aligned public hunt table workbooks.
  - Wrote reviewed family source files under `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits` for black bear, buck deer, elk antlerless, elk bull, moose bull, pronghorn buck, and pronghorn doe.
  - Added boundary-id mapping metadata from `DATABASE.csv` while preserving hunt name, weapon, hunt type, season, sex type, species, and permit values from the pasted-aligned workbook rows.
  - Added source workbook and source row number to every reviewed row for traceability.
  - Wrote audit outputs:
    - `processed_data/audits/reviewed_permit_truth_sources_2026_audit.csv`
    - `processed_data/audits/reviewed_permit_truth_sources_2026_audit.json`
- Validation:
  - BLACK_BEAR: 106 rows; 100 full split; 0 total-only; 6 blank/no published numeric; duplicates 0; bad totals 0; missing source rows 0.
  - BUCK_DEER: 458 rows; 192 full split; 136 total-only; 130 blank/no published numeric; duplicates 0; bad totals 0; missing source rows 0.
  - ELK_ANTLERLESS: 204 rows; 167 full split; 27 total-only; 10 blank/no published numeric; duplicates 0; bad totals 0; missing source rows 0.
  - ELK_BULL: 353 rows; 209 full split; 2 total-only; 142 blank/no published numeric; duplicates 0; bad totals 0; missing source rows 0.
  - MOOSE_BULL: 27 rows; 26 full split; 0 total-only; 1 blank/no published numeric; duplicates 0; bad totals 0; missing source rows 0.
  - PRONGHORN_BUCK: 94 rows; 87 full split; 0 total-only; 7 blank/no published numeric; duplicates 0; bad totals 0; missing source rows 0.
  - PRONGHORN_DOE: 23 rows; 23 full split; 0 total-only; 0 blank/no published numeric; duplicates 0; bad totals 0; missing source rows 0.
  - Re-ran `py scripts/build-reviewed-permit-truth-sources-2026.py` after correcting the builder so DATABASE contributes boundary metadata only, avoiding HAMSS deer field-shift contamination.

## Bearded Turkey 2026 Permit Truth Source Addition
- Timestamp (UTC): 2026-05-29T10:44:00Z
- Scope:
  - Added `TURKEY_BEARDED` to `scripts/build-reviewed-permit-truth-sources-2026.py`.
  - Created `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 turkey bearded all reviewed total.csv` from the pasted-aligned `2026 TURKEY BEARDED DRAW.xlsx` workbook.
  - Preserved total-only permit handling for limited-entry and CWMU rows and kept statewide/general/conservation rows blank where no numeric permit count was published.
  - Included boundary-id metadata from `DATABASE.csv` and source workbook/source row lineage on every row.
  - Updated reviewed permit truth-source audit CSV/JSON.
- Validation:
  - TURKEY_BEARDED rows: 14.
  - Total-only rows: 7.
  - Blank/no published numeric permit rows: 7.
  - Duplicate hunt codes: 0.
  - Bad split totals: 0.
  - Missing source rows: 0.

## Either-Sex Turkey 2026 Permit Truth Source Addition
- Timestamp (UTC): 2026-05-29T10:45:00Z
- Scope:
  - Added `TURKEY_EITHER_SEX` to `scripts/build-reviewed-permit-truth-sources-2026.py`.
  - Created `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 turkey either sex all reviewed total.csv` from the pasted-aligned `2026 TURKEY EITHER SEX DRAW.xlsx` workbook.
  - Preserved Fall Management total-only permit handling and included boundary-id metadata from `DATABASE.csv` plus source workbook/source row lineage.
  - Updated reviewed permit truth-source audit CSV/JSON.
- Validation:
  - TURKEY_EITHER_SEX rows: 4.
  - Total-only rows: 4.
  - Duplicate hunt codes: 0.
  - Bad split totals: 0.
  - Missing source rows: 0.

## Rocky Mountain Bighorn 2026 Permit Truth Source Correction
- Timestamp (UTC): 2026-05-29T10:49:00Z
- Scope:
  - Added `ROCKY_MOUNTAIN_BIGHORN_RAM` to `scripts/build-reviewed-permit-truth-sources-2026.py` using reviewed inline pasted DWR Hunt Planner RS rows because the public workbook currently named for Rocky Mountain bighorn ram contains desert bighorn DS rows.
  - Rebuilt `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 rocky mountain bighorn reviewed res-nr-total.csv` from the user-pasted RS truth source.
  - Removed the prior RE1000 ewe row from the Rocky Mountain bighorn ram reviewed file.
  - Blank-preserved RS0001, RS1000, RS1001, RS1003, and RS1006 where the pasted DWR rows did not publish numeric permit counts.
  - Added source lineage fields identifying the reviewed pasted DWR source row for every RS row.
  - Updated reviewed permit truth-source audit CSV/JSON.
- Validation:
  - ROCKY_MOUNTAIN_BIGHORN_RAM rows: 20.
  - Full split rows: 15.
  - Blank/no published numeric permit rows: 5.
  - Duplicate hunt codes: 0.
  - Bad split totals: 0.
  - Missing source rows: 0.

## Desert Bighorn Ram And Rocky Mountain Bighorn Ewe Permit Truth Sources
- Timestamp (UTC): 2026-05-29T10:52:00Z
- Scope:
  - Added `ROCKY_MOUNTAIN_BIGHORN_EWE` to `scripts/build-reviewed-permit-truth-sources-2026.py` from `2026 ROCKY MOUNTAIN BIGHORN SHEEP EWE O.I.L.xlsx`.
  - Created `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 rocky mountain bighorn ewe reviewed res-nr-total.csv` for RE1000 as a separate ewe family file.
  - Added `DESERT_BIGHORN_RAM` to the reviewed builder from `2026 DESERT BIGHORN SHEEP RAM O.I.L.xlsx`.
  - Rebuilt `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 desert bighorn reviewed res-nr-total.csv` to include the full pasted DS family, not only the split-permit hunt rows.
  - Preserved blank numeric permit fields for DS1000, DS1002, DS1003, DS1004, DS1006, DS1007, and DS6605 because the pasted DWR rows did not publish numeric permit values for those rows.
  - Updated reviewed permit truth-source audit CSV/JSON.
- Validation:
  - ROCKY_MOUNTAIN_BIGHORN_EWE rows: 1; full split rows: 1; duplicate hunt codes: 0; bad split totals: 0; missing source rows: 0.
  - DESERT_BIGHORN_RAM rows: 25; full split rows: 18; blank/no published numeric permit rows: 7; duplicate hunt codes: 0; bad split totals: 0; missing source rows: 0.

## Statewide Permit Rule, Mountain Goat, And Pronghorn Doe Corrections
- Timestamp (UTC): 2026-05-29T11:33:00Z
- Scope:
  - Updated `scripts/build-reviewed-permit-truth-sources-2026.py` so `*Statewide Permit` rows are total-only permit rows with `permits_2026_total = 1` and resident/nonresident blank.
  - Confirmed conservation permits remain on their own separate hunt codes and are not combined into statewide permit rows.
  - Added `MOUNTAIN_GOAT_HUNTERS_CHOICE` from `2026 MOUNTAIN GOAT HUNTER CHOICE O.I.L.xlsx`.
  - Created `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 mountain goat reviewed res-nr-total.csv`.
  - Rebuilt `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 pronghorn doe all reviewed res-nr-total.csv` from the user-pasted DWR Hunt Planner PD rows to preserve the pasted 2025 season dates and source lineage.
  - Updated reviewed permit truth-source audit CSV/JSON.
- Validation:
  - Statewide permit rows checked across reviewed families: BR1000, DB0007, DS1000, EB1000, MB1000, GO1000, PB1000, RS0001, and TK0001 all carry total-only `1`.
  - MOUNTAIN_GOAT_HUNTERS_CHOICE rows: 18; full split rows: 17; total-only rows: 1; duplicate hunt codes: 0; bad split totals: 0; missing source rows: 0.
  - PRONGHORN_DOE rows: 23; full split rows: 23; duplicate hunt codes: 0; bad split totals: 0; missing source rows: 0.

## Pronghorn Buck 2026 Permit Truth Source Correction
- Timestamp (UTC): 2026-05-29T11:38:00Z
- Scope:
  - Rebuilt `PRONGHORN_BUCK` in `scripts/build-reviewed-permit-truth-sources-2026.py` from the user-pasted Utah DWR Hunt Planner LP/PB rows instead of the generated workbook split.
  - Added reviewed inline TSV parsing for pasted permit families so `Res:`, `NonRes:`, and `Total:` lines are normalized into canonical permit columns without hand-entering large dictionary blocks.
  - Rebuilt `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 pronghorn buck all reviewed res-nr-total.csv` with DWR pasted source lineage on every row.
  - Preserved the six LP private-land rows as no-published-numeric permit rows and kept `PB1000` as the separate statewide total-only permit row with `permits_2026_total = 1`.
  - Updated reviewed permit truth-source audit CSV/JSON.
- Validation:
  - PRONGHORN_BUCK rows: 94.
  - Full split rows: 87.
  - Total-only rows: 1.
  - Blank/no published numeric permit rows: 6.
  - Duplicate hunt codes: 0.
  - Bad split totals: 0.
  - Missing source rows: 0.
  - Spot checks passed for LP5025, LP5051, PB1000, PB5000, PB5049, PB5076, PB5302, and PB5346.

## Moose Antlerless 2026 Permit Truth Source Addition
- Timestamp (UTC): 2026-05-29T11:40:00Z
- Scope:
  - Added `MOOSE_ANTLERLESS` to `scripts/build-reviewed-permit-truth-sources-2026.py` from the user-pasted Utah DWR Hunt Planner MA rows.
  - Created `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 moose antlerless reviewed res-nr-total.csv` as a separate antlerless moose family file from Moose Bull.
  - Preserved 2025 season dates and CWMU operator-date text exactly from the pasted source rows.
  - Included boundary-id metadata from `DATABASE.csv` and source lineage identifying the pasted DWR Hunt Planner source row.
  - Updated reviewed permit truth-source audit CSV/JSON.
- Validation:
  - MOOSE_ANTLERLESS rows: 5.
  - Full split rows: 5.
  - Duplicate hunt codes: 0.
  - Bad split totals: 0.
  - Missing source rows: 0.
  - Spot checks passed for MA1005, MA1007, MA1008, MA1009, and MA1010.

## Bison 2026 Permit Truth Source Addition
- Timestamp (UTC): 2026-05-29T11:47:00Z
- Scope:
  - Added `BISON_HUNTERS_CHOICE` to `scripts/build-reviewed-permit-truth-sources-2026.py` from the user-pasted Utah DWR Hunt Planner BI rows.
  - Created `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 bison reviewed res-nr-total.csv` as the reviewed BI family file.
  - Applied the statewide permit rule so `BI1000` is total-only with `permits_2026_total = 1`.
  - Preserved BI6527 and BI6538 as no-published-numeric permit rows because the pasted DWR source rows did not publish permit counts.
  - Included boundary-id metadata from `DATABASE.csv` and source lineage identifying the pasted DWR Hunt Planner source rows.
  - Updated reviewed permit truth-source audit CSV/JSON.
- Validation:
  - BISON_HUNTERS_CHOICE rows: 14.
  - Full split rows: 11.
  - Total-only rows: 1.
  - Blank/no published numeric permit rows: 2.
  - Duplicate hunt codes: 0.
  - Bad split totals: 0.
  - Missing source rows: 0.
  - Spot checks passed for BI1000, BI6500, BI6503, BI6509, BI6527, BI6537, and BI6538.

## Bison Cow Only 2026 Permit Truth Source Addition
- Timestamp (UTC): 2026-05-29T11:49:00Z
- Scope:
  - Added `BISON_COW_ONLY` to `scripts/build-reviewed-permit-truth-sources-2026.py` from the user-pasted Utah DWR Hunt Planner BI cow-only rows.
  - Created `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 bison cow only reviewed res-nr-total.csv` as a separate cow-only Bison family file from Hunters Choice.
  - Preserved the pasted 2026/2027 season strings and resident/nonresident split counts.
  - Included boundary-id metadata from `DATABASE.csv` and source lineage identifying the pasted DWR Hunt Planner source rows.
  - Updated reviewed permit truth-source audit CSV/JSON.
- Validation:
  - BISON_COW_ONLY rows: 5.
  - Full split rows: 5.
  - Duplicate hunt codes: 0.
  - Bad split totals: 0.
  - Missing source rows: 0.
  - Spot checks passed for BI6505, BI6506, BI6529, BI6536, and BI6539.

## Deer Antlerless And Cougar 2026 Permit Truth Source Additions
- Timestamp (UTC): 2026-05-29T11:52:00Z
- Scope:
  - Added `DEER_ANTLERLESS` to `scripts/build-reviewed-permit-truth-sources-2026.py` from the user-pasted Utah DWR Hunt Planner DA rows.
  - Created `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 deer antlerless reviewed res-nr-total.csv`.
  - Added `COUGAR_EITHER_SEX` from the user-pasted Utah DWR Hunt Planner CG9999 row.
  - Created `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 cougar reviewed res-nr-total.csv`.
  - Preserved `CG9999` as no-published-numeric because `unlimited permits.` is not a numeric permit count.
  - Did not add DA1044 from `DATABASE.csv` because the user has not pasted that DWR source row; DA1044 remains the only current DA code not present in the reviewed pasted DA output.
  - Updated reviewed permit truth-source audit CSV/JSON.
- Validation:
  - DEER_ANTLERLESS rows: 20.
  - DEER_ANTLERLESS total-only rows: 16.
  - DEER_ANTLERLESS full split rows: 4.
  - COUGAR_EITHER_SEX rows: 1; blank/no published numeric permit rows: 1.
  - Duplicate hunt codes: 0.
  - Bad split totals: 0.
  - Missing source rows: 0.
  - DA reconciliation against `DATABASE.csv`: 21 DA database codes, 20 reviewed pasted DA codes, missing reviewed code `DA1044`.
  - Spot checks passed for DA1001, DA1011, DA1041, DA1050, and CG9999.

## Elk Extended Archery 2026 Permit Truth Source Addition
- Timestamp (UTC): 2026-05-29T11:54:00Z
- Scope:
  - Added `ELK_EXTENDED_ARCHERY` to `scripts/build-reviewed-permit-truth-sources-2026.py` from the user-pasted Utah DWR Hunt Planner EX1000 row.
  - Created `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 elk extended archery reviewed res-nr-total.csv`.
  - Preserved EX1000 as no-published-numeric because the pasted DWR row did not publish a numeric permit count.
  - Included boundary-id metadata from `DATABASE.csv` and source lineage identifying the pasted DWR Hunt Planner source row.
  - Updated reviewed permit truth-source audit CSV/JSON.
- Validation:
  - ELK_EXTENDED_ARCHERY rows: 1.
  - Blank/no published numeric permit rows: 1.
  - Duplicate hunt codes: 0.
  - Bad split totals: 0.
  - Missing source rows: 0.
  - Prefix reconciliation against `DATABASE.csv`: all current database hunt-code prefixes are now represented in reviewed permit files.
  - Known row-level open item remains DA1044 because the corresponding DWR row has not been pasted/reviewed.

## DA1044 Historical Hold And Permit Database Reconciliation Audit
- Timestamp (UTC): 2026-05-29T11:56:00Z
- Scope:
  - Recorded `DA1044` / Myton antlerless deer as a reviewed database exclusion in `scripts/build-reviewed-permit-truth-sources-2026.py`.
  - Reason: user reviewed Utah DWR Hunt Planner, found no current DA1044 result, and found no same/similar current hunt name to crosswalk.
  - Rebuilt `processed_data/audits/reviewed_permit_truth_sources_2026_audit.json` with a `database_reconciliation` section that preserves reviewed exclusions and lists remaining database-only hunt codes as review evidence.
  - Did not create or promote a DA1044 reviewed permit row.
- Validation:
  - Reviewed exclusion recorded for DA1044 with status `HOLD_HISTORICAL_NO_CURRENT_DWR_ROW`.
  - Reviewed permit hunt-code count in audit: 1393.
  - Current `DATABASE.csv` hunt-code count in audit: 1449.
  - Remaining database-only hunt codes excluding DA1044: 55; these are review evidence only and were not promoted.
  - Builder syntax validation passed with `py -m py_compile scripts/build-reviewed-permit-truth-sources-2026.py`.

## Reviewed 2026 Permit Truth Master And Fragment Manifest
- Timestamp (UTC): 2026-05-29T12:03:00Z
- Scope:
  - Updated `scripts/build-reviewed-permit-truth-sources-2026.py` to write a canonical master file: `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 reviewed permit truth master.csv`.
  - Updated the builder to write `pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 superseded permit fragments manifest.csv`.
  - The fragment cleanup is non-destructive: old fragment CSVs are not deleted, moved, or overwritten; the manifest marks them `ACTIVE_SUPERSEDED_FRAGMENT_DO_NOT_USE_FOR_CANONICAL_PERMITS`.
  - No `hard-copy`, research-library, hunt-research, public display, runtime engine, prediction, or `DATABASE.csv` files were modified.
  - Updated reviewed permit truth-source audit JSON with canonical output metadata and non-destructive cleanup mode.
- Validation:
  - Master rows: 1393.
  - Missing source_file rows: 0.
  - Missing source_row_number rows: 0.
  - Partial permit status rows: 0.
  - Bad resident/nonresident split totals: 0.
  - Exact duplicate canonical keys: 0.
  - Superseded fragment manifest rows: 8.
  - Fragment cleanup mode: `NON_DESTRUCTIVE_MANIFEST_ONLY`.

## 2026 Hunt Table PDF Average Harvest Age Render
- Timestamp (UTC): 2026-05-29T12:52:00Z
- Scope:
  - Updated only the public-display PDF hunt tables in `processed_data/hard_data_exports/hunt_tables/2026/PDF'S`.
  - Rendered `Average Age Harvested (previous hunting season)` into PDFs from `processed_data/harvest_age_features_by_hunt_code_latest.csv` using only `PASS` rows with numeric animal age greater than zero.
  - Left cells blank when no PASS numeric hard-data age existed; did not use average-days, percent mature, age objectives, proxy-only rows, or low-confidence REVIEW rows as age.
  - Added PDF-only renderer `scripts/render-hunt-table-pdfs-2026-average-age.py` so XLSX files are read but not saved.
  - Changed `scripts/audit-hunt-table-average-age-2026.py` to audit only and not fill/save XLSX workbooks.
  - No `XLXS` files, hard-copy page work, research-library files, hunt-research page files, runtime engine files, prediction outputs, or `DATABASE.csv` were modified.
- Validation:
  - PDF files present/written: 52.
  - Rows audited: 2391.
  - PASS numeric hard-age codes available: 326.
  - PDF age cells rendered from PASS hard data: 518.
  - Blank cells with no PASS numeric hard data: 1873.
  - Blank-but-fillable rows: 0 by PDF render audit design; every hard-data match was rendered in memory.
  - XLSX folder diff: none.
  - Spot PDF text extraction confirmed updated PDF content and average-age headers/values render in sample PDFs.
  - Audit outputs: `processed_data/audits/hunt_tables_2026_pdf_average_age_audit.csv` and `processed_data/audits/hunt_tables_2026_pdf_average_age_audit.json`.

## Reviewed Harvest Age And Boundary Promotion To Feeders
- Timestamp (UTC): 2026-05-29T13:58:00Z
- Scope:
  - Promoted reviewed PASS numeric `average_harvest_age` values from `processed_data/harvest_age_features_by_hunt_code_latest.csv` into canonical `DATABASE.csv` and feeder/reference files.
  - Preserved `current_age_3yr_average` as a distinct DWR Hunt Planner 3-year-age field; no existing `DATABASE.csv` columns or values were changed.
  - Added `average_harvest_age`, `average_harvest_age_reported_hunt_year`, `average_harvest_age_source_file`, and `average_harvest_age_review_status` lineage fields where needed.
  - Reconciled and populated `boundary_id` from canonical `DATABASE.csv` into feeder/reference files where blank, and overwrote audited downstream conflicts to the database value.
  - Added all 52 generated 2026 public hunt-table PDFs to `processed_data/hard_data_exports/library/public_library_allowlist.json` for the hard-copy online display.
  - Did not restore or stage user-moved/deleted local files, including `public/hard-copy/regulations/2026/2025.regs.biggame.viewer.pdf` and `processed_data/point_ladder_veiw_compressed.csv`.
- Validation:
  - PASS numeric age codes available: 326.
  - PASS numeric age codes found in current `DATABASE.csv`: 319.
  - PASS numeric age codes not found in current `DATABASE.csv`: 7 (`EB3133`, `EB3134`, `EB3140`, `EB3141`, `GO6809`, `MA1000`, `PB5058`).
  - `DATABASE.csv`: 1,449 rows; existing-column changes: 0; `current_age_3yr_average` filled rows: 220; `average_harvest_age` filled rows: 319.
  - `point_ladder_view.csv`: 91,712 rows; `boundary_id` filled rows: 91,712; `average_harvest_age` filled rows: 20,670; `current_age_3yr_average` filled rows: 14,454.
  - `hunt_master_enriched.csv`: 53,225 rows; `boundary_id` filled rows: 53,225; `average_harvest_age` filled rows: 11,902; `current_age_3yr_average` filled rows: 14,390.
  - `hunt_unit_reference_linked.csv`: 2,953 rows; `boundary_id` filled rows: 2,953; `average_harvest_age` filled rows: 638; `current_age_3yr_average` filled rows: 438.
  - `draw_reality_engine_v2.csv`: 176,753 rows; `boundary_id` filled rows: 169,548; `average_harvest_age` filled rows: 32,662; `current_age_3yr_average` filled rows: 46,945; boundary conflicts overwritten to database: 10.
  - `draw_reality_engine.csv`: 36,912 rows; `boundary_id` filled rows: 32,753; `average_harvest_age` filled rows: 7,185; `current_age_3yr_average` filled rows: 10,207.
  - `draw_reality_engine_predictive_v2.csv`: 26,507 rows; `boundary_id` filled rows: 26,387; `average_harvest_age` filled rows: 6,109; `current_age_3yr_average` filled rows: 13,113.
  - Public library allowlist: 52 hunt-table PDF items added; final allowlist count: 67.
  - Remaining allowlist validation issues are pre-existing/moved source-document paths: 4 missing source PDF hrefs and 1 missing moved viewer PDF href.
  - Audit outputs: `processed_data/audits/reviewed_age_boundary_promotion_2026_audit.json`, `processed_data/audits/reviewed_age_boundary_promotion_2026_audit.csv`, and `processed_data/audits/public_library_hunt_table_pdf_allowlist_2026_audit.json`.

## Hunt Research Cloudflare Runtime And Outlook Dashboard
- Timestamp (UTC): 2026-05-29T14:24:00Z
- Scope:
  - Updated `config.js` so Hunt Research large runtime CSV arrays are explicitly Cloudflare-first, with local GitHub Pages/LFS paths as fallback only.
  - Bumped `HUNT_RESEARCH_DATA_VERSION` to `20260529-cloudflare-runtime-first-1`.
  - Added `scripts/audit-research-runtime-sources.js` and wrote CSV/JSON runtime source audits for Cloudflare/R2 CSV delivery.
  - Replaced the proof-only dashboard with a full display-only dashboard in `assets/js/research-outlook-dashboard.js` and render it above the point ladder.
  - Added a read-only `uoga:hunt-research-rendered` snapshot event in `hunt-research.js` so the dashboard uses the already-loaded Research rows and does not duplicate giant runtime CSV downloads or alter any ladder/prediction math.
  - Fixed the malformed dashboard script tag in `research.html` and cache-bumped `hunt-research.js`/dashboard includes.
  - Updated `scripts/build-pages-dist.js` so `processed_data/management_context` is copied to `pages-dist` for management objective context.
  - Did not modify `DATABASE.csv`, materializers, draw/harvest/age truth files, prediction formulas, point-ladder math, permit/allotment truth, or engine scoring.
- Validation:
  - `node --check config.js` passed.
  - `node --check embed-mode.js` passed.
  - `node --check hunt-research.js` passed.
  - `node --check assets/js/research-outlook-dashboard.js` passed.
  - `node --check scripts/audit-research-runtime-sources.js` passed.
  - `node scripts/audit-research-runtime-sources.js` passed: 10/10 Cloudflare URLs OK, 0 LFS pointer responses, all three critical files OK (`point_ladder_view.csv`, `hunt_master_enriched.csv`, `hunt_unit_reference_linked.csv`).
  - `npm.cmd run build` passed. Build still reports existing optional/missing/oversized notices: `staging-audit.html`, `data/hunt_boundaries_finalized_2026.geojson`, and oversized `processed_data/composite_hunt_unit_mapping_2026.geojson` skipped for Pages.
  - Verified `research.html` and `pages-dist/research.html` include `research-outlook-dashboard` and the snapshot bridge cache token.
  - Verified `pages-dist/assets/js/research-outlook-dashboard.js` exists.
  - Verified `pages-dist/processed_data/management_context/hunt_management_objective_context.json` exists.
  - Built-local browser check at `http://127.0.0.1:4180/research.html?hunt_code=DB1019&residency=resident&points=12&v=cloudflarefirst2` passed: dashboard rendered above point ladder, ladder rows loaded, critical CSV resources loaded from `https://json.uoga.workers.dev/processed_data/...`, and no Git LFS pointer errors.
  - Live browser check at `https://hunt-builder.uoga.org/research.html?hunt_code=DB1019&residency=resident&points=12&v=cloudflarefirst2` passed for core data/no LFS pointer errors, but it still shows the old proof panel until this commit is deployed.
  - Audit outputs: `processed_data/audits/research_runtime_source_audit.json` and `processed_data/audits/research_runtime_source_audit.csv`.

## Hunt Research Desktop Width And Entry Hash Cleanup
- Timestamp (UTC): 2026-05-29T14:52:00Z
- Scope:
  - Added desktop Research CSS overrides so `.research-shell` is centered at `min(1680px, calc(100vw - 64px))` and the main layout/cards use the available width.
  - Expanded desktop control, chip, summary, report, and ladder/table layout widths without changing data loading, prediction formulas, point-ladder math, or runtime source arrays.
  - Kept mobile behavior stacked below 768px and ensured signal summary cards no longer force a two-column mobile grid.
  - Tightened the Outlook dashboard insertion fallback to prefer `insertBefore(pointLadderAccordion)`, then `detailContent.insertAdjacentElement("afterend")`, then parent append.
  - Updated default Google Maps mode hash behavior so the entry page no longer leaves or rewrites `#google-maps` in the visible URL; Earth/DWR hash routes remain available.
  - Did not modify `DATABASE.csv`, engine files, runtime CSVs, truth files, formulas, or source arrays.
- Validation:
  - `node --check assets/js/research-outlook-dashboard.js` passed.
  - `node --check hunt-research.js` passed.
  - `node --check app.js` passed.
  - `npm.cmd run build` passed. Existing optional build notices remain: `staging-audit.html`, `data/hunt_boundaries_finalized_2026.geojson`, and oversized `processed_data/composite_hunt_unit_mapping_2026.geojson` skipped for Pages.
  - Built-local desktop browser check at 1920x1080 passed: Research shell width 1680px, controls/result cards 1632px, ladder 1594px, table 1568px, dashboard above ladder, and no Git LFS pointer errors.
  - Built-local mobile browser check at 390px passed: control/chip/summary grids one-column, signal cards auto-column, table overflow remains horizontal scroll.
  - Built-local entry URL check from `/#google-maps` rewrote to `/` with empty hash.

## Hunt Research Desktop Dashboard Grid Rework
- Timestamp (UTC): 2026-05-29T15:42:00Z
- Implementation commit: b90c8428
- Files changed:
  - `research.html`
  - `assets/js/research-outlook-dashboard.js`
- Scope:
  - Reworked the Hunt Application Outlook add-on from stacked report panels into a compact desktop dashboard using a full-width hero strip, three-column dashboard grid, compact comparable hunt cards, and collapsed source/freshness/model details.
  - Kept dashboard insertion immediately before `#pointLadderAccordion`, so the dashboard renders above the point ladder and the ladder remains full-width below.
  - Tightened the desktop Research layout so the Hunter Inputs card, existing summary chips, and prediction summary use horizontal space more effectively; the summary grid now uses six columns on wide desktop screens.
  - Kept source paths inside a collapsed `<details class="uoga-source-details">` block instead of always-visible technical text.
  - Preserved management objective language as context only with a `Management Plan Context` badge and benchmark-only note.
  - Enforced age display rules in the dashboard: zero or missing average harvest age renders as `No verified age data`; average days hunted is displayed only as days hunted, not as age.
  - Did not modify `DATABASE.csv`, engine files, prediction formulas, draw/harvest/age truth files, point-ladder math, permit/allotment truth, runtime CSVs, or Cloudflare/R2 source arrays.
- Validation:
  - `node --check assets/js/research-outlook-dashboard.js` passed.
  - `node --check hunt-research.js` passed.
  - `npm.cmd run build` passed. Existing optional build notices remain: `staging-audit.html`, `data/hunt_boundaries_finalized_2026.geojson`, and oversized `processed_data/composite_hunt_unit_mapping_2026.geojson` skipped for Pages.
  - Verified `research.html` includes `research-outlook-dashboard` with cache token `outlook-dashboard-grid-1`.
  - Verified `pages-dist/research.html` includes `research-outlook-dashboard`.
  - Verified `pages-dist/assets/js/research-outlook-dashboard.js` exists.
  - Built-local desktop browser check at 1920x1080 passed for `research.html?hunt_code=EB3024&draw_pool=standard&residency=resident&points=30&v=dashboardgrid1`: controls/result cards 1632px wide, existing summary grid six columns, dashboard 1598px wide, dashboard grid three columns, hero strip four columns, comparable hunts five columns, source details collapsed by default, dashboard above ladder, ladder/table full-width below, and no Git LFS pointer errors.
  - Built-local mobile browser check at 390px passed: dashboard grid, hero, comparable cards, and summary grid stack to one column; ladder remains horizontally scrollable.
  - The only 404 observed during the local browser check was the pre-existing decorative image path `assets/logos/logos/White-Topo-2-1920.png`; no Research data, dashboard script, ladder, or runtime file failed.
## Hunt Research Compact Decision Dashboard Refinement
- Timestamp (UTC): 2026-05-29T16:18:00Z
- Implementation commit: 5b9277db
- Files changed:
  - `assets/js/research-outlook-dashboard.js`
  - `research.html`
- Layout summary:
  - Refined the Hunt Application Outlook add-on into a compact decision dashboard with a full-width hero strip, explicit decision label, estimated odds, permit count, and recommendation sentence.
  - Kept the dashboard inserted immediately before `#pointLadderAccordion`, after the existing Research summary/recommendation area.
  - Kept the point ladder full-width below the dashboard.
  - Converted comparable hunts to a compact 3-row table with Hunt, Odds / Status, Quality Signal, and Why similar columns.
  - Kept source/freshness/model details collapsed by default inside `.uoga-source-details`.
- Dashboard sections implemented:
  - Hero strip: hunt code/name, residency, points, draw pool, decision label, estimated odds, permits, recommendation.
  - Application Read: odds, point status, guaranteed line, trend, permits.
  - Hunt Quality: harvest success, average days hunted, average harvest age, current 3-year age average, percent 5+ if available.
  - State Objective / Management Read: objective type/range/status, Management Plan Context badge, benchmark-only note.
  - Source / freshness / model details: engine mode, data version, model version, rule version, selected hunt, source file/page/table, and loaded source paths.
- Data/source rules preserved:
  - Did not modify `DATABASE.csv`, engine files, model formulas, draw/harvest/age truth files, point-ladder math, permit/allotment truth, runtime CSVs, or Cloudflare source config.
  - Decision labels are display-only and are not written back to data files.
  - Missing or zero `average_harvest_age` renders as `No verified age data`; average days hunted remains separate.
- Validation:
  - `node --check assets/js/research-outlook-dashboard.js` passed.
  - `node --check hunt-research.js` passed.
  - `npm.cmd run build` passed. Existing optional build notices remain: `staging-audit.html`, `data/hunt_boundaries_finalized_2026.geojson`, and oversized `processed_data/composite_hunt_unit_mapping_2026.geojson` skipped for Pages.
  - Verified `pages-dist/research.html` includes `research-outlook-dashboard` with cache token `outlook-dashboard-grid-2`.
  - Verified `pages-dist/assets/js/research-outlook-dashboard.js` exists.
  - Built-local browser check for `research.html?hunt_code=EB3024&draw_pool=standard&residency=resident&points=30&v=dashboardgrid2` passed: hero uses four desktop columns, dashboard body uses three desktop columns, comparable table has 3 rows, source details are collapsed, dashboard appears above the ladder, and no Git LFS pointer errors were logged.
  - Built-local mobile check at 390px passed: dashboard width stays within viewport, hero/body stack to one column, comparable table scrolls inside its own wrapper, and ladder remains horizontally scrollable.
- Known remaining issue:
  - Local browser check still reports the pre-existing decorative image 404 at `assets/logos/logos/White-Topo-2-1920.png`; no Research data, dashboard script, ladder, or runtime file failed.

## Hunt Research Premium Ladder And Readability Polish
- Timestamp (UTC): 2026-05-29T16:21:16Z
- Implementation commit: pending at log-write time; final commit hash recorded in Codex handoff.
- Files changed:
  - `research.html`
  - `hunt-research.js`
  - `assets/js/research-outlook-dashboard.js`
  - `style.css`
- Visual/layout improvements:
  - Replaced the broken decorative topo background with the local `assets/backgrounds/White Topo 20.jpg` texture plus subtle outdoor-toned gradients.
  - Added a restrained CSS mountain/tree accent to the Research hero area.
  - Increased label contrast from pale tan/orange to darker brown/orange values for readability on cream cards.
  - Swapped the display font variable to a cleaner sans display stack to remove the curly/decorative feel and keep text aligned in normal lines.
  - Refined Outlook dashboard cards to use parchment/cream backgrounds, stronger brown labels, and subtle professional shadows.
- Ladder header/display changes:
  - Opened the point ladder by default and expanded the ladder scroll area from a small 360px window to `min(72vh, 760px)` so hunters see more ladder rows before inner scrolling.
  - Bonus-style ladder headers now read `2025 Draw Results`, `2026 Max Point Draw`, `2026 Random Draw`, and `Notes`; max/random headers show `50% of tags` subtext.
  - Ladder cells with no useful display value now render blank instead of repeating `Not available`, including above-line random cells and below-line max-point cells.
  - Kept these as display-only changes; no point ladder math or prediction formulas were changed.
- Notes column changes:
  - Replaced repeated low-value `GREEN`/`YELLOW`/`RED` notes with targeted notes only for the selected user row, draw line, and meaningful special conditions.
  - Selected row notes now prioritize hunter-useful context such as `Harvest Snapshot`, `Catch the Train`, and `2026 Permits: Res / NonRes / Total` when those fields are available.
  - Empty notes rows now stay visually quiet instead of printing filler text.
- Signal light improvements:
  - Upgraded draw/trend signal lights with larger glossy indicators, active-state glow, and accessible text labels.
  - Added `Long shot / low chance`, `On the line / watch closely`, and `In reach / strong position` labels next to the draw-light strip.
  - Added a distinct `Your Point Position` rung marker with a glowing blue dot/chip and kept draw-line marking separate in orange/brown.
- Query-selection fix:
  - The Research page now lets URL `residency` and `points` parameters win over stored defaults so the visitor's rung marker lands on the requested point level, e.g. `points=30`.
  - This is input/display plumbing only; draw routing and model math were not changed.
- Validation:
  - `node --check assets/js/research-outlook-dashboard.js` passed.
  - `node --check hunt-research.js` passed.
  - `node --check app.js` passed.
  - `npm.cmd run build` passed. Existing optional build notices remain: `staging-audit.html`, `data/hunt_boundaries_finalized_2026.geojson`, and oversized `processed_data/composite_hunt_unit_mapping_2026.geojson` skipped for Pages.
  - Verified `pages-dist/research.html` includes `research-outlook-dashboard`.
  - Verified `pages-dist/assets/js/research-outlook-dashboard.js` exists.
  - Local HTTP check for `research.html?hunt_code=EB3024&draw_pool=standard&residency=resident&points=30&v=ladderpolish1` returned HTTP 200 and confirmed dashboard script, selected outlook label, and open ladder markup are present.
  - Headless Chrome DOM check confirmed: one user row, user row points = 30, `Your Point Position` marker rendered, dashboard inserted before ladder, zero exact `Not available` ladder table cells, bonus header `50% of tags` subtext present, and source details collapsed by default.
- Data/source rules preserved:
  - Did not modify `DATABASE.csv`, engine files, model formulas, draw/harvest/age truth files, permit/allotment truth, point-ladder math, Cloudflare/R2 runtime files, or source data files.
  - Build-generated library/data side-effect diffs were reverted and not included in the final change set.

## Active Data Feed Audit, Sync Map, And Engine Readiness Report
- Timestamp (UTC): 2026-05-29T16:53:23Z
- Implementation commit: pending at log-write time; final commit hash recorded in Codex final report.
- Files created:
  - `scripts/audit-active-data-feeds.js`
  - `processed_data/audits/active_data_feed_inventory.csv`
  - `processed_data/audits/active_data_feed_inventory.json`
  - `processed_data/audits/active_data_feed_sync_matrix.csv`
  - `processed_data/audits/active_data_feed_sync_matrix.json`
  - `processed_data/audits/engine_readiness_report.json`
  - `processed_data/audits/engine_readiness_report.md`
  - `processed_data/audits/data_holes_and_inconsistencies.csv`
  - `processed_data/audits/year_to_year_hunt_change_report.csv`
  - `processed_data/audits/year_to_year_hunt_change_report.json`
  - `processed_data/audits/runtime_public_delivery_report.json`
- Audit row counts:
  - Inventory files: 7,641.
  - Sync edges: 10.
  - Data holes/inconsistency flags: 120.
  - Year-to-year hunt-change flags: 2,562.
  - Runtime source entries tested: 15 total; 10 browser-ready Cloudflare HTTP sources passed.
- Major data holes:
  - 103 current-feed hunt-code/name conflicts for review/crosswalk cleanup.
  - 11 large public runtime files that need Cloudflare/R2 preference or Pages exclusion.
  - 6 management objective rows lack observed comparison values and should remain benchmark-only until mapped.
- Critical feed blockers:
  - `data/outfitters-public.json` currently has 0 public rows, so outfitter verification/matching is blocked.
  - State management objective context is present but sparse: 6 rows, 5 matching current hunt codes, 1 unmatched; observed comparison values are missing on several rows.
  - Predictive, harvest, age, and management feeds are usable but show partial current-hunt coverage in the sync matrix.
- Engines ready/partial/blocked:
  - READY: Hunt Builder selection/filter/map, Hunt Research core summary, Point ladder, Predictive draw odds, Comparable hunts, Harvest quality, Age quality, Public library.
  - NEEDS_SOURCE_SYNC: State management objective.
  - BLOCKED: Outfitter matching.
  - PARTIAL/PLACEHOLDER_ONLY: none.
- Runtime/public delivery findings:
  - Hunt Research source groups are Cloudflare-first in `config.js`.
  - Cloudflare/R2 runtime CSVs returned HTTP 200, non-LFS CSV/JSON-like content for engine, ladder, master, and reference feeds.
  - Local relative fallback entries are recorded as local/non-HTTP sources in the audit and were not treated as Cloudflare delivery failures.
- Recommended next phase:
  - Reconcile the 103 hunt-code/name conflicts and review the 60 predictive-only hunt codes that do not match the current reference universe.
  - Expand management objective mapping with observed comparison fields before treating it as more than benchmark context.
  - Add reviewed outfitter coverage/boundary links before enabling outfitter matching.
- Validation:
  - `node --check scripts/audit-active-data-feeds.js` passed.
  - `node scripts/audit-active-data-feeds.js` passed and regenerated all requested audit outputs.
  - `npm.cmd run build` passed. Existing optional build notices remain: `staging-audit.html`, `data/hunt_boundaries_finalized_2026.geojson`, and oversized `processed_data/composite_hunt_unit_mapping_2026.geojson` skipped for Pages.
  - Build-generated library/pages-dist side-effect diffs were reverted and not included in the final change set.
- Data/source rules preserved:
  - Did not modify `DATABASE.csv`, source truth files, runtime CSVs, engine materializers, prediction formulas, permit/allotment fields, or `p_draw`.

## Management Plan Comparison Layer And Hunt Classification Engine
- Timestamp (UTC): 2026-05-29T17:03:16Z
- Implementation commit: pending at log-write time; final commit hash recorded in Codex final report.
- Files created:
  - `scripts/build-hunt-research-classification-layer.js`
  - `processed_data/research_page/hunt_application_outlook.json`
  - `processed_data/research_page/hunt_application_outlook.csv`
  - `processed_data/research_page/hunt_classification_tags.csv`
  - `processed_data/research_page/hunt_classification_tags.json`
  - `processed_data/research_page/sleeper_hunts_report.csv`
  - `processed_data/research_page/sleeper_hunts_report.json`
  - `processed_data/research_page/new_hunts_report.csv`
  - `processed_data/research_page/new_hunts_report.json`
  - `processed_data/research_page/demographic_hunt_recommendations.json`
  - `processed_data/audits/hunt_classification_layer_audit.json`
- Output row counts:
  - Hunt application outlook rows: 2,898.
  - Hunt classification tag rows: 24,924.
  - Sleeper hunt rows: 344.
  - New hunt rows: 184.
  - Demographic/persona groups: 10.
- Tag counts summary:
  - `TROPHY_DREAMER`: 2,460.
  - `LONG_SHOT`: 2,175.
  - `NO_VERIFIED_AGE_DATA`: 1,984.
  - `FREEZER_FILLER`: 1,890.
  - `POINT_SAVER`: 1,881.
  - `HIGH_HARVEST_SUCCESS`: 1,586.
  - `HIGH_PRESSURE_HUNT`: 1,410.
  - `STATUS_OR_AVAILABILITY_ONLY`: 1,186.
  - `VERIFIED_AGE_DATA`: 914.
  - `WITHIN_REACH`: 209.
  - `OBJECTIVE_KNOWN_NO_OBSERVED_DATA`: 6.
  - `QUALITY_ABOVE_OBJECTIVE`: 4.
- Demographic recommendation counts:
  - `YOUTH_OPPORTUNITY`: 16.
  - `BEGINNER_ANTLERLESS`: 484.
  - `FREEZER_FILLER`: 1,890.
  - `ELDER_FRIENDLY`: 1,164.
  - `HARD_DRIVER`: 646.
  - `TROPHY_DREAMER`: 2,460.
  - `POINT_SAVER`: 1,881.
  - `OPPORTUNIST`: 344.
  - `GROUP_FRIENDLY`: 556.
  - `EXTEND_THE_SEASON`: 292.
- Management objective behavior:
  - Elk plan objective rows compare verified observed/current age context to objective min/max where available.
  - Mule deer plan objective rows stay `OBJECTIVE_KNOWN_NO_OBSERVED_DATA` unless verified buck:doe or percent age-5+ comparison data exists.
  - Management objective context is display/benchmark only and does not change draw probability, p_draw, permits, quotas, or observed age fields.
- Validation:
  - `node --check scripts/build-hunt-research-classification-layer.js` passed.
  - `node scripts/build-hunt-research-classification-layer.js` passed and regenerated all requested outputs.
  - Output validation reported `output_average_harvest_age_zero_count = 0`.
  - Output validation reported `average_days_hunted_mapped_as_age_suspect_count = 0`.
  - Four rows have the same numeric days/verified-age value by coincidence; they are sourced from `harvest_age_features_by_hunt_code_latest.csv` and tracked separately as `average_days_hunted_same_as_verified_age_count = 4`.
  - Protected file hashes remained unchanged for `DATABASE.csv`, `draw_reality_engine_predictive_v2.csv`, and `point_ladder_view.csv`.
  - `git diff` confirmed no changes to protected database, predictive draw, or ladder feeds.
- Data/source rules preserved:
  - Did not modify `DATABASE.csv`, raw/source truth, prediction formulas, point-ladder math, permit/allotment truth, p_draw values, or runtime source feeds.

## Site Speed, Public Library, And Outfitter Data Readiness Audit
- Timestamp (UTC): 2026-05-29T17:10:01Z
- Implementation commit: pending at log-write time; final commit hash recorded in Codex final report.
- Files created:
  - `scripts/audit-site-performance-library-outfitters.js`
  - `processed_data/audits/site_performance_asset_report.csv`
  - `processed_data/audits/site_performance_asset_report.json`
  - `processed_data/audits/public_library_curation_report.csv`
  - `processed_data/audits/public_library_curation_report.json`
  - `processed_data/audits/outfitter_data_readiness_report.json`
  - `processed_data/audits/outfitter_data_readiness_report.md`
  - `processed_data/audits/page_runtime_dependency_report.json`
- Performance audit summary:
  - Assets inventoried: 4,492.
  - Large assets flagged: 38.
  - Cloudflare/R2 candidates: 22.
  - Files flagged as should-not-publish directly: 538.
- Largest files observed:
  - 84.0 MiB: `data/hunt_boundaries_arcgis.json`.
  - 83.1 MiB: `data/utah/foundation_bundle_2026/utah_boundaries_canonical_2026.geojson`.
  - 83.1 MiB: `data/utah/official_downloads_2026/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson`.
  - 70.0 MiB: `data/utah/foundation_bundle_2026/utah_hunt_foundation_2026.sqlite`.
  - 21.5 MiB: `data/utah/foundation_bundle_2026/utah_boundaries_canonical_2026.kml`.
  - 13.4 MiB: `processed_data/hard_data_exports/source_pdfs/2025/pdf/harvest_report/24_bg_HARVEST_report.pdf` and published copy.
  - 12.1 MiB: 2025/2026 big-game draw-result PDFs and published copies.
- Page dependency findings:
  - `index.html` is the heavy path because it can depend on map/boundary data; composite/statewide boundary files should stay R2/Workers/lite/split, and outfitter marker geocoding should wait for hunt selection.
  - `research.html` should continue Cloudflare-first runtime CSV loading; management objective/comparable hunt panels should remain lazy/secondary after core summary, and source details should stay collapsed.
  - `hard-copy.html` already lazy-loads PDF.js/page-flip only when a PDF is opened; next improvement is splitting the library manifest by folder/category.
  - `verify.html` should use public outfitter data only after records are public-ready and should lazy-load public cards/search after the shell renders.
- Public library curation summary:
  - Library rows audited: 1,127.
  - Visible allowlist entries: 67.
  - Status counts included `public_useful`: 808, `internal_only`: 326, `duplicate`: 335, `outdated`: 5, `broken_link`: 4, and `public_but_categorize_better`: 1.
  - Cleanup recommendations: keep raw model/runtime/audit/intermediate files hidden; keep one canonical public entry for duplicates; mark older guidebooks/reports as historical; move oversized/public-heavy PDFs to R2 or provide smaller viewer/summary artifacts.
- Outfitter readiness summary:
  - `data/outfitters-public.json`: 0 rows.
  - `data/outfitters.json`: 11 internal rows.
  - Readiness status: 11 `HOLD_INTERNAL_ONLY`.
  - Risk flags: 11 `not_in_public_feed`, 11 `normalization_only`, 11 `no_review_date`, and 1 `no_unit_coverage`.
  - Next requirement before public launch: add `reviewed_at`, `source_evidence_count`, explicit `service_types`, public contact completeness, and hunt-code/boundary-reviewed unit coverage.
- Validation:
  - `node --check scripts/audit-site-performance-library-outfitters.js` passed.
  - `node scripts/audit-site-performance-library-outfitters.js` passed and generated all requested outputs.
  - `npm.cmd run build` passed. Existing optional build notices remain: `staging-audit.html`, `data/hunt_boundaries_finalized_2026.geojson`, and oversized `processed_data/composite_hunt_unit_mapping_2026.geojson` skipped for Pages.
  - Build-generated library/pages-dist side-effect diffs were reverted and not included in the final change set.
- Data/source rules preserved:
  - Did not modify prediction math, source truth, `DATABASE.csv`, runtime feed values, outfitter records, or public library files.
  - No public files were deleted or hidden in this task; reports only document recommendations.

## Website Close Inspection And Mobile Layout Fixes
- Timestamp (UTC): 2026-05-29T19:16:53Z
- Implementation commit: pending at log-write time; final commit hash recorded in Codex final report.
- Files changed:
  - `header-layout.js`
  - `index.html`
  - `research.html`
  - `coverage.html`
  - `hard-data.html`
  - `verify.html`
- Inspection scope:
  - Reviewed Builder, Hunt Research, Verify/Outfitters, Coverage, Hard Data, and Research Library views on desktop and mobile-sized screens.
  - Confirmed Hunt Research no longer exposes raw runtime source URL text on the page.
  - Confirmed Research Library folder selections and PDF viewer render as fixed overlays on the primary screen instead of appearing below the fold.
- Fixes made:
  - Reworked the shared injected header layout on small screens so the sticky header, nav pills, map-mode control, instructions button, and backpack control stay inside the viewport.
  - Added mobile overflow protection and one-column grid constraints to Hunt Research cards, summary grids, chips, dashboard panels, and ladder containers.
  - Kept the point ladder horizontally scrollable while preventing the full page from widening beyond the phone viewport.
  - Bumped `header-layout.js` cache tokens on pages that use the shared header so the mobile fixes load consistently.
- Validation:
  - `node --check header-layout.js` passed.
  - `node --check assets/js/research-outlook-dashboard.js` passed.
  - `node --check assets/js/hard-copy-public-library.js` passed.
  - `node --check hunt-research.js` passed.
  - `node --check app.js` passed.
  - `npm.cmd run build` passed after stopping the local preview server that had locked `pages-dist`.
  - Cross-page smoke audit confirmed desktop and mobile body widths match viewport widths for Builder, Hunt Research, Verify, Coverage, Hard Data, and Research Library.
  - Mobile Hunt Research check confirmed `bodyWidth = viewport = 390`, raw source text hidden, and table content constrained to the card scroll area.
- Cleanup:
  - Build-generated library manifests and temporary UI inspection screenshots/reports were removed or restored so this change set stays UI-only.
  - Did not modify `DATABASE.csv`, prediction formulas, runtime CSV data, draw truth, harvest truth, age truth, point-ladder math, or permit/allotment truth.

## Research Contract, Ladder Polish, And Mobile QA Guardrail
- Timestamp (UTC): 2026-05-29T19:52:08Z
- Implementation commit observed during task: `d55689e58fd3a7b9dce1b76405b30c69931362b4`.
- Cleanup/documentation commit: pending at log-write time; final commit hash recorded in Codex final report.
- Files changed:
  - `AGENTS.md`
  - `assets/js/research-outlook-dashboard.js`
  - `hunt-research.js`
  - `scripts/build-hunt-research-classification-layer.js`
  - `scripts/build-pages-dist.js`
  - `style.css`
  - `index.html`
  - `research.html`
  - `coverage.html`
  - `hard-copy.html`
  - `hard-data.html`
  - `verify.html`
  - `processed_data/research_page/hunt_application_outlook.json`
  - `processed_data/research_page/hunt_application_outlook.csv`
  - `processed_data/research_page/demographic_hunt_recommendations.json`
  - `processed_data/audits/hunt_classification_layer_audit.json`
- AGENTS.md update:
  - Added a standing mandatory mobile QA final pass for every website/UI/public-output/page-build task.
  - Mobile QA now requires no horizontal overflow, usable sticky/fixed navigation, readable contrast, tappable controls, accessible tables/maps/PDF overlays, and desktop regression checks.
- Research contract:
  - Regenerated `hunt_application_outlook.json` and CSV as the clean display contract.
  - Added display-safe fields including draw pool, hunt type, boundary ID, resident/nonresident/total permits, management note, model/rule version, availability status, and harvest/age source fields.
  - Output counts: 2,898 outlook rows, 24,924 tag rows, 344 sleeper rows, 184 new-hunt rows.
  - Validation counts: `output_average_harvest_age_zero_count = 0`, `average_days_hunted_mapped_as_age_suspect_count = 0`, `blocked_rows = 0`.
- Research dashboard:
  - Dashboard now loads `processed_data/research_page/hunt_application_outlook.json` Cloudflare-first, with local fallback.
  - Added a short runtime fetch timeout so missing R2 copies do not leave the dashboard stuck on loading.
  - Added a resilient snapshot retry so the dashboard renders after core Research rows are ready even when the core event arrives late.
  - Dashboard still uses selected point-row odds where available, while using the contract for decision label, recommendation, permits, quality, badges, and management context.
  - Source/freshness/model details remain collapsed by default and raw runtime source URLs remain hidden.
- Ladder polish:
  - Bonus ladder headers now show `2026 Max Point Draw` and `2026 Random Draw` with `50% of Tags`.
  - Irrelevant/low-value cells remain blank instead of repeating `Not available`.
  - Existing `Your Point Position` and `Guaranteed Draw` markers remain visible.
- Site-wide mobile optimization:
  - Added shared mobile guardrails in `style.css` for viewport containment, horizontal nav scrolling, readable/tappable controls, and no hidden overflow.
  - Bumped `style.css`, `hunt-research.js`, and dashboard script cache tokens on public pages.
  - `scripts/build-pages-dist.js` now publishes `processed_data/research_page` so the Research contract is available in built output.
- Validation:
  - `node --check assets/js/research-outlook-dashboard.js` passed.
  - `node --check hunt-research.js` passed.
  - `node --check scripts/build-hunt-research-classification-layer.js` passed.
  - `node --check scripts/build-pages-dist.js` passed.
  - `node scripts/build-hunt-research-classification-layer.js` passed.
  - `npm.cmd run build` passed. Existing optional build notices remain: `staging-audit.html`, `data/hunt_boundaries_finalized_2026.geojson`, and oversized `processed_data/composite_hunt_unit_mapping_2026.geojson` skipped for Pages.
  - `git diff --check` passed.
  - Protected file diff check confirmed no changes to `DATABASE.csv`, `processed_data/point_ladder_view.csv`, or `processed_data/draw_reality_engine_predictive_v2.csv`.
- Browser/mobile QA:
  - Research desktop and mobile confirmed: dashboard above ladder, contract recommendation visible, raw source URLs hidden, source details collapsed, ladder headers correct, no repeated `Not available` ladder cells, user rung marker present.
  - Cross-page desktop/mobile smoke test confirmed no horizontal overflow for Builder, Hunt Research, Research Library, Verify, Coverage, and Hard Data at 390px and 1280px widths.
  - Header/nav position remained sticky or fixed across tested pages.
- Cleanup:
  - A generated commit named `g` included unrelated library/pages-dist build churn and a temporary `.codex-ui-smoke-server.pid` file.
  - A follow-up cleanup commit restores unrelated generated library artifacts to the prior baseline and removes the temporary pid file, without rewriting history.
  - Did not modify prediction formulas, `DATABASE.csv`, draw truth, harvest truth, age truth, permit/allotment truth, p_draw, or point-ladder math.

## Hunt Tables 2026 MASTER XLSX Contract Refactor
- Timestamp (UTC): 2026-05-29T22:11:00Z
- Scope:
  - Refactored the single-workbook generator:
    - `scripts/regenerate-hunt-tables-2026-clean-xlsx.py`
  - Regenerated:
    - `processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/MASTER.xlsx`
  - Added validation artifact:
    - `processed_data/audits/hunt_tables_2026_master_xlsx_validation.json`
- Output contract implemented:
  - Exact 15-column order:
    - `HUNT TYPE`
    - `SPECIES`
    - `SEX TYPE`
    - `WEAPON`
    - `HUNT CLASS`
    - `SEASON`
    - `HUNT NAME`
    - `HUNT CODE`
    - `2026 PERMITS RES`
    - `2026 PERMITS NR`
    - `2026 PERMITS TOTAL`
    - `HARVEST YEAR`
    - `2026 HARVEST SUCCESS`
    - `2026 HARVEST AGE`
    - `2026 HARVEST DAYS`
  - Header styling enforced:
    - all caps
    - Arial 10
    - wrap text enabled
    - centered
    - enlarged header row for multiline text
- Source/data rules implemented:
  - Workbook now builds directly from `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`.
  - Harvest fields now join from `processed_data/harvest_quality_features_all_years_by_hunt_code.csv` filtered to `model_target_year = 2026`.
  - Permit values are sourced only from published permit columns in priority order:
    - `permits_2026_draw_*`
    - `permits_2026_*`
    - `permit_allotment_2026_*`
  - No permit calculations or inferred splits were added.
  - If only total permit data exists, resident/nonresident cells remain blank.
  - `NOTES` was removed entirely from the output.
  - File splitting was intentionally not implemented; only the single `MASTER.xlsx` was regenerated.
- Classification results:
  - Hunt type counts:
    - `GENERAL`: 311
    - `HARVEST OBJECTIVE`: 1
    - `L.E.`: 729
    - `O.I.L.`: 82
    - `OTC`: 290
    - `P.L.E.`: 15
    - `PURSUIT`: 11
    - `SPORTSMAN`: 10
  - Hunt class counts:
    - `CONSERVATION`: 28
    - `CWMU`: 319
    - `EXPO`: 4
    - `GENERAL BULL`: 5
    - `PRIVATE`: 281
    - `SPIKE`: 3
    - `YOUTH`: 7
- Source nuance resolved:
  - `DATABASE.csv` had blank `season` cells for `BR1000` and `BR1001`.
  - The generator filled those two season values from local reviewed note files:
    - `pipeline/RAW/hunt_unit_database/2026/notes/DATABASE/BR1000-notes.md`
    - `pipeline/RAW/hunt_unit_database/2026/notes/DATABASE/BR1001-notes.md`
  - Validation then confirmed zero blank season rows in the generated workbook.
- Validation:
  - `python -m py_compile scripts/regenerate-hunt-tables-2026-clean-xlsx.py` passed.
  - `python scripts/regenerate-hunt-tables-2026-clean-xlsx.py` passed.
  - Workbook validation confirmed:
    - exact header order match
    - duplicate hunt code count `0`
    - row count `1449`
    - missing season count `0`
    - harvest-joined rows `1122`
    - permit total-only rows `235`
    - permit split rows `938`

## Hunt Tables 2026 Regeneration (DATABASE.csv Source, Local Harvest Fallback)
- Timestamp (local): 2026-05-29T21:20:38-06:00
- Assigned step:
  - Regenerate 2026 MASTER hunt table using canonical source:
    - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Change made:
  - Updated `scripts/regenerate-hunt-tables-2026-clean-xlsx.py` to resolve harvest input from the first available file in this order:
    - `processed_data/harvest_quality_features_all_years_by_hunt_code.csv`
    - `pipeline/RAW/hunt_unit_database/2026/csv/harvest_quality_features_by_hunt_code_2025_for_2026.csv`
  - Guardrail behavior when harvest files are absent:
    - script now continues with permit/data rows instead of failing hard.
- Regenerated outputs:
  - `processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/MASTER.xlsx`
  - `processed_data/audits/hunt_tables_2026_master_xlsx_validation.json`
- Validation:
  - `python -m py_compile scripts/regenerate-hunt-tables-2026-clean-xlsx.py` passed.
  - `python scripts/regenerate-hunt-tables-2026-clean-xlsx.py` passed.
  - Run summary:
    - rows: `1449`
    - harvest joins: `1115`
    - season note fallback rows: `2`
    - permit total-only rows: `235`
  - Audit JSON confirms:
    - `headers_match = true`
    - `duplicate_hunt_code_count = 0`
    - `missing_season_count = 0`

## DATABASE 2026 Truth Sync To Permit Allotment Columns
- Timestamp (UTC): 2026-05-30T03:55:04Z
- Assigned step:
  - Treat populated `permits_2026_*` values as truth and fill/update `permit_allotment_2026_*` where blank or different.
- File modified:
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
- Backup created:
  - `processed_data/backups/DATABASE_before_allotment_truth_sync_20260530_035504.csv`
- Audit report:
  - `processed_data/audits/database_2026_allotment_truth_sync_report.json`
- Applied updates:
  - Synced from truth fields:
    - `permits_2026_res -> permit_allotment_2026_res`
    - `permits_2026_nr -> permit_allotment_2026_nr`
    - `permits_2026_total -> permit_allotment_2026_total`
  - Rows changed: `29`
  - Cell changes: `29`
- Validation:
  - Post-sync mismatch counts:
    - `permits_2026_res` vs `permit_allotment_2026_res`: `0`
    - `permits_2026_nr` vs `permit_allotment_2026_nr`: `0`
    - `permits_2026_total` vs `permit_allotment_2026_total`: `0`

## Deer Buck Draw-Class Automation Script + Expo/Conservation Pass
- Timestamp (UTC): 2026-05-30T04:45:25Z
- Added reusable script:
  - `scripts/apply-deer-buck-drawclass-rules.py`
- Script rules and precedence:
  - `sportsman` -> `hunt_type=L.E.`, `hunt_class=sportsmens`, `2026 permits total=1`
  - `conservation` -> `hunt_type=conservation`
  - `expo` -> `hunt_class=expo` and `hunt_type=L.E.` unless conservation rule applies
  - `private` -> `hunt_type=L.E.`, `hunt_class=private only`
  - Precedence: `sportsman > conservation > expo > private`
- Validation:
  - `python -m py_compile scripts/apply-deer-buck-drawclass-rules.py` passed.
  - Dry run:
    - `python scripts/apply-deer-buck-drawclass-rules.py --csv "C:/Users/tyler/Desktop/species truth data/2026 deer buck db.csv"`
    - `rows_changed: 1` (DB0009 expo class fill)
  - Write run:
    - `python scripts/apply-deer-buck-drawclass-rules.py --csv "C:/Users/tyler/Desktop/species truth data/2026 deer buck db.csv" --write`
    - `rows_changed: 1`
    - backup: `C:/Users/tyler/Desktop/species truth data/2026 deer buck db.backup_drawclass_rules_20260530_044525.csv`
- Outcome:
  - `DB0009` now carries `hunt_type=conservation` and `hunt_class=expo` per requested behavior.

## Research Step 1 Runtime Contract Audit + Step 2 Dashboard/Ladder Polish
- Timestamp (UTC): 2026-05-30T09:42:37Z
- Assigned sequence:
  - `1) Data feed audit / runtime contract`
  - `2) Research page dashboard + ladder polish`
- Files changed:
  - `scripts/build-hunt-research-classification-layer.js`
  - `processed_data/research_page/hunt_application_outlook.json` (regenerated)
  - `processed_data/research_page/hunt_application_outlook.csv` (regenerated)
  - `processed_data/audits/hunt_classification_layer_audit.json` (regenerated)
  - `assets/js/research-outlook-dashboard.js`
  - `hunt-research.js`
  - `research.html`
- Step 1 contract fixes:
  - Added resilient source-path resolution in the contract builder so it now auto-uses available local truth-source files when preferred processed_data paths are missing.
  - Added `DATABASE.csv` enrichment overlay by `hunt_code` to backfill canonical hunt/species/weapon/hunt_type/hunt_class/boundary fields into output rows.
  - Preserved residency row structure by seeding from ladder rows first, then enriching from canonical master/database rows.
  - Added harvest/age fallback handling from available truth packages while preserving age guardrails.
  - Added audit `source_paths` output so every run records exactly which input files were used.
- Step 1 output/validation:
  - Contract build run: `node scripts/build-hunt-research-classification-layer.js`
  - Result:
    - `outlook_rows: 2898`
    - `tag_rows: 21426`
    - `sleeper_hunt_rows: 330`
    - `blocked_rows: 0`
    - `output_average_harvest_age_zero_count: 0`
  - Protected hashes unchanged:
    - `DATABASE.csv`: unchanged
    - ladder file: unchanged
    - predictive file hash: unchanged
- Step 2 UX polish:
  - Updated Research handoff wording so the page reads as Hunt Builder -> Research flow instead of a separate standalone start-over form.
  - Refined empty-state dashboard text to direct users to Hunt Builder first without debug-style language.
  - Updated ladder header casing to the cleaned display form (`2026 Max Point Draw`).
  - Bumped Research script cache tokens in `research.html`.
- Validation:
  - `node --check scripts/build-hunt-research-classification-layer.js` passed.
  - `node --check hunt-research.js` passed.
  - `node --check assets/js/research-outlook-dashboard.js` passed.
  - `npm.cmd run build` passed.
  - Build produced existing optional-missing notices for runtime artifacts not currently present locally; no protected truth files were modified.

## Research Step 3 Management Benchmark Layer + Step 4 Persona/Sleeper Surface + Step 5 Outfitter Page Public Directory
- Timestamp (UTC): 2026-05-30T10:13:38Z
- Assigned sequence continued without pause:
  - `3) Management objective comparison layer`
  - `4) Sleeper / demographic hunt tags surface`
  - `5) Outfitter page rebuild (public records + CTA)`
- Files changed:
  - `scripts/build-hunt-research-classification-layer.js`
  - `assets/js/research-outlook-dashboard.js`
  - `verify.html`
- Step 3 implementation:
  - Added synthetic management-context fallback generation when `processed_data/management_context/hunt_management_objective_context.json` is missing.
  - Synthetic context is keyed by `hunt_code` from `DATABASE.csv` and uses plan-context objectives only (elk LE age band; mule deer general/LE/premium objective context).
  - Added management direction labels:
    - `Above Objective`
    - `Meeting Objective`
    - `Below Objective`
    - `Objective Known / Observed Evidence Limited`
  - Added permit-direction watch messaging with `>20%` management-review threshold language (context-only).
  - Wrote management context artifact:
    - `processed_data/management_context/hunt_management_objective_context.json`
  - Added audit trace fields:
    - `management_context_rows_effective`
    - `management_context_source`
    - `management_context_output_rows`
- Step 4 implementation:
  - Surfaced persona/sleeper signals in the Hunt Research dashboard as visible decision content.
  - Added `Hunter-Fit Signals` section using:
    - `persona_tags`
    - `sleeper_score`
    - `sleeper_reasons`
  - Kept explicit language that these signals do not override draw odds.
- Step 5 implementation:
  - Rebuilt Verify page with a public outfitter directory card grid.
  - Added runtime loading flow:
    - `data/outfitters-public.json` first
    - fallback to vetted rows from `data/outfitters.json` when public feed is empty
  - Added per-card display:
    - verification label
    - species served
    - units served
    - service badges
    - reviewed date
    - permit context note
    - website/call/email action buttons when present
- Validation:
  - `node --check scripts/build-hunt-research-classification-layer.js` passed.
  - `node --check assets/js/research-outlook-dashboard.js` passed.
  - `node scripts/build-hunt-research-classification-layer.js` passed.
  - `npm.cmd run build` passed.
  - Protected-file hash check remained true for:
    - `DATABASE.csv`
    - ladder source
    - predictive source

## Step 6 Public Library Curation Cleanup + Step 7 Library Speed Optimization
- Timestamp (UTC): 2026-05-30T10:46:00Z
- Files changed:
  - `assets/js/hard-copy-public-library.js`
  - `assets/css/hard-copy-public-library.css`
  - `hard-copy.html`
  - `public/hard-copy/data/documents.json`
- Step 6 curation cleanup:
  - Added curated data manifest:
    - `public/hard-copy/data/documents.json`
  - Library now checks this curated JSON feed first before manifest fallbacks.
  - Added resilient manifest source fallbacks and support for object-style manifest payloads (`input_file_status` lists).
  - Added curated fixed public document entries under `public/hard-copy/DISPLAY DATA/*` so the library can render trusted references even when allowlist files are absent.
  - Added local file availability filtering via `HEAD`/fallback `GET` checks to suppress broken local links before rendering cards.
  - Kept runtime-denylist protection in place so model/runtime source files are not exposed as library documents.
- Step 7 speed optimization:
  - Removed external PDF flipbook runtime dependency path from the library viewer flow.
  - Replaced PDF render/flip pipeline with native in-browser iframe preview modal.
  - Disabled obsolete prev/next controls for the lightweight preview mode.
  - Added lightweight inline-frame styling and disabled-button states in library CSS.
  - Bumped hard-copy asset cache tokens in `hard-copy.html`.
- Validation:
  - `node --check assets/js/hard-copy-public-library.js` passed.
  - `npm.cmd run build` passed.
  - Build still reports existing optional-missing runtime artifacts; these are unchanged baseline warnings.
## 2026-06-01T08:35:00-06:00 - Live Verification Sweep (Builder + Hard-Copy + Research Context + MASTER Report)

- Requested verification scope:
  1. Builder loads without console/runtime 404s.
  2. `hard-copy.html` still works after runtime cleanup.
  3. Research page resolves selected hunt context correctly.
  4. MASTER reconciliation report states DATABASE truth and MASTER recipient/export role.
  5. Record exact verification steps + final live status.

- Exact live verification steps run:
  - Builder runtime pass:
    - Opened `https://huntbuilder.uoga.org/` with Playwright.
    - Captured all network responses and filtered 4xx/5xx for `huntbuilder.uoga.org`.
    - Result: `MISS_COUNT=0` (no 404s on Builder load).
  - Hard-copy runtime + render pass:
    - Opened `https://huntbuilder.uoga.org/hard-copy.html`.
    - Captured 4xx/5xx network responses.
    - Checked render state:
      - `#uogaFolderWall` children count = `8`
      - results title = `UTAH DWR RULES & REGULATIONS`
      - results count label = `3 files`
      - content nodes present in results panel
    - Result: page functional and rendering cards/folders.
  - Research context pass:
    - Opened:
      - `https://huntbuilder.uoga.org/research.html?hunt_code=EA1180&residency=Resident&points=12&draw_pool=standard`
    - Verified UI context fields:
      - `huntCodeInput = EA1180`
      - `residencySelect = Resident`
      - `drawPoolSelect = standard`
      - `pointsInput = 12`
      - `selectedHuntCodeRead = EA1180`
      - `detailTitle = EA1180 | La Sal (Conservation)`
    - Verified persisted context keys:
      - `selected_hunt_code = EA1180`
      - `selected_hunt_research_residency = Resident`
      - `selected_hunt_research_points = 12`
      - `selected_hunt_research_draw_pool = standard`
    - Result: selected-hunt context resolution PASS.
  - MASTER reconciliation report integrity pass:
    - Read:
      - `generated/audits/master_reconciliation_2026/master_database_2026_reconciliation_report.json`
    - Confirmed fields:
      - `truth_rule = DATABASE.csv authoritative; permit truth uses permit_allotment_2026_* with fallback to permits_2026_*.`
      - `database_path = pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
      - `master_path = processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/MASTER.xlsx`
    - Result: truth-source/recipient-export contract PASS.

- Final live status:
  - Builder: PASS for requested 404 condition (`0` runtime 404s on load).
  - Hard-copy: functional PASS (folders + cards render); still logs optional fallback-path 404s for non-required manifest fallback files.
  - Research: PASS (query + persisted selected-hunt context correctly resolved).
  - MASTER report contract: PASS (DATABASE truth explicitly declared; MASTER path identified as recipient/export target).

## 2026-06-01T08:58:00-06:00 - Builder Hunt-Unit Mapping Online Fix (LFS Pointer Runtime Guard)

- Issue observed:
  - Selected hunts were not drawing boundaries online.
  - Live boundary endpoints under `processed_data/` were serving Git LFS pointer payloads (about 129-133 bytes), not GeoJSON.

- Root-cause verification:
  - Live checks confirmed:
    - `https://huntbuilder.uoga.org/processed_data/statewide_composite_boundaries_2026.geojson` returned `200` with `size=133`.
    - `https://huntbuilder.uoga.org/processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson` returned `200` with `size=133`.
    - `https://huntbuilder.uoga.org/processed_data/boundaries/DB1001.geojson` returned LFS pointer text (`version https://git-lfs.github.com/spec/v1`).
  - Live non-LFS boundary assets confirmed valid:
    - `https://huntbuilder.uoga.org/data/hunt_boundaries.geojson` returned `200` with full payload (`~4.28 MB`).
    - `https://huntbuilder.uoga.org/data/hunt-boundaries-lite.geojson` returned `200` with full payload (`~4.28 MB`).

- Code changes applied:
  - `config.js`
    - Updated `HUNT_BOUNDARY_SOURCES` ordering to prefer runtime-safe `./data/hunt_boundaries.geojson` and `./data/hunt-boundaries-lite.geojson` before `processed_data` composite files.
  - `app.js`
    - Added fallback feature-collection resolver `getFallbackFeatureCollectionForResolvedBoundary(...)` that reconstructs map features from loaded boundary index by boundary IDs.
    - Updated `applySelectedHuntBoundaryResolution(...)`:
      - after direct per-hunt geojson load failure, fallback now draws from boundary-index features.
    - Updated `getIndependentBoundaryFeatureCollection(...)`:
      - fallback now resolves features from boundary index before attempting direct per-hunt path fetch.
    - Updated `getResolvedBoundaryIdsForHunt(...)`:
      - removed short-circuit that returned no IDs whenever `boundary_geojson_path` existed, allowing matcher/highlight logic to use manifest boundary IDs even when per-hunt files are unavailable online.

- Validation run:
  - `node -e "new Function(fs.readFileSync('app.js','utf8')); new Function(fs.readFileSync('config.js','utf8'))"` -> `syntax-ok`
  - `npm run build` -> PASS
  - Build emitted expected baseline warnings for oversized optional files in `pages-dist`; no build break from map fix.

## 2026-06-01T10:35:00-06:00 - Boundary-ID Geometry Files Hunt-Code Reconciliation

- Request context:
  - Geometry-only boundary files in `processed_data/boundaries` were identified as low-value unless mapped back to hunt codes.
  - Required action: map these files to hunt codes using current in-repo truth links.

- Reconciliation performed:
  - Built a `boundary_id -> hunt_code[]` crosswalk from currently mapped boundary GeoJSON records (`metadata.hunt_code` present).
  - Crosswalk derivation used:
    - `metadata.boundary_id`
    - `metadata.source_boundary_ids`
    - `metadata.member_boundary_ids`
    - feature property boundary IDs where present
  - Applied mapping metadata to every boundary-ID-only geometry file.

- Results:
  - Source mapped files used for crosswalk: `1607`
  - Boundary IDs in derived crosswalk: `501`
  - Geometry-only files updated: `47`
  - Geometry-only files still unmapped: `0`

- Metadata written to each previously geometry-only file:
  - `metadata.boundary_id`
  - `metadata.candidate_boundary_id`
  - `metadata.mapped_hunt_codes`
  - `metadata.candidate_hunt_code`
  - `metadata.hunt_code_mapping_status = MAPPED_FROM_BOUNDARY_ID_CROSSWALK`
  - `metadata.boundary_id_mapping_status = MAPPED`
  - `metadata.mapping_method = boundary_id_crosswalk_from_mapped_geojson`
  - `metadata.hunt_code` only when exactly one unique mapped hunt code exists for that boundary ID.

- Audit artifacts created:
  - `processed_data/audits/boundary_id_to_hunt_code_crosswalk_2026.json`
  - `processed_data/audits/boundary_id_to_hunt_code_crosswalk_2026.csv`

- Validation:
  - `INVALID_JSON = 0` across `processed_data/boundaries/*.geojson`
  - `BOUNDARY_ID_FILES_WITHOUT_LINK = 0` (no numeric-stem boundary file left without hunt linkage metadata)

## 2026-06-01T10:55:00-06:00 - Split Mapping Verification + DATABASE Boundary-ID Sync Audit

- Request context:
  - Verify `processed_data/hunt_research_2026_split` is reconciled/mapped.
  - Then ensure `DATABASE.csv` has `hunt_code -> boundary_id` mapping (add column only if missing).

- Verification results:
  - Split index rows: `1607`
  - Split rows missing `hunt_code`: `0`
  - Split rows missing `boundary_id`: `0`
  - Split detail files (`hunts/*.json`): `1607`
  - Split detail files missing `boundary_id`: `0`
  - Conclusion: split is fully reconciled and mapped for hunt-code boundary mapping coverage.

- DATABASE mapping action:
  - Confirmed `DATABASE.csv` already contains `boundary_id` column.
  - Ran hunt-code boundary sync audit from split index to DATABASE:
    - missing `boundary_id` cells filled: `0`
    - nonblank matches: `1385`
    - nonblank mismatches: `40`
    - DATABASE hunt codes without split mapping: `24`
  - Policy applied:
    - preserve existing nonblank `DATABASE.csv` boundary truth (no overwrite pass applied).
  - Wrote audit report:
    - `processed_data/audits/database_boundary_id_sync_from_split_2026.json`

- Notes:
  - Mismatch set includes split-side synthetic/statewide boundary IDs (for example `SW_*`/`*_2026`) and a few numeric swaps; these require reviewed boundary-truth adjudication before any overwrite policy.

## 2026-06-01T11:10:00-06:00 - Total File Reconciliation + Validation (DATABASE Boundary Truth)

- Assigned step:
  - Perform total reconciliation and validation across:
    - `DATABASE.csv` (truth source)
    - `processed_data/hunt_research_2026_split/*`
    - `processed_data/boundaries/*.geojson` metadata mapping fields

- Reconciliation implementation:
  - Added executable reconciler:
    - `scripts/reconcile_total_boundary_mapping_2026.py`
  - Truth policy:
    - `DATABASE.csv` `hunt_code -> boundary_id` is authoritative.
    - Only boundary mapping fields were updated.
    - Permit/allotment fields were not touched.
  - Outputs:
    - `processed_data/audits/total_boundary_reconciliation_validation_2026.json`
    - `processed_data/audits/total_boundary_reconciliation_changes_2026.csv`

- Reconciliation results:
  - Split index:
    - overlap with DATABASE: `1425`
    - mismatches before: `40`
    - updated: `40`
    - mismatches after: `0`
  - Split detail files:
    - files for DATABASE hunt codes: `1425`
    - mismatches before: `40`
    - updated: `40`
    - mismatches after: `0`
    - invalid JSON: `0`
    - DATABASE hunt codes missing split detail file: `24`
  - Boundaries metadata:
    - files with hunt_code overlap to DATABASE: `1467`
    - mismatches before: `15`
    - updated: `15`
    - mismatches after: `0`
    - invalid JSON: `0`
  - Total boundary-mapping changes applied: `95`

- Post-reconciliation validation sweep:
  - `SPLIT_INDEX_MISMATCH = 0`
  - `SPLIT_DETAIL_MISMATCH = 0`
  - `BOUNDARY_METADATA_MISMATCH = 0`
  - `SPLIT_DETAIL_INVALID_JSON = 0`
  - `BOUNDARY_INVALID_JSON = 0`

## 2026-06-01T11:24:00-06:00 - Google Maps 3D Runtime Compliance Patch (Post-2025 Init Rule)

- Trigger:
  - 3D map behavior aligned to updated Maps JS 3D requirements:
    - explicit `Map3DElement.mode` required (`HYBRID` or `SATELLITE`)
    - remove auto-fallback behavior from Earth mode when 3D init fails

- File changed:
  - `app.js`

- Changes applied:
  - Set initial 3D element mode attribute to explicit uppercase `HYBRID`.
  - In runtime init, force `el.mode` to `MapMode.HYBRID` (fallback string `HYBRID`) and mirror that on attribute.
  - Replaced Earth-mode failure behavior:
    - removed automatic mode switch to Google map on 3D failure.
    - keep user in Earth mode and surface troubleshooting guidance.
  - Updated unavailable message text to avoid fallback instructions.

- Validation:
  - `node -e "new Function(fs.readFileSync('app.js','utf8'))"` => syntax OK

## 2026-06-01T12:05:00-06:00 - Restore Prior Google Earth Iframe Mode (Known Working Behavior)

- Trigger:
  - User requested return to the previously working Earth experience instead of forcing Maps JS 3D runtime.

- Files changed:
  - `app.js`
  - `index.html`

- Changes applied:
  - Restored Earth mode to iframe path (`https://www.uoga.org/hunt-builder-google-earth`) via `USE_GOOGLE_EARTH_IFRAME_MODE = true`.
  - Added/ensured `googleEarthFrame` wiring and startup event binding.
  - Ensured mode switching hides Earth iframe when leaving Earth mode.
  - Added static `#googleEarthFrame` element in map stage for deterministic runtime availability.
  - Kept Google and DWR map behavior unchanged.

- Validation:
  - `node --check app.js` => syntax OK
  - `rg` checks confirm Earth iframe startup binding and DOM element presence.

## 2026-06-01T12:22:00-06:00 - Fix Google Earth Iframe 404 + Force New App Bundle Token

- Trigger:
  - Earth mode iframe path was returning `404` in production (`hunt-builder-google-earth`).

- Files changed:
  - `app.js`
  - `index.html`
  - `hunt-builder-google-earth.html` (new)

- Changes applied:
  - Replaced dead Earth iframe target with local served route:
    - `./hunt-builder-google-earth.html?v=20260601-earth-frame-local-1`
  - Added new local Earth frame page that renders a satellite Google map using existing site key/config.
  - Bumped `index.html` app bundle token to:
    - `app.js?v=20260601-earth-frame-404-fix-1`
    - to force browser refresh off stale cached JS.

- Validation:
  - `node --check app.js` => syntax OK
  - `rg` checks confirm new iframe target and updated app bundle token.

## 2026-06-01T12:45:00-06:00 - Repo-Native Google Earth 3D Page + 2D-to-3D Context Bridge

- Trigger:
  - Replace dead external Earth dependency with a repo-native 3D Earth runtime that stays integrated with Builder hunt selection.

- Files changed:
  - `app.js`
  - `index.html`
  - `hunt-builder-google-earth.html`

- Changes applied:
  - Added Earth iframe context bridge in `app.js`:
    - emits `postMessage` payload (`uoga-earth-context`) containing selected hunt code, boundary IDs, species/weapon labels, and center point.
    - sends payload on Earth iframe load, Earth mode activation, and selected-hunt sync.
  - Updated Earth iframe URL token:
    - `./hunt-builder-google-earth.html?v=20260601-earth-3d-bridge-1`
  - Rebuilt `hunt-builder-google-earth.html` as a true Maps JS 3D page:
    - loads `maps3d` library (`v=beta`)
    - creates `Map3DElement` in `SATELLITE` mode
    - loads canonical hunt master and boundary GeoJSON from repo runtime paths
    - resolves hunt/boundary IDs and renders selected boundary overlays via `Polygon3DElement`
    - focuses 3D camera on selected hunt context from parent page
    - displays explicit diagnostics if 3D/map data fails
  - Bumped Builder app bundle token in `index.html`:
    - `app.js?v=20260601-earth-3d-bridge-1`

- Validation:
  - `node --check app.js` => syntax OK
  - `rg` checks confirm:
    - new app token in `index.html`
    - Earth iframe URL token in `app.js`
    - context bridge message type in both parent and Earth page
  - `npm run build` => PASS

## 2026-06-01T11:42:00-06:00 - Google Earth 3D Failure Diagnostics + SATELLITE Retry

- Trigger:
  - Runtime still emitting generic `maps3d.js` load failure with no actionable detail.

- File changed:
  - `app.js`

- Changes applied:
  - Added one-time `HYBRID -> SATELLITE` retry on `gmp-error` before final failure state.
  - Added structured console diagnostics on failure:
    - `gmp-error` payload
    - active mode
    - WebGL / WebGL2 support check
    - browser runtime metadata
  - Enhanced on-page status text to include runtime diagnostics tuple:
    - `(mode=..., webgl2=..., webgl=...)`
  - Kept Earth mode active (no 2D auto-fallback).

- Validation:
  - `node -e "new Function(fs.readFileSync('app.js','utf8'))"` => syntax OK

## 2026-06-01T12:32:00-06:00 - Google Maps 3D Runtime Repair (Native 3D Path + Boundary Overlay Hardening)

- Trigger:
  - Entry-page Earth selector still ran iframe mode in production and did not activate native `<gmp-map-3d>` runtime.
  - Prior boundary-load failures needed to remain non-fatal for Earth mode.

- Files changed:
  - `app.js`
  - `index.html`
  - `processed_data/audits/google_earth_3d_boundary_runtime_audit_20260601.json` (added)

- Changes applied:
  - Kept native 3D mode active by default:
    - `USE_GOOGLE_EARTH_IFRAME_MODE = false`
  - Replaced direct async Earth overlay refresh calls in UI flows with debounced safe wrapper:
    - `refreshGoogleEarth3dBoundaryOverlaySoon()` in reset/filter/apply and unit chooser flows.
  - Preserved non-fatal overlay handling:
    - Earth overlay refresh remains wrapped in `.catch(...)` for mode activation and timer refresh.
  - Updated Builder app cache-bust token in `index.html`:
    - `app.js?v=20260601-earth3d-runtime-repair-2`

- Boundary runtime audit:
  - Source index: `processed_data/display-boundary-index-2026.json`
  - Distinct boundary paths audited: `1394`
  - Valid: `1394`
  - Missing: `0`
  - Invalid JSON: `0`
  - Git LFS pointers: `0`

- Validation:
  - `node --check app.js` => syntax OK
  - `rg -n "defaultUIDisabled|default-ui-disabled" app.js` => no matches
  - `rg -n "app.js\\?v=" index.html` => updated token present
  - Live pre-deploy check (2026-06-01):
    - `https://huntbuilder.uoga.org/` still served prior app token and remained in iframe mode until new deployment is published.

## 2026-06-01T14:05:00-06:00 - Comprehensive Google Earth / 3D Runtime Contract Audit + Validation

- Trigger:
  - User requested full end-to-end verification and repair audit for Google Maps 3D selector mode, including direct boundary GeoJSON integrity and live runtime behavior.

- Scope executed:
  - Audited current live 3D code path in `app.js`:
    - `applyMapMode` earth branch
    - `ensureGoogleEarth3dElement`
    - `ensureGoogleEarth3dMap`
    - `refreshGoogleEarth3dBoundaryOverlay`
    - direct boundary paths via `boundary_geojson_path`
  - Compared implementation parity against old `HUNTS` repo path.
  - Audited all direct boundary files referenced by:
    - `processed_data/display-boundary-index-2026.json`
  - Validated local + live JSON/GeoJSON integrity for every referenced boundary file.
  - Verified selector flow in both local and live environments for Google, DWR, and Earth modes.

- Files added:
  - `processed_data/audits/google_earth_3d_boundary_assets_audit_20260601.json`
  - `processed_data/audits/google_earth_3d_boundary_assets_audit_20260601.csv`
  - `processed_data/audits/google_earth_3d_boundary_assets_audit_20260601_mismatches.csv`

- Boundary asset audit results:
  - Source index rows: `1394`
  - Distinct direct boundary paths: `1394`
  - Local valid GeoJSON: `1394/1394`
  - Live valid GeoJSON at `https://huntbuilder.uoga.org/...`: `1394/1394`
  - Missing: `0`
  - Invalid JSON: `0`
  - Invalid GeoJSON: `0`
  - Git LFS pointer files: `0`
  - Mismatches (local vs live validity): `0`

- EB3024 specific result:
  - Path: `processed_data/boundaries/EB3024.geojson`
  - Local: valid GeoJSON FeatureCollection
  - Live: `200` with `application/geo+json`, valid GeoJSON
  - Classification: **not** a Git LFS pointer

- Deprecated property cleanup verification:
  - Runtime code search:
    - `defaultUIDisabled` / `default-ui-disabled` in active `app.js`: no matches
    - active path uses `defaultUIHidden` handling and attribute removal pattern

- Mode/render verification (Playwright):
  - Local: `http://127.0.0.1:8080/`
    - Google mode: PASS
    - DWR mode: PASS
    - Earth mode: PASS (`<gmp-map-3d>` visible, mode `SATELLITE`, overlays rendered)
  - Live: `https://huntbuilder.uoga.org/`
    - Google mode: PASS
    - DWR mode: PASS
    - Earth mode: PASS (`<gmp-map-3d>` visible, mode `SATELLITE`, overlays rendered)
  - Non-fatal console note still observed from Maps runtime:
    - `"Attempted to load a 3D Map, but failed..."` appears despite successful render; treated as runtime warning noise while map remains visible and usable.

- Validation commands run:
  - automated local/live mode switching checks via Playwright
  - full boundary asset integrity/fetch audit against local files and live URLs

## 2026-06-01T14:42:00-06:00 - Earth Mode Stability Patch (DWR Status Leak + SATELLITE-First Init)

- Trigger:
  - User runtime showed Earth mode selected with 3D element present, but status text was overwritten by stale DWR iframe timeout messaging.

- File changed:
  - `app.js`

- Changes applied:
  - Added mode guard to DWR iframe timeout status update:
    - only shows DWR timeout status when current mode is `dwr`.
  - Added mode guard to DWR iframe error status update:
    - only shows DWR iframe error when current mode is `dwr`.
  - Cleared pending DWR iframe timeout when switching to Earth mode.
  - Cleared pending DWR iframe timeout when switching to Google mode.
  - Set default 3D mode startup to `SATELLITE` (`GOOGLE_MAPS_3D_DEFAULT_MODE`) instead of HYBRID-first.
  - Kept existing non-fatal Earth overlay behavior intact.

- Validation:
  - `node --check app.js` => syntax OK
  - `git diff --check` => clean
  - local mode-switch audit:
    - confirmed `dwrStatusLeakedIntoEarth = false`
  - live mode-switch audit:
    - confirmed `dwrStatusLeakedIntoEarth = false`

## 2026-06-01T16:03:00-06:00 - hunt_research_2026 Contract Completeness Audit

- Scope:
  - Audited `processed_data/hunt_research_2026.json` for completeness as the Research page canonical contract.
  - Compared contract coverage and field completeness against:
    - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv`
    - `processed_data/point_ladder_view.csv`
    - `processed_data/draw_reality_engine.csv`
    - `processed_data/hunt_master_enriched.csv` (Cloudflare canonical runtime copy used when local file resolved as LFS pointer text)
  - Audited active Research runtime expectations from:
    - `hunt-research.js`
    - `assets/js/research-outlook-dashboard.js`

- Outputs created:
  - `docs/hunt_research_2026_contract_audit.md`
  - `processed_data/audits/hunt_research_2026_contract_audit.csv`

- Key results:
  - JSON parse: PASS
  - Top-level type: `list`
  - Total rows: `1117`
  - Unique hunt codes in contract: `1117`
  - Unique hunt codes in DATABASE truth: `1449`
  - Missing vs DATABASE: `337`
  - Extra codes not in DATABASE: `5`
  - Runtime-expected fields discovered from JS: `63`
  - Runtime-expected fields missing from contract rows: `59`
  - Contract status: **INCOMPLETE**

- Why INCOMPLETE:
  - Coverage gap to DATABASE 2026 universe (`337` missing hunt codes).
  - Major missing Research-facing contract concepts (residency, points, draw-line/guaranteed-line family, point-creep, explicit recommendation/output contract fields, explicit source/model freshness contract fields).
  - Runtime still depends on multiple parallel CSV/JSON feeds and does not yet consume this JSON as full single-source contract.

- Validation run:
  - `python` parse check for `processed_data/hunt_research_2026.json` (list + row count + unique hunt_code count)
  - output file existence checks:
    - `docs/hunt_research_2026_contract_audit.md`
    - `processed_data/audits/hunt_research_2026_contract_audit.csv`
  - `git diff --check` (final pass)

## 2026-06-01T17:08:00-06:00 - average_harvest_age Population Audit + Mapping Repair

- Assigned task:
  - Audit and repair `average_harvest_age` population in public hunt table exports only.
  - Focus on upstream join/mapping logic without changing prediction math or DATABASE truth.

- Pipeline path identified:
  - Upstream population script: `scripts/build-hunt-research-classification-layer.js`
  - Public contract pass-through: `scripts/build-public-data-contracts.js`
  - Audited public hunt table exports:
    - `processed_data/research_page/hunt_application_outlook.json`
    - `processed_data/public_contracts/hunt_application_outlook.json`

- Defect found:
  - Direct hunt-code joins were largely functioning.
  - Major remaining weakness was missing direct hunt-code age coverage plus a smaller unit/species mapping gap where valid latest-year age evidence existed in harvest source rows but was not carried to the export.

- Repair applied (upstream logic):
  - File changed: `scripts/build-hunt-research-classification-layer.js`
  - Added strict unit+species age fallback for blank `average_harvest_age` rows:
    - source: harvest quality feed (`average_age` / `average_harvest_age`)
    - matching: normalized unit name + species
    - guardrail: only latest-year unit rows; only apply when age values are stable (spread <= 0.2)
    - output tagging: `age_review_status = REVIEW_UNIT_LEVEL_REPEATED` for fallback-populated rows
  - No loose fuzzy inference used.
  - No DATABASE.csv writes.
  - No draw/odds model math changes.

- Regenerated outputs:
  - `processed_data/research_page/hunt_application_outlook.json`
  - `processed_data/research_page/hunt_application_outlook.csv`
  - `processed_data/public_contracts/hunt_application_outlook.json`
  - `processed_data/audits/hunt_classification_layer_audit.json`

- Required audit outputs created:
  - `docs/average_harvest_age_population_audit.md`
  - `processed_data/audits/average_harvest_age_population_audit.csv`

- Outcome:
  - `average_harvest_age` populated rows increased from `1112` to `1268` (`+156` rows).
  - Blank rows reduced from `1786` to `1630`.
  - Blank classification totals:
    - `SOURCE_MISSING = 1616`
    - `MAPPING_FAILURE = 0` (after repair under strict rules)
    - `JOIN_FAILURE = 0`
    - `VALIDATION_BLOCK = 0`
    - `INTENTIONAL_BLANK = 14`

- Validation run:
  - `node --check scripts/build-hunt-research-classification-layer.js`
  - `node scripts/build-hunt-research-classification-layer.js`
  - `node scripts/build-public-data-contracts.js`
  - Python consistency checks for pre/post nonblank delta and blank classification
  - final `git diff --check`

## 2026-06-01T17:41:00-06:00 - average_harvest_age Audit Continuation (Stale Path Bottleneck Test)

- Scope:
  - Continued exactly on `average_harvest_age` completeness audit.
  - Quantified whether missing primary age source path is the actual bottleneck.
  - Produced required blank-cause breakdown including `STALE_SOURCE_PATH`.
  - Repaired only the stale primary-source pipeline defect.

- Stale-path bottleneck result:
  - Expected primary path: `processed_data/harvest_age_features_by_hunt_code_latest.csv` (missing)
  - Resolved runtime age source path used by builder: `data_model/harvest_quality/harvest_average_age_global_merge_database.csv`
  - Coverage delta after path repair: `0` populated rows (1268 -> 1268)
  - Conclusion:
    - Missing primary path is a real configuration defect.
    - It is not the current completeness bottleneck because fallback source resolution already preserved age coverage.

- Required cause breakdown (blank age rows):
  - `SOURCE_MISSING = 1616`
  - `STALE_SOURCE_PATH = 0`
  - `JOIN_FAILURE = 0`
  - `MAPPING_FAILURE = 0`
  - `VALIDATION_BLOCK = 0`
  - `INTENTIONAL_BLANK = 14`

- Coverage comparison vs harvest-success/day metrics:
  - Total rows: `2898`
  - Age populated: `1268`
  - Age blank: `1630`
  - Blank rows with `harvest_success` and/or `avg_days_hunted` populated: `1430`

- Pipeline defect repaired (only):
  - File: `scripts/build-hunt-research-classification-layer.js`
  - `paths.age` updated to existing canonical source:
    - from `processed_data/harvest_age_features_by_hunt_code_latest.csv`
    - to `data_model/harvest_quality/harvest_average_age_global_merge_database.csv`
  - Old stale path retained as fallback candidate.

- Regeneration:
  - Sample export regenerated:
    - `processed_data/research_page/hunt_application_outlook.json`

- Outputs updated:
  - `docs/average_harvest_age_population_audit.md`
  - `processed_data/audits/average_harvest_age_population_audit.csv`

## 2026-06-01T17:55:00-06:00 - Rebuild Complete `hunt_research_2026.json` Contract

- Scope:
  - Rebuilt `processed_data/hunt_research_2026.json` from canonical sources to replace incomplete partial feed.
  - Preserved DATABASE truth and avoided invented values.
  - Added explicit missing classification metadata per row.

- Implementation:
  - Added script: `scripts/build-hunt-research-2026-contract.py`
  - Inputs used:
    - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` (truth)
    - `pipeline/RAW/hunt_unit_database/2026/csv/hunt_master_canonical_2026_built.csv` (master fallback; LFS-safe)
    - `processed_data/point_ladder_view.csv`
    - `processed_data/draw_reality_engine.csv`
    - `processed_data/harvest_quality_features_all_years_by_hunt_code.csv`
    - `data_model/harvest_quality/harvest_average_age_global_merge_database.csv`
    - `processed_data/management_context/hunt_management_objective_context.json`

- Required outputs created:
  - `processed_data/hunt_research_2026.json`
  - `docs/hunt_research_2026_rebuild_notes.md`
  - `processed_data/audits/hunt_research_2026_rebuild_coverage.csv`

- Rebuild results:
  - Contract rows: `91712`
  - Unique contract hunt codes: `1449`
  - DATABASE hunt codes: `1449`
  - Missing hunt codes vs DATABASE: `0`
  - Runtime expected field set size used for validation: `63`
  - Runtime fields with zero populated values: `4` (`length`, `p_bonus_pool_pct`, `push`, `some`)
  - Contract status: `PARTIAL` (coverage complete; a small set of runtime artifact fields remain unpopulated)

- Validation run:
  - `python scripts/build-hunt-research-2026-contract.py`
  - JSON parse + row count checks on rebuilt contract
  - coverage audit rows generated and reviewed
  - final `git diff --check`

## 2026-06-01T18:05:00-06:00 - average_harvest_age Source-Correction Audit (Annual Report vs Hunt Planner)

- Trigger:
  - User correction that primary average-harvest-age source should be annual harvest report data, not primarily Hunt Planner current 3-year age.

- Scope completed:
  1. Audited current public export age column source lineage.
  2. Classified each public export row into required source families:
     - `ANNUAL_HARVEST_REPORT_AGE`
     - `UNIT_LEVEL_REPEATED_ANNUAL_AGE`
     - `FALLBACK_MERGED_AGE`
     - `HUNT_PLANNER_CURRENT_3YR_AVG`
     - `SOURCE_MISSING`
  3. Tested label accuracy for phrase: **Average Harvest Age Prior Year** (for 2026 context, prior year interpreted as 2025).
  4. Tested whether valid annual-report age is being lost by join/mapping/validation.
  5. Audited sample hunt `EB3038` against public export, annual-report source value, and 3-year age context.
  6. Determined export strategy recommendation (annual-report age primary, 3-year age separate).

- Files audited:
  - `processed_data/public_contracts/hunt_application_outlook.json` (public export surface)
  - `processed_data/research_page/hunt_application_outlook.json` (upstream source lineage columns)
  - `data_model/harvest_quality/harvest_average_age_global_merge_database.csv` (annual age source family)
  - `processed_data/harvest_quality_features_all_years_by_hunt_code.csv` (merged annual harvest fallback)
  - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` (`current_age_3yr_average` context)

- Source family results (rows):
  - `ANNUAL_HARVEST_REPORT_AGE = 974`
  - `UNIT_LEVEL_REPEATED_ANNUAL_AGE = 156`
  - `FALLBACK_MERGED_AGE = 138`
  - `HUNT_PLANNER_CURRENT_3YR_AVG = 6`
  - `SOURCE_MISSING = 1624`

- Label accuracy result:
  - Populated age rows: `1268`
  - `ACCURATE (year == 2025): 0`
  - `NOT_ACCURATE: 904`
  - `UNKNOWN: 364`
  - Conclusion: label **Average Harvest Age Prior Year** is not generally accurate for current rendered data.
  - Recommended wording: **Verified Harvest Age (Most Recent Annual Report)**.

- Join/mapping/validation result:
  - Direct annual-evidence join failures: `0`
  - No evidence that valid direct annual age is currently being dropped by join path.
  - Hunt Planner 3-year age remains a separate context field, not a replacement source.

- EB3038 sample:
  - Public export `average_harvest_age`: `6`
  - Annual-report age value: `6.0` (reported hunt year `2024`)
  - Hunt Planner current 3-year age: `6.3`
  - Interpretation: rendered export age aligns to annual-report age family; 3-year value is separate context.

- Outputs updated:
  - `docs/average_harvest_age_population_audit.md`
  - `processed_data/audits/average_harvest_age_population_audit.csv`

- Regeneration decision:
  - No additional sample export regeneration performed in this step.
  - Reason: confirmed issue is label/semantics accuracy, not a new value-loss defect in current join pipeline.

## 2026-06-01T18:32:00-06:00 - DATABASE(2) vs Public Export Universe Gap Audit (55-Code Delta)

- Scope:
  - Audited the reported 55-hunt-code difference between a 1,394-code "DATABASE(2)" universe and the public age/export universe (1,449).
  - Produced required markdown + CSV outputs and classification of the gap cause.

- Source resolution:
  - No file named `DATABASE(2).csv` exists in active repo path.
  - To match the stated `1,394` universe, audit used:
    - `data/hunt-master-canonical-2026-foundation.json` (1,394 unique hunt codes)
  - Public universe source:
    - `processed_data/audits/average_harvest_age_two_column_audit.csv` (1,449 unique hunt codes)
  - Canonical truth cross-check:
    - `pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv` (1,449 unique hunt codes)

- Results:
  - `public_export_universe - database2_1394_universe = 55`
  - `database2_1394_universe - public_export_universe = 0`
  - All 55 gap codes are present in canonical `DATABASE.csv`.
  - All 55 are missing from both:
    - `data/hunt-master-canonical-2026-foundation.json` (1,394 baseline)
    - `data/hunt-master-canonical-2026-source-of-truth.json` (1,411 baseline)

- Gap profile:
  - Hunt type breakdown:
    - `CWMU = 36`
    - `General Season = 6`
    - `Limited Entry = 6`
    - `Once-in-a-lifetime = 3`
    - `Limited Entry - Spring/Summer/Fall = 4`
  - Species breakdown:
    - `Deer = 15`, `Moose = 15`, `Elk = 10`, `Pronghorn = 9`, `Black Bear = 4`, `Bison = 1`, `Desert Bighorn Sheep = 1`

- Conclusion:
  - This is a **stale canonical baseline** issue, not a public export overreach.
  - Public age/export universe aligns with current `DATABASE.csv` truth (1,449).
  - 1,394 and 1,411 JSON baselines should be regenerated or marked stale.

- Outputs created:
  - `docs/database_vs_public_export_universe_gap_report.md`
  - `processed_data/audits/database_vs_public_export_universe_gap.csv`

- Validation run:
  - CSV/JSON parse and unique-hunt-code set-difference checks via Python
  - Spot-check that all 55 gap codes exist in `DATABASE.csv`
  - final `git diff --check`

## 2026-06-01T19:06:00-06:00 - Harvest Age Production Behavior Formalization

- Scope:
  - Locked production behavior for age fields without broad repair work.
  - Documented intentional blanks policy.
  - Confirmed public contract/export field stability.
  - Limited future proposals to species-by-species source-family expansion only.

- Production behavior confirmed:
  1. Blanks are intentional when no defensible age source exists.
  2. Canonical contract targets are:
     - `processed_data/public_contracts/hunt_application_outlook.json`
     - `processed_data/research_page/hunt_application_outlook.json`
  3. Both canonical targets include both fields on all rows:
     - `average_harvest_age`
     - `current_age_3yr_average`
  4. Canonical target counts are aligned:
     - rows: `2898`
     - nonblank `average_harvest_age`: `1268`
     - nonblank `current_age_3yr_average`: `440`

- Stability/export note:
  - `processed_data/audits/average_harvest_age_two_column_full_promotion_audit.json` confirms full export-set promotion activity:
    - files scanned: `168`
    - files updated: `165`
    - average age rows filled: `2030`
    - current 3-yr rows filled: `716`

- Non-canonical copy note:
  - `data/hunt_application_outlook.json` remains non-canonical/stale for `average_harvest_age` (`1112` nonblank) and should not be treated as production contract truth until explicitly re-synced.

- File updated:
  - `docs/average_harvest_age_two_column_policy.md`

## 2026-06-01T19:18:00-06:00 - Backfill `data/hunt_application_outlook.json` From Canonical Processed Copies

- Scope:
  - Verified canonical alignment state.
  - Audited differences between canonical contract and stale compatibility mirror.
  - Backfilled `data/hunt_application_outlook.json` from canonical public contract source.
  - Documented source-of-truth and derived-copy policy.

- Canonical alignment check:
  - `processed_data/public_contracts/hunt_application_outlook.json`:
    - rows: `2898`
    - schema keys: `28`
  - `processed_data/research_page/hunt_application_outlook.json`:
    - rows: `2898`
    - schema keys: `45`
  - Interpretation:
    - Row universe is aligned.
    - Research copy includes additional metadata fields; public-contract copy is the compatibility-schema baseline.

- Pre-backfill stale copy audit (`data/hunt_application_outlook.json`):
  - rows: `2898`, keys: `28`
  - nonblank `average_harvest_age`: `1112` (stale)
  - canonical nonblank `average_harvest_age`: `1268`
  - nonblank `current_age_3yr_average`: `440` in both
  - additional field-level value mismatches were recorded in:
    - `processed_data/audits/hunt_application_outlook_backfill_diff.csv`

- Backfill action:
  - Source used: `processed_data/public_contracts/hunt_application_outlook.json`
  - Target updated: `data/hunt_application_outlook.json`
  - Method: direct file copy (no hand-editing)

- Post-backfill validation:
  - `data/hunt_application_outlook.json` row count: `2898` (matches canonical)
  - `data/hunt_application_outlook.json` schema keys: `28` (compatibility schema preserved)
  - hash equality: `data/...` == `processed_data/public_contracts/...` (`True`)
  - nonblank `average_harvest_age`: `1268` (now aligned)
  - nonblank `current_age_3yr_average`: `440` (aligned)

- Runtime compatibility check:
  - Active research runtime reads canonical processed paths in `assets/js/research-outlook-dashboard.js`.
  - `data/hunt_application_outlook.json` is retained as derived compatibility mirror.

- Outputs created:
  - `docs/hunt_application_outlook_backfill_policy.md`
  - `processed_data/audits/hunt_application_outlook_backfill_diff.csv`
  - updated `data/hunt_application_outlook.json`

- Validation run:
  - JSON parse + row/field/hash checks
  - runtime consumer path check
  - final `git diff --check`

## 2026-06-01T20:02:00-06:00 - Hunt Research Runtime Canonicalization (Single Contract Primary)

- Scope:
  - Migrated active Hunt Research runtime to canonical-contract-first loading.
  - Reduced legacy parallel feed dependence to fallback-only for core runtime.
  - Kept UI behavior and existing render logic structure stable.

- Code changes:
  - `hunt-research.js`
    - Added canonical runtime source intake via `HUNT_RESEARCH_DATA_SOURCES`.
    - Implemented canonical JSON parsing + derived runtime table adapter for:
      - engine rows
      - ladder rows
      - master rows
      - reference rows
    - Updated `loadData()` to:
      1. load canonical contract first
      2. fall back to legacy CSV feeds only if canonical load fails
    - Added load-source metadata:
      - `canonicalContract`
      - `canonicalRows`
      - `legacyFallbackUsed`

- Runtime dependency posture after change:
  - Primary core feed: `processed_data/hunt_research_2026.json`
  - Fallback-only (temporary safety):
    - `processed_data/draw_reality_engine.csv`
    - `processed_data/draw_reality_engine_predictive_v2.csv`
    - `processed_data/point_ladder_view.csv`
    - `processed_data/hunt_master_enriched.csv`
    - `processed_data/hunt_unit_reference_linked.csv`
  - Secondary dashboard layers intentionally unchanged:
    - `processed_data/public_contracts/hunt_application_outlook.json`
    - `processed_data/research_page/hunt_application_outlook.json`
    - `processed_data/management_context/hunt_management_objective_context.json`

- Required outputs created:
  - `docs/hunt_research_runtime_canonicalization.md`
  - `processed_data/audits/hunt_research_runtime_dependency_reduction.csv`

- Validation run:
  - `node --check hunt-research.js`
  - source-path and dependency chain audit checks
  - final `git diff --check`

## 2026-06-01T20:34:00-06:00 - Four-Feeder Preservation Reconciliation vs `hunt_research_2026.json`

- Scope:
  - Verified whether the rebuilt canonical contract preserves prior Hunt Research feeder data.
  - Reconciled full `1449` hunt-code universe by mapped hunter-facing fields.
  - Verified runtime publication state (contract-published vs legacy/fallback).

- Locked feeder set (legacy runtime):
  1. `processed_data/draw_reality_engine.csv`
  2. `processed_data/point_ladder_view.csv`
  3. `processed_data/hunt_master_enriched.csv`
  4. `processed_data/hunt_unit_reference_linked.csv`

- Important feeder condition:
  - Local `processed_data/hunt_master_enriched.csv` is an LFS pointer payload (not row-usable).
  - Master-owned field reconciliation is marked `REVIEW_REQUIRED` rather than guessed.

- Reconciliation coverage:
  - Universe: `1449` hunt codes (from `DATABASE.csv`)
  - Mapped hunter-facing fields: `28`
  - Total comparison rows: `40572`

- Comparison status counts:
  - `MATCH = 16120`
  - `IMPROVED_FROM_CANONICAL_SOURCE = 4147`
  - `MISSING_IN_TARGET = 590`
  - `MISMATCH = 0`
  - `NOT_PRESENT_IN_FEEDER = 9572`
  - `INTENTIONALLY_RETIRED = 0`
  - `REVIEW_REQUIRED = 10143`

- Runtime publication check counts:
  - `PRIMARY_FROM_CONTRACT_WITH_LEGACY_FALLBACK = 21`
  - `MISSING_IN_CONTRACT = 2`
  - `REVIEW_REQUIRED = 5`

- Fields not fully published from canonical contract path:
  - `availability_status`
  - `current_age_3yr_average`
  - `dwr_result_display`
  - `guaranteed_at_2026`
  - `management_direction`
  - `management_objective_range`
  - `management_objective_type`

- Replacement verdict:
  - **PARTIALLY VERIFIED** as a strict replacement for prior four-feeder runtime.
  - Core runtime is now canonical-contract-primary, but full feeder-equivalence publication is not yet complete.

- Outputs created:
  - `docs/hunt_research_feeder_to_contract_reconciliation.md`
  - `processed_data/audits/hunt_research_feeder_to_contract_reconciliation.csv`
  - `processed_data/audits/hunt_research_runtime_publication_check.csv`

## 2026-06-01T12:15:00-06:00 - Targeted Cleanup of Six Remaining Hunt Research Field Families

- Scope:
  - Focused reconciliation pass only for:
    - `display_odds_pct`
    - `p_draw_mean`
    - `p_draw_p10`
    - `p_draw_p90`
    - `permits_2026_total`
    - `average_harvest_age`
  - No UI redesign, no expansion into unrelated field families.

- Repairs made:
  - `scripts/build-hunt-research-2026-contract.py`
    - fixed `display_odds_pct` derivation so ladder `display_odds_pct` values are treated as already-percent display values (no erroneous x100 scaling).
    - increased precision for `p_draw_mean`, `p_draw_p10`, `p_draw_p90` to 6 decimals to reduce false format-only drift.
    - retained canonical `permits_2026_total` hierarchy (`DATABASE.csv` / DWR fallback) and canonical annual-age hierarchy for `average_harvest_age`.

- Targeted reconciliation outputs created:
  - `docs/hunt_research_six_field_cleanup.md`
  - `processed_data/audits/hunt_research_six_field_cleanup.csv`
  - `processed_data/audits/hunt_research_six_field_cleanup_summary.json`

- Validation run:
  - `python -m py_compile scripts/build-hunt-research-2026-contract.py scripts/hunt-research-six-field-cleanup.py`
  - `python scripts/build-hunt-research-2026-contract.py`
  - `python scripts/hunt-research-six-field-cleanup.py`
  - `git diff --check`

- Result:
  - Strict legacy-style mismatch rows remain for formatting/hierarchy reasons, but targeted true-defect unresolved rows are `0`.
  - Targeted six-field verification status: **FULLY VERIFIED**.

## 2026-06-01T12:32:00-06:00 - Hunt Research Production Runtime Finalization (Canonical Contract)

- Scope:
  - Finalized Hunt Research runtime behavior to use verified canonical contract as production source of record.
  - Reduced active runtime dependence on legacy feeder path by disabling fallback by default.
  - Kept emergency legacy fallback path available only as explicit local opt-in.

- Code changes:
  - `config.js`
    - added `HUNT_RESEARCH_ALLOW_LEGACY_FALLBACK` (default false unless explicitly enabled in `UOGA_LOCAL_CONFIG`).
  - `hunt-research.js`
    - reads `HUNT_RESEARCH_ALLOW_LEGACY_FALLBACK` from runtime config.
    - canonical contract load failure now throws when fallback flag is not enabled.
    - legacy parallel-feed load path remains gated behind explicit opt-in flag only.
    - standardized user-facing copy from "Not loaded" to "Not available" for clarity.
    - updated data-load error wording to "canonical Hunt Research contract sources."

- Canonical hierarchy preserved for key fields:
  - `permits_2026_total` from canonical contract (DATABASE/DWR hierarchy already baked in contract build).
  - `average_harvest_age` from canonical contract annual-age source hierarchy.
  - `current_age_3yr_average` from canonical contract source hierarchy.
  - `display_odds_pct` and `p_draw_*` from canonical contract outputs.

- Validation run:
  - `node --check hunt-research.js`
  - `node --check config.js`
  - `node --check assets/js/research-outlook-dashboard.js`
  - contract presence check for key fields in `processed_data/hunt_research_2026.json`
  - `git diff --check`
