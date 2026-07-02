import csv
import json
from collections import Counter
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    for candidate in [repo_root, *repo_root.parents]:
        if (
            (candidate / "AGENTS.MD").exists()
            and (candidate / "engine").is_dir()
            and (candidate / "processed_data").is_dir()
        ):
            return candidate
    raise RuntimeError("Could not locate HUNT-BUILDER repo root")


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


def test_candidate_csv_uses_engine_family_labels_for_modeled_draws() -> None:
    rows = _csv_rows(CANONICAL_CSV)
    expected = {
        "EB3024": "BONUS_LE_BIG_GAME",
        "EB3022": "BONUS_LE_BIG_GAME",
        "DB1004": "BONUS_PLE_BIG_GAME",
        "BI6500": "BONUS_OIL_BIG_GAME",
        "GO6800": "BONUS_OIL_BIG_GAME",
        "PB5025": "BONUS_LE_BIG_GAME",
        "TK1018": "BONUS_TURKEY",
        "DB1770": "PREFERENCE_DEDICATED_HUNTER_DEER",
        "DB1009": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "EA2012": "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK",
        "BR7000": "BEAR_DRAW",
        "EB1007": "YOUTH_DRAW_ONLY_ELK",
    }
    for code, draw_family in expected.items():
        assert _by_code(rows, code)["draw_family"] == draw_family


def test_public_canonical_json_keeps_display_family_labels() -> None:
    rows = _json_rows(CANONICAL_JSON)
    expected = {
        "EB3024": "Limited Entry",
        "EB3022": "Limited Entry",
        "DB1004": "Limited Entry",
        "BI6500": "Limited Entry",
        "GO6800": "Limited Entry",
        "PB5025": "Limited Entry",
        "DA1001": "General",
        "EA1267": "General",
        "PD1012": "General",
        "EA2012": "Allocation",
        "BR1001": "Availability",
        "BR1007": "O.T.C.",
        "DB0008": "O.T.C.",
        "DB0001": "Allocation",
    }
    for code, draw_family in expected.items():
        assert _by_code(rows, code)["draw_family"] == draw_family


def test_candidate_csv_leaves_reference_only_public_rows_unclassified() -> None:
    rows = _csv_rows(CANONICAL_CSV)
    for code in ["DA1001", "EA1267", "PD1012", "BR1001", "BR1007", "DB0008", "DB0001"]:
        assert _by_code(rows, code)["draw_family"] == ""


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
