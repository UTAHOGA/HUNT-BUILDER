from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
AUDIT_DIR = ROOT / "audits" / "2026_canonical_reconciliation"
AUDIT_CSV = AUDIT_DIR / "normalize_2026_canonical_remaining_holes_audit.csv"
SUMMARY_JSON = AUDIT_DIR / "normalize_2026_canonical_remaining_holes_summary.json"

EXPECTED_HUNT_TYPES = {
    "Limited Entry",
    "Once-in-a-Lifetime",
    "General Season",
    "Sportsman",
    "CWMU",
    "Conservation",
    "Private Lands Entry",
    "Tribal",
    "Dedicated Hunter",
    "O.T.C.",
}

BEAR_SPECIES_ARTIFACTS = {
    "Bear Spring": {"species": "Black Bear", "season": "Spring"},
    "Bear Summer": {"species": "Black Bear", "season": "Summer"},
    "Bear Fall": {"species": "Black Bear", "season": "Fall"},
    "Bear Multi-season": {"species": "Black Bear", "season": "Multi-season"},
    "Bear Restricted Pursuit": {"species": "Black Bear", "weapon": "Pursuit Only", "season": "Restricted Pursuit"},
    "Bear Spot And Stalk": {"species": "Black Bear", "weapon": "Spot and Stalk"},
}

HUNT_TYPE_NORMALIZATION = {
    "Premium": "Limited Entry",
    "Management": "Limited Entry",
    "Turkey": "Limited Entry",
    "Over-the-Counter": "O.T.C.",
}

SPORTSMAN_SEX_TYPE_BY_CODE = {
    "BI1000": "Either Sex",
    "BR1000": "Either Sex",
    "DB0007": "Buck",
    "DS1000": "Ram",
    "EB1000": "Bull",
    "GO1000": "Either Sex",
    "MB1000": "Bull",
    "PB1000": "Buck",
    "RS0001": "Ram",
    "TK0001": "Bearded",
}


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def unique_database_values() -> dict[str, dict[str, str]]:
    _, db_rows = read_csv(DATABASE)
    values: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"weapon": set(), "season": set()})
    for row in db_rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        for field in ("weapon", "season"):
            value = clean(row.get(field))
            if value:
                values[code][field].add(value)

    unique: dict[str, dict[str, str]] = defaultdict(dict)
    for code, field_values in values.items():
        for field, candidates in field_values.items():
            if len(candidates) == 1:
                unique[code][field] = next(iter(candidates))
    return unique


def choose_code_designs(rows: list[dict[str, str]]) -> dict[str, str]:
    by_code: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        design = clean(row.get("draw_design"))
        if code and design and design != "Unlimited":
            by_code[code][design] += 1
    return {code: counts.most_common(1)[0][0] for code, counts in by_code.items() if counts}


def record_change(
    audit_rows: list[dict[str, str]],
    file_label: str,
    row: dict[str, str],
    field: str,
    old: str,
    new: str,
    reason: str,
) -> None:
    if old == new:
        return
    audit_rows.append(
        {
            "file": file_label,
            "hunt_code": clean(row.get("hunt_code")),
            "record_type": clean(row.get("record_type")),
            "residency": clean(row.get("residency")),
            "points": clean(row.get("points")),
            "field": field,
            "old_value": old,
            "new_value": new,
            "reason": reason,
        }
    )
    row[field] = new


def normalize_rows(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    file_label: str,
    database_unique: dict[str, dict[str, str]],
    code_designs: dict[str, str],
) -> list[dict[str, str]]:
    audit_rows: list[dict[str, str]] = []
    has_actual_year = "actual_draw_year" in fieldnames

    for row in rows:
        if has_actual_year and clean(row.get("actual_draw_year")) != "2026":
            continue

        code = clean(row.get("hunt_code")).upper()
        record_type = clean(row.get("record_type"))
        species = clean(row.get("species"))

        if code.startswith("BR") and species in BEAR_SPECIES_ARTIFACTS:
            fixes = BEAR_SPECIES_ARTIFACTS[species]
            for field, value in fixes.items():
                if field in fieldnames and (field != "season" or not clean(row.get(field))):
                    record_change(
                        audit_rows,
                        file_label,
                        row,
                        field,
                        clean(row.get(field)),
                        value,
                        f"move bear artifact species '{species}' into normalized field",
                    )

        hunt_type = clean(row.get("hunt_type"))
        if hunt_type in HUNT_TYPE_NORMALIZATION:
            record_change(
                audit_rows,
                file_label,
                row,
                "hunt_type",
                hunt_type,
                HUNT_TYPE_NORMALIZATION[hunt_type],
                "normalize hunt_type to established canonical category",
            )

        if record_type == "point_level_draw_result" and clean(row.get("draw_design")) == "Unlimited":
            replacement = code_designs.get(code)
            if replacement:
                record_change(
                    audit_rows,
                    file_label,
                    row,
                    "draw_design",
                    "Unlimited",
                    replacement,
                    "inherit non-Unlimited draw_design from same hunt code point rows",
                )

        if clean(row.get("sex_type")) == "Sportsman":
            replacement = SPORTSMAN_SEX_TYPE_BY_CODE.get(code)
            if replacement:
                record_change(
                    audit_rows,
                    file_label,
                    row,
                    "sex_type",
                    "Sportsman",
                    replacement,
                    "sportsman belongs in hunt_type/draw_design, not sex_type",
                )

        source_values = database_unique.get(code, {})
        for field in ("weapon", "season"):
            if field not in fieldnames:
                continue
            if clean(row.get(field)):
                continue
            value = clean(source_values.get(field))
            if value:
                record_change(
                    audit_rows,
                    file_label,
                    row,
                    field,
                    "",
                    value,
                    "exact hunt_code backfill from DATABASE.csv single unambiguous value",
                )

    return audit_rows


