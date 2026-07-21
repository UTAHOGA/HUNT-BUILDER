"""Split 2017 antlerless point rows by species and CWMU partition.

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
SOURCE_PDF = REPO_ROOT / "data_truth" / "draw_results_truth" / "raw_pdfs" / "2017_PERMITS=2018_MODEL" / "Parent Files" / "17_antlerless_points.pdf"
RAW_CANDIDATE = REPO_ROOT / "audits" / "draw_truth_2017_source_family_split" / "20260705_142833" / "draw_results_2017_for_2018_canonical_yearly_draw_results_CANDIDATE.after_family_split_fix.csv"
OUT_DIR = REPO_ROOT / "audits" / "2017_antlerless_points_species_cwmu_split" / datetime.now().strftime("%Y%m%d_%H%M%S")


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


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


def page_count(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        return str(len(PdfReader(str(path)).pages))
    except Exception:
        return ""


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


def antlerless_species_bucket(row: Dict[str, str]) -> str:
    species = norm(row.get("species"))
    sex = norm(row.get("sex"))
    text = norm(" ".join([row.get("raw_hunt_name", ""), row.get("hunt_name", ""), row.get("hunt_class", "")]))
    if species == "DEER":
        return "ANTLERLESS_DEER"
    if species == "ELK":
        return "ANTLERLESS_ELK"
    if species == "PRONGHORN" or "DOE_PRONGHORN" in text or sex == "DOE":
        return "DOE_PRONGHORN"
    if species == "MOOSE":
        return "ANTLERLESS_MOOSE"
    if "ROCKY" in text and ("BIGHORN" in text or "SHEEP" in text):
        return "EWE_ROCKY_MOUNTAIN_BIGHORN_SHEEP"
    if "DESERT" in text and ("BIGHORN" in text or "SHEEP" in text):
        return "EWE_DESERT_BIGHORN_SHEEP"
    if "BIGHORN" in text or "SHEEP" in text:
        return "EWE_BIGHORN_SHEEP"
    return "UNKNOWN_ANTLERLESS_REVIEW_REQUIRED"


def cwmu_partition(row: Dict[str, str]) -> str:
    text = norm(" ".join([row.get("raw_hunt_name", ""), row.get("hunt_name", ""), row.get("hunt_type", ""), row.get("hunt_class", "")]))
    return "CWMU" if "CWMU" in text else "NON_CWMU"


def routing_status(row: Dict[str, str]) -> str:
    bucket = antlerless_species_bucket(row)
    if bucket == "UNKNOWN_ANTLERLESS_REVIEW_REQUIRED":
        return "REVIEW_REQUIRED_UNKNOWN_ANTLERLESS_SPECIES"
    if norm(row.get("sex")) not in {"ANTLERLESS", "DOE", "EWE"}:
        return "REVIEW_REQUIRED_NON_ANTLERLESS_SEX_LABEL"
    return "PASS_ROUTED"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [row for row in read_csv(RAW_CANDIDATE) if clean(row.get("source_file")) == "17_antlerless_points.pdf"]
    if not rows:
        raise SystemExit("No 17_antlerless_points.pdf rows found in raw-derived candidate")

    routed_rows: List[Dict[str, object]] = []
    for idx, row in enumerate(rows, start=1):
        bucket = antlerless_species_bucket(row)
        partition = cwmu_partition(row)
        routed = dict(row)
        routed.update(
            {
                "matrix_source_pdf": rel(SOURCE_PDF),
                "matrix_source_pdf_sha256": sha256_file(SOURCE_PDF),
                "antlerless_species_bucket": bucket,
                "cwmu_partition": partition,
                "cwmu_flag": "TRUE" if partition == "CWMU" else "FALSE",
                "split_path": f"ANTLERLESS/{partition}/{bucket}",
                "source_row_id": f"2017_ANTLERLESS_MATRIX-{idx:06d}",
                "routing_status": routing_status(row),
                "routing_notes": "Antlerless species split uses existing species/sex/hunt_type/weapon/hunt_class columns; CWMU is separated by source-proven label.",
            }
        )
        routed_rows.append(routed)

    base_fields = list(rows[0].keys())
    added_fields = [
        "matrix_source_pdf",
        "matrix_source_pdf_sha256",
        "antlerless_species_bucket",
        "cwmu_partition",
        "cwmu_flag",
        "split_path",
        "source_row_id",
        "routing_status",
        "routing_notes",
    ]
    fields = base_fields + [field for field in added_fields if field not in base_fields]

    routed_path = OUT_DIR / "2017_ANTLERLESS_POINTS_SPECIES_CWMU_ROUTED_ROWS.csv"
    write_csv(routed_path, routed_rows, fields)

    groups: Dict[tuple, List[Dict[str, object]]] = defaultdict(list)
    for row in routed_rows:
        groups[(clean(row["cwmu_partition"]), clean(row["antlerless_species_bucket"]))].append(row)

    split_root = OUT_DIR / "split_rows" / "ANTLERLESS"
    manifest_rows = []
    counts_rows = []
    for (partition, bucket), group in sorted(groups.items()):
        out_path = split_root / partition / bucket / f"2017_ANTLERLESS_{partition}_{bucket}_ROWS.csv"
        write_csv(out_path, group, fields)
        pages = sorted({int(clean(row.get("pdf_page")) or 0) for row in group if clean(row.get("pdf_page")).isdigit()})
        hunt_codes = {clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}
        status = "PASS_ROUTED" if all(row.get("routing_status") == "PASS_ROUTED" for row in group) else "REVIEW_REQUIRED"
        manifest_rows.append(
            {
                "cwmu_partition": partition,
                "antlerless_species_bucket": bucket,
                "split_path": f"ANTLERLESS/{partition}/{bucket}",
                "output_path": rel(out_path),
                "row_count": len(group),
                "unique_hunt_codes": len(hunt_codes),
                "source_page_min": min(pages) if pages else "",
                "source_page_max": max(pages) if pages else "",
                "source_page_count": len(pages),
                "sha256": sha256_file(out_path),
                "routing_status": status,
            }
        )
        counts_rows.append(
            {
                "cwmu_partition": partition,
                "antlerless_species_bucket": bucket,
                "row_count": len(group),
                "unique_hunt_codes": len(hunt_codes),
                "source_page_count": len(pages),
                "routing_review_rows": sum(1 for row in group if row.get("routing_status") != "PASS_ROUTED"),
            }
        )

    manifest_path = OUT_DIR / "2017_ANTLERLESS_POINTS_SPECIES_CWMU_SPLIT_MANIFEST.csv"
    write_csv(
        manifest_path,
        manifest_rows,
        [
            "cwmu_partition",
            "antlerless_species_bucket",
            "split_path",
            "output_path",
            "row_count",
            "unique_hunt_codes",
            "source_page_min",
            "source_page_max",
            "source_page_count",
            "sha256",
            "routing_status",
        ],
    )
    counts_path = OUT_DIR / "2017_ANTLERLESS_POINTS_SPECIES_CWMU_SPLIT_COUNTS.csv"
    write_csv(
        counts_path,
        counts_rows,
        [
            "cwmu_partition",
            "antlerless_species_bucket",
            "row_count",
            "unique_hunt_codes",
            "source_page_count",
            "routing_review_rows",
        ],
    )

    species_counts = defaultdict(set)
    for row in routed_rows:
        species_counts[clean(row["antlerless_species_bucket"])].add(clean(row.get("hunt_code")))
    cwmu_rows = [row for row in routed_rows if row["cwmu_partition"] == "CWMU"]
    non_cwmu_rows = [row for row in routed_rows if row["cwmu_partition"] == "NON_CWMU"]
    review_rows = [row for row in routed_rows if row["routing_status"] != "PASS_ROUTED"]
    status = "PASS_ANTLERLESS_SPECIES_CWMU_SPLIT" if not review_rows else "PASS_WITH_REVIEW_REQUIRED"

    reference_path = OUT_DIR / "2017_ANTLERLESS_WEBSITE_MATRIX_REFERENCE.md"
    reference_path.write_text(
        "\n".join(
            [
                "# 2017 Antlerless Website Matrix Reference",
                "",
                "authoritative_matrix_source: https://huntbuilder.uoga.org/",
                "repo_matrix_source: app.js refreshSelectionMatrix()",
                "",
                "## Existing Column Alignment",
                "",
                "- Species -> existing `species` column",
                "- Sex -> existing `sex` column",
                "- Hunt Type -> existing `hunt_type` column",
                "- Weapon Type -> existing `weapon` column",
                "- Hunt Class -> existing `hunt_class` column",
                "- CWMU -> `cwmu_partition` / `cwmu_flag` split",
                "",
                "No duplicate website_matrix_* columns were created.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report_path = OUT_DIR / "2017_ANTLERLESS_POINTS_SPECIES_CWMU_SPLIT_REPORT.md"
    report_path.write_text(
        "\n".join(
            [
                "# 2017 Antlerless Points Species + CWMU Split Report",
                "",
                f"report_timestamp: {datetime.now().isoformat(timespec='seconds')}",
                f"source_pdf: {rel(SOURCE_PDF)}",
                f"source_pdf_pages: {page_count(SOURCE_PDF)}",
                f"source_pdf_sha256: {sha256_file(SOURCE_PDF)}",
                "",
                "## Boundary",
                "",
                "This is an audit-only split from raw/PDF-derived 2017 rows. It does not patch canonical_yearly, draw_results_long, DATABASE.csv, or prediction outputs.",
                "",
                "## Counts",
                "",
                f"source_rows: {len(routed_rows)}",
                f"unique_hunt_codes: {len({clean(row.get('hunt_code')) for row in routed_rows if clean(row.get('hunt_code'))})}",
                f"antlerless_species_bucket_count: {len(species_counts)}",
                f"CWMU rows: {len(cwmu_rows)}",
                f"CWMU unique hunt codes: {len({clean(row.get('hunt_code')) for row in cwmu_rows if clean(row.get('hunt_code'))})}",
                f"non-CWMU rows: {len(non_cwmu_rows)}",
                f"non-CWMU unique hunt codes: {len({clean(row.get('hunt_code')) for row in non_cwmu_rows if clean(row.get('hunt_code'))})}",
                f"routing review rows: {len(review_rows)}",
                "",
                "## Output Files",
                "",
                f"- routed rows: {rel(routed_path)}",
                f"- split manifest: {rel(manifest_path)}",
                f"- split counts: {rel(counts_path)}",
                f"- website matrix reference: {rel(reference_path)}",
                "",
                f"ANTLERLESS_SPECIES_CWMU_STATUS={status}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    terminal = "\n".join(
        [
            f"ANTLERLESS_SPECIES_CWMU_OUTPUT_DIR={OUT_DIR}",
            f"SOURCE_PDF={SOURCE_PDF}",
            f"ROUTED_ROWS={routed_path}",
            f"SPLIT_MANIFEST={manifest_path}",
            f"SPLIT_COUNTS={counts_path}",
            f"SPLIT_REPORT={report_path}",
            f"WEBSITE_MATRIX_REFERENCE={reference_path}",
            f"ANTLERLESS_SOURCE_ROWS={len(routed_rows)}",
            f"ANTLERLESS_UNIQUE_HUNT_CODES={len({clean(row.get('hunt_code')) for row in routed_rows if clean(row.get('hunt_code'))})}",
            f"ANTLERLESS_SPECIES_BUCKET_COUNT={len(species_counts)}",
            f"CWMU_ROWS={len(cwmu_rows)}",
            f"CWMU_UNIQUE_HUNT_CODES={len({clean(row.get('hunt_code')) for row in cwmu_rows if clean(row.get('hunt_code'))})}",
            f"NON_CWMU_ROWS={len(non_cwmu_rows)}",
            f"NON_CWMU_UNIQUE_HUNT_CODES={len({clean(row.get('hunt_code')) for row in non_cwmu_rows if clean(row.get('hunt_code'))})}",
            f"ANTLERLESS_SPECIES_CWMU_STATUS={status}",
            "NEXT_ACTION=USE_SPLIT_MANIFEST_TO_REVIEW_OR_PROMOTE_2017_ANTLERLESS_ROUTING",
        ]
    )
    (OUT_DIR / "FINAL_TERMINAL_OUTPUT.txt").write_text(terminal + "\n", encoding="utf-8")
    print(terminal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
