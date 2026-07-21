from __future__ import annotations

import csv
import hashlib
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path


REPO = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
TRUTH_RAW_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs"
AUDIT_ROOT = REPO / "audits"


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


def year_from_truth_path(path: Path) -> int:
    try:
        model_folder = path.relative_to(TRUTH_RAW_ROOT).parts[0]
        return int(model_folder.split("_", 1)[0])
    except Exception:
        return 9999


def is_regulation_candidate(path: Path) -> bool:
    rel_parts = path.relative_to(TRUTH_RAW_ROOT).parts
    if "_duplicate_archive" in rel_parts or "_quarantine" in rel_parts:
        return False
    name = path.name.upper()
    return "REGULATIONS" in rel_parts or name.startswith(tuple(f"{year}_REGULATIONS__" for year in range(2000, 2035)))


def keep_rank(path: Path) -> tuple[int, int, int, str]:
    rel_parts = path.relative_to(TRUTH_RAW_ROOT).parts
    return (
        year_from_truth_path(path),
        0 if "REGULATIONS" in rel_parts else 1,
        0 if "_REGULATIONS__" in path.name.upper() else 1,
        str(path),
    )


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = AUDIT_ROOT / f"truth_raw_regulation_source_dedup_{stamp}"
    archive_root = TRUTH_RAW_ROOT / "_duplicate_archive" / f"rules_regs_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_root.mkdir(parents=True, exist_ok=True)

    candidates = [path for path in TRUTH_RAW_ROOT.rglob("*.pdf") if is_regulation_candidate(path)]
    inventory_rows = []
    for path in candidates:
        inventory_rows.append(
            {
                "path": str(path.relative_to(REPO)),
                "year": year_from_truth_path(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "regulation_folder": "REGULATIONS" in path.relative_to(TRUTH_RAW_ROOT).parts,
                "non_draw_truth_source_status": "REVIEW_NON_DRAW_SOURCE" if "FISHING" in path.name.upper() else "OK",
            }
        )

    by_hash: dict[str, list[Path]] = defaultdict(list)
    for path in candidates:
        by_hash[sha256(path)].append(path)

    archive_rows = []
    for digest, group in sorted(by_hash.items()):
        ranked = sorted(group, key=keep_rank)
        keeper = ranked[0]
        for duplicate in ranked[1:]:
            rel = duplicate.relative_to(TRUTH_RAW_ROOT)
            dest = archive_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            archive_rows.append(
                {
                    "reason": "EXACT_DUPLICATE_REGULATION_SOURCE",
                    "sha256": digest,
                    "keeper_path": str(keeper.relative_to(REPO)),
                    "archived_original_path": str(duplicate.relative_to(REPO)),
                    "archive_path": str(dest.relative_to(REPO)),
                    "size_bytes": duplicate.stat().st_size,
                }
            )
            shutil.move(str(duplicate), str(dest))

    for path in list(TRUTH_RAW_ROOT.rglob("*.pdf")):
        if not is_regulation_candidate(path):
            continue
        if "FISHING" not in path.name.upper():
            continue
        dest = archive_root / path.relative_to(TRUTH_RAW_ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        archive_rows.append(
            {
                "reason": "NON_DRAW_TRUTH_SOURCE_FISHING_EXCLUDED",
                "sha256": sha256(path),
                "keeper_path": "",
                "archived_original_path": str(path.relative_to(REPO)),
                "archive_path": str(dest.relative_to(REPO)),
                "size_bytes": path.stat().st_size,
            }
        )
        shutil.move(str(path), str(dest))

    after_candidates = [path for path in TRUTH_RAW_ROOT.rglob("*.pdf") if is_regulation_candidate(path)]
    after_hashes: dict[str, list[Path]] = defaultdict(list)
    for path in after_candidates:
        after_hashes[sha256(path)].append(path)
    remaining_duplicates = [
        {
            "sha256": digest,
            "duplicate_count": len(paths),
            "paths": ";".join(str(path.relative_to(REPO)) for path in sorted(paths)),
        }
        for digest, paths in after_hashes.items()
        if len(paths) > 1
    ]
    remaining_split_names = [
        {
            "path": str(path.relative_to(REPO)),
            "issue": "SPLIT_YEAR_FILENAME",
        }
        for path in after_candidates
        if "-" in path.name.split("_REGULATIONS__", 1)[-1] or "_23_" in path.name or "_24_" in path.name
    ]

    write_csv(
        out_dir / "TRUTH_RAW_REGULATION_SOURCE_INVENTORY_BEFORE.csv",
        inventory_rows,
        ["path", "year", "size_bytes", "sha256", "regulation_folder", "non_draw_truth_source_status"],
    )
    write_csv(
        out_dir / "TRUTH_RAW_REGULATION_SOURCE_ARCHIVE_AUDIT.csv",
        archive_rows,
        ["reason", "sha256", "keeper_path", "archived_original_path", "archive_path", "size_bytes"],
    )
    write_csv(
        out_dir / "TRUTH_RAW_REGULATION_SOURCE_REMAINING_DUPLICATES.csv",
        remaining_duplicates,
        ["sha256", "duplicate_count", "paths"],
    )
    write_csv(
        out_dir / "TRUTH_RAW_REGULATION_SOURCE_REMAINING_SPLIT_NAMES.csv",
        remaining_split_names,
        ["path", "issue"],
    )

    status = "PASS" if not remaining_duplicates and not remaining_split_names else "PASS_WITH_REVIEW_REQUIRED"
    summary = {
        "audit_dir": str(out_dir),
        "truth_raw_root": str(TRUTH_RAW_ROOT),
        "regulation_candidates_before": len(candidates),
        "regulation_candidates_after": len(after_candidates),
        "archived_regulation_sources": len(archive_rows),
        "remaining_duplicate_hash_groups": len(remaining_duplicates),
        "remaining_split_year_names": len(remaining_split_names),
        "status": status,
    }
    write_csv(out_dir / "TRUTH_RAW_REGULATION_SOURCE_DEDUP_SUMMARY.csv", [{"metric": k, "value": v} for k, v in summary.items()], ["metric", "value"])
    report = [
        "# Truth Raw Regulation Source Dedup",
        "",
        f"AUDIT_TIMESTAMP={stamp}",
        f"TRUTH_RAW_ROOT={TRUTH_RAW_ROOT}",
        "PUBLISHED_YEAR_RULE=For split-year guidebooks, use the first listed year as the published/source year across all years.",
        "FILE_NAMING_RULE=YYYY_REGULATIONS__NAME.pdf; no split-year convention in active filenames.",
        "PDF_BYTES_CHANGED=FALSE",
        "",
        f"REGULATION_CANDIDATES_BEFORE={summary['regulation_candidates_before']}",
        f"REGULATION_CANDIDATES_AFTER={summary['regulation_candidates_after']}",
        f"ARCHIVED_REGULATION_SOURCES={summary['archived_regulation_sources']}",
        f"REMAINING_DUPLICATE_HASH_GROUPS={summary['remaining_duplicate_hash_groups']}",
        f"REMAINING_SPLIT_YEAR_NAMES={summary['remaining_split_year_names']}",
        f"TRUTH_RAW_REGULATION_SOURCE_DEDUP_STATUS={status}",
    ]
    (out_dir / "TRUTH_RAW_REGULATION_SOURCE_DEDUP_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    for key, value in summary.items():
        print(f"{key.upper()}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
