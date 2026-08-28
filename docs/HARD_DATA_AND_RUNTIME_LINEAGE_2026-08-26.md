# Hard Data Recovery and Live Runtime Lineage — 2026-08-26

## Scope and non-mutation rule

This record inventories the official DWR/UtahDraws source snapshots collected on 2026-08-26 and traces the feeds used by the live Hunt Research page. The collection writes raw files, manifests, and download logs only. It does **not** modify `DATABASE.csv`, normalized canonical truth, prediction outputs, R2 objects, or the live site.

Report-generation year is the raw-source folder year. It is not shifted into the following model year.

## Official source inventory

| Source family | Saved location | Result |
| --- | --- | --- |
| 2026 UtahDraws draw results / odds API snapshot | `pipeline/RAW/hunt_unit_database/2026/json/draw_results/utahdraws_2026_20260826/` | 29 included draw-package endpoints; 1,077 hunts; 22,018 point/residency rows; 0 endpoint errors. |
| Full official DWR draw-report archive | `pipeline/RAW/hunt_unit_database/_staging/draw_odds_deep_pull_20260826_203722/` | 275 official PDF reports saved; 305 manifest rows; the two download failures are retained in the manifest; 24 current UtahDraws endpoints are also captured. |
| Current DWR Hunt Planner public table matrix | `pipeline/RAW/hunt_unit_database/_staging/huntplanner_full_matrix_20260826_204000/` | 30 of 30 advertised category pulls succeeded. |
| Current DWR Hunt Planner deep popup data | `pipeline/RAW/hunt_unit_database/_staging/huntplanner_popup_deep_20260826_205700/` | 1,433 of 1,433 current HuntTableData hunt codes returned successfully; raw JSON payloads and flat evidence extract retained. |
| DWR annual and harvest-report archive, 2007 onward | `pipeline/RAW/hunt_unit_database/<report-year>/pdf/harvest_report/` | 213 current-page links discovered; 172 files present (106 newly downloaded, 66 previously present). 41 linked DWR URLs now return HTTP 404; all are 2014–2016 bighorn-sheep records and remain explicitly logged rather than silently omitted. |
| DWR species-specific harvest supplements, 2007 onward | `pipeline/RAW/hunt_unit_database/<report-year>/pdf/harvest_report/` | 120 links discovered; 99 files present (32 newly downloaded, 67 previously present). 21 current-page DWR URLs return HTTP 404 and remain logged. |

### 2026 UtahDraws snapshot

The exact source is the UtahDraws `DrawOddsData` endpoint family behind the public draw-odds page. Each raw JSON payload retains the hunt, permit and round-quota fields plus its `OddsList` rows, including residency, point level, participant count, successful count, maximum-point-round successes, regular-round successes, and the source's `IsHistoricalData` flag.

The combined flat extract is:

`pipeline/RAW/hunt_unit_database/2026/json/draw_results/utahdraws_2026_20260826/utahdraws_2026/csv/2026_allowed_draw_odds_all_flat_rows.csv`

It has SHA-256 `3f8d89896b9457414b75b41656345234fc16f6d30881c7d615f457d6fdf9162e`. The snapshot includes general-season, limited-entry, once-in-a-lifetime species, Dedicated Hunter, antlerless deer/elk/moose/pronghorn/ewe sheep, black-bear hunting and restricted-pursuit packages, turkey, and Sportsman packages. The four non-scope packages are listed in `DRAW_ODDS_DEEP_PULL_EXCLUDED_LINKS.csv`; no wetland or non-turkey upland package was included.

## Source manifests and retry evidence

