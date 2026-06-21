"""Add draw_design classification to finalized truth datasets.

This script only adds/fills the draw_design classification layer. It preserves
row counts and does not change probability, applicant, permit, or success fields.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
POINT_PATH = REPO / "data_truth" / "finalized_point_distribution.csv"
HUNT_PATH = REPO / "data_truth" / "finalized_hunt_truth.csv"
AUDIT_DIR = REPO / "audits"
SUMMARY_PATH = AUDIT_DIR / "draw_design_classification_summary.csv"
UNCLASSIFIED_PATH = AUDIT_DIR / "draw_design_unclassified.csv"
STATUS_PATH = AUDIT_DIR / "draw_design_classification_status.json"

SPORTSMAN_RANDOM_CODES = {
    "BI1000",
    "BR1000",
    "CG1000",
    "DB0007",
    "DS1000",
    "EB1000",
    "GO1000",
    "MB1000",
    "PB1000",
    "RS0001",
    "TK0001",
}

PROTECTED_FIELDS = {
    "permits",
    "applicants",
    "applicants_total",
    "permits_bonus",
    "permits_regular",
    "permits_total",
    "success_rate",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def lower(value: object) -> str:
    return clean(value).lower()


def joined_text(row: dict[str, str]) -> str:
    keys = (
        "hunt_code",
        "hunt_name",
        "species",
        "hunt_type",
        "hunt_category",
        "hunt_class",
        "hunt_program",
        "permit_allocation_type",
        "availability_status",
        "source_file",
        "source_workbook",
        "source_sheet",
        "source_namespace",
        "record_type",
    )
    return " ".join(lower(row.get(key)) for key in keys if clean(row.get(key)))


def code(row: dict[str, str]) -> str:
    return clean(row.get("hunt_code")).upper()


def classify_draw_design(row: dict[str, str]) -> str:
    hunt_code = code(row)
    text = joined_text(row)
    hunt_type = lower(row.get("hunt_type"))
    hunt_category = lower(row.get("hunt_category"))
    permit_allocation_type = lower(row.get("permit_allocation_type"))
    availability_status = lower(row.get("availability_status"))
    source_namespace = lower(row.get("source_namespace"))
    source_file = lower(row.get("source_file"))

    if hunt_code in SPORTSMAN_RANDOM_CODES or "sportsman" in permit_allocation_type or "sportsman" in text:
        return "RANDOM"

    # Dedicated Hunter must precede generic preference/general-season rules.
    if (
        hunt_code.startswith("DB17")
        or "dedicated hunter" in text
        or "dedicated_hunter" in text
        or "dh_deer" in text
        or "d.h. deer" in text
        or source_namespace in {"dh_deer", "youth_dh_deer"}
        or "dh odds" in source_file
        or "dh_odds" in source_file
    ):
        return "DEDICATED_HUNTER"

    if (
        "otc" in hunt_type
        or " otc" in f" {text}"
        or "over the counter" in text
        or "unlimited" in permit_allocation_type
        or availability_status == "available"
        or "availability" in text
        or "contact operator" in text
    ):
        return "AVAILABILITY"

    if (
        "general" in hunt_type
        or "general season" in text
        or "antlerless" in hunt_category
        or "antlerless" in text
        or "doe pronghorn" in text
        or "general deer preference point" in text
        or hunt_code == "GDR"
        or source_namespace in {
            "antlerless_regular_multi",
            "antlerless_youth_multi",
            "gs_deer",
            "youth_gs_deer",
            "lifetime_gs_deer",
        }
    ):
        return "PREFERENCE"

    if (
        "limited entry" in hunt_type
        or "limited-entry" in text
        or "premium limited" in text
        or "once-in-a-lifetime" in text
        or "once in a lifetime" in text
        or "o.i.l." in text
        or "bonus point" in text
        or source_namespace in {"bg_parent", "bear", "turkey", "youth_turkey", "le_deer", "le_elk", "le_pronghorn"}
        or hunt_code.startswith(("LE", "EL", "DE", "PR"))
        or hunt_code.startswith(("EB", "DB", "PB", "DS", "RS", "GO", "MB", "BI", "BR", "TK", "CG"))
    ):
        return "BONUS_SPLIT"

    return ""


def inferred_species(row: dict[str, str]) -> str:
    value = clean(row.get("species"))
    if value:
        return value
    hunt_code = code(row)
    prefix = hunt_code[:2]
    return {
        "BI": "Bison",
        "BR": "Bear",
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
        "RS": "Rocky Mountain Bighorn Sheep",
        "TK": "Turkey",
    }.get(prefix, "")


def inferred_hunt_program(row: dict[str, str]) -> str:
    for key in ("hunt_program", "hunt_type", "source_namespace", "record_type"):
        value = clean(row.get(key))
        if value:
            return value
    return ""


def process_file(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]

    if "draw_design" not in fieldnames:
        fieldnames.append("draw_design")

    before_count = len(rows)
    protected_before = [{field: row.get(field, "") for field in PROTECTED_FIELDS if field in row} for row in rows]
    existing_nonblank_preserved = 0

    for row in rows:
        existing = clean(row.get("draw_design"))
        if existing:
            existing_nonblank_preserved += 1
            continue
        row["draw_design"] = classify_draw_design(row)

    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temp_path.replace(path)

    protected_after = [{field: row.get(field, "") for field in PROTECTED_FIELDS if field in row} for row in rows]
    if protected_before != protected_after:
        raise RuntimeError(f"Protected value fields changed while processing {path}")

    return {
        "path": str(path.relative_to(REPO)),
        "rows_before": before_count,
        "rows_after": len(rows),
        "columns_after": len(fieldnames),
        "draw_design_blank_count": sum(1 for row in rows if not clean(row.get("draw_design"))),
        "existing_nonblank_draw_design_preserved": existing_nonblank_preserved,
        "rows": rows,
    }


def write_audits(results: list[dict[str, object]]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    summary_counter: dict[tuple[str, str, str, str], int] = Counter()
    unclassified: list[dict[str, str]] = []

    for result in results:
        dataset = str(result["path"])
        for row in result["rows"]:  # type: ignore[index]
            draw_design = clean(row.get("draw_design"))
            species = inferred_species(row)
            hunt_program = inferred_hunt_program(row)
            summary_counter[(dataset, draw_design, species, hunt_program)] += 1
            if not draw_design:
                unclassified.append(
                    {
                        "dataset": dataset,
                        "year": clean(row.get("year")),
                        "model_year": clean(row.get("model_year")),
                        "hunt_code": code(row),
                        "hunt_name": clean(row.get("hunt_name")),
                        "species": species,
                        "hunt_program": hunt_program,
                        "source_file": clean(row.get("source_file")),
                        "source_namespace": clean(row.get("source_namespace")),
                        "record_type": clean(row.get("record_type")),
                    }
                )

    with SUMMARY_PATH.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["dataset", "draw_design", "species", "hunt_program", "row_count"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for (dataset, draw_design, species, hunt_program), count in sorted(summary_counter.items()):
            writer.writerow(
                {
                    "dataset": dataset,
                    "draw_design": draw_design,
                    "species": species,
                    "hunt_program": hunt_program,
                    "row_count": count,
                }
            )

    with UNCLASSIFIED_PATH.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "dataset",
            "year",
            "model_year",
            "hunt_code",
            "hunt_name",
            "species",
            "hunt_program",
            "source_file",
            "source_namespace",
            "record_type",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unclassified)

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": [str(POINT_PATH.relative_to(REPO)), str(HUNT_PATH.relative_to(REPO))],
        "summary_path": str(SUMMARY_PATH.relative_to(REPO)),
        "unclassified_path": str(UNCLASSIFIED_PATH.relative_to(REPO)),
        "row_count_preserved": all(result["rows_before"] == result["rows_after"] for result in results),
        "unclassified_rows": len(unclassified),
        "results": [
            {key: value for key, value in result.items() if key != "rows"}
            for result in results
        ],
    }
    STATUS_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")


def main() -> None:
    results = [process_file(POINT_PATH), process_file(HUNT_PATH)]
    write_audits(results)
    print(STATUS_PATH)


if __name__ == "__main__":
    main()
