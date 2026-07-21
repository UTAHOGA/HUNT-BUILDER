"""Split 2017 antlerless rows into adult/youth and CWMU components.

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
OUT_DIR = REPO_ROOT / "audits" / "2017_antlerless_component_split" / datetime.now().strftime("%Y%m%d_%H%M%S")

SOURCE_FILES = {"17_antlerless_points.pdf", "17_antlerless_youth_points.pdf"}


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


def source_text(row: Dict[str, str]) -> str:
    return norm(" ".join([row.get("source_file", ""), row.get("source_dataset", ""), row.get("hunt_class", ""), row.get("raw_hunt_name", ""), row.get("hunt_name", ""), row.get("sex", "")]))


def antlerless_species_bucket(row: Dict[str, str]) -> str:
    text = source_text(row)
    if "PRONGHORN" in text or "DOE_PRONGHORN" in text:
        return "DOE_PRONGHORN"
    if "MOOSE" in text:
        return "ANTLERLESS_MOOSE"
    if "ELK" in text:
        return "ANTLERLESS_ELK"
    if "DEER" in text or clean(row.get("hunt_code")).upper().startswith("DA"):
        return "ANTLERLESS_DEER"
    if "ROCKY" in text and ("BIGHORN" in text or "SHEEP" in text):
        return "EWE_ROCKY_MOUNTAIN_BIGHORN_SHEEP"
    if "DESERT" in text and ("BIGHORN" in text or "SHEEP" in text):
        return "EWE_DESERT_BIGHORN_SHEEP"
    return "UNKNOWN_ANTLERLESS_REVIEW_REQUIRED"


def youth_flag(row: Dict[str, str]) -> bool:
    return clean(row.get("source_file")) == "17_antlerless_youth_points.pdf" or "YOUTH" in source_text(row)


def cwmu_flag(row: Dict[str, str]) -> bool:
    return "CWMU" in source_text(row)


def antlerless_component(row: Dict[str, str]) -> str:
    y = youth_flag(row)
    c = cwmu_flag(row)
    if y and c:
        return "ANTLERLESS_YOUTH_CWMU"
    if y:
        return "ANTLERLESS_YOUTH"
    if c:
        return "ANTLERLESS_CWMU"
    return "ANTLERLESS"


def species_column_conflict(row: Dict[str, str], bucket: str) -> str:
    species = norm(row.get("species"))
    expected = {
        "ANTLERLESS_DEER": "DEER",
        "ANTLERLESS_ELK": "ELK",
        "DOE_PRONGHORN": "PRONGHORN",
        "ANTLERLESS_MOOSE": "MOOSE",
    }.get(bucket, "")
    if expected and species and species != expected:
        return "TRUE"
    return "FALSE"


def resolved_source_pdf(row: Dict[str, str]) -> str:
    source_file = clean(row.get("source_file"))
    bucket = antlerless_species_bucket(row)
    component = antlerless_component(row)
    candidates = []
    if component == "ANTLERLESS_CWMU":
        candidates.append(RAW_PDF_ROOT / "CWMU" / "ANTLERLESS CWMU" / f"2017_PERMITS=2018_MODEL__CWMU_{bucket}_DRAW_RESULTS.pdf")
    elif component == "ANTLERLESS_YOUTH_CWMU":
        candidates.append(RAW_PDF_ROOT / "CWMU" / "ANTLERLESS CWMU" / f"2017_PERMITS=2018_MODEL__CWMU_YOUTH_{bucket}_DRAW_RESULTS.pdf")
    elif component == "ANTLERLESS_YOUTH":
        candidates.append(RAW_PDF_ROOT / f"2017_PERMITS=2018_MODEL__YOUTH_{bucket}_DRAW_RESULTS.pdf")
    else:
        candidates.append(RAW_PDF_ROOT / f"2017_PERMITS=2018_MODEL__{bucket}_DRAW_RESULTS.pdf")
    # Doe pronghorn source filenames use PRONGHORN, not DOE_PRONGHORN.
    more = []
    for candidate in candidates:
        more.append(candidate)
        more.append(Path(str(candidate).replace("DOE_PRONGHORN", "ANTLERLESS_PRONGHORN")))
        more.append(Path(str(candidate).replace("DOE_PRONGHORN", "YOUTH_ANTLERLESS_PRONGHORN")))
    for candidate in more:
        if candidate.exists():
            return rel(candidate)
    return source_file


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_rows = [row for row in read_csv(RAW_CANDIDATE) if clean(row.get("source_file")) in SOURCE_FILES]
    routed_rows: List[Dict[str, object]] = []
    for idx, row in enumerate(raw_rows, start=1):
        bucket = antlerless_species_bucket(row)
        component = antlerless_component(row)
        conflict = species_column_conflict(row, bucket)
        routed = dict(row)
        routed.update(
            {
                "antlerless_component": component,
                "antlerless_species_bucket": bucket,
                "cwmu_flag": "TRUE" if cwmu_flag(row) else "FALSE",
                "youth_set_aside_overlay_flag": "TRUE" if youth_flag(row) else "FALSE",
                "quota_layer": "YOUTH_SET_ASIDE_QUOTA_OVERLAY" if youth_flag(row) else "ADULT_BASE_HUNT",
                "resolved_raw_source_pdf": resolved_source_pdf(row),
                "source_row_id": f"2017_ANTLERLESS_COMPONENT-{idx:06d}",
                "species_column_conflict_flag": conflict,
                "routing_status": "REVIEW_REQUIRED_SPECIES_COLUMN_CONFLICT" if conflict == "TRUE" else ("PASS_ROUTED" if bucket != "UNKNOWN_ANTLERLESS_REVIEW_REQUIRED" else "REVIEW_REQUIRED_UNKNOWN_ANTLERLESS_SPECIES"),
                "routing_notes": "Routed from source_file + hunt_class/raw_hunt_name. Existing matrix columns are preserved; no website_matrix_* columns added.",
            }
        )
        routed_rows.append(routed)

    base_fields = list(raw_rows[0].keys()) if raw_rows else []
    added_fields = [
        "antlerless_component",
        "antlerless_species_bucket",
        "cwmu_flag",
        "youth_set_aside_overlay_flag",
        "quota_layer",
        "resolved_raw_source_pdf",
        "source_row_id",
        "species_column_conflict_flag",
        "routing_status",
        "routing_notes",
    ]
    fields = base_fields + [field for field in added_fields if field not in base_fields]

    routed_path = OUT_DIR / "2017_ANTLERLESS_COMPONENT_ROUTED_ROWS.csv"
    write_csv(routed_path, routed_rows, fields)

    groups: Dict[tuple, List[Dict[str, object]]] = defaultdict(list)
    for row in routed_rows:
        groups[(clean(row["antlerless_component"]), clean(row["antlerless_species_bucket"]))].append(row)

    split_root = OUT_DIR / "split_rows" / "ANTLERLESS"
    manifest_rows = []
    counts_rows = []
    for (component, bucket), group in sorted(groups.items()):
        out_path = split_root / component / bucket / f"2017_{component}_{bucket}_ROWS.csv"
        write_csv(out_path, group, fields)
        hunts = {clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}
        pages = {(clean(row.get("source_file")), clean(row.get("pdf_page"))) for row in group if clean(row.get("pdf_page"))}
        review_rows = sum(1 for row in group if row.get("routing_status") != "PASS_ROUTED")
        manifest_rows.append(
            {
                "antlerless_component": component,
                "antlerless_species_bucket": bucket,
                "split_path": f"ANTLERLESS/{component}/{bucket}",
                "output_path": rel(out_path),
                "row_count": len(group),
                "unique_hunt_codes": len(hunts),
                "source_page_count": len(pages),
                "species_column_conflict_rows": sum(1 for row in group if row.get("species_column_conflict_flag") == "TRUE"),
                "routing_review_rows": review_rows,
                "sha256": sha256_file(out_path),
                "routing_status": "PASS_ROUTED" if review_rows == 0 else "REVIEW_REQUIRED",
            }
        )
        counts_rows.append(
            {
                "antlerless_component": component,
                "antlerless_species_bucket": bucket,
                "row_count": len(group),
                "unique_hunt_codes": len(hunts),
                "source_page_count": len(pages),
                "species_column_conflict_rows": sum(1 for row in group if row.get("species_column_conflict_flag") == "TRUE"),
                "routing_review_rows": review_rows,
            }
        )

    manifest_path = OUT_DIR / "2017_ANTLERLESS_COMPONENT_SPLIT_MANIFEST.csv"
    write_csv(
        manifest_path,
        manifest_rows,
        [
            "antlerless_component",
            "antlerless_species_bucket",
            "split_path",
            "output_path",
            "row_count",
            "unique_hunt_codes",
            "source_page_count",
            "species_column_conflict_rows",
            "routing_review_rows",
            "sha256",
            "routing_status",
        ],
    )
    counts_path = OUT_DIR / "2017_ANTLERLESS_COMPONENT_SPLIT_COUNTS.csv"
    write_csv(
        counts_path,
        counts_rows,
        [
            "antlerless_component",
            "antlerless_species_bucket",
            "row_count",
            "unique_hunt_codes",
            "source_page_count",
            "species_column_conflict_rows",
            "routing_review_rows",
        ],
    )

    component_summary = []
    for component in ["ANTLERLESS", "ANTLERLESS_CWMU", "ANTLERLESS_YOUTH", "ANTLERLESS_YOUTH_CWMU"]:
        group = [row for row in routed_rows if row["antlerless_component"] == component]
        component_summary.append(
            {
                "antlerless_component": component,
                "row_count": len(group),
                "unique_hunt_codes": len({clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}),
                "species_bucket_count": len({clean(row.get("antlerless_species_bucket")) for row in group if clean(row.get("antlerless_species_bucket"))}),
                "species_column_conflict_rows": sum(1 for row in group if row.get("species_column_conflict_flag") == "TRUE"),
                "routing_review_rows": sum(1 for row in group if row.get("routing_status") != "PASS_ROUTED"),
            }
        )
    component_summary_path = OUT_DIR / "2017_ANTLERLESS_COMPONENT_SUMMARY.csv"
    write_csv(component_summary_path, component_summary, ["antlerless_component", "row_count", "unique_hunt_codes", "species_bucket_count", "species_column_conflict_rows", "routing_review_rows"])

    review_rows = [row for row in routed_rows if row["routing_status"] != "PASS_ROUTED"]
    status = "PASS_WITH_REVIEW_REQUIRED" if review_rows else "PASS_ANTLERLESS_COMPONENT_SPLIT"

    reference_path = OUT_DIR / "2017_ANTLERLESS_COMPONENT_MATRIX_REFERENCE.md"
    reference_path.write_text(
        "\n".join(
            [
                "# 2017 Antlerless Component Matrix Reference",
                "",
                "Matrix columns already exist and are preserved: `species`, `sex`, `hunt_type`, `weapon`, `hunt_class`.",
                "",
                "## Components",
                "",
                "- ANTLERLESS = adult/base antlerless, non-CWMU",
                "- ANTLERLESS_CWMU = adult/base antlerless, CWMU",
                "- ANTLERLESS_YOUTH = youth set-aside quota overlay, non-CWMU",
                "- ANTLERLESS_YOUTH_CWMU = youth set-aside quota overlay, CWMU",
                "",
                "Youth is a set-aside quota overlay on the base antlerless hunt where source-proven.",
                "Rows with species-column conflicts are routed by `hunt_class` and `raw_hunt_name`, then flagged for review.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report_path = OUT_DIR / "2017_ANTLERLESS_COMPONENT_SPLIT_REPORT.md"
    report_path.write_text(
        "\n".join(
            [
                "# 2017 Antlerless Component Split Report",
                "",
                f"report_timestamp: {datetime.now().isoformat(timespec='seconds')}",
                "",
                "## Boundary",
                "",
                "This is an audit-only split from raw/PDF-derived 2017 rows. It does not patch canonical_yearly, draw_results_long, DATABASE.csv, or prediction outputs.",
                "",
                "## Counts",
                "",
                f"source_rows: {len(routed_rows)}",
                f"unique_hunt_codes: {len({clean(row.get('hunt_code')) for row in routed_rows if clean(row.get('hunt_code'))})}",
                f"component_count: 4",
                f"species_column_conflict_rows: {sum(1 for row in routed_rows if row.get('species_column_conflict_flag') == 'TRUE')}",
                f"routing_review_rows: {len(review_rows)}",
                "",
                "## Output Files",
                "",
                f"- routed rows: {rel(routed_path)}",
                f"- split manifest: {rel(manifest_path)}",
                f"- split counts: {rel(counts_path)}",
                f"- component summary: {rel(component_summary_path)}",
                f"- matrix reference: {rel(reference_path)}",
                "",
                f"ANTLERLESS_COMPONENT_SPLIT_STATUS={status}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary_by_component = {row["antlerless_component"]: row for row in component_summary}
    terminal = "\n".join(
        [
            f"ANTLERLESS_COMPONENT_SPLIT_OUTPUT_DIR={OUT_DIR}",
            f"ROUTED_ROWS={routed_path}",
            f"SPLIT_MANIFEST={manifest_path}",
            f"SPLIT_COUNTS={counts_path}",
            f"COMPONENT_SUMMARY={component_summary_path}",
            f"SPLIT_REPORT={report_path}",
            f"MATRIX_REFERENCE={reference_path}",
            f"ANTLERLESS_SOURCE_ROWS={len(routed_rows)}",
            f"ANTLERLESS_UNIQUE_HUNT_CODES={len({clean(row.get('hunt_code')) for row in routed_rows if clean(row.get('hunt_code'))})}",
            f"ANTLERLESS_ROWS={summary_by_component['ANTLERLESS']['row_count']}",
            f"ANTLERLESS_CWMU_ROWS={summary_by_component['ANTLERLESS_CWMU']['row_count']}",
            f"ANTLERLESS_YOUTH_ROWS={summary_by_component['ANTLERLESS_YOUTH']['row_count']}",
            f"ANTLERLESS_YOUTH_CWMU_ROWS={summary_by_component['ANTLERLESS_YOUTH_CWMU']['row_count']}",
            f"SPECIES_COLUMN_CONFLICT_ROWS={sum(1 for row in routed_rows if row.get('species_column_conflict_flag') == 'TRUE')}",
            f"ANTLERLESS_COMPONENT_SPLIT_STATUS={status}",
            "NEXT_ACTION=REVIEW_SPECIES_COLUMN_CONFLICT_ROWS_BEFORE_PROMOTION_OR_PATCHING",
        ]
    )
    (OUT_DIR / "FINAL_TERMINAL_OUTPUT.txt").write_text(terminal + "\n", encoding="utf-8")
    print(terminal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