def blank_count(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if not clean(row.get(field)))


def summarize(rows: list[dict[str, str]]) -> dict[str, object]:
    expected_designs = {"Max/Weighted Split", "Preference", "Random", "Capped Permits", "Unlimited", "Organizations"}
    return {
        "rows": len(rows),
        "unique_hunt_codes": len({clean(row.get("hunt_code")) for row in rows if clean(row.get("hunt_code"))}),
        "record_type_counts": dict(Counter(clean(row.get("record_type")) for row in rows)),
        "blank_counts": {
            "hunt_code": blank_count(rows, "hunt_code"),
            "hunt_name": blank_count(rows, "hunt_name"),
            "species": blank_count(rows, "species"),
            "sex_type": blank_count(rows, "sex_type"),
            "hunt_type": blank_count(rows, "hunt_type"),
            "draw_design": blank_count(rows, "draw_design"),
            "boundary_id": blank_count(rows, "boundary_id"),
            "weapon": blank_count(rows, "weapon"),
            "season": blank_count(rows, "season"),
        },
        "unexpected_hunt_type_values": sorted(
            {
                clean(row.get("hunt_type"))
                for row in rows
                if clean(row.get("hunt_type")) and clean(row.get("hunt_type")) not in EXPECTED_HUNT_TYPES
            }
        ),
        "unexpected_draw_design_values": sorted(
            {
                clean(row.get("draw_design"))
                for row in rows
                if clean(row.get("draw_design")) and clean(row.get("draw_design")) not in expected_designs
            }
        ),
        "bear_species_artifact_rows": sum(1 for row in rows if clean(row.get("species")) in BEAR_SPECIES_ARTIFACTS),
        "sportsman_sex_type_rows": sum(1 for row in rows if clean(row.get("sex_type")) == "Sportsman"),
        "point_rows_unlimited_draw_design": sum(
            1
            for row in rows
            if clean(row.get("record_type")) == "point_level_draw_result" and clean(row.get("draw_design")) == "Unlimited"
        ),
        "unsupported_success_applicant_columns_decision": "successful_applicants and unsuccessful_applicants were removed from the 2026 canonical/long schema until a true raw source field is identified",
    }


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    database_unique = unique_database_values()

    canonical_fields, canonical_rows = read_csv(CANONICAL)
    code_designs = choose_code_designs(canonical_rows)
    canonical_audit = normalize_rows(canonical_rows, canonical_fields, "canonical_2026", database_unique, code_designs)
    write_csv(CANONICAL, canonical_fields, canonical_rows)

    long_fields, long_rows = read_csv(LONG)
    long_audit = normalize_rows(long_rows, long_fields, "draw_results_long_2026_slice", database_unique, code_designs)
    write_csv(LONG, long_fields, long_rows)

    audit_rows = canonical_audit + long_audit
    with AUDIT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file",
                "hunt_code",
                "record_type",
                "residency",
                "points",
                "field",
                "old_value",
                "new_value",
                "reason",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(audit_rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_path": str(CANONICAL),
        "long_path": str(LONG),
        "database_path": str(DATABASE),
        "audit_csv": str(AUDIT_CSV),
        "canonical_cell_changes": len(canonical_audit),
        "long_cell_changes": len(long_audit),
        "change_counts_by_field": dict(Counter(row["field"] for row in audit_rows)),
        "change_counts_by_reason": dict(Counter(row["reason"] for row in audit_rows)),
        "post_canonical_summary": summarize(canonical_rows),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
