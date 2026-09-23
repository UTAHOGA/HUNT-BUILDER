from scripts.audit_pipeline_annual_report_coverage import DRAW_TITLE, ReportIndex, unique_reports


def test_duplicate_official_link_is_one_report():
    index = ReportIndex('https://wildlife.utah.gov/biggame/odds')
    index.feed('<h2>2025</h2><h3>Youth</h3><a href="/pdf/a.pdf">Youth</a>'
               '<h3>Points</h3><a href="/pdf/a.pdf">Youth duplicate</a>')
    assert len(unique_reports(index.rows)) == 1
    assert index.rows[0]['scope_year'] == 2025


def test_cougar_season_is_separate_from_draw_calendar_year():
    index = ReportIndex('https://wildlife.utah.gov/odds')
    index.feed('<h2>Cougar</h2><h3>2022-23</h3><a href="/pdf/c.pdf">Odds</a>')
    assert index.rows[0]['index_period'] == '2022-23'
    assert index.rows[0]['scope_year'] == 2023
    assert 'draw_year' not in index.rows[0]


def test_excludes_out_of_scope_birds_and_keeps_split_bear_reports():
    index = ReportIndex('https://wildlife.utah.gov/odds')
    index.feed('<h2>Black bear</h2><h3>2017</h3><a href="/pdf/a.pdf">Odds</a>'
               '<a href="/pdf/b.pdf">Point rows</a>'
               '<h2>Tundra swan</h2><h3>2025</h3><a href="/pdf/c.pdf">Odds</a>')
    assert len(index.rows) == 2
    assert {r['family'] for r in index.rows} == {'Black bear'}


def test_report_year_not_guessed_from_filename_or_print_date():
    assert DRAW_TITLE.findall('2019 Draw T, Turkey\n2020 printing date') == ['2019']
    assert DRAW_TITLE.findall('2025 Draws 5 & 7, Point Purchase Results') == ['2025']
    assert DRAW_TITLE.findall('2025 filename.pdf\n2024 publication date') == []
