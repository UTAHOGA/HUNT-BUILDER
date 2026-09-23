"""Score regenerated forecasts against the full exact-year adult actual census.

Reuses the retained pool-aware diagnostic, never the old subset scoring joins.
This is a known-year verification, not untouched holdout certification.
"""
import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "audits/prediction_release_candidates/antlerless_certification_review_20260921_v1"
sys.path.insert(0, str(REVIEW))
sys.path.insert(0, str(ROOT))
from assess_candidate import read, sha, grouped, FAMILIES

spec = importlib.util.spec_from_file_location("retained_antlerless_actuals", REVIEW / "exact_year_adult_pool_diagnostic.py")
actuals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actuals)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecasts", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.out_dir.exists():
        raise SystemExit("Refusing to overwrite retained verification evidence")
    scores, census, hashes = [], [], {}
    for source_year in range(2017, 2026):
        target = source_year + 1
        truth = ROOT / f"data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_{target}_for_{target+1}_canonical_yearly_draw_results.csv"
        forecast = args.forecasts / f"{source_year}_forecast.csv"
        hashes[str(truth)] = sha(truth)
        hashes[str(forecast)] = sha(forecast)
        points, excluded, conflicts = actuals.actual_points(read(truth), target)
        if conflicts:
            raise ValueError(f"Conflicting official actual identities: {target}")
        predictions = {}
        for row in read(forecast):
            family = row.get("draw_system_type")
            if family not in FAMILIES or row.get("draw_pool", "").lower() not in actuals.ADULT_POOLS[family]:
                continue
            key = (family, row["hunt_code"], row["residency"], row["points"])
            if key in predictions:
                raise ValueError(f"Duplicate forecast key: {source_year} {key}")
            used = [int(y) for y in re.split(r"[,;]", row.get("source_years_used", "")) if y.strip()]
            if not used or any(year > source_year for year in used):
                raise ValueError(f"Missing or future source years: {source_year} {key}")
            predictions[key] = row
        for key, evidence in points.items():
            prediction = predictions.get(key, {})
            value = actuals.number(prediction.get("p_draw_mean"))
            row = {"source_year": source_year, "target_year": target,
                   "draw_design_key": key[0], "hunt_code": key[1], "residency": key[2], "points": key[3],
                   **evidence, "forecast_algorithm_status": prediction.get("algorithm_status", ""),
                   "forecast_reason_codes": prediction.get("reason_codes", "")}
            if not evidence["applicants"]:
                status = "ZERO_ACTUAL_APPLICANTS_NOT_SCORABLE"
            elif evidence["probability"] is None:
                status = "MISSING_OFFICIAL_PROBABILITY"
            elif not evidence["source_file"] or not (evidence["pdf_page"] or evidence["source_row_identifier"]):
                status = "MISSING_OFFICIAL_LINEAGE"
            elif value is None:
                status = "MISSING_FORECAST_REQUIRES_SOURCE_CLASSIFICATION"
            else:
                status = "SCORED"
                row.update(predicted_probability=value, actual_probability=evidence["probability"])
                scores.append(row)
            row["classification"] = status
            census.append(row)
    import csv
    args.out_dir.mkdir(parents=True)
    for name, rows in (("scores.csv", scores), ("census.csv", census)):
        fields = list(dict.fromkeys(key for row in rows for key in row))
        with (args.out_dir / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    report = {
        "purpose": "FRESH_FORECAST_KNOWN_YEAR_FULL_ADULT_CENSUS_VERIFICATION_NOT_CERTIFICATION",
        "folds": "2017->2018 through 2025->2026",
        "join": "exact actual year / adult draw design / hunt code / residency / point",
        "website_probability_field": "p_draw_mean from final mixed_row",
        "input_hashes": hashes,
        "actual_projector_sha256": sha(REVIEW / "exact_year_adult_pool_diagnostic.py"),
        "verification_script_sha256": sha(__file__),
        "family_metrics": grouped(scores, ("draw_design_key",)),
        "fold_metrics": grouped(scores, ("draw_design_key", "source_year", "target_year")),
        "census_counts": dict(Counter(row["classification"] for row in census)),
        "missing_forecast_statuses": dict(Counter(row["forecast_algorithm_status"] or "ABSENT" for row in census if row["classification"].startswith("MISSING_FORECAST"))),
        "probability_engine_changed": False, "registry_changed": False, "promotion_authorized_by_this_report": False,
    }
    (args.out_dir / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("family_metrics", "census_counts", "missing_forecast_statuses")}, indent=2))


if __name__ == "__main__":
    main()
