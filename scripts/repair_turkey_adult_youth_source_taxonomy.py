from __future__ import annotations

import csv
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
AUDIT_DIR = REPO / "audits" / f"turkey_adult_youth_source_taxonomy_repair_{TIMESTAMP}"
CANONICAL_DIR = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
LONG_PATH = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"

ADULT_VALUES = {
    "hunt_class": "Adult",
    "hunt_draw_class": "BONUS_TURKEY",
    "draw_system_type": "BONUS_TURKEY",
    "draw_design": "BONUS_TURKEY",
    "draw_pool": "preference_point",
}
YOUTH_VALUES = {
    "hunt_class": "Youth",
    "hunt_draw_class": "YOUTH_TURKEY_SET_ASIDE",
    "draw_system_type": "YOUTH_TURKEY_SET_ASIDE",
    "draw_design": "YOUTH_TURKEY_SET_ASIDE",
    "draw_pool": "youth_turkey",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", clean(value).lower())


def is_turkey(row: dict[str, str]) -> bool:
    return norm(row.get("species")) == "turkey" or clean(row.get("hunt_code")).upper().startswith("TK")


def preserve_row(row: dict[str, str]) -> bool:
    text = " ".join(
        norm(row.get(key))
        for key in (
            "hunt_code",
            "hunt_name",
            "species",
            "sex_type",
            "hunt_type",
            "hunt_class",
            "hunt_draw_class",
            "draw_system_type",
            "draw_design",
            "draw_pool",
            "source_file",
        )
    )
    return any(
        token in text
        for token in (
            "cwmu",
            "sportsman",
            "conservation",
            "statewide permit",
            "fall management",
            "spring general season",
            "general season",
            "reference_only",
            "reference only",
        )
    )


def desired_values(row: dict[str, str]) -> dict[str, str] | None:
    if not is_turkey(row) or preserve_row(row):
        return None
    source = norm(row.get("source_file"))
    source_tokenized = source.replace("_", " ").replace("-", " ")
    if "youth turkey" in source_tokenized or "youth_turkey" in source:
        return YOUTH_VALUES
    if "turkey" in source_tokenized and any(
        token in source_tokenized
        for token in ("draw results", "bonus points", "draw odds", "drawoddsdata", "limited entry")
    ):
        return ADULT_VALUES
    return None


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    tmp = path.with_suffix(path.suffix + f".tmp_turkey_taxonomy_{TIMESTAMP}")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        fieldnames = fieldnames or ["no_rows"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def repair_file(path: Path, make_backup: bool) -> dict[str, object]:
    fieldnames, rows = read_rows(path)
    for col in ("hunt_class", "hunt_draw_class", "draw_system_type", "draw_design", "draw_pool"):
        if col not in fieldnames:
            fieldnames.append(col)

    changed_rows: list[dict[str, object]] = []
    final_counts: dict[tuple[str, str, str], int] = {}
    for idx, row in enumerate(rows, start=2):
        desired = desired_values(row)
        if desired is None:
            continue
        before = {key: clean(row.get(key)) for key in desired}
        if before == desired:
            pass
        else:
            for key, value in desired.items():
                row[key] = value
            changed_rows.append(
                {
                    "file": str(path.relative_to(REPO)),
                    "line_number": idx,
                    "hunt_code": clean(row.get("hunt_code")),
                    "source_file": clean(row.get("source_file")),
                    "before_hunt_class": before.get("hunt_class", ""),
                    "after_hunt_class": desired["hunt_class"],
                    "before_hunt_draw_class": before.get("hunt_draw_class", ""),
                    "after_hunt_draw_class": desired["hunt_draw_class"],
                    "before_draw_system_type": before.get("draw_system_type", ""),
                    "after_draw_system_type": desired["draw_system_type"],
                    "before_draw_pool": before.get("draw_pool", ""),
                    "after_draw_pool": desired["draw_pool"],
                }
            )

    for row in rows:
        if is_turkey(row):
            key = (clean(row.get("hunt_class")), clean(row.get("draw_system_type")), clean(row.get("draw_pool")))
            final_counts[key] = final_counts.get(key, 0) + 1

    if changed_rows:
        if make_backup:
            backup_dir = AUDIT_DIR / "canonical_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_dir / f"{path.stem}.backup_{TIMESTAMP}{path.suffix}")
        write_rows(path, fieldnames, rows)

    return {
        "file": str(path.relative_to(REPO)),
        "rows": len(rows),
        "changed_rows": len(changed_rows),
        "changed_detail": changed_rows,
        "final_counts": [
            {
                "file": str(path.relative_to(REPO)),
                "hunt_class": key[0],
                "draw_system_type": key[1],
                "draw_pool": key[2],
                "count": count,
            }
            for key, count in sorted(final_counts.items())
        ],
    }


def main() -> int:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(CANONICAL_DIR.glob("draw_results_*_canonical_yearly_draw_results.csv")) + [LONG_PATH]
    summaries: list[dict[str, object]] = []
    changed_detail: list[dict[str, object]] = []
    final_counts: list[dict[str, object]] = []
    for path in files:
        result = repair_file(path, make_backup=path != LONG_PATH)
        summaries.append({key: value for key, value in result.items() if key not in {"changed_detail", "final_counts"}})
        changed_detail.extend(result["changed_detail"])
        final_counts.extend(result["final_counts"])

    summary = {
        "turkey_adult_youth_source_taxonomy_repair_complete": True,
        "files_processed": len(files),
        "canonical_files_processed": len(files) - 1,
        "draw_results_long_processed": LONG_PATH.exists(),
        "rows_changed": len(changed_detail),
        "adult_draw_pool": "preference_point",
        "youth_draw_pool": "youth_turkey",
        "cwmu_sportsman_reference_preserved": True,
        "runtime_updated": False,
        "audit_dir": str(AUDIT_DIR.relative_to(REPO)).replace("\\", "/"),
    }
    write_csv(AUDIT_DIR / "turkey_adult_youth_source_taxonomy_file_summary.csv", summaries)
    write_csv(AUDIT_DIR / "turkey_adult_youth_source_taxonomy_changed_rows.csv", changed_detail)
    write_csv(AUDIT_DIR / "turkey_adult_youth_source_taxonomy_final_counts.csv", final_counts)
    (AUDIT_DIR / "turkey_adult_youth_source_taxonomy_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = [
        "# Turkey Adult/Youth Source Taxonomy Repair",
        "",
        f"- complete: `{summary['turkey_adult_youth_source_taxonomy_repair_complete']}`",
        f"- files_processed: `{summary['files_processed']}`",
        f"- rows_changed: `{summary['rows_changed']}`",
        "- adult limited-entry Turkey rows are labeled `Adult` / `BONUS_TURKEY` / `preference_point`.",
        "- youth limited-entry Turkey rows are labeled `Youth` / `YOUTH_TURKEY_SET_ASIDE` / `youth_turkey`.",
        "- CWMU, Sportsman, conservation, general/fall/reference rows were preserved.",
        "- runtime_updated: `False`",
    ]
    (AUDIT_DIR / "TURKEY_ADULT_YOUTH_SOURCE_TAXONOMY_REPAIR_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
