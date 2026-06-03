import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "exports" / "utahdraws_draw_odds_20260603" / "csv"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
AUDIT_OUT = ROOT / "processed_data" / "audits" / "dwr_2026_draw_results_vs_database_allotments.csv"
SUMMARY_OUT = ROOT / "processed_data" / "audits" / "dwr_2026_draw_results_vs_database_allotments_summary.json"
REPORT_OUT = ROOT / "docs" / "dwr_2026_draw_results_vs_database_allotments.md"

CODE_RE = re.compile(r"^[A-Z]{2,3}\d{3,4}$")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean(value):
    return str(value or "").strip()


def int_or_blank(value):
    value = clean(value).replace(",", "")
    if value == "":
        return ""
    try:
        return str(int(float(value)))
    except ValueError:
        return ""


def classify_family(code):
    if code.startswith("BR"):
        return "Black Bear"
    if code.startswith("DB"):
        return "Buck Deer"
    if code.startswith("EB"):
        return "Bull Elk"
    if code.startswith("PB"):
        return "Buck Pronghorn"
    if code.startswith("MB"):
        return "Bull Moose"
    if code.startswith("BI"):
        return "Bison"
    if code.startswith("DS"):
        return "Desert Bighorn Sheep"
    if code.startswith("RS"):
        return "Rocky Mountain Bighorn Sheep"
    if code.startswith("GO"):
        return "Mountain Goat"
    if code.startswith("TK"):
        return "Turkey"
    return code[:2]


def source_records():
    by_code = defaultdict(lambda: {
        "hunt_code": "",
        "source_hunt_names": set(),
        "source_species": set(),
        "source_files": set(),
        "source_hunt_ids": set(),
        "source_res_values": set(),
        "source_nr_values": set(),
        "source_total_values": set(),
        "source_row_count": 0,
    })
    input_files = sorted(SOURCE_DIR.glob("*.csv"))
    skipped_non_hunt_codes = Counter()
    for path in input_files:
        for row in read_csv(path):
            code = clean(row.get("HuntCode")).upper()
            if not CODE_RE.match(code):
                if code:
                    skipped_non_hunt_codes[code] += 1
                continue
            rec = by_code[code]
            rec["hunt_code"] = code
            rec["source_hunt_names"].add(clean(row.get("HuntName")))
            rec["source_species"].add(clean(row.get("SpeciesSubtypeName")))
            rec["source_files"].add(str(path.relative_to(ROOT)).replace("\\", "/"))
            rec["source_hunt_ids"].add(clean(row.get("HuntID")))
            rec["source_res_values"].add(int_or_blank(row.get("ResidentQuotaQuantity")))
            rec["source_nr_values"].add(int_or_blank(row.get("NonResidentQuotaQuantity")))
            rec["source_total_values"].add(int_or_blank(row.get("QuotaQuantity")))
            rec["source_row_count"] += 1
    return by_code, input_files, skipped_non_hunt_codes


def db_records():
    rows = {}
    for row in read_csv(DATABASE):
        code = clean(row.get("hunt_code")).upper()
        if code:
            rows[code] = row
    return rows


def single_value(values):
    clean_values = sorted(v for v in values if v != "")
    if not clean_values:
        return ""
    if len(set(clean_values)) == 1:
        return clean_values[0]
    return "|".join(sorted(set(clean_values), key=lambda x: int(x) if x.isdigit() else x))


def compare_value(src, db):
    if src == "" and db == "":
        return "BOTH_BLANK"
    if src == "":
        return "SOURCE_BLANK"
    if db == "":
        return "DATABASE_BLANK"
    return "MATCH" if src == db else "MISMATCH"


