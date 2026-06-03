"""Extract and confirm as many 2026 permit numbers as DWR Hunt Planner exposes.

This is a confirmation audit only. It snapshots reviewed DWR HuntTableData
endpoints, compares by hunt_code to canonical DATABASE.csv, and does not modify
DATABASE.csv.
"""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
RAW_OUT = ROOT / "data_truth/crosswalk_truth/raw_inventory/live_dwr_hunt_planner_permit_numbers_comprehensive_2026.csv"
COMPARE_OUT = ROOT / "data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.csv"
SUMMARY_OUT = ROOT / "data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026_summary.json"
REPORT_OUT = ROOT / "processed_data/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.md"

REQUEST_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://dwrapps.utah.gov/huntboundary/hbstart",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
}

# These are the DWR endpoint gender labels that currently return permit tables.
# Some database labels intentionally map to DWR aliases, e.g. sheep "Ram" rows
# are exposed by DWR as "Male Only".
LIVE_ENDPOINTS = [
    ("Bison", "Hunters Choice"),
    ("Black Bear", "Either Sex"),
    ("Cougar", "Either Sex"),
    ("Deer", "Antlerless"),
    ("Deer", "Buck"),
    ("Deer", "Hunters Choice"),
    ("Desert Bighorn Sheep", "Male Only"),
    ("Elk", "Antlerless"),
    ("Elk", "Bull"),
    ("Elk", "Hunters Choice"),
    ("Moose", "Antlerless"),
    ("Moose", "Bull"),
    ("Mountain Goat", "Hunters Choice"),
    ("Pronghorn", "Buck"),
    ("Pronghorn", "Doe"),
    ("Rocky Mountain Bighorn Sheep", "Ewe"),
    ("Rocky Mountain Bighorn Sheep", "Male Only"),
    ("Turkey", "Bearded"),
    ("Turkey", "Either Sex"),
]
TOTAL_ONLY_TYPES = {
    "CWMU",
    "Private Lands Only",
    "Conservation",
    "Expo",
    "Antlerless Elk Control",
    "General Season - Youth",
    "Statewide",
}


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\ufeff", "")
    text = re.sub(r"\s+", " ", text).strip()
    return "" if text in {"", "-", "nan", "None"} else text


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return ""
    return str(int(number)) if number.is_integer() else str(number)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def endpoint_url(species: str, gender: str) -> str:
    return "https://dwrapps.utah.gov/huntboundary/HuntTableData?" + urllib.parse.urlencode(
        {"species": species, "gender": gender}
    )


def fetch_json(source_url: str) -> object:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urlopen(Request(source_url, headers=REQUEST_HEADERS), timeout=30) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2 * attempt)
    raise RuntimeError(f"Unable to fetch DWR HuntTableData after retries: {source_url}") from last_error


