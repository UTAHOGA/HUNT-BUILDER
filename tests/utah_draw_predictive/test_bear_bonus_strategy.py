import csv
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


def test_public_limited_entry_bear_rows_can_be_modeled_bonus() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/bear_draw_predictions_v1.csv")))
    modeled = [
        row for row in rows
        if row.get("algorithm_status") == "MODELED_BONUS"
        and row.get("bear_draw_subtype") == "LIMITED_ENTRY_BEAR_HUNT"
    ]
    assert modeled
    assert all((row.get("p_preference_draw") or "").strip() == "" for row in modeled)
    assert all((row.get("p_bonus_pool") or "").strip() != "" for row in modeled)
    assert all((row.get("p_random_pool") or "").strip() != "" for row in modeled)
    assert all(0.0 <= float(row["p_draw"]) <= 1.0 for row in modeled if (row.get("p_draw") or "").strip())
    assert all(0.0 <= float(row["p_draw_pct"]) <= 100.0 for row in modeled if (row.get("p_draw_pct") or "").strip())


def test_nonpublic_and_ambiguous_bear_rows_do_not_receive_fake_draw_odds() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/bear_draw_predictions_v1.csv")))
    nonpublic = [row for row in rows if row.get("bear_draw_subtype") == "CONSERVATION_OR_NON_PUBLIC"]
    ambiguous = [row for row in rows if row.get("bear_draw_subtype") == "UNKNOWN_BEAR_SUBTYPE"]
    assert all((row.get("p_draw") or "").strip() == "" for row in nonpublic)
    assert all((row.get("p_draw") or "").strip() == "" for row in ambiguous)
    assert all(row.get("algorithm_status") == "IN_SCOPE_MODEL_PENDING" for row in ambiguous)
