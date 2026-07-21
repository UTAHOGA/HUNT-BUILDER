"""Split 2017 general season deer preference rows into source components.

Audit-only output. This does not patch canonical truth, draw_results_long, or
DATABASE.csv.
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
OUT_DIR = REPO_ROOT / "audits" / "2017_general_season_deer_component_split" / datetime.now().strftime("%Y%m%d_%H%M%S")

SOURCE_FILE_MAP = {
    "17_general_deer.pdf": RAW_PDF_ROOT / "2017_PERMITS=2018_MODEL__G.S._BUCK_DEER_DRAW_RESULTS.pdf",
    "17_youth_general_deer.pdf": RAW_PDF_ROOT / "2017_PERMITS=2018_MODEL__YOUTH_G.S._DEER_DRAW_RESULTS.pdf",
    "17_dedicated_hunter_deer.pdf": RAW_PDF_ROOT / "2017_PERMITS=2018_MODEL__D.H._DEER_DRAW_RESULTS.pdf",
}


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def clean(value: object) -> str:
    return str(value or "").strip()


def norm(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", clean(value).upper()).strip("_")


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


def source_text(row: Dict[str, str]) -> str:
    return norm(
        " ".join(
            [
                row.get("source_file", ""),
                row.get("source_dataset", ""),
                row.get("hunt_class", ""),
                row.get("hunt_type", ""),
                row.get("raw_hunt_name", ""),
                row.get("hunt_name", ""),
            ]
        )
    )


def deer_component(row: Dict[str, str]) -> str:
    source_file = source_file_name(row)
    if source_file == "17_youth_general_deer.pdf":
        return "GENERAL_SEASON_DEER_YOUTH_SET_ASIDE"
    if source_file == "17_dedicated_hunter_deer.pdf":
        return "DEDICATED_HUNTER_DEER"
    return "GENERAL_SEASON_DEER"


def quota_layer(row: Dict[str, str]) -> str:
    if deer_component(row) == "GENERAL_SEASON_DEER_YOUTH_SET_ASIDE":
        return "YOUTH_SET_ASIDE_QUOTA_OVERLAY"
    return "ADULT_BASE_HUNT"


def draw_algorithm_family(row: Dict[str, str]) -> str:
    component = deer_component(row)
    if component == "DEDICATED_HUNTER_DEER":
        return "PREFERENCE_DEDICATED_HUNTER_DEER"
    return "PREFERENCE_GENERAL_SEASON_BUCK_DEER"


def routing_status(row: Dict[str, str]) -> str:
    text = source_text(row)
    component = deer_component(row)
    if source_file_name(row) not in SOURCE_FILE_MAP:
        return "REVIEW_REQUIRED_UNEXPECTED_SOURCE_FILE"
    if norm(row.get("species")) != "DEER":
        return "REVIEW_REQUIRED_UNEXPECTED_SPECIES"
    if norm(row.get("sex")) != "BUCK":
        return "REVIEW_REQUIRED_UNEXPECTED_SEX"
    if component == "GENERAL_SEASON_DEER_YOUTH_SET_ASIDE" and "YOUTH" not in text:
        return "REVIEW_REQUIRED_YOUTH_SOURCE_WITHOUT_YOUTH_LABEL"
    if component == "DEDICATED_HUNTER_DEER" and "DEDICATED_HUNTER" not in text:
        return "REVIEW_REQUIRED_DEDICATED_HUNTER_LABEL"
    if component == "GENERAL_SEASON_DEER" and "GENERAL_SEASON" not in text:
        return "REVIEW_REQUIRED_GENERAL_SEASON_LABEL"
    return "PASS_ROUTED"


def resolved_source_pdf(row: Dict[str, str]) -> str:
    mapped = SOURCE_FILE_MAP.get(source_file_name(row))
    if mapped and mapped.exists():
        return rel(mapped)
    return clean(row.get("source_file"))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_rows = [row for row in read_csv(RAW_CANDIDATE) if source_file_name(row) in SOURCE_FILE_MAP]
    if not raw_rows:
        raise RuntimeError(f"No general season deer source rows found in {RAW_CANDIDATE}")

    routed_rows: List[Dict[str, object]] = []
    for idx, row in enumerate(raw_rows, start=1):
        component = deer_component(row)
        status = routing_status(row)
        routed = dict(row)
        routed.update(
            {
                "deer_component": component,
                "deer_species_bucket": "DEER",
                "program_bucket": "DEDICATED_HUNTER" if component == "DEDICATED_HUNTER_DEER" else "GENERAL_SEASON",
                "preference_point_draw_flag": "TRUE",
                "youth_set_aside_overlay_flag": "TRUE" if component == "GENERAL_SEASON_DEER_YOUTH_SET_ASIDE" else "FALSE",
                "quota_layer": quota_layer(row),
                "draw_algorithm_family": draw_algorithm_family(row),
                "resolved_raw_source_pdf": resolved_source_pdf(row),
                "source_row_id": f"2017_GS_DEER_COMPONENT-{idx:06d}",
                "routing_status": status,
                "routing_notes": "General season deer is preference-point based. Youth G.S. deer is routed as a set-aside quota overlay from the G.S. allotment. Existing matrix columns are preserved; no website_matrix_* columns added.",
            }
        )
        routed_rows.append(routed)

    base_fields = list(raw_rows[0].keys())
    added_fields = [
        "deer_component",
        "deer_species_bucket",
        "program_bucket",
        "preference_point_draw_flag",
        "youth_set_aside_overlay_flag",
        "quota_layer",
        "draw_algorithm_family",
        "resolved_raw_source_pdf",
        "source_row_id",
        "routing_status",
        "routing_notes",
    ]
    fields = base_fields + [field for field in added_fields if field not in base_fields]

    routed_path = OUT_DIR / "2017_GENERAL_SEASON_DEER_COMPONENT_ROUTED_ROWS.csv"
    write_csv(routed_path, routed_rows, fields)

    source_audit_rows = []
    for source_file, group in sorted(group_by(routed_rows, "source_file").items()):
        hunts = {clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}
        pages = {clean(row.get("pdf_page")) for row in group if clean(row.get("pdf_page"))}
        pdf = SOURCE_FILE_MAP.get(Path(source_file).name)
        source_audit_rows.append(
            {
                "source_file": source_file,
                "resolved_raw_source_pdf": rel(pdf) if pdf else source_file,
                "raw_pdf_exists": "TRUE" if pdf and pdf.exists() else "FALSE",
                "source_row_count": len(group),
                "unique_hunt_codes": len(hunts),
                "source_page_count": len(pages),
                "sha256_raw_pdf": sha256_file(pdf) if pdf and pdf.exists() else "",
            }
        )
    source_audit_path = OUT_DIR / "2017_GENERAL_SEASON_DEER_SOURCE_FILE_AUDIT.csv"
    write_csv(
        source_audit_path,
        source_audit_rows,
        [
            "source_file",
            "resolved_raw_source_pdf",
            "raw_pdf_exists",
            "source_row_count",
            "unique_hunt_codes",
            "source_page_count",
            "sha256_raw_pdf",
        ],
    )

    split_root = OUT_DIR / "split_rows" / "GENERAL_SEASON_DEER"
    manifest_rows = []
    counts_rows = []
    for component, group in sorted(group_by(routed_rows, "deer_component").items()):
        out_path = split_root / component / f"2017_{component}_ROWS.csv"
        write_csv(out_path, group, fields)
        hunts = {clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}
        pages = {(clean(row.get("source_file")), clean(row.get("pdf_page"))) for row in group if clean(row.get("pdf_page"))}
        review_rows = sum(1 for row in group if row.get("routing_status") != "PASS_ROUTED")
        manifest_rows.append(
            {
                "deer_component": component,
                "split_path": f"GENERAL_SEASON_DEER/{component}",
                "output_path": rel(out_path),
                "row_count": len(group),
                "unique_hunt_codes": len(hunts),
                "source_page_count": len(pages),
                "review_rows": review_rows,
                "sha256": sha256_file(out_path),
                "routing_status": "PASS_ROUTED" if review_rows == 0 else "REVIEW_REQUIRED",
            }
        )
        counts_rows.append(
            {
                "deer_component": component,
                "program_bucket": clean(group[0].get("program_bucket")),
                "quota_layer": clean(group[0].get("quota_layer")),
                "draw_algorithm_family": clean(group[0].get("draw_algorithm_family")),
                "row_count": len(group),
                "unique_hunt_codes": len(hunts),
                "source_page_count": len(pages),
                "review_rows": review_rows,
            }
        )

    manifest_path = OUT_DIR / "2017_GENERAL_SEASON_DEER_COMPONENT_SPLIT_MANIFEST.csv"
    write_csv(
        manifest_path,
        manifest_rows,
        [
            "deer_component",
            "split_path",
            "output_path",
            "row_count",
            "unique_hunt_codes",
            "source_page_count",
            "review_rows",
            "sha256",
            "routing_status",
        ],
    )

    counts_path = OUT_DIR / "2017_GENERAL_SEASON_DEER_COMPONENT_COUNTS.csv"
    write_csv(
        counts_path,
        counts_rows,
        [
            "deer_component",
            "program_bucket",
            "quota_layer",
            "draw_algorithm_family",
            "row_count",
            "unique_hunt_codes",
            "source_page_count",
            "review_rows",
        ],
    )

    review_rows = [row for row in routed_rows if row.get("routing_status") != "PASS_ROUTED"]
    status = "PASS_WITH_REVIEW_REQUIRED" if review_rows else "PASS_GENERAL_SEASON_DEER_COMPONENT_SPLIT"

    reference_path = OUT_DIR / "2017_GENERAL_SEASON_DEER_COMPONENT_MATRIX_REFERENCE.md"
    reference_path.write_text(
        "\n".join(
            [
                "# 2017 General Season Deer Component Matrix Reference",
                "",
                "Matrix columns already exist and are preserved: `species`, `sex`, `hunt_type`, `weapon`, `hunt_class`.",
                "",
                "## Components",
                "",
                "- GENERAL_SEASON_DEER = adult/base G.S. buck deer preference-point draw rows.",
                "- GENERAL_SEASON_DEER_YOUTH_SET_ASIDE = youth G.S. deer set-aside quota overlay rows.",
                "- DEDICATED_HUNTER_DEER = Dedicated Hunter deer preference-point draw rows.",
                "",
                "Youth G.S. deer is not a separate species universe. It is a quota overlay drawn from the G.S. deer allotment first where source-proven.",
                "Dedicated Hunter deer stays separate from G.S. deer because the source PDF and draw algorithm family are distinct.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report_path = OUT_DIR / "2017_GENERAL_SEASON_DEER_COMPONENT_SPLIT_REPORT.md"
    report_path.write_text(
        "\n".join(
            [
                "# 2017 General Season Deer Component Split Report",
                "",
                f"report_timestamp: {datetime.now().isoformat(timespec='seconds')}",
                "",
                "## Boundary",
                "",
                "This is an audit-only split from raw/PDF-derived 2017 rows. It does not patch canonical_yearly, draw_results_long, DATABASE.csv, or prediction outputs.",
                "",
                "## Routing Rule",
                "",
                "General Season Deer and Youth General Season Deer are preference-point draw rows. Youth General Season Deer is a set-aside quota overlay that comes out of the G.S. allotment first. Dedicated Hunter Deer is also preference-point based but remains its own program component.",
                "",
                "## Counts",
                "",
                f"source_rows: {len(routed_rows)}",
                f"unique_hunt_codes: {len({clean(row.get('hunt_code')) for row in routed_rows if clean(row.get('hunt_code'))})}",
                f"component_count: {len({clean(row.get('deer_component')) for row in routed_rows if clean(row.get('deer_component'))})}",
                f"routing_review_rows: {len(review_rows)}",
                "",
                "## Output Files",
                "",
                f"- routed rows: {rel(routed_path)}",
                f"- split manifest: {rel(manifest_path)}",
                f"- component counts: {rel(counts_path)}",
                f"- source file audit: {rel(source_audit_path)}",
                f"- matrix reference: {rel(reference_path)}",
                "",
                f"GENERAL_SEASON_DEER_COMPONENT_SPLIT_STATUS={status}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary_by_component = {row["deer_component"]: row for row in counts_rows}
    terminal = "\n".join(
        [
            f"GENERAL_SEASON_DEER_COMPONENT_SPLIT_OUTPUT_DIR={OUT_DIR}",
            f"ROUTED_ROWS={routed_path}",
            f"SPLIT_MANIFEST={manifest_path}",
            f"COMPONENT_COUNTS={counts_path}",
            f"SOURCE_FILE_AUDIT={source_audit_path}",
            f"SPLIT_REPORT={report_path}",
            f"MATRIX_REFERENCE={reference_path}",
            f"GENERAL_SEASON_DEER_SOURCE_ROWS={len(routed_rows)}",
            f"GENERAL_SEASON_DEER_UNIQUE_HUNT_CODES={len({clean(row.get('hunt_code')) for row in routed_rows if clean(row.get('hunt_code'))})}",
            f"GENERAL_SEASON_DEER_ROWS={summary_by_component['GENERAL_SEASON_DEER']['row_count']}",
            f"GENERAL_SEASON_DEER_YOUTH_SET_ASIDE_ROWS={summary_by_component['GENERAL_SEASON_DEER_YOUTH_SET_ASIDE']['row_count']}",
            f"DEDICATED_HUNTER_DEER_ROWS={summary_by_component['DEDICATED_HUNTER_DEER']['row_count']}",
            f"ROUTING_REVIEW_ROWS={len(review_rows)}",
            "YOUTH_SET_ASIDE_OVERLAY=TRUE",
            "PREFERENCE_POINT_DRAW_FAMILY=TRUE",
            f"GENERAL_SEASON_DEER_COMPONENT_SPLIT_STATUS={status}",
            "NEXT_ACTION=REVIEW_BEFORE_PROMOTION_OR_PATCHING",
        ]
    )
    (OUT_DIR / "FINAL_TERMINAL_OUTPUT.txt").write_text(terminal + "\n", encoding="utf-8")
    print(terminal)
    return 0


def group_by(rows: Iterable[Dict[str, object]], field: str) -> Dict[str, List[Dict[str, object]]]:
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[clean(row.get(field))].append(row)
    return grouped


if __name__ == "__main__":
    raise SystemExit(main())
