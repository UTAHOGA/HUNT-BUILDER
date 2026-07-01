from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Mapping

import pdfplumber


REPO = Path(__file__).resolve().parents[1]
CANONICAL_PATH = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
)
PDF_SOURCES = (
    (
        REPO
        / "outputs"
        / "2026"
        / "pdf"
        / "draw results"
        / "2026_PERMITS=2027_MODEL__G.S. BUCK DEER DRAW RESULTS.pdf",
        "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "GENERAL_SEASON_DEER",
        "Big Game:General-Season",
    ),
    (
        REPO
        / "outputs"
        / "2026"
        / "pdf"
        / "draw results"
        / "2026_PERMITS=2027_MODEL__D.H. DEER DRAW RESULTS.pdf",
        "PREFERENCE_DEDICATED_HUNTER_DEER",
        "DEDICATED_HUNTER",
        "Big Game:Dedicated Hunter",
    ),
)
AUDIT_DIR = REPO / "audits" / f"repair_2026_preference_deer_canonical_from_pdf_{datetime.now():%Y%m%d_%H%M%S}"

ROW_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(N/A|1\s+in\s+[\d.]+)\s+"
    r"(\d+(?:\.\d+)?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(N/A|1\s+in\s+[\d.]+)\s*$"
)


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def to_int(value: object) -> int | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def point_text(value: object) -> str:
    text = clean(value)
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if abs(number - round(number)) < 1e-9 else str(number)


def probability(applicants: int, permits: int) -> str:
    if applicants <= 0:
        return ""
    if permits <= 0:
        return "0"
    value = permits / applicants
    return f"{value:.9f}".rstrip("0").rstrip(".")


def percent_from_probability(p_draw: str) -> str:
    if not p_draw:
        return ""
    try:
        return f"{float(p_draw) * 100.0:.6f}".rstrip("0").rstrip(".")
    except ValueError:
        return ""


def parse_hunt_header(text: str) -> tuple[str, str, str, str]:
    header_match = re.search(r"Hunt:\s+([A-Z]{2}\d+)\s+(.+?)(?:\n|$)", text)
    if not header_match:
        return "", "", "", ""
    hunt_code = header_match.group(1).upper()
    title_blob = header_match.group(2).strip()
    title, _, inline_season = title_blob.partition(" | ")
    title_parts = [part.strip() for part in title.split(" - ")]
    hunt_name = title_parts[0] if title_parts else title
    weapon = title_parts[-1] if len(title_parts) > 1 else ""
    season = inline_season.strip()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if f"Hunt: {hunt_code}" in line and index + 1 < len(lines):
            maybe_season = lines[index + 1].strip()
            if "2026 Draw" not in maybe_season and "Resident Applicants" not in maybe_season:
                season = maybe_season
            break
    return hunt_code, hunt_name, weapon, season


