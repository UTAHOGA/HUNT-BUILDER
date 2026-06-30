from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def materialized_rows(tmp_path_factory: pytest.TempPathFactory) -> list[dict[str, str]]:
    out_dir = tmp_path_factory.mktemp("max_weighted")
    subprocess.run(
        [
            sys.executable,
            "scripts/build_predictive_bonus_engine_v1.py",
            "--prediction-year",
            "2026",
            "--iterations",
            "20",
            "--out-dir",
            str(out_dir),
        ],
        cwd=ROOT,
        check=True,
    )
    with (out_dir / "predictive_bonus_engine_2026.materialized.csv").open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def row(materialized_rows: list[dict[str, str]], points: str) -> dict[str, str]:
    return next(
        r
        for r in materialized_rows
        if r["hunt_code"] == "EB3024" and r["residency"] == "Resident" and r["points"] == points
    )


def test_eb3024_resident_has_max_mixed_random_zone_behavior(materialized_rows: list[dict[str, str]]) -> None:
    p30 = row(materialized_rows, "30")
    p29 = row(materialized_rows, "29")
    p28 = row(materialized_rows, "28")
    assert p30["point_pool_zone"] == "max_pool_guaranteed"
    assert p30["p_max_pool_mean"] == "1.0"
    assert p29["point_pool_zone"] == "max_pool_cutoff_mixed"
    assert p29["projected_applicants"] == "19"
    assert p29["forecast_applicants_at_level"] == "19"
    assert p29["p_max_pool_mean"] == "0.157895"
    assert p28["point_pool_zone"] == "random_pool"
    assert p28["p_random_mean"]


def test_2025_historical_random_success_not_copied_to_2026_prediction(materialized_rows: list[dict[str, str]]) -> None:
    p12 = row(materialized_rows, "12")
    assert p12["display_odds_text"] != "~1 in 49.0 or 2.0%"
    assert p12["display_odds_text"].startswith("~1 in ")
    assert p12["display_odds_text"] == "~1 in 353 or 0.3%"


def test_max_weighted_challenge_guardrails(materialized_rows: list[dict[str, str]]) -> None:
    assert materialized_rows
    assert not [r for r in materialized_rows if r["points"] == "ALL"]
    assert not [r for r in materialized_rows if not r["display_odds_text"]]
    assert not [r for r in materialized_rows if not r["projected_applicants"]]
    assert not [
        r
        for r in materialized_rows
        if "sportsman" in " ".join(str(r.get(k, "")) for k in ("hunt_code", "hunt_name", "hunt_type", "draw_system_type")).lower()
    ]
    assert not [
        r
        for r in materialized_rows
        if r.get("p_draw") and not (0.0 <= float(r["p_draw"]) <= 1.0)
    ]
    assert not [
        r
        for r in materialized_rows
        if r.get("p_random_mean") and not (0.0 <= float(r["p_random_mean"]) <= 1.0)
    ]
    zones = {r["point_pool_zone"] for r in materialized_rows}
    assert {"max_pool_guaranteed", "max_pool_cutoff_mixed", "random_pool"}.issubset(zones)
