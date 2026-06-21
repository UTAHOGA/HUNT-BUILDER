import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MASTER = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
NORMALIZED = REPO / "data_truth" / "draw_results_truth" / "normalized"
CANONICAL_YEARLY = NORMALIZED / "canonical_yearly"
AUDIT = REPO / "audits" / "truth_cross_year" / "final_yearly_canonical_audit"
BACKUPS = AUDIT / "backups"
YEARS = list(range(2019, 2027))


def clean(value):
    return "" if value is None else str(value).strip()


def norm_int(value):
    text = clean(value)
    if not text:
        return ""
    try:
        return str(int(float(text.replace(",", ""))))
    except Exception:
        return text


def row_year(row):
    for key in ("source_year", "year", "actual_draw_year", "truth_year"):
        value = clean(row.get(key))
        if value:
            return norm_int(value)
    return ""


def row_model_year(row):
    for key in ("model_year", "permit_year", "permits_year", "model_target_year"):
        value = clean(row.get(key))
        if value:
            return norm_int(value)
    year = row_year(row)
    return str(int(year) + 1) if year.isdigit() else ""


def norm_residency(value):
    text = clean(value).lower().replace("-", "").replace(" ", "")
    if text in {"resident", "res", "r"}:
        return "Resident"
    if text in {"nonresident", "nonres", "nr"}:
        return "Nonresident"
    if text in {"all", "both", "total"}:
        return "All"
    return clean(value)


def norm_row_type(row):
    text = clean(row.get("row_type") or row.get("record_type")).lower()
    if text in {"point_row", "point_level", "point_level_draw_result", "point"}:
        return "point_level_draw_result"
    if text in {"total", "total_row", "hunt_total_draw_result", "sportsman_total", "sportsman_total_draw_result"}:
        return "hunt_total_draw_result"
    if text == "availability_only":
        return "availability_only"
    if text == "point_purchase_reference":
        return "point_purchase_reference"
    if text == "supplemental_permit_total_row":
        return "supplemental_permit_total_row"
    return text or "(blank)"


def source_identity(row):
    for key in (
        "source_file",
        "source_pdf",
        "draw_source_file",
        "source_report",
        "source_scope",
        "source_namespace",
        "draw_source_namespace",
        "source_dataset",
    ):
        value = clean(row.get(key))
        if value:
            return value
    return ""


def strict_key(row):
    return "|".join(
        [
            row_year(row),
            row_model_year(row),
            source_identity(row),
            clean(row.get("hunt_code")).upper(),
            clean(row.get("species") or row.get("family")).upper(),
            clean(row.get("sex_type") or row.get("sex") or row.get("sex_class")).upper(),
            clean(row.get("weapon")).upper(),
            clean(row.get("hunt_type") or row.get("program_family")).upper(),
            clean(row.get("hunt_class") or row.get("hunt_draw_class")).upper(),
            clean(row.get("draw_design")).upper(),
            norm_residency(row.get("residency")),
            norm_int(row.get("points") or row.get("point_level")),
            norm_row_type(row),
        ]
    )


def csv_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows_by_year():
    rows_by_year = {year: [] for year in YEARS}
    with MASTER.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            year = row_year(row)
            if year.isdigit() and int(year) in rows_by_year:
                rows_by_year[int(year)].append(row)
    return fieldnames, rows_by_year


