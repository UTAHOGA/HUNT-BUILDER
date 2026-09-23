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
    matched_codes = set()
    for original in rows:
        row = dict(original)
        hunt = official.get(clean(row.get("hunt_code")))
        if hunt is not None:
            code = clean(row.get("hunt_code"))
            if code in matched_codes:
                raise ValueError(f"Duplicate target general-deer code: {code}")
            matched_codes.add(code)
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
                    "residency_total_check": "PASS",
                    "residency_total_check_count": len(audit),
                    "historical_use": "PROHIBITED", "drawing_outcomes_read": False}


def export_current_deer_allocations(database_path: Path, source_path: Path,
                                    output_dir: Path, forecast_year: int):
    """Materialize current target rows with the existing opt-in quota feeder.

    This is a local current-year input, not a new historical truth authority or
    a prediction release. Protected inputs are never written. An existing
    output directory is rejected rather than overwriting a prior review.
    """
    if output_dir.exists():
        raise ValueError(f"Output directory already exists: {output_dir}")
    with database_path.open(encoding="utf-8-sig", newline="") as handle:
        original = list(csv.DictReader(handle))
    enriched, audit = apply_official_general_deer_regular_quotas(
        original, source_path, forecast_year)
    codes = {row["hunt_code"] for row in audit["rows"]}
    if not codes:
        raise ValueError("No official current general-deer allocations to export")
    selected = [row for row in enriched if clean(row.get("hunt_code")) in codes]
    audit.update({
        "database_identity_source": str(database_path),
        "database_sha256": hashlib.sha256(database_path.read_bytes()).hexdigest(),
        "publication_status": "LOCAL_CURRENT_TARGET_INPUT_ONLY",
        "planner_fields_overwritten": False,
        "historical_canonicals_changed": False,
        "residency_rows": len(selected) * 2,
    })
    lanes = []
    for row in selected:
        for residency, key in (("Resident", "target_permits_res"),
                               ("Nonresident", "target_permits_nr")):
            lanes.append({"hunt_code": row["hunt_code"], "residency": residency,
                          "draw_allocation": row[key],
                          "draw_allocation_total": row["target_permits_total"],
                          "scope": row["target_permits_scope"],
                          "source_sha256": row["target_permits_source_sha256"]})
    output_dir.mkdir(parents=True)
    for name, data in (("current_general_deer_target_rows.csv", selected),
                       ("current_general_deer_residency_rows.csv", lanes)):
        path = output_dir / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
        audit.setdefault("outputs", {})[name] = {
            "rows": len(data), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (output_dir / "official_general_deer_regular_quota_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    return audit


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export official current general-deer residency allocations; no engine build or promotion.")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--forecast-year", type=int, required=True)
    args = parser.parse_args()
    report = export_current_deer_allocations(args.database, args.source, args.output_dir, args.forecast_year)
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