def row_status(row):
    if row["source_presence"] == "SOURCE_ONLY":
        return "SOURCE_ONLY_NOT_IN_DATABASE"
    if row["source_presence"] == "DATABASE_ONLY":
        return "DATABASE_ONLY_NOT_IN_SOURCE_PULL"
    if row["source_value_status"] == "MULTIPLE_SOURCE_VALUES":
        return "REVIEW_MULTIPLE_SOURCE_VALUES"
    comparisons = [row["res_compare_status"], row["nr_compare_status"], row["total_compare_status"]]
    if "MISMATCH" in comparisons:
        parts = []
        if row["res_compare_status"] == "MISMATCH":
            parts.append("RES")
        if row["nr_compare_status"] == "MISMATCH":
            parts.append("NR")
        if row["total_compare_status"] == "MISMATCH":
            parts.append("TOTAL")
        return "MISMATCH_" + "_".join(parts)
    if "DATABASE_BLANK" in comparisons:
        return "SOURCE_HAS_VALUE_DATABASE_BLANK"
    if "SOURCE_BLANK" in comparisons:
        return "DATABASE_HAS_VALUE_SOURCE_BLANK"
    if all(c in ("MATCH", "BOTH_BLANK") for c in comparisons):
        return "MATCH_ALL_COMPARABLE"
    return "REVIEW"


