"""Current-year permit/allotment compatibility helpers.

Runtime quota authority is the published ``permits_2026_*`` fields in
DATABASE.csv. Legacy ``permit_allotment_2026_*`` fields are carried for audit
and compatibility only; they must not backfill public prediction quotas.
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
    del truth_root
    return {}


def apply_current_year_allotments_to_rows(
    rows: list[dict[str, str]],
    allotments: dict[str, CurrentYearAllotment] | None = None,
) -> list[dict[str, str]]:
    del allotments
    return [dict(row) for row in rows]


def current_year_quota_for_residency(row: Mapping[str, str], residency: str) -> int:
    residency_text = clean(residency).lower()
    if residency_text.startswith("non"):
        return to_int(row.get("permits_2026_nr"))
    if residency_text.startswith("res"):
        return to_int(row.get("permits_2026_res"))
    return to_int(row.get("permits_2026_total"))
