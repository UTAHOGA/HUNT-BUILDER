import csv
import hashlib
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
IN_MANIFEST = REPO / "pipeline" / "manifests" / "utah_dwr_draw_pdf_links_2020plus.csv"
RAW_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
OUT_LOG = REPO / "pipeline" / "manifests" / "draw_pdf_download_log.csv"


def safe_name(name: str) -> str:
    bad = '<>:"/\\|?*'
    s = "".join("_" if c in bad else c for c in name).strip()
    return " ".join(s.split())


def main() -> None:
    rows = list(csv.DictReader(IN_MANIFEST.open("r", encoding="utf-8-sig", newline="")))
    out_rows = []
    downloaded = 0
    skipped = 0
    failed = 0

    for r in rows:
        year = str(r.get("publish_year", "")).strip()
        url = (r.get("url") or "").strip()
        label = (r.get("label") or "draw_results").strip()
        if not year.isdigit() or not url.lower().endswith(".pdf"):
            continue

        dest_dir = RAW_ROOT / year / "pdf" / "draw_odds"
        dest_dir.mkdir(parents=True, exist_ok=True)
        prefix = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        fname = safe_name(f"{prefix}__{label}.pdf")
        dest = dest_dir / fname

        if dest.exists():
            skipped += 1
            out_rows.append(
                {
                    "publish_year": year,
                    "label": label,
                    "url": url,
                    "status": "skipped_exists",
                    "dest_path": str(dest),
                }
            )
            continue

        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                data = resp.read()
            # basic PDF sanity check
            if not data.startswith(b"%PDF"):
                raise RuntimeError("Not a PDF header")
            dest.write_bytes(data)
            downloaded += 1
            out_rows.append(
                {
                    "publish_year": year,
                    "label": label,
                    "url": url,
                    "status": "downloaded",
                    "dest_path": str(dest),
                }
            )
        except Exception as e:
            failed += 1
            out_rows.append(
                {
                    "publish_year": year,
                    "label": label,
                    "url": url,
                    "status": f"failed:{type(e).__name__}",
                    "dest_path": "",
                }
            )

    OUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with OUT_LOG.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["publish_year", "label", "url", "status", "dest_path"])
        w.writeheader()
        w.writerows(out_rows)

    print(f"DOWNLOADED={downloaded}")
    print(f"SKIPPED_EXISTS={skipped}")
    print(f"FAILED={failed}")
    print(f"LOG={OUT_LOG}")


if __name__ == "__main__":
    main()
