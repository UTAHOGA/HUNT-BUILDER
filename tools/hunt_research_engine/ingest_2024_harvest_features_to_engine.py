#!/usr/bin/env python3
"""Append missing 2024 harvest feature rows from normalized truth to engine feeder.

This tool does not parse raw PDFs and does not overwrite source truth. It only
copies already-normalized 2024 harvest feature rows into the engine-facing
feature history when the exact (reported_hunt_year, hunt_code) key is absent.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUT_DIR = "audits/hunt_research_engine"
SOURCE_PATH = "data_truth/harvest_results_truth/normalized/harvest_quality_features_all_years_by_hunt_code.csv"
TARGET_PATH = "data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv"
FORBIDDEN_TARGET_PARTS = [
    "pipeline/raw",
    "database.csv",
    "data_truth/draw_results_truth/normalized",
    "data_truth/harvest_results_truth/normalized",
    "engine/",
]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv_atomic(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def key(row: dict[str, str]) -> tuple[str, str]:
    return clean(row.get("reported_hunt_year")), clean(row.get("hunt_code")).upper()


def ensure_safe_target(root: Path, target: Path) -> None:
    rel = target.resolve().relative_to(root.resolve()).as_posix().lower()
    if any(part in rel for part in FORBIDDEN_TARGET_PARTS):
        raise ValueError(f"Refusing to mutate protected target: {rel}")


def build_plan(source_rows: list[dict[str, str]], target_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    target_keys = {key(row) for row in target_rows if key(row)[0] and key(row)[1]}
    candidates = []
    for row in source_rows:
        row_key = key(row)
        if row_key[0] != "2024" or not row_key[1] or row_key in target_keys:
            continue
        if clean(row.get("do_not_use_for_permit_quota")).lower() != "true":
            raise ValueError(f"Source row {row_key} is missing permit-quota guardrail.")
        if clean(row.get("do_not_use_directly_for_p_draw")).lower() != "true":
            raise ValueError(f"Source row {row_key} is missing p_draw guardrail.")
        candidates.append(dict(row))
    return sorted(candidates, key=lambda row: (clean(row.get("reported_hunt_year")), clean(row.get("hunt_code"))))


def write_reports(out_dir: Path, summary: dict[str, object], ledger_rows: list[dict[str, object]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / "harvest_feature_2024_engine_ingestion"
    base.with_suffix(".json").write_text(json.dumps({"summary": summary, "ledger": ledger_rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    columns = [
        "mutation_id",
        "timestamp_utc",
        "mode",
        "target_file",
        "target_sha256_before",
        "target_sha256_after",
        "target_row_number",
        "stable_row_key",
        "column",
        "before_value",
        "after_value",
        "source_file",
        "source_sha256",
        "source_key",
        "source_column",
        "source_value",
        "rule_name",
        "reason",
        "confidence",
        "validation_status",
    ]
    with base.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger_rows)

    lines = [
        "# 2024 Harvest Feature Engine Ingestion",
        "",
        f"- Mode: `{summary['mode']}`.",
        f"- Result: `{summary['result']}`.",
        f"- Source: `{summary['source_file']}`.",
        f"- Target: `{summary['target_file']}`.",
        f"- Target rows before: `{summary['target_rows_before']}`.",
        f"- Planned/appended rows: `{summary['candidate_rows']}`.",
        f"- Target rows after: `{summary['target_rows_after']}`.",
        f"- Protected source files edited: `false`.",
        f"- DATABASE.csv edited: `false`.",
        f"- Normalized truth edited: `false`.",
        "",
        "## Appended Hunt Codes",
        "",
        "| Hunt Code | Species | Hunt Name | Source |",
        "| --- | --- | --- | --- |",
    ]
    for row in ledger_rows:
        if row.get("column") == "ROW_APPEND":
            lines.append(f"| {row['source_key']} | {row.get('species', '')} | {row.get('hunt_name', '')} | {row['source_file']} |")
    if not ledger_rows:
        lines.append("|  |  |  | No rows required |")
    base.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--source", default=SOURCE_PATH, help="Normalized truth feature source.")
    parser.add_argument("--target", default=TARGET_PATH, help="Engine harvest feature history target.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Audit output directory.")
    parser.add_argument("--dry-run", action="store_true", help="Plan only. This is the default.")
    parser.add_argument("--apply", action="store_true", help="Append the planned rows.")
    parser.add_argument("--max-additions", type=int, default=25, help="Safety brake for appended rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    source = (root / args.source).resolve()
    target = (root / args.target).resolve()
    out_dir = (root / args.out_dir).resolve()
    mode = "apply" if args.apply else "dry-run"

    if not source.exists():
        raise FileNotFoundError(source)
    if not target.exists():
        raise FileNotFoundError(target)
    ensure_safe_target(root, target)

    source_fields, source_rows = read_csv(source)
    target_fields, target_rows = read_csv(target)
    if source_fields != target_fields:
        raise ValueError("Source and target schemas differ; refusing to append.")

    candidates = build_plan(source_rows, target_rows)
    if len(candidates) > args.max_additions:
        raise ValueError(f"Planned additions {len(candidates)} exceed --max-additions {args.max_additions}.")

    source_hash = sha256(source)
    target_hash_before = sha256(target)
    timestamp = datetime.now(timezone.utc).isoformat()
    target_row_start = len(target_rows) + 2
    ledger_rows: list[dict[str, object]] = []
    for offset, row in enumerate(candidates):
        row_num = target_row_start + offset
        mutation_id = f"harvest-2024-feature-{offset + 1:04d}"
        ledger_rows.append(
            {
                "mutation_id": mutation_id,
                "timestamp_utc": timestamp,
                "mode": mode,
                "target_file": str(target.relative_to(root)),
                "target_sha256_before": target_hash_before,
                "target_sha256_after": "",
                "target_row_number": row_num,
                "stable_row_key": f"reported_hunt_year=2024|hunt_code={clean(row.get('hunt_code')).upper()}",
                "column": "ROW_APPEND",
                "before_value": "",
                "after_value": json.dumps({field: row.get(field, "") for field in target_fields}, sort_keys=True),
                "source_file": str(source.relative_to(root)),
                "source_sha256": source_hash,
                "source_key": clean(row.get("hunt_code")).upper(),
                "source_column": "FULL_ROW",
                "source_value": json.dumps({field: row.get(field, "") for field in source_fields}, sort_keys=True),
                "rule_name": "append_missing_2024_harvest_feature_from_normalized_truth",
                "reason": "Exact 2024 hunt_code feature row exists in normalized harvest truth and is absent from engine harvest feature history.",
                "confidence": "HIGH",
                "validation_status": "PLANNED" if not args.apply else "APPLIED_PENDING_HASH",
                "species": clean(row.get("species")),
                "hunt_name": clean(row.get("hunt_name")),
            }
        )

    target_rows_after = target_rows
    target_hash_after = target_hash_before
    if args.apply and candidates:
        target_rows_after = target_rows + candidates
        write_csv_atomic(target, target_rows_after, target_fields)
        target_hash_after = sha256(target)
        for row in ledger_rows:
            row["target_sha256_after"] = target_hash_after
            row["validation_status"] = "APPLIED"
    elif not args.apply:
        for row in ledger_rows:
            row["target_sha256_after"] = target_hash_before

    summary = {
        "generated_at_utc": timestamp,
        "mode": mode,
        "result": "PASS",
        "source_file": str(source.relative_to(root)),
        "target_file": str(target.relative_to(root)),
        "source_rows": len(source_rows),
        "target_rows_before": len(target_rows),
        "candidate_rows": len(candidates),
        "target_rows_after": len(target_rows_after),
        "source_sha256": source_hash,
        "target_sha256_before": target_hash_before,
        "target_sha256_after": target_hash_after,
        "database_csv_edited": False,
        "normalized_truth_edited": False,
        "raw_sources_edited": False,
        "engine_code_edited": False,
    }
    write_reports(out_dir, summary, ledger_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
