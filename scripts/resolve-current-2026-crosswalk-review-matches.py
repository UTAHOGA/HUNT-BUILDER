from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPLIT_DIR = ROOT / "processed_data/audits/current_2026_permit_unresolved_split"
SOURCE = SPLIT_DIR / "remaining_unresolved_after_crosswalk_exact_history_rule.csv"
CROSSWALK_REVIEW = SPLIT_DIR / "current_hunt_code_crosswalk_review_preview.csv"
RESOLVED = SPLIT_DIR / "resolved_crosswalk_review_matches.csv"
REMAINING = SPLIT_DIR / "remaining_unresolved_after_crosswalk_review_rule.csv"
SUMMARY = SPLIT_DIR / "current_2026_permit_crosswalk_review_resolution_summary.json"


RESOLVABLE_STATUSES = {
    "PROMOTED_PARALLEL_PUBLIC_UNIT_REFERENCE": "RESOLVED_BY_PARALLEL_PUBLIC_UNIT_REFERENCE",
    "REVIEWED_CURRENT_REFERENCE": "RESOLVED_BY_REVIEWED_CURRENT_REFERENCE",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize(v: object) -> str:
    return str(v or "").strip()


def pick_total(row: dict[str, str]) -> str:
    return (
        normalize(row.get("matching_total"))
        or normalize(row.get("recommended_total"))
        or normalize(row.get("database_total_reference"))
        or ""
    )


def pick_res(row: dict[str, str]) -> str:
    return (
        normalize(row.get("matching_res"))
        or normalize(row.get("recommended_res"))
        or normalize(row.get("database_res_reference"))
        or ""
    )


def pick_nr(row: dict[str, str]) -> str:
    return (
        normalize(row.get("matching_nr"))
        or normalize(row.get("recommended_nr"))
        or normalize(row.get("database_nr_reference"))
        or ""
    )


def resolved_row(row: dict[str, str], status: str) -> dict[str, str]:
    out = dict(row)
    out["crosswalk_resolution_status"] = RESOLVABLE_STATUSES[status]
    out["resolved_status"] = RESOLVABLE_STATUSES[status]
    out["resolved_res"] = pick_res(row)
    out["resolved_nr"] = pick_nr(row)
    out["resolved_total"] = pick_total(row)
    out["resolved_matching_sources"] = "CURRENT_TO_HISTORICAL_CROSSWALK"
    out["resolved_matching_source_count"] = "1"
    out["resolved_source_rule"] = (
        "Crosswalk review status indicates deterministic migration path for this row; "
        "kept as resolved for permit repair queue with full source audit columns preserved."
    )
    out["crosswalk_status"] = status
    out["remaining_review_required"] = "false"
    return out


def remaining_row(row: dict[str, str]) -> dict[str, str]:
    out = dict(row)
    out["remaining_review_required"] = "true"
    return out


def main() -> int:
    source_rows = read_csv(SOURCE)
    crosswalk_rows = read_csv(CROSSWALK_REVIEW)
    status_lookup = {
        normalize(r.get("hunt_code")): normalize(r.get("crosswalk_status"))
        for r in crosswalk_rows
        if normalize(r.get("hunt_code"))
    }

    resolved_rows: list[dict[str, str]] = []
    remaining_rows: list[dict[str, str]] = []

    for row in source_rows:
        status = status_lookup.get(normalize(row.get("hunt_code")), "")
        if status in RESOLVABLE_STATUSES:
            resolved_rows.append(resolved_row(row, status))
        else:
            row2 = remaining_row(row)
            row2["crosswalk_status"] = status
            remaining_rows.append(row2)

    if len(source_rows) != 339:
        raise RuntimeError(f"Expected 339 source rows for this rule, found {len(source_rows)}")

    write_csv(REMAINING, remaining_rows, list(remaining_rows[0].keys()) if remaining_rows else list(source_rows[0].keys()))

    if resolved_rows:
        resolved_fields = list(resolved_rows[0].keys())
    else:
        resolved_fields = list(source_rows[0].keys()) + [
            "crosswalk_resolution_status",
            "resolved_status",
            "resolved_res",
            "resolved_nr",
            "resolved_total",
            "resolved_matching_sources",
            "resolved_matching_source_count",
            "resolved_source_rule",
        ]
    write_csv(RESOLVED, resolved_rows, resolved_fields)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_remaining_after_crosswalk_exact_history": SOURCE.relative_to(ROOT).as_posix(),
        "row_counts": {
            "source_rows": len(source_rows),
            "resolved_crosswalk_review_rows": len(resolved_rows),
            "remaining_after_crosswalk_review_rule": len(remaining_rows),
        },
        "resolved_status_counts": dict(
            Counter(
                row.get("resolved_status", "")
                for row in resolved_rows
            )
        ),
        "crosswalk_status_counts_remaining": dict(
            Counter(
                row.get("crosswalk_status") or "<missing>"
                for row in remaining_rows
            )
        ),
        "outputs": {
            "resolved_csv": RESOLVED.relative_to(ROOT).as_posix(),
            "remaining_unresolved_csv": REMAINING.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY.relative_to(ROOT).as_posix(),
        },
        "notes": [
            "No source values or DATABASE.csv values were modified.",
            "Rows with deterministic crosswalk review statuses were moved out of unresolved repair scope.",
            "Remaining rows retain complete source columns for manual review continuation.",
        ],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
