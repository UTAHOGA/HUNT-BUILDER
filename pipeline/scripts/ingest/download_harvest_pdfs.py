import argparse
import csv
import re
import urllib.request
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root
import hashlib


REPO = Path(str(_repo_root()))
RAW_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
MANIFEST = REPO / "pipeline" / "manifests" / "utah_dwr_harvest_pdf_links_2020plus.csv"
LOG = REPO / "pipeline" / "manifests" / "harvest_pdf_download_log.csv"

HARVEST_PAGE = "https://wildlife.utah.gov/biggame/reports"
ANNUAL_PAGE = "https://wildlife.utah.gov/hunting/reports"


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read().decode("utf-8", "ignore")


def safe_name(name: str) -> str:
    bad = '<>:"/\\|?*'
    s = "".join("_" if c in bad else c for c in name).strip()
    return " ".join(s.split())


def extract_links_by_year(html: str, min_year: int = 2020) -> list[dict]:
    out = []
    sec_pat = re.compile(r"<h[234][^>]*>\s*(20\d{2})\s*</h[234]>", re.IGNORECASE)
    matches = list(sec_pat.finditer(html))
    for i, m in enumerate(matches):
        year = int(m.group(1))
        if year < min_year:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        block = html[start:end]
        for a in re.finditer(r'<a[^>]+href="([^"]+\.pdf[^"]*)"[^>]*>(.*?)</a>', block, re.IGNORECASE | re.DOTALL):
            href = a.group(1).strip()
            label = re.sub(r"<[^>]+>", "", a.group(2)).strip()
            if href.startswith("/"):
                href = "https://wildlife.utah.gov" + href
            out.append({"publish_year": year, "label": label, "url": href})
    return out


def extract_annual_biggame_links(html: str, min_year: int = 2020) -> list[dict]:
    out = []
    # pattern on annual reports page: "2024 – PDF"
    for m in re.finditer(r'<a[^>]+href=\"([^\"]+annual-reports/big-game/[^\"]+\.pdf[^\"]*)\"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
        href = m.group(1).strip()
        label = re.sub(r"<[^>]+>", "", m.group(2)).strip() or "Big game annual report"
        # infer year from href like /24_bg_report.pdf
        ym = re.search(r"/(\d{2})_bg_report\.pdf", href, re.IGNORECASE)
        if not ym:
            continue
        year = 2000 + int(ym.group(1))
        if year < min_year:
            continue
        if href.startswith("/"):
            href = "https://wildlife.utah.gov" + href
        out.append({"publish_year": year, "label": label, "url": href})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Download official Utah DWR harvest and annual big-game reports.")
    parser.add_argument("--min-year", type=int, default=2020, help="Earliest report-generation year to collect.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST, help="Output source manifest path.")
    parser.add_argument("--log", type=Path, default=LOG, help="Output download-log path.")
    args = parser.parse_args()

    harvest_html = fetch_text(HARVEST_PAGE)
    annual_html = fetch_text(ANNUAL_PAGE)

    links = extract_links_by_year(harvest_html, min_year=args.min_year)
    links += extract_annual_biggame_links(annual_html, min_year=args.min_year)

    # de-dupe by URL
    uniq = {}
    for r in links:
        uniq[r["url"]] = r
    rows = list(uniq.values())

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["publish_year", "label", "url"])
        w.writeheader()
        w.writerows(rows)

    downloaded = 0
    skipped = 0
    failed = 0
    dlog = []

    for r in rows:
        year = str(r["publish_year"])
        url = r["url"]
        label = r["label"] or "harvest_report"
        dest_dir = RAW_ROOT / year / "pdf" / "harvest_report"
        dest_dir.mkdir(parents=True, exist_ok=True)
        pref = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        name = safe_name(f"{pref}__{label}.pdf")
        dest = dest_dir / name
        if dest.exists():
            skipped += 1
            dlog.append({"publish_year": year, "label": label, "url": url, "status": "skipped_exists", "dest_path": str(dest)})
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if not data.startswith(b"%PDF"):
                raise RuntimeError("Not PDF")
            dest.write_bytes(data)
            downloaded += 1
            dlog.append({"publish_year": year, "label": label, "url": url, "status": "downloaded", "dest_path": str(dest)})
        except Exception as e:
            failed += 1
            dlog.append({"publish_year": year, "label": label, "url": url, "status": f"failed:{type(e).__name__}", "dest_path": ""})

    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["publish_year", "label", "url", "status", "dest_path"])
        w.writeheader()
        w.writerows(dlog)

    print(f"LINKS={len(rows)}")
    print(f"DOWNLOADED={downloaded}")
    print(f"SKIPPED_EXISTS={skipped}")
    print(f"FAILED={failed}")
    print(f"MANIFEST={args.manifest}")
    print(f"LOG={args.log}")


if __name__ == "__main__":
    main()
