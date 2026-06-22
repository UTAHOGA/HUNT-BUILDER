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
AUDIT = REPO / "audits" / "truth_cross_year" / "final_yearly_canonical_audit" / "2019_for_2020" / "raw_pdf_blank_fill"
BACKUPS = AUDIT / "backups"

RAW_PDF_PROOFS = {
    "cougar_weapon": REPO
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2019_PERMITS=2020_MODEL"
    / "2019_PERMITS=2020_MODEL_L.E. COUGAR DRAW RESULTS.pdf",
    "antlerless_draw_design": REPO
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2019_PERMITS=2020_MODEL"
    / "2019_PERMITS=2020_MODEL__ANTLERLESS DEER DRAW RESULTS.pdf",
    "pronghorn_zero_total": REPO
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2019_PERMITS=2020_MODEL"
    / "2019_PERMITS=2020_MODEL__L.E. PROGHORN DRAW RESULTS.pdf",
}

PROTECTED_NUMERIC_FIELDS = {
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "p_draw",
    "p_draw_percent",
}


def clean(value):
    return "" if value is None else str(value).strip()


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


def source_file(row):
    return clean(row.get("source_file") or row.get("source_pdf") or row.get("source_scope"))


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with TARGET.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    before = blank_counts(rows, fields)
    backup = BACKUPS / f"{TARGET.stem}.backup_before_raw_pdf_fill_{timestamp}.csv"
    shutil.copy2(TARGET, backup)

    mutation_counts = Counter()
    mutation_samples = []
    review_rows = []

    def set_value(row, column, value, reason, proof):
        if clean(row.get(column)) or value == "":
            return
        old = clean(row.get(column))
        row[column] = value
        mutation_counts[column] += 1
        if len(mutation_samples) < 500:
            mutation_samples.append(
                {
                    "hunt_code": clean(row.get("hunt_code")),
                    "hunt_name": clean(row.get("hunt_name")),
                    "column": column,
                    "old_value": old,
                    "new_value": value,
                    "reason": reason,
                    "proof": proof,
                    "source_file": source_file(row),
                    "row_type": clean(row.get("row_type")),
                    "residency": clean(row.get("residency")),
                    "points": clean(row.get("points")),
                }
            )

    for row in rows:
        src = source_file(row)
        code = clean(row.get("hunt_code")).upper()

        if src == "2020_cougar_odds_report(2).pdf":
            set_value(
                row,
                "weapon",
                "Any Legal Weapon",
                "raw_pdf_hunt_lines_all_show_any_legal_weapon",
                str(RAW_PDF_PROOFS["cougar_weapon"]),
            )

        if src == "19_antlerless_drawing_odds_report(1).pdf":
            set_value(
                row,
                "draw_design",
                "PREFERENCE_POINT_ORDERED",
                "raw_pdf_title_2019_draw_7_antlerless_preference_point_draw_results",
                str(RAW_PDF_PROOFS["antlerless_draw_design"]),
            )

        if code == "PB5058" and src == "19_bg-odds(1).pdf":
            # The species split PDF page for PB5058 shows resident and nonresident Totals 0 0 0 0 N/A.
            set_value(row, "permits_year_res", "0", "raw_pdf_pb5058_totals_zero", str(RAW_PDF_PROOFS["pronghorn_zero_total"]))
            set_value(row, "permits_year_nr", "0", "raw_pdf_pb5058_totals_zero", str(RAW_PDF_PROOFS["pronghorn_zero_total"]))
            set_value(row, "permits_year_total", "0", "raw_pdf_pb5058_totals_zero", str(RAW_PDF_PROOFS["pronghorn_zero_total"]))

        if (
            not clean(row.get("success_ratio"))
            and clean(row.get("row_type")) == "point_level_draw_result"
            and to_int(row.get("total_permits")) == 0
            and not clean(row.get("p_draw"))
            and not clean(row.get("p_draw_percent"))
        ):
            set_value(
                row,
                "success_ratio",
                "N/A",
                "raw_pdf_zero_permit_rows_print_NA_success_ratio",
                src,
            )

        if (not clean(row.get("sex")) or not clean(row.get("sex_type"))) and src in {
            "2020_cougar_odds_report(2).pdf",
            "19_bg-odds(1).pdf",
        }:
            review_rows.append(
                {
                    "hunt_code": code,
                    "hunt_name": clean(row.get("hunt_name")),
                    "species": clean(row.get("species")),
                    "source_file": src,
                    "blank_sex": "TRUE" if not clean(row.get("sex")) else "FALSE",
                    "blank_sex_type": "TRUE" if not clean(row.get("sex_type")) else "FALSE",
                    "review_reason": "raw_pdf_hunt_title_does_not_print_explicit_sex_type",
                }
            )

        if not clean(row.get("boundary_id")):
            review_rows.append(
                {
                    "hunt_code": code,
                    "hunt_name": clean(row.get("hunt_name")),
                    "species": clean(row.get("species")),
                    "source_file": src,
                    "blank_sex": "FALSE",
                    "blank_sex_type": "FALSE",
                    "review_reason": "boundary_id_not_printed_in_draw_result_pdf_requires_database_or_geojson_crosswalk",
                }
            )

    protected_mutations = {field: mutation_counts[field] for field in PROTECTED_NUMERIC_FIELDS if mutation_counts[field]}
    after = blank_counts(rows, fields)

    temp_target = TARGET.with_suffix(f".raw_pdf_blank_fill_{timestamp}.tmp")
    with temp_target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    shutil.move(str(temp_target), str(TARGET))

    with (AUDIT / "2019_raw_pdf_blank_fill_mutation_samples.csv").open("w", encoding="utf-8", newline="") as handle:
        sample_fields = [
            "hunt_code",
            "hunt_name",
            "column",
            "old_value",
            "new_value",
            "reason",
            "proof",
            "source_file",
            "row_type",
            "residency",
            "points",
        ]
        writer = csv.DictWriter(handle, fieldnames=sample_fields)
        writer.writeheader()
        writer.writerows(mutation_samples)

    with (AUDIT / "2019_raw_pdf_blank_fill_column_counts.csv").open("w", encoding="utf-8", newline="") as handle:
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

    with (AUDIT / "2019_raw_pdf_remaining_review_rows.csv").open("w", encoding="utf-8", newline="") as handle:
        review_fields = ["hunt_code", "hunt_name", "species", "source_file", "blank_sex", "blank_sex_type", "review_reason"]
        writer = csv.DictWriter(handle, fieldnames=review_fields)
        writer.writeheader()
        deduped = []
        seen = set()
        for row in review_rows:
            key = tuple(row.get(field, "") for field in review_fields)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        writer.writerows(deduped)

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(TARGET),
        "backup": str(backup),
        "status": "PASS_RAW_PDF_BACKED_BLANK_FILL" if not protected_mutations else "FAIL_PROTECTED_NUMERIC_FIELD_TOUCHED",
        "mutation_counts": dict(sorted(mutation_counts.items())),
        "protected_numeric_field_mutations": protected_mutations,
        "before_blank_counts": before,
        "after_blank_counts": after,
        "raw_pdf_proofs": {key: str(value) for key, value in RAW_PDF_PROOFS.items()},
        "review_rows": len(deduped),
        "rules": [
            "Cougar weapon filled only because every cougar PDF hunt line contains Any Legal Weapon.",
            "Antlerless draw_design filled only because PDF title is Antlerless Preference Point Draw Results.",
            "PB5058 permit-year totals filled as 0/0/0 from PDF totals row.",
            "success_ratio filled with literal N/A only when blank, point-level, total_permits=0, and p_draw fields are blank.",
            "p_draw and p_draw_percent were not fabricated from N/A rows.",
            "sex/sex_type left blank where the PDF title does not explicitly print sex type.",
            "boundary_id left blank because draw-result PDFs do not print boundary IDs; needs DATABASE/geojson crosswalk.",
        ],
    }
    (AUDIT / "2019_RAW_PDF_BLANK_FILL_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    report = [
        "# 2019 Canonical Raw-PDF Blank Fill",
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
            "## Held For Review",
            "- `sex` / `sex_type` where the PDF title does not explicitly print the sex type.",
            "- `boundary_id`, because draw-result PDFs do not print boundary IDs.",
            "- `p_draw` and `p_draw_percent` for N/A rows, because those are not numeric probabilities.",
            "",
            f"Review rows: `{len(deduped)}`",
        ]
    )
    (AUDIT / "2019_RAW_PDF_BLANK_FILL_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
