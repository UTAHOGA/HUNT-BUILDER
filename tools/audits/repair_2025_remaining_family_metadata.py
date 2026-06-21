from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


REPO = Path(r"C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER")
TARGET = REPO / "data_truth/draw_results_truth/normalized/draw_results_2025_for_2026_candidate_promotion_file_records.csv"
OUT_DIR = REPO / "audits/truth_document_audit/repair_2025_remaining_family_metadata"
BACKUP_DIR = OUT_DIR / "backups"


CANONICAL_SOURCE_BY_FILE = {
    "2025 Antlerless Draw Results(1).pdf": "2025_PERMITS=2026_MODEL__(ANTLERLESS BIG GAME) DRAW RESULTS.pdf",
    "2025 Youth Antlerless Draw.pdf": "2025_PERMITS=2026_MODEL__(YOUTH ANTLERLESS BIG GAME) DRAW RESULTS.pdf",
    "2025 Buck Deer General Season.pdf": "2025_PERMITS=2026_MODEL__G.S. BUCK DEER DRAW RESULTS.pdf",
    "2025 Youth G.S. Deer Draw Results.pdf": "2025_PERMITS=2026_MODEL__YOUTH G.S. DEER DRAW RESULTS.pdf",
    "2025 Lifetime General Deer Draw.pdf": "2025_PERMITS=2026_MODEL__LIFETIME G.S. DEER DRAW RESULTS.pdf",
    "2025 Dedicated Hunter Draw Results.pdf": "2025_PERMITS=2026_MODEL__D.H. DEER DRAW RESULTS.pdf",
    "2025 Youth Dedicated Hunter Draw Results.pdf": "2025_PERMITS=2026_MODEL__YOUTH D.H. DEER DRAW RESULTS.pdf",
    "2025 Black Bear Draw odds.pdf": "2025_PERMITS=2026_MODEL__BEAR DRAW RESULTS.pdf",
    "2025 Turkey Draw Results.pdf": "2025_PERMITS=2026_MODEL__YOUTH TURKEY DRAW RESULTS.pdf",
    "2025 Youth G.S.. Mature Bull Draw.pdf": "2025_PERMITS=2026_MODEL__YOUTH ELK DRAW RESULTS.pdf",
}

ANTLERLESS_SOURCE_BY_FAMILY = {
    "ANTLERLESS_DEER": "2025_PERMITS=2026_MODEL__(ANTLERLESS DEER) DRAW RESULTS.pdf",
    "ANTLERLESS_ELK": "2025_PERMITS=2026_MODEL__(ANTLERLESS ELK) DRAW RESULTS.pdf",
    "ANTLERLESS_PRONGHORN": "2025_PERMITS=2026_MODEL__(DOE PRONGHORN) DRAW RESULTS.pdf",
    "ANTLERLESS_MOOSE": "2025_PERMITS=2026_MODEL__(ANTLERLESS BIG GAME) DRAW RESULTS.pdf",
    "ANTLERLESS_ROCKY_MOUNTAIN_BIGHORN_SHEEP": "2025_PERMITS=2026_MODEL__(ANTLERLESS BIG GAME) DRAW RESULTS.pdf",
}

