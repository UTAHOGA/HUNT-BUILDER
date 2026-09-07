from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "promote_2020_black_bear_pdf_lanes_to_canonical.py"


def load_module():
    spec = importlib.util.spec_from_file_location("promote_legacy_bear_lanes", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.configure_report_year(2018)
    return module


def test_2018_bear_promotion_uses_published_residency_lanes() -> None:
    module = load_module()
    _fields, rows, manifest = module.build_promoted_rows()

    assert manifest["parity_status"] == "PASS"
    assert manifest["official_pdf_point_keys"] == 1_820
    assert manifest["canonical_bear_point_keys"] == 1_820
    assert manifest["promoted_rows"] == 1_820

    br7004_point_ten = next(
        row
        for row in rows
        if row.get("hunt_code") == "BR7004"
        and row.get("points") == "10"
        and row.get("metric_scope") == "total"
    )
    assert {
        field: br7004_point_ten[field]
        for field in (
            "resident_eligible_applicants",
            "resident_bonus_permits",
            "resident_regular_permits",
            "resident_total_permits",
            "nonresident_eligible_applicants",
            "nonresident_bonus_permits",
            "nonresident_regular_permits",
            "nonresident_total_permits",
        )
    } == {
        "resident_eligible_applicants": "4",
        "resident_bonus_permits": "1",
        "resident_regular_permits": "0",
        "resident_total_permits": "1",
        "nonresident_eligible_applicants": "0",
        "nonresident_bonus_permits": "0",
        "nonresident_regular_permits": "0",
        "nonresident_total_permits": "0",
    }
    assert br7004_point_ten["resident_success_ratio"] == "1 in 4.0"
    assert br7004_point_ten["nonresident_success_ratio"] == "N/A"
    assert br7004_point_ten["qa_status"] == "OFFICIAL_PDF_RESIDENCY_LANES_CANONICAL"
    assert br7004_point_ten["source_namespace"] == "OFFICIAL_DWR_DRAW_RESULTS_2018"
    assert br7004_point_ten["source_dataset"] == "DWR_2018_DRAW_RESULTS_PDF"
