import csv
import json
import math
from pathlib import Path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_phase11_sportsman_materialization_uses_official_odds_source() -> None:
    repo = Path(__file__).resolve().parents[2]
    csv_path = repo / "processed_data" / "sportsman_permit_predictions_v1.csv"
    report_path = repo / "processed_data" / "sportsman_permit_report.json"

    rows = _read_csv(csv_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert len(rows) == 10
    assert report["sportsman_source_year"] == 2025
    assert report["sportsman_rows_reviewed"] == 10
    assert report["sportsman_rows_modeled"] == 10
    assert report["sportsman_rows_pending"] == 0
    assert report["p_sportsman_draw_non_null_count"] == 10
    assert report["p_draw_non_null_count"] == 10
    assert report["p_draw_pct_non_null_count"] == 10
    assert report["p_bonus_pool_non_null_count"] == 0
    assert report["p_random_pool_non_null_count"] == 0
    assert report["p_preference_draw_non_null_count"] == 0
    assert any("sportsman" in str(path).lower() for path in report["source_files_used"])

    codes = {row["hunt_code"] for row in rows}
    assert codes == {"BI1000", "BR1000", "DB0007", "DS1000", "EB1000", "GO1000", "MB1000", "PB1000", "RS0001", "TK0001"}
    assert all(row["algorithm_status"] == "MODELED_SPORTSMAN_DRAW" for row in rows)
    assert all(row["residency"] == "Resident" for row in rows)
    assert all((row.get("p_bonus_pool") or "").strip() == "" for row in rows)
    assert all((row.get("p_random_pool") or "").strip() == "" for row in rows)
    assert all((row.get("p_preference_draw") or "").strip() == "" for row in rows)

    for row in rows:
        p_draw = float(row["p_draw"])
        p_sportsman_draw = float(row["p_sportsman_draw"])
        p_draw_pct = float(row["p_draw_pct"])
        assert math.isclose(p_draw, p_sportsman_draw, rel_tol=0.0, abs_tol=1e-9)
        assert math.isclose(p_draw_pct, p_draw * 100.0, rel_tol=0.0, abs_tol=1e-3)
