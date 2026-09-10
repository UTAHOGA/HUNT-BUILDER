#!/usr/bin/env python3
"""Compare a user PDF folder with a fresh official-source pull manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


def clean(value: object) -> str:
    return str(value or "").strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_name(path: Path) -> str:
    stem = re.sub(r"\s*\(\d+\)$", "", path.stem, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_") + ".pdf"


def pdf_signature(path: Path) -> tuple[int, str, str, str]:
    reader = PdfReader(path)
    page_texts: list[str] = []
    for page in reader.pages:
        text = (page.extract_text() or "").replace("\x00", " ")
        page_texts.append(re.sub(r"\s+", " ", text).strip())
    joined = "\n\f\n".join(page_texts)
    text_hash = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    first = page_texts[0][:500] if page_texts else ""
    last = page_texts[-1][:500] if page_texts else ""
    return len(reader.pages), text_hash, first, last


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--fresh-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    folder = args.folder.resolve()
    fresh_manifest = args.fresh_manifest.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    fresh_rows = read_manifest(fresh_manifest)
    fresh_by_hash = {clean(row["fresh_sha256"]): row for row in fresh_rows}
    fresh_by_name = {
        normalized_name(Path(clean(row["fresh_path"]))): row for row in fresh_rows
    }
    fresh_signature_cache: dict[Path, tuple[int, str, str, str]] = {}
    audit_rows: list[dict[str, object]] = []
    matched_fresh_paths: set[str] = set()

    for local in sorted(folder.rglob("*.pdf")):
        local_hash = sha256_file(local)
        local_pages, local_text_hash, local_first, local_last = pdf_signature(local)
        fresh = fresh_by_hash.get(local_hash)
        match_basis = "SHA256"
        if fresh is None:
            fresh = fresh_by_name.get(normalized_name(local))
            match_basis = "NORMALIZED_FILENAME" if fresh else "NO_MATCH"

        fresh_path = Path(clean(fresh["fresh_path"])).resolve() if fresh else None
        fresh_hash = clean(fresh["fresh_sha256"]) if fresh else ""
        fresh_pages = ""
        fresh_text_hash = ""
        comparison = "NO_OFFICIAL_MATCH"
        if fresh and fresh_path:
            matched_fresh_paths.add(clean(fresh["fresh_path"]))
            if fresh_path not in fresh_signature_cache:
                fresh_signature_cache[fresh_path] = pdf_signature(fresh_path)
            official_pages, official_text_hash, _first, _last = fresh_signature_cache[fresh_path]
            fresh_pages = official_pages
            fresh_text_hash = official_text_hash
            if local_hash == fresh_hash:
                comparison = "EXACT_PDF_BYTES_MATCH"
            elif local_pages == official_pages and local_text_hash == official_text_hash:
                comparison = "SAME_EXTRACTED_TABLE_TEXT_DIFFERENT_PDF_BYTES"
            else:
                comparison = "CONTENT_DIFFERENCE_REVIEW_REQUIRED"

        audit_rows.append(
            {
                "local_path": str(local),
                "local_name": local.name,
                "local_size_bytes": local.stat().st_size,
                "local_sha256": local_hash,
                "local_page_count": local_pages,
                "local_text_sha256": local_text_hash,
                "matched_official_title": clean(fresh.get("official_title")) if fresh else "",
                "matched_official_url": clean(fresh.get("official_url")) if fresh else "",
                "fresh_path": clean(fresh.get("fresh_path")) if fresh else "",
                "fresh_size_bytes": clean(fresh.get("size_bytes")) if fresh else "",
                "fresh_sha256": fresh_hash,
                "fresh_page_count": fresh_pages,
                "fresh_text_sha256": fresh_text_hash,
                "match_basis": match_basis,
                "comparison": comparison,
                "local_first_page_text_sample": local_first,
                "local_last_page_text_sample": local_last,
            }
        )

    manifest_path = output_dir / "LOCAL_FOLDER_VS_FRESH_OFFICIAL_PDF_AUDIT.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)

    comparison_counts = Counter(clean(row["comparison"]) for row in audit_rows)
    unmatched_official = [
        clean(row["fresh_path"])
        for row in fresh_rows
        if clean(row["fresh_path"]) not in matched_fresh_paths
    ]
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": (
            "PASS_COMPLETE_FOLDER_EQUIVALENCE"
            if not unmatched_official
            and not any(
                key in comparison_counts
                for key in ("NO_OFFICIAL_MATCH", "CONTENT_DIFFERENCE_REVIEW_REQUIRED")
            )
            else "REVIEW_REQUIRED"
        ),
        "local_folder": str(folder),
        "local_pdf_count": len(audit_rows),
        "fresh_official_pdf_count": len(fresh_rows),
        "comparison_counts": dict(sorted(comparison_counts.items())),
        "unmatched_official_fresh_paths": unmatched_official,
        "audit_csv": str(manifest_path),
        "preferred_truth_source": "fresh current official URL bytes",
        "writes_to_local_folder": [],
    }
    (output_dir / "LOCAL_FOLDER_VS_FRESH_OFFICIAL_PDF_SUMMARY.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "PASS_COMPLETE_FOLDER_EQUIVALENCE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
