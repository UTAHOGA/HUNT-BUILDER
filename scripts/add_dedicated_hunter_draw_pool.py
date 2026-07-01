from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve()
while REPO.name != "HUNT-BUILDER" and REPO.parent != REPO:
    REPO = REPO.parent

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
AUDIT_DIR = REPO / "audits" / f"dedicated_hunter_draw_pool_alignment_{TIMESTAMP}"

CANONICAL_DIR = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
LONG_PATH = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE_PATH = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"

DH_LABELS = {
    "PREFERENCE_DEDICATED_HUNTER_DEER",
    "DEDICATED_HUNTER_DEER",
    "PREFERENCE_YOUTH_DEDICATED_HUNTER_DEER",
    "YOUTH_DEDICATED_HUNTER_DEER",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def backup_file(path: Path) -> Path:
    backup = path.with_name(path.stem + f".backup_dh_draw_pool_{TIMESTAMP}" + path.suffix)
    shutil.copy2(path, backup)
    return backup


def is_dedicated_hunter_row(row: dict[str, str]) -> bool:
    labels = {clean(row.get(key)).upper() for key in ("draw_system_type", "draw_design", "hunt_draw_class", "hunt_class", "draw_class_type")}
    if labels & DH_LABELS:
        return True
    code = clean(row.get("hunt_code")).upper()
    text = " ".join(clean(row.get(key)).lower() for key in ("hunt_name", "hunt_type", "hunt_class", "weapon", "source_file", "source_scope"))
    return code.startswith(("DB17", "DB18")) and "dedicated hunter" in text


def is_source_backed_youth_dedicated_hunter(row: dict[str, str]) -> bool:
    if not is_dedicated_hunter_row(row):
        return False
    source_text = " ".join(
        clean(value).lower()
        for key, value in row.items()
        if key
        in {
            "source_file",
            "draw_source_file",
            "source_path",
            "source_pdf",
            "source_scope",
            "source_namespace",
            "draw_source_namespace",
            "source_dataset",
            "page_kind",
            "notes",
            "qa_notes",
        }
    )
    return "youth" in source_text


def desired_draw_pool(row: dict[str, str]) -> str:
    if not is_dedicated_hunter_row(row):
        return clean(row.get("draw_pool"))
    if is_source_backed_youth_dedicated_hunter(row):
        return "youth_dedicated_hunter"
    return "dedicated_hunter"


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    tmp = path.with_suffix(path.suffix + f".tmp_dh_draw_pool_{TIMESTAMP}")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def write_audit(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["no_rows"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def process_small_csv(path: Path, source_group: str) -> dict[str, object]:
    fieldnames, rows = read_csv(path)
    if "draw_pool" not in fieldnames:
        insert_after = "draw_system_type" if "draw_system_type" in fieldnames else fieldnames[-1]
        index = fieldnames.index(insert_after) + 1
        fieldnames.insert(index, "draw_pool")

    changed: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    for row_number, row in enumerate(rows, start=2):
        before = clean(row.get("draw_pool"))
        after = desired_draw_pool(row)
        if after:
            counts[after] += 1
        if before != after:
            row["draw_pool"] = after
            changed.append(
                {
                    "file": str(path.relative_to(REPO)),
                    "source_group": source_group,
                    "row_number": str(row_number),
                    "hunt_code": clean(row.get("hunt_code")),
                    "hunt_name": clean(row.get("hunt_name")),
                    "draw_system_type": clean(row.get("draw_system_type")),
                    "draw_design": clean(row.get("draw_design")),
                    "before_draw_pool": before,
                    "after_draw_pool": after,
                }
            )

    backup = ""
    if changed:
        backup = str(backup_file(path).relative_to(REPO))
        write_rows(path, fieldnames, rows)

    write_audit(AUDIT_DIR / f"{path.stem}_draw_pool_changes.csv", changed)
    return {
        "file": str(path.relative_to(REPO)),
        "source_group": source_group,
        "rows": len(rows),
        "changed_rows": len(changed),
        "dedicated_hunter_rows": counts["dedicated_hunter"],
        "youth_dedicated_hunter_rows": counts["youth_dedicated_hunter"],
        "backup": backup,
    }


def process_large_csv(path: Path, source_group: str) -> dict[str, object]:
    backup = backup_file(path)
    tmp = path.with_suffix(path.suffix + f".tmp_dh_draw_pool_{TIMESTAMP}")
    changed: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    rows_total = 0
    changed_rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as src, tmp.open("w", encoding="utf-8", newline="") as dst:
        reader = csv.DictReader(src)
        fieldnames = list(reader.fieldnames or [])
        if "draw_pool" not in fieldnames:
            insert_after = "draw_system_type" if "draw_system_type" in fieldnames else fieldnames[-1]
            index = fieldnames.index(insert_after) + 1
            fieldnames.insert(index, "draw_pool")
        writer = csv.DictWriter(dst, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row_number, row in enumerate(reader, start=2):
            rows_total += 1
            before = clean(row.get("draw_pool"))
            after = desired_draw_pool(row)
            if after:
                counts[after] += 1
            if before != after:
                changed_rows += 1
                row["draw_pool"] = after
                if len(changed) < 5000:
                    changed.append(
                        {
                            "file": str(path.relative_to(REPO)),
                            "source_group": source_group,
                            "row_number": str(row_number),
                            "hunt_code": clean(row.get("hunt_code")),
                            "hunt_name": clean(row.get("hunt_name")),
                            "actual_draw_year": clean(row.get("actual_draw_year")),
                            "draw_system_type": clean(row.get("draw_system_type")),
                            "draw_design": clean(row.get("draw_design")),
                            "before_draw_pool": before,
                            "after_draw_pool": after,
                        }
                    )
            writer.writerow(row)
    tmp.replace(path)
    write_audit(AUDIT_DIR / f"{path.stem}_draw_pool_changes_sample.csv", changed)
    return {
        "file": str(path.relative_to(REPO)),
        "source_group": source_group,
        "rows": rows_total,
        "changed_rows": changed_rows,
        "dedicated_hunter_rows": counts["dedicated_hunter"],
        "youth_dedicated_hunter_rows": counts["youth_dedicated_hunter"],
        "backup": str(backup.relative_to(REPO)),
    }


def main() -> int:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    for path in sorted(CANONICAL_DIR.glob("draw_results_*_canonical_yearly_draw_results.csv")):
        summaries.append(process_small_csv(path, "canonical_yearly"))
    summaries.append(process_large_csv(LONG_PATH, "draw_results_long"))
    summaries.append(process_small_csv(DATABASE_PATH, "database"))

    write_audit(AUDIT_DIR / "draw_pool_alignment_file_summary.csv", [{k: str(v) for k, v in row.items()} for row in summaries])
    summary = {
        "audit_dir": str(AUDIT_DIR.relative_to(REPO)),
        "files_processed": len(summaries),
        "total_changed_rows": sum(int(row["changed_rows"]) for row in summaries),
        "total_dedicated_hunter_rows": sum(int(row["dedicated_hunter_rows"]) for row in summaries),
        "total_youth_dedicated_hunter_rows": sum(int(row["youth_dedicated_hunter_rows"]) for row in summaries),
        "draw_pool_column_added_where_missing": True,
        "youth_rule": "source-backed youth marker in D.H. source metadata",
    }
    (AUDIT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (AUDIT_DIR / "DEDICATED_HUNTER_DRAW_POOL_ALIGNMENT_REPORT.md").write_text(
        "# Dedicated Hunter Draw Pool Alignment\n\n"
        "- Added `draw_pool` where missing.\n"
        "- D.H. rows with source-backed youth markers use `youth_dedicated_hunter`.\n"
        "- Other D.H. rows use `dedicated_hunter`.\n"
        "- Non-D.H. rows remain blank unless they already had a value.\n"
        f"- Total changed rows: `{summary['total_changed_rows']}`.\n"
        f"- Youth D.H. rows: `{summary['total_youth_dedicated_hunter_rows']}`.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
