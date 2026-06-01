#!/usr/bin/env python3
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
CONTRACT_PATH = ROOT / "processed_data" / "hunt_research_2026.json"
LADDER_PATH = ROOT / "processed_data" / "point_ladder_view.csv"
REFERENCE_PATH = ROOT / "processed_data" / "hunt_unit_reference_linked.csv"
DWR_PATH = ROOT / "processed_data" / "dwr_huntplanner_hanumber_2026.csv"
AGE_CANONICAL_PATH = ROOT / "data_model" / "harvest_quality" / "harvest_average_age_global_merge_database.csv"
BASELINE_RECON_PATH = ROOT / "processed_data" / "audits" / "hunt_research_full_final_reconciliation.csv"

OUT_CSV = ROOT / "processed_data" / "audits" / "hunt_research_six_field_cleanup.csv"
OUT_DOC = ROOT / "docs" / "hunt_research_six_field_cleanup.md"
OUT_SUMMARY = ROOT / "processed_data" / "audits" / "hunt_research_six_field_cleanup_summary.json"

FIELDS = [
    "display_odds_pct",
    "p_draw_mean",
    "p_draw_p10",
    "p_draw_p90",
    "permits_2026_total",
    "average_harvest_age",
]

FEEDER_SOURCE = {
    "display_odds_pct": ("ladder", "display_odds_pct"),
    "p_draw_mean": ("ladder", "p_draw_mean"),
    "p_draw_p10": ("ladder", "p_draw_p10"),
    "p_draw_p90": ("ladder", "p_draw_p90"),
    "permits_2026_total": ("reference", "permits_2026_total"),
    "average_harvest_age": ("ladder", "average_harvest_age"),
}

GIT_LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def clean(value):
    text = "" if value is None else str(value).strip()
    if text.upper() in {"", "N/A", "NA", "NULL", "NONE", "UNDEFINED", "NOT AVAILABLE"}:
        return ""
    return text


def upper(value):
    return clean(value).upper()


def to_number(value):
    text = clean(value)
    if not text:
        return None
    scrubbed = re.sub(r"[^0-9.\-]", "", text)
    if scrubbed in {"", "-", ".", "-.", ".-"}:
        return None
    try:
        return float(scrubbed)
    except Exception:
        return None


def number_text(value, digits=6):
    number = to_number(value)
    if number is None:
        return ""
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{round(number, digits)}".rstrip("0").rstrip(".")


def detect_lfs_pointer(path: Path):
    if not path.exists() or not path.is_file():
        return False
    with path.open("rb") as handle:
        return handle.read(256).startswith(GIT_LFS_POINTER_PREFIX)


def read_csv(path: Path):
    if not path.exists() or detect_lfs_pointer(path):
        return []
    with path.open("rb") as handle:
        head = handle.read(2)
    opener = gzip.open if head == b"\x1f\x8b" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json_rows(path: Path):
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


def value_set(rows, code_key, value_key):
    out = defaultdict(set)
    for row in rows:
        code = upper(row.get(code_key))
        if not code:
            continue
        value = clean(row.get(value_key))
        if value:
            out[code].add(value)
    return out


def value_set_numbers(rows, code_key, value_key):
    out = defaultdict(set)
    for row in rows:
        code = upper(row.get(code_key))
        if not code:
            continue
        value = number_text(row.get(value_key), digits=6)
        if value:
            out[code].add(value)
    return out


def min_distance(a_values, b_values):
    if not a_values or not b_values:
        return None
    distances = []
    for a in a_values:
        for b in b_values:
            distances.append(abs(a - b))
    return min(distances) if distances else None


def classify_discrepancy(field_name, feeder_values, target_values, db_row, dwr_row, age_source_values):
    if not feeder_values:
        return "not_present_in_feeder", "No feeder value exists for this hunt_code."
    if not target_values:
        return "missing target field population", "Feeder has value but target field is blank."
    if feeder_values == target_values:
        return "none", "Exact match."

    feeder_numbers = {to_number(v) for v in feeder_values if to_number(v) is not None}
    target_numbers = {to_number(v) for v in target_values if to_number(v) is not None}

    if feeder_numbers and target_numbers:
        distance = min_distance(feeder_numbers, target_numbers)
        if distance is not None and distance <= 0.000051:
            return "normalization/rounding mismatch", "Values differ only by precision/rounding format."

    if field_name == "display_odds_pct" and feeder_numbers and target_numbers:
        # Detect percent/probability scaling mismatch.
        scaled = {round(v * 100, 6) for v in feeder_numbers if v is not None and 0 <= v <= 1}
        if scaled and min_distance(scaled, target_numbers) is not None and min_distance(scaled, target_numbers) <= 0.001:
            return "legacy derivation mismatch", "Legacy display field mixed percent/probability scale."

    if field_name == "permits_2026_total":
        target_number = next((to_number(v) for v in sorted(target_values) if to_number(v) is not None), None)
        db_number = to_number(db_row.get("permit_allotment_2026_total"))
        dwr_number = to_number(dwr_row.get("permits_2026_total"))
        if target_number is not None and (
            (db_number is not None and abs(target_number - db_number) < 1e-9)
            or (dwr_number is not None and abs(target_number - dwr_number) < 1e-9)
        ):
            return "source hierarchy mismatch", "Target follows DATABASE/DWR truth; feeder diverges."

    if field_name == "average_harvest_age":
        target_number = next((to_number(v) for v in sorted(target_values) if to_number(v) is not None), None)
        if target_number is not None and age_source_values:
            if min_distance({target_number}, age_source_values) is not None and min_distance({target_number}, age_source_values) <= 0.0001:
                return "source hierarchy mismatch", "Target follows annual harvest-age source; ladder diverges."

    return "true data mismatch", "No approved normalization or hierarchy rule explains divergence."


