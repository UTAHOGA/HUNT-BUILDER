"""Audit current DATABASE universe counts and deletion candidates."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
ACTIVE_RECON = ROOT / "processed_data/audits/current_2026_hunt_code_permit_reconciliation.csv"
RETIRED = ROOT / "processed_data/audits/reviewed_retired_hunt_codes_2026.csv"

OUT_CSV = ROOT / "processed_data/audits/database_2026_universe_count_and_delete_review.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/database_2026_universe_count_and_delete_review_summary.json"
OUT_DOC = ROOT / "docs/database_2026_universe_count_and_delete_review.md"

REFERENCE_FILES = [
    ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.pre_2025_permit_backfill_backup.csv",
    ROOT / "processed_data/backups/DATABASE_before_allotment_reconciliation_20260604T052630Z.csv",
    ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/draw_database_alignment_changes_by_hunt_code_V2.csv",
    ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/draw_results_database_alignment_outputs_V3/draw_database_alignment_changes_by_hunt_code_V3.csv",
    ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/draw_results_database_alignment_outputs_V3/draw_results_long_cumulative_2025_draw_folder_DATABASE_ALIGNED_V3.csv",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def code_stats(path: Path) -> dict[str, object]:
    rows, _ = read_csv(path)
    codes = [clean(row.get("hunt_code")).upper() for row in rows if clean(row.get("hunt_code"))]
    counts = Counter(codes)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "rows": len(rows),
        "unique_hunt_codes": len(set(codes)),
        "duplicate_hunt_codes": sum(1 for count in counts.values() if count > 1),
    }


def main() -> int:
    db_rows, _ = read_csv(DATABASE)
    active_rows, _ = read_csv(ACTIVE_RECON)
    retired_rows, _ = read_csv(RETIRED)

    active_codes = {clean(row.get("hunt_code")).upper() for row in active_rows if clean(row.get("hunt_code"))}
    retired_by_code = {
        clean(row.get("hunt_code")).upper(): row for row in retired_rows if clean(row.get("hunt_code"))
    }

    out_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    delete_counts: Counter[str] = Counter()
    for row in db_rows:
        code = clean(row.get("hunt_code")).upper()
        if code in retired_by_code:
            status = "RETIRED_REFERENCE_ROW"
            delete_recommendation = "KEEP_REFERENCE_DO_NOT_DELETE"
            notes = (
                f"Retired for 2026; successor {clean(retired_by_code[code].get('successor_hunt_code'))}. "
                "Keep as historical/crosswalk row unless building a current-active-only export."
            )
        elif code in active_codes:
            status = "ACTIVE_RECONCILIATION_ROW"
            delete_recommendation = "KEEP"
            notes = "Included in active 2026 permit reconciliation union."
        else:
            status = "DATABASE_ONLY_NOT_ACTIVE_RECONCILIATION"
            delete_recommendation = "REVIEW_BEFORE_DELETE"
            notes = "Not present in active reconciliation and not listed as reviewed retired."
        status_counts[status] += 1
        delete_counts[delete_recommendation] += 1
        out_rows.append(
            {
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "sex_type": clean(row.get("sex_type")),
                "hunt_type": clean(row.get("hunt_type")),
                "universe_status": status,
                "delete_recommendation": delete_recommendation,
                "successor_hunt_code": clean(retired_by_code.get(code, {}).get("successor_hunt_code")),
                "permit_allotment_2026_res": clean(row.get("permit_allotment_2026_res")),
                "permit_allotment_2026_nr": clean(row.get("permit_allotment_2026_nr")),
                "permit_allotment_2026_total": clean(row.get("permit_allotment_2026_total")),
                "permit_allotment_2026_status": clean(row.get("permit_allotment_2026_status")),
                "notes": notes,
            }
        )

    fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "hunt_type",
        "universe_status",
        "delete_recommendation",
        "successor_hunt_code",
        "permit_allotment_2026_res",
        "permit_allotment_2026_nr",
        "permit_allotment_2026_total",
        "permit_allotment_2026_status",
        "notes",
    ]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(out_rows, key=lambda row: str(row["hunt_code"])))

    reference_stats = [code_stats(path) for path in REFERENCE_FILES if path.exists()]
    current_codes = [clean(row.get("hunt_code")).upper() for row in db_rows if clean(row.get("hunt_code"))]
    current_counts = Counter(current_codes)
    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_path": DATABASE.relative_to(ROOT).as_posix(),
        "current_database_rows": len(db_rows),
        "current_database_unique_hunt_codes": len(set(current_codes)),
        "current_database_duplicate_hunt_codes": sum(1 for count in current_counts.values() if count > 1),
        "active_reconciliation_rows": len(active_rows),
        "active_reconciliation_unique_hunt_codes": len(active_codes),
        "retired_reference_rows": len(retired_rows),
        "universe_status_counts": dict(sorted(status_counts.items())),
        "delete_recommendation_counts": dict(sorted(delete_counts.items())),
        "reference_file_counts": reference_stats,
        "interpretation": {
            "previous_active_database_baseline": "Recent DATABASE backups before current permit-row additions were 1449 rows / 1449 unique hunt codes.",
            "why_1600_appeared": "The 1600/1615 figures came from historical draw/alignment working files, not the active DATABASE.csv current universe.",
            "delete_guidance": "Do not bulk-delete from DATABASE.csv. Keep retired/reference rows for crosswalk/history; generate current-active-only exports from the active reconciliation universe.",
        },
        "outputs": {
            "audit_csv": OUT_CSV.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# DATABASE 2026 Universe Count And Delete Review",
        "",
        "## Short Answer",
        "",
        "Do not bulk-delete rows from `DATABASE.csv` right now. The current file has `1471` rows / `1471` unique hunt codes, but the active current reconciliation universe has `1470` rows because `PD1025` is now retained only as a retired reference row.",
        "",
        "The earlier `1600+` number did not come from the active `DATABASE.csv`; it came from historical draw/alignment working files with `1600` or `1615` unique source/alignment codes.",
        "",
        "## Current Counts",
        "",
        f"- Current DATABASE rows: `{summary['current_database_rows']}`",
        f"- Current DATABASE unique hunt codes: `{summary['current_database_unique_hunt_codes']}`",
        f"- Active reconciliation rows: `{summary['active_reconciliation_rows']}`",
        f"- Retired reference rows: `{summary['retired_reference_rows']}`",
        "",
        "## Row Classification",
        "",
    ]
    for key, value in summary["universe_status_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Delete Recommendation", ""])
    for key, value in summary["delete_recommendation_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Reference Counts", ""])
    for stat in reference_stats:
        lines.append(
            f"- `{stat['path']}`: `{stat['rows']}` rows / `{stat['unique_hunt_codes']}` unique hunt codes"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Keep `DATABASE.csv` as truth/reference with retired rows clearly marked. For website/current permit outputs, use the active reconciliation universe instead of physically deleting historical/crosswalk rows.",
            "",
            "If you later want a current-only file, generate a derived export that excludes `RETIRED_REFERENCE_ROW` rows rather than deleting them from the truth database.",
            "",
            "## Outputs",
            "",
            f"- `{OUT_CSV.relative_to(ROOT).as_posix()}`",
            f"- `{OUT_SUMMARY.relative_to(ROOT).as_posix()}`",
        ]
    )
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
