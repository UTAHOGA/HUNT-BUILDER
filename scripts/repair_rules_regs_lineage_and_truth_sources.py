from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path


REPO = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
PIPELINE_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
TRUTH_RAW_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs"
AUDIT_ROOT = REPO / "audits"

SKIP_DIR_NAMES = {
    ".git",
    "audits",
    "canonical",
    "generated",
    "_quarantine",
    "_duplicate_archive",
    "__pycache__",
}

REFERENCE_ROOTS = [
    REPO / "data_truth",
    REPO / "data_model" / "quality",
    REPO / "processed_data",
    REPO / "scripts",
    REPO / "tests",
    REPO / "tools",
    REPO / "docs",
]

TEXT_EXTENSIONS = {
    ".csv",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".html",
    ".css",
}

PATH_REPLACEMENTS = {
    "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__COUGAR.pdf": "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__COUGAR.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\2022_REGULATIONS__23_COUGAR.pdf": "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\2022_REGULATIONS__COUGAR.pdf",
    "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__COUGAR.pdf": "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__COUGAR.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\guidebook_2022-23_cougar.pdf": "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\2022_REGULATIONS__COUGAR.pdf",
    "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__COUGAR.pdf": "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__COUGAR.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\Rules Regs\\2022-23_cougar.pdf": "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\2022_REGULATIONS__COUGAR.pdf",
    "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__FURBEARER.pdf": "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__FURBEARER.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\Rules Regs\\2022-23_furbearer.pdf": "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\2022_REGULATIONS__FURBEARER.pdf",
    "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__UPLAND_TURKEY.pdf": "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\Rules Regs\\2022-23_upland_turkey.pdf": "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\2022_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__BEAR.pdf": "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__BEAR.pdf",
    "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__BIGGAMEAPP.pdf": "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__BIGGAMEAPP.pdf",
    "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__FIELD_REGS.pdf": "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__FIELD_REGS.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\Rules Regs\\2022_bear.pdf": "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\2022_REGULATIONS__BEAR.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\Rules Regs\\2022_biggameapp.pdf": "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\2022_REGULATIONS__BIGGAMEAPP.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\Rules Regs\\2022_field_regs.pdf": "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\2022_REGULATIONS__FIELD_REGS.pdf",
    "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__UPLAND_TURKEY.pdf": "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2023\\pdf\\regulations\\2023_REGULATIONS__2022_23_UPLAND_TURKEY.pdf": "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\2022_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__CONSERVATION_PERMITS.pdf": "pipeline/RAW/hunt_unit_database/2022/pdf/regulations/2022_REGULATIONS__CONSERVATION_PERMITS.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2023\\pdf\\regulations\\2023_REGULATIONS__9E134C35_2022_24_CONSERVATION_PERMITS.pdf": "pipeline\\RAW\\hunt_unit_database\\2022\\pdf\\regulations\\2022_REGULATIONS__CONSERVATION_PERMITS.pdf",
    "pipeline/RAW/hunt_unit_database/2023/pdf/regulations/2023_REGULATIONS__COUGAR.pdf": "pipeline/RAW/hunt_unit_database/2023/pdf/regulations/2023_REGULATIONS__COUGAR.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2023\\pdf\\regulations\\2023_REGULATIONS__24_COUGAR.pdf": "pipeline\\RAW\\hunt_unit_database\\2023\\pdf\\regulations\\2023_REGULATIONS__COUGAR.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__BEAR.pdf": "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__BEAR.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__BIGGAMEAPP.pdf": "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__BIGGAMEAPP.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__COUGAR.pdf": "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__COUGAR.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__FIELD_REGS.pdf": "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__FIELD_REGS.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__UPLAND_TURKEY.pdf": "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline/RAW/hunt_unit_database/2023/pdf/regulations/2023_REGULATIONS__UPLAND_TURKEY.pdf": "pipeline/RAW/hunt_unit_database/2023/pdf/regulations/2023_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulation\\2024_bear.pdf": "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulations\\2024_REGULATIONS__BEAR.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulation\\2024_biggameapp.pdf": "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulations\\2024_REGULATIONS__BIGGAMEAPP.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulation\\2024_cougar.pdf": "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulations\\2024_REGULATIONS__COUGAR.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulation\\2024_field_regs.pdf": "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulations\\2024_REGULATIONS__FIELD_REGS.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulation\\2024-25_upland_turkey.pdf": "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulations\\2024_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulation\\2023-24_upland_turkey.pdf": "pipeline\\RAW\\hunt_unit_database\\2023\\pdf\\regulations\\2023_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__BEAR_COUGAR.pdf": "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__BEAR_COUGAR.pdf",
    "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__FIELD_REGS.pdf": "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__FIELD_REGS.pdf",
    "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__COUGAR.pdf": "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__COUGAR.pdf",
    "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__BIGGAMEAPP.pdf": "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__BIGGAMEAPP.pdf",
    "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__FIELD_REGS.pdf": "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__FIELD_REGS.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__UPLAND_TURKEY.pdf": "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__UPLAND_TURKEY.pdf": "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulation\\2025 Bear and Cougar.pdf": "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulations\\2025_REGULATIONS__BEAR_COUGAR.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulation\\2025 Big Game.pdf": "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulations\\2025_REGULATIONS__FIELD_REGS.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulation\\2025 Cougar.pdf": "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulations\\2025_REGULATIONS__COUGAR.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulation\\2025_biggameapp.pdf": "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulations\\2025_REGULATIONS__BIGGAMEAPP.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulation\\field_regs 2025.pdf": "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulations\\2025_REGULATIONS__FIELD_REGS.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulation\\2024-25_upland_turkey.pdf": "pipeline\\RAW\\hunt_unit_database\\2024\\pdf\\regulations\\2024_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulation\\2025-26 Upland Game Turkey.pdf": "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulations\\2025_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__UPLAND_TURKEY.pdf": "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__UPLAND_TURKEY.pdf",
    "pipeline\\RAW\\hunt_unit_database\\2026\\pdf\\regulations\\2025-26 Upland Game Turkey.pdf": "pipeline\\RAW\\hunt_unit_database\\2025\\pdf\\regulations\\2025_REGULATIONS__UPLAND_TURKEY.pdf",
}

