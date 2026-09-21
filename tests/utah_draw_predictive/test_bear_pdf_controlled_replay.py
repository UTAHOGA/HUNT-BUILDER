"""Historical PDF replay must not consume 2026 successor identities."""
import pytest

from engine.utah_draw_predictive import bear


def lane(code, year=2020):
    return {
        "hunt_code": code, "hunt_name": "La Sal - Any Legal Weapon",
        "species": "Black Bear", "actual_draw_year": str(year),
        "draw_pool": "LIMITED_ENTRY_BEAR_HUNT", "record_type": "point_level_draw_result",
        "residency": "Resident", "metric_scope": "resident", "points": "0",
        "eligible_applicants": "10", "bonus_permits": "1", "regular_permits": "1", "total_permits": "2",
        "bear_source_classification": "TRUE_BEAR_BONUS_DRAW",
        "bear_source_identity_source": "RETAINED_OFFICIAL_BLACK_BEAR_PDF",
        "source_file": f"pipeline/RAW/hunt_unit_database/{year}/pdf/draw_odds/official_dwr_archive/black_bear/{str(year)[2:]}_drawing_odds.pdf",
        "qa_status": "OFFICIAL_PDF_RESIDENCY_LANE_PROJECTED",
    }


@pytest.mark.parametrize("code", ["BR7008", "BR7108", "BR7208", "BR7307"])
def test_2026_successors_do_not_delete_historical_hunts(monkeypatch, code):
    def forbidden(*args, **kwargs):
        raise AssertionError("Historical PDF replay read a later report")

    monkeypatch.setattr(bear, "official_bear_draw_odds_hunt_codes", forbidden)
    row = lane(code)
    target = {**row, "permits_2020_res": "2", "permits_2020_nr": "0", "permits_2020_total": "2"}
    predictions, report = bear.build_bear_bonus_predictions([row], [target], 2021, [2020])
    assert {item["hunt_code"] for item in predictions} == {code}
    assert report["historical_successor_current_rows_skipped"] == 0


def test_2026_old_public_codes_still_do_not_double_feed_current_hunts():
    row = lane("BR7008", 2025)
    predictions, report = bear.build_bear_bonus_predictions([row], [row], 2026, [2025])
    assert predictions == []
    assert report["historical_successor_current_rows_skipped"] == 1


@pytest.mark.parametrize("code", sorted(bear.BEAR_SPLIT_HISTORY_START))
def test_split_hunts_cannot_inherit_parent_or_misdated_exact_code_history(code):
    rows = [lane(parent, 2025) for parent in bear.BEAR_HISTORICAL_CODE_SUCCESSORS_2026]
    rows.append(lane(code, 2025))  # Even an erroneously backfilled new code is rejected.
    target = {**lane(code, 2026), "permits_2026_res": "2", "permits_2026_nr": "2"}
    output, _ = bear.build_bear_bonus_predictions(rows, [target], 2026, [2025])
    assert len(output) == 2
    for row in output:
        assert row["p_draw"] == ""
        assert row["history_hunt_code"] == code
        assert row["source_years_used"] == ""
        assert "SPLIT_UNIT_POST_EFFECTIVE_HISTORY_REQUIRED" in row["data_quality_flags"]


def test_post_split_forecast_is_invariant_to_all_pre_split_demand():
    post = [lane("BR7022", 2026)]
    target = {**post[0], "permits_2026_res": "2", "permits_2026_nr": "0"}
    first, _ = bear.build_bear_bonus_predictions(post, [target], 2027, [2026])
    old = [{**lane("BR7008", year), "eligible_applicants": str(year * 100)} for year in (2023, 2024, 2025)]
    second, _ = bear.build_bear_bonus_predictions(old + post, [target], 2027, [2023, 2024, 2025, 2026])
    assert first == second
    assert all(r["source_years_used"] == "2026" for r in second if r["residency"] == "Resident")


def test_rounded_empty_cell_does_not_mean_zero_conditional_draw_chance():
    source = {**lane("BR7000"), "points": "5", "eligible_applicants": "2", "bonus_permits": "2", "regular_permits": "0"}
    target = {**source, "permits_2020_res": "2", "permits_2020_nr": "0"}
    rows, _ = bear.build_bear_bonus_predictions([source], [target], 2021, [2020])
    row = next(r for r in rows if r["residency"] == "Resident" and r["points"] == "6")
    assert float(row["p_draw"]) > 0


def test_absent_cohort_has_reasoned_blank_not_invented_odds():
    source = lane("BR7000")
    empty = {**source, "points": "19", "eligible_applicants": "0", "bonus_permits": "0", "regular_permits": "0", "total_permits": "0"}
    target = {**source, "permits_2020_res": "2", "permits_2020_nr": "0"}
    rows, _ = bear.build_bear_bonus_predictions([source, empty], [target], 2021, [2020])
    row = next(r for r in rows if r["residency"] == "Resident" and r["points"] == "20")
    assert row["p_draw"] == ""
    assert row["algorithm_status"] == "NO_TRANSITION_EVIDENCE"
    assert max(int(r["points"]) for r in rows if r["points"] != "") <= 20


