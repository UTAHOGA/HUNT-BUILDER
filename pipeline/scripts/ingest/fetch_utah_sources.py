import csv
import json
import re
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


REPO = Path(str(_repo_root()))
OUT_DIR = REPO / "pipeline" / "processed" / "canonical"
MANIFEST_DIR = REPO / "pipeline" / "manifests"
OUT_PERMITS = OUT_DIR / "utah_huntplanner_permits_raw.csv"
OUT_DRAW_PDFS = MANIFEST_DIR / "utah_dwr_draw_pdf_links_2020plus.csv"


HB_START = "https://dwrapps.utah.gov/huntboundary/hbstart"
HB_MAPDATA = "https://dwrapps.utah.gov/huntboundary/HuntMapData"
HB_BOUNDARY_TO_HUNTS = "https://dwrapps.utah.gov/huntboundary/BoundaryToHuntNumbers"
PUBLIC_BOUNDARY_LAYER = "https://dwrmapserv.utah.gov/arcgis/rest/services/hunt/Boundaries_and_Tables_for_HuntP/MapServer/0/query"

BIGGAME_ODDS_PAGE = "https://wildlife.utah.gov/biggame/odds"


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read().decode("utf-8", "ignore")


def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def parse_map_config(mapdata: list[dict]) -> tuple[str, str]:
    service_url = ""
    service_token = ""
    for row in mapdata:
        if row.get("keyName") == "HUNT_BOUNDARY_PROD":
            service_url = row.get("serviceURL", "")
        if row.get("keyName") == "serviceToken":
            service_token = row.get("serviceURL", "")
    return service_url, service_token


def get_boundary_ids(service_url: str, service_token: str) -> list[int]:
    # service_url comes as .../HUNT_BOUNDARY_PROD/ and planner app appends MapServer/0
    query_url = service_url.rstrip("/") + "/MapServer/0/query"
    params = {
        "where": "1=1",
        "outFields": "BoundaryID",
        "returnGeometry": "false",
        "f": "json",
    }
    token = service_token.lstrip("?")
    if token:
        url = f"{query_url}?{urllib.parse.urlencode(params)}&{token}"
    else:
        url = f"{query_url}?{urllib.parse.urlencode(params)}"
    data = fetch_json(url)
    if data.get("error"):
        # Fall back to public, non-token ArcGIS endpoint
        pub_url = f"{PUBLIC_BOUNDARY_LAYER}?{urllib.parse.urlencode(params)}"
        data = fetch_json(pub_url)
    ids = []
    for feat in data.get("features", []):
        bid = feat.get("attributes", {}).get("BoundaryID")
        if isinstance(bid, int):
            ids.append(bid)
    return sorted(set(ids))


def scrape_huntplanner_permits() -> list[dict]:
    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # Start session/cookie
    opener.open(HB_START, timeout=60).read()

    mapdata = json.loads(opener.open(HB_MAPDATA, timeout=60).read().decode("utf-8", "ignore"))
    service_url, service_token = parse_map_config(mapdata)
    if not service_url:
        raise RuntimeError("Could not find HUNT_BOUNDARY_PROD service URL from HuntMapData.")

    boundary_ids = get_boundary_ids(service_url, service_token)
    rows: list[dict] = []

    for i, bid in enumerate(boundary_ids, start=1):
        q = urllib.parse.urlencode({"boundaryID": f"[{bid}]"})
        url = f"{HB_BOUNDARY_TO_HUNTS}?{q}"
        try:
            raw = opener.open(url, timeout=60).read().decode("utf-8", "ignore")
            if not raw.strip():
                continue
            data = json.loads(raw)
        except Exception:
            continue

        for r in data:
            rows.append(
                {
                    "boundary_id": bid,
                    "hunt_number": r.get("huntNumber", ""),
                    "hunt_name": r.get("huntName", ""),
                    "species": r.get("species", ""),
                    "gender": r.get("gender", ""),
                    "weapon": r.get("weapon", ""),
                    "hunt_type": r.get("huntType", ""),
                    "years": r.get("years", ""),
                    "season_date_text": r.get("seasonDateText", ""),
                    "quota_total": r.get("quota", ""),
                    "quota_resident": r.get("resQuota", ""),
                    "quota_nonresident": r.get("nonresQuota", ""),
                    "source": "dwrapps.utah.gov/huntboundary/BoundaryToHuntNumbers",
                }
            )

        if i % 100 == 0:
            time.sleep(0.15)

    return rows


def scrape_biggame_draw_pdf_links_2020plus() -> list[dict]:
    html = fetch_text(BIGGAME_ODDS_PAGE)
    rows = []
    section_pattern = re.compile(r"<h2[^>]*>\s*(20\d{2})\s*</h2>", re.IGNORECASE)
    matches = list(section_pattern.finditer(html))
    for idx, m in enumerate(matches):
        year = int(m.group(1))
        if year < 2020:
            continue
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(html)
        block = html[start:end]
        # capture all PDF links in that year block
        for a in re.finditer(r'<a[^>]+href="([^"]+\.pdf[^"]*)"[^>]*>(.*?)</a>', block, re.IGNORECASE | re.DOTALL):
            href = a.group(1).strip()
            label = re.sub(r"<[^>]+>", "", a.group(2)).strip()
            label_l = label.lower()
            if not any(k in label_l for k in ["draw", "drawing", "odds", "point"]):
                continue
            if href.startswith("/"):
                href = "https://wildlife.utah.gov" + href
            rows.append(
                {
                    "publish_year": year,
                    "label": label,
                    "url": href,
                    "source_page": BIGGAME_ODDS_PAGE,
                }
            )

    # De-duplicate
    uniq = {}
    for r in rows:
        key = (r["publish_year"], r["label"], r["url"])
        uniq[key] = r
    return list(uniq.values())


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    permit_rows = scrape_huntplanner_permits()
    write_csv(
        OUT_PERMITS,
        permit_rows,
        [
            "boundary_id",
            "hunt_number",
            "hunt_name",
            "species",
            "gender",
            "weapon",
            "hunt_type",
            "years",
            "season_date_text",
            "quota_total",
            "quota_resident",
            "quota_nonresident",
            "source",
        ],
    )

    draw_rows = scrape_biggame_draw_pdf_links_2020plus()
    write_csv(
        OUT_DRAW_PDFS,
        draw_rows,
        ["publish_year", "label", "url", "source_page"],
    )

    print(f"PERMIT_ROWS={len(permit_rows)} -> {OUT_PERMITS}")
    print(f"DRAW_PDF_ROWS={len(draw_rows)} -> {OUT_DRAW_PDFS}")


if __name__ == "__main__":
    main()
