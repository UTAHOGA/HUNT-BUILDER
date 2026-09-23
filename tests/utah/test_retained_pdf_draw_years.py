from scripts.audit_retained_pdf_draw_years import explicit_draw_years


def test_report_title_not_folder_or_publication_year():
    assert explicit_draw_years('2025 folder\n2024 Draw 7, Antlerless Draw Results\nPrinted 2026') == [2024]


def test_unknown_and_conflicting_titles_are_not_guessed():
    assert explicit_draw_years('2025 antlerless.pdf\nPublished 2026') == []
    assert explicit_draw_years('2024 Draw 7, Results\n2025 Draw 5, Results') == [2024, 2025]


def test_wrapped_title():
    assert explicit_draw_years('2024\nDraw\n7, Antlerless Draw Results') == [2024]
