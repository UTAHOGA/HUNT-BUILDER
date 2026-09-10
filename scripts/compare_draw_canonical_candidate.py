#!/usr/bin/env python3
"""Compare an isolated yearly draw-truth candidate with a retained canonical."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


KEY_FIELDS = (
    "actual_draw_year",
    "model_target_year",
    "source_scope",
    "hunt_code",
    "points",
    "record_type",
)
OFFICIAL_VALUE_FIELDS = (
    "resident_eligible_applicants",
    "resident_bonus_permits",
    "resident_regular_permits",
    "resident_total_permits",
    "resident_success_ratio",
    "resident_p_draw",
    "nonresident_eligible_applicants",
    "nonresident_bonus_permits",
    "nonresident_regular_permits",
    "nonresident_total_permits",
    "nonresident_success_ratio",
    "nonresident_p_draw",
    "total_eligible_applicants",
    "total_bonus_permits",
    "total_regular_permits",
    "total_permits",
    "total_p_draw",
)
IDENTITY_AND_LINEAGE_FIELDS = (
    "hunt_name",
    "species",
    "sex",
    "hunt_type",
    "draw_design",
    "hunt_class",
    "algorithm_status",
    "source_file",
    "source_path",
    "pdf_page",
)
COUNT_FIELDS = (
    "resident_eligible_applicants",
    "resident_bonus_permits",
    "resident_regular_permits",
    "resident_total_permits",
    "nonresident_eligible_applicants",
    "nonresident_bonus_permits",
    "nonresident_regular_permits",
    "nonresident_total_permits",
    "total_eligible_applicants",
    "total_bonus_permits",
    "total_regular_permits",
    "total_permits",
)
LANE_PROBABILITY_FIELDS = ("resident_p_draw", "nonresident_p_draw")
SUCCESS_RATIO_FIELDS = ("resident_success_ratio", "nonresident_success_ratio")


def clean(value: object) -> str:
    return str(value or "").strip()


def decimal_value(value: object) -> Decimal | None:
    text = clean(value).replace(",", "")
    if not text or text.upper() in {"N/A", "NA"}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def success_ratio_denominator(value: object) -> Decimal | None:
    text = clean(value).upper().replace(",", "")
    if not text or text in {"N/A", "NA"}:
        return None
    if text.startswith("1 IN "):
        text = text[5:].strip()
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized_source_role(row: dict[str, str]) -> str:
    """Bridge legacy split-output filenames to their official parent source role."""
    text = " ".join(
        clean(row.get(field)).upper().replace("\\", "/")
        for field in ("source_scope", "source_file", "source_pdf")
    )
    if "YOUTH_TURKEY" in text:
        return "YOUTH_TURKEY"
    if "TURKEY" in text:
        return "TURKEY"
    if "YOUTH_D.H." in text or "YOUTH_DH" in text or "YOUTH_DEDICATED_HUNTER" in text:
        return "YOUTH_DEDICATED_HUNTER"
    if "LIFETIME" in text:
        return "LIFETIME_GENERAL_SEASON_DEER"
    if "YOUTH_G.S." in text or "YOUTH_GENERAL_SEASON_DEER" in text or "YOUTH_DEER" in text:
        return "YOUTH_GENERAL_SEASON_DEER"
    if "YOUTH_ANY_BULL" in text or "YOUTH_BULL_ELK" in text:
        return "YOUTH_ANY_BULL_ELK"
    if "YOUTH_ANTLERLESS" in text or "CWMU_YOUTH_ANTLERLESS" in text:
        return "YOUTH_ANTLERLESS"
    if "ANTLERLESS" in text or "DOE_PRONGHORN" in text:
        return "ANTLERLESS"
    if "BLACK_BEAR" in text or "/BLACK_BEAR/" in text:
        return "BLACK_BEAR"
    if "COUGAR" in text:
        return "COUGAR"
    if "SPORTSMAN" in text:
        return "SPORTSMAN"
    if "D.H._DEER" in text or "DEDICATED_HUNTER" in text or "DH_ODDS" in text:
        return "DEDICATED_HUNTER"
    if "G.S._BUCK_DEER" in text or "GENERAL_SEASON_DEER" in text or "DEER_ODDS" in text:
        return "GENERAL_SEASON_DEER"
    if any(token in text for token in ("BG-ODDS", "L.E._", "O.I.L._", "CWMU_BIG_GAME", "BIG_GAME")):
        return "BIG_GAME"
    return clean(row.get("source_scope"))


def row_key(row: dict[str, str], normalize_source_roles: bool = False) -> tuple[str, ...]:
    values = []
    for field in KEY_FIELDS:
        if field == "source_scope" and normalize_source_roles:
            values.append(normalized_source_role(row))
        elif (
            field == "record_type"
            and normalize_source_roles
            and clean(row.get(field)) in {"sportsman_total", "sportsman_total_draw_result"}
        ):
            values.append("sportsman_total_draw_result")
        elif (
            field == "points"
            and normalize_source_roles
            and clean(row.get("record_type")) == "hunt_total_draw_result"
            and clean(row.get(field)).upper() in {"", "TOTAL", "TOTALS"}
        ):
            values.append("")
        else:
            values.append(clean(row.get(field)))
    return tuple(values)


def key_text(key: tuple[str, ...]) -> str:
    return "|".join(key)


def index_rows(
    rows: list[dict[str, str]], normalize_source_roles: bool = False
) -> tuple[dict[tuple[str, ...], dict[str, str]], int]:
    counts = Counter(row_key(row, normalize_source_roles) for row in rows)
    duplicates = sum(count - 1 for count in counts.values() if count > 1)
    return {row_key(row, normalize_source_roles): row for row in rows}, duplicates


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--normalize-source-roles",
        action="store_true",
        help="Compare legacy split-output source filenames with semantic parent-PDF source roles.",
    )
    args = parser.parse_args()

    baseline_path = args.baseline.resolve()
    candidate_path = args.candidate.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_rows = read_rows(baseline_path)
    candidate_rows = read_rows(candidate_path)
    baseline, baseline_duplicates = index_rows(baseline_rows, args.normalize_source_roles)
    candidate, candidate_duplicates = index_rows(candidate_rows, args.normalize_source_roles)
    baseline_keys = set(baseline)
    candidate_keys = set(candidate)

    baseline_only = [
        {"comparison_key": key_text(key), **baseline[key]}
        for key in sorted(baseline_keys - candidate_keys)
    ]
    candidate_only = [
        {"comparison_key": key_text(key), **candidate[key]}
        for key in sorted(candidate_keys - baseline_keys)
    ]
    differences: list[dict[str, str]] = []
    official_value_diff_keys: set[tuple[str, ...]] = set()
    metadata_diff_keys: set[tuple[str, ...]] = set()
    count_diff_keys: set[tuple[str, ...]] = set()
    count_field_differences: Counter[str] = Counter()
    p_draw_material_diff_keys: set[tuple[str, ...]] = set()
    p_draw_material_field_differences: Counter[str] = Counter()
    p_draw_max_absolute_delta = Decimal("0")
    success_ratio_semantic_diff_keys: set[tuple[str, ...]] = set()
    success_ratio_semantic_field_differences: Counter[str] = Counter()
    for key in sorted(baseline_keys & candidate_keys):
        old = baseline[key]
        new = candidate[key]
        for field in COUNT_FIELDS:
            old_number = decimal_value(old.get(field))
            new_number = decimal_value(new.get(field))
            if old_number != new_number:
                count_diff_keys.add(key)
                count_field_differences[field] += 1
        for field in LANE_PROBABILITY_FIELDS:
            old_number = decimal_value(old.get(field))
            new_number = decimal_value(new.get(field))
            if old_number is None and new_number is None:
                continue
            if old_number is None or new_number is None:
                p_draw_material_diff_keys.add(key)
                p_draw_material_field_differences[field] += 1
                continue
            delta = abs(old_number - new_number)
            p_draw_max_absolute_delta = max(p_draw_max_absolute_delta, delta)
            if delta > Decimal("0.000000001"):
                p_draw_material_diff_keys.add(key)
                p_draw_material_field_differences[field] += 1
        for field in SUCCESS_RATIO_FIELDS:
            if success_ratio_denominator(old.get(field)) != success_ratio_denominator(new.get(field)):
                success_ratio_semantic_diff_keys.add(key)
                success_ratio_semantic_field_differences[field] += 1
        for field in OFFICIAL_VALUE_FIELDS + IDENTITY_AND_LINEAGE_FIELDS:
            old_value = clean(old.get(field))
            new_value = clean(new.get(field))
            if old_value == new_value:
                continue
            category = "OFFICIAL_VALUE" if field in OFFICIAL_VALUE_FIELDS else "IDENTITY_OR_LINEAGE"
            if category == "OFFICIAL_VALUE":
                official_value_diff_keys.add(key)
            else:
                metadata_diff_keys.add(key)
            differences.append(
                {
                    "comparison_key": key_text(key),
                    "difference_category": category,
                    "field": field,
                    "baseline_value": old_value,
                    "candidate_value": new_value,
                    "baseline_source_file": clean(old.get("source_file")),
                    "candidate_source_file": clean(new.get("source_file")),
                    "baseline_pdf_page": clean(old.get("pdf_page")),
                    "candidate_pdf_page": clean(new.get("pdf_page")),
                }
            )

    row_fields = ["comparison_key"] + list(candidate_rows[0])
    write_csv(output_dir / "baseline_only_rows.csv", baseline_only, row_fields)
    write_csv(output_dir / "candidate_only_rows.csv", candidate_only, row_fields)
    write_csv(
        output_dir / "matched_row_field_differences.csv",
        differences,
        [
            "comparison_key",
            "difference_category",
            "field",
            "baseline_value",
            "candidate_value",
            "baseline_source_file",
            "candidate_source_file",
            "baseline_pdf_page",
            "candidate_pdf_page",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseline": str(baseline_path),
        "candidate": str(candidate_path),
        "key_fields": list(KEY_FIELDS),
        "source_role_normalization": args.normalize_source_roles,
        "baseline_rows": len(baseline_rows),
        "candidate_rows": len(candidate_rows),
        "baseline_duplicate_keys": baseline_duplicates,
        "candidate_duplicate_keys": candidate_duplicates,
        "matched_keys": len(baseline_keys & candidate_keys),
        "baseline_only_rows": len(baseline_only),
        "candidate_only_rows": len(candidate_only),
        "matched_rows_with_official_value_differences": len(official_value_diff_keys),
        "matched_rows_with_identity_or_lineage_differences": len(metadata_diff_keys),
        "matched_rows_with_count_differences": len(count_diff_keys),
        "count_field_difference_counts_numeric_normalized": dict(sorted(count_field_differences.items())),
        "matched_rows_with_material_lane_p_draw_differences": len(p_draw_material_diff_keys),
        "material_lane_p_draw_field_difference_counts": dict(sorted(p_draw_material_field_differences.items())),
        "maximum_lane_p_draw_absolute_delta": str(p_draw_max_absolute_delta),
        "matched_rows_with_success_ratio_semantic_differences": len(success_ratio_semantic_diff_keys),
        "success_ratio_semantic_field_difference_counts": dict(sorted(success_ratio_semantic_field_differences.items())),
        "field_difference_counts": dict(sorted(Counter(row["field"] for row in differences).items())),
        "baseline_only_by_source_scope": dict(sorted(Counter(row.get("source_scope", "") for row in baseline_only).items())),
        "candidate_only_by_source_scope": dict(sorted(Counter(row.get("source_scope", "") for row in candidate_only).items())),
        "status": "PASS_EXACT_PARITY" if not baseline_only and not candidate_only and not differences else "DIFFERENCES_REQUIRE_SOURCE_REVIEW",
    }
    (output_dir / "canonical_candidate_comparison_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
