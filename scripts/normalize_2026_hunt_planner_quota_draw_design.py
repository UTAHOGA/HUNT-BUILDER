import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv",
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv",
    ROOT / "audits" / "2026_live_source_comparison" / "appended_2026_hunt_planner_antlerless_rows.csv",
]
SUMMARY = ROOT / "audits" / "2026_live_source_comparison" / "normalize_2026_hunt_planner_quota_draw_design_summary.json"


def normalize_file(path):
    if not path.exists():
        return {"path": str(path), "changed_rows": 0, "exists": False}
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    changed = 0
    for row in rows:
        is_quota_row = row.get("record_type") == "hunt_planner_permit_quota" or path.name == "appended_2026_hunt_planner_antlerless_rows.csv"
        if is_quota_row and row.get("hunt_type") == "CWMU" and row.get("draw_design") == "CWMU Allocation":
            row["draw_design"] = "Preference"
            changed += 1
    if changed:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    return {"path": str(path), "changed_rows": changed, "exists": True}


def main():
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    results = [normalize_file(path) for path in TARGETS]
    SUMMARY.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()
