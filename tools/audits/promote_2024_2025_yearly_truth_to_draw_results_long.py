from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


REPO = Path(r"C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER")
MASTER = REPO / "data_truth/draw_results_truth/normalized/draw_results_long.csv"
YEARLY = {
    "2024": REPO / "data_truth/draw_results_truth/normalized/draw_results_2024_for_2025_candidate_promotion_file_records.csv",
    "2025": REPO / "data_truth/draw_results_truth/normalized/draw_results_2025_for_2026_candidate_promotion_file_records.csv",
}
OUT_DIR = REPO / "audits/truth_document_audit/promote_2024_2025_yearly_truth_to_draw_results_long"
BACKUP_DIR = OUT_DIR / "backups"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def norm_year(value: object) -> str:
    text = clean(value)
    return text[:-2] if text.endswith(".0") else text


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def first(row: dict[str, str], names: list[str]) -> str:
    for name in names:
        value = clean(row.get(name))
        if value:
            return value
    return ""


def year_of(row: dict[str, str]) -> str:
    return norm_year(first(row, ["source_year", "actual_draw_year", "reported_draw_year", "year", "truth_year"]))


def model_year_of(row: dict[str, str], source_year: str) -> str:
    value = norm_year(first(row, ["model_year", "model_target_year", "permits_year"]))
    if value:
        return value
    return str(int(source_year) + 1) if source_year.isdigit() else ""


def canonical_record_type(row: dict[str, str]) -> str:
    value = first(row, ["record_type", "record_kind"])
    if value == "POINT_ROW":
        return "point_level_draw_result"
    if value == "SPORTSMAN_TOTAL":
        return "sportsman_total_draw_result"
    if value == "AVAILABILITY_ONLY":
        return "availability_only"
    if value == "SUPPLEMENTAL_PERMIT_TOTAL_ROW":
        return "supplemental_permit_total_row"
    return value


def conform(row: dict[str, str], fields: list[str]) -> dict[str, str]:
    source_year = year_of(row)
    model_year = model_year_of(row, source_year)
    source_scope = first(row, ["source_scope", "source_report_family", "source_classification", "normalized_family", "source_family"])
    source_file = first(row, ["source_file", "source_pdf", "draw_source_file"])
    pdf_page = first(row, ["pdf_page", "source_pdf_page", "page_number", "pdf_page_number", "source_report_page"])
    out = {field: "" for field in fields}
    values = {
        "source_year": source_year,
        "year": source_year,
        "actual_draw_year": source_year,
        "model_year": model_year,
        "model_target_year": model_year,
        "truth_year": source_year,
        "permits_year": model_year,
        "source_scope": source_scope,
        "source_namespace": first(row, ["source_namespace", "source_dataset"]),
        "draw_source_namespace": first(row, ["draw_source_namespace", "source_dataset"]),
        "source_file": source_file,
        "draw_source_file": source_file,
        "source_path": first(row, ["source_path", "source_file_path"]),
        "source_pdf": first(row, ["source_pdf"]) or source_file,
        "pdf_page": pdf_page,
        "official_page": first(row, ["official_page", "source_report_page"]),
        "page_kind": first(row, ["page_kind"]),
        "hunt_code": clean(row.get("hunt_code")).upper(),
        "hunt_name": first(row, ["hunt_name", "database_hunt_name"]),
        "raw_hunt_name": first(row, ["raw_hunt_name", "hunt_name", "database_hunt_name"]),
        "species": first(row, ["species", "database_species", "normalized_species_family"]),
        "sex_type": first(row, ["sex_type", "database_sex_type"]),
        "hunt_type": first(row, ["hunt_type", "database_hunt_type"]),
        "hunt_class": first(row, ["hunt_class"]),
        "weapon": first(row, ["weapon", "database_weapon"]),
        "season": first(row, ["season"]),
        "draw_design": first(row, ["normalized_family", "source_classification", "source_report_family"]),
        "draw_type": first(row, ["draw_type"]),
        "draw_method": first(row, ["draw_method"]),
        "draw_pool": first(row, ["draw_pool"]),
        "residency": first(row, ["residency"]),
        "points": first(row, ["points"]),
        "eligible_applicants": first(row, ["eligible_applicants"]),
        "bonus_permits": first(row, ["bonus_permits"]),
        "preference_permits": first(row, ["preference_permits"]),
        "regular_permits": first(row, ["regular_permits"]),
        "total_permits": first(row, ["total_permits"]),
        "pool_permits": first(row, ["pool_permits"]),
        "p_draw": first(row, ["p_draw"]),
        "p_draw_percent": first(row, ["p_draw_percent"]),
        "success_ratio": first(row, ["success_ratio"]),
        "record_type": canonical_record_type(row),
        "successful_applicants": first(row, ["successful_applicants"]),
        "unsuccessful_applicants": first(row, ["unsuccessful_applicants"]),
        "boundary_id": first(row, ["boundary_id", "database_boundary_id"]),
        "candidate_promotion_status": first(row, ["candidate_promotion_status"]),
        "algorithm_status": first(row, ["algorithm_status", "validation_status", "status"]),
        "source_dataset": first(row, ["source_dataset"]),
        "extraction_status": first(row, ["extraction_status"]),
        "parse_method": first(row, ["parse_method"]),
        "qa_status": first(row, ["qa_status", "validation_status", "status"]),
        "qa_notes": first(row, ["qa_notes", "missing_required_metadata"]),
        "notes": first(row, ["notes", "candidate_promotion_reason"]),
        "permits_year_res": first(row, ["permits_year_res", "database_permits_2025_res"]),
        "permits_year_nr": first(row, ["permits_year_nr", "database_permits_2025_nr"]),
        "permits_year_total": first(row, ["permits_year_total", "database_permits_2025_total", "database_permits_2025_draw_total"]),
    }
    for field, value in values.items():
        if field in out:
            out[field] = value
    return out


