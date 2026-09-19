"""Read-only diagnostics of frozen LE gaps and development-only deer errors."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "audits/prediction_release_candidates/core_final_coverage_20260919"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def key(row):
    return row.get("hunt_code"), row.get("residency"), row.get("points")


def stats(rows):
    errors = sorted(abs(float(r["predicted_probability"]) - float(r["actual_probability"])) for r in rows)
    return {"n": len(errors), "mae": sum(errors) / len(errors), "p90": errors[int(.9 * (len(errors) - 1))],
            "tail": sum(e > .25 for e in errors) / len(errors),
            "bias": sum(float(r["predicted_probability"]) - float(r["actual_probability"]) for r in rows) / len(rows)}


def main():
    gaps = []
    dev = []
    for year in range(2017, 2026):
        fold = BASE / f"historical_folds/{year}_to_{year + 1}"
        prediction = {key(r): r for r in read(fold / "prediction_phase/final_public_predictions.csv")
                      if r["draw_system_type"] == "BONUS_LE_BIG_GAME"}
        for row in read(fold / "comparison_phase/draw_line_aware_actual_gap_classifications.csv"):
            if row["draw_design_key"] != "BONUS_LE_BIG_GAME" or row["certification_gap_status"] != "BLOCKING_ENGINE_GAP":
                continue
            pred = prediction.get(key(row), {})
            gaps.append({"year": year, **{f: row.get(f) for f in ["hunt_code", "residency", "points", "prior_year_eligible_applicants", "prior_year_successful_applicants"]},
                         **{f: pred.get(f) for f in ["algorithm_status", "forecast_applicants_at_level", "forecast_applicants_above", "source_years_used", "p_draw_mean", "reason_codes"]}})
        if year <= 2022:
            for row in read(fold / "comparison_phase/draw_line_aware_prediction_vs_actual_rowlevel.csv"):
                if row["draw_design_key"] == "PREFERENCE_GENERAL_SEASON_BUCK_DEER" and row["scoring_decision"] == "score_probability":
                    row["source_year"] = str(year)
                    dev.append(row)
    print("LE_GAPS", json.dumps(gaps, indent=2))
    print("DEVELOPMENT_ONLY", json.dumps(stats(dev)))
    for field in ["source_year", "residency", "points", "predicted_probability"]:
        groups = defaultdict(list)
        for row in dev:
            value = row[field]
            if field == "predicted_probability":
                value = f"{int(float(value) * 10)}"
            groups[value].append(row)
        print(field, json.dumps({k: stats(v) for k, v in sorted(groups.items())}, indent=2))


if __name__ == "__main__":
    main()
