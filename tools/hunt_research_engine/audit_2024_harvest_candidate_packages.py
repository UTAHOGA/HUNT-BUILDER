#!/usr/bin/env python3
"""Audit candidate 2024 harvest packages against current engine feeders.

This is a read-only promotion/hold audit for the richer 2024 harvest packages
outside the compact pipeline copy. It checks whether each package is safe to
promote, already reflected downstream, or should remain context evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUT_DIR = "audits/hunt_research_engine"
REPORTED_HUNT_YEAR = "2024"

PACKAGES = {
    "database_package": "pipeline/RAW/hunt_unit_database/harvest_results_2024_for_2025_database/harvest_reports_2024_for_2025_database",
    "elk_age_supplement": "pipeline/RAW/hunt_unit_database/harvest_results_2024_for_2025_elk_age_supplement/harvest_reports_2024_for_2025_elk_age_supplement",
    "extra_oil_supplement": "pipeline/RAW/hunt_unit_database/harvest_results_2024_for_2025_extra_oil_supplement/harvest_reports_2024_for_2025_extra_oil_supplement",
}

CURRENT_FILES = {
    "truth_features": "data_truth/harvest_results_truth/normalized/harvest_quality_features_all_years_by_hunt_code.csv",
    "truth_long": "data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv",
    "model_features": "data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv",
    "model_long": "data_model/harvest_quality/harvest_results_all_years_long.csv",
    "feature_model_2026": "data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def read_json(path: Path) -> object:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def code_value(row: dict[str, str]) -> str:
    return clean(row.get("hunt_code") or row.get("selected_hunt_code")).upper()


def year_value(row: dict[str, str]) -> str:
    return clean(row.get("reported_hunt_year") or row.get("harvest_year") or row.get("year"))


def rows_for_2024(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    year_rows = [row for row in rows if year_value(row) == REPORTED_HUNT_YEAR]
    return year_rows if year_rows else rows


def code_set(rows: list[dict[str, str]]) -> set[str]:
    return {code_value(row) for row in rows if code_value(row)}


def count_nonblank(rows: list[dict[str, str]], column: str) -> int:
    return sum(1 for row in rows if clean(row.get(column)))


def package_reports(package_dir: Path) -> list[dict[str, object]]:
    reports = []
    for path in sorted(package_dir.glob("*report.json")):
        payload = read_json(path)
        reports.append(
            {
                "report_file": path.name,
                "path": str(path),
                "loaded": bool(payload),
                "reported_hunt_year": payload.get("reported_hunt_year") if isinstance(payload, dict) else "",
                "model_target_year": payload.get("model_target_year") if isinstance(payload, dict) else "",
                "source_files": payload.get("source_files", []) if isinstance(payload, dict) else [],
                "safeguards": payload.get("safeguards", {}) if isinstance(payload, dict) else {},
                "notes": payload.get("notes", []) if isinstance(payload, dict) else [],
            }
        )
    return reports


def classify_file(package_name: str, path: Path, fields: list[str], rows_2024: list[dict[str, str]], current_truth_codes: set[str], current_model_codes: set[str]) -> tuple[str, str]:
    codes = code_set(rows_2024)
    age_columns = observed_age_columns(fields)
    has_observed_age = any(count_nonblank(rows_2024, column) for column in age_columns)
    context_metric_columns = [
        "latest_population_estimate",
        "latest_lambs_per_100_ewes",
        "latest_rams_per_100_ewes",
        "harvest_total",
        "bull_harvest",
        "cow_harvest",
        "billy_harvest",
        "nanny_harvest",
        "total_goat_harvest",
        "percent_success",
    ]
    has_context_metrics = any(column in fields and count_nonblank(rows_2024, column) for column in context_metric_columns)
    has_quota_guardrail = "do_not_use_for_permit_quota" in fields
    has_pdraw_guardrail = "do_not_use_directly_for_p_draw" in fields

    if not path.exists():
        return "BLOCKER_MISSING_FILE", "Candidate file is missing."
    if not rows_2024:
        return "HOLD_EMPTY_OR_NON_2024", "No rows were available for reported_hunt_year 2024."
    if not codes and has_observed_age:
        return "CONTEXT_PROMOTE_UNIT_LEVEL_REVIEW", "Observed age/context rows exist but lack hunt_code; use only through reviewed unit-to-hunt mapping."
    if not codes and has_context_metrics:
        return "CONTEXT_PROMOTE_UNIT_LEVEL_REVIEW", "Unit-level quality/context metrics exist but lack hunt_code; use only through reviewed unit-to-hunt mapping."
    if not codes:
        return "CONTEXT_HOLD_NO_HUNT_CODE", "Rows have no direct hunt_code key, so they cannot replace hunt-code feeder rows."
    if codes <= current_truth_codes and codes <= current_model_codes and has_quota_guardrail and has_pdraw_guardrail:
        return "REFERENCE_ALREADY_COVERED", "Hunt-code coverage is already represented downstream; keep as stronger source evidence, not a replacement."
    if codes - current_truth_codes:
        return "PROMOTION_REVIEW_CANDIDATE", "Candidate has hunt_code rows not present in normalized 2024 truth and needs source review."
    return "REVIEW_REQUIRED", "Candidate is source-like but lacks enough guardrail/context evidence for automatic promotion."


def observed_age_columns(fields: list[str]) -> list[str]:
    blocked = {"average_days", "source_page"}
    return [
        column
        for column in fields
        if "age" in column.lower() and column.lower() not in blocked and not column.lower().endswith("_page")
    ]


def summarize_candidate_file(package_name: str, path: Path, current_truth_codes: set[str], current_model_codes: set[str]) -> dict[str, object]:
    fields, rows = read_csv(path)
    rows_2024 = rows_for_2024(rows)
    codes = code_set(rows_2024)
    age_columns = observed_age_columns(fields)
    metric_columns = [
        "permits",
        "quota",
        "hunters_afield",
        "harvest_total",
        "harvest_male",
        "harvest_female",
        "percent_success",
        "average_days",
        "average_age",
        "avg_age_2024",
        "avg_age_3yr_average",
        "hunter_satisfaction",
    ]
    classification, recommendation = classify_file(package_name, path, fields, rows_2024, current_truth_codes, current_model_codes)
    return {
        "package": package_name,
        "file": path.name,
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "rows": len(rows),
        "rows_2024": len(rows_2024),
        "columns": len(fields),
        "hunt_codes": len(codes),
        "codes_missing_from_current_truth": len(codes - current_truth_codes),
        "codes_missing_from_current_model": len(codes - current_model_codes),
        "current_truth_codes_missing_from_candidate": len(current_truth_codes - codes) if codes else "",
        "age_columns": "|".join(age_columns),
        "age_nonblank_counts": json.dumps({column: count_nonblank(rows_2024, column) for column in age_columns}, sort_keys=True),
        "metric_nonblank_counts": json.dumps({column: count_nonblank(rows_2024, column) for column in metric_columns if column in fields}, sort_keys=True),
        "has_hunt_code": "hunt_code" in fields or "selected_hunt_code" in fields,
        "has_quota_guardrail": "do_not_use_for_permit_quota" in fields,
        "has_pdraw_guardrail": "do_not_use_directly_for_p_draw" in fields,
        "classification": classification,
        "recommendation": recommendation,
    }


def current_2024_rows(root: Path, key: str) -> list[dict[str, str]]:
    _, rows = read_csv(root / CURRENT_FILES[key])
    return [row for row in rows if year_value(row) == REPORTED_HUNT_YEAR]


def build_audit(root: Path) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    truth_features = current_2024_rows(root, "truth_features")
    model_features = current_2024_rows(root, "model_features")
    truth_long = current_2024_rows(root, "truth_long")
    model_long = current_2024_rows(root, "model_long")
    truth_codes = code_set(truth_features)
    model_codes = code_set(model_features)

    feature_model_fields, feature_model_rows = read_csv(root / CURRENT_FILES["feature_model_2026"])
    feature_model_using_2024 = [
        row for row in feature_model_rows if REPORTED_HUNT_YEAR in clean(row.get("harvest_feature_source_years")).split("|")
    ]

    inventory_rows: list[dict[str, object]] = []
    report_rows: list[dict[str, object]] = []
    for package_name, package_rel in PACKAGES.items():
        package_dir = root / package_rel
        for path in sorted(package_dir.rglob("*.csv")):
            inventory_rows.append(summarize_candidate_file(package_name, path, truth_codes, model_codes))
        for report in package_reports(package_dir):
            report_rows.append(
                {
                    "package": package_name,
                    "report_file": report["report_file"],
                    "path": report["path"],
                    "loaded": report["loaded"],
                    "reported_hunt_year": report["reported_hunt_year"],
                    "model_target_year": report["model_target_year"],
                    "source_file_count": len(report["source_files"]),
                    "safeguards": json.dumps(report["safeguards"], sort_keys=True),
                    "notes": json.dumps(report["notes"], sort_keys=True),
                }
            )

    all_candidate_codes: dict[str, set[str]] = {}
    for row in inventory_rows:
        path = Path(str(row["path"]))
        _, rows = read_csv(path)
        all_candidate_codes[str(row["package"])] = all_candidate_codes.get(str(row["package"]), set()) | code_set(rows_for_2024(rows))

    coverage_rows = []
    for package_name, codes in sorted(all_candidate_codes.items()):
        missing_truth_codes = sorted(truth_codes - codes) if codes else []
        new_codes = sorted(codes - truth_codes)
        coverage_rows.append(
            {
                "package": package_name,
                "candidate_hunt_codes": len(codes),
                "candidate_codes_missing_from_current_truth": len(new_codes),
                "current_truth_codes_missing_from_candidate": len(missing_truth_codes) if codes else "",
                "sample_current_truth_missing_from_candidate": "|".join(missing_truth_codes[:25]),
                "sample_candidate_missing_from_current_truth": "|".join(new_codes[:25]),
            }
        )

    classification_counts = Counter(str(row["classification"]) for row in inventory_rows)
    age_rows = [row for row in inventory_rows if "avg_age_2024" in str(row["age_columns"]) or "average_age" in str(row["age_columns"])]
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_name": "2024_harvest_candidate_package_audit",
        "result": "PASS_REVIEW_ONLY",
        "reported_hunt_year": 2024,
        "model_target_year": 2025,
        "packages_checked": len(PACKAGES),
        "candidate_csv_files_checked": len(inventory_rows),
        "candidate_report_files_loaded": sum(1 for row in report_rows if row["loaded"]),
        "classification_counts": dict(sorted(classification_counts.items())),
        "current_truth_feature_rows_2024": len(truth_features),
        "current_truth_feature_hunt_codes_2024": len(truth_codes),
        "current_model_feature_rows_2024": len(model_features),
        "current_model_feature_hunt_codes_2024": len(model_codes),
        "current_truth_long_rows_2024": len(truth_long),
        "current_model_long_rows_2024": len(model_long),
        "current_model_average_age_nonblank_2024": sum(1 for row in model_features if clean(row.get("average_age"))),
        "current_truth_average_age_nonblank_2024": sum(1 for row in truth_features if clean(row.get("average_age"))),
        "feature_model_rows_using_2024": len(feature_model_using_2024),
        "feature_model_columns": len(feature_model_fields),
        "candidate_files_with_observed_age_columns": len(age_rows),
        "guardrail": "Candidate 2024 harvest packages may support harvest quality/history and unit-level context only. They must not overwrite permit quota, draw odds, p_draw, or DATABASE.csv.",
        "recommendation": "Do not wholesale replace current 2024 harvest feeders. Keep the full database package as stronger source evidence, and treat elk-age/OIL supplements as reviewed context-feature candidates because several rows are unit-level rather than direct hunt_code rows.",
    }
    return summary, inventory_rows, report_rows, coverage_rows


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, summary: dict[str, object], inventory_rows: list[dict[str, object]], coverage_rows: list[dict[str, object]]) -> None:
    lines = [
        "# 2024 Harvest Candidate Package Audit",
        "",
        "Read-only review of the richer 2024 harvest packages supplied for possible Hunt Research use.",
        "",
        "## Summary",
        "",
        f"- Result: `{summary['result']}`.",
        f"- Candidate CSV files checked: `{summary['candidate_csv_files_checked']}`.",
        f"- Candidate report files loaded: `{summary['candidate_report_files_loaded']}`.",
        f"- Current normalized 2024 feature rows: `{summary['current_truth_feature_rows_2024']}`.",
        f"- Current model 2024 feature rows: `{summary['current_model_feature_rows_2024']}`.",
        f"- Current model rows with observed `average_age`: `{summary['current_model_average_age_nonblank_2024']}`.",
        f"- Current truth rows with observed `average_age`: `{summary['current_truth_average_age_nonblank_2024']}`.",
        f"- 2026 feature model rows using 2024 harvest history: `{summary['feature_model_rows_using_2024']}`.",
        "",
        "## Recommendation",
        "",
        str(summary["recommendation"]),
        "",
        "## Package Coverage",
        "",
        "| Package | Candidate Hunt Codes | New Codes vs Current Truth | Current Truth Codes Missing From Candidate | Sample Missing From Candidate |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in coverage_rows:
        lines.append(
            f"| {row['package']} | {row['candidate_hunt_codes']} | {row['candidate_codes_missing_from_current_truth']} | {row['current_truth_codes_missing_from_candidate']} | {row['sample_current_truth_missing_from_candidate']} |"
        )
    lines.extend(
        [
            "",
            "## Candidate File Classifications",
            "",
            "| Package | File | Rows 2024 | Hunt Codes | Classification | Recommendation |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in inventory_rows:
        lines.append(
            f"| {row['package']} | {row['file']} | {row['rows_2024']} | {row['hunt_codes']} | {row['classification']} | {row['recommendation']} |"
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
    summary, inventory_rows, report_rows, coverage_rows = build_audit(root)
    base = out_dir / "harvest_candidate_packages_2024"
    inventory_columns = [
        "package",
        "file",
        "path",
        "exists",
        "size_bytes",
        "rows",
        "rows_2024",
        "columns",
        "hunt_codes",
        "codes_missing_from_current_truth",
        "codes_missing_from_current_model",
        "current_truth_codes_missing_from_candidate",
        "age_columns",
        "age_nonblank_counts",
        "metric_nonblank_counts",
        "has_hunt_code",
        "has_quota_guardrail",
        "has_pdraw_guardrail",
        "classification",
        "recommendation",
    ]
    report_columns = [
        "package",
        "report_file",
        "path",
        "loaded",
        "reported_hunt_year",
        "model_target_year",
        "source_file_count",
        "safeguards",
        "notes",
    ]
    coverage_columns = [
        "package",
        "candidate_hunt_codes",
        "candidate_codes_missing_from_current_truth",
        "current_truth_codes_missing_from_candidate",
        "sample_current_truth_missing_from_candidate",
        "sample_candidate_missing_from_current_truth",
    ]
    write_csv(base.with_suffix(".csv"), inventory_rows, inventory_columns)
    write_csv(out_dir / "harvest_candidate_packages_2024_reports.csv", report_rows, report_columns)
    write_csv(out_dir / "harvest_candidate_packages_2024_coverage.csv", coverage_rows, coverage_columns)
    base.with_suffix(".json").write_text(
        json.dumps(
            {
                "summary": summary,
                "inventory_rows": inventory_rows,
                "report_rows": report_rows,
                "coverage_rows": coverage_rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    write_markdown(base.with_suffix(".md"), summary, inventory_rows, coverage_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
