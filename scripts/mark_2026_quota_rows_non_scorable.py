from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
)
LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
AUDIT_DIR = ROOT / "audits" / "2026_canonical_reconciliation"
AUDIT_JSON = AUDIT_DIR / "mark_2026_permit_reference_rows_non_scorable_summary.json"
AUDIT_CSV = AUDIT_DIR / "mark_2026_permit_reference_rows_non_scorable_changes.csv"

DRAW_SUCCESS_FIELDS = [
    "points",
    "residency",
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "success_ratio",
    "p_draw",
    "p_draw_percent",
]


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    temp_path = path.with_name(f"{path.stem}.tmp{path.suffix}")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp_path, path)


def process_file(path: Path, label: str) -> dict[str, object]:
    fieldnames, rows = read_csv(path)
    changed: list[dict[str, str]] = []
    permit_reference_rows = 0
    contaminated_permit_reference_rows = 0

    for row_number, row in enumerate(rows, start=2):
        if clean(row.get("actual_draw_year") or row.get("year") or row.get("source_year")) != "2026":
            continue
        if clean(row.get("record_type") or row.get("row_type")) not in {
            "hunt_planner_permit_reference",
            "hunt_planner_permit_quota",
        }:
            continue

        permit_reference_rows += 1
        populated_success_fields = [field for field in DRAW_SUCCESS_FIELDS if clean(row.get(field))]
        if populated_success_fields:
            contaminated_permit_reference_rows += 1
            for field in populated_success_fields:
                old = row.get(field, "")
                row[field] = ""
                changed.append(
                    {
                        "file": label,
                        "row_number": str(row_number),
                        "hunt_code": clean(row.get("hunt_code")),
                        "field": field,
                        "old_value": old,
                        "new_value": "",
                        "reason": "permit-reference row cannot carry draw-success/applicant/probability data",
                    }
                )

        for field, value in (
            ("record_type", "hunt_planner_permit_reference"),
            ("page_kind", "PERMIT_REFERENCE_ROW"),
            ("source_namespace", "2026_HUNT_PLANNER_PERMIT_REFERENCE"),
            ("algorithm_status", "NON_SCORABLE_PERMIT_REFERENCE"),
            ("qa_status", "permit_number_only_not_draw_result"),
            ("notes", "2026 Hunt Planner antlerless/female-equivalent permit-number reference row; not a draw-result point row."),
        ):
            if field not in fieldnames:
                continue
            old = row.get(field, "")
            if clean(old) == value:
                continue
            row[field] = value
            changed.append(
                {
                    "file": label,
                    "row_number": str(row_number),
                    "hunt_code": clean(row.get("hunt_code")),
                        "field": field,
                        "old_value": old,
                        "new_value": value,
                        "reason": "make permit-reference rows explicitly non-scorable for engine/feed routing",
                    }
                )

    if changed:
        write_csv(path, fieldnames, rows)

    return {
        "path": str(path),
        "permit_reference_rows": permit_reference_rows,
        "contaminated_permit_reference_rows_before_cleanup": contaminated_permit_reference_rows,
        "changes": changed,
    }


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        process_file(CANONICAL, "canonical_2026"),
        process_file(LONG, "draw_results_long_2026_slice"),
    ]
    all_changes = [change for result in results for change in result["changes"]]

    with AUDIT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["file", "row_number", "hunt_code", "field", "old_value", "new_value", "reason"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(all_changes)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": (
            "Permit-reference rows are not draw-result rows. They retain permit-number columns but are "
            "explicitly marked non-scorable and any draw-success fields are blanked if present."
        ),
        "draw_success_fields_checked": DRAW_SUCCESS_FIELDS,
        "targets": [
            {key: value for key, value in result.items() if key != "changes"} | {"change_count": len(result["changes"])}
            for result in results
        ],
    }
    AUDIT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
