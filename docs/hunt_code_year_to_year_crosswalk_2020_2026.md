# Hunt Code Year-To-Year Crosswalk 2020-2026

## Purpose

This audit creates an adjacent year-to-year hunt-code crosswalk from the BIBLE HUNT CODES comprehensive evidence. It distinguishes exact code continuity from candidate successor links.

## Year Semantics

- `report_year` / `draw_year` is the year permits were drawn.
- `model_year` is `report_year + 1`.

## Key Counts

- Crosswalk rows: `6403`
- Candidate rows: `819`
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

- `ADDED_NO_PREDECESSOR_CANDIDATE`: `239`
- `CANDIDATE_SUCCESSOR_BY_IDENTITY`: `213`
- `DROPPED_NO_SUCCESSOR_CANDIDATE`: `356`
- `EXACT_CODE_RETAINED`: `5595`

## Transition Counts

- `2020->2021`: ADDED_NO_PREDECESSOR_CANDIDATE=43, CANDIDATE_SUCCESSOR_BY_IDENTITY=66, DROPPED_NO_SUCCESSOR_CANDIDATE=18, EXACT_CODE_RETAINED=944
- `2021->2022`: ADDED_NO_PREDECESSOR_CANDIDATE=30, CANDIDATE_SUCCESSOR_BY_IDENTITY=32, DROPPED_NO_SUCCESSOR_CANDIDATE=20, EXACT_CODE_RETAINED=971
- `2022->2023`: ADDED_NO_PREDECESSOR_CANDIDATE=58, CANDIDATE_SUCCESSOR_BY_IDENTITY=47, DROPPED_NO_SUCCESSOR_CANDIDATE=42, EXACT_CODE_RETAINED=931
- `2023->2024`: ADDED_NO_PREDECESSOR_CANDIDATE=23, CANDIDATE_SUCCESSOR_BY_IDENTITY=22, DROPPED_NO_SUCCESSOR_CANDIDATE=21, EXACT_CODE_RETAINED=980
- `2024->2025`: ADDED_NO_PREDECESSOR_CANDIDATE=60, CANDIDATE_SUCCESSOR_BY_IDENTITY=46, DROPPED_NO_SUCCESSOR_CANDIDATE=11, EXACT_CODE_RETAINED=960
- `2025->2026`: ADDED_NO_PREDECESSOR_CANDIDATE=25, DROPPED_NO_SUCCESSOR_CANDIDATE=244, EXACT_CODE_RETAINED=809

## Outputs

- `processed_data/audits/hunt_code_year_to_year_crosswalk_2020_2026.csv`
- `processed_data/audits/hunt_code_year_to_year_crosswalk_candidates_2020_2026.csv`
- `processed_data/audits/hunt_code_year_to_year_crosswalk_2020_2026_summary.json`
- `docs/hunt_code_year_to_year_crosswalk_2020_2026.md`

## Source Guardrails

- Artifact codes excluded from the crosswalk: `10`
- 2026 `DATABASE.csv` is used only as an identity reference for codes already observed in 2026 source hits; this audit does not promote or change permit values.

## Caution

Candidate successor rows are review evidence only. They are not promoted crosswalk truth until reviewed against official PDFs and family context.
