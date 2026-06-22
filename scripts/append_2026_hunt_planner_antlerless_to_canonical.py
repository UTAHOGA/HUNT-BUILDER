import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRESH = ROOT / "audits" / "2025_canonical_finalization" / "fresh_live_pulls_20260621_192945"
AUDIT_DIR = ROOT / "audits" / "2026_live_source_comparison"
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"


SOURCE_FILES = [
    ("Deer", "Antlerless", "dwr_huntboundary_deer_antlerless.json"),
    ("Elk", "Antlerless", "dwr_huntboundary_elk_antlerless.json"),
    ("Moose", "Antlerless", "dwr_huntboundary_moose_antlerless.json"),
    ("Pronghorn", "Doe", "dwr_huntboundary_pronghorn_doe.json"),
    ("Rocky Mountain Bighorn Sheep", "Ewe", "dwr_huntboundary_rocky_mountain_bighorn_sheep_ewe.json"),
    ("Bison", "Cow Only", "dwr_huntboundary_bison_cow_only.json"),
]


def clean(value):
    return " ".join(str(value or "").replace("\r", "\n").split())


def int_or_blank(value):
    if value is None or value == "":
        return ""
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return clean(value)


def load_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def database_by_code():
    by_code = defaultdict(list)
    if not DATABASE.exists():
        return by_code
    with DATABASE.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            code = clean(row.get("hunt_code")).upper()
            if code:
                by_code[code].append(row)
    return by_code


def choose_database_row(matches, source):
    if not matches:
        return None
    species = clean(source.get("SPECIES")).lower()
    sex = clean(source.get("GENDER")).lower()
    weapon = clean(source.get("WEAPON")).lower()
    name = clean(source.get("HUNT_NAME")).lower()

    def score(row):
        total = 0
        if clean(row.get("species")).lower() == species:
            total += 8
        if clean(row.get("sex_type")).lower() == sex:
            total += 4
        if clean(row.get("weapon")).lower() == weapon:
            total += 3
        db_name = clean(row.get("hunt_name")).lower()
        if db_name and (db_name == name or db_name in name or name in db_name):
            total += 2
        if clean(row.get("boundary_id")):
            total += 1
        return total

    return max(matches, key=score)


def normalize_hunt_type(raw):
    value = clean(raw)
    folded = value.lower()
    if folded in {"general season", "general-season", "general-season"}:
        return "General Season"
    if folded == "cwmu":
        return "CWMU"
    if folded == "conservation":
        return "Conservation"
    if folded == "private lands only":
        return "Over-the-Counter"
    if folded == "antlerless elk control":
        return "Over-the-Counter"
    if folded == "limited entry":
        return "Limited Entry"
    return value


def draw_design_for(raw_hunt_type, species, code):
    folded = clean(raw_hunt_type).lower()
    code = clean(code).upper()
    species = clean(species).lower()
    if folded in {"general season", "general-season", "general-season"}:
        return "Preference"
    if folded in {"private lands only", "antlerless elk control"}:
        return "Capped Permits"
    if folded == "conservation":
        return "Organizations"
    if folded == "cwmu":
        return "Preference"
    if folded == "limited entry":
        return "Max/Weighted Split" if species in {"moose", "rocky mountain bighorn sheep", "bison"} else "Preference"
    if code.startswith(("DA", "EA", "PD")):
        return "Preference"
    return ""


def permit_values(row):
    quota_res = int(row.get("QUOTA_RES") or 0)
    quota_nr = int(row.get("QUOTA_NRES") or 0)
    quota = int(row.get("QUOTA") or 0)

    if quota > 0 and quota_res == 0 and quota_nr == 0:
        return "", "", str(quota)
    total = quota_res + quota_nr
    if total > 0:
        return str(quota_res), str(quota_nr), str(total)
    if quota > 0:
        return "", "", str(quota)
    return "", "", "0"


def source_url(species, sex):
    from urllib.parse import quote_plus

    return f"https://dwrapps.utah.gov/huntboundary/HuntTableData?species={quote_plus(species)}&gender={quote_plus(sex)}"


