"""Split 2017 bear, cougar, and turkey rows into source-proven components.

Audit-only output. This does not patch canonical truth, draw_results_long,
DATABASE.csv, or prediction outputs.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


REPO_ROOT = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
RAW_CANDIDATE = REPO_ROOT / "audits" / "draw_truth_2017_source_family_split" / "20260705_142833" / "draw_results_2017_for_2018_canonical_yearly_draw_results_CANDIDATE.after_family_split_fix.csv"
RAW_PDF_ROOT = REPO_ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2017" / "pdf" / "draw_odds"
DATABASE_2026 = REPO_ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
OUT_DIR = REPO_ROOT / "audits" / "2017_bear_cougar_turkey_component_split" / datetime.now().strftime("%Y%m%d_%H%M%S")

SOURCE_FILES = {
    "17_bonus_points.pdf",
    "17_drawing_odds.pdf",
    "2017_cougar_odds_report.pdf",
    "2017_turkey_bonus_points_and_draw_results.pdf",
}

SOURCE_PDF_MAP = {
    "17_bonus_points.pdf": RAW_PDF_ROOT / "2017_PERMITS=2018_MODEL__BLACK_BEAR_DRAW_RESULTS.pdf",
    "17_drawing_odds.pdf": RAW_PDF_ROOT / "2017_PERMITS=2018_MODEL__BLACK_BEAR_DRAW_RESULTS.pdf",
    "2017_cougar_odds_report.pdf": RAW_PDF_ROOT / "2017_PERMITS=2018_MODEL__COUGAR_DRAW_RESULTS.pdf",
    "2017_turkey_bonus_points_and_draw_results.pdf": RAW_PDF_ROOT / "2017_PERMITS=2018_MODEL__TURKEY_DRAW_RESULTS.pdf",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def norm(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", clean(value).upper()).strip("_")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Iterable[Dict[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def source_file_name(row: Dict[str, str]) -> str:
    return Path(clean(row.get("source_file"))).name


def row_text(row: Dict[str, str]) -> str:
    return norm(
        " ".join(
            [
                row.get("source_file", ""),
                row.get("source_dataset", ""),
                row.get("hunt_class", ""),
                row.get("draw_system_type", ""),
                row.get("hunt_type", ""),
                row.get("raw_hunt_name", ""),
                row.get("hunt_name", ""),
                row.get("species", ""),
            ]
        )
    )


def all_value_text(row: Dict[str, str]) -> str:
    return norm(" ".join(clean(value) for value in row.values()))


def special_component(row: Dict[str, str]) -> str:
    source_file = source_file_name(row)
    text = row_text(row)
    if source_file == "17_bonus_points.pdf" and "PURSUIT" in text:
        return "BLACK_BEAR_PURSUIT_MAX_WEIGHTED_SPLIT"
    if source_file == "17_bonus_points.pdf":
        return "BLACK_BEAR_MAX_WEIGHTED_SPLIT"
    if source_file == "17_drawing_odds.pdf":
        return "BLACK_BEAR_HUNT_CHOICE_ROW_ODDS"
    if source_file == "2017_cougar_odds_report.pdf":
        return "COUGAR_MAX_WEIGHTED_SPLIT"
    if source_file == "2017_turkey_bonus_points_and_draw_results.pdf":
        return "TURKEY_BONUS_POINT_DRAW"
    return "REVIEW_REQUIRED_UNKNOWN_SPECIAL_COMPONENT"


def source_proven_family(row: Dict[str, str]) -> str:
    component = special_component(row)
    if component.startswith("BLACK_BEAR"):
        return "BLACK_BEAR"
    if component.startswith("COUGAR"):
        return "COUGAR"
    if component.startswith("TURKEY"):
        return "TURKEY"
    return "UNKNOWN"


def scoring_disposition(row: Dict[str, str]) -> str:
    component = special_component(row)
    if component == "BLACK_BEAR_HUNT_CHOICE_ROW_ODDS":
        return "SUPPORTING_HUNT_CHOICE_ODDS_ROW"
    return "POINT_LEVEL_DRAW_RESULT"


def resolved_source_pdf(row: Dict[str, str]) -> str:
    pdf = SOURCE_PDF_MAP.get(source_file_name(row))
    if pdf and pdf.exists():
        return rel(pdf)
    return clean(row.get("source_file"))


def database_reference_counts() -> Dict[str, int]:
    counts = {
        "BLACK_BEAR_HARVEST_OBJECTIVE": 0,
        "TURKEY_YOUTH": 0,
    }
    if not DATABASE_2026.exists():
        return counts
    for row in read_csv(DATABASE_2026):
        text = all_value_text(row)
        if "HARVEST_OBJECTIVE" in text or "HARVEST_OBJECTIVE_UNITS" in text or "HARVEST OBJECTIVE" in text:
            counts["BLACK_BEAR_HARVEST_OBJECTIVE"] += 1
        if "YOUTH" in text and "TURKEY" in text:
            counts["TURKEY_YOUTH"] += 1
    return counts


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_rows = [row for row in read_csv(RAW_CANDIDATE) if source_file_name(row) in SOURCE_FILES]
    routed_rows: List[Dict[str, object]] = []
    for idx, row in enumerate(raw_rows, start=1):
        component = special_component(row)
        routed = dict(row)
        routed.update(
            {
                "special_species_component": component,
                "source_proven_family": source_proven_family(row),
                "source_proven_species_bucket": "BLACK_BEAR" if component.startswith("BLACK_BEAR") else ("COUGAR" if component.startswith("COUGAR") else "TURKEY"),
                "algorithm_family": clean(row.get("draw_system_type")),
                "scoring_disposition": scoring_disposition(row),
                "resolved_raw_source_pdf": resolved_source_pdf(row),
                "source_row_id": f"2017_SPECIAL_SPECIES-{idx:06d}",
                "routing_status": "PASS_SOURCE_PROVEN_COMPONENT",
                "routing_notes": "Routed only from source-proven 2017 bear/cougar/turkey draw-odds rows. Youth turkey and harvest-objective are not synthesized from later-year sources.",
            }
        )
        routed_rows.append(routed)

    base_fields = list(raw_rows[0].keys()) if raw_rows else []
    added_fields = [
        "special_species_component",
        "source_proven_family",
        "source_proven_species_bucket",
        "algorithm_family",
        "scoring_disposition",
        "resolved_raw_source_pdf",
        "source_row_id",
        "routing_status",
        "routing_notes",
    ]
    fields = base_fields + [field for field in added_fields if field not in base_fields]

    routed_path = OUT_DIR / "2017_BEAR_COUGAR_TURKEY_COMPONENT_ROUTED_ROWS.csv"
    write_csv(routed_path, routed_rows, fields)

    split_root = OUT_DIR / "split_rows"
    manifest_rows = []
    counts_rows = []
    groups: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in routed_rows:
        groups[clean(row["special_species_component"])].append(row)
    for component, group in sorted(groups.items()):
        out_path = split_root / component / f"2017_{component}_ROWS.csv"
        write_csv(out_path, group, fields)
        hunts = {clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}
        pages = {(clean(row.get("source_file")), clean(row.get("pdf_page"))) for row in group if clean(row.get("pdf_page"))}
        source_files = sorted({clean(row.get("source_file")) for row in group if clean(row.get("source_file"))})
        row = {
            "special_species_component": component,
            "source_proven_family": clean(group[0].get("source_proven_family")),
            "algorithm_family": clean(group[0].get("algorithm_family")),
            "scoring_disposition": clean(group[0].get("scoring_disposition")),
            "source_files": ";".join(source_files),
            "output_path": rel(out_path),
            "row_count": len(group),
            "unique_hunt_codes": len(hunts),
            "source_page_count": len(pages),
            "sha256": sha256_file(out_path),
            "routing_status": "PASS_SOURCE_PROVEN_COMPONENT",
        }
        manifest_rows.append(row)
        counts_rows.append({k: row[k] for k in ["special_species_component", "source_proven_family", "algorithm_family", "scoring_disposition", "row_count", "unique_hunt_codes", "source_page_count", "routing_status"]})

    manifest_path = OUT_DIR / "2017_BEAR_COUGAR_TURKEY_COMPONENT_MANIFEST.csv"
    write_csv(
        manifest_path,
        manifest_rows,
        ["special_species_component", "source_proven_family", "algorithm_family", "scoring_disposition", "source_files", "output_path", "row_count", "unique_hunt_codes", "source_page_count", "sha256", "routing_status"],
    )

    counts_path = OUT_DIR / "2017_BEAR_COUGAR_TURKEY_COMPONENT_COUNTS.csv"
    write_csv(
        counts_path,
        counts_rows,
        ["special_species_component", "source_proven_family", "algorithm_family", "scoring_disposition", "row_count", "unique_hunt_codes", "source_page_count", "routing_status"],
    )

    db_counts = database_reference_counts()
    raw_texts = [row_text(row) for row in raw_rows]
    source_status_rows = [
        {
            "requested_component": "TURKEY_YOUTH",
            "raw_2017_draw_odds_row_hits": sum(1 for text in raw_texts if "YOUTH" in text and "TURKEY" in text),
            "database_2026_reference_rows": db_counts["TURKEY_YOUTH"],
            "source_status": "ABSENT_FROM_2017_OFFICIAL_DRAW_ODDS",
            "scoring_disposition": "DO_NOT_SYNTHESIZE_PRE_2019_YOUTH_TURKEY",
            "notes": "2017 source rows contain bonus turkey only. Youth turkey must remain absent unless a separate 2017 official youth source is found.",
        },
        {
            "requested_component": "BLACK_BEAR_HARVEST_OBJECTIVE",
            "raw_2017_draw_odds_row_hits": sum(1 for text in raw_texts if "HARVEST_OBJECTIVE" in text or "HARVEST OBJECTIVE" in text),
            "database_2026_reference_rows": db_counts["BLACK_BEAR_HARVEST_OBJECTIVE"],
            "source_status": "SOURCE_REQUIRED_NOT_PRESENT_AS_2017_DRAW_ODDS",
            "scoring_disposition": "NON_SCORABLE_PERMIT_OR_ALLOTMENT_REFERENCE_UNLESS_YEAR_SOURCE_PROVES_DRAW_ODDS",
            "notes": "Harvest-objective is visible as a later permit/reference concept, but no 2017 draw-odds rows were found in the raw 2017 draw-odds source package.",
        },
    ]
    source_status_path = OUT_DIR / "2017_BEAR_COUGAR_TURKEY_SOURCE_STATUS.csv"
    write_csv(
        source_status_path,
        source_status_rows,
        ["requested_component", "raw_2017_draw_odds_row_hits", "database_2026_reference_rows", "source_status", "scoring_disposition", "notes"],
    )

    report_path = OUT_DIR / "2017_BEAR_COUGAR_TURKEY_COMPONENT_SPLIT_REPORT.md"
    summary = {row["special_species_component"]: row for row in counts_rows}
    status = "PASS_WITH_SOURCE_REVIEW_REQUIRED" if any(int(row["raw_2017_draw_odds_row_hits"]) == 0 for row in source_status_rows) else "PASS_SPECIAL_SPECIES_COMPONENT_SPLIT"
    report_path.write_text(
        "\n".join(
            [
                "# 2017 Bear Cougar Turkey Component Split Report",
                "",
                f"report_timestamp: {datetime.now().isoformat(timespec='seconds')}",
                "",
                "## Boundary",
                "",
                "This is an audit-only split from repo-visible raw/PDF-derived 2017 rows. It does not patch canonical_yearly, draw_results_long, DATABASE.csv, or prediction outputs.",
                "",
                "## Source-Proven Components",
                "",
                f"BLACK_BEAR_PURSUIT_MAX_WEIGHTED_SPLIT rows: {summary.get('BLACK_BEAR_PURSUIT_MAX_WEIGHTED_SPLIT', {}).get('row_count', 0)}",
                f"BLACK_BEAR_MAX_WEIGHTED_SPLIT rows: {summary.get('BLACK_BEAR_MAX_WEIGHTED_SPLIT', {}).get('row_count', 0)}",
                f"BLACK_BEAR_HUNT_CHOICE_ROW_ODDS rows: {summary.get('BLACK_BEAR_HUNT_CHOICE_ROW_ODDS', {}).get('row_count', 0)}",
                f"COUGAR_MAX_WEIGHTED_SPLIT rows: {summary.get('COUGAR_MAX_WEIGHTED_SPLIT', {}).get('row_count', 0)}",
                f"TURKEY_BONUS_POINT_DRAW rows: {summary.get('TURKEY_BONUS_POINT_DRAW', {}).get('row_count', 0)}",
                "",
                "## Source-Required / Not Synthesized",
                "",
                "TURKEY_YOUTH is absent from the 2017 official draw-odds rows and is not synthesized.",
                "BLACK_BEAR_HARVEST_OBJECTIVE is not present as 2017 draw-odds rows in this source package; it remains a source-required non-scorable/reference concept unless year-specific source is provided.",
                "",
                "## Output Files",
                "",
                f"- routed rows: {rel(routed_path)}",
                f"- manifest: {rel(manifest_path)}",
                f"- counts: {rel(counts_path)}",
                f"- source status: {rel(source_status_path)}",
                "",
                f"2017_BEAR_COUGAR_TURKEY_COMPONENT_SPLIT_STATUS={status}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    terminal = "\n".join(
        [
            f"2017_BEAR_COUGAR_TURKEY_COMPONENT_SPLIT_OUTPUT_DIR={OUT_DIR}",
            f"ROUTED_ROWS={routed_path}",
            f"MANIFEST={manifest_path}",
            f"COUNTS={counts_path}",
            f"SOURCE_STATUS={source_status_path}",
            f"SPLIT_REPORT={report_path}",
            f"BLACK_BEAR_PURSUIT_ROWS={summary.get('BLACK_BEAR_PURSUIT_MAX_WEIGHTED_SPLIT', {}).get('row_count', 0)}",
            f"BLACK_BEAR_PURSUIT_UNIQUE_HUNT_CODES={summary.get('BLACK_BEAR_PURSUIT_MAX_WEIGHTED_SPLIT', {}).get('unique_hunt_codes', 0)}",
            f"BLACK_BEAR_MAX_SPLIT_ROWS={summary.get('BLACK_BEAR_MAX_WEIGHTED_SPLIT', {}).get('row_count', 0)}",
            f"BLACK_BEAR_MAX_SPLIT_UNIQUE_HUNT_CODES={summary.get('BLACK_BEAR_MAX_WEIGHTED_SPLIT', {}).get('unique_hunt_codes', 0)}",
            f"BLACK_BEAR_HUNT_CHOICE_ROW_ODDS_ROWS={summary.get('BLACK_BEAR_HUNT_CHOICE_ROW_ODDS', {}).get('row_count', 0)}",
            f"COUGAR_MAX_SPLIT_ROWS={summary.get('COUGAR_MAX_WEIGHTED_SPLIT', {}).get('row_count', 0)}",
            f"COUGAR_MAX_SPLIT_UNIQUE_HUNT_CODES={summary.get('COUGAR_MAX_WEIGHTED_SPLIT', {}).get('unique_hunt_codes', 0)}",
            f"TURKEY_BONUS_ROWS={summary.get('TURKEY_BONUS_POINT_DRAW', {}).get('row_count', 0)}",
            f"TURKEY_BONUS_UNIQUE_HUNT_CODES={summary.get('TURKEY_BONUS_POINT_DRAW', {}).get('unique_hunt_codes', 0)}",
            "TURKEY_YOUTH_STATUS=ABSENT_FROM_2017_OFFICIAL_DRAW_ODDS",
            "BLACK_BEAR_HARVEST_OBJECTIVE_STATUS=SOURCE_REQUIRED_NOT_PRESENT_AS_2017_DRAW_ODDS",
            f"2017_BEAR_COUGAR_TURKEY_COMPONENT_SPLIT_STATUS={status}",
            "NEXT_ACTION=REVIEW_SOURCE_STATUS_BEFORE_PROMOTION_OR_PATCHING",
        ]
    )
    (OUT_DIR / "FINAL_TERMINAL_OUTPUT.txt").write_text(terminal + "\n", encoding="utf-8")
    print(terminal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
