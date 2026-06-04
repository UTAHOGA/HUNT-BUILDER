from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPLIT_DIR = ROOT / "processed_data/audits/current_2026_permit_unresolved_split"
SOURCE = SPLIT_DIR / "remaining_unresolved_after_hanumber_hunttable_database_rule.csv"
CROSSWALK_REVIEW = SPLIT_DIR / "current_hunt_code_crosswalk_review_preview.csv"
RESOLVED = SPLIT_DIR / "resolved_crosswalk_exact_history_matches.csv"
REMAINING = SPLIT_DIR / "remaining_unresolved_after_crosswalk_exact_history_rule.csv"
SUMMARY = SPLIT_DIR / "current_2026_permit_crosswalk_exact_history_resolution_summary.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def resolved_row(row: dict[str, str]) -> dict[str, str]:
    out = dict(row)
    out["resolution_status"] = "RESOLVED_BY_EXACT_CODE_HISTORY_CROSSWALK"
    resolved_total = (
        row.get("recommended_total", "").strip()
        or row.get("database_total_reference", "").strip()
        or row.get("matching_total", "").strip()
        or ""
    )
    out["resolved_res"] = (
        row.get("recommended_res", "").strip()
        or row.get("database_res_reference", "").strip()
        or row.get("matching_res", "").strip()
        or ""
    )
    out["resolved_nr"] = (
        row.get("recommended_nr", "").strip()
        or row.get("database_nr_reference", "").strip()
        or row.get("matching_nr", "").strip()
        or ""
    )
    out["resolved_total"] = resolved_total
    out["resolved_matching_sources"] = "CURRENT_HISTORICAL_EXACT_CODE_CROSSWALK"
    out["resolved_matching_source_count"] = "1"
    out["resolved_source_rule"] = (
        "Exact-code historical continuity was confirmed; this row remains sourced through historical crosswalk evidence "
        "and is moved out of unresolved current-permit review."
    )
    out["remaining_review_required"] = "false"
    return out


def remaining_row(row: dict[str, str]) -> dict[str, str]:
    out = dict(row)
    out["remaining_review_required"] = "true"
    if not out.get("remaining_unresolved_bucket", ""):
        out["remaining_unresolved_bucket"] = "reviewed_crosswalk_exact_history"
    return out


def main() -> int:
    source_rows = read_csv(SOURCE)
    crosswalk_rows = read_csv(CROSSWALK_REVIEW)
    crosswalk_exact_codes = {
        row["hunt_code"]
        for row in crosswalk_rows
        if (
            row.get("crosswalk_status", "").strip() == "PROMOTED_EXACT_HISTORY"
            or row.get("crosswalk_bucket", "").strip() == "PROMOTED_EXACT_HISTORY"
        )
    }
    exact_history_rows = [row for row in source_rows if row["hunt_code"] in crosswalk_exact_codes]
    remaining_rows = [remaining_row(row) for row in source_rows if row["hunt_code"] not in crosswalk_exact_codes]
    resolved_rows = [resolved_row(row) for row in exact_history_rows]

    if len(exact_history_rows) != 15:
        raise RuntimeError(f"Expected 15 exact-history match rows, found {len(exact_history_rows)}")
    if len(source_rows) != 354:
        raise RuntimeError(f"Expected 354 source rows, found {len(source_rows)}")
    if len(resolved_rows) + len(remaining_rows) != len(source_rows):
        raise RuntimeError("Resolved + remaining row counts do not match source row count")

    write_csv(RESOLVED, resolved_rows, list(resolved_rows[0].keys()) if resolved_rows else list(source_rows[0].keys()))
    write_csv(REMAINING, remaining_rows, list(remaining_rows[0].keys()) if remaining_rows else list(source_rows[0].keys()))

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_remaining_after_hanumber": SOURCE.relative_to(ROOT).as_posix(),
        "row_counts": {
            "source_rows_after_hanumber": len(source_rows),
            "resolved_crosswalk_exact_history_rows": len(resolved_rows),
            "remaining_after_crosswalk_exact_history_rule": len(remaining_rows),
        },
        "resolved_prefix_counts": dict(
            sorted(Counter((row["hunt_code"][:2] for row in resolved_rows)).items())
        ),
        "resolved_bucket_counts": dict(Counter((row.get("remaining_unresolved_bucket") or "unassigned") for row in resolved_rows)),
        "remaining_bucket_counts": dict(Counter((row.get("remaining_unresolved_bucket") or "unassigned") for row in remaining_rows)),
        "outputs": {
            "resolved_csv": RESOLVED.relative_to(ROOT).as_posix(),
            "remaining_unresolved_csv": REMAINING.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY.relative_to(ROOT).as_posix(),
        },
        "notes": [
            "No source values were edited. This operation only moves exact-history crosswalk rows out of unresolved current-permit repair scope.",
            "Resolved entries remain fully auditable with all original source columns preserved plus resolution provenance.",
        ],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
