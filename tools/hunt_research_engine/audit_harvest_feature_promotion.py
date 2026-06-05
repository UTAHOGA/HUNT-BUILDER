#!/usr/bin/env python3
"""Audit harvest feature readiness for the Hunt Research runtime.

This tool is intentionally read-only. It compares the current 2026 hunt-code
universe against the existing harvest truth and feature surfaces, then reports
which harvest fields are safe display/model context and which need review.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_DATABASE = "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
DEFAULT_HARVEST_FEATURES = "data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv"
DEFAULT_HARVEST_LONG = "data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv"
DEFAULT_SUMMARY = "processed_data/hunt_research_2026_summary.json"

SAFE_DISPLAY_FIELDS = [
    "harvest_success_recent",
    "harvest_success_3yr_avg",
    "hunter_effort_days_recent",
    "hunter_effort_days_3yr_avg",
    "harvest_recent",
    "harvest_3yr_avg",
    "hunters_afield_recent",
    "hunters_afield_3yr_avg",
    "average_age_recent",
    "average_age_3yr_avg",
    "harvest_quality_index",
    "demand_pressure_signal",
    "demand_pressure_category",
]

SAFE_MODEL_FEATURE_FIELDS = [
    "harvest_quality_index",
    "demand_pressure_signal",
    "point_creep_quality_adjustment",
    "harvest_success_3yr_avg",
    "harvest_success_trend_direction",
    "hunter_effort_days_3yr_avg",
    "harvest_3yr_avg",
    "hunters_afield_3yr_avg",
    "average_age_3yr_avg",
    "population_signal_recent",
    "pursuit_pressure_recent",
]

FORBIDDEN_OUTPUT_FIELDS = [
    "p_draw",
    "p_draw_pct",
    "display_odds_pct",
    "p_max_pool_mean",
    "p_random_pool",
    "permits_2026_res",
    "permits_2026_nr",
    "permits_2026_total",
    "permit_allotment_2026_res",
    "permit_allotment_2026_nr",
    "permit_allotment_2026_total",
    "max_point_permits_2026",
    "random_permits_2026",
]


@dataclass(frozen=True)
class AuditPaths:
    root: Path
    database: Path
    harvest_features: Path
    harvest_long: Path
    summary: Path
    out_dir: Path


def norm(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "NOT_APPLICABLE") for field in fieldnames})


def load_summary_codes(path: Path) -> tuple[set[str], dict[str, Counter]]:
    if not path.exists():
        return set(), {}
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("rows", [])
    codes: set[str] = set()
    nonblank_by_code: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = norm(row.get("hunt_code"))
        if not code:
            continue
        codes.add(code)
        for field in SAFE_DISPLAY_FIELDS:
            if norm(row.get(field)):
                nonblank_by_code[code][field] += 1
    return codes, nonblank_by_code


def build_audit(paths: AuditPaths) -> tuple[dict[str, object], list[dict[str, object]]]:
    required = [paths.database, paths.harvest_features, paths.harvest_long]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required files: " + ", ".join(missing))

    db_headers, db_rows = read_csv_rows(paths.database)
    feature_headers, feature_rows = read_csv_rows(paths.harvest_features)
    long_headers, long_rows = read_csv_rows(paths.harvest_long)
    summary_codes, summary_feature_presence = load_summary_codes(paths.summary)

    db_by_code = {norm(row.get("hunt_code")): row for row in db_rows if norm(row.get("hunt_code"))}
    feature_by_code = {norm(row.get("hunt_code")): row for row in feature_rows if norm(row.get("hunt_code"))}

    historical_years_by_code: dict[str, set[str]] = defaultdict(set)
    historical_nonblank_metrics_by_code: dict[str, Counter] = defaultdict(Counter)
    for row in long_rows:
        code = norm(row.get("hunt_code"))
        if not code:
            continue
        historical_years_by_code[code].add(norm(row.get("reported_hunt_year")))
        for field in ["percent_success", "average_days", "average_age", "hunters_afield", "harvest_total"]:
            if norm(row.get(field)):
                historical_nonblank_metrics_by_code[code][field] += 1

    duplicate_db_codes = [code for code, count in Counter(norm(row.get("hunt_code")) for row in db_rows).items() if code and count > 1]
    duplicate_feature_codes = [code for code, count in Counter(norm(row.get("hunt_code")) for row in feature_rows).items() if code and count > 1]

    audit_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    grade_counts: Counter[str] = Counter()
    species_counts: Counter[str] = Counter()

    for code in sorted(db_by_code):
        db = db_by_code[code]
        feature = feature_by_code.get(code)
        historical_years = sorted(year for year in historical_years_by_code.get(code, set()) if year)
        metrics = historical_nonblank_metrics_by_code.get(code, Counter())
        feature_match = feature is not None
        in_summary = code in summary_codes
        quality_grade = norm(feature.get("harvest_feature_data_quality_grade")) if feature else ""
        match_method = norm(feature.get("harvest_feature_match_method")) if feature else ""
        source_years = norm(feature.get("harvest_feature_source_years")) if feature else ""
        reason_codes = norm(feature.get("harvest_feature_reason_codes")) if feature else ""
        species = norm(db.get("species")) or (norm(feature.get("species")) if feature else "UNKNOWN")
        species_counts[species or "UNKNOWN"] += 1

        if feature_match and quality_grade.upper() not in {"BLOCK", "BLOCKED", "REVIEW_BLOCKED"}:
            if in_summary:
                status = "READY_FOR_HUNT_RESEARCH_CONTEXT"
            else:
                status = "FEATURE_READY_SUMMARY_MISSING"
        elif feature_match:
            status = "HARVEST_FEATURE_REVIEW_REQUIRED"
        elif historical_years:
            status = "RAW_HISTORY_EXISTS_FEATURE_MISSING"
        else:
            status = "NO_HARVEST_HISTORY_FOUND"

        status_counts[status] += 1
        grade_counts[quality_grade or "NOT_APPLICABLE"] += 1

        display_values_present = [field for field in SAFE_DISPLAY_FIELDS if feature and norm(feature.get(field))]
        model_values_present = [field for field in SAFE_MODEL_FEATURE_FIELDS if feature and norm(feature.get(field))]

        audit_rows.append(
            {
                "hunt_code": code,
                "boundary_id": norm(db.get("boundary_id")),
                "hunt_name": norm(db.get("hunt_name")),
                "species": species,
                "sex_type": norm(db.get("sex_type")),
                "weapon": norm(db.get("weapon")),
                "hunt_type": norm(db.get("hunt_type")),
                "hunt_class": norm(db.get("hunt_class")),
                "in_hunt_research_summary": str(in_summary).upper(),
                "harvest_feature_match": str(feature_match).upper(),
                "harvest_feature_match_method": match_method or "NOT_APPLICABLE",
                "harvest_feature_data_quality_grade": quality_grade or "NOT_APPLICABLE",
                "harvest_feature_source_years": source_years or ",".join(historical_years) or "NOT_APPLICABLE",
                "historical_harvest_year_count": len(historical_years),
                "historical_metric_nonblank_counts": json.dumps(metrics, sort_keys=True),
                "safe_display_fields_present": ",".join(display_values_present) or "NONE",
                "safe_model_feature_fields_present": ",".join(model_values_present) or "NONE",
                "forbidden_fields_to_leave_unchanged": ",".join(FORBIDDEN_OUTPUT_FIELDS),
                "harvest_quality_index": norm(feature.get("harvest_quality_index")) if feature else "NOT_APPLICABLE",
                "demand_pressure_signal": norm(feature.get("demand_pressure_signal")) if feature else "NOT_APPLICABLE",
                "demand_pressure_category": norm(feature.get("demand_pressure_category")) if feature else "NOT_APPLICABLE",
                "point_creep_quality_adjustment": norm(feature.get("point_creep_quality_adjustment")) if feature else "NOT_APPLICABLE",
                "harvest_success_3yr_avg": norm(feature.get("harvest_success_3yr_avg")) if feature else "NOT_APPLICABLE",
                "average_age_3yr_avg": norm(feature.get("average_age_3yr_avg")) if feature else "NOT_APPLICABLE",
                "harvest_feature_reason_codes": reason_codes or "NOT_APPLICABLE",
                "promotion_status": status,
                "promotion_decision": (
                    "PROMOTE_CONTEXT_ONLY"
                    if status == "READY_FOR_HUNT_RESEARCH_CONTEXT"
                    else "DO_NOT_PROMOTE_WITHOUT_REVIEW"
                ),
                "promotion_notes": (
                    "Safe for Hunt Research quality/context display and demand-feature modeling; not allowed to mutate odds or quotas."
                    if status == "READY_FOR_HUNT_RESEARCH_CONTEXT"
                    else "Review coverage, feature generation, or source lineage before use."
                ),
            }
        )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_file": str(paths.database),
        "harvest_feature_file": str(paths.harvest_features),
        "harvest_truth_file": str(paths.harvest_long),
        "hunt_research_summary_file": str(paths.summary),
        "database_row_count": len(db_rows),
        "database_unique_hunt_codes": len(db_by_code),
        "harvest_feature_row_count": len(feature_rows),
        "harvest_feature_unique_hunt_codes": len(feature_by_code),
        "harvest_truth_row_count": len(long_rows),
        "harvest_truth_unique_hunt_codes": len(historical_years_by_code),
        "hunt_research_summary_unique_hunt_codes": len(summary_codes),
        "duplicate_database_hunt_codes": duplicate_db_codes,
        "duplicate_feature_hunt_codes": duplicate_feature_codes,
        "promotion_status_counts": dict(sorted(status_counts.items())),
        "harvest_feature_grade_counts": dict(sorted(grade_counts.items())),
        "database_species_counts": dict(sorted(species_counts.items())),
        "safe_display_fields": SAFE_DISPLAY_FIELDS,
        "safe_model_feature_fields": SAFE_MODEL_FEATURE_FIELDS,
        "forbidden_output_fields": FORBIDDEN_OUTPUT_FIELDS,
        "production_rule": "Harvest features are quality/context/demand inputs only; they must not overwrite p_draw, draw odds, 2026 permits, or 2026 quota/allotment fields.",
        "recommended_next_step": "Promote only PROMOTE_CONTEXT_ONLY fields into Hunt Research display/scoring after reviewing FEATURE_READY_SUMMARY_MISSING and RAW_HISTORY_EXISTS_FEATURE_MISSING rows.",
    }
    return summary, audit_rows


def write_markdown(path: Path, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status_counts = summary["promotion_status_counts"]
    grade_counts = summary["harvest_feature_grade_counts"]
    lines = [
        "# Hunt Research Harvest Feature Promotion Audit",
        "",
        "This is a read-only audit. It does not mutate `DATABASE.csv`, draw truth, engine code, probability fields, quota fields, or runtime manifests.",
        "",
        "## Verdict",
        "",
        "Harvest results are already ingested. The correct next step is not raw harvest ingestion; it is controlled promotion of reviewed harvest quality/context features into Hunt Research.",
        "",
        "## Counts",
        "",
        f"- Current DATABASE hunt codes: `{summary['database_unique_hunt_codes']}`",
        f"- Harvest feature rows: `{summary['harvest_feature_row_count']}`",
        f"- Harvest feature unique hunt codes: `{summary['harvest_feature_unique_hunt_codes']}`",
        f"- Harvest truth rows: `{summary['harvest_truth_row_count']}`",
        f"- Harvest truth unique hunt codes: `{summary['harvest_truth_unique_hunt_codes']}`",
        f"- Hunt Research summary unique hunt codes: `{summary['hunt_research_summary_unique_hunt_codes']}`",
        "",
        "## Promotion Status",
        "",
    ]
    for key, value in status_counts.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Harvest Feature Grades", ""])
    for key, value in grade_counts.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Safe Hunt Research Uses",
            "",
            "- Quality cards: harvest success, harvest trend, hunter effort, average age, harvest-quality index.",
            "- Demand context: pressure signal, effort signal, harvest trend, point-creep quality adjustment.",
            "- Sleeper hunt logic: high quality / lower demand / tolerable odds, with draw odds still produced by draw engine.",
            "- Point-creep explanation: demand pressure and quality adjustment can explain why a hunt is heating up or cooling off.",
            "",
            "## Forbidden Uses",
            "",
            "- Do not use harvest data to overwrite `p_draw`, `p_draw_pct`, `display_odds_pct`, max-pool odds, random-pool odds, 2026 permits, or 2026 allotments.",
            "- Do not infer current quotas from historical harvest reports.",
            "- Do not treat missing harvest history as zero quality.",
            "",
            "## Engine Architecture Placement",
            "",
            "1. `DATABASE.csv` defines the current hunt universe, boundary IDs, current permit/allotment truth, and current hunt metadata.",
            "2. Draw truth and point ladder files define observed historical draw behavior and ladder rows.",
            "3. Harvest truth defines quality, effort, demand, and age context.",
            "4. The prediction engine should forecast applicant pressure and quota environment, then route rows into deterministic Utah draw mechanics.",
            "5. Hunt Research should display draw-ladder math separately from harvest-quality context so users know what is odds math and what is hunt-quality evidence.",
            "",
            "## Recommended Next Step",
            "",
            str(summary["recommended_next_step"]),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--harvest-features", default=DEFAULT_HARVEST_FEATURES)
    parser.add_argument("--harvest-long", default=DEFAULT_HARVEST_LONG)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--out-dir", default="audits/hunt_research_engine")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    paths = AuditPaths(
        root=root,
        database=(root / args.database).resolve(),
        harvest_features=(root / args.harvest_features).resolve(),
        harvest_long=(root / args.harvest_long).resolve(),
        summary=(root / args.summary).resolve(),
        out_dir=(root / args.out_dir).resolve(),
    )
    summary, rows = build_audit(paths)

    csv_path = paths.out_dir / "harvest_feature_promotion_audit.csv"
    json_path = paths.out_dir / "harvest_feature_promotion_audit.json"
    md_path = paths.out_dir / "harvest_feature_promotion_audit.md"
    fieldnames = [
        "hunt_code",
        "boundary_id",
        "hunt_name",
        "species",
        "sex_type",
        "weapon",
        "hunt_type",
        "hunt_class",
        "in_hunt_research_summary",
        "harvest_feature_match",
        "harvest_feature_match_method",
        "harvest_feature_data_quality_grade",
        "harvest_feature_source_years",
        "historical_harvest_year_count",
        "historical_metric_nonblank_counts",
        "safe_display_fields_present",
        "safe_model_feature_fields_present",
        "forbidden_fields_to_leave_unchanged",
        "harvest_quality_index",
        "demand_pressure_signal",
        "demand_pressure_category",
        "point_creep_quality_adjustment",
        "harvest_success_3yr_avg",
        "average_age_3yr_avg",
        "harvest_feature_reason_codes",
        "promotion_status",
        "promotion_decision",
        "promotion_notes",
    ]
    write_csv(csv_path, fieldnames, rows)
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_path, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
