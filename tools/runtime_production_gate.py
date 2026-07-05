#!/usr/bin/env python3
"""Tiered runtime production gate.

FAST_RUNTIME_GATE validates changed/affected runtime scope without requiring a
full all-family run. FULL_FAMILY_CERTIFICATION is the heavier gate used for
formula, truth, schema, classification, quota, release, and scheduled audits.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AUDIT_ROOT = Path("audits") / "runtime_production_gate"
LATEST_FULL_CERT = AUDIT_ROOT / "LATEST_FULL_FAMILY_CERTIFICATION.json"

FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "PREFERENCE_DRAW": ("preference", "dedicated_hunter", "general_deer", "antlerless", "doe_pronghorn", "point_ladder"),
    "BONUS_SPLIT_DRAW": ("bonus", "split", "max_pool", "random_pool", "utah_bonus_predictive"),
    "YOUTH_RANDOM": ("youth",),
    "AVAILABILITY_ONLY": ("availability", "mountain_lion", "cougar"),
    "OTC_CAPPED": ("otc_capped", "capped"),
    "OTC_UNLIMITED": ("otc_unlimited", "unlimited"),
    "DIRECT_ALLOCATION": ("allocation", "sportsman", "private_lands", "cwmu", "conservation"),
    "HARVEST_FEATURE": ("harvest", "quality"),
    "POINT_LADDER": ("point_ladder", "ladder", "points"),
    "MIXED_DRAW": ("mixed", "utah_predictive_mixed"),
}

RUNTIME_PATTERNS = (
    "prediction",
    "predictions",
    "runtime",
    "draw_system_coverage",
    "hunt_research",
    "point_ladder",
    "ml_draw",
    "availability",
    "report",
)

FEEDER_PATTERNS = (
    "draw_reality_engine",
    "hunt_master_enriched",
    "hunt_unit_reference_linked",
    "DATABASE.csv",
    "point_ladder_view.csv",
    "data_truth/",
    "pipeline/RAW/",
    "data_model/",
)

FULL_CERT_TRIGGERS = (
    "engine/",
    "tools/engine_feeder_contract.py",
    "tools/validate_research_page_canonical_contract.py",
    "contracts/",
    "schemas/",
    "data_truth/draw_results_truth/normalized/",
    "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
)

PROMOTION_COMPILE_COMMAND: tuple[str, ...] = (
    "python",
    "-m",
    "compileall",
    "engine",
    "scripts",
    "tools",
)

PROMOTION_PYTEST_COMMANDS: tuple[tuple[str, ...], ...] = (
    (
        "python",
        "-m",
        "pytest",
        "tests/test_runtime_production_gate.py",
        "-q",
        "-p",
        "no:cacheprovider",
    ),
    (
        "python",
        "-m",
        "pytest",
        "tests/test_engine_no_truth_leakage.py",
        "tests/test_engine_probability_bounds.py",
        "tests/test_engine_quota_arithmetic.py",
        "tests/test_engine_scorable_coverage.py",
        "-q",
        "-p",
        "no:cacheprovider",
    ),
)

csv.field_size_limit(min(sys.maxsize, 2_147_483_647))


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def norm_path(path: str | Path) -> str:
    return str(path).replace("\\", "/").strip()


def rel(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return norm_path(path)


def safe_float(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if not text or text.upper() in {"N/A", "NA", "NULL", "NONE", "UNLIMITED"}:
        return None
    try:
        return float(text)
    except ValueError:
        return math.nan


def safe_int(value: Any) -> int | None:
    value_float = safe_float(value)
    if value_float is None or math.isnan(value_float) or not value_float.is_integer():
        return None
    return int(value_float)


def norm_code(value: Any) -> str:
    return clean(value).upper()


def row_year(row: Mapping[str, Any]) -> int | None:
    for key in ("target_year", "actual_draw_year", "draw_year", "year", "permit_year", "source_year", "truth_year"):
        value = safe_int(row.get(key))
        if value is not None:
            return value
    return None


def probability_columns(fields: Sequence[str]) -> list[str]:
    excluded = re.compile(r"(percent|pct|odds|count|applicant|denominator|display|text|allowed|eligible|flag|status)", re.I)
    return [
        field
        for field in fields
        if re.search(r"(^p_draw$|p_draw_mean|p_random|p_bonus|p_max|probability|prob_|_prob)", field, re.I) and not excluded.search(field)
    ]


def percent_columns(fields: Sequence[str]) -> list[str]:
    excluded = re.compile(r"(odds_text|display_odds|odds_denominator|denominator)", re.I)
    return [field for field in fields if re.search(r"(percent|pct|_odds$)", field, re.I) and not excluded.search(field)]


def count_columns(fields: Sequence[str]) -> list[str]:
    excluded = re.compile(
        r"(source|status|file|url|href|note|method|type|name|class|family|species|weapon|season|date|valid|flag|eligible|category|missing|do_not_use|ratio|delta)",
        re.I,
    )
    included = re.compile(r"(^|_)(permit|permits|quota|applicant|applicants|drawn|available|cap|total|count|allocation|allotment)($|_)", re.I)
    return [field for field in fields if included.search(field) and not excluded.search(field)]


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def run_command(repo: Path, args: Sequence[str]) -> tuple[int, str]:
    proc = subprocess.run(list(args), cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout


def git_text(repo: Path, *args: str) -> str:
    code, out = run_command(repo, ("git", *args))
    return out if code == 0 else f"COMMAND_FAILED git {' '.join(args)}\n{out}"


def changed_files(repo: Path, changed_since: str) -> list[str]:
    paths: set[str] = set()
    for args in (
        ("git", "diff", "--name-only", changed_since),
        ("git", "diff", "--cached", "--name-only"),
        ("git", "ls-files", "--others", "--exclude-standard"),
    ):
        code, out = run_command(repo, args)
        if code == 0:
            paths.update(
                norm_path(line)
                for line in out.splitlines()
                if line.strip() and not line.lower().startswith("warning:") and not line.startswith("COMMAND_FAILED")
            )
    return sorted(paths)


def is_runtime_file(path: str) -> bool:
    low = path.lower()
    if low.endswith("_runtime_updates.csv"):
        return False
    if low.startswith("data_model/runtime_drafts/"):
        return False
    return (
        low.startswith("processed_data/")
        or low.startswith("data_model/")
        or low.startswith("runtime/")
        or low.startswith("public/")
        or low.startswith("pages-dist/")
    ) and any(pattern in low for pattern in RUNTIME_PATTERNS)


def should_audit_prediction_keys(path: str, fields: Sequence[str]) -> bool:
    low = path.lower()
    field_set = {field.lower() for field in fields}
    has_prediction_name = "prediction" in low or "predictive" in low
    has_prediction_key = "hunt_code" in field_set and (
        "residency" in field_set or "points" in field_set or "point_level" in field_set or "draw_pool" in field_set
    )
    return is_runtime_file(path) and has_prediction_name and has_prediction_key


def is_feeder_file(path: str) -> bool:
    low = path.lower()
    return any(pattern.lower() in low for pattern in FEEDER_PATTERNS)


def is_truth_file(path: str) -> bool:
    low = path.lower()
    return low.startswith("data_truth/") or "canonical_yearly" in low or "draw_results_truth" in low


def is_engine_file(path: str) -> bool:
    low = path.lower()
    return low.startswith("engine/") or (low.startswith("tools/") and ("engine" in low or "runtime_production_gate" in low)) or low.startswith("scripts/")


def is_contract_or_schema(path: str) -> bool:
    low = path.lower()
    return low.startswith("contracts/") or low.startswith("schemas/") or "contract" in low or "schema" in low


def affected_families(paths: Sequence[str], explicit: Sequence[str] | None = None) -> list[str]:
    if explicit:
        return sorted(set(explicit))
    families: set[str] = set()
    for path in paths:
        low = path.lower()
        for family, keywords in FAMILY_KEYWORDS.items():
            if any(keyword in low for keyword in keywords):
                families.add(family)
    return sorted(families or {"UNKNOWN"})


def full_cert_required(paths: Sequence[str]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for path in paths:
        low = path.lower()
        if any(low.startswith(trigger.lower()) or trigger.lower() in low for trigger in FULL_CERT_TRIGGERS):
            reasons.append(path)
    return bool(reasons), reasons


def recent_full_cert(repo: Path, max_age_days: int) -> tuple[bool, dict[str, Any]]:
    path = repo / LATEST_FULL_CERT
    if not path.exists():
        return False, {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False, {}
    if payload.get("status") not in {"PROMOTION_READY", "PASS_WITH_REPAIR_CANDIDATES"}:
        return False, payload
    stamp = clean(payload.get("certified_at"))
    try:
        certified = datetime.fromisoformat(stamp)
    except ValueError:
        return False, payload
    return datetime.now() - certified <= timedelta(days=max_age_days), payload


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def summarize_json(path: Path) -> tuple[int, set[str], set[str]]:
    payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    codes: set[str] = set()
    years: set[str] = set()
    rows = 0
    if isinstance(payload, list):
        rows = len(payload)
        for item in payload:
            if isinstance(item, dict):
                if norm_code(item.get("hunt_code")):
                    codes.add(norm_code(item.get("hunt_code")))
                year = row_year(item)
                if year:
                    years.add(str(year))
    elif isinstance(payload, dict):
        details = payload.get("details_by_hunt_code")
        if isinstance(details, dict):
            rows = len(details)
            codes.update(norm_code(code) for code in details if norm_code(code))
        else:
            rows = len(payload)
            for key, item in payload.items():
                if isinstance(item, dict):
                    codes.add(norm_code(item.get("hunt_code") or key))
                    year = row_year(item)
                    if year:
                        years.add(str(year))
    return rows, codes, years


def validate_file(repo: Path, path_text: str, output_dir: Path) -> dict[str, Any]:
    path = repo / path_text
    result = {
        "file_path": path_text,
        "exists": path.exists(),
        "file_type": path.suffix.lower(),
        "row_count": 0,
        "unique_hunt_codes": 0,
        "detected_years": "",
        "schema_valid": "true",
        "probability_valid": "true",
        "percent_valid": "true",
        "quota_valid": "true",
        "duplicate_key_count": 0,
        "leakage_risk": "false",
        "public_safe": "true",
        "issues": "",
    }
    issues: list[str] = []
    probability_rows: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    quota_rows: list[dict[str, Any]] = []
    leakage_rows: list[dict[str, Any]] = []
    if not path.exists():
        issues.append("missing_file")
        result.update({"schema_valid": "false", "public_safe": "false"})
    elif path.suffix.lower() == ".csv":
        try:
            fields, rows = read_csv_rows(path)
            result["row_count"] = len(rows)
            codes: set[str] = set()
            years: set[str] = set()
            key_counts: Counter[tuple[str, str, str, str, str]] = Counter()
            prob_cols = probability_columns(fields)
            pct_cols = percent_columns(fields)
            qty_cols = count_columns(fields)
            audit_probability_bounds = is_runtime_file(path_text)
            audit_prediction_keys = should_audit_prediction_keys(path_text, fields)
            actual_cols = [field for field in fields if "actual" in field.lower()]
            truth_year_cols = [field for field in fields if field.lower() in {"truth_year", "actual_draw_year", "source_year"} or "truth_year" in field.lower()]
            if actual_cols and is_runtime_file(path_text):
                result["leakage_risk"] = "true"
                issues.append("actual_columns_in_runtime_output")
            for row_number, row in enumerate(rows, start=2):
                code = norm_code(row.get("hunt_code"))
                if code:
                    codes.add(code)
                year = row_year(row)
                if year:
                    years.add(str(year))
                if audit_prediction_keys:
                    key_counts[(str(year or ""), code, clean(row.get("residency")), clean(row.get("points") or row.get("point_level")), clean(row.get("draw_pool")))] += 1
                for col in prob_cols if audit_probability_bounds else ():
                    value = safe_float(row.get(col))
                    if value is not None and (math.isnan(value) or value < 0 or value > 1):
                        result["probability_valid"] = "false"
                        probability_rows.append({"file_path": path_text, "row_number": row_number, "column": col, "value": row.get(col), "issue": "probability_out_of_bounds"})
                for col in pct_cols if audit_probability_bounds else ():
                    value = safe_float(row.get(col))
                    if value is not None and (math.isnan(value) or value < 0 or value > 100):
                        result["percent_valid"] = "false"
                        probability_rows.append({"file_path": path_text, "row_number": row_number, "column": col, "value": row.get(col), "issue": "percent_out_of_bounds"})
                for col in qty_cols:
                    value = safe_float(row.get(col))
                    if value is not None and (math.isnan(value) or value < 0):
                        result["quota_valid"] = "false"
                        quota_rows.append({"file_path": path_text, "row_number": row_number, "column": col, "value": row.get(col), "issue": "negative_or_invalid_quantity"})
                for col in truth_year_cols:
                    truth_year = safe_int(row.get(col))
                    target_year = safe_int(row.get("target_year")) or safe_int(row.get("year"))
                    if truth_year and target_year and truth_year >= target_year and is_runtime_file(path_text):
                        result["leakage_risk"] = "true"
                        leakage_rows.append({"file_path": path_text, "row_number": row_number, "target_year": target_year, "truth_year": truth_year, "issue": "truth_year_not_less_than_target_year"})
            duplicate_count = sum(count - 1 for key, count in key_counts.items() if count > 1 and any(key)) if audit_prediction_keys else 0
            result["duplicate_key_count"] = duplicate_count
            if duplicate_count:
                for key, count in key_counts.items():
                    if count > 1 and any(key):
                        duplicate_rows.append({"file_path": path_text, "primary_key": "|".join(key), "duplicate_count": count})
                issues.append("duplicate_keys")
            result["unique_hunt_codes"] = len(codes)
            result["detected_years"] = "|".join(sorted(years))
        except Exception as exc:
            result["schema_valid"] = "false"
            issues.append(f"parse_error:{exc!r}")
    elif path.suffix.lower() == ".json":
        try:
            rows, codes, years = summarize_json(path)
            result["row_count"] = rows
            result["unique_hunt_codes"] = len(codes)
            result["detected_years"] = "|".join(sorted(years))
        except Exception as exc:
            result["schema_valid"] = "false"
            issues.append(f"json_parse_error:{exc!r}")
    else:
        issues.append("unsupported_validation_type")
    if result["probability_valid"] == "false":
        issues.append("invalid_probability_or_percent")
    if result["quota_valid"] == "false":
        issues.append("quota_arithmetic_or_quantity_issue")
    if result["leakage_risk"] == "true":
        issues.append("leakage_risk")
    if issues:
        result["public_safe"] = "false"
    result["issues"] = ";".join(sorted(set(issues)))
    append_csv(output_dir / "PROBABILITY_BOUND_AUDIT.csv", ("file_path", "row_number", "column", "value", "issue"), probability_rows)
    append_csv(output_dir / "DUPLICATE_KEY_AUDIT.csv", ("file_path", "primary_key", "duplicate_count"), duplicate_rows)
    append_csv(output_dir / "NO_LEAKAGE_AUDIT.csv", ("file_path", "row_number", "target_year", "truth_year", "issue"), leakage_rows)
    append_csv(output_dir / "VALIDATION_RESULTS.csv", result.keys(), [result])
    append_csv(output_dir / "RUNTIME_OUTPUT_SAFETY.csv", result.keys(), [result] if is_runtime_file(path_text) else [])
    append_csv(output_dir / "HUNT_CODE_COVERAGE_DELTA.csv", ("file_path", "unique_hunt_codes", "row_count", "detected_years"), [{"file_path": path_text, "unique_hunt_codes": result["unique_hunt_codes"], "row_count": result["row_count"], "detected_years": result["detected_years"]}])
    append_csv(output_dir / "QUOTA_ARITHMETIC_AUDIT.csv", ("file_path", "row_number", "column", "value", "issue"), quota_rows)
    return result


def append_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        if not path.exists():
            write_csv(path, fieldnames, [])
        return
    exists = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore", lineterminator="\n")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def targeted_test_files(repo: Path, families: Sequence[str]) -> list[str]:
    tests: set[str] = set()
    family_terms = {term for family in families for term in FAMILY_KEYWORDS.get(family, ())}
    for path in (repo / "tests").rglob("test_*.py") if (repo / "tests").exists() else []:
        low = rel(path, repo).lower()
        if any(term in low for term in family_terms):
            tests.add(rel(path, repo))
    return sorted(tests)


def promotion_targets(validated_runtime_files: Sequence[str]) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    for src in validated_runtime_files:
        if src.startswith("processed_data/"):
            targets.append((src, f"public/{src}"))
    return targets


def promote_files(repo: Path, output_dir: Path, runtime_files: Sequence[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    manifest: list[dict[str, Any]] = []
    promoted: list[dict[str, Any]] = []
    backups: list[dict[str, Any]] = []
    timestamp = output_dir.name
    for src_text, dst_text in promotion_targets(runtime_files):
        src = repo / src_text
        dst = repo / dst_text
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        backup = ""
        if dst.exists():
            backup_path = dst.with_name(f"{dst.name}.backup_{timestamp}")
            shutil.copy2(dst, backup_path)
            backup = rel(backup_path, repo)
            backups.append({"destination": dst_text, "backup_file": backup})
        shutil.copy2(src, dst)
        promoted.append({"source": src_text, "destination": dst_text, "backup_file": backup})
        manifest.append({"source": src_text, "destination": dst_text, "status": "promoted", "promoted_at": datetime.now().isoformat(timespec="seconds")})
    return manifest, promoted, backups


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--mode", choices=("fast", "full"), required=True)
    parser.add_argument("--write-audits", action="store_true")
    promote_group = parser.add_mutually_exclusive_group()
    promote_group.add_argument("--promote", action="store_true")
    promote_group.add_argument("--no-promote", action="store_true")
    parser.add_argument("--target-years", nargs="*", type=int, default=[2026, 2027])
    parser.add_argument("--families", nargs="*")
    parser.add_argument("--changed-since", default="HEAD")
    parser.add_argument("--require-recent-full-cert", action="store_true")
    parser.add_argument("--max-full-cert-age-days", type=int, default=14)
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = repo / AUDIT_ROOT / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []

    branch = git_text(repo, "branch", "--show-current")
    head = git_text(repo, "rev-parse", "HEAD")
    status_text = git_text(repo, "status", "--short")
    changed = changed_files(repo, args.changed_since)
    if args.mode == "full":
        for path in ENGINE_FEEDERS_FROM_CONTRACT(repo):
            if path not in changed:
                changed.append(path)
    changed = sorted(set(changed))

    write_text(output_dir / "BASELINE_BRANCH.txt", branch)
    write_text(output_dir / "BASELINE_HEAD_COMMIT.txt", head)
    write_text(output_dir / "BASELINE_GIT_STATUS.txt", status_text)
    write_csv(output_dir / "CHANGED_FILES.csv", ("path", "category"), [{"path": path, "category": categorize(path)} for path in changed])

    runtime_files = sorted(path for path in changed if is_runtime_file(path) and Path(path).suffix.lower() in {".csv", ".json"})
    feeder_files = sorted(path for path in changed if is_feeder_file(path) and Path(path).suffix.lower() in {".csv", ".json"})
    cert_required, cert_reasons = full_cert_required(changed)
    if args.mode == "fast":
        feeder_files = [
            path
            for path in feeder_files
            if not path.lower().startswith("data_truth/draw_results_truth/normalized/")
        ]
    if args.mode == "full":
        runtime_files = sorted(set(runtime_files) | {path for path in default_runtime_files(repo) if (repo / path).exists()})
        feeder_files = sorted(set(feeder_files) | {path for path in ENGINE_FEEDERS_FROM_CONTRACT(repo) if (repo / path).exists() and Path(path).suffix.lower() in {".csv", ".json"}})
    families = affected_families(changed, args.families)
    if args.mode == "full":
        cert_required = False
    recent_found, recent_payload = recent_full_cert(repo, args.max_full_cert_age_days)

    write_csv(output_dir / "AFFECTED_ENGINE_FAMILIES.csv", ("engine_family",), [{"engine_family": family} for family in families])
    write_csv(output_dir / "AFFECTED_RUNTIME_FILES.csv", ("file_path",), [{"file_path": path} for path in runtime_files])
    write_csv(output_dir / "AFFECTED_FEEDER_FILES.csv", ("file_path",), [{"file_path": path} for path in feeder_files])

    validation_results = [validate_file(repo, path, output_dir) for path in sorted(set(runtime_files + feeder_files))]
    blockers = []
    repair_candidates = []
    for row in validation_results:
        if row["issues"]:
            if "missing_file" in row["issues"] or "leakage_risk" in row["issues"] or "invalid_probability" in row["issues"] or "schema" in row["issues"]:
                blockers.append(f"{row['file_path']}: {row['issues']}")
            else:
                repair_candidates.append(f"{row['file_path']}: {row['issues']}")
    if cert_required and args.mode == "fast" and (args.require_recent_full_cert or args.promote) and not recent_found:
        blockers.append("FULL_CERT_REQUIRED but no recent full certification found")

    test_blocks: list[str] = []
    compile_cmd = PROMOTION_COMPILE_COMMAND
    commands.append(" ".join(compile_cmd))
    compile_code, compile_out = run_command(repo, compile_cmd)
    test_blocks.append(f"$ {' '.join(compile_cmd)}\nEXIT_CODE={compile_code}\n{compile_out}")
    tests_passing = compile_code == 0
    if compile_code != 0:
        blockers.append("compileall failed")
    if not args.skip_pytest:
        for pytest_cmd in PROMOTION_PYTEST_COMMANDS:
            commands.append(" ".join(pytest_cmd))
            code, out = run_command(repo, pytest_cmd)
            test_blocks.append(f"$ {' '.join(pytest_cmd)}\nEXIT_CODE={code}\n{out}")
            tests_passing = tests_passing and code == 0
            if code != 0:
                blockers.append("runtime promotion pytest failed")
    else:
        test_blocks.append("pytest skipped by --skip-pytest")
    write_text(output_dir / "TEST_RESULTS.txt", "\n\n".join(test_blocks) + "\n")
    write_text(output_dir / "COMMANDS_RUN.txt", "\n".join(commands) + "\n")

    promoted = False
    promoted_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    backup_rows: list[dict[str, Any]] = []
    promotion_ready = not blockers and tests_passing and (not cert_required or args.mode == "full" or recent_found)
    status_value = "PROMOTION_READY" if promotion_ready else "FULL_CERT_REQUIRED" if cert_required and args.mode == "fast" else "PASS_WITH_REPAIR_CANDIDATES" if repair_candidates and not blockers else "FAIL_BLOCKED"
    if args.promote and promotion_ready:
        manifest_rows, promoted_rows, backup_rows = promote_files(repo, output_dir, runtime_files)
        promoted = bool(promoted_rows)
    elif args.promote and not promotion_ready:
        blockers.append("promotion requested but gate is not promotion-ready")
        status_value = "FAIL_BLOCKED"

    write_csv(output_dir / "PROMOTION_MANIFEST.csv", ("source", "destination", "status", "promoted_at"), manifest_rows)
    write_csv(output_dir / "PROMOTED_FILES.csv", ("source", "destination", "backup_file"), promoted_rows)
    write_csv(output_dir / "BACKUP_FILES.csv", ("destination", "backup_file"), backup_rows)

    if args.mode == "full" and promotion_ready:
        cert = {
            "status": status_value,
            "certified_at": datetime.now().isoformat(timespec="seconds"),
            "audit_output_dir": str(output_dir),
            "families": families,
            "target_years": args.target_years,
            "head_commit": head.strip(),
        }
        write_json(output_dir / "FULL_FAMILY_CERTIFICATION.json", cert)
        write_json(repo / LATEST_FULL_CERT, cert)

    summary = {
        "RUNTIME_PRODUCTION_GATE_COMPLETE": not (args.strict and status_value in {"FAIL_BLOCKED", "FULL_CERT_REQUIRED"}),
        "MODE": args.mode,
        "STATUS": status_value,
        "AUDIT_OUTPUT_DIR": str(output_dir),
        "CHANGED_FILES": len(changed),
        "AFFECTED_FAMILIES": ",".join(families),
        "AFFECTED_RUNTIME_FILES": len(runtime_files),
        "AFFECTED_FEEDER_FILES": len(feeder_files),
        "BLOCKERS": len(blockers),
        "REPAIR_CANDIDATES": len(repair_candidates),
        "FULL_CERT_REQUIRED": cert_required,
        "RECENT_FULL_CERT_FOUND": recent_found,
        "TESTS_PASSING": tests_passing,
        "PROMOTION_READY": promotion_ready,
        "PROMOTED": promoted,
    }
    write_json(output_dir / "RUNTIME_GATE_SUMMARY.json", {**summary, "blockers_detail": blockers, "repair_candidates_detail": repair_candidates, "full_cert_reasons": cert_reasons, "recent_full_cert": recent_payload})
    write_text(
        output_dir / "RUNTIME_GATE_SUMMARY.md",
        "\n".join(["# Runtime Production Gate Summary", "", *(f"- {key}: {value}" for key, value in summary.items()), "", "## Blockers", *(f"- {item}" for item in blockers), "", "## Repair Candidates", *(f"- {item}" for item in repair_candidates)])
        + "\n",
    )
    write_text(
        output_dir / "PROMOTION_READINESS.md",
        "\n".join(
            [
                "# Promotion Readiness",
                "",
                f"STATUS: {status_value}",
                f"PROMOTION_READY: {str(promotion_ready).lower()}",
                f"PROMOTED: {str(promoted).lower()}",
                "",
                "## Full Certification",
                f"FULL_CERT_REQUIRED: {str(cert_required).lower()}",
                f"RECENT_FULL_CERT_FOUND: {str(recent_found).lower()}",
                "",
                "## Blockers",
                *(f"- {item}" for item in blockers),
            ]
        )
        + "\n",
    )
    final_lines = []
    for key, value in summary.items():
        if isinstance(value, bool):
            value = str(value).lower()
        final_lines.append(f"{key}: {value}")
    final = "\n".join(final_lines) + "\n"
    write_text(output_dir / "FINAL_CONSOLE_SUMMARY.txt", final)
    print(final, end="")
    return 1 if args.strict and status_value in {"FAIL_BLOCKED", "FULL_CERT_REQUIRED"} else 0


def categorize(path: str) -> str:
    if is_truth_file(path):
        return "truth"
    if is_feeder_file(path):
        return "feeder"
    if is_engine_file(path):
        return "engine"
    if is_runtime_file(path):
        return "runtime_public"
    if is_contract_or_schema(path):
        return "contract_schema"
    if path.startswith("tests/"):
        return "tests"
    return "other"


def default_runtime_files(repo: Path) -> list[str]:
    candidates = [
        "processed_data/hunt_research_2026_summary.json",
        "processed_data/hunt_research_2026_split/hunt_research_2026.index.json",
        "processed_data/hunt_research_2026_split/hunt_research_2026.details.json",
        "processed_data/draw_reality_engine_predictive_v2.csv",
        "processed_data/ml_draw_predictions_v1.csv",
        "processed_data/point_ladder_view.csv",
        "processed_data/draw_system_coverage_report.json",
    ]
    return [path for path in candidates if (repo / path).exists()]


def ENGINE_FEEDERS_FROM_CONTRACT(repo: Path) -> list[str]:
    paths = {
        "processed_data/draw_reality_engine.csv",
        "processed_data/draw_reality_engine_v2.csv",
        "processed_data/draw_reality_engine_predictive_v2.csv",
        "processed_data/ml_draw_predictions_v1.csv",
        "processed_data/point_ladder_view.csv",
        "processed_data/hunt_master_enriched.csv",
        "processed_data/hunt_unit_reference_linked.csv",
        "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
    }
    try:
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        from tools.engine_feeder_contract import feeders_for_group

        for feeder in feeders_for_group():
            paths.add(norm_path(feeder.path))
            paths.update(norm_path(path) for path in feeder.alternatives)
    except Exception:
        pass
    return sorted(paths)


if __name__ == "__main__":
    raise SystemExit(main())
