"""Current-year permit allotment helpers.

Direct hunt-code rows in normalized RAC files are the canonical current-year
available permit/allotment source. Existing DATABASE/runtime 2026 permit fields
are retained as fallback when no direct RAC row exists.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


REPO = Path(__file__).resolve().parents[2]
DEFAULT_TRUTH_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv"
RAC_SOURCE_LABEL = "2026_RAC_CURRENT_YEAR_ALLOTMENT"
FALLBACK_SOURCE_LABEL = "FALLBACK_EXISTING_2026_PERMITS"

RAC_EXCLUDE_TOKENS = (
    "comparison",
    "supplemental",
    "permit_rows_from_pdf",
    "control_units",
)

ALLOTMENT_FIELDS = [
    "permit_allotment_2026_res",
    "permit_allotment_2026_nr",
    "permit_allotment_2026_total",
    "permit_allotment_2026_source",
    "permit_allotment_2026_source_file",
    "permit_allotment_2026_status",
]


@dataclass(frozen=True)
class CurrentYearAllotment:
    hunt_code: str
    res: str
    nr: str
    total: str
    source_file: str
    has_split: bool


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text in {"-", "–", "—"}:
        return ""
    return text


def to_int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if text == "":
        return ""
    try:
        number = float(text)
    except ValueError:
        return ""
    if number.is_integer():
        return str(int(number))
    return str(number)


def to_int(value: object) -> int:
    text = to_int_text(value)
    return int(text) if text else 0


def first_nonempty(*values: object) -> str:
    for value in values:
        text = clean(value)
        if text:
            return text
    return ""


def _row_total(row: Mapping[str, str]) -> str:
    total = to_int_text(row.get("permits_2026_total"))
    if total:
        return total
    res = to_int_text(row.get("permits_2026_res"))
    nr = to_int_text(row.get("permits_2026_nr"))
    if res or nr:
        return str(int(res or 0) + int(nr or 0))
    return ""


def _choose(existing: CurrentYearAllotment | None, candidate: CurrentYearAllotment) -> CurrentYearAllotment:
    if existing is None:
        return candidate
    if candidate.has_split and not existing.has_split:
        return candidate
    if candidate.total and not existing.total:
        return candidate
    return existing


def load_rac_current_year_allotments(
    truth_root: Path | str = DEFAULT_TRUTH_ROOT,
) -> dict[str, CurrentYearAllotment]:
    root = Path(truth_root)
    allotments: dict[str, CurrentYearAllotment] = {}
    for path in sorted(root.glob("2026_rac_*.csv")):
        if any(token in path.name for token in RAC_EXCLUDE_TOKENS):
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "hunt_code" not in reader.fieldnames:
                continue
            for row in reader:
                hunt_code = clean(row.get("hunt_code")).upper()
                if not hunt_code:
                    continue
                res = to_int_text(row.get("permits_2026_res"))
                nr = to_int_text(row.get("permits_2026_nr"))
                total = _row_total(row)
                if not (res or nr or total):
                    continue
                candidate = CurrentYearAllotment(
                    hunt_code=hunt_code,
                    res=res,
                    nr=nr,
                    total=total,
                    source_file=path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else path.as_posix(),
                    has_split=bool(res or nr),
                )
                allotments[hunt_code] = _choose(allotments.get(hunt_code), candidate)
    return allotments


def apply_current_year_allotments_to_rows(
    rows: list[dict[str, str]],
    allotments: dict[str, CurrentYearAllotment] | None = None,
) -> list[dict[str, str]]:
    source = allotments if allotments is not None else load_rac_current_year_allotments()
    overlaid: list[dict[str, str]] = []
    for row in rows:
        next_row = dict(row)
        hunt_code = clean(next_row.get("hunt_code")).upper()
        allotment = source.get(hunt_code)
        if allotment:
            next_row["permit_allotment_2026_res"] = allotment.res
            next_row["permit_allotment_2026_nr"] = allotment.nr
            next_row["permit_allotment_2026_total"] = allotment.total
            next_row["permit_allotment_2026_source"] = RAC_SOURCE_LABEL
            next_row["permit_allotment_2026_source_file"] = allotment.source_file
            next_row["permit_allotment_2026_status"] = (
                "RAC_CURRENT_YEAR_SPLIT" if allotment.has_split else "RAC_CURRENT_YEAR_TOTAL_ONLY"
            )
        else:
            res = to_int_text(next_row.get("permits_2026_res"))
            nr = to_int_text(next_row.get("permits_2026_nr"))
            total = _row_total(next_row)
            if res or nr or total:
                next_row["permit_allotment_2026_res"] = res
                next_row["permit_allotment_2026_nr"] = nr
                next_row["permit_allotment_2026_total"] = total
                next_row["permit_allotment_2026_source"] = FALLBACK_SOURCE_LABEL
                next_row["permit_allotment_2026_source_file"] = clean(next_row.get("permits_2026_source"))
                next_row["permit_allotment_2026_status"] = "FALLBACK_EXISTING_2026_PERMITS"
        overlaid.append(next_row)
    return overlaid


def current_year_quota_for_residency(row: Mapping[str, str], residency: str) -> int:
    residency_text = clean(residency).lower()
    source = clean(row.get("permit_allotment_2026_source"))
    if source == RAC_SOURCE_LABEL:
        if residency_text.startswith("non"):
            return to_int(row.get("permit_allotment_2026_nr"))
        if residency_text.startswith("res"):
            return to_int(row.get("permit_allotment_2026_res"))
        return to_int(row.get("permit_allotment_2026_total"))

    if residency_text.startswith("non"):
        return to_int(first_nonempty(row.get("permit_allotment_2026_nr"), row.get("permits_2026_nr")))
    if residency_text.startswith("res"):
        return to_int(first_nonempty(row.get("permit_allotment_2026_res"), row.get("permits_2026_res")))
    return to_int(first_nonempty(row.get("permit_allotment_2026_total"), row.get("permits_2026_total")))
