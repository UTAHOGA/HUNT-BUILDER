import csv
import hashlib
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


REPO = Path(str(_repo_root()))
RAW_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
MANIFEST = REPO / "pipeline" / "manifests" / "utah_bear_turkey_pdf_links_2020plus.csv"
LOG = REPO / "pipeline" / "manifests" / "bear_turkey_download_log.csv"
ODDS_URL = "https://wildlife.utah.gov/odds"


def safe_name(s: str) -> str:
    bad = '<>:"/\\|?*'
    return " ".join("".join("_" if c in bad else c for c in s).split())


def full_url(href: str) -> str:
    return href if href.startswith("http") else f"https://wildlife.utah.gov{href}"


def infer_publish_year(href: str) -> int | None:
    # Prefer 4-digit in path
    m4 = re.search(r"(20\d{2})", href)
    if m4:
        y = int(m4.group(1))
        if 2000 <= y <= 2035:
            return y
    # 2-digit bear paths like /pdf/bear/25_drawing_odds.pdf
    m2 = re.search(r"/bear/(\d{2})_", href)
    if m2:
        yy = int(m2.group(1))
        return 2000 + yy
    return None


def species_from_href(href: str) -> str | None:
    h = href.lower()
    if "/pdf/bear/" in h:
        return "black_bear"
    if "/pdf/uplandgame/turkey/" in h:
        return "turkey"
    return None


def main() -> None:
    req = urllib.request.Request(ODDS_URL, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "ignore")
    hrefs = sorted(set(re.findall(r'href="([^"]+\.pdf[^"]*)"', html, re.IGNORECASE)))

    links = []
    for href in hrefs:
        sp = species_from_href(href)
        if not sp:
            continue
        pub = infer_publish_year(href)
        if not pub or pub < 2020:
            continue
        links.append(
            {
                "species": sp,
                "publish_year": pub,
                "href": href,
                "url": full_url(href),
            }
        )

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["species", "publish_year", "href", "url"])
        w.writeheader()
        w.writerows(links)

    dlog = []
    downloaded = skipped = failed = 0
    for r in links:
        sp = r["species"]
        year = str(r["publish_year"])
        url = r["url"]
        doc_type = "draw_odds"
        dest_dir = RAW_ROOT / year / "pdf" / doc_type
        dest_dir.mkdir(parents=True, exist_ok=True)
        pref = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        fname = safe_name(f"{pref}__{sp}_{Path(r['href']).name}")
        dest = dest_dir / fname
        if dest.exists():
            skipped += 1
            dlog.append({**r, "status": "skipped_exists", "dest_path": str(dest)})
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=90).read()
            if not data.startswith(b"%PDF"):
                raise RuntimeError("Not PDF")
            dest.write_bytes(data)
            downloaded += 1
            dlog.append({**r, "status": "downloaded", "dest_path": str(dest)})
        except Exception as e:
            failed += 1
            dlog.append({**r, "status": f"failed:{type(e).__name__}", "dest_path": ""})

    with LOG.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["species", "publish_year", "href", "url", "status", "dest_path"])
        w.writeheader()
        w.writerows(dlog)

    print(f"LINKS={len(links)}")
    print(f"DOWNLOADED={downloaded}")
    print(f"SKIPPED_EXISTS={skipped}")
    print(f"FAILED={failed}")
    print(f"MANIFEST={MANIFEST}")
    print(f"LOG={LOG}")


if __name__ == "__main__":
    main()
