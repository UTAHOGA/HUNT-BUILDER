"""Reconcile current DWR harvest rows to canonical and reference feeders.

Identity is exact normalized hunt_code plus compatible hunt_name/unit and
species. boundary_id is never read as a match key. Only harvest fields may be
written; every other field is fingerprinted before and after.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.utah.quality.harvest_identity import (
    build_identity_index,
    harvest_identity_compatible,
    normalize_code,
    resolve_identity_match,
)


SOURCE = ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_results_2025_for_2026_current.csv"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
REFERENCE = ROOT / "processed_data" / "hunt_unit_reference_linked.csv"
AUDIT_DIR = ROOT / "data_truth" / "harvest_results_truth" / "validation" / "current_2025_reconciliation"

DATABASE_HARVEST_FIELDS = {"percent_harvest_success_previous_hunting_season"}
REFERENCE_HARVEST_FIELDS = {
    "harvest_hunters_2025",
    "harvest_2025",
    "harvest_success_percent_2025",
    "harvest_average_days_2025",
    "harvest_satisfaction_2025",
}


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def protected_fingerprint(rows: list[dict[str, str]], fields: list[str], writable: set[str]) -> str:
    protected_fields = [field for field in fields if field not in writable]
    payload = [[row.get(field, "") for field in protected_fields] for row in rows]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def source_metrics(row: dict[str, str]) -> dict[str, str]:
    return {
        "harvest_hunters_2025": row.get("hunters_afield", ""),
        "harvest_2025": row.get("harvest_total", ""),
        "harvest_success_percent_2025": row.get("percent_success", ""),
        "harvest_average_days_2025": row.get("average_days", ""),
        "harvest_satisfaction_2025": row.get("hunter_satisfaction", ""),
    }


def reconcile_surface(
    source_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    target_fields: list[str],
    field_map: dict[str, str],
    surface: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    output = [dict(row) for row in target_rows]
    target_index = build_identity_index(output)
    row_positions = {id(row): index for index, row in enumerate(output)}
    pending: dict[tuple[int, str], tuple[str, str]] = {}
    audit_rows: list[dict[str, str]] = []
    status_counts: Counter[str] = Counter()
    changed_cells = 0
    populated_cells = 0

    for source in source_rows:
        code = normalize_code(source.get("hunt_code"))
        candidates = target_index.get(code, [])
        resolution = resolve_identity_match(source, candidates)
        compatible = [row for row in candidates if harvest_identity_compatible(source, row)]
        status = resolution.status
        conflict = False
        source_key = "|".join(
            [source.get("species", ""), code, source.get("hunt_name", ""), source.get("weapon", "")]
        )

        for target in compatible:
            target_position = row_positions[id(target)]
            for target_field, source_field in field_map.items():
                if target_field not in target_fields:
                    continue
                value = source.get(source_field, "").strip()
                if not value:
                    continue
                pending_key = (target_position, target_field)
                prior = pending.get(pending_key)
                if prior is not None and prior[0] != value:
                    conflict = True
                    status = "CONFLICTING_SOURCE_VALUES_REJECTED"
                    continue
                pending[pending_key] = (value, source_key)

        status_counts[status] += 1
        audit_rows.append(
            {
                "surface": surface,
                "status": status,
                "hunt_code": code,
                "source_species": source.get("species", ""),
                "source_hunt_name": source.get("hunt_name", ""),
                "source_weapon": source.get("weapon", ""),
                "source_hunters_afield": source.get("hunters_afield", ""),
                "source_harvest_total": source.get("harvest_total", ""),
                "source_percent_success": source.get("percent_success", ""),
                "candidate_count": str(resolution.candidate_count),
                "compatible_row_count": str(len(compatible)),
                "target_species": str((resolution.row or {}).get("species", "")),
                "target_hunt_name": str((resolution.row or {}).get("hunt_name", "")),
                "target_weapon": str((resolution.row or {}).get("weapon", "")),
                "candidate_species": "|".join(sorted({str(row.get("species", "")) for row in candidates})),
                "candidate_hunt_names": "|".join(sorted({str(row.get("hunt_name", "")) for row in candidates})),
                "candidate_weapons": "|".join(sorted({str(row.get("weapon", "")) for row in candidates})),
                "boundary_id_used": "NO",
                "source_value_conflict": "YES" if conflict else "NO",
            }
        )

    for (position, field), (value, _) in pending.items():
        before = output[position].get(field, "")
        if before != value:
            output[position][field] = value
            changed_cells += 1
        if value:
            populated_cells += 1

    summary = {
        "surface": surface,
        "source_rows": len(source_rows),
        "target_rows": len(target_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "changed_cells": changed_cells,
        "populated_target_cells": populated_cells,
        "boundary_id_used": False,
    }
    return output, audit_rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-only", action="store_true", help="Write reports without modifying canonical/reference CSVs.")
    args = parser.parse_args()

    source_rows, _ = read_csv(SOURCE)
    database_rows, database_fields = read_csv(DATABASE)
    database_before = protected_fingerprint(database_rows, database_fields, DATABASE_HARVEST_FIELDS)
    database_output, database_audit, database_summary = reconcile_surface(
        source_rows,
        database_rows,
        database_fields,
        {"percent_harvest_success_previous_hunting_season": "percent_success"},
        "canonical_database_2026",
    )
    database_after = protected_fingerprint(database_output, database_fields, DATABASE_HARVEST_FIELDS)
    if database_before != database_after:
        raise AssertionError("Canonical reconciliation changed non-harvest fields, including protected 2026 permits.")

    reference_audit: list[dict[str, str]] = []
    reference_summary: dict[str, object] = {"surface": "hunt_unit_reference_linked", "status": "MISSING_LOCAL_FILE"}
    reference_output: list[dict[str, str]] = []
    reference_fields: list[str] = []
    reference_before = reference_after = ""
    if REFERENCE.exists():
        reference_rows, reference_fields = read_csv(REFERENCE)
        reference_before = protected_fingerprint(reference_rows, reference_fields, REFERENCE_HARVEST_FIELDS)
        reference_output, reference_audit, reference_summary = reconcile_surface(
            source_rows,
            reference_rows,
            reference_fields,
            {
                "harvest_hunters_2025": "hunters_afield",
                "harvest_2025": "harvest_total",
                "harvest_success_percent_2025": "percent_success",
                "harvest_average_days_2025": "average_days",
                "harvest_satisfaction_2025": "hunter_satisfaction",
            },
            "hunt_unit_reference_linked",
        )
        reference_after = protected_fingerprint(reference_output, reference_fields, REFERENCE_HARVEST_FIELDS)
        if reference_before != reference_after:
            raise AssertionError("Reference reconciliation changed non-harvest fields, including protected 2026 permits.")

    if not args.audit_only:
        write_csv(DATABASE, database_output, database_fields)
        if reference_output:
            write_csv(REFERENCE, reference_output, reference_fields)

    all_audit = database_audit + reference_audit
    matched = [row for row in all_audit if row["status"] == "MATCHED_CODE_NAME_SPECIES"]
    missing = [row for row in all_audit if row["status"] == "MISSING_HUNT_CODE"]
    mismatched = [row for row in all_audit if row["status"] not in {"MATCHED_CODE_NAME_SPECIES", "MISSING_HUNT_CODE"}]
    audit_fields = list(all_audit[0]) if all_audit else ["surface", "status", "hunt_code"]
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(AUDIT_DIR / "matched_rows.csv", matched, audit_fields)
    write_csv(AUDIT_DIR / "missing_rows.csv", missing, audit_fields)
    write_csv(AUDIT_DIR / "mismatched_rows.csv", mismatched, audit_fields)
    write_csv(AUDIT_DIR / "all_rows.csv", all_audit, audit_fields)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": str(SOURCE.relative_to(ROOT)),
        "source_rows": len(source_rows),
        "mode": "AUDIT_ONLY" if args.audit_only else "APPLIED",
        "identity_contract": "exact normalized hunt_code plus compatible hunt_name/unit and species",
        "boundary_id_used": False,
        "database": database_summary,
        "reference": reference_summary,
        "protected_field_fingerprints": {
            "database_before": database_before,
            "database_after": database_after,
            "database_unchanged": database_before == database_after,
            "reference_before": reference_before,
            "reference_after": reference_after,
            "reference_unchanged": reference_before == reference_after,
        },
        "audit_rows": {"matched": len(matched), "missing": len(missing), "mismatched": len(mismatched)},
    }
    (AUDIT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = [
        "# Current 2025 Harvest Reconciliation",
        "",
        f"- Mode: `{summary['mode']}`",
        f"- Source rows: `{len(source_rows)}`",
        f"- Matched audit rows: `{len(matched)}`",
        f"- Missing-code audit rows: `{len(missing)}`",
        f"- Mismatched audit rows: `{len(mismatched)}`",
        f"- Canonical harvest cells changed: `{database_summary['changed_cells']}`",
        f"- Reference harvest cells changed: `{reference_summary.get('changed_cells', 0)}`",
        f"- Non-harvest canonical fields unchanged: `{database_before == database_after}`",
        f"- Non-harvest reference fields unchanged: `{reference_before == reference_after}`",
        "- boundary_id used for matching: `NO`",
    ]
    (AUDIT_DIR / "summary.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
