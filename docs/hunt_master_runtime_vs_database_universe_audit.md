# Hunt Master Runtime vs DATABASE Universe Audit

Generated: `2026-06-04T07:05:14+00:00`

## Current read path

`config.js` points the Builder entry-page hunt loader at `data/hunt-master-canonical-2026-foundation.json` first. `data.js` treats that source as authoritative and stops before the second source-of-truth candidate when the foundation file loads.

## Key counts

- `DATABASE.csv` unique hunt codes: `1471`
- Active current reconciliation unique hunt codes: `1470`
- Builder first-load foundation unique hunt codes: `1471`
- Builder second-candidate source-of-truth unique hunt codes: `1471`
- Retired ledger codes considered: `1`
- Active codes missing from Builder first-load foundation: `0`
- Research split-index extra codes not in DATABASE: `0`

## Source summaries

| Source | Role | Unique codes | Extra not in DATABASE | Active codes missing from source | Retired present |
|---|---:|---:|---:|---:|---:|
| DATABASE.csv | truth_current_database | 1471 | 0 | 0 | 1 |
| active_current_reconciliation | active_current_permit_union | 1470 | 0 | 0 | 0 |
| builder_runtime_foundation_json | active_builder_first_load | 1471 | 0 | 0 | 1 |
| builder_runtime_source_of_truth_json | builder_second_candidate_not_reached_if_foundation_loads | 1471 | 0 | 0 | 1 |
| processed_source_of_truth_json | processed_reference | 1471 | 0 | 0 | 1 |
| processed_source_of_truth_csv | processed_reference | 1471 | 0 | 0 | 1 |
| hard_copy_canonical_current_hunts | hard_copy_public_reference | 1449 | 0 | 22 | 1 |
| hunt_research_summary_json | research_summary_contract | 1471 | 0 | 0 | 1 |
| hunt_research_index_json | research_split_index | 1471 | 0 | 0 | 1 |
| dwr_hanumber_pull | dwr_popup_pull | 1449 | 0 | 22 | 1 |
| live_hunttable_comparison | dwr_hunttable_pull | 1471 | 0 | 0 | 1 |
| official_boundary_table_bighorn_sheep_hunt_table_official | official_boundary_table | 125 | 57 | scoped-table | 0 |
| official_boundary_table_bison_hunt_table_official | official_boundary_table | 42 | 22 | scoped-table | 0 |
| official_boundary_table_black_bear_hunt_table_official | official_boundary_table | 137 | 27 | scoped-table | 0 |
| official_boundary_table_cougar_hunt_table_official | official_boundary_table | 92 | 91 | scoped-table | 0 |
| official_boundary_table_elk_antlerless_hunt_table_official | official_boundary_table | 329 | 116 | scoped-table | 0 |
| official_boundary_table_elk_hunt_table_official | official_boundary_table | 350 | 1 | scoped-table | 0 |
| official_boundary_table_moose_hunt_table_official | official_boundary_table | 63 | 16 | scoped-table | 0 |
| official_boundary_table_mountain_goat_hunt_table_official | official_boundary_table | 24 | 6 | scoped-table | 0 |
| official_boundary_table_pronghorn_hunt_table_official | official_boundary_table | 180 | 51 | scoped-table | 1 |
| official_boundary_table_turkey_hunt_table_official | official_boundary_table | 25 | 7 | scoped-table | 0 |

## Active Builder foundation gaps

Family breakdown for the `0` active reconciliation codes missing from `data/hunt-master-canonical-2026-foundation.json`: none.

Codes: `none`

## Oversized Research split-index extras

`processed_data/hunt_research_2026_split/hunt_research_2026.index.json` contains `0` codes not in `DATABASE.csv`.
Family breakdown: none.

First examples: `none`

## Builder fallback source-of-truth extras

`data/hunt-master-canonical-2026-source-of-truth.json` contains `0` code(s) not in `DATABASE.csv`: `none`.

## Interpretation

- If the online Builder appears to load a different universe than `DATABASE.csv`, the first file to check is `data/hunt-master-canonical-2026-foundation.json`, because that is the active first-load Builder master.
- `data/hunt-master-canonical-2026-source-of-truth.json` may be more current, but it is currently a fallback and is not reached when the foundation file succeeds.
- Extra source rows are not automatically current truth. They need to be checked against the active reconciliation, retired ledger, and current DWR pulls before promotion.

## Outputs

- Audit CSV: `processed_data\audits\hunt_master_runtime_vs_database_universe_audit.csv`
- Summary JSON: `processed_data\audits\hunt_master_runtime_vs_database_universe_summary.json`
