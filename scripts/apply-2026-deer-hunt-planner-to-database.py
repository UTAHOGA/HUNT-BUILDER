from __future__ import annotations

import csv
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATABASE_CSV = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
HUNT_PLANNER_XLSX = (
    ROOT
    / "outputs"
    / "20260626_fresh_2026_source_species_docs"
    / "hunt_planner_xlsx"
    / "2026_HUNTPLANNER__deer.xlsx"
)
AUDIT_CSV = ROOT / "processed_data" / "audits" / "deer_hunt_planner_truth_database_patch_2026.csv"
SUMMARY_JSON = ROOT / "processed_data" / "audits" / "deer_hunt_planner_truth_database_patch_2026_summary.json"
BACKUP_DIR = ROOT / "processed_data" / "backups"

SOURCE_LABEL = "2026_HUNT_PLANNER_DWR_CONFIRMED_TRUTH_SOURCE"
LEGACY_STATUS = "LEGACY_COMPAT_MIRROR_OF_PERMITS_2026"
PRIVATE_LAND_UNPUBLISHED_SOURCE = "2026_HUNT_PLANNER_PERMIT_DATA_NOT_PUBLISHED"
PRIVATE_LAND_UNPUBLISHED_STATUS = "PERMIT_DATA_NOT_PUBLISHED_HUNT_PLANNER_REFERENCE"


def clean_code(value: object) -> str:
    return "" if value is None else str(value).strip()


def clean_int(value: object) -> int:
    if value is None:
        return 0
    if pd.isna(value):
        return 0
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    return int(float(text))


def load_hunt_planner() -> dict[str, dict[str, object]]:
    df = pd.read_excel(HUNT_PLANNER_XLSX, sheet_name="Table 1")
    df["hunt_code"] = df["hunt_code"].map(clean_code)
    for col in ["permits_res", "permits_nr", "permits_total"]:
        df[col] = df[col].map(clean_int)

    by_code: dict[str, dict[str, object]] = {}
    for _, row in df.iterrows():
        code = clean_code(row.get("hunt_code"))
        if not code:
            continue

        res = clean_int(row.get("permits_res"))
        nr = clean_int(row.get("permits_nr"))
        total = clean_int(row.get("permits_total"))
        has_split = res != 0 or nr != 0
        source_shape = "RES_NR_SPLIT" if has_split else "TOTAL_ONLY_OR_ZERO"
        is_private_land_unpublished = (
            total == 0
            and "private land only" in clean_code(row.get("hunt_type")).lower()
        )

        by_code[code] = {
            "hunt_code": code,
            "hunt_name": clean_code(row.get("hunt_name")),
            "endpoint_gender": clean_code(row.get("endpoint_gender")),
            "sex_type": clean_code(row.get("sex_type")),
            "species": clean_code(row.get("species")),
            "weapon": clean_code(row.get("weapon")),
            "hunt_type": clean_code(row.get("hunt_type")),
            "season": clean_code(row.get("season")),
            "source_url": clean_code(row.get("source_url")),
            "hp_res": res,
            "hp_nr": nr,
            "hp_total": total,
            "source_shape": source_shape,
            "is_private_land_unpublished": is_private_land_unpublished,
            "live_shape_status": clean_code(row.get("live_shape_status")),
        }
    return by_code


