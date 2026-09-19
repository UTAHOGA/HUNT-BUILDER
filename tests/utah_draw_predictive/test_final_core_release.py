import importlib.util
from pathlib import Path

import pytest

from engine.utah_bonus_predictive.materialize import expand_collapsed_truth_rows_for_engine, _apply_current_target_design
from engine.utah_draw_predictive.preference_general_deer import _build_truth_ladders
from engine.utah_predictive_mixed.materialize import mixed_row, CORE_FINAL_PROBABILITY_DESIGNS
from engine.utah_predictive_mixed.models import BlendWeights


def test_canonical_expansion_preserves_deer_lanes_counts_and_ignores_hunt_totals():
    point = {
        "year": "2025", "actual_draw_year": "2025", "hunt_code": "DB1501",
        "hunt_name": "Box Elder", "species": "Deer", "sex_type": "Buck",
        "hunt_type": "General Season", "hunt_class": "GENERAL_SEASON_DEER",
        "draw_pool": "GENERAL_SEASON_DEER", "points": "0", "metric_scope": "total",
        "resident_eligible_applicants": "100", "resident_total_permits": "20",
        "resident_regular_permits": "20", "nonresident_eligible_applicants": "10",
        "nonresident_total_permits": "2", "nonresident_regular_permits": "2",
        "successful_applicants": "22", "eligible_applicants": "110", "total_permits": "22",
    }
    total = {**point, "points": "", "row_type": "HUNT_TOTAL"}
    raw = [point, total]
    direct, _, _ = _build_truth_ladders(raw, {2025})
    expanded, _, _ = _build_truth_ladders(expand_collapsed_truth_rows_for_engine(raw), {2025})
    assert direct == expanded
    assert len(expanded) == 2
    assert expanded[(2025, "DB1501", "adult_general_deer", "Resident")][0] == {"eligible": 100, "drawn": 20}
    assert expanded[(2025, "DB1501", "adult_general_deer", "Nonresident")][0] == {"eligible": 10, "drawn": 2}


def test_historical_only_antlerless_record_cannot_inherit_core_certification():
    rows = [{"hunt_code": "DA1006", "draw_system_type": "BONUS_LE_BIG_GAME", "p_draw": ".8"}]
    truth = [{"hunt_code": "DA1006", "actual_draw_year": "2017", "draw_system_type": "PREFERENCE_ANTLERLESS_DEER", "source_file": "17_antlerless_youth_points.pdf", "pdf_page": "7"}]
    database = [{"hunt_code": "DA1006", "draw_system_type": "PREFERENCE_ANTLERLESS_DEER", "NOTES": "PDF_CONFIRMED_TRUTH_ONLY_BACKFILL"}]
    result = _apply_current_target_design(rows, database, truth)[0]
    assert result["draw_system_type"] == "PREFERENCE_ANTLERLESS_DEER"
    assert result["status"] == "HISTORICAL_REFERENCE_ONLY"
    assert result["p_draw"] == ""
    assert result["source_file"] == truth[0]["source_file"]
    # Repeat after a family placeholder has been produced, as in the complete
    # runtime merge. The late family output must not undo the classification.
    placeholder = {"hunt_code": "DA1006", "draw_system_type": "BONUS_LE_BIG_GAME", "algorithm_status": "IN_SCOPE_MODEL_PENDING"}
    final = _apply_current_target_design([placeholder], database, truth, historical_only=True)[0]
    assert final["algorithm_status"] == "EXCLUDED_NOT_PREDICTIVE_DRAW"
    assert final["draw_system_type"] == "PREFERENCE_ANTLERLESS_DEER"


