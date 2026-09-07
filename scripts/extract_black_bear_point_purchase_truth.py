#!/usr/bin/env python3
"""Extract statewide limited-entry black-bear bonus-point purchases from DWR PDFs.

These tables describe the statewide pool of point holders, not hunt-specific
applications or draw outcomes.  They must remain outside draw-result
canonicals and are retained as a separate, hash-linked behavioral input for
future, source-backed Bear cohort evaluation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path
from typing import Iterable

import pdfplumber


REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = (
    REPO
    / "data_truth"
    / "point_purchase_truth"
    / "black_bear_limited_entry_bonus_point_purchases_2018_2025.csv"
)
POINT_ROW = re.compile(r"^(?P<points>\d+)(?:\s+(?P<resident>[\d,]+))?(?:\s+(?P<nonresident>[\d,]+))?$")
TOTAL_ROW = re.compile(r"^Totals\s+(?P<resident>[\d,]+)\s+Totals\s+(?P<nonresident>[\d,]+)$")
TOTAL_ROW_NEW = re.compile(r"^Totals\s+(?P<resident>[\d,]+)\s+(?P<nonresident>[\d,]+)$")


def _as_int(value: str | None) -> int:
    return int((value or "0").replace(",", ""))


def parse_purchase_page(text: str) -> tuple[dict[int, tuple[int, int]], tuple[int, int]]:
    """Parse one DWR statewide point-purchase table from extracted PDF text."""

    rows: dict[int, tuple[int, int]] = {}
    declared_totals: tuple[int, int] | None = None
    legacy_repeated_point_layout = "TOTAL TOTAL" in text.upper()
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        total_match = TOTAL_ROW.match(line) or TOTAL_ROW_NEW.match(line)
        if total_match:
            declared_totals = (
                _as_int(total_match.group("resident")),
                _as_int(total_match.group("nonresident")),
            )
            continue
        tokens = line.split()
        # In 2018-2020 DWR printed one shared physical line as
        # `points resident points nonresident`, including both point labels.
        # Newer layouts print `points resident nonresident` only once.
        if tokens and all(token.replace(",", "").isdigit() for token in tokens):
            points = _as_int(tokens[0])
            if legacy_repeated_point_layout:
                if len(tokens) == 2:
                    resident, nonresident = 0, 0
                elif len(tokens) == 3 and _as_int(tokens[1]) == points:
                    resident, nonresident = 0, _as_int(tokens[2])
                elif len(tokens) == 3:
                    resident, nonresident = _as_int(tokens[1]), 0
                elif _as_int(tokens[2]) == points:
                    resident, nonresident = _as_int(tokens[1]), _as_int(tokens[3])
                else:
                    raise ValueError(f"Unrecognized legacy point-purchase row: {line}")
            else:
                resident = _as_int(tokens[1]) if len(tokens) > 1 else 0
                nonresident = _as_int(tokens[2]) if len(tokens) > 2 else 0
        else:
            match = POINT_ROW.match(line)
            if not match:
                continue
            points = _as_int(match.group("points"))
            resident = _as_int(match.group("resident"))
            nonresident = _as_int(match.group("nonresident"))
        rows[points] = (resident, nonresident)
    if declared_totals is None:
        raise ValueError("DWR point-purchase table has no parseable Totals row")
    return rows, declared_totals


def _is_limited_entry_purchase_page(year: int, text: str) -> bool:
    upper = text.upper()
    if "BONUS POINT PURCHASE RESULTS" not in upper:
        return False
    if year <= 2020:
        return "LIMITED ENTRY BEAR" in upper
    # In newer reports page one is the limited-entry Bear point-purchase pool;
    # restricted pursuit has its own explicitly labelled table.
    return "SPECIES: BEAR" in upper and "RESTRICTED PURSUIT" not in upper


def _source_pdf(year: int) -> Path:
    path = (
        REPO
        / "pipeline"
        / "RAW"
        / "hunt_unit_database"
        / str(year)
        / "pdf"
        / "draw_odds"
        / "official_dwr_archive"
        / "black_bear"
        / f"{str(year)[-2:]}_drawing_odds.pdf"
    )
    if not path.exists():
        raise FileNotFoundError(f"Missing retained official DWR Black Bear PDF: {path}")
    return path


def extract_year(year: int) -> tuple[list[dict[str, object]], dict[str, object]]:
    source = _source_pdf(year)
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    with pdfplumber.open(source) as pdf:
        matches = [
            (page_number, page.extract_text() or "")
            for page_number, page in enumerate(pdf.pages, start=1)
            if _is_limited_entry_purchase_page(year, page.extract_text() or "")
        ]
    if len(matches) != 1:
        raise ValueError(f"Expected one limited-entry purchase page for {year}; found {len(matches)}")
    page_number, text = matches[0]
    point_rows, declared_totals = parse_purchase_page(text)
    computed_totals = (
        sum(resident for resident, _ in point_rows.values()),
        sum(nonresident for _, nonresident in point_rows.values()),
    )
    if computed_totals != declared_totals:
        raise ValueError(
            f"{year} DWR purchase totals do not reconcile: parsed {computed_totals}, "
            f"published {declared_totals}"
        )
    source_relative = source.relative_to(REPO).as_posix()
    records: list[dict[str, object]] = []
    for points in sorted(point_rows, reverse=True):
        resident, nonresident = point_rows[points]
        for residency, applicants in (("Resident", resident), ("Nonresident", nonresident)):
            records.append(
                {
                    "draw_year": year,
                    "point_program": "BLACK_BEAR_LIMITED_ENTRY_BONUS_POINT_PURCHASE",
                    "residency": residency,
                    "points": points,
                    "point_purchase_applicants": applicants,
                    "source_file": source_relative,
                    "source_sha256": source_sha256,
                    "pdf_page": page_number,
                    "source_scope": "STATEWIDE_POINT_PURCHASE_NOT_HUNT_DRAW_RESULT",
                    "qa_status": "PASS_PUBLISHED_TOTAL_RECONCILED",
                }
            )
    return records, {
        "year": year,
        "pdf_page": page_number,
        "resident_total": declared_totals[0],
        "nonresident_total": declared_totals[1],
        "source_sha256": source_sha256,
    }


def write_records(records: Iterable[dict[str, object]], out_path: Path) -> None:
    rows = list(records)
    if not rows:
        raise ValueError("No point-purchase rows were extracted")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--replace", action="store_true", help="Allow replacing an existing output file.")
    args = parser.parse_args()
    if args.end_year < args.start_year:
        raise SystemExit("--end-year must be at least --start-year")
    if args.out.exists() and not args.replace:
        raise SystemExit(f"Refusing to overwrite existing output without --replace: {args.out}")

    records: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    for year in range(args.start_year, args.end_year + 1):
        year_records, summary = extract_year(year)
        records.extend(year_records)
        summaries.append(summary)
    write_records(records, args.out)
    print(f"Wrote {len(records)} source-backed point-purchase rows to {args.out}")
    for summary in summaries:
        print(
            f"{summary['year']}: page {summary['pdf_page']}; "
            f"resident {summary['resident_total']}; nonresident {summary['nonresident_total']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
