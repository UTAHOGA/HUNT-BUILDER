from pathlib import Path

from tools.audit_engine_feeders import audit_contract
from tools.engine_feeder_contract import ENGINE_FEEDERS, FeederContract, groups


def test_contract_includes_required_engine_groups() -> None:
    expected = {
        "utah_rebuild_fixtures",
        "utah_materialize_engine",
        "utah_bonus_predictive",
        "utah_bonus_predictive_skip_upstream",
        "utah_draw_predictive",
        "harvest_quality",
        "utah_predictive_mixed",
    }
    assert expected.issubset(set(groups()))
    assert len(ENGINE_FEEDERS) >= 50


def test_p_draw_pct_is_percent_not_probability_contract() -> None:
    for contract in ENGINE_FEEDERS:
        assert "p_draw_pct" not in contract.probability_columns
        if "p_draw_pct" in contract.required_columns or "p_draw_pct" in contract.percent_columns:
            assert "p_draw_pct" in contract.percent_columns


def test_missing_required_production_file_is_blocker(tmp_path: Path) -> None:
    contract = FeederContract(
        group="test",
        path="missing.csv",
        consumer_module="engine.test",
        required=True,
        production_blocker=True,
    )
    result = audit_contract(tmp_path, contract)
    assert result["status"] == "BLOCKER"
    assert result["blocker"] is True
    assert "missing_file" in result["issues"]


def test_csv_contract_reports_duplicates_ranges_and_nulls(tmp_path: Path) -> None:
    csv_path = tmp_path / "feed.csv"
    csv_path.write_text(
        "hunt_code,residency,points,p_draw,success_pct,count,source_file\n"
        "EB1,R,1,0.5,50,1,source.pdf\n"
        "EB1,R,1,1.5,101,-1,\n",
        encoding="utf-8",
    )
    contract = FeederContract(
        group="test",
        path="feed.csv",
        consumer_module="engine.test",
        primary_key=("hunt_code", "residency", "points"),
        required_columns=("hunt_code", "residency", "points", "p_draw"),
        critical_columns=("hunt_code", "residency", "points"),
        probability_columns=("p_draw",),
        percent_columns=("success_pct",),
        nonnegative_integer_columns=("count",),
        lineage_columns=("source_file",),
        generated=True,
    )
    result = audit_contract(tmp_path, contract)
    assert result["duplicate_key_count"] == 1
    assert result["invalid_probability_values"] == {"p_draw": 1}
    assert result["invalid_percent_values"] == {"success_pct": 1}
    assert result["invalid_nonnegative_integer_values"] == {"count": 1}
    assert result["null_lineage_fields"] == {"source_file": 1}
    assert result["status"] == "BLOCKER"
