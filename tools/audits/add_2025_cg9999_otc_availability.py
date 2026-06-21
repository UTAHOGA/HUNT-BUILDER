from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


REPO = Path(r"C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER")
TARGET = REPO / "data_truth/draw_results_truth/normalized/draw_results_2025_for_2026_candidate_promotion_file_records.csv"
OUT_DIR = REPO / "audits/truth_document_audit/add_2025_cg9999_otc_availability"
BACKUP_DIR = OUT_DIR / "backups"


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
    if field in row:
        row[field] = value


def build_row(fields: list[str]) -> dict[str, str]:
    row = {field: "" for field in fields}
    values = {
        "record_kind": "AVAILABILITY_ONLY",
        "source_dataset": "official_2025_otc_availability_reference",
        "reported_draw_year": "2025",
        "model_target_year": "2026",
        "actual_draw_year": "2025",
        "source_record_id": "2025_OTC_COUGAR::CG9999",
        "candidate_promotion_status": "SOURCE_BACKED_AVAILABILITY_REFERENCE",
        "candidate_promotion_reason": "2025 statewide cougar is open-season OTC/unlimited; not a draw probability point row.",
        "hunt_code": "CG9999",
        "boundary_id": "5107",
        "hunt_code_mapping_status": "SOURCE_BACKED_CURRENT_REFERENCE",
        "boundary_id_mapping_status": "INTERNAL_REFERENCE_COMPOSITE_BOUNDARY_ID",
        "candidate_hunt_code": "CG9999",
        "candidate_boundary_id": "5107",
        "database_hunt_code_status": "CURRENT_REFERENCE",
        "database_boundary_id": "5107",
        "database_hunt_name": "Cougar - Statewide",
        "database_species": "Cougar",
        "database_sex_type": "Either Sex",
        "database_weapon": "Any Legal Weapon",
        "database_hunt_type": "Statewide Permit",
        "hunt_name": "Cougar - Statewide",
        "raw_hunt_name": "Cougar - Statewide",
        "species": "Cougar",
        "sex_type": "Either Sex",
        "hunt_type": "OTC",
        "hunt_class": "Statewide Permit",
        "weapon": "Any Legal Weapon",
        "season": "Open Season",
        "year": "2025",
        "draw_pool": "availability",
        "draw_method": "OTC",
        "residency": "All",
        "points": "",
        "eligible_applicants": "",
        "bonus_permits": "",
        "preference_permits": "",
        "regular_permits": "",
        "total_permits": "unlimited",
        "total_drawn": "",
        "success_ratio": "",
        "p_draw_percent": "",
        "source_file": "Utah DWR Hunt Planner / 2025 cougar open-season OTC availability",
        "source_path": "",
        "source_file_path": "",
        "source_family": "COUGAR_OTC_AVAILABILITY",
        "source_classification": "COUGAR_OTC_AVAILABILITY",
        "source_class": "COUGAR_OTC_AVAILABILITY",
        "source_report_family": "COUGAR_OTC_AVAILABILITY",
        "validation_status": "OK",
        "normalization_status": "SOURCE_BACKED_AVAILABILITY_REFERENCE",
        "metadata_status": "SOURCE_BACKED_AVAILABILITY_REFERENCE",
        "draw_type": "OTC",
        "status": "OK",
        "normalized_family": "COUGAR_OTC",
        "normalized_species_family": "COUGAR",
        "normalized_age_class": "ADULT",
        "normalized_antlerless_family": "",
        "required_metadata_complete": "true",
    }
    for field, value in values.items():
        set_if_present(row, field, value)
    return row


def strict_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        clean(row.get("actual_draw_year") or row.get("reported_draw_year") or row.get("year")),
        clean(row.get("model_target_year")),
        clean(row.get("source_report_family") or row.get("source_classification")),
        clean(row.get("hunt_code")).upper(),
        clean(row.get("residency")),
        clean(row.get("points")),
        clean(row.get("record_kind")),
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields, rows = read_rows(TARGET)
    for column in ("actual_draw_year", "source_report_family"):
        if column not in fields:
            fields.append(column)
            for row in rows:
                row[column] = ""

    before_rows = len(rows)
    before_cg9999 = sum(1 for row in rows if clean(row.get("hunt_code")).upper() == "CG9999")
    to_add: list[dict[str, str]] = []
    if before_cg9999 == 0:
        to_add.append(build_row(fields))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{TARGET.name}.backup_before_2025_cg9999_otc_{stamp}.csv"
    shutil.copy2(TARGET, backup_path)

    final_rows = rows + to_add
    write_csv(TARGET, final_rows, fields)
    write_csv(OUT_DIR / "2025_cg9999_otc_availability_row_added.csv", to_add, fields)

    dupes = [
        {"strict_key": "|".join(key), "count": count}
        for key, count in Counter(strict_key(row) for row in final_rows).items()
        if count > 1
    ]
    write_csv(OUT_DIR / "2025_duplicate_strict_keys_after_cg9999.csv", dupes, ["strict_key", "count"])

    status = {
        "generated_at": datetime.now().isoformat(),
        "target": str(TARGET),
        "backup_path": str(backup_path),
        "rows_before": before_rows,
        "rows_after": len(final_rows),
        "cg9999_before": before_cg9999,
        "cg9999_after": sum(1 for row in final_rows if clean(row.get("hunt_code")).upper() == "CG9999"),
        "added_rows": len(to_add),
        "duplicate_strict_key_groups_after": len(dupes),
        "probability_fields_fabricated": False,
        "applicant_or_drawn_fields_fabricated": False,
        "status": "PASS_CG9999_OTC_AVAILABILITY_ADDED" if before_cg9999 == 0 and len(to_add) == 1 and not dupes else "REVIEW_REQUIRED",
    }
    (OUT_DIR / "ADD_2025_CG9999_OTC_AVAILABILITY_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
