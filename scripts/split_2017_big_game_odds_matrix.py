"""Split 2017 Big Game odds rows into the approved species/program matrix.

Audit-only output. This does not patch canonical truth, draw_results_long, or
DATABASE.csv.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


REPO_ROOT = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
SOURCE_PDF = REPO_ROOT / "data_truth" / "draw_results_truth" / "raw_pdfs" / "2017_PERMITS=2018_MODEL" / "Parent Files" / "17_big_game_odds_report.pdf"
RAW_CANDIDATE = REPO_ROOT / "audits" / "draw_truth_2017_source_family_split" / "20260705_142833" / "draw_results_2017_for_2018_canonical_yearly_draw_results_CANDIDATE.after_family_split_fix.csv"
OUT_DIR = REPO_ROOT / "audits" / "2017_big_game_odds_matrix_split" / datetime.now().strftime("%Y%m%d_%H%M%S")

BIG_GAME_SPECIES = [
    "DEER",
    "ELK",
    "PRONGHORN",
    "BISON",
    "ROCKY_MOUNTAIN_BIGHORN_SHEEP",
    "DESERT_BIGHORN_SHEEP",
    "MOOSE",
    "MOUNTAIN_GOAT",
]

PROGRAM_SPECIES = {
    "PREMIUM_LIMITED_ENTRY": {"DEER"},
    "LIMITED_ENTRY": {"DEER", "ELK", "PRONGHORN"},
    "ONCE_IN_A_LIFETIME": {
        "BISON",
        "ROCKY_MOUNTAIN_BIGHORN_SHEEP",
        "DESERT_BIGHORN_SHEEP",
        "MOOSE",
        "MOUNTAIN_GOAT",
    },
}


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean(value: object) -> str:
    return str(value or "").strip()


def norm(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", clean(value).upper()).strip("_")


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


def page_count(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        return str(len(PdfReader(str(path)).pages))
    except Exception:
        return ""


def species_bucket(row: Dict[str, str]) -> str:
    species_text = norm(row.get("species", ""))
    if species_text == "DEER":
        return "DEER"
    if species_text == "ELK":
        return "ELK"
    if species_text == "PRONGHORN":
        return "PRONGHORN"
    if species_text == "BISON":
        return "BISON"
    if species_text == "MOOSE":
        return "MOOSE"
    if species_text in {"MOUNTAIN_GOAT", "MTN_GOAT"}:
        return "MOUNTAIN_GOAT"
    if species_text == "DESERT_BIGHORN_SHEEP":
        return "DESERT_BIGHORN_SHEEP"
    if species_text in {"ROCKY_MOUNTAIN_BIGHORN_SHEEP", "ROCKY_MTN_SHEEP"}:
        return "ROCKY_MOUNTAIN_BIGHORN_SHEEP"
    text = norm(" ".join([row.get("raw_hunt_name", ""), row.get("hunt_name", ""), row.get("hunt_class", "")]))
    if "PRONGHORN" in text:
        return "PRONGHORN"
    if "ELK" in text:
        return "ELK"
    if "MOUNTAIN_GOAT" in text or "MTN_GOAT" in text or "GOAT" in text:
        return "MOUNTAIN_GOAT"
    if "DESERT" in text and ("BIGHORN" in text or "SHEEP" in text):
        return "DESERT_BIGHORN_SHEEP"
    if ("ROCKY" in text or "ROCKY_MTN" in text) and ("BIGHORN" in text or "SHEEP" in text):
        return "ROCKY_MOUNTAIN_BIGHORN_SHEEP"
    if "BISON" in text:
        return "BISON"
    if "MOOSE" in text:
        return "MOOSE"
    if "DEER" in text:
        return "DEER"
    return "UNKNOWN"


def program_bucket(row: Dict[str, str], bucket: str) -> str:
    text = norm(" ".join([row.get("raw_hunt_name", ""), row.get("hunt_name", ""), row.get("hunt_class", "")]))
    if bucket == "DEER" and ("PREMIUM_LE" in text or "PREMIUM_LIMITED_ENTRY" in text or "PREMIUM_CWMU" in text):
        return "PREMIUM_LIMITED_ENTRY"
    if bucket in PROGRAM_SPECIES["ONCE_IN_A_LIFETIME"]:
        return "ONCE_IN_A_LIFETIME"
    if bucket in PROGRAM_SPECIES["LIMITED_ENTRY"]:
        return "LIMITED_ENTRY"
    return "REVIEW_REQUIRED_UNROUTED"


def cwmu_flag(row: Dict[str, str]) -> str:
    text = norm(" ".join([row.get("raw_hunt_name", ""), row.get("hunt_name", ""), row.get("hunt_class", "")]))
    return "TRUE" if "CWMU" in text else "FALSE"


def sex_class(row: Dict[str, str]) -> str:
    text = norm(" ".join([row.get("sex", ""), row.get("raw_hunt_name", ""), row.get("hunt_name", "")]))
    if "COW" in text or "EWE" in text or "ANTLERLESS" in text:
        return "FEMALE_OR_ANTLERLESS"
    if "BUCK" in text or "BULL" in text or "RAM" in text:
        return "MALE"
    if "EITHER" in text:
        return "EITHER_SEX"
    return norm(row.get("sex")) or "UNKNOWN"


def youth_set_aside_overlay_flag(row: Dict[str, str]) -> str:
    text = norm(" ".join([row.get("raw_hunt_name", ""), row.get("hunt_name", ""), row.get("hunt_class", ""), row.get("source_file", "")]))
    return "TRUE" if "YOUTH" in text else "FALSE"


def youth_overlay_status(row: Dict[str, str]) -> str:
    if youth_set_aside_overlay_flag(row) == "TRUE":
        return "SOURCE_PROVEN_YOUTH_SET_ASIDE_QUOTA_OVERLAY"
    return "ADULT_BASE_HUNT_NO_YOUTH_OVERLAY_IN_SOURCE"


def route_status(program: str, bucket: str) -> str:
    allowed = PROGRAM_SPECIES.get(program, set())
    if bucket == "UNKNOWN" or program == "REVIEW_REQUIRED_UNROUTED":
        return "REVIEW_REQUIRED_UNROUTED_BIG_GAME_ROW"
    if bucket not in allowed:
        if program == "PREMIUM_LIMITED_ENTRY":
            return "REVIEW_REQUIRED_UNEXPECTED_PREMIUM_NON_DEER_LABEL"
        return "REVIEW_REQUIRED_PROGRAM_SPECIES_CONFLICT"
    return "PASS_ROUTED"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    split_root = OUT_DIR / "split_rows" / "BIG_GAME"
    rows = [
        row
        for row in read_csv(RAW_CANDIDATE)
        if clean(row.get("source_file")) == "17_big_game_odds_report.pdf"
    ]
    routed_rows: List[Dict[str, object]] = []
    for idx, row in enumerate(rows, start=1):
        bucket = species_bucket(row)
        program = program_bucket(row, bucket)
        status = route_status(program, bucket)
        pdf_page = clean(row.get("pdf_page"))
        routed = dict(row)
        routed.update(
            {
                "matrix_source_pdf": rel(SOURCE_PDF),
                "matrix_source_pdf_sha256": sha256_file(SOURCE_PDF),
                "big_game_species_bucket": bucket,
                "matrix_program_bucket": program,
                "matrix_species_path": f"BIG_GAME/{program}/{bucket}" if status == "PASS_ROUTED" else "BIG_GAME/REVIEW/{bucket}",
                "cwmu_flag": cwmu_flag(row),
                "base_hunt_layer": "ADULT_BASE_HUNT",
                "youth_set_aside_overlay_flag": youth_set_aside_overlay_flag(row),
                "youth_overlay_status": youth_overlay_status(row),
                "sex_class_matrix": sex_class(row),
                "source_row_id": f"2017_BIG_GAME_MATRIX-{idx:06d}",
                "routing_status": status,
                "routing_notes": "P.L.E. deer-only; L.E. deer/elk/pronghorn; O.I.L. bison/sheep/moose/goat. CWMU and youth set-aside quota retained as overlays.",
                "source_pdf_page": pdf_page,
            }
        )
        routed_rows.append(routed)

    base_fields = list(rows[0].keys()) if rows else []
    added_fields = [
        "matrix_source_pdf",
        "matrix_source_pdf_sha256",
        "big_game_species_bucket",
        "matrix_program_bucket",
        "matrix_species_path",
        "cwmu_flag",
        "base_hunt_layer",
        "youth_set_aside_overlay_flag",
        "youth_overlay_status",
        "sex_class_matrix",
        "source_row_id",
        "routing_status",
        "routing_notes",
        "source_pdf_page",
    ]
    fields = base_fields + [field for field in added_fields if field not in base_fields]

    routed_path = OUT_DIR / "2017_BIG_GAME_ODDS_MATRIX_ROUTED_ROWS.csv"
    write_csv(routed_path, routed_rows, fields)
    website_reference_path = OUT_DIR / "2017_BIG_GAME_WEBSITE_MATRIX_REFERENCE.md"
    website_reference_path.write_text(
        "\n".join(
            [
                "# 2017 Big Game Website Matrix Reference",
                "",
                "authoritative_matrix_source: https://huntbuilder.uoga.org/",
                "repo_matrix_source: app.js refreshSelectionMatrix()",
                "",
                "## Live Filter Fields",
                "",
                "- Species",
                "- Sex",
                "- Hunt Type",
                "- Weapon Type",
                "- Hunt Class",
                "- DWR Hunt Units",
                "",
                "## Output Column Alignment",
                "",
                "- Species -> existing `species` column",
                "- Sex -> existing `sex` column",
                "- Hunt Type -> existing `hunt_type` column",
                "- Weapon Type -> existing `weapon` column",
                "- Hunt Class -> existing `hunt_class` column",
                "- CWMU -> cwmu_flag / cwmu_partition overlay",
                "- Youth set-aside quota -> youth_set_aside_overlay_flag / quota_layer overlay",
                "",
                "## Rule",
                "",
                "Youth is not a peer split against adult. Youth is a source-proven set-aside quota overlay on adult/base hunts where it applies.",
                "CWMU is also preserved as an overlay/partition so website-facing hunt type/class can be reviewed separately from raw PDF source structure.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    path_groups: Dict[tuple, List[Dict[str, object]]] = defaultdict(list)
    for row in routed_rows:
        path_groups[(clean(row["matrix_program_bucket"]), clean(row["big_game_species_bucket"]))].append(row)
    split_manifest_rows = []
    for (program, bucket), group in sorted(path_groups.items()):
        out_path = split_root / program / bucket / f"2017_BIG_GAME_{program}_{bucket}_ROWS.csv"
        write_csv(out_path, group, fields)
        pages = sorted({int(clean(row.get("pdf_page")) or 0) for row in group if clean(row.get("pdf_page")).isdigit()})
        split_manifest_rows.append(
            {
                "matrix_program_bucket": program,
                "big_game_species_bucket": bucket,
                "matrix_species_path": f"BIG_GAME/{program}/{bucket}",
                "output_path": rel(out_path),
                "row_count": len(group),
                "unique_hunt_codes": len({clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}),
                "source_page_min": min(pages) if pages else "",
                "source_page_max": max(pages) if pages else "",
                "source_page_count": len(pages),
                "cwmu_hunt_codes": len({clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code")) and row.get("cwmu_flag") == "TRUE"}),
                "sha256": sha256_file(out_path),
                "routing_status": "PASS_ROUTED" if all(row.get("routing_status") == "PASS_ROUTED" for row in group) else "REVIEW_REQUIRED",
            }
        )

    manifest_path = OUT_DIR / "2017_BIG_GAME_ODDS_MATRIX_SPLIT_MANIFEST.csv"
    write_csv(
        manifest_path,
        split_manifest_rows,
        [
            "matrix_program_bucket",
            "big_game_species_bucket",
            "matrix_species_path",
            "output_path",
            "row_count",
            "unique_hunt_codes",
            "source_page_min",
            "source_page_max",
            "source_page_count",
            "cwmu_hunt_codes",
            "sha256",
            "routing_status",
        ],
    )

    counts = []
    for (program, bucket), group in sorted(path_groups.items()):
        counts.append(
            {
                "count_scope": "program_species",
                "matrix_program_bucket": program,
                "big_game_species_bucket": bucket,
                "row_count": len(group),
                "unique_hunt_codes": len({clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}),
                "cwmu_rows": sum(1 for row in group if row.get("cwmu_flag") == "TRUE"),
                "cwmu_unique_hunt_codes": len({clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code")) and row.get("cwmu_flag") == "TRUE"}),
                "routing_review_rows": sum(1 for row in group if row.get("routing_status") != "PASS_ROUTED"),
            }
        )
    for program in ["PREMIUM_LIMITED_ENTRY", "LIMITED_ENTRY", "ONCE_IN_A_LIFETIME"]:
        group = [row for row in routed_rows if row["matrix_program_bucket"] == program]
        counts.append(
            {
                "count_scope": "program_total",
                "matrix_program_bucket": program,
                "big_game_species_bucket": "ALL",
                "row_count": len(group),
                "unique_hunt_codes": len({clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}),
                "cwmu_rows": sum(1 for row in group if row.get("cwmu_flag") == "TRUE"),
                "cwmu_unique_hunt_codes": len({clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code")) and row.get("cwmu_flag") == "TRUE"}),
                "routing_review_rows": sum(1 for row in group if row.get("routing_status") != "PASS_ROUTED"),
            }
        )
    counts_path = OUT_DIR / "2017_BIG_GAME_ODDS_MATRIX_SPLIT_COUNTS.csv"
    write_csv(
        counts_path,
        counts,
        [
            "count_scope",
            "matrix_program_bucket",
            "big_game_species_bucket",
            "row_count",
            "unique_hunt_codes",
            "cwmu_rows",
            "cwmu_unique_hunt_codes",
            "routing_review_rows",
        ],
    )

    quota_overlay_manifest_rows = []
    quota_overlay_groups: Dict[tuple, List[Dict[str, object]]] = defaultdict(list)
    for row in routed_rows:
        cwmu_partition = "CWMU" if row.get("cwmu_flag") == "TRUE" else "NON_CWMU"
        quota_layer = "YOUTH_SET_ASIDE_QUOTA_OVERLAY" if row.get("youth_set_aside_overlay_flag") == "TRUE" else "ADULT_BASE_HUNT"
        quota_overlay_groups[
            (
                clean(row["matrix_program_bucket"]),
                clean(row["big_game_species_bucket"]),
                cwmu_partition,
                quota_layer,
            )
        ].append(row)
    overlay_root = OUT_DIR / "split_rows_by_quota_overlay" / "BIG_GAME"
    for (program, bucket, cwmu_partition, quota_layer), group in sorted(quota_overlay_groups.items()):
        out_path = overlay_root / program / bucket / cwmu_partition / quota_layer / f"2017_BIG_GAME_{program}_{bucket}_{cwmu_partition}_{quota_layer}_ROWS.csv"
        write_csv(out_path, group, fields)
        pages = sorted({int(clean(row.get("pdf_page")) or 0) for row in group if clean(row.get("pdf_page")).isdigit()})
        quota_overlay_manifest_rows.append(
            {
                "matrix_program_bucket": program,
                "big_game_species_bucket": bucket,
                "cwmu_partition": cwmu_partition,
                "quota_layer": quota_layer,
                "youth_set_aside_overlay_flag": "TRUE" if quota_layer == "YOUTH_SET_ASIDE_QUOTA_OVERLAY" else "FALSE",
                "matrix_overlay_path": f"BIG_GAME/{program}/{bucket}/{cwmu_partition}/{quota_layer}",
                "output_path": rel(out_path),
                "row_count": len(group),
                "unique_hunt_codes": len({clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}),
                "source_page_min": min(pages) if pages else "",
                "source_page_max": max(pages) if pages else "",
                "source_page_count": len(pages),
                "sha256": sha256_file(out_path),
                "routing_status": "PASS_ROUTED" if all(row.get("routing_status") == "PASS_ROUTED" for row in group) else "REVIEW_REQUIRED",
            }
        )
    overlay_manifest_path = OUT_DIR / "2017_BIG_GAME_ODDS_YOUTH_SET_ASIDE_CWMU_OVERLAY_MANIFEST.csv"
    write_csv(
        overlay_manifest_path,
        quota_overlay_manifest_rows,
        [
            "matrix_program_bucket",
            "big_game_species_bucket",
            "cwmu_partition",
            "quota_layer",
            "youth_set_aside_overlay_flag",
            "matrix_overlay_path",
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
    overlay_count_rows = []
    for (program, bucket, cwmu_partition, quota_layer), group in sorted(quota_overlay_groups.items()):
        overlay_count_rows.append(
            {
                "matrix_program_bucket": program,
                "big_game_species_bucket": bucket,
                "cwmu_partition": cwmu_partition,
                "quota_layer": quota_layer,
                "youth_set_aside_overlay_flag": "TRUE" if quota_layer == "YOUTH_SET_ASIDE_QUOTA_OVERLAY" else "FALSE",
                "row_count": len(group),
                "unique_hunt_codes": len({clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}),
                "routing_review_rows": sum(1 for row in group if row.get("routing_status") != "PASS_ROUTED"),
            }
        )
    overlay_counts_path = OUT_DIR / "2017_BIG_GAME_ODDS_YOUTH_SET_ASIDE_CWMU_OVERLAY_COUNTS.csv"
    write_csv(
        overlay_counts_path,
        overlay_count_rows,
        [
            "matrix_program_bucket",
            "big_game_species_bucket",
            "cwmu_partition",
            "quota_layer",
            "youth_set_aside_overlay_flag",
            "row_count",
            "unique_hunt_codes",
            "routing_review_rows",
        ],
    )

    cwmu_manifest_rows = []
    cwmu_counts_rows = []
    cwmu_groups: Dict[tuple, List[Dict[str, object]]] = defaultdict(list)
    for row in routed_rows:
        partition = "CWMU" if row.get("cwmu_flag") == "TRUE" else "NON_CWMU"
        cwmu_groups[(partition, clean(row["matrix_program_bucket"]), clean(row["big_game_species_bucket"]))].append(row)
    cwmu_root = OUT_DIR / "split_rows_cwmu" / "BIG_GAME"
    for (partition, program, bucket), group in sorted(cwmu_groups.items()):
        out_path = cwmu_root / partition / program / bucket / f"2017_BIG_GAME_{partition}_{program}_{bucket}_ROWS.csv"
        write_csv(out_path, group, fields)
        pages = sorted({int(clean(row.get("pdf_page")) or 0) for row in group if clean(row.get("pdf_page")).isdigit()})
        hunt_codes = {clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}
        manifest_row = {
            "cwmu_partition": partition,
            "matrix_program_bucket": program,
            "big_game_species_bucket": bucket,
            "split_path": f"BIG_GAME/{partition}/{program}/{bucket}",
            "output_path": rel(out_path),
            "row_count": len(group),
            "unique_hunt_codes": len(hunt_codes),
            "source_page_min": min(pages) if pages else "",
            "source_page_max": max(pages) if pages else "",
            "source_page_count": len(pages),
            "sha256": sha256_file(out_path),
            "routing_status": "PASS_ROUTED" if all(row.get("routing_status") == "PASS_ROUTED" for row in group) else "REVIEW_REQUIRED",
        }
        cwmu_manifest_rows.append(manifest_row)
        cwmu_counts_rows.append(
            {
                "cwmu_partition": partition,
                "matrix_program_bucket": program,
                "big_game_species_bucket": bucket,
                "row_count": len(group),
                "unique_hunt_codes": len(hunt_codes),
                "routing_review_rows": sum(1 for row in group if row.get("routing_status") != "PASS_ROUTED"),
            }
        )
    cwmu_manifest_path = OUT_DIR / "2017_BIG_GAME_CWMU_SPLIT_MANIFEST.csv"
    write_csv(
        cwmu_manifest_path,
        cwmu_manifest_rows,
        [
            "cwmu_partition",
            "matrix_program_bucket",
            "big_game_species_bucket",
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
    cwmu_counts_path = OUT_DIR / "2017_BIG_GAME_CWMU_SPLIT_COUNTS.csv"
    write_csv(
        cwmu_counts_path,
        cwmu_counts_rows,
        [
            "cwmu_partition",
            "matrix_program_bucket",
            "big_game_species_bucket",
            "row_count",
            "unique_hunt_codes",
            "routing_review_rows",
        ],
    )

    route_status_counts = Counter(clean(row["routing_status"]) for row in routed_rows)
    species_count = len({clean(row["big_game_species_bucket"]) for row in routed_rows if clean(row["big_game_species_bucket"]) in BIG_GAME_SPECIES})
    oil_species_count = len({clean(row["big_game_species_bucket"]) for row in routed_rows if clean(row["matrix_program_bucket"]) == "ONCE_IN_A_LIFETIME"})
    ple_species_count = len({clean(row["big_game_species_bucket"]) for row in routed_rows if clean(row["matrix_program_bucket"]) == "PREMIUM_LIMITED_ENTRY"})
    le_species_count = len({clean(row["big_game_species_bucket"]) for row in routed_rows if clean(row["matrix_program_bucket"]) == "LIMITED_ENTRY"})
    unexpected_ple_non_deer = sum(1 for row in routed_rows if row["matrix_program_bucket"] == "PREMIUM_LIMITED_ENTRY" and row["big_game_species_bucket"] != "DEER")
    youth_overlay_row_count = sum(1 for row in routed_rows if row["youth_set_aside_overlay_flag"] == "TRUE")
    adult_base_row_count = sum(1 for row in routed_rows if row["base_hunt_layer"] == "ADULT_BASE_HUNT")
    cwmu_row_count = sum(1 for row in routed_rows if row["cwmu_flag"] == "TRUE")
    non_cwmu_row_count = sum(1 for row in routed_rows if row["cwmu_flag"] != "TRUE")
    taxonomy_status = "PASS_BIG_GAME_MATRIX_ROUTED" if not unexpected_ple_non_deer and route_status_counts.get("PASS_ROUTED", 0) == len(routed_rows) else "PASS_WITH_REVIEW_REQUIRED"

    report_path = OUT_DIR / "2017_BIG_GAME_ODDS_MATRIX_SPLIT_REPORT.md"
    report_path.write_text(
        "\n".join(
            [
                "# 2017 Big Game Odds Matrix Split Report",
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
                "## Matrix Rule",
                "",
                "BIG_GAME_SPECIES_BUCKET_COUNT=8",
                "OIL_SPECIES_BUCKET_COUNT=5",
                "PLE_SPECIES_BUCKET_COUNT=1",
                "LE_BIG_GAME_SPECIES_BUCKET_COUNT=3",
                "PLE_DEER_ONLY=TRUE",
                "",
                "P.L.E. routes deer only. L.E. routes deer, elk, and pronghorn. O.I.L. routes bison, Rocky Mountain bighorn sheep, Desert bighorn sheep, moose, and mountain goat. CWMU is preserved as an overlay flag. Youth is a set-aside quota overlay on adult/base hunts where source-proven, not a peer split against adult.",
                "",
                "## Counts",
                "",
                f"source_rows: {len(routed_rows)}",
                f"unique_hunt_codes: {len({clean(row.get('hunt_code')) for row in routed_rows if clean(row.get('hunt_code'))})}",
                f"routed_species_count: {species_count}",
                f"PLE species count: {ple_species_count}",
                f"LE species count: {le_species_count}",
                f"OIL species count: {oil_species_count}",
                f"unexpected PLE non-deer rows: {unexpected_ple_non_deer}",
                f"adult base rows: {adult_base_row_count}",
                f"youth set-aside overlay rows: {youth_overlay_row_count}",
                f"CWMU rows: {cwmu_row_count}",
                f"non-CWMU rows: {non_cwmu_row_count}",
                "",
                "## Output Files",
                "",
                f"- routed rows: {rel(routed_path)}",
                f"- split manifest: {rel(manifest_path)}",
                f"- split counts: {rel(counts_path)}",
                f"- website matrix reference: {rel(website_reference_path)}",
                f"- youth set-aside/CWMU overlay manifest: {rel(overlay_manifest_path)}",
                f"- youth set-aside/CWMU overlay counts: {rel(overlay_counts_path)}",
                f"- CWMU split manifest: {rel(cwmu_manifest_path)}",
                f"- CWMU split counts: {rel(cwmu_counts_path)}",
                "",
                "## Routing Status Counts",
                "",
                *[f"- {status}: {count}" for status, count in sorted(route_status_counts.items())],
                "",
                f"TAXONOMY_STATUS={taxonomy_status}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    terminal = "\n".join(
        [
            f"BIG_GAME_MATRIX_SPLIT_OUTPUT_DIR={OUT_DIR}",
            f"SOURCE_PDF={SOURCE_PDF}",
            f"ROUTED_ROWS={routed_path}",
            f"SPLIT_MANIFEST={manifest_path}",
            f"SPLIT_COUNTS={counts_path}",
            f"SPLIT_REPORT={report_path}",
            f"WEBSITE_MATRIX_REFERENCE={website_reference_path}",
            f"YOUTH_SET_ASIDE_CWMU_OVERLAY_MANIFEST={overlay_manifest_path}",
            f"YOUTH_SET_ASIDE_CWMU_OVERLAY_COUNTS={overlay_counts_path}",
            f"CWMU_SPLIT_MANIFEST={cwmu_manifest_path}",
            f"CWMU_SPLIT_COUNTS={cwmu_counts_path}",
            f"BIG_GAME_SOURCE_ROWS={len(routed_rows)}",
            f"BIG_GAME_UNIQUE_HUNT_CODES={len({clean(row.get('hunt_code')) for row in routed_rows if clean(row.get('hunt_code'))})}",
            f"ADULT_BASE_ROWS={adult_base_row_count}",
            f"YOUTH_SET_ASIDE_OVERLAY_ROWS={youth_overlay_row_count}",
            f"CWMU_ROWS={cwmu_row_count}",
            f"NON_CWMU_ROWS={non_cwmu_row_count}",
            "BIG_GAME_SPECIES_BUCKET_COUNT=8",
            "OIL_SPECIES_BUCKET_COUNT=5",
            "PLE_SPECIES_BUCKET_COUNT=1",
            "LE_BIG_GAME_SPECIES_BUCKET_COUNT=3",
            "PLE_DEER_ONLY=TRUE",
            f"TAXONOMY_STATUS={taxonomy_status}",
            "NEXT_ACTION=USE_SPLIT_MANIFEST_TO_REVIEW_OR_PROMOTE_2017_BIG_GAME_ROUTING",
        ]
    )
    (OUT_DIR / "FINAL_TERMINAL_OUTPUT.txt").write_text(terminal + "\n", encoding="utf-8")
    print(terminal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
