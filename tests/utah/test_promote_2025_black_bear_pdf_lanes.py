from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "promote_2025_black_bear_pdf_lanes_to_canonical.py"


def load_module():
    spec = importlib.util.spec_from_file_location("promote_2025_bear_lanes", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retained_2025_bear_pdf_matches_canonical_before_lane_promotion() -> None:
    module = load_module()
    result = module.build_promotion()
    manifest = result["manifest"]

    assert manifest["parity_status"] == "PASS"
    assert manifest["official_pdf_hunt_pages"] == 97
    assert manifest["official_pdf_point_keys"] == 2_231
    assert manifest["excluded_public_draw_code"] == "BR7307"
    assert manifest["excluded_public_draw_point_keys"] == 23
    assert manifest["canonical_bear_point_keys"] == 2_208
    assert manifest["promoted_rows"] == 2_208
    assert manifest["promoted_hunt_codes"] == 96
    assert manifest["count_changes"] == 0
    assert manifest["identity_changes"] == 0
    assert manifest["br7307_changes"] == 0
    assert manifest["source_classification_counts"] == {
        "BEAR_PURSUIT_BONUS_DRAW": 207,
        "TRUE_BEAR_BONUS_DRAW": 2_001,
    }


def test_promotion_marks_only_verified_residency_lanes_and_preserves_br7307() -> None:
    module = load_module()
    rows = module.build_promotion()["rows"]
    promoted = [row for row in rows if row.get("qa_status") == "OFFICIAL_PDF_RESIDENCY_LANES_CANONICAL"]
    br7307 = [row for row in rows if row.get("hunt_code") == "BR7307"]

    assert len(promoted) == 2_208
    assert {row["bear_source_classification"] for row in promoted} == {
        "BEAR_PURSUIT_BONUS_DRAW",
        "TRUE_BEAR_BONUS_DRAW",
    }
    assert br7307
    assert all(row.get("qa_status") != "OFFICIAL_PDF_RESIDENCY_LANES_CANONICAL" for row in br7307)