def test_current_deer_residency_does_not_reuse_last_year_winner_counts():
    from engine.utah_draw_predictive.preference_general_deer import _official_quota_for_residency
    target = {"draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER", "permits_2026_total": "1160",
              "permits_2025_res": "876", "permits_2025_nr": "42", "permits_2025_total": "918"}
    assert _official_quota_for_residency(target, "Resident", 2026, source_year=2025)[0] is None
    assert _official_quota_for_residency(target, "Nonresident", 2026, source_year=2025)[0] is None
    proxy = {**target, "target_permits_total": "918", "target_permits_res": "876", "target_permits_nr": "42"}
    assert _official_quota_for_residency(proxy, "Nonresident", 2026, source_year=2025)[0] == 42


@pytest.mark.parametrize("design", sorted(CORE_FINAL_PROBABILITY_DESIGNS))
def test_final_core_probability_preserves_family_across_prior_awards_and_harvest(design):
    row = {"hunt_code": "TEST", "residency": "Nonresident", "points": "5", "draw_system_type": design,
           "algorithm_status": "MODELED_PREFERENCE" if design.startswith("PREFERENCE") else "MODELED_BONUS",
           "p_draw": ".17", "p_draw_mean": ".17", "p_preference_draw": ".17",
           "public_permits_2025": "10", "permits_2026_nr": "20", "permits_2026_total": "100"}
    for awards in [0, 1, 10]:
        prior = {"eligible_applicants": "10", "total_permits": str(awards), "regular_permits": str(awards)}
        out = mixed_row(row, prior, {"demand_pressure_signal": "100"}, BlendWeights())
        assert out["p_draw"] == out["p_draw_mean"] == "0.170000"
        assert out["p_draw_pct"] == "17.000"