- Full draw-report archive manifest: `pipeline/RAW/hunt_unit_database/_staging/draw_odds_deep_pull_20260826_203722/DRAW_ODDS_DEEP_PULL_MANIFEST.csv`
- 2026 UtahDraws-only manifest: `pipeline/RAW/hunt_unit_database/2026/json/draw_results/utahdraws_2026_20260826/DRAW_ODDS_DEEP_PULL_MANIFEST.csv`
- Hunt Planner matrix manifest: `pipeline/RAW/hunt_unit_database/_staging/huntplanner_full_matrix_20260826_204000/dwr_huntboundary_full_matrix_manifest.csv`
- Annual/harvest manifest and log: `pipeline/manifests/utah_dwr_harvest_pdf_links_2007plus.csv`, `pipeline/manifests/harvest_pdf_download_log_2007plus.csv`
- Species-harvest manifest and log: `pipeline/manifests/species_harvest_supplement_links_2007plus.csv`, `pipeline/manifests/species_harvest_supplement_download_log_2007plus.csv`
- Broken-link HTTP probe: `pipeline/manifests/dwr_historical_harvest_broken_link_http_probe_20260826.csv` (all 41 unique failed original URLs returned HTTP 404 on the official host during this run)

The download logs retain the exact original DWR URLs for every saved, pre-existing, and currently-404 response. A 404 row is not treated as data, evidence, a zero, or a prediction input.

### DWR Hunt Planner popup snapshot

The public Hunt Planner table matrix is the source of the active 2026 hunt-code universe. The popup collector then queried `HaNumber?roles=&hn={hunt_code}` once for each of those 1,433 codes. All returned HTTP 200. The retained raw payloads include the official hunt identity, design designation, resident/nonresident/youth quota fields, season text, boundary IDs and boundary details, waiting period, special provisions, harvest-reporting rules, management metrics, and biologist notes.

The popup source contains 29 active current-table codes not present in the current `DATABASE.csv`; that is a reconciliation finding, not permission to add or alter database rows automatically. The popup output is source evidence only.

### Hunt Planner to UtahDraws 2026 crosswalk

The current Hunt Planner universe has been mapped to the current UtahDraws draw-result snapshot. The source-to-source audit is at:

`pipeline/RAW/hunt_unit_database/_staging/huntplanner_popup_deep_20260826_205700/draw_results_crosswalk/huntplanner_to_utahdraws_draw_results_2026_crosswalk.csv`

Results:

- 1,433 Hunt Planner codes and 1,077 UtahDraws codes were compared.
- 1,058 codes have an exact current-code match.
- 375 Hunt Planner-only and 19 UtahDraws-only codes were classified rather than assumed invalid or missing.
- 275 exact-code quota differences are expected CWMU scope differences; 10 are expected Sportsman random-only scope differences.
- 383 exact-code public-draw quota differences were identified: 133 general-season/antlerless, 105 general-season deer, 92 limited-entry, 31 general-season/Dedicated Hunter, 11 once-in-a-lifetime, and 11 other families.
- Six non-quota rows require targeted review: `BR7237`, `CG9999`, `DB0009`, `EA2000`, `RS1000`, and UtahDraws-only `PB5329`.

The audit compares each exact-code row's official total, resident, and nonresident quota fields where UtahDraws publishes a split. It does not alter `DATABASE.csv` or allow an out-of-scope/allocation/reference row to become a draw probability row.

### Hunt Planner quota authority resolution

For current published permit quotas, the DWR Hunt Planner `HuntTableData` matrix is authoritative. UtahDraws values remain retained draw-result evidence; they never overwrite the DWR quota. The companion reconciliation attaches each crosswalk row to its exact DWR matrix file and endpoint URL, retains the UtahDraws evidence, and blocks unsupported residency-split derivation when DWR publishes a total-only row or a resident/nonresident split that does not equal its published total.

The 2026 authoritative reconciliation resolves the 383 matched public-draw differences by retaining the DWR value as the current quota and preserving the conflicting UtahDraws value for draw-result history/audit. Of the 773 matched public-draw rows, 470 have a usable official DWR resident/nonresident split and 166 are DWR total-only and therefore remain blocked from split-dependent forecasting. DWR draw-odds evidence directly reconciles 136 self-inconsistent Planner rows: 135 retain their published DWR resident/nonresident values while the draw-odds record confirms their sum as the missing zero total, and `BR7004` is confirmed at 18 resident, 2 nonresident, 20 total. `PD1056` is a user-confirmed DWR Planner typo: the raw table's `63 / 4 / 0` is retained as evidence, while the reviewed DWR record and official draw odds agree on `36 / 4 / 40`. No residency value is derived from a percentage, history, or another source.

