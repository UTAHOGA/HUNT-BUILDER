#!/usr/bin/env python3
"""Acceptance verifier for the targeted prediction-feeder backfill.

This tool is intentionally read-only for feeder/data files. It proves as much
of the previous repair as possible from git history, the repair summary,
DATABASE.csv, manifests, and the published R2 copies.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPAIRED_FILES = [
    "processed_data/point_ladder_view.csv",
    "processed_data/draw_reality_engine_predictive_v2.csv",
    "processed_data/ml_draw_predictions_v1.csv",
    "processed_data/hunt_master_enriched.csv",
    "processed_data/draw_reality_engine.csv",
    "processed_data/hunt_unit_reference_linked.csv",
]

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

FORBIDDEN_PATTERNS = [
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
]

DEFERRED_MODEL_PATTERNS = [
    "p_draw",
    "p_max_pool",
    "p_random",
    "random_draw_odds",
    "display_odds",
    "projected_2026",
    "probability_model",
    "draw_model_class",
    "availability_status",
    "algorithm_status",
]

DEFERRED_DRAW_TRUTH_PATTERNS = [
    "applicants",
    "prior_year",
    "success_ratio",
    "public_permits_2025",
    "total_permits",
]

PRIMARY_KEYS = {
    "processed_data/point_ladder_view.csv": ["hunt_code", "residency", "points"],
    "processed_data/draw_reality_engine_predictive_v2.csv": ["hunt_code", "residency", "points"],
    "processed_data/ml_draw_predictions_v1.csv": ["hunt_code", "residency", "points"],
    "processed_data/hunt_master_enriched.csv": ["hunt_code", "residency", "points"],
    "processed_data/draw_reality_engine.csv": ["hunt_code", "year", "residency", "points"],
    "processed_data/hunt_unit_reference_linked.csv": ["hunt_code", "residency"],
}

PROBABILITY_COLUMNS = [
    "p_draw",
    "p_draw_mean",
    "p_draw_p10",
    "p_draw_p50",
    "p_draw_p90",
    "p_max_pool_mean",
    "p_random_mean",
    "p_bonus_pool",
    "p_random_pool",
    "p_preference_draw",
    "p_prior_year_baseline",
    "p_quota_adjusted",
    "p_rollover_adjusted",
    "p_harvest_adjusted",
]

PERCENT_COLUMNS = [
    "p_draw_pct",
    "display_odds_pct",
]


@dataclass
class CsvData:
    path: str
    header: list[str]
    rows: list[dict[str, str]]
    size_bytes: int
    sha256: str


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def norm(value: object) -> str:
    text = clean(value)
    if text.endswith(".0"):
        try:
            return str(int(float(text)))
        except ValueError:
            return text
    return text


def is_blank(value: object) -> bool:
    return clean(value) == ""


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_text(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(args, cwd=str(cwd), text=True, capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def load_csv_file(path: Path, logical_path: str | None = None) -> CsvData:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = [{k: clean(v) for k, v in row.items()} for row in reader]
    return CsvData(
        path=logical_path or str(path),
        header=list(reader.fieldnames or []),
        rows=rows,
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def load_csv_text(text: str, logical_path: str) -> CsvData:
    raw = text.encode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = [{k: clean(v) for k, v in row.items()} for row in reader]
    return CsvData(
        path=logical_path,
        header=list(reader.fieldnames or []),
        rows=rows,
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def load_database(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    data = load_csv_file(path, str(path))
    by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in data.rows:
        code = clean(row.get("hunt_code")).upper()
        if code:
            by_code[code].append(row)
    first = {code: rows[0] for code, rows in by_code.items()}
    return first, by_code


def source_value(db_row: dict[str, str], field: str, database_rel: str) -> tuple[str, str]:
    if field in DIRECT_DB_FIELDS:
        source_field = DIRECT_DB_FIELDS[field]
        return db_row.get(source_field, ""), source_field
    source_field = DERIVED_FIELDS.get(field, "")
    if source_field == "__constant_2026__":
        if clean(db_row.get("permit_allotment_2026_total")):
            return "2026", "permit_allotment_2026_total"
        return "", "permit_allotment_2026_total"
    if source_field == "__quota_source_file__":
        value = db_row.get("permit_allotment_2026_source_file") or db_row.get("permit_allotment_2026_source")
        if not clean(value) and clean(db_row.get("permit_allotment_2026_total")):
            value = database_rel.replace("/", "\\")
        return value, "permit_allotment_2026_source_file"
    if source_field:
        return db_row.get(source_field, ""), source_field
    return "", ""


def is_forbidden(field: str) -> bool:
    lower = field.lower()
    return any(pattern in lower for pattern in FORBIDDEN_PATTERNS)


def classify_blank(field: str, db_available: bool) -> str:
    lower = field.lower()
    if any(pattern in lower for pattern in DEFERRED_MODEL_PATTERNS):
        return "deferred_model_logic"
    if any(pattern in lower for pattern in DEFERRED_DRAW_TRUTH_PATTERNS):
        return "deferred_draw_truth_logic"
    if field in APPROVED_FIELDS and not db_available:
        return "blocker_missing_source"
    if field not in APPROVED_FIELDS:
        return "acceptable_optional_blank"
    return "blocker_unmapped_field"


def load_summary(path: Path) -> tuple[list[dict[str, str]], Counter[tuple[str, str]], dict[str, set[str]], dict[str, set[str]]]:
    rows = load_csv_file(path, str(path)).rows
    applied: Counter[tuple[str, str]] = Counter()
    applied_fields: dict[str, set[str]] = defaultdict(set)
    deferred_fields: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        file_path = clean(row.get("file_path")).replace("\\", "/")
        field = clean(row.get("field_name"))
        status = clean(row.get("status"))
        count = int(clean(row.get("count")) or "0")
        if status == "APPLIED":
            applied[(file_path, field)] += count
            applied_fields[file_path].add(field)
        elif status.startswith("DEFERRED"):
            deferred_fields[file_path].add(field)
    return rows, applied, applied_fields, deferred_fields


def find_backfill_parent(root: Path) -> str | None:
    code, stdout, _ = run_text(
        ["git", "log", "--grep", "Repair targeted prediction feeder backfills", "-n", "1", "--format=%P"],
        root,
    )
    parent = stdout.strip().split()
    if code == 0 and parent:
        return parent[0]
    return None


def git_show_csv(root: Path, ref: str, path: str) -> CsvData | None:
    code, stdout, _ = run_text(["git", "show", f"{ref}:{path}"], root)
    if code != 0:
        return None
    return load_csv_text(stdout, f"{ref}:{path}")


def count_duplicate_keys(rows: list[dict[str, str]], key_fields: list[str]) -> int:
    if not key_fields:
        return 0
    counts: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        key = tuple(clean(row.get(field)) for field in key_fields)
        if all(part == "" for part in key):
            continue
        counts[key] += 1
    return sum(count - 1 for count in counts.values() if count > 1)


def numeric(value: str) -> float | None:
    text = clean(value).replace(",", "")
    if text in {"", "N/A", "NA", "Unlimited", "UNLIMITED"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def quota_arithmetic(rows: list[dict[str, str]], columns: tuple[str, str, str]) -> dict[str, object]:
    res_col, nr_col, total_col = columns
    if not all(col in (rows[0].keys() if rows else []) for col in columns):
        return {"status": "NOT_APPLICABLE", "checked_rows": 0, "failures": 0}
    checked = 0
    failures = 0
    samples: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=2):
        values = [numeric(row.get(col, "")) for col in columns]
        if any(value is None for value in values):
            continue
        checked += 1
        if abs((values[0] or 0) + (values[1] or 0) - (values[2] or 0)) > 0.000001:
            failures += 1
            if len(samples) < 10:
                samples.append(
                    {
                        "row_number": str(index),
                        "hunt_code": row.get("hunt_code", ""),
                        res_col: row.get(res_col, ""),
                        nr_col: row.get(nr_col, ""),
                        total_col: row.get(total_col, ""),
                    }
                )
    status = "PASS" if failures == 0 else "FAIL"
    return {"status": status, "checked_rows": checked, "failures": failures, "samples": samples}


def range_check(rows: list[dict[str, str]], header: list[str]) -> dict[str, object]:
    failures: list[dict[str, object]] = []
    checked = 0
    for col in PROBABILITY_COLUMNS:
        if col not in header:
            continue
        for index, row in enumerate(rows, start=2):
            value = numeric(row.get(col, ""))
            if value is None:
                continue
            checked += 1
            if value < 0 or value > 1:
                failures.append({"row_number": index, "hunt_code": row.get("hunt_code", ""), "field": col, "value": row.get(col, "")})
                if len(failures) >= 50:
                    break
    for col in PERCENT_COLUMNS:
        if col not in header:
            continue
        for index, row in enumerate(rows, start=2):
            value = numeric(row.get(col, ""))
            if value is None:
                continue
            checked += 1
            if value < 0 or value > 100:
                failures.append({"row_number": index, "hunt_code": row.get("hunt_code", ""), "field": col, "value": row.get(col, "")})
                if len(failures) >= 50:
                    break
    return {"status": "PASS" if not failures else "FAIL", "checked_values": checked, "failures": len(failures), "samples": failures[:10]}


def audit_actual_diffs(
    before: CsvData | None,
    after: CsvData,
    database: dict[str, dict[str, str]],
    database_dupes: dict[str, list[dict[str, str]]],
    database_rel: str,
) -> tuple[Counter[str], list[dict[str, str]], list[str], list[dict[str, str]]]:
    changed_by_field: Counter[str] = Counter()
    sample_rows: list[dict[str, str]] = []
    blockers: list[str] = []
    verification_rows: list[dict[str, str]] = []
    if before is None:
        blockers.append("before_snapshot_unavailable")
        return changed_by_field, sample_rows, blockers, verification_rows
    if before.header != after.header:
        blockers.append("header_changed")
    if len(before.rows) != len(after.rows):
        blockers.append("row_count_changed")
    for row_index, (old, new) in enumerate(zip(before.rows, after.rows), start=2):
        changed_fields = [field for field in after.header if norm(old.get(field)) != norm(new.get(field))]
        for field in changed_fields:
            changed_by_field[field] += 1
            hunt_code = clean(new.get("hunt_code")).upper()
            db_row = database.get(hunt_code, {})
            expected, source_field = source_value(db_row, field, database_rel)
            status = "PASS"
            notes = []
            if field not in APPROVED_FIELDS:
                status = "FAIL"
                notes.append("changed_column_not_in_allowlist")
            if is_forbidden(field):
                status = "FAIL"
                notes.append("forbidden_column_changed")
            if not is_blank(old.get(field)):
                status = "FAIL"
                notes.append("target_before_not_blank")
            if not hunt_code:
                status = "FAIL"
                notes.append("missing_hunt_code")
            if not db_row:
                status = "FAIL"
                notes.append("database_hunt_code_not_found")
            if field in APPROVED_FIELDS and is_blank(expected):
                status = "FAIL"
                notes.append("database_source_blank")
            if field in APPROVED_FIELDS and norm(new.get(field)) != norm(expected):
                status = "FAIL"
                notes.append("target_value_not_equal_expected_source")
            dupes = database_dupes.get(hunt_code, [])
            if len(dupes) > 1 and source_field:
                values = {norm(row.get(source_field)) for row in dupes}
                if len(values) > 1:
                    status = "FAIL"
                    notes.append("database_duplicate_hunt_code_conflicting_source_values")
            row_out = {
                "file_path": after.path,
                "row_number": str(row_index),
                "hunt_code": hunt_code,
                "field_name": field,
                "before_value": old.get(field, ""),
                "after_value": new.get(field, ""),
                "source_file": database_rel,
                "source_field": source_field,
                "source_value": expected,
                "status": status,
                "notes": "; ".join(notes) or "source-backed blank-cell fill",
            }
            verification_rows.append(row_out)
            if len(sample_rows) < 25:
                sample_rows.append(row_out)
    return changed_by_field, sample_rows, blockers, verification_rows


def sample_current_source_values(
    file_path: str,
    rows: list[dict[str, str]],
    fields: list[str],
    database: dict[str, dict[str, str]],
    database_rel: str,
    limit: int = 25,
) -> list[dict[str, str]]:
    samples: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=2):
        hunt_code = clean(row.get("hunt_code")).upper()
        db_row = database.get(hunt_code, {})
        if not db_row:
            continue
        for field in fields:
            if field not in row or is_blank(row.get(field)):
                continue
            expected, source_field = source_value(db_row, field, database_rel)
            if is_blank(expected):
                continue
            samples.append(
                {
                    "file_path": file_path,
                    "row_number": str(index),
                    "hunt_code": hunt_code,
                    "field_name": field,
                    "target_value": row.get(field, ""),
                    "source_file": database_rel,
                    "source_field": source_field,
                    "source_value": expected,
                    "status": "PASS" if norm(row.get(field)) == norm(expected) else "REVIEW",
                    "notes": "current source-vs-target sample; not a before/after proof",
                }
            )
            if len(samples) >= limit:
                return samples
    return samples


def download_url(url: str) -> tuple[bytes | None, str | None]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "HUNT-BUILDER acceptance audit"})
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read(), None
    except Exception as exc:  # noqa: BLE001 - report exact network blocker
        return None, str(exc)


def csv_stats_from_bytes(data: bytes, logical_path: str) -> CsvData:
    text = data.decode("utf-8-sig", errors="replace")
    loaded = load_csv_text(text, logical_path)
    return CsvData(
        path=logical_path,
        header=loaded.header,
        rows=loaded.rows,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def load_manifest(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {clean(asset.get("path")).replace("\\", "/"): asset for asset in data.get("assets", [])}


def verify_r2_and_manifest(
    root: Path,
    files: list[str],
    remote_base: str,
    skip_remote: bool = False,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    expected_base = remote_base.rstrip("/") + "/"
    manifest_paths = [
        root / "public/data/runtime-manifest.json",
        root / "data/runtime-manifest.json",
    ]
    manifests = {rel(path, root): load_manifest(path) for path in manifest_paths}
    r2_rows: list[dict[str, object]] = []
    manifest_checks: list[dict[str, object]] = []
    for file_path in files:
        local = load_csv_file(root / file_path, file_path)
        manifest_asset = None
        manifest_statuses = []
        for manifest_path, assets in manifests.items():
            asset = assets.get(file_path)
            if asset:
                manifest_asset = manifest_asset or asset
                canonical_url = clean(asset.get("canonical_url"))
                size_match = str(asset.get("size_bytes", "")) == str(local.size_bytes)
                status = "PASS" if canonical_url.startswith(expected_base) and size_match else "FAIL"
                manifest_statuses.append(status)
                manifest_checks.append(
                    {
                        "manifest": manifest_path,
                        "file_path": file_path,
                        "canonical_url": canonical_url,
                        "manifest_size_bytes": asset.get("size_bytes"),
                        "local_size_bytes": local.size_bytes,
                        "status": status,
                    }
                )
            else:
                manifest_statuses.append("FAIL")
                manifest_checks.append(
                    {
                        "manifest": manifest_path,
                        "file_path": file_path,
                        "canonical_url": "",
                        "manifest_size_bytes": "",
                        "local_size_bytes": local.size_bytes,
                        "status": "FAIL",
                    }
                )
        url = clean((manifest_asset or {}).get("canonical_url")) or f"{expected_base}{file_path}"
        if skip_remote:
            r2_rows.append(
                {
                    "file_path": file_path,
                    "canonical_url": url,
                    "local_size_bytes": local.size_bytes,
                    "remote_size_bytes": "",
                    "local_sha256": local.sha256,
                    "remote_sha256": "",
                    "local_row_count": len(local.rows),
                    "remote_row_count": "",
                    "header_equal": "",
                    "status": "SKIPPED",
                    "notes": "remote verification skipped by flag; manifests still checked",
                }
            )
            continue
        remote_bytes, error = download_url(url)
        if remote_bytes is None:
            r2_rows.append(
                {
                    "file_path": file_path,
                    "canonical_url": url,
                    "local_size_bytes": local.size_bytes,
                    "remote_size_bytes": "",
                    "local_sha256": local.sha256,
                    "remote_sha256": "",
                    "local_row_count": len(local.rows),
                    "remote_row_count": "",
                    "header_equal": "NO",
                    "status": "FAIL",
                    "notes": error or "download_failed",
                }
            )
            continue
        remote = csv_stats_from_bytes(remote_bytes, url)
        status = "PASS"
        notes = []
        if local.size_bytes != remote.size_bytes:
            status = "FAIL"
            notes.append("byte_size_mismatch")
        if local.sha256 != remote.sha256:
            status = "FAIL"
            notes.append("sha256_mismatch")
        if len(local.rows) != len(remote.rows):
            status = "FAIL"
            notes.append("row_count_mismatch")
        if local.header != remote.header:
            status = "FAIL"
            notes.append("header_mismatch")
        if any(item != "PASS" for item in manifest_statuses):
            status = "FAIL"
            notes.append("manifest_mismatch")
        r2_rows.append(
            {
                "file_path": file_path,
                "canonical_url": url,
                "local_size_bytes": local.size_bytes,
                "remote_size_bytes": remote.size_bytes,
                "local_sha256": local.sha256,
                "remote_sha256": remote.sha256,
                "local_row_count": len(local.rows),
                "remote_row_count": len(remote.rows),
                "header_equal": "YES" if local.header == remote.header else "NO",
                "status": status,
                "notes": "; ".join(notes) or "local and R2 match",
            }
        )
    return r2_rows, {"manifest_checks": manifest_checks}


def run_validation_commands(root: Path) -> list[dict[str, object]]:
    commands = [
        ["python", "-m", "compileall", "-q", "engine", "scripts", "tools", "tests"],
        ["python", "tools/audit_engine_feeders.py", "--root", ".", "--forecast-year", "2026", "--warn-only"],
        ["python", "-m", "pytest", "-q", "tests/test_engine_feeder_audit_tools.py"],
        ["git", "diff", "--check"],
    ]
    results = []
    for command in commands:
        code, stdout, stderr = run_text(command, root)
        results.append(
            {
                "command": " ".join(command),
                "exit_code": code,
                "status": "PASS" if code == 0 else "FAIL",
                "stdout_tail": stdout[-4000:],
                "stderr_tail": stderr[-4000:],
            }
        )
    blank_audit = root / "processed_data/audits/prediction_engine_feeder_blank_cell_audit.csv"
    if blank_audit.exists():
        results.append(
            {
                "command": "blank-cell audit rerun",
                "exit_code": None,
                "status": "BLOCKED",
                "stdout_tail": "Existing blank-cell audit found, but no standalone rerun script is present in tools/ or scripts/.",
                "stderr_tail": "",
            }
        )
    else:
        results.append(
            {
                "command": "blank-cell audit rerun",
                "exit_code": None,
                "status": "FAIL",
                "stdout_tail": "",
                "stderr_tail": "Existing blank-cell audit output not found.",
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--database", default="pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv")
    parser.add_argument("--summary", default="processed_data/audits/prediction_engine_targeted_backfill_summary.csv")
    parser.add_argument("--remote-base", default="https://json.uoga.workers.dev/")
    parser.add_argument("--skip-r2", "--skip-remote", action="store_true", dest="skip_r2")
    parser.add_argument("--skip-validation-commands", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    audits_dir = root / "processed_data/audits"
    audits_dir.mkdir(parents=True, exist_ok=True)
    database_rel = args.database.replace("\\", "/")
    database_path = root / database_rel
    summary_path = root / args.summary

    blockers: list[str] = []
    if not database_path.exists():
        blockers.append(f"missing_database:{database_rel}")
    if not summary_path.exists():
        blockers.append(f"missing_summary:{args.summary}")
    for file_path in REPAIRED_FILES:
        if not (root / file_path).exists():
            blockers.append(f"missing_repaired_file:{file_path}")
    if blockers:
        print("\n".join(blockers), file=sys.stderr)
        return 1

    database, database_dupes = load_database(database_path)
    summary_rows, summary_applied, summary_applied_fields, deferred_fields = load_summary(summary_path)
    before_ref = find_backfill_parent(root)
    if not before_ref:
        blockers.append("backfill_parent_commit_not_found")

    per_file: list[dict[str, object]] = []
    column_rows: list[dict[str, object]] = []
    forbidden_rows: list[dict[str, object]] = []
    verification_rows: list[dict[str, str]] = []
    all_samples: dict[str, list[dict[str, str]]] = {}
    total_forbidden_observed = 0
    source_failures = 0
    quota_failures = 0
    before_unavailable_files: list[str] = []

    for file_path in REPAIRED_FILES:
        after = load_csv_file(root / file_path, file_path)
        before = git_show_csv(root, before_ref, file_path) if before_ref else None
        before_available = before is not None
        if not before_available:
            before_unavailable_files.append(file_path)
        actual_changed, samples, diff_blockers, rows = audit_actual_diffs(before, after, database, database_dupes, database_rel)
        verification_rows.extend(rows)
        all_samples[file_path] = samples
        blockers.extend([f"{file_path}:{blocker}" for blocker in diff_blockers])

        changed_columns = sorted(summary_applied_fields.get(file_path, set()))
        deferred_columns = sorted(field for field in deferred_fields.get(file_path, set()) if field in after.header)
        repaired_nulls = {field: sum(1 for row in after.rows if is_blank(row.get(field))) for field in changed_columns if field in after.header}
        deferred_nulls = {field: sum(1 for row in after.rows if is_blank(row.get(field))) for field in deferred_columns}
        quota_checks = {
            "permit_allotment_2026": quota_arithmetic(after.rows, ("permit_allotment_2026_res", "permit_allotment_2026_nr", "permit_allotment_2026_total")),
            "permits_2026": quota_arithmetic(after.rows, ("permits_2026_res", "permits_2026_nr", "permits_2026_total")),
        }
        if any(check["status"] == "FAIL" for check in quota_checks.values()):
            quota_failures += 1
        range_result = range_check(after.rows, after.header)
        duplicate_pk = count_duplicate_keys(after.rows, PRIMARY_KEYS.get(file_path, []))
        changed_cell_count = sum(summary_applied.get((file_path, field), 0) for field in changed_columns)
        current_samples = sample_current_source_values(file_path, after.rows, changed_columns, database, database_rel)

        for field in sorted(set(changed_columns) | set(actual_changed)):
            source_field = DIRECT_DB_FIELDS.get(field) or DERIVED_FIELDS.get(field, "")
            current_expected_match = 0
            current_nonblank = 0
            remaining_null = 0
            for row in after.rows:
                value = row.get(field, "")
                if is_blank(value):
                    remaining_null += 1
                    continue
                current_nonblank += 1
                db_row = database.get(clean(row.get("hunt_code")).upper(), {})
                expected, _ = source_value(db_row, field, database_rel)
                if norm(value) == norm(expected):
                    current_expected_match += 1
            row_status = "PASS"
            notes = []
            if field not in APPROVED_FIELDS:
                row_status = "FAIL"
                notes.append("not in approved repair allowlist")
            if is_forbidden(field):
                row_status = "FAIL"
                notes.append("forbidden pattern")
            if before_available and actual_changed.get(field, 0) != summary_applied.get((file_path, field), 0):
                row_status = "FAIL"
                notes.append("summary count differs from observed git diff")
            if not before_available:
                row_status = "BLOCKED"
                notes.append("before snapshot unavailable for this file")
            column_rows.append(
                {
                    "file_path": file_path,
                    "field_name": field,
                    "approved_field": "YES" if field in APPROVED_FIELDS else "NO",
                    "forbidden_field": "YES" if is_forbidden(field) else "NO",
                    "summary_changed_cell_count": summary_applied.get((file_path, field), 0),
                    "before_available": "YES" if before_available else "NO",
                    "observed_changed_cell_count": actual_changed.get(field, ""),
                    "current_nonblank_count": current_nonblank,
                    "current_expected_match_count": current_expected_match,
                    "remaining_null_count": remaining_null,
                    "source_field": source_field,
                    "acceptance_status": row_status,
                    "notes": "; ".join(notes) or "approved source-backed field",
                }
            )
            if row_status == "FAIL":
                source_failures += 1

        for pattern in FORBIDDEN_PATTERNS:
            matching_fields = [field for field in after.header if pattern in field.lower()]
            summary_count = sum(summary_applied.get((file_path, field), 0) for field in matching_fields)
            observed_count = sum(actual_changed.get(field, 0) for field in matching_fields)
            if observed_count:
                total_forbidden_observed += observed_count
            status = "PASS" if summary_count == 0 and observed_count == 0 else "FAIL"
            if not before_available:
                status = "BLOCKED" if summary_count == 0 else "FAIL"
            forbidden_rows.append(
                {
                    "file_path": file_path,
                    "forbidden_pattern": pattern,
                    "matching_columns": "|".join(matching_fields),
                    "summary_applied_count": summary_count,
                    "before_available": "YES" if before_available else "NO",
                    "observed_changed_cell_count": observed_count if before_available else "",
                    "status": status,
                    "notes": "before snapshot unavailable" if not before_available else "",
                }
            )

        blank_classification = Counter()
        for field in changed_columns + deferred_columns:
            if field not in after.header:
                continue
            for row in after.rows:
                if not is_blank(row.get(field)):
                    continue
                db_available = clean(row.get("hunt_code")).upper() in database
                blank_classification[classify_blank(field, db_available)] += 1

        per_file.append(
            {
                "file_path": file_path,
                "exists": True,
                "row_count": len(after.rows),
                "column_count": len(after.header),
                "changed_cell_count": changed_cell_count,
                "observed_changed_cell_count": sum(actual_changed.values()) if before_available else None,
                "before_snapshot_available": before_available,
                "changed_columns": changed_columns,
                "duplicate_primary_key_count": duplicate_pk,
                "null_count_remaining_in_repaired_columns": repaired_nulls,
                "null_count_remaining_in_deferred_columns": deferred_nulls,
                "blank_classification": dict(blank_classification),
                "probability_column_range_check": range_result,
                "quota_arithmetic_check": quota_checks,
                "sample_repaired_rows": current_samples,
                "before_after_sample_rows": samples,
            }
        )

    r2_rows: list[dict[str, object]] = []
    manifest_result: dict[str, object] = {"manifest_checks": []}
    r2_rows, manifest_result = verify_r2_and_manifest(root, REPAIRED_FILES, args.remote_base, skip_remote=args.skip_r2)
    if not args.skip_r2 and any(row["status"] != "PASS" for row in r2_rows):
        blockers.append("r2_local_mismatch")
    if any(check["status"] != "PASS" for check in manifest_result.get("manifest_checks", [])):
        blockers.append("manifest_mismatch")

    validation_results = []
    if args.skip_validation_commands:
        blockers.append("validation_commands_skipped")
    else:
        validation_results = run_validation_commands(root)

    duplicate_database_conflicts = []
    source_columns = sorted(set(DIRECT_DB_FIELDS.values()) | {value for value in DERIVED_FIELDS.values() if not value.startswith("__")})
    for code, rows in database_dupes.items():
        if len(rows) <= 1:
            continue
        for column in source_columns:
            values = {norm(row.get(column)) for row in rows}
            if len(values) > 1:
                duplicate_database_conflicts.append({"hunt_code": code, "column": column, "values": sorted(values)})
                break

    if duplicate_database_conflicts:
        blockers.append("database_duplicate_hunt_code_conflicting_source_values")
    if total_forbidden_observed:
        blockers.append("forbidden_columns_changed")
    if quota_failures:
        blockers.append("quota_arithmetic_failed")
    if source_failures:
        blockers.append("source_backing_failed")
    if before_unavailable_files:
        blockers.append("before_after_unavailable_for_large_ignored_files")
    if any(result.get("command") == "blank-cell audit rerun" and result.get("status") != "PASS" for result in validation_results):
        blockers.append("blank_cell_audit_rerun_script_not_found")

    r2_status_fail = any(row.get("status") != "PASS" for row in r2_rows) if not args.skip_r2 else False
    hard_fail = bool(
        total_forbidden_observed
        or r2_status_fail
        or quota_failures
        or source_failures
        or duplicate_database_conflicts
        or before_unavailable_files
        or any(check["status"] != "PASS" for check in manifest_result.get("manifest_checks", []))
    )
    deferred_only = not hard_fail and any(
        item.get("blank_classification", {}).get("deferred_model_logic", 0)
        or item.get("blank_classification", {}).get("deferred_draw_truth_logic", 0)
        for item in per_file
    )
    production_readiness = "FAIL" if hard_fail else ("PASS_WITH_DEFERRED_MODEL_FIELDS" if deferred_only else "PASS")

    acceptance = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_readiness": production_readiness,
        "database": database_rel,
        "summary": args.summary,
        "before_ref": before_ref,
        "requirements": {
            "blank_before_repair_proven_for_tracked_files": all(item["before_snapshot_available"] for item in per_file),
            "source_nonblank_and_exact_hunt_code_checked": True,
            "approved_allowlist_checked": True,
            "forbidden_fields_checked": True,
            "r2_checked": not args.skip_r2,
            "remote_base": args.remote_base,
            "manifests_checked": True,
            "validation_commands_run": not args.skip_validation_commands,
        },
        "blockers": sorted(set(blockers)),
        "before_unavailable_files": before_unavailable_files,
        "database_duplicate_conflicts": duplicate_database_conflicts[:100],
        "files": per_file,
        "r2_verification": r2_rows,
        "manifest_verification": manifest_result,
        "validation_results": validation_results,
    }

    write_csv(
        audits_dir / "prediction_engine_targeted_backfill_column_diff.csv",
        [
            "file_path",
            "field_name",
            "approved_field",
            "forbidden_field",
            "summary_changed_cell_count",
            "before_available",
            "observed_changed_cell_count",
            "current_nonblank_count",
            "current_expected_match_count",
            "remaining_null_count",
            "source_field",
            "acceptance_status",
            "notes",
        ],
        column_rows,
    )
    write_csv(
        audits_dir / "prediction_engine_targeted_backfill_forbidden_field_check.csv",
        [
            "file_path",
            "forbidden_pattern",
            "matching_columns",
            "summary_applied_count",
            "before_available",
            "observed_changed_cell_count",
            "status",
            "notes",
        ],
        forbidden_rows,
    )
    write_csv(
        audits_dir / "prediction_engine_targeted_backfill_r2_verification.csv",
        [
            "file_path",
            "canonical_url",
            "local_size_bytes",
            "remote_size_bytes",
            "local_sha256",
            "remote_sha256",
            "local_row_count",
            "remote_row_count",
            "header_equal",
            "status",
            "notes",
        ],
        r2_rows,
    )
    write_csv(
        audits_dir / "prediction_engine_targeted_backfill_verification.csv",
        [
            "file_path",
            "row_number",
            "hunt_code",
            "field_name",
            "before_value",
            "after_value",
            "source_file",
            "source_field",
            "source_value",
            "status",
            "notes",
        ],
        verification_rows,
    )

    (audits_dir / "prediction_engine_targeted_backfill_acceptance.json").write_text(
        json.dumps(acceptance, indent=2),
        encoding="utf-8",
    )
    (audits_dir / "prediction_engine_targeted_backfill_verification.json").write_text(
        json.dumps(
            {
                "generated_at": acceptance["generated_at"],
                "production_readiness": production_readiness,
                "blockers": acceptance["blockers"],
                "verified_changed_cells": len(verification_rows),
                "failed_changed_cells": sum(1 for row in verification_rows if row["status"] != "PASS"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    md_lines = [
        "# Prediction Engine Targeted Backfill Acceptance",
        "",
        f"Generated: {acceptance['generated_at']}",
        f"Production readiness: **{production_readiness}**",
        "",
        "## Scope",
        "",
        "This audit is read-only. It verifies the previous targeted feeder backfill against DATABASE.csv, the repair summary, git history where available, manifests, and Cloudflare R2.",
        "",
        "## Blockers",
        "",
    ]
    if acceptance["blockers"]:
        md_lines.extend([f"- {item}" for item in acceptance["blockers"]])
    else:
        md_lines.append("- None")
    md_lines.extend(["", "## File Results", ""])
    for item in per_file:
        md_lines.extend(
            [
                f"### {item['file_path']}",
                "",
                f"- Rows: {item['row_count']}",
                f"- Columns: {item['column_count']}",
                f"- Summary changed cells: {item['changed_cell_count']}",
                f"- Before snapshot available: {'YES' if item['before_snapshot_available'] else 'NO'}",
                f"- Duplicate primary-key rows: {item['duplicate_primary_key_count']}",
                f"- Changed columns: {', '.join(item['changed_columns']) if item['changed_columns'] else 'None'}",
                f"- Probability range check: {item['probability_column_range_check']['status']}",
                f"- Permit-allotment arithmetic: {item['quota_arithmetic_check']['permit_allotment_2026']['status']}",
                f"- Permits-2026 arithmetic: {item['quota_arithmetic_check']['permits_2026']['status']}",
                "",
            ]
        )
    md_lines.extend(["## R2 Verification", ""])
    for row in r2_rows:
        md_lines.append(f"- {row['file_path']}: {row['status']} ({row['notes']})")
    md_lines.extend(["", "## Validation Commands", ""])
    for result in validation_results:
        md_lines.append(f"- `{result['command']}`: {result['status']} ({result['exit_code']})")
    md_lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Tracked feeder diffs can be proven at cell level from the backfill parent commit. Large ignored/R2-served feeder files do not have Git before snapshots available, so their safety is reconstructed from the repair summary, current DATABASE.csv equality checks, manifests, and R2/local hashes.",
        ]
    )
    (audits_dir / "prediction_engine_targeted_backfill_acceptance.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    (audits_dir / "prediction_engine_targeted_backfill_verification.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps({"production_readiness": production_readiness, "blockers": acceptance["blockers"]}, indent=2))
    return 0 if production_readiness != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