def test_blank_residency_is_never_defaulted_or_published():
    path = Path(__file__).resolve().parents[2] / "scripts/build_certified_research_contract_candidate.py"
    spec = importlib.util.spec_from_file_location("contract_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.residency("") == ""
    assert module.residency("All") == ""
    with pytest.raises(ValueError, match="explicit residency"):
        module.sanitize_public_row({"hunt_code": "DB1501", "residency": "", "certified_p_draw": ".5"})
    base = {"hunt_code": "DB1501", "residency": "Resident", "certified_p_draw": ".9", "prediction_certification_status": "CERTIFIED", "permits_2026_res": "12"}
    cleared = module.clear_retained_prediction_authority(base)
    assert "certified_p_draw" not in cleared
    assert cleared["permits_2026_res"] == "12"
    assert module.merge_row(base, {"certified_p_draw": "", "prediction_certification_status": "INSUFFICIENT_EVIDENCE"})["certified_p_draw"] == ""


def test_full_population_release_rejects_failed_design_and_stale_certification():
    from scripts.build_certified_research_contract_release_manifest import CORE_RELEASE_DESIGNS, certification_alignment_failures
    registry = {"registry_id": "new", "families": {d: {"certification_status": "CERTIFIED"} for d in CORE_RELEASE_DESIGNS}}
    row = {"hunt_code": "DB1501", "residency": "Resident", "points": "0",
           "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER", "certified_p_draw": "0.4",
           "prediction_certification_registry_id": "new"}
    assert certification_alignment_failures([row], registry) == []
    registry["families"][row["draw_system_type"]]["certification_status"] = "EXPERIMENTAL_NOT_CERTIFIED"
    errors = certification_alignment_failures([row], registry)
    assert any(e.startswith("CORE_DESIGN_NOT_CERTIFIED") for e in errors)
    assert any(e.startswith("UNCERTIFIED_PUBLIC_PROBABILITY") for e in errors)
    registry["families"][row["draw_system_type"]]["certification_status"] = "CERTIFIED"
    row["prediction_certification_registry_id"] = "old"
    assert any(e.startswith("STALE_CERTIFICATION_REGISTRY") for e in certification_alignment_failures([row], registry))


def test_current_deer_regular_quota_context_never_reads_winners_or_rewrites_board_total(tmp_path):
    import json
    from engine.utah.current_year_allotments import apply_official_general_deer_regular_quotas
    source = tmp_path / "official.json"
    hunt = {"HuntCode": "DB1502", "HuntName": "Cache", "HuntCategoryName": "General-Season",
            "SeasonWeapons": [{"LicenseYear": 2026, "WeaponName": "Archery",
                               "SeasonStartDate": "2026-08-15", "SeasonEndDate": "2026-09-11"}],
            "ResidentRegularRoundQuota": 647, "NonResidentRegularRoundQuota": 72,
            "RegularRoundQuota": 719, "OddsList": "NOT_TO_BE_READ"}
    source.write_text(json.dumps({"Status": 0, "Data": [hunt]}))
    target = {"hunt_code": "DB1502", "hunt_name": "Cache", "species": "Deer", "sex_type": "Buck",
              "weapon": "Archery", "season": "Aug 15 2026 - Sep 11 2026", "permits_2026_total": "1160"}
    rows, evidence = apply_official_general_deer_regular_quotas([target], source, 2026)
    assert evidence["matched_hunts"] == 1
    assert rows[0]["permits_2026_total"] == target["permits_2026_total"] == "1160"
    assert rows[0]["target_permits_res"] == "647"
    assert rows[0]["target_permits_nr"] == "72"
    with pytest.raises(ValueError, match="identity mismatch"):
        apply_official_general_deer_regular_quotas([target], source, 2025)
    with pytest.raises(ValueError, match="identity mismatch"):
        apply_official_general_deer_regular_quotas([{**target, "hunt_name": "Different unit"}], source, 2026)
    with pytest.raises(ValueError, match="identity mismatch"):
        apply_official_general_deer_regular_quotas([{**target, "season": ""}], source, 2026)
    with pytest.raises(ValueError, match="absent from target inventory"):
        apply_official_general_deer_regular_quotas([], source, 2026)


def test_missing_deer_regular_quota_is_withheld_for_both_residencies_not_zero():
    from engine.utah_draw_predictive.preference_general_deer import build_preference_general_deer_predictions
    target = {"hunt_code": "DB1502", "hunt_name": "Cache", "species": "Deer", "sex_type": "Buck",
              "hunt_type": "General Season", "permits_2026_total": "1160"}
    history = [{**target, "year": "2025", "draw_pool": "standard", "residency": lane,
                "points": "0", "eligible_applicants": "100", "total_permits": "50"}
               for lane in ["Resident", "Nonresident"]]
    rows = build_preference_general_deer_predictions(history, [target], 2026, [2025])
    assert {r["residency"] for r in rows} == {"Resident", "Nonresident"}
    assert all(r["p_draw"] == "" and r["status"] == "WITHHELD_NO_CURRENT_PERMIT_ALLOCATION" for r in rows)


def test_independent_coverage_gate_catches_missing_nonresident_lane(tmp_path):
    from scripts.audit_core_prediction_coverage import audit
    target = {"hunt_code": "DB1501", "hunt_name": "Box Elder", "species": "Deer", "sex_type": "Buck",
              "hunt_type": "General Season", "hunt_class": "Public", "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
              "permits_2026_res": "90", "permits_2026_nr": "10", "permits_2026_total": "100"}
    source = {"hunt_code": "DB1501", "actual_draw_year": "2025", "points": "0",
              "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER", "resident_eligible_applicants": "100",
              "resident_total_permits": "90", "nonresident_eligible_applicants": "20", "nonresident_total_permits": "10"}
    predictions = [{"hunt_code": "DB1501", "residency": lane, "points": str(point),
                    "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER", "p_draw": ".5"}
                   for lane in ["Resident", "Nonresident"] for point in [0, 1]]
    assert audit([target], predictions, [source])["status"] == "PASS"
    missing = audit([target], [row for row in predictions if row["residency"] == "Resident"], [source])
    assert missing["status"] == "FAIL"
    assert "BLOCKED_MISSING_FORECAST:DB1501:Nonresident" in missing["failures"]
    missing_detail = audit([target], predictions, [source], details_dir=tmp_path)
    assert missing_detail["status"] == "FAIL"
    assert all("MISSING_DETAIL_FILE" in row["public_detail_missing_points"] for row in missing_detail["inventory"])
