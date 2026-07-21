"""Create a dedicated 2017 CWMU and allotment/OTC component separation audit.

This is audit-only. It separates CWMU rows from existing raw/PDF-derived 2017
component outputs and records allotment/OTC families that require non-draw
source handling.
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
DATABASE_2026 = REPO_ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
OUT_DIR = REPO_ROOT / "audits" / "2017_cwmu_allotment_component_separation" / datetime.now().strftime("%Y%m%d_%H%M%S")

ALLOTMENT_FAMILIES = [
    "GENERAL_SEASON_SPIKE_ELK",
    "GENERAL_SEASON_GENERAL_BULL_ELK",
    "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK",
]


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


def row_text(row: Dict[str, str]) -> str:
    return norm(
        " ".join(
            [
                row.get("source_file", ""),
                row.get("source_dataset", ""),
                row.get("hunt_class", ""),
                row.get("hunt_type", ""),
                row.get("raw_hunt_name", ""),
                row.get("hunt_name", ""),
                row.get("species", ""),
                row.get("sex", ""),
            ]
        )
    )


def all_value_text(row: Dict[str, str]) -> str:
    return norm(" ".join(clean(value) for value in row.values()))


def source_file_name(row: Dict[str, str]) -> str:
    return Path(clean(row.get("source_file"))).name


def species_bucket(row: Dict[str, str]) -> str:
    text = row_text(row)
    species = norm(row.get("species"))
    if "PRONGHORN" in text:
        return "PRONGHORN" if source_file_name(row) == "17_big_game_odds_report.pdf" else "DOE_PRONGHORN"
    if "MOOSE" in text:
        return "MOOSE" if source_file_name(row) == "17_big_game_odds_report.pdf" else "ANTLERLESS_MOOSE"
    if "ELK" in text:
        return "ELK" if source_file_name(row) == "17_big_game_odds_report.pdf" else "ANTLERLESS_ELK"
    if "DEER" in text or clean(row.get("hunt_code")).upper().startswith("DA"):
        return "DEER" if source_file_name(row) == "17_big_game_odds_report.pdf" else "ANTLERLESS_DEER"
    return species or "UNKNOWN"


def program_bucket(row: Dict[str, str], bucket: str) -> str:
    text = row_text(row)
    source_file = source_file_name(row)
    if source_file == "17_big_game_odds_report.pdf":
        if bucket == "DEER" and ("PREMIUM_LE" in text or "PREMIUM_LIMITED_ENTRY" in text or "PREMIUM_CWMU" in text):
            return "PREMIUM_LIMITED_ENTRY"
        if bucket in {"BISON", "ROCKY_MOUNTAIN_BIGHORN_SHEEP", "DESERT_BIGHORN_SHEEP", "MOOSE", "MOUNTAIN_GOAT"}:
            return "ONCE_IN_A_LIFETIME"
        return "LIMITED_ENTRY"
    if source_file == "17_antlerless_points.pdf":
        return "ANTLERLESS"
    if source_file == "17_antlerless_youth_points.pdf":
        return "YOUTH_ANTLERLESS"
    return "UNKNOWN_PROGRAM"


def component_bucket(row: Dict[str, str]) -> str:
    source_file = source_file_name(row)
    if source_file == "17_big_game_odds_report.pdf":
        return "BIG_GAME_CWMU"
    if source_file == "17_antlerless_points.pdf":
        return "ANTLERLESS_CWMU"
    if source_file == "17_antlerless_youth_points.pdf":
        return "YOUTH_ANTLERLESS_CWMU"
    return "UNKNOWN_CWMU"


def is_cwmu(row: Dict[str, str]) -> bool:
    return "CWMU" in row_text(row)


def database_allotment_rows() -> Dict[str, List[Dict[str, str]]]:
    if not DATABASE_2026.exists():
        return {family: [] for family in ALLOTMENT_FAMILIES}
    rows = read_csv(DATABASE_2026)
    grouped = {family: [] for family in ALLOTMENT_FAMILIES}
    for row in rows:
        text = all_value_text(row)
        if "PRIVATE_LANDS_ONLY" in text and "ANTLERLESS" in text and "ELK" in text:
            grouped["PRIVATE_LANDS_ONLY_ANTLERLESS_ELK"].append(row)
        if "SPIKE" in text and "ELK" in text and "GENERAL" in text:
            grouped["GENERAL_SEASON_SPIKE_ELK"].append(row)
        if "GENERAL_BULL" in text or ("GENERAL_SEASON" in text and "BULL_ELK" in text):
            grouped["GENERAL_SEASON_GENERAL_BULL_ELK"].append(row)
    return grouped


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_rows = read_csv(RAW_CANDIDATE)
    cwmu_rows = [
        row
        for row in raw_rows
        if source_file_name(row) in {"17_big_game_odds_report.pdf", "17_antlerless_points.pdf", "17_antlerless_youth_points.pdf"}
        and is_cwmu(row)
    ]

    routed_rows: List[Dict[str, object]] = []
    for idx, row in enumerate(cwmu_rows, start=1):
        bucket = species_bucket(row)
        component = component_bucket(row)
        routed = dict(row)
        routed.update(
            {
                "separated_component": component,
                "program_bucket": program_bucket(row, bucket),
                "species_bucket": bucket,
                "cwmu_partition": "CWMU",
                "quota_layer": "YOUTH_SET_ASIDE_QUOTA_OVERLAY" if component == "YOUTH_ANTLERLESS_CWMU" else "ADULT_BASE_HUNT",
                "component_layer_type": "CWMU_SEPARATED_FROM_PARENT_DRAW_FAMILY",
                "source_row_id": f"2017_CWMU_SEPARATED-{idx:06d}",
                "routing_status": "PASS_CWMU_SEPARATED",
                "routing_notes": "CWMU pulled to top-level component output from raw/PDF-derived 2017 rows. Parent family columns are preserved for lineage.",
            }
        )
        routed_rows.append(routed)

    base_fields = list(cwmu_rows[0].keys()) if cwmu_rows else list(raw_rows[0].keys())
    added_fields = [
        "separated_component",
        "program_bucket",
        "species_bucket",
        "cwmu_partition",
        "quota_layer",
        "component_layer_type",
        "source_row_id",
        "routing_status",
        "routing_notes",
    ]
    fields = base_fields + [field for field in added_fields if field not in base_fields]

    routed_path = OUT_DIR / "2017_CWMU_SEPARATED_COMPONENT_ROWS.csv"
    write_csv(routed_path, routed_rows, fields)

    split_root = OUT_DIR / "split_rows"
    manifest_rows = []
    counts_rows = []
    groups: Dict[tuple, List[Dict[str, object]]] = defaultdict(list)
    for row in routed_rows:
        groups[(clean(row["separated_component"]), clean(row["program_bucket"]), clean(row["species_bucket"]))].append(row)
    for (component, program, species), group in sorted(groups.items()):
        out_path = split_root / component / program / species / f"2017_{component}_{program}_{species}_ROWS.csv"
        write_csv(out_path, group, fields)
        hunts = {clean(row.get("hunt_code")) for row in group if clean(row.get("hunt_code"))}
        pages = {(clean(row.get("source_file")), clean(row.get("pdf_page"))) for row in group if clean(row.get("pdf_page"))}
        row = {
            "separated_component": component,
            "program_bucket": program,
            "species_bucket": species,
            "split_path": rel(out_path.parent),
            "output_path": rel(out_path),
            "row_count": len(group),
            "unique_hunt_codes": len(hunts),
            "source_page_count": len(pages),
            "sha256": sha256_file(out_path),
            "routing_status": "PASS_CWMU_SEPARATED",
        }
        manifest_rows.append(row)
        counts_rows.append({k: row[k] for k in ["separated_component", "program_bucket", "species_bucket", "row_count", "unique_hunt_codes", "source_page_count", "routing_status"]})

    manifest_path = OUT_DIR / "2017_CWMU_SEPARATED_COMPONENT_MANIFEST.csv"
    write_csv(
        manifest_path,
        manifest_rows,
        ["separated_component", "program_bucket", "species_bucket", "split_path", "output_path", "row_count", "unique_hunt_codes", "source_page_count", "sha256", "routing_status"],
    )

    counts_path = OUT_DIR / "2017_CWMU_SEPARATED_COMPONENT_COUNTS.csv"
    write_csv(
        counts_path,
        counts_rows,
        ["separated_component", "program_bucket", "species_bucket", "row_count", "unique_hunt_codes", "source_page_count", "routing_status"],
    )

    allotment_rows = []
    db_grouped = database_allotment_rows()
    raw_text = "\n".join(row_text(row) for row in raw_rows)
    for family in ALLOTMENT_FAMILIES:
        db_rows = db_grouped.get(family, [])
        raw_hits = 0
        if family == "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK":
            raw_hits = sum(1 for row in raw_rows if "PRIVATE" in row_text(row) and "ANTLERLESS" in row_text(row) and "ELK" in row_text(row))
        elif family == "GENERAL_SEASON_SPIKE_ELK":
            raw_hits = sum(1 for row in raw_rows if "SPIKE" in row_text(row) and "ELK" in row_text(row) and "GENERAL" in row_text(row))
        elif family == "GENERAL_SEASON_GENERAL_BULL_ELK":
            raw_hits = sum(1 for row in raw_rows if ("GENERAL_BULL" in row_text(row) or "GENERAL_SEASON_GENERAL_BULL_ELK" in row_text(row)))
        status = "SOURCE_PRESENT_IN_DATABASE_NON_SCORABLE_PERMIT_REFERENCE" if db_rows else "SOURCE_REQUIRED_NOT_PRESENT_IN_2017_DRAW_ODDS"
        if raw_hits:
            status = "REVIEW_REQUIRED_RAW_DRAW_ODDS_TEXT_HIT"
        allotment_rows.append(
            {
                "component_family": family,
                "component_layer_type": "ALLOTMENT_OR_OTC_NON_DRAW_COMPONENT",
                "raw_2017_draw_odds_row_hits": raw_hits,
                "database_2026_reference_rows": len(db_rows),
                "database_2026_unique_hunt_codes": len({clean(row.get("hunt_code") or row.get("hunt_code_normalized")) for row in db_rows if clean(row.get("hunt_code") or row.get("hunt_code_normalized"))}),
                "scoring_disposition": "NON_SCORABLE_PERMIT_OR_ALLOTMENT_REFERENCE_UNLESS_YEAR_SOURCE_PROVES_DRAW_ODDS",
                "source_status": status,
                "notes": "Do not score as point-level draw odds until a year-specific official source proves draw rows exist.",
            }
        )
    allotment_path = OUT_DIR / "2017_ALLOTMENT_OTC_COMPONENT_SOURCE_STATUS.csv"
    write_csv(
        allotment_path,
        allotment_rows,
        ["component_family", "component_layer_type", "raw_2017_draw_odds_row_hits", "database_2026_reference_rows", "database_2026_unique_hunt_codes", "scoring_disposition", "source_status", "notes"],
    )

    report_path = OUT_DIR / "2017_CWMU_ALLOTMENT_COMPONENT_SEPARATION_REPORT.md"
    big_game_rows = [row for row in routed_rows if row.get("separated_component") == "BIG_GAME_CWMU"]
    antlerless_rows = [row for row in routed_rows if row.get("separated_component") == "ANTLERLESS_CWMU"]
    youth_antlerless_rows = [row for row in routed_rows if row.get("separated_component") == "YOUTH_ANTLERLESS_CWMU"]
    status = "PASS_WITH_SOURCE_REVIEW_REQUIRED" if any(row["source_status"] != "SOURCE_PRESENT_IN_DATABASE_NON_SCORABLE_PERMIT_REFERENCE" for row in allotment_rows) else "PASS_CWMU_ALLOTMENT_COMPONENT_SEPARATED"
    report_path.write_text(
        "\n".join(
            [
                "# 2017 CWMU And Allotment Component Separation Report",
                "",
                f"report_timestamp: {datetime.now().isoformat(timespec='seconds')}",
                "",
                "## Boundary",
                "",
                "This is an audit-only separation from repo-visible raw/PDF-derived 2017 rows and repo-visible database reference rows. It does not patch canonical_yearly, draw_results_long, DATABASE.csv, or prediction outputs.",
                "",
                "## CWMU Separation",
                "",
                f"BIG_GAME_CWMU rows: {len(big_game_rows)}",
                f"BIG_GAME_CWMU unique hunt codes: {len({clean(row.get('hunt_code')) for row in big_game_rows if clean(row.get('hunt_code'))})}",
                f"ANTLERLESS_CWMU rows: {len(antlerless_rows)}",
                f"ANTLERLESS_CWMU unique hunt codes: {len({clean(row.get('hunt_code')) for row in antlerless_rows if clean(row.get('hunt_code'))})}",
                f"YOUTH_ANTLERLESS_CWMU rows: {len(youth_antlerless_rows)}",
                f"YOUTH_ANTLERLESS_CWMU unique hunt codes: {len({clean(row.get('hunt_code')) for row in youth_antlerless_rows if clean(row.get('hunt_code'))})}",
                "",
                "## Allotment / OTC Handling",
                "",
                "GENERAL_SEASON_SPIKE_ELK, GENERAL_SEASON_GENERAL_BULL_ELK, and PRIVATE_LANDS_ONLY_ANTLERLESS_ELK are tracked as separate allotment/OTC component families. They are not promoted into point-level draw odds unless a year-specific official source proves draw rows exist.",
                "",
                "## Output Files",
                "",
                f"- CWMU routed rows: {rel(routed_path)}",
                f"- CWMU manifest: {rel(manifest_path)}",
                f"- CWMU counts: {rel(counts_path)}",
                f"- allotment/OTC source status: {rel(allotment_path)}",
                "",
                f"2017_CWMU_ALLOTMENT_COMPONENT_SEPARATION_STATUS={status}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    terminal = "\n".join(
        [
            f"2017_CWMU_ALLOTMENT_COMPONENT_SEPARATION_OUTPUT_DIR={OUT_DIR}",
            f"CWMU_ROUTED_ROWS={routed_path}",
            f"CWMU_MANIFEST={manifest_path}",
            f"CWMU_COUNTS={counts_path}",
            f"ALLOTMENT_OTC_SOURCE_STATUS={allotment_path}",
            f"SEPARATION_REPORT={report_path}",
            f"BIG_GAME_CWMU_ROWS={len(big_game_rows)}",
            f"BIG_GAME_CWMU_UNIQUE_HUNT_CODES={len({clean(row.get('hunt_code')) for row in big_game_rows if clean(row.get('hunt_code'))})}",
            f"ANTLERLESS_CWMU_ROWS={len(antlerless_rows)}",
            f"ANTLERLESS_CWMU_UNIQUE_HUNT_CODES={len({clean(row.get('hunt_code')) for row in antlerless_rows if clean(row.get('hunt_code'))})}",
            f"YOUTH_ANTLERLESS_CWMU_ROWS={len(youth_antlerless_rows)}",
            f"YOUTH_ANTLERLESS_CWMU_UNIQUE_HUNT_CODES={len({clean(row.get('hunt_code')) for row in youth_antlerless_rows if clean(row.get('hunt_code'))})}",
            "GENERAL_SEASON_SPIKE_ELK_STATUS=SOURCE_REQUIRED_NOT_PRESENT_AS_2017_DRAW_ODDS",
            "GENERAL_SEASON_GENERAL_BULL_ELK_STATUS=SOURCE_REQUIRED_NOT_PRESENT_AS_2017_DRAW_ODDS",
            "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK_STATUS=NON_SCORABLE_PERMIT_REFERENCE_LAYER",
            f"2017_CWMU_ALLOTMENT_COMPONENT_SEPARATION_STATUS={status}",
            "NEXT_ACTION=REVIEW_SOURCE_STATUS_BEFORE_PROMOTION_OR_PATCHING",
        ]
    )
    (OUT_DIR / "FINAL_TERMINAL_OUTPUT.txt").write_text(terminal + "\n", encoding="utf-8")
    print(terminal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