@pytest.mark.parametrize("subtype", [bear.LIMITED_ENTRY_BEAR_HUNT, bear.RESTRICTED_BEAR_PURSUIT])
@pytest.mark.parametrize("probability", ["", "0", "0.2", "0.99"])
def test_final_bear_probability_cannot_be_raised_by_prior_winners_or_harvest(subtype, probability):
    from engine.utah_predictive_mixed.materialize import mixed_row
    from engine.utah_predictive_mixed.models import BlendWeights
    row = {"hunt_code": "BR7000", "residency": "Resident", "points": "5", "draw_system_type": "BEAR_DRAW",
           "bear_draw_subtype": subtype, "p_draw": probability,
           "algorithm_status": "MODELED_BONUS" if probability else "NO_TRANSITION_EVIDENCE",
           "public_permits_2026": "5", "quota_2026_total": "5", "public_permits_2025": "5"}
    output = mixed_row(row, {"eligible_applicants": "1", "total_permits": "1", "regular_permits": "1"},
                       {"harvest_quality_index": "100", "demand_pressure_signal": "1"}, BlendWeights())
    assert output["p_draw"] == (f"{float(probability):.6f}" if probability else "")
    assert output["final_probability_contract"] == "BEAR_FAMILY_MECHANICS_PRESERVED_V1"


def test_historical_final_quota_metadata_does_not_claim_current_database():
    from engine.utah_predictive_mixed.quota import quota_for_row
    result, reasons = quota_for_row({"quota_2026_total": "2", "quota_source_year": "2020",
                                    "quota_source_file": "2020_official.pdf",
                                    "quota_source_type": "SOURCE_YEAR_OFFICIAL_DRAW_RESULT_PERMIT_PROXY"})
    assert result["quota_source_year"] == "2020"
    assert result["quota_source_file"] == "2020_official.pdf"
    assert not any("DATABASE" in r for r in reasons)


def test_cumulative_candidate_uses_only_same_identity_and_separate_residency():
    key = (bear.LIMITED_ENTRY_BEAR_HUNT, 2020, "BR7000", "Resident")
    ladders = {key: {0: {"eligible": 10, "total": 2}, 1: {"eligible": 4, "total": 1}}}
    first = bear._forecast_cumulative_stack(ladders, key[0], key[2], key[3])
    ladders[(key[0], 2020, key[2], "Nonresident")] = {0: {"eligible": 100000, "total": 10}}
    assert first == bear._forecast_cumulative_stack(ladders, key[0], key[2], key[3])
    assert all(n >= 0 for n in first.values())


def test_historical_program_change_cutoff_blocks_old_exact_code():
    source = lane("BR7000", 2020)
    target = {**source, "permits_2020_res": "2", "permits_2020_nr": "2", "bear_history_effective_start_year": 2021}
    output, _ = bear.build_bear_bonus_predictions([source], [target], 2021, [2020])
    assert all(r["p_draw"] == "" and r["source_years_used"] == "" for r in output)


def test_forecast_read_guard_blocks_database_and_target_results(monkeypatch, tmp_path):
    import sys
    from scripts.audit_bear_controlled_candidates import source_read_guard, ROOT
    hooks = []
    monkeypatch.setattr(sys, "addaudithook", hooks.append)
    source = ROOT / "audits/source_2020.csv"
    reads, _ = source_read_guard([source], tmp_path)
    hooks[0]("open", (str(source), "r", 0))
    assert len(reads) == 1
    for forbidden in (ROOT/"pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv", ROOT/"audits/target_2021.csv"):
        with pytest.raises(RuntimeError, match="unapproved/future"):
            hooks[0]("open", (str(forbidden), "r", 0))


def test_exact_code_scoring_never_loads_current_crosswalks(monkeypatch, tmp_path):
    from tools.prediction_accuracy_backtest import score_full_engine_draw_line_aware as scorer
    monkeypatch.setattr(scorer, "HUNT_CODE_CROSSWALK", {})
    monkeypatch.setattr(scorer, "ACTIVE_SCORING_HUNT_CODE_ALIASES", {})
    def empty_only(paths):
        assert paths == []
        return []
    monkeypatch.setattr(scorer, "crosswalk_files_from_dirs", empty_only)
    monkeypatch.setattr(scorer, "load_hunt_code_crosswalk", lambda paths: {} if empty_only(paths) == [] else None)
    monkeypatch.setattr(scorer, "read_csv", lambda path: (["official_score_key_v2"], []))
    monkeypatch.setattr(scorer, "run_official_score_key_v2_mode", lambda *args: {"status": "TEST"})
    args = scorer.parse_args(["--predictions", "unused.csv", "--truth", "unused.csv", "--output-dir", str(tmp_path),
                              "--source-year", "2020", "--target-year", "2021", "--exact-codes-only"])
    assert scorer.run(args) == {"status": "TEST"}
    assert scorer.ACTIVE_SCORING_HUNT_CODE_ALIASES == {}