def canonical_payload(source, db_row, canonical_fields):
    code = clean(source.get("HUNT_NBR")).upper()
    species = clean(source.get("SPECIES"))
    sex = clean(source.get("GENDER"))
    raw_hunt_type = clean(source.get("HUNT_TYPE"))
    permits_res, permits_nr, permits_total = permit_values(source)

    row = {field: "" for field in canonical_fields}
    row.update(
        {
            "actual_draw_year": "2026",
            "model_target_year": "2027",
            "source_scope": "DWR_HUNT_PLANNER_ANTLERLESS",
            "source_namespace": "2026_HUNT_PLANNER_PERMIT_TABLE",
            "draw_source_namespace": "DWR_HUNT_PLANNER_2026",
            "source_file": source_url(species, sex),
            "page_kind": "PERMIT_QUOTA_ROW",
            "hunt_code": code,
            "hunt_name": clean(source.get("HUNT_NAME")),
            "species": species,
            "sex_type": sex,
            "draw_design": draw_design_for(raw_hunt_type, species, code),
            "weapon": clean(source.get("WEAPON")),
            "hunt_type": normalize_hunt_type(raw_hunt_type),
            "season": clean(source.get("SEASON_DATE_TEXT")),
            "record_type": "hunt_planner_permit_quota",
            "boundary_id": clean((db_row or {}).get("boundary_id")),
            "algorithm_status": "NON_SCORABLE_PERMIT_QUOTA_ROW_HUNT_PLANNER",
            "source_dataset": "DWR_HUNT_PLANNER_2026_ANTLERLESS_REFRESH_20260621",
            "extraction_status": "LIVE_DWR_HUNT_PLANNER_REFRESH",
            "parse_method": "DWR_HUNTBOUNDARY_HUNTTABLEDATA",
            "qa_status": "LIVE_HUNT_PLANNER_2026_PERMIT_TABLE",
            "notes": "2026 Hunt Planner antlerless/female-equivalent permit/quota row; not a draw-result point row.",
            "permits_2026_res": permits_res,
            "permits_2026_nr": permits_nr,
            "permits_2026_total": permits_total,
        }
    )
    return row


def row_key(row):
    return (
        clean(row.get("hunt_code")).upper(),
        clean(row.get("species")).lower(),
        clean(row.get("sex_type")).lower(),
        clean(row.get("weapon")).lower(),
        clean(row.get("hunt_name")).lower(),
        clean(row.get("season")).lower(),
    )


def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    canonical_fields, canonical_rows = load_csv(CANONICAL)
    long_fields, _ = load_csv(LONG)
    db = database_by_code()

    existing_codes = {clean(row.get("hunt_code")).upper() for row in canonical_rows if clean(row.get("hunt_code"))}
    existing_keys = {row_key(row) for row in canonical_rows}

    sources = []
    for species, sex, filename in SOURCE_FILES:
        path = FRESH / filename
        if not path.exists():
            raise FileNotFoundError(path)
        for row in json.loads(path.read_text(encoding="utf-8-sig")):
            row["_source_filename"] = filename
            sources.append(row)

    appended = []
    skipped = []
    for source in sources:
        code = clean(source.get("HUNT_NBR")).upper()
        db_row = choose_database_row(db.get(code, []), source)
        payload = canonical_payload(source, db_row, canonical_fields)
        key = row_key(payload)
        if code in existing_codes or key in existing_keys:
            skipped.append(
                {
                    "hunt_code": code,
                    "hunt_name": payload["hunt_name"],
                    "species": payload["species"],
                    "sex_type": payload["sex_type"],
                    "weapon": payload["weapon"],
                    "season": payload["season"],
                    "reason": "already_present_in_canonical",
                    "canonical_boundary_id": payload["boundary_id"],
                    "source_filename": source.get("_source_filename", ""),
                }
            )
            continue
        appended.append(payload)
        existing_codes.add(code)
        existing_keys.add(key)

    if appended:
        write_csv(CANONICAL, canonical_fields, canonical_rows + appended)

        with LONG.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=long_fields, lineterminator="\n")
            for row in appended:
                long_row = {field: row.get(field, "") for field in long_fields}
                writer.writerow(long_row)

    audit_fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "hunt_type",
        "draw_design",
        "weapon",
        "season",
        "boundary_id",
        "permits_2026_res",
        "permits_2026_nr",
        "permits_2026_total",
        "source_file",
    ]
    with (AUDIT_DIR / "appended_2026_hunt_planner_antlerless_rows.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=audit_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in audit_fields} for row in appended)

    skipped_fields = ["hunt_code", "hunt_name", "species", "sex_type", "weapon", "season", "reason", "canonical_boundary_id", "source_filename"]
    with (AUDIT_DIR / "skipped_2026_hunt_planner_antlerless_rows.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=skipped_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(skipped)

    summary = {
        "source_rows": len(sources),
        "canonical_rows_before": len(canonical_rows),
        "canonical_rows_after": len(canonical_rows) + len(appended),
        "appended_rows": len(appended),
        "skipped_existing_rows": len(skipped),
        "appended_boundary_id_populated": sum(1 for row in appended if clean(row.get("boundary_id"))),
        "appended_boundary_id_blank": sum(1 for row in appended if not clean(row.get("boundary_id"))),
        "appended_by_species": dict(sorted(defaultdict(int, ((k, 0) for k in [])).items())),
    }
    by_species = defaultdict(int)
    by_design = defaultdict(int)
    by_type = defaultdict(int)
    for row in appended:
        by_species[row["species"]] += 1
        by_design[row["draw_design"]] += 1
        by_type[row["hunt_type"]] += 1
    summary["appended_by_species"] = dict(sorted(by_species.items()))
    summary["appended_by_draw_design"] = dict(sorted(by_design.items()))
    summary["appended_by_hunt_type"] = dict(sorted(by_type.items()))

    (AUDIT_DIR / "append_2026_hunt_planner_antlerless_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
