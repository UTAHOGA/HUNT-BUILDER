#!/usr/bin/env python3
"""Fresh-pull one report year of official Utah DWR draw-source PDFs.

The existing retention catalog supplies the reviewed official URLs and the
hashes of the prior durable archive. This command always downloads each URL
again into a separately named audit directory, validates that the response is
a readable PDF, and reports whether DWR currently serves the same bytes.

It never writes the durable raw archive, normalized truth, prediction runtime,
or hosted data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "raw_inventory"
    / "official_draw_source_retention_2017_2026.csv"
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def clean(value: object) -> str:
    return str(value or "").strip()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def safe_component(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return result or "unknown"


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_catalog(path: Path, report_year: int) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if clean(row.get("report_year")) == str(report_year)
            and clean(row.get("source_kind")) == "official_dwr_pdf"
        ]
    rows.sort(key=lambda row: (clean(row.get("source_family")), clean(row.get("official_url"))))
    return rows


def read_source_manifest(path: Path, report_year: int) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if clean(row.get("report_year")) == str(report_year)
        ]
    rows.sort(key=lambda row: (clean(row.get("source_family")), clean(row.get("official_url"))))
    return rows


def download(url: str) -> tuple[bytes, str, int]:
    request = Request(
        url,
        headers={
            "Accept": "application/pdf,*/*",
            "Referer": "https://wildlife.utah.gov/",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=120) as response:
        return response.read(), clean(response.headers.get("content-type")), int(response.status)


def pdf_metadata(path: Path) -> tuple[int, str, str]:
    reader = PdfReader(path)
    if not reader.pages:
        raise ValueError("PDF contains zero pages")
    first_text = (reader.pages[0].extract_text() or "").replace("\x00", " ")
    last_text = (reader.pages[-1].extract_text() or "").replace("\x00", " ")
    first_text = re.sub(r"\s+", " ", first_text).strip()[:500]
    last_text = re.sub(r"\s+", " ", last_text).strip()[:500]
    return len(reader.pages), first_text, last_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=None,
        help="Optional live-page-reviewed year manifest. When supplied, it replaces the retention catalog URL list.",
    )
    args = parser.parse_args()

    catalog = args.catalog if args.catalog.is_absolute() else ROOT / args.catalog
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"Refusing to reuse nonempty fresh-pull directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    source_manifest = None
    if args.source_manifest is not None:
        source_manifest = (
            args.source_manifest
            if args.source_manifest.is_absolute()
            else ROOT / args.source_manifest
        )
    catalog_rows = (
        read_source_manifest(source_manifest, args.year)
        if source_manifest is not None
        else read_catalog(catalog, args.year)
    )
    if not catalog_rows:
        raise SystemExit(f"No official PDF catalog rows found for report year {args.year}")

    pulled_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest: list[dict[str, object]] = []
    for index, source in enumerate(catalog_rows, start=1):
        url = clean(source.get("official_url"))
        category = safe_component(clean(source.get("source_family")))
        filename = safe_component(Path(urlparse(url).path).name or f"source_{index}.pdf")
        destination = output_dir / "pdf" / category / filename
        destination.parent.mkdir(parents=True, exist_ok=True)

        row: dict[str, object] = {
            "report_year": args.year,
            "source_family": clean(source.get("source_family")),
            "official_title": clean(source.get("official_title")),
            "official_url": url,
            "fresh_path": relative(destination),
            "prior_archive_path": clean(source.get("durable_archive_path")),
            "prior_archive_sha256": clean(source.get("sha256")),
            "fresh_sha256": "",
            "hash_comparison": "",
            "http_status": "",
            "content_type": "",
            "size_bytes": "",
            "page_count": "",
            "first_page_text_sample": "",
            "last_page_text_sample": "",
            "download_status": "ERROR",
            "error": "",
        }
        try:
            payload, content_type, http_status = download(url)
            if not payload.startswith(b"%PDF"):
                raise ValueError("response does not begin with a PDF header")
            destination.write_bytes(payload)
            pages, first_text, last_text = pdf_metadata(destination)
            fresh_hash = sha256_bytes(payload)
            archived_hash = clean(source.get("sha256") or source.get("prior_archive_sha256"))
            row.update(
                {
                    "fresh_sha256": fresh_hash,
                    "hash_comparison": (
                        "NO_PRIOR_ARCHIVE_HASH"
                        if not archived_hash
                        else "MATCH_PRIOR_ARCHIVE"
                        if fresh_hash == archived_hash
                        else "OFFICIAL_BYTES_CHANGED"
                    ),
                    "http_status": http_status,
                    "content_type": content_type,
                    "size_bytes": len(payload),
                    "page_count": pages,
                    "first_page_text_sample": first_text,
                    "last_page_text_sample": last_text,
                    "download_status": "OK",
                }
            )
        except Exception as exc:  # preserve one manifest row for every official source
            row["error"] = f"{type(exc).__name__}: {exc}"
        manifest.append(row)

    manifest_path = output_dir / "OFFICIAL_DWR_DRAW_PDF_FRESH_PULL_MANIFEST.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)

    status_counts = Counter(clean(row["download_status"]) for row in manifest)
    hash_counts = Counter(clean(row["hash_comparison"]) for row in manifest)
    category_counts = Counter(clean(row["source_family"]) for row in manifest)
    summary = {
        "generated_at_utc": pulled_at,
        "status": (
            "PASS_FRESH_OFFICIAL_PULL"
            if status_counts == {"OK": len(manifest)}
            and not any(key in hash_counts for key in ("OFFICIAL_BYTES_CHANGED", ""))
            else "REVIEW_REQUIRED"
        ),
        "report_year": args.year,
        "model_target_year": args.year + 1,
        "source_authority": "Utah Division of Wildlife Resources official draw-odds pages and linked PDFs",
        "catalog": relative(catalog),
        "source_manifest": relative(source_manifest) if source_manifest is not None else "",
        "fresh_output_dir": relative(output_dir),
        "official_pdf_count": len(manifest),
        "download_status_counts": dict(sorted(status_counts.items())),
        "hash_comparison_counts": dict(sorted(hash_counts.items())),
        "source_family_counts": dict(sorted(category_counts.items())),
        "total_size_bytes": sum(int(row["size_bytes"] or 0) for row in manifest),
        "total_pages": sum(int(row["page_count"] or 0) for row in manifest),
        "manifest": relative(manifest_path),
        "writes_outside_fresh_output_dir": [],
        "canonical_truth_changed": False,
        "prediction_runtime_changed": False,
        "hosted_action": "NONE",
    }
    summary_path = output_dir / "OFFICIAL_DWR_DRAW_PDF_FRESH_PULL_SUMMARY.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "PASS_FRESH_OFFICIAL_PULL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
