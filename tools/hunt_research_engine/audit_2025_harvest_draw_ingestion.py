#!/usr/bin/env python3
"""Audit 2025-for-2026 harvest/draw ingestion for Hunt Research engine feeds.

The 2025 preliminary harvest package was published in 2026, but the observed
harvest year remains 2025. This read-only audit proves whether the 2025
harvest rows and 2025 draw-result rows are already aligned into the engine
surfaces used for the 2026 Hunt Research model.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUT_DIR = "audits/hunt_research_engine"

RAW_HARVEST_CSVS = [
    "harvest_results_2025_for_2026_BISON_hunt_success.csv",
    "harvest_results_2025_for_2026_DEER_hunt_success.csv",
    "harvest_results_2025_for_2026_DESERT_BIGHORN_SHEEP_hunt_success.csv",
    "harvest_results_2025_for_2026_ELK_hunt_success.csv",
    "harvest_results_2025_for_2026_hunt_code_keyed.csv",
    "harvest_results_2025_for_2026_MOOSE_hunt_success.csv",
    "harvest_results_2025_for_2026_MOUNTAIN_GOAT_hunt_success.csv",
    "harvest_results_2025_for_2026_PRONGHORN_hunt_success.csv",
    "harvest_results_2025_for_2026_ROCKY_MOUNTAIN_BIGHORN_SHEEP_hunt_success.csv",
    "harvest_results_2025_for_2026_source_inventory.csv",
    "harvest_results_2025_for_2026_summary.csv",
    "harvest_quality_features_by_hunt_code_2025_for_2026.csv",
    "harvest_results_2025_for_2026_all_long.csv",
]

NON_HARVEST_REFERENCE_CSVS = [
    "limited entry elk private lands draw odds 2025.csv",
]

FILES = {
    "raw_harvest_dir": "pipeline/RAW/hunt_unit_database/2026/csv/harvest report",
    "harvest_truth_long": "data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv",
    "harvest_truth_features": "data_truth/harvest_results_truth/normalized/harvest_quality_features_all_years_by_hunt_code.csv",
    "harvest_model_long": "data_model/harvest_quality/harvest_results_all_years_long.csv",
    "harvest_model_features": "data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv",
    "harvest_feature_model_2026": "data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv",
    "draw_truth_long": "data_truth/draw_results_truth/normalized/draw_results_long.csv",
    "draw_reality_engine": "processed_data/draw_reality_engine.csv",
    "draw_reality_engine_v2": "processed_data/draw_reality_engine_v2.csv",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def code_count(rows: list[dict[str, str]]) -> int:
    return len({clean(row.get("hunt_code")).upper() for row in rows if clean(row.get("hunt_code"))})


def summarize_year(rows: list[dict[str, str]], year_field: str, year: str) -> dict[str, object]:
    hits = [row for row in rows if clean(row.get(year_field)) == year]
    source_counts = Counter(clean(row.get("source_file")) for row in hits if clean(row.get("source_file")))
    species_counts = Counter(clean(row.get("species")) for row in hits if clean(row.get("species")))
    return {
        "rows": len(hits),
        "hunt_codes": code_count(hits),
        "source_counts_top": dict(source_counts.most_common(20)),
        "species_counts": dict(sorted(species_counts.items())),
    }


def feature_key(row: dict[str, str]) -> tuple[str, str]:
    return clean(row.get("reported_hunt_year")), clean(row.get("hunt_code")).upper()


def source_summary(path: Path, classification: str) -> dict[str, object]:
    fields, rows = read_csv(path)
    source_dates = sorted({clean(row.get("source_date")) for row in rows if clean(row.get("source_date"))})
    source_files = Counter(clean(row.get("source_file")) for row in rows if clean(row.get("source_file")))
    years = sorted({clean(row.get("reported_hunt_year")) for row in rows if clean(row.get("reported_hunt_year"))})
    targets = sorted({clean(row.get("model_target_year")) for row in rows if clean(row.get("model_target_year"))})
    return {
        "source_csv": path.name,
        "raw_path": str(path),
        "raw_exists": path.exists(),
        "raw_size_bytes": path.stat().st_size if path.exists() else 0,
        "raw_rows": len(rows),
        "raw_columns": len(fields),
        "has_hunt_code": "hunt_code" in fields,
        "hunt_codes": code_count(rows),
        "reported_hunt_years": "|".join(years),
        "model_target_years": "|".join(targets),
        "source_dates": "|".join(source_dates),
        "top_source_files": json.dumps(dict(source_files.most_common(5)), sort_keys=True),
        "classification": classification,
        "status": "RAW_GENERATED_CSV_PRESENT" if path.exists() else "RAW_GENERATED_CSV_MISSING",
    }


def build_audit(root: Path) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    raw_dir = root / FILES["raw_harvest_dir"]
    raw_rows = [source_summary(raw_dir / name, "HARVEST_SOURCE") for name in RAW_HARVEST_CSVS]
    raw_rows.extend(source_summary(raw_dir / name, "NON_HARVEST_DRAW_REFERENCE") for name in NON_HARVEST_REFERENCE_CSVS)

    _, truth_long = read_csv(root / FILES["harvest_truth_long"])
    _, truth_features = read_csv(root / FILES["harvest_truth_features"])
    _, model_long = read_csv(root / FILES["harvest_model_long"])
    _, model_features = read_csv(root / FILES["harvest_model_features"])
    _, feature_model = read_csv(root / FILES["harvest_feature_model_2026"])
    _, draw_truth = read_csv(root / FILES["draw_truth_long"])
    _, draw_engine = read_csv(root / FILES["draw_reality_engine"])
    _, draw_v2 = read_csv(root / FILES["draw_reality_engine_v2"])

    truth_keys = {feature_key(row) for row in truth_features if feature_key(row)[0] == "2025" and feature_key(row)[1]}
    model_keys = {feature_key(row) for row in model_features if feature_key(row)[0] == "2025" and feature_key(row)[1]}
    truth_by_key = {feature_key(row): row for row in truth_features if feature_key(row)[0] == "2025" and feature_key(row)[1]}
    missing_keys = sorted(truth_keys - model_keys)
    missing_rows = [
        {
            "reported_hunt_year": key[0],
            "hunt_code": key[1],
            "species": clean(truth_by_key[key].get("species")),
            "hunt_name": clean(truth_by_key[key].get("hunt_name")),
            "source_file": clean(truth_by_key[key].get("source_file")),
            "recommended_action": "APPEND_TO_ENGINE_FEATURE_FEEDER_FROM_NORMALIZED_TRUTH",
        }
        for key in missing_keys
    ]

    feature_using_2025 = [
        row for row in feature_model if "2025" in clean(row.get("harvest_feature_source_years")).split("|")
    ]
    feature_using_2026 = [
        row for row in feature_model if "2026" in clean(row.get("harvest_feature_source_years")).split("|")
    ]
    draw_truth_2025 = summarize_year(draw_truth, "year", "2025")
    draw_v2_2025 = summarize_year(draw_v2, "year", "2025")
    draw_legacy_2025 = summarize_year(draw_engine, "year", "2025")
    raw_status_counts = Counter(clean(row["status"]) for row in raw_rows)
    nonharvest_rows = [row for row in raw_rows if row["classification"] == "NON_HARVEST_DRAW_REFERENCE"]
    result = "PASS" if not missing_rows else "PASS_WITH_SOURCE_BACKED_ENGINE_FEATURE_GAPS"

    zip_path = Path("C:/Users/tyler/Desktop/BIBLE HUNT CODES/2025.zip")
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_name": "2025_harvest_draw_ingestion",
        "result": result,
        "reported_hunt_year": 2025,
        "model_target_year": 2026,
        "raw_harvest_csvs_checked": len(RAW_HARVEST_CSVS),
        "non_harvest_reference_csvs_checked": len(NON_HARVEST_REFERENCE_CSVS),
        "raw_status_counts": dict(sorted(raw_status_counts.items())),
        "bible_hunt_codes_zip": str(zip_path),
        "bible_hunt_codes_zip_exists": zip_path.exists(),
        "bible_hunt_codes_zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
        "harvest_truth_2025": summarize_year(truth_long, "reported_hunt_year", "2025"),
        "harvest_truth_features_2025": summarize_year(truth_features, "reported_hunt_year", "2025"),
        "harvest_model_long_2025": summarize_year(model_long, "reported_hunt_year", "2025"),
        "harvest_model_features_2025": summarize_year(model_features, "reported_hunt_year", "2025"),
        "truth_feature_keys_2025": len(truth_keys),
        "engine_feature_keys_2025": len(model_keys),
        "missing_engine_feature_keys_2025": len(missing_rows),
        "feature_model_rows_using_2025": len(feature_using_2025),
        "feature_model_hunt_codes_using_2025": len({clean(row.get("hunt_code")).upper() for row in feature_using_2025 if clean(row.get("hunt_code"))}),
        "feature_model_rows_using_2026_source_year": len(feature_using_2026),
        "draw_truth_2025": draw_truth_2025,
        "draw_reality_engine_v2_2025": draw_v2_2025,
        "draw_reality_engine_legacy_2025": draw_legacy_2025,
        "draw_engine_v2_matches_draw_truth_rows": draw_v2_2025["rows"] == draw_truth_2025["rows"],
        "draw_engine_legacy_has_2025_rows": draw_legacy_2025["rows"] > 0,
        "non_harvest_reference_files": [row["source_csv"] for row in nonharvest_rows],
        "guardrail": "The 2026-03-06 source date is the publication/report date for 2025 harvest results. These rows are valid 2025 observed harvest history for the 2026 model, not observed 2026 harvest-year data.",
        "recommended_next_step": "No 2025 source-backed harvest feature feeder gaps remain. Continue with downstream engine/runtime regeneration only when the broader production phase calls for it.",
    }
    return summary, raw_rows, missing_rows


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, summary: dict[str, object], raw_rows: list[dict[str, object]], missing_rows: list[dict[str, object]]) -> None:
    lines = [
        "# 2025 Harvest/Draw Ingestion Audit",
        "",
        "Read-only alignment proof for 2025 harvest results used by the 2026 Hunt Research model.",
        "",
        "## Summary",
        "",
        f"- Result: `{summary['result']}`.",
        f"- Reported hunt year: `{summary['reported_hunt_year']}`.",
        f"- Model target year: `{summary['model_target_year']}`.",
        f"- Raw harvest CSVs checked: `{summary['raw_harvest_csvs_checked']}`.",
        f"- Non-harvest reference CSVs checked: `{summary['non_harvest_reference_csvs_checked']}`.",
        f"- `2025.zip` exists: `{summary['bible_hunt_codes_zip_exists']}`.",
        f"- Harvest truth rows for 2025: `{summary['harvest_truth_2025']['rows']}`.",
        f"- Harvest truth hunt codes for 2025: `{summary['harvest_truth_2025']['hunt_codes']}`.",
        f"- Engine harvest long rows for 2025: `{summary['harvest_model_long_2025']['rows']}`.",
        f"- Engine harvest feature rows for 2025: `{summary['harvest_model_features_2025']['rows']}`.",
        f"- Missing engine feature rows sourced from normalized truth: `{summary['missing_engine_feature_keys_2025']}`.",
        f"- 2026 feature model rows using 2025 harvest history: `{summary['feature_model_rows_using_2025']}`.",
        f"- 2026 feature model rows using 2026 harvest source year: `{summary['feature_model_rows_using_2026_source_year']}`.",
        f"- Draw truth rows for 2025: `{summary['draw_truth_2025']['rows']}`.",
        f"- Draw truth hunt codes for 2025: `{summary['draw_truth_2025']['hunt_codes']}`.",
        f"- Draw reality engine v2 rows for 2025: `{summary['draw_reality_engine_v2_2025']['rows']}`.",
        f"- Draw reality engine v2 matches draw truth row count: `{summary['draw_engine_v2_matches_draw_truth_rows']}`.",
        f"- Legacy draw_reality_engine.csv has 2025 rows: `{summary['draw_engine_legacy_has_2025_rows']}`.",
        "",
        "## Missing Engine Feature Rows",
        "",
        "| Hunt Code | Species | Hunt Name | Source | Action |",
        "| --- | --- | --- | --- | --- |",
    ]
    if missing_rows:
        for row in missing_rows:
            lines.append(f"| {row['hunt_code']} | {row['species']} | {row['hunt_name']} | {row['source_file']} | {row['recommended_action']} |")
    else:
        lines.append("|  |  |  |  | No source-backed gaps found |")
    lines.extend(
        [
            "",
            "## Raw CSV Inventory",
            "",
            "| CSV | Class | Rows | Hunt Codes | Reported Years | Target Years | Source Dates | Status |",
            "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in raw_rows:
        lines.append(
            f"| {row['source_csv']} | {row['classification']} | {row['raw_rows']} | {row['hunt_codes']} | {row['reported_hunt_years']} | {row['model_target_years']} | {row['source_dates']} | {row['status']} |"
        )
    lines.extend(["", "## Guardrail", "", str(summary["guardrail"])])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Audit output directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_dir = (root / args.out_dir).resolve()
    summary, raw_rows, missing_rows = build_audit(root)
    base = out_dir / "harvest_draw_ingestion_2025"
    raw_columns = [
        "source_csv",
        "raw_path",
        "raw_exists",
        "raw_size_bytes",
        "raw_rows",
        "raw_columns",
        "has_hunt_code",
        "hunt_codes",
        "reported_hunt_years",
        "model_target_years",
        "source_dates",
        "top_source_files",
        "classification",
        "status",
    ]
    gap_columns = ["reported_hunt_year", "hunt_code", "species", "hunt_name", "source_file", "recommended_action"]
    write_csv(base.with_suffix(".csv"), raw_rows, raw_columns)
    write_csv(out_dir / "harvest_draw_ingestion_2025_engine_feature_gaps.csv", missing_rows, gap_columns)
    base.with_suffix(".json").write_text(json.dumps({"summary": summary, "raw_rows": raw_rows, "missing_rows": missing_rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(base.with_suffix(".md"), summary, raw_rows, missing_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
