import csv
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_preference_field_contract_is_normalized() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/ml_draw_predictions_v1.csv")))

    modeled_preference = [row for row in rows if row.get("algorithm_status") == "MODELED_PREFERENCE"]
    modeled_bonus = [row for row in rows if row.get("algorithm_status") == "MODELED_BONUS"]
    pending = [row for row in rows if row.get("algorithm_status") == "IN_SCOPE_MODEL_PENDING"]
    out_of_scope = [row for row in rows if row.get("algorithm_status") == "OUT_OF_SCOPE_NON_TARGET"]

    assert modeled_preference
    assert all(str(row.get("p_preference_draw") or "").strip() for row in modeled_preference)
    assert all(str(row.get("p_draw") or "").strip() for row in modeled_preference)
    assert all(str(row.get("p_draw_pct") or "").strip() for row in modeled_preference)
    assert all((row.get("p_preference_draw") or "") == (row.get("p_draw") or "") for row in modeled_preference)
    assert all(abs(float(row["p_draw_pct"]) - (float(row["p_draw"]) * 100.0)) <= 0.001 for row in modeled_preference)
    assert all(str(row.get("p_bonus_pool") or "").strip() == "" for row in modeled_preference)
    assert all(str(row.get("p_random_pool") or "").strip() == "" for row in modeled_preference)
    assert all(str(row.get("p_preference_draw") or "").strip() == "" for row in modeled_bonus)
    assert all(str(row.get("p_draw") or "").strip() == "" for row in pending)
    assert all(str(row.get("p_draw") or "").strip() == "" for row in out_of_scope)
