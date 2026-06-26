from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HUNT_MASTER = ROOT / "processed_data" / "hunt_master_enriched.csv"
SUMMARY = ROOT / "data_truth" / "comparison_outputs" / "validation" / "hunt_master_enriched_hunt_class_routing_2026_summary.json"


def read_rows() -> tuple[list[str], list[dict[str, str]]]:
    with HUNT_MASTER.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def rows_for(code: str) -> list[dict[str, str]]:
    _, rows = read_rows()
    return [row for row in rows if row.get("hunt_code") == code]


def test_main_enriched_carries_selection_and_routing_columns() -> None:
    fields, rows = read_rows()

    assert len(rows) == 53225
    assert len({row["hunt_code"] for row in rows if row.get("hunt_code")}) == 1449
    for field in (
        "species",
        "sex_type",
        "hunt_class",
        "draw_2026_system_type",
        "draw_system_type",
        "algorithm_status",
        "draw_routing_reason",
    ):
        assert field in fields


def test_main_enriched_routes_draw_only_and_availability_youth_elk_separately() -> None:
    eb1007 = rows_for("EB1007")
    eb1011 = rows_for("EB1011")
    youth_general_any_bull_aliases = {"YOUTH_GENERAL_ANY_BULL_ELK", "YOUTH_DRAW_ONLY_ELK"}

    assert eb1007
    assert eb1011
    assert {row["hunt_class"] for row in eb1007} == {"Youth"}
    assert {row["draw_system_type"] for row in eb1007}.issubset(youth_general_any_bull_aliases)
    assert {row["draw_2026_system_type"] for row in eb1007}.issubset(youth_general_any_bull_aliases)
    assert {row["algorithm_status"] for row in eb1007} == {"IN_SCOPE_MODEL_PENDING"}

    assert {row["hunt_class"] for row in eb1011} == {"General Bull"}
    assert {row["draw_system_type"] for row in eb1011} == {"YOUTH_OTC_OR_AVAILABILITY"}
    assert {row["draw_2026_system_type"] for row in eb1011} == {"YOUTH_OTC_OR_AVAILABILITY"}
    assert {row["algorithm_status"] for row in eb1011} == {"EXCLUDED_NOT_PREDICTIVE_DRAW"}


def test_promotion_summary_preserves_rows_and_protected_numeric_cells() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["row_count_before"] == 53225
    assert summary["row_count_after"] == 53225
    assert summary["unique_hunt_codes_before"] == 1449
    assert summary["unique_hunt_codes_after"] == 1449
    assert summary["protected_numeric_cells_changed"] == 0
    fields, _ = read_rows()
    assert "hunt_class" in fields
    assert (
        summary["draw_system_type_counts"].get("YOUTH_GENERAL_ANY_BULL_ELK")
        or summary["draw_system_type_counts"].get("YOUTH_DRAW_ONLY_ELK")
    ) == 4
    assert summary["draw_system_type_counts"]["YOUTH_OTC_OR_AVAILABILITY"] == 4