TITLE_REPLACEMENTS = {
    "2025-26 Upland Game Turkey Guidebook": "2025 Upland Turkey Guidebook",
}

FILENAME_REPLACEMENTS = {
    "2022-23_cougar.pdf": "2022_REGULATIONS__COUGAR.pdf",
    "guidebook_2022-23_cougar.pdf": "2022_REGULATIONS__COUGAR.pdf",
    "2022-23_furbearer.pdf": "2022_REGULATIONS__FURBEARER.pdf",
    "2022-23_upland_turkey.pdf": "2022_REGULATIONS__UPLAND_TURKEY.pdf",
    "2023_REGULATIONS__2022_23_UPLAND_TURKEY.pdf": "2022_REGULATIONS__UPLAND_TURKEY.pdf",
    "2023_REGULATIONS__24_COUGAR.pdf": "2023_REGULATIONS__COUGAR.pdf",
    "2023-24_upland_turkey.pdf": "2023_REGULATIONS__UPLAND_TURKEY.pdf",
    "2024_bear.pdf": "2024_REGULATIONS__BEAR.pdf",
    "2024_biggameapp.pdf": "2024_REGULATIONS__BIGGAMEAPP.pdf",
    "2024_cougar.pdf": "2024_REGULATIONS__COUGAR.pdf",
    "2024_field_regs.pdf": "2024_REGULATIONS__FIELD_REGS.pdf",
    "2024-25_upland_turkey.pdf": "2024_REGULATIONS__UPLAND_TURKEY.pdf",
    "2025 Bear and Cougar.pdf": "2025_REGULATIONS__BEAR_COUGAR.pdf",
    "2025 Big Game.pdf": "2025_REGULATIONS__FIELD_REGS.pdf",
    "2025 Cougar.pdf": "2025_REGULATIONS__COUGAR.pdf",
    "2025_biggameapp.pdf": "2025_REGULATIONS__BIGGAMEAPP.pdf",
    "field_regs 2025.pdf": "2025_REGULATIONS__FIELD_REGS.pdf",
    "2025-26 Upland Game Turkey.pdf": "2025_REGULATIONS__UPLAND_TURKEY.pdf",
    "2022_24_CONSERVATION_PERMITS.pdf": "2022_REGULATIONS__CONSERVATION_PERMITS.pdf",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def active_pipeline_regulation_pdfs() -> list[Path]:
    files = []
    for path in PIPELINE_ROOT.rglob("*.pdf"):
        if "FISHING" in path.name.upper():
            continue
        parts = set(path.parts)
        if parts & SKIP_DIR_NAMES:
            continue
        rel = path.relative_to(PIPELINE_ROOT)
        if len(rel.parts) >= 4 and rel.parts[0].isdigit() and rel.parts[1] == "pdf" and rel.parts[2] == "regulations":
            files.append(path)
    return sorted(files)


def truth_target_for_pipeline(path: Path) -> Path:
    rel = path.relative_to(PIPELINE_ROOT)
    year = int(rel.parts[0])
    target_year = year + 1
    return TRUTH_RAW_ROOT / f"{year}_PERMITS={target_year}_MODEL" / "REGULATIONS" / path.name


def copy_truth_sources() -> list[dict[str, object]]:
    rows = []
    for src in active_pipeline_regulation_pdfs():
        dst = truth_target_for_pipeline(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        src_hash = sha256(src)
        action = "COPY"
        if dst.exists():
            dst_hash = sha256(dst)
            if dst_hash == src_hash:
                action = "UNCHANGED_ALREADY_PRESENT"
            else:
                action = "REVIEW_EXISTING_TARGET_HASH_DIFF"
        if action == "COPY":
            shutil.copy2(src, dst)
            dst_hash = sha256(dst)
        elif dst.exists():
            dst_hash = sha256(dst)
        else:
            dst_hash = ""
        rows.append(
            {
                "source_pipeline_path": str(src.relative_to(REPO)),
                "truth_raw_pdf_path": str(dst.relative_to(REPO)),
                "size_bytes": src.stat().st_size,
                "source_sha256": src_hash,
                "truth_sha256": dst_hash,
                "hash_equal": src_hash == dst_hash,
                "action": action,
            }
        )
    return rows


def should_skip(path: Path) -> bool:
    if path.name == "repair_rules_regs_lineage_and_truth_sources.py":
        return True
    rel_parts = path.relative_to(REPO).parts
    if any(part in SKIP_DIR_NAMES for part in rel_parts):
        return True
    if "backups" in rel_parts or "backup" in rel_parts:
        return True
    return path.suffix.lower() not in TEXT_EXTENSIONS


def repair_text_references() -> list[dict[str, object]]:
    rows = []
    for root in REFERENCE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or should_skip(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                try:
                    text = path.read_text(encoding="utf-8-sig")
                    encoding = "utf-8"
                except UnicodeDecodeError:
                    continue
            original = text
            replacements_applied = []
            for old, new in PATH_REPLACEMENTS.items():
                if old in text:
                    count = text.count(old)
                    text = text.replace(old, new)
                    replacements_applied.append(f"{old}=>{new} ({count})")
            for old, new in TITLE_REPLACEMENTS.items():
                if old in text:
                    count = text.count(old)
                    text = text.replace(old, new)
                    replacements_applied.append(f"{old}=>{new} ({count})")
            for old, new in FILENAME_REPLACEMENTS.items():
                if old not in text:
                    continue
                line_count = 0
                new_lines = []
                for line in text.splitlines(keepends=True):
                    if old in line and "https://wildlife.utah.gov/" not in line:
                        line_count += line.count(old)
                        line = line.replace(old, new)
                    new_lines.append(line)
                if line_count:
                    text = "".join(new_lines)
                    replacements_applied.append(f"{old}=>{new} ({line_count})")
            if text == original:
                continue
            path.write_text(text, encoding=encoding, newline="")
            rows.append(
                {
                    "file_path": str(path.relative_to(REPO)),
                    "replacement_count": len(replacements_applied),
                    "replacements": "; ".join(replacements_applied),
                }
            )
    return rows


def scan_remaining_old_refs() -> list[dict[str, object]]:
    patterns = [
        "2024-25_upland_turkey",
        "2025-26 Upland Game Turkey",
        "2024_bear.pdf",
        "2024_biggameapp.pdf",
        "2024_cougar.pdf",
        "2024_field_regs.pdf",
        "2025 Bear and Cougar.pdf",
        "2025 Big Game.pdf",
        "2025 Cougar.pdf",
        "2025_biggameapp.pdf",
        "field_regs 2025.pdf",
        "2022-23_cougar",
        "2022-23_furbearer",
        "2022-23_upland_turkey",
        "2023-24_upland_turkey",
        "2023_REGULATIONS__2022_23_UPLAND_TURKEY",
        "2023_REGULATIONS__24_COUGAR",
        "2022_24_CONSERVATION_PERMITS",
    ]
    rows = []
    for root in REFERENCE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or should_skip(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern in patterns:
                if pattern not in text:
                    continue
                count = 0
                for line in text.splitlines():
                    if "https://wildlife.utah.gov/" in line:
                        continue
                    count += line.count(pattern)
                if count:
                    rows.append({"file_path": str(path.relative_to(REPO)), "pattern": pattern, "count": count})
    return rows


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = AUDIT_ROOT / f"rules_regs_lineage_truth_source_repair_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    copy_rows = copy_truth_sources()
    repair_rows = repair_text_references()
    remaining_rows = scan_remaining_old_refs()

    write_csv(
        out_dir / "RULES_REGS_TRUTH_SOURCE_COPY_AUDIT.csv",
        copy_rows,
        ["source_pipeline_path", "truth_raw_pdf_path", "size_bytes", "source_sha256", "truth_sha256", "hash_equal", "action"],
    )
    write_csv(
        out_dir / "RULES_REGS_REFERENCE_REPAIR_AUDIT.csv",
        repair_rows,
        ["file_path", "replacement_count", "replacements"],
    )
    write_csv(
        out_dir / "RULES_REGS_REMAINING_OLD_REFERENCE_SCAN.csv",
        remaining_rows,
        ["file_path", "pattern", "count"],
    )

    status = "PASS"
    if any(row["action"] == "REVIEW_EXISTING_TARGET_HASH_DIFF" for row in copy_rows):
        status = "PASS_WITH_REVIEW_REQUIRED"
    if remaining_rows:
        status = "PASS_WITH_REVIEW_REQUIRED"

    summary = {
        "audit_dir": str(out_dir),
        "pipeline_regulation_sources_checked": len(copy_rows),
        "truth_source_copied": sum(1 for row in copy_rows if row["action"] == "COPY"),
        "truth_source_already_present": sum(1 for row in copy_rows if row["action"] == "UNCHANGED_ALREADY_PRESENT"),
        "truth_source_hash_diff_review": sum(1 for row in copy_rows if row["action"] == "REVIEW_EXISTING_TARGET_HASH_DIFF"),
        "files_with_references_updated": len(repair_rows),
        "remaining_old_reference_rows": len(remaining_rows),
        "status": status,
    }
    write_csv(out_dir / "RULES_REGS_LINEAGE_TRUTH_SOURCE_REPAIR_SUMMARY.csv", [{"metric": k, "value": v} for k, v in summary.items()], ["metric", "value"])

    report = [
        "# Rules / Regulations Lineage and Truth Source Repair",
        "",
        f"AUDIT_TIMESTAMP={stamp}",
        "TRUTH_SOURCE_ROOT=data_truth/draw_results_truth/raw_pdfs",
        "SOURCE_OF_TRUTH=normalized pipeline regulation PDFs",
        "PUBLISHED_YEAR_RULE=For split-year guidebooks, use the first listed year as the published/source year across all years.",
        "FILE_NAMING_RULE=YYYY_REGULATIONS__NAME.pdf; no split-year convention in active filenames.",
        "PDF_BYTES_CHANGED=FALSE",
        "",
        f"PIPELINE_REGULATION_SOURCES_CHECKED={summary['pipeline_regulation_sources_checked']}",
        f"TRUTH_SOURCE_COPIED={summary['truth_source_copied']}",
        f"TRUTH_SOURCE_ALREADY_PRESENT={summary['truth_source_already_present']}",
        f"TRUTH_SOURCE_HASH_DIFF_REVIEW={summary['truth_source_hash_diff_review']}",
        f"FILES_WITH_REFERENCES_UPDATED={summary['files_with_references_updated']}",
        f"REMAINING_OLD_REFERENCE_ROWS={summary['remaining_old_reference_rows']}",
        f"RULES_REGS_LINEAGE_TRUTH_SOURCE_REPAIR_STATUS={status}",
    ]
    (out_dir / "RULES_REGS_LINEAGE_TRUTH_SOURCE_REPAIR_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    for key, value in summary.items():
        print(f"{key.upper()}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
