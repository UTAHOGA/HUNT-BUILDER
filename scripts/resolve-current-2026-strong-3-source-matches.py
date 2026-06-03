from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPLIT_DIR = ROOT / "processed_data/audits/current_2026_permit_unresolved_split"
STRONG = SPLIT_DIR / "strong_3_source_current_matches.csv"
TRUE_CONFLICTS = SPLIT_DIR / "true_source_conflicts.csv"
DATABASE_ONLY = SPLIT_DIR / "database_only_external_missing.csv"
NO_VALUE = SPLIT_DIR / "true_no_permit_value.csv"

RESOLVED = SPLIT_DIR / "resolved_3_source_current_matches.csv"
REMAINING = SPLIT_DIR / "remaining_unresolved_after_3_source_rule.csv"
SUMMARY = SPLIT_DIR / "current_2026_permit_strong_match_resolution_summary.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def resolved_row(row: dict[str, str]) -> dict[str, str]:
    out = dict(row)
    out["resolution_status"] = "RESOLVED_BY_3_SOURCE_CURRENT_MATCH_RULE"
    out["resolved_res"] = row.get("matching_res", "")
    out["resolved_nr"] = row.get("matching_nr", "")
    out["resolved_total"] = row.get("matching_total", "")
    out["resolved_source_rule"] = (
        "At least three non-database current sources match exactly; conflicting UtahDraws/BIBLE value remains audit evidence "
        "but does not keep the row in unresolved current-permit review."
    )
    out["remaining_review_required"] = "false"
    return out


def remaining_row(row: dict[str, str], bucket_name: str) -> dict[str, str]:
    out = dict(row)
    out["remaining_unresolved_bucket"] = bucket_name
    out["remaining_review_required"] = "true"
    return out


def main() -> int:
    strong_rows = read_csv(STRONG)
    true_conflicts = read_csv(TRUE_CONFLICTS)
    database_only = read_csv(DATABASE_ONLY)
    no_value = read_csv(NO_VALUE)

    resolved_rows = [resolved_row(row) for row in strong_rows]
    remaining_rows = (
        [remaining_row(row, "true_source_conflicts") for row in true_conflicts]
        + [remaining_row(row, "database_only_external_missing") for row in database_only]
        + [remaining_row(row, "true_no_permit_value") for row in no_value]
    )
    if len(resolved_rows) != 158:
        raise RuntimeError(f"Expected 158 strong rows, found {len(resolved_rows)}")
    if len(remaining_rows) != 438:
        raise RuntimeError(f"Expected 438 remaining unresolved rows, found {len(remaining_rows)}")
    if len(resolved_rows) + len(remaining_rows) != 596:
        raise RuntimeError("Resolved plus remaining rows does not equal original unresolved count 596")

    resolved_fields = list(resolved_rows[0].keys()) if resolved_rows else []
    remaining_fields = list(remaining_rows[0].keys()) if remaining_rows else []
    write_csv(RESOLVED, resolved_rows, resolved_fields)
    write_csv(REMAINING, remaining_rows, remaining_fields)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_files": {
            "strong_3_source_current_matches": STRONG.relative_to(ROOT).as_posix(),
            "true_source_conflicts": TRUE_CONFLICTS.relative_to(ROOT).as_posix(),
            "database_only_external_missing": DATABASE_ONLY.relative_to(ROOT).as_posix(),
            "true_no_permit_value": NO_VALUE.relative_to(ROOT).as_posix(),
        },
        "row_counts": {
            "resolved_3_source_current_matches": len(resolved_rows),
            "remaining_unresolved_after_3_source_rule": len(remaining_rows),
            "original_unresolved_total": len(resolved_rows) + len(remaining_rows),
        },
        "resolved_prefix_counts": dict(sorted(Counter(row["hunt_code"][:2] for row in resolved_rows).items())),
        "remaining_bucket_counts": dict(Counter(row["remaining_unresolved_bucket"] for row in remaining_rows)),
        "remaining_prefix_counts": dict(sorted(Counter(row["hunt_code"][:2] for row in remaining_rows).items())),
        "outputs": {
            "resolved_csv": RESOLVED.relative_to(ROOT).as_posix(),
            "remaining_unresolved_csv": REMAINING.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY.relative_to(ROOT).as_posix(),
        },
        "notes": [
            "No source data or DATABASE.csv values are modified.",
            "The 158 strong three-source matches are moved out of unresolved current-permit review.",
            "Conflicting UtahDraws/BIBLE values remain visible in the resolved CSV for audit traceability.",
        ],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
