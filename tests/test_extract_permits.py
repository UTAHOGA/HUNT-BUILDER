from scripts.extract_permits import HUNT_LINE_RE, normalize_text_lines, parse_hunt_line, parse_totals_line


def test_hunt_line_regex_finds_antlerless_deer_permit():
    line = "Hunt: DA1001 Antlerless Deer - Box Elder, West Bear River - Archery, Mzldr, Shotgn Only"

    match = HUNT_LINE_RE.match(line)

    assert match
    assert match.group("permit_number") == "DA1001"


def test_parse_hunt_line_splits_species_hunt_and_weapon():
    line = "Hunt: EA1010 Antlerless Elk - Cache - Any Legal Weapon"

    parsed = parse_hunt_line(line)

    assert parsed == ("EA1010", "Antlerless Elk", "Cache", "Any Legal Weapon")


def test_parse_hunt_line_removes_pdf_page_suffix_from_method():
    line = "Hunt: DB1000 Premium Le Archery Buck Deer - Henry Mtns - Archery Page 17"

    parsed = parse_hunt_line(line)

    assert parsed == (
        "DB1000",
        "Premium Le Archery Buck Deer",
        "Henry Mtns",
        "Archery",
    )


def test_parse_hunt_line_infers_general_deer_category_when_pdf_omits_it():
    line = "Hunt: DB1501 Box Elder - Archery Page 2"

    parsed = parse_hunt_line(line)

    assert parsed == ("DB1501", "Buck Deer", "Box Elder", "Archery")


def test_parse_hunt_line_handles_dash_attached_to_unit_name():
    line = "Hunt: DB1005 Premium Le Muzzleloader Buck Deer -Henr y Mtns - Muzzleloader Page 22"

    parsed = parse_hunt_line(line)

    assert parsed == (
        "DB1005",
        "Premium Le Muzzleloader Buck Deer",
        "Henr y Mtns",
        "Muzzleloader",
    )


def test_parse_hunt_line_does_not_parse_non_hunt_table_rows():
    line = "20 0 0 0 0 N/A 20 0 0 0 0 N/A"

    assert parse_hunt_line(line) is None


def test_normalize_text_lines_repairs_split_hunt_line():
    text = "\n".join(
        [
            "Hunt: DA1001 Antlerless Deer - Box Elder,",
            "West Bear River - Archery, Mzldr, Shotgn Only",
            "Resident Applicants",
            "20 0 0 0 0 N/A",
        ]
    )

    lines = normalize_text_lines(text)

    assert lines[0] == (
        "Hunt: DA1001 Antlerless Deer - Box Elder, "
        "West Bear River - Archery, Mzldr, Shotgn Only"
    )


def test_parse_totals_line_extracts_actual_permit_counts():
    line = "Totals 68 0 24 24 1 in 2.8 Totals 0 0 0 0 N/A"

    parsed = parse_totals_line(line)

    assert parsed["permits_res_bonus"] == 0
    assert parsed["permits_res_regular"] == 24
    assert parsed["permits_res_total"] == 24
    assert parsed["permits_nonres_bonus"] == 0
    assert parsed["permits_nonres_regular"] == 0
    assert parsed["permits_nonres_total"] == 0
    assert parsed["permits_total"] == 24