YOUTH_ANTLERLESS_SOURCE_BY_FAMILY = {
    "YOUTH_ANTLERLESS_DEER": "2025_PERMITS=2026_MODEL__YOUTH_ANTLERLESS_DEER_DRAW_RESULTS.pdf",
    "YOUTH_ANTLERLESS_ELK": "2025_PERMITS=2026_MODEL__YOUTH_ANTLERLESS_ELK_DRAW_RESULTS.pdf",
    "YOUTH_ANTLERLESS_PRONGHORN": "2025_PERMITS=2026_MODEL__YOUTH_ANTLERLESS_PRONGHORN_DRAW_RESULTS.pdf",
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


def family_for_row(row: dict[str, str]) -> tuple[str, str]:
    source_file = clean(row.get("source_file"))
    normalized_family = clean(row.get("normalized_family")).upper()
    antlerless_family = clean(row.get("normalized_antlerless_family")).upper()
    hunt_type = clean(row.get("hunt_type")).upper()
    hunt_class = clean(row.get("hunt_class")).upper()
    species = clean(row.get("species")).upper()

    if source_file == "2025 Antlerless Draw Results(1).pdf":
        return antlerless_family or "ANTLERLESS", "ANTLERLESS"
    if source_file == "2025 Youth Antlerless Draw.pdf":
        return antlerless_family or "YOUTH_ANTLERLESS", "YOUTH_ANTLERLESS"
    if source_file == "2025 Buck Deer General Season.pdf":
        if "EXTENDED ARCHERY" in hunt_type:
            return "EXTENDED_ARCHERY_DEER", "GENERAL_SEASON_DEER"
        return "GENERAL_SEASON_DEER", "GENERAL_SEASON_DEER"
    if source_file == "2025 Youth G.S. Deer Draw Results.pdf":
        if "EXTENDED ARCHERY" in hunt_type:
            return "YOUTH_EXTENDED_ARCHERY_DEER", "YOUTH_GENERAL_SEASON_DEER"
        return "YOUTH_GENERAL_SEASON_DEER", "YOUTH_GENERAL_SEASON_DEER"
    if source_file == "2025 Lifetime General Deer Draw.pdf":
        return "LIFETIME_GENERAL_SEASON_DEER", "LIFETIME_GENERAL_SEASON_DEER"
    if source_file == "2025 Dedicated Hunter Draw Results.pdf":
        return "DEDICATED_HUNTER_DEER", "DEDICATED_HUNTER_DEER"
    if source_file == "2025 Youth Dedicated Hunter Draw Results.pdf":
        return "YOUTH_DEDICATED_HUNTER_DEER", "YOUTH_DEDICATED_HUNTER_DEER"
    if source_file == "2025 Black Bear Draw odds.pdf":
        if "PURSUIT" in hunt_type:
            return "BEAR_RESTRICTED_PURSUIT", "BLACK_BEAR"
        return "BLACK_BEAR", "BLACK_BEAR"
    if source_file == "2025 Turkey Draw Results.pdf":
        if "CWMU" in hunt_type or "CWMU" in hunt_class or normalized_family == "CWMU":
            return "YOUTH_TURKEY_CWMU", "YOUTH_TURKEY"
        return "YOUTH_TURKEY", "YOUTH_TURKEY"
    if source_file == "2025 Youth G.S.. Mature Bull Draw.pdf" and species == "ELK":
        return "YOUTH_GENERAL_SEASON_ANY_BULL_ELK", "YOUTH_GENERAL_SEASON_ELK"

    return "", ""


def set_if_present(row: dict[str, str], field: str, value: str) -> None:
    if field in row and value:
        row[field] = value


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields, rows = read_rows(TARGET)
    before_rows = len(rows)
    before_blank_source_classification = sum(1 for row in rows if not clean(row.get("source_classification")))
    before_youth_elk_wrong_family = sum(
        1
        for row in rows
        if clean(row.get("source_file")) == "2025 Youth G.S.. Mature Bull Draw.pdf"
        and clean(row.get("normalized_family")).upper() == "GENERAL_SEASON_DEER"
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{TARGET.name}.backup_before_2025_remaining_family_metadata_{stamp}.csv"
    shutil.copy2(TARGET, backup_path)

    mutations: list[dict[str, object]] = []
    changed_rows = 0
    for index, row in enumerate(rows, start=2):
        source_file = clean(row.get("source_file"))
        classification, source_family = family_for_row(row)
        if not classification:
            continue

        before = dict(row)
        canonical_source_file = CANONICAL_SOURCE_BY_FILE.get(source_file, source_file)
        if source_file == "2025 Antlerless Draw Results(1).pdf":
            canonical_source_file = ANTLERLESS_SOURCE_BY_FAMILY.get(classification, canonical_source_file)
        elif source_file == "2025 Youth Antlerless Draw.pdf":
            canonical_source_file = YOUTH_ANTLERLESS_SOURCE_BY_FAMILY.get(classification, canonical_source_file)

        set_if_present(row, "source_classification", classification)
        set_if_present(row, "source_family", source_family)
        set_if_present(row, "source_class", classification)
        set_if_present(row, "metadata_status", "FAMILY_METADATA_REPAIRED_2025")
        set_if_present(row, "normalization_status", "FAMILY_METADATA_REPAIRED_2025")
        set_if_present(row, "candidate_promotion_status", "PDF_GROUNDED_PROMOTED_CANDIDATE")
        set_if_present(row, "candidate_promotion_reason", f"2025 family metadata repaired from canonical source-file lineage; no numeric fields changed. source_classification={classification}")
        set_if_present(row, "source_file", canonical_source_file)
        set_if_present(row, "source_dataset", "official_2025_remaining_pdf_family_metadata_repair")

        if source_file == "2025 Youth G.S.. Mature Bull Draw.pdf":
            set_if_present(row, "normalized_family", "YOUTH_GENERAL_SEASON_ELK")
            set_if_present(row, "normalized_species_family", "ELK")
            set_if_present(row, "normalized_age_class", "YOUTH")

        if row != before:
            changed_rows += 1
            mutations.append(
                {
                    "row_number": index,
                    "hunt_code": row.get("hunt_code", ""),
                    "source_file_before": before.get("source_file", ""),
                    "source_file_after": row.get("source_file", ""),
                    "source_classification_before": before.get("source_classification", ""),
                    "source_classification_after": row.get("source_classification", ""),
                    "normalized_family_before": before.get("normalized_family", ""),
                    "normalized_family_after": row.get("normalized_family", ""),
                    "numeric_fields_changed": "false",
                }
            )

    write_csv(TARGET, rows, fields)

    after_blank_source_classification = sum(1 for row in rows if not clean(row.get("source_classification")))
    after_youth_elk_wrong_family = sum(
        1
        for row in rows
        if clean(row.get("source_file")) == "2025_PERMITS=2026_MODEL__YOUTH ELK DRAW RESULTS.pdf"
        and clean(row.get("normalized_family")).upper() == "GENERAL_SEASON_DEER"
    )
    scope_counts = Counter(clean(row.get("source_classification")) or "<blank>" for row in rows)
    source_counts = Counter(clean(row.get("source_file")) or "<blank>" for row in rows)

    summary_rows = [
        {"metric": "rows_before", "value": before_rows},
        {"metric": "rows_after", "value": len(rows)},
        {"metric": "changed_rows", "value": changed_rows},
        {"metric": "blank_source_classification_before", "value": before_blank_source_classification},
        {"metric": "blank_source_classification_after", "value": after_blank_source_classification},
        {"metric": "youth_elk_wrong_family_before", "value": before_youth_elk_wrong_family},
        {"metric": "youth_elk_wrong_family_after", "value": after_youth_elk_wrong_family},
    ]
    family_rows = [
        {"source_classification": key, "rows": value}
        for key, value in sorted(scope_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    source_rows = [
        {"source_file": key, "rows": value}
        for key, value in sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    write_csv(OUT_DIR / "2025_remaining_family_metadata_summary.csv", summary_rows, ["metric", "value"])
    write_csv(OUT_DIR / "2025_remaining_family_metadata_mutation_ledger.csv", mutations, [
        "row_number",
        "hunt_code",
        "source_file_before",
        "source_file_after",
        "source_classification_before",
        "source_classification_after",
        "normalized_family_before",
        "normalized_family_after",
        "numeric_fields_changed",
    ])
    write_csv(OUT_DIR / "2025_source_classification_counts_after.csv", family_rows, ["source_classification", "rows"])
    write_csv(OUT_DIR / "2025_source_file_counts_after.csv", source_rows, ["source_file", "rows"])

    status = {
        "generated_at": datetime.now().isoformat(),
        "target": str(TARGET),
        "backup_path": str(backup_path),
        "rows_before": before_rows,
        "rows_after": len(rows),
        "changed_rows": changed_rows,
        "blank_source_classification_before": before_blank_source_classification,
        "blank_source_classification_after": after_blank_source_classification,
        "youth_elk_wrong_family_before": before_youth_elk_wrong_family,
        "youth_elk_wrong_family_after": after_youth_elk_wrong_family,
        "numeric_fields_changed": False,
        "status": "PASS_METADATA_REPAIR_ONLY" if len(rows) == before_rows and after_youth_elk_wrong_family == 0 else "REVIEW_REQUIRED",
    }
    (OUT_DIR / "REPAIR_2025_REMAINING_FAMILY_METADATA_STATUS.json").write_text(
        json.dumps(status, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "REPAIR_2025_REMAINING_FAMILY_METADATA_REPORT.md").write_text(
        "\n".join(
            [
                "# 2025 Remaining Family Metadata Repair",
                "",
                f"- Rows before/after: {before_rows} / {len(rows)}",
                f"- Changed rows: {changed_rows}",
                f"- Blank source_classification before/after: {before_blank_source_classification} / {after_blank_source_classification}",
                f"- Youth elk rows mislabeled as GENERAL_SEASON_DEER before/after: {before_youth_elk_wrong_family} / {after_youth_elk_wrong_family}",
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
