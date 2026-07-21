#!/usr/bin/env python3
"""Split CWMU pages out of yearly draw-odds PDFs.

The 2019 folder established the active CWMU stack:

    draw_odds/CWMU/ANTLERLESS CWMU/
    draw_odds/CWMU/BIG GAME CWMU/

This script scans the active first-level draw-odds PDFs plus broad CWMU parent
bundles, extracts pages whose text actually contains CWMU, and writes child PDFs
under that stack. It does not fabricate empty species files when a year has no
source pages for that bucket.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import fitz


REPO = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
AUDIT_ROOT = REPO / "audits" / "cwmu_child_pdf_split"

ANTLERLESS_DIR = Path("CWMU") / "ANTLERLESS CWMU"
BIG_GAME_DIR = Path("CWMU") / "BIG GAME CWMU"

EXPECTED_CHILDREN = [
    ANTLERLESS_DIR / "{year}_PERMITS={target}_MODEL__CWMU_ANTLERLESS_DEER_DRAW_RESULTS.pdf",
    ANTLERLESS_DIR / "{year}_PERMITS={target}_MODEL__CWMU_ANTLERLESS_ELK_DRAW_RESULTS.pdf",
    ANTLERLESS_DIR / "{year}_PERMITS={target}_MODEL__CWMU_DOE_PRONGHORN_DRAW_RESULTS.pdf",
    ANTLERLESS_DIR / "{year}_PERMITS={target}_MODEL__CWMU_YOUTH_ANTLERLESS_DEER_DRAW_RESULTS.pdf",
    ANTLERLESS_DIR / "{year}_PERMITS={target}_MODEL__CWMU_YOUTH_ANTLERLESS_ELK_DRAW_RESULTS.pdf",
    ANTLERLESS_DIR / "{year}_PERMITS={target}_MODEL__CWMU_YOUTH_ANTLERLESS_PRONGHORN_DRAW_RESULTS.pdf",
    BIG_GAME_DIR / "{year}_PERMITS={target}_MODEL__CWMU_BIG_GAME_BISON_COW_ONLY.pdf",
    BIG_GAME_DIR / "{year}_PERMITS={target}_MODEL__CWMU_BIG_GAME_BISON_HUNTERS_CHOICE.pdf",
    BIG_GAME_DIR / "{year}_PERMITS={target}_MODEL__CWMU_BIG_GAME_BISON_SEX_NOT_STATED_OR_SUMMARY.pdf",
    BIG_GAME_DIR / "{year}_PERMITS={target}_MODEL__CWMU_BIG_GAME_DEER_BUCK.pdf",
    BIG_GAME_DIR / "{year}_PERMITS={target}_MODEL__CWMU_BIG_GAME_DESERT_BIGHORN_SHEEP_SEX_NOT_STATED.pdf",
    BIG_GAME_DIR / "{year}_PERMITS={target}_MODEL__CWMU_BIG_GAME_ELK_BULL.pdf",
    BIG_GAME_DIR / "{year}_PERMITS={target}_MODEL__CWMU_BIG_GAME_MOOSE_BULL.pdf",
    BIG_GAME_DIR / "{year}_PERMITS={target}_MODEL__CWMU_BIG_GAME_MOUNTAIN_GOAT_FEMALE_ONLY.pdf",
    BIG_GAME_DIR / "{year}_PERMITS={target}_MODEL__CWMU_BIG_GAME_MOUNTAIN_GOAT_SEX_NOT_STATED_OR_SUMMARY.pdf",
    BIG_GAME_DIR / "{year}_PERMITS={target}_MODEL__CWMU_BIG_GAME_PRONGHORN_BUCK.pdf",
    BIG_GAME_DIR / "{year}_PERMITS={target}_MODEL__CWMU_BIG_GAME_ROCKY_MOUNTAIN_BIGHORN_SHEEP_SEX_NOT_STATED.pdf",
]


@dataclass(frozen=True)
class PageRef:
    source: Path
    page_index: int
    source_page_count: int
    sample: str


def clean_text(value: str) -> str:
    return " ".join((value or "").split())


def target_prefix(year: int) -> str:
    return f"{year}_PERMITS={year + 1}_MODEL__"


def expected_child_paths(draw_dir: Path, year: int) -> list[Path]:
    return [draw_dir / Path(str(template).format(year=year, target=year + 1)) for template in EXPECTED_CHILDREN]


def classify_cwmu_page(text: str, source_name: str) -> str:
    hay = clean_text(text).upper()
    name = source_name.upper()
    if "CWMU" not in hay:
        return ""

    is_youth = "YOUTH" in hay or "YOUTH" in name
    is_antlerless_draw = "ANTLERLESS" in hay or "DOE PRONGHORN" in hay or "TWO DOE" in hay
    if is_antlerless_draw:
        prefix = "CWMU_YOUTH_" if is_youth else "CWMU_"
        if "PRONGHORN" in hay:
            return prefix + ("ANTLERLESS_PRONGHORN" if is_youth else "DOE_PRONGHORN")
        if "ELK" in hay:
            return prefix + "ANTLERLESS_ELK"
        if "DEER" in hay:
            return prefix + "ANTLERLESS_DEER"
        return prefix + "UNKNOWN"

    if "BISON" in hay:
        if "COW ONLY" in hay or "(COW" in hay:
            return "CWMU_BIG_GAME_BISON_COW_ONLY"
        if "HUNTER" in hay and "CHOICE" in hay:
            return "CWMU_BIG_GAME_BISON_HUNTERS_CHOICE"
        return "CWMU_BIG_GAME_BISON_SEX_NOT_STATED_OR_SUMMARY"
    if "DESERT BIGHORN" in hay:
        return "CWMU_BIG_GAME_DESERT_BIGHORN_SHEEP_SEX_NOT_STATED"
    if "ROCKY" in hay and ("SHEEP" in hay or "BIGHORN" in hay):
        return "CWMU_BIG_GAME_ROCKY_MOUNTAIN_BIGHORN_SHEEP_SEX_NOT_STATED"
    if "MOUNTAIN GOAT" in hay or "MTN GOAT" in hay:
        if "FEMALE" in hay:
            return "CWMU_BIG_GAME_MOUNTAIN_GOAT_FEMALE_ONLY"
        return "CWMU_BIG_GAME_MOUNTAIN_GOAT_SEX_NOT_STATED_OR_SUMMARY"
    if "MOOSE" in hay:
        return "CWMU_BIG_GAME_MOOSE_BULL"
    if "PRONGHORN" in hay:
        return "CWMU_BIG_GAME_PRONGHORN_BUCK"
    if "ELK" in hay:
        return "CWMU_BIG_GAME_ELK_BULL"
    if "DEER" in hay:
        return "CWMU_BIG_GAME_DEER_BUCK"
    return "CWMU_BIG_GAME_UNKNOWN"


def output_path_for(draw_dir: Path, year: int, bucket: str) -> Path:
    if bucket.startswith("CWMU_YOUTH_") or bucket in {
        "CWMU_ANTLERLESS_DEER",
        "CWMU_ANTLERLESS_ELK",
        "CWMU_DOE_PRONGHORN",
    }:
        folder = draw_dir / ANTLERLESS_DIR
    else:
        folder = draw_dir / BIG_GAME_DIR
    return folder / f"{target_prefix(year)}{bucket}_DRAW_RESULTS.pdf"


def first_level_source_candidates(draw_dir: Path) -> list[Path]:
    # First-level species PDFs are the authoritative source. Broad CWMU bundle
    # PDFs duplicate these pages and are moved to ignored parent storage after
    # child PDFs are created.
    return sorted(draw_dir.glob("*.pdf"))


def broad_cwmu_parent_candidates(draw_dir: Path) -> list[Path]:
    parent_dir = draw_dir / "CWMU"
    if not parent_dir.exists():
        return []
    return [
        path
        for path in sorted(parent_dir.rglob("*.pdf"))
        if "CWMU_BIG_GAME_DRAW_RESULTS" in path.name.upper()
        or re.search(r"CWMU_(YOUTH_)?ANTLERLESS_DRAW_RESULTS", path.name.upper())
    ]


def collect_buckets_from_sources(sources: list[Path]) -> dict[str, list[PageRef]]:
    buckets: dict[str, list[PageRef]] = defaultdict(list)
    for source in sources:
        doc = fitz.open(source)
        try:
            for page_index in range(doc.page_count):
                page = doc.load_page(page_index)
                text = page.get_text("text")
                bucket = classify_cwmu_page(text, source.name)
                if not bucket or bucket.endswith("_UNKNOWN"):
                    continue
                sample = clean_text(text.splitlines()[0] if text.splitlines() else "")[:180]
                buckets[bucket].append(PageRef(source, page_index, doc.page_count, sample))
        finally:
            doc.close()
    return buckets


def collect_buckets(draw_dir: Path, extra_sources: list[Path] | None = None) -> dict[str, list[PageRef]]:
    buckets = collect_buckets_from_sources(first_level_source_candidates(draw_dir))
    if extra_sources:
        extra_buckets = collect_buckets_from_sources(extra_sources)
        for bucket, refs in extra_buckets.items():
            buckets[bucket] = refs
    parent_buckets = collect_buckets_from_sources(broad_cwmu_parent_candidates(draw_dir))
    for bucket, refs in parent_buckets.items():
        if bucket not in buckets:
            buckets[bucket] = refs
    return buckets


def write_bucket_pdf(output: Path, refs: list[PageRef], apply: bool) -> str:
    if output.exists():
        return "EXISTS"
    if not refs:
        return "NO_SOURCE_PAGES"
    if not apply:
        return "READY"
    output.parent.mkdir(parents=True, exist_ok=True)
    out = fitz.open()
    try:
        open_docs: dict[Path, fitz.Document] = {}
        for ref in refs:
            doc = open_docs.get(ref.source)
            if doc is None:
                doc = fitz.open(ref.source)
                open_docs[ref.source] = doc
            out.insert_pdf(doc, from_page=ref.page_index, to_page=ref.page_index)
        out.save(output)
    finally:
        out.close()
        for doc in locals().get("open_docs", {}).values():
            doc.close()
    return "CREATED"


def move_broad_cwmu_parents(draw_dir: Path, apply: bool) -> list[dict[str, str]]:
    moved: list[dict[str, str]] = []
    parent_dir = draw_dir / "CWMU"
    ignored_dir = draw_dir.parent / "draw_odds_ignored" / "cwmu_parent_bundles"
    if not parent_dir.exists():
        return moved
    for path in sorted(parent_dir.rglob("*.pdf")):
        upper = path.name.upper()
        if "CWMU_BIG_GAME_DRAW_RESULTS" not in upper and not re.search(r"CWMU_(YOUTH_)?ANTLERLESS_DRAW_RESULTS", upper):
            continue
        target = ignored_dir / path.name
        status = "READY_TO_MOVE"
        if target.exists():
            status = "TARGET_EXISTS"
        elif apply:
            ignored_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            status = "MOVED"
        moved.append({"source_path": str(path), "target_path": str(target), "status": status})
    return moved


def process_year(year: int, apply: bool, extra_sources: list[Path] | None = None) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    draw_dir = PIPELINE_ROOT / str(year) / "pdf" / "draw_odds"
    if not draw_dir.exists():
        return [], []
    buckets = collect_buckets(draw_dir, extra_sources=extra_sources)
    rows: list[dict[str, str]] = []
    for expected in expected_child_paths(draw_dir, year):
        bucket = expected.stem.split("__", 1)[-1].replace("_DRAW_RESULTS", "")
        refs = buckets.get(bucket, [])
        status = write_bucket_pdf(expected, refs, apply=apply)
        rows.append(
            {
                "source_year": str(year),
                "target_year": str(year + 1),
                "bucket": bucket,
                "output_path": str(expected),
                "status": status,
                "page_count": str(len(refs)),
                "source_files": ";".join(sorted({str(ref.source) for ref in refs})),
                "sample": refs[0].sample if refs else "",
            }
        )
    moved = move_broad_cwmu_parents(draw_dir, apply=apply)
    return rows, moved


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create missing child PDFs and move broad CWMU parents.")
    parser.add_argument("--year", action="append", type=int, help="Limit to a source year. Can be repeated.")
    parser.add_argument("--source-dir", action="append", type=Path, help="Additional source directory of PDFs to scan for the selected year.")
    parser.add_argument("--source-file", action="append", type=Path, help="Additional source PDF to scan for the selected year.")
    args = parser.parse_args()

    years = args.year or list(range(2017, 2027))
    extra_sources = []
    for source_dir in args.source_dir or []:
        extra_sources.extend(sorted(path for path in source_dir.rglob("*.pdf") if path.is_file()))
    extra_sources.extend(path for path in args.source_file or [] if path.is_file())
    all_rows: list[dict[str, str]] = []
    all_moves: list[dict[str, str]] = []
    for year in years:
        rows, moves = process_year(year, apply=args.apply, extra_sources=extra_sources if len(years) == 1 else None)
        all_rows.extend(rows)
        all_moves.extend(moves)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    report_dir = AUDIT_ROOT / stamp
    write_csv(
        report_dir / "cwmu_child_pdf_split_plan.csv",
        all_rows,
        ["source_year", "target_year", "bucket", "output_path", "status", "page_count", "source_files", "sample"],
    )
    write_csv(report_dir / "cwmu_parent_bundle_moves.csv", all_moves, ["source_path", "target_path", "status"])
    summary = {
        "ok": True,
        "apply": args.apply,
        "report_dir": str(report_dir),
        "rows": len(all_rows),
        "created": sum(1 for row in all_rows if row["status"] == "CREATED"),
        "ready": sum(1 for row in all_rows if row["status"] == "READY"),
        "exists": sum(1 for row in all_rows if row["status"] == "EXISTS"),
        "no_source_pages": sum(1 for row in all_rows if row["status"] == "NO_SOURCE_PAGES"),
        "moved_parent_bundles": sum(1 for row in all_moves if row["status"] == "MOVED"),
    }
    (report_dir / "cwmu_child_pdf_split_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
