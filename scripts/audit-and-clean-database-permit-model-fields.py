from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
RECON = ROOT / "processed_data" / "audits" / "current_2026_hunt_code_permit_reconciliation.csv"
BACKUP_DIR = ROOT / "processed_data" / "backups"

HEADER_MAP_OUT = ROOT / "processed_data" / "audits" / "database_permit_model_year_header_map.csv"
CLEAN_AUDIT_OUT = ROOT / "processed_data" / "audits" / "database_permit_field_cleanliness_audit.csv"
DISPLAY_EXPORT_OUT = ROOT / "processed_data" / "audits" / "DATABASE_permit_model_year_display_headers.csv"
SUMMARY_OUT = ROOT / "processed_data" / "audits" / "database_permit_model_field_cleanliness_summary.json"
DOC_OUT = ROOT / "docs" / "database_permit_model_year_header_policy.md"


PERMIT_FIELD_GROUPS = [
    {
        "draw_results_year": "2024",
        "model_target_year": "2025",
        "res": "permits_2024_res",
        "nr": "permits_2024_nr",
        "total": "permits_2024_total",
        "source": "permits_2024_source",
    },
    {
        "draw_results_year": "2025",
        "model_target_year": "2026",
        "res": "permits_2025_res",
        "nr": "permits_2025_nr",
        "total": "permits_2025_total",
        "source": "permits_2025_source",
    },
    {
        "draw_results_year": "2026",
        "model_target_year": "2027",
        "res": "permit_allotment_2026_res",
        "nr": "permit_allotment_2026_nr",
        "total": "permit_allotment_2026_total",
        "source": "permit_allotment_2026_source",
    },
]


DISPLAY_HEADERS = {
    "permits_2024_res": "RES_PERMITS_2024=2025_MODEL",
    "permits_2024_nr": "N.R_PERMITS_2024=2025_MODEL",
    "permits_2024_total": "TOTAL_PERMITS_2024=2025_MODEL",
    "permits_2025_res": "RES_PERMITS_2025=2026_MODEL",
    "permits_2025_nr": "N.R_PERMITS_2025=2026_MODEL",
    "permits_2025_total": "TOTAL_PERMITS_2025=2026_MODEL",
    "permit_allotment_2026_res": "RES_PERMITS_2026=2027_MODEL",
    "permit_allotment_2026_nr": "N.R_PERMITS_2026=2027_MODEL",
    "permit_allotment_2026_total": "TOTAL_PERMITS_2026=2027_MODEL",
}