def strict_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        clean(row.get("source_year") or row.get("year")),
        clean(row.get("model_year") or row.get("model_target_year") or row.get("permits_year")),
        clean(row.get("source_scope") or row.get("source_namespace")),
        clean(row.get("hunt_code")).upper(),
        clean(row.get("residency")),
        clean(row.get("points")),
        clean(row.get("record_type")),
    )


def summarize(rows: list[dict[str, str]]) -> dict[str, object]:
    year_counts = Counter(clean(row.get("source_year") or row.get("year")) for row in rows)
    dupes = [key for key, count in Counter(strict_key(row) for row in rows).items() if count > 1]
    return {
        "rows": len(rows),
        "year_counts": dict(sorted(year_counts.items())),
        "unique_hunt_codes": len({clean(row.get("hunt_code")).upper() for row in rows if clean(row.get("hunt_code"))}),
        "blank_hunt_code": sum(1 for row in rows if not clean(row.get("hunt_code"))),
        "blank_source_year": sum(1 for row in rows if not clean(row.get("source_year") or row.get("year"))),
        "cg9999_by_year": dict(sorted(Counter(clean(row.get("source_year") or row.get("year")) for row in rows if clean(row.get("hunt_code")).upper() == "CG9999").items())),
        "duplicate_strict_key_groups": len(dupes),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    master_fields, master_rows = read_rows(MASTER)
    current_2024_2025 = [row for row in master_rows if year_of(row) in {"2024", "2025"}]
    retained = [row for row in master_rows if year_of(row) not in {"2024", "2025"}]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"draw_results_long.backup_before_2024_2025_promotion_{stamp}.csv"
    shutil.copy2(MASTER, backup_path)

    promoted_by_year: dict[str, list[dict[str, str]]] = {}
    yearly_input_summary: dict[str, object] = {}
    for year, path in YEARLY.items():
        fields, rows = read_rows(path)
        conformed = [conform(row, master_fields) for row in rows]
        promoted_by_year[year] = conformed
        yearly_input_summary[year] = {
            "path": str(path),
            "input_rows": len(rows),
            "input_columns": len(fields),
            "conformed_rows": len(conformed),
        }

    promoted_rows = promoted_by_year["2024"] + promoted_by_year["2025"]
    final_rows = retained + promoted_rows
    write_csv(MASTER, final_rows, master_fields)

    write_csv(OUT_DIR / "current_long_2024_2025_rows_replaced.csv", current_2024_2025, master_fields)
    write_csv(OUT_DIR / "promoted_2024_2025_conformed_rows.csv", promoted_rows, master_fields)
    row_count_audit = [
        {"bucket": "master_before", **summarize(master_rows)},
        {"bucket": "retained_not_2024_2025", **summarize(retained)},
        {"bucket": "current_2024_2025_replaced", **summarize(current_2024_2025)},
        {"bucket": "promoted_2024", **summarize(promoted_by_year["2024"])},
        {"bucket": "promoted_2025", **summarize(promoted_by_year["2025"])},
        {"bucket": "master_after", **summarize(final_rows)},
    ]
    write_csv(
        OUT_DIR / "promote_2024_2025_row_count_audit.csv",
        [{k: json.dumps(v, sort_keys=True) if isinstance(v, dict) else v for k, v in row.items()} for row in row_count_audit],
        ["bucket", "rows", "year_counts", "unique_hunt_codes", "blank_hunt_code", "blank_source_year", "cg9999_by_year", "duplicate_strict_key_groups"],
    )

    final_summary = summarize(final_rows)
    expected_rows = len(retained) + len(promoted_by_year["2024"]) + len(promoted_by_year["2025"])
    failed_gates = []
    if final_summary["rows"] != expected_rows:
        failed_gates.append("MASTER_ROW_COUNT_MISMATCH")
    if final_summary["blank_hunt_code"]:
        failed_gates.append("BLANK_HUNT_CODE")
    if final_summary["blank_source_year"]:
        failed_gates.append("BLANK_SOURCE_YEAR")
    if final_summary["duplicate_strict_key_groups"]:
        failed_gates.append("DUPLICATE_STRICT_KEYS")
    if final_summary["year_counts"].get("2024") != len(promoted_by_year["2024"]):
        failed_gates.append("2024_ROW_COUNT_NOT_PROMOTED")
    if final_summary["year_counts"].get("2025") != len(promoted_by_year["2025"]):
        failed_gates.append("2025_ROW_COUNT_NOT_PROMOTED")
    if final_summary["cg9999_by_year"].get("2024") != 1:
        failed_gates.append("2024_CG9999_COUNT_NOT_1")
    if final_summary["cg9999_by_year"].get("2025") != 1:
        failed_gates.append("2025_CG9999_COUNT_NOT_1")
    for pre in ["2019", "2020", "2021", "2022"]:
        if final_summary["cg9999_by_year"].get(pre, 0) != 0:
            failed_gates.append(f"PRE_2023_CG9999_{pre}")

    status = {
        "generated_at": datetime.now().isoformat(),
        "master": str(MASTER),
        "backup_path": str(backup_path),
        "yearly_inputs": yearly_input_summary,
        "master_before": summarize(master_rows),
        "current_2024_2025_replaced": summarize(current_2024_2025),
        "promoted_2024": summarize(promoted_by_year["2024"]),
        "promoted_2025": summarize(promoted_by_year["2025"]),
        "master_after": final_summary,
        "failed_gates": failed_gates,
        "status": "PASS_2024_2025_PROMOTED_TO_DRAW_RESULTS_LONG" if not failed_gates else "REVIEW_REQUIRED",
    }
    (OUT_DIR / "PROMOTE_2024_2025_TO_DRAW_RESULTS_LONG_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    if not failed_gates:
        (OUT_DIR / "ACCEPT_PROMOTE_2024_2025_TO_DRAW_RESULTS_LONG.md").write_text(
            "\n".join(
                [
                    "# Accept 2024-2025 Promotion To draw_results_long",
                    "",
                    f"- Master: `{MASTER}`",
                    f"- Backup: `{backup_path}`",
                    "- 2024 and 2025 were conformed into the canonical long schema.",
                    "- 2023 and older rows were preserved.",
                    "- No duplicate strict keys remain.",
                    "- CG9999 is present only in 2023+ years.",
                    "",
                    "ACCEPT_PROMOTE_2024_2025_TO_DRAW_RESULTS_LONG: true",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
