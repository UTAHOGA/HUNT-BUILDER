from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPLIT_DIR = ROOT / "processed_data/audits/current_2026_permit_unresolved_split"
SOURCE = SPLIT_DIR / "remaining_unresolved_after_3_source_rule.csv"
RESOLVED = SPLIT_DIR / "resolved_hanumber_hunttable_database_matches.csv"
REMAINING = SPLIT_DIR / "remaining_unresolved_after_hanumber_hunttable_database_rule.csv"
SUMMARY = SPLIT_DIR / "current_2026_permit_hanumber_hunttable_database_resolution_summary.json"


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


def values(row: dict[str, str], prefix: str) -> tuple[str, str, str]:
    if prefix == "database":
        return (
            (row.get("database_res_reference") or "").strip(),
            (row.get("database_nr_reference") or "").strip(),
            (row.get("database_total_reference") or "").strip(),
        )
    return (
        (row.get(f"{prefix}_res") or "").strip(),
        (row.get(f"{prefix}_nr") or "").strip(),
        (row.get(f"{prefix}_total") or "").strip(),
    )


def has_value(value: tuple[str, str, str]) -> bool:
    return any(part not in {"", "0"} for part in value)


def hanumber_hunttable_database_exact_match(row: dict[str, str]) -> bool:
    hanumber = values(row, "hanumber")
    hunttable = values(row, "hunttable")
    database = values(row, "database")
    return has_value(hanumber) and hanumber == hunttable and hanumber == database


def resolved_row(row: dict[str, str]) -> dict[str, str]:
    hanumber = values(row, "hanumber")
    out = dict(row)
    out["resolution_status"] = "RESOLVED_BY_HANUMBER_HUNTTABLE_DATABASE_EXACT_MATCH"
    out["resolved_res"] = hanumber[0]
    out["resolved_nr"] = hanumber[1]
    out["resolved_total"] = hanumber[2]
    out["resolved_matching_sources"] = "HANUMBER|HUNTTABLE|DATABASE"
    out["resolved_matching_source_count"] = "3"
    out["resolved_source_rule"] = (
        "HaNumber current DWR value, HuntTable current DWR value, and DATABASE reference match exactly; conflicting source "
        "remains audit evidence but row is moved out of unresolved current-permit review."
    )
    out["remaining_review_required"] = "false"
    return out


def remaining_row(row: dict[str, str]) -> dict[str, str]:
    out = dict(row)
    out["remaining_review_required"] = "true"
    return out


def main() -> int:
    rows = read_csv(SOURCE)
    resolved_rows = [resolved_row(row) for row in rows if hanumber_hunttable_database_exact_match(row)]
    remaining_rows = [remaining_row(row) for row in rows if not hanumber_hunttable_database_exact_match(row)]
    if len(rows) != 438:
        raise RuntimeError(f"Expected 438 source rows, found {len(rows)}")
    if len(resolved_rows) != 84:
        raise RuntimeError(f"Expected 84 HaNumber/HuntTable/DATABASE matches, found {len(resolved_rows)}")
    if len(remaining_rows) != 354:
        raise RuntimeError(f"Expected 354 remaining rows, found {len(remaining_rows)}")
    write_csv(RESOLVED, resolved_rows, list(resolved_rows[0].keys()))
    write_csv(REMAINING, remaining_rows, list(remaining_rows[0].keys()))
    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_remaining_csv": SOURCE.relative_to(ROOT).as_posix(),
        "row_counts": {
            "source_remaining_after_3_source_rule": len(rows),
            "resolved_hanumber_hunttable_database_matches": len(resolved_rows),
            "remaining_unresolved_after_hanumber_hunttable_database_rule": len(remaining_rows),
        },
        "resolved_bucket_counts": dict(Counter(row.get("remaining_unresolved_bucket") for row in resolved_rows)),
        "resolved_prefix_counts": dict(sorted(Counter(row["hunt_code"][:2] for row in resolved_rows).items())),
        "resolved_species_counts": dict(sorted(Counter(row.get("species") or "UNKNOWN" for row in resolved_rows).items())),
        "remaining_bucket_counts": dict(Counter(row.get("remaining_unresolved_bucket") for row in remaining_rows)),
        "remaining_prefix_counts": dict(sorted(Counter(row["hunt_code"][:2] for row in remaining_rows).items())),
        "outputs": {
            "resolved_csv": RESOLVED.relative_to(ROOT).as_posix(),
            "remaining_unresolved_csv": REMAINING.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY.relative_to(ROOT).as_posix(),
        },
        "notes": [
            "No source data or DATABASE.csv values are modified.",
            "Resolved rows require exact HaNumber, HuntTable, and DATABASE match with a nonblank permit value.",
            "Conflicting source values remain visible in the resolved CSV for audit traceability.",
        ],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
