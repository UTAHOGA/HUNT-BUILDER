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


def test_phase9_private_lands_coverage_matches_predictive_artifact() -> None:
    coverage = json.loads(Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json")).read_text(encoding="utf-8"))
    rows = _read_csv(Path(str(_repo_root() / "processed_data/private_lands_antlerless_elk_predictions_v1.csv")))
    section = coverage["phase9_private_lands_antlerless_elk"]

    assert section["private_lands_only_antlerless_elk_in_scope"] is True
    assert section["private_lands_only_antlerless_elk_modeled_capped_permits"] is True
    assert section["private_lands_only_antlerless_elk_row_count"] == len(rows)
    assert section["private_lands_only_antlerless_elk_p_draw_count"] == 0
    assert section["private_lands_only_antlerless_elk_incorrectly_classified_as_preference_antlerless_elk_count"] == 0
    assert section["normal_antlerless_elk_preference_still_modeled"] is True
