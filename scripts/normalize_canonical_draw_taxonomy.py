#!/usr/bin/env python3
"""Normalize legacy hunt_type and draw_design labels in yearly canonical files."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
AUDIT_DIR = ROOT / "audits" / "dwr_table_shape_canonical_rebuild" / "taxonomy_normalization"
BACKUP_DIR = AUDIT_DIR / "backups"

YEARS = list(range(2019, 2027))

HUNT_TYPE_MAP = {
    "Antlerless": "Limited Entry",
    "G.S.": "General Season",
    "Management Buck Deer": "Limited Entry",
    "Once-in-a-lifetime": "Once-in-a-Lifetime",
    "Premium": "Premium Limited Entry",
    "Restricted Pursuit - Late Summer": "O.T.C.",
    "Restricted Pursuit - Spring": "O.T.C.",
    "Restricted Pursuit - Summer": "O.T.C.",
    "Spot and Stalk": "O.T.C.",
    "Turkey": "Limited Entry",
    "Youth Antlerless": "Limited Entry",
}

DRAW_DESIGN_MAP = {
    "2019 Draw 5, Big Game Bonus Point Draw Results": "Max/Weighted Split",
    "Antlerless": "Preference",
    "Dedicated Hunter": "Preference",
    "Dedicated Hunter Youth": "Preference",
    "General Season Deer": "Preference",
    "Lifetime Permit Holder": "Preference",
    "Limited Entry Cougar": "Preference",
    "Limited Entry Turkey": "Preference",
    "Sportsman": "Random",
    "Youth Antlerless": "Preference",
    "Youth Deer": "Preference",
    "Youth General Any Bull Elk": "Random",
    "Youth Turkey": "Preference",
}

OIL_PREFIXES = {"BI", "DS", "GO", "MB", "RS"}

PREFIX_SPECIES = {
    "BI": "Bison",
    "BR": "Black Bear",
    "CG": "Cougar",
    "DA": "Deer",
    "DB": "Deer",
    "DS": "Desert Bighorn Sheep",
    "EA": "Elk",
    "EB": "Elk",
    "GO": "Mountain Goat",
    "MA": "Moose",
    "MB": "Moose",
    "PB": "Pronghorn",
    "PD": "Pronghorn",
    "RE": "Rocky Mountain Sheep",
    "RS": "Rocky Mountain Sheep",
    "TK": "Turkey",
}

PREFIX_SEX_TYPE = {
    "BR": "Either Sex",
    "CG": "Either Sex",
    "DA": "Antlerless",
    "DB": "Buck",
    "DS": "Ram",
    "EA": "Antlerless",
    "EB": "Bull",
    "GO": "Either Sex",
    "MA": "Antlerless",
    "MB": "Bull",
    "PB": "Buck",
    "PD": "Doe",
    "RE": "Ewe",
    "RS": "Ram",
    "TK": "Bearded",
}

SEX_BY_SOURCE_TOKEN = [
    ("G.S. BUCK DEER", "Buck"),
    ("GS BUCK DEER", "Buck"),
    ("D.H. DEER", "Buck"),
    ("DH DEER", "Buck"),
    ("LIFETIME G.S. DEER", "Buck"),
    ("LIFETIME GS DEER", "Buck"),
    ("BULL ELK", "Bull"),
    ("BUCK PRONGHORN", "Buck"),
    ("BISON", "Either Sex"),
    ("BULL MOOSE", "Bull"),
    ("DESERT BIGHORN", "Ram"),
    ("ROCKY MTN SHEEP", "Ram"),
    ("ROCKY MOUNTAIN SHEEP", "Ram"),
    ("MTN GOAT", "Either Sex"),
    ("MOUNTAIN GOAT", "Either Sex"),
    ("BLACK BEAR", "Either Sex"),
    ("BEAR", "Either Sex"),
    ("COUGAR", "Either Sex"),
    ("TURKEY", "Bearded"),
]


def canonical_path(year: int) -> Path:
    return CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(path)


def source_text(row: dict[str, str]) -> str:
    return " ".join(
        [
            clean(row.get("source_file")),
            clean(row.get("source_scope")),
            clean(row.get("source_namespace")),
            clean(row.get("draw_source_namespace")),
        ]
    ).upper()


def prefix(row: dict[str, str]) -> str:
    return clean(row.get("hunt_code")).upper()[:2]


def infer_hunt_type(row: dict[str, str]) -> str:
    text = source_text(row)
    code_prefix = prefix(row)
    if "SPORTSMAN" in text:
        return "Sportsman"
    if "D.H. DEER" in text or "DH DEER" in text:
        return "Dedicated Hunter"
    if "G.S. BUCK DEER" in text or "G.S. DEER" in text or "GS BUCK DEER" in text or "LIFETIME G.S. DEER" in text:
        return "General Season"
    if "ANTLERLESS" in text:
        return "Limited Entry"
    if "TURKEY" in text:
        return "Limited Entry"
    if "COUGAR" in text:
        return "Limited Entry"
    if "BLACK BEAR" in text or "BEAR" in text:
        name_weapon = f"{clean(row.get('hunt_name'))} {clean(row.get('weapon'))}".lower()
        if "pursuit" in name_weapon or "spot and stalk" in name_weapon:
            return "O.T.C."
        return "Limited Entry"
    if "BIG GAME" in text or text.endswith("BG-ODDS.PDF") or "BG-ODDS" in text or "L.E." in text or "LIMITED" in text:
        return "Once-in-a-Lifetime" if code_prefix in OIL_PREFIXES else "Limited Entry"
    if "YOUTH ELK" in text or "YOUTH BULL ELK" in text:
        return "Limited Entry"
    return ""


def infer_draw_design(row: dict[str, str], normalized_hunt_type: str) -> str:
    text = source_text(row)
    if "SPORTSMAN" in text or normalized_hunt_type == "Sportsman":
        return "Random"
    if normalized_hunt_type == "O.T.C.":
        return "Capped Permits"
    if "YOUTH ELK" in text or "YOUTH BULL ELK" in text:
        return "Random"
    if normalized_hunt_type in {"General Season", "Dedicated Hunter"}:
        return "Preference"
    if "ANTLERLESS" in text:
        return "Preference"
    if "TURKEY" in text:
        return "Preference"
    if "BLACK BEAR" in text or "BEAR" in text:
        return "Preference"
    if "COUGAR" in text:
        return "Preference"
    if normalized_hunt_type in {"Limited Entry", "Once-in-a-Lifetime", "Premium Limited Entry", "CWMU"}:
        return "Max/Weighted Split"
    return ""


def infer_sex_type(row: dict[str, str]) -> str:
    text = source_text(row)
    code_prefix = prefix(row)
    hunt_name = clean(row.get("hunt_name")).lower()
    if code_prefix == "BI":
        if "cow" in hunt_name:
            return "Cow Only"
        if "hunter" in hunt_name or "choice" in hunt_name:
            return "Hunters Choice"
        return "Either Sex"
    for token, sex_type in SEX_BY_SOURCE_TOKEN:
        if token in text:
            return sex_type
    return PREFIX_SEX_TYPE.get(code_prefix, "")


def infer_species(row: dict[str, str]) -> str:
    return PREFIX_SPECIES.get(prefix(row), "")


def record_change(
    audit_rows: list[dict[str, str]],
    year: int,
    row_number: int,
    row: dict[str, str],
    field: str,
    new_value: str,
    reason: str,
) -> None:
    old_value = clean(row.get(field))
    if not new_value or old_value == new_value:
        return
    audit_rows.append(
        {
            "year": str(year),
            "row_number": str(row_number),
            "hunt_code": clean(row.get("hunt_code")),
            "points": clean(row.get("points")),
            "record_type": clean(row.get("record_type")),
            "source_file": clean(row.get("source_file")),
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
        }
    )
    row[field] = new_value


def normalize_year(year: int, *, write: bool) -> dict[str, object]:
    path = canonical_path(year)
    fieldnames, rows = read_csv(path)
    audit_rows: list[dict[str, str]] = []

    for row_number, row in enumerate(rows, start=2):
        if "hunt_type" in fieldnames:
            hunt_type = clean(row.get("hunt_type"))
            mapped = HUNT_TYPE_MAP.get(hunt_type)
            if mapped:
                record_change(audit_rows, year, row_number, row, "hunt_type", mapped, "normalize legacy hunt_type label")
            elif not hunt_type:
                inferred = infer_hunt_type(row)
                if inferred:
                    record_change(audit_rows, year, row_number, row, "hunt_type", inferred, "fill blank hunt_type from source file family")

        normalized_hunt_type = clean(row.get("hunt_type"))
        if "draw_design" in fieldnames:
            draw_design = clean(row.get("draw_design"))
            draw_system_type = clean(row.get("draw_system_type"))
            if draw_system_type and draw_design != draw_system_type:
                record_change(audit_rows, year, row_number, row, "draw_design", draw_system_type, "sync draw_design to draw_system_type")
            elif draw_design in DRAW_DESIGN_MAP and "draw_system_type" not in fieldnames:
                mapped = DRAW_DESIGN_MAP[draw_design]
                record_change(audit_rows, year, row_number, row, "draw_design", mapped, "normalize legacy draw_design label")
            elif draw_design == "Black Bear":
                inferred = "OTC_CAPPED" if normalized_hunt_type == "O.T.C." else "BLACK_BEAR"
                record_change(audit_rows, year, row_number, row, "draw_design", inferred, "normalize bear draw_design label")
            elif not draw_design:
                inferred = infer_draw_design(row, normalized_hunt_type)
                if inferred:
                    record_change(audit_rows, year, row_number, row, "draw_design", inferred, "fill blank draw_design from source file family")

        if "sex_type" in fieldnames and not clean(row.get("sex_type")):
            inferred = infer_sex_type(row)
            if inferred:
                record_change(audit_rows, year, row_number, row, "sex_type", inferred, "fill blank sex_type from source file family")

        if "species" in fieldnames and not clean(row.get("species")):
            inferred = infer_species(row)
            if inferred:
                record_change(audit_rows, year, row_number, row, "species", inferred, "fill blank species from hunt-code prefix")

    if write and audit_rows:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = BACKUP_DIR / f"{path.stem}.before_taxonomy_normalization_{stamp}{path.suffix}"
        shutil.copy2(path, backup)
        write_csv(path, fieldnames, rows)
    else:
        backup = None

    return {
        "year": year,
        "write": write,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "backup_path": str(backup.relative_to(ROOT)).replace("\\", "/") if backup else "",
        "rows": len(rows),
        "cell_changes": len(audit_rows),
        "changes_by_field": dict(Counter(row["field"] for row in audit_rows)),
        "audit_rows": audit_rows,
    }


def write_audit(rows: list[dict[str, str]]) -> str:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / "taxonomy_normalization_audit.csv"
    fieldnames = [
        "year",
        "row_number",
        "hunt_code",
        "points",
        "record_type",
        "source_file",
        "field",
        "old_value",
        "new_value",
        "reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return str(path.relative_to(ROOT)).replace("\\", "/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summaries = [normalize_year(year, write=args.write) for year in YEARS]
    audit_rows = [row for summary in summaries for row in summary.pop("audit_rows")]
    audit_path = write_audit(audit_rows)
    summary = {
        "write": args.write,
        "years": YEARS,
        "audit_path": audit_path,
        "total_cell_changes": len(audit_rows),
        "changes_by_year": {str(summary["year"]): summary["cell_changes"] for summary in summaries},
        "changes_by_field": dict(Counter(row["field"] for row in audit_rows)),
        "summaries": summaries,
    }
    (AUDIT_DIR / "taxonomy_normalization_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