NUMERIC_PERMIT_FIELDS = set(DISPLAY_HEADERS)


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_numeric(value: Any) -> str:
    text = clean(value).replace(",", "")
    if text == "":
        return ""
    try:
        number = float(text)
    except ValueError:
        return clean(value)
    return str(int(number)) if number.is_integer() else str(number)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = [{key: clean(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def build_header_map() -> list[dict[str, str]]:
    rows = []
    for group in PERMIT_FIELD_GROUPS:
        year = group["draw_results_year"]
        model = group["model_target_year"]
        for role in ("res", "nr", "total"):
            canonical = group[role]
            rows.append(
                {
                    "canonical_machine_header": canonical,
                    "display_header": DISPLAY_HEADERS[canonical],
                    "draw_results_year": year,
                    "model_target_year": model,
                    "permit_component": role,
                    "rule": "folder/draw-results year feeds next model year",
                    "notes": "Keep canonical machine header in DATABASE.csv; use display_header for human-facing exports.",
                }
            )
    return rows


def source_column_for(field: str) -> str:
    for group in PERMIT_FIELD_GROUPS:
        if field in {group["res"], group["nr"], group["total"]}:
            return group["source"]
    return ""


def active_reconciliation_by_code() -> dict[str, dict[str, str]]:
    if not RECON.exists():
        return {}
    _, rows = read_csv(RECON)
    return {row.get("hunt_code", "").upper(): row for row in rows if row.get("hunt_code")}


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    fieldnames, rows = read_csv(DATABASE)
    backup_path = BACKUP_DIR / f"DATABASE_before_permit_model_field_clean_20260604T063500Z.csv"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATABASE, backup_path)

    changed_cells = []
    for row in rows:
        code = row.get("hunt_code", "").upper()
        for field in NUMERIC_PERMIT_FIELDS:
            before = row.get(field, "")
            after = normalize_numeric(before)
            if before != after:
                row[field] = after
                changed_cells.append({"hunt_code": code, "field": field, "before": before, "after": after})

    write_csv(DATABASE, fieldnames, rows)

    header_rows = build_header_map()
    write_csv(
        HEADER_MAP_OUT,
        [
            "canonical_machine_header",
            "display_header",
            "draw_results_year",
            "model_target_year",
            "permit_component",
            "rule",
            "notes",
        ],
        header_rows,
    )

    recon_by_code = active_reconciliation_by_code()
    audit_rows: list[dict[str, Any]] = []
    species_missing_counter: dict[str, Counter[str]] = defaultdict(Counter)
    field_summary: dict[str, dict[str, int]] = {}

    for group in PERMIT_FIELD_GROUPS:
        for role in ("res", "nr", "total"):
            field = group[role]
            values = [row.get(field, "") for row in rows]
            field_summary[field] = {
                "populated": sum(value != "" for value in values),
                "blank": sum(value == "" for value in values),
                "zero": sum(value == "0" for value in values),
            }

    for row in rows:
        code = row.get("hunt_code", "").upper()
        species = row.get("species", "")
        hunt_name = row.get("hunt_name", "")
        for group in PERMIT_FIELD_GROUPS:
            res_field = group["res"]
            nr_field = group["nr"]
            total_field = group["total"]
            source_field = group["source"]
            values = {
                "res": row.get(res_field, ""),
                "nr": row.get(nr_field, ""),
                "total": row.get(total_field, ""),
            }
            total_expected = ""
            if values["res"] != "" and values["nr"] != "":
                try:
                    total_expected = str(int(values["res"]) + int(values["nr"]))
                except ValueError:
                    total_expected = ""
            if values["total"] == "":
                status = "BLANK_TOTAL"
                species_missing_counter[group["draw_results_year"]][species or "Unknown"] += 1
            elif total_expected and total_expected != values["total"]:
                status = "TOTAL_DOES_NOT_EQUAL_RES_PLUS_NR"
            elif values["res"] == "" and values["nr"] == "" and values["total"] != "":
                status = "TOTAL_ONLY"
            else:
                status = "CLEAN"

            recon = recon_by_code.get(code, {}) if group["draw_results_year"] == "2026" else {}
            audit_rows.append(
                {
                    "hunt_code": code,
                    "hunt_name": hunt_name,
                    "species": species,
                    "draw_results_year": group["draw_results_year"],
                    "model_target_year": group["model_target_year"],
                    "res_header": res_field,
                    "nr_header": nr_field,
                    "total_header": total_field,
                    "res_display_header": DISPLAY_HEADERS[res_field],
                    "nr_display_header": DISPLAY_HEADERS[nr_field],
                    "total_display_header": DISPLAY_HEADERS[total_field],
                    "res_value": values["res"],
                    "nr_value": values["nr"],
                    "total_value": values["total"],
                    "source_value": row.get(source_field, ""),
                    "status": status,
                    "recommended_2026_res": recon.get("recommended_res", ""),
                    "recommended_2026_nr": recon.get("recommended_nr", ""),
                    "recommended_2026_total": recon.get("recommended_total", ""),
                    "recommended_2026_winner_source": recon.get("winner_source", ""),
                    "recommended_2026_alignment": recon.get("database_alignment", ""),
                }
            )

    display_fieldnames = [
        "hunt_code",
        "boundary_id",
        "hunt_name",
        "sex_type",
        "species",
        "weapon",
        "hunt_type",
        "hunt_class",
        "season",
        "NOTES",
        DISPLAY_HEADERS["permits_2024_res"],
        DISPLAY_HEADERS["permits_2024_nr"],
        DISPLAY_HEADERS["permits_2024_total"],
        DISPLAY_HEADERS["permits_2025_res"],
        DISPLAY_HEADERS["permits_2025_nr"],
        DISPLAY_HEADERS["permits_2025_total"],
        DISPLAY_HEADERS["permit_allotment_2026_res"],
        DISPLAY_HEADERS["permit_allotment_2026_nr"],
        DISPLAY_HEADERS["permit_allotment_2026_total"],
        "permits_2024_source",
        "permits_2025_source",
        "permit_allotment_2026_source",
        "permit_allotment_2026_status",
    ]
    display_rows = []
    for row in rows:
        out = {field: row.get(field, "") for field in display_fieldnames if field in row}
        for canonical, display in DISPLAY_HEADERS.items():
            out[display] = row.get(canonical, "")
        for field in (
            "hunt_code",
            "boundary_id",
            "hunt_name",
            "sex_type",
            "species",
            "weapon",
            "hunt_type",
            "hunt_class",
            "season",
            "NOTES",
            "permits_2024_source",
            "permits_2025_source",
            "permit_allotment_2026_source",
            "permit_allotment_2026_status",
        ):
            out[field] = row.get(field, "")
        display_rows.append(out)
    write_csv(DISPLAY_EXPORT_OUT, display_fieldnames, display_rows)

    audit_fieldnames = [
        "hunt_code",
        "hunt_name",
        "species",
        "draw_results_year",
        "model_target_year",
        "res_header",
        "nr_header",
        "total_header",
        "res_display_header",
        "nr_display_header",
        "total_display_header",
        "res_value",
        "nr_value",
        "total_value",
        "source_value",
        "status",
        "recommended_2026_res",
        "recommended_2026_nr",
        "recommended_2026_total",
        "recommended_2026_winner_source",
        "recommended_2026_alignment",
    ]
    write_csv(CLEAN_AUDIT_OUT, audit_fieldnames, audit_rows)

    duplicate_codes = [
        code for code, count in Counter(row.get("hunt_code", "").upper() for row in rows).items() if code and count > 1
    ]
    status_counts = Counter(row["status"] for row in audit_rows)
    summary = {
        "generated_at_utc": timestamp,
        "database_path": str(DATABASE.relative_to(ROOT)),
        "backup_path": str(backup_path.relative_to(ROOT)),
        "rows": len(rows),
        "columns": len(fieldnames),
        "unique_hunt_codes": len({row.get("hunt_code", "").upper() for row in rows if row.get("hunt_code")}),
        "duplicate_hunt_codes": duplicate_codes,
        "numeric_cells_normalized": len(changed_cells),
        "field_summary": field_summary,
        "permit_row_status_counts": dict(sorted(status_counts.items())),
        "missing_by_draw_year_species": {
            year: dict(counter.most_common()) for year, counter in species_missing_counter.items()
        },
        "decision": "Canonical DATABASE.csv machine headers were preserved; display/model-year headers were generated as an export and mapping to avoid breaking active scripts/runtime.",
    }
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    doc = [
        "# DATABASE Permit Model-Year Header Policy",
        "",
        f"Generated: `{timestamp}`",
        "",
        "## Decision",
        "",
        "The exact model-year labels are now defined, but `DATABASE.csv` keeps machine-safe canonical headers for now. "
        "This avoids breaking active Python and website code that still reads `permits_2025_total` and `permit_allotment_2026_total`.",
        "",
        "Human-facing exports should use the display headers in the map below.",
        "",
        "## Header Map",
        "",
        "| Canonical machine header | Display/model-year header |",
        "|---|---|",
    ]
    for row in header_rows:
        doc.append(f"| `{row['canonical_machine_header']}` | `{row['display_header']}` |")
    doc.extend(
        [
            "",
            "## Database Cleanliness Results",
            "",
            f"- Rows: `{summary['rows']}`",
            f"- Unique hunt codes: `{summary['unique_hunt_codes']}`",
            f"- Duplicate hunt codes: `{len(duplicate_codes)}`",
            f"- Numeric permit cells normalized from decimal-looking values: `{len(changed_cells)}`",
            "",
            "## Field Population",
            "",
            "| Field | Populated | Blank | Zero |",
            "|---|---:|---:|---:|",
        ]
    )
    for field, stats in field_summary.items():
        doc.append(f"| `{field}` | {stats['populated']} | {stats['blank']} | {stats['zero']} |")
    doc.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Header map: `{HEADER_MAP_OUT.relative_to(ROOT)}`",
            f"- Cleanliness audit: `{CLEAN_AUDIT_OUT.relative_to(ROOT)}`",
            f"- Display-header export: `{DISPLAY_EXPORT_OUT.relative_to(ROOT)}`",
            f"- Summary: `{SUMMARY_OUT.relative_to(ROOT)}`",
        ]
    )
    DOC_OUT.write_text("\n".join(doc) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
