from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
HUNT_MASTER = ROOT / "processed_data" / "hunt_master_enriched.csv"
POINT_LADDER = ROOT / "processed_data" / "point_ladder_view.csv"
DRAW_REALITY = ROOT / "processed_data" / "draw_reality_engine.csv"

OUT_CSV = ROOT / "data_truth" / "comparison_outputs" / "validation" / "runtime_reference_surface_coverage_repair_2026.csv"
OUT_JSON = ROOT / "data_truth" / "comparison_outputs" / "validation" / "runtime_reference_surface_coverage_repair_2026_summary.json"
OUT_MD = ROOT / "processed_data" / "runtime_reference_surface_coverage_repair_2026.md"

SURFACES = {
    "hunt_master_enriched": HUNT_MASTER,
    "point_ladder_view": POINT_LADDER,
    "draw_reality_engine": DRAW_REALITY,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append identity-only DATABASE reference rows to missing runtime surfaces."
    )
    parser.add_argument(
        "--code-prefix",
        action="append",
        default=[],
        help="Limit repairs to a hunt-code prefix. Repeat for multiple prefixes; default is all codes.",
    )
    return parser.parse_args()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def clean(value: object) -> str:
    return str(value or "").strip()


def code_set(rows: list[dict[str, str]]) -> set[str]:
    return {clean(row.get("hunt_code")).upper() for row in rows if clean(row.get("hunt_code"))}


def permit_for_residency(row: dict[str, str], year: str, residency: str) -> str:
    if residency == "Resident":
        return clean(row.get(f"permits_{year}_res"))
    if residency == "Nonresident":
        return clean(row.get(f"permits_{year}_nr"))
    return ""


def access_type(row: dict[str, str]) -> str:
    values = " ".join(
        clean(row.get(field))
        for field in ("hunt_type", "hunt_class", "hunt_name")
    ).lower()
    if "cwmu" in values:
        return "CWMU"
    if "private" in values:
        return "Private"
    return "Public"


def allocation_status(row: dict[str, str]) -> str:
    if clean(row.get("permits_2026_total")):
        if clean(row.get("permits_2026_res")) or clean(row.get("permits_2026_nr")):
            return "COMPLETE"
        return "COMPLETE_TOTAL_ONLY"
    if clean(row.get("permits_2025_total")):
        return "HISTORICAL_2025_DATABASE_REFERENCE_ONLY"
    return "DATABASE_REFERENCE_ONLY_NO_QUOTA"


def base_reference_row(fieldnames: list[str], db_row: dict[str, str], surface: str, residency: str) -> dict[str, str]:
    row = {field: "" for field in fieldnames}
    for field in fieldnames:
        if field in db_row:
            row[field] = clean(db_row.get(field))

    row["hunt_code"] = clean(db_row.get("hunt_code")).upper()
    if "residency" in row:
        row["residency"] = residency
    if "points" in row:
        row["points"] = ""
    if "access_type" in row:
        row["access_type"] = access_type(db_row)

    public_2025 = permit_for_residency(db_row, "2025", residency) or clean(db_row.get("permits_2025_total"))
    public_2026 = permit_for_residency(db_row, "2026", residency) or clean(db_row.get("permits_2026_total"))
    if "public_permits_2025" in row:
        row["public_permits_2025"] = public_2025
    if "public_permits_2026" in row:
        row["public_permits_2026"] = public_2026
    if "public_permits_2026_source" in row:
        row["public_permits_2026_source"] = clean(db_row.get("permits_2026_source"))

    if "permit_status" in row and not row["permit_status"]:
        row["permit_status"] = "FULL_SPLIT" if clean(db_row.get("permits_2026_res")) or clean(db_row.get("permits_2026_nr")) else "TOTAL_ONLY" if clean(db_row.get("permits_2026_total")) else "NO_2026_TOTAL"
    if "permit_allocation_type" in row and not row["permit_allocation_type"]:
        row["permit_allocation_type"] = row.get("permit_status", "")
    if "permit_source_authority" in row and not row["permit_source_authority"]:
        row["permit_source_authority"] = "DATABASE.csv reviewed hunt-code reference"
    if "permit_overlay_source" in row and not row["permit_overlay_source"]:
        row["permit_overlay_source"] = "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
    if "data_status" in row:
        row["data_status"] = allocation_status(db_row)
    if "missing_permits" in row:
        row["missing_permits"] = "FALSE" if clean(db_row.get("permits_2026_total")) else "TRUE"
    if "missing_draw_data" in row:
        row["missing_draw_data"] = "TRUE"
    if "missing_projection" in row:
        row["missing_projection"] = "TRUE"

    if surface == "draw_reality_engine":
        row["year"] = "2026" if clean(db_row.get("permits_2026_total")) else "2025"
        row["source_file"] = "DATABASE.csv"
        row["status"] = "DATABASE_REFERENCE_ONLY_NO_DRAW_DETAIL"
        row["total_permits"] = public_2026 or public_2025
        if "truth_source_file" in row:
            row["truth_source_file"] = "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
        if "truth_source_status" in row:
            row["truth_source_status"] = "REFERENCE_ONLY_NO_DRAW_DETAIL"
        if "data_quality_grade" in row:
            row["data_quality_grade"] = "REFERENCE_ONLY"
        if "reason_codes" in row:
            row["reason_codes"] = "database_code_surface_coverage_repair_2026"
    elif surface == "point_ladder_view":
        if "status" in row:
            row["status"] = "REFERENCE ONLY"
        if "trend" in row:
            row["trend"] = "GRAY"
        if "draw_outlook" in row:
            row["draw_outlook"] = "REFERENCE ONLY - NO POINT LADDER DETAIL"
        if "projected_applicants_2026_source" in row:
            row["projected_applicants_2026_source"] = "database_reference_only_no_projection"

    return row


