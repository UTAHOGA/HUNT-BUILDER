# 2023 Big Game Field Regulations Source Audit

Source PDF: `pipeline/RAW/hunt_unit_database/2023/pdf/regulation/2023_field_regs.pdf`

This audit locks the file identity as 2023 field regulations only. It does not promote the file into draw odds, harvest features, quota math, or prediction math.

## Summary

- Expected title: `2023 Utah Big Game Field Regulations`
- Expected source year: `2023`
- SHA-256: ``
- PDF pages: `0`
- Extracted text lines: `0`
- Extracted number/date/citation tokens: `0`
- Expected pasted-text checks: `69`
- Expected pasted-text failures: `69`
- Database reconciliation effect: `NO_DRAW_OR_PREDICTION_ROWS_PROMOTED`
- Audit blockers: `73`

## Outputs

- Text lines: `data_truth/regulations_truth/normalized/2023_big_game_field_regulations_text_lines.csv`
- Number/date/citation tokens: `data_truth/regulations_truth/normalized/2023_big_game_field_regulations_number_tokens.csv`
- Pasted-text checks: `data_truth/regulations_truth/normalized/2023_big_game_field_regulations_expected_text_checks.csv`

## Checks

| check | status |
|---|---:|
| source_pdf_exists | REVIEW |
| source_path_is_2023_folder | PASS |
| source_hash_matches_expected | REVIEW |
| source_size_matches_expected | REVIEW |
| text_mentions_2023_field_regulations | REVIEW |
| text_does_not_identify_as_draw_odds | PASS |
| raw_inventory_classifies_as_regulation_if_present | PASS |
| not_promoted_by_quality_or_draw_audit | PASS |
