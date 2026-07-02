import csv
import json
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_bear_draw_odds_source_audit_records_pursuit_pdf_evidence() -> None:
    csv_path = Path(str(_repo_root() / "processed_data/bear_draw_odds_source_audit.csv"))
    json_path = Path(str(_repo_root() / "processed_data/bear_draw_odds_source_audit.json"))
    rows = _read_csv(csv_path)
    report = json.loads(json_path.read_text(encoding="utf-8"))

    assert rows
    assert report["bear_hunt_codes_found_in_official_draw_odds_pdf"] > 0
    assert report["bear_pursuit_hunt_codes_found_in_official_draw_odds_pdf"] >= 9
    for hunt_code in {"BR1008", "BR1009", "BR1011"}:
        row = next(row for row in rows if row["hunt_code"] == hunt_code)
        assert row["appears_in_draw_odds_pdf"] == "yes"
        assert row["has_point_level_bonus_rows"] == "yes"
        assert row["source_classification"] == "BEAR_PURSUIT_BONUS_DRAW"
        assert row["engine_classification_after"] == "RESTRICTED_BEAR_PURSUIT"
