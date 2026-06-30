import csv
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ML_PATH = REPO / "processed_data" / "ml_draw_predictions_v1.csv"
REVIEW_PATH = REPO / "processed_data" / "modeled_availability_review_report.json"
GPT_REVIEW_PATH = REPO / "processed_data" / "gpt_work_review_report.json"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_modeled_availability_does_not_change_bonus_or_preference_counts_unexpectedly() -> None:
    rows = _read_csv(ML_PATH)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["algorithm_status"]] = counts.get(row["algorithm_status"], 0) + 1

    expected = {
        "MODELED_BONUS": 28081,
        "MODELED_PREFERENCE": 12814,
        "MODELED_ALLOCATION": 0,
        "MODELED_AVAILABILITY": 124,
        "MODELED_SPORTSMAN_DRAW": 10,
        "MODELED_RANDOM_ONLY": 2,
        "IN_SCOPE_MODEL_PENDING": 124,
        "EXCLUDED_NOT_PREDICTIVE_DRAW": 4,
        "OUT_OF_SCOPE_NON_TARGET": 0,
    }
    for key, value in expected.items():
        assert counts.get(key, 0) == value

    review = _read_json(REVIEW_PATH)
    assert "stale" in review["conclusion"].lower()

    gpt_review = _read_json(GPT_REVIEW_PATH)
    assert gpt_review["row_counts"]["MODELED_AVAILABILITY"] == expected["MODELED_AVAILABILITY"]
    assert gpt_review["row_counts"]["MODELED_SPORTSMAN_DRAW"] == expected["MODELED_SPORTSMAN_DRAW"]
    assert gpt_review["row_counts"]["OUT_OF_SCOPE_NON_TARGET"] == expected["OUT_OF_SCOPE_NON_TARGET"]
