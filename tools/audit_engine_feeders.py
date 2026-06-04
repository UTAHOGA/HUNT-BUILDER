#!/usr/bin/env python3
"""Audit prediction engine feeder contracts.

The audit is intentionally read-only: missing official files are reported as
blockers instead of being generated.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.engine_feeder_contract import FeederContract, feeders_for_group, groups


AUDIT_DIR = Path("audits/engine_feeders")

_FIELD_SIZE_LIMIT = sys.maxsize
while True:
    try:
        csv.field_size_limit(_FIELD_SIZE_LIMIT)
        break
    except OverflowError:
        _FIELD_SIZE_LIMIT = int(_FIELD_SIZE_LIMIT / 10)


def _clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def _is_blank(value: object) -> bool:
    return _clean(value) == ""


def _parse_float(value: object) -> float | None:
    text = _clean(value).replace(",", "")
    if text == "":
        return None
    try:
        result = float(text)
    except ValueError:
        return math.nan
    return result


def _resolve_path(root: Path, contract: FeederContract) -> tuple[Path, str, list[str]]:
    primary = root / contract.path
    checked = [contract.path]
    if primary.exists():
        return primary, contract.path, checked
    for alt in contract.alternatives:
        checked.append(alt)
        alt_path = root / alt
        if alt_path.exists():
            return alt_path, alt, checked
    return primary, contract.path, checked


def _read_csv_summary(path: Path, contract: FeederContract) -> dict[str, object]:
    result: dict[str, object] = {
        "row_count": 0,
        "column_count": 0,
        "missing_required_columns": [],
        "duplicate_key_count": 0,
        "null_critical_fields": {},
        "null_lineage_fields": {},
        "invalid_numeric_values": {},
        "invalid_probability_values": {},
        "invalid_percent_values": {},
        "invalid_nonnegative_integer_values": {},
    }
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        fieldset = set(fieldnames)
        result["column_count"] = len(fieldnames)
        result["missing_required_columns"] = [col for col in contract.required_columns if col not in fieldset]
        key_counter: Counter[tuple[str, ...]] = Counter()
        null_critical: Counter[str] = Counter()
        null_lineage: Counter[str] = Counter()
        invalid_numeric: Counter[str] = Counter()
        invalid_probability: Counter[str] = Counter()
        invalid_percent: Counter[str] = Counter()
        invalid_integer: Counter[str] = Counter()

        for row in reader:
            result["row_count"] = int(result["row_count"]) + 1
            if contract.primary_key and all(col in fieldset for col in contract.primary_key):
                key = tuple(_clean(row.get(col)) for col in contract.primary_key)
                if all(key):
                    key_counter[key] += 1
            for col in contract.critical_columns:
                if col in fieldset and _is_blank(row.get(col)):
                    null_critical[col] += 1
            for col in contract.lineage_columns:
                if col in fieldset and _is_blank(row.get(col)):
                    null_lineage[col] += 1
            for col in contract.numeric_columns:
                if col in fieldset:
                    value = _parse_float(row.get(col))
                    if value is not None and math.isnan(value):
                        invalid_numeric[col] += 1
            for col in contract.probability_columns:
                if col in fieldset:
                    value = _parse_float(row.get(col))
                    if value is not None and (math.isnan(value) or value < 0 or value > 1):
                        invalid_probability[col] += 1
            for col in contract.percent_columns:
                if col in fieldset:
                    value = _parse_float(row.get(col))
                    if value is not None and (math.isnan(value) or value < 0 or value > 100):
                        invalid_percent[col] += 1
            for col in contract.nonnegative_integer_columns:
                if col in fieldset:
                    value = _parse_float(row.get(col))
                    if value is not None and (math.isnan(value) or value < 0 or not float(value).is_integer()):
                        invalid_integer[col] += 1

        result["duplicate_key_count"] = sum(count - 1 for count in key_counter.values() if count > 1)
        result["null_critical_fields"] = dict(sorted(null_critical.items()))
        result["null_lineage_fields"] = dict(sorted(null_lineage.items()))
        result["invalid_numeric_values"] = dict(sorted(invalid_numeric.items()))
        result["invalid_probability_values"] = dict(sorted(invalid_probability.items()))
        result["invalid_percent_values"] = dict(sorted(invalid_percent.items()))
        result["invalid_nonnegative_integer_values"] = dict(sorted(invalid_integer.items()))
    return result


def _status_from_result(contract: FeederContract, result: dict[str, object]) -> tuple[str, list[str], bool]:
    issues: list[str] = []
    blocker = False
    if not result["exists"]:
        issues.append("missing_file")
        blocker = bool(contract.required and contract.production_blocker)
        return ("BLOCKER" if blocker else "WARN", issues, blocker)
    if result.get("parse_error"):
        issues.append("parse_error")
        blocker = bool(contract.required and contract.production_blocker)
    if result.get("missing_required_columns"):
        issues.append("missing_required_columns")
        blocker = bool(contract.required and contract.production_blocker)
    if int(result.get("duplicate_key_count") or 0) > 0:
        issues.append("duplicate_primary_keys")
        blocker = bool(contract.required and contract.production_blocker)
    for key in ("invalid_probability_values", "invalid_percent_values", "invalid_nonnegative_integer_values", "invalid_numeric_values"):
        if result.get(key):
            issues.append(key)
            blocker = bool(contract.required and contract.production_blocker)
    if result.get("null_critical_fields"):
        issues.append("null_critical_fields")
        blocker = bool(contract.required and contract.production_blocker)
    if contract.generated:
        missing_lineage_columns = [col for col in contract.lineage_columns if result.get("exists") and col not in set(result.get("columns", []))]
        if missing_lineage_columns:
            result["missing_lineage_columns"] = missing_lineage_columns
            issues.append("missing_lineage_columns")
            blocker = bool(contract.required and contract.production_blocker)
        if result.get("null_lineage_fields"):
            issues.append("null_lineage_fields")
            blocker = bool(contract.required and contract.production_blocker)
    if blocker:
        return "BLOCKER", issues, True
    if issues:
        return "WARN", issues, False
    return "PASS", issues, False


def audit_contract(root: Path, contract: FeederContract) -> dict[str, object]:
    path, resolved_path, checked_paths = _resolve_path(root, contract)
    result: dict[str, object] = {
        "group": contract.group,
        "path": contract.path,
        "resolved_path": resolved_path,
        "checked_paths": checked_paths,
        "consumer_module": contract.consumer_module,
        "required": contract.required,
        "production_blocker": contract.production_blocker,
        "file_type": contract.file_type,
        "primary_key": list(contract.primary_key),
        "required_columns": list(contract.required_columns),
        "critical_columns": list(contract.critical_columns),
        "lineage_columns": list(contract.lineage_columns),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "row_count": None,
        "column_count": None,
        "columns": [],
        "notes": contract.notes,
    }
    if not path.exists():
        status, issues, blocker = _status_from_result(contract, result)
        result.update({"status": status, "issues": issues, "blocker": blocker})
        return result

    try:
        if contract.file_type == "csv":
            csv_result = _read_csv_summary(path, contract)
            result.update(csv_result)
            with path.open(newline="", encoding="utf-8-sig") as handle:
                result["columns"] = list(csv.DictReader(handle).fieldnames or [])
        elif contract.file_type == "json":
            with path.open(encoding="utf-8") as handle:
                parsed = json.load(handle)
            result["json_type"] = type(parsed).__name__
            result["json_top_level_count"] = len(parsed) if hasattr(parsed, "__len__") else None
        else:
            result["row_count"] = None
            result["column_count"] = None
    except Exception as exc:  # noqa: BLE001 - audit must report parse errors.
        result["parse_error"] = f"{type(exc).__name__}: {exc}"

    status, issues, blocker = _status_from_result(contract, result)
    result.update({"status": status, "issues": issues, "blocker": blocker})
    return result


def _flatten_issue_counts(mapping: object) -> int:
    if isinstance(mapping, dict):
        return int(sum(int(v) for v in mapping.values()))
    if isinstance(mapping, list):
        return len(mapping)
    return 0


def write_reports(root: Path, results: list[dict[str, object]], forecast_year: int) -> None:
    out_dir = root / AUDIT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    block_count = sum(1 for row in results if row["blocker"])
    status_counts = Counter(str(row["status"]) for row in results)
    group_counts = Counter(str(row["group"]) for row in results)
    summary = {
        "forecast_year": forecast_year,
        "total_contracts": len(results),
        "status_counts": dict(sorted(status_counts.items())),
        "group_counts": dict(sorted(group_counts.items())),
        "production_blocker_count": block_count,
        "production_ready": block_count == 0,
        "results": results,
    }
    (out_dir / "engine_feeder_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    fieldnames = [
        "group",
        "path",
        "resolved_path",
        "consumer_module",
        "required",
        "production_blocker",
        "status",
        "blocker",
        "exists",
        "size_bytes",
        "row_count",
        "column_count",
        "duplicate_key_count",
        "missing_required_column_count",
        "null_critical_count",
        "null_lineage_count",
        "invalid_probability_count",
        "invalid_percent_count",
        "invalid_nonnegative_integer_count",
        "issues",
        "notes",
    ]
    with (out_dir / "engine_feeder_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in results:
            writer.writerow({
                "group": row["group"],
                "path": row["path"],
                "resolved_path": row["resolved_path"],
                "consumer_module": row["consumer_module"],
                "required": row["required"],
                "production_blocker": row["production_blocker"],
                "status": row["status"],
                "blocker": row["blocker"],
                "exists": row["exists"],
                "size_bytes": row["size_bytes"],
                "row_count": row.get("row_count"),
                "column_count": row.get("column_count"),
                "duplicate_key_count": row.get("duplicate_key_count", 0),
                "missing_required_column_count": _flatten_issue_counts(row.get("missing_required_columns")),
                "null_critical_count": _flatten_issue_counts(row.get("null_critical_fields")),
                "null_lineage_count": _flatten_issue_counts(row.get("null_lineage_fields")),
                "invalid_probability_count": _flatten_issue_counts(row.get("invalid_probability_values")),
                "invalid_percent_count": _flatten_issue_counts(row.get("invalid_percent_values")),
                "invalid_nonnegative_integer_count": _flatten_issue_counts(row.get("invalid_nonnegative_integer_values")),
                "issues": ";".join(str(x) for x in row.get("issues", [])),
                "notes": row.get("notes", ""),
            })

    lines = [
        "# Engine Feeder Audit",
        "",
        f"Forecast year: {forecast_year}",
        f"Total contracts: {len(results)}",
        f"Production blockers: {block_count}",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "## Blockers", ""])
    blockers = [row for row in results if row["blocker"]]
    if blockers:
        for row in blockers:
            lines.append(f"- `{row['group']}` `{row['path']}`: {', '.join(row.get('issues', []))}")
    else:
        lines.append("- None")
    lines.extend(["", "## Feeder Results", ""])
    lines.append("| Status | Group | Path | Rows | Duplicate Keys | Issues |")
    lines.append("| --- | --- | --- | ---: | ---: | --- |")
    for row in results:
        issues = ", ".join(row.get("issues", [])) or "-"
        lines.append(
            f"| {row['status']} | {row['group']} | `{row['path']}` | "
            f"{row.get('row_count') if row.get('row_count') is not None else ''} | "
            f"{row.get('duplicate_key_count', 0)} | {issues} |"
        )
    (out_dir / "engine_feeder_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit prediction engine feeder contracts.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--forecast-year", type=int, default=2026)
    parser.add_argument("--group", choices=groups())
    parser.add_argument("--check-only", action="store_true", help="Do not write audit files; return status only.")
    parser.add_argument("--warn-only", action="store_true", help="Return 0 even when production blockers exist.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.root).resolve()
    contracts = list(feeders_for_group(args.group))
    results = [audit_contract(root, contract) for contract in contracts]
    blockers = [row for row in results if row["blocker"]]

    if not args.check_only:
        write_reports(root, results, args.forecast_year)

    status_counts = Counter(str(row["status"]) for row in results)
    print(f"contracts={len(results)} blockers={len(blockers)} statuses={dict(sorted(status_counts.items()))}")
    if blockers:
        print("blockers:")
        for row in blockers[:50]:
            print(f"- {row['group']} {row['path']}: {', '.join(row.get('issues', []))}")
        if len(blockers) > 50:
            print(f"... {len(blockers) - 50} more")

    if blockers and not args.warn_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
