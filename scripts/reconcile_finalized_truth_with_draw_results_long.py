"""Reconcile finalized truth splits with draw_results_long and sync canonical slices.

This script is intentionally conservative:
- draw_results_long.csv remains the engine-facing canonical master schema.
- finalized_point_distribution.csv and finalized_hunt_truth.csv are treated as
  narrower truth/reconciliation surfaces.
- 2021/2022 stale normalized yearly files are replaced from the canonical long
  slices.
- 2026 is appended from the accepted dense live+PDF candidate after writing a
  backup of the current master.
"""

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NORMALIZED = ROOT / "data_truth" / "draw_results_truth" / "normalized"
LONG_PATH = NORMALIZED / "draw_results_long.csv"
POINT_PATH = ROOT / "data_truth" / "finalized_point_distribution.csv"
HUNT_PATH = ROOT / "data_truth" / "finalized_hunt_truth.csv"
ACCEPTED_2026 = (
    ROOT
    / "audits"
    / "truth_document_audit"
    / "refresh_2026_candidate_from_live_utahdraws_20260618"
    / "2026_live_plus_pdf_dense_ladder_candidate_NOT_PROMOTED.csv"
)
AUDIT_DIR = (
    ROOT
    / "audits"
    / "truth_document_audit"
    / "reconcile_finalized_vs_long_and_sync_2026"
)
BACKUP_DIR = AUDIT_DIR / "backups"


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def norm_year(value: object) -> str:
    text = clean(value)
    return text[:-2] if text.endswith(".0") else text


def norm_code(value: object) -> str:
    return clean(value).upper()


def norm_residency(value: object) -> str:
    text = clean(value).lower().replace("-", "").replace("_", "").replace(" ", "")
    if text in {"r", "res", "resident"}:
        return "Resident"
    if text in {"nr", "nonres", "nonresident"}:
        return "Nonresident"
    if text in {"all", "both"}:
        return "All"
    return clean(value)


def norm_points(value: object) -> str:
    text = clean(value)
    if text.endswith(".0"):
        text = text[:-2]
    return text


def finalized_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        norm_year(row.get("year")),
        norm_year(row.get("model_year")),
        clean(row.get("source_namespace")),
        clean(row.get("source_file")),
        norm_code(row.get("hunt_code")),
        norm_residency(row.get("residency")),
        norm_points(row.get("point_level") or row.get("points")),
        clean(row.get("record_type") or "point_level_draw_result"),
    )


def long_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        norm_year(row.get("source_year") or row.get("year") or row.get("actual_draw_year")),
        norm_year(row.get("model_year") or row.get("model_target_year") or row.get("permits_year")),
        clean(row.get("source_namespace") or row.get("draw_source_namespace")),
        clean(row.get("source_file") or row.get("source_scope") or row.get("draw_source_file")),
        norm_code(row.get("hunt_code")),
        norm_residency(row.get("residency")),
        norm_points(row.get("points")),
        clean(row.get("record_type") or row.get("row_type")),
    )


