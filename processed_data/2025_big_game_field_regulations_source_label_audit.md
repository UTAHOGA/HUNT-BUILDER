# 2025 Big Game Field Regulations Source Label Audit

Source PDF: `pipeline/RAW/hunt_unit_database/2025/pdf/regulation/field_regs 2025.pdf`

This audit locks the file identity as 2025 field regulations only. It does not promote the file into draw odds, harvest features, quota math, or prediction math.

## Summary

- Expected title: `2025 Utah Big Game Field Regulations`
- Expected source year: `2025`
- SHA-256: `05a87b5babd0a22af62c993bd3fe0ba106fb18f7029ed60fc75f6babe4dbdaa7`
- Library export status: `NOT_EXPORTED_TO_HUNTING_BIBLE`
- PDF pages: `68`
- Extracted text lines: `3723`
- Extracted number/date/citation tokens: `1483`
- Expected pasted-text checks: `50`
- Expected pasted-text failures: `0`
- Mislabeled 2026 manifest items: `0`
- Post-publication corrections captured: `7`
- Audit blockers: `0`

## Outputs

- Text lines: `data_truth/regulations_truth/normalized/2025_big_game_field_regulations_text_lines.csv`
- Number/date/citation tokens: `data_truth/regulations_truth/normalized/2025_big_game_field_regulations_number_tokens.csv`
- Pasted-text checks: `data_truth/regulations_truth/normalized/2025_big_game_field_regulations_expected_text_checks.csv`

## Checks

| check | status |
|---|---:|
| source_pdf_exists | PASS |
| source_path_is_2025_folder | PASS |
| source_hash_matches_expected | PASS |
| source_size_matches_expected | PASS |
| text_mentions_2025_field_regulations | PASS |
| text_does_not_identify_as_2026 | PASS |
| not_in_quality_raw_inventory | PASS |
| not_promoted_by_quality_or_draw_audit | PASS |
| no_2026_field_regulations_manifest_label | PASS |
