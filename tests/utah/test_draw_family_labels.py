import csv
import json
from collections import Counter
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


REPO = Path(str(_repo_root()))
CANONICAL_CSV = REPO / "data" / "hunt-master-canonical-2026-database-candidate.csv"
CANONICAL_JSON = REPO / "canonical" / "hunt-planner-2026.json"
REPORT = REPO / "processed_data" / "draw_family_label_normalization_report.json"


OLD_INTERNAL_LABELS = {"BONUS", "ANTLERLESS", "TURKEY_DRAW", "NONE", "HARVEST_OBJECTIVE", "UNKNOWN"}


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _json_rows(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["hunt_catalog"]


def _by_code(rows: list[dict[str, str]], code: str) -> dict[str, str]:
    return next(row for row in rows if row.get("hunt_code") == code or row.get("huntCode") == code)


def test_draw_family_internal_bucket_labels_removed_from_canonical_csv() -> None:
    rows = _csv_rows(CANONICAL_CSV)
    labels = {row["draw_family"] for row in rows}
    assert labels.isdisjoint(OLD_INTERNAL_LABELS)


def test_draw_family_internal_bucket_labels_removed_from_canonical_json() -> None:
    rows = _json_rows(CANONICAL_JSON)
    labels = {row["draw_family"] for row in rows}
    assert labels.isdisjoint(OLD_INTERNAL_LABELS)


def test_draw_family_bonus_random_hunts_are_limited_entry() -> None:
    rows = _csv_rows(CANONICAL_CSV)
    for code in ["EB3024", "EB3022", "DB1004", "BI6500", "GO6800", "PB5025", "TK1003"]:
        assert _by_code(rows, code)["draw_family"] == "Limited Entry"


def test_draw_family_preference_style_public_draws_are_general() -> None:
    rows = _csv_rows(CANONICAL_CSV)
    for code in ["DA1001", "EA1267", "PD1012"]:
        assert _by_code(rows, code)["draw_family"] == "General"


def test_draw_family_total_only_allocation_and_availability_are_not_generalized() -> None:
    rows = _csv_rows(CANONICAL_CSV)
    assert _by_code(rows, "EA2012")["draw_family"] == "Allocation"
    assert _by_code(rows, "BR1001")["draw_family"] == "Availability"
    assert _by_code(rows, "BR1007")["draw_family"] == "O.T.C."
    assert _by_code(rows, "DB0008")["draw_family"] == "O.T.C."
    assert _by_code(rows, "DB0001")["draw_family"] == "Allocation"


def test_draw_family_normalization_report_written() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["changed_files"] >= 0
    aggregate = Counter()
    for item in report["files"]:
        if item["file"] == "data/hunt-master-canonical-2026-database-candidate.csv":
            aggregate.update(item["after"])
            assert set(item["after"]).isdisjoint(OLD_INTERNAL_LABELS)
    assert aggregate["Limited Entry"] > 0
    assert aggregate["General"] > 0
