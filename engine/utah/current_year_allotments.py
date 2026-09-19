"""Current-year permit/allotment compatibility helpers.

DATABASE.csv supplies current hunt identity and published permit references.
An explicitly supplied official general-deer regular-round snapshot may add
separate target_permits_* context without changing the Board/Planner fields.
Legacy permit_allotment_2026_* values must not backfill prediction quotas.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
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


def apply_official_general_deer_regular_quotas(rows, source_path: Path, forecast_year: int):
    """Attach exact official regular-round context, never drawing outcomes.

    Explicit opt-in for a current target build only. Historical fold builders
    never call this helper. The caller records the immutable payload hash.
    Existing Planner/Board permit fields are preserved, not overwritten.
    """
    payload = json.loads(source_path.read_text(encoding="utf-8-sig"))
    if payload.get("Status") != 0:
        raise ValueError("Official general-deer quota source is not successful")
    norm = lambda value: re.sub(r"[^a-z0-9]+", "", clean(value).lower())
    def weapon(value):
        token = norm(value)
        return {"anylegalweaponlate": "anylegalweapon", "anylegalweaponearly": "earlyanylegalweapon"}.get(token, token)
    def season_matches(row, season):
        if not clean(row.get("season")):
            return False
        dates = re.findall(r"([A-Za-z]+)\s+(\d{1,2})\s+(\d{4})", row["season"])
        if len(dates) != 2:
            return False
        parsed = [datetime.strptime(f"{m[:3]} {d} {y}", "%b %d %Y").date().isoformat() for m, d, y in dates]
        return parsed == [clean(season.get(k))[:10] for k in ("SeasonStartDate", "SeasonEndDate")]
    official = {}
    for hunt in payload["Data"]:
        code = clean(hunt.get("HuntCode"))
        if not code.startswith("DB") or code == "DB0008" or norm(hunt.get("HuntCategoryName")) != "generalseason":
            continue
        if code in official:
            raise ValueError(f"Duplicate official general-deer code: {code}")
        official[code] = hunt
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    result, audit = [], []
    for original in rows:
        row = dict(original)
        hunt = official.get(clean(row.get("hunt_code")))
        if hunt is not None:
            seasons = hunt.get("SeasonWeapons") or []
            name_pair = (norm(row.get("hunt_name")), norm(hunt.get("HuntName")))
            name_matches = name_pair[0] == name_pair[1] or name_pair == ("lasalmtns", "lasallasalmtns")
            if (not name_matches
                    or norm(row.get("species")) != "deer" or norm(row.get("sex_type")) != "buck"
                    or not any(int(s.get("LicenseYear") or 0) == forecast_year
                               and weapon(s.get("WeaponName")) == weapon(row.get("weapon"))
                               and season_matches(row, s) for s in seasons)):
                raise ValueError(f"Current deer quota identity mismatch: {row.get('hunt_code')}")
            values = [hunt.get(k) for k in ("ResidentRegularRoundQuota", "NonResidentRegularRoundQuota", "RegularRoundQuota")]
            if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in values) or values[0] + values[1] != values[2]:
                raise ValueError(f"Unreconciled official regular quotas: {row.get('hunt_code')}")
            row.update({
                "target_permits_res": str(values[0]), "target_permits_nr": str(values[1]),
                "target_permits_total": str(values[2]), "target_permits_scope": "REGULAR_DRAW_AFTER_PROGRAM_ALLOCATIONS",
                "target_permits_source": str(source_path), "target_permits_source_sha256": source_hash,
                "target_permits_source_fields": "ResidentRegularRoundQuota;NonResidentRegularRoundQuota;RegularRoundQuota",
                "target_permits_year": str(forecast_year),
            })
            audit.append({k: row[k] for k in ("hunt_code", "hunt_name", "weapon", "target_permits_res", "target_permits_nr", "target_permits_total", "target_permits_scope")})
        result.append(row)
    unmatched = sorted(set(official) - {row["hunt_code"] for row in audit})
    if unmatched:
        raise ValueError(f"Official current deer hunts absent from target inventory: {unmatched}")
    return result, {"status": "PASS", "source": str(source_path), "sha256": source_hash,
                    "forecast_year": forecast_year, "source_eligible_hunts": len(official),
                    "matched_hunts": len(audit), "rows": audit,
                    "historical_use": "PROHIBITED", "drawing_outcomes_read": False}
