from __future__ import annotations

import csv
from pathlib import Path

from scripts.build_blind_acceptance_review import load_draw_line_fold
from tools.prediction_accuracy_backtest.score_full_engine_draw_line_aware import prediction_bear_subtype


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_acceptance_review_separates_bear_hunting_and_restricted_pursuit(tmp_path: Path) -> None:
    path = tmp_path / "scored.csv"
    common = {
        "scoring_decision": "score_probability",
        "draw_design_key": "BEAR_DRAW",
        "hunt_code": "BR7001",
        "residency": "Resident",
        "points": "10",
        "actual_species": "Black Bear",
        "predicted_probability": "0.5",
        "actual_probability": "0.4",
    }
    _write_rows(
        path,
        [
            {**common, "bear_draw_subtype": "LIMITED_ENTRY_BEAR_HUNT"},
            {**common, "hunt_code": "BR1011", "bear_draw_subtype": "RESTRICTED_BEAR_PURSUIT"},
            {**common, "hunt_code": "BR7999", "bear_draw_subtype": ""},
        ],
    )

    rows = load_draw_line_fold("2019_to_2020", path)

    assert [row["draw_design"] for row in rows] == [
        "BEAR_LIMITED_ENTRY_HUNT_BONUS",
        "BEAR_RESTRICTED_PURSUIT_BONUS",
        "BEAR_DRAW_UNCLASSIFIED_SUBTYPE",
    ]


def test_scorer_hydrates_missing_bear_subtype_from_frozen_forecast_metadata() -> None:
    legacy_pursuit = {
        "hunt_code": "BR1008",
        "hunt_name": "Book Cliffs - Pursuit",
        "species": "Black Bear",
        "hunt_type": "O.T.C.",
        "bear_draw_subtype": "",
    }
    emitted_hunt = {
        "hunt_code": "BR7001",
        "hunt_name": "Cache",
        "species": "Black Bear",
        "bear_draw_subtype": "LIMITED_ENTRY_BEAR_HUNT",
    }

    assert prediction_bear_subtype(legacy_pursuit, "BEAR_DRAW") == (
        "RESTRICTED_BEAR_PURSUIT",
        "SOURCE_CLASSIFIED_FROM_FROZEN_FORECAST_METADATA",
    )
    assert prediction_bear_subtype(emitted_hunt, "BEAR_DRAW") == (
        "LIMITED_ENTRY_BEAR_HUNT",
        "FORECAST_EMITTED",
    )


def test_scorer_prefers_exact_source_year_canonical_bear_classification() -> None:
    legacy_hunt = {
        "source_year": "2017",
        "hunt_code": "BR7006",
        "hunt_name": "Chalk Creek/Kamas/North Slope, Summit - Any Legal Weapon",
        "species": "Black Bear",
        "bear_draw_subtype": "",
    }

    assert prediction_bear_subtype(legacy_hunt, "BEAR_DRAW") == (
        "LIMITED_ENTRY_BEAR_HUNT",
        "SOURCE_YEAR_CANONICAL_TRUTH",
    )


def test_scorer_uses_retained_pdf_lineage_when_legacy_canonical_label_is_generic() -> None:
    historic_lasal = {
        "source_year": "2019",
        "hunt_code": "BR7307",
        "hunt_name": "La Sal",
        "species": "Black Bear",
        "bear_draw_subtype": "",
    }

    assert prediction_bear_subtype(historic_lasal, "BEAR_DRAW") == (
        "LIMITED_ENTRY_BEAR_HUNT",
        "SOURCE_YEAR_RETAINED_OFFICIAL_BEAR_PDF",
    )
