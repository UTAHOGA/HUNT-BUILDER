"""Build a fail-closed audit of DWR permit recommendations for 2024-2026.

This output is neither draw-result truth nor forecast quota authority.  RAC
packets and recommendation tables are retained only as contemporaneous
supporting evidence.  Historical/scoring truth remains the approved yearly
canonicals and ``draw_results_long.csv``.  A recommendation may be compared
with a separately retained final guidebook or dated Hunt Planner publication,
but it cannot enter a certifying forecast merely because it preceded the draw.

The 2024 DWR tables are image-only.  Hunt codes and table geometry are found
with RapidOCR, and unresolved numeric cells are independently recognized from
tight cell crops with EasyOCR.  A split row is admitted only when resident plus
nonresident equals total.  Allocation-only/private-land rows are excluded.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
import pdfplumber
import pymupdf
from rapidocr_onnxruntime import RapidOCR


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "pipeline" / "manifests" / "utah_dwr_permit_recommendation_sources.csv"
DEFAULT_OUTPUT = ROOT / "processed_data" / "permit_recommendation_crosscheck_2024_2026.csv"
DEFAULT_AUDIT_DIR = (
    ROOT / "audit_output_real_final" / "permit_recommendation_source_review_20260922_v2"
)

CODE_RE = re.compile(r"^(DA|EA|PD|MA|RE)\d{4}$")
PREFERENCE_CONTEXT_PREFIXES = {"DA", "EA", "PD"}
PRIVATE_OR_ALLOCATION = re.compile(
    r"PRIVATE[- ]LANDS|CONTROL UNIT|CONTACT OPERATOR|LANDOWNER|VOUCHER|ALLOCATION",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceReceipt:
    permit_year: int
    family: str
    path: Path
    sha256: str
    pages: int
    original_url: str
    fetch_url: str


def clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def normalized_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()


def integer(value: Any) -> int | None:
    text = clean(value).replace(",", "")
    return int(text) if re.fullmatch(r"\d+", text) else None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path = MANIFEST) -> list[SourceReceipt]:
    if not path.exists():
        raise FileNotFoundError(f"Missing source manifest: {path}")
    receipts: list[SourceReceipt] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            retained = ROOT / clean(row.get("retained_path"))
            if clean(row.get("status")) == "FAILED":
                raise RuntimeError(f"Source manifest contains failed row: {row}")
            if not retained.exists():
                raise FileNotFoundError(f"Missing retained permit source: {retained}")
            measured_sha = file_sha256(retained)
            expected_sha = clean(row.get("sha256"))
            if not expected_sha or measured_sha != expected_sha:
                raise RuntimeError(
                    f"Permit source hash mismatch: {retained} ({measured_sha} != {expected_sha})"
                )
            with pymupdf.open(retained) as document:
                pages = len(document)
            expected_pages = integer(row.get("pages"))
            if expected_pages is None or pages != expected_pages:
                raise RuntimeError(
                    f"Permit source page mismatch: {retained} ({pages} != {expected_pages})"
                )
            receipts.append(
                SourceReceipt(
                    permit_year=int(clean(row.get("permit_year"))),
                    family=clean(row.get("family")),
                    path=retained,
                    sha256=measured_sha,
                    pages=pages,
                    original_url=clean(row.get("original_url")),
                    fetch_url=clean(row.get("fetch_url")),
                )
            )
    return receipts


def base_row(
    receipt: SourceReceipt,
    *,
    permit_year: int,
    family: str,
    page: int,
    hunt_code: str = "",
    unit_name: str = "",
    resident: int | None = None,
    nonresident: int | None = None,
    total: int | None = None,
    extraction_method: str,
    source_timing: str,
) -> dict[str, Any]:
    split = resident is not None or nonresident is not None
    if split and (resident is None or nonresident is None or total is None):
        raise ValueError(f"Incomplete residency split for {hunt_code or unit_name}")
    if split and resident + nonresident != total:
        raise ValueError(
            f"Residency split does not reconcile for {hunt_code or unit_name}: "
            f"{resident}+{nonresident}!={total}"
        )
    if total is None:
        raise ValueError(f"Missing total for {hunt_code or unit_name}")
    return {
        "permit_year": permit_year,
        "family": family,
        "hunt_code": hunt_code,
        "unit_name": clean(unit_name),
        "unit_name_normalized": normalized_name(unit_name),
        "resident_permits": "" if resident is None else resident,
        "nonresident_permits": "" if nonresident is None else nonresident,
        "total_permits": total,
        "permit_scope": "RESIDENCY_SPLIT" if split else "COMBINED_TOTAL",
        "source_path": receipt.path.relative_to(ROOT).as_posix(),
        "source_page": page,
        "source_sha256": receipt.sha256,
        "source_original_url": receipt.original_url,
        "source_fetch_url": receipt.fetch_url,
        "source_timing": source_timing,
        "extraction_method": extraction_method,
        "eligible_for_probability_quota": "false",
        "crosscheck_status": "NOT_AVAILABLE",
        "crosscheck_source_path": "",
        "crosscheck_source_page": "",
        "notes": "",
    }


def parse_machine_readable(receipt: SourceReceipt) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current: list[dict[str, Any]] = []
    retrospective: list[dict[str, Any]] = []
    with pdfplumber.open(receipt.path) as document:
        for page_number, page in enumerate(document.pages, start=1):
            page_text = clean(page.extract_text()).upper()
            if PRIVATE_OR_ALLOCATION.search(page_text):
                continue
            for table in page.extract_tables() or []:
                if len(table) < 3:
                    continue
                width = max((len(row) for row in table), default=0)
                if receipt.family == "buck_deer" and page_number == 1 and width == 9:
                    for row in table[2:]:
                        if len(row) != 9 or not clean(row[0]):
                            continue
                        unit_name_upper = clean(row[0]).upper()
                        if "ALL UNITS" in unit_name_upper or "PUBLIC UNITS" in unit_name_upper:
                            continue
                        target = integer(row[8])
                        prior = integer(row[7])
                        if target is not None:
                            current.append(
                                base_row(
                                    receipt,
                                    permit_year=receipt.permit_year,
                                    family="general_season_buck_deer_unit_quota",
                                    page=page_number,
                                    unit_name=row[0],
                                    total=target,
                                    extraction_method="PDF_TEXT_TABLE",
                                    source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                                )
                            )
                        if prior is not None:
                            retrospective.append(
                                base_row(
                                    receipt,
                                    permit_year=receipt.permit_year - 1,
                                    family="general_season_buck_deer_unit_quota",
                                    page=page_number,
                                    unit_name=row[0],
                                    total=prior,
                                    extraction_method="PDF_TEXT_TABLE_RETROSPECTIVE_COLUMN",
                                    source_timing="FOLLOWING_REPORT_RETROSPECTIVE_CROSSCHECK_ONLY",
                                )
                            )
                    continue

                for row in table[2:]:
                    if not row:
                        continue
                    code = clean(row[0]).upper()
                    if not CODE_RE.fullmatch(code):
                        continue
                    if code[:2] not in PREFERENCE_CONTEXT_PREFIXES:
                        continue
                    family = {
                        "DA": "antlerless_deer",
                        "EA": "antlerless_elk",
                        "PD": "doe_pronghorn",
                        "MA": "antlerless_moose",
                        "RE": "ewe_bighorn_sheep",
                    }[code[:2]]
                    unit_name = row[1] if len(row) > 1 else ""
                    if width == 6:
                        prior = integer(row[4])
                        target = integer(row[5])
                        if target is not None:
                            current.append(
                                base_row(
                                    receipt,
                                    permit_year=receipt.permit_year,
                                    family=family,
                                    page=page_number,
                                    hunt_code=code,
                                    unit_name=unit_name,
                                    total=target,
                                    extraction_method="PDF_TEXT_TABLE",
                                    source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                                )
                            )
                        if prior is not None:
                            retrospective.append(
                                base_row(
                                    receipt,
                                    permit_year=receipt.permit_year - 1,
                                    family=family,
                                    page=page_number,
                                    hunt_code=code,
                                    unit_name=unit_name,
                                    total=prior,
                                    extraction_method="PDF_TEXT_TABLE_RETROSPECTIVE_COLUMN",
                                    source_timing="FOLLOWING_REPORT_RETROSPECTIVE_CROSSCHECK_ONLY",
                                )
                            )
                    elif width == 10:
                        prior_values = [integer(value) for value in row[4:7]]
                        target_values = [integer(value) for value in row[7:10]]
                        if all(value is not None for value in target_values):
                            current.append(
                                base_row(
                                    receipt,
                                    permit_year=receipt.permit_year,
                                    family=family,
                                    page=page_number,
                                    hunt_code=code,
                                    unit_name=unit_name,
                                    resident=target_values[0],
                                    nonresident=target_values[1],
                                    total=target_values[2],
                                    extraction_method="PDF_TEXT_TABLE",
                                    source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                                )
                            )
                        if all(value is not None for value in prior_values):
                            retrospective.append(
                                base_row(
                                    receipt,
                                    permit_year=receipt.permit_year - 1,
                                    family=family,
                                    page=page_number,
                                    hunt_code=code,
                                    unit_name=unit_name,
                                    resident=prior_values[0],
                                    nonresident=prior_values[1],
                                    total=prior_values[2],
                                    extraction_method="PDF_TEXT_TABLE_RETROSPECTIVE_COLUMN",
                                    source_timing="FOLLOWING_REPORT_RETROSPECTIVE_CROSSCHECK_ONLY",
                                )
                            )
    return current, retrospective


def _legacy_split(
    *,
    year: int,
    prefix: str,
    row: list[Any],
) -> tuple[int, int, int] | None:
    """Read the printed residency columns used by the 2019-2022 packets."""
    if len(row) < 6:
        return None
    values = [integer(value) for value in row[3:6]]
    if any(value is None for value in values):
        return None
    first, second, third = (int(value) for value in values)
    if year <= 2020:
        total, resident, nonresident = first, second, third
    elif prefix == "EA":
        nonresident, resident, total = first, second, third
    else:
        resident, nonresident, total = first, second, third
    if resident + nonresident != total:
        raise ValueError(
            f"Legacy packet split does not reconcile: {year} {row[0]} "
            f"{resident}+{nonresident}!={total}"
        )
    return resident, nonresident, total


def _parse_2023_layout_line(line: str) -> tuple[str, list[int | None]] | None:
    match = re.search(r"\b((?:DA|EA|PD)\d{4})\b", line)
    if not match:
        return None
    code = match.group(1)
    tokens = re.findall(r"(?<!\S)(\d[\d,]*|-)(?!\S)", line)
    required = 2 if code.startswith("DA") else 6
    if len(tokens) < required:
        return None
    values = [integer(token) for token in tokens[-required:]]
    return code, values


def parse_legacy_rac_packet(receipt: SourceReceipt) -> list[dict[str, Any]]:
    """Extract cross-check values from retained 2019-2023 RAC packets.

    These are recommendations, not approved draw-result truth or final quota
    authority.  The 2023 packet is a flattened report export, so its printed
    recommendation columns are read from layout-preserving text; earlier
    packets have ordinary PDF tables.
    """
    year = receipt.permit_year
    if year < 2019 or year > 2023:
        return []
    rows: list[dict[str, Any]] = []
    with pdfplumber.open(receipt.path) as document:
        for page_number, page in enumerate(document.pages, start=1):
            page_text = page.extract_text() or ""
            page_upper = clean(page_text).upper()

            if year == 2023:
                if "GENERAL SEASON BUCK DEER" in page_upper:
                    for line in (page.extract_text(layout=True) or "").splitlines():
                        unit_match = re.match(
                            r"\s*(.+?)\s+(?:15|18)[–-](?:17|20)\s+",
                            line,
                        )
                        if not unit_match:
                            continue
                        unit_name = clean(unit_match.group(1))
                        if "GENERAL SEASON" in unit_name.upper() or unit_name.lower().startswith("zz "):
                            continue
                        numeric_tokens = re.findall(r"(?<![\d.])\d[\d,]*(?![\d.])", line)
                        target = integer(numeric_tokens[-1]) if numeric_tokens else None
                        if target is None:
                            continue
                        rows.append(
                            base_row(
                                receipt,
                                permit_year=year,
                                family="general_season_buck_deer_unit_quota",
                                page=page_number,
                                unit_name=unit_name,
                                total=target,
                                extraction_method="PDF_LAYOUT_TEXT_FINAL_PRINTED_COLUMN",
                                source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                            )
                        )
                if not re.search(r"\b(?:DA|EA|PD)\d{4}\b", page_text):
                    continue
                for line in (page.extract_text(layout=True) or "").splitlines():
                    parsed = _parse_2023_layout_line(line)
                    if parsed is None:
                        continue
                    code, values = parsed
                    prefix = code[:2]
                    family = {
                        "DA": "antlerless_deer",
                        "EA": "antlerless_elk",
                        "PD": "doe_pronghorn",
                    }[prefix]
                    if prefix == "DA":
                        target = values[-1]
                        if target is None:
                            continue
                        rows.append(
                            base_row(
                                receipt,
                                permit_year=year,
                                family=family,
                                page=page_number,
                                hunt_code=code,
                                total=target,
                                extraction_method="PDF_LAYOUT_TEXT_FINAL_PRINTED_COLUMN",
                                source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                            )
                        )
                    else:
                        resident, nonresident, total = values[-3:]
                        if None in (resident, nonresident, total):
                            continue
                        rows.append(
                            base_row(
                                receipt,
                                permit_year=year,
                                family=family,
                                page=page_number,
                                hunt_code=code,
                                resident=int(resident),
                                nonresident=int(nonresident),
                                total=int(total),
                                extraction_method="PDF_LAYOUT_TEXT_FINAL_PRINTED_COLUMNS",
                                source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                            )
                        )
                continue

            for table in page.extract_tables() or []:
                for row in table:
                    if not row:
                        continue
                    code = clean(row[0]).upper()
                    if CODE_RE.fullmatch(code) and code[:2] in PREFERENCE_CONTEXT_PREFIXES:
                        prefix = code[:2]
                        family = {
                            "DA": "antlerless_deer",
                            "EA": "antlerless_elk",
                            "PD": "doe_pronghorn",
                        }[prefix]
                        unit_name = row[1] if len(row) > 1 else ""
                        if prefix == "DA":
                            target = integer(row[3]) if len(row) > 3 else None
                            if target is None:
                                continue
                            rows.append(
                                base_row(
                                    receipt,
                                    permit_year=year,
                                    family=family,
                                    page=page_number,
                                    hunt_code=code,
                                    unit_name=unit_name,
                                    total=target,
                                    extraction_method="PDF_TEXT_TABLE_FINAL_PRINTED_COLUMN",
                                    source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                                )
                            )
                            continue
                        split = _legacy_split(year=year, prefix=prefix, row=row)
                        if split is None:
                            continue
                        resident, nonresident, total = split
                        rows.append(
                            base_row(
                                receipt,
                                permit_year=year,
                                family=family,
                                page=page_number,
                                hunt_code=code,
                                unit_name=unit_name,
                                resident=resident,
                                nonresident=nonresident,
                                total=total,
                                extraction_method="PDF_TEXT_TABLE_FINAL_PRINTED_COLUMNS",
                                source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                            )
                        )

                if "GENERAL SEASON BUCK DEER" not in page_upper:
                    continue
                for row in table:
                    if not row:
                        continue
                    if year == 2020 and len(row) >= 8:
                        unit_name, target = row[1], integer(row[7])
                    elif year in {2021, 2022} and len(row) >= 9:
                        unit_name, target = row[0], integer(row[8])
                    else:
                        continue
                    if not clean(unit_name) or target is None:
                        continue
                    if "GENERAL SEASON" in clean(unit_name).upper() or "TOTAL" in clean(unit_name).upper():
                        continue
                    rows.append(
                        base_row(
                            receipt,
                            permit_year=year,
                            family="general_season_buck_deer_unit_quota",
                            page=page_number,
                            unit_name=unit_name,
                            total=target,
                            extraction_method="PDF_TEXT_TABLE_FINAL_PRINTED_COLUMN",
                            source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                        )
                    )
    return rows


def _midpoint(box: Iterable[Iterable[float]]) -> tuple[float, float]:
    points = list(box)
    return (
        sum(float(point[0]) for point in points) / len(points),
        sum(float(point[1]) for point in points) / len(points),
    )


def _easy_reader():
    try:
        import easyocr
    except ImportError as exc:  # fail closed; image-only source cannot be guessed
        raise RuntimeError(
            "EasyOCR is required to verify unresolved 2024 image-table cells"
        ) from exc
    return easyocr.Reader(["en"], gpu=False, verbose=False)


def _tight_cell_value(image: np.ndarray, center_x: float, center_y: float, reader: Any) -> int | None:
    y0, y1 = int(center_y - 17), int(center_y + 18)
    x0, x1 = int(center_x - 36), int(center_x + 36)
    cell = image[max(0, y0) : min(image.shape[0], y1), max(0, x0) : min(image.shape[1], x1)]
    gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(gray < 190)
    if len(xs) == 0:
        return None
    width = int(xs.max() - xs.min() + 1)
    height = int(ys.max() - ys.min() + 1)
    if width > 2.2 * max(1, height):  # printed em dash / no recommendation
        return None
    crop = cell[
        max(0, int(ys.min()) - 3) : min(cell.shape[0], int(ys.max()) + 4),
        max(0, int(xs.min()) - 3) : min(cell.shape[1], int(xs.max()) + 4),
    ]
    crop = cv2.copyMakeBorder(
        crop, 5, 5, 5, 5, cv2.BORDER_CONSTANT, value=(255, 255, 255)
    )
    crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    recognized = reader.recognize(crop, detail=1, allowlist="0123456789-")
    text = "".join(clean(item[1]) for item in recognized)
    return int(text) if text.isdigit() else None


def _candidate_values(value: int | None) -> list[tuple[int | None, int]]:
    if value is None:
        return [(None, 0)]
    candidates: list[tuple[int | None, int]] = [(value, 0)]
    text = str(value)
    # Tight OCR sometimes reads the table separator as an extra leading 1.
    # The correction is admitted only when the three printed cells then obey
    # the independent row invariant resident + nonresident = total.
    for removed in range(1, len(text)):
        shortened = text[removed:]
        if text[:removed] == "1" * removed and shortened:
            candidates.append((int(shortened), removed))
    return candidates


def _reconcile_split(values: list[int | None], identity: str) -> tuple[int, int, int, str]:
    choices: list[tuple[int, int, int, int]] = []
    for resident, r_edits in _candidate_values(values[0]):
        for nonresident, nr_edits in _candidate_values(values[1]):
            for total, t_edits in _candidate_values(values[2]):
                if None in (resident, nonresident, total):
                    continue
                if resident + nonresident == total:
                    choices.append((r_edits + nr_edits + t_edits, resident, nonresident, total))
    if not choices:
        resident, nonresident, total = values
        # A row has three independently printed cells.  If OCR damages one
        # cell but reads total and the other residency cell, the damaged value
        # is recoverable from the table's mandatory arithmetic invariant.  We
        # record that recovery explicitly; two unreadable cells still block.
        if nonresident is not None and total is not None and total >= nonresident:
            return total - nonresident, nonresident, total, "RESIDENT_DERIVED_FROM_PRINTED_TOTAL_MINUS_NONRESIDENT"
        if resident is not None and total is not None and total >= resident:
            return resident, total - resident, total, "NONRESIDENT_DERIVED_FROM_PRINTED_TOTAL_MINUS_RESIDENT"
        if resident is not None and nonresident is not None:
            return resident, nonresident, resident + nonresident, "TOTAL_DERIVED_FROM_PRINTED_RESIDENCY_CELLS"
        raise ValueError(f"OCR residency split is unresolved for {identity}: {values}")
    choices.sort()
    best = choices[0]
    if len(choices) > 1 and choices[1][0] == best[0] and choices[1][1:] != best[1:]:
        raise ValueError(f"OCR residency split is ambiguous for {identity}: {values}")
    action = "DIRECT_OCR_ROW_INVARIANT"
    if best[0]:
        action = "OCR_SEPARATOR_ARTIFACT_REMOVED_BY_PRINTED_ROW_INVARIANT"
    return best[1], best[2], best[3], action


def _rapid_items(pixmap: pymupdf.Pixmap, rapid: RapidOCR) -> tuple[np.ndarray, list[dict[str, Any]]]:
    png = pixmap.tobytes("png")
    image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    result, _ = rapid(png)
    items: list[dict[str, Any]] = []
    for box, text, score in result or []:
        x, y = _midpoint(box)
        items.append(
            {
                "x": x,
                "y": y,
                "text": clean(text).replace(" ", ""),
                "score": float(score),
            }
        )
    return image, items


def _rapid_numeric(items: list[dict[str, Any]], center_x: float, center_y: float) -> int | None:
    matches = [
        item
        for item in items
        if abs(item["x"] - center_x) <= 36
        and abs(item["y"] - center_y) <= 10
        and item["text"].isdigit()
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: (abs(item["x"] - center_x), -item["score"]))
    return int(matches[0]["text"])


def parse_2024_image_tables(receipt: SourceReceipt) -> list[dict[str, Any]]:
    if receipt.permit_year != 2024:
        return []
    rapid = RapidOCR()
    easy = _easy_reader()
    rows: list[dict[str, Any]] = []
    with pymupdf.open(receipt.path) as document:
        for page_number, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=False)
            image, items = _rapid_items(pixmap, rapid)

            if receipt.family == "buck_deer" and page_number == 1:
                header = [
                    item for item in items if item["y"] < 310 and "RECOMMENDED2024" in item["text"].upper()
                ]
                if len(header) != 1:
                    raise ValueError("Could not locate 2024 general-deer quota column")
                target_x = header[0]["x"]
                for item in items:
                    if not (310 < item["y"] < pixmap.height - 300):
                        continue
                    if not item["text"].isdigit() or abs(item["x"] - target_x) > 35:
                        continue
                    same_line = [
                        candidate
                        for candidate in items
                        if candidate["x"] < 570
                        and abs(candidate["y"] - item["y"]) <= 5
                        and candidate["text"]
                    ]
                    if not same_line:
                        continue
                    same_line.sort(key=lambda candidate: candidate["x"])
                    unit_name = " ".join(candidate["text"] for candidate in same_line)
                    if "ALLUNITS" in unit_name.upper() or "PUBLICUNITS" in unit_name.upper():
                        continue
                    rows.append(
                        base_row(
                            receipt,
                            permit_year=2024,
                            family="general_season_buck_deer_unit_quota",
                            page=page_number,
                            unit_name=unit_name,
                            total=int(item["text"]),
                            extraction_method="RAPIDOCR_IMAGE_TABLE",
                            source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                        )
                    )
                continue

            code_items = [
                item
                for item in items
                if CODE_RE.fullmatch(item["text"])
                and item["text"][:2] in PREFERENCE_CONTEXT_PREFIXES
            ]
            if not code_items:
                continue
            page_upper = " ".join(item["text"].upper() for item in items if item["y"] < 430)
            if PRIVATE_OR_ALLOCATION.search(page_upper):
                continue
            code_items.sort(key=lambda item: item["y"])

            if all(item["text"].startswith("DA") for item in code_items):
                year_headers = [
                    item for item in items if item["y"] < 380 and item["text"] == "2024"
                ]
                if not year_headers:
                    raise ValueError(f"Could not locate target total column on page {page_number}")
                total_x = max(item["x"] for item in year_headers)
                centers = [total_x]
            else:
                res_headers = sorted(
                    item["x"]
                    for item in items
                    if 300 < item["y"] < 380 and item["text"] == "Res"
                )
                total_headers = [
                    item["x"]
                    for item in items
                    if 300 < item["y"] < 380 and item["text"] == "Total"
                ]
                if len(res_headers) < 2 or not total_headers:
                    raise ValueError(f"Could not locate target split columns on page {page_number}")
                centers = [res_headers[-2], res_headers[-1], max(total_headers)]

            for code_item in code_items:
                values: list[int | None] = []
                for center_x in centers:
                    value = _rapid_numeric(items, center_x, code_item["y"])
                    if value is None:
                        value = _tight_cell_value(image, center_x, code_item["y"], easy)
                    values.append(value)
                code = code_item["text"]
                if all(value is None for value in values):
                    continue
                same_line_names = [
                    item
                    for item in items
                    if 390 < item["x"] < 610
                    and abs(item["y"] - code_item["y"]) <= 7
                    and item["text"]
                ]
                same_line_names.sort(key=lambda item: item["x"])
                unit_name = " ".join(item["text"] for item in same_line_names)
                family = {
                    "DA": "antlerless_deer",
                    "EA": "antlerless_elk",
                    "PD": "doe_pronghorn",
                    "MA": "antlerless_moose",
                    "RE": "ewe_bighorn_sheep",
                }[code[:2]]
                if len(values) == 1:
                    if values[0] is None:
                        continue
                    row = base_row(
                        receipt,
                        permit_year=2024,
                        family=family,
                        page=page_number,
                        hunt_code=code,
                        unit_name=unit_name,
                        total=values[0],
                        extraction_method="RAPIDOCR_IMAGE_TABLE_WITH_CELL_RECOGNITION",
                        source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                    )
                else:
                    resident, nonresident, total, reconciliation_note = _reconcile_split(values, code)
                    row = base_row(
                        receipt,
                        permit_year=2024,
                        family=family,
                        page=page_number,
                        hunt_code=code,
                        unit_name=unit_name,
                        resident=resident,
                        nonresident=nonresident,
                        total=total,
                        extraction_method="RAPIDOCR_IMAGE_TABLE_WITH_CELL_RECOGNITION",
                        source_timing="PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY",
                    )
                    row["notes"] = reconciliation_note
                rows.append(row)
    return rows


def row_key(row: dict[str, Any]) -> tuple[Any, ...]:
    identity = clean(row.get("hunt_code")) or normalized_name(row.get("unit_name"))
    return int(row["permit_year"]), clean(row["family"]), identity


def values_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        integer(row.get("resident_permits")),
        integer(row.get("nonresident_permits")),
        integer(row.get("total_permits")),
    )


def attach_crosschecks(
    current: list[dict[str, Any]], retrospective: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    retrospective_by_key: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in retrospective:
        retrospective_by_key.setdefault(row_key(row), []).append(row)
    mismatches: list[dict[str, Any]] = []
    for row in current:
        candidates = retrospective_by_key.get(row_key(row), [])
        if not candidates:
            row["crosscheck_status"] = "NO_RETROSPECTIVE_ROW"
            continue
        exact = [candidate for candidate in candidates if values_key(candidate) == values_key(row)]
        if len(exact) == 1:
            candidate = exact[0]
            row["crosscheck_status"] = "EXACT_MATCH"
            row["crosscheck_source_path"] = candidate["source_path"]
            row["crosscheck_source_page"] = candidate["source_page"]
        elif len(exact) > 1:
            row["crosscheck_status"] = "EXACT_MATCH_DUPLICATE_RETROSPECTIVE_ROWS"
            candidate = exact[0]
            row["crosscheck_source_path"] = candidate["source_path"]
            row["crosscheck_source_page"] = candidate["source_page"]
        else:
            row["crosscheck_status"] = (
                "OFFICIAL_RETROSPECTIVE_DIFFERENCE_RETAIN_SAME_YEAR_PRE_DRAW"
            )
            mismatches.append(
                {
                    "key": row_key(row),
                    "same_year_values": values_key(row),
                    "same_year_source": row["source_path"],
                    "retrospective_values": [values_key(candidate) for candidate in candidates],
                    "retrospective_sources": [candidate["source_path"] for candidate in candidates],
                }
            )
    return current, mismatches


def assert_unique(rows: list[dict[str, Any]]) -> None:
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = row_key(row)
        prior = seen.get(key)
        if prior is None:
            seen[key] = row
            continue
        if values_key(prior) != values_key(row):
            raise ValueError(f"Conflicting same-year permit rows for {key}")
        raise ValueError(f"Duplicate same-year permit rows for {key}")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build(
    *, output: Path = DEFAULT_OUTPUT, audit_dir: Path = DEFAULT_AUDIT_DIR
) -> dict[str, Any]:
    receipts = read_manifest()
    current: list[dict[str, Any]] = []
    retrospective: list[dict[str, Any]] = []
    for receipt in receipts:
        if receipt.family == "cwmu_antlerless":
            continue  # different public/private identity contract; audited separately
        if receipt.family == "april_rac_packet":
            # Retain the legacy packet receipts, but do not promote their
            # recommendation cells into the machine quota context.  Historical
            # folds continue to use source-year canonical awards as declared by
            # the accepted engine architecture.
            continue
        if receipt.family == "antlerless" and receipt.permit_year in {2021, 2022}:
            # Two-page recommendation summaries do not provide hunt-level
            # identities; the full packets above are the row-level evidence.
            continue
        if receipt.permit_year == 2024:
            current.extend(parse_2024_image_tables(receipt))
        else:
            current_rows, retrospective_rows = parse_machine_readable(receipt)
            current.extend(current_rows)
            retrospective.extend(retrospective_rows)
    assert_unique(current)
    current, mismatches = attach_crosschecks(current, retrospective)
    current.sort(key=row_key)
    write_csv(output, current)
    audit_dir.mkdir(parents=True, exist_ok=True)
    mismatch_path = audit_dir / "pre_draw_permit_crosscheck_mismatches.json"
    mismatch_path.write_text(json.dumps(mismatches, indent=2) + "\n", encoding="utf-8")
    summary = {
        "status": (
            "PASS"
            if not mismatches
            else "PASS_WITH_RECORDED_RETROSPECTIVE_DIFFERENCES"
        ),
        "output": output.relative_to(ROOT).as_posix(),
        "row_count": len(current),
        "year_counts": {
            str(year): sum(int(row["permit_year"]) == year for row in current)
            for year in sorted({int(row["permit_year"]) for row in current})
        },
        "family_counts": {
            family: sum(row["family"] == family for row in current)
            for family in sorted({str(row["family"]) for row in current})
        },
        "crosscheck_counts": {
            status: sum(row["crosscheck_status"] == status for row in current)
            for status in sorted({str(row["crosscheck_status"]) for row in current})
        },
        "crosscheck_mismatches": len(mismatches),
        "private_or_allocation_rows_admitted": 0,
        "source_role": "PRE_DRAW_RECOMMENDATION_CROSSCHECK_NOT_DRAW_RESULT_TRUTH",
        "forecast_authority": "NONE_RECOMMENDATIONS_REQUIRE_FINAL_PUBLISHED_CONFIRMATION",
        "retrospective_role": "NUMERIC_CROSSCHECK_ONLY",
    }
    (audit_dir / "pre_draw_permit_context_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    args = parser.parse_args()
    summary = build(output=args.output, audit_dir=args.audit_dir)
    print(json.dumps(summary, indent=2))
    return 0 if str(summary["status"]).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
