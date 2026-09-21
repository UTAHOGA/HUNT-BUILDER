"""Owner-level foundation invariants, independent of an audit adapter."""
import pytest

from engine.utah_draw_predictive import bear
from tests.utah_draw_predictive.test_bear_pdf_controlled_replay import lane


def canonical(code="BR7000", program=bear.LIMITED_ENTRY_BEAR_HUNT):
    row = lane(code)
    for field in ("bear_source_classification", "bear_source_identity_source"):
        row.pop(field)
    row.update(residency="", metric_scope="total", source_scope="BLACK_BEAR",
               draw_pool=program, hunt_class=program, qa_status="SOURCE_TABLE_PARSED",
               extraction_status="OK", candidate_promotion_status="OFFICIAL_SOURCE_PARSED", pdf_page="12")
    for field in ("eligible_applicants", "bonus_permits", "regular_permits", "total_permits"):
        row[f"resident_{field}"] = row[field]
        row[f"nonresident_{field}"] = "0"
    return row


@pytest.mark.parametrize("program", sorted(bear.MODELED_BEAR_SUBTYPES))
def test_fresh_canonical_program_precedes_later_pdf(monkeypatch, program):
    monkeypatch.setattr(bear, "official_bear_draw_odds_hunt_codes", lambda: pytest.fail("Later PDF lookup"))
    row = canonical(program=program)
    assert bear.classify_bear_subtype(row) == program
    ladders, _, _ = bear._build_truth_ladders([row], {2020})
    assert set(k[3] for k in ladders) == {"Resident", "Nonresident"}


def test_explicit_pdf_lanes_still_require_reconciliation():
    row = canonical()
    row.update(qa_status="OFFICIAL_PDF_RESIDENCY_LANES_CANONICAL",
               bear_source_identity_source="CANONICAL_OFFICIAL_BLACK_BEAR_PDF",
               bear_source_classification="TRUE_BEAR_BONUS_DRAW", nonresident_total_permits="5")
    assert bear._canonical_official_bear_residency_lanes(row) == []


def test_2017_report_filename_does_not_erase_source_program(monkeypatch):
    row = canonical()
    row.update(actual_draw_year="2017", source_file="official_dwr_archive/black_bear/17_bonus_points.pdf",
               candidate_promotion_status="SOURCE_ONLY_CANONICAL_CANDIDATE_NOT_PROMOTED")
    monkeypatch.setattr(bear, "official_bear_draw_odds_hunt_codes", lambda: pytest.fail("Later PDF"))
    assert bear.classify_bear_subtype(row) == bear.LIMITED_ENTRY_BEAR_HUNT
    assert len(bear._canonical_official_bear_residency_lanes(row)) == 2


def test_historical_target_adapter_retains_source_program(monkeypatch):
    from engine.utah_draw_predictive.run_all_families import _historical_source_year_runtime_db_rows
    row = canonical()
    targets = _historical_source_year_runtime_db_rows([row], 2020)
    monkeypatch.setattr(bear, "official_bear_draw_odds_hunt_codes", lambda: pytest.fail("Later PDF"))
    assert len(targets) == 1
    assert bear.classify_bear_subtype(targets[0]) == bear.LIMITED_ENTRY_BEAR_HUNT


def test_combined_history_is_not_duplicated_into_two_residencies():
    source = dict(lane("BR7000"), residency="", metric_scope="total")
    target = dict(source, permits_2020_res="10", permits_2020_nr="10")
    rows, _ = bear.build_bear_bonus_predictions([source], [target], 2021, [2020])
    assert len(rows) == 2
    assert all(r["p_draw"] == "" and r["source_years_used"] == "" for r in rows)


def test_identical_point_duplicates_count_once():
    row = lane("BR7000")
    one = bear._build_truth_ladders([row], {2020})
    assert bear._build_truth_ladders([row, dict(row)], {2020}) == one


def test_conflicting_point_duplicates_fail():
    row = lane("BR7000")
    with pytest.raises(ValueError, match="Conflicting Bear point"):
        bear._build_truth_ladders([row, dict(row, eligible_applicants="11")], {2020})


def test_component_awards_must_reconcile():
    with pytest.raises(ValueError, match="Bear award components"):
        bear._build_truth_ladders([dict(lane("BR7000"), total_permits="3")], {2020})


def test_database_quota_cannot_override_source_awards(monkeypatch):
    monkeypatch.setattr(bear, "target_residency_permit_allocation", lambda *a, **kw: pytest.fail("Target quota read"))
    source = lane("BR7000")
    target = dict(source, permits_2026_res="999", target_permits_res="999", permits_2020_res="999")
    rows, report = bear.build_bear_bonus_predictions([source], [target], 2021, [2020])
    resident = [r for r in rows if r["residency"] == "Resident"]
    assert all(r["public_permits_target"] == 2 for r in resident)
    assert all(r["quota_source_type"] == "SOURCE_YEAR_CANONICAL_AWARDS_PROXY" for r in resident)
    assert all(r["quota_is_current_allocation"] == "FALSE" for r in resident)
    assert report["database_quota_used"] is False


