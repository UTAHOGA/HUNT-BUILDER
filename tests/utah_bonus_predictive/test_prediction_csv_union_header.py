from __future__ import annotations

import csv

from scripts.build_predictive_bonus_engine_v1 import write_csv


def test_write_csv_preserves_status_fields_emitted_by_later_prediction_rows(tmp_path):
    output = tmp_path / "predictions.csv"
    rows = [
        {"hunt_code": "EB1001", "p_draw_mean": 0.5},
        {
            "hunt_code": "DB1001",
            "p_draw_mean": 0.75,
            "algorithm_status": "MODELED_BONUS",
            "prediction_status": "MODELED",
            "permit_source_field": "forecast_permits_res",
        },
    ]

    write_csv(output, ["hunt_code", "p_draw_mean"], rows)

    with output.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        written = list(reader)

    assert reader.fieldnames == [
        "hunt_code",
        "p_draw_mean",
        "algorithm_status",
        "prediction_status",
        "permit_source_field",
    ]
    assert written[1]["algorithm_status"] == "MODELED_BONUS"
    assert written[1]["prediction_status"] == "MODELED"
    assert written[1]["permit_source_field"] == "forecast_permits_res"
