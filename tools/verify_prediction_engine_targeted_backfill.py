#!/usr/bin/env python3
"""Acceptance verifier for the targeted prediction feeder backfill repair."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


REPAIRED_FILES = [
    "processed_data/point_ladder_view.csv",
    "processed_data/draw_reality_engine_predictive_v2.csv",
    "processed_data/ml_draw_predictions_v1.csv",
    "processed_data/hunt_master_enriched.csv",
    "processed_data/draw_reality_engine.csv",
    "processed_data/hunt_unit_reference_linked.csv",
]

PRIMARY_KEYS = {
    "processed_data/point_ladder_view.csv": ("hunt_code", "residency", "points"),
    "processed_data/draw_reality_engine_predictive_v2.csv": ("hunt_code", "residency", "points"),
    "processed_data/ml_draw_predictions_v1.csv": ("hunt_code", "residency", "points"),
    "processed_data/hunt_master_enriched.csv": ("hunt_code", "residency", "points"),
    "processed_data/draw_reality_engine.csv": ("hunt_code", "year", "residency", "points"),
    "processed_data/hunt_unit_reference_linked.csv": ("hunt_code", "residency"),
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
    "draw_system_type": "draw_2026_system_type",
    "permits_2026_res": "permit_allotment_2026_res",
    "permits_2026_nr": "permit_allotment_2026_nr",
    "permits_2026_total": "permit_allotment_2026_total",
    "public_permits_2026": "permit_allotment_2026_total",
    "quota_2026_total": "permit_allotment_2026_total",
    "quota_source_status": "permit_allotment_2026_status",
    "quota_source_year": "__constant_2026__",
    "quota_source_file": "__quota_source_file__",
    "truth_source_file": "__quota_source_file__",
    "truth_source_status": "permit_allotment_2026_status",
}

APPROVED_FIELDS = set(DIRECT_DB_FIELDS) | set(DERIVED_FIELDS)
FORBIDDEN_PATTERNS = (
    "p_draw",
    "p_max_pool",
    "p_random",
    "random_draw_odds",
    "display_odds",
    "applicants",
    "prior_year",
    "success_ratio",
    "projected_2026",
    "probability_model",
    "draw_model_class",
    "availability_status",
    "algorithm_status",
)
DEFERRED_PATTERNS = FORBIDDEN_PATTERNS + (
    "p_prior",
    "p_quota",
    "p_rollover",
    "p_harvest",
    "dwr_result_display",
    "display_2025",
    "display_2026",
    "quota_2026_max_pool",
    "quota_2026_random_pool",
    "is_2026_",
    "data_quality",
    "reason_codes",
    "public_permits_2025",
    "total_permits",
)
PROBABILITY_COLUMNS = (
    "p_draw",
    "p_draw_mean",
    "p_draw_p10",
    "p_draw_p50",
    "p_draw_p90",
    "p_max_pool_mean",
    "p_random_mean",
    "p_sportsman_draw",
    "p_bonus_pool",
    "p_random_pool",
    "p_preference_draw",
)
QUOTA_TRIPLES = (
    ("permit_allotment_2026_res", "permit_allotment_2026_nr", "permit_allotment_2026_total"),
    ("permits_2026_res", "permits_2026_nr", "permits_2026_total"),
)
MANIFESTS = ("public/data/runtime-manifest.json", "data/runtime-manifest.json")
R2_BASE = "https://json.uoga.workers.dev"
BACKFILL_COMMIT = "0f011540"


def norm_path(path: str) -> str:
    return path.replace("\\", "/")


def win_path(path: str) -> str:
    return path.replace("/", "\\")


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalized(value: object) -> str:
    return clean(value).replace("\r\n", "\n")


def is_blank(value: object) -> bool:
    return clean(value) == ""


def is_forbidden(field: str) -> bool:
    return any(field.startswith(pattern) or pattern in field for pattern in FORBIDDEN_PATTERNS)


def classify_remaining_blank(field: str, source_present: bool, allowed: bool) -> str:
    if any(field.startswith(pattern) or pattern in field for pattern in ("p_draw", "p_max_pool", "p_random", "random_draw_odds", "display_odds", "projected_2026", "probability_model", "draw_model_class", "availability_status", "algorithm_status")):
        return "deferred_model_logic"
    if any(field.startswith(pattern) or pattern in field for pattern in ("applicants", "prior_year", "success_ratio", "display_2025", "dwr_result_display")):
        return "deferred_draw_truth_logic"
    if allowed and not source_present:
        return "blocker_missing_source"
    if not allowed:
        return "blocker_unmapped_field"
    return "acceptable_optional_blank"


def parse_number(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return float("nan")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [{k: clean(v) for k, v in row.items()} for row in reader]


def read_csv_text(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(text.splitlines())
    return list(reader.fieldnames or []), [{k: clean(v) for k, v in row.items()} for row in reader]


def git_file_text(ref: str, path: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None


def git_tracked(path: str) -> bool:
    result = subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=REPO_ROOT, capture_output=True, text=True)
    return result.returncode == 0


def load_database(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]], list[str]]:
    header, rows = read_csv_rows(path)
    by_code: dict[str, dict[str, str]] = {}
    duplicates: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        duplicates[code].append(row)
        if code not in by_code:
            by_code[code] = row
    return by_code, duplicates, header


def source_value(db_row: dict[str, str] | None, field: str) -> tuple[str, str]:
    if not db_row:
        return "", ""
    if field in DIRECT_DB_FIELDS:
        source_field = DIRECT_DB_FIELDS[field]
        return clean(db_row.get(source_field)), source_field
    if field not in DERIVED_FIELDS:
        return "", ""
    source_field = DERIVED_FIELDS[field]
    if source_field == "__constant_2026__":
        return ("2026", "permit_allotment_2026_total") if clean(db_row.get("permit_allotment_2026_total")) else ("", "permit_allotment_2026_total")
    if source_field == "__quota_source_file__":
        value = clean(db_row.get("permit_allotment_2026_source_file")) or clean(db_row.get("permit_allotment_2026_source"))
        if not value and clean(db_row.get("permit_allotment_2026_total")):
            value = "pipeline\\RAW\\hunt_unit_database\\2026\\csv\\DATABASE.csv"
        return value, "permit_allotment_2026_source_file"
    return clean(db_row.get(source_field)), source_field


def load_summary(path: Path) -> tuple[list[dict[str, str]], dict[tuple[str, str], int], list[dict[str, str]]]:
    rows = []
    applied: dict[tuple[str, str], int] = {}
    forbidden = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            row = {k: clean(v) for k, v in row.items()}
            rows.append(row)
            file_path = norm_path(row.get("file_path", ""))
            field = row.get("field_name", "")
            count = int(row.get("count") or 0)
            if row.get("status") == "APPLIED":
                applied[(file_path, field)] = applied.get((file_path, field), 0) + count
                if field not in APPROVED_FIELDS or is_forbidden(field):
                    forbidden.append(row)
    return rows, applied, forbidden


def duplicate_count(rows: list[dict[str, str]], key_fields: Iterable[str]) -> int:
    fields = tuple(key_fields)
    if not fields or not all(fields[0] in row for row in rows[:1]):
        return 0
    counter: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        key = tuple(clean(row.get(field)) for field in fields)
        if all(key):
            counter[key] += 1
    return sum(count - 1 for count in counter.values() if count > 1)


def probability_check(rows: list[dict[str, str]], header: list[str]) -> dict[str, object]:
    checked = [col for col in PROBABILITY_COLUMNS if col in header]
    invalid: Counter[str] = Counter()
    for row in rows:
        for col in checked:
            value = parse_number(row.get(col))
            if value is not None and (value != value or value < 0 or value > 1):
                invalid[col] += 1
    return {"checked_columns": checked, "invalid_counts": dict(invalid), "pass": not invalid}


def quota_arithmetic_check(rows: list[dict[str, str]], header: list[str]) -> dict[str, object]:
    failures: Counter[str] = Counter()
    checked: Counter[str] = Counter()
    for res_col, nr_col, total_col in QUOTA_TRIPLES:
        if not all(col in header for col in (res_col, nr_col, total_col)):
            continue
        label = f"{res_col}+{nr_col}={total_col}"
        for row in rows:
            res = parse_number(row.get(res_col))
            nr = parse_number(row.get(nr_col))
            total = parse_number(row.get(total_col))
            if res is None or nr is None or total is None:
                continue
            checked[label] += 1
            if any(v != v for v in (res, nr, total)) or int(res) + int(nr) != int(total):
                failures[label] += 1
    return {"checked_counts": dict(checked), "failure_counts": dict(failures), "pass": not failures}


def verify_r2(root: Path, file_path: str) -> dict[str, object]:
    local = root / file_path
    url = f"{R2_BASE}/{file_path}"
    row: dict[str, object] = {"file_path": file_path, "url": url, "local_exists": local.exists()}
    if not local.exists():
        row.update({"status": "FAIL_LOCAL_MISSING"})
        return row
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp_path = Path(tmp.name)
    try:
        urllib.request.urlretrieve(url, tmp_path)
        local_header, local_rows = read_csv_rows(local)
        remote_header, remote_rows = read_csv_rows(tmp_path)
        row.update({
            "local_size": local.stat().st_size,
            "remote_size": tmp_path.stat().st_size,
            "local_sha256": sha256_file(local),
            "remote_sha256": sha256_file(tmp_path),
            "local_row_count": len(local_rows),
            "remote_row_count": len(remote_rows),
            "header_equal": local_header == remote_header,
        })
        row["status"] = "PASS" if all((
            row["local_size"] == row["remote_size"],
            row["local_sha256"] == row["remote_sha256"],
            row["local_row_count"] == row["remote_row_count"],
            row["header_equal"],
        )) else "FAIL_MISMATCH"
    except Exception as exc:  # noqa: BLE001
        row.update({"status": "FAIL_DOWNLOAD_OR_PARSE", "error": f"{type(exc).__name__}: {exc}"})
    finally:
        tmp_path.unlink(missing_ok=True)
    return row


def verify_manifests(root: Path, r2_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    results = []
    r2_by_file = {row["file_path"]: row for row in r2_rows}
    for manifest in MANIFESTS:
        path = root / manifest
        result: dict[str, object] = {"manifest": manifest, "exists": path.exists()}
        if not path.exists():
            result["status"] = "FAIL_MISSING"
            results.append(result)
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            assets = {asset.get("path"): asset for asset in data.get("assets", [])}
            file_results = {}
            ok = True
            for file_path, r2 in r2_by_file.items():
                asset = assets.get(file_path)
                if not asset:
                    file_results[file_path] = "missing_asset"
                    ok = False
                    continue
                expected_url = f"{R2_BASE}/{file_path}"
                size_ok = int(asset.get("size_bytes") or -1) == int(r2.get("local_size") or -2)
                url_ok = clean(asset.get("canonical_url")) == expected_url
                mode_ok = clean(asset.get("update_mode")) == "AUTO_PUBLIC_R2"
                file_results[file_path] = {
                    "size_ok": size_ok,
                    "url_ok": url_ok,
                    "update_mode_ok": mode_ok,
                    "manifest_size": asset.get("size_bytes"),
                    "local_size": r2.get("local_size"),
                }
                ok = ok and size_ok and url_ok and mode_ok
            result.update({"status": "PASS" if ok else "FAIL", "files": file_results})
        except Exception as exc:  # noqa: BLE001
            result.update({"status": "FAIL_PARSE", "error": f"{type(exc).__name__}: {exc}"})
        results.append(result)
    return results


def compare_tracked_before_after(
    root: Path,
    before_ref: str,
    file_path: str,
    header: list[str],
    rows: list[dict[str, str]],
    db_by_code: dict[str, dict[str, str]],
) -> dict[str, object]:
    result: dict[str, object] = {
        "before_available": False,
        "tracked": git_tracked(file_path),
        "changed_cell_count": None,
        "changed_columns": {},
        "violations": [],
    }
    if not result["tracked"]:
        result["blocker"] = "before_snapshot_unavailable_untracked_ignored_runtime_file"
        return result
    before_text = git_file_text(before_ref, file_path)
    if before_text is None:
        result["blocker"] = "before_snapshot_unavailable_git_show_failed"
        return result
    before_header, before_rows = read_csv_text(before_text)
    result["before_available"] = True
    if before_header != header:
        result["violations"].append({"type": "header_changed", "before": before_header, "after": header})
    if len(before_rows) != len(rows):
        result["violations"].append({"type": "row_count_changed", "before": len(before_rows), "after": len(rows)})
    changed_columns: Counter[str] = Counter()
    changed_count = 0
    max_rows = min(len(before_rows), len(rows))
    for index in range(max_rows):
        before = before_rows[index]
        after = rows[index]
        code = clean(after.get("hunt_code")).upper()
        for field in header:
            if normalized(before.get(field)) == normalized(after.get(field)):
                continue
            changed_count += 1
            changed_columns[field] += 1
            source, source_field = source_value(db_by_code.get(code), field)
            if is_forbidden(field):
                result["violations"].append({"type": "forbidden_column_changed", "row": index + 2, "hunt_code": code, "field": field})
            if field not in APPROVED_FIELDS:
                result["violations"].append({"type": "unapproved_column_changed", "row": index + 2, "hunt_code": code, "field": field})
            if not is_blank(before.get(field)):
                result["violations"].append({"type": "target_before_not_blank", "row": index + 2, "hunt_code": code, "field": field, "before": before.get(field), "after": after.get(field)})
            if not code or code not in db_by_code:
                result["violations"].append({"type": "source_hunt_code_missing", "row": index + 2, "hunt_code": code, "field": field})
            elif not source:
                result["violations"].append({"type": "source_value_blank", "row": index + 2, "hunt_code": code, "field": field, "source_field": source_field})
            elif normalized(after.get(field)) != normalized(source):
                result["violations"].append({"type": "target_not_equal_source", "row": index + 2, "hunt_code": code, "field": field, "target": after.get(field), "source": source, "source_field": source_field})
    result["changed_cell_count"] = changed_count
    result["changed_columns"] = dict(sorted(changed_columns.items()))
    return result


def analyze_file(
    root: Path,
    file_path: str,
    applied_counts: dict[tuple[str, str], int],
    db_by_code: dict[str, dict[str, str]],
    before_ref: str,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    path = root / file_path
    header, rows = read_csv_rows(path)
    changed_fields = sorted(field for (fp, field), count in applied_counts.items() if fp == file_path and count > 0)
    before = compare_tracked_before_after(root, before_ref, file_path, header, rows, db_by_code)

    row_count = len(rows)
    duplicate_keys = duplicate_count(rows, PRIMARY_KEYS.get(file_path, ()))
    probability = probability_check(rows, header)
    quota = quota_arithmetic_check(rows, header)
    column_rows: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    forbidden_summary_rows: list[dict[str, object]] = []

    forbidden_observed_changes = {
        field: count for field, count in dict(before.get("changed_columns") or {}).items() if is_forbidden(field)
    }
    for pattern in FORBIDDEN_PATTERNS:
        applied = sum(count for (fp, field), count in applied_counts.items() if fp == file_path and (field.startswith(pattern) or pattern in field))
        observed = sum(count for field, count in forbidden_observed_changes.items() if field.startswith(pattern) or pattern in field)
        status = "PASS" if applied == 0 and observed == 0 and before.get("before_available") else "PASS_SUMMARY_ONLY_BEFORE_UNAVAILABLE" if applied == 0 and not before.get("before_available") else "FAIL"
        forbidden_summary_rows.append({
            "file_path": file_path,
            "pattern": pattern,
            "applied_summary_count": applied,
            "observed_tracked_changed_count": observed,
            "before_available": before.get("before_available"),
            "status": status,
        })

    deferred_columns = [col for col in header if any(col.startswith(pattern) or pattern in col for pattern in DEFERRED_PATTERNS)]
    null_deferred = {
        col: sum(1 for row in rows if is_blank(row.get(col)))
        for col in deferred_columns
        if sum(1 for row in rows if is_blank(row.get(col)))
    }

    for field in changed_fields:
        applied = applied_counts[(file_path, field)]
        null_remaining = sum(1 for row in rows if is_blank(row.get(field)))
        source_nonblank = 0
        expected_match = 0
        missing_hunt_code = 0
        source_blank = 0
        blank_class_counts: Counter[str] = Counter()
        for row_number, row in enumerate(rows, start=2):
            code = clean(row.get("hunt_code")).upper()
            db_row = db_by_code.get(code)
            source, source_field = source_value(db_row, field)
            if not code:
                missing_hunt_code += 1
            if source:
                source_nonblank += 1
            else:
                source_blank += 1
            if source and normalized(row.get(field)) == normalized(source):
                expected_match += 1
                if len(samples) < 25:
                    samples.append({
                        "file_path": file_path,
                        "row_number": row_number,
                        "hunt_code": code,
                        "field_name": field,
                        "target_value": row.get(field, ""),
                        "source_field": source_field,
                        "source_value": source,
                        "source_file": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
                    })
            if is_blank(row.get(field)):
                blank_class_counts[classify_remaining_blank(field, bool(source), field in APPROVED_FIELDS)] += 1
        status = "PASS" if field in APPROVED_FIELDS and not is_forbidden(field) and expected_match >= applied and missing_hunt_code == 0 else "FAIL"
        if not before.get("before_available"):
            status = "BLOCKED_BEFORE_UNAVAILABLE" if status == "PASS" else status
        column_rows.append({
            "file_path": file_path,
            "field_name": field,
            "applied_summary_count": applied,
            "before_available": before.get("before_available"),
            "observed_changed_cells": (before.get("changed_columns") or {}).get(field, ""),
            "current_nonblank_count": row_count - null_remaining,
            "current_expected_source_match_count": expected_match,
            "source_nonblank_count": source_nonblank,
            "source_blank_count": source_blank,
            "remaining_null_count": null_remaining,
            "remaining_blank_classification": json.dumps(dict(sorted(blank_class_counts.items())), sort_keys=True),
            "approved_field": field in APPROVED_FIELDS,
            "forbidden_field": is_forbidden(field),
            "status": status,
        })

    summary = {
        "file_path": file_path,
        "row_count": row_count,
        "column_count": len(header),
        "changed_cell_count": sum(applied_counts.get((file_path, field), 0) for field in changed_fields),
        "changed_columns": changed_fields,
        "duplicate_primary_key_count": duplicate_keys,
        "null_count_remaining_in_repaired_columns": {row["field_name"]: row["remaining_null_count"] for row in column_rows},
        "null_count_remaining_in_deferred_columns": null_deferred,
        "probability_column_range_check": probability,
        "quota_arithmetic_check": quota,
        "before_after": before,
        "sample_repaired_rows": samples,
    }
    return summary, column_rows, forbidden_summary_rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--database", default="pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv")
    parser.add_argument("--summary", default="processed_data/audits/prediction_engine_targeted_backfill_summary.csv")
    parser.add_argument("--before-ref", default=f"{BACKFILL_COMMIT}^")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.root).resolve()
    out_dir = root / "processed_data/audits"
    db_by_code, db_duplicates, db_header = load_database(root / args.database)
    summary_rows, applied_counts, forbidden_summary = load_summary(root / args.summary)

    db_duplicate_conflicts = []
    fill_source_cols = set(DIRECT_DB_FIELDS.values()) | {v for v in DERIVED_FIELDS.values() if not v.startswith("__")} | {"permit_allotment_2026_source_file", "permit_allotment_2026_source"}
    for code, rows in db_duplicates.items():
        if len(rows) <= 1:
            continue
        signatures = {tuple(clean(row.get(col)) for col in sorted(fill_source_cols)) for row in rows}
        if len(signatures) > 1:
            db_duplicate_conflicts.append(code)

    file_summaries = []
    column_diff_rows = []
    forbidden_rows = []
    sample_rows = []
    blockers = []
    for file_path in REPAIRED_FILES:
        summary, column_rows, forbidden_file_rows = analyze_file(root, file_path, applied_counts, db_by_code, args.before_ref)
        file_summaries.append(summary)
        column_diff_rows.extend(column_rows)
        forbidden_rows.extend(forbidden_file_rows)
        sample_rows.extend(summary["sample_repaired_rows"])
        if not summary["before_after"].get("before_available"):
            blockers.append(f"before_after_unavailable:{file_path}")
        if summary["before_after"].get("violations"):
            blockers.append(f"before_after_violations:{file_path}")
        if not summary["probability_column_range_check"]["pass"]:
            blockers.append(f"probability_range_failure:{file_path}")
        if not summary["quota_arithmetic_check"]["pass"]:
            blockers.append(f"quota_arithmetic_failure:{file_path}")

    if forbidden_summary:
        blockers.append("forbidden_field_in_repair_summary")
    if any(row["status"] == "FAIL" for row in forbidden_rows):
        blockers.append("forbidden_field_changed")
    if any(row["status"] == "FAIL" for row in column_diff_rows):
        blockers.append("column_diff_failure")
    if db_duplicate_conflicts:
        blockers.append("database_duplicate_source_conflicts")

    r2_rows = [verify_r2(root, file_path) for file_path in REPAIRED_FILES]
    if any(row["status"] != "PASS" for row in r2_rows):
        blockers.append("r2_local_mismatch")
    manifest_rows = verify_manifests(root, r2_rows)
    if any(row["status"] != "PASS" for row in manifest_rows):
        blockers.append("manifest_mismatch")

    status = "PASS"
    if blockers:
        status = "FAIL"
    else:
        deferred_remaining = any(summary["null_count_remaining_in_deferred_columns"] for summary in file_summaries)
        if deferred_remaining:
            status = "PASS_WITH_DEFERRED_MODEL_FIELDS"

    verification = {
        "status": status,
        "before_ref": args.before_ref,
        "database": args.database,
        "summary": args.summary,
        "approved_fields": sorted(APPROVED_FIELDS),
        "forbidden_patterns": list(FORBIDDEN_PATTERNS),
        "total_applied_summary_cells": sum(applied_counts.values()),
        "database_duplicate_hunt_code_count": sum(1 for rows in db_duplicates.values() if len(rows) > 1),
        "database_duplicate_source_conflicts": db_duplicate_conflicts,
        "blockers": blockers,
        "files": file_summaries,
        "r2_verification": r2_rows,
        "manifest_verification": manifest_rows,
        "sample_repaired_rows": sample_rows[:25],
    }

    verification_json = out_dir / "prediction_engine_targeted_backfill_verification.json"
    verification_csv = out_dir / "prediction_engine_targeted_backfill_verification.csv"
    verification_md = out_dir / "prediction_engine_targeted_backfill_verification.md"
    acceptance_json = out_dir / "prediction_engine_targeted_backfill_acceptance.json"
    acceptance_md = out_dir / "prediction_engine_targeted_backfill_acceptance.md"
    column_diff_csv = out_dir / "prediction_engine_targeted_backfill_column_diff.csv"
    forbidden_csv = out_dir / "prediction_engine_targeted_backfill_forbidden_field_check.csv"
    r2_csv = out_dir / "prediction_engine_targeted_backfill_r2_verification.csv"

    out_dir.mkdir(parents=True, exist_ok=True)
    verification_json.write_text(json.dumps(verification, indent=2), encoding="utf-8")
    acceptance_json.write_text(json.dumps(verification, indent=2), encoding="utf-8")

    write_csv(column_diff_csv, column_diff_rows, [
        "file_path", "field_name", "applied_summary_count", "before_available", "observed_changed_cells",
        "current_nonblank_count", "current_expected_source_match_count", "source_nonblank_count",
        "source_blank_count", "remaining_null_count", "remaining_blank_classification",
        "approved_field", "forbidden_field", "status",
    ])
    write_csv(forbidden_csv, forbidden_rows, [
        "file_path", "pattern", "applied_summary_count", "observed_tracked_changed_count", "before_available", "status",
    ])
    write_csv(r2_csv, r2_rows, [
        "file_path", "url", "local_exists", "status", "local_size", "remote_size", "local_sha256",
        "remote_sha256", "local_row_count", "remote_row_count", "header_equal", "error",
    ])
    write_csv(verification_csv, [
        {
            "file_path": item["file_path"],
            "row_count": item["row_count"],
            "column_count": item["column_count"],
            "changed_cell_count": item["changed_cell_count"],
            "changed_columns": ";".join(item["changed_columns"]),
            "duplicate_primary_key_count": item["duplicate_primary_key_count"],
            "probability_range_pass": item["probability_column_range_check"]["pass"],
            "quota_arithmetic_pass": item["quota_arithmetic_check"]["pass"],
            "before_available": item["before_after"]["before_available"],
            "before_violations": len(item["before_after"].get("violations") or []),
        }
        for item in file_summaries
    ], [
        "file_path", "row_count", "column_count", "changed_cell_count", "changed_columns",
        "duplicate_primary_key_count", "probability_range_pass", "quota_arithmetic_pass",
        "before_available", "before_violations",
    ])

    lines = [
        "# Prediction Engine Targeted Backfill Acceptance",
        "",
        f"Status: `{status}`",
        f"Total applied cells from repair summary: {verification['total_applied_summary_cells']}",
        f"Before reference: `{args.before_ref}`",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        for blocker in blockers:
            lines.append(f"- `{blocker}`")
    else:
        lines.append("- None")
    lines.extend(["", "## File Summary", ""])
    lines.append("| File | Rows | Columns | Applied Cells | Changed Columns | Duplicate Keys | Probability Range | Quota Arithmetic | Before Available |")
    lines.append("| --- | ---: | ---: | ---: | --- | ---: | --- | --- | --- |")
    for item in file_summaries:
        lines.append(
            f"| `{item['file_path']}` | {item['row_count']} | {item['column_count']} | "
            f"{item['changed_cell_count']} | {', '.join(item['changed_columns'])} | "
            f"{item['duplicate_primary_key_count']} | {item['probability_column_range_check']['pass']} | "
            f"{item['quota_arithmetic_check']['pass']} | {item['before_after']['before_available']} |"
        )
    lines.extend(["", "## R2 Verification", ""])
    for row in r2_rows:
        lines.append(f"- `{row['file_path']}`: `{row['status']}` size `{row.get('local_size')}` / `{row.get('remote_size')}`")
    lines.extend(["", "## Manifest Verification", ""])
    for row in manifest_rows:
        lines.append(f"- `{row['manifest']}`: `{row['status']}`")
    lines.extend(["", "## Sample Repaired Rows", ""])
    if sample_rows:
        lines.append("| File | Row | Hunt Code | Field | Target | Source Field | Source Value |")
        lines.append("| --- | ---: | --- | --- | --- | --- | --- |")
        for row in sample_rows[:25]:
            lines.append(f"| `{row['file_path']}` | {row['row_number']} | `{row['hunt_code']}` | `{row['field_name']}` | `{row['target_value']}` | `{row['source_field']}` | `{row['source_value']}` |")
    else:
        lines.append("- No source-matching sample rows found.")
    acceptance_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    verification_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"status={status} blockers={len(blockers)} applied_cells={verification['total_applied_summary_cells']}")
    for blocker in blockers:
        print(f"blocker: {blocker}")
    return 0 if status in {"PASS", "PASS_WITH_DEFERRED_MODEL_FIELDS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
