from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "build_2017_blind_source_truth",
    ROOT / "scripts" / "build_2017_blind_source_truth.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _lane(residency: str, applicants: int, bonus: int, regular: int) -> dict[str, str]:
    row = {field: "" for field in MODULE.HEADER}
    row.update(
        {
            "actual_draw_year": "2017",
            "model_target_year": "2018",
            "source_scope": "ANTLERLESS",
            "source_file": "official_dwr_archive/example.pdf",
            "pdf_page": "1",
            "hunt_code": "DA1000",
            "hunt_name": "Example hunt",
            "points": "0",
            "record_type": "point_level_draw_result",
            "hunt_type": "Antlerless",
            "draw_design": "PREFERENCE_ANTLERLESS_DEER",
            "residency": residency,
            "eligible_applicants": str(applicants),
            "bonus_permits": str(bonus),
            "regular_permits": str(regular),
            "total_permits": str(bonus + regular),
            "success_ratio": "1 in 2.0",
        }
    )
    return row


def test_collapsed_2017_candidate_retains_both_official_residency_lanes() -> None:
    collapsed = MODULE.dwr_table_shape_rows(
        [_lane("Resident", 189, 0, 0), _lane("Nonresident", 35, 0, 0)]
    )

    assert len(collapsed) == 1
    row = collapsed[0]
    assert row["resident_eligible_applicants"] == "189"
    assert row["nonresident_eligible_applicants"] == "35"
    assert row["total_eligible_applicants"] == "224"
    assert row["resident_total_permits"] == "0"
    assert row["nonresident_total_permits"] == "0"
    assert row["total_permits"] == "0"
