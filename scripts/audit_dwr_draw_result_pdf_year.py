#!/usr/bin/env python3
"""Compare one fresh DWR draw-result PDF year with retained source and normalized truth."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_ROOT = (
    ROOT
    / "audits"
    / "source_pdf_revalidation"
    / "dwr_draw_results_2017_2026_20260907"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def page_count(path: Path) -> int | None:
    try:
        return len(PdfReader(path).pages)
    except Exception:
        return None


def pdf_text_sha256(path: Path) -> str | None:
    try:
        text = "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
    except Exception:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def semicolon(values: Iterable[str]) -> str:
    return ";".join(sorted({value for value in values if value}))


def normalized_source_names(row: dict[str, str]) -> set[str]:
    names: set[str] = set()
    for field in ("source_file", "draw_source_file", "source_path", "source_pdf"):
        value = (row.get(field) or "").strip()
        if not value:
            continue
        names.add(Path(value.replace("\\", "/")).name.casefold())
    return names


def load_normalized_rows(year: int) -> list[dict[str, str]]:
    path = (
        ROOT
        / "data_truth"
        / "draw_results_truth"
        / "normalized"
        / "canonical_yearly"
        / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"
    )
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def manifest_rows(year_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for manifest in sorted(year_dir.glob("*_archive_manifest.csv")):
        with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("status") != "ok":
                    continue
                row["manifest"] = manifest.name
                rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("year", type=int)
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT_ROOT)
    args = parser.parse_args()

    year = args.year
    year_dir = args.audit_root / str(year)
    retained_root = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / str(year) / "pdf"

    links = manifest_rows(year_dir)
    if not links:
        raise SystemExit(f"No successful fresh PDF manifest rows found in {year_dir}")

    retained_by_hash: dict[str, list[Path]] = defaultdict(list)
    retained_by_name: dict[str, list[Path]] = defaultdict(list)
    for path in retained_root.rglob("*.pdf") if retained_root.exists() else []:
        retained_by_hash[sha256(path)].append(path)
        retained_by_name[path.name.casefold()].append(path)

    normalized_rows = load_normalized_rows(year)
    normalized_by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in normalized_rows:
        for name in normalized_source_names(row):
            normalized_by_name[name].append(row)

    links_by_url: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in links:
        links_by_url[row["url"]].append(row)

    comparison: list[dict[str, object]] = []
    for url, mentions in sorted(links_by_url.items()):
        row = mentions[0]
        fresh_path = year_dir / row["file"]
        fresh_hash = sha256(fresh_path)
        exact_matches = retained_by_hash.get(fresh_hash, [])
        same_name = retained_by_name.get(fresh_path.name.casefold(), [])
        direct_rows = normalized_by_name.get(fresh_path.name.casefold(), [])
        fresh_pdf_pages = page_count(fresh_path)
        content_matches: list[Path] = []
        if not exact_matches and same_name:
            fresh_text_hash = pdf_text_sha256(fresh_path)
            for candidate in same_name:
                if (
                    page_count(candidate) == fresh_pdf_pages
                    and pdf_text_sha256(candidate) == fresh_text_hash
                ):
                    content_matches.append(candidate)

        if exact_matches:
            comparison_status = "EXACT_RETAINED_COPY"
        elif content_matches:
            comparison_status = "CONTENT_EQUIVALENT_RETAINED_COPY"
        else:
            comparison_status = "NO_EQUIVALENT_RETAINED_COPY"

        comparison.append(
            {
                "year": year,
                "source_group": row.get("source", ""),
                "species": row.get("species", "big_game"),
                "title": row.get("title", ""),
                "url": url,
                "fresh_filename": fresh_path.name,
                "fresh_path": fresh_path.relative_to(ROOT).as_posix(),
                "fresh_sha256": fresh_hash,
                "fresh_bytes": fresh_path.stat().st_size,
                "fresh_pages": fresh_pdf_pages,
                "source_page_link_mentions": len(mentions),
                "retained_exact_match_count": len(exact_matches),
                "retained_exact_matches": semicolon(
                    match.relative_to(ROOT).as_posix() for match in exact_matches
                ),
                "retained_same_name_count": len(same_name),
                "retained_same_name_hashes": semicolon(sha256(match) for match in same_name),
                "retained_content_equivalent_match_count": len(content_matches),
                "retained_content_equivalent_matches": semicolon(
                    match.relative_to(ROOT).as_posix() for match in content_matches
                ),
                "normalized_direct_row_count": len(direct_rows),
                "normalized_draw_pools": semicolon(row.get("draw_pool", "") for row in direct_rows),
                "normalized_draw_system_types": semicolon(
                    row.get("draw_system_type", "") for row in direct_rows
                ),
                "normalized_source_is_youth_values": semicolon(
                    row.get("source_is_youth", "") for row in direct_rows
                ),
                "comparison_status": comparison_status,
            }
        )

    fieldnames = list(comparison[0])
    csv_path = year_dir / f"dwr_draw_result_pdf_source_comparison_{year}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comparison)

    summary = {
        "year": year,
        "official_pdf_links": len(links),
        "official_unique_pdf_urls": len(comparison),
        "duplicate_link_mentions": len(links) - len(comparison),
        "fresh_downloads_with_exact_retained_copy": sum(
            row["comparison_status"] == "EXACT_RETAINED_COPY" for row in comparison
        ),
        "fresh_downloads_without_exact_retained_copy": sum(
            row["comparison_status"] != "EXACT_RETAINED_COPY" for row in comparison
        ),
        "fresh_downloads_with_content_equivalent_retained_copy": sum(
            row["comparison_status"] == "CONTENT_EQUIVALENT_RETAINED_COPY"
            for row in comparison
        ),
        "fresh_downloads_without_equivalent_retained_copy": sum(
            row["comparison_status"] == "NO_EQUIVALENT_RETAINED_COPY" for row in comparison
        ),
        "fresh_downloads_with_direct_normalized_rows": sum(
            int(row["normalized_direct_row_count"]) > 0 for row in comparison
        ),
        "normalized_canonical_rows": len(normalized_rows),
        "comparison_csv": csv_path.relative_to(ROOT).as_posix(),
    }
    json_path = year_dir / f"dwr_draw_result_pdf_source_comparison_{year}.json"
    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
