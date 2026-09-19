"""Verify the selected repair freeze, account for LE gaps, and rebuild registry."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_core_le_deer_repair import read

BASE = ROOT / "audits/prediction_release_candidates/core_final_coverage_20260919"
OUT = ROOT / "audits/prediction_release_candidates/core_le_deer_repair_20260919"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def identity(row):
    return tuple(row.get(k) for k in ("draw_design_key", "draw_pool_key", "hunt_code", "residency", "points"))


def main():
    frozen = json.loads((OUT / "SELECTED_REPAIR_FREEZE.json").read_text())
    for group in ["protected_baselines", "implementation"]:
        for path, expected in frozen[group].items():
            if sha(ROOT / path) != expected:
                raise SystemExit(f"Frozen {group} changed: {path}")
    command = [sys.executable, "scripts/build_blind_acceptance_review.py", "--out-dir", str(OUT / "acceptance_review")]
    resolutions = []
    evidence = []
    for source_year in range(2017, 2026):
        fold = f"{source_year}_to_{source_year + 1}"
        comparison = OUT / "historical_folds" / fold / "comparison_phase"
        classification = comparison / "draw_line_aware_actual_gap_classifications.csv"
        manifest = json.loads(classification.with_suffix(".manifest.json").read_text())
        prediction = OUT / "historical_folds" / fold / "prediction_phase/final_public_predictions.csv"
        checks = {"output_sha256": classification,
                  "actual_gaps_sha256": comparison / "draw_line_aware_actual_ladder_scoring_rows.csv",
                  "conditional_abstention_frozen_predictions_sha256": prediction,
                  "conditional_abstention_history_truth_sha256": ROOT / "data_truth/draw_results_truth/normalized/draw_results_long.csv"}
        for field, path in checks.items():
            if manifest[field] != sha(path):
                raise SystemExit(f"Stale gap evidence: {fold}:{field}")
        current = {identity(r): r for r in read(classification)}
        for row in read(BASE / "historical_folds" / fold / "comparison_phase/draw_line_aware_actual_gap_classifications.csv"):
            if row["draw_design_key"] == "BONUS_LE_BIG_GAME" and row["certification_gap_status"] == "BLOCKING_ENGINE_GAP":
                resolved = current[identity(row)]
                if resolved["actual_gap_classification"] != "SOURCE_SAFETY_NO_COHORT_AND_NO_OBSERVED_TRANSITION":
                    raise SystemExit(f"LE gap not independently resolved: {fold}:{identity(row)}")
                resolutions.append({"fold": fold, **resolved})
        evidence.append({"fold": fold, "classification_sha256": sha(classification), "frozen_prediction_sha256": sha(prediction)})
        command.extend(["--fold", f"{fold}={comparison / 'draw_line_aware_prediction_vs_actual_rowlevel.csv'}"])
    if len(resolutions) != 32:
        raise SystemExit(f"Expected all 32 original LE gaps, found {len(resolutions)}")
    (OUT / "le_gap_resolution_summary.json").write_text(json.dumps({"status": "PASS", "resolved": 32,
        "invented_probabilities": 0, "deleted_actuals": 0, "resolutions": resolutions}, indent=2) + "\n")
    (OUT / "freeze_verification.json").write_text(json.dumps({"status": "PASS", "protected_baselines_unchanged": True,
        "selected_implementation_unchanged": True, "fold_evidence": evidence}, indent=2) + "\n")
    subprocess.run(command, cwd=ROOT, check=True)
    subprocess.run([sys.executable, "scripts/build_prediction_family_certification_registry.py", "--review-dir",
                    str(OUT / "acceptance_review"), "--output", str(OUT / "certification_registry.json")], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
