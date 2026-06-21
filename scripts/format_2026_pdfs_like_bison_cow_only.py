"""Wrap selected 2026 PDFs in the bison-cow-only branded landscape style.

The source PDFs are preserved as page content. This script adds a consistent
header, table-frame style, and footer without re-parsing or rewriting numbers.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2026\.pdf")
OUTPUT_DIR = ROOT / "output" / "pdf" / "2026_formatted_like_bison_cow_only"
AUDIT_DIR = ROOT / "audits" / "pdf_formatting" / "2026_formatted_like_bison_cow_only"

REFERENCE = SOURCE_DIR / "bison cow only.pdf"

SOURCE_FILES = [
    "rm  sheep non res.pdf",
    "rm sheep res.pdf",
    "bison non res.pdf",
    "bison res.pdf",
    "black bear pursuit res.pdf",
    "deer  buck non res l.e..pdf",
    "des sheep nr.pdf",
    "desert sheep res.pdf",
    "goat non res.pdf",
    "goat res.pdf",
    "gs deer nr.pdf",
    "gs deer res.pdf",
    "gs der res.pdf",
    "le buck deer.pdf",
    "le buck prong.pdf",
    "le elk nr.pdf",
    "le elk.pdf",
    "mtn goat res.pdf",
    "nr le buck deer.pdf",
    "oil moose.pdf",
    "bison 2.pdf",
    "bear pursuit non res.pdf",
]

ADDITIONAL_SOURCE_FILES = [
    Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2026\bear nr.pdf"),
    Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2026\bear.pdf"),
]

COVER_PAGE_ONLY_FILES = {
    "rm sheep res.pdf",
    "bison non res.pdf",
    "bison res.pdf",
    "des sheep nr.pdf",
    "desert sheep res.pdf",
    "goat non res.pdf",
    "goat res.pdf",
    "gs der res.pdf",
    "le buck deer.pdf",
    "le elk nr.pdf",
    "le elk.pdf",
    "mtn goat res.pdf",
    "nr le buck deer.pdf",
    "oil moose.pdf",
}

IMPORT_ROTATION_OVERRIDE = {
    "bear.pdf": 270,
}

PAGE_W = 1218.46
PAGE_H = 941.538

WHITE = (1, 1, 1)
DARK_BROWN = (0.20, 0.12, 0.06)
MED_BROWN = (0.43, 0.27, 0.14)
TAN = (0.92, 0.84, 0.71)
GREEN_BLACK = (0.08, 0.18, 0.14)
ORANGE = (0.82, 0.39, 0.13)
LIGHT = (0.98, 0.96, 0.91)


def clean_title(name: str) -> str:
    stem = Path(name).stem.lower().replace("l.e.", "le")
    tokens = re.sub(r"[^a-z0-9]+", " ", stem).split()
    replacements = {
        "nr": "Nonresident",
        "res": "Resident",
        "rm": "Rocky Mountain",
        "gs": "General Season",
        "der": "Deer",
        "le": "Limited Entry",
        "des": "Desert",
        "mtn": "Mountain",
        "oil": "O.I.L.",
    }
    words: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "non" and index + 1 < len(tokens) and tokens[index + 1] == "res":
            words.append("Nonresident")
            index += 2
            continue
        words.append(replacements.get(token, token.title()))
        index += 1
    return " ".join(words).upper()


def safe_name(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return f"2026_PERMITS_2027_MODEL__{stem}__UOGA_FORMATTED.pdf"


def draw_brand_frame(page: fitz.Page, title: str, source_name: str, page_index: int, page_total: int) -> fitz.Rect:
    page.draw_rect(fitz.Rect(0, 0, PAGE_W, PAGE_H), color=WHITE, fill=WHITE)

    # Corner identity marks: simple vector placeholders matching the reference's
    # visual placement without depending on external logo image files.
    page.draw_circle(fitz.Point(112, 120), 52, color=DARK_BROWN, fill=DARK_BROWN)
    page.insert_textbox(
        fitz.Rect(70, 94, 154, 146),
        "U.O.G.A",
        fontsize=17,
        fontname="helv",
        color=WHITE,
        align=fitz.TEXT_ALIGN_CENTER,
    )
    page.insert_textbox(
        fitz.Rect(PAGE_W - 172, 82, PAGE_W - 72, 154),
        "UTAH\nWILDLIFE",
        fontsize=15,
        fontname="helv",
        color=DARK_BROWN,
        align=fitz.TEXT_ALIGN_CENTER,
    )

    page.insert_textbox(
        fitz.Rect(210, 82, PAGE_W - 210, 124),
        title,
        fontsize=24,
        fontname="helv",
        color=(0, 0, 0),
        align=fitz.TEXT_ALIGN_CENTER,
    )
    page.insert_textbox(
        fitz.Rect(210, 122, PAGE_W - 210, 152),
        "UTAH OUTFITTER AND GUIDE ASSOCIATION",
        fontsize=12,
        fontname="helv",
        color=DARK_BROWN,
        align=fitz.TEXT_ALIGN_CENTER,
    )

    outer = fitz.Rect(62, 202, PAGE_W - 62, PAGE_H - 94)
    page.draw_rect(outer, color=DARK_BROWN, width=2.0)
    page.draw_rect(fitz.Rect(outer.x0, outer.y0, outer.x1, outer.y0 + 34), color=DARK_BROWN, fill=DARK_BROWN)
    page.draw_rect(fitz.Rect(outer.x0, outer.y0 + 34, outer.x1, outer.y0 + 70), color=MED_BROWN, fill=TAN)
    page.draw_rect(fitz.Rect(outer.x0, outer.y0 + 70, outer.x1, outer.y0 + 100), color=GREEN_BLACK, fill=GREEN_BLACK)

    page.insert_textbox(
        fitz.Rect(outer.x0 + 12, outer.y0 + 8, outer.x1 - 12, outer.y0 + 28),
        "2026 Utah Draw Results - Source Page Reformatted for Review",
        fontsize=12,
        fontname="helv",
        color=WHITE,
        align=fitz.TEXT_ALIGN_CENTER,
    )
    page.insert_textbox(
        fitz.Rect(outer.x0 + 12, outer.y0 + 42, outer.x1 - 12, outer.y0 + 64),
        f"{source_name}  |  page {page_index + 1} of {page_total}",
        fontsize=11,
        fontname="helv",
        color=DARK_BROWN,
        align=fitz.TEXT_ALIGN_CENTER,
    )

    content = fitz.Rect(outer.x0 + 18, outer.y0 + 112, outer.x1 - 18, outer.y1 - 32)
    page.draw_rect(content + (-4, -4, 4, 4), color=(0.75, 0.70, 0.62), fill=LIGHT)
    page.insert_textbox(
        fitz.Rect(outer.x0 + 12, outer.y1 - 24, outer.x1 - 12, outer.y1 - 8),
        "Data Source: Utah Division of Wildlife Resources / Formatting layer: U.O.G.A review document",
        fontsize=7,
        fontname="helv",
        color=(0.35, 0.35, 0.35),
        align=fitz.TEXT_ALIGN_CENTER,
    )
    return content


def is_cover_page(source_path: Path, source_page: fitz.Page, source_index: int, source_page_count: int) -> bool:
    if source_index != 0 or source_page_count <= 1:
        return False
    if source_path.name.lower() in COVER_PAGE_ONLY_FILES:
        return True
    text = (source_page.get_text("text") or "").lower()
    if "hunt:" in text:
        return False
    cover_markers = [
        "udwr draw odds",
        "draw odds",
        "data are draw odds",
        "for historical draw odds",
        "frequently asked questions",
    ]
    return any(marker in text for marker in cover_markers)


def format_pdf(source_path: Path) -> dict[str, object]:
    source = fitz.open(str(source_path))
    out = fitz.open()
    title = clean_title(source_path.name)
    out_path = OUTPUT_DIR / safe_name(source_path.name)
    source_page_count = len(source)
    kept_indices = [
        index
        for index in range(source_page_count)
        if not is_cover_page(source_path, source[index], index, source_page_count)
    ]
    if not kept_indices:
        kept_indices = list(range(source_page_count))
    for output_index, index in enumerate(kept_indices):
        page = out.new_page(width=PAGE_W, height=PAGE_H)
        content = draw_brand_frame(page, title, source_path.name, output_index, len(kept_indices))
        source_rotation = int(source[index].rotation or 0)
        import_rotation = IMPORT_ROTATION_OVERRIDE.get(
            source_path.name.lower(),
            (360 - source_rotation) % 360,
        )
        page.show_pdf_page(content, source, index, keep_proportion=True, rotate=import_rotation)
    out.save(str(out_path), deflate=True, garbage=4)
    source.close()
    out.close()
    return {
        "source_file": str(source_path),
        "output_file": str(out_path),
        "source_pages": source_page_count,
        "output_pages": len(kept_indices),
        "cover_pages_removed": source_page_count - len(kept_indices),
        "output_bytes": out_path.stat().st_size,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    missing = []
    source_paths = [SOURCE_DIR / name for name in SOURCE_FILES] + ADDITIONAL_SOURCE_FILES
    for path in source_paths:
        if not path.exists():
            missing.append(str(path))
            continue
        results.append(format_pdf(path))

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "reference_pdf": str(REFERENCE),
        "output_dir": str(OUTPUT_DIR),
        "source_dir": str(SOURCE_DIR),
        "source_files_requested": len(source_paths),
        "source_files_formatted": len(results),
        "missing_source_files": missing,
        "total_output_bytes": sum(int(row["output_bytes"]) for row in results),
        "results": results,
        "note": "Source pages were visually embedded into a UOGA/bison-cow-only style frame; source values were not re-parsed or modified.",
    }
    (AUDIT_DIR / "FORMAT_2026_PDFS_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    with (AUDIT_DIR / "formatted_2026_pdf_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        import csv

        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_file",
                "output_file",
                "source_pages",
                "output_pages",
                "cover_pages_removed",
                "output_bytes",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
