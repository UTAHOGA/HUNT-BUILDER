# Hunt Code Year-To-Year Crosswalk 2020-2026

## Purpose

This audit creates an adjacent year-to-year hunt-code crosswalk from the BIBLE HUNT CODES comprehensive evidence. It distinguishes exact code continuity from candidate successor links.

## Year Semantics

- `report_year` / `draw_year` is the year permits were drawn.
- `model_year` is `report_year + 1`.

## Key Counts

- Crosswalk rows: `6406`
- Candidate rows: `804`
- Reviewed 2020->2021 discontinued/no-successor rows: `17`
- Reviewed 2020->2021 cougar active-continuity rows: `4`
- Reviewed 2020->2021 exact-code boundary-change rows: `2`
- Reviewed 2021->2022 bear successor rows: `8`
- Reviewed 2021->2022 identity/boundary successor rows: `3`
- Reviewed 2021->2022 antlerless successor rows: `3`
- Reviewed 2021->2022 antlerless discontinued/no-successor rows: `6`
- Reviewed 2021->2022 cougar active-continuity rows: `1`
- Reviewed 2021->2022 source-artifact rows: `2`
- Reviewed 2021->2022 name-crosswalk rows: `1`
- Reviewed 2022->2023 sportsman active-continuity rows: `10`
- Reviewed 2022->2023 cougar statewide/unlimited rows: `1`
- Reviewed 2024->2025 guidebook-reference/not-draw-result rows: `2`
- Candidate rows list up to five same-prefix successor candidates per dropped code; they are not promoted one-to-one links.

## Codes By Report Year

- `2020`: `1028`
- `2021`: `1023`
- `2022`: `1020`
- `2023`: `1023`
- `2024`: `1017`
- `2025`: `1053`
- `2026`: `834`

## Status Counts

- `ADDED_NO_PREDECESSOR_CANDIDATE`: `242`
- `CANDIDATE_SUCCESSOR_BY_IDENTITY`: `207`
- `DROPPED_NO_SUCCESSOR_CANDIDATE`: `307`
- `EXACT_CODE_RETAINED`: `5595`
- `REVIEWED_2021_COUGAR_ACTIVE_CONTINUITY`: `4`
- `REVIEWED_2022_COUGAR_ACTIVE_CONTINUITY`: `1`
- `REVIEWED_COUGAR_ROLLS_TO_STATEWIDE_UNLIMITED`: `1`
- `REVIEWED_DISCONTINUED_AFTER_2020_NO_SUCCESSOR`: `17`
- `REVIEWED_EXACT_CODE_RETAINED_WITH_2021_BOUNDARY_CHANGE`: `2`
- `REVIEWED_DISCONTINUED_AFTER_2021_NO_2022_ANTLERLESS_SUCCESSOR`: `6`
- `REVIEWED_SOURCE_YEAR_ARTIFACT_NOT_TRUE_DROP`: `2`
- `REVIEWED_2022_NAME_CROSSWALK_FORMERLY_TJ_CATTLE`: `1`
- `REVIEWED_SPORTSMAN_ACTIVE_CONTINUITY`: `10`
- `REVIEWED_SUCCESSOR_BY_2022_ANTLERLESS_DRAW_RESULTS`: `3`
- `REVIEWED_SUCCESSOR_BY_2022_BEAR_GUIDE`: `8`
- `REVIEWED_SUCCESSOR_BY_IDENTITY_AND_BOUNDARY`: `3`

## Transition Counts

- `2020->2021`: ADDED_NO_PREDECESSOR_CANDIDATE=46, CANDIDATE_SUCCESSOR_BY_IDENTITY=63, EXACT_CODE_RETAINED=944, REVIEWED_2021_COUGAR_ACTIVE_CONTINUITY=4, REVIEWED_DISCONTINUED_AFTER_2020_NO_SUCCESSOR=17, REVIEWED_EXACT_CODE_RETAINED_WITH_2021_BOUNDARY_CHANGE=2
- `2021->2022`: ADDED_NO_PREDECESSOR_CANDIDATE=30, CANDIDATE_SUCCESSOR_BY_IDENTITY=29, EXACT_CODE_RETAINED=971, REVIEWED_2022_COUGAR_ACTIVE_CONTINUITY=1, REVIEWED_DISCONTINUED_AFTER_2021_NO_2022_ANTLERLESS_SUCCESSOR=6, REVIEWED_SOURCE_YEAR_ARTIFACT_NOT_TRUE_DROP=2, REVIEWED_2022_NAME_CROSSWALK_FORMERLY_TJ_CATTLE=1, REVIEWED_SUCCESSOR_BY_2022_ANTLERLESS_DRAW_RESULTS=3, REVIEWED_SUCCESSOR_BY_2022_BEAR_GUIDE=8, REVIEWED_SUCCESSOR_BY_IDENTITY_AND_BOUNDARY=3
- `2022->2023`: ADDED_NO_PREDECESSOR_CANDIDATE=58, CANDIDATE_SUCCESSOR_BY_IDENTITY=47, DROPPED_NO_SUCCESSOR_CANDIDATE=31, EXACT_CODE_RETAINED=931, REVIEWED_COUGAR_ROLLS_TO_STATEWIDE_UNLIMITED=1, REVIEWED_SPORTSMAN_ACTIVE_CONTINUITY=10
- `2023->2024`: ADDED_NO_PREDECESSOR_CANDIDATE=23, CANDIDATE_SUCCESSOR_BY_IDENTITY=22, DROPPED_NO_SUCCESSOR_CANDIDATE=21, EXACT_CODE_RETAINED=980
- `2024->2025`: ADDED_NO_PREDECESSOR_CANDIDATE=60, CANDIDATE_SUCCESSOR_BY_IDENTITY=46, DROPPED_NO_SUCCESSOR_CANDIDATE=11, EXACT_CODE_RETAINED=960
- `2025->2026`: ADDED_NO_PREDECESSOR_CANDIDATE=25, DROPPED_NO_SUCCESSOR_CANDIDATE=244, EXACT_CODE_RETAINED=809

