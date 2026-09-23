from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW = (
    ROOT
    / "audits"
    / "prediction_release_candidates"
    / "residency_lane_acceptance_20260922"
    / "acceptance_review"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_certified_designs_pass_each_residency_slice() -> None:
    path = REVIEW / "acceptance_by_draw_design_and_residency.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 8
    assert {(row["draw_design"], row["residency"]) for row in rows} == {
        (design, residency)
        for design in {
            "BONUS_LE_BIG_GAME",
            "BONUS_OIL_BIG_GAME",
            "BONUS_PLE_BIG_GAME",
            "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        }
        for residency in {"Resident", "Nonresident"}
    }
    for row in rows:
        assert row["acceptance_status"] == "ACCEPTED"
        assert int(row["fold_count"]) >= 2
        assert int(row["joined_rows"]) >= 400
        assert float(row["mae"]) <= 0.1
        assert float(row["p90_absolute_error"]) <= 0.3
        assert float(row["tail_error_rate_over_25pp"]) <= 0.1
        assert int(row["false_guarantee_rows"]) == 0
        assert int(row["unclassified_actual_gap_rows"]) == 0


def test_residency_evidence_hashes_and_registry_policy_agree() -> None:
    manifest = json.loads((REVIEW / "acceptance_review_manifest.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "governance" / "prediction-family-certification.json").read_text(encoding="utf-8"))
    residency = registry["residency_acceptance"]

    for key in ("acceptance_by_draw_design", "acceptance_by_draw_design_and_residency"):
        evidence = manifest["evidence"][key]
        path = REVIEW / evidence["path"]
        assert _sha256(path) == evidence["sha256"]
        assert residency["evidence"][f"{key}_sha256"] == evidence["sha256"]

    assert residency["cross_lane_ladder_borrowing_allowed"] is False
    assert residency["accepted_slices"] == 8
    assert residency["rejected_slices"] == 0
    assert residency["new_designs_certified"] == []


def test_public_residency_summary_matches_gate_scope() -> None:
    public = json.loads(
        (ROOT / "public" / "data" / "prediction-residency-certification.json").read_text(encoding="utf-8")
    )
    assert public["cross_lane_borrowing_allowed"] is False
    assert set(public["certified_designs"]) == {
        "BONUS_LE_BIG_GAME",
        "BONUS_OIL_BIG_GAME",
        "BONUS_PLE_BIG_GAME",
        "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
    }
    assert all(
        lane["status"] == "ACCEPTED"
        for design in public["certified_designs"].values()
        for lane in design.values()
    )
    assert public["withheld_designs_unchanged"] is True
