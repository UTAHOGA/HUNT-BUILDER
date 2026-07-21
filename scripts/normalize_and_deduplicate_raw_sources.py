#!/usr/bin/env python3
"""Normalize and deduplicate active raw source PDFs.

The pass inventories active raw CSV/PDF sources, but it only renames or
quarantines PDFs. Existing audit/artifact/quarantine/archive/staging folders are
excluded so generated evidence stays untouched.
"""

from __future__ import annotations

import csv
import hashlib
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path


REPO = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
RAW_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
AUDIT_ROOT = REPO / "audits"

ACTIVE_DOC_DIRS = {"draw_odds", "harvest_report", "regulations", "regulation", "Rules Regs", "csv"}
DOC_TYPE_ALIASES = {
    "regulation": "regulations",
    "Rules Regs": "regulations",
}
SKIP_PARTS = {
    "_archive",
    "_quarantine",
    "_staging",
    "ARTIFACTS",
    "draw_odds_artifacts",
    "draw_odds_ignored",
    "backups",
    "backup",
    "__pycache__",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def safe_token(value: str) -> str:
    text = value.upper()
    text = text.replace("&", " AND ")
    text = text.replace("+", " PLUS ")
    text = text.replace("O.I.L.", "OIL")
    text = text.replace("P.L.E.", "PLE")
    text = text.replace("L.E.", "LE")
    text = text.replace("G.S.", "GS")
    text = text.replace("D.H.", "DH")
    text = text.replace("MTN", "MOUNTAIN")
    text = re.sub(r"[^A-Z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def strip_year_prefix(stem: str, year: int, target: int) -> str:
    text = stem
    patterns = [
        rf"^{year}_PERMITS={target}_MODEL__",
        rf"^{year}_HARVEST_REPORT__",
        rf"^{year}_REGULATIONS__",
        rf"^{year}_CSV__",
        rf"^{year}[_\-\s]*",
        rf"^{str(year)[-2:]}[_\-\s]*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text


def classify_active_file(path: Path) -> tuple[int, str] | None:
    rel = path.relative_to(RAW_ROOT)
    parts = rel.parts
    if not parts or not parts[0].isdigit():
        return None
    if any(part in SKIP_PARTS for part in parts):
        return None
    year = int(parts[0])
    if len(parts) < 3:
        return None
    if parts[1] == "pdf" and len(parts) >= 4:
        doc_type = parts[2]
    elif parts[1] == "csv":
        doc_type = "csv"
    else:
        return None
    if doc_type not in ACTIVE_DOC_DIRS:
        return None
    return year, DOC_TYPE_ALIASES.get(doc_type, doc_type)


def normalized_name(path: Path, year: int, doc_type: str) -> str:
    suffix = path.suffix.lower()
    target = year + 1 if doc_type == "draw_odds" else year
    body = safe_token(strip_year_prefix(path.stem, year, target)) or "SOURCE"
    if doc_type == "draw_odds":
        prefix = f"{year}_PERMITS={year + 1}_MODEL__"
    elif doc_type == "harvest_report":
        prefix = f"{year}_HARVEST_REPORT__"
    elif doc_type == "regulations":
        prefix = f"{year}_REGULATIONS__"
    else:
        return path.name
    return f"{prefix}{body}{suffix}"


def unique_quarantine_path(quarantine_dir: Path, source: Path, digest: str) -> Path:
    candidate = quarantine_dir / f"{digest[:8]}__{source.name}"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = quarantine_dir / f"{digest[:8]}__{source.stem}__dup{n}{source.suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = AUDIT_ROOT / f"raw_source_normalize_dedup_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir = RAW_ROOT / "_quarantine" / "duplicates" / "exact_hash" / stamp
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    active_files = []
    for path in RAW_ROOT.rglob("*"):
        if not path.is_file():
            continue
        classified = classify_active_file(path)
        if classified is None:
            continue
        year, doc_type = classified
        active_files.append(
            {
                "path": path,
                "relative_path": path.relative_to(REPO).as_posix(),
                "year": year,
                "doc_type": doc_type,
                "extension": path.suffix.lower(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )

    before_rows = [
        {k: v for k, v in item.items() if k != "path"}
        for item in sorted(active_files, key=lambda row: row["relative_path"])
    ]

    by_hash: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in active_files:
        if item["extension"] == ".pdf":
            by_hash[str(item["sha256"])].append(item)

    duplicate_rows = []
    duplicate_moves = []
    keep_paths = {item["path"] for item in active_files if item["extension"] != ".pdf"}
    for digest, group in by_hash.items():
        if len(group) == 1:
            keep_paths.add(group[0]["path"])
            continue
        ranked = sorted(
            group,
            key=lambda row: (
                row["year"],
                0 if row["doc_type"] == "draw_odds" else 1,
                0 if Path(str(row["path"])).parent.name == "regulations" else 1,
                0 if re.search(r"_PERMITS=\d{4}_MODEL__", row["path"].name) else 1,
                len(str(row["path"])),
                str(row["path"]),
            ),
        )
        keeper = ranked[0]
        keep_paths.add(keeper["path"])
        for dup in ranked[1:]:
            src: Path = dup["path"]
            dest = unique_quarantine_path(quarantine_dir, src, digest)
            duplicate_rows.append(
                {
                    "sha256": digest,
                    "size_bytes": dup["size_bytes"],
                    "keeper_path": keeper["relative_path"],
                    "duplicate_original_path": dup["relative_path"],
                    "duplicate_quarantine_path": dest.relative_to(REPO).as_posix(),
                    "action": "MOVE_TO_QUARANTINE",
                }
            )
            duplicate_moves.append((src, dest))

    rename_rows = []
    rename_moves = []
    for item in sorted(active_files, key=lambda row: row["relative_path"]):
        path: Path = item["path"]
        if path not in keep_paths:
            continue
        year = int(item["year"])
        doc_type = str(item["doc_type"])
        if item["extension"] != ".pdf":
            rename_rows.append(
                {
                    "original_path": item["relative_path"],
                    "normalized_path": item["relative_path"],
                    "year": year,
                    "doc_type": doc_type,
                    "size_bytes": item["size_bytes"],
                    "sha256": item["sha256"],
                    "action": "UNCHANGED_NON_PDF",
                }
            )
            continue
        new_name = normalized_name(path, year, doc_type)
        if path.name == new_name:
            action = "UNCHANGED"
            dest = path
        else:
            dest = path.with_name(new_name)
            if dest.exists() and sha256(dest) != item["sha256"]:
                action = "REVIEW_NAME_COLLISION"
            elif dest.exists() and sha256(dest) == item["sha256"]:
                action = "DUPLICATE_TARGET_EXISTS_QUARANTINE_SOURCE"
                qdest = unique_quarantine_path(quarantine_dir, path, str(item["sha256"]))
                duplicate_moves.append((path, qdest))
                duplicate_rows.append(
                    {
                        "sha256": item["sha256"],
                        "size_bytes": item["size_bytes"],
                        "keeper_path": dest.relative_to(REPO).as_posix(),
                        "duplicate_original_path": item["relative_path"],
                        "duplicate_quarantine_path": qdest.relative_to(REPO).as_posix(),
                        "action": "MOVE_TO_QUARANTINE_NORMALIZED_TARGET_EXISTS",
                    }
                )
            else:
                action = "RENAME"
                rename_moves.append((path, dest))
        rename_rows.append(
            {
                "original_path": item["relative_path"],
                "normalized_path": dest.relative_to(REPO).as_posix(),
                "year": year,
                "doc_type": doc_type,
                "size_bytes": item["size_bytes"],
                "sha256": item["sha256"],
                "action": action,
            }
        )

    for src, dest in duplicate_moves:
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))

    for src, dest in rename_moves:
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))

    after_files = []
    for path in RAW_ROOT.rglob("*"):
        if not path.is_file():
            continue
        classified = classify_active_file(path)
        if classified is None:
            continue
        year, doc_type = classified
        after_files.append(
            {
                "relative_path": path.relative_to(REPO).as_posix(),
                "year": year,
                "doc_type": doc_type,
                "extension": path.suffix.lower(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "normalized_name_status": "PASS"
                if path.suffix.lower() != ".pdf" or path.name == normalized_name(path, year, doc_type)
                else "REVIEW",
            }
        )

    after_by_hash: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in after_files:
        if item["extension"] == ".pdf":
            after_by_hash[str(item["sha256"])].append(item)
    remaining_dupes = [
        {
            "sha256": digest,
            "size_bytes": group[0]["size_bytes"],
            "active_duplicate_count": len(group),
            "paths": ";".join(str(row["relative_path"]) for row in sorted(group, key=lambda row: str(row["relative_path"]))),
        }
        for digest, group in after_by_hash.items()
        if len(group) > 1
    ]

    size_rows = []
    by_year_doc: dict[tuple[int, str], list[int]] = defaultdict(list)
    for item in after_files:
        by_year_doc[(int(item["year"]), str(item["doc_type"]))].append(int(item["size_bytes"]))
    for (year, doc_type), sizes in sorted(by_year_doc.items()):
        size_rows.append(
            {
                "year": year,
                "doc_type": doc_type,
                "file_count": len(sizes),
                "total_size_bytes": sum(sizes),
                "min_size_bytes": min(sizes),
                "max_size_bytes": max(sizes),
                "avg_size_bytes": round(sum(sizes) / len(sizes), 2),
            }
        )

    write_csv(
        out_dir / "RAW_SOURCE_FILE_INVENTORY_BEFORE.csv",
        before_rows,
        ["relative_path", "year", "doc_type", "extension", "size_bytes", "sha256"],
    )
    write_csv(
        out_dir / "RAW_SOURCE_NORMALIZED_RENAME_AUDIT.csv",
        rename_rows,
        ["original_path", "normalized_path", "year", "doc_type", "size_bytes", "sha256", "action"],
    )
    write_csv(
        out_dir / "RAW_SOURCE_EXACT_DUPLICATE_AUDIT.csv",
        duplicate_rows,
        ["sha256", "size_bytes", "keeper_path", "duplicate_original_path", "duplicate_quarantine_path", "action"],
    )
    write_csv(
        out_dir / "RAW_SOURCE_FILE_INVENTORY_AFTER.csv",
        sorted(after_files, key=lambda row: row["relative_path"]),
        ["relative_path", "year", "doc_type", "extension", "size_bytes", "sha256", "normalized_name_status"],
    )
    write_csv(
        out_dir / "RAW_SOURCE_SIZE_COMPARISON_BY_YEAR_DOC_TYPE.csv",
        size_rows,
        ["year", "doc_type", "file_count", "total_size_bytes", "min_size_bytes", "max_size_bytes", "avg_size_bytes"],
    )
    write_csv(
        out_dir / "RAW_SOURCE_REMAINING_DUPLICATES_AFTER.csv",
        remaining_dupes,
        ["sha256", "size_bytes", "active_duplicate_count", "paths"],
    )

    summary = {
        "active_files_before": len(before_rows),
        "active_files_after": len(after_files),
        "renamed_files": sum(1 for row in rename_rows if row["action"] == "RENAME"),
        "quarantined_exact_duplicates": len(duplicate_moves),
        "remaining_active_duplicate_hash_groups": len(remaining_dupes),
        "remaining_non_normalized_files": sum(1 for row in after_files if row["normalized_name_status"] != "PASS"),
        "audit_dir": str(out_dir),
        "quarantine_dir": str(quarantine_dir),
    }
    write_csv(out_dir / "RAW_SOURCE_NORMALIZE_DEDUP_SUMMARY.csv", [{"metric": k, "value": v} for k, v in summary.items()], ["metric", "value"])

    status = "PASS" if summary["remaining_active_duplicate_hash_groups"] == 0 and summary["remaining_non_normalized_files"] == 0 else "PASS_WITH_REVIEW_REQUIRED"
    report = [
        "# Raw Source Normalize / Deduplicate Report",
        "",
        f"report_timestamp: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Scope: active files under pipeline/RAW/hunt_unit_database/<year>/pdf/{draw_odds,harvest_report,regulations} and <year>/csv.",
        "Excluded: audits, _archive, _quarantine, _staging, draw_odds_artifacts, draw_odds_ignored, ARTIFACTS, and backups.",
        "",
        f"active_files_before: {summary['active_files_before']}",
        f"active_files_after: {summary['active_files_after']}",
        f"renamed_files: {summary['renamed_files']}",
        f"quarantined_exact_duplicates: {summary['quarantined_exact_duplicates']}",
        f"remaining_active_duplicate_hash_groups: {summary['remaining_active_duplicate_hash_groups']}",
        f"remaining_non_normalized_files: {summary['remaining_non_normalized_files']}",
        "",
        "Deduplication rule: exact SHA256 duplicate PDFs only; one canonical active copy preserved; duplicates moved to quarantine.",
        "Naming rule: source-year prefix plus doc-type pattern, uppercase ASCII tokens, underscores, lowercase extension.",
        "",
        f"RAW_SOURCE_NORMALIZE_DEDUP_STATUS={status}",
    ]
    (out_dir / "RAW_SOURCE_NORMALIZE_DEDUP_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    for key, value in summary.items():
        print(f"{key.upper()}={value}")
    print(f"RAW_SOURCE_NORMALIZE_DEDUP_STATUS={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
