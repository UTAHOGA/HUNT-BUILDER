"""Compare fresh DWR live hunt-code universe against BIBLE year documents."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIVE_TABLE = ROOT / "data_truth/crosswalk_truth/raw_inventory/live_dwr_hunt_planner_permit_numbers_comprehensive_2026.csv"
LIVE_COMPARE = ROOT / "data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.csv"
HANUMBER = ROOT / "processed_data/dwr_huntplanner_hanumber_2026.csv"
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
BIBLE_DIR = ROOT / "processed_data/audits/bible_hunt_code_year_documents"
OUT_CSV = ROOT / "processed_data/audits/current_2026_live_vs_bible_hunt_code_universe.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/current_2026_live_vs_bible_hunt_code_universe_summary.json"
OUT_DOC = ROOT / "docs/current_2026_live_vs_bible_hunt_code_universe.md"
SPORTSMAN_CODES = {
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


def clean(value: object) -> str:
    return str(value or "").strip()


def code(value: object) -> str:
    return clean(value).upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def bible_code(row: dict[str, str]) -> str:
    for field in ("hunt_code", "comparison_hunt_code", "current_active_code", "historical_code"):
        value = code(row.get(field))
        if value:
            return value
    return ""


def load_bible_years() -> dict[int, dict[str, dict[str, str]]]:
    by_year: dict[int, dict[str, dict[str, str]]] = {}
    for year in range(2020, 2027):
        path = BIBLE_DIR / f"bible_hunt_code_year_document_{year}.csv"
        rows = read_csv(path)
        by_code: dict[str, dict[str, str]] = {}
        for row in rows:
            c = bible_code(row)
            if c and c not in by_code:
                by_code[c] = row
        by_year[year] = by_code
    return by_year


def classify_extra(row: dict[str, str]) -> str:
    hunt_code = code(row.get("hunt_code"))
    prefix = hunt_code[:2]
    hunt_type = clean(row.get("hunt_type")).lower()
    name = clean(row.get("hunt_name")).lower()
    if hunt_code in SPORTSMAN_CODES or "sportsman" in name:
        return "SPORTSMAN_CURRENT_PLANNER"
    if "extended archery" in hunt_type or "extended archery" in name:
        return "EXTENDED_ARCHERY_CURRENT_PLANNER"
    if prefix in {"EL", "LO", "LP", "LD"} or "private land" in hunt_type or "private land" in name:
        return "PRIVATE_LAND_OR_LANDOWNER_CURRENT_PLANNER"
    if "conservation" in hunt_type or "conservation" in name:
        return "CONSERVATION_CURRENT_PLANNER"
    if "statewide" in hunt_type or "statewide" in name or prefix in {"CG"}:
        return "STATEWIDE_OR_UNLIMITED_CURRENT_PLANNER"
    if "tribal" in hunt_type or "tribal" in name:
        return "TRIBAL_CURRENT_PLANNER"
    if "cwmu" in hunt_type or "cwmu" in name:
        return "CWMU_CURRENT_PLANNER"
    return "OTHER_CURRENT_PLANNER_NOT_IN_2025_BIBLE"


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    bible = load_bible_years()
    live_rows = read_csv(LIVE_TABLE)
    live_compare_rows = {code(r.get("hunt_code")): r for r in read_csv(LIVE_COMPARE)}
    hanumber_rows = {code(r.get("hunt_code")): r for r in read_csv(HANUMBER)}
    db_rows = {code(r.get("hunt_code")): r for r in read_csv(DATABASE)}

    live_by_code: dict[str, dict[str, str]] = {}
    for row in live_rows:
        c = code(row.get("hunt_code"))
        if c and c not in live_by_code:
            live_by_code[c] = row

    all_codes = sorted(set(live_by_code) | set(db_rows) | set().union(*(set(v) for v in bible.values())))
    rows: list[dict[str, object]] = []
    for c in all_codes:
        live = live_by_code.get(c, {})
        db = db_rows.get(c, {})
        compare = live_compare_rows.get(c, {})
        hanumber = hanumber_rows.get(c, {})
        present_years = [str(year) for year, year_rows in bible.items() if c in year_rows]
        in_2025_bible = c in bible[2025]
        in_2026_bible = c in bible[2026]
        in_live = c in live_by_code
        if in_live and not in_2025_bible:
            universe_status = "LIVE_2026_NOT_IN_2025_BIBLE"
            cause = classify_extra(live)
        elif in_2025_bible and not in_live:
            universe_status = "BIBLE_2025_NOT_IN_LIVE_2026_TABLE"
            cause = "DROPPED_OR_NOT_EXPOSED_IN_CURRENT_TABLE"
        elif in_live and in_2025_bible:
            universe_status = "LIVE_2026_AND_2025_BIBLE"
            cause = "CONTINUITY"
        elif c in db_rows and c not in live_by_code:
            universe_status = "DATABASE_NOT_IN_LIVE_TABLE"
            cause = "DATABASE_REFERENCE_OR_ARCHIVE_REVIEW"
        else:
            universe_status = "BIBLE_HISTORICAL_ONLY"
            cause = "HISTORICAL_LIBRARY"
        rows.append(
            {
                "hunt_code": c,
                "universe_status": universe_status,
                "likely_cause": cause,
                "prefix": c[:2],
                "present_in_bible_years": "|".join(present_years),
                "present_in_2025_bible": "yes" if in_2025_bible else "no",
                "present_in_2026_bible": "yes" if in_2026_bible else "no",
                "present_in_live_2026_hunttable": "yes" if in_live else "no",
                "present_in_database": "yes" if c in db_rows else "no",
                "hanumber_fetch_status": hanumber.get("fetch_status", ""),
                "live_presence_status": compare.get("presence_status", ""),
                "live_comparison_status": compare.get("comparison_status", ""),
                "live_shape_status": compare.get("live_shape_status", ""),
                "hunt_name": live.get("hunt_name") or db.get("hunt_name") or "",
                "species": live.get("species") or db.get("species") or "",
                "sex_type": live.get("sex_type") or db.get("sex_type") or "",
                "weapon": live.get("weapon") or db.get("weapon") or "",
                "hunt_type": live.get("hunt_type") or db.get("hunt_type") or "",
                "live_res": compare.get("live_res", ""),
                "live_nr": compare.get("live_nr", ""),
                "live_total": compare.get("live_total", ""),
                "database_compared_res": compare.get("database_compared_res", ""),
                "database_compared_nr": compare.get("database_compared_nr", ""),
                "database_compared_total": compare.get("database_compared_total", ""),
                "source_url": live.get("source_url", ""),
            }
        )

    fields = [
        "hunt_code",
        "universe_status",
        "likely_cause",
        "prefix",
        "present_in_bible_years",
        "present_in_2025_bible",
        "present_in_2026_bible",
        "present_in_live_2026_hunttable",
        "present_in_database",
        "hanumber_fetch_status",
        "live_presence_status",
        "live_comparison_status",
        "live_shape_status",
        "hunt_name",
        "species",
        "sex_type",
        "weapon",
        "hunt_type",
        "live_res",
        "live_nr",
        "live_total",
        "database_compared_res",
        "database_compared_nr",
        "database_compared_total",
        "source_url",
    ]
    write_csv(OUT_CSV, rows, fields)

    year_counts = {
        str(year): {
            "row_count": len(read_csv(BIBLE_DIR / f"bible_hunt_code_year_document_{year}.csv")),
            "unique_hunt_codes": len(codes),
        }
        for year, codes in bible.items()
    }
    status_counts = Counter(r["universe_status"] for r in rows)
    cause_counts = Counter(r["likely_cause"] for r in rows if r["universe_status"] == "LIVE_2026_NOT_IN_2025_BIBLE")
    live_not_2025 = [r for r in rows if r["universe_status"] == "LIVE_2026_NOT_IN_2025_BIBLE"]
    bible_2025_not_live = [r for r in rows if r["universe_status"] == "BIBLE_2025_NOT_IN_LIVE_2026_TABLE"]
    summary = {
        "created_at_utc": timestamp,
        "bible_year_counts": year_counts,
        "live_2026_hunttable_unique_codes": len(live_by_code),
        "database_unique_codes": len(db_rows),
        "hanumber_codes_fetched_from_database_list": len(hanumber_rows),
        "important_interpretation": "HaNumber success is not active-code proof; it is popup resolution for the submitted database hunt-code list.",
        "universe_status_counts": dict(sorted(status_counts.items())),
        "live_2026_not_2025_bible_count": len(live_not_2025),
        "live_2026_not_2025_bible_likely_cause_counts": dict(sorted(cause_counts.items())),
        "bible_2025_not_live_2026_table_count": len(bible_2025_not_live),
        "bible_2025_not_live_2026_table_codes": [r["hunt_code"] for r in bible_2025_not_live],
        "outputs": {
            "csv": OUT_CSV.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Audit only. DATABASE.csv was not modified.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Current 2026 Live Hunt-Code Universe Vs BIBLE Year Documents",
        "",
        "## Interpretation",
        "",
        "`HaNumber` resolving a code does not prove the code is an active 2026 hunt. It proves the popup endpoint returned data for the submitted hunt-code list. The active current-table universe should be based on `HuntTableData` plus reviewed source context.",
        "",
        "The 2026 BIBLE document currently has only 31 rows, so the correct adjacent historical comparison for the 2026 model/current-year question is primarily the 2025 BIBLE draw-results document.",
        "",
        "## Key Counts",
        "",
        f"- 2025 BIBLE unique hunt codes: `{year_counts['2025']['unique_hunt_codes']}`",
        f"- 2026 BIBLE unique hunt codes currently structured: `{year_counts['2026']['unique_hunt_codes']}`",
        f"- Fresh DWR Hunt Planner table unique hunt codes: `{len(live_by_code)}`",
        f"- DATABASE unique hunt codes: `{len(db_rows)}`",
        f"- HaNumber popup rows fetched from DATABASE list: `{len(hanumber_rows)}`",
        "",
        "## Live 2026 Codes Not In 2025 BIBLE",
        "",
        f"- Count: `{len(live_not_2025)}`",
    ]
    for cause, count in sorted(cause_counts.items()):
        lines.append(f"- `{cause}`: `{count}`")
    lines.extend(
        [
            "",
            "## 2025 BIBLE Codes Not In Fresh 2026 Live Table",
            "",
            f"- Count: `{len(bible_2025_not_live)}`",
            "- Codes: "
            + (", ".join(f"`{r['hunt_code']}`" for r in bible_2025_not_live) if bible_2025_not_live else "`none`"),
            "",
            "## Output",
            "",
            f"- Detail CSV: `{OUT_CSV.relative_to(ROOT).as_posix()}`",
            f"- Summary JSON: `{OUT_SUMMARY.relative_to(ROOT).as_posix()}`",
        ]
    )
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
