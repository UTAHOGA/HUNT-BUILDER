import csv
import json
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


REPO = Path(str(_repo_root()))
ML_PATH = REPO / "processed_data" / "ml_draw_predictions_v1.csv"
DRE_PATH = REPO / "processed_data" / "draw_reality_engine_predictive_v2.csv"
REVIEW_PATH = REPO / "processed_data" / "modeled_availability_review_report.json"
COVERAGE_PATH = REPO / "processed_data" / "draw_system_coverage_report.json"
MOUNTAIN_LION_REPORT_PATH = REPO / "processed_data" / "mountain_lion_availability_report.json"
BEAR_REPORT_PATH = REPO / "processed_data" / "bear_report.json"
GPT_REVIEW_PATH = REPO / "processed_data" / "gpt_work_review_report.json"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(value: object) -> str:
    return str(value or "").strip()


def _nonnull(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if _clean(row.get(field)))


def _availability_rows() -> list[dict[str, str]]:
    return [row for row in _read_csv(ML_PATH) if row.get("algorithm_status") == "MODELED_AVAILABILITY"]


def test_modeled_availability_rows_have_no_draw_probability_fields() -> None:
    rows = _availability_rows()
    assert rows
    for field in ("p_draw", "p_draw_pct", "p_preference_draw", "p_bonus_pool", "p_random_pool"):
        assert _nonnull(rows, field) == 0


def test_modeled_availability_rows_have_availability_signal() -> None:
    rows = _availability_rows()
    signal_fields = (
        "p_availability",
        "availability_pct",
        "availability_status",
        "permit_availability_type",
        "unit_status",
        "rule_status",
        "harvest_objective_status",
        "reason_codes",
    )
    assert all(any(_clean(row.get(field)) for field in signal_fields) for row in rows)


def test_modeled_availability_total_count_matches_report() -> None:
    rows = _availability_rows()
    review = _read_json(REVIEW_PATH)
    coverage = _read_json(COVERAGE_PATH)
    gpt_review = _read_json(GPT_REVIEW_PATH)
    assert len(rows) == review["total_MODELED_AVAILABILITY_rows"]
    assert len(rows) == coverage["modeled_availability"]["modeled_availability_total_row_count"]
    assert len(rows) == gpt_review["row_counts"]["MODELED_AVAILABILITY"]


def test_mountain_lion_availability_accounts_for_120_rows() -> None:
    rows = [row for row in _availability_rows() if row.get("draw_system_type") == "MOUNTAIN_LION_DRAW"]
    report = _read_json(MOUNTAIN_LION_REPORT_PATH)
    assert len(rows) == 120
    assert _nonnull(rows, "p_draw") == 0
    assert _nonnull(rows, "p_availability") == 120
    assert _nonnull(rows, "availability_pct") == 120
    assert report["modeled_availability_row_count"] == 120
    assert report["p_draw_non_null_count"] == 0
    assert report["p_availability_non_null_count"] == 120
    assert report["availability_pct_non_null_count"] == 120


def test_bear_availability_rows_are_not_draw_odds() -> None:
    rows = [row for row in _availability_rows() if row.get("draw_system_type") == "BEAR_DRAW"]
    report = _read_json(BEAR_REPORT_PATH)
    assert len(rows) == 4
    assert all(_clean(row.get("p_draw")) == "" for row in rows)
    assert all(_clean(row.get("p_bonus_pool")) == "" for row in rows)
    assert all(_clean(row.get("p_random_pool")) == "" for row in rows)
    assert all(_clean(row.get("p_preference_draw")) == "" for row in rows)
    assert sum(1 for row in rows if row.get("hunt_code") == "BR1001" and _clean(row.get("p_draw")) == "") == 2
    assert sum(1 for row in rows if row.get("hunt_code") == "BR1007" and _clean(row.get("p_draw")) == "") == 1
    assert sum(1 for row in rows if row.get("hunt_code") == "BR1018" and _clean(row.get("p_draw")) == "") == 1
    assert report["bear_rows_by_algorithm_status"]["MODELED_AVAILABILITY"] == 4
    assert report["harvest_objective_p_draw_non_null_count"] == 0
    assert report["unlimited_pursuit_permit_p_draw_non_null_count"] == 0


def test_other_modeled_availability_rows_are_explained() -> None:
    review = _read_json(REVIEW_PATH)
    other_count = review["other_availability_row_count"]
    detail = review["other_availability_rows_detail"]
    assert other_count == len(detail)
    if other_count:
        assert all(_clean(row.get("reason_codes")) for row in detail)
        assert all(
            _clean(row.get("availability_status"))
            or _clean(row.get("permit_availability_type"))
            or _clean(row.get("unit_status"))
            or _clean(row.get("rule_status"))
            for row in detail
        )


def test_modeled_availability_duplicate_key_count_zero() -> None:
    review = _read_json(REVIEW_PATH)
    assert review["duplicate_key_count"] == 0


def test_availability_rows_not_present_in_draw_odds_ui_as_probability() -> None:
    rows = [row for row in _read_csv(DRE_PATH) if row.get("algorithm_status") == "MODELED_AVAILABILITY"]
    assert rows
    assert _nonnull(rows, "p_draw") == 0
    assert _nonnull(rows, "p_draw_pct") == 0


def test_availability_report_written() -> None:
    assert REVIEW_PATH.exists()
    md_path = REPO / "processed_data" / "modeled_availability_review_report.md"
    assert md_path.exists()
    review = _read_json(REVIEW_PATH)
    assert review["total_MODELED_AVAILABILITY_rows"] >= 0
