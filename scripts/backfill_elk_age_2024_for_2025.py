import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


REPO = Path(__file__).resolve().parents[1]
SOURCE_ENHANCED = Path(
    str(_repo_root() / "pipeline/RAW/hunt_unit_database/harvest_results_2024_for_2025_elk_age_supplement/harvest_reports_2024_for_2025_elk_age_supplement/harvest_results_2024_for_2025_all_long_enhanced.csv")
)
TARGET_FEATURES = REPO / "processed_data" / "harvest_quality_features_all_years_by_hunt_code.csv"


def norm_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def norm_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def write_csv(path: Path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_code_age_map(enhanced_rows):
    age_rows = [
        row
        for row in enhanced_rows
        if row.get("reported_hunt_year") == "2024"
        and row.get("model_target_year") == "2025"
        and str(row.get("avg_age_2024", "")).strip() != ""
    ]
    keyed_rows = [
        row
        for row in enhanced_rows
        if row.get("reported_hunt_year") == "2024"
        and row.get("model_target_year") == "2025"
        and norm_code(row.get("hunt_code"))
    ]

    age_by_name = {
        (norm_text(row.get("species")), norm_text(row.get("hunt_name"))): str(row.get("avg_age_2024")).strip()
        for row in age_rows
    }

    code_to_ages = defaultdict(list)
    for row in keyed_rows:
        code = norm_code(row.get("hunt_code"))
        key = (norm_text(row.get("species")), norm_text(row.get("hunt_name")))
        age_value = age_by_name.get(key)
        if not age_value:
            continue
        code_to_ages[code].append(age_value)

    conflicts = {}
    final_map = {}
    for code, values in code_to_ages.items():
        unique = sorted(set(values))
        if len(unique) > 1:
            conflicts[code] = Counter(values)
            continue
        final_map[code] = unique[0]

    return final_map, conflicts, len(age_rows), len(keyed_rows)


def main():
    _, enhanced_rows = read_csv(SOURCE_ENHANCED)
    fields, feature_rows = read_csv(TARGET_FEATURES)

    code_age_map, conflicts, age_rows_count, keyed_rows_count = build_code_age_map(enhanced_rows)

    before_missing = 0
    after_missing = 0
    updated = 0
    touched_codes = set()
    for row in feature_rows:
        if row.get("reported_hunt_year") != "2024" or row.get("model_target_year") != "2025":
            continue

        current_age = str(row.get("average_age", "")).strip()
        if not current_age:
            before_missing += 1

        code = norm_code(row.get("hunt_code"))
        mapped_age = code_age_map.get(code)
        if not mapped_age:
            if not current_age:
                after_missing += 1
            continue

        if not current_age:
            row["average_age"] = mapped_age
            updated += 1
            touched_codes.add(code)
            current_flags = str(row.get("data_quality_flags", "")).strip()
            marker = "AVERAGE_AGE_2024_ELK_SUPPLEMENT_NAME_MAPPED"
            if marker not in current_flags:
                row["data_quality_flags"] = f"{current_flags}|{marker}".strip("|")
        if not str(row.get("average_age", "")).strip():
            after_missing += 1

    write_csv(TARGET_FEATURES, fields, feature_rows)

    print(
        json.dumps(
            {
                "ok": True,
                "source_file": str(SOURCE_ENHANCED),
                "target_file": str(TARGET_FEATURES.relative_to(REPO)).replace("\\", "/"),
                "source_age_rows_2024_2025": age_rows_count,
                "source_keyed_rows_2024_2025": keyed_rows_count,
                "mapped_codes": len(code_age_map),
                "conflict_codes_skipped": len(conflicts),
                "rows_updated": updated,
                "rows_missing_before": before_missing,
                "rows_missing_after": after_missing,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
