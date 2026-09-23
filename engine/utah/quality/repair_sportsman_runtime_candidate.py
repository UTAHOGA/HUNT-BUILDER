"""Rebuild Sportsman coverage locally without replacing incomplete runtime files."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

from engine.utah_bonus_predictive.materialize import _replace_rows_by_draw_system_type, write_csv
from engine.utah_draw_predictive.certification import annotate_prediction_rows, load_registry
from engine.utah_draw_predictive.classifier import sanitize_modeled_probability_fields
from engine.utah_draw_predictive.sportsman import (
    SPORTSMAN_DRAW_SYSTEM_TYPE, build_sportsman_predictions, validate_sportsman_output_coverage,
)

ROOT = Path(__file__).resolve().parents[3]


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output, planner_path):
    if output.exists():
        raise ValueError("Preserve prior candidates; output directory must be new")
    ml = ROOT / "processed_data/ml_draw_predictions_v1.csv"
    old_report = ROOT / "processed_data/ml_draw_predictions_v1_report.json"
    family = ROOT / "processed_data/sportsman_permit_predictions_v1.csv"
    database = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
    registry_path = ROOT / "governance/prediction-family-certification.json"
    before = {str(p): sha(p) for p in (ml, old_report, family, database, registry_path, planner_path)}
    original = read_rows(ml)
    previous = json.loads(old_report.read_text(encoding="utf-8"))
    identities = read_rows(database)
    planner = {r["hunt_code"]: r for r in read_rows(planner_path) if r["hunt_year"] == "2026"}
    for row in identities:
        p = planner.get(row["hunt_code"])
        if p and p.get("season_date_text"):
            row["season"] = p["season_date_text"]
    # Existing owner reads prior-year source, never current actual applicant counts.
    sportsman, family_report = build_sportsman_predictions([], identities, 2026, [2025])
    sportsman = [sanitize_modeled_probability_fields(dict(r)) for r in sportsman]
    certification = annotate_prediction_rows(sportsman, load_registry(registry_path))
    for row in sportsman:
        if any(row.get(k) not in (None, "") for k in ("certified_p_draw", "certified_p_draw_mean", "certified_p_draw_pct")):
            raise ValueError("Sportsman certification changed; explicit review required")
        p = planner.get(row["hunt_code"])
        if p is None:
            raise ValueError(f"Missing current Planner identity: {row['hunt_code']}")
        row.update(planner_hunt_name=p["dwr_hunt_name"], planner_hunt_type=p["dwr_hunt_type"],
                   planner_source_url=p["source_url"])
    combined = _replace_rows_by_draw_system_type(original, sportsman, {SPORTSMAN_DRAW_SYSTEM_TYPE})
    validate_sportsman_output_coverage(combined, sportsman)
    if [r for r in original if r.get("draw_system_type") != SPORTSMAN_DRAW_SYSTEM_TYPE] != [r for r in combined if r.get("draw_system_type") != SPORTSMAN_DRAW_SYSTEM_TYPE]:
        raise ValueError("Unrelated family rows changed")
    source_paths = {ROOT / r["sportsman_source_file"] for r in sportsman}
    source_hashes = {str(p): sha(p) for p in source_paths}
    # Current actual evidence stays in the audit only, not in forecast fields.
    actual_path = ROOT / "pipeline/RAW/hunt_unit_database/2026/json/draw_results/utahdraws_2026_20260902/utahdraws_2026/json/2026_sportsman_30_sportsman_black_bear.json"
    actual = [r for r in json.loads(actual_path.read_text(encoding="utf-8-sig"))["Data"] if r["HuntCode"] == "BR1000"]
    if len(actual) != 1 or actual[0]["HuntCategoryName"] != "Sportsman":
        raise ValueError("Ambiguous BR1000 actual source")
    output.mkdir(parents=True)
    backup = output / "rollback"
    backup.mkdir()
    for p in (ml, old_report, family):
        shutil.copy2(p, backup / p.name)
        if sha(p) != sha(backup / p.name):
            raise ValueError("Rollback hash verification failed")
    for name, rows in (("ml_draw_predictions_v1.csv", combined), ("sportsman_permit_predictions_v1.csv", sportsman)):
        write_csv(output / name, rows, list(dict.fromkeys(k for row in rows for k in row)))
    (output / "ml_draw_predictions_v1_report.json").write_text(json.dumps({
        "rows": len(combined), "unique_hunt_codes": len({r['hunt_code'] for r in combined}),
        "forecast_year": 2026, "status": "PARTIAL_BASE_SPORTSMAN_REPAIR_ONLY_DO_NOT_PROMOTE",
        "source": str(ml), "source_sha256": before[str(ml)],
        "full_population_verified": False,
    }, indent=2) + "\n", encoding="utf-8")
    report = {
        "status": "SPORTSMAN_COVERAGE_REPAIRED_CANDIDATE_ONLY", "promotion": "BLOCKED",
        "runtime_replaced": False, "original_rows": len(original),
        "original_hunt_codes": len({r['hunt_code'] for r in original}),
        "companion_report_rows": previous.get("rows"), "companion_report_codes": previous.get("unique_hunt_codes"),
        "candidate_rows": len(combined), "candidate_hunt_codes": len({r['hunt_code'] for r in combined}),
        "sportsman_rows": len(sportsman), "other_family_cells_unchanged": True,
        "added_sportsman_codes": sorted({r['hunt_code'] for r in sportsman} - {r['hunt_code'] for r in original}),
        "source_year": 2025, "source_hashes": source_hashes,
        "family_report": family_report, "certification": certification,
        "br1000_current_actual_evidence_not_forecast_input": {
            "path": str(actual_path), "sha256": sha(actual_path), "odds_rows": actual[0]["OddsList"]},
        "br1000_candidate": next(r for r in sportsman if r["hunt_code"] == "BR1000"),
        "protected_input_hashes": before,
        "blockers": ["BASE_RUNTIME_POPULATION_AND_REPORT_DISAGREE", "DATABASE_HASH_REVIEW_PENDING", "NO_DEPLOYMENT_AUTHORIZATION"],
    }
    if any(sha(Path(p)) != h for p, h in before.items()):
        raise ValueError("Protected input changed during repair")
    report["outputs"] = {p.name: sha(p) for p in output.glob("*.csv")}
    (output / "repair_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--planner", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.output_dir, args.planner)
    print(json.dumps({k: report[k] for k in ("status", "promotion", "original_rows", "candidate_rows", "sportsman_rows", "added_sportsman_codes", "blockers")}, indent=2))