def main():
    sources, input_files, skipped = source_records()
    db = db_records()
    rows = []
    all_codes = sorted(set(sources) | set(db))
    for code in all_codes:
        src = sources.get(code)
        db_row = db.get(code)
        source_presence = "SOURCE_AND_DATABASE" if src and db_row else ("SOURCE_ONLY" if src else "DATABASE_ONLY")
        source_res = single_value(src["source_res_values"]) if src else ""
        source_nr = single_value(src["source_nr_values"]) if src else ""
        source_total = single_value(src["source_total_values"]) if src else ""
        source_value_status = "OK"
        if any("|" in value for value in (source_res, source_nr, source_total)):
            source_value_status = "MULTIPLE_SOURCE_VALUES"
        db_res = int_or_blank(db_row.get("permit_allotment_2026_res")) if db_row else ""
        db_nr = int_or_blank(db_row.get("permit_allotment_2026_nr")) if db_row else ""
        db_total = int_or_blank(db_row.get("permit_allotment_2026_total")) if db_row else ""
        out = {
            "hunt_code": code,
            "species_family": classify_family(code),
            "source_presence": source_presence,
            "source_value_status": source_value_status,
            "source_hunt_name": "|".join(sorted(src["source_hunt_names"])) if src else "",
            "database_hunt_name": clean(db_row.get("hunt_name")) if db_row else "",
            "source_species": "|".join(sorted(src["source_species"])) if src else "",
            "database_species": clean(db_row.get("species")) if db_row else "",
            "source_res": source_res,
            "source_nr": source_nr,
            "source_total": source_total,
            "database_allotment_res": db_res,
            "database_allotment_nr": db_nr,
            "database_allotment_total": db_total,
            "res_compare_status": compare_value(source_res, db_res),
            "nr_compare_status": compare_value(source_nr, db_nr),
            "total_compare_status": compare_value(source_total, db_total),
            "source_row_count": str(src["source_row_count"]) if src else "0",
            "source_files": "|".join(sorted(src["source_files"])) if src else "",
            "source_hunt_ids": "|".join(sorted(src["source_hunt_ids"])) if src else "",
            "notes": "2026 draw-results pull is provisional evidence; DATABASE allotment columns remain authoritative until promotion review.",
        }
        out["comparison_status"] = row_status(out)
        rows.append(out)

    fieldnames = [
        "hunt_code",
        "species_family",
        "source_presence",
        "comparison_status",
        "source_value_status",
        "source_hunt_name",
        "database_hunt_name",
        "source_species",
        "database_species",
        "source_res",
        "source_nr",
        "source_total",
        "database_allotment_res",
        "database_allotment_nr",
        "database_allotment_total",
        "res_compare_status",
        "nr_compare_status",
        "total_compare_status",
        "source_row_count",
        "source_files",
        "source_hunt_ids",
        "notes",
    ]
    write_csv(AUDIT_OUT, rows, fieldnames)

    status_counts = Counter(row["comparison_status"] for row in rows)
    presence_counts = Counter(row["source_presence"] for row in rows)
    family_status_counts = Counter((row["species_family"], row["comparison_status"]) for row in rows)
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Provisional comparison of DWR/UtahDraws 2026 draw-results pull against DATABASE.csv permit_allotment_2026 fields.",
        "source_directory": str(SOURCE_DIR),
        "database": str(DATABASE),
        "input_csv_count": len(input_files),
        "source_hunt_codes": len(sources),
        "database_hunt_codes": len(db),
        "union_hunt_codes": len(rows),
        "presence_counts": dict(sorted(presence_counts.items())),
        "comparison_status_counts": dict(sorted(status_counts.items())),
        "skipped_non_hunt_codes": dict(sorted(skipped.items())),
        "family_status_counts": {
            f"{family}|{status}": count
            for (family, status), count in sorted(family_status_counts.items())
        },
        "outputs": {
            "audit_csv": str(AUDIT_OUT),
            "summary_json": str(SUMMARY_OUT),
            "report_md": str(REPORT_OUT),
        },
        "truth_status": "PROVISIONAL_SOURCE_EVIDENCE_ONLY_NOT_PROMOTED",
    }
    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    mismatch_rows = [r for r in rows if r["comparison_status"].startswith("MISMATCH")]
    source_only = [r for r in rows if r["comparison_status"] == "SOURCE_ONLY_NOT_IN_DATABASE"]
    db_only = [r for r in rows if r["comparison_status"] == "DATABASE_ONLY_NOT_IN_SOURCE_PULL"]
    lines = [
        "# DWR 2026 Draw Results vs DATABASE Allotment Audit",
        "",
        "## Scope",
        "- Compared the provisional 2026 DWR/UtahDraws draw-results pull to `DATABASE.csv` allotment fields.",
        "- Source fields: `QuotaQuantity`, `ResidentQuotaQuantity`, `NonResidentQuotaQuantity` from the generated 2026 CSV exports.",
        "- DATABASE fields: `permit_allotment_2026_total`, `permit_allotment_2026_res`, `permit_allotment_2026_nr`.",
        "- This audit does not promote the 2026 draw-results pull as truth and does not modify `DATABASE.csv`.",
        "",
        "## Key Counts",
        f"- Input source CSV files: `{len(input_files)}`",
        f"- Source hunt codes: `{len(sources)}`",
        f"- DATABASE hunt codes: `{len(db)}`",
        f"- Union hunt codes compared: `{len(rows)}`",
        "",
        "## Comparison Status Counts",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"- `{status}`: `{count}`")
    lines.extend([
        "",
        "## Important Interpretation",
        "- `DATABASE.csv` remains authoritative for current allotment values.",
        "- The 2026 draw-results pull appears to cover a narrower draw-results universe than the full current hunt-code universe.",
        "- `DATABASE_ONLY_NOT_IN_SOURCE_PULL` rows are not automatically defects; they may be current application/allotment rows that are absent from this provisional draw-results pull.",
        "- `SOURCE_ONLY_NOT_IN_DATABASE` rows need review before promotion or crosswalk action.",
        "",
        "## Source-Only Hunt Codes",
    ])
    if source_only:
        for r in source_only[:50]:
            lines.append(f"- `{r['hunt_code']}`: source total `{r['source_total']}`, source name `{r['source_hunt_name']}`")
    else:
        lines.append("- None.")
    lines.extend(["", "## Mismatches"])
    if mismatch_rows:
        for r in mismatch_rows[:100]:
            lines.append(
                f"- `{r['hunt_code']}` `{r['comparison_status']}`: source `{r['source_res']}/{r['source_nr']}/{r['source_total']}` vs DB `{r['database_allotment_res']}/{r['database_allotment_nr']}/{r['database_allotment_total']}`"
            )
    else:
        lines.append("- No numeric mismatches where both source and DATABASE have comparable populated values.")
    lines.extend([
        "",
        "## Database-Only Coverage",
        f"- DATABASE-only rows: `{len(db_only)}`",
        "- Review the CSV for details; this is expected to include current rows outside this draw-results pull.",
        "",
        "## Outputs",
        f"- `{AUDIT_OUT}`",
        f"- `{SUMMARY_OUT}`",
    ])
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
