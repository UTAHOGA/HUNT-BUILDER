"""Reconcile 2026 Hunt Planner quota authority with UtahDraws result evidence.

The DWR Hunt Planner matrix is the authoritative current published quota source.
UtahDraws draw-result values remain immutable outcome evidence.  This audit keeps
both values and never writes DATABASE.csv, canonical draw truth, engine inputs, or
runtime artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "_staging"
MATRIX_DEFAULT = STAGING / "huntplanner_full_matrix_20260826_204000"
CROSSWALK_DEFAULT = (
    STAGING
    / "huntplanner_popup_deep_20260826_205700"
    / "draw_results_crosswalk"
    / "huntplanner_to_utahdraws_draw_results_2026_crosswalk.csv"
)
REVIEWED_DEFAULT = (
    ROOT
    / "pipeline"
    / "RAW"
    / "hunt_unit_database"
    / "2026"
    / "csv"
    / "2026 Permits"
    / "2026 reviewed permit truth master.csv"
)
EXPO_DEFAULT = (
    ROOT
    / "data_truth"
    / "permit_overlay_truth"
    / "normalized"
    / "expo_permit_allocations_2026_official_board_packet.csv"
)
OUT_DEFAULT = CROSSWALK_DEFAULT.parent / "huntplanner_authoritative_quota_reconciliation"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def code(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean(value).upper())


def integer(value: object) -> int | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def integer_text(value: object) -> str:
    parsed = integer(value)
    return "" if parsed is None else str(parsed)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def comparison(left: tuple[int | None, int | None, int | None], right: tuple[int | None, int | None, int | None]) -> str:
    left_res, left_nr, left_total = left
    right_res, right_nr, right_total = right
    if right_total is None and right_res is None and right_nr is None:
        return "NO_UTAHDRAWS_DRAW_RESULT_QUOTA"
    if left == right:
        return "MATCH_ALL_COMPARABLE"
    if left_total is not None and right_total is not None and left_total == right_total:
        if right_res is None and right_nr is None:
            return "TOTAL_MATCH_UTAHDRAWS_SPLIT_NOT_PUBLISHED"
        return "TOTAL_MATCH_SPLIT_DIFFERS"
    if left_res == right_res and left_nr == right_nr and left_total != right_total:
        return "RES_NR_MATCH_TOTAL_CONCEPT_DIFFERS"
    return "QUOTA_DIFFERENCE"


def dwr_split_shape(values: tuple[int | None, int | None, int | None]) -> str:
    resident, nonresident, total = values
    if total is None:
        return "DWR_NO_NUMERIC_QUOTA"
    if resident is None and nonresident is None:
        return "DWR_TOTAL_ONLY"
    resident = resident or 0
    nonresident = nonresident or 0
    if resident == 0 and nonresident == 0:
        return "DWR_TOTAL_ONLY"
    if resident + nonresident == total:
        return "DWR_FULL_RES_NR_SPLIT"
    return "DWR_SPLIT_TOTAL_INCONSISTENT"


PUBLIC_DRAW_EXCLUSIONS = {
    "EXPECTED_CWMU_QUOTA_SCOPE_DIFFERENCE",
    "EXPECTED_SPORTSMAN_RANDOM_ONLY_SCOPE_DIFFERENCE",
}

# User-confirmed DWR Hunt Planner typo overrides.  Each override must be backed
# by an exact matching official DWR draw-odds result; the raw Planner value is
# still retained in the audit output for provenance.
USER_CONFIRMED_DWR_PLANNER_TYPO_OVERRIDES = {
    "PD1056": (36, 4, 40),
}


def reconcile_with_dwr_draw_odds(
    crosswalk: dict[str, str],
    dwr_values: tuple[int | None, int | None, int | None],
    draw_values: tuple[int | None, int | None, int | None],
) -> tuple[tuple[int | None, int | None, int | None], str]:
    """Use DWR draw-odds evidence only to repair a self-inconsistent DWR row.

    The source is eligible only when the row is a matched standard public draw
    and the draw-odds result directly confirms the published DWR split or total.
    It never supplies a quota for CWMU, Sportsman, private, allocation, or
    unmatched rows.
    """
    override = USER_CONFIRMED_DWR_PLANNER_TYPO_OVERRIDES.get(code(crosswalk.get("hunt_code")))
    if override and draw_values == override:
        return override, "USER_CONFIRMED_DWR_PLANNER_TYPO_RECONCILED_BY_DWR_DRAW_ODDS"
    if (
        clean(crosswalk.get("mapping_status")) != "EXACT_CODE_MATCH"
        or clean(crosswalk.get("discrepancy_category")) in PUBLIC_DRAW_EXCLUSIONS
        or dwr_split_shape(dwr_values) != "DWR_SPLIT_TOTAL_INCONSISTENT"
    ):
        return dwr_values, "NOT_APPLICABLE"
    dwr_res, dwr_nr, dwr_total = dwr_values
    draw_res, draw_nr, draw_total = draw_values
    if None in draw_values or draw_res + draw_nr != draw_total:
        return dwr_values, "DWR_DRAW_ODDS_NO_COMPLETE_OFFICIAL_SPLIT"
    if (
        dwr_total == 0
        and dwr_res == draw_res
        and dwr_nr == draw_nr
        and dwr_res + dwr_nr == draw_total
    ):
        return (
            dwr_res,
            dwr_nr,
            draw_total,
        ), "DWR_DRAW_ODDS_CONFIRMS_DWR_SPLIT_AND_RECONCILES_ZERO_TOTAL"
    if (
        dwr_total is not None
        and dwr_res == draw_res
        and dwr_nr == 0
        and draw_nr == dwr_total - dwr_res
        and draw_total == dwr_total
    ):
        return (
            dwr_res,
            draw_nr,
            dwr_total,
        ), "DWR_DRAW_ODDS_RECONCILES_MISSING_NONRESIDENT_SPLIT"
    return dwr_values, "DWR_DRAW_ODDS_CONFLICT_REMAINS"


def load_matrix(matrix_dir: Path) -> dict[str, dict[str, object]]:
    manifest_path = matrix_dir / "dwr_huntboundary_full_matrix_manifest.csv"
    manifest = {row["file"]: row for row in read_csv(manifest_path) if clean(row.get("file"))}
    collected: dict[str, list[dict[str, object]]] = defaultdict(list)
    for raw_path in sorted(matrix_dir.glob("dwr_huntboundary_*.json")):
        if raw_path.name == "dwr_huntboundary_hasetup.json":
            continue
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            continue
        manifest_row = manifest.get(raw_path.name, {})
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            hunt_code = code(raw.get("HUNT_NBR"))
            if not hunt_code:
                continue
            collected[hunt_code].append(
                {
                    "res": integer(raw.get("QUOTA_RES")),
                    "nr": integer(raw.get("QUOTA_NRES")),
                    "total": integer(raw.get("QUOTA")),
                    "source_file": raw_path.relative_to(ROOT).as_posix(),
                    "source_url": clean(manifest_row.get("url")),
                    "source_species": clean(manifest_row.get("species")),
                    "source_gender": clean(manifest_row.get("gender")),
                }
            )
    resolved: dict[str, dict[str, object]] = {}
    for hunt_code, rows in collected.items():
        triples = {(row["res"], row["nr"], row["total"]) for row in rows}
        first = rows[0]
        resolved[hunt_code] = {
            **first,
            "row_count": len(rows),
            "value_status": "ONE_DWR_MATRIX_VALUE" if len(triples) == 1 else "MULTIPLE_DWR_MATRIX_VALUES",
            "source_files": " | ".join(sorted({str(row["source_file"]) for row in rows})),
            "source_urls": " | ".join(sorted({str(row["source_url"]) for row in rows if row["source_url"]})),
        }
    return resolved


def load_reviewed(path: Path) -> dict[str, dict[str, object]]:
    collected: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(path):
        hunt_code = code(row.get("hunt_code"))
        if hunt_code:
            collected[hunt_code].append(row)
    output: dict[str, dict[str, object]] = {}
    for hunt_code, rows in collected.items():
        triples = {
            (integer(row.get("permits_2026_res")), integer(row.get("permits_2026_nr")), integer(row.get("permits_2026_total")))
            for row in rows
        }
        first = rows[0]
        output[hunt_code] = {
            "res": integer(first.get("permits_2026_res")),
            "nr": integer(first.get("permits_2026_nr")),
            "total": integer(first.get("permits_2026_total")),
            "status": clean(first.get("permit_count_status")),
            "source_files": " | ".join(sorted({clean(row.get("source_file")) for row in rows if clean(row.get("source_file"))})),
            "row_count": len(rows),
            "value_status": "ONE_REVIEWED_VALUE" if len(triples) == 1 else "MULTIPLE_REVIEWED_VALUES",
        }
    return output


def load_expo(path: Path) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for row in read_csv(path):
        hunt_code = code(row.get("hunt_code"))
        if not hunt_code:
            continue
        values = (
            integer(row.get("resident_permits")),
            integer(row.get("nonresident_permits")),
            integer(row.get("total_permits")),
        )
        if None in values:
            raise RuntimeError(f"Expo row lacks a complete official split: {hunt_code}")
        if values[0] + values[1] != values[2]:
            raise RuntimeError(f"Expo row has inconsistent split: {hunt_code}")
        output[hunt_code] = {
            "res": values[0],
            "nr": values[1],
            "total": values[2],
            "source_url": clean(row.get("source_url")),
            "source_page": clean(row.get("source_page")),
            "source_lines": clean(row.get("source_lines")),
        }
    return output


def reconcile_with_official_expo(
    crosswalk: dict[str, str],
    dwr_values: tuple[int | None, int | None, int | None],
    draw_values: tuple[int | None, int | None, int | None],
    expo: dict[str, object],
) -> str:
    """Confirm that the DWR/public-draw delta is the official Expo allocation.

    2026 Expo permits are a separately approved allocation deducted from public
    drawing permits.  This check never adds Expo permits to draw odds or makes
    an unsupported residency allocation: all three values must match exactly.
    """
    if not expo:
        return "NO_OFFICIAL_EXPO_ALLOCATION_FOR_CODE"
    if clean(crosswalk.get("mapping_status")) != "EXACT_CODE_MATCH":
        return "EXPO_NOT_APPLICABLE_NONEXACT_CODE"
    if None in dwr_values or None in draw_values:
        return "EXPO_NOT_COMPARABLE_INCOMPLETE_QUOTA"
    dwr_res, dwr_nr, dwr_total = dwr_values
    draw_res, draw_nr, draw_total = draw_values
    expo_values = (expo["res"], expo["nr"], expo["total"])
    if dwr_res + dwr_nr != dwr_total or draw_res + draw_nr != draw_total:
        return "EXPO_NOT_COMPARABLE_INCONSISTENT_SPLIT"
    if (dwr_res - draw_res, dwr_nr - draw_nr, dwr_total - draw_total) == expo_values:
        return "DWR_PLANNER_TO_PUBLIC_DRAW_RECONCILED_BY_OFFICIAL_EXPO_ALLOCATION"
    return "OFFICIAL_EXPO_ALLOCATION_DOES_NOT_EXPLAIN_DWR_DRAW_DIFFERENCE"


def public_draw_odds_status(draw_values: tuple[int | None, int | None, int | None]) -> str:
    """Classify the result row that is authoritative for public-draw odds."""
    resident, nonresident, total = draw_values
    if resident is None and nonresident is None and total is None:
        return "NO_OFFICIAL_ACTUAL_DRAW_RESULT"
    if None not in draw_values and resident + nonresident == total:
        return "OFFICIAL_ACTUAL_DRAW_RESULT_FULL_RES_NR_SPLIT"
    return "OFFICIAL_ACTUAL_DRAW_RESULT_PARTIAL_OR_TOTAL_ONLY"


def disposition(
    crosswalk: dict[str, str], quota_comparison: str, draw_odds_reconciliation: str, expo_reconciliation: str
) -> str:
    mapping_status = clean(crosswalk.get("mapping_status"))
    category = clean(crosswalk.get("discrepancy_category"))
    if mapping_status == "UTAHDRAWS_ONLY":
        return "NO_CURRENT_DWR_HUNT_PLANNER_QUOTA_AUTHORITY"
    if mapping_status == "PLANNER_ONLY":
        return "DWR_CURRENT_QUOTA_RETAINED_NO_UTAHDRAWS_DRAW_RESULT_ROW"
    if category in {
        "EXPECTED_CWMU_QUOTA_SCOPE_DIFFERENCE",
        "EXPECTED_SPORTSMAN_RANDOM_ONLY_SCOPE_DIFFERENCE",
    }:
        return "DWR_QUOTA_RETAINED_NONCOMPARABLE_PROGRAM_SCOPE"
    if expo_reconciliation == "DWR_PLANNER_TO_PUBLIC_DRAW_RECONCILED_BY_OFFICIAL_EXPO_ALLOCATION":
        return "DWR_PLANNER_TO_PUBLIC_DRAW_RECONCILED_BY_OFFICIAL_EXPO_ALLOCATION"
    if draw_odds_reconciliation in {
        "DWR_DRAW_ODDS_CONFIRMS_DWR_SPLIT_AND_RECONCILES_ZERO_TOTAL",
        "DWR_DRAW_ODDS_RECONCILES_MISSING_NONRESIDENT_SPLIT",
        "USER_CONFIRMED_DWR_PLANNER_TYPO_RECONCILED_BY_DWR_DRAW_ODDS",
    }:
        return "DWR_QUOTA_RECONCILED_BY_OFFICIAL_DWR_DRAW_ODDS"
    if quota_comparison == "MATCH_ALL_COMPARABLE":
        return "DWR_QUOTA_AND_UTAHDRAWS_DRAW_RESULT_QUOTA_AGREE"
    if quota_comparison == "TOTAL_MATCH_UTAHDRAWS_SPLIT_NOT_PUBLISHED":
        return "DWR_TOTAL_AND_UTAHDRAWS_DRAW_RESULT_TOTAL_AGREE_SPLIT_UNPUBLISHED"
    return "DWR_QUOTA_RETAINED_UTAHDRAWS_DRAW_RESULT_DIVERGENCE_PRESERVED"


def forecast_split_status(
    shape: str,
    mapping_status: str,
    discrepancy_category: str,
    draw_odds_reconciliation: str,
    expo_reconciliation: str,
) -> str:
    if mapping_status != "EXACT_CODE_MATCH" or discrepancy_category in {
        "EXPECTED_CWMU_QUOTA_SCOPE_DIFFERENCE",
        "EXPECTED_SPORTSMAN_RANDOM_ONLY_SCOPE_DIFFERENCE",
    }:
        return "NOT_A_MATCHED_PUBLIC_DRAW_QUOTA_ROW"
    if draw_odds_reconciliation in {
        "DWR_DRAW_ODDS_CONFIRMS_DWR_SPLIT_AND_RECONCILES_ZERO_TOTAL",
        "DWR_DRAW_ODDS_RECONCILES_MISSING_NONRESIDENT_SPLIT",
        "USER_CONFIRMED_DWR_PLANNER_TYPO_RECONCILED_BY_DWR_DRAW_ODDS",
    }:
        return "OFFICIAL_DWR_SPLIT_RECONCILED_BY_DWR_DRAW_ODDS"
    if expo_reconciliation == "DWR_PLANNER_TO_PUBLIC_DRAW_RECONCILED_BY_OFFICIAL_EXPO_ALLOCATION":
        return "OFFICIAL_PUBLIC_DRAW_SPLIT_RECONCILED_BY_EXPO_ALLOCATION"
    if shape == "DWR_FULL_RES_NR_SPLIT":
        return "OFFICIAL_DWR_RES_NR_SPLIT_AVAILABLE"
    if shape == "DWR_TOTAL_ONLY":
        return "BLOCK_TOTAL_ONLY_NO_UNSUPPORTED_SPLIT_DERIVATION"
    if shape == "DWR_SPLIT_TOTAL_INCONSISTENT":
        return "BLOCK_DWR_SPLIT_TOTAL_INCONSISTENCY"
    return "BLOCK_NO_DWR_NUMERIC_QUOTA"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crosswalk-csv", type=Path, default=CROSSWALK_DEFAULT)
    parser.add_argument("--matrix-dir", type=Path, default=MATRIX_DEFAULT)
    parser.add_argument("--reviewed-csv", type=Path, default=REVIEWED_DEFAULT)
    parser.add_argument("--expo-csv", type=Path, default=EXPO_DEFAULT)
    parser.add_argument("--output-dir", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()

    crosswalk_path = args.crosswalk_csv if args.crosswalk_csv.is_absolute() else ROOT / args.crosswalk_csv
    matrix_dir = args.matrix_dir if args.matrix_dir.is_absolute() else ROOT / args.matrix_dir
    reviewed_path = args.reviewed_csv if args.reviewed_csv.is_absolute() else ROOT / args.reviewed_csv
    expo_path = args.expo_csv if args.expo_csv.is_absolute() else ROOT / args.expo_csv
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir

    matrix_by_code = load_matrix(matrix_dir)
    reviewed_by_code = load_reviewed(reviewed_path)
    expo_by_code = load_expo(expo_path)
    output_rows: list[dict[str, object]] = []

    for row in read_csv(crosswalk_path):
        hunt_code = code(row.get("hunt_code"))
        matrix = matrix_by_code.get(hunt_code, {})
        reviewed = reviewed_by_code.get(hunt_code, {})
        expo = expo_by_code.get(hunt_code, {})
        matrix_values = (matrix.get("res"), matrix.get("nr"), matrix.get("total"))
        popup_values = (
            integer(row.get("planner_res_quota")),
            integer(row.get("planner_nr_quota")),
            integer(row.get("planner_total_quota")),
        )
        dwr_values = matrix_values if matrix else popup_values
        draw_values = (
            integer(row.get("utahdraws_res_quota")),
            integer(row.get("utahdraws_nr_quota")),
            integer(row.get("utahdraws_total_quota")),
        )
        odds_status = public_draw_odds_status(draw_values)
        reconciled_values, draw_odds_reconciliation = reconcile_with_dwr_draw_odds(row, dwr_values, draw_values)
        expo_reconciliation = reconcile_with_official_expo(row, dwr_values, draw_values, expo)
        reviewed_values = (reviewed.get("res"), reviewed.get("nr"), reviewed.get("total"))
        dwr_to_popup = comparison(dwr_values, popup_values) if matrix else "NO_DWR_MATRIX_ROW"
        dwr_to_draw = comparison(dwr_values, draw_values)
        dwr_to_reviewed = comparison(dwr_values, reviewed_values) if reviewed else "NO_REVIEWED_DWR_SUPPORT_ROW"
        shape = dwr_split_shape(dwr_values)
        output_rows.append(
            {
                **row,
                "quota_authority": "DWR_HUNT_PLANNER_HUNTTABLE" if matrix else "DWR_HUNT_PLANNER_HANUMBER_FALLBACK",
                "authoritative_dwr_res_quota": integer_text(dwr_values[0]),
                "authoritative_dwr_nr_quota": integer_text(dwr_values[1]),
                "authoritative_dwr_total_quota": integer_text(dwr_values[2]),
                "authoritative_dwr_split_shape": shape,
                "reconciled_dwr_res_quota": integer_text(reconciled_values[0]),
                "reconciled_dwr_nr_quota": integer_text(reconciled_values[1]),
                "reconciled_dwr_total_quota": integer_text(reconciled_values[2]),
                "dwr_draw_odds_reconciliation": draw_odds_reconciliation,
                "public_draw_odds_res_quota": integer_text(draw_values[0]),
                "public_draw_odds_nr_quota": integer_text(draw_values[1]),
                "public_draw_odds_total_quota": integer_text(draw_values[2]),
                "public_draw_odds_authority": "UTAHDRAWS_OFFICIAL_ACTUAL_DRAW_RESULT",
                "public_draw_odds_status": odds_status,
                "official_expo_res_quota": integer_text(expo.get("res")),
                "official_expo_nr_quota": integer_text(expo.get("nr")),
                "official_expo_total_quota": integer_text(expo.get("total")),
                "official_expo_source_url": clean(expo.get("source_url")),
                "official_expo_source_page": clean(expo.get("source_page")),
                "official_expo_source_lines": clean(expo.get("source_lines")),
                "expo_reconciliation": expo_reconciliation,
                "authoritative_dwr_matrix_value_status": clean(matrix.get("value_status")),
                "authoritative_dwr_matrix_source_files": clean(matrix.get("source_files")),
                "authoritative_dwr_matrix_source_urls": clean(matrix.get("source_urls")),
                "dwr_matrix_to_popup_comparison": dwr_to_popup,
                "utahdraws_to_authoritative_dwr_comparison": dwr_to_draw,
                "reviewed_dwr_support_res_quota": integer_text(reviewed_values[0]),
                "reviewed_dwr_support_nr_quota": integer_text(reviewed_values[1]),
                "reviewed_dwr_support_total_quota": integer_text(reviewed_values[2]),
                "reviewed_dwr_support_status": clean(reviewed.get("status")),
                "reviewed_dwr_support_source_files": clean(reviewed.get("source_files")),
                "authoritative_dwr_to_reviewed_support_comparison": dwr_to_reviewed,
                "reconciliation_disposition": disposition(row, dwr_to_draw, draw_odds_reconciliation, expo_reconciliation),
                "forecast_residency_split_status": forecast_split_status(
                    shape,
                    clean(row.get("mapping_status")),
                    clean(row.get("discrepancy_category")),
                    draw_odds_reconciliation,
                    expo_reconciliation,
                ),
                "guardrail": "DWR Hunt Planner is the current published quota authority. UtahDraws result values are retained as draw-result evidence and never overwrite DWR quota fields.",
            }
        )

    fields = [
        *list(output_rows[0].keys()),
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "huntplanner_authoritative_quota_reconciliation_2026.csv"
    json_path = output_dir / "huntplanner_authoritative_quota_reconciliation_2026_summary.json"
    md_path = output_dir / "huntplanner_authoritative_quota_reconciliation_2026_summary.md"
    write_csv(csv_path, output_rows, fields)

    disposition_counts = Counter(clean(row["reconciliation_disposition"]) for row in output_rows)
    shape_counts = Counter(clean(row["authoritative_dwr_split_shape"]) for row in output_rows)
    result_comparison_counts = Counter(clean(row["utahdraws_to_authoritative_dwr_comparison"]) for row in output_rows)
    forecast_counts = Counter(clean(row["forecast_residency_split_status"]) for row in output_rows)
    draw_odds_reconciliation_counts = Counter(clean(row["dwr_draw_odds_reconciliation"]) for row in output_rows)
    expo_reconciliation_counts = Counter(clean(row["expo_reconciliation"]) for row in output_rows)
    public_draw_odds_status_counts = Counter(clean(row["public_draw_odds_status"]) for row in output_rows)
    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "scope": "2026 DWR Hunt Planner current published quota authority versus retained 2026 UtahDraws draw-result evidence.",
        "input_hashes": {
            "crosswalk_csv_sha256": sha256(crosswalk_path),
            "reviewed_dwr_support_csv_sha256": sha256(reviewed_path),
            "official_expo_allocation_csv_sha256": sha256(expo_path),
        },
        "inputs": {
            "crosswalk_csv": crosswalk_path.relative_to(ROOT).as_posix(),
            "dwr_hunt_planner_matrix_directory": matrix_dir.relative_to(ROOT).as_posix(),
            "reviewed_dwr_support_csv": reviewed_path.relative_to(ROOT).as_posix(),
            "official_expo_allocation_csv": expo_path.relative_to(ROOT).as_posix(),
        },
        "row_count": len(output_rows),
        "reconciliation_disposition_counts": dict(sorted(disposition_counts.items())),
        "authoritative_dwr_split_shape_counts": dict(sorted(shape_counts.items())),
        "utahdraws_to_authoritative_dwr_comparison_counts": dict(sorted(result_comparison_counts.items())),
        "forecast_residency_split_status_counts": dict(sorted(forecast_counts.items())),
        "dwr_draw_odds_reconciliation_counts": dict(sorted(draw_odds_reconciliation_counts.items())),
        "expo_reconciliation_counts": dict(sorted(expo_reconciliation_counts.items())),
        "public_draw_odds_status_counts": dict(sorted(public_draw_odds_status_counts.items())),
        "guardrails": [
            "DWR Hunt Planner is the authoritative current published permit-quota source.",
            "UtahDraws rows remain retained draw-result evidence; divergent values are not overwritten or promoted as current quota truth.",
            "DWR total-only and internally inconsistent residency splits are blocked from unsupported split derivation.",
            "A Planner-to-public-draw split difference is reconciled only when it exactly equals the official Expo allocation for the same hunt code.",
            "Public-draw odds and backtests use official actual draw-result values, never Hunt Planner quota values or special-permit overlays.",
            "This audit does not modify DATABASE.csv, canonical draw-result truth, prediction inputs, runtime artifacts, R2, or the live site.",
        ],
        "outputs": {
            "csv": csv_path.relative_to(ROOT).as_posix(),
            "summary_json": json_path.relative_to(ROOT).as_posix(),
            "summary_md": md_path.relative_to(ROOT).as_posix(),
        },
    }
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# 2026 Hunt Planner Authoritative Quota Reconciliation",
        "",
        "## Decision",
        "",
        "The DWR Hunt Planner (`HuntTableData`) is the authoritative current published permit-quota source. UtahDraws quota fields remain retained draw-result evidence. A UtahDraws value never replaces a DWR quota value in this audit.",
        "",
        "## Counts",
        "",
        f"- Crosswalk rows: `{len(output_rows)}`",
        "",
        "### Reconciliation disposition",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(disposition_counts.items()))
    lines.extend(["", "### DWR published quota shape", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(shape_counts.items()))
    lines.extend(["", "### UtahDraws comparison to DWR authority", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(result_comparison_counts.items()))
    lines.extend(["", "### Forecast residency-split eligibility", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(forecast_counts.items()))
    lines.extend(["", "### DWR draw-odds reconciliation of self-inconsistent Planner rows", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(draw_odds_reconciliation_counts.items()))
    lines.extend(["", "### Official Expo reconciliation", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(expo_reconciliation_counts.items()))
    lines.extend(["", "### Public-draw odds authority", ""])
    lines.append("Public-draw odds and all historical scoring use the retained UtahDraws/DWR actual draw-result fields, not Hunt Planner quotas.")
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(public_draw_odds_status_counts.items()))
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- DWR total-only values stay total-only; no residency split is invented.",
            "- A self-inconsistent DWR Planner row is eligible for repair only when the official DWR draw-odds record directly confirms its published split or total; all other conflicts remain blocked.",
            "- Draw-result evidence remains available for outcome/history work under the existing official-truth contract, but does not redefine current published quota values.",
            "- Expo reconciliation requires exact resident, nonresident, and total arithmetic against the official Board allocation; conservation permits are a separate overlay and are not used for this test.",
            "- Public-draw odds, application behavior, and prediction backtests consume actual draw-result rows. Planner quotas are only current-allocation context for a forecast and must never replace actual outcomes.",
            "- This is audit-only and does not mutate `DATABASE.csv`, canonical truth, prediction inputs, runtime artifacts, R2, or the live site.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
