"""Deep-pull allowed Utah draw-odds raw sources into repo staging.

Scope is intentionally narrow:
- Big Game, including antlerless, from UtahDraws current-year data and the
  official historical big-game odds page.
- Cougar, turkey, and black bear from the official odds page.
- No wetland files and no non-turkey upland files.

This script writes only repo-side raw-source snapshots, manifests, and compact
flat extracts. It does not build truth-vs-prediction comparables.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
YEAR = 2026

CURRENT_UTAHDRAWS_URL = (
    "https://www.utahdraws.com/internetsales/home/drawodds"
    "?drawPackage=Big+Game&youth=false&licenseYear=2026"
)
BIGGAME_ODDS_URL = "https://wildlife.utah.gov/biggame/odds"
BEAR_COUGAR_TURKEY_ODDS_URL = "https://wildlife.utah.gov/odds#bearReports"
UTAHDRAWS_SUPPLEMENT_URL = "https://www.utahdraws.com/internetsales/Home/DrawOddsSupplementData"
UTAHDRAWS_DATA_URL = "https://www.utahdraws.com/internetsales/Home/DrawOddsData"

REQUEST_HEADERS = {
    "Accept": "text/html,application/pdf,application/json,text/plain,*/*",
    "Referer": "https://www.utahdraws.com/internetsales/home/drawodds",
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


@dataclass(frozen=True)
class Link:
    source_page: str
    text: str
    href: str
    url: str


class LinkParser(HTMLParser):
    def __init__(self, base_url: str, source_page: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.source_page = source_page
        self.links: list[Link] = []
        self._href_stack: list[str] = []
        self._text_stack: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {name.lower(): value for name, value in attrs}
        href = attr_map.get("href")
        if not href:
            return
        self._href_stack.append(href)
        self._text_stack.append([])

    def handle_data(self, data: str) -> None:
        if self._text_stack:
            self._text_stack[-1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href_stack:
            return
        href = self._href_stack.pop()
        text = clean_text(" ".join(self._text_stack.pop()))
        url = urllib.parse.urljoin(self.base_url, href)
        self.links.append(Link(self.source_page, text, href, url))


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def slug(value: object) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "unknown"


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def fetch_bytes(url: str, accept: str | None = None) -> tuple[int, str, bytes]:
    headers = dict(REQUEST_HEADERS)
    if accept:
        headers["Accept"] = accept
    request = Request(url, headers=headers)
    with urlopen(request, timeout=90) as response:
        return response.status, response.headers.get("content-type", ""), response.read()


def write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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


def flatten_utahdraws_rows(data: dict[str, object], source_json_file: str) -> list[dict[str, object]]:
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
            row = dict(base)
            for field in ODDS_FIELDS:
                row[field] = ""
            row["source_json_file"] = source_json_file
            rows.append(row)
            continue
        for odds in odds_list:
            if not isinstance(odds, dict):
                continue
            row = dict(base)
            for field in ODDS_FIELDS:
                if field == "residency_label":
                    row[field] = residency_label(odds.get("ResidencyTypeID"))
                else:
                    row[field] = csv_value(odds.get(field, ""))
            row["source_json_file"] = source_json_file
            rows.append(row)
    return rows


def endpoint_url(draw_name: str, license_year: int, master_hunt_type_id: int) -> str:
    return UTAHDRAWS_DATA_URL + "?" + urllib.parse.urlencode(
        {
            "drawName": draw_name,
            "licenseYear": license_year,
            "masterHuntTypeID": master_hunt_type_id,
        }
    )


def classify_utahdraws_endpoint(endpoint: dict[str, Any]) -> tuple[bool, str, str]:
    draw_name = clean_text(endpoint.get("DrawName"))
    master_name = clean_text(endpoint.get("MasterHuntTypeName"))
    haystack = f"{draw_name} {master_name}".lower()
    if "wetland" in haystack or "waterfowl" in haystack:
        return False, "excluded_wetland_or_waterfowl", "wetland_or_waterfowl"
    if "upland" in haystack and "turkey" not in haystack:
        return False, "excluded_non_turkey_upland", "non_turkey_upland"
    if draw_name.lower() == "big game":
        if "antlerless" in haystack:
            return True, "included_big_game_antlerless", "big_game_antlerless"
        return True, "included_big_game", "big_game"
    if draw_name.lower() in {"black bear", "bear"}:
        return True, "included_black_bear", "black_bear"
    if draw_name.lower() == "cougar":
        return True, "included_cougar", "cougar"
    if draw_name.lower() == "turkey":
        return True, "included_turkey", "turkey"
    if draw_name.lower() == "sportsman":
        allowed_sportsman_terms = {
            "deer",
            "elk",
            "pronghorn",
            "moose",
            "bison",
            "sheep",
            "goat",
            "bear",
            "turkey",
        }
        if any(term in haystack for term in allowed_sportsman_terms):
            if "turkey" in haystack:
                return True, "included_sportsman_turkey", "sportsman_turkey"
            if "bear" in haystack:
                return True, "included_sportsman_black_bear", "sportsman_black_bear"
            return True, "included_sportsman_big_game", "sportsman_big_game"
    return False, "excluded_not_allowed_species_or_draw_package", "not_allowed"


def parse_links(html: bytes, base_url: str, source_page: str) -> list[Link]:
    parser = LinkParser(base_url, source_page)
    parser.feed(html.decode("utf-8", errors="replace"))
    return parser.links


def pdf_category_from_link(link: Link) -> tuple[bool, str, str]:
    parsed = urllib.parse.urlparse(link.url)
    path = parsed.path.lower()
    text = link.text.lower()
    haystack = f"{text} {path}"
    if not path.endswith(".pdf"):
        return False, "excluded_not_pdf", "not_pdf"
    if "waterfowl" in haystack or "wetland" in haystack:
        return False, "excluded_wetland_or_waterfowl", "wetland_or_waterfowl"
    if "/pdf/bg/" in path:
        if any(term in haystack for term in ("harvest", "guidebook", "guide-book", "proc")):
            return False, "excluded_big_game_not_draw_odds", "big_game_non_odds"
        if any(
            term in haystack
            for term in (
                "draw",
                "drawing",
                "odds",
                "point",
                "points",
                "sportsman",
                "lifetime",
                "dedicated",
                "antlerless",
                "limited",
                "general",
                "buck",
                "bull",
                "big game",
            )
        ):
            if "antlerless" in haystack:
                return True, "included_big_game_antlerless_pdf", "big_game_antlerless"
            return True, "included_big_game_pdf", "big_game"
        return False, "excluded_big_game_unrecognized_pdf", "big_game_unrecognized"
    if "/pdf/bear/" in path:
        if "harvest" in haystack:
            return False, "excluded_bear_harvest_not_draw_odds", "bear_harvest"
        return True, "included_black_bear_pdf", "black_bear"
    if "/pdf/cougar/" in path:
        if "harvest" in haystack:
            return False, "excluded_cougar_harvest_not_draw_odds", "cougar_harvest"
        return True, "included_cougar_pdf", "cougar"
    if "/pdf/uplandgame/turkey/" in path:
        if "harvest" in haystack:
            return False, "excluded_turkey_harvest_not_draw_odds", "turkey_harvest"
        return True, "included_turkey_pdf", "turkey"
    if "/pdf/uplandgame/" in path:
        return False, "excluded_non_turkey_upland", "non_turkey_upland"
    return False, "excluded_not_allowed_pdf_scope", "not_allowed"


def unique_links(links: list[Link]) -> list[Link]:
    seen: set[str] = set()
    unique: list[Link] = []
    for link in links:
        normalized = urllib.parse.urldefrag(link.url)[0]
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(Link(link.source_page, link.text, link.href, normalized))
    return unique


def safe_pdf_path(root: Path, category: str, url: str) -> Path:
    parsed = urllib.parse.urlparse(url)
    parts = [slug(part) for part in parsed.path.split("/") if part]
    year_parts = [part for part in parts if re.fullmatch(r"20\d{2}", part)]
    year_part = year_parts[-1] if year_parts else "unknown_year"
    basename = Path(parsed.path).name or "source.pdf"
    basename = re.sub(r"[^A-Za-z0-9._-]+", "_", basename)
    if not basename.lower().endswith(".pdf"):
        basename += ".pdf"
    return root / "wildlife_pdfs" / category / year_part / basename


def download_pdf_links(
    links: list[Link],
    out_dir: Path,
    fetched_at_utc: str,
    manifest_rows: list[dict[str, object]],
    excluded_rows: list[dict[str, object]],
) -> tuple[int, int]:
    downloaded = 0
    errors = 0
    for link in unique_links(links):
        include, decision, category = pdf_category_from_link(link)
        row_base: dict[str, object] = {
            "source_kind": "official_pdf",
            "source_page": link.source_page,
            "link_text": link.text,
            "source_url": link.url,
            "scope_decision": decision,
            "category": category,
            "fetched_at_utc": fetched_at_utc,
        }
        if not include:
            excluded_rows.append(row_base)
            continue
        output_path = safe_pdf_path(out_dir, category, link.url)
        status = ""
        content_type = ""
        size_bytes = 0
        sha256 = ""
        error = ""
        download_status = "OK"
        try:
            status, content_type, payload = fetch_bytes(link.url, "application/pdf,*/*")
            write_bytes(output_path, payload)
            size_bytes = len(payload)
            sha256 = sha256_bytes(payload)
            downloaded += 1
            time.sleep(0.05)
        except Exception as exc:
            errors += 1
            download_status = "ERROR"
            error = str(exc)
        manifest_rows.append(
            {
                **row_base,
                "output_file": rel(output_path),
                "http_status": status,
                "content_type": content_type,
                "records_returned": "",
                "odds_rows_returned": "",
                "size_bytes": size_bytes,
                "sha256": sha256,
                "download_status": download_status,
                "error": error,
            }
        )
    return downloaded, errors


def pull_utahdraws_current(
    out_dir: Path,
    fetched_at_utc: str,
    manifest_rows: list[dict[str, object]],
    excluded_rows: list[dict[str, object]],
) -> tuple[int, int, int, int]:
    json_dir = out_dir / "utahdraws_2026" / "json"
    csv_dir = out_dir / "utahdraws_2026" / "csv"
    page_status, page_content_type, page_payload = fetch_bytes(CURRENT_UTAHDRAWS_URL, "text/html,*/*")
    page_path = out_dir / "source_pages" / "utahdraws_big_game_2026.html"
    write_bytes(page_path, page_payload)
    manifest_rows.append(
        {
            "source_kind": "source_page_html",
            "source_page": "utahdraws_2026_big_game",
            "link_text": "UtahDraws 2026 Big Game draw odds page",
            "source_url": CURRENT_UTAHDRAWS_URL,
            "scope_decision": "included_source_page",
            "category": "source_page",
            "output_file": rel(page_path),
            "fetched_at_utc": fetched_at_utc,
            "http_status": page_status,
            "content_type": page_content_type,
            "records_returned": "",
            "odds_rows_returned": "",
            "size_bytes": len(page_payload),
            "sha256": sha256_bytes(page_payload),
            "download_status": "OK",
            "error": "",
        }
    )

    supplement_status, supplement_content_type, supplement_payload = fetch_bytes(
        UTAHDRAWS_SUPPLEMENT_URL, "application/json,*/*"
    )
    supplement_path = json_dir / "draw_odds_supplement_data.json"
    write_bytes(supplement_path, supplement_payload)
    manifest_rows.append(
        {
            "source_kind": "utahdraws_supplement_json",
            "source_page": "utahdraws_supplement",
            "link_text": "UtahDraws DrawOddsSupplementData",
            "source_url": UTAHDRAWS_SUPPLEMENT_URL,
            "scope_decision": "included_current_year_endpoint_discovery",
            "category": "utahdraws_supplement",
            "output_file": rel(supplement_path),
            "fetched_at_utc": fetched_at_utc,
            "http_status": supplement_status,
            "content_type": supplement_content_type,
            "records_returned": "",
            "odds_rows_returned": "",
            "size_bytes": len(supplement_payload),
            "sha256": sha256_bytes(supplement_payload),
            "download_status": "OK",
            "error": "",
        }
    )
    supplement = json.loads(supplement_payload.decode("utf-8-sig"))
    endpoints = [
        row
        for row in supplement.get("Data", {}).get("DrawNameAvailableLicenseYears", [])
        if int(row.get("LicenseYear") or 0) == YEAR
    ]

    included = 0
    endpoint_errors = 0
    hunts_total = 0
    odds_rows_total = 0
    all_flat_rows: list[dict[str, object]] = []
    for endpoint in endpoints:
        include, decision, category = classify_utahdraws_endpoint(endpoint)
        draw_name = clean_text(endpoint.get("DrawName"))
        master_id = int(endpoint.get("MasterHuntTypeID") or 0)
        master_name = clean_text(endpoint.get("MasterHuntTypeName"))
        url = endpoint_url(draw_name, YEAR, master_id)
        row_base: dict[str, object] = {
            "source_kind": "utahdraws_draw_odds_json",
            "source_page": "utahdraws_supplement",
            "link_text": f"{draw_name} / {master_name}",
            "source_url": url,
            "scope_decision": decision,
            "category": category,
            "fetched_at_utc": fetched_at_utc,
            "hunt_count_advertised": endpoint.get("HuntCount", ""),
            "draw_name": draw_name,
            "license_year": YEAR,
            "master_hunt_type_id": master_id,
            "master_hunt_type_name": master_name,
        }
        if not include:
            excluded_rows.append(row_base)
            continue

        included += 1
        stem = f"{YEAR}_{slug(draw_name)}_{master_id:02d}_{slug(master_name)}"
        json_path = json_dir / f"{stem}.json"
        csv_path = csv_dir / f"{stem}.csv"
        status = ""
        content_type = ""
        size_bytes = 0
        sha256 = ""
        api_status = ""
        records_returned = 0
        odds_rows_returned = 0
        error = ""
        download_status = "OK"
        try:
            status, content_type, payload = fetch_bytes(url, "application/json,*/*")
            data = json.loads(payload.decode("utf-8-sig"))
            compact_payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            write_bytes(json_path, compact_payload)
            flat_rows = flatten_utahdraws_rows(data, json_path.name)
            write_csv(csv_path, flat_rows, [*HUNT_FIELDS, *ODDS_FIELDS, "source_json_file"])
            all_flat_rows.extend(flat_rows)
            hunts = data.get("Data", []) if isinstance(data, dict) else []
            records_returned = len(hunts) if isinstance(hunts, list) else 0
            odds_rows_returned = len(flat_rows)
            api_status = data.get("Status", "") if isinstance(data, dict) else ""
            size_bytes = len(compact_payload)
            sha256 = sha256_bytes(compact_payload)
            hunts_total += records_returned
            odds_rows_total += odds_rows_returned
            time.sleep(0.05)
        except Exception as exc:
            endpoint_errors += 1
            download_status = "ERROR"
            error = str(exc)
        manifest_rows.append(
            {
                **row_base,
                "output_file": rel(json_path),
                "csv_output_file": rel(csv_path),
                "http_status": status,
                "content_type": content_type,
                "api_status": api_status,
                "records_returned": records_returned,
                "odds_rows_returned": odds_rows_returned,
                "size_bytes": size_bytes,
                "sha256": sha256,
                "download_status": download_status,
                "error": error,
            }
        )

    combined_csv = csv_dir / "2026_allowed_draw_odds_all_flat_rows.csv"
    write_csv(combined_csv, all_flat_rows, [*HUNT_FIELDS, *ODDS_FIELDS, "source_json_file"])
    return included, endpoint_errors, hunts_total, odds_rows_total


def pull_official_pages(
    out_dir: Path,
    fetched_at_utc: str,
    manifest_rows: list[dict[str, object]],
    excluded_rows: list[dict[str, object]],
) -> tuple[int, int, int]:
    pages = [
        ("wildlife_biggame_odds", BIGGAME_ODDS_URL, "wildlife_biggame_odds.html"),
        ("wildlife_bear_cougar_turkey_odds", BEAR_COUGAR_TURKEY_ODDS_URL, "wildlife_bear_cougar_turkey_odds.html"),
    ]
    links: list[Link] = []
    for source_page, url, filename in pages:
        status, content_type, payload = fetch_bytes(url, "text/html,*/*")
        page_path = out_dir / "source_pages" / filename
        write_bytes(page_path, payload)
        manifest_rows.append(
            {
                "source_kind": "source_page_html",
                "source_page": source_page,
                "link_text": source_page,
                "source_url": url,
                "scope_decision": "included_source_page",
                "category": "source_page",
                "output_file": rel(page_path),
                "fetched_at_utc": fetched_at_utc,
                "http_status": status,
                "content_type": content_type,
                "records_returned": "",
                "odds_rows_returned": "",
                "size_bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "download_status": "OK",
                "error": "",
            }
        )
        links.extend(parse_links(payload, url, source_page))
    pdf_downloaded, pdf_errors = download_pdf_links(links, out_dir, fetched_at_utc, manifest_rows, excluded_rows)
    return len(links), pdf_downloaded, pdf_errors


def count_by(rows: list[dict[str, object]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(field) or "")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def write_report(
    out_dir: Path,
    fetched_at_utc: str,
    manifest_rows: list[dict[str, object]],
    excluded_rows: list[dict[str, object]],
    summary: dict[str, object],
) -> None:
    manifest_path = out_dir / "DRAW_ODDS_DEEP_PULL_MANIFEST.csv"
    excluded_path = out_dir / "DRAW_ODDS_DEEP_PULL_EXCLUDED_LINKS.csv"
    summary_path = out_dir / "DRAW_ODDS_DEEP_PULL_SUMMARY.json"
    report_path = out_dir / "DRAW_ODDS_DEEP_PULL_REPORT.md"
    lines = [
        "# Draw Odds Deep Pull Report",
        "",
        f"FETCHED_AT_UTC={fetched_at_utc}",
        f"OUTPUT_DIR={out_dir}",
        "",
        "## Source URLs",
        "",
        f"- Current UtahDraws Big Game 2026: {CURRENT_UTAHDRAWS_URL}",
        f"- Older Big Game odds: {BIGGAME_ODDS_URL}",
        f"- Bear, cougar, and turkey odds: {BEAR_COUGAR_TURKEY_ODDS_URL}",
        "",
        "## Scope",
        "",
        "- Included: Big Game, antlerless Big Game, black bear, cougar, and turkey.",
        "- Included current-year UtahDraws JSON endpoints for allowed 2026 draw packages.",
        "- Included official historical PDF odds/point-result files from Utah DWR pages.",
        "- Excluded: wetland, waterfowl, and non-turkey upland game.",
        "",
        "## Counts",
        "",
        f"- Manifest rows: {len(manifest_rows)}",
        f"- Excluded link/endpoint rows: {len(excluded_rows)}",
        f"- UtahDraws included endpoints: {summary['utahdraws_endpoints_included']}",
        f"- UtahDraws endpoint errors: {summary['utahdraws_endpoint_errors']}",
        f"- UtahDraws hunts returned: {summary['utahdraws_hunts_returned']}",
        f"- UtahDraws odds rows returned: {summary['utahdraws_odds_rows_returned']}",
        f"- Official page links inspected: {summary['official_page_links_inspected']}",
        f"- Official PDF files downloaded: {summary['official_pdf_files_downloaded']}",
        f"- Official PDF download errors: {summary['official_pdf_download_errors']}",
        "",
        "## Included By Category",
        "",
    ]
    for category, count in count_by(manifest_rows, "category").items():
        lines.append(f"- {category}: {count}")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "ONLY_ALLOWED_SPECIES_PULLED = TRUE",
            "ANTLERLESS_INCLUDED = TRUE",
            "WETLAND_UPLAND_NON_TURKEY_EXCLUDED = TRUE",
            "EXTERNAL_OUTPUT_PATH_USED = FALSE",
            "LARGE_TRUTH_VS_PREDICTION_COMPARABLES_CREATED = FALSE",
            "",
            "## Output Files",
            "",
            f"- Manifest: {manifest_path}",
            f"- Excluded links/endpoints: {excluded_path}",
            f"- Summary JSON: {summary_path}",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    fetched_at_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out_dir = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "_staging" / f"draw_odds_deep_pull_{now_stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, object]] = []
    excluded_rows: list[dict[str, object]] = []
    utahdraws_included, utahdraws_errors, utahdraws_hunts, utahdraws_odds_rows = pull_utahdraws_current(
        out_dir, fetched_at_utc, manifest_rows, excluded_rows
    )
    link_count, pdf_downloaded, pdf_errors = pull_official_pages(
        out_dir, fetched_at_utc, manifest_rows, excluded_rows
    )

    manifest_fields = [
        "source_kind",
        "source_page",
        "link_text",
        "source_url",
        "scope_decision",
        "category",
        "draw_name",
        "license_year",
        "master_hunt_type_id",
        "master_hunt_type_name",
        "hunt_count_advertised",
        "output_file",
        "csv_output_file",
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
    excluded_fields = [
        "source_kind",
        "source_page",
        "link_text",
        "source_url",
        "scope_decision",
        "category",
        "draw_name",
        "license_year",
        "master_hunt_type_id",
        "master_hunt_type_name",
        "hunt_count_advertised",
        "fetched_at_utc",
    ]
    write_csv(out_dir / "DRAW_ODDS_DEEP_PULL_MANIFEST.csv", manifest_rows, manifest_fields)
    write_csv(out_dir / "DRAW_ODDS_DEEP_PULL_EXCLUDED_LINKS.csv", excluded_rows, excluded_fields)

    summary = {
        "fetched_at_utc": fetched_at_utc,
        "output_dir": str(out_dir),
        "source_urls": [
            CURRENT_UTAHDRAWS_URL,
            BIGGAME_ODDS_URL,
            BEAR_COUGAR_TURKEY_ODDS_URL,
        ],
        "utahdraws_endpoints_included": utahdraws_included,
        "utahdraws_endpoint_errors": utahdraws_errors,
        "utahdraws_hunts_returned": utahdraws_hunts,
        "utahdraws_odds_rows_returned": utahdraws_odds_rows,
        "official_page_links_inspected": link_count,
        "official_pdf_files_downloaded": pdf_downloaded,
        "official_pdf_download_errors": pdf_errors,
        "manifest_rows": len(manifest_rows),
        "excluded_rows": len(excluded_rows),
        "included_by_category": count_by(manifest_rows, "category"),
        "excluded_by_category": count_by(excluded_rows, "category"),
        "ONLY_ALLOWED_SPECIES_PULLED": True,
        "ANTLERLESS_INCLUDED": True,
        "WETLAND_UPLAND_NON_TURKEY_EXCLUDED": True,
        "EXTERNAL_OUTPUT_PATH_USED": False,
        "LARGE_TRUTH_VS_PREDICTION_COMPARABLES_CREATED": False,
    }
    (out_dir / "DRAW_ODDS_DEEP_PULL_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_report(out_dir, fetched_at_utc, manifest_rows, excluded_rows, summary)

    status = "PASS"
    if utahdraws_errors or pdf_errors:
        status = "PASS_WITH_DOWNLOAD_ERRORS"
    print(f"DRAW_ODDS_DEEP_PULL_OUTPUT_DIR={out_dir}")
    print(f"UTAHDRAWS_ENDPOINTS_INCLUDED={utahdraws_included}")
    print(f"UTAHDRAWS_HUNTS_RETURNED={utahdraws_hunts}")
    print(f"UTAHDRAWS_ODDS_ROWS_RETURNED={utahdraws_odds_rows}")
    print(f"OFFICIAL_PAGE_LINKS_INSPECTED={link_count}")
    print(f"OFFICIAL_PDF_FILES_DOWNLOADED={pdf_downloaded}")
    print(f"EXCLUDED_LINKS_OR_ENDPOINTS={len(excluded_rows)}")
    print(f"STATUS={status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(f"FAILED_HTTP={exc.code} {exc.url}", file=sys.stderr)
        raise
