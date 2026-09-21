#!/usr/bin/env python3
"""Apply and prove the reviewed 2023 Bear name-only canonical repair."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = (
    ROOT
    / "data_truth/draw_results_truth/normalized/canonical_yearly"
    / "draw_results_2023_for_2024_canonical_yearly_draw_results.csv"
)
LONG = ROOT / "data_truth/draw_results_truth/normalized/draw_results_long.csv"
SOURCE_PDF = (
    ROOT
    / "pipeline/RAW/hunt_unit_database/2023/pdf/draw_odds/official_dwr_archive/black_bear"
    / "23_drawing_odds.pdf"
)
SOURCE_PDF_SHA256 = "9726e78747de7634cb3d4038c3daf3665e142285ef7ecbdd342d0ac929cb0de3"
PROOF = ROOT / "audits/bear_2023_name_repair_276_cell_proof.json"

OFFICIAL_NAMES = {
    "BR7000": ("1 in 19.0", "Beaver - Any Legal Weapon", 14),
    "BR7001": ("1 in 9.0", "Book Cliffs, Bitter Creek/south - Any Legal Weapon", 15),
    "BR7005": ("N/A", "Central Mtns, Nebo - Any Legal Weapon", 18),
    "BR7007": ("N/A", "Fillmore, Pahvant - Any Legal Weapon", 19),
    "BR7010": ("N/A", "Panguitch Lake/zion - Any Legal Weapon", 22),
    "BR7015": ("1 in 9.0", "South Slope, Bonanza/diamond Mtn/vernal - Any Legal Weapon", 27),
}
NAME_COLUMNS = ("hunt_name", "raw_hunt_name")
REQUESTED_PROTECTED_COLUMNS = (
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "points",
    "residency",
    "source_year",
    "actual_draw_year",
    "pdf_page",
    "source_file",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_check() -> None:
    actual = sha256(SOURCE_PDF)
    if actual != SOURCE_PDF_SHA256:
        raise ValueError(f"Official source PDF hash changed: {actual}")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def field_digest(rows: list[dict[str, str]], field: str) -> str:
    digest = hashlib.sha256()
    for row in rows:
        value = row.get(field, "").encode("utf-8")
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    return digest.hexdigest()


def repair() -> dict[str, object]:
    source_check()
    payload = CANONICAL.read_bytes()
    lines = payload.splitlines(keepends=True)
    header = next(csv.reader([lines[0].decode("utf-8-sig")]))
    if any(column not in header for column in NAME_COLUMNS):
        raise ValueError(f"Missing required name columns: {NAME_COLUMNS}")

    _, rows = read_csv(CANONICAL)
    if len(lines) != len(rows) + 1:
        raise ValueError("Canonical has multiline records; refusing a non-byte-local repair")

    counts: Counter[str] = Counter()
    changed_rows: list[dict[str, object]] = []
    rebuilt = [lines[0]]
    for line_number, (row, raw) in enumerate(zip(rows, lines[1:]), start=2):
        values = next(csv.reader([raw.decode("utf-8")]))
        if dict(zip(header, values)) != row:
            raise ValueError(f"CSV record ambiguity at line {line_number}")
        code = row.get("hunt_code", "")
        if code not in OFFICIAL_NAMES:
            rebuilt.append(raw)
            continue

        old_name, new_name, pdf_page = OFFICIAL_NAMES[code]
        if row.get("actual_draw_year") != "2023":
            raise ValueError(f"Unexpected target year at line {line_number}")
        if any(row.get(column) != old_name for column in NAME_COLUMNS):
            raise ValueError(f"Unexpected current Bear name at line {line_number}: {code}")
        for column in NAME_COLUMNS:
            values[header.index(column)] = new_name
        newline = "\r\n" if raw.endswith(b"\r\n") else "\n"
        buffer = io.StringIO(newline="")
        csv.writer(buffer, lineterminator=newline).writerow(values)
        rebuilt.append(buffer.getvalue().encode("utf-8"))
        counts[code] += 1
        changed_rows.append(
            {
                "csv_line": line_number,
                "hunt_code": code,
                "residency": row.get("residency", ""),
                "points": row.get("points", ""),
                "record_type": row.get("record_type", ""),
                "old_hunt_name": old_name,
                "new_hunt_name": new_name,
                "changed_columns": list(NAME_COLUMNS),
                "official_pdf_page": pdf_page,
                "canonical_pdf_page": row.get("pdf_page", ""),
                "source_file": row.get("source_file", ""),
            }
        )

    expected_counts = Counter({code: 23 for code in OFFICIAL_NAMES})
    if counts != expected_counts or len(changed_rows) != 138:
        raise ValueError(f"Expected 138 reviewed rows, found {dict(counts)}")

    with tempfile.NamedTemporaryFile(dir=CANONICAL.parent, delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(b"".join(rebuilt))
    _, repaired_rows = read_csv(temp_path)
    changed_cells = sum(
        before.get(column, "") != after.get(column, "")
        for before, after in zip(rows, repaired_rows)
        for column in header
    )
    if changed_cells != 276:
        temp_path.unlink(missing_ok=True)
        raise ValueError(f"Expected exactly 276 changed cells, found {changed_cells}")
    for before, after in zip(rows, repaired_rows):
        for column in header:
            if column not in NAME_COLUMNS and before.get(column, "") != after.get(column, ""):
                temp_path.unlink(missing_ok=True)
                raise ValueError(f"Protected column changed: {column}")
    temp_path.replace(CANONICAL)
    return {
        "canonical": str(CANONICAL.relative_to(ROOT)).replace("\\", "/"),
        "changed_rows": len(changed_rows),
        "changed_name_cells": changed_cells,
        "changes_by_hunt_code": dict(sorted(counts.items())),
        "row_list": changed_rows,
    }


def compare(before_path: Path, after_path: Path) -> dict[str, object]:
    before_header, before_rows = read_csv(before_path)
    after_header, after_rows = read_csv(after_path)
    if before_header != after_header:
        raise ValueError(f"Header changed for {after_path}")
    if len(before_rows) != len(after_rows):
        raise ValueError(f"Row count changed for {after_path}")

    changed_rows: list[dict[str, object]] = []
    changed_columns: Counter[str] = Counter()
    for line_number, (before, after) in enumerate(zip(before_rows, after_rows), start=2):
        columns = [column for column in before_header if before.get(column, "") != after.get(column, "")]
        if columns:
            changed_columns.update(columns)
            changed_rows.append(
                {
                    "csv_line": line_number,
                    "actual_draw_year": after.get("actual_draw_year", ""),
                    "hunt_code": after.get("hunt_code", ""),
                    "residency": after.get("residency", ""),
                    "points": after.get("points", ""),
                    "record_type": after.get("record_type", ""),
                    "changed_columns": columns,
                    "before": {column: before.get(column, "") for column in columns},
                    "after": {column: after.get(column, "") for column in columns},
                }
            )

    before_hashes = {column: field_digest(before_rows, column) for column in before_header}
    after_hashes = {column: field_digest(after_rows, column) for column in after_header}
    protected = {
        column: {
            "present": column in before_header,
            "before_sha256": before_hashes.get(column, ""),
            "after_sha256": after_hashes.get(column, ""),
            "byte_identical_values": before_hashes.get(column) == after_hashes.get(column),
        }
        for column in REQUESTED_PROTECTED_COLUMNS
    }
    all_non_name_identical = all(
        before_hashes[column] == after_hashes[column]
        for column in before_header
        if column not in NAME_COLUMNS
    )
    return {
        "before_path": str(before_path),
        "after_path": str(after_path.relative_to(ROOT)).replace("\\", "/"),
        "before_file_sha256": sha256(before_path),
        "after_file_sha256": sha256(after_path),
        "rows_before": len(before_rows),
        "rows_after": len(after_rows),
        "columns": len(before_header),
        "header_byte_identical": before_header == after_header,
        "changed_row_count": len(changed_rows),
        "changed_cell_count": sum(changed_columns.values()),
        "changed_columns": dict(sorted(changed_columns.items())),
        "all_non_name_column_value_hashes_identical": all_non_name_identical,
        "requested_protected_column_hashes": protected,
        "all_column_value_hashes": {
            column: {
                "before_sha256": before_hashes[column],
                "after_sha256": after_hashes[column],
                "identical": before_hashes[column] == after_hashes[column],
            }
            for column in before_header
        },
        "changed_rows": changed_rows,
    }


def prove(before_canonical: Path, before_long: Path) -> dict[str, object]:
    source_check()
    canonical = compare(before_canonical, CANONICAL)
    long_file = compare(before_long, LONG)
    for label, result in (("canonical", canonical), ("derived_long", long_file)):
        if result["changed_row_count"] != 138 or result["changed_cell_count"] != 276:
            raise ValueError(f"{label} change count is not 138 rows / 276 cells")
        if result["changed_columns"] != {"hunt_name": 138, "raw_hunt_name": 138}:
            raise ValueError(f"{label} changed unexpected columns: {result['changed_columns']}")
        if not result["all_non_name_column_value_hashes_identical"]:
            raise ValueError(f"{label} changed a protected non-name value")

    payload = {
        "status": "PASS_EXACT_276_CANONICAL_NAME_CELLS_ONLY",
        "official_source_pdf": str(SOURCE_PDF.relative_to(ROOT)).replace("\\", "/"),
        "official_source_pdf_sha256": SOURCE_PDF_SHA256,
        "official_names": {
            code: {"before": old, "after": new, "pdf_page": page}
            for code, (old, new, page) in OFFICIAL_NAMES.items()
        },
        "canonical_repair": canonical,
        "derived_long_rebuild": long_file,
        "interpretation": (
            "The controlled canonical repair changed exactly 276 data cells across 138 rows. "
            "The canonical rebuild mirrored the same 276 name-cell changes into draw_results_long.csv. "
            "No other column value changed."
        ),
    }
    PROOF.parent.mkdir(parents=True, exist_ok=True)
    PROOF.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("repair")
    proof = subparsers.add_parser("prove")
    proof.add_argument("--before-canonical", type=Path, required=True)
    proof.add_argument("--before-long", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = repair() if args.command == "repair" else prove(args.before_canonical, args.before_long)
    summary = {
        key: value
        for key, value in result.items()
        if key not in {"row_list", "canonical_repair", "derived_long_rebuild"}
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
