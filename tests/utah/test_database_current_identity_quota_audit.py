from __future__ import annotations

import pytest

from scripts.audit_database_current_identity_quota_2026 import (
    PLANNER_SOURCE_LABEL,
    repair_rac_source_labels_from_planner,
)


def database_row() -> dict[str, str]:
    return {
        "hunt_code": "BI6506",
        "species": "Bison",
        "permits_2026_res": "11",
        "permits_2026_nr": "0",
        "permits_2026_total": "11",
        "permits_2026_source": "2026_RAC_CURRENT_YEAR_ALLOTMENT",
        "permits_2026_draw_source": "2026_RAC_CURRENT_YEAR_ALLOTMENT",
        "permit_allotment_2026_source": "2026_RAC_CURRENT_YEAR_ALLOTMENT",
        "permit_allotment_2026_source_file": "old-rac.csv",
        "permit_allotment_2026_status": "RAC_CURRENT_YEAR_SPLIT",
    }


def planner_row() -> dict[str, str]:
    return {
        "hunt_code": "BI6506",
        "fetch_status": "OK",
        "hunt_year": "2026",
        "dwr_species": "Bison",
        "permits_2026_res": "11",
        "permits_2026_nr": "0",
        "permits_2026_total": "11",
    }


def test_exact_current_planner_row_replaces_only_provenance() -> None:
    row = database_row()
    before = tuple(row[key] for key in ("permits_2026_res", "permits_2026_nr", "permits_2026_total"))
    repaired = repair_rac_source_labels_from_planner([row], {"BI6506": planner_row()})
    assert repaired == ["BI6506"]
    assert tuple(row[key] for key in ("permits_2026_res", "permits_2026_nr", "permits_2026_total")) == before
    assert row["permits_2026_source"] == PLANNER_SOURCE_LABEL
    assert row["permits_2026_draw_source"] == PLANNER_SOURCE_LABEL
    assert row["permit_allotment_2026_source"] == PLANNER_SOURCE_LABEL
    assert row["permit_allotment_2026_status"] == "DWR_CURRENT_EXACT"


def test_planner_value_difference_blocks_source_relabel() -> None:
    row = database_row()
    planner = planner_row()
    planner["permits_2026_total"] = "12"
    with pytest.raises(RuntimeError, match="Planner"):
        repair_rac_source_labels_from_planner([row], {"BI6506": planner})
