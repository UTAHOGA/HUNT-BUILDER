from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


REPO = Path(r"C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER")
TARGET = REPO / "data_truth/draw_results_truth/normalized/draw_results_2025_for_2026_candidate_promotion_file_records.csv"
OUT_DIR = REPO / "audits/truth_document_audit/repair_2025_le_oil_subfamily_metadata"
BACKUP_DIR = OUT_DIR / "backups"


LE_OIL_SOURCE_FILES = {
    "2025_PERMITS=2026_MODEL__L.E. BUCK DEER DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__L.E. BULL ELK DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__L.E. BUCK PRONGHORN DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__O.I.L. BISON DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__O.I.L. BULL MOOSE DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__O.I.L. DESERT BIGHORN SHEEP DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__O.I.L. MTN GOAT DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__O.I.L. ROCKY MTN SHEEP DRAW RESULTS.pdf",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def set_if_present(row: dict[str, str], field: str, value: str) -> None:
    if field in row and value:
        row[field] = value


def classify_subfamily(row: dict[str, str]) -> tuple[str, str, str]:
    raw = clean(row.get("raw_hunt_name") or row.get("hunt_name")).upper()
    species = clean(row.get("species")).upper()
    source_file = clean(row.get("source_file"))
    if source_file not in LE_OIL_SOURCE_FILES:
        return "", "", ""

    if "CWMU" in raw or "C.W.M.U" in raw:
        return "CWMU", "CWMU", "CWMU"
    if "PREMIUM" in raw:
        return "PLE", "PREMIUM_LIMITED_ENTRY", "P.L.E."
    if source_file.startswith("2025_PERMITS=2026_MODEL__O.I.L."):
        return clean(row.get("source_classification")) or "OIL", "OIL", "O.I.L."
    if species == "DEER":
        return "LIMITED_ENTRY_DEER", "LIMITED_ENTRY_DEER", "L.E."
    if species == "ELK":
        return "LIMITED_ENTRY_ELK", "LIMITED_ENTRY_ELK", "L.E."
    if species == "PRONGHORN":
        return "LIMITED_ENTRY_PRONGHORN", "LIMITED_ENTRY_PRONGHORN", "L.E."
    return "", "", ""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields, rows = read_rows(TARGET)
    before_rows = len(rows)
    before_counts = Counter(clean(row.get("normalized_family")) or "<blank>" for row in rows)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{TARGET.name}.backup_before_2025_le_oil_subfamily_metadata_{stamp}.csv"
    shutil.copy2(TARGET, backup_path)

    mutations: list[dict[str, object]] = []
    changed_rows = 0
    for index, row in enumerate(rows, start=2):
        if clean(row.get("record_kind")) != "POINT_ROW":
            continue
        normalized_family, source_classification, hunt_type = classify_subfamily(row)
        if not normalized_family:
            continue
        before = dict(row)
        set_if_present(row, "normalized_family", normalized_family)
        set_if_present(row, "source_classification", source_classification)
        set_if_present(row, "source_family", source_classification)
        set_if_present(row, "source_class", source_classification)
        set_if_present(row, "hunt_type", hunt_type)
        set_if_present(row, "metadata_status", "LE_OIL_SUBFAMILY_METADATA_REPAIRED_2025")
        set_if_present(row, "normalization_status", "LE_OIL_SUBFAMILY_METADATA_REPAIRED_2025")
        set_if_present(row, "candidate_promotion_reason", f"2025 LE/OIL subfamily metadata repaired from raw hunt title; no numeric fields changed. normalized_family={normalized_family}")
        if row != before:
            changed_rows += 1
            mutations.append(
                {
                    "row_number": index,
                    "hunt_code": row.get("hunt_code", ""),
                    "raw_hunt_name": row.get("raw_hunt_name", ""),
                    "normalized_family_before": before.get("normalized_family", ""),
                    "normalized_family_after": row.get("normalized_family", ""),
                    "source_classification_before": before.get("source_classification", ""),
                    "source_classification_after": row.get("source_classification", ""),
                    "hunt_type_before": before.get("hunt_type", ""),
                    "hunt_type_after": row.get("hunt_type", ""),
                    "numeric_fields_changed": "false",
                }
            )

    write_csv(TARGET, rows, fields)
    after_counts = Counter(clean(row.get("normalized_family")) or "<blank>" for row in rows)
    family_rows = [
        {
            "normalized_family": key,
            "before_rows": before_counts.get(key, 0),
            "after_rows": after_counts.get(key, 0),
            "delta": after_counts.get(key, 0) - before_counts.get(key, 0),
        }
        for key in sorted(set(before_counts) | set(after_counts))
    ]

    write_csv(OUT_DIR / "2025_le_oil_subfamily_metadata_mutation_ledger.csv", mutations, [
        "row_number",
        "hunt_code",
        "raw_hunt_name",
        "normalized_family_before",
        "normalized_family_after",
        "source_classification_before",
        "source_classification_after",
        "hunt_type_before",
        "hunt_type_after",
        "numeric_fields_changed",
    ])
    write_csv(OUT_DIR / "2025_le_oil_subfamily_family_delta.csv", family_rows, ["normalized_family", "before_rows", "after_rows", "delta"])

    status = {
        "generated_at": datetime.now().isoformat(),
        "target": str(TARGET),
        "backup_path": str(backup_path),
        "rows_before": before_rows,
        "rows_after": len(rows),
        "changed_rows": changed_rows,
        "numeric_fields_changed": False,
        "normalized_family_counts_after": dict(sorted(after_counts.items())),
        "status": "PASS_METADATA_REPAIR_ONLY" if len(rows) == before_rows else "REVIEW_REQUIRED",
    }
    (OUT_DIR / "REPAIR_2025_LE_OIL_SUBFAMILY_METADATA_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    (OUT_DIR / "REPAIR_2025_LE_OIL_SUBFAMILY_METADATA_REPORT.md").write_text(
        "\n".join(
            [
                "# 2025 LE/OIL Subfamily Metadata Repair",
                "",
                f"- Rows before/after: {before_rows} / {len(rows)}",
                f"- Changed rows: {changed_rows}",
                "- Numeric applicant/permit/probability fields changed: false",
                f"- Status: `{status['status']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
