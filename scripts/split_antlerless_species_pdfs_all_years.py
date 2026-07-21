#!/usr/bin/env python3
"""Split umbrella antlerless draw-result PDFs into species-specific children.

The repo already contains several year folders where the public PDF bundle is
an umbrella parent and the species children are expected to exist alongside it.
This helper mirrors the 2022 split pattern across all discovered umbrella
parents, writes child PDFs into the active draw-odds folder and the truth-store
raw PDF folder, and emits a source alias manifest per source/target year pair.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader, PdfWriter


REPO = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
TRUTH_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs"
ALIASES_DIR = REPO / "data_truth" / "draw_results_truth" / "source_file_aliases"
REPORT_DIR = REPO / "audits" / "antlerless_species_split_all_years"

PARENT_PATTERNS = (
    re.compile(r"__ANTLERLESS_DRAW_RESULTS\.pdf$", re.I),
    re.compile(r"__YOUTH_ANTLERLESS_DRAW_RESULTS\.pdf$", re.I),
    re.compile(r"__ANTLERLESS_BIG_GAME_DRAW_RESULTS\.pdf$", re.I),
)

HUNT_RE = re.compile(r"(?m)^Hunt:\s+([A-Z0-9]+)\b")

PREFIX_TO_CHILD_TITLE = {
    "DA": ("ANTLERLESS_DEER", "YOUTH_ANTLERLESS_DEER"),
    "EA": ("ANTLERLESS_ELK", "YOUTH_ANTLERLESS_ELK"),
    "PD": ("ANTLERLESS_PRONGHORN", "YOUTH_ANTLERLESS_PRONGHORN"),
    "MA": ("ANTLERLESS_MOOSE", None),
    "RE": ("ANTLERLESS_ROCKY_MOUNTAIN_SHEEP", None),
}


@dataclass(frozen=True)
class ParentDoc:
    source_year: int
    target_year: int
    parent_path: Path
    parent_family: str
    is_youth: bool


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_pdf_prefixes(path: Path) -> list[str | None]:
    reader = PdfReader(str(path))
    prefixes: list[str | None] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        match = HUNT_RE.search(text)
        prefixes.append(match.group(1)[:2] if match else None)
    return prefixes


def page_blocks(prefixes: list[str | None]) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    current_prefix: str | None = None
    start_page: int | None = None
    first_code_seen = False

    for page_index, prefix in enumerate(prefixes, start=1):
        if prefix is None:
            continue
        if not first_code_seen:
            first_code_seen = True
            current_prefix = prefix
            start_page = 1
            continue
        if prefix != current_prefix:
            assert start_page is not None
            blocks.append((start_page, page_index - 1, current_prefix))
            current_prefix = prefix
            start_page = page_index

    if first_code_seen and current_prefix is not None and start_page is not None:
        blocks.append((start_page, len(prefixes), current_prefix))
    return blocks


def detect_parents() -> list[ParentDoc]:
    docs: list[ParentDoc] = []
    for year_dir in sorted(p for p in PIPELINE_ROOT.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}", p.name)):
        draw_dirs = [year_dir / "pdf" / "draw_odds", year_dir / "pdf" / "draw results", year_dir / "pdf" / "2025 draw results"]
        for draw_dir in draw_dirs:
            if not draw_dir.exists():
                continue
            for path in sorted(p for p in draw_dir.rglob("*.pdf") if p.is_file()):
                name = path.name
                if not any(pattern.search(name) for pattern in PARENT_PATTERNS):
                    continue
                docs.append(
                    ParentDoc(
                        source_year=int(year_dir.name),
                        target_year=int(year_dir.name) + 1,
                        parent_path=path,
                        parent_family="YOUTH_ANTLERLESS" if "YOUTH_ANTLERLESS" in name.upper() else "ADULT_ANTLERLESS",
                        is_youth="YOUTH_ANTLERLESS" in name.upper(),
                    )
                )
    return docs


def child_title(prefix: str, is_youth: bool, source_year: int) -> str | None:
    family_titles = PREFIX_TO_CHILD_TITLE.get(prefix)
    if not family_titles:
        return None
    title = family_titles[1] if is_youth else family_titles[0]
    if title is None:
        return None
    return title


def target_name(source_year: int, target_year: int, is_youth: bool, prefix: str) -> str | None:
    title = child_title(prefix, is_youth=is_youth, source_year=source_year)
    if not title:
        return None
    if prefix == "RE":
        candidates = [
            "ANTLERLESS_ROCKY_MTN_SHEEP",
            "ANTLERLESS_ROCKY_MOUNTAIN_BIGHORN_SHEEP",
            "ANTLERLESS_ROCKY_MOUNTAIN_SHEEP",
        ]
        family = "YOUTH_ANTLERLESS" if is_youth else "ANTLERLESS"
        for candidate in candidates:
            candidate_name = f"{source_year}_PERMITS={target_year}_MODEL__{family}_{candidate.removeprefix('ANTLERLESS_')}_DRAW_RESULTS.pdf"
            if (PIPELINE_ROOT / f"{source_year}" / "pdf" / "draw_odds" / candidate_name).exists():
                return candidate_name
            truth_candidate = TRUTH_ROOT / f"{source_year}_PERMITS={target_year}_MODEL" / candidate_name
            if truth_candidate.exists():
                return candidate_name
        return f"{source_year}_PERMITS={target_year}_MODEL__{family}_{candidates[-1].removeprefix('ANTLERLESS_')}_DRAW_RESULTS.pdf"
    family = "YOUTH_ANTLERLESS" if is_youth else "ANTLERLESS"
    return f"{source_year}_PERMITS={target_year}_MODEL__{family}_{title.removeprefix('YOUTH_ANTLERLESS_').removeprefix('ANTLERLESS_')}_DRAW_RESULTS.pdf"


def write_split(source_pdf: Path, target_pdf: Path, start_page: int, end_page: int) -> None:
    reader = PdfReader(str(source_pdf))
    writer = PdfWriter()
    for page_index in range(start_page - 1, end_page):
        writer.add_page(reader.pages[page_index])
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
) -> dict[str, str]:
    return {
        "source_year": str(source_year),
        "target_year": str(target_year),
        "canonical_source_value": canonical_source_value,
        "canonical_source_leaf": Path(canonical_source_value).name,
        "canonical_source_slug": canonical_source_value.lower().replace(".pdf", "").replace("__", "_").replace(" ", "_"),
        "source_columns": "draw_source_file|source_file|source_pdf",
        "canonical_row_count": "0",
        "standardized_raw_pdf_relative_path": standardized_raw_pdf_relative_path,
        "source_family": source_family,
        "source_role": source_role,
        "active_for_scoring": "True" if active_for_scoring else "False",
        "resolution_method": resolution_method,
        "sha256": sha256(path),
        "size_bytes": str(path.stat().st_size),
    }


def split_parent(doc: ParentDoc) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    prefixes = read_pdf_prefixes(doc.parent_path)
    blocks = page_blocks(prefixes)
    manifest_rows: list[dict[str, str]] = []
    report_rows: list[dict[str, str]] = []

    for start_page, end_page, prefix in blocks:
        child = target_name(doc.source_year, doc.target_year, doc.is_youth, prefix)
        if not child:
            report_rows.append(
                {
                    "parent_name": doc.parent_path.name,
                    "status": "SKIPPED_UNKNOWN_PREFIX",
                    "prefix": prefix,
                    "start_page": str(start_page),
                    "end_page": str(end_page),
                }
            )
            continue

        target_pipeline = doc.parent_path.parent / child
        truth_dir = TRUTH_ROOT / f"{doc.source_year}_PERMITS={doc.target_year}_MODEL"
        target_truth = truth_dir / child

        if target_pipeline.exists() and target_truth.exists():
            pipeline_hash = sha256(target_pipeline)
            truth_hash = sha256(target_truth)
            if pipeline_hash != truth_hash:
                raise RuntimeError(
                    f"Target already exists with different content: {target_pipeline} vs {target_truth}"
                )
        else:
            write_split(doc.parent_path, target_pipeline, start_page, end_page)
            write_split(doc.parent_path, target_truth, start_page, end_page)

        manifest_rows.append(
            manifest_row(
                source_year=doc.source_year,
                target_year=doc.target_year,
                canonical_source_value=child,
                standardized_raw_pdf_relative_path=child,
                source_family=("YOUTH_ANTLERLESS" if doc.is_youth else "ADULT_ANTLERLESS"),
                source_role="CANONICAL_SOURCE_ALIAS_ACTIVE",
                active_for_scoring=True,
                resolution_method="PDF_SPLIT_CHILD",
                path=target_truth,
            )
        )
        report_rows.append(
            {
                "parent_name": doc.parent_path.name,
                "child_name": child,
                "prefix": prefix,
                "start_page": str(start_page),
                "end_page": str(end_page),
                "pipeline_path": str(target_pipeline),
                "truth_path": str(target_truth),
                "sha256": sha256(target_truth),
                "size_bytes": str(target_truth.stat().st_size),
                "source_family": "YOUTH_ANTLERLESS" if doc.is_youth else "ADULT_ANTLERLESS",
            }
        )

    parent_truth_path = TRUTH_ROOT / f"{doc.source_year}_PERMITS={doc.target_year}_MODEL" / doc.parent_path.name
    if parent_truth_path.exists():
        manifest_rows.append(
            manifest_row(
                source_year=doc.source_year,
                target_year=doc.target_year,
                canonical_source_value=doc.parent_path.name,
                standardized_raw_pdf_relative_path=f"Parent/{doc.parent_path.name}",
                source_family=("YOUTH_ANTLERLESS" if doc.is_youth else "ADULT_ANTLERLESS"),
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
    ALIASES_DIR.mkdir(parents=True, exist_ok=True)

    docs = detect_parents()
    if not docs:
        raise SystemExit("No umbrella antlerless parent PDFs were found.")

    manifest_rows_by_pair: dict[tuple[int, int], list[dict[str, str]]] = {}
    report_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, object]] = []

    for doc in docs:
        manifest_rows, split_rows = split_parent(doc)
        manifest_rows_by_pair.setdefault((doc.source_year, doc.target_year), []).extend(manifest_rows)
        report_rows.extend(split_rows)
        summary_rows.append(
            {
                "source_year": doc.source_year,
                "target_year": doc.target_year,
                "parent_name": doc.parent_path.name,
                "split_children": len(split_rows),
                "source_family": doc.parent_family,
            }
        )

    manifest_fieldnames = [
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
    ]
    for (source_year, target_year), rows in sorted(manifest_rows_by_pair.items()):
        manifest_path = ALIASES_DIR / f"{source_year}_PERMITS={target_year}_MODEL_source_alias_manifest.csv"
        write_csv(manifest_path, manifest_fieldnames, rows)

    report_path = REPORT_DIR / f"antlerless_species_split_all_years_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')}.json"
    report_path.write_text(
        json.dumps(
            {
                "parents": summary_rows,
                "manifest_pairs": sorted([f"{source}->{target}" for source, target in manifest_rows_by_pair]),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "ok": True,
                "parent_files": len(docs),
                "split_children": len(report_rows),
                "manifest_files": len(manifest_rows_by_pair),
                "report_path": str(report_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
