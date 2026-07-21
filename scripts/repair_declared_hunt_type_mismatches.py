#!/usr/bin/env python3
"""Repair active PDFs whose declared path hunt type differs from audited content."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import fitz


REPO = Path(__file__).resolve().parents[1]
AUDIT_ROOT = REPO / "audits" / "draw_odds_pdf_page_role_audit"


def safe_repo_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO / path
    resolved = path.resolve()
    resolved.relative_to(REPO.resolve())
    return resolved


def single_hunt_type(hunt_type_counts_json: str) -> str:
    counts = json.loads(hunt_type_counts_json or "{}")
    hunt_types = [hunt_type for hunt_type in counts if hunt_type != "UNKNOWN"]
    return hunt_types[0] if len(hunt_types) == 1 else ""


def declared_tokens(path: Path, known_hunt_types: set[str]) -> list[str]:
    tokens: list[str] = []
    parts = list(path.parts)
    for index, part in enumerate(parts[:-1]):
        if part.upper() == "SPLIT BY HUNT TYPE" and index + 1 < len(parts):
            tokens.append(parts[index + 1])
    upper_stem = path.stem.upper()
    if upper_stem.count("__") >= 2:
        pieces = upper_stem.split("__")
        if pieces[-1] in {"CWMU_DEDUPED", "CWMU_UNIQUE_PAGES"} and len(pieces) >= 3:
            if pieces[-2] in known_hunt_types:
                tokens.append(pieces[-2])
        else:
            if pieces[-1] in known_hunt_types:
                tokens.append(pieces[-1])
    return tokens


def target_path(path: Path, audited_hunt_type: str, bad_tokens: list[str]) -> Path:
    parts = []
    for part in path.parts[:-1]:
        parts.append(audited_hunt_type if part in bad_tokens else part)
    name = path.name
    for token in sorted(set(bad_tokens), key=len, reverse=True):
        name = name.replace(token, audited_hunt_type)
    parts.append(name)
    return Path(*parts)


def hunt_codes_by_pdf(audit_dir: Path) -> dict[str, set[str]]:
    by_pdf: dict[str, set[str]] = defaultdict(set)
    with (audit_dir / "page_role_audit.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            hunt_code = (row.get("hunt_code") or "").strip()
            if hunt_code:
                by_pdf[str(safe_repo_path(row["source_pdf"]))].add(hunt_code)
    return by_pdf


def append_pdf(source: Path, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".tmp")
    with fitz.open(target) as target_doc:
        with fitz.open(source) as source_doc:
            target_doc.insert_pdf(source_doc)
        target_doc.save(tmp)
    tmp.replace(target)


def inactive_fragment_path(source: Path) -> Path:
    return source.parent / "Merged Source Fragments" / source.name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--include-permit-quota", action="store_true")
    args = parser.parse_args()

    audit_dir = args.audit_dir
    if not audit_dir.is_absolute():
        audit_dir = REPO / audit_dir

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    backup_dir = AUDIT_ROOT / f"declared_hunt_type_mismatch_merge_backups_{stamp}"
    code_map = hunt_codes_by_pdf(audit_dir)
    rows: list[dict[str, object]] = []
    file_rows = list(csv.DictReader((audit_dir / "file_role_audit.csv").open(newline="", encoding="utf-8")))
    known_hunt_types = {
        hunt_type
        for row in file_rows
        for hunt_type in json.loads(row["hunt_type_counts_json"] or "{}")
        if hunt_type != "UNKNOWN"
    }

    for row in file_rows:
            audited_hunt_type = single_hunt_type(row["hunt_type_counts_json"])
            if not audited_hunt_type:
                continue
            if audited_hunt_type.startswith("PERMIT_QUOTA_") and not args.include_permit_quota:
                continue
            source = safe_repo_path(row["source_pdf"])
            bad_tokens = [token for token in declared_tokens(source, known_hunt_types) if token != audited_hunt_type]
            if not bad_tokens:
                continue
            target = target_path(source, audited_hunt_type, bad_tokens)
            target.resolve().relative_to(REPO.resolve())
            target_codes = code_map.get(str(target), set())
            source_codes = code_map.get(str(source), set())
            overlap = sorted(source_codes & target_codes)
            rows.append(
                {
                    "year": row["year"],
                    "action": "DRY_RUN",
                    "audited_hunt_type": audited_hunt_type,
                    "declared_tokens": ",".join(bad_tokens),
                    "source_pdf": str(source),
                    "target_pdf": str(target),
                    "source_exists": source.exists(),
                    "target_exists": target.exists(),
                    "overlap_hunt_codes": ",".join(overlap),
                    "inactive_fragment_pdf": str(inactive_fragment_path(source)),
                    "target_backup_pdf": str(backup_dir / target.relative_to(REPO)),
                }
            )

    if args.apply:
        for row in rows:
            source = Path(str(row["source_pdf"]))
            target = Path(str(row["target_pdf"]))
            if not source.exists():
                row["action"] = "SKIPPED_SOURCE_MISSING"
                continue
            if row["overlap_hunt_codes"]:
                row["action"] = "SKIPPED_HUNT_CODE_OVERLAP"
                continue
            if target.exists():
                backup = Path(str(row["target_backup_pdf"]))
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                append_pdf(source, target)
                inactive = Path(str(row["inactive_fragment_pdf"]))
                inactive.parent.mkdir(parents=True, exist_ok=True)
                source.replace(inactive)
                row["action"] = "MERGED_INTO_TARGET"
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                source.replace(target)
                row["action"] = "RENAMED"

    output = AUDIT_ROOT / f"declared_hunt_type_mismatch_repair_{stamp}.csv"
    fields = [
        "year",
        "action",
        "audited_hunt_type",
        "declared_tokens",
        "source_pdf",
        "target_pdf",
        "source_exists",
        "target_exists",
        "overlap_hunt_codes",
        "inactive_fragment_pdf",
        "target_backup_pdf",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({"apply": args.apply, "actions": len(rows), "output": str(output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