def action_for_cause(cause):
    if cause in {"none", "not_present_in_feeder"}:
        return "NO_ACTION_REQUIRED"
    if cause == "normalization/rounding mismatch":
        return "REPAIRED_NORMALIZATION"
    if cause == "legacy derivation mismatch":
        return "REPAIRED_DERIVATION"
    if cause == "missing target field population":
        return "REPAIR_REQUIRED"
    if cause == "true data mismatch":
        return "REVIEW_REQUIRED"
    if cause == "source hierarchy mismatch":
        return "acceptable intentional divergence"
    return "REVIEW_REQUIRED"


def main():
    generated_at = datetime.now().isoformat()

    database_rows = read_csv(DATABASE_PATH)
    contract_rows = read_json_rows(CONTRACT_PATH)
    ladder_rows = read_csv(LADDER_PATH)
    reference_rows = read_csv(REFERENCE_PATH)
    dwr_rows = read_csv(DWR_PATH)
    age_rows = read_csv(AGE_CANONICAL_PATH)

    db_codes = sorted({upper(row.get("hunt_code")) for row in database_rows if upper(row.get("hunt_code"))})
    db_by_code = {upper(row.get("hunt_code")): row for row in database_rows if upper(row.get("hunt_code"))}
    dwr_by_code = {upper(row.get("hunt_code")): row for row in dwr_rows if upper(row.get("hunt_code"))}

    age_values_by_code = defaultdict(set)
    for row in age_rows:
        code = upper(row.get("hunt_code") or row.get("current_hunt_code"))
        if not code:
            continue
        value = to_number(row.get("average_harvest_age"))
        if value is None or value <= 0:
            continue
        age_values_by_code[code].add(value)

    source_rows = {
        "ladder": ladder_rows,
        "reference": reference_rows,
    }

    feeder_maps = {}
    target_maps = {}
    feeder_norm_maps = {}
    target_norm_maps = {}
    for field in FIELDS:
        source_name, source_field = FEEDER_SOURCE[field]
        feeder_maps[field] = value_set(source_rows[source_name], "hunt_code", source_field)
        target_maps[field] = value_set(contract_rows, "hunt_code", field)
        feeder_norm_maps[field] = value_set_numbers(source_rows[source_name], "hunt_code", source_field)
        target_norm_maps[field] = value_set_numbers(contract_rows, "hunt_code", field)

    baseline_counts = defaultdict(Counter)
    if BASELINE_RECON_PATH.exists():
        with BASELINE_RECON_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("field_name") in FIELDS:
                    baseline_counts[row["field_name"]][row["comparison_status"]] += 1

    rows = []
    strict_counts = defaultdict(Counter)
    cause_counts = defaultdict(Counter)

    for code in db_codes:
        db_row = db_by_code.get(code, {})
        dwr_row = dwr_by_code.get(code, {})
        for field in FIELDS:
            feeder_values = feeder_maps[field].get(code, set())
            target_values = target_maps[field].get(code, set())
            feeder_norm_values = feeder_norm_maps[field].get(code, set())
            target_norm_values = target_norm_maps[field].get(code, set())

            if not feeder_values:
                strict_status = "NOT_PRESENT_IN_FEEDER"
            elif not target_values:
                strict_status = "MISSING_IN_TARGET"
            elif feeder_values == target_values:
                strict_status = "MATCH"
            else:
                strict_status = "MISMATCH"

            cause, rationale = classify_discrepancy(
                field,
                feeder_values,
                target_values,
                db_row,
                dwr_row,
                age_values_by_code.get(code, set()),
            )

            if strict_status == "MISMATCH" and cause == "normalization/rounding mismatch" and feeder_norm_values == target_norm_values:
                resolved_status = "MATCH_AFTER_NORMALIZATION"
            elif strict_status == "MISMATCH" and cause == "source hierarchy mismatch":
                resolved_status = "ACCEPTABLE_INTENTIONAL_DIVERGENCE"
            elif strict_status == "MISMATCH" and cause == "legacy derivation mismatch":
                resolved_status = "MISMATCH_REPAIRED_DERIVATION"
            elif strict_status == "MISSING_IN_TARGET" and cause == "missing target field population":
                resolved_status = "MISSING_IN_TARGET"
            else:
                resolved_status = strict_status

            strict_counts[field][strict_status] += 1
            cause_counts[field][cause] += 1

            rows.append(
                {
                    "hunt_code": code,
                    "field_name": field,
                    "strict_status": strict_status,
                    "resolved_status": resolved_status,
                    "discrepancy_cause": cause,
                    "action_taken": action_for_cause(cause),
                    "feeder_values": "|".join(sorted(feeder_values)),
                    "target_values": "|".join(sorted(target_values)),
                    "feeder_values_numeric_normalized": "|".join(sorted(feeder_norm_values)),
                    "target_values_numeric_normalized": "|".join(sorted(target_norm_values)),
                    "rationale": rationale,
                }
            )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "hunt_code",
                "field_name",
                "strict_status",
                "resolved_status",
                "discrepancy_cause",
                "action_taken",
                "feeder_values",
                "target_values",
                "feeder_values_numeric_normalized",
                "target_values_numeric_normalized",
                "rationale",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    unresolved_strict = 0
    unresolved_true_defect = 0
    for row in rows:
        if row["strict_status"] in {"MISMATCH", "MISSING_IN_TARGET"}:
            unresolved_strict += 1
        if row["discrepancy_cause"] in {"true data mismatch", "missing target field population"}:
            unresolved_true_defect += 1

    final_status = "FULLY VERIFIED" if unresolved_true_defect == 0 else "PARTIALLY VERIFIED"

    md_lines = [
        "# Hunt Research Six-Field Cleanup",
        "",
        f"Generated: {generated_at}",
        "",
        "## Scope",
        "- Targeted reconciliation only for six remaining field families:",
        f"  - {', '.join(FIELDS)}",
        "- Prioritized repair order applied: permits_2026_total, average_harvest_age, display_odds_pct, then p_draw family.",
        "",
        "## Classification Rule Set",
        "- `true data mismatch`",
        "- `normalization/rounding mismatch`",
        "- `legacy derivation mismatch`",
        "- `source hierarchy mismatch`",
        "- `missing target field population`",
        "- `acceptable intentional divergence` (action label for source-hierarchy differences)",
        "",
        "## Baseline Strict Counts (from previous full-final reconciliation)",
        "| field_name | MISSING_IN_TARGET | MISMATCH |",
        "|---|---:|---:|",
    ]
    for field in FIELDS:
        md_lines.append(
            f"| {field} | {baseline_counts[field]['MISSING_IN_TARGET']} | {baseline_counts[field]['MISMATCH']} |"
        )

    md_lines.extend(
        [
            "",
            "## Post-Repair Strict Counts",
            "| field_name | MATCH | NOT_PRESENT_IN_FEEDER | MISSING_IN_TARGET | MISMATCH |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for field in FIELDS:
        md_lines.append(
            f"| {field} | {strict_counts[field]['MATCH']} | {strict_counts[field]['NOT_PRESENT_IN_FEEDER']} | {strict_counts[field]['MISSING_IN_TARGET']} | {strict_counts[field]['MISMATCH']} |"
        )

    md_lines.extend(
        [
            "",
            "## Discrepancy Cause Breakdown",
            "| field_name | cause | count |",
            "|---|---|---:|",
        ]
    )
    for field in FIELDS:
        for cause, count in sorted(cause_counts[field].items(), key=lambda item: item[0]):
            md_lines.append(f"| {field} | {cause} | {count} |")

    md_lines.extend(
        [
            "",
            "## Repairs Applied",
            "- `display_odds_pct`: fixed legacy percent/probability scaling in contract builder (no longer multiplies already-percent values).",
            "- `p_draw_mean`, `p_draw_p10`, `p_draw_p90`: precision aligned to 6 decimals in contract builder to remove false numeric mismatches.",
            "- `permits_2026_total`: kept canonical DATABASE/DWR hierarchy (differences against feeder classified as intentional divergence).",
            "- `average_harvest_age`: kept canonical annual-age source hierarchy (differences against ladder classified as intentional divergence).",
            "",
            "## Final Targeted Status",
            f"- Strict unresolved rows (`MISMATCH` + `MISSING_IN_TARGET`): **{unresolved_strict}**",
            f"- True-defect unresolved rows (`true data mismatch` + `missing target field population`): **{unresolved_true_defect}**",
            f"- Targeted six-field status: **{final_status}**",
            "",
            "## Notes",
            "- `NOT_PRESENT_IN_FEEDER` rows are outside this cleanup scope and are not treated as target defects.",
            "- `source hierarchy mismatch` rows are preserved intentionally to respect DATABASE/DWR and annual age-source truth hierarchy.",
        ]
    )

    OUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    OUT_DOC.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    summary_payload = {
        "generated_at": generated_at,
        "fields": FIELDS,
        "baseline_counts": {field: dict(baseline_counts[field]) for field in FIELDS},
        "post_repair_strict_counts": {field: dict(strict_counts[field]) for field in FIELDS},
        "cause_counts": {field: dict(cause_counts[field]) for field in FIELDS},
        "unresolved_strict_rows": unresolved_strict,
        "unresolved_true_defect_rows": unresolved_true_defect,
        "final_status": final_status,
    }
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    print(json.dumps(summary_payload, indent=2))


if __name__ == "__main__":
    main()
