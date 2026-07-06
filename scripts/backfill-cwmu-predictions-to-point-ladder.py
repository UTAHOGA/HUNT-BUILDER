#!/usr/bin/env python3
"""Backfill modeled CWMU prediction values into the compact point ladder.

This is intentionally narrow:
- CWMU source folders must exist under data_truth/draw_results_truth/raw_pdfs.
- Only rows with matching modeled CWMU prediction keys are updated.
- Contact/operator, quota-only, allocation-only, boundary, and reference rows
  without modeled prediction rows are left unchanged.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_LADDER = REPO / "processed_data" / "point_ladder_view.csv"
DEFAULT_PREDICTIONS = REPO / "processed_data" / "full_prediction_engine_2027_family_predictions.csv"
DEFAULT_CWMU_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs"
AUDIT_ROOT = REPO / "audits" / "cwmu_ladder_backfill"

PROBABILITY_FIELDS = [
    "p_draw_mean",
    "p_draw",
    "p_draw_pct",
    "random_draw_odds_2026",
    "p_draw_p10",
    "p_draw_p50",
    "p_draw_p90",
    "display_odds_pct",
    "display_odds_text",
    "p_bonus_pool",
    "p_bonus_pool_pct",
    "p_random_pool",
    "p_random_pool_pct",
    "p_random_mean",
    "p_max_pool_mean",
    "p_max_pool_pct",
    "p_max_pool_mean_pct",
    "guaranteed_probability",
]

LINEAGE_FIELDS = [
    "draw_pool",
    "draw_system_type",
    "draw_2026_system_type",
    "draw_design",
    "engine_family",
    "family",
    "algorithm_status",
    "model_strategy",
    "model_version",
    "rule_version",
    "prediction_status",
    "classification_status",
    "public_permits_target",
    "public_permits_source",
    "source_years_used",
    "source_year",
    "target_year",
    "prediction_year",
    "source_file",
    "truth_source_file",
    "reason_codes",
    "data_quality_grade",
]


def clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def upper(value: Any) -> str:
    return clean(value).upper()


def norm_residency(value: Any) -> str:
    text = clean(value).lower()
    if text in {"resident", "res", "r"}:
        return "RESIDENT"
    if text in {"nonresident", "non-resident", "non resident", "nonres", "nr"}:
        return "NONRESIDENT"
    return upper(value)


def norm_points(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else text


def key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        upper(row.get("hunt_code")),
        norm_residency(row.get("residency") or row.get("metric_scope")),
        norm_points(row.get("points") or row.get("point") or row.get("point_level")),
    )


def is_cwmu_text(row: dict[str, str]) -> bool:
    text = " ".join(
        upper(row.get(field))
        for field in (
            "hunt_type",
            "hunt_class",
            "hunt_name",
            "draw_pool",
            "draw_design",
            "draw_system_type",
            "source_file",
        )
    )
    return "CWMU" in text


def has_probability(row: dict[str, str]) -> bool:
    return any(clean(row.get(field)) for field in ("p_draw_mean", "p_draw", "display_odds_pct", "display_odds_text"))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    os.replace(tmp, path)


def cwmu_folder_inventory(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for folder in sorted(root.glob("*_PERMITS=*_MODEL/CWMU")):
        files = sorted(folder.glob("*.pdf"))
        out.append(
            {
                "folder": str(folder.relative_to(REPO)),
                "pdf_count": len(files),
                "draw_result_pdf_count": sum(1 for item in files if "DRAW RESULT" in item.name.upper()),
                "quota_reference_pdf_count": sum(1 for item in files if "QUOTA" in item.name.upper()),
            }
        )
    return out


def build_prediction_index(prediction_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], dict[str, str]], Counter]:
    prediction_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    counters: Counter = Counter()
    for row in prediction_rows:
        if not is_cwmu_text(row) or not has_probability(row):
            continue
        row_key = key(row)
        if not row_key[0] or not row_key[1] or not row_key[2]:
            counters["skipped_bad_key"] += 1
            continue
        if row_key in prediction_by_key:
            counters["duplicate_prediction_key"] += 1
            continue
        prediction_by_key[row_key] = row
        counters["prediction_rows_indexed"] += 1
        counters[f"prediction_family::{clean(row.get('family')) or clean(row.get('engine_family'))}"] += 1
    return prediction_by_key, counters


def merge_value(field: str, current: str, predicted: str) -> str:
    if not clean(predicted):
        return current
    return predicted


def prediction_value_for_ladder_field(field: str, prediction: dict[str, str]) -> str:
    if field == "draw_2026_system_type":
        return clean(prediction.get("draw_system_type"))
    if field == "truth_source_file":
        return clean(prediction.get("source_file"))
    if field == "p_draw_pct":
        return clean(prediction.get("p_draw_pct") or prediction.get("display_odds_pct"))
    if field == "random_draw_odds_2026":
        return clean(
            prediction.get("p_random_pool_pct")
            or prediction.get("p_bonus_pool_pct")
            or prediction.get("display_odds_pct")
        )
    return clean(prediction.get(field))


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill modeled CWMU prediction rows into point_ladder_view.csv.")
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--ladder", type=Path, default=DEFAULT_LADDER)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--cwmu-root", type=Path, default=DEFAULT_CWMU_ROOT)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo = args.repo.resolve()
    ladder_path = args.ladder if args.ladder.is_absolute() else repo / args.ladder
    prediction_path = args.predictions if args.predictions.is_absolute() else repo / args.predictions
    cwmu_root = args.cwmu_root if args.cwmu_root.is_absolute() else repo / args.cwmu_root
    audit_dir = repo / "audits" / "cwmu_ladder_backfill" / args.timestamp
    audit_dir.mkdir(parents=True, exist_ok=True)

    folder_inventory = cwmu_folder_inventory(cwmu_root)
    if not folder_inventory:
        raise FileNotFoundError(f"No CWMU source folders found under {cwmu_root}")

    ladder_fields, ladder_rows = read_csv(ladder_path)
    _prediction_fields, prediction_rows = read_csv(prediction_path)
    prediction_by_key, counters = build_prediction_index(prediction_rows)

    changed_rows: list[dict[str, str]] = []
    missing_prediction_rows: list[dict[str, str]] = []
    no_change_rows = 0
    matched_rows = 0

    update_fields = [field for field in PROBABILITY_FIELDS + LINEAGE_FIELDS if field in ladder_fields]
    for row in ladder_rows:
        if not is_cwmu_text(row):
            continue
        counters["ladder_cwmu_rows"] += 1
        row_key = key(row)
        prediction = prediction_by_key.get(row_key)
        if prediction is None:
            counters["ladder_cwmu_rows_without_prediction"] += 1
            if len(missing_prediction_rows) < 5000:
                missing_prediction_rows.append(
                    {
                        "hunt_code": row_key[0],
                        "residency": row_key[1],
                        "points": row_key[2],
                        "hunt_name": clean(row.get("hunt_name")),
                        "draw_system_type": clean(row.get("draw_system_type")),
                        "hunt_type": clean(row.get("hunt_type")),
                        "draw_pool": clean(row.get("draw_pool")),
                    }
                )
            continue
        matched_rows += 1
        before = {field: clean(row.get(field)) for field in update_fields}
        for field in update_fields:
            row[field] = merge_value(field, row.get(field, ""), prediction_value_for_ladder_field(field, prediction))
        after = {field: clean(row.get(field)) for field in update_fields}
        if before != after:
            changed_rows.append(
                {
                    "hunt_code": row_key[0],
                    "residency": row_key[1],
                    "points": row_key[2],
                    "hunt_name": clean(row.get("hunt_name")),
                    "prediction_family": clean(prediction.get("family") or prediction.get("engine_family")),
                    "old_p_draw_mean": before.get("p_draw_mean", ""),
                    "new_p_draw_mean": after.get("p_draw_mean", ""),
                    "old_p_draw": before.get("p_draw", ""),
                    "new_p_draw": after.get("p_draw", ""),
                    "old_display_odds_pct": before.get("display_odds_pct", ""),
                    "new_display_odds_pct": after.get("display_odds_pct", ""),
                    "old_display_odds_text": before.get("display_odds_text", ""),
                    "new_display_odds_text": after.get("display_odds_text", ""),
                    "old_random_draw_odds_2026": before.get("random_draw_odds_2026", ""),
                    "new_random_draw_odds_2026": after.get("random_draw_odds_2026", ""),
                    "source_file": clean(prediction.get("source_file")),
                }
            )
        else:
            no_change_rows += 1

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "classification": "DRY_RUN" if args.dry_run else "CWMU_LADDER_BACKFILL_APPLIED",
        "ladder_path": str(ladder_path.relative_to(repo)),
        "prediction_path": str(prediction_path.relative_to(repo)),
        "cwmu_source_folder_count": len(folder_inventory),
        "cwmu_source_pdf_count": sum(int(item["pdf_count"]) for item in folder_inventory),
        "prediction_rows_indexed": counters["prediction_rows_indexed"],
        "matched_ladder_rows": matched_rows,
        "changed_ladder_rows": len(changed_rows),
        "no_change_matched_rows": no_change_rows,
        "ladder_cwmu_rows": counters["ladder_cwmu_rows"],
        "ladder_cwmu_rows_without_prediction": counters["ladder_cwmu_rows_without_prediction"],
        "duplicate_prediction_keys": counters["duplicate_prediction_key"],
        "dry_run": args.dry_run,
    }

    with (audit_dir / "CWMU_LADDER_BACKFILL_SUMMARY.json").open("w", encoding="utf-8") as handle:
        json.dump({**summary, "counters": dict(counters), "cwmu_folders": folder_inventory}, handle, indent=2)

    with (audit_dir / "CWMU_LADDER_BACKFILL_CHANGED_ROWS.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "hunt_code",
            "residency",
            "points",
            "hunt_name",
            "prediction_family",
            "old_p_draw_mean",
            "new_p_draw_mean",
            "old_p_draw",
            "new_p_draw",
            "old_display_odds_pct",
            "new_display_odds_pct",
            "old_display_odds_text",
            "new_display_odds_text",
            "old_random_draw_odds_2026",
            "new_random_draw_odds_2026",
            "source_file",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(changed_rows)

    with (audit_dir / "CWMU_LADDER_BACKFILL_MISSING_PREDICTION_SAMPLE.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["hunt_code", "residency", "points", "hunt_name", "draw_system_type", "hunt_type", "draw_pool"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(missing_prediction_rows)

    notes = [
        "# CWMU Ladder Backfill",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Classification: `{summary['classification']}`",
        "",
        "## Inputs",
        "",
        f"- Ladder: `{summary['ladder_path']}`",
        f"- Predictions: `{summary['prediction_path']}`",
        f"- CWMU source folders: `{summary['cwmu_source_folder_count']}` folders / `{summary['cwmu_source_pdf_count']}` PDFs",
        "",
        "## Results",
        "",
        f"- Prediction rows indexed: `{summary['prediction_rows_indexed']}`",
        f"- Matched ladder rows: `{summary['matched_ladder_rows']}`",
        f"- Changed ladder rows: `{summary['changed_ladder_rows']}`",
        f"- Duplicate prediction keys: `{summary['duplicate_prediction_keys']}`",
        f"- CWMU ladder rows left without modeled prediction: `{summary['ladder_cwmu_rows_without_prediction']}`",
        "",
        "Rows without matching modeled prediction were left unchanged. This keeps CWMU contact/operator, quota-only, allocation-only, boundary, and reference scaffolding out of scoring.",
    ]
    (audit_dir / "CWMU_LADDER_BACKFILL_SUMMARY.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    if not args.dry_run:
        write_csv(ladder_path, ladder_fields, ladder_rows)

    print(json.dumps(summary, indent=2))
    print(f"AUDIT_DIR: {audit_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
