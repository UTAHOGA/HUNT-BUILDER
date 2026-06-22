"""Reconcile 2026=2027 working/candidate draw-result targets against canonical truth."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PATH = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
)
DEFAULT_TARGET_PATH = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "draw_results_2026_for_2027_candidate_promotion_file_records.csv"
)
AUDIT_DIR = ROOT / "audits" / "2026_canonical_reconciliation"
BACKUP_DIR = AUDIT_DIR / "backups"


def norm_text(value: str | None) -> str:
    return "" if value is None else str(value).strip()


def norm_number(value: str | None) -> str:
    text = norm_text(value)
    if text.endswith(".0"):
        text = text[:-2]
    return text


def norm_residency(value: str | None) -> str:
    text = norm_text(value).lower().replace("-", "").replace("_", "").replace(" ", "")
    if text in {"resident", "res", "r"}:
        return "Resident"
    if text in {"nonresident", "nonres", "nr"}:
        return "Nonresident"
    if text in {"all", "both", "total"}:
        return "All"
    return norm_text(value) or "Unknown"


def normalize_record_kind(value: str | None) -> str:
    text = norm_text(value).lower().replace("-", "").replace("_", "").replace(" ", "")
    if text in {"", "pointlevel", "pointrow", "point", "pointleveldrawresult", "scorablepointrow", "scorablepoint"}:
        return "point_level_draw_result"
    if text in {"pointpurchasereference", "pointpurchaseref", "pointpurchase", "reference", "availabilityonly", "supplementalpermittotalrow"}:
        return "point_purchase_reference"
    if text in {"total", "hunttotal", "hunttotaldrawresult", "sportsmantotal", "sportsmantotaldrawresult"}:
        return "sportsman_total"
    return text


def first_non_empty(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = norm_text(row.get(key))
        if value != "":
            return value
    return ""


def strict_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        norm_number(first_non_empty(row, "actual_draw_year", "year", "source_year", "reported_draw_year")),
        norm_number(first_non_empty(row, "model_target_year", "model_year")),
        norm_text(first_non_empty(row, "hunt_code")).upper(),
        norm_residency(first_non_empty(row, "residency")),
        norm_number(first_non_empty(row, "points")),
        normalize_record_kind(first_non_empty(row, "record_type", "row_type", "record_kind")),
    )


def resolve_record_kind(row: dict[str, str]) -> str:
    """Resolve a canonical-compatible record kind for matching."""
    canonical_kind = normalize_record_kind(first_non_empty(row, "record_type", "row_type", "record_kind"))
    if canonical_kind != "point_level_draw_result":
        return canonical_kind

    source_family = norm_text(row.get("source_family")).lower().replace(" ", "").replace("-", "").replace("_", "")
    draw_family = norm_text(row.get("draw_family")).lower().replace(" ", "").replace("-", "").replace("_", "")
    hunt_type = norm_text(row.get("hunt_type")).lower().replace(" ", "").replace("-", "").replace("_", "")

    if (
        source_family == "sportsman"
        or draw_family == "sportsmanrandomonly"
        or draw_family == "sportsmanrandom"
        or hunt_type == "sportsman"
    ):
        return "sportsman_total"

    return canonical_kind


def row_payload_signature(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        norm_text(row.get("age_class")),
        norm_text(row.get("draw_round")),
        norm_text(row.get("eligible_applicants")),
        norm_text(row.get("total_drawn")),
        norm_text(row.get("first_choice_permits")),
        norm_text(row.get("first_choice_apps")),
    )


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [{k: norm_text(v) for k, v in row.items()} for row in csv.DictReader(handle)]
        fields = list(rows[0].keys()) if rows else []
    return fields, rows


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def reconcile(target_path: Path) -> None:
    if not CANONICAL_PATH.exists():
        raise FileNotFoundError(f"canonical file missing: {CANONICAL_PATH}")
    if not target_path.exists():
        raise FileNotFoundError(f"target file missing: {target_path}")

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    canonical_fields, canonical_rows = read_csv(CANONICAL_PATH)
    target_fields, target_rows = read_csv(target_path)

    canonical_by_key: dict[tuple[str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in canonical_rows:
        canonical_by_key[strict_key(row)].append(row)

    consumed_by_key: dict[tuple[str, str, str, str, str, str], int] = defaultdict(int)
    seen_payloads_by_key: dict[tuple[str, str, str, str, str, str], set[tuple[str, str, str, str, str, str]]] = defaultdict(set)
    shared_fields = sorted(set(canonical_fields) & set(target_fields))
    keep_fields = set(shared_fields)
    if "row_type" in target_fields and "record_type" not in target_fields:
        keep_fields.add("row_type")
    sync_fields = [field for field in canonical_fields if field in keep_fields]

    kept_rows: list[dict[str, str]] = []
    removed_reference_rows: list[dict[str, str]] = []
    unmatched_target_rows: list[dict[str, str]] = []
    mutation_audit: list[dict[str, str]] = []
    mutation_counts: dict[str, int] = defaultdict(int)

    for index, target_row in enumerate(target_rows, start=2):
        row_kind = resolve_record_kind(target_row)
        if row_kind == "point_purchase_reference":
            removed_reference_rows.append({**target_row, "removal_reason": "reference_row_type_point_purchase_reference"})
            continue

        key = strict_key(target_row)
        key = (*key[:-1], row_kind)
        bucket = canonical_by_key.get(key, [])
        if not bucket:
            unmatched_target_rows.append({**target_row, "match_status": "no_canonical_match", "strict_key": "|".join(key)})
            continue

        payload_signature = row_payload_signature(target_row)
        if payload_signature in seen_payloads_by_key[key]:
            unmatched_target_rows.append(
                {
                    **target_row,
                    "match_status": "duplicate_target_row_identical_payload",
                    "strict_key": "|".join(key),
                }
            )
            continue

        consume = consumed_by_key[key]
        if consume >= len(bucket):
            unmatched_target_rows.append(
                {
                    **target_row,
                    "match_status": "duplicate_target_row_exceeds_canonical_count",
                    "strict_key": "|".join(key),
                }
            )
            continue

        canonical_row = bucket[consume]
        consumed_by_key[key] = consume + 1
        seen_payloads_by_key[key].add(payload_signature)

        target_row_copy = {field: target_row.get(field, "") for field in target_fields}
        for field in sync_fields:
            canonical_value = canonical_row.get(field, "")
            target_value = target_row_copy.get(field, "")
            if canonical_value != target_value:
                mutation_audit.append(
                    {
                        "row_number": str(index),
                        "hunt_code": target_row.get("hunt_code", ""),
                        "field": field,
                        "target_before": target_value,
                        "canonical_value": canonical_value,
                        "strict_key": "|".join(key),
                    }
                )
                mutation_counts[field] += 1
                target_row_copy[field] = canonical_value

        if "record_type" in target_fields:
            target_row_copy["record_type"] = canonical_row.get("record_type", target_row_copy.get("record_type", ""))
        if "row_type" in target_fields and "record_type" not in target_fields:
            target_row_copy["row_type"] = canonical_row.get("record_type", target_row_copy.get("row_type", ""))
        if "source_file" in target_fields and canonical_row.get("source_file"):
            target_row_copy["source_file"] = canonical_row.get("source_file")
        if "actual_draw_year" in target_fields and canonical_row.get("actual_draw_year"):
            target_row_copy["actual_draw_year"] = canonical_row.get("actual_draw_year")
        if "model_target_year" in target_fields and canonical_row.get("model_target_year"):
            target_row_copy["model_target_year"] = canonical_row.get("model_target_year")
        if "source_year" in target_fields:
            target_row_copy["source_year"] = target_row_copy.get("actual_draw_year")
        if "year" in target_fields:
            target_row_copy["year"] = target_row_copy.get("actual_draw_year")
        if "model_year" in target_fields:
            target_row_copy["model_year"] = target_row_copy.get("model_target_year")
        if "truth_year" in target_fields:
            target_row_copy["truth_year"] = target_row_copy.get("actual_draw_year")
        if "permits_year" in target_fields:
            target_row_copy["permits_year"] = target_row_copy.get("model_target_year")
        if "hunt_draw_class" in target_fields and "hunt_class" in canonical_row and target_row_copy.get("hunt_draw_class") != canonical_row.get("hunt_class", ""):
            target_row_copy["hunt_draw_class"] = canonical_row.get("hunt_class", "")

        kept_rows.append(target_row_copy)

    unmatched_reference_count = len(removed_reference_rows)
    unmatched_target_count = len(unmatched_target_rows)
    consumed_total = sum(consumed_by_key.values())
    remaining_canonical = len(canonical_rows) - consumed_total
    output_count = len(kept_rows)
    expected_output_count = len(target_rows) - unmatched_reference_count - unmatched_target_count

    target_stem = target_path.stem
    if target_stem == DEFAULT_TARGET_PATH.stem:
        token = "candidate"
    else:
        token = target_stem.replace("draw_results_2026_for_2027_", "")

    status = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_path": str(CANONICAL_PATH),
        "target_path": str(target_path),
        "canonical_rows": len(canonical_rows),
        "target_rows_before": len(target_rows),
        "target_rows_after": output_count,
        "target_reference_rows_removed": unmatched_reference_count,
        "target_unmatched_rows_removed": unmatched_target_count,
        "target_kept_rows": output_count,
        "canonical_rows_consumed": consumed_total,
        "canonical_rows_remaining": remaining_canonical,
        "expected_target_after": expected_output_count,
        "strict_match_fields": ["actual_draw_year", "model_target_year", "hunt_code", "residency", "points", "record_type_or_row_type"],
        "mutations": len(mutation_audit),
        "mutation_column_counts": sorted(({"field": field, "count": count} for field, count in mutation_counts.items()), key=lambda row: row["field"]),
        "row_mutation_fields": sorted(mutation_counts.keys()),
        "removed_reference_audit": str(AUDIT_DIR / f"draw_results_2026_for_2027_{token}_point_purchase_rows_dropped.csv"),
        "unmatched_target_audit": str(AUDIT_DIR / f"draw_results_2026_for_2027_{token}_unmatched_rows_dropped.csv"),
        "mutation_audit": str(AUDIT_DIR / f"draw_results_2026_for_2027_{token}_sync_mutations.csv"),
        "status": "PASS_RECONCILED" if remaining_canonical == 0 and unmatched_target_count == 0 else "REVIEW_REQUIRED",
    }
    status["status_reason"] = (
        "strict canonical key reconciliation succeeded"
        if status["status"] == "PASS_RECONCILED"
        else "strict key mismatch remains"
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"{target_stem}.before_reconcile_{timestamp}.csv"
    shutil.copy2(target_path, backup_path)

    write_csv(AUDIT_DIR / f"draw_results_2026_for_2027_{token}_point_purchase_rows_dropped.csv", removed_reference_rows, target_fields + ["removal_reason"])
    write_csv(
        AUDIT_DIR / f"draw_results_2026_for_2027_{token}_unmatched_rows_dropped.csv",
        unmatched_target_rows,
        target_fields + ["match_status", "strict_key"],
    )
    write_csv(
        AUDIT_DIR / f"draw_results_2026_for_2027_{token}_sync_mutations.csv",
        mutation_audit,
        ["row_number", "hunt_code", "field", "target_before", "canonical_value", "strict_key"],
    )

    write_csv(target_path, kept_rows, target_fields)

    status["backup_path"] = str(backup_path)
    status["output_path"] = str(target_path)

    status_path = AUDIT_DIR / f"RECONCILE_2026_FOR_2027_{token}_STATUS.json"
    with status_path.open("w", encoding="utf-8") as handle:
        json.dump(status, handle, indent=2)
        handle.write("\n")

    report_lines = [
        "# 2026=2027 Candidate Reconcile",
        "",
        f"Generated UTC: {status['generated_utc']}",
        "",
        f"Status: `{status['status']}`",
        f"Reason: {status['status_reason']}",
        "",
        f"- Canonical rows: `{status['canonical_rows']}`",
        f"- Target rows before: `{status['target_rows_before']}`",
        f"- Target rows after: `{status['target_rows_after']}`",
        f"- Removed point_purchase_reference rows: `{status['target_reference_rows_removed']}`",
        f"- Removed unmatched target rows: `{status['target_unmatched_rows_removed']}`",
        f"- Canonical rows remaining unmatched: `{status['canonical_rows_remaining']}`",
        "",
        "## Mutation counts",
        "",
    ]
    for field in status["row_mutation_fields"]:
        report_lines.append(f"- `{field}`: {mutation_counts[field]}")
    (AUDIT_DIR / f"RECONCILE_2026_FOR_2027_{token}_REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconcile a 2026=2027 target file against canonical truth.")
    parser.add_argument(
        "--target",
        default=str(DEFAULT_TARGET_PATH),
        help="Path to target CSV file to reconcile",
    )
    args = parser.parse_args()
    reconcile(Path(args.target))
