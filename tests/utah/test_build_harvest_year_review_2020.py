from scripts.build_harvest_year_review_2020 import build_biology, build_identity_audit, build_observations, read_csv, AGGREGATED_SOURCE


def test_2020_observations_preserve_adult_youth_rows_and_blanks() -> None:
    rows = build_observations()
    assert len(rows) == 976
    assert len({row["hunt_code"] for row in rows}) == 939
    assert sum(row["participant_class"] == "Adult" for row in rows) == 125
    assert sum(row["participant_class"] == "Youth" for row in rows) == 37

    db1530 = [row for row in rows if row["hunt_code"] == "DB1530"]
    assert {row["participant_class"] for row in db1530} == {"Adult", "Youth"}
    assert {row["permits"] for row in db1530} == {"228", "929"}

    no_data = [row for row in rows if row["parse_status"] == "OFFICIAL_PDF_NO_DATA_ROW"]
    assert len(no_data) == 6
    assert all(row["hunters_afield"] == "" for row in no_data)
    assert all(row["harvest_total"] == "" for row in no_data)
    assert all(row["percent_success"] == "" for row in no_data)


def test_2020_biology_is_unit_deduplicated_and_species_specific() -> None:
    rows = build_biology()
    assert len(rows) == 168
    assert len({row["deduplication_key"] for row in rows}) == len(rows)

    deer = next(
        row
        for row in rows
        if row["species"] == "Deer"
        and row["management_program"] == "General Season Public Land"
        and row["management_unit"] == "Beaver"
    )
    assert deer["metric"] == "Postseason buck-to-doe ratio"
    assert deer["metric_unit"] == "bucks per 100 does"
    assert deer["annual_observed_2020"] == "13"
    assert deer["three_year_average_2018_2020"] == "14.5"
    assert deer["management_objective_2020"] == "18-20"

    elk = next(row for row in rows if row["species"] == "Elk" and row["management_unit"] == "Beaver")
    assert elk["annual_observed_2020"] == "8.3"
    assert elk["three_year_average_2018_2020"] == "7.9"
    assert elk["management_objective_2020"] == "7.5-8.0"

    moose = next(row for row in rows if row["species"] == "Moose" and row["management_unit"] == "Cache")
    assert moose["annual_observed_2020"] == "4.2"
    assert moose["three_year_average_2018_2020"] == "4.7"


def test_2020_identity_audit_never_uses_boundary_id() -> None:
    aggregated = [row for row in read_csv(AGGREGATED_SOURCE) if row["reported_hunt_year"] == "2020"]
    audit = build_identity_audit(aggregated)
    assert len(audit) == 939
    assert all(row["match_keys_used"] == "hunt_code+hunt_name+species" for row in audit)
    assert all(row["boundary_id_used"] == "False" for row in audit)
    assert sum(row["match_status"] == "MATCHED_EXACT_CODE_NAME_SPECIES" for row in audit) == 918