## Outputs

- `processed_data/audits/hunt_code_year_to_year_crosswalk_2020_2026.csv`
- `processed_data/audits/hunt_code_year_to_year_crosswalk_candidates_2020_2026.csv`
- `processed_data/audits/hunt_code_year_to_year_reviewed_decisions_2020_to_2021.csv`
- `processed_data/audits/hunt_code_year_to_year_reviewed_decisions_2021_to_2022.csv`
- `processed_data/audits/hunt_code_year_to_year_reviewed_decisions_2022_to_2023.csv`
- `processed_data/audits/hunt_code_year_to_year_reviewed_decisions_2024_to_2025.csv`
- `processed_data/audits/hunt_code_year_to_year_crosswalk_2020_2026_summary.json`
- `docs/hunt_code_year_to_year_crosswalk_2020_2026.md`

## Source Guardrails

- Artifact codes excluded from the crosswalk: `10`
- 2026 `DATABASE.csv` is used only as an identity reference for codes already observed in 2026 source hits; this audit does not promote or change permit values.

## Locked Universe Count Contract

- Use `official_active_hunt_code_count` / `active_year_truth_codes` as the locked year hunt-code truth count.
- `DATABASE_NEXT_YEAR_PERMIT_SUPPORT` rows are retained only when confirmed by the following yearly canonical file. They do not count as active-year truth and do not feed active-year prediction accuracy.
- `DATABASE_NONSCORABLE_REFERENCE_APPENDIX` rows are lookup/review scaffolding only. They must not feed official current hunt-code counts, public odds, engine scoring, or prediction accuracy unless later promoted by same-year canonical, draw-result PDF, regulation/guidebook, or another approved DWR truth source.
- The full union ledger is an audit surface, not the official hunt-code count.

## Caution

Candidate successor rows are review evidence only. They are not promoted crosswalk truth until reviewed against official PDFs and family context.

Reviewed discontinuation rows are closure decisions, not successor mappings.

## 2021 Regulation Crosswalk Notes

- `RS6708` and `RS6709` are exact-code retained rows. The 2021 Big Game Application Guidebook marks both as boundary-change hunts, so they are reviewed as retained hunt codes with boundary changes, not old-code-to-new-code successors.
- `CG9999` appears in the 2021 Sportsman draw-results source as `Sportsman Cougar 2023*` with a one-time extra permit footnote. Existing reviewed crosswalk status remains `REVIEWED_SOURCE_YEAR_ARTIFACT_NOT_TRUE_DROP`; it should not inflate active 2021 hunt-code truth.

## 2022 Regulation Crosswalk Notes

- `DB1339` is listed in the 2022 Big Game Application Guidebook as `Double J Valley (formerly TJ Cattle)`. This is recorded as a name-crosswalk/reference note, not as a promoted old-code-to-new-code successor. The candidate `DB1210 -> DB1339` remains candidate-only unless additional official code-successor evidence is found.

## 2025 Regulation Crosswalk Notes

- `DB1109` is listed in the 2025 Big Game Application Guidebook as `Thousand Lakes (new)` under the new restricted multiseason hunt section. It is absent from the current 2025 draw-result PDFs, canonical yearly file, and long file, so the 2025 lock retains it as active-year guidebook reference only and excludes it from 2025 prediction accuracy/scorable rows unless later canonicalized.
- `EB3168` is listed in the 2025 Big Game Application Guidebook as `Cache, Meadowville` under late-season archery hunts. It is absent from the current 2025 draw-result PDFs, canonical yearly file, and long file, so the 2025 lock retains it as active-year guidebook reference only and excludes it from 2025 prediction accuracy/scorable rows unless later canonicalized.
