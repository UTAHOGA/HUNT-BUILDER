# 2026 PDF Truth Rebuild Audit

This is an audit candidate only. No normalized truth file or master draw_results_long.csv file was modified.

- Source root: `C:\Users\tyler\Desktop\BIBLE HUNT CODES\2026\.pdf`
- PDF files found: 15 / 15
- Extracted rows: 30,298
- Unique hunt codes: 847
- Point rows: 29,564
- Point-purchase reference rows: 714
- Sportsman rows: 20
- Scorable rows: 30,298
- Zero-applicant rows retained: 12,552
- Duplicate point-key groups: 0

## PDF vs API Candidate

- PDF point rows: 29,564
- API point rows: 18,378
- Shared point keys: 18,325
- PDF-only point keys: 11,239
- API-only point keys: 53
- PDF-only zero-applicant rows: 11,202
- PDF-only nonzero-applicant rows: 37
- Shared value-difference rows: 18,188

The PDF-only rows are overwhelmingly legitimate zero-applicant ladder rows. Those rows should be retained in the yearly truth/ladder surface because they define the point ceiling even when no applicant exists at that point level.

The shared value differences are almost entirely `total_permits`. The API candidate appears to carry hunt-level total permits in that column, while the PDF row extraction carries the official row-level Total # Permits from the draw-results table. `total_drawn`/probability fields remain the safer scoring fields.

## Decision

PDF_DERIVED_CANDIDATE_CREATED_NOT_APPLIED

Recommended next move: build a normalized 2026 candidate from `2026_pdf_extracted_rows.csv`, keep POINT_PURCHASE_REFERENCE out of hunt-code keyed scoring, collapse/route SPORTSMAN_TOTAL as separate-lane random-only, and then replace the current 1,096-row placeholder only after the normalized candidate passes strict key and source-family gates.

## Outputs

- rows_csv: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_pdf_extracted_rows.csv`
- rows_xlsx: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_pdf_extracted_rows.xlsx`
- page_audit_csv: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_pdf_page_audit.csv`
- source_summary_csv: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_pdf_extraction_by_source_file.csv`
- family_summary_csv: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_pdf_extraction_by_family.csv`
- duplicate_keys_csv: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_pdf_duplicate_point_keys.csv`
- comparison_csv: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_pdf_vs_existing_candidates_summary.csv`
- report_md: `C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER\audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_PDF_TRUTH_REBUILD_REPORT.md`
- pdf_only: `audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_pdf_only_point_keys.csv`
- api_only: `audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_api_only_point_keys.csv`
- shared_diffs: `audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_pdf_api_shared_value_differences.csv`
