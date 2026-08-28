"""Crosswalk current DWR Hunt Planner hunts to current UtahDraws result rows.

This is a source-to-source audit.  It does not modify DATABASE.csv, canonical
truth, prediction outputs, or any hosted runtime artifact.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POPUP_DEFAULT = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "_staging" / "huntplanner_popup_deep_20260826_205700" / "dwr_huntplanner_hanumber_2026.csv"
DRAWS_DEFAULT = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "json" / "draw_results" / "utahdraws_2026_20260826" / "utahdraws_2026" / "csv" / "2026_allowed_draw_odds_all_flat_rows.csv"
OUT_DEFAULT = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "_staging" / "huntplanner_popup_deep_20260826_205700" / "draw_results_crosswalk"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def code(value: object) -> str:
    return "".join(char for char in clean(value).upper() if char.isalnum())


def number(value: object) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def join_distinct(values: list[object]) -> str:
    return " | ".join(sorted({clean(value) for value in values if clean(value)}))


def classify_planner_only(row: dict[str, str]) -> tuple[str, str, str]:
    """Classify absence from the collected public UtahDraws draw-result packages.

    These are audit lanes, not a claim that the hunt is invalid.  A lane named
    EXPECTED_* is intentionally excluded from the public-draw result comparison.
    """
    species = clean(row.get("dwr_species")).lower()
    hunt_type = clean(row.get("dwr_hunt_type")).lower()
    designation = clean(row.get("dwr_draw_designation")).upper()
    total = number(row.get("permits_2026_total"))
    text = f"{species} {hunt_type}".strip()
    if "private land" in text or "cwmu" in text:
        return (
            "EXPECTED_PRIVATE_LANDS_OR_CWMU_NOT_PUBLIC_DRAWS",
            "INFO",
            "Private-land and CWMU programs are not a public UtahDraws draw-result parity target.",
        )
    if any(token in text for token in ("conservation", "tribal", "depredation", "coyote reimbursement")):
        return (
            "EXPECTED_NONPUBLIC_OR_ALLOCATION_PROGRAM",
            "INFO",
            "Conservation, tribal, depredation, and reimbursement programs are not public draw-result rows.",
        )
    if species in {
        "sandhill crane",
        "greater sage-grouse",
        "sharp-tailed grouse",
        "tundra swan",
        "waterfowl",
        "goose, dark",
        "goose, light",
        "goose, white-fronted",
    }:
        return (
            "OUT_OF_SCOPE_PACKAGE_NOT_COLLECTED_FROM_UTAHDRAWS",
            "INFO",
            "This audit's UtahDraws snapshot intentionally excludes wetland and non-turkey upland packages.",
        )
    if any(token in text for token in ("pursuit", "harvest objective", "general season", "extended archery", "spike bull", "fall management", "spring general")):
        return (
            "EXPECTED_AVAILABILITY_OR_NON_DRAW_PROGRAM",
            "INFO",
            "Availability, pursuit, and non-draw programs do not require a current public draw-result row.",
        )
    if designation == "P" and total == 0:
        return (
            "PUBLIC_DESIGNATION_ZERO_QUOTA_NO_RESULT_ROW",
            "REVIEW",
            "The Hunt Planner marks this public-designated hunt with zero current quota; retain for review, not probability modeling.",
        )
    return (
        "UNMATCHED_CURRENT_HUNT_REQUIRES_REVIEW",
        "REVIEW",
        "No exact code appears in the collected UtahDraws public draw-result packages and no expected-exclusion lane applies.",
    )


def classify_draw_only(record: dict[str, object]) -> tuple[str, str, str]:
    category = clean(record.get("category")).lower()
    total = record.get("total")
    if total == 0 and ("bonus point" in category or "preference point" in category):
        return (
            "EXPECTED_POINT_PURCHASE_NOT_HUNT_PLANNER_HUNT",
            "INFO",
            "A point-purchase row has no active Hunt Planner hunt code or public permit quota.",
        )
    if "cwmu" in category:
        return (
            "UTAHDRAWS_CWMU_CODE_NOT_IN_CURRENT_HUNT_PLANNER",
            "REVIEW",
            "A UtahDraws CWMU code is not in the current public Hunt Planner code universe.",
        )
    return (
        "UTAHDRAWS_ONLY_CODE_REQUIRES_REVIEW",
        "REVIEW",
        "A current UtahDraws code has no exact current Hunt Planner code match.",
    )


def classify_exact_match(
    planner: dict[str, str],
    summary: dict[str, object],
    comparisons: tuple[str, str, str],
) -> tuple[str, str, str]:
    """Separate known program-scope differences from public-draw discrepancies."""
    total_compare, res_compare, nr_compare = comparisons
    if "MISMATCH" not in comparisons:
        return "EXACT_CODE_MATCH", "INFO", "Both official sources expose this current hunt code and comparable quota fields match."
    hunt_type = clean(planner.get("dwr_hunt_type")).lower()
    categories = clean(summary.get("categories")).lower()
    if "cwmu" in hunt_type or "cwmu" in categories:
        return (
            "EXPECTED_CWMU_QUOTA_SCOPE_DIFFERENCE",
            "INFO",
            "CWMU quota surfaces are distinct from the public draw quota and must not be used as public-draw probability evidence.",
        )
    if "sportsman" in categories or hunt_type == "statewide":
        return (
            "EXPECTED_SPORTSMAN_RANDOM_ONLY_SCOPE_DIFFERENCE",
            "INFO",
            "Sportsman permits are a separate random-only program and are not comparable to a standard Hunt Planner permit total.",
        )
    return (
        "PUBLIC_DRAW_QUOTA_DIFFERENCE_REQUIRES_REVIEW",
        "REVIEW",
        "Exact current code exists in both official sources but one or more comparable public-draw quota fields differ.",
    )


def build_draw_records(rows: list[dict[str, str]]) -> dict[str, list[dict[str, object]]]:
    by_code_hunt_id: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        hunt_code = code(row.get("HuntCode"))
        hunt_id = clean(row.get("HuntID"))
        if not hunt_code or not hunt_id:
            continue
        key = (hunt_code, hunt_id)
        if key not in by_code_hunt_id:
            by_code_hunt_id[key] = {
                "hunt_code": hunt_code,
                "hunt_id": hunt_id,
                "hunt_name": clean(row.get("HuntName")),
                "species_subtype": clean(row.get("SpeciesSubtypeName")),
                "category": clean(row.get("HuntCategoryName")),
                "draw_package_id": clean(row.get("MasterHuntTypeID")),
                "res": number(row.get("ResidentQuotaQuantity")),
                "nr": number(row.get("NonResidentQuotaQuantity")),
                "total": number(row.get("QuotaQuantity")),
                "source_json_files": {clean(row.get("source_json_file"))},
            }
        else:
            by_code_hunt_id[key]["source_json_files"].add(clean(row.get("source_json_file")))
    by_code: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in by_code_hunt_id.values():
        record["source_json_files"] = sorted(file for file in record["source_json_files"] if file)
        by_code[record["hunt_code"]].append(record)
    return dict(by_code)


def quota_summary(records: list[dict[str, object]]) -> dict[str, object]:
    def summed(field: str) -> int | None:
        values = [record[field] for record in records]
        return None if any(value is None for value in values) else sum(int(value) for value in values)

    return {
        "hunt_ids": join_distinct([record["hunt_id"] for record in records]),
        "hunt_names": join_distinct([record["hunt_name"] for record in records]),
        "subtypes": join_distinct([record["species_subtype"] for record in records]),
        "categories": join_distinct([record["category"] for record in records]),
        "draw_package_ids": join_distinct([record["draw_package_id"] for record in records]),
        "source_json_files": join_distinct(file for record in records for file in record["source_json_files"]),
        "hunt_id_count": len(records),
        "res": summed("res"),
        "nr": summed("nr"),
        "total": summed("total"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--popup-csv", type=Path, default=POPUP_DEFAULT)
    parser.add_argument("--utahdraws-csv", type=Path, default=DRAWS_DEFAULT)
    parser.add_argument("--output-dir", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()

    popup_path = args.popup_csv if args.popup_csv.is_absolute() else ROOT / args.popup_csv
    draws_path = args.utahdraws_csv if args.utahdraws_csv.is_absolute() else ROOT / args.utahdraws_csv
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    planner_rows = read_csv(popup_path)
    draw_by_code = build_draw_records(read_csv(draws_path))
    planner_by_code = {code(row.get("hunt_code")): row for row in planner_rows if code(row.get("hunt_code"))}

    fields = [
        "hunt_code", "mapping_status", "discrepancy_category", "severity", "reason",
        "planner_species", "planner_hunt_type", "planner_draw_designation", "planner_hunt_name", "planner_weapon",
        "planner_res_quota", "planner_nr_quota", "planner_total_quota", "planner_source_url",
        "utahdraws_hunt_ids", "utahdraws_hunt_id_count", "utahdraws_hunt_names", "utahdraws_subtypes", "utahdraws_categories",
        "utahdraws_draw_package_ids", "utahdraws_res_quota", "utahdraws_nr_quota", "utahdraws_total_quota", "utahdraws_source_json_files",
        "total_quota_comparison", "resident_quota_comparison", "nonresident_quota_comparison",
    ]
    output_rows: list[dict[str, object]] = []
    exact_total_mismatches = 0
    exact_resident_mismatches = 0
    exact_nonresident_mismatches = 0

    for hunt_code in sorted(planner_by_code):
        planner = planner_by_code[hunt_code]
        base: dict[str, object] = {
            "hunt_code": hunt_code,
            "planner_species": clean(planner.get("dwr_species")),
            "planner_hunt_type": clean(planner.get("dwr_hunt_type")),
            "planner_draw_designation": clean(planner.get("dwr_draw_designation")),
            "planner_hunt_name": clean(planner.get("dwr_hunt_name")),
            "planner_weapon": clean(planner.get("dwr_weapon")),
            "planner_res_quota": clean(planner.get("permits_2026_res")),
            "planner_nr_quota": clean(planner.get("permits_2026_nr")),
            "planner_total_quota": clean(planner.get("permits_2026_total")),
            "planner_source_url": clean(planner.get("source_url")),
        }
        records = draw_by_code.get(hunt_code, [])
        if not records:
            category, severity, reason = classify_planner_only(planner)
            output_rows.append({
                **base,
                "mapping_status": "PLANNER_ONLY",
                "discrepancy_category": category,
                "severity": severity,
                "reason": reason,
                "total_quota_comparison": "NO_UTAHDRAWS_PUBLIC_DRAW_ROW",
                "resident_quota_comparison": "NO_UTAHDRAWS_PUBLIC_DRAW_ROW",
                "nonresident_quota_comparison": "NO_UTAHDRAWS_PUBLIC_DRAW_ROW",
            })
            continue

        summary = quota_summary(records)
        p_res = number(planner.get("permits_2026_res"))
        p_nr = number(planner.get("permits_2026_nr"))
        p_total = number(planner.get("permits_2026_total"))
        total_compare = "MATCH" if p_total == summary["total"] else "MISMATCH"
        res_compare = "NOT_COMPARABLE_UNPUBLISHED_SPLIT" if summary["res"] is None else ("MATCH" if p_res == summary["res"] else "MISMATCH")
        nr_compare = "NOT_COMPARABLE_UNPUBLISHED_SPLIT" if summary["nr"] is None else ("MATCH" if p_nr == summary["nr"] else "MISMATCH")
        if total_compare == "MISMATCH":
            exact_total_mismatches += 1
        if res_compare == "MISMATCH":
            exact_resident_mismatches += 1
        if nr_compare == "MISMATCH":
            exact_nonresident_mismatches += 1
        category, severity, reason = classify_exact_match(planner, summary, (total_compare, res_compare, nr_compare))
        output_rows.append({
            **base,
            "mapping_status": "EXACT_CODE_MATCH",
            "discrepancy_category": category,
            "severity": severity,
            "reason": reason,
            "utahdraws_hunt_ids": summary["hunt_ids"],
            "utahdraws_hunt_id_count": summary["hunt_id_count"],
            "utahdraws_hunt_names": summary["hunt_names"],
            "utahdraws_subtypes": summary["subtypes"],
            "utahdraws_categories": summary["categories"],
            "utahdraws_draw_package_ids": summary["draw_package_ids"],
            "utahdraws_res_quota": "" if summary["res"] is None else summary["res"],
            "utahdraws_nr_quota": "" if summary["nr"] is None else summary["nr"],
            "utahdraws_total_quota": "" if summary["total"] is None else summary["total"],
            "utahdraws_source_json_files": summary["source_json_files"],
            "total_quota_comparison": total_compare,
            "resident_quota_comparison": res_compare,
            "nonresident_quota_comparison": nr_compare,
        })

    for hunt_code in sorted(set(draw_by_code) - set(planner_by_code)):
        summary = quota_summary(draw_by_code[hunt_code])
        category, severity, reason = classify_draw_only({"category": summary["categories"], "total": summary["total"]})
        output_rows.append({
            "hunt_code": hunt_code,
            "mapping_status": "UTAHDRAWS_ONLY",
            "discrepancy_category": category,
            "severity": severity,
            "reason": reason,
            "utahdraws_hunt_ids": summary["hunt_ids"],
            "utahdraws_hunt_id_count": summary["hunt_id_count"],
            "utahdraws_hunt_names": summary["hunt_names"],
            "utahdraws_subtypes": summary["subtypes"],
            "utahdraws_categories": summary["categories"],
            "utahdraws_draw_package_ids": summary["draw_package_ids"],
            "utahdraws_res_quota": "" if summary["res"] is None else summary["res"],
            "utahdraws_nr_quota": "" if summary["nr"] is None else summary["nr"],
            "utahdraws_total_quota": "" if summary["total"] is None else summary["total"],
            "utahdraws_source_json_files": summary["source_json_files"],
            "total_quota_comparison": "NO_CURRENT_HUNT_PLANNER_ROW",
            "resident_quota_comparison": "NO_CURRENT_HUNT_PLANNER_ROW",
            "nonresident_quota_comparison": "NO_CURRENT_HUNT_PLANNER_ROW",
        })

    output_rows.sort(key=lambda row: (str(row["mapping_status"]), str(row["hunt_code"])))
    out_csv = output_dir / "huntplanner_to_utahdraws_draw_results_2026_crosswalk.csv"
    out_json = output_dir / "huntplanner_to_utahdraws_draw_results_2026_summary.json"
    out_md = output_dir / "huntplanner_to_utahdraws_draw_results_2026_summary.md"
    write_csv(out_csv, output_rows, fields)
    category_counts = Counter(clean(row.get("discrepancy_category")) for row in output_rows)
    status_counts = Counter(clean(row.get("mapping_status")) for row in output_rows)
    review_rows = [row for row in output_rows if row.get("severity") == "REVIEW"]
    summary: dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "Current 2026 official DWR Hunt Planner popup code universe versus collected current 2026 UtahDraws draw-result packages.",
        "popup_csv": str(popup_path.relative_to(ROOT)).replace("\\", "/"),
        "utahdraws_csv": str(draws_path.relative_to(ROOT)).replace("\\", "/"),
        "output_csv": str(out_csv.relative_to(ROOT)).replace("\\", "/"),
        "planner_hunt_codes": len(planner_by_code),
        "utahdraws_hunt_codes": len(draw_by_code),
        "mapping_status_counts": dict(sorted(status_counts.items())),
        "discrepancy_category_counts": dict(sorted(category_counts.items())),
        "review_rows": len(review_rows),
        "exact_code_total_quota_mismatches": exact_total_mismatches,
        "exact_code_resident_quota_mismatches": exact_resident_mismatches,
        "exact_code_nonresident_quota_mismatches": exact_nonresident_mismatches,
        "guardrails": [
            "No missing-code row is treated as a zero or as proof a hunt is invalid.",
            "Private lands, CWMU, conservation, tribal, availability, pursuit, and excluded species packages remain distinct from public draw-result rows.",
            "Quota disagreements are review evidence only; this audit does not update DATABASE.csv or engine inputs.",
        ],
    }
    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Hunt Planner to UtahDraws Draw Results Crosswalk — 2026",
        "",
        f"- Hunt Planner current codes: `{summary['planner_hunt_codes']}`",
        f"- UtahDraws current codes: `{summary['utahdraws_hunt_codes']}`",
        f"- Exact code matches: `{status_counts.get('EXACT_CODE_MATCH', 0)}`",
        f"- Hunt Planner-only codes: `{status_counts.get('PLANNER_ONLY', 0)}`",
        f"- UtahDraws-only codes: `{status_counts.get('UTAHDRAWS_ONLY', 0)}`",
        f"- Rows requiring review: `{summary['review_rows']}`",
        f"- Exact-code total-quota disagreements: `{exact_total_mismatches}`",
        f"- Exact-code resident-split disagreements: `{exact_resident_mismatches}`",
        f"- Exact-code nonresident-split disagreements: `{exact_nonresident_mismatches}`",
        "",
        "## Classification counts",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(category_counts.items()))
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {item}" for item in summary["guardrails"])
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"CROSSWALK={out_csv}")
    print(f"SUMMARY={out_json}")
    print(f"PLANNER_CODES={len(planner_by_code)}")
    print(f"UTAHDRAWS_CODES={len(draw_by_code)}")
    print(f"EXACT_MATCHES={status_counts.get('EXACT_CODE_MATCH', 0)}")
    print(f"REVIEW_ROWS={len(review_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
