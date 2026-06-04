# Hunt Code Year-To-Year Crosswalk 2020-2026

## Purpose

This audit creates an adjacent year-to-year hunt-code crosswalk from the BIBLE HUNT CODES comprehensive evidence. It distinguishes exact code continuity from candidate successor links.

## Year Semantics

- `report_year` / `draw_year` is the year permits were drawn.
- `model_year` is `report_year + 1`.

## Key Counts

- Crosswalk rows: `6406`
- Candidate rows: `816`
- Reviewed 2020->2021 discontinued/no-successor rows: `17`
- Reviewed 2020->2021 cougar active-continuity rows: `4`
- Reviewed 2021->2022 bear successor rows: `8`
- Reviewed 2021->2022 antlerless successor rows: `3`
- Reviewed 2021->2022 antlerless discontinued/no-successor rows: `6`
- Reviewed 2021->2022 cougar active-continuity rows: `1`
- Reviewed 2021->2022 source-artifact rows: `2`
- Reviewed 2022->2023 sportsman active-continuity rows: `10`
- Reviewed 2022->2023 cougar statewide/unlimited rows: `1`
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
- `CANDIDATE_SUCCESSOR_BY_IDENTITY`: `210`
- `DROPPED_NO_SUCCESSOR_CANDIDATE`: `307`
- `EXACT_CODE_RETAINED`: `5595`
- `REVIEWED_2021_COUGAR_ACTIVE_CONTINUITY`: `4`
- `REVIEWED_2022_COUGAR_ACTIVE_CONTINUITY`: `1`
- `REVIEWED_COUGAR_ROLLS_TO_STATEWIDE_UNLIMITED`: `1`
- `REVIEWED_DISCONTINUED_AFTER_2020_NO_SUCCESSOR`: `17`
- `REVIEWED_DISCONTINUED_AFTER_2021_NO_2022_ANTLERLESS_SUCCESSOR`: `6`
- `REVIEWED_SOURCE_YEAR_ARTIFACT_NOT_TRUE_DROP`: `2`
- `REVIEWED_SPORTSMAN_ACTIVE_CONTINUITY`: `10`
- `REVIEWED_SUCCESSOR_BY_2022_ANTLERLESS_DRAW_RESULTS`: `3`
- `REVIEWED_SUCCESSOR_BY_2022_BEAR_GUIDE`: `8`

## Transition Counts

- `2020->2021`: ADDED_NO_PREDECESSOR_CANDIDATE=46, CANDIDATE_SUCCESSOR_BY_IDENTITY=63, EXACT_CODE_RETAINED=944, REVIEWED_2021_COUGAR_ACTIVE_CONTINUITY=4, REVIEWED_DISCONTINUED_AFTER_2020_NO_SUCCESSOR=17
- `2021->2022`: ADDED_NO_PREDECESSOR_CANDIDATE=30, CANDIDATE_SUCCESSOR_BY_IDENTITY=32, EXACT_CODE_RETAINED=971, REVIEWED_2022_COUGAR_ACTIVE_CONTINUITY=1, REVIEWED_DISCONTINUED_AFTER_2021_NO_2022_ANTLERLESS_SUCCESSOR=6, REVIEWED_SOURCE_YEAR_ARTIFACT_NOT_TRUE_DROP=2, REVIEWED_SUCCESSOR_BY_2022_ANTLERLESS_DRAW_RESULTS=3, REVIEWED_SUCCESSOR_BY_2022_BEAR_GUIDE=8
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
- `processed_data/audits/hunt_code_year_to_year_crosswalk_2020_2026_summary.json`
- `docs/hunt_code_year_to_year_crosswalk_2020_2026.md`

## Source Guardrails

- Artifact codes excluded from the crosswalk: `10`
- 2026 `DATABASE.csv` is used only as an identity reference for codes already observed in 2026 source hits; this audit does not promote or change permit values.

## Caution

Candidate successor rows are review evidence only. They are not promoted crosswalk truth until reviewed against official PDFs and family context.

Reviewed discontinuation rows are closure decisions, not successor mappings.
