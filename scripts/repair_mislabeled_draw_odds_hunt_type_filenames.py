#!/usr/bin/env python3
"""Rename draw-odds PDFs whose path hunt-type suffix disagrees with audited pages."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
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


def load_single_hunt_type(hunt_type_counts_json: str) -> str:
    counts = json.loads(hunt_type_counts_json or "{}")
    draw_types = [hunt_type for hunt_type in counts if hunt_type != "UNKNOWN"]
    if len(draw_types) != 1:
        return ""
    return draw_types[0]


def replacement_path(path: Path, audited_hunt_type: str) -> Path:
    parts = list(path.parts)
    bad_tokens = {
        "ANTLERLESS_BLACK_BEAR",
        "YOUTH_ANTLERLESS_BLACK_BEAR",
        "CWMU_ANTLERLESS_BLACK_BEAR",
        "CWMU_YOUTH_ANTLERLESS_BLACK_BEAR",
        "CWMU_BIG_GAME_BLACK_BEAR",
        "LE_BLACK_BEAR",
    }

    new_parts = []
    for part in parts[:-1]:
        new_parts.append(audited_hunt_type if part in bad_tokens else part)

    name = path.name
    for token in sorted(bad_tokens, key=len, reverse=True):
        name = name.replace(token, audited_hunt_type)
    new_parts.append(name)
    return Path(*new_parts)


def source_hunt_codes_by_pdf(audit_dir: Path) -> dict[str, set[str]]:
    page_audit = audit_dir / "page_role_audit.csv"
    by_pdf: dict[str, set[str]] = {}
    if not page_audit.exists():
        return by_pdf
    with page_audit.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            hunt_code = (row.get("hunt_code") or "").strip()
            if not hunt_code:
                continue
            source = str(safe_repo_path(row["source_pdf"]))
            by_pdf.setdefault(source, set()).add(hunt_code)
    return by_pdf


def append_pdf(source: Path, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".tmp")
    with fitz.open(target) as target_doc:
        target_doc.insert_pdf(fitz.open(source))
        target_doc.save(tmp)
    tmp.replace(target)


def inactive_fragment_path(source: Path) -> Path:
    return source.parent / "Merged Source Fragments" / source.name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--merge-existing-targets",
        action="store_true",
        help="Append non-overlapping mislabeled fragments into the existing correct target PDF.",
    )
    args = parser.parse_args()

    audit_dir = args.audit_dir
    if not audit_dir.is_absolute():
        audit_dir = REPO / audit_dir
    file_audit = audit_dir / "file_role_audit.csv"
    if not file_audit.exists():
        raise FileNotFoundError(file_audit)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    rows: list[dict[str, object]] = []
    hunt_codes_by_pdf = source_hunt_codes_by_pdf(audit_dir)
    backup_dir = AUDIT_ROOT / f"mislabeled_hunt_type_merge_backups_{stamp}"
    with file_audit.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            source_pdf = safe_repo_path(row["source_pdf"])
            audited_hunt_type = load_single_hunt_type(row["hunt_type_counts_json"])
            if not audited_hunt_type:
                continue
            if "BLACK_BEAR" not in str(source_pdf) or "BLACK_BEAR" in audited_hunt_type:
                continue
            target_pdf = replacement_path(source_pdf, audited_hunt_type)
            if target_pdf == source_pdf:
                continue
            target_pdf.resolve().relative_to(REPO.resolve())
            source_hunt_codes = hunt_codes_by_pdf.get(str(source_pdf), set())
            target_hunt_codes = hunt_codes_by_pdf.get(str(target_pdf), set())
            overlap = sorted(source_hunt_codes & target_hunt_codes)
            rows.append(
                {
                    "year": row["year"],
                    "action": "RENAMED" if args.apply else "DRY_RUN",
                    "source_pdf": str(source_pdf),
                    "target_pdf": str(target_pdf),
                    "audited_hunt_type": audited_hunt_type,
                    "source_exists": source_pdf.exists(),
                    "target_exists": target_pdf.exists(),
                    "source_hunt_code_count": len(source_hunt_codes),
                    "target_hunt_code_count": len(target_hunt_codes),
                    "overlap_hunt_codes": ",".join(overlap),
                    "inactive_fragment_pdf": str(inactive_fragment_path(source_pdf)),
                    "target_backup_pdf": str(backup_dir / target_pdf.relative_to(REPO)),
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
            if target.exists() and not args.merge_existing_targets:
                row["action"] = "SKIPPED_TARGET_EXISTS"
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
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)

    output = AUDIT_ROOT / f"mislabeled_hunt_type_filename_repair_{stamp}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "year",
        "action",
        "source_pdf",
        "target_pdf",
        "audited_hunt_type",
        "source_exists",
        "target_exists",
        "source_hunt_code_count",
        "target_hunt_code_count",
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
