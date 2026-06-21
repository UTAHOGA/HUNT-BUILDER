import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TARGET = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2019_for_2020_canonical_yearly_draw_results.csv"
)
AUDIT = REPO / "audits" / "truth_cross_year" / "final_yearly_canonical_audit" / "2019_for_2020" / "safe_blank_fill"
BACKUPS = AUDIT / "backups"


PROTECTED_FIELDS = {
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "success_ratio",
    "p_draw",
    "p_draw_percent",
    "successful_applicants",
    "unsuccessful_applicants",
}


def clean(value):
    return "" if value is None else str(value).strip()


def norm_key(*parts):
    return "|".join(clean(part).upper() for part in parts)


def to_int(value):
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text.replace(",", "")))
    except Exception:
        return None


def blank_counts(rows, fields):
    counts = {field: 0 for field in fields}
    for row in rows:
        for field in fields:
            if not clean(row.get(field)):
                counts[field] += 1
    return counts


def row_kind(row):
    row_type = clean(row.get("row_type") or row.get("record_type")).lower()
    if "point" in row_type:
        return "DRAW_RESULT_POINT_ROW"
    if "total" in row_type:
        return "DRAW_RESULT_TOTAL_ROW"
    if "availability" in row_type:
        return "AVAILABILITY_REFERENCE_ROW"
    return "DRAW_RESULT_ROW"


def build_boundary_lookup(rows):
    values = defaultdict(set)
    for row in rows:
        boundary_id = clean(row.get("boundary_id"))
        if not boundary_id:
            continue
        values[norm_key(row.get("hunt_code"), row.get("hunt_name"), row.get("species"))].add(boundary_id)

    return {key: next(iter(ids)) for key, ids in values.items() if len(ids) == 1}


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with TARGET.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    before = blank_counts(rows, fields)
    backup = BACKUPS / f"{TARGET.stem}.backup_before_safe_blank_fill_{timestamp}.csv"
    shutil.copy2(TARGET, backup)

    boundary_lookup = build_boundary_lookup(rows)
    mutation_counts = Counter()
    mutation_samples = []

    def set_value(row, column, value, reason):
        old = clean(row.get(column))
        if old or not value:
            return
        row[column] = value
        mutation_counts[column] += 1
        if len(mutation_samples) < 200:
            mutation_samples.append(
                {
                    "hunt_code": clean(row.get("hunt_code")),
                    "hunt_name": clean(row.get("hunt_name")),
                    "column": column,
                    "old_value": old,
                    "new_value": value,
                    "reason": reason,
                    "source_file": clean(row.get("source_file")),
                    "row_type": clean(row.get("row_type")),
                    "residency": clean(row.get("residency")),
                    "points": clean(row.get("points")),
                }
            )

    for row in rows:
        set_value(row, "page_kind", row_kind(row), "deterministic_from_row_type")
        set_value(row, "parse_method", "canonical_yearly_from_draw_results_long", "canonical_yearly_build_method")

        if not clean(row.get("draw_design")) and clean(row.get("hunt_type")).lower() == "antlerless":
            set_value(row, "draw_design", "PREFERENCE_POINT_ORDERED", "antlerless_source_family_preference_rule")

        if not clean(row.get("boundary_id")):
            boundary = boundary_lookup.get(norm_key(row.get("hunt_code"), row.get("hunt_name"), row.get("species")))
            if boundary:
                set_value(row, "boundary_id", boundary, "same_file_exact_hunt_code_name_species_boundary_id")

        # Permit-year totals are hunt-level reference fields. Fill NR only when the arithmetic is exact:
        # total - resident == 0. This does not change point-level draw result values.
        if not clean(row.get("permits_year_nr")):
            total = to_int(row.get("permits_year_total"))
            resident = to_int(row.get("permits_year_res"))
            if total is not None and resident is not None and total - resident == 0:
                set_value(row, "permits_year_nr", "0", "arithmetic_total_minus_resident_equals_zero")

    after = blank_counts(rows, fields)

    temp_target = TARGET.with_suffix(f".safe_blank_fill_{timestamp}.tmp")
    with temp_target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    shutil.move(str(temp_target), str(TARGET))

    with (AUDIT / "2019_safe_blank_fill_mutation_samples.csv").open("w", encoding="utf-8", newline="") as handle:
        sample_fields = [
            "hunt_code",
            "hunt_name",
            "column",
            "old_value",
            "new_value",
            "reason",
            "source_file",
            "row_type",
            "residency",
            "points",
        ]
        writer = csv.DictWriter(handle, fieldnames=sample_fields)
        writer.writeheader()
        writer.writerows(mutation_samples)

    with (AUDIT / "2019_safe_blank_fill_column_counts.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["column", "before_blank_count", "after_blank_count", "filled_count"])
        writer.writeheader()
        for field in fields:
            writer.writerow(
                {
                    "column": field,
                    "before_blank_count": before[field],
                    "after_blank_count": after[field],
                    "filled_count": before[field] - after[field],
                }
            )

    protected_changed = {field: mutation_counts[field] for field in PROTECTED_FIELDS if mutation_counts[field]}
    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(TARGET),
        "backup": str(backup),
        "status": "PASS_SAFE_BLANKS_FILLED" if not protected_changed else "FAIL_PROTECTED_FIELD_TOUCHED",
        "mutation_counts": dict(sorted(mutation_counts.items())),
        "protected_field_mutations": protected_changed,
        "before_blank_counts": before,
        "after_blank_counts": after,
        "rules": [
            "page_kind filled from row_type",
            "parse_method filled as canonical_yearly_from_draw_results_long",
            "blank antlerless draw_design filled as PREFERENCE_POINT_ORDERED",
            "boundary_id filled only from same-file exact hunt_code+hunt_name+species with a single nonblank value",
            "permits_year_nr filled only when permits_year_total - permits_year_res == 0",
        ],
        "not_filled_policy": "No applicant, point-level permit, success, probability, season, notes, or unsupported identity values were invented.",
    }
    (AUDIT / "2019_SAFE_BLANK_FILL_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    report = [
        "# 2019 Canonical Yearly Safe Blank Fill",
        "",
        f"Status: `{status['status']}`",
        f"Target: `{TARGET}`",
        f"Backup: `{backup}`",
        "",
        "## Mutation Counts",
    ]
    for column, count in sorted(mutation_counts.items()):
        report.append(f"- `{column}`: {count}")
    report.extend(
        [
            "",
            "## Protected Fields",
            f"Protected field mutations: `{protected_changed}`",
            "",
            "No applicant, point-level permit, success, probability, season, notes, or unsupported identity values were invented.",
        ]
    )
    (AUDIT / "2019_SAFE_BLANK_FILL_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