def test_stale_lane_does_not_fill_missing_immediately_previous_year():
    source = lane("BR7000", 2019)
    rows, _ = bear.build_bear_bonus_predictions([source], [source], 2021, [2019, 2020])
    assert all(r["p_draw"] == "" for r in rows)
    assert "MISSING_SOURCE_YEAR_PROGRAM_RESIDENCY_LADDER" in rows[0]["reason_codes"]


def test_target_year_history_is_rejected():
    with pytest.raises(ValueError, match="before forecast year"):
        bear.build_bear_bonus_predictions([lane("BR7000", 2021)], [], 2021, [2021])


@pytest.mark.parametrize("code", sorted(bear.BEAR_SPLIT_HISTORY_START))
def test_split_status_and_forward_fields(code):
    target = lane(code, 2026)
    rows, _ = bear.build_bear_bonus_predictions([lane("BR7008", 2025)], [target], 2026, [2025])
    for row in rows:
        assert row["algorithm_status"] == "NO_TRANSITION_EVIDENCE"
        assert row["effective_split_year"] == 2026
        assert row["use_pre_split_history"] is False
        assert row["use_forward_from"] == 2026
        assert row["p_draw"] == ""
        assert "Split-unit effective 2026" in row["no_transition_reason"]
        assert row["public_permits_target"] == bear.BEAR_SPLIT_REFERENCE_TOTALS_2026[code]
        assert row["forecast_quota_proxy"] == ""
        from engine.utah_predictive_mixed.quota import quota_for_row
        assert quota_for_row(row)[0]["quota_2026_total"] == ""
        from engine.utah_draw_predictive.classifier import sanitize_modeled_probability_fields
        sanitized = sanitize_modeled_probability_fields(dict(row, p_draw_mean="0.8", certified_p_draw="0.8"))
        assert sanitized["algorithm_status"] == "NO_TRANSITION_EVIDENCE"
        assert sanitized["p_draw_mean"] == sanitized["certified_p_draw"] == ""
        assert sanitized["modeled_by_engine"] is False


def test_split_reference_totals_match_retained_crosswalk():
    import csv
    with (bear.REPO / "data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv").open(encoding="utf-8-sig") as stream:
        totals = {r["current_2026_code"]: int(r["permits_2026_total"]) for r in csv.DictReader(stream)
                  if r["current_2026_code"] in bear.BEAR_SPLIT_HISTORY_START}
    assert totals == bear.BEAR_SPLIT_REFERENCE_TOTALS_2026


def test_bonus_and_random_winners_both_leave_program_ladder():
    forecast = bear._forecast_applicant_ladder(
        {3: {"eligible": 10, "bonus": 2, "regular": 3, "total": 5}},
        {band: 1.0 for band in ("0", "1", "2_3", "4_5", "6_9", "10_plus")}, 1.0)
    assert forecast[4] == 5


def test_other_program_demand_and_hunting_point_purchases_do_not_change_pursuit():
    source = dict(lane("BR1008"), bear_source_classification="BEAR_PURSUIT_BONUS_DRAW",
                  draw_pool=bear.RESTRICTED_BEAR_PURSUIT)
    arrival = dict(source, actual_draw_year="2021", points="6")
    target = dict(arrival)
    history = [source, arrival]
    purchases = [{"actual_draw_year": "2020", "residency": "Resident", "points": "6",
                  "point_purchase_applicants": "1000000"}]
    ladders, _, _ = bear._build_truth_ladders(history, {2020, 2021})
    purchase_counts = bear._point_purchase_counts_by_year_residency(purchases, {2020, 2021})
    # The fixture would create an arrival profile if hunting purchases leaked
    # into pursuit calibration; it is not a test of an ignored input field.
    assert bear._build_source_calibrated_returning_tail_profiles(ladders, purchase_counts)
    options = dict(central_estimate_mode="simulation_mean", iterations=10,
                   returning_cohort_mode="source_calibrated_tail_mixture")
    first, _ = bear.build_bear_bonus_predictions(history, [target], 2022, [2020, 2021], **options)
    hunting = dict(lane("BR7000"), eligible_applicants="100000")
    second, _ = bear.build_bear_bonus_predictions(history + [hunting], [target], 2022, [2020, 2021],
                                                 point_purchase_rows=purchases, **options)
    assert first == second
