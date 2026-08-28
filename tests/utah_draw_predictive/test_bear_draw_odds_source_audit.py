import csv
from pathlib import Path

from engine.utah_draw_predictive.bear import build_bear_draw_odds_source_audit


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
    # `processed_data` is deliberately held at the last promoted candidate;
    # validate the current source classifier directly so the test does not
    # mistake that known-stale runtime artifact for current engine evidence.
    database = _repo_root() / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
    rows, report = build_bear_draw_odds_source_audit(_read_csv(database))

    assert rows
    assert report["bear_hunt_codes_found_in_official_draw_odds_pdf"] > 0
    assert report["bear_pursuit_hunt_codes_found_in_official_draw_odds_pdf"] >= 9
    for hunt_code in {"BR1008", "BR1009", "BR1011"}:
        row = next(row for row in rows if row["hunt_code"] == hunt_code)
        assert row["appears_in_draw_odds_pdf"] == "yes"
        assert row["has_point_level_bonus_rows"] == "yes"
        assert row["source_classification"] == "BEAR_PURSUIT_BONUS_DRAW"
        assert row["engine_classification_after"] == "RESTRICTED_BEAR_PURSUIT"
