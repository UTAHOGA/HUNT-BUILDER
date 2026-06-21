from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path


REPO = Path(r"C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER")
TARGET = REPO / "data_truth/draw_results_truth/normalized/draw_results_2025_for_2026_candidate_promotion_file_records.csv"
OUT_DIR = REPO / "audits/truth_document_audit/repair_2025_year_metadata"
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields, rows = read_rows(TARGET)
    before_rows = len(rows)
    before_blank_year = sum(1 for row in rows if not clean(row.get("year")))
    added_columns = []
    if "actual_draw_year" not in fields:
        fields.append("actual_draw_year")
        added_columns.append("actual_draw_year")
        for row in rows:
            row["actual_draw_year"] = ""
    if "source_report_family" not in fields:
        fields.append("source_report_family")
        added_columns.append("source_report_family")
        for row in rows:
            row["source_report_family"] = ""

    before_blank_actual = sum(1 for row in rows if not clean(row.get("actual_draw_year")))
    before_blank_report_family = sum(1 for row in rows if not clean(row.get("source_report_family")))
    before_wrong_model = sum(1 for row in rows if clean(row.get("model_target_year")) not in {"2026"})

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{TARGET.name}.backup_before_2025_year_metadata_{stamp}.csv"
    shutil.copy2(TARGET, backup_path)

    mutations: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=2):
        before = dict(row)
        if "year" in row and not clean(row.get("year")):
            row["year"] = "2025"
        if "actual_draw_year" in row and not clean(row.get("actual_draw_year")):
            row["actual_draw_year"] = "2025"
        if "source_report_family" in row and not clean(row.get("source_report_family")):
            row["source_report_family"] = clean(row.get("source_classification"))
        if "reported_draw_year" in row and not clean(row.get("reported_draw_year")):
            row["reported_draw_year"] = "2025"
        if "model_target_year" in row and not clean(row.get("model_target_year")):
            row["model_target_year"] = "2026"
        if row != before:
            mutations.append(
                {
                    "row_number": index,
                    "hunt_code": row.get("hunt_code", ""),
                    "record_kind": row.get("record_kind", ""),
                    "year_before": before.get("year", ""),
                    "year_after": row.get("year", ""),
                    "actual_draw_year_before": before.get("actual_draw_year", ""),
                    "actual_draw_year_after": row.get("actual_draw_year", ""),
                    "source_report_family_before": before.get("source_report_family", ""),
                    "source_report_family_after": row.get("source_report_family", ""),
                    "reported_draw_year_before": before.get("reported_draw_year", ""),
                    "reported_draw_year_after": row.get("reported_draw_year", ""),
                    "model_target_year_before": before.get("model_target_year", ""),
                    "model_target_year_after": row.get("model_target_year", ""),
                    "numeric_fields_changed": "false",
                }
            )

    write_csv(TARGET, rows, fields)
    after_blank_year = sum(1 for row in rows if not clean(row.get("year")))
    after_blank_actual = sum(1 for row in rows if not clean(row.get("actual_draw_year")))
    after_blank_report_family = sum(1 for row in rows if not clean(row.get("source_report_family")))
    after_wrong_model = sum(1 for row in rows if clean(row.get("model_target_year")) not in {"2026"})

    write_csv(OUT_DIR / "2025_year_metadata_mutation_ledger.csv", mutations, [
        "row_number",
        "hunt_code",
        "record_kind",
        "year_before",
        "year_after",
        "actual_draw_year_before",
        "actual_draw_year_after",
        "source_report_family_before",
        "source_report_family_after",
        "reported_draw_year_before",
        "reported_draw_year_after",
        "model_target_year_before",
        "model_target_year_after",
        "numeric_fields_changed",
    ])
    status = {
        "generated_at": datetime.now().isoformat(),
        "target": str(TARGET),
        "backup_path": str(backup_path),
        "rows_before": before_rows,
        "rows_after": len(rows),
        "changed_rows": len(mutations),
        "blank_year_before": before_blank_year,
        "blank_year_after": after_blank_year,
        "blank_actual_draw_year_before": before_blank_actual,
        "blank_actual_draw_year_after": after_blank_actual,
        "blank_source_report_family_before": before_blank_report_family,
        "blank_source_report_family_after": after_blank_report_family,
        "added_columns": added_columns,
        "wrong_model_target_year_before": before_wrong_model,
        "wrong_model_target_year_after": after_wrong_model,
        "numeric_fields_changed": False,
        "status": "PASS_METADATA_REPAIR_ONLY" if len(rows) == before_rows and after_blank_year == 0 and after_blank_actual == 0 and after_blank_report_family == 0 and after_wrong_model == 0 else "REVIEW_REQUIRED",
    }
    (OUT_DIR / "REPAIR_2025_YEAR_METADATA_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