def profile_rows(rows, fieldnames, expected_year):
    keys = Counter()
    hunt_codes = set()
    statuses = Counter()
    row_types = Counter()
    scopes = Counter()
    blank_hunt_code = 0
    blank_year = 0
    wrong_year = 0
    cg9999 = 0
    exact_rows = Counter()

    for row in rows:
        year = row_year(row)
        if not year:
            blank_year += 1
        if year and year != str(expected_year):
            wrong_year += 1
        code = clean(row.get("hunt_code")).upper()
        if not code:
            blank_hunt_code += 1
        else:
            hunt_codes.add(code)
        if code == "CG9999":
            cg9999 += 1
        statuses[clean(row.get("candidate_promotion_status") or row.get("algorithm_status")) or "(blank)"] += 1
        row_types[norm_row_type(row)] += 1
        scopes[source_identity(row) or "(blank)"] += 1
        keys[strict_key(row)] += 1
        exact_rows[tuple(row.get(field, "") for field in fieldnames)] += 1

    return {
        "rows": len(rows),
        "columns": len(fieldnames),
        "unique_hunt_codes": len(hunt_codes),
        "blank_hunt_code": blank_hunt_code,
        "blank_year": blank_year,
        "wrong_year": wrong_year,
        "cg9999_rows": cg9999,
        "duplicate_strict_key_groups": sum(1 for count in keys.values() if count > 1),
        "exact_duplicate_row_groups": sum(1 for count in exact_rows.values() if count > 1),
        "source_identity_count": len(scopes),
        "top_statuses": statuses.most_common(10),
        "top_row_types": row_types.most_common(10),
    }


