#!/usr/bin/env python3
"""Targeted source-backed blank-cell backfill for prediction feeder files.

This intentionally avoids modeled probability fields and historical draw-result
truth fields. It only fills blank derived/runtime feeder cells from exact
DATABASE.csv hunt_code matches.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = REPO_ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
AUDIT_INPUT = REPO_ROOT / "processed_data/audits/prediction_engine_feeder_blank_cell_audit.csv"
SUMMARY_PATH = REPO_ROOT / "processed_data/audits/prediction_engine_targeted_backfill_summary.csv"

TARGET_FILES = [
    REPO_ROOT / "processed_data/hunt_master_enriched.csv",
    REPO_ROOT / "processed_data/hunt_unit_reference_linked.csv",
    REPO_ROOT / "processed_data/ml_draw_predictions_v1.csv",
    REPO_ROOT / "processed_data/draw_reality_engine_predictive_v2.csv",
    REPO_ROOT / "processed_data/draw_reality_engine.csv",
    REPO_ROOT / "processed_data/point_ladder_view.csv",
]

EXCLUDED_REVIEW_FILES = {
    "pipeline\\RAW\\hunt_unit_database\\2026\\csv\\DATABASE.csv": "TRUTH_SOURCE_NOT_MODIFIED",
    "data_truth\\draw_results_truth\\normalized\\draw_results_long.csv": "DRAW_TRUTH_NOT_MODIFIED",
    "data_model\\runtime_drafts\\draw_reality_engine_v2.csv": "HISTORICAL_RUNTIME_DRAFT_NOT_MODIFIED_FROM_CURRENT_DB",
    "processed_data\\draw_system_coverage_report.csv": "GENERATED_COVERAGE_REPORT_NOT_MODIFIED",
}

DIRECT_DB_FIELDS = {
    "hunt_name": "hunt_name",
    "species": "species",
    "sex_type": "sex_type",
    "weapon": "weapon",
    "hunt_type": "hunt_type",
    "hunt_class": "hunt_class",
    "draw_2026_system_type": "draw_2026_system_type",
    "boundary_id": "boundary_id",
    "permit_allotment_2026_res": "permit_allotment_2026_res",
    "permit_allotment_2026_nr": "permit_allotment_2026_nr",
    "permit_allotment_2026_total": "permit_allotment_2026_total",
    "permit_allotment_2026_source": "permit_allotment_2026_source",
    "permit_allotment_2026_source_file": "permit_allotment_2026_source_file",
    "permit_allotment_2026_status": "permit_allotment_2026_status",
}

DERIVED_FIELDS = {
    "draw_system_type": ("draw_2026_system_type", "same semantic draw-routing family"),
    "permits_2026_res": ("permit_allotment_2026_res", "2026 DWR allotment used as current public permit value"),
    "permits_2026_nr": ("permit_allotment_2026_nr", "2026 DWR allotment used as current public permit value"),
    "permits_2026_total": ("permit_allotment_2026_total", "2026 DWR allotment used as current public permit value"),
    "public_permits_2026": ("permit_allotment_2026_total", "2026 total public permits from DWR allotment"),
    "quota_2026_total": ("permit_allotment_2026_total", "2026 total quota from DWR allotment"),
    "quota_source_status": ("permit_allotment_2026_status", "quota source status copied from DWR allotment status"),
    "quota_source_year": ("__constant_2026__", "quota year set only when 2026 quota exists"),
    "quota_source_file": ("__quota_source_file__", "quota source file copied from DWR allotment source file"),
    "truth_source_file": ("__quota_source_file__", "truth source file copied from DWR allotment source file"),
    "truth_source_status": ("permit_allotment_2026_status", "truth source status copied from DWR allotment status"),
}

DEFERRED_FIELD_PATTERNS = (
    "p_draw",
    "p_max_pool",
    "p_random",
    "p_prior",
    "p_quota",
    "p_rollover",
    "p_harvest",
    "display_odds",
    "random_draw_odds",
    "applicants",
    "prior_year",
    "success_ratio",
    "dwr_result_display",
    "display_2025",
    "display_2026",
    "quota_2026_max_pool",
    "quota_2026_random_pool",
    "projected_2026",
    "is_2026_",
    "data_quality",
    "reason_codes",
    "probability_model",
    "draw_model_class",
    "availability_status",
    "algorithm_status",
    "public_permits_2025",
    "total_permits",
)


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("/", "\\")


def is_blank(value: object) -> bool:
    return value is None or str(value).strip() == ""


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def load_database() -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with DATABASE_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            code = clean(row.get("hunt_code")).upper()
            if code and code not in rows:
                rows[code] = {k: clean(v) for k, v in row.items()}
    return rows


def load_review_targets() -> dict[str, set[str]]:
    targets: dict[str, set[str]] = defaultdict(set)
    with AUDIT_INPUT.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get("recommended_action") != "REVIEW_TARGETED_BACKFILL":
                continue
            targets[row["file_path"]].add(row["field_name"])
    return targets


def source_value(db_row: dict[str, str], field: str) -> tuple[str, str, str]:
    if field in DIRECT_DB_FIELDS:
        source_field = DIRECT_DB_FIELDS[field]
        return db_row.get(source_field, ""), source_field, "DIRECT_DATABASE_HUNT_CODE_BACKFILL"
    if field not in DERIVED_FIELDS:
        return "", "", "NO_SAFE_BACKFILL_RULE"

    source_field, note = DERIVED_FIELDS[field]
    if source_field == "__constant_2026__":
        if db_row.get("permit_allotment_2026_total"):
            return "2026", "permit_allotment_2026_total", note
        return "", "permit_allotment_2026_total", "NO_2026_QUOTA_TO_ANCHOR_YEAR"
    if source_field == "__quota_source_file__":
        value = db_row.get("permit_allotment_2026_source_file") or db_row.get("permit_allotment_2026_source")
        if not value and db_row.get("permit_allotment_2026_total"):
            value = rel(DATABASE_PATH)
        return value, "permit_allotment_2026_source_file", note
    return db_row.get(source_field, ""), source_field, note


def deferred_reason(field: str) -> str:
    for pattern in DEFERRED_FIELD_PATTERNS:
        if field.startswith(pattern) or pattern in field:
            return "DEFERRED_REQUIRES_MODEL_OR_DRAW_TRUTH_LOGIC"
    return "NO_SAFE_BACKFILL_RULE"


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def process_file(
    path: Path,
    fields: set[str],
    database: dict[str, dict[str, str]],
    apply: bool,
) -> Counter[tuple[str, str, str]]:
    counter: Counter[tuple[str, str, str]] = Counter()
    if not path.exists():
        counter[(rel(path), "", "SKIPPED_FILE_MISSING")] += 1
        return counter

    tmp_path = None
    audit_rows: list[dict[str, str]] = []
    changed = False
    with path.open(newline="", encoding="utf-8-sig") as src:
        reader = csv.DictReader(src)
        if not reader.fieldnames:
            return []
        writable_fields = fields.intersection(reader.fieldnames)
        tmp_handle = None
        writer = None
        if apply:
            fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
            os.close(fd)
            tmp_path = Path(tmp_name)
            tmp_handle = tmp_path.open("w", newline="", encoding="utf-8")
            writer = csv.DictWriter(tmp_handle, fieldnames=reader.fieldnames, lineterminator="\n")
            writer.writeheader()

        try:
            for row_number, row in enumerate(reader, start=2):
                code = clean(row.get("hunt_code")).upper()
                db_row = database.get(code)
                for field in sorted(writable_fields):
                    if not is_blank(row.get(field)):
                        continue
                    if not db_row:
                        continue
                    new_value, source_field, rule = source_value(db_row, field)
                    if not new_value:
                        continue
                    row[field] = new_value
                    changed = True
                    counter[(rel(path), field, "APPLIED" if apply else "PREVIEW")] += 1
                if writer:
                    writer.writerow(row)
        finally:
            if tmp_handle:
                tmp_handle.close()

    if apply and tmp_path:
        if changed:
            shutil.move(str(tmp_path), str(path))
        else:
            tmp_path.unlink(missing_ok=True)
    return counter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write repairs to feeder files")
    args = parser.parse_args()

    database = load_database()
    review_targets = load_review_targets()

    summary_counter: Counter[tuple[str, str, str]] = Counter()

    for excluded_path, reason in sorted(EXCLUDED_REVIEW_FILES.items()):
        for field in sorted(review_targets.get(excluded_path, ())):
            summary_counter[(excluded_path, field, reason)] += 1

    for path in TARGET_FILES:
        path_key = rel(path)
        fields = review_targets.get(path_key, set())
        if not fields:
            continue
        safe_fields = {
            field for field in fields
            if field in DIRECT_DB_FIELDS or field in DERIVED_FIELDS
        }
        for field in sorted(fields - safe_fields):
            summary_counter[(path_key, field, deferred_reason(field))] += 1
        file_counter = process_file(path, safe_fields, database, args.apply)
        summary_counter.update(file_counter)

    summary_rows = [
        {
            "file_path": file_path,
            "field_name": field,
            "status": status,
            "count": count,
        }
        for (file_path, field, status), count in sorted(summary_counter.items())
    ]
    write_rows(SUMMARY_PATH, ["file_path", "field_name", "status", "count"], summary_rows)

    mode = "APPLY" if args.apply else "PREVIEW"
    print(f"{mode} complete summary rows written: {len(summary_rows)}")
    print(f"Summary: {rel(SUMMARY_PATH)}")
    print(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
