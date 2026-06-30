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
MANIFEST = REPO / "pipeline" / "manifests" / "species_harvest_supplement_links.csv"
LOG = REPO / "pipeline" / "manifests" / "species_harvest_supplement_download_log.csv"

SEED_PAGES = [
    "https://wildlife.utah.gov/hunting/reports",
    "https://wildlife.utah.gov/biggame/reports",
    "https://wildlife.utah.gov/upland-reports.html",
    "https://wildlife.utah.gov/odds",
]

SPECIES = ["bear", "turkey", "cougar", "sheep", "goat", "moose", "pronghorn"]
HARVEST_HINTS = ["harvest", "report", "annual", "survey", "hr", "oial", "stats"]


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read().decode("utf-8", "ignore")


def full_url(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return "https://wildlife.utah.gov" + href
    return href


def infer_year(text: str) -> int | None:
    m = re.search(r"(20\d{2})", text)
    if m:
        y = int(m.group(1))
        if 2000 <= y <= 2035:
            return y
    m2 = re.search(r"(?<!\d)(\d{2})(?!\d)", text)
    if m2:
        yy = int(m2.group(1))
        if 10 <= yy <= 35:
            return 2000 + yy
    return None


def pick_species(blob: str) -> str:
    b = blob.lower()
    for s in SPECIES:
        if re.search(rf"\b{s}\b", b):
            return s
    return "mixed"


def safe_name(s: str) -> str:
    bad = '<>:"/\\|?*'
    return " ".join("".join("_" if c in bad else c for c in s).split())


def main() -> None:
    links = []

    for page in SEED_PAGES:
        try:
            html = fetch_text(page)
        except Exception:
            continue
        for m in re.finditer(r'<a[^>]+href="([^"]+\.(?:pdf|csv|xlsx)[^"]*)"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
            href = m.group(1).strip()
            label = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            url = full_url(href)
            blob = f"{href} {label}".lower()
            if not any(sp in blob for sp in SPECIES):
                continue
            if not any(h in blob for h in HARVEST_HINTS):
                continue
            year = infer_year(f"{href} {label}")
            if not year or year < 2020:
                continue
            links.append(
                {
                    "source_page": page,
                    "species": pick_species(blob),
                    "publish_year": year,
                    "label": label,
                    "url": url,
                }
            )

    # de-dupe by URL
    uniq = {}
    for r in links:
        uniq[r["url"]] = r
    rows = list(uniq.values())
    rows.sort(key=lambda r: (r["publish_year"], r["species"], r["url"]))

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source_page", "species", "publish_year", "label", "url"])
        w.writeheader()
        w.writerows(rows)

    downloaded = skipped = failed = 0
    dlog = []
    for r in rows:
        year = str(r["publish_year"])
        url = r["url"]
        species = r["species"]
        label = r["label"] or f"{species}_harvest_report"
        ext = ".pdf"
        if url.lower().endswith(".csv"):
            ext = ".csv"
        elif url.lower().endswith(".xlsx"):
            ext = ".xlsx"

        # store all supplemental harvest artifacts under harvest_report
        dest_dir = RAW_ROOT / year / "pdf" / "harvest_report"
        dest_dir.mkdir(parents=True, exist_ok=True)
        pref = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        name = safe_name(f"{pref}__{species}_{label}") + ext
        dest = dest_dir / name

        if dest.exists():
            skipped += 1
            dlog.append({**r, "status": "skipped_exists", "dest_path": str(dest)})
            continue

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=90).read()
            if ext == ".pdf" and not data.startswith(b"%PDF"):
                raise RuntimeError("Not PDF")
            dest.write_bytes(data)
            downloaded += 1
            dlog.append({**r, "status": "downloaded", "dest_path": str(dest)})
        except Exception as e:
            failed += 1
            dlog.append({**r, "status": f"failed:{type(e).__name__}", "dest_path": ""})

    with LOG.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["source_page", "species", "publish_year", "label", "url", "status", "dest_path"],
        )
        w.writeheader()
        w.writerows(dlog)

    print(f"LINKS_FOUND={len(rows)}")
    print(f"DOWNLOADED={downloaded}")
    print(f"SKIPPED_EXISTS={skipped}")
    print(f"FAILED={failed}")
    print(f"MANIFEST={MANIFEST}")
    print(f"LOG={LOG}")


if __name__ == "__main__":
    main()
