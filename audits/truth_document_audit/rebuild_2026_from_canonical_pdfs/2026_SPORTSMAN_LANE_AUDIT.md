# 2026 Sportsman Lane Audit

User-supplied Sportsman values were compared to the PDF-derived 2026 extraction.

- Sportsman codes expected: 10
- Resident PDF rows matched: 10
- Nonresident zero rows present in PDF extraction: 10
- Recommended route: SPORTSMAN_RANDOM_ONLY_SEPARATE_LANE
- Promotion note: do not route Sportsman rows through bonus/preference point math.

## Decision

SPORTSMAN_USER_VALUES_MATCH_PDF_EXTRACTION

The 10 resident Sportsman rows should be retained as Sportsman random-only lane records. The 10 nonresident zero rows should remain source-auditable but should not inflate ordinary scoring coverage.

- Audit CSV: `audits\truth_document_audit\rebuild_2026_from_canonical_pdfs\2026_sportsman_user_supplied_vs_pdf_audit.csv`