def main() -> int:
    if not DATABASE_CSV.exists():
        raise FileNotFoundError(DATABASE_CSV)
    if not HUNT_PLANNER_XLSX.exists():
        raise FileNotFoundError(HUNT_PLANNER_XLSX)

    hp_by_code = load_hunt_planner()

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"DATABASE_before_deer_hunt_planner_truth_patch_{timestamp}.csv"
    shutil.copy2(DATABASE_CSV, backup_path)

    with DATABASE_CSV.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    audit_rows: list[dict[str, object]] = []
    found_codes: set[str] = set()
    skipped_sportsman_codes: set[str] = set()
    changed_count = 0
    zero_rows = 0
    split_rows = 0
    total_only_rows = 0
    private_land_unpublished_rows = 0

    for row in rows:
        code = clean_code(row.get("hunt_code"))
        hp = hp_by_code.get(code)
        if not hp:
            continue
        if clean_code(row.get("species")).lower() != "deer":
            continue
        if clean_code(row.get("draw_2026_system_type")).upper() == "SPORTSMAN_PERMIT":
            skipped_sportsman_codes.add(code)
            continue

        found_codes.add(code)
        old_res = clean_code(row.get("permits_2026_res"))
        old_nr = clean_code(row.get("permits_2026_nr"))
        old_total = clean_code(row.get("permits_2026_total"))

        if hp["is_private_land_unpublished"]:
            new_res = ""
            new_nr = ""
            new_total = ""
            source_label = PRIVATE_LAND_UNPUBLISHED_SOURCE
            legacy_status = PRIVATE_LAND_UNPUBLISHED_STATUS
            private_land_unpublished_rows += 1
        elif hp["source_shape"] == "RES_NR_SPLIT":
            new_res = str(hp["hp_res"])
            new_nr = str(hp["hp_nr"])
            new_total = str(hp["hp_total"])
            source_label = SOURCE_LABEL
            legacy_status = LEGACY_STATUS
            split_rows += 1
        else:
            new_res = ""
            new_nr = ""
            new_total = str(hp["hp_total"])
            source_label = SOURCE_LABEL
            legacy_status = LEGACY_STATUS
            total_only_rows += 1
            if hp["hp_total"] == 0:
                zero_rows += 1

        changed = (old_res, old_nr, old_total) != (new_res, new_nr, new_total)
        if changed:
            changed_count += 1

        row["permits_2026_res"] = new_res
        row["permits_2026_nr"] = new_nr
        row["permits_2026_total"] = new_total
        row["permits_2026_source"] = source_label
        row["permits_2026_draw_source"] = HUNT_PLANNER_XLSX.name

        row["permit_allotment_2026_res"] = new_res
        row["permit_allotment_2026_nr"] = new_nr
        row["permit_allotment_2026_total"] = new_total
        row["permit_allotment_2026_source"] = source_label
        row["permit_allotment_2026_source_file"] = HUNT_PLANNER_XLSX.name
        row["permit_allotment_2026_status"] = legacy_status

        audit_rows.append(
            {
                "hunt_code": code,
                "database_hunt_name": clean_code(row.get("hunt_name")),
                "hunt_planner_hunt_name": hp["hunt_name"],
                "database_hunt_type": clean_code(row.get("hunt_type")),
                "hunt_planner_hunt_type": hp["hunt_type"],
                "database_hunt_class": clean_code(row.get("hunt_class")),
                "weapon": clean_code(row.get("weapon")),
                "old_res": old_res,
                "old_nr": old_nr,
                "old_total": old_total,
                "new_res": new_res,
                "new_nr": new_nr,
                "new_total": new_total,
                "source_shape": hp["source_shape"],
                "live_shape_status": hp["live_shape_status"],
                "private_land_unpublished": "YES" if hp["is_private_land_unpublished"] else "NO",
                "changed": "YES" if changed else "NO",
                "source_url": hp["source_url"],
            }
        )

    missing_from_database = sorted(set(hp_by_code) - found_codes - skipped_sportsman_codes)
    for code in missing_from_database:
        hp = hp_by_code[code]
        if hp["is_private_land_unpublished"]:
            new_res = ""
            new_nr = ""
            new_total = ""
            changed_status = "HUNT_PLANNER_CODE_NOT_IN_DATABASE_PERMIT_DATA_NOT_PUBLISHED"
            new_row = {field: "" for field in fieldnames}
            new_row.update(
                {
                    "hunt_code": code,
                    "hunt_name": hp["hunt_name"],
                    "sex_type": hp["sex_type"],
                    "species": hp["species"],
                    "weapon": hp["weapon"],
                    "hunt_type": hp["hunt_type"],
                    "hunt_class": "Reference Only",
                    "season": hp["season"],
                    "NOTES": "DWR Hunt Planner lists this hunt, but permit data is not published.",
                    "permits_2026_source": PRIVATE_LAND_UNPUBLISHED_SOURCE,
                    "permits_2026_draw_source": HUNT_PLANNER_XLSX.name,
                    "permit_allotment_2026_source": PRIVATE_LAND_UNPUBLISHED_SOURCE,
                    "permit_allotment_2026_source_file": HUNT_PLANNER_XLSX.name,
                    "permit_allotment_2026_status": PRIVATE_LAND_UNPUBLISHED_STATUS,
                }
            )
            rows.append(new_row)
            private_land_unpublished_rows += 1
        else:
            new_res = hp["hp_res"]
            new_nr = hp["hp_nr"]
            new_total = hp["hp_total"]
            changed_status = "HUNT_PLANNER_CODE_NOT_IN_DATABASE"
        audit_rows.append(
            {
                "hunt_code": code,
                "database_hunt_name": "",
                "hunt_planner_hunt_name": hp["hunt_name"],
                "database_hunt_type": "",
                "hunt_planner_hunt_type": hp["hunt_type"],
                "database_hunt_class": "",
                "weapon": hp["weapon"],
                "old_res": "",
                "old_nr": "",
                "old_total": "",
                "new_res": new_res,
                "new_nr": new_nr,
                "new_total": new_total,
                "source_shape": hp["source_shape"],
                "live_shape_status": hp["live_shape_status"],
                "private_land_unpublished": "YES" if hp["is_private_land_unpublished"] else "NO",
                "changed": changed_status,
                "source_url": hp["source_url"],
            }
        )

    with DATABASE_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    AUDIT_CSV.parent.mkdir(parents=True, exist_ok=True)
    audit_fields = [
        "hunt_code",
        "database_hunt_name",
        "hunt_planner_hunt_name",
        "database_hunt_type",
        "hunt_planner_hunt_type",
        "database_hunt_class",
        "weapon",
        "old_res",
        "old_nr",
        "old_total",
        "new_res",
        "new_nr",
        "new_total",
        "source_shape",
        "live_shape_status",
        "private_land_unpublished",
        "changed",
        "source_url",
    ]
    with AUDIT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=audit_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)

    import json

    summary = {
        "source": str(HUNT_PLANNER_XLSX),
        "database": str(DATABASE_CSV),
        "backup": str(backup_path),
        "audit": str(AUDIT_CSV),
        "hunt_planner_codes": len(hp_by_code),
        "database_codes_updated": len(found_codes),
        "numeric_rows_changed": changed_count,
        "split_rows": split_rows,
        "total_only_rows": total_only_rows,
        "zero_total_only_rows": zero_rows,
        "private_land_unpublished_rows": private_land_unpublished_rows,
        "skipped_sportsman_codes": sorted(skipped_sportsman_codes),
        "hunt_planner_codes_missing_from_database": len(missing_from_database),
        "missing_codes": missing_from_database,
        "source_label": SOURCE_LABEL,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
