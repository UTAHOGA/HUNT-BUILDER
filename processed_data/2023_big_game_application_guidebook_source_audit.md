# 2023 Big Game Application Guidebook Source Audit

Source PDF: `pipeline/RAW/hunt_unit_database/2023/pdf/regulation/2023_biggameapp.pdf`

This audit locks the file identity as the revised May 2023 Big Game Application Guidebook. Hunt codes are extracted as application-guidebook reference rows only; this does not promote draw odds, harvest features, quota math, or prediction rows.

## Summary

- Expected title: `2023 Utah Big Game Application Guidebook`
- Expected source year: `2023`
- SHA-256: ``
- PDF pages: `0`
- Extracted text lines: `0`
- Extracted number/date/citation tokens: `0`
- Hunt-table reference rows: `0`
- Unique hunt codes: `0`
- Expected pasted-text checks: `66`
- Expected pasted-text failures: `66`
- Database reconciliation effect: `NO_DRAW_OR_PREDICTION_ROWS_PROMOTED`
- Audit blockers: `71`

## Outputs

- Text lines: `data_truth/regulations_truth/normalized/2023_big_game_application_guidebook_text_lines.csv`
- Number/date/citation tokens: `data_truth/regulations_truth/normalized/2023_big_game_application_guidebook_number_tokens.csv`
- Pasted-text checks: `data_truth/regulations_truth/normalized/2023_big_game_application_guidebook_expected_text_checks.csv`
- Hunt-table references: `data_truth/regulations_truth/normalized/2023_big_game_application_guidebook_hunt_tables.csv`

## Checks

| check | status |
|---|---:|
| source_pdf_exists | REVIEW |
| source_path_is_2023_folder | PASS |
| source_hash_matches_expected | REVIEW |
| source_size_matches_expected | REVIEW |
| text_mentions_2023_application_guidebook | REVIEW |
| text_mentions_revised_may_2023 | REVIEW |
| text_does_not_identify_as_draw_odds | PASS |
| not_promoted_by_quality_or_draw_audit | PASS |