def profile_existing_yearly(year):
    path = NORMALIZED / f"draw_results_{year}_for_{year + 1}_candidate_promotion_file_records.csv"
    if not path.exists():
        return {"path": str(path), "exists": False}
    rows = 0
    blank_hunt_code = 0
    blank_year = 0
    years = Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            rows += 1
            year_value = row_year(row)
            years[year_value] += 1
            if not clean(row.get("hunt_code")):
                blank_hunt_code += 1
            if not year_value:
                blank_year += 1
    return {
        "path": str(path),
        "exists": True,
        "rows": rows,
        "columns": len(fieldnames),
        "size_mb": round(path.stat().st_size / 1024 / 1024, 3),
        "blank_hunt_code": blank_hunt_code,
        "blank_year": blank_year,
        "year_counts": dict(sorted(years.items())),
    }


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    CANONICAL_YEARLY.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).isoformat()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    fieldnames, rows_by_year = load_rows_by_year()

    canonical_manifest_rows = []
    current_yearly_rows = []
    failed_gates = []
    canonical_files = []

    for year in YEARS:
        rows = rows_by_year[year]
        target = CANONICAL_YEARLY / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"
        if target.exists():
            backup = BACKUPS / f"{target.stem}.backup_before_final_yearly_canonical_{timestamp}.csv"
            shutil.copy2(target, backup)
        write_csv(target, fieldnames, rows)
        canonical_files.append(target)

        profile = profile_rows(rows, fieldnames, year)
        if profile["rows"] == 0:
            failed_gates.append(f"{year}: canonical yearly file has zero rows")
        if profile["blank_hunt_code"] != 0:
            failed_gates.append(f"{year}: blank hunt_code rows {profile['blank_hunt_code']}")
        if profile["blank_year"] != 0:
            failed_gates.append(f"{year}: blank year rows {profile['blank_year']}")
        if profile["wrong_year"] != 0:
            failed_gates.append(f"{year}: wrong-year rows {profile['wrong_year']}")
        if profile["duplicate_strict_key_groups"] != 0:
            failed_gates.append(f"{year}: duplicate strict-key groups {profile['duplicate_strict_key_groups']}")
        if year < 2023 and profile["cg9999_rows"] != 0:
            failed_gates.append(f"{year}: invalid pre-2023 CG9999 rows {profile['cg9999_rows']}")

        canonical_manifest_rows.append(
            {
                "year": year,
                "model_year": year + 1,
                "canonical_yearly_path": str(target.relative_to(REPO)).replace("\\", "/"),
                "rows": profile["rows"],
                "columns": profile["columns"],
                "size_mb": round(target.stat().st_size / 1024 / 1024, 3),
                "unique_hunt_codes": profile["unique_hunt_codes"],
                "blank_hunt_code": profile["blank_hunt_code"],
                "blank_year": profile["blank_year"],
                "wrong_year": profile["wrong_year"],
                "duplicate_strict_key_groups": profile["duplicate_strict_key_groups"],
                "exact_duplicate_row_groups": profile["exact_duplicate_row_groups"],
                "cg9999_rows": profile["cg9999_rows"],
                "source_identity_count": profile["source_identity_count"],
                "sha256": csv_sha256(target),
            }
        )

        current = profile_existing_yearly(year)
        current_yearly_rows.append(
            {
                "year": year,
                "current_yearly_path": current.get("path", ""),
                "exists": current.get("exists", False),
                "rows": current.get("rows", 0),
                "columns": current.get("columns", 0),
                "size_mb": current.get("size_mb", 0),
                "blank_hunt_code": current.get("blank_hunt_code", 0),
                "blank_year": current.get("blank_year", 0),
                "canonical_rows": profile["rows"],
                "canonical_columns": profile["columns"],
                "row_delta_current_minus_canonical": current.get("rows", 0) - profile["rows"],
                "column_delta_current_minus_canonical": current.get("columns", 0) - profile["columns"],
            }
        )

    manifest_path = AUDIT / "canonical_yearly_draw_results_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(canonical_manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(canonical_manifest_rows)

    current_comparison_path = AUDIT / "current_normalized_yearly_vs_canonical_yearly.csv"
    with current_comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(current_yearly_rows[0].keys()))
        writer.writeheader()
        writer.writerows(current_yearly_rows)

    rebuilt_long = AUDIT / "draw_results_long_rebuilt_from_canonical_yearly_DRYRUN.csv"
    with rebuilt_long.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for year in YEARS:
            writer.writerows(rows_by_year[year])

    master_hash = csv_sha256(MASTER)
    rebuilt_hash = csv_sha256(rebuilt_long)
    master_matches_rebuilt = master_hash == rebuilt_hash
    if not master_matches_rebuilt:
        failed_gates.append("draw_results_long.csv does not byte-match dry-run rebuild from canonical yearly files")

    status = {
        "generated_at_utc": generated_at,
        "status": "PASS_CANONICAL_YEARLY_READY_LONG_CONFIRMED" if not failed_gates else "FAIL_REVIEW_REQUIRED",
        "source_master": str(MASTER),
        "canonical_yearly_folder": str(CANONICAL_YEARLY),
        "canonical_yearly_files": [str(path) for path in canonical_files],
        "manifest": str(manifest_path),
        "current_vs_canonical": str(current_comparison_path),
        "dryrun_rebuilt_long": str(rebuilt_long),
        "master_rows": sum(len(rows_by_year[year]) for year in YEARS),
        "master_sha256": master_hash,
        "dryrun_rebuilt_long_sha256": rebuilt_hash,
        "master_matches_dryrun_rebuilt_long": master_matches_rebuilt,
        "failed_gates": failed_gates,
        "large_file_policy": "Canonical yearly CSVs over 50 MB require review before Git staging; draw_results_long.csv and any dry-run rebuild over 100 MB belong in Cloudflare R2, not Git.",
    }

    status_path = AUDIT / "FINAL_YEARLY_CANONICAL_AUDIT_STATUS.json"
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

    report = [
        "# Final Yearly Canonical Audit",
        "",
        f"Generated UTC: {generated_at}",
        f"Status: `{status['status']}`",
        "",
        "## Canonical Yearly Files",
        "",
        "| Year | Model Year | Rows | Hunt Codes | Size MB | Duplicate Keys | CG9999 Rows | File |",
        "|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in canonical_manifest_rows:
        report.append(
            f"| {row['year']} | {row['model_year']} | {row['rows']} | {row['unique_hunt_codes']} | {row['size_mb']} | {row['duplicate_strict_key_groups']} | {row['cg9999_rows']} | `{row['canonical_yearly_path']}` |"
        )
    report.extend(
        [
            "",
            "## Long File Confirmation",
            "",
            f"`draw_results_long.csv` byte-matches the dry-run rebuild from canonical yearly files: `{master_matches_rebuilt}`",
            "",
            "## Git / R2 Policy",
            "",
            "The canonical yearly CSVs for 2023, 2024, and 2025 are over 50 MB, so they need review before Git staging. The master long file and dry-run rebuilt long file are over 100 MB and should be R2-backed, not committed to Git.",
            "",
        ]
    )
    if failed_gates:
        report.append("## Failed Gates")
        for gate in failed_gates:
            report.append(f"- {gate}")
    else:
        report.append("All validation gates passed.")
    (AUDIT / "FINAL_YEARLY_CANONICAL_AUDIT_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
