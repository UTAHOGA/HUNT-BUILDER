"""Create a hash-verified, report-year archive of retained Utah draw sources.

The deep official DWR pull is intentionally an immutable staging capture.  This
tool copies each verified PDF into the durable report-generation-year raw tree
without deleting or overwriting the staging file.  It also catalogs the
separate durable 2026 UtahDraws endpoint snapshot.  The catalog is the small,
versionable lineage record; the raw PDFs and endpoint payloads stay outside
Git under the repository's raw-data policy.

Run with ``--apply`` to perform the non-destructive copies.  Without it, the
tool reports the planned archive and validates the available source files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = ROOT / "pipeline" / "RAW" / "hunt_unit_database"
STAGING_ROOT = (
    PIPELINE_ROOT / "_staging" / "draw_odds_deep_pull_20260826_203722"
)
STAGING_MANIFEST = STAGING_ROOT / "DRAW_ODDS_DEEP_PULL_MANIFEST.csv"
CURRENT_2026_ROOT = (
    PIPELINE_ROOT
    / "2026"
    / "json"
    / "draw_results"
    / "utahdraws_2026_20260826"
)
CURRENT_2026_MANIFEST = CURRENT_2026_ROOT / "DRAW_ODDS_DEEP_PULL_MANIFEST.csv"
CATALOG_DIR = ROOT / "data_truth" / "draw_results_truth" / "raw_inventory"
CATALOG_CSV = CATALOG_DIR / "official_draw_source_retention_2017_2026.csv"
CATALOG_JSON = CATALOG_DIR / "official_draw_source_retention_2017_2026.json"
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"

START_YEAR = 2017
END_YEAR = 2026

CATALOG_FIELDS = [
    "report_year",
    "source_family",
    "source_kind",
    "official_url",
    "official_page",
    "official_title",
    "staging_or_snapshot_path",
    "durable_archive_path",
    "sha256",
    "size_bytes",
    "manifest_sha256_status",
    "durable_sha256_status",
    "archive_action",
    "canonical_pdf_source_labels",
    "canonical_source_linkage",
    "notes",
]


def repo_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def clean(value: object) -> str:
    return str(value or "").strip()


def source_year(row: dict[str, str], source_path: Path) -> int | None:
    """Determine actual report year from the saved path, URL, then title."""
    parts = source_path.parts
    for part in reversed(parts):
        if part.isdigit() and START_YEAR <= int(part) <= END_YEAR:
            return int(part)
    candidates = " ".join(
        clean(row.get(field))
        for field in ("source_url", "link_text", "output_file", "source_page")
    )
    years = [
        int(match)
        for match in re.findall(r"(?<!\d)(20(?:1[7-9]|2[0-6]))(?!\d)", candidates)
    ]
    # A range such as "2019-20" identifies the report-generation year first.
    # The following season is the model/use year and must not move the raw
    # source into the later folder.
    if years:
        return min(years)
    short_years = [
        2000 + int(match)
        for match in re.findall(r"(?<!\d)(1[7-9]|2[0-5])(?!\d)", candidates)
    ]
    return min(short_years) if short_years else None


def canonical_pdf_label_counts() -> dict[int, int]:
    result: dict[int, int] = {}
    for year in range(2018, END_YEAR + 1):
        files = list(CANONICAL_DIR.glob(f"draw_results_{year}_for_*_canonical_yearly_draw_results.csv"))
        if len(files) != 1:
            result[year] = 0
            continue
        labels = {
            clean(row.get("source_file"))
            for row in read_csv(files[0])
            if clean(row.get("source_file")).lower().endswith(".pdf")
        }
        result[year] = len(labels)
    return result


def archive_destination(year: int, category: str, source: Path) -> Path:
    safe_category = re.sub(r"[^a-z0-9_]+", "_", clean(category).lower()) or "other"
    return (
        PIPELINE_ROOT
        / str(year)
        / "pdf"
        / "draw_odds"
        / "official_dwr_archive"
        / safe_category
        / source.name
    )


def legacy_later_year(row: dict[str, str], source_path: Path) -> int | None:
    """Return the original, incorrect later-year range interpretation."""
    candidates = " ".join(
        clean(row.get(field))
        for field in ("source_url", "link_text", "output_file", "source_page")
    )
    years = [
        int(match)
        for match in re.findall(r"(?<!\d)(20(?:1[7-9]|2[0-6]))(?!\d)", candidates)
    ]
    if years:
        return max(years)
    short_years = [
        2000 + int(match)
        for match in re.findall(r"(?<!\d)(1[7-9]|2[0-5])(?!\d)", candidates)
    ]
    return max(short_years) if short_years else None


def copy_verified(source: Path, destination: Path, expected_hash: str, apply: bool) -> tuple[str, str, Path]:
    """Return action, durable hash status, and destination; never replace bytes."""
    if destination.exists():
        destination_hash = sha256(destination)
        if destination_hash == expected_hash:
            return "ALREADY_ARCHIVED", "MATCH", destination
        destination = destination.with_name(
            f"{destination.stem}__sha256-{expected_hash[:12]}{destination.suffix}"
        )
        if destination.exists() and sha256(destination) == expected_hash:
            return "ALREADY_ARCHIVED_HASH_SUFFIX", "MATCH", destination
    if not apply:
        return "PLANNED_COPY", "NOT_WRITTEN", destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return "COPIED", "MATCH" if sha256(destination) == expected_hash else "MISMATCH", destination


def staged_pdf_rows(apply: bool, label_counts: dict[int, int]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for manifest in read_csv(STAGING_MANIFEST):
        if clean(manifest.get("source_kind")) != "official_pdf":
            continue
        if clean(manifest.get("download_status")) != "OK":
            continue
        source_rel = clean(manifest.get("output_file"))
        if not source_rel:
            continue
        source = ROOT / source_rel
        year = source_year(manifest, source)
        if year is None or not START_YEAR <= year <= 2025:
            continue
        expected_hash = clean(manifest.get("sha256"))
        source_hash = sha256(source) if source.exists() else ""
        manifest_status = "MATCH" if source_hash and source_hash == expected_hash else "MISMATCH_OR_MISSING"
        destination = archive_destination(year, clean(manifest.get("category")), source)
        action = "SOURCE_HASH_INVALID"
        durable_status = "NOT_WRITTEN"
        actual_destination = destination
        if manifest_status == "MATCH":
            action, durable_status, actual_destination = copy_verified(
                source, destination, expected_hash, apply
            )
        rows.append(
            {
                "report_year": str(year),
                "source_family": clean(manifest.get("category")),
                "source_kind": "official_dwr_pdf",
                "official_url": clean(manifest.get("source_url")),
                "official_page": clean(manifest.get("source_page")),
                "official_title": clean(manifest.get("link_text")),
                "staging_or_snapshot_path": source_rel.replace("\\", "/"),
                "durable_archive_path": repo_relative(actual_destination),
                "sha256": expected_hash,
                "size_bytes": clean(manifest.get("size_bytes")),
                "manifest_sha256_status": manifest_status,
                "durable_sha256_status": durable_status,
                "archive_action": action,
                "canonical_pdf_source_labels": str(label_counts.get(year, 0)),
                "canonical_source_linkage": "PARENT_SOURCE_AVAILABLE_MAPPING_PENDING",
                "notes": "Original DWR file retained in immutable deep-pull staging; archive copy is report-year organized.",
            }
        )
    return rows


def current_2026_rows(label_counts: dict[int, int]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for manifest in read_csv(CURRENT_2026_MANIFEST):
        if clean(manifest.get("source_kind")) not in {"utahdraws_draw_odds_json", "utahdraws_supplement_json"}:
            continue
        if clean(manifest.get("download_status")) != "OK":
            continue
        source_rel = clean(manifest.get("output_file"))
        if not source_rel:
            continue
        source = ROOT / source_rel
        expected_hash = clean(manifest.get("sha256"))
        actual_hash = sha256(source) if source.exists() else ""
        status = "MATCH" if actual_hash and actual_hash == expected_hash else "MISMATCH_OR_MISSING"
        rows.append(
            {
                "report_year": "2026",
                "source_family": clean(manifest.get("category")),
                "source_kind": clean(manifest.get("source_kind")),
                "official_url": clean(manifest.get("source_url")),
                "official_page": clean(manifest.get("source_page")),
                "official_title": clean(manifest.get("link_text")),
                "staging_or_snapshot_path": source_rel.replace("\\", "/"),
                "durable_archive_path": source_rel.replace("\\", "/"),
                "sha256": expected_hash,
                "size_bytes": clean(manifest.get("size_bytes")),
                "manifest_sha256_status": status,
                "durable_sha256_status": status,
                "archive_action": "ALREADY_DURABLE_2026_ENDPOINT_SNAPSHOT",
                "canonical_pdf_source_labels": str(label_counts.get(2026, 0)),
                "canonical_source_linkage": "ENDPOINT_SOURCE_AVAILABLE_PDF_PARENT_MAPPING_PENDING",
                "notes": "Official UtahDraws endpoint snapshot is already stored in the report-year raw tree.",
            }
        )
    return rows


def remove_misdated_initial_copies() -> int:
    """Remove only verified duplicate archive copies created by the first run.

    This corrects the now-fixed report-range interpretation. It never touches
    a staging source, an existing non-archive document, or a differently
    hashed archive file.
    """
    removed = 0
    for manifest in read_csv(STAGING_MANIFEST):
        if clean(manifest.get("source_kind")) != "official_pdf":
            continue
        if clean(manifest.get("download_status")) != "OK":
            continue
        source_rel = clean(manifest.get("output_file"))
        if not source_rel:
            continue
        source = ROOT / source_rel
        correct_year = source_year(manifest, source)
        wrong_year = legacy_later_year(manifest, source)
        if (
            correct_year is None
            or wrong_year is None
            or correct_year == wrong_year
            or not START_YEAR <= correct_year <= 2025
            or not START_YEAR <= wrong_year <= 2025
        ):
            continue
        expected_hash = clean(manifest.get("sha256"))
        wrong_path = archive_destination(wrong_year, clean(manifest.get("category")), source)
        correct_path = archive_destination(correct_year, clean(manifest.get("category")), source)
        if not wrong_path.exists() or not correct_path.exists():
            continue
        if sha256(wrong_path) != expected_hash or sha256(correct_path) != expected_hash:
            continue
        wrong_path.unlink()
        removed += 1
    return removed


def write_catalog(rows: list[dict[str, str]], apply: bool) -> None:
    if not apply:
        return
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    with CATALOG_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    summary: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "official Utah DWR draw PDFs 2017-2025 plus durable UtahDraws 2026 endpoint snapshot",
        "rows": len(rows),
        "by_report_year": dict(sorted(Counter(row["report_year"] for row in rows).items())),
        "manifest_hash_status": dict(sorted(Counter(row["manifest_sha256_status"] for row in rows).items())),
        "durable_hash_status": dict(sorted(Counter(row["durable_sha256_status"] for row in rows).items())),
        "archive_actions": dict(sorted(Counter(row["archive_action"] for row in rows).items())),
        "catalog_csv": repo_relative(CATALOG_CSV),
        "policy": "No raw source is overwritten. Source PDFs stay outside Git; this catalog records official URLs and SHA-256 values.",
        "remaining_lineage_work": "Map each canonical source label to one or more archived parent PDFs or official 2026 endpoint records.",
    }
    CATALOG_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Copy verified PDFs and write the durable catalog.")
    parser.add_argument(
        "--repair-misdated-copies",
        action="store_true",
        help="Remove only redundant hash-identical archive copies made under an earlier range-year interpretation.",
    )
    args = parser.parse_args()
    if args.repair_misdated_copies and not args.apply:
        raise SystemExit("--repair-misdated-copies requires --apply")
    if not STAGING_MANIFEST.exists():
        raise SystemExit(f"Missing DWR staging manifest: {STAGING_MANIFEST}")
    if not CURRENT_2026_MANIFEST.exists():
        raise SystemExit(f"Missing durable 2026 UtahDraws manifest: {CURRENT_2026_MANIFEST}")
    labels = canonical_pdf_label_counts()
    rows = staged_pdf_rows(args.apply, labels) + current_2026_rows(labels)
    removed_misdated = remove_misdated_initial_copies() if args.repair_misdated_copies else 0
    write_catalog(rows, args.apply)
    print(f"MODE={'APPLY' if args.apply else 'DRY_RUN'}")
    print(f"SOURCE_ROWS={len(rows)}")
    print("BY_YEAR=" + json.dumps(dict(sorted(Counter(row['report_year'] for row in rows).items()))))
    print("MANIFEST_HASH_STATUS=" + json.dumps(dict(sorted(Counter(row['manifest_sha256_status'] for row in rows).items()))))
    print("DURABLE_HASH_STATUS=" + json.dumps(dict(sorted(Counter(row['durable_sha256_status'] for row in rows).items()))))
    print("ARCHIVE_ACTIONS=" + json.dumps(dict(sorted(Counter(row['archive_action'] for row in rows).items()))))
    print(f"REMOVED_MISDATED_DUPLICATE_COPIES={removed_misdated}")
    if args.apply:
        print(f"CATALOG_CSV={CATALOG_CSV}")
        print(f"CATALOG_JSON={CATALOG_JSON}")


if __name__ == "__main__":
    main()
