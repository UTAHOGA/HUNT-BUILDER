from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CANONICAL_2019 = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2019_for_2020_canonical_yearly_draw_results.csv"
)
CANDIDATE_2019 = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "draw_results_2019_for_2020_candidate_promotion_file_records.csv"
)
DRAW_RESULTS_LONG = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
FINALIZED_HUNT = REPO / "data_truth" / "finalized_hunt_truth.csv"
FINALIZED_POINT = REPO / "data_truth" / "finalized_point_distribution.csv"

AUDIT_DIR = (
    REPO
    / "audits"
    / "2019_promote_truth_surfaces"
    / "promote_canonical_hunt_names"
)
BACKUP_DIR = AUDIT_DIR / "backups"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def row_year(row: dict[str, str]) -> str:
    for key in ("year", "source_year", "actual_draw_year", "truth_year"):
        value = clean(row.get(key))
        if value:
            return value[:-2] if value.endswith(".0") else value
    return ""


def row_model_year(row: dict[str, str]) -> str:
    for key in ("model_year", "permits_year", "model_target_year"):
        value = clean(row.get(key))
        if value:
            return value[:-2] if value.endswith(".0") else value
    return ""


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [{k: clean(v) for k, v in row.items()} for row in reader]
    return fields, rows


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def backup(path: Path, label: str, tag: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"{path.stem}.{label}.{tag}{path.suffix}"
    shutil.copy2(path, target)
    return target


def lookup_key(row: dict[str, str], include_points: bool) -> tuple[str, ...]:
    key = [
        row_year(row),
        row_model_year(row),
        clean(row.get("source_namespace")),
        clean(row.get("source_file")),
        clean(row.get("hunt_code")).upper(),
        clean(row.get("residency")),
    ]
    if include_points:
        key.append(clean(row.get("points") or row.get("point_level")))
    key.append(clean(row.get("record_type") or row.get("row_type")))
    return tuple(key)


def hunt_name_for(row: dict[str, str]) -> str:
    return clean(row.get("hunt_name"))


def update_rows(
    target_rows: list[dict[str, str]],
    lookup: dict[tuple[str, ...], str],
    include_points: bool,
) -> tuple[int, Counter[str]]:
    changed = 0
    years = Counter()
    for row in target_rows:
        if row_year(row) != "2019":
            continue
        key = lookup_key(row, include_points)
        new_name = lookup.get(key)
        if not new_name:
            continue
        if clean(row.get("hunt_name")) != new_name:
            row["hunt_name"] = new_name
            changed += 1
            years["2019"] += 1
    return changed, years


def main() -> None:
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    _, candidate_rows = read_rows(CANDIDATE_2019)
    long_fields, long_rows = read_rows(DRAW_RESULTS_LONG)
    hunt_fields, hunt_rows = read_rows(FINALIZED_HUNT)
    point_fields, point_rows = read_rows(FINALIZED_POINT)

    candidate_lookup_long = {
        lookup_key(row, include_points=True): hunt_name_for(row)
        for row in candidate_rows
        if row_year(row) == "2019"
    }
    candidate_lookup_final = {
        lookup_key(row, include_points=False): hunt_name_for(row)
        for row in candidate_rows
        if row_year(row) == "2019"
    }
    candidate_lookup_point = {
        lookup_key(row, include_points=True): hunt_name_for(row)
        for row in candidate_rows
        if row_year(row) == "2019" and clean(row.get("record_type")) == "point_level_draw_result"
    }

    backups = {}
    for path, label in [
        (DRAW_RESULTS_LONG, "before_promote_2019_long_hunt_names"),
        (FINALIZED_HUNT, "before_promote_2019_finalized_hunt_truth"),
        (FINALIZED_POINT, "before_promote_2019_finalized_point_distribution"),
    ]:
        backups[str(path)] = str(backup(path, label, tag))

    long_changed = 0
    for row in long_rows:
        if row_year(row) != "2019":
            continue
        key = lookup_key(row, include_points=True)
        new_name = candidate_lookup_long.get(key)
        if new_name and clean(row.get("hunt_name")) != new_name:
            row["hunt_name"] = new_name
            long_changed += 1

    hunt_changed = 0
    for row in hunt_rows:
        if row_year(row) != "2019":
            continue
        key = lookup_key(row, include_points=False)
        new_name = candidate_lookup_final.get(key)
        if new_name and clean(row.get("hunt_name")) != new_name:
            row["hunt_name"] = new_name
            hunt_changed += 1

    point_changed = 0
    for row in point_rows:
        if row_year(row) != "2019":
            continue
        key = lookup_key(row, include_points=True)
        new_name = candidate_lookup_point.get(key)
        if new_name and clean(row.get("hunt_name")) != new_name:
            row["hunt_name"] = new_name
            point_changed += 1

    write_rows(DRAW_RESULTS_LONG, long_fields, long_rows)
    write_rows(FINALIZED_HUNT, hunt_fields, hunt_rows)
    write_rows(FINALIZED_POINT, point_fields, point_rows)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "candidate_source": str(CANDIDATE_2019.relative_to(REPO)).replace("\\", "/"),
        "targets": {
            "draw_results_long": str(DRAW_RESULTS_LONG.relative_to(REPO)).replace("\\", "/"),
            "finalized_hunt_truth": str(FINALIZED_HUNT.relative_to(REPO)).replace("\\", "/"),
            "finalized_point_distribution": str(FINALIZED_POINT.relative_to(REPO)).replace("\\", "/"),
        },
        "backup_paths": backups,
        "changes": {
            "draw_results_long": long_changed,
            "finalized_hunt_truth": hunt_changed,
            "finalized_point_distribution": point_changed,
        },
        "year": 2019,
        "notes": [
            "Promoted cleaned 2019 hunt_name values from the corrected candidate promotion file into canonical master truth surfaces.",
            "Left 2020 rows unchanged.",
            "Preserved all other columns and source metadata.",
        ],
    }

    (AUDIT_DIR / "promote_2019_canonical_hunt_names_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
