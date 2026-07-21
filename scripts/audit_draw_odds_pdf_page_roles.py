#!/usr/bin/env python3
"""Audit and optionally split yearly draw-odds PDFs by page role and hunt type.

The raw DWR PDFs can mix page roles inside one file. A common case is a first
page with point-purchase summary rows followed by actual draw-result pages. This
script records that page-level structure and can move summary pages into a
separate evidence PDF while rewriting the active source PDF to contain only draw
result pages.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import fitz


REPO = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
RAW_PDFS_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs"
AUDIT_ROOT = REPO / "audits" / "draw_odds_pdf_page_role_audit"


SUMMARY_ROLES = {
    "PREFERENCE_POINT_PURCHASE_SUMMARY",
    "BONUS_POINT_PURCHASE_SUMMARY",
    "POINT_SUMMARY",
    "PERMIT_QUOTA_SUMMARY",
}

PLE_DEER_HUNT_CODES = {f"DB100{i}" for i in range(0, 9)}
MANAGEMENT_DEER_HUNT_CODES = {"DB1009", "DB1010"}


@dataclass(frozen=True)
class PageInfo:
    source_pdf: Path
    source_root_kind: str
    year: int
    page_index: int
    page_number: int
    page_count: int
    page_role: str
    hunt_type: str
    hunt_code: str
    source_title: str
    sample_text: str


def clean_text(value: str) -> str:
    return " ".join((value or "").split())


def upper_text(value: str) -> str:
    return clean_text(value).upper()


def target_prefix(year: int) -> str:
    return f"{year}_PERMITS={year + 1}_MODEL__"


def draw_odds_roots_for_year(year: int) -> list[tuple[str, Path]]:
    pipeline_year_dir = PIPELINE_ROOT / str(year)
    pipeline_dirs = [
        pipeline_year_dir / "pdf" / "draw_odds",
        pipeline_year_dir / "draw_odds",
    ]
    existing_pipeline_dirs = [path for path in pipeline_dirs if path.exists()]
    if existing_pipeline_dirs:
        return [("pipeline_raw", path) for path in existing_pipeline_dirs]

    raw_pdf_dir = RAW_PDFS_ROOT / f"{year}_PERMITS={year + 1}_MODEL"
    if raw_pdf_dir.exists():
        return [("data_truth_raw_pdfs", raw_pdf_dir)]

    return []


def is_candidate_pdf(path: Path) -> bool:
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if path.suffix.lower() != ".pdf":
        return False
    if "backup" in name or ".tmp" in name:
        return False
    if (
        "summary pages" in parts
        or "parent bundles" in parts
        or "duplicate active sources" in parts
        or "merged source fragments" in parts
    ):
        return False
    return True


def extract_source_title(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    for line in lines[:8]:
        if line.startswith("Hunt:") or line.startswith("Species:"):
            return line
    return lines[0] if lines else ""


def extract_hunt_code(text: str) -> str:
    match = re.search(r"\bHunt:\s*([A-Z]{1,3}\d{4})\b", text or "", re.IGNORECASE)
    return match.group(1).upper() if match else ""


def species_from_hunt_code(hunt_code: str) -> str:
    code = (hunt_code or "").upper()
    if code.startswith(("DB", "DA")):
        return "DEER"
    if code.startswith(("EB", "EA")):
        return "ELK"
    if code.startswith(("PB", "PD")):
        return "PRONGHORN"
    if code.startswith(("MB", "MA")):
        return "MOOSE"
    if code.startswith("BI"):
        return "BISON"
    if code.startswith("GO"):
        return "MTN_GOAT"
    if code.startswith("DS"):
        return "DESERT_BIGHORN_SHEEP"
    if code.startswith("RS"):
        return "ROCKY_MOUNTAIN_BIGHORN_SHEEP"
    if code.startswith("BB"):
        return "BLACK_BEAR"
    return ""


def species_from_source_name(source_name: str) -> str:
    hay = upper_text(source_name)
    if "DOE_PRONGHORN" in hay or "DOE PRONGHORN" in hay or "PRONGHORN" in hay:
        return "PRONGHORN"
    if "BUCK_DEER" in hay or "BUCK DEER" in hay or "ANTLERLESS_DEER" in hay or "ANTLERLESS DEER" in hay or "DEER" in hay:
        return "DEER"
    if "BULL_ELK" in hay or "BULL ELK" in hay or "ANTLERLESS_ELK" in hay or "ANTLERLESS ELK" in hay or "ELK" in hay:
        return "ELK"
    if "BULL_MOOSE" in hay or "BULL MOOSE" in hay or "ANTLERLESS_MOOSE" in hay or "ANTLERLESS MOOSE" in hay or "MOOSE" in hay:
        return "MOOSE"
    if "BISON" in hay:
        return "BISON"
    if "MTN_GOAT" in hay or "MTN GOAT" in hay or "MOUNTAIN_GOAT" in hay or "MOUNTAIN GOAT" in hay:
        return "MTN_GOAT"
    if "DESERT_BIGHORN" in hay or "DESERT BIGHORN" in hay:
        return "DESERT_BIGHORN_SHEEP"
    if "ROCKY_MTN" in hay or "ROCKY MTN" in hay or "ROCKY_MOUNTAIN" in hay or "ROCKY MOUNTAIN" in hay:
        return "ROCKY_MOUNTAIN_BIGHORN_SHEEP"
    if "TURKEY" in hay:
        return "TURKEY"
    if "COUGAR" in hay:
        return "COUGAR"
    if "BLACK_BEAR" in hay or "BLACK BEAR" in hay or "BEAR_DRAW" in hay or "BEAR DRAW" in hay:
        return "BLACK_BEAR"
    return ""


def classify_page_role(text: str, source_name: str) -> str:
    hay = upper_text(f"{source_name} {text}")
    if "PERMIT QUOTA" in hay:
        return "PERMIT_QUOTA_SUMMARY"
    if "PREFERENCE POINT PURCHASE RESULTS" in hay:
        return "PREFERENCE_POINT_PURCHASE_SUMMARY"
    if "BONUS POINT PURCHASE RESULTS" in hay:
        return "BONUS_POINT_PURCHASE_SUMMARY"
    if "POINT SUMMARY" in hay or "BONUS POINTS" in hay and "DRAW RESULTS" not in hay:
        return "POINT_SUMMARY"
    if "DRAW RESULTS" in hay or "DRAWING ODDS" in hay or "ODDS REPORT" in hay:
        return "DRAW_RESULTS"
    return "UNKNOWN"


def species_token(hay: str) -> str:
    if "PRONGHORN" in hay:
        return "PRONGHORN"
    if "MOUNTAIN GOAT" in hay or "MTN GOAT" in hay:
        return "MTN_GOAT"
    if "DESERT BIGHORN" in hay:
        return "DESERT_BIGHORN_SHEEP"
    if "ROCKY" in hay and ("BIGHORN" in hay or "SHEEP" in hay):
        return "ROCKY_MOUNTAIN_BIGHORN_SHEEP"
    if "BIGHORN" in hay or "SHEEP" in hay:
        return "BIGHORN_SHEEP"
    if "BISON" in hay:
        return "BISON"
    if "MOOSE" in hay:
        return "MOOSE"
    if "BLACK BEAR" in hay:
        return "BLACK_BEAR"
    if "COUGAR" in hay or "MOUNTAIN LION" in hay:
        return "COUGAR"
    if "TURKEY" in hay:
        return "TURKEY"
    if "ELK" in hay:
        return "ELK"
    if "DEER" in hay:
        return "DEER"
    return "UNKNOWN"


def classify_hunt_type(text: str, source_name: str, hunt_code: str = "") -> str:
    hay = upper_text(f"{source_name} {text}")
    hunt_code = (hunt_code or "").upper()
    species = species_from_hunt_code(hunt_code) or species_from_source_name(source_name) or species_token(hay)
    is_general_season = "GENERAL SEASON" in hay or "G.S." in hay or "G S " in hay

    if "PERMIT QUOTA" in hay:
        if species != "UNKNOWN":
            return f"PERMIT_QUOTA_{species}"
        return "PERMIT_QUOTA_SUMMARY"
    if "SPORTSMAN" in hay:
        return "SPORTSMAN"
    if "CWMU" in hay:
        if "YOUTH" in hay and ("ANTLERLESS" in hay or "DOE PRONGHORN" in hay):
            return f"CWMU_YOUTH_ANTLERLESS_{species}"
        if "ANTLERLESS" in hay or "DOE PRONGHORN" in hay:
            return f"CWMU_ANTLERLESS_{species}"
        return f"CWMU_BIG_GAME_{species}"
    if "LIFETIME" in hay and "DEER" in hay:
        return "LIFETIME_GS_DEER"
    if "YOUTH" in hay and ("DEDICATED HUNTER" in hay or "D.H." in hay or "_D.H" in hay):
        return "YOUTH_DEDICATED_HUNTER_DEER"
    if "DEDICATED HUNTER" in hay or "D.H." in hay or "_D.H" in hay:
        return "DEDICATED_HUNTER_DEER"
    if "YOUTH" in hay and is_general_season and "DEER" in hay:
        return "YOUTH_GS_DEER"
    if "YOUTH" in hay and "ANY BULL" in hay and "ELK" in hay:
        return "YOUTH_ANY_BULL_ELK"
    if "YOUTH" in hay and ("ANTLERLESS" in hay or "DOE PRONGHORN" in hay):
        return f"YOUTH_ANTLERLESS_{species}"
    if is_general_season and "DEER" in hay:
        return "GS_BUCK_DEER"
    if "CACTUS" in hay and "DEER" in hay:
        return "CACTUS_DEER"
    if re.search(r"\bHAMS?\b", hay) or "HAMSS" in hay:
        return "HAMS_DEER" if species == "DEER" else f"HAMS_{species}"
    if hunt_code in MANAGEMENT_DEER_HUNT_CODES or ("MANAGEMENT" in hay and "DEER" in hay):
        return "MANAGEMENT_DEER"
    if hunt_code in PLE_DEER_HUNT_CODES or "P.L.E" in hay or "P L E" in hay or "PREMIUM LIMITED" in hay:
        return "PLE_DEER" if species == "DEER" else f"PLE_{species}"
    if "O.I.L" in hay or "OIL " in hay or "ONCE-IN-A-LIFETIME" in hay or "ONCE IN A LIFETIME" in hay:
        return f"OIL_{species}"
    if "ANTLERLESS MOOSE" in hay:
        return "ANTLERLESS_MOOSE"
    if "ANTLERLESS" in hay or "DOE PRONGHORN" in hay:
        return f"ANTLERLESS_{species}"
    if "L.E" in hay or "LIMITED ENTRY" in hay:
        return f"LE_{species}"
    if species in {"BLACK_BEAR", "COUGAR", "TURKEY"}:
        return species
    return "UNKNOWN"


def page_infos_for_pdf(path: Path, year: int, source_root_kind: str) -> list[PageInfo]:
    infos: list[PageInfo] = []
    with fitz.open(path) as doc:
        page_count = doc.page_count
        for page_index in range(page_count):
            page = doc.load_page(page_index)
            text = page.get_text("text") or ""
            hunt_code = extract_hunt_code(text)
            infos.append(
                PageInfo(
                    source_pdf=path,
                    source_root_kind=source_root_kind,
                    year=year,
                    page_index=page_index,
                    page_number=page_index + 1,
                    page_count=page_count,
                    page_role=classify_page_role(text, path.name),
                    hunt_type=classify_hunt_type(text, path.name, hunt_code),
                    hunt_code=hunt_code,
                    source_title=extract_source_title(text),
                    sample_text=clean_text(text)[:400],
                )
            )
    return infos


def write_csv(path: Path, rows: Iterable[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def has_multiple_hunt_types(hunt_type_counts_json: str) -> bool:
    counts = json.loads(hunt_type_counts_json or "{}")
    return len([hunt_type for hunt_type in counts if hunt_type != "UNKNOWN"]) > 1


def write_page_subset(source: Path, target: Path, page_indexes: list[int]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(source) as src:
        out = fitz.open()
        for page_index in page_indexes:
            out.insert_pdf(src, from_page=page_index, to_page=page_index)
        tmp = target.with_suffix(target.suffix + ".tmp")
        out.save(tmp)
        out.close()
    tmp.replace(target)


def strip_summary_pages(path: Path, infos: list[PageInfo], stamp: str) -> dict[str, object]:
    summary_indexes = [info.page_index for info in infos if info.page_role in SUMMARY_ROLES]
    draw_indexes = [info.page_index for info in infos if info.page_role not in SUMMARY_ROLES]
    if not summary_indexes or not draw_indexes:
        return {"action": "SKIPPED", "reason": "NO_MIXED_SUMMARY_AND_DRAW_PAGES"}

    backup = path.with_name(path.stem + f".backup_with_summary_pages_{stamp}" + path.suffix)
    shutil.copy2(path, backup)

    summary_dir = path.parent / "Summary Pages"
    summary_pdf = summary_dir / (path.stem + "__POINT_PURCHASE_OR_POINT_SUMMARY_PAGES.pdf")
    write_page_subset(path, summary_pdf, summary_indexes)

    tmp = path.with_suffix(path.suffix + ".tmp")
    with fitz.open(path) as src:
        out = fitz.open()
        for page_index in draw_indexes:
            out.insert_pdf(src, from_page=page_index, to_page=page_index)
        out.save(tmp)
        out.close()
    tmp.replace(path)

    return {
        "action": "STRIPPED_SUMMARY_PAGES",
        "reason": "",
        "backup_pdf": str(backup),
        "summary_pdf": str(summary_pdf),
        "summary_pages_removed": len(summary_indexes),
        "pages_before": len(infos),
        "pages_after": len(draw_indexes),
    }


def split_by_hunt_type(path: Path, infos: list[PageInfo]) -> list[dict[str, object]]:
    by_hunt_type: dict[str, list[int]] = defaultdict(list)
    for info in infos:
        if info.page_role in SUMMARY_ROLES:
            continue
        by_hunt_type[info.hunt_type].append(info.page_index)
    if len(by_hunt_type) <= 1:
        return []

    rows: list[dict[str, object]] = []
    split_root = path.parent / "Split By Hunt Type"
    for hunt_type, page_indexes in sorted(by_hunt_type.items()):
        if hunt_type == "UNKNOWN":
            continue
        target = split_root / hunt_type / f"{path.stem}__{hunt_type}.pdf"
        write_page_subset(path, target, page_indexes)
        rows.append(
            {
                "source_pdf": str(path),
                "hunt_type": hunt_type,
                "target_pdf": str(target),
                "page_count": len(page_indexes),
                "source_pages": ",".join(str(index + 1) for index in page_indexes),
            }
        )
    return rows


def move_parent_bundle(path: Path, split_rows: list[dict[str, object]]) -> dict[str, object]:
    if not split_rows:
        return {"source_pdf": str(path), "action": "SKIPPED", "reason": "NO_SPLIT_CHILDREN"}
    parent_dir = path.parent / "Parent Bundles"
    parent_dir.mkdir(parents=True, exist_ok=True)
    target = parent_dir / path.name
    if target.exists():
        return {
            "source_pdf": str(path),
            "action": "SKIPPED",
            "reason": "PARENT_BUNDLE_TARGET_EXISTS",
            "parent_bundle_pdf": str(target),
        }
    shutil.move(str(path), str(target))
    return {
        "source_pdf": str(path),
        "action": "MOVED_PARENT_BUNDLE",
        "reason": "",
        "parent_bundle_pdf": str(target),
        "split_child_count": len(split_rows),
    }


def scan_year(year: int) -> list[PageInfo]:
    infos: list[PageInfo] = []
    for source_root_kind, draw_dir in draw_odds_roots_for_year(year):
        for path in sorted(draw_dir.rglob("*.pdf")):
            if not is_candidate_pdf(path):
                continue
            infos.extend(page_infos_for_pdf(path, year, source_root_kind))
    return infos


def parse_years(value: str) -> list[int]:
    years: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = [int(piece) for piece in part.split("-", 1)]
            years.extend(range(start, end + 1))
        else:
            years.append(int(part))
    return sorted(set(years))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", default="2017-2026", help="Year list/range, e.g. 2017,2018 or 2017-2026.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--strip-summary-pages", action="store_true", help="Move summary pages aside and rewrite mixed PDFs without them.")
    parser.add_argument("--split-hunt-type-pages", action="store_true", help="Write child PDFs for mixed hunt-type page groups.")
    parser.add_argument(
        "--move-mixed-hunt-type-parents",
        action="store_true",
        help="Move mixed hunt-type source PDFs into Parent Bundles after split children are written.",
    )
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    output_dir = args.output_dir or AUDIT_ROOT / stamp
    years = parse_years(args.years)

    all_infos: list[PageInfo] = []
    for year in years:
        all_infos.extend(scan_year(year))

    page_rows = [
        {
            "year": info.year,
            "source_root_kind": info.source_root_kind,
            "source_pdf": str(info.source_pdf),
            "source_pdf_relative": str(info.source_pdf.relative_to(REPO)),
            "page_number": info.page_number,
            "page_count": info.page_count,
            "page_role": info.page_role,
            "hunt_type": info.hunt_type,
            "hunt_code": info.hunt_code,
            "source_title": info.source_title,
            "sample_text": info.sample_text,
        }
        for info in all_infos
    ]
    write_csv(
        output_dir / "page_role_audit.csv",
        page_rows,
        [
            "year",
            "source_root_kind",
            "source_pdf",
            "source_pdf_relative",
            "page_number",
            "page_count",
            "page_role",
            "hunt_type",
            "hunt_code",
            "source_title",
            "sample_text",
        ],
    )

    by_pdf: dict[Path, list[PageInfo]] = defaultdict(list)
    for info in all_infos:
        by_pdf[info.source_pdf].append(info)

    file_rows: list[dict[str, object]] = []
    strip_rows: list[dict[str, object]] = []
    split_rows: list[dict[str, object]] = []
    parent_move_rows: list[dict[str, object]] = []
    for path, infos in sorted(by_pdf.items()):
        role_counts = Counter(info.page_role for info in infos)
        hunt_type_counts = Counter(info.hunt_type for info in infos)
        has_summary = any(role in SUMMARY_ROLES for role in role_counts)
        has_draw = any(role not in SUMMARY_ROLES for role in role_counts)
        mixed_hunt_type = len([hunt_type for hunt_type in hunt_type_counts if hunt_type != "UNKNOWN"]) > 1
        file_rows.append(
            {
                "year": infos[0].year,
                "source_root_kind": infos[0].source_root_kind,
                "source_pdf": str(path),
                "source_pdf_relative": str(path.relative_to(REPO)),
                "page_count": len(infos),
                "page_role_counts_json": json.dumps(dict(sorted(role_counts.items())), sort_keys=True),
                "hunt_type_counts_json": json.dumps(dict(sorted(hunt_type_counts.items())), sort_keys=True),
                "has_summary_pages": str(has_summary).lower(),
                "has_draw_pages": str(has_draw).lower(),
                "mixed_summary_and_draw": str(has_summary and has_draw).lower(),
            }
        )
        if args.strip_summary_pages and has_summary and has_draw:
            result = strip_summary_pages(path, infos, stamp)
            strip_rows.append({"source_pdf": str(path), **result})
        if args.split_hunt_type_pages and mixed_hunt_type:
            path_split_rows = split_by_hunt_type(path, infos)
            split_rows.extend(path_split_rows)
            if args.move_mixed_hunt_type_parents:
                parent_move_rows.append(move_parent_bundle(path, path_split_rows))

    write_csv(
        output_dir / "file_role_audit.csv",
        file_rows,
        [
            "year",
            "source_root_kind",
            "source_pdf",
            "source_pdf_relative",
            "page_count",
            "page_role_counts_json",
            "hunt_type_counts_json",
            "has_summary_pages",
            "has_draw_pages",
            "mixed_summary_and_draw",
        ],
    )
    write_csv(
        output_dir / "summary_page_strip_actions.csv",
        strip_rows,
        ["source_pdf", "action", "reason", "backup_pdf", "summary_pdf", "summary_pages_removed", "pages_before", "pages_after"],
    )
    write_csv(
        output_dir / "hunt_type_split_actions.csv",
        split_rows,
        ["source_pdf", "hunt_type", "target_pdf", "page_count", "source_pages"],
    )
    write_csv(
        output_dir / "parent_bundle_move_actions.csv",
        parent_move_rows,
        ["source_pdf", "action", "reason", "parent_bundle_pdf", "split_child_count"],
    )

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "years": years,
        "pdfs_scanned": len(by_pdf),
        "pages_scanned": len(all_infos),
        "mixed_summary_and_draw_pdfs": sum(1 for row in file_rows if row["mixed_summary_and_draw"] == "true"),
        "mixed_hunt_type_pdfs": sum(1 for row in file_rows if has_multiple_hunt_types(str(row["hunt_type_counts_json"]))),
        "summary_strip_applied": bool(args.strip_summary_pages),
        "summary_strip_actions": len(strip_rows),
        "hunt_type_split_applied": bool(args.split_hunt_type_pages),
        "hunt_type_split_outputs": len(split_rows),
        "parent_bundle_move_applied": bool(args.move_mixed_hunt_type_parents),
        "parent_bundle_move_actions": len(parent_move_rows),
        "output_dir": str(output_dir),
    }
    (output_dir / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
