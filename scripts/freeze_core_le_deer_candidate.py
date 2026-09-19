"""Freeze the selected repair and copy retained family inputs to a new audit."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "audits/prediction_release_candidates/core_final_coverage_20260919"
OUT = REPO / "audits/prediction_release_candidates/core_le_deer_repair_20260919"


def digest(path):
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def main():
    target = OUT / "SELECTED_REPAIR_FREEZE.json"
    if target.exists():
        raise SystemExit("Selected repair is already frozen; refusing overwrite")
    protected = ["data_truth/draw_results_truth/normalized/draw_results_long.csv",
                 "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
                 "audits/prediction_release_candidates/certified_core_random_winner_20260919/mixed_materialization/ml_draw_predictions_v1.csv",
                 "audits/prediction_release_candidates/core_final_coverage_20260919/mixed_final_audited/ml_draw_predictions_v1.csv",
                 "audits/prediction_release_candidates/core_final_coverage_20260919/certification_registry.json"]
    code = ["engine/utah_draw_predictive/preference_general_deer.py", "engine/utah_draw_predictive/run_all_families.py",
            "engine/utah_predictive_mixed/materialize.py", "scripts/classify_historical_actual_gaps.py",
            "scripts/build_blind_acceptance_review.py", "scripts/build_prediction_family_certification_registry.py",
            "docs/decisions/ADR-0006-historical-blind-acceptance-thresholds.md"]
    manifest = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(),
                "selected_repair": "SOURCE_POINT_AWARDS_ONCE_EXCLUDING_HUNT_TOTALS; SOURCE_PROVEN_CONDITIONAL_ABSTENTIONS",
                "deer_probability_formula_or_calibration_changes": False,
                "threshold_changes": False, "later_validation_inspected_for_this_selection": False,
                "later_folds_previously_inspected_in_project": True,
                "development_report_sha256": digest(OUT / "development_quota_dedup_v2/development_report.json"),
                "protected_baselines": {p: digest(REPO / p) for p in protected},
                "implementation": {p: digest(REPO / p) for p in code}, "retained_family_inputs": {}}
    for year in range(2017, 2026):
        fold = f"{year}_to_{year + 1}"
        dest = OUT / "historical_folds" / fold / "prediction_phase"
        dest.mkdir(parents=True, exist_ok=False)
        manifest["retained_family_inputs"][fold] = {}
        for name in ["family_predictions.csv", "run_metadata.json"]:
            source = BASE / "historical_folds" / fold / "prediction_phase" / name
            shutil.copy2(source, dest / name)
            manifest["retained_family_inputs"][fold][name] = {"source": str(source), "sha256": digest(source)}
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(target, digest(target))


if __name__ == "__main__":
    main()
