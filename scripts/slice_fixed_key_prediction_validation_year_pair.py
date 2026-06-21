import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "audits" / "prediction_validation" / "prediction_vs_actual_full_fixed.csv"
DEFAULT_OUTPUT_ROOT = ROOT / "audits" / "prediction_validation"


def clean(value):
    return "" if value is None else str(value).strip()


def to_float(value):
    text = clean(value).replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def metrics(rows):
    errors = []
    for row in rows:
        error = to_float(row.get("error"))
        if error is not None:
            errors.append(error)
    if not errors:
        return {
            "row_count": 0,
            "mae": "",
            "rmse": "",
            "bias": "",
            "failure_count_abs_error_gt_0_25": 0,
        }
    return {
        "row_count": len(errors),
        "mae": sum(abs(error) for error in errors) / len(errors),
        "rmse": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "bias": sum(errors) / len(errors),
        "failure_count_abs_error_gt_0_25": sum(1 for error in errors if abs(error) > 0.25),
    }


def group_metrics(rows, group_field):
    groups = defaultdict(list)
    for row in rows:
        groups[clean(row.get(group_field)) or "UNKNOWN"].append(row)
    out = []
    for group, group_rows in sorted(groups.items()):
        item = {group_field: group}
        item.update(metrics(group_rows))
        out.append(item)
    return out


def duplicate_key_rows(rows):
    keys = defaultdict(list)
    for row in rows:
        key = (
            clean(row.get("hunt_code")).upper(),
            clean(row.get("model_year")),
            clean(row.get("residency")),
            clean(row.get("hunt_program")),
            clean(row.get("point_level")),
            clean(row.get("draw_family")),
        )
        keys[key].append(row)
    out = []
    for key, group in sorted(keys.items()):
        if len(group) > 1:
            out.append(
                {
                    "hunt_code": key[0],
                    "model_year": key[1],
                    "residency": key[2],
                    "hunt_program": key[3],
                    "point_level": key[4],
                    "draw_family": key[5],
                    "duplicate_count": len(group),
                }
            )
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-year", required=True, type=int)
    parser.add_argument("--prediction-source-year", required=True, type=int)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    input_path = Path(args.input)
    output_root = Path(args.output_root)
    out_dir = output_root / f"year_to_year_{args.prediction_source_year}_to_{args.model_year}_fixed_key"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows = read_csv(input_path)
    rows = [row for row in all_rows if clean(row.get("model_year")) == str(args.model_year)]
    duplicate_rows = duplicate_key_rows(rows)
    full_name = f"prediction_{args.prediction_source_year}_vs_actual_{args.model_year}_fixed_key_full.csv"
    write_csv(out_dir / full_name, rows, list(rows[0].keys()) if rows else [])
    write_csv(
        out_dir / "duplicate_key_audit.csv",
        duplicate_rows,
        ["hunt_code", "model_year", "residency", "hunt_program", "point_level", "draw_family", "duplicate_count"],
    )

    families = group_metrics(rows, "draw_family")
    point_buckets = group_metrics(rows, "point_bucket")
    species = group_metrics(rows, "species")
    failures = [row for row in rows if clean(row.get("failure_abs_error_gt_0_25")).upper() == "TRUE"]

    write_csv(
        out_dir / f"prediction_{args.prediction_source_year}_vs_actual_{args.model_year}_by_draw_family.csv",
        families,
        ["draw_family", "row_count", "mae", "rmse", "bias", "failure_count_abs_error_gt_0_25"],
    )
    write_csv(
        out_dir / f"prediction_{args.prediction_source_year}_vs_actual_{args.model_year}_by_point_bucket.csv",
        point_buckets,
        ["point_bucket", "row_count", "mae", "rmse", "bias", "failure_count_abs_error_gt_0_25"],
    )
    write_csv(
        out_dir / f"prediction_{args.prediction_source_year}_vs_actual_{args.model_year}_by_species.csv",
        species,
        ["species", "row_count", "mae", "rmse", "bias", "failure_count_abs_error_gt_0_25"],
    )
    write_csv(out_dir / f"prediction_{args.prediction_source_year}_vs_actual_{args.model_year}_failures.csv", failures, list(rows[0].keys()) if rows else [])

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "comparison": f"{args.prediction_source_year}_predictions_model_year_{args.model_year}_vs_{args.model_year}_actual_truth",
        "input_fixed_key_validation": str(input_path),
        "join_key": "hunt_code + model_year + residency + hunt_program + point_level + draw_family",
        "duplicate_join_key_groups": len(duplicate_rows),
        "row_count": len(rows),
        **metrics(rows),
        "failure_rows_written": len(failures),
        "outputs_dir": str(out_dir),
    }
    (out_dir / f"year_to_year_{args.prediction_source_year}_to_{args.model_year}_status.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8"
    )
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
