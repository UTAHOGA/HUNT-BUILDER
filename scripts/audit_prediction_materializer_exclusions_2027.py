"""Audit materialized prediction rows against non-public draw guardrails.

This audit verifies that rows retained for conservation overlays, CWMU/contact-
operator references, private-land unpublished/reference rows, Sportsman-only
rows, and no-quota rows are not leaking into public draw-odds probability math.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
PROCESSED = ROOT / "processed_data"
AUDITS = PROCESSED / "audits"

OUTPUT_FILES = [
    PROCESSED / "ml_draw_predictions_v1.csv",
    PROCESSED / "draw_reality_engine_predictive_v2.csv",
    PROCESSED / "phase6_bonus_special_predictions_v1.csv",
    PROCESSED / "sportsman_permit_predictions_v1.csv",
    PROCESSED / "private_lands_antlerless_elk_predictions_v1.csv",
    PROCESSED / "bear_draw_predictions_v1.csv",
    PROCESSED / "turkey_bonus_predictions_v1.csv",
    PROCESSED / "youth_draw_predictions_v1.csv",
    PROCESSED / "dedicated_hunter_predictions_v1.csv",
]

PROBABILITY_FIELDS = [
    "p_draw_mean",
    "p_draw",
    "p_draw_pct",
    "display_odds_pct",
    "p_bonus_pool",
    "p_random_pool",
    "p_preference_draw",
]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def clean_lower(value: object) -> str:
    return clean(value).lower()


def numeric(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[Mapping[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def db_by_code() -> dict[str, dict[str, str]]:
    rows = read_csv(DATABASE)
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if code and code not in out:
            out[code] = row
    return out


def db_permit_total(row: Mapping[str, str]) -> float:
    total = numeric(row.get("permits_2026_total"))
    if total is not None:
        return total
    res = numeric(row.get("permits_2026_res")) or 0.0
    nr = numeric(row.get("permits_2026_nr")) or 0.0
    return res + nr


def probability_fields_present(row: Mapping[str, str]) -> list[str]:
    present = []
    for field in PROBABILITY_FIELDS:
        if clean(row.get(field)) not in {"", "Not available"}:
            present.append(field)
    return present


def exclusion_buckets(output_row: Mapping[str, str], db_row: Mapping[str, str] | None) -> list[str]:
    buckets: list[str] = []
    row_text = " ".join(
        clean_lower(output_row.get(field))
        for field in ("hunt_code", "hunt_name", "species", "hunt_type", "hunt_class", "draw_system_type", "draw_pool", "season_dates")
    )
    db_text = ""
    if db_row:
        db_text = " ".join(
            clean_lower(db_row.get(field))
            for field in (
                "hunt_code",
                "hunt_name",
                "species",
                "hunt_type",
                "hunt_class",
                "draw_2026_system_type",
                "permit_allotment_2026_status",
                "season",
                "NOTES",
            )
        )

    combined = f"{row_text} {db_text}"
    draw_system = clean(output_row.get("draw_system_type")) or clean(db_row.get("draw_2026_system_type") if db_row else "")
    algorithm_status = clean(output_row.get("algorithm_status"))

    if "conservation" in combined or "organizations" in combined:
        buckets.append("CONSERVATION_OR_ORGANIZATION")
    if draw_system == "SPORTSMAN_PERMIT" or "sportsman" in combined:
        buckets.append("SPORTSMAN_RANDOM_ONLY")
    if "cwmu" in combined or "contact operator" in combined or "contact cwmu operator" in combined:
        buckets.append("CWMU_OR_CONTACT_OPERATOR")
    if "private land only" in combined or "private lands only" in combined or "permit_data_not_published" in combined:
        buckets.append("PRIVATE_LAND_REFERENCE_OR_UNPUBLISHED")

    no_quota = False
    if db_row is not None:
        no_quota = db_permit_total(db_row) <= 0
        status = clean_lower(db_row.get("permit_allotment_2026_status"))
        if "no_quota" in status or "not_published" in status or "reference" in status:
            no_quota = True
    if no_quota and algorithm_status not in {"MODELED_AVAILABILITY", "MODELED_ALLOCATION"}:
        buckets.append("NO_PUBLIC_QUOTA")

    return list(dict.fromkeys(buckets))


def is_allowed_separate_model(row: Mapping[str, str], buckets: list[str], source_file: str) -> bool:
    draw_system = clean(row.get("draw_system_type"))
    status = clean(row.get("algorithm_status"))
    if "SPORTSMAN_RANDOM_ONLY" in buckets:
        return draw_system == "SPORTSMAN_PERMIT" and status == "MODELED_SPORTSMAN_DRAW" and source_file == "sportsman_permit_predictions_v1.csv"
    if "PRIVATE_LAND_REFERENCE_OR_UNPUBLISHED" in buckets:
        return status in {"MODELED_ALLOCATION", "IN_SCOPE_MODEL_PENDING"} and not probability_fields_present(row)
    return False


def main() -> int:
    db = db_by_code()
    audit_rows: list[dict[str, object]] = []
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(DATABASE.relative_to(ROOT)),
        "files_checked": [],
        "row_count": 0,
        "excluded_bucket_row_counts": {},
        "violation_count": 0,
        "violation_counts_by_bucket": {},
        "sportsman_separate_model_rows": 0,
        "private_land_allocation_reference_rows": 0,
        "pass": False,
    }

    bucket_counts: Counter[str] = Counter()
    violation_counts: Counter[str] = Counter()

    for path in OUTPUT_FILES:
        rows = read_csv(path)
        if not rows:
            continue
        source_file = path.name
        summary["files_checked"].append(str(path.relative_to(ROOT)))
        for index, row in enumerate(rows, start=2):
            summary["row_count"] += 1
            code = clean(row.get("hunt_code")).upper()
            db_row = db.get(code)
            buckets = exclusion_buckets(row, db_row)
            if not buckets:
                continue
            for bucket in buckets:
                bucket_counts[bucket] += 1

            allowed = is_allowed_separate_model(row, buckets, source_file)
            if allowed and "SPORTSMAN_RANDOM_ONLY" in buckets:
                summary["sportsman_separate_model_rows"] += 1
            if allowed and "PRIVATE_LAND_REFERENCE_OR_UNPUBLISHED" in buckets:
                summary["private_land_allocation_reference_rows"] += 1

            present_probability_fields = probability_fields_present(row)
            violation_reason = ""
            if not allowed and present_probability_fields:
                violation_reason = "EXCLUDED_BUCKET_HAS_PUBLIC_PROBABILITY_FIELDS"
            if not allowed and "SPORTSMAN_RANDOM_ONLY" in buckets and source_file != "sportsman_permit_predictions_v1.csv" and present_probability_fields:
                violation_reason = "SPORTSMAN_PROBABILITY_ON_PUBLIC_SURFACE"
            if not allowed and "CWMU_OR_CONTACT_OPERATOR" in buckets and present_probability_fields:
                violation_reason = "CWMU_CONTACT_OPERATOR_PUBLIC_ODDS_LEAK"
            if not allowed and "CONSERVATION_OR_ORGANIZATION" in buckets and present_probability_fields:
                violation_reason = "CONSERVATION_PUBLIC_ODDS_LEAK"
            if not allowed and "NO_PUBLIC_QUOTA" in buckets and present_probability_fields:
                violation_reason = "NO_QUOTA_PUBLIC_ODDS_LEAK"

            if not violation_reason:
                continue

            for bucket in buckets:
                violation_counts[bucket] += 1
            audit_rows.append(
                {
                    "source_file": source_file,
                    "row_number": index,
                    "hunt_code": code,
                    "hunt_name": clean(row.get("hunt_name")) or clean(db_row.get("hunt_name") if db_row else ""),
                    "species": clean(row.get("species")) or clean(db_row.get("species") if db_row else ""),
                    "residency": clean(row.get("residency")),
                    "points": clean(row.get("points")),
                    "draw_system_type": clean(row.get("draw_system_type")),
                    "algorithm_status": clean(row.get("algorithm_status")),
                    "db_hunt_type": clean(db_row.get("hunt_type") if db_row else ""),
                    "db_hunt_class": clean(db_row.get("hunt_class") if db_row else ""),
                    "db_permits_2026_res": clean(db_row.get("permits_2026_res") if db_row else ""),
                    "db_permits_2026_nr": clean(db_row.get("permits_2026_nr") if db_row else ""),
                    "db_permits_2026_total": clean(db_row.get("permits_2026_total") if db_row else ""),
                    "db_permit_status": clean(db_row.get("permit_allotment_2026_status") if db_row else ""),
                    "exclusion_buckets": "|".join(buckets),
                    "probability_fields_present": "|".join(present_probability_fields),
                    "violation_reason": violation_reason,
                }
            )

    summary["excluded_bucket_row_counts"] = dict(sorted(bucket_counts.items()))
    summary["violation_count"] = len(audit_rows)
    summary["violation_counts_by_bucket"] = dict(sorted(violation_counts.items()))
    summary["pass"] = len(audit_rows) == 0

    AUDITS.mkdir(parents=True, exist_ok=True)
    detail_path = AUDITS / "prediction_materializer_exclusion_guardrail_2027.csv"
    summary_path = AUDITS / "prediction_materializer_exclusion_guardrail_2027_summary.json"
    write_csv(
        detail_path,
        audit_rows,
        [
            "source_file",
            "row_number",
            "hunt_code",
            "hunt_name",
            "species",
            "residency",
            "points",
            "draw_system_type",
            "algorithm_status",
            "db_hunt_type",
            "db_hunt_class",
            "db_permits_2026_res",
            "db_permits_2026_nr",
            "db_permits_2026_total",
            "db_permit_status",
            "exclusion_buckets",
            "probability_fields_present",
            "violation_reason",
        ],
    )
    summary["detail_csv"] = str(detail_path.relative_to(ROOT))
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
