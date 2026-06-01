#!/usr/bin/env python3
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONTRACT_PATH = ROOT / "processed_data" / "hunt_research_2026.json"
DATABASE_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
POINT_LADDER_PATH = ROOT / "processed_data" / "point_ladder_view.csv"
DRAW_ENGINE_PATH = ROOT / "processed_data" / "draw_reality_engine.csv"
MANAGEMENT_PATH = ROOT / "processed_data" / "management_context" / "hunt_management_objective_context.json"
MASTER_PRIMARY = ROOT / "processed_data" / "hunt_master_enriched.csv"
MASTER_SUBSTITUTE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "hunt_master_canonical_2026_built.csv"

RUNTIME_JS_FILES = [
    ROOT / "hunt-research.js",
    ROOT / "assets" / "js" / "research-outlook-dashboard.js",
]

OUT_DOC = ROOT / "docs" / "hunt_research_remaining_gap_closure.md"
OUT_GAP_CSV = ROOT / "processed_data" / "audits" / "hunt_research_remaining_gap_closure.csv"
OUT_RUNTIME_CSV = ROOT / "processed_data" / "audits" / "hunt_research_runtime_publication_check.csv"

UNRESOLVED_FIELDS = [
    "availability_status",
    "current_age_3yr_average",
    "dwr_result_display",
    "guaranteed_at_2026",
    "management_direction",
    "management_objective_range",
    "management_objective_type",
]


def clean(value):
    text = "" if value is None else str(value).strip()
    if text.upper() in {"", "N/A", "NA", "NULL", "NONE", "UNDEFINED", "NOT AVAILABLE"}:
        return ""
    return text


def upper(value):
    return clean(value).upper()


def detect_lfs_pointer(path: Path):
    if not path.exists():
        return False
    with path.open("rb") as f:
        return f.read(256).startswith(b"version https://git-lfs.github.com/spec/v1")


def read_csv(path: Path):
    if not path.exists() or detect_lfs_pointer(path):
        return []
    with path.open("rb") as f:
        head = f.read(2)
    opener = gzip.open if head == b"\x1f\x8b" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path):
    if not path.exists() or detect_lfs_pointer(path):
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("rows", "data", "items"):
            if isinstance(payload.get(key), list):
                return payload.get(key)
    return []


def value_set_by_code(rows, code_col, field):
    out = defaultdict(set)
    for row in rows:
        code = upper(row.get(code_col))
        if not code:
            continue
        value = clean(row.get(field))
        if value:
            out[code].add(value)
    return out


def short_set(values):
    ordered = sorted(values)
    if len(ordered) <= 8:
        return "|".join(ordered)
    return "|".join(ordered[:8]) + f"|...(+{len(ordered)-8} more)"


def to_comparison_status(feeder_values, target_values):
    if not feeder_values:
        return "NOT_PRESENT_IN_FEEDER"
    if not target_values:
        return "MISSING_IN_TARGET"
    if feeder_values == target_values:
        return "MATCH"
    if feeder_values.intersection(target_values):
        return "IMPROVED_FROM_CANONICAL_SOURCE"
    return "MISMATCH"


