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


def test_phase7_turkey_coverage_pending_counts_match_predictive_artifact() -> None:
    coverage_path = Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json"))
    turkey_csv_path = Path(str(_repo_root() / "processed_data/turkey_bonus_predictions_v1.csv"))
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    turkey_rows = _read_csv(turkey_csv_path)
    pending_rows = [row for row in turkey_rows if row.get("algorithm_status") == "IN_SCOPE_MODEL_PENDING"]

    phase7 = coverage["phase7_turkey"]
    assert phase7["turkey_in_scope_model_pending_rows_active_predictive"] == len(pending_rows)
    assert phase7["turkey_rows_seen_active_predictive"] == len(turkey_rows)
    assert phase7["turkey_rows_seen_observed_history"] > 0
    assert phase7["turkey_in_scope_model_pending_rows_observed_history"] >= phase7["turkey_in_scope_model_pending_rows_active_predictive"]

