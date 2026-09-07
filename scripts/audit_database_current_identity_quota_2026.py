"""Audit DATABASE.csv as the current DWR identity/quota reference.

This does not use historical draw-result canonicals as a current-quota feeder.
Those canonicals and draw_results_long.csv remain the historical prediction
truth.  The current quota reference is reconciled independently against the
retained 2026 DWR Hunt Planner extraction and the two narrower, source-backed
non-draw permit feeders that intentionally supersede its generic popup values.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
PLANNER = ROOT / "processed_data/dwr_huntplanner_hanumber_2026.csv"
EA_OVERLAY = ROOT / "data_truth/permit_overlay_truth/normalized/elk_antlerless_private_lands_EA_2026_canonical.csv"
TURKEY_FEEDER = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/2026 turkey either sex all reviewed total.csv"
OUTPUT_DIR = ROOT / "processed_data/audits"
OUTPUT_CSV = OUTPUT_DIR / "database_current_identity_quota_2026_feeder_audit.csv"
OUTPUT_JSON = OUTPUT_DIR / "database_current_identity_quota_2026_feeder_audit_summary.json"

QUOTA_FIELDS = ("permits_2026_res", "permits_2026_nr", "permits_2026_total")
STALE_CONSERVATION_CODE = "BR7324"
PD1056_REVIEWED_QUOTA = ("36", "4", "40")
BR7004_DRAW_RESULT_QUOTA = ("18", "2", "20")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def compact(values: tuple[str, str, str]) -> tuple[str, str, str]:
    return tuple((value or "").strip() for value in values)


def quota(row: dict[str, str], prefix: str = "permits_2026_") -> tuple[str, str, str]:
    return compact(tuple(row.get(f"{prefix}{part}", "") for part in ("res", "nr", "total")))


def nonnegative_int(value: str) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def is_total_only_semantic_match(database_quota: tuple[str, str, str], planner_quota: tuple[str, str, str]) -> bool:
    planner_res, planner_nr, planner_total = planner_quota
    return (
        planner_res == "0"
        and planner_nr == "0"
        and planner_total not in ("", "0")
        and database_quota == ("", "", planner_total)
    )


def is_split_total_derived_match(database_quota: tuple[str, str, str], planner_quota: tuple[str, str, str]) -> bool:
    planner_res, planner_nr, planner_total = planner_quota
    res = nonnegative_int(planner_res)
    nr = nonnegative_int(planner_nr)
    if res is None or nr is None or planner_total != "0" or (res + nr) == 0:
        return False
    return database_quota == (planner_res, planner_nr, str(res + nr))


def is_no_quota_semantic_match(database_quota: tuple[str, str, str], planner_quota: tuple[str, str, str]) -> bool:
    return planner_quota == ("0", "0", "0") and database_quota in {("", "", ""), ("0", "0", "0")}


def source_total_map(rows: list[dict[str, str]]) -> dict[str, str]:
    return {row["hunt_code"].strip(): row.get("permits_2026_total", "").strip() for row in rows if row.get("hunt_code")}


def repair_stale_conservation_reference(database_rows: list[dict[str, str]], planner_by_code: dict[str, dict[str, str]]) -> bool:
    row = next((candidate for candidate in database_rows if candidate.get("hunt_code") == STALE_CONSERVATION_CODE), None)
    planner = planner_by_code.get(STALE_CONSERVATION_CODE)
    if row is None or planner is None:
        raise RuntimeError("BR7324 is missing from DATABASE.csv or the retained DWR Planner extract.")
    if planner.get("hunt_year") == "2026":
        raise RuntimeError("Refusing BR7324 repair: retained Planner source now reports it as a 2026 hunt.")
    if planner.get("dwr_hunt_type") != "Conservation" or planner.get("permits_2026_total") != "0":
        raise RuntimeError("Refusing BR7324 repair: source no longer proves non-current conservation reference status.")
    if row.get("conservation_permits_2026_total") != "1":
        raise RuntimeError("Refusing BR7324 repair: dedicated conservation count is not preserved.")

    expected = {
        "permits_2026_res": "",
        "permits_2026_nr": "",
        "permits_2026_total": "",
        "permit_allotment_2026_res": "",
        "permit_allotment_2026_nr": "",
        "permit_allotment_2026_total": "",
        "permits_2026_source": "DWR_HUNT_PLANNER_HUNT_YEAR_2025_CONSERVATION_REFERENCE_NOT_CURRENT_2026_QUOTA",
        "permit_allotment_2026_source": "DWR_HUNT_PLANNER_HUNT_YEAR_2025_CONSERVATION_REFERENCE_NOT_CURRENT_2026_QUOTA",
        "permit_allotment_2026_source_file": "processed_data/dwr_huntplanner_hanumber_2026.csv",
        "permit_allotment_2026_status": "NONCURRENT_CONSERVATION_REFERENCE_NO_2026_PUBLIC_QUOTA",
    }
    changed = any(row.get(key, "") != value for key, value in expected.items())
    row.update(expected)
    return changed


def classify(
    database_row: dict[str, str],
    planner_row: dict[str, str] | None,
    ea_totals: dict[str, str],
    turkey_totals: dict[str, str],
) -> dict[str, str]:
    code = database_row["hunt_code"]
    db_quota = quota(database_row)
    result = {
        "hunt_code": code,
        "database_quota": "/".join(db_quota),
        "planner_quota": "",
        "identity_status": "NO_RETAINED_CURRENT_PLANNER_RECORD",
        "quota_status": "DATABASE_SUPPORT_OR_HISTORICAL_REFERENCE",
        "resolution_source": "",
        "unresolved_current_delta": "NO",
        "reason": "No current 2026 DWR Hunt Planner record was retained for this database support/reference row.",
    }
    if planner_row is None:
        return result

    planner_quota = quota(planner_row)
    result["planner_quota"] = "/".join(planner_quota)
    # Hunt codes are the identity key.  DWR's hunt-type/sex labels can differ
    # legitimately from the locally normalized display taxonomy, so species is
    # the only second identity check here.  A difference in it is material.
    species_conflict = database_row.get("species", "").strip().casefold() != planner_row.get("dwr_species", "").strip().casefold()
    result["identity_status"] = "DWR_CURRENT_CODE_AND_SPECIES_MATCH" if not species_conflict else "DWR_CURRENT_CODE_SPECIES_CONFLICT"
    if species_conflict:
        result["unresolved_current_delta"] = "YES"
        result["quota_status"] = "IDENTITY_FIELD_CONFLICT"
        result["reason"] = "Current DWR source conflicts on species identity."
        return result

    # These two differences have retained, code-specific official resolution.
    # They are evaluated before generic popup semantics so the report states
    # precisely why the more complete source value is kept.
    if code == "PD1056" and db_quota == PD1056_REVIEWED_QUOTA and "USER_CONFIRMED_PD1056" in database_row.get("permits_2026_source", ""):
        result.update(
            quota_status="OFFICIAL_PD1056_TYPO_OVERRIDE_CONFIRMED_BY_DRAW_ODDS",
            resolution_source="processed_data/audits/reviewed_permit_value_overrides_2026.csv + official 2026 DWR draw odds",
            reason="Raw Planner 63/4/0 is a documented typo; reviewed DWR Planner and official draw odds both retain 36/4/40.",
        )
        return result
    if code == "BR7004" and db_quota == BR7004_DRAW_RESULT_QUOTA:
        result.update(
            quota_status="OFFICIAL_DRAW_RESULT_SPLIT_RECONCILES_PLANNER_TOTAL",
            resolution_source="2025 Big Game Bear Draw Results (2026 quota) + retained 2026 DWR current-source reconciliation",
            reason="Planner total is 20 but its 18/0 split is incomplete; official draw results supply the complete 18/2/20 residency outcome.",
        )
        return result

    # These rows are deliberately retained as non-public allocation/reference
    # data.  A generic Planner popup of 0/0/0 is not evidence that a Sportsman,
    # youth set-aside, conservation, or tribal value should be erased or used
    # as a public-draw probability.
    draw_design = database_row.get("draw_design", "").strip()
    hunt_type = database_row.get("hunt_type", "").strip().casefold()
    hunt_class = database_row.get("hunt_class", "").strip().casefold()
    if code == "EB1007" and db_quota[2] == planner_quota[2] == "750":
        result.update(
            quota_status="OFFICIAL_YOUTH_SET_ASIDE_SPLIT_RETAINED_PLANNER_TOTAL_MATCH",
            resolution_source=database_row.get("permits_2026_source", "") or "retained EB1007 youth source",
            reason="Planner publishes the 750 total only; the source-classified youth set-aside retains its reviewed 675/75 lane split and is not a general public-draw quota.",
        )
        return result
    if draw_design == "SPORTSMAN_RANDOM_ONLY":
        result.update(
            quota_status="SPORTSMAN_PERMIT_REFERENCE_SEPARATE_FROM_GENERIC_PLANNER_QUOTA",
            resolution_source=database_row.get("permits_2026_source", "") or "official Sportsman draw results",
            reason="Sportsman permits are a separate random draw; generic Planner 0/0/0 fields do not replace the retained Sportsman permit record.",
        )
        return result
    if code != STALE_CONSERVATION_CODE and (
        "conservation" in hunt_type
        or hunt_type == "tribal"
        or hunt_class in {"organizations", "tribal"}
        or draw_design in {"REFERENCE_ONLY", "TRIBAL", "YOUTH_TURKEY_SET_ASIDE"}
    ):
        result.update(
            quota_status="NONPUBLIC_ALLOCATION_OR_REFERENCE_SEPARATE_FROM_GENERIC_PLANNER_QUOTA",
            resolution_source=database_row.get("permits_2026_source", "") or database_row.get("conservation_permits_2026_source", "") or "retained official allocation/reference source",
            reason="Conservation, tribal, youth-set-aside, or reference-only row; it is excluded from public-draw odds and retained separately from generic Planner quota fields.",
        )
        return result

    if code == STALE_CONSERVATION_CODE:
        if planner_row.get("hunt_year") != "2026" and db_quota == ("", "", "") and database_row.get("conservation_permits_2026_total") == "1":
            result.update(
                quota_status="NONCURRENT_CONSERVATION_REFERENCE_SEPARATED",
                resolution_source="retained DWR Planner BR7324 (hunt_year=2025) + dedicated conservation_permits_2026_total",
                reason="The 2025-27 conservation-cycle permit is retained only in the dedicated conservation field; current 2026 public-draw quota fields are blank.",
            )
            return result
        result.update(
            quota_status="STALE_CURRENT_QUOTA_FIELD",
            unresolved_current_delta="YES",
            reason="Non-current conservation reference still occupies a current 2026 quota field.",
        )
        return result

    if planner_row.get("hunt_year") != "2026":
        if db_quota == ("", "", ""):
            result.update(
                quota_status="NONCURRENT_PLANNER_REFERENCE_NO_CURRENT_QUOTA",
                resolution_source="retained DWR Planner hunt-year field",
                reason=f"Retained Planner record is hunt year {planner_row.get('hunt_year')}; no numeric current quota is carried.",
            )
        else:
            result.update(
                quota_status="NONCURRENT_PLANNER_WITH_CURRENT_QUOTA",
                unresolved_current_delta="YES",
                reason=f"Retained Planner record is hunt year {planner_row.get('hunt_year')} but DATABASE.csv carries a current quota.",
            )
        return result

    if code in turkey_totals and db_quota == ("", "", turkey_totals[code]) and planner_quota[2] != turkey_totals[code]:
        result.update(
            quota_status="OFFICIAL_TURKEY_WORKBOOK_SUPERSEDES_GENERIC_ENDPOINT_NON_DRAW",
            resolution_source="2026 turkey either sex reviewed total.csv",
            reason="Retained DWR turkey feeder supplies the reviewed fall-management/private total; generic Planner endpoint total differs. This is not a draw-odds quota.",
        )
        return result

    if code in ea_totals and db_quota[2] == ea_totals[code] and planner_quota[2] != ea_totals[code]:
        result.update(
            quota_status="OFFICIAL_EA_PRIVATE_LANDS_OVERLAY_SUPERSEDES_GENERIC_ENDPOINT_NON_DRAW",
            resolution_source="elk_antlerless_private_lands_EA_2026_canonical.csv",
            reason="Retained DWR private-lands overlay supplies the reviewed allocation; generic Planner endpoint total differs. This is not a public draw-odds quota.",
        )
        return result

    if db_quota == planner_quota:
        result.update(quota_status="DWR_DIRECT_EXACT", resolution_source="dwr_huntplanner_hanumber_2026.csv", reason="All current quota fields exactly match retained DWR Planner values.")
    elif is_total_only_semantic_match(db_quota, planner_quota):
        result.update(quota_status="DWR_TOTAL_ONLY_SEMANTIC_MATCH", resolution_source="dwr_huntplanner_hanumber_2026.csv", reason="Planner publishes a total only; blank resident/nonresident database fields intentionally avoid inventing a split.")
    elif is_split_total_derived_match(db_quota, planner_quota):
        result.update(quota_status="DWR_SPLIT_TOTAL_DERIVED_MATCH", resolution_source="dwr_huntplanner_hanumber_2026.csv", reason="Planner publishes resident/nonresident values but zero total; database total is the exact sum, not an inferred residency allocation.")
    elif is_no_quota_semantic_match(db_quota, planner_quota):
        result.update(quota_status="DWR_NO_QUOTA_OR_AVAILABILITY_REFERENCE", resolution_source="dwr_huntplanner_hanumber_2026.csv", reason="Planner has no numeric quota; database blanks/zeros are reference-only and emit no probability.")
    else:
        result.update(quota_status="UNEXPLAINED_CURRENT_QUOTA_DELTA", unresolved_current_delta="YES", reason="DATABASE.csv and retained current Planner quota values differ without an approved narrower official feeder.")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repair-stale-conservation-reference", action="store_true", help="Clear BR7324 current quota fields while preserving its dedicated conservation count.")
    args = parser.parse_args()

    database_rows = read_csv(DATABASE)
    database_fields = list(database_rows[0])
    planner_rows = read_csv(PLANNER)
    planner_by_code = {row["hunt_code"]: row for row in planner_rows if row.get("fetch_status") == "OK"}
    ea_totals = source_total_map(read_csv(EA_OVERLAY))
    turkey_totals = source_total_map(read_csv(TURKEY_FEEDER))

    repaired = False
    if args.repair_stale_conservation_reference:
        repaired = repair_stale_conservation_reference(database_rows, planner_by_code)
        if repaired:
            write_csv(DATABASE, database_rows, database_fields)

    audit_rows = [classify(row, planner_by_code.get(row["hunt_code"]), ea_totals, turkey_totals) for row in database_rows]
    audit_fields = list(audit_rows[0])
    write_csv(OUTPUT_CSV, audit_rows, audit_fields)
    counts = Counter(row["quota_status"] for row in audit_rows)
    unresolved = [row for row in audit_rows if row["unresolved_current_delta"] == "YES"]
    summary = {
        "artifact": "database_current_identity_quota_2026_feeder_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Verify DATABASE.csv only as current DWR Hunt Planner identity and permit-reference data; it is not historical prediction truth.",
        "historical_prediction_truth": "data_truth/draw_results_truth/normalized/canonical_yearly/*.csv -> data_truth/draw_results_truth/normalized/draw_results_long.csv",
        "inputs": {
            "database": {"path": DATABASE.relative_to(ROOT).as_posix(), "sha256": sha256(DATABASE)},
            "planner": {"path": PLANNER.relative_to(ROOT).as_posix(), "sha256": sha256(PLANNER), "ok_rows": len(planner_by_code)},
            "ea_private_lands_overlay": {"path": EA_OVERLAY.relative_to(ROOT).as_posix(), "sha256": sha256(EA_OVERLAY)},
            "turkey_reviewed_feeder": {"path": TURKEY_FEEDER.relative_to(ROOT).as_posix(), "sha256": sha256(TURKEY_FEEDER)},
        },
        "database_rows": len(database_rows),
        "quota_status_counts": dict(sorted(counts.items())),
        "unresolved_current_field_delta_count": len(unresolved),
        "unresolved_current_field_delta_codes": [row["hunt_code"] for row in unresolved],
        "repair_applied_this_run": repaired,
        "stale_conservation_reference_status": next(
            row["quota_status"] for row in audit_rows if row["hunt_code"] == STALE_CONSERVATION_CODE
        ),
        "status": "PASS" if not unresolved else "FAIL",
        "outputs": {"audit_csv": OUTPUT_CSV.relative_to(ROOT).as_posix(), "summary_json": OUTPUT_JSON.relative_to(ROOT).as_posix()},
    }
    OUTPUT_JSON.write_text(json.dumps(summary, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if not unresolved else 1


if __name__ == "__main__":
    raise SystemExit(main())
