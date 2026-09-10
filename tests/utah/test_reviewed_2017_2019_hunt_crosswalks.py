from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_reviewed_2017_2019_hunt_crosswalks.py"
OUT_DIR = (
    ROOT
    / "audits"
    / "prediction_rebuilds"
    / "fresh_official_draw_truth_rebuild_2017_forward_20260909"
    / "crosswalks"
)


def read_rows(name: str) -> list[dict[str, str]]:
    with (OUT_DIR / name).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def find(
    rows: list[dict[str, str]], from_code: str, to_code: str
) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if row["from_hunt_code"] == from_code and row["to_hunt_code"] == to_code
    ]
    assert len(matches) == 1, (from_code, to_code, len(matches))
    return matches[0]


def setup_module() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)


def test_2017_to_2018_carry_forward_gate() -> None:
    rows = read_rows("reviewed_hunt_identity_crosswalk_2017_to_2018.csv")
    assert find(rows, "DA1003", "DA1038")["applicant_stack_carry_forward_allowed"] == "TRUE"
    assert find(rows, "EA1083", "EA1197")["applicant_stack_carry_forward_allowed"] == "TRUE"
    bear_pursuit = find(rows, "BR1008", "BR1008")
    assert bear_pursuit["transition_type"] == "SAME_IDENTITY"
    assert bear_pursuit["applicant_stack_carry_forward_allowed"] == "TRUE"
    assert bear_pursuit["carry_forward_draw_designs"] == "RESTRICTED_BEAR_PURSUIT"
    assert find(rows, "GO6812", "GO6818")["transition_type"] == "ONE_TO_MANY_SPLIT"
    assert find(rows, "GO6812", "GO6818")["applicant_stack_carry_forward_allowed"] == "FALSE"
    assert find(rows, "DB1045", "DB1045")["carry_forward_draw_designs"] == "BONUS_LE_BIG_GAME"
    assert find(rows, "DB1045", "DB0007")["applicant_stack_carry_forward_allowed"] == "FALSE"


def test_2018_to_2019_carry_forward_gate() -> None:
    rows = read_rows("reviewed_hunt_identity_crosswalk_2018_to_2019.csv")
    assert find(rows, "DA1038", "DA1003")["applicant_stack_carry_forward_allowed"] == "TRUE"
    assert find(rows, "MB6204", "MB6240")["applicant_stack_carry_forward_allowed"] == "TRUE"
    assert find(rows, "DB1259", "DB1259")["transition_type"] == "NAME_ALIAS"
    assert find(rows, "DB1259", "DB1259")["applicant_stack_carry_forward_allowed"] == "TRUE"
    assert find(rows, "BI6507", "BI6507")["transition_type"] == "BOUNDARY_CHANGE"
    assert find(rows, "BI6507", "BI6507")["applicant_stack_carry_forward_allowed"] == "FALSE"
    assert find(rows, "BR7103", "BR7121")["transition_type"] == "ONE_TO_MANY_SPLIT"
    assert find(rows, "BR7103", "BR7122")["applicant_stack_carry_forward_allowed"] == "FALSE"
    assert find(rows, "PD1027", "PD1034")["transition_type"] == "ONE_TO_MANY_SPLIT"
    assert find(rows, "PD1027", "PD1035")["applicant_stack_carry_forward_allowed"] == "FALSE"


def test_only_verified_identity_rows_can_carry() -> None:
    for name in (
        "reviewed_hunt_identity_crosswalk_2017_to_2018.csv",
        "reviewed_hunt_identity_crosswalk_2018_to_2019.csv",
    ):
        rows = read_rows(name)
        for row in rows:
            if row["applicant_stack_carry_forward_allowed"] == "TRUE":
                assert row["transition_type"] in {"SAME_IDENTITY", "NAME_ALIAS"}
                assert row["identity_continuity_verified"] == "TRUE"
                assert row["carry_forward_draw_designs"]
                assert row["carry_forward_scope"] == "SAME_DRAW_DESIGN_AND_RESIDENCY_LANE_ONLY"
            if row["transition_type"] in {
                "BOUNDARY_CHANGE",
                "PROGRAM_CHANGE",
                "ONE_TO_MANY_SPLIT",
                "NEW_HUNT",
                "ELIMINATED_HUNT",
                "UNRESOLVED",
            }:
                assert row["applicant_stack_carry_forward_allowed"] == "FALSE"
