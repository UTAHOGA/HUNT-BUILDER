#!/usr/bin/env python3
"""Split the 2022 antlerless parent PDFs into species-specific child PDFs.

This keeps the umbrella parent PDFs in `Parent/` and writes the split children
into the active `draw_odds` folder plus the truth-store raw_pdf folder.
It also emits a source alias manifest so the split lineage stays explicit.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader, PdfWriter


REPO = Path(__file__).resolve().parents[1]
PIPELINE_DIR = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2022" / "pdf" / "draw_odds"
PIPELINE_PARENT_DIR = PIPELINE_DIR / "Parent"
TRUTH_DIR = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs" / "2022_PERMITS=2023_MODEL"
ALIASES_DIR = REPO / "data_truth" / "draw_results_truth" / "source_file_aliases"
REPORT_DIR = REPO / "audits" / "2022_antlerless_species_split"


@dataclass(frozen=True)
class SplitSpec:
    parent_name: str
    child_name: str
    start_page: int
    end_page: int
    source_family: str


SPECS = [
    # Adult antlerless umbrella
    SplitSpec(
        parent_name="2022_PERMITS=2023_MODEL__ANTLERLESS_DRAW_RESULTS.pdf",
        child_name="2022_PERMITS=2023_MODEL__ANTLERLESS_DEER_DRAW_RESULTS.pdf",
        start_page=1,
        end_page=25,
        source_family="ADULT_ANTLERLESS",
    ),
    SplitSpec(
        parent_name="2022_PERMITS=2023_MODEL__ANTLERLESS_DRAW_RESULTS.pdf",
        child_name="2022_PERMITS=2023_MODEL__ANTLERLESS_ELK_DRAW_RESULTS.pdf",
        start_page=26,
        end_page=187,
        source_family="ADULT_ANTLERLESS",
    ),
    SplitSpec(
        parent_name="2022_PERMITS=2023_MODEL__ANTLERLESS_DRAW_RESULTS.pdf",
        child_name="2022_PERMITS=2023_MODEL__ANTLERLESS_PRONGHORN_DRAW_RESULTS.pdf",
        start_page=188,
        end_page=214,
        source_family="ADULT_ANTLERLESS",
    ),
    SplitSpec(
        parent_name="2022_PERMITS=2023_MODEL__ANTLERLESS_DRAW_RESULTS.pdf",
        child_name="2022_PERMITS=2023_MODEL__ANTLERLESS_MOOSE_DRAW_RESULTS.pdf",
        start_page=215,
        end_page=219,
        source_family="ADULT_ANTLERLESS",
    ),
    SplitSpec(
        parent_name="2022_PERMITS=2023_MODEL__ANTLERLESS_DRAW_RESULTS.pdf",
        child_name="2022_PERMITS=2023_MODEL__ANTLERLESS_ROCKY_MTN_SHEEP_DRAW_RESULTS.pdf",
        start_page=220,
        end_page=222,
        source_family="ADULT_ANTLERLESS",
    ),
    # Youth antlerless umbrella
    SplitSpec(
        parent_name="2022_PERMITS=2023_MODEL__YOUTH_ANTLERLESS_DRAW_RESULTS.pdf",
        child_name="2022_PERMITS=2023_MODEL__YOUTH_ANTLERLESS_DEER_DRAW_RESULTS.pdf",
        start_page=1,
        end_page=24,
        source_family="YOUTH_ANTLERLESS",
    ),
    SplitSpec(
        parent_name="2022_PERMITS=2023_MODEL__YOUTH_ANTLERLESS_DRAW_RESULTS.pdf",
        child_name="2022_PERMITS=2023_MODEL__YOUTH_ANTLERLESS_ELK_DRAW_RESULTS.pdf",
        start_page=25,
        end_page=176,
        source_family="YOUTH_ANTLERLESS",
    ),
    SplitSpec(
        parent_name="2022_PERMITS=2023_MODEL__YOUTH_ANTLERLESS_DRAW_RESULTS.pdf",
        child_name="2022_PERMITS=2023_MODEL__YOUTH_ANTLERLESS_PRONGHORN_DRAW_RESULTS.pdf",
        start_page=177,
        end_page=202,
        source_family="YOUTH_ANTLERLESS",
    ),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(value: str) -> str:
    return value.lower().replace(".pdf", "").replace("__", "_").replace(" ", "_")


def write_split_pdf(source_pdf: Path, target_pdf: Path, start_page: int, end_page: int) -> None:
    reader = PdfReader(str(source_pdf))
    writer = PdfWriter()
    for index in range(start_page - 1, end_page):
        writer.add_page(reader.pages[index])
    target_pdf.parent.mkdir(parents=True, exist_ok=True)
    with target_pdf.open("wb") as handle:
        writer.write(handle)


def manifest_row(
    *,
    source_year: int,
    target_year: int,
    canonical_source_value: str,
    standardized_raw_pdf_relative_path: str,
    source_family: str,
    source_role: str,
    active_for_scoring: bool,
    resolution_method: str,
    path: Path,
    canonical_row_count: int = 0,
) -> dict[str, str]:
    return {
        "source_year": str(source_year),
        "target_year": str(target_year),
        "canonical_source_value": canonical_source_value,
        "canonical_source_leaf": Path(canonical_source_value).name,
        "canonical_source_slug": slug(canonical_source_value),
        "source_columns": "draw_source_file|source_file|source_pdf",
        "canonical_row_count": str(canonical_row_count),
        "standardized_raw_pdf_relative_path": standardized_raw_pdf_relative_path,
        "source_family": source_family,
        "source_role": source_role,
        "active_for_scoring": "True" if active_for_scoring else "False",
        "resolution_method": resolution_method,
        "sha256": sha256(path),
        "size_bytes": str(path.stat().st_size),
    }


def split_family(specs: list[SplitSpec]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    manifest_rows: list[dict[str, str]] = []
    report_rows: list[dict[str, str]] = []
    grouped: dict[str, list[SplitSpec]] = {}
    for spec in specs:
        grouped.setdefault(spec.parent_name, []).append(spec)

    for parent_name, items in grouped.items():
        source_pdf = PIPELINE_PARENT_DIR / parent_name
        if not source_pdf.exists():
            raise FileNotFoundError(source_pdf)
        for spec in items:
            target_pipeline = PIPELINE_DIR / spec.child_name
            target_truth = TRUTH_DIR / spec.child_name
            write_split_pdf(source_pdf, target_pipeline, spec.start_page, spec.end_page)
            write_split_pdf(source_pdf, target_truth, spec.start_page, spec.end_page)
            manifest_rows.append(
                manifest_row(
                    source_year=2022,
                    target_year=2023,
                    canonical_source_value=spec.child_name,
                    standardized_raw_pdf_relative_path=spec.child_name,
                    source_family=spec.source_family,
                    source_role="CANONICAL_SOURCE_ALIAS_ACTIVE",
                    active_for_scoring=True,
                    resolution_method="PDF_SPLIT_CHILD",
                    path=target_truth,
                )
            )
            report_rows.append(
                {
                    "parent_name": parent_name,
                    "child_name": spec.child_name,
                    "start_page": str(spec.start_page),
                    "end_page": str(spec.end_page),
                    "source_family": spec.source_family,
                    "pipeline_path": str(target_pipeline),
                    "truth_path": str(target_truth),
                    "sha256": sha256(target_truth),
                    "size_bytes": str(target_truth.stat().st_size),
                }
            )

        parent_truth_path = TRUTH_DIR / parent_name
        if parent_truth_path.exists():
            manifest_rows.append(
                manifest_row(
                    source_year=2022,
                    target_year=2023,
                    canonical_source_value=parent_name,
                    standardized_raw_pdf_relative_path=f"Parent/{parent_name}",
                    source_family=items[0].source_family,
                    source_role="CANONICAL_SOURCE_ALIAS_SUPERSEDED",
                    active_for_scoring=False,
                    resolution_method="PDF_SPLIT_PARENT",
                    path=parent_truth_path,
                )
            )

    return manifest_rows, report_rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_rows, report_rows = split_family(SPECS)
    manifest_path = ALIASES_DIR / "2022_PERMITS=2023_MODEL_source_alias_manifest.csv"
    write_csv(
        manifest_path,
        [
            "source_year",
            "target_year",
            "canonical_source_value",
            "canonical_source_leaf",
            "canonical_source_slug",
            "source_columns",
            "canonical_row_count",
            "standardized_raw_pdf_relative_path",
            "source_family",
            "source_role",
            "active_for_scoring",
            "resolution_method",
            "sha256",
            "size_bytes",
        ],
        manifest_rows,
    )
    report_path = REPORT_DIR / f"2022_antlerless_species_split_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')}.json"
    report_path.write_text(json.dumps({"splits": report_rows, "manifest_path": str(manifest_path)}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "split_count": len(report_rows),
        "manifest_path": str(manifest_path),
        "report_path": str(report_path),
    }, indent=2))


if __name__ == "__main__":
    main()