def parse_pdf_rows() -> list[dict[str, object]]:
    parsed: list[dict[str, object]] = []
    for pdf_path, family, source_scope, source_file_label in PDF_SOURCES:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                hunt_code, hunt_name, weapon, season = parse_hunt_header(text)
                if not hunt_code:
                    continue
                for line in text.splitlines():
                    match = ROW_RE.match(line.strip())
                    if not match:
                        continue
                    groups = match.groups()
                    for residency, values in (("Resident", groups[:6]), ("Nonresident", groups[6:])):
                        points, applicants, preference_permits, regular_permits, total_permits, ratio = values
                        applicants_i = to_int(applicants) or 0
                        preference_i = to_int(preference_permits) or 0
                        regular_i = to_int(regular_permits) or 0
                        total_i = to_int(total_permits) or 0
                        p_draw = probability(applicants_i, total_i)
                        if hunt_code == "DB0008":
                            draw_system_type = "AVAILABILITY_ONLY"
                            draw_design = "AVAILABILITY_ONLY"
                            source_scope_out = "GENERAL_SEASON_DEER_EXTENDED_ARCHERY_REFERENCE"
                        else:
                            draw_system_type = family
                            draw_design = family
                            source_scope_out = source_scope
                        parsed.append(
                            {
                                "hunt_code": hunt_code,
                                "hunt_name": hunt_name,
                                "weapon": weapon,
                                "season": season,
                                "family": family,
                                "draw_design": draw_design,
                                "draw_system_type": draw_system_type,
                                "source_scope": source_scope_out,
                                "residency": residency,
                                "points": point_text(points),
                                "eligible_applicants": str(applicants_i),
                                "bonus_permits": str(preference_i),
                                "regular_permits": str(regular_i),
                                "total_permits": str(total_i),
                                "success_ratio": ratio,
                                "p_draw": p_draw,
                                "p_draw_percent": percent_from_probability(p_draw),
                                "successful_applicants": str(total_i),
                                "unsuccessful_applicants": str(max(applicants_i - total_i, 0)),
                                "source_file": str(pdf_path),
                                "draw_source_file": str(pdf_path),
                                "source_pdf": str(pdf_path),
                                "source_dataset": "OFFICIAL_DWR_2026_PDF_DRAW_RESULTS",
                                "draw_source_namespace": source_file_label,
                                "pdf_page": str(page_number),
                                "official_page": str(page_number),
                            }
                        )
    return parsed


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[Mapping[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def row_key(row: Mapping[str, object]) -> tuple[str, str, str, str]:
    return (
        clean(row.get("hunt_code")).upper(),
        clean(row.get("residency")).title(),
        point_text(row.get("points")),
        clean(row.get("draw_system_type")) or clean(row.get("draw_design")),
    )


def point_family(row: Mapping[str, object]) -> str:
    code = clean(row.get("hunt_code")).upper()
    draw_system_type = clean(row.get("draw_system_type")) or clean(row.get("draw_design"))
    if code == "DB0008":
        return "DB0008_REFERENCE"
    if draw_system_type in {"PREFERENCE_GENERAL_SEASON_BUCK_DEER", "PREFERENCE_DEDICATED_HUNTER_DEER"}:
        return draw_system_type
    return ""


def choose_template(
    parsed_row: Mapping[str, object],
    exact_candidates: dict[tuple[str, str, str, str], list[dict[str, str]]],
    code_candidates: dict[str, list[dict[str, str]]],
) -> dict[str, str]:
    key = row_key(parsed_row)
    target_applicants = clean(parsed_row.get("eligible_applicants"))
    target_total = clean(parsed_row.get("total_permits"))
    target_p = clean(parsed_row.get("p_draw"))
    for candidate in exact_candidates.get(key, []):
        same_values = (
            clean(candidate.get("eligible_applicants")) == target_applicants
            and clean(candidate.get("total_permits")) == target_total
            and (
                clean(candidate.get("p_draw")) == target_p
                or (target_p == "0" and clean(candidate.get("p_draw")) == "")
            )
        )
        if same_values:
            return dict(candidate)
    candidates = exact_candidates.get(key) or code_candidates.get(clean(parsed_row.get("hunt_code")).upper()) or []
    return dict(candidates[0]) if candidates else {}


def apply_parsed_values(template: dict[str, str], parsed_row: Mapping[str, object]) -> dict[str, str]:
    row = dict(template)
    for field, value in parsed_row.items():
        if field == "family":
            continue
        if field in row:
            row[field] = clean(value)
    row["actual_draw_year"] = "2026"
    row["model_target_year"] = "2027"
    row["row_type"] = "point_level_draw_result"
    row["record_type"] = "point_level_draw_result"
    row["qa_status"] = "CONFIRMED_CANONICAL_SCORABLE"
    row["parse_method"] = "2026_PDF_TABLE_TRUTH_DEDUP_REPAIR"
    row["extraction_status"] = "source_backed_pdf_table_repair"
    row["candidate_promotion_status"] = "promoted_pdf_table_truth"
    row["source_row_count"] = "1"
    row["collapse_conflict_count"] = "0"
    return row


def main() -> int:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames, rows = read_csv(CANONICAL_PATH)
    parsed_rows = parse_pdf_rows()

    parsed_codes = {clean(row.get("hunt_code")).upper() for row in parsed_rows}
    parsed_repair_codes = {
        code
        for code in parsed_codes
        if code == "DB0008" or code.startswith(("DB15", "DB16", "DB17", "DB18"))
    }
    exact_candidates: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    code_candidates: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if code in parsed_repair_codes:
            exact_candidates[row_key(row)].append(row)
            code_candidates[code].append(row)

    replacement_rows = [apply_parsed_values(choose_template(row, exact_candidates, code_candidates), row) for row in parsed_rows if clean(row.get("hunt_code")).upper() in parsed_repair_codes]
    replacement_by_code = Counter(clean(row.get("hunt_code")).upper() for row in replacement_rows)

    removed_rows = []
    kept_rows = []
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if code in parsed_repair_codes and (point_family(row) or code == "DB0008"):
            removed_rows.append(row)
        else:
            kept_rows.append(row)

    repaired_rows = kept_rows + replacement_rows
    backup_path = CANONICAL_PATH.with_suffix(f".backup_preference_pdf_repair_{datetime.now():%Y%m%d_%H%M%S}.csv")
    shutil.copy2(CANONICAL_PATH, backup_path)
    temp_path = CANONICAL_PATH.with_suffix(".tmp_preference_pdf_repair.csv")
    write_csv(temp_path, fieldnames, repaired_rows)
    temp_path.replace(CANONICAL_PATH)

    def duplicate_summary(target_rows: list[Mapping[str, object]]) -> dict[str, int]:
        groups: Counter[tuple[str, str, str, str]] = Counter()
        for row in target_rows:
            fam = point_family(row)
            if fam in {"PREFERENCE_GENERAL_SEASON_BUCK_DEER", "PREFERENCE_DEDICATED_HUNTER_DEER"}:
                groups[row_key(row)] += 1
        duplicate_groups = sum(1 for count in groups.values() if count > 1)
        duplicate_rows = sum(count for count in groups.values() if count > 1)
        duplicate_codes = len({key[0] for key, count in groups.items() if count > 1})
        return {
            "duplicate_groups": duplicate_groups,
            "duplicate_rows": duplicate_rows,
            "duplicate_codes": duplicate_codes,
        }

    summary = {
        "canonical_path": str(CANONICAL_PATH.relative_to(REPO)),
        "backup_path": str(backup_path.relative_to(REPO)),
        "rows_before": len(rows),
        "rows_removed": len(removed_rows),
        "rows_added_from_pdf": len(replacement_rows),
        "rows_after": len(repaired_rows),
        "parsed_pdf_rows": len(parsed_rows),
        "parsed_repair_codes": len(parsed_repair_codes),
        "replacement_rows_by_top_family": dict(Counter(clean(row.get("draw_system_type")) for row in replacement_rows)),
        "replacement_rows_by_code_top_25": dict(replacement_by_code.most_common(25)),
        "duplicate_summary_before": duplicate_summary(rows),
        "duplicate_summary_after": duplicate_summary(repaired_rows),
        "db0008_policy": "kept_out_of_ordinary_preference_model_as_AVAILABILITY_ONLY",
        "positive_applicant_zero_permit_policy": "p_draw_zero",
        "zero_applicant_policy": "preserved_structural_blank_p_draw",
    }

    write_csv(AUDIT_DIR / "removed_canonical_rows.csv", fieldnames, removed_rows)
    write_csv(AUDIT_DIR / "replacement_pdf_table_rows.csv", fieldnames, replacement_rows)
    (AUDIT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = [
        "# 2026 Preference Deer Canonical PDF Repair",
        "",
        f"- Rows before: `{summary['rows_before']}`",
        f"- Rows removed: `{summary['rows_removed']}`",
        f"- Rows added from PDF tables: `{summary['rows_added_from_pdf']}`",
        f"- Rows after: `{summary['rows_after']}`",
        f"- Duplicate summary before: `{summary['duplicate_summary_before']}`",
        f"- Duplicate summary after: `{summary['duplicate_summary_after']}`",
        f"- DB0008 policy: `{summary['db0008_policy']}`",
        f"- Positive-applicant/zero-permit policy: `{summary['positive_applicant_zero_permit_policy']}`",
        f"- Zero-applicant policy: `{summary['zero_applicant_policy']}`",
        f"- Backup: `{summary['backup_path']}`",
    ]
    (AUDIT_DIR / "REPAIR_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
