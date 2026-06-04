"""Pull 2026 UtahDraws draw-odds JSON and regenerate CSV extracts.

This is a source snapshot only. It does not modify DATABASE.csv or promote
draw-result values as current permit truth.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
YEAR = 2026
JSON_DIR = ROOT / "pipeline/RAW/hunt_unit_database/2026/json/utahdraws_draw_odds_20260603"
CSV_DIR = ROOT / "pipeline/RAW/hunt_unit_database/2026/exports/utahdraws_draw_odds_20260603/csv"
SUPPLEMENT_URL = "https://www.utahdraws.com/internetsales/Home/DrawOddsSupplementData"
DATA_URL = "https://www.utahdraws.com/internetsales/Home/DrawOddsData"

REQUEST_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.utahdraws.com/internetsales/Home/DrawOdds",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
}

HUNT_FIELDS = [
    "HuntID",
    "HuntCode",
    "HuntName",
    "HuntCategoryName",
    "SpeciesSubtypeName",
    "MasterHuntTypeID",
    "SeasonWeapons",
    "QuotaQuantity",
    "ResidentQuotaQuantity",
    "NonResidentQuotaQuantity",
    "RegularRoundQuota",
    "MaxPointRoundQuota",
    "ResidentRegularRoundQuota",
    "ResidentMaxPointRoundQuota",
    "NonResidentRegularRoundQuota",
    "NonResidentMaxPointRoundQuota",
    "YouthQuotaQuantity",
    "ResidentYouthQuotaQuantity",
    "NonResidentYouthQuotaQuantity",
    "YouthRegularRoundQuota",
    "YouthMaxPointRoundQuota",
    "PointCalculationTypeID",
    "IsBonusPoint",
    "IsMultiseasonHunt",
    "QuotaFromArea",
    "ActiveDH",
    "HuntMapURL",
]

ODDS_FIELDS = [
    "ResidencyTypeID",
    "residency_label",
    "IsYouth",
    "Point",
    "PreferencePoint",
    "ParticipantCount",
    "SuccessfulCount",
    "AllChoicesSuccessfulCount",
    "SuccessfulByMaxPointRoundCount",
    "SuccessfulByRegularRoundCount",
    "AllChoicesSuccessfulByMaxPointRoundCount",
    "AllChoicesSuccessfulByRegularRoundCount",
    "SuccessfulByLifetimeCount",
    "HideSuccessfulByMaxPointRoundCount",
    "HideSuccessfulByRegularRoundCount",
    "IsHistoricalData",
    "BreakoutNonResidentRegularRoundQuota",
    "BreakoutNonResidentYouthQuota",
    "BreakoutResidentRegularRoundQuota",
    "BreakoutResidentYouthQuota",
    "BreakoutYouthQuota",
    "ConvertedYouthQuota",
    "YouthNonResidentMaxPointRoundQuota",
    "YouthNonResidentRegularRoundQuota",
    "YouthQuotaPercentage",
    "YouthResidentMaxPointRoundQuota",
    "YouthResidentRegularRoundQuota",
]


def slug(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "unknown"


def fetch_bytes(url: str) -> tuple[int, str, bytes]:
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=60) as response:
        return response.status, response.headers.get("content-type", ""), response.read()


def write_json(path: Path, data: object) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def csv_value(value: object) -> object:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "" if value is None else value


def residency_label(value: object) -> str:
    text = str(value or "").strip()
    if text == "1":
        return "Resident"
    if text == "2":
        return "Nonresident"
    return text


def flatten_rows(data: dict[str, object], source_json_file: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    hunts = data.get("Data") if isinstance(data, dict) else []
    if not isinstance(hunts, list):
        return rows
    for hunt in hunts:
        if not isinstance(hunt, dict):
            continue
        base = {field: csv_value(hunt.get(field, "")) for field in HUNT_FIELDS}
        odds_list = hunt.get("OddsList")
        if not isinstance(odds_list, list) or not odds_list:
            row = {**base}
            for field in ODDS_FIELDS:
                row[field] = ""
            row["source_json_file"] = source_json_file
            rows.append(row)
            continue
        for odds in odds_list:
            if not isinstance(odds, dict):
                continue
            row = {**base}
            for field in ODDS_FIELDS:
                if field == "residency_label":
                    row[field] = residency_label(odds.get("ResidencyTypeID"))
                else:
                    row[field] = csv_value(odds.get(field, ""))
            row["source_json_file"] = source_json_file
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = [*HUNT_FIELDS, *ODDS_FIELDS, "source_json_file"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def endpoint_url(draw_name: str, license_year: int, master_hunt_type_id: int) -> str:
    return DATA_URL + "?" + urllib.parse.urlencode(
        {
            "drawName": draw_name,
            "licenseYear": license_year,
            "masterHuntTypeID": master_hunt_type_id,
        }
    )


def main() -> int:
    fetched_at = datetime.now(timezone.utc).isoformat()
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)

    supplement_status, supplement_content_type, supplement_payload = fetch_bytes(SUPPLEMENT_URL)
    supplement = json.loads(supplement_payload.decode("utf-8-sig"))
    supplement_path = JSON_DIR / "draw_odds_supplement_data.json"
    supplement_path.write_bytes(supplement_payload)

    endpoints = [
        row
        for row in supplement.get("Data", {}).get("DrawNameAvailableLicenseYears", [])
        if int(row.get("LicenseYear") or 0) == YEAR
    ]

    manifest_rows: list[dict[str, object]] = []
    total_hunts = 0
    total_odds_rows = 0
    total_bytes = len(supplement_payload)
    failed = 0
    sportsman_rows: list[dict[str, object]] = []

    for endpoint in endpoints:
        draw_name = str(endpoint.get("DrawName") or "")
        master_id = int(endpoint.get("MasterHuntTypeID") or 0)
        master_name = str(endpoint.get("MasterHuntTypeName") or "")
        url = endpoint_url(draw_name, YEAR, master_id)
        file_stem = f"{YEAR}_{slug(draw_name)}_{master_id:02d}_{slug(master_name)}"
        json_file = JSON_DIR / f"{file_stem}.json"
        csv_file = CSV_DIR / f"{file_stem}.csv"
        error = ""
        status = ""
        content_type = ""
        api_status = ""
        rows_returned = 0
        odds_rows_returned = 0
        sha256 = ""
        size_bytes = 0
        download_status = "OK"
        try:
            status, content_type, payload = fetch_bytes(url)
            data = json.loads(payload.decode("utf-8-sig"))
            payload = write_json(json_file, data)
            flat_rows = flatten_rows(data, json_file.name)
            write_csv(csv_file, flat_rows)
            hunts = data.get("Data", []) if isinstance(data, dict) else []
            rows_returned = len(hunts) if isinstance(hunts, list) else 0
            odds_rows_returned = len(flat_rows)
            api_status = data.get("Status", "") if isinstance(data, dict) else ""
            sha256 = hashlib.sha256(payload).hexdigest()
            size_bytes = len(payload)
            total_hunts += rows_returned
            total_odds_rows += odds_rows_returned
            total_bytes += size_bytes
            if draw_name.lower() == "sportsman":
                sportsman_rows.extend(flat_rows)
        except Exception as exc:  # keep manifest evidence for failed endpoint
            failed += 1
            download_status = "ERROR"
            error = str(exc)

        manifest_rows.append(
            {
                "draw_name": draw_name,
                "license_year": YEAR,
                "master_hunt_type_id": master_id,
                "master_hunt_type_name": master_name,
                "hunt_count_advertised": endpoint.get("HuntCount", ""),
                "draw_odds_calculation_split_residency": endpoint.get("DrawOddsCalculationSplitResidency", ""),
                "draw_odds_calculation_split_youth": endpoint.get("DrawOddsCalculationSplitYouth", ""),
                "source_url": url,
                "output_file": json_file.relative_to(ROOT).as_posix(),
                "fetched_at_utc": fetched_at,
                "http_status": status,
                "content_type": content_type,
                "api_status": api_status,
                "records_returned": rows_returned,
                "odds_rows_returned": odds_rows_returned,
                "size_bytes": size_bytes,
                "sha256": sha256,
                "download_status": download_status,
                "error": error,
            }
        )

    if sportsman_rows:
        write_csv(CSV_DIR / f"{YEAR}_sportsman_all.csv", sportsman_rows)

    manifest_fields = [
        "draw_name",
        "license_year",
        "master_hunt_type_id",
        "master_hunt_type_name",
        "hunt_count_advertised",
        "draw_odds_calculation_split_residency",
        "draw_odds_calculation_split_youth",
        "source_url",
        "output_file",
        "fetched_at_utc",
        "http_status",
        "content_type",
        "api_status",
        "records_returned",
        "odds_rows_returned",
        "size_bytes",
        "sha256",
        "download_status",
        "error",
    ]
    with (JSON_DIR / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=manifest_fields)
        writer.writeheader()
        writer.writerows(manifest_rows)

    summary = {
        "fetched_at_utc": fetched_at,
        "supplement_url": SUPPLEMENT_URL,
        "supplement_file": supplement_path.relative_to(ROOT).as_posix(),
        "supplement_http_status": supplement_status,
        "supplement_content_type": supplement_content_type,
        "supplement_sha256": hashlib.sha256(supplement_payload).hexdigest(),
        "available_endpoint_count": len(endpoints),
        "downloaded_endpoint_count": len([r for r in manifest_rows if r["download_status"] == "OK"]),
        "failed_endpoint_count": failed,
        "total_hunt_records_returned": total_hunts,
        "total_odds_rows_returned": total_odds_rows,
        "total_bytes": total_bytes,
        "output_directory": JSON_DIR.relative_to(ROOT).as_posix(),
    }
    (JSON_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
