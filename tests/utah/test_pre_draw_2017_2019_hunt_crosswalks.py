from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_pre_draw_2017_2019_hunt_crosswalks.py"
OUT_DIR = (
    ROOT
    / "audits"
    / "prediction_rebuilds"
    / "fresh_official_draw_truth_rebuild_2017_forward_20260909"
    / "crosswalks"
    / "pre_draw_source_only"
)


def read_rows(name: str) -> list[dict[str, str]]:
    with (OUT_DIR / name).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def find(rows: list[dict[str, str]], from_code: str, to_code: str) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if row["from_hunt_code"] == from_code and row["to_hunt_code"] == to_code
    ]
    assert len(matches) == 1, (from_code, to_code, len(matches))
    return matches[0]


def setup_module() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)


def test_2017_to_2018_pre_draw_crosswalk_blocks_splits_and_same_code_boundary_changes() -> None:
    rows = read_rows("pre_draw_hunt_identity_crosswalk_2017_to_2018.csv")
    assert find(rows, "GO6812", "GO6818")["transition_type"] == "ONE_TO_MANY_SPLIT"
    assert find(rows, "GO6812", "GO6818")["applicant_stack_carry_forward_allowed"] == "FALSE"
    assert find(rows, "BR7120", "BR7120")["transition_type"] == "BOUNDARY_CHANGE"
    assert find(rows, "PB5008", "PB5008")["applicant_stack_carry_forward_allowed"] == "FALSE"


def test_2018_to_2019_pre_draw_crosswalk_allows_only_the_verified_one_to_one_recode() -> None:
    rows = read_rows("pre_draw_hunt_identity_crosswalk_2018_to_2019.csv")
    recode = find(rows, "MB6204", "MB6240")
    assert recode["transition_type"] == "NAME_ALIAS"
    assert recode["applicant_stack_carry_forward_allowed"] == "TRUE"
    assert recode["carry_forward_draw_designs"]
    assert find(rows, "BR7103", "BR7121")["applicant_stack_carry_forward_allowed"] == "FALSE"
    assert find(rows, "CG7501", "CG1034")["transition_type"] == "BOUNDARY_CHANGE"


def test_2019_to_2020_pre_draw_crosswalk_blocks_every_printed_same_code_boundary_change() -> None:
    rows = read_rows("pre_draw_hunt_identity_crosswalk_2019_to_2020.csv")

    assert len(rows) == 12
    assert {row["transition_type"] for row in rows} == {"BOUNDARY_CHANGE"}
    assert {row["applicant_stack_carry_forward_allowed"] for row in rows} == {"FALSE"}
    assert find(rows, "EB3004", "EB3004")["target_application_evidence_pages"]
    assert find(rows, "DS6607", "DS6607")["target_application_evidence_pages"]


def test_2020_to_2021_pre_draw_crosswalk_blocks_the_two_reused_changed_boundaries() -> None:
    rows = read_rows("pre_draw_hunt_identity_crosswalk_2020_to_2021.csv")

    assert len(rows) == 2
    assert {row["from_hunt_code"] for row in rows} == {"RS6708", "RS6709"}
    assert {row["applicant_stack_carry_forward_allowed"] for row in rows} == {"FALSE"}


def test_2021_to_2022_pre_draw_crosswalk_blocks_restructured_or_eliminated_hunts() -> None:
    rows = read_rows("pre_draw_hunt_identity_crosswalk_2021_to_2022.csv")

    assert len(rows) == 30
    assert {row["applicant_stack_carry_forward_allowed"] for row in rows} == {"FALSE"}
    assert find(rows, "BI6517", "")["transition_type"] == "BOUNDARY_CHANGE"
    assert find(rows, "DS6612", "")["transition_type"] == "ELIMINATED"
    assert find(rows, "BR7209", "")["transition_type"] == "PROGRAM_CHANGE"
    assert all(row["target_application_evidence_pages"] for row in rows)


