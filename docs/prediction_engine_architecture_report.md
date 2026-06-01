# Prediction Engine Architecture Report

Generated: 2026-06-01 (America/Denver)  
Scope: current repo engines + live runtime usage on `https://huntbuilder.uoga.org`

## Executive Snapshot
- Production Research UI currently runs on a **Cloudflare-first CSV runtime contract**.
- Builder runtime is primarily **deterministic/filter/map + canonical JSON/GeoJSON**, not prediction math.
- Multiple predictive stacks exist in repo (`utah`, `utah_bonus_predictive`, `utah_draw_predictive`, `utah_predictive_mixed`), but not all are simultaneously active in live rendering.
- Current live prediction display depends on which engine CSV is loaded by `config.js` and runtime flag `USE_PREDICTIVE_DRAW_ENGINE`.

## Engine Inventory

| Engine | File path(s) | Status | Type | Inputs | Outputs | Current role | Overlap / risk notes |
|---|---|---|---|---|---|---|---|
| Hunt Research runtime selector | `config.js`, `hunt-research.js` | ACTIVE | Runtime routing/display | Cloudflare/local source lists; mode flag | Loaded engine/ladder/master/reference rows in browser | Chooses observed vs predictive feed and renders odds/ladder | Long fallback chains include missing local files; runtime still works due Cloudflare-first order |
| Research outlook dashboard contract layer | `assets/js/research-outlook-dashboard.js` | ACTIVE | Contract/display layer | `hunt_application_outlook.json`, management context JSON, core research snapshot | Hero metrics, 3-column dashboard content, management benchmark panels | Decision-dashboard presentation over core rows | Contract can silently degrade if fallback JSON paths drift |
| Utah deterministic draw core | `engine/utah/simulator.py`, `engine/utah/rules.py`, `engine/utah/materialize.py` | ACTIVE_LOCAL | Deterministic rules engine | Historical draw truth, demand/quota modules, source promotions | Materialized processed CSVs | Canonical deterministic mechanics and materialization pipeline | Not directly browser-executed; quality depends on upstream truth refresh cadence |
| Utah bonus predictive engine | `engine/utah_bonus_predictive/*`, `scripts/materialize_predictive_outputs.py` | ACTIVE_LOCAL | Modeled (bonus/cohort/MC + deterministic split rules) | Draw history, quota signals, rollover/cohort rules | `draw_reality_engine_predictive_v2.csv`, `ml_draw_predictions_v1.csv`, backtest reports | Primary predictive artifact generator for research odds mode | Competes with other runtime builders if contracts are not unified |
| Utah draw predictive family rules | `engine/utah_draw_predictive/*` | REVIEW | Hybrid deterministic/rule-family modules | Hunt-family classification + rule-specific inputs | Family-level draw behavior outputs | Supports species/family-specific routing and exclusions | Unclear direct materialization ownership vs bonus/mixed engines |
| Utah mixed predictive engine | `engine/utah_predictive_mixed/*`, `scripts/build_mixed_predictive_engine_2026.py` | ACTIVE_LOCAL | Hybrid modeled | Prior-year odds, quota deltas, rollover, harvest quality features | Mixed predictive engine CSV outputs | Adds weighted blended forecast behavior | Parallel output path can create contract confusion with bonus engine outputs |
| Runtime draw feed normalizer | `scripts/build_runtime_draw_feed_v2.py` | ACTIVE_LOCAL | Deterministic normalization/validation | `data_truth/.../draw_results_long.csv`, `DATABASE.csv`, current runtime feed | `data_model/runtime_drafts/draw_reality_engine_v2.csv` + validation reports | Builds normalized v2 runtime candidate feed | Candidate path can diverge from live if not promoted to Cloudflare/static source |
| Public contract materializer | `scripts/build-public-data-contracts.js` | ACTIVE_LOCAL | Contract packaging | Predictive/odds/outlook/outfitters/unit candidates | `processed_data/public_contracts/*` outputs | Produces public-facing JSON/CSV contract artifacts | Depends on file-candidate ordering; missing files can shift source lineage |
| Runtime sync orchestrator | `scripts/sync_online_runtime_from_predictive.py` | ACTIVE_LOCAL | Sync/orchestration | Predictive engine CSV + ladder/master/reference + DATABASE | `online_runtime_crosscheck.json/.md` and updated aligned outputs | Keeps runtime surfaces in sync with predictive output | Useful guardrail; not itself draw math |
| Legacy observed engine feed | `processed_data/draw_reality_engine.csv` | LEGACY | Observed historical/runtime legacy | Legacy draw-reality rows | Legacy CSV | Older fallback for research feed | Missing locally in current checkout; keep only if still required by fallbacks |
| Legacy display view | `processed_data/draw_reality_view.csv` | DISPLAY_ONLY | Display/reference | Processed display rows | Display table | Reference/legacy display surface | Not part of active live source ordering |

## Current Live Flow (Observed)
1. User selects/arrives at `research.html` with `hunt_code`, `residency`, `points`, `draw_pool`.
2. `hunt-research.js` loads data source groups from `config.js`.
3. `config.js` uses Cloudflare-first order for:
   - `draw_reality_engine_v2.csv` (or predictive variant when flag enabled)
   - `point_ladder_view.csv`
   - `hunt_master_enriched.csv`
   - `hunt_unit_reference_linked.csv`
4. Browser computes selected rung, guaranteed line context, projected draw odds, recommendation text, and ladder table.
5. `research-outlook-dashboard.js` layers outlook contract + management context for hero/decision cards.

## Truth vs Model vs Display Separation (Current)
- Truth-source layer:
  - `DATABASE.csv` (authoritative hunt/permit truth where applicable).
- Deterministic rules layer:
  - `engine/utah/*` draw mechanics and materialization.
- Modeled probability layer:
  - `engine/utah_bonus_predictive/*` and `engine/utah_predictive_mixed/*`.
- Display/runtime layer:
  - `hunt-research.js`, `research-outlook-dashboard.js`, Cloudflare-served runtime CSV/JSON contracts.

## Canonical-Now Assessment
- Most canonical live runtime contract today appears to be:
  - **Cloudflare research CSV feeds** + `config.js` source ordering.
- Most canonical truth source for data reconciliation remains:
  - **`DATABASE.csv`**.
- Most canonical export-recipient for workbook consumption:
  - **`MASTER.xlsx`**.

## Weaknesses / Overlap Risks
1. Multiple predictive pipelines exist with overlapping output intent.
2. Local fallback files referenced by runtime are absent in current checkout, increasing fragility if Cloudflare sources fail.
3. Legacy observed/display feeds remain in source lists or docs, causing ambiguity.
4. Builder boundary mapping includes at least one parse-broken source returning pointer-like payload.

## Deprecation Candidates (Not Applied In This Task)
- `draw_reality_view.csv` as runtime dependency (keep as reference only).
- `draw_reality_engine.csv` fallback entry if `v2` contract is fully canonicalized.
- Duplicate route aliases (`hunt-research.html`, `vetting.html`) once redirect strategy is approved.
