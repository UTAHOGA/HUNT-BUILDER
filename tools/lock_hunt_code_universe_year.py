#!/usr/bin/env python3
"""Create a locked hunt-code universe package from a reviewed yearly audit."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
SPORTSMAN_OCR_ARTIFACT_RE = re.compile(r"^A[A-Z]{2}\d{4}$")
REVIEWED_INCORRECT_HUNT_NUMBER_BY_YEAR = {
    2026: {
        "EA1287": "Correction page lists EA1287 as the incorrect hunt number for Box Elder, Grouse Creek; corrected hunt number is EA1007.",
        "EA1176": "Correction page lists EA1176 as the incorrect hunt number for Weber Florence Creek/Stillman Creek CWMU; corrected hunt number is EA1263.",
        "PD1025": "Correction page lists PD1025 as the incorrect hunt number for Cottonwood Ridge CWMU; corrected hunt number is PD1050.",
    }
}


def clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_legacy_bucket(value: str) -> str:
    if value == "DATABASE_BOUNDARY_SUPPORT_REFERENCE":
        return "DATABASE_NONSCORABLE_REFERENCE_APPENDIX"
    return value


def normalize_source_summary_buckets(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = normalize_legacy_bucket(key)
            normalized_item = normalize_source_summary_buckets(item)
            if normalized_key in out and isinstance(out[normalized_key], (int, float)) and isinstance(normalized_item, (int, float)):
                out[normalized_key] += normalized_item
            else:
                out[normalized_key] = normalized_item
        return out
    if isinstance(value, list):
        return [normalize_source_summary_buckets(item) for item in value]
    if isinstance(value, str):
        return normalize_legacy_bucket(value)
    return value


def canonical_codes_for_year(year: int) -> set[str]:
    path = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / (
        f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"
    )
    if not path.exists():
        return set()
    return {clean(row.get("hunt_code")).upper() for row in read_csv(path) if clean(row.get("hunt_code"))}


def is_reviewed_source_artifact(row: dict[str, str]) -> str:
    code = clean(row.get("hunt_code")).upper()
    if SPORTSMAN_OCR_ARTIFACT_RE.match(code):
        return (
            "A-prefixed sportsman/application extraction artifact; not a real hunt-code prefix. "
            "Exclude from official active truth, scoring, and year-to-year hunt-code counts."
        )
    return ""


def classify_locked_row(year: int, row: dict[str, str], next_year_canonical_codes: set[str]) -> dict[str, str]:
    scoring_bucket = clean(row.get("scoring_bucket"))
    primary_bucket = normalize_legacy_bucket(clean(row.get("primary_universe_bucket")))
    present_canonical = clean(row.get("present_canonical_yearly")) == "YES"
    out: dict[str, str] = {
        "locked_year": str(year),
        "model_target_year": str(year + 1),
        "active_year_truth": "NO",
        "locked_reconciled_bucket": "NEEDS_REVIEW",
        "prediction_accuracy_treatment": "EXCLUDE_PENDING_REVIEW",
        "database_next_year_support": "NO",
        "source_year_artifact": "NO",
        "excluded_from_lock_prefix_filter": "NO",
        "lock_status": f"LOCKED_{year}_UNTIL_NEXT_YEAR_DATA_ADDED",
        "lock_note": "",
    }
    source_artifact_note = is_reviewed_source_artifact(row)
    incorrect_note = REVIEWED_INCORRECT_HUNT_NUMBER_BY_YEAR.get(year, {}).get(clean(row.get("hunt_code")).upper())
    if source_artifact_note:
        out.update(
            {
                "source_year_artifact": "YES",
                "locked_reconciled_bucket": "REVIEWED_SOURCE_YEAR_ARTIFACT_NOT_ACTIVE_TRUTH",
                "prediction_accuracy_treatment": "EXCLUDED_SOURCE_EXTRACTION_ARTIFACT",
                "lock_note": source_artifact_note,
            }
        )
    elif incorrect_note:
        out.update(
            {
                "source_year_artifact": "YES",
                "locked_reconciled_bucket": "REVIEWED_INCORRECT_HUNT_NUMBER_NOT_ACTIVE_TRUTH",
                "prediction_accuracy_treatment": "EXCLUDED_INCORRECT_HUNT_NUMBER_CORRECTION_ARTIFACT",
                "lock_note": incorrect_note,
            }
        )
    elif present_canonical:
        out.update(
            {
                "active_year_truth": "YES",
                "locked_reconciled_bucket": "ACTIVE_YEAR_CANONICAL_TRUTH",
                "prediction_accuracy_treatment": "SCORABLE_OR_REFERENCE_BY_CANONICAL_RECORD_TYPE",
                "lock_note": "Same-year yearly canonical confirms this hunt code; long-file presence is reconciled separately.",
            }
        )
    elif scoring_bucket == "REGULATION_SOURCE_REVIEW_NOT_IN_CANONICAL":
        out.update(
            {
                "active_year_truth": "YES",
                "locked_reconciled_bucket": "ACTIVE_YEAR_REGULATION_REFERENCE_REVIEW",
                "prediction_accuracy_treatment": "REFERENCE_ONLY_NOT_SCORABLE_UNLESS_CANONICALIZED",
                "lock_note": "Same-year regulation/guidebook evidence confirms a hunt-code reference, but canonical yearly draw-result truth does not make it scorable.",
            }
        )
    elif scoring_bucket == "DRAW_RESULT_SOURCE_REVIEW_NOT_IN_CANONICAL":
        out.update(
            {
                "active_year_truth": "YES",
                "locked_reconciled_bucket": "ACTIVE_YEAR_DRAW_RESULT_REFERENCE_REVIEW",
                "prediction_accuracy_treatment": "REFERENCE_ONLY_NOT_SCORABLE_UNLESS_CANONICALIZED",
                "lock_note": "Same-year draw-result PDF evidence exists outside canonical yearly truth; retain for review and exclude from scoring until canonicalized.",
            }
        )
    elif primary_bucket == "DATABASE_NONSCORABLE_REFERENCE_APPENDIX" or scoring_bucket == "SUPPORT_ONLY_REVIEW":
        if clean(row.get("hunt_code")).upper() in next_year_canonical_codes:
            out.update(
                {
                    "database_next_year_support": "YES",
                    "locked_reconciled_bucket": "DATABASE_NEXT_YEAR_PERMIT_SUPPORT",
                    "prediction_accuracy_treatment": "EXCLUDED_FROM_ACTIVE_YEAR_ACCURACY_NEXT_YEAR_SUPPORT",
                    "lock_note": "DATABASE reference support exists without same-year canonical or PDF draw evidence, and the code appears in next-year canonical truth; retain for crosswalk support and exclude from active-year scoring.",
                }
            )
        else:
            out.update(
                {
                    "locked_reconciled_bucket": "DATABASE_NONSCORABLE_REFERENCE_APPENDIX",
                    "prediction_accuracy_treatment": "EXCLUDED_FROM_ACTIVE_YEAR_ACCURACY_NONSCORABLE_APPENDIX",
                    "lock_note": "DATABASE-only reference row without same-year canonical/PDF draw evidence or next-year canonical confirmation; retain only in the non-scorable appendix, not official hunt-code truth.",
                }
            )
    return out


def build_lock(year: int, audit_dir: Path, out_dir: Path) -> dict[str, Any]:
    audit_dir = audit_dir.resolve()
    out_dir = out_dir.resolve()
    audit_csv = audit_dir / f"{year}_HUNT_CODE_UNIVERSE_AUDIT.csv"
    audit_summary_path = audit_dir / f"{year}_HUNT_CODE_UNIVERSE_SUMMARY.json"
    if not audit_csv.exists():
        raise FileNotFoundError(audit_csv)
    if not audit_summary_path.exists():
        raise FileNotFoundError(audit_summary_path)

    source_summary = normalize_source_summary_buckets(load_json(audit_summary_path))
    rows = read_csv(audit_csv)
    next_year_canonical_codes = canonical_codes_for_year(year + 1)
    locked_rows: list[dict[str, Any]] = []
    for row in rows:
        locked = dict(row)
        locked["primary_universe_bucket"] = normalize_legacy_bucket(clean(locked.get("primary_universe_bucket")))
        locked.update(classify_locked_row(year, row, next_year_canonical_codes))
        locked_rows.append(locked)

    base_fields = list(rows[0].keys()) if rows else []
    lock_fields = [
        "locked_year",
        "model_target_year",
        "active_year_truth",
        "locked_reconciled_bucket",
        "prediction_accuracy_treatment",
        "database_next_year_support",
        "source_year_artifact",
        "excluded_from_lock_prefix_filter",
        "lock_status",
        "lock_note",
    ]
    fields = base_fields + [field for field in lock_fields if field not in base_fields]

    active_rows = [row for row in locked_rows if row["active_year_truth"] == "YES"]
    support_rows = [row for row in locked_rows if row["database_next_year_support"] == "YES"]
    nonscorable_reference_rows = [
        row for row in locked_rows if row["locked_reconciled_bucket"] == "DATABASE_NONSCORABLE_REFERENCE_APPENDIX"
    ]
    artifact_rows = [row for row in locked_rows if row["source_year_artifact"] == "YES"]
    excluded_rows: list[dict[str, Any]] = []
    for code in source_summary.get("excluded_codes", []):
        prefix = "".join(ch for ch in clean(code) if ch.isalpha())
        excluded_row = {field: "" for field in fields}
        excluded_row.update(
            {
                "hunt_code": clean(code),
                "prefix": prefix,
                "locked_year": str(year),
                "model_target_year": str(year + 1),
                "active_year_truth": "NO",
                "locked_reconciled_bucket": "OUT_OF_SCOPE_PREFIX_EXCLUDED",
                "prediction_accuracy_treatment": "EXCLUDED_FROM_BIG_GAME_HUNT_CODE_UNIVERSE",
                "database_next_year_support": "NO",
                "source_year_artifact": "NO",
                "excluded_from_lock_prefix_filter": "YES",
                "lock_status": f"LOCKED_{year}_UNTIL_NEXT_YEAR_DATA_ADDED",
                "lock_note": "Excluded by prefix policy for this big-game hunt-code universe lock.",
            }
        )
        excluded_rows.append(excluded_row)
    reconciliation_rows = [
        row
        for row in locked_rows
        if row["locked_reconciled_bucket"]
        in {
            "ACTIVE_YEAR_CANONICAL_TRUTH",
            "DATABASE_NEXT_YEAR_PERMIT_SUPPORT",
            "DATABASE_NONSCORABLE_REFERENCE_APPENDIX",
            "ACTIVE_YEAR_REGULATION_REFERENCE_REVIEW",
            "ACTIVE_YEAR_DRAW_RESULT_REFERENCE_REVIEW",
            "REVIEWED_INCORRECT_HUNT_NUMBER_NOT_ACTIVE_TRUTH",
            "REVIEWED_SOURCE_YEAR_ARTIFACT_NOT_ACTIVE_TRUTH",
            "NEEDS_REVIEW",
        }
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / f"LOCKED_{year}_HUNT_CODE_UNIVERSE_WITH_BOUNDARY_ID.csv", locked_rows, fields)
    write_csv(out_dir / f"LOCKED_{year}_ACTIVE_YEAR_TRUTH_WITH_BOUNDARY_ID.csv", active_rows, fields)
    write_csv(out_dir / f"LOCKED_{year}_DATABASE_NEXT_YEAR_PERMIT_SUPPORT.csv", support_rows, fields)
    write_csv(out_dir / f"LOCKED_{year}_DATABASE_NONSCORABLE_REFERENCE_APPENDIX.csv", nonscorable_reference_rows, fields)
    write_csv(out_dir / f"LOCKED_{year}_SOURCE_YEAR_ARTIFACT_ROWS.csv", artifact_rows, fields)
    write_csv(out_dir / f"LOCKED_{year}_EXCLUDED_WATERFOWL_UPLAND_PREFIX_ROWS.csv", excluded_rows, fields)
    write_csv(out_dir / f"LOCKED_{year}_CANONICAL_LONG_RECONCILIATION.csv", reconciliation_rows, fields)

    bucket_counts = Counter(row["locked_reconciled_bucket"] for row in locked_rows)
    scoring_bucket_counts = Counter(row.get("scoring_bucket", "") for row in locked_rows)
    canonical_codes = sum(1 for row in locked_rows if row.get("present_canonical_yearly") == "YES")
    long_codes = sum(1 for row in locked_rows if row.get("present_long_file") == "YES")
    canonical_set = {row["hunt_code"] for row in locked_rows if row.get("present_canonical_yearly") == "YES"}
    long_set = {row["hunt_code"] for row in locked_rows if row.get("present_long_file") == "YES"}
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "locked_year": year,
        "model_target_year": year + 1,
        "classification": f"LOCKED_{year}_CANONICAL_LONG_HUNT_CODE_UNIVERSE_RECONCILED",
        "source_audit": str(audit_csv.relative_to(REPO)),
        "pdf_source_scope": source_summary.get("pdf_source_scope", ""),
        "duplicate_pdf_count": source_summary.get("duplicate_pdf_count", 0),
        "excluded_prefixes": source_summary.get("excluded_prefixes", []),
        "excluded_prefix_rows": len(excluded_rows),
        "total_union_hunt_codes": len(locked_rows),
        "official_active_hunt_code_count": len(active_rows),
        "active_year_truth_codes": len(active_rows),
        "active_year_prediction_scorable_codes": scoring_bucket_counts.get(
            "CANDIDATE_MODEL_SCORABLE_REQUIRES_ENGINE_GATES", 0
        ),
        "active_year_reference_only_codes": len(active_rows)
        - scoring_bucket_counts.get("CANDIDATE_MODEL_SCORABLE_REQUIRES_ENGINE_GATES", 0),
        "canonical_yearly_codes": canonical_codes,
        "long_file_codes": long_codes,
        "canonical_long_aligned_codes": len(canonical_set & long_set),
        "canonical_minus_long_codes": sorted(canonical_set - long_set),
        "long_minus_canonical_codes": sorted(long_set - canonical_set),
        "regulation_reference_review_codes": bucket_counts.get("ACTIVE_YEAR_REGULATION_REFERENCE_REVIEW", 0),
        "draw_result_review_codes": bucket_counts.get("ACTIVE_YEAR_DRAW_RESULT_REFERENCE_REVIEW", 0),
        "source_year_artifact_codes": len(artifact_rows),
        "database_next_year_permit_support_codes": len(support_rows),
        "database_nonscorable_reference_appendix_codes": len(nonscorable_reference_rows),
        "codes_with_boundary_id": sum(1 for row in locked_rows if clean(row.get("boundary_id"))),
        "active_year_codes_with_boundary_id": sum(1 for row in active_rows if clean(row.get("boundary_id"))),
        "locked_bucket_counts": dict(sorted(bucket_counts.items())),
        "outputs": [
            f"LOCKED_{year}_HUNT_CODE_UNIVERSE_WITH_BOUNDARY_ID.csv",
            f"LOCKED_{year}_ACTIVE_YEAR_TRUTH_WITH_BOUNDARY_ID.csv",
            f"LOCKED_{year}_DATABASE_NEXT_YEAR_PERMIT_SUPPORT.csv",
            f"LOCKED_{year}_DATABASE_NONSCORABLE_REFERENCE_APPENDIX.csv",
            f"LOCKED_{year}_SOURCE_YEAR_ARTIFACT_ROWS.csv",
            f"LOCKED_{year}_EXCLUDED_WATERFOWL_UPLAND_PREFIX_ROWS.csv",
            f"LOCKED_{year}_CANONICAL_LONG_RECONCILIATION.csv",
            f"LOCKED_{year}_HUNT_CODE_UNIVERSE_SUMMARY.json",
            f"README_LOCKED_{year}.md",
        ],
        "policy": {
            "OFFICIAL_HUNT_CODE_COUNT": "Use official_active_hunt_code_count / active_year_truth_codes for the locked year's hunt-code truth count.",
            "DATABASE_NEXT_YEAR_PERMIT_SUPPORT": "Retain only when the code is confirmed by next-year canonical truth; exclude from active-year truth counts and prediction accuracy for the locked year.",
            "DATABASE_NONSCORABLE_REFERENCE_APPENDIX": "Retain only as a non-scorable appendix when same-year and next-year canonical truth do not confirm the code. Do not use for official counts, scoring, public odds, or prediction accuracy.",
            "excluded_prefixes": "SC, SG, ST, and TS are excluded from this big-game hunt-code universe lock; waterfowl is out of scope.",
            "active_truth_rule": "Active-year truth requires same-year canonical, long/PDF draw evidence, or same-year regulation/guidebook evidence. Hunt-code-only DATABASE permit carry-forward is not sufficient.",
        },
        "source_summary_counts": source_summary,
    }
    (out_dir / f"LOCKED_{year}_HUNT_CODE_UNIVERSE_SUMMARY.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    lines = [
        f"# Locked {year} Hunt-Code Universe",
        "",
        f"Status: `LOCKED_{year}_UNTIL_NEXT_YEAR_DATA_ADDED`",
        "",
        "No runtime, engine, website, or prediction-output files are changed by this lock.",
        "",
        "## Counts",
        "",
        f"- Official active hunt-code count: `{summary['official_active_hunt_code_count']}`",
        f"- Active prediction-scorable codes: `{summary['active_year_prediction_scorable_codes']}`",
        f"- Active reference-only codes: `{summary['active_year_reference_only_codes']}`",
        f"- Full ledger rows, including support/appendix rows: `{summary['total_union_hunt_codes']}`",
        f"- Active-year truth codes: `{summary['active_year_truth_codes']}`",
        f"- Canonical yearly codes: `{summary['canonical_yearly_codes']}`",
        f"- Long-file codes: `{summary['long_file_codes']}`",
        f"- Canonical/long aligned codes: `{summary['canonical_long_aligned_codes']}`",
        f"- Regulation reference-review codes: `{summary['regulation_reference_review_codes']}`",
        f"- Draw-result review codes: `{summary['draw_result_review_codes']}`",
        f"- DATABASE next-year support codes: `{summary['database_next_year_permit_support_codes']}`",
        f"- DATABASE non-scorable reference appendix codes: `{summary['database_nonscorable_reference_appendix_codes']}`",
        f"- Codes with boundary_id: `{summary['codes_with_boundary_id']}`",
        f"- Active-year truth codes with boundary_id: `{summary['active_year_codes_with_boundary_id']}`",
        f"- Excluded prefix rows: `{summary['excluded_prefix_rows']}`",
        f"- Duplicate PDFs skipped: `{summary['duplicate_pdf_count']}`",
        "",
        "## Policy",
        "",
        "- Official year truth is `active_year_truth_codes`; support and appendix rows do not count as official current hunt codes.",
        "- DATABASE next-year support rows are retained only when confirmed by next-year canonical truth and excluded from active-year prediction accuracy.",
        "- DATABASE non-scorable reference appendix rows are retained for lookup/review only and must not feed scoring, public odds, or official count totals.",
        "- Regulation-only rows are reference-review active truth unless canonicalized as scorable draw-result rows.",
        "- Waterfowl/swan TS codes are excluded from this big-game hunt-code universe lock.",
        "",
        "## Outputs",
        "",
        *(f"- `{item}`" for item in summary["outputs"]),
        "",
        "Do not change these locked counts until another year of source data is intentionally added and a new lock folder is created.",
    ]
    (out_dir / f"README_LOCKED_{year}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Lock a reviewed hunt-code universe audit for one year.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to data_truth/hunt_code_universe_truth/locked/<year>.",
    )
    args = parser.parse_args()
    out_dir = args.output_dir or REPO / "data_truth" / "hunt_code_universe_truth" / "locked" / str(args.year)
    summary = build_lock(args.year, args.audit_dir, out_dir)
    print(f"LOCK_DIR: {out_dir}")
    print(f"TOTAL_UNION_HUNT_CODES: {summary['total_union_hunt_codes']}")
    print(f"ACTIVE_YEAR_TRUTH_CODES: {summary['active_year_truth_codes']}")
    print(f"CANONICAL_LONG_ALIGNED_CODES: {summary['canonical_long_aligned_codes']}")
    print(f"DATABASE_NEXT_YEAR_SUPPORT_CODES: {summary['database_next_year_permit_support_codes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
