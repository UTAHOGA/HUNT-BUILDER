from __future__ import annotations

import csv
import hashlib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BIBLE_ROOT = Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES")
PIPELINE_ROOT = ROOT / "pipeline" / "RAW" / "hunt_unit_database"
MANIFEST_OUT = ROOT / "data_truth" / "draw_results_truth" / "raw_inventory" / "bible_truth_year_documents_manifest.csv"
SUMMARY_OUT = ROOT / "data_truth" / "draw_results_truth" / "raw_inventory" / "bible_truth_year_documents_summary.json"

YEARS = [str(year) for year in range(2020, 2027)]
ALLOWED_SUFFIXES = {".pdf", ".csv", ".xlsx", ".json", ".md"}
YEAR_PATTERN = re.compile(r"^(?P<draw_year>20\d{2})_PERMITS=(?P<model_year>20\d{2})_MODEL__(?P<name>.+)$", re.I)


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def family_group(name: str) -> str:
    upper = name.upper()
    if "SPORTSMAN" in upper:
        return "SPORTSMAN"
    if "ANTLERLESS" in upper:
        return "ANTLERLESS"
    if "YOUTH" in upper:
        return "YOUTH"
    if "G.S." in upper or "GENERAL" in upper:
        return "GENERAL_SEASON"
    if "D.H." in upper or "DEDICATED" in upper:
        return "DEDICATED_HUNTER"
    if "BEAR" in upper:
        return "BEAR"
    if "COUGAR" in upper:
        return "COUGAR_HISTORICAL"
    if "TURKEY" in upper:
        return "TURKEY"
    if "O.I.L" in upper or "OIL" in upper or "BISON" in upper or "MOOSE" in upper or "BIGHORN" in upper or "MTN GOAT" in upper:
        return "OIL"
    if "L.E." in upper or "LIMITED" in upper:
        return "LE"
    if "HUNT EXPO" in upper or "EXPO" in upper:
        return "EXPO"
    return "REVIEW_REQUIRED"


def source_role(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "truth_source_pdf"
    if suffix == ".xlsx":
        return "structured_extract_xlsx"
    if suffix == ".csv":
        return "structured_extract_csv"
    if suffix in {".json", ".md"}:
        return "source_control_metadata"
    return "review_required"


def parse_years(year_folder: str, path: Path) -> tuple[str, str, str]:
    stem = path.stem
    match = YEAR_PATTERN.match(stem)
    if match:
        return match.group("draw_year"), match.group("model_year"), clean(match.group("name"))
    return year_folder, str(int(year_folder) + 1), stem


def destination_for(year: str, source: Path) -> Path:
    suffix_name = source.suffix.lower().lstrip(".") or "other"
    if suffix_name == "xlsx":
        suffix_name = "xlsx"
    return PIPELINE_ROOT / year / "bible_truth" / suffix_name / source.name


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for year in YEARS:
        year_dir = BIBLE_ROOT / year
        if not year_dir.exists():
            continue
        for path in year_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            files.append(path)
    return sorted(files, key=lambda p: str(p).lower())


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows: list[dict[str, Any]] = []
    copied = 0
    unchanged = 0

    for source in iter_source_files():
        year = source.relative_to(BIBLE_ROOT).parts[0]
        draw_year, model_year, document_name = parse_years(year, source)
        dest = destination_for(year, source)
        dest.parent.mkdir(parents=True, exist_ok=True)

        source_hash = sha256_file(source)
        prior_hash = sha256_file(dest) if dest.exists() else ""
        if source_hash != prior_hash:
            shutil.copy2(source, dest)
            copied += 1
            copy_status = "COPIED"
        else:
            unchanged += 1
            copy_status = "UNCHANGED"

        rows.append(
            {
                "draw_year": draw_year,
                "model_year": model_year,
                "bible_folder_year": year,
                "document_name": document_name,
                "family_group": family_group(source.name),
                "source_role": source_role(source),
                "source_file": str(source),
                "pipeline_file": str(dest.relative_to(ROOT)),
                "suffix": source.suffix.lower(),
                "size_bytes": source.stat().st_size,
                "sha256": source_hash,
                "copy_status": copy_status,
                "is_truth_source": "true" if source.suffix.lower() == ".pdf" else "false",
                "is_derived": "false" if source.suffix.lower() == ".pdf" else "true",
            }
        )

    fieldnames = [
        "draw_year",
        "model_year",
        "bible_folder_year",
        "document_name",
        "family_group",
        "source_role",
        "source_file",
        "pipeline_file",
        "suffix",
        "size_bytes",
        "sha256",
        "copy_status",
        "is_truth_source",
        "is_derived",
    ]
    write_csv(MANIFEST_OUT, rows, fieldnames)

    import json

    by_year: dict[str, int] = {}
    by_suffix: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for row in rows:
        by_year[row["draw_year"]] = by_year.get(row["draw_year"], 0) + 1
        by_suffix[row["suffix"]] = by_suffix.get(row["suffix"], 0) + 1
        by_family[row["family_group"]] = by_family.get(row["family_group"], 0) + 1
    SUMMARY_OUT.write_text(
        json.dumps(
            {
                "generated_at_utc": timestamp,
                "source_root": str(BIBLE_ROOT),
                "pipeline_root": str(PIPELINE_ROOT),
                "total_files": len(rows),
                "copied": copied,
                "unchanged": unchanged,
                "by_draw_year": dict(sorted(by_year.items())),
                "by_suffix": dict(sorted(by_suffix.items())),
                "by_family_group": dict(sorted(by_family.items())),
                "manifest": str(MANIFEST_OUT.relative_to(ROOT)),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(SUMMARY_OUT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
