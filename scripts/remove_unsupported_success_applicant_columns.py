from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "audits" / "2026_canonical_reconciliation"
AUDIT_JSON = AUDIT_DIR / "remove_unsupported_success_applicant_columns_summary.json"
AUDIT_CSV = AUDIT_DIR / "remove_unsupported_success_applicant_columns_inventory.csv"

TARGETS = [
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv",
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv",
]

REMOVE_COLUMNS = ["successful_applicants", "unsuccessful_applicants"]


def clean(value: object) -> str:
    return "" if value is None else str(value)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    inventory: list[dict[str, object]] = []
    summary: dict[str, object] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": (
            "Removed successful_applicants and unsuccessful_applicants because the raw Utah draw "
            "artifacts expose applicant counts, permit counts, and success ratio, but not distinct "
            "successful/unsuccessful applicant source columns. Do not derive or fabricate these "
            "fields until a true raw source field is identified."
        ),
        "removed_columns": REMOVE_COLUMNS,
        "targets": [],
    }

    for path in TARGETS:
        fieldnames, rows = read_csv(path)
        present = [column for column in REMOVE_COLUMNS if column in fieldnames]
        before_columns = len(fieldnames)
        before_blank_counts = {
            column: sum(1 for row in rows if clean(row.get(column)).strip() == "") for column in present
        }
        new_fieldnames = [column for column in fieldnames if column not in REMOVE_COLUMNS]

        if present:
            write_csv(path, new_fieldnames, rows)

        inventory.append(
            {
                "path": str(path),
                "rows": len(rows),
                "columns_before": before_columns,
                "columns_after": len(new_fieldnames),
                "removed_columns_present": "|".join(present),
                "successful_applicants_blank_count_before": before_blank_counts.get("successful_applicants", ""),
                "unsuccessful_applicants_blank_count_before": before_blank_counts.get("unsuccessful_applicants", ""),
            }
        )
        summary["targets"].append(inventory[-1])

    with AUDIT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(inventory[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(inventory)

    AUDIT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
