import csv
import json
import shutil
from collections import Counter
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
AUDIT = (
    REPO
    / "audits"
    / "truth_cross_year"
    / "final_yearly_canonical_audit"
    / "2019_for_2020"
    / "sex_boundary_fill"
    / "ram_fill"
)
BACKUPS = AUDIT / "backups"

TARGET_CODES = {"RS6714", "RS6719"}
TARGET_SPECIES = "Rocky Mountain Bighorn Sheep"
RAM_VALUE = "Ram"

PROTECTED_DRAW_FIELDS = {
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


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def blank_counts(rows):
    return {
        "sex": sum(1 for row in rows if not clean(row.get("sex"))),
        "sex_type": sum(1 for row in rows if not clean(row.get("sex_type"))),
        "rocky_mountain_bighorn_sheep_blank_sex": sum(
            1
            for row in rows
            if clean(row.get("species")) == TARGET_SPECIES
            and (not clean(row.get("sex")) or not clean(row.get("sex_type")))
        ),
    }


def duplicate_strict_key_count(rows):
    keys = Counter()
    for row in rows:
        key = (
            clean(row.get("source_year") or row.get("year") or row.get("actual_draw_year")),
            clean(row.get("model_year") or row.get("model_target_year") or row.get("permits_year")),
            clean(row.get("source_scope") or row.get("source_namespace") or row.get("draw_source_namespace")),
            clean(row.get("hunt_code")).upper(),
            clean(row.get("residency")),
            clean(row.get("points")),
            clean(row.get("row_type") or row.get("record_type")),
        )
        keys[key] += 1
    return sum(1 for count in keys.values() if count > 1)


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    fields, rows = read_csv(TARGET)

    before_counts = blank_counts(rows)
    protected_before = {field: Counter(clean(row.get(field)) for row in rows) for field in PROTECTED_DRAW_FIELDS}

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUPS / f"{TARGET.stem}.backup_before_rs_sheep_ram_fill_{timestamp}.csv"
    shutil.copy2(TARGET, backup_path)

    mutations = []
    for row_number, row in enumerate(rows, start=2):
        code = clean(row.get("hunt_code")).upper()
        if code not in TARGET_CODES:
            continue
        if clean(row.get("species")) != TARGET_SPECIES:
            continue
        for column in ("sex", "sex_type"):
            if column in fields and not clean(row.get(column)):
                old_value = row.get(column, "")
                row[column] = RAM_VALUE
                mutations.append(
                    {
                        "row_number": row_number,
                        "hunt_code": code,
                        "column": column,
                        "old_value": old_value,
                        "new_value": RAM_VALUE,
                        "source_type": "USER_APPROVED_OIL_ROCKY_MOUNTAIN_BIGHORN_SHEEP_RULE",
                        "source_detail": "2019 O.I.L. Rocky Mountain Bighorn Sheep rows approved as Ram where sex is blank",
                    }
                )

    protected_after = {field: Counter(clean(row.get(field)) for row in rows) for field in PROTECTED_DRAW_FIELDS}
    protected_changed = [
        field for field in sorted(PROTECTED_DRAW_FIELDS) if protected_before[field] != protected_after[field]
    ]

    tmp_path = TARGET.with_suffix(".tmp")
    write_csv(tmp_path, rows, fields)
    shutil.move(str(tmp_path), str(TARGET))

    after_counts = blank_counts(rows)
    duplicate_groups = duplicate_strict_key_count(rows)
    mutation_counts = Counter(m["column"] for m in mutations)

    write_csv(
        AUDIT / "2019_rs_sheep_ram_fill_mutation_ledger.csv",
        mutations,
        ["row_number", "hunt_code", "column", "old_value", "new_value", "source_type", "source_detail"],
    )
    write_csv(
        AUDIT / "2019_rs_sheep_ram_fill_summary.csv",
        [{"column": column, "mutation_count": count} for column, count in sorted(mutation_counts.items())],
        ["column", "mutation_count"],
    )

    status = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(TARGET),
        "backup_path": str(backup_path),
        "row_count": len(rows),
        "before_blank_counts": before_counts,
        "after_blank_counts": after_counts,
        "target_codes": sorted(TARGET_CODES),
        "mutation_counts": dict(sorted(mutation_counts.items())),
        "duplicate_strict_key_groups": duplicate_groups,
        "protected_draw_fields_changed": protected_changed,
        "status": "PASS" if not protected_changed and duplicate_groups == 0 else "REVIEW_REQUIRED",
    }
    (AUDIT / "2019_RS_SHEEP_RAM_FILL_STATUS.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8"
    )
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