def long_validation_key(row: dict[str, str]) -> tuple[str, ...]:
    """Engine-safe uniqueness key for mixed point/reference rows.

    The source-file/year/hunt/residency/points key is too coarse for modern
    rows because adult/youth, draw pools, and reference/point-purchase lanes
    can legitimately share a hunt code and point level.
    """
    return (
        norm_year(row.get("source_year") or row.get("year") or row.get("actual_draw_year")),
        norm_year(row.get("model_year") or row.get("model_target_year") or row.get("permits_year")),
        clean(row.get("source_namespace") or row.get("draw_source_namespace")),
        clean(row.get("source_file") or row.get("source_scope") or row.get("draw_source_file")),
        norm_code(row.get("hunt_code")),
        clean(row.get("species")),
        clean(row.get("sex_type") or row.get("sex")),
        clean(row.get("weapon")),
        clean(row.get("hunt_type")),
        clean(row.get("hunt_class") or row.get("hunt_draw_class")),
        clean(row.get("draw_design")),
        norm_residency(row.get("residency")),
        norm_points(row.get("points")),
        clean(row.get("record_type") or row.get("row_type")),
    )


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [{k: clean(v) for k, v in row.items()} for row in reader]
    return fields, rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def backup(path: Path, label: str, tag: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    safe_label = label[:20]
    safe_stem = path.stem[:36]
    target = BACKUP_DIR / f"{safe_stem}.{safe_label}.{tag}{path.suffix}"
    shutil.copy2(path, target)
    return target


def count_by_year(rows: list[dict[str, str]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[norm_year(row.get("source_year") or row.get("year") or row.get("actual_draw_year"))] += 1
    return counts


def build_finalized_rows() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    _, point_rows = read_rows(POINT_PATH)
    _, hunt_rows = read_rows(HUNT_PATH)
    return point_rows, hunt_rows


def row_kind_to_record_type(record_kind: str) -> str:
    kind = clean(record_kind).upper()
    if kind in {"POINT_ROW", "POINT_LEVEL", "POINT_LEVEL_DRAW_RESULT"}:
        return "point_level_draw_result"
    if kind in {"TOTAL_ROW", "HUNT_TOTAL", "HUNT_TOTAL_DRAW_RESULT"}:
        return "hunt_total_draw_result"
    if kind in {"POINT_PURCHASE_REFERENCE"}:
        return "point_purchase_reference"
    if kind in {"AVAILABILITY_ONLY", "REFERENCE_ONLY"}:
        return "availability_only"
    return clean(record_kind).lower() or "point_level_draw_result"


def map_2026_to_long(row: dict[str, str], long_fields: list[str]) -> dict[str, str]:
    year = norm_year(row.get("actual_draw_year") or row.get("year") or "2026")
    model_year = norm_year(row.get("model_target_year") or "2027")
    record_type = row_kind_to_record_type(row.get("record_kind", ""))
    source_file = clean(row.get("source_file"))
    source_family = clean(row.get("source_report_family"))
    mapped = {field: "" for field in long_fields}
    mapped.update(
        {
            "actual_draw_year": year,
            "model_target_year": model_year,
            "source_scope": source_family or source_file,
            "source_namespace": "2026_PERMITS=2027_MODEL_LIVE_PLUS_PDF_DENSE",
            "draw_source_namespace": "2026_LIVE_PLUS_PDF_DENSE_RECONCILED",
            "source_file": source_file,
            "draw_source_file": source_file,
            "source_path": source_file,
            "source_pdf": source_file,
            "pdf_page": clean(row.get("source_pdf_page")),
            "official_page": clean(row.get("source_pdf_page")),
            "page_kind": clean(row.get("record_kind")),
            "hunt_code": norm_code(row.get("hunt_code")),
            "hunt_name": clean(row.get("hunt_name")),
            "raw_hunt_name": clean(row.get("raw_hunt_name") or row.get("hunt_name")),
            "species": clean(row.get("species")),
            "sex": clean(row.get("sex_type")),
            "sex_type": clean(row.get("sex_type")),
            "draw_design": clean(row.get("draw_pool") or row.get("draw_design")),
            "weapon": clean(row.get("weapon")),
            "hunt_draw_class": clean(row.get("hunt_class")),
            "hunt_type": clean(row.get("hunt_type")),
            "hunt_class": clean(row.get("hunt_class")),
            "residency": norm_residency(row.get("residency")),
            "points": norm_points(row.get("points")),
            "eligible_applicants": clean(row.get("eligible_applicants")),
            "bonus_permits": clean(row.get("bonus_permits")),
            "regular_permits": clean(row.get("regular_permits")),
            "total_permits": clean(row.get("total_permits")),
            "success_ratio": clean(row.get("success_ratio") or row.get("success_ratio_text")),
            "p_draw": clean(row.get("p_draw")),
            "p_draw_percent": clean(row.get("p_draw_percent")),
            "row_type": record_type,
            "record_type": record_type,
            "candidate_promotion_status": clean(row.get("candidate_promotion_status")),
            "algorithm_status": clean(row.get("candidate_promotion_reason")),
            "source_dataset": clean(row.get("source_dataset")),
            "extraction_status": clean(row.get("merge_source")),
            "parse_method": "2026_ACCEPTED_DENSE_CANDIDATE_TO_LONG_SCHEMA",
            "qa_status": clean(row.get("candidate_promotion_status")),
            "qa_notes": clean(row.get("candidate_promotion_reason")),
            "notes": clean(row.get("source_report_title")),
            "permits_2026_res": clean(row.get("resident_quota_quantity")),
            "permits_2026_nr": clean(row.get("nonresident_quota_quantity")),
            "permits_2026_total": clean(row.get("quota_quantity")),
        }
    )
    return mapped


def duplicate_groups(rows: list[dict[str, str]], key_fn) -> list[dict[str, object]]:
    counts: Counter[tuple[str, ...]] = Counter(key_fn(row) for row in rows)
    dupes = []
    for key, count in counts.items():
        if count > 1:
            dupes.append({"count": count, "key": "|".join(key)})
    return dupes


def main() -> None:
    tag = now_tag()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    long_fields, long_rows = read_rows(LONG_PATH)
    point_rows, hunt_rows = build_finalized_rows()
    finalized_rows = point_rows + hunt_rows
    accepted_2026_fields, accepted_2026_rows = read_rows(ACCEPTED_2026)

    finalized_by_year = count_by_year(finalized_rows)
    long_by_year_before = count_by_year(long_rows)

    finalized_keys_by_year: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for row in finalized_rows:
        finalized_keys_by_year[finalized_key(row)[0]].add(finalized_key(row))
    long_keys_by_year: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for row in long_rows:
        long_keys_by_year[long_key(row)[0]].add(long_key(row))

    reconciliation_rows: list[dict[str, object]] = []
    for year in sorted(set(finalized_by_year) | set(long_by_year_before)):
        fkeys = finalized_keys_by_year.get(year, set())
        lkeys = long_keys_by_year.get(year, set())
        reconciliation_rows.append(
            {
                "year": year,
                "finalized_split_rows": finalized_by_year.get(year, 0),
                "draw_results_long_rows_before": long_by_year_before.get(year, 0),
                "finalized_unique_keys": len(fkeys),
                "long_unique_keys_before": len(lkeys),
                "shared_keys": len(fkeys & lkeys),
                "only_in_finalized_keys": len(fkeys - lkeys),
                "only_in_long_keys_before": len(lkeys - fkeys),
                "reconciliation_read": (
                    "MATCH"
                    if finalized_by_year.get(year, 0) == long_by_year_before.get(year, 0)
                    else "ROW_COUNT_DIFF"
                ),
            }
        )

    write_csv(
        AUDIT_DIR / "finalized_vs_draw_results_long_by_year.csv",
        reconciliation_rows,
        [
            "year",
            "finalized_split_rows",
            "draw_results_long_rows_before",
            "finalized_unique_keys",
            "long_unique_keys_before",
            "shared_keys",
            "only_in_finalized_keys",
            "only_in_long_keys_before",
            "reconciliation_read",
        ],
    )

    # Sync stale normalized yearly files from canonical long slices for 2021/2022.
    yearly_sync_rows: list[dict[str, object]] = []
    yearly_backup_paths: list[str] = []
    for year, model_year in [("2021", "2022"), ("2022", "2023")]:
        target = NORMALIZED / f"draw_results_{year}_for_{model_year}_candidate_promotion_file_records.csv"
        if target.exists():
            target_fields, target_rows = read_rows(target)
            target_before_rows = len(target_rows)
            backup_path = backup(target, f"sync_{year}_{model_year}_yearly_from_long", tag)
            yearly_backup_paths.append(str(backup_path))
        else:
            target_before_rows = 0
            backup_path = None
        slice_rows = [
            row
            for row in long_rows
            if norm_year(row.get("source_year") or row.get("year")) == year
            and norm_year(row.get("model_year") or row.get("model_target_year")) == model_year
        ]
        write_csv(target, slice_rows, long_fields)
        yearly_sync_rows.append(
            {
                "year": year,
                "model_year": model_year,
                "target": str(target),
                "before_rows": target_before_rows,
                "after_rows": len(slice_rows),
                "source": "draw_results_long.csv canonical slice",
                "backup_path": str(backup_path) if backup_path else "",
            }
        )

    write_csv(
        AUDIT_DIR / "yearly_normalized_sync_2021_2022.csv",
        yearly_sync_rows,
        ["year", "model_year", "target", "before_rows", "after_rows", "source", "backup_path"],
    )

    # Append 2026 into canonical long master by replacing any existing 2026 slice.
    long_backup = backup(LONG_PATH, "append_2026_reconciled_slice", tag)
    rows_without_2026 = [
        row
        for row in long_rows
        if norm_year(row.get("source_year") or row.get("year") or row.get("actual_draw_year")) != "2026"
    ]
    mapped_2026 = [map_2026_to_long(row, long_fields) for row in accepted_2026_rows]
    promoted_rows = rows_without_2026 + mapped_2026
    write_csv(LONG_PATH, promoted_rows, long_fields)

    # Also synchronize the normalized 2026 yearly file to the same long-schema slice.
    target_2026 = NORMALIZED / "draw_results_2026_for_2027_candidate_promotion_file_records.csv"
    target_2026_before_rows = 0
    target_2026_backup = ""
    if target_2026.exists():
        _, t2026_rows = read_rows(target_2026)
        target_2026_before_rows = len(t2026_rows)
        target_2026_backup = str(backup(target_2026, "sync_2026_yearly_from_accepted_dense_candidate", tag))
    write_csv(target_2026, mapped_2026, long_fields)

    long_by_year_after = count_by_year(promoted_rows)
    strict_dupes_after = duplicate_groups(promoted_rows, long_validation_key)
    cg9999_by_year: Counter[str] = Counter()
    blank_hunt_code_rows = 0
    blank_year_rows = 0
    for row in promoted_rows:
        year = norm_year(row.get("source_year") or row.get("year"))
        if norm_code(row.get("hunt_code")) == "CG9999":
            cg9999_by_year[year] += 1
        if not norm_code(row.get("hunt_code")):
            blank_hunt_code_rows += 1
        if not year:
            blank_year_rows += 1

    write_csv(
        AUDIT_DIR / "draw_results_long_row_counts_before_after.csv",
        [
            {
                "year": year,
                "before_rows": long_by_year_before.get(year, 0),
                "after_rows": long_by_year_after.get(year, 0),
                "delta": long_by_year_after.get(year, 0) - long_by_year_before.get(year, 0),
            }
            for year in sorted(set(long_by_year_before) | set(long_by_year_after))
        ],
        ["year", "before_rows", "after_rows", "delta"],
    )
    write_csv(AUDIT_DIR / "draw_results_long_duplicate_strict_keys_after.csv", strict_dupes_after, ["count", "key"])
    write_csv(
        AUDIT_DIR / "draw_results_long_cg9999_by_year_after.csv",
        [{"year": year, "cg9999_rows": count} for year, count in sorted(cg9999_by_year.items())],
        ["year", "cg9999_rows"],
    )

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_decision": "DRAW_RESULTS_LONG_REMAINS_ENGINE_FEEDER_CANONICAL",
        "canonical_reason": (
            "draw_results_long.csv carries the 55-column engine-facing schema and richer identity/source metadata; "
            "finalized_point_distribution.csv and finalized_hunt_truth.csv remain narrower reconciliation/source-truth surfaces."
        ),
        "finalized_point_distribution_rows": len(point_rows),
        "finalized_hunt_truth_rows": len(hunt_rows),
        "finalized_combined_rows": len(finalized_rows),
        "draw_results_long_rows_before": len(long_rows),
        "draw_results_long_rows_after": len(promoted_rows),
        "draw_results_long_backup": str(long_backup),
        "accepted_2026_candidate": str(ACCEPTED_2026),
        "accepted_2026_rows": len(accepted_2026_rows),
        "accepted_2026_columns": len(accepted_2026_fields),
        "mapped_2026_rows_added": len(mapped_2026),
        "normalized_2026_yearly_before_rows": target_2026_before_rows,
        "normalized_2026_yearly_after_rows": len(mapped_2026),
        "normalized_2026_backup": target_2026_backup,
        "yearly_2021_2022_sync": yearly_sync_rows,
        "row_counts_after_by_year": dict(sorted(long_by_year_after.items())),
        "duplicate_strict_key_groups_after": len(strict_dupes_after),
        "blank_hunt_code_rows_after": blank_hunt_code_rows,
        "blank_year_rows_after": blank_year_rows,
        "cg9999_by_year_after": dict(sorted(cg9999_by_year.items())),
        "reconciliation_report": str(AUDIT_DIR / "finalized_vs_draw_results_long_by_year.csv"),
        "row_count_audit": str(AUDIT_DIR / "draw_results_long_row_counts_before_after.csv"),
        "duplicate_key_audit": str(AUDIT_DIR / "draw_results_long_duplicate_strict_keys_after.csv"),
        "cg9999_audit": str(AUDIT_DIR / "draw_results_long_cg9999_by_year_after.csv"),
        "failed_gates": [],
    }

    if blank_hunt_code_rows:
        status["failed_gates"].append("BLANK_HUNT_CODE_ROWS_AFTER")
    if blank_year_rows:
        status["failed_gates"].append("BLANK_YEAR_ROWS_AFTER")
    if strict_dupes_after:
        status["failed_gates"].append("DUPLICATE_STRICT_KEY_GROUPS_AFTER")
    if len(mapped_2026) != 30298:
        status["failed_gates"].append("ACCEPTED_2026_ROW_COUNT_NOT_30298")
    if long_by_year_after.get("2026") != 30298:
        status["failed_gates"].append("DRAW_RESULTS_LONG_2026_ROW_COUNT_NOT_30298")

    status["status"] = "PASS_RECONCILED_SYNCED_2021_2022_AND_APPENDED_2026" if not status["failed_gates"] else "REVIEW_REQUIRED"

    (AUDIT_DIR / "RECONCILE_FINALIZED_VS_LONG_AND_SYNC_2026_STATUS.json").write_text(
        json.dumps(status, indent=2),
        encoding="utf-8",
    )
    report = [
        "# Reconcile Finalized Truth With Draw Results Long",
        "",
        f"Generated UTC: {status['generated_at_utc']}",
        "",
        f"Status: {status['status']}",
        "",
        "## Canonical Decision",
        "",
        f"{status['canonical_decision']}: {status['canonical_reason']}",
        "",
        "## Actions",
        "",
        "- Synced 2021 normalized yearly file from draw_results_long canonical slice.",
        "- Synced 2022 normalized yearly file from draw_results_long canonical slice.",
        "- Appended accepted 2026 dense live+PDF candidate into draw_results_long.csv.",
        "- Synced 2026 normalized yearly file to the same long-schema 2026 slice because the previous target was stale.",
        "",
        "## Final Counts",
        "",
        f"- draw_results_long rows before: {len(long_rows)}",
        f"- draw_results_long rows after: {len(promoted_rows)}",
        f"- 2026 rows added: {len(mapped_2026)}",
        f"- duplicate strict-key groups after: {len(strict_dupes_after)}",
        f"- blank hunt_code rows after: {blank_hunt_code_rows}",
        f"- blank year rows after: {blank_year_rows}",
        "",
        "## Outputs",
        "",
        f"- Status JSON: {AUDIT_DIR / 'RECONCILE_FINALIZED_VS_LONG_AND_SYNC_2026_STATUS.json'}",
        f"- Reconciliation CSV: {AUDIT_DIR / 'finalized_vs_draw_results_long_by_year.csv'}",
        f"- Row counts: {AUDIT_DIR / 'draw_results_long_row_counts_before_after.csv'}",
        f"- Duplicate keys: {AUDIT_DIR / 'draw_results_long_duplicate_strict_keys_after.csv'}",
        f"- Backups: {BACKUP_DIR}",
    ]
    (AUDIT_DIR / "RECONCILE_FINALIZED_VS_LONG_AND_SYNC_2026_REPORT.md").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