def fetch_live_rows(timestamp: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    endpoint_rows: list[dict[str, object]] = []
    for species, gender in LIVE_ENDPOINTS:
        source_url = endpoint_url(species, gender)
        payload = fetch_json(source_url)
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected DWR payload for {source_url}")
        endpoint_rows.append(
            {
                "source_url": source_url,
                "endpoint_species": species,
                "endpoint_gender": gender,
                "row_count": len(payload),
            }
        )
        for row in payload:
            rows.append(
                {
                    "snapshot_utc": timestamp,
                    "source_url": source_url,
                    "endpoint_species": species,
                    "endpoint_gender": gender,
                    "hunt_code": clean(row.get("HUNT_NBR")).upper(),
                    "hunt_name": clean(row.get("HUNT_NAME")),
                    "species": clean(row.get("SPECIES")) or species,
                    "sex_type": clean(row.get("GENDER")) or gender,
                    "weapon": clean(row.get("WEAPON")),
                    "hunt_type": clean(row.get("HUNT_TYPE")),
                    "season": clean(row.get("SEASON_DATE_TEXT")),
                    "live_res": int_text(row.get("QUOTA_RES")),
                    "live_nr": int_text(row.get("QUOTA_NRES")),
                    "live_total": int_text(row.get("QUOTA")),
                }
            )
        time.sleep(0.1)
    return rows, endpoint_rows


def live_shape(row: dict[str, object]) -> tuple[str, str, str, str]:
    hunt_type = clean(row.get("hunt_type"))
    live_res = int_text(row.get("live_res"))
    live_nr = int_text(row.get("live_nr"))
    live_total = int_text(row.get("live_total"))
    if hunt_type == "CWMU":
        total = live_res if live_res not in {"", "0"} else live_total
        return "", "", total, "LIVE_DWR_CWMU_TOTAL_ONLY_FROM_QUOTA_RES"
    if hunt_type in TOTAL_ONLY_TYPES:
        total = live_total or live_res
        if total in {"", "0"}:
            return "", "", "", "LIVE_DWR_NO_QUOTA_PUBLISHED"
        return "", "", total, "LIVE_DWR_TOTAL_ONLY"
    if live_total in {"", "0"} and live_res in {"", "0"} and live_nr in {"", "0"}:
        return "", "", "", "LIVE_DWR_NO_QUOTA_PUBLISHED"
    if live_total in {"", "0"} and (live_res not in {"", "0"} or live_nr not in {"", "0"}):
        live_total = str(int(live_res or 0) + int(live_nr or 0))
    if live_total not in {"", "0"} and live_res in {"", "0"} and live_nr in {"", "0"}:
        return "", "", live_total, "LIVE_DWR_TOTAL_ONLY"
    if live_res not in {"", "0"} and live_total and live_nr in {"", "0"} and int(live_total) > int(live_res):
        live_nr = str(int(live_total) - int(live_res))
    return live_res, live_nr, live_total, "LIVE_DWR_RES_NR_SPLIT"


def db_triple(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        int_text(row.get("permits_2026_res")),
        int_text(row.get("permits_2026_nr")),
        int_text(row.get("permits_2026_total")),
    )


def allotment_triple(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        int_text(row.get("permit_allotment_2026_res")),
        int_text(row.get("permit_allotment_2026_nr")),
        int_text(row.get("permit_allotment_2026_total")),
    )


def compare_triple(live: tuple[str, str, str], database: tuple[str, str, str]) -> str:
    if not any(live) and not any(database):
        return "BOTH_BLANK"
    if any(live) and not any(database):
        return "LIVE_HAS_NUMERIC_DATABASE_BLANK"
    if any(database) and not any(live):
        return "DATABASE_HAS_NUMERIC_LIVE_BLANK"
    if live == database:
        return "MATCH"
    if live[2] and database[2] and live[2] == database[2]:
        return "TOTAL_MATCH_SPLIT_DIFFERS"
    return "NUMERIC_MISMATCH"


def compare(live_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    live_by_code = {clean(row.get("hunt_code")): row for row in live_rows if row.get("hunt_code")}
    db_by_code = {clean(row.get("hunt_code")): row for row in read_csv(DATABASE) if row.get("hunt_code")}
    rows: list[dict[str, object]] = []
    for code in sorted(set(live_by_code) | set(db_by_code)):
        live = live_by_code.get(code, {})
        db = db_by_code.get(code, {})
        live_res, live_nr, live_total, live_shape_status = ("", "", "", "")
        if live:
            live_res, live_nr, live_total, live_shape_status = live_shape(live)
        permits = db_triple(db)
        allotment = allotment_triple(db)
        compared = permits if any(permits) else allotment
        compare_source = "DATABASE.permits_2026" if any(permits) else ("DATABASE.permit_allotment_2026" if any(allotment) else "")
        if live and db:
            presence_status = "LIVE_AND_DATABASE"
        elif live:
            presence_status = "LIVE_ONLY"
        else:
            presence_status = "DATABASE_ONLY"
        if live and db and live_shape_status == "LIVE_DWR_NO_QUOTA_PUBLISHED":
            comparison_status = "LIVE_NO_QUOTA_DATABASE_PRESERVED" if any(compared) else "BOTH_BLANK"
        elif live and db:
            comparison_status = compare_triple((live_res, live_nr, live_total), compared)
        else:
            comparison_status = presence_status
        rows.append(
            {
                "hunt_code": code,
                "presence_status": presence_status,
                "comparison_status": comparison_status,
                "live_shape_status": live_shape_status,
                "database_compare_source": compare_source,
                "source_url": live.get("source_url", ""),
                "endpoint_species": live.get("endpoint_species", ""),
                "endpoint_gender": live.get("endpoint_gender", ""),
                "live_hunt_name": live.get("hunt_name", ""),
                "database_hunt_name": db.get("hunt_name", ""),
                "live_species": live.get("species", ""),
                "database_species": db.get("species", ""),
                "live_sex_type": live.get("sex_type", ""),
                "database_sex_type": db.get("sex_type", ""),
                "live_weapon": live.get("weapon", ""),
                "database_weapon": db.get("weapon", ""),
                "live_hunt_type": live.get("hunt_type", ""),
                "database_hunt_type": db.get("hunt_type", ""),
                "live_season": live.get("season", ""),
                "database_season": db.get("season", ""),
                "live_raw_res": int_text(live.get("live_res")),
                "live_raw_nr": int_text(live.get("live_nr")),
                "live_raw_total": int_text(live.get("live_total")),
                "live_res": live_res,
                "live_nr": live_nr,
                "live_total": live_total,
                "database_res": permits[0],
                "database_nr": permits[1],
                "database_total": permits[2],
                "database_allotment_res": allotment[0],
                "database_allotment_nr": allotment[1],
                "database_allotment_total": allotment[2],
                "database_compared_res": compared[0],
                "database_compared_nr": compared[1],
                "database_compared_total": compared[2],
                "database_source": db.get("permits_2026_source", ""),
                "database_allotment_source": db.get("permit_allotment_2026_source", ""),
                "database_allotment_status": db.get("permit_allotment_2026_status", ""),
            }
        )
    return rows


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    live_rows, endpoint_rows = fetch_live_rows(timestamp)
    compare_rows = compare(live_rows)

    raw_fields = [
        "snapshot_utc",
        "source_url",
        "endpoint_species",
        "endpoint_gender",
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "weapon",
        "hunt_type",
        "season",
        "live_res",
        "live_nr",
        "live_total",
    ]
    compare_fields = [
        "hunt_code",
        "presence_status",
        "comparison_status",
        "live_shape_status",
        "database_compare_source",
        "source_url",
        "endpoint_species",
        "endpoint_gender",
        "live_hunt_name",
        "database_hunt_name",
        "live_species",
        "database_species",
        "live_sex_type",
        "database_sex_type",
        "live_weapon",
        "database_weapon",
        "live_hunt_type",
        "database_hunt_type",
        "live_season",
        "database_season",
        "live_raw_res",
        "live_raw_nr",
        "live_raw_total",
        "live_res",
        "live_nr",
        "live_total",
        "database_res",
        "database_nr",
        "database_total",
        "database_allotment_res",
        "database_allotment_nr",
        "database_allotment_total",
        "database_compared_res",
        "database_compared_nr",
        "database_compared_total",
        "database_source",
        "database_allotment_source",
        "database_allotment_status",
    ]
    write_csv(RAW_OUT, live_rows, raw_fields)
    write_csv(COMPARE_OUT, compare_rows, compare_fields)

    status_counts = Counter(row["comparison_status"] for row in compare_rows)
    presence_counts = Counter(row["presence_status"] for row in compare_rows)
    shape_counts = Counter(row["live_shape_status"] for row in compare_rows if row["live_shape_status"])
    endpoint_counts = {f"{row['endpoint_species']}|{row['endpoint_gender']}": row["row_count"] for row in endpoint_rows}
    numeric_mismatches = [row for row in compare_rows if row["comparison_status"] == "NUMERIC_MISMATCH"]
    live_numeric_db_blank = [row for row in compare_rows if row["comparison_status"] == "LIVE_HAS_NUMERIC_DATABASE_BLANK"]
    db_numeric_live_blank = [row for row in compare_rows if row["comparison_status"] == "DATABASE_HAS_NUMERIC_LIVE_BLANK"]
    database_only = [row for row in compare_rows if row["presence_status"] == "DATABASE_ONLY"]
    live_only = [row for row in compare_rows if row["presence_status"] == "LIVE_ONLY"]

    summary = {
        "artifact": "live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026",
        "snapshot_utc": timestamp,
        "endpoint_count": len(endpoint_rows),
        "endpoint_row_counts": endpoint_counts,
        "live_row_count": len(live_rows),
        "live_unique_hunt_code_count": len({row["hunt_code"] for row in live_rows if row.get("hunt_code")}),
        "database_row_count": len(read_csv(DATABASE)),
        "comparison_row_count": len(compare_rows),
        "presence_counts": dict(sorted(presence_counts.items())),
        "comparison_status_counts": dict(sorted(status_counts.items())),
        "live_shape_status_counts": dict(sorted(shape_counts.items())),
        "numeric_mismatch_count": len(numeric_mismatches),
        "numeric_mismatch_codes": [str(row["hunt_code"]) for row in numeric_mismatches[:200]],
        "live_numeric_database_blank_count": len(live_numeric_db_blank),
        "live_numeric_database_blank_codes": [str(row["hunt_code"]) for row in live_numeric_db_blank[:200]],
        "database_numeric_live_blank_count": len(db_numeric_live_blank),
        "database_numeric_live_blank_codes": [str(row["hunt_code"]) for row in db_numeric_live_blank[:200]],
        "database_only_count": len(database_only),
        "database_only_codes": [str(row["hunt_code"]) for row in database_only[:250]],
        "live_only_count": len(live_only),
        "live_only_codes": [str(row["hunt_code"]) for row in live_only[:250]],
        "guardrail": "Comprehensive DWR website extraction is confirmation evidence only and does not modify DATABASE.csv. DWR no-quota rows preserve reviewed database-entered values.",
        "outputs": {
            "raw_csv": RAW_OUT.relative_to(ROOT).as_posix(),
            "comparison_csv": COMPARE_OUT.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY_OUT.relative_to(ROOT).as_posix(),
            "report_md": REPORT_OUT.relative_to(ROOT).as_posix(),
        },
    }
    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Comprehensive Live DWR Permit Numbers Vs DATABASE 2026",
        "",
        f"- Snapshot UTC: `{timestamp}`",
        f"- DWR endpoints queried: `{len(endpoint_rows)}`",
        f"- Live rows extracted: `{len(live_rows)}`",
        f"- Live unique hunt codes: `{summary['live_unique_hunt_code_count']}`",
        f"- DATABASE rows compared: `{summary['database_row_count']}`",
        f"- Numeric mismatches: `{len(numeric_mismatches)}`",
        f"- Live numeric / database blank: `{len(live_numeric_db_blank)}`",
        f"- Database numeric / live blank: `{len(db_numeric_live_blank)}`",
        f"- Database-only rows not exposed by queried DWR endpoints: `{len(database_only)}`",
        f"- Live-only rows not in DATABASE: `{len(live_only)}`",
        "",
        "## Comparison Status Counts",
        "",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "## Endpoint Row Counts", ""])
    for key, count in sorted(endpoint_counts.items()):
        lines.append(f"- `{key}`: `{count}`")
    if numeric_mismatches:
        lines.extend(["", "## Numeric Mismatch Codes", ""])
        for row in numeric_mismatches[:100]:
            lines.append(
                f"- `{row['hunt_code']}` {row['database_hunt_name'] or row['live_hunt_name']}: "
                f"live `{row['live_res']}/{row['live_nr']}/{row['live_total']}` vs "
                f"database `{row['database_compared_res']}/{row['database_compared_nr']}/{row['database_compared_total']}`"
            )
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