The resulting audit is written under:

`pipeline/RAW/hunt_unit_database/_staging/huntplanner_popup_deep_20260826_205700/draw_results_crosswalk/huntplanner_authoritative_quota_reconciliation/`

## What serves Hunt Research in production

The hosted `config.js` declares `https://json.uoga.workers.dev` as its object-store base. In production, `hunt-research.js` enables its split canonical contract unless configuration explicitly sets `HUNT_RESEARCH_USE_SPLIT_CONTRACT` to `false`. The normal browser request path is therefore:

```text
R2 hunt_research_2026_summary.json
    + R2 hunt_research_2026_split/hunt_research_2026.index.json
    + R2 hunt_research_2026_ladder.json
    -> optional selected-hunt detail from the R2 split directory/bundle
    -> Hunt Research page
```

The R2 objects were confirmed available on 2026-08-26, as were the observed and predictive engine CSVs, point ladder, enriched hunt master, and linked unit reference. The engine CSVs are a legacy fallback path; they are not the normal data path while the split contract is healthy. Predictive mode is opt-in through `UOGA_LOCAL_CONFIG.USE_PREDICTIVE_DRAW_ENGINE`; without that local setting the configuration selects observed mode.

## Local rebuild lineage

```text
Official DWR PDFs / UtahDraws API / Hunt Planner tables
    -> report-year raw files with manifests and hashes
    -> yearly canonical draw and harvest truth
    -> normalized draw_results_long.csv + current official reference inputs
    -> family-routed prediction materializer
    -> predictive engine + point ladder + Hunt Research contract
    -> R2 publication (only with explicit authorization)
    -> hosted Hunt Research page
```

The relevant builders are:

- `engine/utah_bonus_predictive/materialize.py`: reads normalized `draw_results_long.csv` and current `DATABASE.csv`; routes draw families rather than applying one generic formula.
- `engine/utah_predictive_mixed/materialize.py`: applies the calibrated mixed layer to eligible family outputs and writes the predictive engine and point ladder.
- `scripts/build-hunt-research-2026-contract.py`: combines the database, enriched master, point ladder, normalized draw history, and harvest inputs into the Research contract.
- `scripts/rebuild-runtime-hunt-master-and-split.py`: produces the public hunt-master mirrors and split Research index/detail files.
- `scripts/publish-runtime-assets-r2.js`: catalogues the R2 publication targets. It was not run for this recovery.

## Current trust boundary

The current local normalized draw truth SHA-256 is `48240cfded2661cd0dc74f43db4d0a31b230d85a123f42f4befbd79820f68b6a`.

The checked-in predictive manifest records that same draw-truth hash, but records `DATABASE.csv` at SHA-256 `62dafb22d683e5a4b1a8226040fad02753175071c23d8fabb8f983755f8018a2`. The current local `DATABASE.csv` SHA-256 is `5e07dcdc7fa85e0f157d62de87436eef2e1f83f1c9c80f4ef77aa8133c1144f0`.

Therefore the existing local predictive manifest is stale relative to the current database. The hosted R2 objects have their own object ETags but do not expose the local input-hash manifest, so live-to-local equivalence is not proven. Do not treat the existing database, local model output, or hosted output as a newly verified canonical rebuild.

## Safe next sequence

1. Parse and validate the newly retained official reports into per-report-year canonical rows, including the dedicated 2018 legacy-layout parser and the 2020 canonical gap.
2. Rebuild `draw_results_long.csv` only from those canonical yearly files; preserve row-level source lineage and exclude non-scorable/reference rows.
3. Rebuild the current reference database reproducibly from declared official inputs, including its row-level provenance, rather than manually patching it.
4. Materialize engines into an isolated output directory, freeze its input hashes, and score only against following-year official actuals.
5. Reconcile duplicate prediction keys and missing actual/engine keys before any production promotion.
6. Publish to R2 only after a separately authorized, successful certification run.