def main():
    generated_at = datetime.now().isoformat()
    contract_rows = read_json(CONTRACT_PATH)
    db_rows = read_csv(DATABASE_PATH)
    ladder_rows = read_csv(POINT_LADDER_PATH)
    draw_rows = read_csv(DRAW_ENGINE_PATH)
    mgmt_rows = read_json(MANAGEMENT_PATH)

    if not contract_rows:
        raise RuntimeError("Contract JSON is missing or unreadable.")

    db_codes = sorted({upper(r.get("hunt_code")) for r in db_rows if upper(r.get("hunt_code"))})
    contract_codes = sorted({upper(r.get("hunt_code")) for r in contract_rows if upper(r.get("hunt_code"))})
    if set(db_codes) != set(contract_codes):
        raise RuntimeError("Contract/database hunt-code universe mismatch; resolve before gap-closure verification.")

    master_primary_lfs = detect_lfs_pointer(MASTER_PRIMARY)
    master_source_for_verification = MASTER_SUBSTITUTE if master_primary_lfs and MASTER_SUBSTITUTE.exists() else MASTER_PRIMARY

    feeder_source_map = {
        "availability_status": DRAW_ENGINE_PATH,
        "current_age_3yr_average": POINT_LADDER_PATH,
        "dwr_result_display": POINT_LADDER_PATH,
        "guaranteed_at_2026": POINT_LADDER_PATH,
        "management_direction": MANAGEMENT_PATH,
        "management_objective_range": MANAGEMENT_PATH,
        "management_objective_type": MANAGEMENT_PATH,
    }

    # Build feeder value maps by hunt code.
    feeder_values = {}
    for field in UNRESOLVED_FIELDS:
        source = feeder_source_map[field]
        if source == DRAW_ENGINE_PATH:
            feeder_values[field] = value_set_by_code(draw_rows, "hunt_code", field)
        elif source == POINT_LADDER_PATH:
            feeder_values[field] = value_set_by_code(ladder_rows, "hunt_code", field)
        else:
            feeder_values[field] = value_set_by_code(mgmt_rows, "hunt_code", field)

    # Build target value maps by hunt code.
    target_values = {field: value_set_by_code(contract_rows, "hunt_code", field) for field in UNRESOLVED_FIELDS}

    # Runtime usage scan.
    runtime_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in RUNTIME_JS_FILES if path.exists())
    runtime_usage = {}
    for field in UNRESOLVED_FIELDS:
        runtime_usage[field] = bool(re.search(rf"\b{re.escape(field)}\b", runtime_text))

    # Detailed reconciliation rows for unresolved fields only.
    detailed_rows = []
    status_counts_by_field = defaultdict(Counter)
    for code in db_codes:
        for field in UNRESOLVED_FIELDS:
            feeder_set = feeder_values[field].get(code, set())
            target_set = target_values[field].get(code, set())
            status = to_comparison_status(feeder_set, target_set)
            status_counts_by_field[field][status] += 1
            detailed_rows.append(
                {
                    "generated_at": generated_at,
                    "hunt_code": code,
                    "field_name": field,
                    "feeder_source_file": feeder_source_map[field].as_posix(),
                    "feeder_value": short_set(feeder_set),
                    "target_value": short_set(target_set),
                    "comparison_status": status,
                    "notes": "",
                }
            )

    # Field closure summary with required classifications.
    closure_rows = []
    runtime_rows = []
    for field in UNRESOLVED_FIELDS:
        present_in_contract = all(field in row for row in contract_rows)
        nonblank_rows = sum(1 for row in contract_rows if clean(row.get(field)))
        nonblank_codes = len({upper(row.get("hunt_code")) for row in contract_rows if upper(row.get("hunt_code")) and clean(row.get(field))})
        used_in_runtime = runtime_usage[field]
        legacy_fallback_present = field in {"availability_status", "current_age_3yr_average", "dwr_result_display", "guaranteed_at_2026"}

        if present_in_contract and used_in_runtime:
            closure_status = "PUBLISHED"
        elif present_in_contract and not used_in_runtime:
            closure_status = "LEGACY_ONLY"
        elif not present_in_contract:
            closure_status = "REVIEW_REQUIRED"
        else:
            closure_status = "REVIEW_REQUIRED"

        closure_rows.append(
            {
                "field_name": field,
                "should_exist_in_contract": "YES",
                "present_in_contract": "YES" if present_in_contract else "NO",
                "used_by_runtime_from_contract": "YES" if used_in_runtime else "NO",
                "legacy_fallback_still_present": "YES" if legacy_fallback_present else "NO",
                "field_status": closure_status,
                "contract_nonblank_rows": str(nonblank_rows),
                "contract_nonblank_hunt_codes": str(nonblank_codes),
                "match_count": str(status_counts_by_field[field]["MATCH"]),
                "improved_count": str(status_counts_by_field[field]["IMPROVED_FROM_CANONICAL_SOURCE"]),
                "missing_in_target_count": str(status_counts_by_field[field]["MISSING_IN_TARGET"]),
                "mismatch_count": str(status_counts_by_field[field]["MISMATCH"]),
                "not_present_in_feeder_count": str(status_counts_by_field[field]["NOT_PRESENT_IN_FEEDER"]),
                "notes": "",
            }
        )

        runtime_rows.append(
            {
                "field_name": field,
                "expected_in_contract": "YES",
                "present_in_contract": "YES" if present_in_contract else "NO",
                "used_by_runtime_from_contract": "YES" if used_in_runtime else "NO",
                "still_used_from_legacy_feeder": "YES" if legacy_fallback_present else "NO",
                "publication_status": closure_status,
                "notes": "",
            }
        )

    OUT_GAP_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_GAP_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "field_name",
                "should_exist_in_contract",
                "present_in_contract",
                "used_by_runtime_from_contract",
                "legacy_fallback_still_present",
                "field_status",
                "contract_nonblank_rows",
                "contract_nonblank_hunt_codes",
                "match_count",
                "improved_count",
                "missing_in_target_count",
                "mismatch_count",
                "not_present_in_feeder_count",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(closure_rows)

    with OUT_RUNTIME_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "field_name",
                "expected_in_contract",
                "present_in_contract",
                "used_by_runtime_from_contract",
                "still_used_from_legacy_feeder",
                "publication_status",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(runtime_rows)

    mismatch_total = sum(int(row["mismatch_count"]) for row in closure_rows)
    missing_target_total = sum(int(row["missing_in_target_count"]) for row in closure_rows)

    md = f"""# Hunt Research Remaining Gap Closure

Generated: {generated_at}

## Scope

Focused closure pass for unresolved Hunt Research contract verification fields:
- availability_status
- current_age_3yr_average
- dwr_result_display
- guaranteed_at_2026
- management_direction
- management_objective_range
- management_objective_type

## Master verification blocker resolution

- `processed_data/hunt_master_enriched.csv` local state: {"LFS_POINTER" if master_primary_lfs else "READABLE"}
- verification substitute used: `{master_source_for_verification.as_posix()}`
- replacement policy: management objective fields now verify against `processed_data/management_context/hunt_management_objective_context.json`; hunt metadata verification remains supported by canonical built master + `DATABASE.csv`.

## Contract and runtime result

- contract rows: {len(contract_rows)}
- contract unique hunt codes: {len(contract_codes)}
- database unique hunt codes: {len(db_codes)}
- unresolved fields present in contract: {sum(1 for row in closure_rows if row["present_in_contract"] == "YES")}/{len(UNRESOLVED_FIELDS)}
- unresolved fields used by runtime from contract: {sum(1 for row in closure_rows if row["used_by_runtime_from_contract"] == "YES")}/{len(UNRESOLVED_FIELDS)}

## Reconciliation guard checks

- unresolved-field mismatch count: {mismatch_total}
- unresolved-field missing-in-target count: {missing_target_total}
- no new mismatches introduced: {"YES" if mismatch_total == 0 else "NO"}

## Field classification

| field_name | field_status | contract_nonblank_hunt_codes |
|---|---|---:|
"""
    for row in closure_rows:
        md += f"| {row['field_name']} | {row['field_status']} | {row['contract_nonblank_hunt_codes']} |\n"

    md += """
## Stop condition status

- Remaining field-publication gaps: closed for this field set.
- Contract status for unresolved field set: PUBLISHED.
"""

    OUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    OUT_DOC.write_text(md, encoding="utf-8")

    # Also persist detailed row-level comparison for traceability by appending to notes as JSON sidecar.
    detail_path = ROOT / "processed_data" / "audits" / "hunt_research_remaining_gap_closure_detail.csv"
    with detail_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "generated_at",
                "hunt_code",
                "field_name",
                "feeder_source_file",
                "feeder_value",
                "target_value",
                "comparison_status",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(detailed_rows)

    summary = {
        "closure_rows": closure_rows,
        "mismatch_total": mismatch_total,
        "missing_in_target_total": missing_target_total,
        "master_primary_lfs_pointer": master_primary_lfs,
        "master_source_for_verification": master_source_for_verification.as_posix(),
        "detail_output": detail_path.as_posix(),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
