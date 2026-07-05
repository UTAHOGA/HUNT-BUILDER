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
AUDIT_DIR = REPO / "audits" / f"dedicated_hunter_weapon_hunt_type_normalization_{TIMESTAMP}"

CANONICAL_DIR = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
LONG_PATH = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE_PATH = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"

DH_LABELS = {
    "PREFERENCE_DEDICATED_HUNTER_DEER",
    "DEDICATED_HUNTER_DEER",
    "YOUTH_DEDICATED_HUNTER_DEER",
    "PREFERENCE_YOUTH_DEDICATED_HUNTER_DEER",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv_atomic(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    tmp = path.with_suffix(path.suffix + f".tmp_dh_normalize_{TIMESTAMP}")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def backup_file(path: Path) -> Path:
    backup = path.with_name(path.stem + f".backup_dh_weapon_hunt_type_{TIMESTAMP}" + path.suffix)
    shutil.copy2(path, backup)
    return backup


def is_dedicated_hunter_row(row: dict[str, str]) -> bool:
    labels = {clean(row.get(key)).upper() for key in ("draw_system_type", "draw_design", "hunt_draw_class", "hunt_class", "draw_class_type")}
    if labels & DH_LABELS:
        return True
    code = clean(row.get("hunt_code")).upper()
    text = " ".join(clean(row.get(key)).lower() for key in ("hunt_name", "hunt_type", "hunt_class", "weapon", "draw_pool"))
    return code.startswith(("DB17", "DB18")) and "dedicated hunter" in text


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    before = {
        "weapon": row.get("weapon", ""),
        "hunt_type": row.get("hunt_type", ""),
        "hunt_class": row.get("hunt_class", ""),
    }
    if "weapon" in row:
        row["weapon"] = "Any Legal Weapon"
    if "hunt_type" in row:
        row["hunt_type"] = "General Season"
    if "hunt_class" in row:
        row["hunt_class"] = "Dedicated Hunter"
    after = {
        "weapon": row.get("weapon", ""),
        "hunt_type": row.get("hunt_type", ""),
        "hunt_class": row.get("hunt_class", ""),
    }
    row["_dh_normalization_changed"] = "true" if before != after else "false"
    row["_dh_before"] = json.dumps(before, sort_keys=True)
    row["_dh_after"] = json.dumps(after, sort_keys=True)
    return row


def normalize_small_csv(path: Path, source_group: str) -> dict[str, object]:
    fieldnames, rows = read_csv(path)
    if not fieldnames:
        return {"file": str(path.relative_to(REPO)), "source_group": source_group, "rows": 0, "dh_rows": 0, "changed_rows": 0}

    audit_rows: list[dict[str, str]] = []
    value_counts_before: Counter[tuple[str, str, str]] = Counter()
    value_counts_after: Counter[tuple[str, str, str]] = Counter()
    dh_rows = 0
    changed_rows = 0
    for idx, row in enumerate(rows, start=2):
        if not is_dedicated_hunter_row(row):
            continue
        dh_rows += 1
        before_key = (clean(row.get("weapon")), clean(row.get("hunt_type")), clean(row.get("hunt_class")))
        value_counts_before[before_key] += 1
        row = normalize_row(row)
        rows[idx - 2] = {k: v for k, v in row.items() if not k.startswith("_dh_")}
        after_key = (clean(row.get("weapon")), clean(row.get("hunt_type")), clean(row.get("hunt_class")))
        value_counts_after[after_key] += 1
        if row["_dh_normalization_changed"] == "true":
            changed_rows += 1
            audit_rows.append(
                {
                    "file": str(path.relative_to(REPO)),
                    "source_group": source_group,
                    "row_number": str(idx),
                    "hunt_code": clean(row.get("hunt_code")),
                    "hunt_name": clean(row.get("hunt_name")),
                    "draw_system_type": clean(row.get("draw_system_type")),
                    "draw_design": clean(row.get("draw_design")),
                    "before": row["_dh_before"],
                    "after": row["_dh_after"],
                }
            )

    backup = ""
    if changed_rows:
        backup = str(backup_file(path).relative_to(REPO))
        write_csv_atomic(path, fieldnames, rows)

    write_audit_rows(audit_rows, AUDIT_DIR / f"{path.stem}_changed_rows.csv")
    write_value_counts(value_counts_before, AUDIT_DIR / f"{path.stem}_before_value_counts.csv", path, source_group)
    write_value_counts(value_counts_after, AUDIT_DIR / f"{path.stem}_after_value_counts.csv", path, source_group)
    return {
        "file": str(path.relative_to(REPO)),
        "source_group": source_group,
        "rows": len(rows),
        "dh_rows": dh_rows,
        "changed_rows": changed_rows,
        "backup": backup,
    }


def normalize_large_csv(path: Path, source_group: str) -> dict[str, object]:
    backup = backup_file(path)
    tmp = path.with_suffix(path.suffix + f".tmp_dh_normalize_{TIMESTAMP}")
    audit_rows: list[dict[str, str]] = []
    value_counts_before: Counter[tuple[str, str, str]] = Counter()
    value_counts_after: Counter[tuple[str, str, str]] = Counter()
    rows_total = 0
    dh_rows = 0
    changed_rows = 0

    with path.open("r", encoding="utf-8-sig", newline="") as src, tmp.open("w", encoding="utf-8", newline="") as dst:
        reader = csv.DictReader(src)
        fieldnames = list(reader.fieldnames or [])
        writer = csv.DictWriter(dst, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row_number, row in enumerate(reader, start=2):
            rows_total += 1
            if is_dedicated_hunter_row(row):
                dh_rows += 1
                value_counts_before[(clean(row.get("weapon")), clean(row.get("hunt_type")), clean(row.get("hunt_class")))] += 1
                row = normalize_row(row)
                value_counts_after[(clean(row.get("weapon")), clean(row.get("hunt_type")), clean(row.get("hunt_class")))] += 1
                if row["_dh_normalization_changed"] == "true":
                    changed_rows += 1
                    if len(audit_rows) < 5000:
                        audit_rows.append(
                            {
                                "file": str(path.relative_to(REPO)),
                                "source_group": source_group,
                                "row_number": str(row_number),
                                "hunt_code": clean(row.get("hunt_code")),
                                "hunt_name": clean(row.get("hunt_name")),
                                "actual_draw_year": clean(row.get("actual_draw_year")),
                                "draw_system_type": clean(row.get("draw_system_type")),
                                "draw_design": clean(row.get("draw_design")),
                                "before": row["_dh_before"],
                                "after": row["_dh_after"],
                            }
                        )
                row = {k: v for k, v in row.items() if not k.startswith("_dh_")}
            writer.writerow(row)

    if changed_rows:
        tmp.replace(path)
    else:
        tmp.unlink(missing_ok=True)

    write_audit_rows(audit_rows, AUDIT_DIR / f"{path.stem}_changed_rows_sample.csv")
    write_value_counts(value_counts_before, AUDIT_DIR / f"{path.stem}_before_value_counts.csv", path, source_group)
    write_value_counts(value_counts_after, AUDIT_DIR / f"{path.stem}_after_value_counts.csv", path, source_group)
    return {
        "file": str(path.relative_to(REPO)),
        "source_group": source_group,
        "rows": rows_total,
        "dh_rows": dh_rows,
        "changed_rows": changed_rows,
        "backup": str(backup.relative_to(REPO)),
    }


def write_audit_rows(rows: list[dict[str, str]], path: Path) -> None:
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


def write_value_counts(counter: Counter[tuple[str, str, str]], path: Path, source_path: Path, source_group: str) -> None:
    rows = [
        {
            "file": str(source_path.relative_to(REPO)),
            "source_group": source_group,
            "weapon": key[0],
            "hunt_type": key[1],
            "hunt_class": key[2],
            "rows": str(count),
        }
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]
    write_audit_rows(rows, path)


def main() -> int:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    for path in sorted(CANONICAL_DIR.glob("draw_results_*_canonical_yearly_draw_results.csv")):
        summaries.append(normalize_small_csv(path, "canonical_yearly"))
    summaries.append(normalize_large_csv(LONG_PATH, "draw_results_long"))
    summaries.append(normalize_small_csv(DATABASE_PATH, "database"))

    write_audit_rows([{k: str(v) for k, v in row.items()} for row in summaries], AUDIT_DIR / "normalization_file_summary.csv")
    summary = {
        "audit_dir": str(AUDIT_DIR.relative_to(REPO)),
        "files_processed": len(summaries),
        "total_dh_rows": sum(int(row["dh_rows"]) for row in summaries),
        "total_changed_rows": sum(int(row["changed_rows"]) for row in summaries),
        "canonical_files_processed": sum(1 for row in summaries if row["source_group"] == "canonical_yearly"),
        "draw_results_long_processed": True,
        "database_processed": True,
        "normalization": {
            "weapon": "Any Legal Weapon",
            "hunt_type": "General Season",
            "hunt_class": "Dedicated Hunter",
        },
    }
    (AUDIT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (AUDIT_DIR / "DEDICATED_HUNTER_WEAPON_HUNT_TYPE_NORMALIZATION_REPORT.md").write_text(
        "# Dedicated Hunter Weapon / Hunt Type Normalization\n\n"
        "- Scope: Dedicated Hunter deer rows only.\n"
        "- Source-backed normalization requested by Tyler.\n"
        "- `weapon` normalized to `Any Legal Weapon`.\n"
        "- `hunt_type` normalized to `General Season`.\n"
        "- `hunt_class` normalized to `Dedicated Hunter`.\n"
        "- `draw_system_type` and `draw_design` remain engine-family labels.\n"
        f"- Files processed: `{summary['files_processed']}`.\n"
        f"- Total D.H. rows: `{summary['total_dh_rows']}`.\n"
        f"- Changed rows: `{summary['total_changed_rows']}`.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
