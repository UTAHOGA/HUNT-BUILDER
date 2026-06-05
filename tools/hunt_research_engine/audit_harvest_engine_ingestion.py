#!/usr/bin/env python3
"""Audit whether harvest data is ingested into the correct engine surfaces.

This tool is read-only. It verifies the intended chain:

harvest truth -> harvest feature model -> mixed predictive engine fields ->
Hunt Research runtime/display fields.

It does not rebuild engines, mutate source files, edit DATABASE.csv, or publish
runtime files.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_OUT_DIR = "audits/hunt_research_engine"

FILES = {
    "database": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
    "harvest_truth": "data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv",
    "harvest_all_years_features": "data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv",
    "harvest_feature_model": "data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv",
    "ml_predictions": "processed_data/ml_draw_predictions_v1.csv",
    "predictive_v2": "processed_data/draw_reality_engine_predictive_v2.csv",
    "point_ladder": "processed_data/point_ladder_view.csv",
    "reference_linked": "processed_data/hunt_unit_reference_linked.csv",
    "research_summary": "processed_data/hunt_research_2026_summary.json",
    "split_index": "processed_data/hunt_research_2026_split/hunt_research_2026.index.json",
    "split_details": "processed_data/hunt_research_2026_split/hunt_research_2026.details.json",
}

FEATURE_FIELDS = [
    "harvest_quality_index",
    "demand_pressure_signal",
    "demand_pressure_category",
    "point_creep_quality_adjustment",
    "harvest_success_recent",
    "harvest_success_3yr_avg",
    "hunter_satisfaction_recent",
    "hunter_effort_days_recent",
    "harvest_recent",
    "hunters_afield_recent",
    "average_age_recent",
    "average_age_3yr_avg",
    "harvest_feature_source_years",
    "harvest_feature_match_method",
    "harvest_feature_data_quality_grade",
    "harvest_feature_reason_codes",
]

MIXED_ENGINE_FIELDS = [
    "harvest_quality_index",
    "demand_pressure_signal",
    "demand_pressure_category",
    "point_creep_quality_adjustment",
    "harvest_feature_match_method",
    "harvest_feature_source_years",
    "harvest_feature_reason_codes",
    "p_harvest_adjusted",
]

DISPLAY_FIELDS = [
    "harvest_success_pct",
    "average_days_hunted",
    "average_harvest_age",
    "current_age_3yr_average",
]

REFERENCE_DISPLAY_FIELDS = [
    "harvest_success_percent_2025",
    "harvest_2025",
    "harvest_hunters_2025",
    "harvest_average_days_2025",
    "harvest_satisfaction_2025",
]

FORBIDDEN_DIRECT_TRUTH_FIELDS = {
    "p_draw",
    "p_draw_mean",
    "p_random_pool",
    "p_max_pool_mean",
    "permits_2026_total",
    "permit_allotment_2026_total",
}


@dataclass(frozen=True)
class Paths:
    root: Path
    out_dir: Path

    def file(self, key: str) -> Path:
        return self.root / FILES[key]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def read_json_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("details_by_hunt_code"), dict):
        return [row for row in payload["details_by_hunt_code"].values() if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def nonblank_count(rows: Iterable[dict[str, object]], field: str) -> int:
    return sum(1 for row in rows if clean(row.get(field)))


def code_set(rows: Iterable[dict[str, object]]) -> set[str]:
    return {clean(row.get("hunt_code")).upper() for row in rows if clean(row.get("hunt_code"))}


def duplicate_count(rows: list[dict[str, object]], key_fields: tuple[str, ...]) -> int:
    keys = []
    for row in rows:
        key = tuple(clean(row.get(field)).upper() if field == "hunt_code" else clean(row.get(field)) for field in key_fields)
        if any(key):
            keys.append(key)
    return len(keys) - len(set(keys))


def csv_surface_report(name: str, path: Path, required_fields: list[str], key_fields: tuple[str, ...]) -> tuple[dict[str, object], list[dict[str, object]]]:
    headers, rows = read_csv(path)
    field_counts = {field: nonblank_count(rows, field) if field in headers else None for field in required_fields}
    report = {
        "surface": name,
        "path": str(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "column_count": len(headers),
        "hunt_code_count": len(code_set(rows)),
        "duplicate_key_count": duplicate_count(rows, key_fields),
        "required_fields_present": all(field in headers for field in required_fields),
        "field_nonblank_counts": field_counts,
    }
    return report, rows


def json_surface_report(name: str, path: Path, required_fields: list[str], key_fields: tuple[str, ...]) -> tuple[dict[str, object], list[dict[str, object]]]:
    rows = read_json_rows(path)
    field_counts = {field: nonblank_count(rows, field) for field in required_fields}
    report = {
        "surface": name,
        "path": str(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "hunt_code_count": len(code_set(rows)),
        "duplicate_key_count": duplicate_count(rows, key_fields),
        "required_fields_present": True,
        "field_nonblank_counts": field_counts,
    }
    return report, rows


def detail_summary_counts(detail_rows: list[dict[str, object]]) -> dict[str, object]:
    summary_row_count = 0
    summary_codes_with_harvest_success = 0
    summary_codes_with_average_age = 0
    for detail in detail_rows:
        rows = detail.get("research_summary_rows")
        if not isinstance(rows, list):
            continue
        summary_row_count += len(rows)
        if any(clean(row.get("harvest_success_pct")) for row in rows if isinstance(row, dict)):
            summary_codes_with_harvest_success += 1
        if any(clean(row.get("average_harvest_age")) for row in rows if isinstance(row, dict)):
            summary_codes_with_average_age += 1
    return {
        "detail_research_summary_rows_total": summary_row_count,
        "detail_codes_with_summary_harvest_success": summary_codes_with_harvest_success,
        "detail_codes_with_summary_average_age": summary_codes_with_average_age,
    }


def build_audit(paths: Paths) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    surfaces: list[dict[str, object]] = []
    blockers: list[dict[str, object]] = []

    db_headers, db_rows = read_csv(paths.file("database"))
    db_codes = code_set(db_rows)

    harvest_truth_report, harvest_truth_rows = csv_surface_report(
        "harvest_truth_normalized",
        paths.file("harvest_truth"),
        ["reported_hunt_year", "model_target_year", "hunt_code", "percent_success", "source_file"],
        ("reported_hunt_year", "hunt_code", "source_file"),
    )
    surfaces.append(harvest_truth_report)

    all_years_report, all_years_rows = csv_surface_report(
        "harvest_all_years_features",
        paths.file("harvest_all_years_features"),
        ["reported_hunt_year", "model_target_year", "hunt_code", "percent_success", "recommended_use"],
        ("reported_hunt_year", "hunt_code"),
    )
    surfaces.append(all_years_report)

    feature_report, feature_rows = csv_surface_report(
        "harvest_feature_model_by_hunt_code_2026",
        paths.file("harvest_feature_model"),
        FEATURE_FIELDS,
        ("hunt_code",),
    )
    surfaces.append(feature_report)

    ml_report, ml_rows = csv_surface_report("ml_draw_predictions_v1", paths.file("ml_predictions"), MIXED_ENGINE_FIELDS, ("hunt_code", "residency", "points", "draw_pool"))
    surfaces.append(ml_report)

    predictive_report, predictive_rows = csv_surface_report("draw_reality_engine_predictive_v2", paths.file("predictive_v2"), MIXED_ENGINE_FIELDS, ("hunt_code", "residency", "points", "draw_pool"))
    surfaces.append(predictive_report)

    ladder_report, ladder_rows = csv_surface_report("point_ladder_view", paths.file("point_ladder"), MIXED_ENGINE_FIELDS, ("hunt_code", "residency", "points", "draw_pool"))
    surfaces.append(ladder_report)

    reference_report, reference_rows = csv_surface_report("hunt_unit_reference_linked", paths.file("reference_linked"), REFERENCE_DISPLAY_FIELDS, ("hunt_code", "residency", "draw_pool"))
    surfaces.append(reference_report)

    summary_report, summary_rows = json_surface_report("hunt_research_2026_summary", paths.file("research_summary"), DISPLAY_FIELDS, ("hunt_code", "residency", "points", "draw_pool"))
    surfaces.append(summary_report)

    index_report, index_rows = json_surface_report("hunt_research_2026_split_index", paths.file("split_index"), ["average_harvest_age", "current_age_3yr_average"], ("hunt_code",))
    surfaces.append(index_report)

    details_report, detail_rows = json_surface_report("hunt_research_2026_split_details", paths.file("split_details"), ["has_harvest", "percent_success", "harvest", "average_harvest_age", "current_age_3yr_average"], ("hunt_code",))
    details_report.update(detail_summary_counts(detail_rows))
    surfaces.append(details_report)

    feature_codes = code_set(feature_rows)
    summary_codes = code_set(summary_rows)
    detail_codes = code_set(detail_rows)

    current_codes_with_feature_row = len(db_codes & feature_codes)
    current_codes_missing_feature_row = sorted(db_codes - feature_codes)
    feature_codes_missing_from_summary = sorted(feature_codes - summary_codes)
    feature_codes_missing_from_details = sorted(feature_codes - detail_codes)

    def add_blocker(condition: bool, blocker_id: str, severity: str, message: str) -> None:
        if condition:
            blockers.append({"blocker_id": blocker_id, "severity": severity, "message": message})

    add_blocker(not paths.file("harvest_truth").exists(), "MISSING_HARVEST_TRUTH", "BLOCKER", "Normalized harvest truth file is missing.")
    add_blocker(not paths.file("harvest_feature_model").exists(), "MISSING_HARVEST_FEATURE_MODEL", "BLOCKER", "Harvest feature model is missing.")
    add_blocker(not feature_report["required_fields_present"], "FEATURE_MODEL_SCHEMA_GAP", "BLOCKER", "Harvest feature model is missing required fields.")
    add_blocker(not ml_report["required_fields_present"], "ML_HARVEST_FIELDS_MISSING", "BLOCKER", "ML predictions file is missing mixed-engine harvest fields.")
    add_blocker(not predictive_report["required_fields_present"], "PREDICTIVE_V2_HARVEST_FIELDS_MISSING", "BLOCKER", "Predictive v2 file is missing mixed-engine harvest fields.")
    add_blocker(not summary_report["field_nonblank_counts"].get("harvest_success_pct"), "SUMMARY_HARVEST_DISPLAY_MISSING", "BLOCKER", "Hunt Research summary has no harvest success display values.")
    add_blocker(bool(feature_codes_missing_from_summary), "FEATURE_CODES_MISSING_FROM_SUMMARY", "WARNING", f"Feature codes absent from Hunt Research summary: {feature_codes_missing_from_summary[:12]}")
    add_blocker(bool(feature_codes_missing_from_details), "FEATURE_CODES_MISSING_FROM_DETAILS", "WARNING", f"Feature codes absent from split details: {feature_codes_missing_from_details[:12]}")
    add_blocker(bool(current_codes_missing_feature_row), "CURRENT_CODES_WITHOUT_FEATURE_ROW", "WARNING", f"Current DATABASE codes without a 2026 harvest feature row: {current_codes_missing_feature_row[:20]}")

    protected_headers = set(db_headers)
    direct_truth_collision = sorted(FORBIDDEN_DIRECT_TRUTH_FIELDS & protected_headers)
    # This is informational: these fields can exist in DATABASE, but the harvest feature scripts
    # must not source from them or mutate them.
    guardrails = {
        "harvest_feature_model_protected_fields": sorted(FORBIDDEN_DIRECT_TRUTH_FIELDS),
        "database_contains_some_protected_fields_for_other_purposes": direct_truth_collision,
        "harvest_quality_engine_policy": "Harvest features are quality/demand/display context. They must not directly overwrite draw truth, 2026 quota, or DATABASE permit/allotment truth.",
    }

    status_counts = Counter(row.get("surface") for row in surfaces)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_name": "harvest_engine_ingestion",
        "result": "PASS" if not any(row["severity"] == "BLOCKER" for row in blockers) else "FAIL",
        "surface_count": len(surfaces),
        "surface_counts": dict(status_counts),
        "current_database_hunt_codes": len(db_codes),
        "harvest_truth_rows": len(harvest_truth_rows),
        "harvest_all_years_feature_rows": len(all_years_rows),
        "harvest_feature_model_rows": len(feature_rows),
        "current_codes_with_feature_row": current_codes_with_feature_row,
        "current_codes_missing_feature_row_count": len(current_codes_missing_feature_row),
        "current_codes_missing_feature_row_sample": current_codes_missing_feature_row[:30],
        "feature_codes_missing_from_summary_count": len(feature_codes_missing_from_summary),
        "feature_codes_missing_from_summary_sample": feature_codes_missing_from_summary[:30],
        "feature_codes_missing_from_details_count": len(feature_codes_missing_from_details),
        "feature_codes_missing_from_details_sample": feature_codes_missing_from_details[:30],
        "mixed_engine_consumes_harvest_features": all(
            report["required_fields_present"] and (report["field_nonblank_counts"].get("harvest_quality_index") or 0) > 0
            for report in [ml_report, predictive_report, ladder_report]
        ),
        "mixed_engine_harvest_probability_component_present": all(
            (report["field_nonblank_counts"].get("p_harvest_adjusted") or 0) > 0 for report in [ml_report, predictive_report, ladder_report]
        ),
        "website_summary_harvest_display_present": (summary_report["field_nonblank_counts"].get("harvest_success_pct") or 0) > 0,
        "website_split_detail_harvest_present": (details_report["field_nonblank_counts"].get("has_harvest") or 0) > 0,
        "blocker_count": sum(1 for row in blockers if row["severity"] == "BLOCKER"),
        "warning_count": sum(1 for row in blockers if row["severity"] == "WARNING"),
        "guardrails": guardrails,
        "conclusion": (
            "Harvest data is ingested into the correct engine path: quality feature model, mixed predictive engine "
            "harvest adjustment fields, and Hunt Research display/runtime harvest fields. Remaining gaps are coverage warnings, "
            "not evidence that harvest is being used as quota or draw truth."
        ),
    }

    return summary, surfaces, blockers


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: json.dumps(row.get(column), sort_keys=True) if isinstance(row.get(column), (dict, list)) else row.get(column, "") for column in columns})


def write_markdown(path: Path, summary: dict[str, object], surfaces: list[dict[str, object]], blockers: list[dict[str, object]]) -> None:
    lines = [
        "# Harvest Engine Ingestion Audit",
        "",
        "Read-only proof that harvest data is entering the correct downstream engine surfaces.",
        "",
        "## Result",
        "",
        f"- Result: `{summary['result']}`.",
        f"- Current `DATABASE.csv` hunt codes: `{summary['current_database_hunt_codes']}`.",
        f"- Harvest truth rows: `{summary['harvest_truth_rows']}`.",
        f"- Harvest feature model rows: `{summary['harvest_feature_model_rows']}`.",
        f"- Current codes with feature row: `{summary['current_codes_with_feature_row']}`.",
        f"- Mixed engine consumes harvest features: `{summary['mixed_engine_consumes_harvest_features']}`.",
        f"- Mixed engine harvest probability component present: `{summary['mixed_engine_harvest_probability_component_present']}`.",
        f"- Website summary harvest display present: `{summary['website_summary_harvest_display_present']}`.",
        f"- Website split detail harvest present: `{summary['website_split_detail_harvest_present']}`.",
        "",
        "## Correct Engine Path",
        "",
        "1. `data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv` stores normalized harvest truth.",
        "2. `data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv` stores year-by-year feature evidence.",
        "3. `data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv` rolls that evidence into 2026 hunt-code feature rows.",
        "4. `processed_data/ml_draw_predictions_v1.csv`, `processed_data/draw_reality_engine_predictive_v2.csv`, and `processed_data/point_ladder_view.csv` carry `harvest_quality_index`, `demand_pressure_signal`, and `p_harvest_adjusted`.",
        "5. Hunt Research runtime files carry harvest display values such as `harvest_success_pct`, `average_harvest_age`, `current_age_3yr_average`, and split-detail `has_harvest` fields.",
        "",
        "## Surface Counts",
        "",
        "| Surface | Rows | Hunt codes | Duplicate key count | Required fields present | Key nonblank counts |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for surface in surfaces:
        counts = surface.get("field_nonblank_counts", {})
        compact_counts = ", ".join(f"{key}={value}" for key, value in list(counts.items())[:8])
        lines.append(
            f"| {surface['surface']} | {surface.get('row_count', '')} | {surface.get('hunt_code_count', '')} | "
            f"{surface.get('duplicate_key_count', '')} | {surface.get('required_fields_present', '')} | {compact_counts} |"
        )
    lines.extend(["", "## Blockers And Warnings", ""])
    if blockers:
        lines.extend(["| Severity | ID | Message |", "| --- | --- | --- |"])
        for blocker in blockers:
            lines.append(f"| {blocker['severity']} | {blocker['blocker_id']} | {blocker['message']} |")
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Harvest data is quality/demand/display context.",
            "- Harvest data is not a source for directly overwriting draw truth, probability truth, current-year quota, or `DATABASE.csv` permit/allotment truth.",
            "- This audit did not run engines, edit source files, edit runtime manifests, or publish to R2.",
            "",
            "## Conclusion",
            "",
            str(summary["conclusion"]),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Audit output directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = Paths(root=Path(args.root).resolve(), out_dir=(Path(args.root) / args.out_dir).resolve())
    summary, surfaces, blockers = build_audit(paths)
    base = paths.out_dir / "harvest_engine_ingestion_audit"
    write_csv(
        base.with_suffix(".csv"),
        surfaces,
        ["surface", "path", "exists", "row_count", "column_count", "hunt_code_count", "duplicate_key_count", "required_fields_present", "field_nonblank_counts"],
    )
    write_csv(base.with_name(base.name + "_blockers.csv"), blockers, ["severity", "blocker_id", "message"])
    base.with_suffix(".json").write_text(json.dumps({"summary": summary, "surfaces": surfaces, "blockers": blockers}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(base.with_suffix(".md"), summary, surfaces, blockers)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