def append_missing_surface_rows(
    surface: str,
    path: Path,
    db_by_code: dict[str, dict[str, str]],
    db_codes: set[str],
) -> list[dict[str, str]]:
    fieldnames, rows = read_rows(path)
    existing = code_set(rows)
    missing = sorted(db_codes - existing)
    additions: list[dict[str, str]] = []
    for code in missing:
        db_row = db_by_code[code]
        for residency in ("Resident", "Nonresident"):
            additions.append(base_reference_row(fieldnames, db_row, surface, residency))
    if additions:
        write_rows(path, fieldnames, rows + additions)
    return [
        {
            "surface": surface,
            "hunt_code": code,
            "rows_added": "2",
            "hunt_name": clean(db_by_code[code].get("hunt_name")),
            "species": clean(db_by_code[code].get("species")),
            "hunt_type": clean(db_by_code[code].get("hunt_type")),
            "weapon": clean(db_by_code[code].get("weapon")),
            "permits_2025_total": clean(db_by_code[code].get("permits_2025_total")),
            "permits_2026_total": clean(db_by_code[code].get("permits_2026_total")),
            "repair_status": "ADDED_DATABASE_REFERENCE_ONLY",
        }
        for code in missing
    ]


def main() -> int:
    args = parse_args()
    requested_prefixes = {clean(prefix).upper() for prefix in args.code_prefix if clean(prefix)}
    _, database_rows = read_rows(DATABASE)
    db_by_code = {
        clean(row.get("hunt_code")).upper(): row
        for row in database_rows
        if clean(row.get("hunt_code"))
        and (
            not requested_prefixes
            or any(clean(row.get("hunt_code")).upper().startswith(prefix) for prefix in requested_prefixes)
        )
    }
    db_codes = set(db_by_code)

    repair_rows: list[dict[str, str]] = []
    for surface, path in SURFACES.items():
        repair_rows.extend(append_missing_surface_rows(surface, path, db_by_code, db_codes))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    repair_fields = [
        "surface",
        "hunt_code",
        "rows_added",
        "hunt_name",
        "species",
        "hunt_type",
        "weapon",
        "permits_2025_total",
        "permits_2026_total",
        "repair_status",
    ]
    write_rows(OUT_CSV, repair_fields, repair_rows)

    post_summary: dict[str, object] = {
        "artifact": "runtime_reference_surface_coverage_repair_2026",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_code_count": len(db_codes),
        "code_prefix_scope": sorted(requested_prefixes) if requested_prefixes else ["ALL"],
        "guardrail": "Only missing runtime reference-surface rows were appended from DATABASE.csv. Existing numeric permit cells were not overwritten.",
        "surfaces": {},
        "total_rows_added": len(repair_rows) * 2 if False else sum(int(row["rows_added"]) for row in repair_rows),
        "unique_codes_repaired": len({row["hunt_code"] for row in repair_rows}),
        "detail_csv": str(OUT_CSV.relative_to(ROOT)).replace("\\", "/"),
    }
    for surface, path in SURFACES.items():
        _, rows = read_rows(path)
        codes = code_set(rows)
        post_summary["surfaces"][surface] = {
            "row_count": len(rows),
            "unique_hunt_code_count": len(codes),
            "database_codes_missing_after_repair": sorted(db_codes - codes),
            "database_codes_missing_after_repair_count": len(db_codes - codes),
        }

    OUT_JSON.write_text(json.dumps(post_summary, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(
        "\n".join(
            [
                "# Runtime Reference Surface Coverage Repair 2026",
                "",
                f"- Database hunt codes: `{post_summary['database_code_count']}`",
                f"- Unique codes repaired: `{post_summary['unique_codes_repaired']}`",
                f"- Reference rows appended: `{post_summary['total_rows_added']}`",
                "",
                "## Surface Coverage After Repair",
                "",
                *[
                    f"- `{surface}`: `{details['unique_hunt_code_count']}` unique codes, `{details['database_codes_missing_after_repair_count']}` DATABASE codes still missing"
                    for surface, details in post_summary["surfaces"].items()
                ],
                "",
                "Existing rows and populated numeric permit cells were not overwritten. Added rows are database-reference rows only.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(post_summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
