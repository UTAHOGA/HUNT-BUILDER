#!/usr/bin/env python3
"""Normalize only canonical species metadata from official hunt-code prefixes.

This is deliberately narrower than a taxonomy or parser rebuild.  It does
not change any official result value, hunt name, source lineage, permit count,
applicant count, point, probability, draw class, or draw design.  Its sole
purpose is to make the normalized ``species`` field agree with the documented
species encoded by the official hunt code, so unit names such as Bear Mountain
and Elk Ridge cannot misclassify the draw record.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:  # support both ``python scripts/file.py`` and package-style test imports
    from scripts.extract_2020_draw_results_from_pdfs import CODE_PREFIX_SPECIES
except ModuleNotFoundError:  # pragma: no cover - exercised by direct script execution
    from extract_2020_draw_results_from_pdfs import CODE_PREFIX_SPECIES


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
AUDIT_DIR = ROOT / "audits" / "dwr_table_shape_canonical_rebuild" / "species_prefix_normalization"
BACKUP_DIR = AUDIT_DIR / "backups"


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())


def expected_species(hunt_code: object) -> str:
    """Return the canonical species defined by a recognized official prefix."""

    return CODE_PREFIX_SPECIES.get(clean(hunt_code).upper()[:2], "")


def canonical_paths() -> list[Path]:
    return sorted(CANONICAL_DIR.glob("draw_results_*_for_*_canonical_yearly_draw_results.csv"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def row_non_species_fingerprint(row: dict[str, str], fieldnames: list[str]) -> str:
    """Fingerprint every source/result field except the intended metadata cell."""

    payload = "\x1f".join(f"{field}={row.get(field, '')}" for field in fieldnames if field != "species")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_path(path: Path, *, write: bool) -> dict[str, object]:
    fieldnames, rows = read_csv(path)
    if "hunt_code" not in fieldnames or "species" not in fieldnames:
        raise ValueError(f"Canonical missing hunt_code/species columns: {path}")

    before_non_species = [row_non_species_fingerprint(row, fieldnames) for row in rows]
    audit_rows: list[dict[str, str]] = []
    for row_number, row in enumerate(rows, start=2):
        expected = expected_species(row.get("hunt_code"))
        observed = clean(row.get("species"))
        if expected and observed != expected:
            audit_rows.append(
                {
                    "canonical_file": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "row_number": str(row_number),
                    "hunt_code": clean(row.get("hunt_code")).upper(),
                    "points": clean(row.get("points")),
                    "record_type": clean(row.get("record_type")),
                    "source_file": clean(row.get("source_file")),
                    "pdf_page": clean(row.get("pdf_page")),
                    "old_species": observed,
                    "new_species": expected,
                    "reason": "official_hunt_code_prefix_controls_species_metadata",
                }
            )
            row["species"] = expected

    after_non_species = [row_non_species_fingerprint(row, fieldnames) for row in rows]
    if before_non_species != after_non_species:
        raise AssertionError(f"Unexpected non-species mutation while normalizing {path}")

    backup_path = ""
    after_sha256 = sha256(path)
    if write and audit_rows:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = BACKUP_DIR / f"{path.stem}.before_species_prefix_normalization_{stamp}{path.suffix}"
        shutil.copy2(path, backup)
        write_csv(path, fieldnames, rows)
        backup_path = str(backup.relative_to(ROOT)).replace("\\", "/")
        after_sha256 = sha256(path)

    return {
        "canonical_file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "write": write,
        "rows": len(rows),
        "species_cell_changes": len(audit_rows),
        "changes_by_old_new_species": dict(
            Counter(f"{entry['old_species']} -> {entry['new_species']}" for entry in audit_rows)
        ),
        "before_sha256": sha256(path) if not write or not audit_rows else sha256(Path(backup_path)),
        "after_sha256": after_sha256,
        "backup_path": backup_path,
        "audit_rows": audit_rows,
    }


def write_audit(rows: list[dict[str, str]]) -> str:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / "canonical_species_prefix_normalization_audit.csv"
    fields = [
        "canonical_file", "row_number", "hunt_code", "points", "record_type",
        "source_file", "pdf_page", "old_species", "new_species", "reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return str(path.relative_to(ROOT)).replace("\\", "/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Apply the narrowly audited species metadata corrections.")
    args = parser.parse_args()

    summaries = [normalize_path(path, write=args.write) for path in canonical_paths()]
    audit_rows = [row for summary in summaries for row in summary.pop("audit_rows")]
    audit_path = write_audit(audit_rows)
    summary = {
        "write": args.write,
        "purpose": "Only correct canonical species metadata from official hunt-code prefixes; no result values or source lineage change.",
        "canonical_files": len(summaries),
        "total_species_cell_changes": len(audit_rows),
        "changes_by_year": {
            Path(summary["canonical_file"]).name.split("_")[2]: summary["species_cell_changes"]
            for summary in summaries
        },
        "audit_path": audit_path,
        "summaries": summaries,
    }
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    (AUDIT_DIR / "canonical_species_prefix_normalization_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