def test_2022_to_2023_pre_draw_crosswalk_stops_cougar_and_unresolved_restructures() -> None:
    rows = read_rows("pre_draw_hunt_identity_crosswalk_2022_to_2023.csv")

    cougar = [row for row in rows if row["from_hunt_code"].startswith("CG")]
    assert len(cougar) == 9
    assert {row["transition_type"] for row in cougar} == {"PROGRAM_TERMINATED"}
    assert {row["applicant_stack_carry_forward_allowed"] for row in rows} == {"FALSE"}
    assert find(rows, "EB3001", "")["transition_type"] == "UNRESOLVED_TARGET_IDENTITY"


def test_2023_to_2024_pre_draw_crosswalk_blocks_only_absent_source_codes() -> None:
    rows = read_rows("pre_draw_hunt_identity_crosswalk_2023_to_2024.csv")

    assert rows
    assert not any(row["from_hunt_code"].startswith("CG") for row in rows)
    assert {row["transition_type"] for row in rows} == {"UNRESOLVED_TARGET_IDENTITY"}
    assert {row["applicant_stack_carry_forward_allowed"] for row in rows} == {"FALSE"}


def test_2024_to_2025_pre_draw_crosswalk_blocks_only_absent_source_codes() -> None:
    rows = read_rows("pre_draw_hunt_identity_crosswalk_2024_to_2025.csv")

    assert rows
    assert not any(row["from_hunt_code"].startswith("CG") for row in rows)
    assert {row["transition_type"] for row in rows} == {"UNRESOLVED_TARGET_IDENTITY"}
    assert {row["applicant_stack_carry_forward_allowed"] for row in rows} == {"FALSE"}


def test_2025_to_2026_pre_draw_crosswalk_blocks_only_absent_source_codes() -> None:
    rows = read_rows("pre_draw_hunt_identity_crosswalk_2025_to_2026.csv")

    assert rows
    assert not any(row["from_hunt_code"].startswith("CG") for row in rows)
    assert {row["transition_type"] for row in rows} == {"UNRESOLVED_TARGET_IDENTITY"}
    assert {row["applicant_stack_carry_forward_allowed"] for row in rows} == {"FALSE"}


def test_every_pre_draw_row_is_anti_leak_certification_evidence() -> None:
    for name in (
        "pre_draw_hunt_identity_crosswalk_2017_to_2018.csv",
        "pre_draw_hunt_identity_crosswalk_2018_to_2019.csv",
        "pre_draw_hunt_identity_crosswalk_2019_to_2020.csv",
        "pre_draw_hunt_identity_crosswalk_2020_to_2021.csv",
        "pre_draw_hunt_identity_crosswalk_2021_to_2022.csv",
        "pre_draw_hunt_identity_crosswalk_2022_to_2023.csv",
        "pre_draw_hunt_identity_crosswalk_2023_to_2024.csv",
        "pre_draw_hunt_identity_crosswalk_2024_to_2025.csv",
        "pre_draw_hunt_identity_crosswalk_2025_to_2026.csv",
    ):
        for row in read_rows(name):
            assert row["evidence_timing"] == "PRE_DRAW"
            assert row["target_draw_results_used"] == "FALSE"
            assert row["crosswalk_scope"] == "EXCEPTIONS_ONLY_PRE_DRAW"
            assert row["certification_use"] == "ELIGIBLE_PRE_DRAW_IDENTITY_ONLY"
            assert row["target_application_evidence_file"].endswith(".pdf")
            assert row["target_application_evidence_sha256"]
            assert row["target_application_evidence_pages"]


def test_summary_explicitly_excludes_target_draw_results() -> None:
    summary = json.loads(
        (OUT_DIR / "pre_draw_hunt_identity_crosswalk_2017_to_2026_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "PASS_PRE_DRAW_SOURCE_ONLY"
    assert summary["target_draw_results_used"] is False
    assert summary["unlisted_source_code_behavior"] == "PASS_THROUGH_UNCHANGED_HUNT_CODE"
