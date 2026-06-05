#!/usr/bin/env python3
"""Audit 2022-for-2023 harvest package ingestion for Hunt Research feeds.

This read-only audit checks the generated 2022 harvest package against
normalized harvest truth, engine-facing harvest feature history, and 2022
draw-result surfaces. It does not mutate source, truth, engine, or runtime
files.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUT_DIR = "audits/hunt_research_engine"
REPORTED_HUNT_YEAR = "2022"
MODEL_TARGET_YEAR = "2023"
AUDIT_NAME = "2022_harvest_database_ingestion"

RAW_PACKAGE_FILES = [
    "harvest_quality_features_by_hunt_code_2022_for_2023.csv",
    "harvest_results_2022_for_2023_all_long.csv",
    "harvest_results_2022_for_2023_antlerless.csv",
    "harvest_results_2022_for_2023_black_bear.csv",
    "harvest_results_2022_for_2023_cougar.csv",
    "harvest_results_2022_for_2023_hunt_code_keyed.csv",
    "harvest_results_2022_for_2023_le_oial_all.csv",
    "harvest_results_2022_for_2023_summary.csv",
]

PACKAGE_SUPPORT_FILES = [
    "utah_harvest_results_2022_for_2023.sqlite",
    "harvest_results_2022_for_2023_database_report.json",
    "harvest_results_2022_for_2023_database_report.md",
]

FILES = {
    "raw_package_dir": "pipeline/RAW/hunt_unit_database/2023/harvest_results_2022_for_2023_database",
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


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def code_value(row: dict[str, str]) -> str:
    return clean(row.get("hunt_code") or row.get("selected_hunt_code")).upper()


def code_count(rows: list[dict[str, str]]) -> int:
    return len({code_value(row) for row in rows if code_value(row)})


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


def source_summary(path: Path) -> dict[str, object]:
    fields, rows = read_csv(path)
    source_classes = sorted({clean(row.get("source_class")) for row in rows if clean(row.get("source_class"))})
    years = sorted({clean(row.get("reported_hunt_year")) for row in rows if clean(row.get("reported_hunt_year"))})
    targets = sorted({clean(row.get("model_target_year")) for row in rows if clean(row.get("model_target_year"))})
    source_files = Counter(clean(row.get("source_file")) for row in rows if clean(row.get("source_file")))
    species = Counter(clean(row.get("species")) for row in rows if clean(row.get("species")))
    return {
        "source_csv": path.name,
        "raw_path": str(path),
        "raw_exists": path.exists(),
        "raw_size_bytes": path.stat().st_size if path.exists() else 0,
        "raw_rows": len(rows),
        "raw_columns": len(fields),
        "has_hunt_code": "hunt_code" in fields or "selected_hunt_code" in fields,
        "hunt_codes": code_count(rows),
        "reported_hunt_years": "|".join(years),
        "model_target_years": "|".join(targets),
        "source_classes": "|".join(source_classes),
        "top_source_files": json.dumps(dict(source_files.most_common(5)), sort_keys=True),
        "species_counts": json.dumps(dict(species.most_common(8)), sort_keys=True),
        "status": "RAW_GENERATED_CSV_PRESENT" if path.exists() else "RAW_GENERATED_CSV_MISSING",
    }


def support_summary(path: Path) -> dict[str, object]:
    return {
        "support_file": path.name,
        "raw_path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "status": "SUPPORT_FILE_PRESENT" if path.exists() else "SUPPORT_FILE_MISSING",
    }


def build_audit(
    root: Path,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    raw_dir = root / FILES["raw_package_dir"]
    raw_rows = [source_summary(raw_dir / name) for name in RAW_PACKAGE_FILES]
    support_rows = [support_summary(raw_dir / name) for name in PACKAGE_SUPPORT_FILES]

    _, truth_long = read_csv(root / FILES["harvest_truth_long"])
    _, truth_features = read_csv(root / FILES["harvest_truth_features"])
    _, model_long = read_csv(root / FILES["harvest_model_long"])
    _, model_features = read_csv(root / FILES["harvest_model_features"])
    _, feature_model = read_csv(root / FILES["harvest_feature_model_2026"])
    _, draw_truth = read_csv(root / FILES["draw_truth_long"])
    _, draw_legacy = read_csv(root / FILES["draw_reality_engine"])
    _, draw_v2 = read_csv(root / FILES["draw_reality_engine_v2"])

    truth_keys = {
        feature_key(row) for row in truth_features if feature_key(row)[0] == REPORTED_HUNT_YEAR and feature_key(row)[1]
    }
    model_keys = {
        feature_key(row) for row in model_features if feature_key(row)[0] == REPORTED_HUNT_YEAR and feature_key(row)[1]
    }
    truth_by_key = {
        feature_key(row): row for row in truth_features if feature_key(row)[0] == REPORTED_HUNT_YEAR and feature_key(row)[1]
    }
    model_by_key = {
        feature_key(row): row for row in model_features if feature_key(row)[0] == REPORTED_HUNT_YEAR and feature_key(row)[1]
    }

    missing_rows = [
        {
            "reported_hunt_year": key[0],
            "hunt_code": key[1],
            "species": clean(truth_by_key[key].get("species")),
            "hunt_name": clean(truth_by_key[key].get("hunt_name")),
            "source_file": clean(truth_by_key[key].get("source_file")),
            "recommended_action": "APPEND_TO_ENGINE_FEATURE_FEEDER_FROM_NORMALIZED_TRUTH",
        }
        for key in sorted(truth_keys - model_keys)
    ]
    extra_rows = [
        {
            "reported_hunt_year": key[0],
            "hunt_code": key[1],
            "species": clean(model_by_key[key].get("species")),
            "hunt_name": clean(model_by_key[key].get("hunt_name")),
            "source_file": clean(model_by_key[key].get("source_file")),
            "classification": "ENGINE_SUPPLEMENTAL_FEATURE_ROW_NOT_IN_NORMALIZED_TRUTH_FEATURES",
            "review_status": "KEEP_FOR_ENGINE_CONTEXT_UNLESS_LATER_TRUTH_REVIEW_DEMOTES",
        }
        for key in sorted(model_keys - truth_keys)
    ]

    feature_using_year = [
        row for row in feature_model if REPORTED_HUNT_YEAR in clean(row.get("harvest_feature_source_years")).split("|")
    ]
    draw_truth_year = summarize_year(draw_truth, "year", REPORTED_HUNT_YEAR)
    draw_v2_year = summarize_year(draw_v2, "year", REPORTED_HUNT_YEAR)
    draw_legacy_year = summarize_year(draw_legacy, "year", REPORTED_HUNT_YEAR)
    package_report = read_json(raw_dir / "harvest_results_2022_for_2023_database_report.json")
    zip_path = Path("C:/Users/tyler/Desktop/BIBLE HUNT CODES/2022.zip")
    result = "PASS" if not missing_rows else "PASS_WITH_SOURCE_BACKED_ENGINE_FEATURE_GAPS"

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_name": AUDIT_NAME,
        "result": result,
        "reported_hunt_year": int(REPORTED_HUNT_YEAR),
        "model_target_year": int(MODEL_TARGET_YEAR),
        "raw_package_csvs_checked": len(raw_rows),
        "support_files_checked": len(support_rows),
        "raw_status_counts": dict(sorted(Counter(clean(row["status"]) for row in raw_rows).items())),
        "support_status_counts": dict(sorted(Counter(clean(row["status"]) for row in support_rows).items())),
        "bible_hunt_codes_zip": str(zip_path),
        "bible_hunt_codes_zip_exists": zip_path.exists(),
        "bible_hunt_codes_zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
        "package_report_loaded": bool(package_report),
        "package_report": package_report,
        "harvest_truth_2022": summarize_year(truth_long, "reported_hunt_year", REPORTED_HUNT_YEAR),
        "harvest_truth_features_2022": summarize_year(truth_features, "reported_hunt_year", REPORTED_HUNT_YEAR),
        "harvest_model_long_2022": summarize_year(model_long, "reported_hunt_year", REPORTED_HUNT_YEAR),
        "harvest_model_features_2022": summarize_year(model_features, "reported_hunt_year", REPORTED_HUNT_YEAR),
        "truth_feature_keys_2022": len(truth_keys),
        "engine_feature_keys_2022": len(model_keys),
        "missing_engine_feature_keys_2022": len(missing_rows),
        "engine_feature_extra_keys_2022": len(extra_rows),
        "feature_model_rows_using_2022": len(feature_using_year),
        "feature_model_hunt_codes_using_2022": len({code_value(row) for row in feature_using_year if code_value(row)}),
        "draw_truth_2022": draw_truth_year,
        "draw_reality_engine_v2_2022": draw_v2_year,
        "draw_reality_engine_legacy_2022": draw_legacy_year,
        "draw_engine_v2_matches_draw_truth_rows": draw_v2_year["rows"] == draw_truth_year["rows"],
        "draw_engine_legacy_matches_draw_truth_rows": draw_legacy_year["rows"] == draw_truth_year["rows"],
        "draw_engine_legacy_row_delta_vs_truth": int(draw_legacy_year["rows"]) - int(draw_truth_year["rows"]),
        "guardrail": "2022 harvest rows are quality/history inputs only. They are not permit quota truth and are not direct p_draw truth.",
        "recommended_next_step": "No 2022 source-backed harvest feature feeder gaps remain. Use draw_reality_engine_v2.csv as the complete 2022 draw surface; legacy draw_reality_engine.csv is short for 2022 and should not be treated as complete draw truth.",
    }
    return summary, raw_rows, support_rows, missing_rows, extra_rows


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(
    path: Path,
    summary: dict[str, object],
    raw_rows: list[dict[str, object]],
    support_rows: list[dict[str, object]],
    missing_rows: list[dict[str, object]],
    extra_rows: list[dict[str, object]],
) -> None:
    lines = [
        "# 2022 Harvest Database Ingestion Audit",
        "",
        "Read-only alignment proof for the 2022-for-2023 harvest database package.",
        "",
        "## Summary",
        "",
        f"- Result: `{summary['result']}`.",
        f"- Reported hunt year: `{summary['reported_hunt_year']}`.",
        f"- Model target year: `{summary['model_target_year']}`.",
        f"- Raw package CSVs checked: `{summary['raw_package_csvs_checked']}`.",
        f"- Support files checked: `{summary['support_files_checked']}`.",
        f"- `2022.zip` exists: `{summary['bible_hunt_codes_zip_exists']}`.",
        f"- Harvest truth rows for 2022: `{summary['harvest_truth_2022']['rows']}`.",
        f"- Harvest truth hunt codes for 2022: `{summary['harvest_truth_2022']['hunt_codes']}`.",
        f"- Engine harvest long rows for 2022: `{summary['harvest_model_long_2022']['rows']}`.",
        f"- Engine harvest feature rows for 2022: `{summary['harvest_model_features_2022']['rows']}`.",
        f"- Missing engine feature rows sourced from normalized truth: `{summary['missing_engine_feature_keys_2022']}`.",
        f"- Engine supplemental feature rows not in normalized truth feature table: `{summary['engine_feature_extra_keys_2022']}`.",
        f"- 2026 feature model rows using 2022 harvest history: `{summary['feature_model_rows_using_2022']}`.",
        f"- Draw truth rows for 2022: `{summary['draw_truth_2022']['rows']}`.",
        f"- Draw truth hunt codes for 2022: `{summary['draw_truth_2022']['hunt_codes']}`.",
        f"- Draw reality engine v2 rows for 2022: `{summary['draw_reality_engine_v2_2022']['rows']}`.",
        f"- Draw reality engine v2 matches draw truth row count: `{summary['draw_engine_v2_matches_draw_truth_rows']}`.",
        f"- Legacy draw_reality_engine.csv rows for 2022: `{summary['draw_reality_engine_legacy_2022']['rows']}`.",
        f"- Legacy draw_reality_engine.csv row delta vs draw truth: `{summary['draw_engine_legacy_row_delta_vs_truth']}`.",
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
            "## Supplemental Engine Feature Rows",
            "",
            f"`{len(extra_rows)}` engine 2022 feature rows are present beyond the normalized truth feature table. These are review-visible supplemental context rows, not missing truth rows.",
            "",
            "## Raw CSV Inventory",
            "",
            "| CSV | Rows | Hunt Codes | Reported Years | Target Years | Source Classes | Status |",
            "| --- | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in raw_rows:
        lines.append(
            f"| {row['source_csv']} | {row['raw_rows']} | {row['hunt_codes']} | {row['reported_hunt_years']} | {row['model_target_years']} | {row['source_classes']} | {row['status']} |"
        )
    lines.extend(["", "## Support Files", "", "| File | Size Bytes | Status |", "| --- | ---: | --- |"])
    for row in support_rows:
        lines.append(f"| {row['support_file']} | {row['size_bytes']} | {row['status']} |")
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
    summary, raw_rows, support_rows, missing_rows, extra_rows = build_audit(root)
    base = out_dir / "harvest_database_ingestion_2022"
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
        "source_classes",
        "top_source_files",
        "species_counts",
        "status",
    ]
    support_columns = ["support_file", "raw_path", "exists", "size_bytes", "status"]
    gap_columns = ["reported_hunt_year", "hunt_code", "species", "hunt_name", "source_file", "recommended_action"]
    extra_columns = ["reported_hunt_year", "hunt_code", "species", "hunt_name", "source_file", "classification", "review_status"]
    write_csv(base.with_suffix(".csv"), raw_rows, raw_columns)
    write_csv(out_dir / "harvest_database_ingestion_2022_support_files.csv", support_rows, support_columns)
    write_csv(out_dir / "harvest_database_ingestion_2022_engine_feature_gaps.csv", missing_rows, gap_columns)
    write_csv(out_dir / "harvest_database_ingestion_2022_engine_feature_extras.csv", extra_rows, extra_columns)
    base.with_suffix(".json").write_text(
        json.dumps(
            {
                "summary": summary,
                "raw_rows": raw_rows,
                "support_rows": support_rows,
                "missing_rows": missing_rows,
                "extra_rows": extra_rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    write_markdown(base.with_suffix(".md"), summary, raw_rows, support_rows, missing_rows, extra_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
